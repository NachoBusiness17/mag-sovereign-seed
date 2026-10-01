r"""catalog_tags -- the tag pass arm of the corpus map freshness policy.

Split out of mag/catalog_rescan.py at B2-104 landing (ratchet file-too-long
law: one module per arm). This module owns the salon Appendix B transcription
and nothing else:

Kind rules (watch/inbox/CORPUS_MAP_SALON_20260918.md, Appendix B, first
match, path+ext only): card = watch/*_YYYYMMDD.md; receipt = name/parent says
receipt; ledger = .jsonl; state = state/*.json; brief = memory/briefs/*.md;
corpus = memory/{corpus,research_packs,archaeology,ingest} texts; test =
test_*; code (.py .js .mjs .ts .ps1 .sh .cmd .bat .sql); image; config;
prose (.md); other. Rules apply to the LSA-relative view of the stored path
(the map walks the projects parent, so repo files carry the
local_sovereign_agent/ prefix; the salon rules were written repo-relative).

Age classes: fresh <7d, aging <30d, stale <64d, fossil >=64d (mtime, AT RUN
TIME, so ages move by design). Kind counts over an unchanged base must be
stable run to run; the Sep-18 base they were tuned against was replaced
mid-lane 2026-09-26 (489,038 rows) before parity could be pinned, so exact
count parity with TAG_REPORT v2 is Unproven -- the rules themselves are the
verbatim transcription and are pinned rule-by-rule in
tests/test_catalog_tags.py.

The tags sidecar is derived data: re-run after every catalog byte change
(salon law; this module is how).

Tags v2 (Q-031, 2026-09-28): rows carry an extra "owner" field, the owning
top-level surface of the stored path (owner_of below). The salon Appendix B
kind rules above are untouched; owner is additive metadata, distinct from
zone (zone buckets watch/inbox into intake and mag/tests/scripts/configs
into code, and masks non-repo projects as ext:<16 chars>; owner is the
exact untruncated owning directory or sibling project name).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAGS = os.path.join(REPO, "catalog", "tags.jsonl")
TAG_REPORT = os.path.join(REPO, "catalog", "TAG_REPORT.md")

_PFX = "local_sovereign_agent/"
_CODE_EXTS = {".py", ".js", ".mjs", ".ts", ".ps1", ".sh", ".cmd", ".bat", ".sql"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
               ".ico", ".tif", ".tiff"}
_CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
                ".xml", ".env", ".properties"}
_CORPUS_DIRS = ("memory/corpus/", "memory/research_packs/",
                "memory/archaeology/", "memory/ingest/")
_CORPUS_TEXT_EXTS = {".md", ".txt", ".rst", ".html", ".htm"}
_CARD_RE = re.compile(r"_\d{8}\.md$")


def classify_kind(path, ext):
    """One kind label per salon Appendix B, first match, path+ext only."""
    p = path.replace("\\", "/").lower()
    if p.startswith(_PFX):
        p = p[len(_PFX):]
    base = p.rsplit("/", 1)[-1]
    parent = p.rsplit("/", 2)[-2] if "/" in p else ""
    if p.startswith("watch/") and _CARD_RE.search(base):
        return "card"
    if "receipt" in base or "receipt" in parent:
        return "receipt"
    if ext == ".jsonl":
        return "ledger"
    if ext == ".json" and "/state/" in ("/" + p):
        return "state"
    if p.startswith("memory/briefs/") and ext == ".md":
        return "brief"
    if any(p.startswith(d) for d in _CORPUS_DIRS) and ext in _CORPUS_TEXT_EXTS:
        return "corpus"
    if base.startswith("test_"):
        return "test"
    if ext in _CODE_EXTS:
        return "code"
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _CONFIG_EXTS:
        return "config"
    if ext == ".md":
        return "prose"
    return "other"


def age_class_of(mtime_iso, now_utc=None):
    """fresh <7d, aging <30d, stale <64d, fossil >=64d (mtime, at run time)."""
    now = now_utc or datetime.datetime.now(datetime.timezone.utc)
    mt = datetime.datetime.strptime(mtime_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)
    days = (now - mt).days
    if days < 7:
        return "fresh"
    if days < 30:
        return "aging"
    if days < 64:
        return "stale"
    return "fossil"


def owner_of(path):
    """Tags v2 owner (Q-031): the owning top-level surface of a stored path.

    The map walks the projects parent, so repo files carry the
    local_sovereign_agent/ prefix (same strip classify_kind does);
    owner is the first path segment after that strip -- the repo's owning
    directory (mag, watch, docs, ...) for repo files, the sibling project
    name (hermes-agent, mycelial-republic, ...) for estate files outside
    the repo. A file at the top level with no owning directory owns
    "root". Preserves stored case; it is a join key, not a classifier.
    """
    p = path.replace("\\", "/")
    if p.lower().startswith(_PFX):
        p = p[len(_PFX):]
    if "/" not in p:
        return "root"
    return p.split("/", 1)[0]


def run_tags(catalog_path, tags_path=TAGS):
    """Re-run the tag pass over the given map; temp-write then replace.

    Tags v2 (Q-031): each row also carries "owner" (owner_of); the result
    reports the owner distribution alongside kinds and ages.
    """
    kinds = {}
    ages = {}
    owners = {}
    rows = 0
    tmp = tags_path + ".retag"
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    with open(catalog_path, encoding="utf-8") as cat, \
         open(tmp, "w", encoding="utf-8", newline="\n") as out:
        for line in cat:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            path = str(row.get("path", ""))
            if not path:
                continue
            ext = str(row.get("ext", "") or "")
            kind = classify_kind(path, ext)
            age = age_class_of(str(row.get("mtime", "")), now_utc)
            owner = owner_of(path)
            out.write(json.dumps(
                {"id": row.get("id"), "path": path,
                 "zone": row.get("zone"), "kind": kind,
                 "age_class": age, "bytes": row.get("bytes"),
                 "owner": owner},
                ensure_ascii=False) + "\n")
            kinds[kind] = kinds.get(kind, 0) + 1
            ages[age] = ages.get(age, 0) + 1
            owners[owner] = owners.get(owner, 0) + 1
            rows += 1
    os.replace(tmp, tags_path)
    return {"rows": rows, "kinds": kinds, "ages": ages, "owners": owners}


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def write_tag_report(tag_result, report_path=TAG_REPORT):
    """Rewrite TAG_REPORT.md; the previous dated report is preserved once."""
    prev_date = None
    try:
        with open(report_path, encoding="utf-8") as fh:
            head = fh.readline()
        m = re.search(r"(\d{4}-\d{2}-\d{2})", head)
        prev_date = m.group(1) if m else None
    except OSError:
        prev_date = None
    if prev_date:
        keep = os.path.join(REPO, "catalog",
                            "TAG_REPORT_%s.md" % prev_date.replace("-", ""))
        if not os.path.exists(keep):
            shutil.copy2(report_path, keep)
    kinds = tag_result["kinds"]
    ages = tag_result["ages"]
    owners = tag_result.get("owners", {})
    lines = [
        "# TAG REPORT -- corpus map (refreshed %s)" % _now_iso(),
        "",
        "Source: catalog/catalog.jsonl as of the manifest snapshot_ts; "
        "sidecar catalog/tags.jsonl via mag/catalog_tags.py (salon "
        "Appendix B kind rules, verbatim; tags v2 owner column since "
        "Q-031 2026-09-28). LAW: estimation must not replace "
        "the thing -- corpus_get the bytes before quoting.",
        "",
        "## Total tagged rows: %d" % tag_result["rows"],
        "",
        "## By kind",
    ]
    for k in sorted(kinds, key=lambda x: -kinds[x]):
        lines.append("- %s: %d" % (k, kinds[k]))
    lines += ["", "## By age (mtime at run time)", ""]
    for a in ("fresh", "aging", "stale", "fossil"):
        lines.append("- %s: %d" % (a, ages.get(a, 0)))
    lines += ["", "## By owner (tags v2, top 15)", ""]
    for o in sorted(owners, key=lambda x: -owners[x])[:15]:
        lines.append("- %s: %d" % (o, owners[o]))
    lines.append("")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
