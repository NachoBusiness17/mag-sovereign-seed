r"""catalog_rescan -- corpus map freshness policy (C6), landed 2026-09-26 by B2-104.

## The disease (proven twice on bytes)

The corpus map (catalog/catalog.jsonl) is a snapshot. Every map-derived answer
was a snapshot-date answer served as if current: the salon felt it live
(watch/inbox/CORPUS_MAP_SALON_20260918.md C6, "ruins go" 0 hits on the Sep-16
map while corpus_get served the two-day-old bytes) and B2-22 re-proved it on
the Sep-18 map ("qdrop" 0 hits on BOTH scan and FTS5). B2-506 correction
(2026-09-26): the "rows_scanned 757667" figure often quoted beside that B2-22
result is true only under PRE-wiring scan semantics (a full-map walk count);
after the engine split, a fresh-index qdrop search reports rows_scanned 0
walked (the answer is known from the index), and 757,667 reappears only on
the stale-scan arm, where the early-break usually stops far earlier. The
snapshot-datedness lesson stands either way: watch/inbox/qdrop_export
postdated the snapshot, so the map answered a world without it. A week-old
estate answered every corpus tool. The salon demanded: a refresh policy
(incremental rescan or scheduled rebuild) ships. This module is that policy.

## Policy decision (this spec is the C1-swap companion the salon named)

Three arms, one chain, all local, $0, no daemon (salon C3 forbids a resident
indexer; the long-lived-daemon graveyard stands). One module per arm, split
at landing per the ratchet file-too-long law:

  1. INCREMENTAL RESCAN (frequent arm, this module, default). Walk the
     projects-parent tree with the map's own lineage rules (ROOT, EXCLUDE
     set, zone map and junction policy P1/P2 all inherited from
     mag.catalog_scan, so the map never indexes itself), compare each disk
     file against the base map by the signature (bytes, mtime), and APPEND
     one fresh row per new or changed path. Append stays the map's write law
     (v3: "write mode stays append"); readers already resolve last-row-wins
     by path, and compaction (arm 2) materializes it. Deletions are never
     tombstoned: they are COUNTED as vanished in the manifest and resolved
     at the next rebuild, so no reader learns a new row shape.
  2. DATED REBUILD (periodic arm, this module, operator-invoked or after
     large drift). Full walk to a temp file, archive the current map as
     catalog/catalog_<prev-snapshot-date>.jsonl, then one atomic os.replace
     (the exact flow the 2026-09-18 inline v3 walk used). Vanished paths
     drop out here; in-walk duplicate paths are skipped and counted (v3 P5).
  3. TAGS RE-RUN (mag/catalog_tags.py; always after a map byte change; the
     salon Appendix B law "the tags sidecar is derived data: re-run after
     every catalog rebuild"). Streams the map, applies the kind rules
     verbatim, rewrites catalog/tags.jsonl via temp+replace and a dated
     catalog/TAG_REPORT.md (previous report preserved once, dated).

Every map arm ends by writing catalog/catalog_manifest.json (snapshot_ts,
mode, counts, map bytes + sha256, tags_ts, kind/age counts, budget). The
DISCLOSURE arm (mag/catalog_freshness.py) makes readers honest between
rescans: corpus_search and corpus_stats answers carry map_asof /
map_age_hours / map_stale from the manifest; a missing manifest can never
read fresh (the map file's own mtime becomes the asof). Budget 48h: the
salon felt 2-day staleness as a live wound, so the nightly cadence must
keep the map under two days old or every tool says so.

## Who fires it

MagCorpusRescanDaily, a Windows Task Scheduler task registered by
scripts/register_corpus_rescan_task.ps1 (the MagImproveDaily house pattern),
03:30 local, running the repo venv interpreter:
  .venv\\Scripts\\python.exe -m mag.catalog_rescan incremental
A local janitor fires it, not an LLM lane (tier law: local first). Any seat
can force the same command by hand; corpus_status prints the verdict.

## Composition with the FTS query plane (B2-22 spike, B2-102 wiring)

After any map byte change, catalog/catalog_fts.sqlite is stale by
construction. B2-102's db-vs-map gate stays honest (falls back to scan and
says so) until tools/corpus_fts_rebuild.py runs; this module never touches
the index. The nightly chain is therefore: rescan (here) keeps the MAP true,
the FTS rebuild (B2-102's documented entry point) keeps the INDEX true, the
tags sidecar rides arm 3, and both disclosures ride the tools.

Confined and read-only over file contents: the only bytes opened are .md/.txt
title heads, exactly like the base scan. Run:
  .venv/Scripts/python.exe -m mag.catalog_rescan incremental|rebuild|tags|status
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from mag.catalog_scan import (  # noqa: E402  (the map's own walker lineage)
    EXCLUDE,
    FILE_ATTRIBUTE_REPARSE_POINT,
    ROOT,
    _title_from_file,
    reparse_record,
    zone_of,
)
from mag.catalog_freshness import corpus_status  # noqa: E402  (disclosure arm)
from mag.catalog_tags import (  # noqa: E402  (tags arm)
    run_tags,
    write_tag_report,
)

CATALOG = os.path.join(REPO, "catalog", "catalog.jsonl")
MANIFEST = os.path.join(REPO, "catalog", "catalog_manifest.json")
JUNCTIONS = os.path.join(REPO, "catalog", "junctions.jsonl")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _sig(bytes_, mtime_iso):
    return (bytes_, mtime_iso)


def load_index(catalog_path=CATALOG):
    """path -> (bytes, mtime) signature, last row wins per path.

    Returns (index, base_rows, base_dups): base_rows counts every parsed
    line, base_dups counts extra rows for a path already seen (v3 P5 spirit;
    the 2026-09-26 map carries 158 of them -- the append-mode dup disease
    the dated rebuild exists to compact).
    """
    index = {}
    base_rows = 0
    base_dups = 0
    with open(catalog_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            base_rows += 1
            p = str(row.get("path", ""))
            if not p:
                continue
            if p in index:
                base_dups += 1
            index[p] = _sig(row.get("bytes"), str(row.get("mtime", "")))
    return index, base_rows, base_dups


def walk_disk(root=ROOT):
    """Stream ("row", row_dict, sig), ("record", junction_row, None) and
    ("done", stats, None) events.

    Same walk contract as the map's lineage (the projects parent, see
    mag.catalog_scan.ROOT): EXCLUDE set (the map never indexes itself),
    reparse dirs pruned and journalled (P1), reparse files journalled and
    never opened (P2), in-walk duplicate paths skipped and counted (P5).
    Paths are root-relative exactly as the map stores them, zones from the
    v3 ZONE_MAP (mag.catalog_scan.zone_of), row schema kept identical to the
    filed rows (id, path, bytes, mtime, zone, ext, title, age_days).
    """
    seen = set()
    stats = {"rows": 0, "dups": 0, "records": 0, "reparse_dirs": 0,
             "reparse_files": 0, "machinery_dirs_excluded": 0}
    for dp, dns, fns in os.walk(root, onerror=lambda e: None):
        try:
            rel = os.path.relpath(dp, root)
        except ValueError:
            dns[:] = []  # device-space directory (the \\.\nul class): skip
            continue
        rel = "" if rel == "." else rel.replace("\\", "/")
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
                relp = (rel + "/" + d) if rel else d
                stats["records"] += 1
                stats["reparse_dirs"] += 1
                yield ("record", reparse_record(full, relp, lst, True), None)
            else:
                keep.append(d)
        dns[:] = keep

        for fn in fns:
            full = os.path.join(dp, fn)
            try:
                relfile = os.path.relpath(full, root).replace("\\", "/")
            except (ValueError, OSError):
                continue
            if "\\.\\" in relfile or "\\\\" in relfile:
                continue
            if relfile in seen:
                stats["dups"] += 1
                continue
            seen.add(relfile)
            try:
                lst = os.lstat(full)
            except OSError:
                continue
            if getattr(lst, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                stats["records"] += 1
                stats["reparse_files"] += 1
                yield ("record", reparse_record(full, relfile, lst, False), None)
                continue  # P2: lstat bytes, never follow, never a catalog row
            try:
                st = os.stat(full)
            except OSError:
                continue
            ext = os.path.splitext(fn)[1].lower()
            title = fn[:110]
            if ext in (".md", ".txt"):
                title = _title_from_file(full, title)
            mt_dt = datetime.datetime.fromtimestamp(
                st.st_mtime, datetime.timezone.utc)
            mtime = mt_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            rid = hashlib.sha256(
                relfile.encode("utf-8", "replace")).hexdigest()[:12]
            row = {"id": rid, "path": relfile, "bytes": st.st_size,
                   "mtime": mtime, "zone": zone_of(relfile), "ext": ext,
                   "title": title,
                   "age_days": (datetime.datetime.now(
                       datetime.timezone.utc) - mt_dt).days}
            stats["rows"] += 1
            yield ("row", row, _sig(st.st_size, mtime))
    yield ("done", stats, None)


def incremental(catalog_path=CATALOG, junctions_path=JUNCTIONS, root=ROOT):
    """Append one fresh row per new or changed path; count the rest."""
    index, base_rows, base_dups = load_index(catalog_path)
    added = refreshed = unchanged = 0
    seen_paths = set()
    walk_stats = {"dups": 0, "records": 0, "machinery_dirs_excluded": 0}
    with open(catalog_path, "a", encoding="utf-8", newline="\n") as cat, \
         open(junctions_path, "a", encoding="utf-8", newline="\n") as jun:
        for kind, payload, sigv in walk_disk(root):
            if kind == "record":
                jun.write(json.dumps(payload, ensure_ascii=False) + "\n")
                continue
            if kind == "done":
                walk_stats = payload
                break
            row = payload
            seen_paths.add(row["path"])
            prev = index.get(row["path"])
            if prev is not None and prev == sigv:
                unchanged += 1
                continue
            cat.write(json.dumps(row, ensure_ascii=False) + "\n")
            if prev is None:
                added += 1
            else:
                refreshed += 1
    vanished = len(set(index) - seen_paths)
    return {"mode": "incremental", "base_rows": base_rows,
            "base_dups": base_dups, "added": added, "refreshed": refreshed,
            "unchanged": unchanged, "vanished": vanished,
            "reparse_records": walk_stats["records"],
            "walk_dups": walk_stats["dups"],
            "machinery_dirs_excluded": walk_stats["machinery_dirs_excluded"]}


def rebuild(catalog_path=CATALOG, junctions_path=JUNCTIONS,
            manifest_path=MANIFEST, root=ROOT):
    """Full walk to temp, archive the old map by its snapshot date, replace."""
    tmp = catalog_path + ".rebuild"
    rows = 0
    walk_stats = {"dups": 0, "records": 0, "machinery_dirs_excluded": 0}
    with open(tmp, "w", encoding="utf-8", newline="\n") as cat, \
         open(junctions_path, "a", encoding="utf-8", newline="\n") as jun:
        for kind, payload, _sigv in walk_disk(root):
            if kind == "record":
                jun.write(json.dumps(payload, ensure_ascii=False) + "\n")
                continue
            if kind == "done":
                walk_stats = payload
                break
            cat.write(json.dumps(payload, ensure_ascii=False) + "\n")
            rows += 1
    prev_date = None
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            prev_date = str(json.load(fh).get("snapshot_ts", ""))[:10]
    except (OSError, json.JSONDecodeError, ValueError):
        prev_date = None
    if not prev_date:
        prev_date = datetime.datetime.fromtimestamp(
            os.stat(catalog_path).st_mtime,
            datetime.timezone.utc).strftime("%Y-%m-%d")
    archive = os.path.join(REPO, "catalog", "catalog_%s.jsonl" % prev_date)
    if os.path.exists(archive):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S")
        archive = "%s_%s.jsonl" % (archive[:-6], stamp)
    os.replace(catalog_path, archive)
    os.replace(tmp, catalog_path)
    return {"mode": "rebuild", "rows": rows, "archive": archive,
            "reparse_records": walk_stats["records"],
            "walk_dups": walk_stats["dups"],
            "machinery_dirs_excluded": walk_stats["machinery_dirs_excluded"]}


def _map_sha(path=CATALOG):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(summary, retag=True, manifest_path=MANIFEST,
                   catalog_path=CATALOG):
    """Stamp the manifest; by default run the tags arm first (salon law)."""
    prev = {}
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            prev = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        prev = {}
    tags_ts = None
    kinds = ages = None
    if retag:
        t = run_tags(catalog_path)
        tags_ts = _now_iso()
        kinds, ages = t["kinds"], t["ages"]
        summary["tags_rows"] = t["rows"]
        write_tag_report(t)
    manifest = {
        "policy": "B2-104 C6 freshness: incremental rescan + dated rebuild "
                  "+ tags re-run; readers disclose map_asof/map_stale",
        "snapshot_ts": _now_iso(),
        "mode": summary.get("mode"),
        "prev_snapshot_ts": prev.get("snapshot_ts"),
        "summary": summary,
        "map_bytes": os.stat(catalog_path).st_size,
        "map_sha256": _map_sha(catalog_path),
        "tags_ts": tags_ts,
        "kind_counts": kinds,
        "age_counts": ages,
        "staleness_budget_hours": 48,
        "scheduler": "MagCorpusRescanDaily 03:30 local (Task Scheduler, "
                     "repo venv python -m mag.catalog_rescan incremental)",
    }
    tmp = manifest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, manifest_path)
    return manifest


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = argv[0] if argv else "incremental"
    skip_tags = "--no-tags" in argv
    if mode == "status":
        corpus_status()
        return 0
    if mode == "tags":
        manifest = write_manifest({"mode": "tags"}, retag=True)
        print(json.dumps({"ok": True, "mode": "tags",
                          "tags_rows": manifest["summary"]["tags_rows"]}))
        return 0
    if mode == "rebuild":
        summary = rebuild()
    elif mode == "incremental":
        summary = incremental()
    else:
        print("unknown mode: %s (incremental|rebuild|tags|status)" % mode)
        return 2
    manifest = write_manifest(summary, retag=not skip_tags)
    print(json.dumps({"ok": True, "mode": manifest["mode"],
                      "summary": summary,
                      "map_bytes": manifest["map_bytes"],
                      "map_sha256": manifest["map_sha256"][:12],
                      "tags_ts": manifest["tags_ts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
