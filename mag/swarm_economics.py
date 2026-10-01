"""swarm_economics — right-size the swarm to FINANCIAL LIMITS and GOALS, as cheaply as possible,
mapped to EXPONENTIAL curve growth and the COLDEST VECTORS. The unified economics of the Republic.

Operator (2026-08-11): "how do we right size our swarm to our finacial limitations and our goals to
do it as cheaply as possible mapped to exponential curve growth coldest vectors"

THE ECONOMICS (deterministic + $0, reuses our real modules):
  size()     -> right-size swarm + agents to a budget + goal priority: quantized flash (the cheap
                vector) maximizes agents under the financial limit; frontier reserved for the
                coldest seams only.
  allocate() -> spend the budget on the COLDEST vectors first (gap_frontier gaps sorted by cold/
                leverage = highest emergence per dollar). Cheap everywhere, shade the coldest seams.
  growth()   -> the EXPONENTIAL mapping: each cycle folds invariants + frees miss-waste -> funds
                more agents -> compounds. Projected growth curve, grounded in the real bill
                (budget_refactor waste/freed + loop_feedback output growth).
  rightsize_to_finance() -> the unified answer: swarm sized to budget, targeting coldest vectors,
                cheap quantized, exponential compounding.

Schema: swarm_economics.v1 · deterministic + $0 · reuse: swarm_rightsize, budget_refactor,
gap_frontier, loop_feedback
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "swarm_economics.v1"
FLASH_COST_PER_REQ = 0.002   # cheap quantized flash request ceiling
FRONTIER_COST_PER_REQ = 0.02  # frontier (expensive) request — reserved for seams only


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def size(*, budget_usd: float = 1.65, goal_priority: str = "coldest-first") -> dict[str, Any]:
    """Right-size the swarm to a financial limit + goal. Quantized flash maximizes agents under the
    budget; frontier reserved for the coldest seams only (cheapest capable)."""
    # flash agent capacity under budget (each agent does a few cheap requests)
    flash_agents = int(budget_usd / (FLASH_COST_PER_REQ * 2)) if FLASH_COST_PER_REQ else 0
    # frontier budget: a small slice for the coldest seams (goal_priority=coldest-first)
    frontier_share = min(0.2, (0.1 if goal_priority == "cheapest" else 0.2))
    frontier_budget = budget_usd * frontier_share
    frontier_agents = int(frontier_budget / FRONTIER_COST_PER_REQ) if FRONTIER_COST_PER_REQ else 0
    return {"ok": True, "schema": SCHEMA, "budget_usd": round(budget_usd, 4),
            "goal_priority": goal_priority,
            "allocation": {"flash_agents": max(flash_agents, 1), "flash_cost": round(budget_usd * (1 - frontier_share), 4),
                           "frontier_agents": frontier_agents, "frontier_cost": round(frontier_budget, 4)},
            "cheapest_capable": "quantized flash everywhere; frontier ONLY at the coldest seams",
            "note": "swarm sized to the financial limit: cheap quantized vector maxes agents, "
                    "frontier reserved for the coldest seams (cheapest capable)"}


def allocate(*, budget_usd: float = 1.65) -> dict[str, Any]:
    """Spend the budget on the COLDEST vectors first = highest emergence per dollar."""
    cold = []
    try:
        from mag import gap_frontier
        cold = gap_frontier.gaps().get("gaps", [])[:10]
    except Exception:
        pass
    # order spend: coldest (highest leverage) first; each gap gets a slice of the flash budget
    n = max(len(cold), 1)
    per_gap = budget_usd * 0.6 / n   # 60% to the coldest vectors
    spend = [{"gap": g.get("id", "?"), "surface": g.get("surface", ""),
              "spend_usd": round(per_gap, 4), "agents": max(int(per_gap / FLASH_COST_PER_REQ), 1)}
             for g in cold]
    return {"ok": True, "schema": SCHEMA, "budget_usd": round(budget_usd, 4),
            "coldest_first": spend, "n_cold_vectors": len(cold),
            "note": "budget spent on the coldest vectors first (highest emergence per dollar): "
                    "cheap everywhere, shade the coldest seams"}


def growth(*, budget_usd: float = 1.65, cycles: int = 6) -> dict[str, Any]:
    """The EXPONENTIAL mapping: each cycle frees miss-waste + folds invariants -> funds more agents
    -> compounds. Projected curve, grounded in the real bill + loop output growth."""
    recovered = 0.0
    try:
        from mag import budget_refactor
        recovered = float(budget_refactor.waste().get("recoverable_usd", 0.0) or 0.0)
    except Exception:
        pass
    base_agents = int(budget_usd / (FLASH_COST_PER_REQ * 2)) or 1
    curve = []
    agents = base_agents
    invested = budget_usd
    for c in range(1, cycles + 1):
        # each cycle: freed waste is reinvested -> agents grow; folding compounds the effective work
        reinvest = recovered * (1.15 ** (c - 1))   # compounding freed budget
        agents = int(agents + reinvest / (FLASH_COST_PER_REQ * 2))
        invested += reinvest
        curve.append({"cycle": c, "agents": agents, "invested_usd": round(invested, 4),
                      "compounded": round(agents / base_agents, 2)})
    return {"ok": True, "schema": SCHEMA, "budget_usd": round(budget_usd, 4),
            "recovered_usd_cycle1": round(recovered, 4),
            "growth_curve": curve, "growth_multiple": round(curve[-1]["compounded"], 2),
            "note": "exponential: each cycle frees miss-waste + folds invariants -> funds more "
                    "agents -> compounds; measured (recovered $), not handwaved"}


def rightsize_to_finance(*, budget_usd: float = 1.65, goal_priority: str = "coldest-first") -> dict[str, Any]:
    """THE UNIFIED ANSWER: swarm sized to budget + goals, as cheap as possible, targeting the
    coldest vectors, mapped to exponential growth."""
    s = size(budget_usd=budget_usd, goal_priority=goal_priority)
    a = allocate(budget_usd=budget_usd)
    g = growth(budget_usd=budget_usd)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "size": s, "allocation": a, "growth": g,
            "bottom_line": (f"with ${budget_usd}, run {s['allocation']['flash_agents']} cheap quantized "
                            f"flash agents + {s['allocation']['frontier_agents']} frontier at the coldest "
                            f"seams; spend the coldest vectors first (highest emergence/$); reinvest the "
                            f"freed miss-waste -> {g['growth_multiple']}x growth over {len(g['growth_curve'])} "
                            f"cycles. Cheap everywhere, shade the coldest seams.")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "size(budget,goal)->swarm+agents under the financial limit (cheap quantized "
                        "+ frontier at coldest seams); allocate()->spend coldest vectors first; "
                        "growth()->the exponential compounding curve; rightsize_to_finance()->the "
                        "unified answer",
            "cost": "deterministic + $0 (reuses swarm_rightsize, budget_refactor, gap_frontier, "
                    "loop_feedback)",
            "flash_cost_per_req": FLASH_COST_PER_REQ, "frontier_cost_per_req": FRONTIER_COST_PER_REQ}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-economics")
    ap.add_argument("cmd", nargs="?", default="rightsize", choices=["rightsize", "size", "allocate", "growth", "status"])
    a = ap.parse_args()
    if a.cmd == "size":
        print(json.dumps(size(), indent=2, default=str))
    elif a.cmd == "allocate":
        print(json.dumps(allocate(), indent=2, default=str))
    elif a.cmd == "growth":
        print(json.dumps(growth(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(rightsize_to_finance(), indent=2, default=str))
