r"""catalog_freshness -- the disclosure arm of the corpus map freshness policy.

Split out of mag/catalog_rescan.py at B2-104 landing (ratchet file-too-long
law: one module per arm). The C6 disease this arm closes: a snapshot map
answered every corpus tool as if current (the Sep-18 map scored qdrop 0 on
scan AND fts5 while watch/inbox/qdrop_export sat on disk; B2-22 re-proved
what the salon felt live). The cure has two halves: the rescan arm
(mag/catalog_rescan.py) keeps the map true, and THIS arm keeps the ANSWERS
honest between rescans -- every map-derived answer carries its as-of date
and a stale flag against the policy budget.

Contract:

  manifest_freshness(manifest, now_utc, map_mtime_utc)  pure verdict
  map_freshness(catalog_path, manifest_path)            IO wrapper
  corpus_status()                                       CLI print + dict

A missing or corrupt manifest can never read fresh: the asof falls back to
the map file's own mtime and the verdict is computed against the same
budget. The budget is read from the manifest when it carries one; the policy
default is STALENESS_BUDGET_HOURS = 48 (the salon felt 2-day staleness as a
live wound). The consumer is tools/corpus.py: search and stats answers
attach map_asof / map_age_hours / map_stale; byte-serving tools (get/tail)
stay unstamped because they hash the live bytes they serve and never quote
the map.
"""
from __future__ import annotations

import datetime
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(REPO, "catalog", "catalog.jsonl")
MANIFEST = os.path.join(REPO, "catalog", "catalog_manifest.json")

STALENESS_BUDGET_HOURS = 48


def _parse_iso(s):
    return datetime.datetime.strptime(
        str(s), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def manifest_freshness(manifest, now_utc, map_mtime_utc):
    """Pure freshness verdict. manifest: parsed dict or None."""
    asof = map_mtime_utc
    if isinstance(manifest, dict) and manifest.get("snapshot_ts"):
        try:
            asof = _parse_iso(manifest["snapshot_ts"])
        except ValueError:
            asof = map_mtime_utc
    budget = STALENESS_BUDGET_HOURS
    if isinstance(manifest, dict):
        try:
            budget = int(manifest.get("staleness_budget_hours", budget))
        except (TypeError, ValueError):
            budget = STALENESS_BUDGET_HOURS
    age_h = (now_utc - asof).total_seconds() / 3600.0
    return {"map_asof": asof.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "map_age_hours": round(age_h, 2),
            "map_stale": age_h > budget,
            "staleness_budget_hours": budget}


def map_freshness(catalog_path=CATALOG, manifest_path=MANIFEST):
    """IO wrapper: read the manifest + stat the map, return the verdict."""
    manifest = None
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            manifest = loaded
    except (OSError, json.JSONDecodeError, ValueError):
        manifest = None
    map_mt = datetime.datetime.fromtimestamp(
        os.stat(catalog_path).st_mtime, datetime.timezone.utc)
    return manifest_freshness(
        manifest, datetime.datetime.now(datetime.timezone.utc), map_mt)


def corpus_status(catalog_path=CATALOG, manifest_path=MANIFEST):
    """Print and return the standing freshness verdict for the map."""
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        manifest = None
    verdict = map_freshness(catalog_path, manifest_path)
    out = {"ok": True, "tool": "corpus_status", "manifest": manifest,
           "freshness": verdict}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out
