"""flock_usage_guard — the RIB catches cost/cache-miss spikes BEFORE they happen, using flocking.

Operator (2026-08-11): "as a rule we need to monitor live api use data to catch this shit before
it hits" + "our rib should be able to catch these things before they happen using flocking within
our systems."

THE MECHANISM (deterministic + $0, no LLM, module functions only):
  - A cache-miss is a SEAM: a divergence point in the token stream (a mid-context edit changes the
    cache prefix -> the region after the first changed token MISSES at 50x). Flocking is EXACTLY a
    seam detector (flock_shader.seams = where agents/points diverge). We apply the SAME lens to the
    LIVE USAGE STREAM: a rising miss-rate / a first large-miss request is the leading edge of a
    burst, detected BEFORE the full threshold (and before the hourly bill).
  - guard_rib() folds the cache-preservation INSTRUCTION as a RIB (rib_bus.publish_rib, domain
    'usage-guard') so every cheap worker auto-carries it: preserve the stable prefix; route the
    volatile tail to cheap/free; a mid-context edit is a seam -> defer/route, don't pay 50x.
  - predict_seams(rows) — flock-style early seam detection on the live stream: flag a PREDICTED
    spike at a LOW early threshold (miss_ratio rising / a miss burst starting), BEFORE the hard
    threshold (usage_monitor/cost_learn MISS_SPIKE_THRESHOLD).
  - watch_and_guard() — fold the RIB once, then watch the live feed; on a predicted seam, publish a
    STEER RIB + fold a training signal immediately (cache_miss_predicted) — the 50x tax is caught
    before it hits the bill.

Schema: flock_usage_guard.v1 · deterministic + $0 · reuse: rib_bus, usage_monitor, cost_learn,
flock_shader (seam lens), behavioral_analytics.
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
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "flock_usage_guard.v1"
EARLY_RATIO = 0.05          # miss_ratio >= 5% in a window = EARLY seam (predict before hard threshold)
EARLY_MISS = 20_000         # or >= 20k miss tokens = leading edge of a burst
GUARD_RIB = ("Cache-preservation: keep the stable prefix immutable (invariant.py); a mid-context "
             "edit is a SEAM -> route the volatile tail to cheap/free, never pay the 50x miss price; "
             "preserve the cache prefix on every flock dispatch.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def guard_rib(*, fold: bool = True) -> dict[str, Any]:
    """Fold the cache-preservation guard as a RIB so every worker/flock carries it. $0."""
    if not fold:
        return {"ok": True, "schema": SCHEMA, "rib": GUARD_RIB, "folded": False}
    try:
        from mag import rib_bus
        r = rib_bus.publish_rib(GUARD_RIB, domain="usage-guard", source="flock_usage_guard",
                                target_rank="T2", fold=True, publish=True)
        return {"ok": True, "schema": SCHEMA, "rib": GUARD_RIB, "folded": True, "rib_bus": r}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "rib": GUARD_RIB, "folded": False, "error": str(e)[:160]}


def predict_seams(rows: list[dict[str, Any]] | None = None, *, window: int = 60) -> dict[str, Any]:
    """Flock-style EARLY seam detection on the live usage stream — predicts a spike before it hits.

    Reads the recent live feed (provider_usage.jsonl). A seam = the leading edge of a cache-miss
    burst: miss_ratio >= EARLY_RATIO OR a miss burst >= EARLY_MISS starting. This fires BEFORE the
    hard threshold (usage_monitor / cost_learn), so the guard can steer before the bill.
    """
    rows = rows if rows is not None else _read_recent()
    recent = rows[-window:] if len(rows) >= window else rows
    hit = sum(int(r.get("cache_hit_tokens") or 0) for r in recent)
    miss = sum(int(r.get("cache_miss_tokens") or 0) for r in recent)
    tin = hit + miss
    ratio = miss / tin if tin else 0.0
    seam = (miss >= EARLY_MISS) or (ratio >= EARLY_RATIO)
    return {"schema": SCHEMA, "ts": _now(), "rows_in_window": len(recent),
            "hit_tokens": int(hit), "miss_tokens": int(miss), "hit_ratio": round(hit / tin, 4) if tin else None,
            "predicted_spike": seam, "early_ratio": EARLY_RATIO, "early_miss": EARLY_MISS,
            "cause": "mid_context_edit_seam" if seam else "stable"}


def _read_recent(n: int = 2000) -> list[dict[str, Any]]:
    from mag.usage_monitor import USAGE
    if not USAGE.is_file():
        return []
    out = []
    try:
        for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def watch_and_guard(*, fold_rib: bool = True, steer: bool = True) -> dict[str, Any]:
    """Fold the guard RIB (once), watch the live feed, and on a PREDICTED seam publish a steer RIB +
    fold a training signal immediately — the 50x tax is caught BEFORE it hits the bill."""
    rib = guard_rib(fold=fold_rib)
    pred = predict_seams()
    res = {"ok": True, "schema": SCHEMA, "rib": rib, "prediction": pred}
    if pred["predicted_spike"] and steer:
        try:
            from mag import rib_bus
            steer_rib = ("STEER: cache-miss seam predicted in the live stream — route the volatile "
                         "tail to cheap/free now, preserve the stable prefix, avoid the 50x miss.")
            res["steer_rib"] = rib_bus.publish_rib(steer_rib, domain="usage-guard",
                                                   source="flock_usage_guard", target_rank="T2")
        except Exception as e:
            res["steer_error"] = str(e)[:160]
        try:
            from mag.behavioral_analytics import log_behavioral_event
            log_behavioral_event(kind="cache_miss_predicted",
                                 detail=f"miss={pred['miss_tokens']:,} ratio={pred['hit_ratio']} "
                                        f"cause={pred['cause']} BEFORE bill")
            res["folded_training"] = True
        except Exception as e:
            res["fold_error"] = str(e)[:120]
    return res


def status() -> dict[str, Any]:
    from mag.usage_monitor import rule as _urule
    return {"ok": True, "schema": SCHEMA, "guard_rib": GUARD_RIB,
            "early_ratio": EARLY_RATIO, "early_miss": EARLY_MISS,
            "rule": _urule()["rule"], "current": predict_seams()}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="flock-usage-guard")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "predict", "guard", "watch"])
    a = ap.parse_args()
    import json as _j
    if a.cmd == "predict":
        print(_j.dumps(predict_seams(), indent=2, default=str))
    elif a.cmd == "guard":
        print(_j.dumps(guard_rib(), indent=2, default=str))
    elif a.cmd == "watch":
        print(_j.dumps(watch_and_guard(), indent=2, default=str))
    else:
        print(_j.dumps(status(), indent=2, default=str))
