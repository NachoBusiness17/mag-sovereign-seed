"""budget_refactor — the COMPLETE DETERMINISTIC refactor of how we spend the budget, grounded in
the REAL billing data. Ramp up the value of the cash we've already spent.

Operator (2026-08-11): "so now with our old data how could we ramp up the use of that cash we spent.
how best would you use our budget so far right now if you could in a complete deterministic refactor?"

GROUNDED IN THE REAL BILL (memory/cost/daily_baseline_2026-08-11.json + provider_usage.jsonl):
  Day total $1.65. Cache hit ~99% (hit $0.92/55%, miss $0.43/26%, output $0.31/19%).
  Miss tokens are 50x the hit price. The 08-09 hour = $0.41 (25% of day) from a 1.37M miss burst.

THE REFACTOR (deterministic + $0, reuses cache_shard/flock_usage_guard/swarm_rightsize):
  waste()     -> the recoverable budget: the cache-MISS cost (50x waste). Converting misses to hits
                 (prefix-stable cache affinity via cache_shard) recovers ~23% of the bill.
  freed()     -> what the freed budget funds: N more cheap quantized flash agents/tasks (rightsized).
  plan()      -> the ranked refactor: (1) kill miss bursts -> recover $; (2) re-spend the freed $ on
                 more flash swarm work; (3) reserve frontier only for seams; (4) deterministic-first
                 (do deterministic work free, spend only on genuine novelty).
  Ramp-up: the same cash buys MORE work by eliminating the 50x miss waste and rightsizing.

Schema: budget_refactor.v1 · deterministic + $0 · reuse: cache_shard, flock_usage_guard, swarm_rightsize
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "budget_refactor.v1"
BASELINE = ROOT / "memory" / "cost" / "daily_baseline_2026-08-11.json"
USAGE = ROOT / "logs" / "provider_usage.jsonl"
MISS_PRICE = 1.4e-7      # deepseek cache-miss input price
HIT_PRICE = 2.8e-9       # deepseek cache-hit input price
MISS_VS_HIT = 50          # the 50x multiplier
FLASH_COST_PER_REQ = 0.002  # cheap quantized flash request ceiling (rightsized)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _base() -> dict[str, Any]:
    if BASELINE.is_file():
        try:
            return json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _usage_miss_tokens() -> int:
    if not USAGE.is_file():
        return 0
    total = 0
    for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            total += int(json.loads(line).get("cache_miss_tokens") or 0)
        except Exception:
            continue
    return total


def waste() -> dict[str, Any]:
    """The RECOVERABLE budget: the cache-MISS cost (50x waste). Deterministic, grounded."""
    b = _base()
    miss_cost = float(b.get("token_type_cost_usd", {}).get("input_cache_miss", 0.0) or 0.0)
    miss_tokens = int(b.get("totals", {}).get("input_cache_miss_tokens", 0) or _usage_miss_tokens())
    total = float(b.get("total_cost_usd", 0.0) or 0.0)
    # if we converted those misses to hits (prefix-stable cache affinity), the 50x waste is recovered
    hit_cost_if_cached = miss_tokens * HIT_PRICE
    recovered = miss_cost - hit_cost_if_cached
    return {"ok": True, "schema": SCHEMA, "miss_cost": round(miss_cost, 4),
            "miss_tokens": miss_tokens, "total": round(total, 4),
            "recoverable_usd": round(recovered, 4),
            "recoverable_pct_of_bill": round((recovered / total * 100) if total else 0, 1),
            "note": f"miss tokens are {MISS_VS_HIT}x the hit price; converting misses to hits "
                    f"(prefix-stable cache affinity) recovers ~{round(recovered,2)} of the bill"}


def freed() -> dict[str, Any]:
    """What the freed budget FUNDS: N more cheap quantized flash agents/tasks (rightsized ramp-up)."""
    w = waste()
    freed_usd = w["recoverable_usd"]
    n_flash_tasks = int(freed_usd / FLASH_COST_PER_REQ) if FLASH_COST_PER_REQ else 0
    n_flash_agents = n_flash_tasks * 2  # rightsized: ~2 agents per task
    return {"ok": True, "schema": SCHEMA, "freed_usd": round(freed_usd, 4),
            "flash_cost_per_task": FLASH_COST_PER_REQ,
            "more_flash_tasks": n_flash_tasks, "more_flash_agents": n_flash_agents,
            "ramp_up": f"the SAME cash funds ~{n_flash_tasks} more cheap flash tasks "
                       f"(~{n_flash_agents} agents) by eliminating the 50x miss waste",
            "note": "reallocate the recovered miss-waste into MORE quantized flash swarm work"}


def plan() -> dict[str, Any]:
    """The COMPLETE DETERMINISTIC REFACTOR of budget use, ranked. Grounded in the real bill."""
    b = _base()
    total = float(b.get("total_cost_usd", 0.0) or 0.0)
    w = waste()
    f = freed()
    spike = b.get("spike", {})
    steps = [
        {"rank": 1, "move": "KILL MISS BURSTS (cache_shard prefix affinity)",
         "detail": f"recover ${w['recoverable_usd']} by converting cache misses to hits "
                   f"(50x cheaper). The 08-09 spike ({spike.get('miss_tokens','?')} miss tokens = "
                   f"${spike.get('cost_usd','?')}) is the single biggest recoverable chunk.",
         "impact_usd": round(w["recoverable_usd"], 4)},
        {"rank": 2, "move": "RE-SPEND the freed cash on quantized flash swarm work",
         "detail": f"the ${w['recoverable_usd']} freed funds ~{f['more_flash_tasks']} more flash "
                   f"tasks (~{f['more_flash_agents']} agents, rightsized) — the ramp-up of value.",
         "impact_usd": round(f["freed_usd"], 4)},
        {"rank": 3, "move": "FRONTIER ONLY AT THE SEAMS",
         "detail": "reserve expensive frontier models for the seams only (flock_shader doctrine); "
                   "cheap flash everywhere else — the 99% cache-hit deterministic core stays free.",
         "impact_usd": 0.0},
        {"rank": 4, "move": "DETERMINISTIC-FIRST (spend only on genuine novelty)",
         "detail": "do deterministic/$0 work free (percolator, lensing, cache-affinity routing); "
                   "spend the budget only where the cost guard folds a genuine cache-miss/novel seam.",
         "impact_usd": round(float(w["recoverable_usd"]) + float(f["freed_usd"]), 4)},
    ]
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "total_bill": round(total, 4),
            "waste": w, "freed": f,
            "refactor_steps": steps,
            "ramp_up": f["ramp_up"],
            "bottom_line": (f"same ${total} buys MORE work: recover ${w['recoverable_usd']} of "
                            f"50x miss-waste -> fund ~{f['more_flash_tasks']} more flash tasks; "
                            f"frontier only at the seams; deterministic-first."),
            "note": "the complete deterministic refactor of budget use, grounded in the real bill"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "waste()->recoverable cache-miss budget; freed()->what it funds (more flash "
                        "tasks/agents); plan()->the ranked refactor (kill misses -> re-spend -> "
                        "seams-only frontier -> deterministic-first)",
            "cost": "deterministic + $0 (grounded in the real bill + provider_usage)",
            "baseline": str(BASELINE.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="budget-refactor")
    ap.add_argument("cmd", nargs="?", default="plan",
                    choices=["plan", "waste", "freed", "status"])
    a = ap.parse_args()
    if a.cmd == "waste":
        print(json.dumps(waste(), indent=2, default=str))
    elif a.cmd == "freed":
        print(json.dumps(freed(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(plan(), indent=2, default=str))
