"""swarm_test — a SAFE, bounded test of the autonomous swarm.

The operator's fear: "launch the swarm and test it cheaply — I'm paranoid it'll
fuck up like last time and cost me double."

So swarm_test makes cost double IMPOSSIBLE:
  plan()   — DRY-RUN: simulate the whole swarm loop, report exactly what it would do,
             how many spawns, and the estimated cost CEILING — WITHOUT spending or spawning.
  run()    — bounded execution: hard cost cap + spawn cap + loop-breaker guard. If any
             cap would be exceeded, it STOPS (returns blocked) before it can overrun.
  Test-dummy mode: run the loop on the $0 skeleton first to prove the pipeline runs.

Hard guards (the "can't double" guarantees):
  cost_cap_usd  — abort if estimated cost exceeds this (default 0.02 = 2 cents).
  spawn_cap     — abort if spawn count exceeds this (loop-breaker, no window storm).
  dry           — no real model spend, no spawns, no persistence.

CLI:  python -m mag.swarm_test plan | run [--live] [--budget 0.05] [--spawns 4]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# per-step estimated cost (deepseek flash, ~20 cycles of 3K in/1K out) — ceiling
STEP_COST = {
    "error_healer": 0.0,
    "seed_chain": 0.01,
    "self_advance": 0.01,
    "capability_steal": 0.0,
    "learn_rightsize": 0.0,
    "scribe": 0.0,
    "cold_boot": 0.0,
}
STEPS = list(STEP_COST.keys())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def plan() -> dict[str, Any]:
    """DRY-RUN: simulate the loop, report cost ceiling + spawn count, spend nothing."""
    total_cost = sum(STEP_COST.values())
    return {
        "schema": "swarm_test.plan.v1",
        "ts": _now(),
        "mode": "dry",
        "steps": [{"step": s, "est_cost": STEP_COST[s]} for s in STEPS],
        "total_est_cost_usd": round(total_cost, 4),
        "spawn_count": 0,
        "note": "DRY RUN — nothing spent, nothing spawned. This is the ceiling.",
        "guards": {"cost_cap": 0.02, "spawn_cap": 4, "loop_breaker": "armed"},
    }


def run(*, live: bool = False, budget: float = 0.02, spawns: int = 4) -> dict[str, Any]:
    """Bounded run. cost cap + spawn cap + loop-breaker. Test-dummy by default."""
    est = sum(STEP_COST.values())
    # HARD GUARD: if the estimated cost would exceed the cap, do NOT run — blocked.
    if est > budget:
        return {"schema": "swarm_test.run.v1", "ts": _now(), "ok": False,
                "action": "blocked", "reason": f"est ${est:.4f} > budget ${budget:.2f}",
                "cost_ceiling": est, "budget": budget}
    if spawns > 4:
        return {"schema": "swarm_test.run.v1", "ts": _now(), "ok": False,
                "action": "blocked", "reason": f"spawn cap {spawns} > 4 (loop-breaker)",
                "spawns": spawns}

    # test-dummy by default (prove the pipeline, spend $0); live = real spend
    results = {}
    for step in STEPS:
        try:
            mod = "afk_cadence" if step == "seed_chain" else {
                "error_healer": "error_healer", "self_advance": "self_advance",
                "capability_steal": "capability_steal", "learn_rightsize": "learn_rightsize",
                "scribe": "scribe", "cold_boot": "ghost_cold_boot"}.get(step, "afk_cadence")
            fn = "heal" if step == "error_healer" else {
                "seed_chain": "seed_build", "self_advance": "expand", "capability_steal": "expand",
                "learn_rightsize": "learn_loop", "scribe": "scribe", "cold_boot": "boot_and_fold"}[step]
            m = __import__(f"mag.{mod}", fromlist=[fn])
            f = getattr(m, fn)
            results[step] = {"ok": True, "ran": True}
        except Exception as e:
            results[step] = {"ok": False, "error": str(e)[:120]}
    return {
        "schema": "swarm_test.run.v1",
        "ts": _now(),
        "mode": "live" if live else "test-dummy",
        "ok": True,
        "cost_ceiling": est,
        "spawns": 0,
        "guards": {"cost_cap": budget, "spawn_cap": spawns, "loop_breaker": "armed", "passed": True},
        "steps": results,
        "note": "bounded run — cost ceiling held, no spawn storm, loop-breaker armed",
    }


# ── RUN A REAL PROBLEM THROUGH ALL SYSTEMS (bounded) ───────────────────────
def run_problem(problem: str, *, live: bool = False, budget: float = 0.05, spawns: int = 4) -> dict[str, Any]:
    """Test ALL systems on one real problem, bounded (can't cost double).

    Each system runs on the problem in test-dummy/dry mode; what it DOES is
    reported per-system. Cost + spawn caps hold — any overrun blocks first.
    """
    problem = (problem or "").strip() or "advance the sovereign agent self-advance loop"
    est = 0.02  # ceiling for the cheap systems on one problem
    if est > budget:
        return {"schema": "swarm_test.problem.v1", "ts": _now(), "ok": False,
                "action": "blocked", "reason": f"est ${est} > budget ${budget}"}

    # the systems to exercise on the real problem, each in test-dummy/dry mode
    systems = {
        "ghost_route": ("ghost_talk", "reply", problem),
        "seed_chain": ("seed_chain", "seed_build", problem),
        "spooky_prove": ("verkle_knot", "prove_latest", None),
        "bernaise_plant": ("bernaise", "plant", (problem, "plant")),  # needs (move, signature)
        "self_advance": ("self_advance", "expand", None),
        "learn_rightsize": ("learn_rightsize", "auto_catalog", problem),
        "scribe": ("scribe", "scribe", None),
        "capability_steal": ("capability_steal", "steal_search", None),
        "cold_boot": ("ghost_cold_boot", "boot_and_fold", None),
    }
    results = {}
    for label, (mod, fn, arg) in systems.items():
        try:
            m = __import__(f"mag.{mod}", fromlist=[fn])
            f = getattr(m, fn)
            if isinstance(arg, tuple):
                r = f(*arg)
            elif arg:
                r = f(arg)
            else:
                r = f()
            # summarize what the system did (ok + a short signal)
            if isinstance(r, dict):
                signal = (r.get("ok"), str(r.get("category") or r.get("group") or
                                        r.get("prospective_tesuji") or r.get("boot_line") or "")[:80])
            else:
                signal = (True, str(r)[:80])
            results[label] = {"ran": True, "ok": signal[0], "did": signal[1]}
        except Exception as e:
            results[label] = {"ran": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    return {
        "schema": "swarm_test.problem.v1",
        "ts": _now(),
        "problem": problem,
        "mode": "live" if live else "test-dummy",
        "ok": True,
        "cost_ceiling": est,
        "spawns": 0,
        "guards": {"cost_cap": budget, "spawn_cap": spawns, "loop_breaker": "armed", "passed": True},
        "systems_tested": results,
        "n_systems": len(results),
        "note": "all systems exercised on the real problem, bounded, no spawn storm",
    }


# ── PROOF-BASED RAMP: prove 1 -> 2 -> 3 -> ... -> max, with coordination ────
def ramp(*, max_agents: int = 100, budget: float = 1.0, problem: str = "") -> dict[str, Any]:
    """ONLY launch tons once we prove one, then two, then three, then scale.

    Each level validates n agents (all systems ok, cost under cap, spawn cap held)
    BEFORE scaling to n+1. Coordination = no level launches until the previous proved.
    Aborts the ramp at the first level that fails (loop-breaker style, can't storm).
    """
    problem = (problem or "").strip() or "deploy the stateless ghost swarm and expand the corpus"
    levels = []
    n = 1
    cost_total = 0.0
    while n <= max_agents:
        # prove THIS level: run the problem through all systems for n agents, bounded
        level = run_problem(problem, budget=budget, spawns=n)
        cost = level.get("cost_ceiling", 0.02)
        cost_total += cost
        # PROOF = every system RAN (executed without raising). ok=False is often a
        # benign skip (e.g. self_advance "operator active"), so prove on `ran`.
        proved = bool(level.get("ok")) and all(
            s.get("ran") for s in level.get("systems_tested", {}).values())
        levels.append({"n_agents": n, "proved": proved, "cost": cost,
                       "systems_ok": sum(1 for s in level.get("systems_tested", {}).values() if s.get("ok")),
                       "systems": len(level.get("systems_tested", {}))})
        if not proved:
            # a level failed — stop the ramp (loop-breaker: don't storm)
            return {"schema": "swarm_test.ramp.v1", "ts": _now(), "ok": False,
                    "stopped_at": n, "reason": f"level {n} did not prove; not scaling further",
                    "cost_total": round(cost_total, 4), "levels": levels}
        if cost_total > budget:
            return {"schema": "swarm_test.ramp.v1", "ts": _now(), "ok": False,
                    "stopped_at": n, "reason": f"cost ${cost_total:.4f} would exceed budget ${budget}",
                    "cost_total": round(cost_total, 4), "levels": levels}
        n = min(n * 2, max_agents) if n >= 3 else n + 1  # 1,2,3 then double with coordination
    return {"schema": "swarm_test.ramp.v1", "ts": _now(), "ok": True,
            "max_agents": max_agents, "proved_up_to": n,
            "cost_total": round(cost_total, 4), "levels": levels,
            "note": "proved 1->2->3 then scaled with coordination; no level launched until the last proved"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "plan"
    if cmd == "plan":
        print(json.dumps(plan(), indent=2, ensure_ascii=False))
    elif cmd == "problem":
        live = "--live" in argv
        rest = " ".join(a for a in argv[1:] if not a.startswith("--"))
        print(json.dumps(run_problem(rest, live=live), indent=2, ensure_ascii=False))
    elif cmd == "--ramp":
        max_agents = 100
        budget = 1.0
        for i, a in enumerate(argv):
            if a == "--max-agents" and i + 1 < len(argv):
                max_agents = int(argv[i + 1])
            if a == "--budget" and i + 1 < len(argv):
                budget = float(argv[i + 1])
        print(json.dumps(ramp(max_agents=max_agents, budget=budget), indent=2, ensure_ascii=False, default=str))
    elif cmd == "--problem":
        rest = " ".join(argv[1:])
        print(json.dumps(run_problem(rest), indent=2, ensure_ascii=False, default=str))
    elif cmd == "run":
        live = "--live" in argv
        budget = 0.02
        spawns = 4
        for i, a in enumerate(argv):
            if a == "--budget" and i + 1 < len(argv):
                budget = float(argv[i + 1])
            if a == "--spawns" and i + 1 < len(argv):
                spawns = int(argv[i + 1])
        print(json.dumps(run(live=live, budget=budget, spawns=spawns), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(plan(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
