"""time_estimate — turn the existing WORK estimate (tokens+cost) into a wall-clock ETA.

Operator (2026-08-12): "what is the speed control of the system size of the job? can't we estimate
work?" + "yes" (to building the time estimate).

THE GAP: cost_ledger.task_estimate() estimates WORK (context/output tokens + price_band_usd), but
NOT time. We can derive wall-clock time from: work size x concurrency (N) x measured per-call
latency. That's the missing half.

  estimate(goal, n, provider) -> ETA = (total_tokens / N_parallel) / tokens_per_sec + drain_cadence
      - work:    cost_ledger.task_estimate -> context_need_tokens + output_tokens
      - latency: cost_learn (per-provider avg_latency_ms from REAL usage) -> tokens/sec
      - n:       swarm_rightsize.rightsize (or explicit) -> how many run in parallel
      - cadence: the drain poll interval (an honest additive constant)
      - HONEST: if no real latency is measured, reports "no measured latency — rough estimate",
        never fabricates a precise ETA.

Schema: time_estimate.v1 · deterministic + $0 · reuse: cost_ledger, cost_learn, swarm_rightsize
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "time_estimate.v1"
# honest fallback tokens/sec if no measured latency (deepseek flash, conservative)
FALLBACK_TPS = 30.0
# drain poll cadence (additive constant, seconds) — the worker's poll interval
DRAIN_CADENCE_S = 120.0


def _measured_tps(provider: str) -> float | None:
    """Measured tokens/sec for a provider from REAL usage (cost_learn). None if not measured."""
    try:
        from mag import cost_learn
        s = cost_learn.learn()
        provs = s.get("per_provider") or s.get("providers") or {}
        # cost_learn rows carry avg_latency_ms + input/output token sums -> derive tps
        for name, row in (provs.items() if isinstance(provs, dict) else []):
            if str(name).lower() == str(provider).lower():
                lat = row.get("avg_latency_ms") or row.get("latency_ms") or 0
                outp = row.get("output_tokens") or row.get("completion_tokens") or 0
                if lat and outp:
                    # tokens across that many calls / avg latency -> per-call tps approx
                    calls = row.get("calls") or 1
                    per_call_out = outp / max(calls, 1)
                    tps = (per_call_out / (lat / 1000.0)) if lat else 0.0
                    if tps > 0:
                        return round(tps, 1)
        return None
    except Exception:
        return None


def _work(goal: str, provider: str, model: str | None) -> dict[str, Any]:
    try:
        from mag import cost_ledger
        return cost_ledger.task_estimate(goal, provider=provider, model=model)
    except Exception:
        return {}


def _concurrency(provider: str) -> int:
    try:
        from mag.swarm_rightsize import rightsize
        return int(rightsize("time estimate", provider=provider).get("n_agents", 4))
    except Exception:
        return 4


def estimate(goal: str = "", *, provider: str = "deepseek-v4-flash", n: int | None = None,
             model: str | None = None) -> dict[str, Any]:
    """Wall-clock ETA: (work tokens / N_parallel) / tps + drain cadence. Honest about measured vs fallback."""
    goal = (goal or "").strip() or "the queued task"
    w = _work(goal, provider, model)
    ctx = int(w.get("context_need_tokens") or 0)
    out = int(w.get("output_tokens") or 0)
    total = ctx + out
    if n is None:
        n = _concurrency(provider)
    n = max(1, int(n))

    tps = _measured_tps(provider)
    measured = tps is not None
    if not measured:
        tps = FALLBACK_TPS

    # tokens processed per second across the whole batch (parallel workers)
    batch_tps = tps * n
    work_s = (total / batch_tps) if batch_tps else 0.0
    eta_s = work_s + DRAIN_CADENCE_S  # + the poll cadence
    return {
        "ok": True, "schema": SCHEMA, "goal": goal[:80], "provider": provider, "n": n,
        "work": {"context_tokens": ctx, "output_tokens": out, "total_tokens": total},
        "speed": {"tokens_per_sec_per_worker": tps, "batch_tokens_per_sec": round(batch_tps, 1),
                  "measured_latency": measured},
        "eta": {"seconds": round(eta_s, 1), "minutes": round(eta_s / 60, 1),
                "work_seconds": round(work_s, 1), "drain_cadence_s": DRAIN_CADENCE_S},
        "honest": ("measured from real usage latency" if measured
                   else f"NO measured latency for {provider} — using fallback {FALLBACK_TPS} tps; "
                        f"rough estimate, not precise"),
        "formula": "eta = (total_tokens / (n_parallel * tps)) + drain_cadence",
    }


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "estimate(goal, n, provider)->wall-clock ETA from work tokens x concurrency "
                        "x measured per-call latency + drain cadence. Turns the existing work "
                        "estimate into time. Honest when latency isn't measured.",
            "cost": "deterministic + $0 (reuse cost_ledger, cost_learn, swarm_rightsize)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="time-estimate")
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--provider", default="deepseek-v4-flash")
    ap.add_argument("cmd", nargs="?", default="estimate", choices=["estimate", "status"])
    a = ap.parse_args()
    if a.cmd == "estimate":
        print(json.dumps(estimate(" ".join(a.goal), provider=a.provider, n=a.n), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
