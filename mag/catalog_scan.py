r"""catalog_scan -- full-estate walker for the catalog (v3, junction policy).

Walks the entire local_sovereign_agent tree (minus machinery), emits one
catalog row per file into catalog/catalog.jsonl, and one reparse-point row
per junction or symlink into catalog/junctions.jsonl. Machinery dirs (.git,
.venv, node_modules, __pycache__, .mimosa) are excluded at walk time and
COUNTED in the summary, so the census accounts for what it skipped.

## Junction policy (v3 spec, landed 2026-09-26 by burn lane B2-76)

History: v2 walked junctions and counted duplicate trees; the 2026-09-18
inline v3 walk pruned them (catalog 946,773 -> 757,667 rows, delta
-189,106; watch/inbox/CORPUS_MAP_SALON_20260918.md execution receipt,
catalog/TAG_REPORT.md:3). Full attribution of that delta to the junction
was filed Unproven, and SOCRATIC_GAPS_20260918.md asks whether the pruned
rows were a duplicate or a deliberate mount. This module replaces the
inline walk: the prune is now codified policy with a ledger, never a
silent preference for the smaller number.

Law sources (watch/inbox/LINKS.jsonl XIDIG-WIN-* 2026-09-26T11:53:49Z,
Microsoft Learn, verified-live):

  XIDIG-WIN-REPARSE-LAW     reparse data incl. tag and GUID <= 16 KB;
                            63 reparse points per path (31 when the
                            target is fully qualified); a directory must
                            be empty to take a reparse point.
  XIDIG-WIN-JUNCTION-RULES  a junction links directories only, may cross
                            local volumes, and may NOT reference mapped
                            network volumes or files; junctions are
                            implemented through reparse points.
  XIDIG-WIN-SYMLINK-RULES   contrast: a symlink MAY point directly at a
                            remote UNC path; a relative symlink is
                            restricted to a single volume.

Consequences coded here:

  P1  Every kept directory entry is lstat-checked; a reparse point is
      recorded to junctions.jsonl and PRUNED from traversal (never
      descended, so a mirrored tree is counted once, at its real path).
      os.walk on Python 3.11 does not treat junctions as links, so the
      prune is the walker's own job; that gap is exactly how v2 double-
      counted.
  P2  A FILE carrying the reparse attribute is recorded the same way and
      emitted from its lstat bytes: never followed, never opened for a
      title read. A UNC target can hang the open, and the reparse
      payload is legally <= 16 KB (XIDIG-WIN-REPARSE-LAW); it is not
      file content.
  P3  The recorded target is classified: device_local (\\?\C:\... win32
      device namespace, still a local volume, NOT network), local_volume
      (C:\...), unc_remote (\\server\share or \\?\UNC\...), relative, or
      over_cap (the target repr alone exceeds the 16 KB reparse-data
      law, so it cannot be a valid payload). A junction classified
      unc_remote violates XIDIG-WIN-JUNCTION-RULES and is flagged
      violation=true; a symlink with the same class is legal by
      XIDIG-WIN-SYMLINK-RULES and carries the contrast note instead.
  P4  The 63/31 chain limits are bounds, not runtime branches: because
      P1 prunes every reparse directory, a walked path contains at most
      one reparse component (the pruned node itself), strictly under
      the limit. Any future mirror-builder that CREATES reparse points
      owns those limits and the empty-directory rule.
  P5  Rows are deduped by relpath inside one walk (the inline v3 walk
      skipped 24 in-walk dups); the count is reported, never swallowed.

The junctions.jsonl sidecar is the duplicate-vs-mirror instrument: each
row carries path, tag, target and class, so the junction diff
SOCRATIC_GAPS_20260918.md asked for (walk the target, compare bytes) is
runnable against filed rows instead of staying Unproven.

Row schema of catalog.jsonl is unchanged from v2. Write mode stays
append (a rebuild-replace is an operator-invoked flow, see the 2026-09-18
salon receipt). Deterministic, read-only over the files, $0. Run:
.venv/Scripts/python.exe -m mag.catalog_scan
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat
import sys

ROOT = r"C:\Users\ESTATE_USER\Documents\projects"
LSA = os.path.join(ROOT, "local_sovereign_agent")
OUT = os.path.join(LSA, "catalog", "catalog.jsonl")
JUNCTIONS_OUT = os.path.join(LSA, "catalog", "junctions.jsonl")
EXCLUDE = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mimosa",
           ".ruff_cache", ".pytest_cache", ".idea", ".vscode", "catalog"}

# --- Junction policy constants (law: XIDIG-WIN-* 2026-09-26, see spec) ----
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003   # junction / mounted folder
IO_REPARSE_TAG_SYMLINK = 0xA0000000
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
REPARSE_DATA_CAP_BYTES = 16 * 1024        # tag + GUID + data <= 16 KB
REPARSE_POINTS_PER_PATH_LIMIT = 63        # 31 when target fully qualified
REPARSE_POINTS_PER_PATH_LIMIT_FQ = 31

ZONE_MAP = [
    ("local_sovereign_agent/watch/inbox", "intake"),
    ("local_sovereign_agent/watch/astra_hold0", "astra"),
    ("local_sovereign_agent/watch/", "watch"),
    ("local_sovereign_agent/basecamp", "basecamp"),
    ("local_sovereign_agent/campaigns", "campaigns"),
    ("local_sovereign_agent/docs/", "doctrine"),
    ("local_sovereign_agent/memory/runs", "runs"),
    ("local_sovereign_agent/memory/", "memory"),
    ("local_sovereign_agent/mag/", "code"),
    ("local_sovereign_agent/tests/", "code"),
    ("local_sovereign_agent/scripts/", "code"),
    ("local_sovereign_agent/configs/", "code"),
    ("local_sovereign_agent/dashboard/static/games", "games"),
    ("local_sovereign_agent/dashboard/", "dashboard"),
    ("local_sovereign_agent/research/", "research"),
    ("local_sovereign_agent/queue/", "queue"),
    ("local_sovereign_agent/catalog/", "catalog"),
    ("local_sovereign_agent/", "lsa"),
]


def zone_of(relpath):
    p = relpath.replace("\\", "/").lower()
    for prefix, zone in ZONE_MAP:
        if p.startswith(prefix):
            return zone
    top = p.split("/")[0] if "/" in p else p
    return "ext:" + top[:16]


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def classify_target(target):
    """Classify a reparse target string per the XIDIG-WIN law.

    Returns (target_class, note). The junction/symlink violation split is
    applied by reparse_record, which knows the kind: unc_remote is a
    violation for a junction (XIDIG-WIN-JUNCTION-RULES) and legal for a
    symlink (XIDIG-WIN-SYMLINK-RULES contrast).
    """
    if len(target.encode("utf-8", "replace")) > REPARSE_DATA_CAP_BYTES:
        return "over_cap", ("target repr exceeds the 16 KB reparse-data law "
                            "(XIDIG-WIN-REPARSE-LAW)")
    if target.startswith("\\\\?\\UNC\\"):
        return "unc_remote", "device UNC path (network)"
    if target.startswith("\\\\?\\"):
        rest = target[4:]
        if len(rest) >= 2 and rest[1] == ":":
            return "device_local", ("win32 device namespace, local volume "
                                    "(not network)")
        return "unc_remote", "device path without a drive letter"
    if target.startswith("\\\\"):
        return "unc_remote", "UNC server-share path (network)"
    if len(target) >= 2 and target[1] == ":":
        return "local_volume", "drive-letter target on a local volume"
    return "relative", ("relative target (single-volume rule, "
                        "XIDIG-WIN-SYMLINK-RULES)")


def reparse_record(full, relpath, lst, is_dir):
    """Build one junctions.jsonl row for a reparse-point entry."""
    tag = getattr(lst, "st_reparse_tag", 0)
    try:
        target = os.readlink(full)
        cls, note = classify_target(target)
    except OSError as exc:
        target, cls, note = "", "unresolved", "readlink failed: %s" % exc

    if tag == IO_REPARSE_TAG_MOUNT_POINT:
        kind = "junction"
    elif tag == IO_REPARSE_TAG_SYMLINK:
        kind = "symlink"
    else:
        kind = "tag_0x%08X" % tag

    violation = False
    if kind == "junction":
        if cls in ("unc_remote", "over_cap"):
            violation = True
            note += " (XIDIG-WIN-JUNCTION-RULES: never network)"
        if not is_dir:
            violation = True
            note += (" (XIDIG-WIN-JUNCTION-RULES: junctions link "
                     "directories only, never files)")
    elif kind == "symlink" and cls == "unc_remote":
        note += (" (contrast, legal: a symlink may target UNC directly, "
                 "XIDIG-WIN-SYMLINK-RULES)")

    return {
        "id": hashlib.sha256(relpath.encode("utf-8", "replace")).hexdigest()[:12],
        "path": relpath,
        "kind": kind,
        "tag": "0x%08X" % tag,
        "is_dir": is_dir,
        "target": target,
        "target_class": cls,
        "violation": violation,
        "action": "pruned" if is_dir else "recorded_no_follow",
        "note": note,
        "reparse_data_cap_bytes": REPARSE_DATA_CAP_BYTES,
        "path_limit_law": "63 per path, 31 fully qualified target",
        "ts": _now(),
    }


def _title_from_file(full, fallback):
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#"):
                    return line.lstrip("# ").strip()[:110]
                if line:
                    return line[:110]
    except OSError:
        pass
    return fallback


def scan_tree(root, stats, onerror=None):
    """Stream walk events from root: ("row", catalog_row) and
    ("record", junction_ledger_row). Fills stats:
    rows, dups, records, reparse_dirs, reparse_files,
    machinery_dirs_excluded. Never descends into reparse dirs (P1);
    never follows or opens reparse files (P2).
    """
    for key in ("rows", "dups", "records", "reparse_dirs", "reparse_files",
                "machinery_dirs_excluded"):
        stats.setdefault(key, 0)
    seen = set()
    for dp, dns, fns in os.walk(root, onerror=onerror):
        try:
            rel = os.path.relpath(dp, root)
        except ValueError:
            dns[:] = []
            continue
        if rel == ".":
            rel = ""
        if "\\\\" in rel or "\\.\\" in rel:
            dns[:] = []
            continue

        keep = []
        for d in dns:
            if d in EXCLUDE or d.startswith("."):
                stats["machinery_dirs_excluded"] += 1
                continue
            full = os.path.join(dp, d)
            try:
                lst = os.lstat(full)
            except OSError:
                continue
            if getattr(lst, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                relp = (rel + "/" + d).replace("\\", "/") if rel else d
                stats["records"] += 1
                stats["reparse_dirs"] += 1
                yield ("record", reparse_record(full, relp, lst, True))
            else:
                keep.append(d)
        dns[:] = keep

        z = zone_of(rel) if rel else "vault"
        for fn in fns:
            full = os.path.join(dp, fn)
            try:
                relfile = os.path.relpath(full, root).replace("\\", "/")
            except (ValueError, OSError):
                continue
            if "\\.\\" in relfile or "\\\\.\\\\" in relfile:
                continue
            if relfile in seen:
                stats["dups"] += 1
                continue
            seen.add(relfile)
            try:
                lst = os.lstat(full)
            except OSError:
                continue
            followed = False
            try:
                lst = os.lstat(full)
            except OSError:
                continue
            if getattr(lst, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                stats["records"] += 1
                stats["reparse_files"] += 1
                yield ("record", reparse_record(full, relfile, lst, False))
                st = lst                      # P2: lstat bytes, never follow
            else:
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                followed = True
            title = fn[:110]
            ext = os.path.splitext(fn)[1].lower()
            if ext in (".md", ".txt") and followed:
                title = _title_from_file(full, title)
            rid = hashlib.sha256(relfile.encode("utf-8", "replace")).hexdigest()[:12]
            mtime = datetime.datetime.utcfromtimestamp(st.st_mtime).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            stats["rows"] += 1
            yield ("row", {"id": rid, "path": relfile, "bytes": st.st_size,
                           "mtime": mtime, "zone": z, "ext": ext,
                           "title": title})
            if stats["rows"] % 100000 == 0:
                print("  ...%d rows" % stats["rows"], flush=True)


def main():
    stats = {"rows": 0, "dups": 0, "records": 0, "reparse_dirs": 0,
             "reparse_files": 0, "machinery_dirs_excluded": 0}
    with open(OUT, "a", encoding="utf-8", newline="\n") as cat, \
         open(JUNCTIONS_OUT, "a", encoding="utf-8", newline="\n") as jun:
        for kind, payload in scan_tree(ROOT, stats, onerror=lambda e: None):
            if kind == "row":
                cat.write(json.dumps(payload, ensure_ascii=False) + "\n")
            else:
                jun.write(json.dumps(payload, ensure_ascii=False) + "\n")
    classes = {}
    print("TOTAL rows: %d" % stats["rows"])
    print("in-walk dup rows skipped: %d" % stats["dups"])
    print("reparse points recorded: %d (pruned dirs %d, no-follow files %d)"
          % (stats["records"], stats["reparse_dirs"], stats["reparse_files"]))
    print("machinery dirs excluded: %d (%s)"
          % (stats["machinery_dirs_excluded"], ", ".join(sorted(EXCLUDE))))
    print("junction ledger: %s" % os.path.relpath(JUNCTIONS_OUT, LSA))


if __name__ == "__main__":
    main()
