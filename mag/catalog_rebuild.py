r"""catalog_rebuild -- idempotent full-estate catalog rebuild (v3, landed 2026-09-26).

This is the salon Appendix A draft landed at last (landing checklist was:
save as mag/catalog_rebuild.py, run --dry, real run, then run twice and diff
row counts; watch/inbox/CORPUS_MAP_SALON_20260918.md:212-216, 391-405). The
2026-09-18 execution ran this logic inline and hook-blocked the module; the
map has been rebuildable only by retelling the inline code since.

Disease this module cures (measured, not assumed):

  v2 opened catalog.jsonl in append mode, so every re-run doubled the file
  (salon S7 measured AGENTS.md twice in the Sep-16 catalog, 946,773 rows).
  v3 writes a sibling temp and atomically replaces, deduping paths within
  the run.

Path-anchoring law (B2-103 census, 2026-09-26):

  ONE walk root, therefore ONE id per path string. The walk root is the
  projects/ estate root (mag.catalog_scan.ROOT), never the repo dir and
  never the cwd: a drifted root is what let one physical file carry two
  ids (id = sha256(path)[:12], so the id is only as stable as the anchor).
  The census of the Sep-18 map found zero duplicate ids and zero run seams
  (it was a single projects-root walk), but three anchor CLASSES live under
  that one root and every consumer must know them:

    local_sovereign_agent/...            the repo itself (723,676 rows)
    <sibling-top>/...                    sibling projects: azerothcore-wow,
                                         mycelial-republic, world_key, ...
                                         (zone ext:<top>)
    <loose file at the projects root>    strays such as AGENTS.md (a byte-
                                         different twin of the repo's own
                                         AGENTS.md), receipt pngs (zone
                                         vault per the B2-76 walker spec;
                                         the Sep-18 inline walk called them
                                         ext:<name>)

  The census receipt:
  watch/inbox/burn_wave_20260926/B2_103_path_census_20260926.md

Walk policy: imported from mag.catalog_scan (B2-76), single source of truth
for the junction law: reparse-point directories are pruned from traversal
and recorded to catalog/junctions.jsonl, reparse-point files are emitted
from lstat bytes and never opened (XIDIG-WIN-* law, P1-P5 in that
module's spec). Machinery dirs (.git, .venv, node_modules, __pycache__,
.mimosa, ...) are excluded at walk time and counted in the summary.

Row schema is unchanged from the Sep-18 map:
  {id, path, bytes, mtime, zone, ext, title, age_days}
age_days is evaluated at walk time (derived data inside a derived row; the
tags pass and the FTS5 spike read it).

Sidecars: catalog/junctions.jsonl is atomically replaced from the same
walk, so a rebuild leaves catalog.jsonl + junctions.jsonl consistent with
each other. tags.jsonl and catalog_fts.sqlite are NOT refreshed here
(Appendix B law: re-run the tag pass after every catalog rebuild; filed as
burn-wave self-feed B2-481).

The catalog is derived data and this write is a full re-derivation: no
unique bytes pass through this module, it only ever reads.

Deterministic, read-only over the walked files, $0. Run:
.venv/Scripts/python.exe -m mag.catalog_rebuild [--dry]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os

from mag.catalog_scan import LSA, ROOT, scan_tree

OUT = os.path.join(LSA, "catalog", "catalog.jsonl")
TMP = OUT + ".rebuild.tmp"
JUNCTIONS_OUT = os.path.join(LSA, "catalog", "junctions.jsonl")
JUNCTIONS_TMP = JUNCTIONS_OUT + ".rebuild.tmp"


def _with_age_days(row):
    """Schema parity with the Sep-18 map: add walk-time age_days."""
    out = dict(row)
    try:
        mtime = datetime.datetime.strptime(out["mtime"], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        out["age_days"] = (now - mtime).days
    except (KeyError, ValueError, TypeError):
        out["age_days"] = -1
    return out


def rebuild(dry=False):
    """One full-estate walk; returns the summary dict.

    dry=True counts only and writes nothing. dry=False streams rows into
    sibling temps and atomically replaces catalog.jsonl and
    junctions.jsonl on success (a failed walk leaves the old map standing).
    """
    stats = {}
    cat = jun = None
    if not dry:
        cat = open(TMP, "w", encoding="utf-8", newline="\n")
        jun = open(JUNCTIONS_TMP, "w", encoding="utf-8", newline="\n")
    try:
        for kind, payload in scan_tree(ROOT, stats, onerror=lambda e: None):
            if kind == "row":
                if cat is not None:
                    cat.write(json.dumps(_with_age_days(payload),
                                         ensure_ascii=False) + "\n")
            elif jun is not None:
                jun.write(json.dumps(payload, ensure_ascii=False) + "\n")
    finally:
        for fh in (cat, jun):
            if fh is not None:
                fh.close()
        if dry:
            for tmp in (TMP, JUNCTIONS_TMP):
                if os.path.exists(tmp):
                    os.unlink(tmp)
    if not dry:
        os.replace(TMP, OUT)
        os.replace(JUNCTIONS_TMP, JUNCTIONS_OUT)
    return {
        "ok": True,
        "mode": "dry" if dry else "replace",
        "walk_root": ROOT,
        "rows": stats.get("rows", 0),
        "dups_skipped": stats.get("dups", 0),
        "junction_records": stats.get("records", 0),
        "reparse_dirs": stats.get("reparse_dirs", 0),
        "reparse_files": stats.get("reparse_files", 0),
        "machinery_dirs_excluded": stats.get("machinery_dirs_excluded", 0),
        "out": OUT,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="catalog-rebuild")
    ap.add_argument("--dry", action="store_true",
                    help="counts only, no writes")
    args = ap.parse_args(argv)
    t0 = datetime.datetime.now(datetime.timezone.utc)
    summary = rebuild(dry=args.dry)
    summary["elapsed_s"] = round(
        (datetime.datetime.now(datetime.timezone.utc) - t0).total_seconds(), 1)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
