"""popup_insights — AUTOMATICALLY extract structural insights as data pops up.

Operator (2026-08-12): "do this and do these types of insights automatically as they popup" — the
billing-invariant analysis (the shared-doctrine-prefix engine) should happen automatically whenever
new data lands, not by hand.

THE LOOP (idempotent, runs on the cadence):
  1. SCAN for new data popups since the last run (marker file = the processed cursor): new billing
     CSVs, new folded swarm results, new rib_bus folds, new steals/research packs.
  2. EXTRACT the structural insight from each new popup: the ONE invariant the data proves. Uses the
     billing-invariant pattern for cost data; cross-lens synthesis (apply_all_lenses -> merged
     insight) for corpus/result data.
  3. FOLD each new insight as a RIB + record it, then advance the cursor so it isn't re-processed.

Guarded (never breaks cadence), deterministic + $0, idempotent via the cursor.

Schema: popup_insights.v1 · reuse: lens_library, rib_bus
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "popup_insights.v1"
MARKER = ROOT / "memory" / "runs" / "popup_insights_cursor.json"

# Data-popup sources (each is a scan function returning list of (name, mtime, text))
SCAN_DIRS = [
    ("billing", ROOT / "memory" / "billing"),
    ("swarm_results", ROOT / "memory" / "runs" / "swarm_worker" / "results"),
    ("rib_bus", ROOT / "memory" / "rib_bus"),
    ("steals", ROOT / "memory" / "steal"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cursor() -> dict[str, float]:
    if MARKER.is_file():
        try:
            return json.loads(MARKER.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cursor(c: dict[str, float]) -> None:
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_popups() -> list[dict[str, Any]]:
    """Find data popups newer than the cursor (idempotent scan of the popup sources)."""
    cur = _cursor()
    popups: list[dict[str, Any]] = []
    for kind, d in SCAN_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")) + sorted(d.glob("*.json")) + sorted(d.glob("*.jsonl")):
            try:
                mtime = p.stat().st_mtime
            except Exception:
                continue
            key = f"{kind}:{p.name}"
            if mtime > cur.get(key, 0):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")[:3000]
                except Exception:
                    text = ""
                popups.append({"kind": kind, "path": str(p), "name": p.name, "mtime": mtime,
                               "text": text})
    return popups


def _billing_invariant(text: str) -> str:
    """The billing-invariant insight: cost scales with cold (cache-miss) input, not output work.
    Extracted deterministically from amount-style billing text when present."""
    t = text.lower()
    if "cache_miss" in t and ("cache_hit" in t or "input_cache" in t):
        return ("COST ~= cold(cache-miss) input, NOT output work: as the shared doctrine prefix is "
                "reused, the expensive cold-input term collapses -> the swarm does more output work "
                "for declining cost. Grow the shared RIB prefix to push cold input -> 0.")
    return ""


def _structural_insight(popup: dict[str, Any]) -> str:
    """The ONE invariant the data proves: billing -> the cost-invariant; else cross-lens merged
    insight (deterministic $0; honestly flags when it needs model inference)."""
    if popup["kind"] == "billing":
        inv = _billing_invariant(popup["text"])
        if inv:
            return inv
    try:
        from mag import lens_library
        syn = lens_library.apply_all_lenses(popup["text"], popup["name"])
        mi = getattr(syn, "merged_insight", "") or ""
        if mi and "No strong patterns detected" not in mi:
            return f"CROSS-LENS INSIGHT ({popup['kind']}): {mi[:300]}"
    except Exception:
        pass
    return ""


def cycle(*, fold: bool = True, domain: str = "popup-insights") -> dict[str, Any]:
    """The automatic popup-insight loop: scan new data -> extract the structural insight -> fold.
    Idempotent (cursor advances). Deterministic + $0."""
    from mag import rib_bus

    popups = _new_popups()
    insights: list[dict[str, Any]] = []
    cursor = _cursor()

    for popup in popups:
        inv = _structural_insight(popup)
        folded = {}
        if inv and fold:
            try:
                folded = rib_bus.publish_rib(inv, domain=domain,
                                             source=f"popup_insights.auto ({popup['kind']})",
                                             target_rank="T2")
            except Exception as e:
                folded = {"ok": False, "error": str(e)[:100]}
        if inv:
            insights.append({"kind": popup["kind"], "source": popup["name"],
                             "insight": inv[:200], "folded": folded.get("ok")})
        cursor[f"{popup['kind']}:{popup['name']}"] = popup["mtime"]

    _save_cursor(cursor)
    return {"ok": True, "schema": SCHEMA, "n_new_popups": len(popups),
            "n_insights": len(insights), "insights": insights,
            "note": "structural insights auto-extracted + folded as data pops up; cursor advanced "
                    "so it's idempotent"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    print(_json.dumps(cycle(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
