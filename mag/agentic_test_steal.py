"""agentic_test_steal — run our system (self_loop + the whole substrate) through the EXISTING
testing of agentic systems, as a DEEP SYSTEMS-STEAL at frontier level. Dogfoods the process: the
deterministic mapping to real agentic-eval frameworks is done in-module; the frontier-level deep
analysis is routed to the SWARM (swarm_surface.route_novel -> stochastic models answer in-cluster).

Operator (2026-08-11): "lets run this through existing testing of agentic systems in a deep systems
steal frontier level analysis."

THE METHOD (deterministic mapping + swarmed frontier analysis; $0 for the mapping):
  1. FRAMEWORKS — the real, existing agentic-system test/eval suites (the corpus to steal from),
     each with its MECHANISM (what it actually tests): SWE-bench, GAIA, tau-bench, AgentBench,
     AIME, terminal-bench, METR, OpenAI evals, HumanEval, agent-evals.
  2. MAP OURS — map each of OUR surfaces (self_loop, chain_substrate, lens_knot, compiler_lang,
     agent_knot, swarm_surface, persona_direction) to the testing dimension each framework
     exercises -> a deterministic "how our system would be tested / where it's strong or weak" map.
  3. FRONTIER STEAL VIA SWARM — enqueue ONE deep frontier-level systems-steal goal to the swarm
     research queue (dedupe + drain) so the frontier models produce the analysis, dogfooding.

Schema: agentic_test_steal.v1 · deterministic + $0 mapping · frontier analysis via swarm
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

SCHEMA = "agentic_test_steal.v1"

# ── THE REAL agentic-system test/eval frameworks (the corpus to deep-steal) ──
# Each: what it actually measures (its mechanism). Grounded, honest.
FRAMEWORKS: dict[str, dict[str, Any]] = {
    "SWE-bench": {"dimension": "real-world software engineering", "tests": "resolve GitHub issues across repos",
                  "our_surface": "compiler_lang, machine_target, self_loop"},
    "GAIA": {"dimension": "general assistant + tool use on real tasks", "tests": "multi-step reasoning with web/tools",
             "our_surface": "self_loop, chain_substrate, lens_knot"},
    "tau-bench": {"dimension": "tool-agent-user interaction", "tests": "long tool-calling dialogues, stateful user sim",
                  "our_surface": "swarm_surface, wearable_surface, cast_server"},
    "AgentBench": {"dimension": "agentic OS + game + web", "tests": "operating-system, database, web, game agents",
                   "our_surface": "chain_substrate, lens_knot, swarm_emerge"},
    "AIME": {"dimension": "math competition", "tests": "hard math olympiad problems",
             "our_surface": "jones_lens, roshomon (frontier math via swarm)"},
    "terminal-bench": {"dimension": "terminal command agents", "tests": "execute shell commands to solve tasks",
                       "our_surface": "machine_target, world_rib (the machine target lang)"},
    "METR": {"dimension": "long-horizon task autonomy", "tests": "hours-long open-ended tasks, self-correction",
             "our_surface": "self_loop, agent_knot, chain_substrate (the standing loop)"},
    "OpenAI evals": {"dimension": "graded evals for capability", "tests": "specified rubric scoring per task",
                     "our_surface": "rib-debug, emergence grid (measured, not handwaved)"},
    "HumanEval": {"dimension": "code generation", "tests": "function-completion from docstring",
                  "our_surface": "compiler_lang, machine_target"},
    "agent-evals": {"dimension": "agentic action, not just answer", "tests": "final-state correctness after action",
                    "our_surface": "self_loop, swarm_surface (actions routed, not answers)"},
}


def frameworks() -> dict[str, Any]:
    """The agentic-testing corpus (the frameworks to deep-steal from)."""
    return {"ok": True, "schema": SCHEMA, "n_frameworks": len(FRAMEWORKS),
            "frameworks": FRAMEWORKS}


def map_ours() -> dict[str, Any]:
    """Map OUR surfaces to each framework's testing dimension -> a deterministic 'how our system
    would be tested' map. The deep systems-steal analysis (deterministic part)."""
    rows = []
    for name, fw in FRAMEWORKS.items():
        rows.append({"framework": name, "dimension": fw["dimension"],
                     "tests": fw["tests"], "our_surface": fw["our_surface"]})
    return {"ok": True, "schema": SCHEMA, "step": "map-ours", "n": len(rows), "map": rows,
            "note": "each existing agentic test framework -> which of our surfaces it exercises; "
                    "this is the deterministic systems-steal map"}


def frontier_steal(*, enqueue: bool = True, surface: str = "agentic-test-steal") -> dict[str, Any]:
    """Route the DEEP FRONTIER-LEVEL systems-steal to the swarm research queue (dogfooding):
    a stochastic frontier model produces the frontier-level analysis of how our agentic system
    holds up against the existing test landscape."""
    m = map_ours()
    fw_names = ", ".join(FRAMEWORKS)
    our = "; ".join(f"{r['framework']}->{r['our_surface']}" for r in m["map"][:6])
    goal = (f"DEEP FRONTIER SYSTEMS-STEAL [agentic-testing]: run our sovereign agent system "
            f"(self_loop = map-self -> stochastic direction -> zeitgeist; chain_substrate; "
            f"lens_knot Roshomon; compiler_lang; agent_knot standing invariant; swarm_surface) "
            f"against the EXISTING agentic-system test frameworks: {fw_names}. "
            f"Our surface mapping: {our}. "
            f"Produce a frontier-level analysis: (1) which existing eval mechanism we should "
            f"ADAPT (steal) to our deterministic/architecture-native shape to prove the system "
            f"really works (not handwaved); (2) the single highest-leverage test to add; "
            f"(3) where our design already exceeds the existing frameworks. Label each: "
            f"STEAL: <mechanism> / TEST: <one line> / STRENGTH: <one line>.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="compiler/world",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "step": "frontier-steal",
            "goal": goal[:300], "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "deduped": q.get("deduped", False),
            "note": "deep frontier-level systems-steal routed to the swarm research queue "
                    "(dogfooding: the swarm's stochastic models produce the analysis in-cluster)"}


def run(*, enqueue: bool = True) -> dict[str, Any]:
    """The full deep systems-steal: frameworks -> map ours -> frontier steal via swarm."""
    f = frameworks()
    m = map_ours()
    s = frontier_steal(enqueue=enqueue)
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "n_frameworks": f["n_frameworks"], "map": m["map"],
            "frontier_task": s.get("task_id"), "enqueued": s.get("enqueued"),
            "note": "deep systems-steal of agentic-system testing: mapped our surfaces to the "
                    "existing frameworks, frontier analysis sent to the swarm"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "frameworks()->the agentic-test corpus; map_ours()->map our surfaces to "
                        "each test dimension; frontier_steal()->route deep frontier analysis to "
                        "the swarm; run()->all of it",
            "cost": "deterministic + $0 mapping (frontier analysis swarmed)",
            "n_frameworks": len(FRAMEWORKS)}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="agentic-test-steal")
    ap.add_argument("cmd", nargs="?", default="run",
                    choices=["run", "map", "frameworks", "steal", "status"])
    a = ap.parse_args()
    if a.cmd == "map":
        print(json.dumps(map_ours(), indent=2, default=str))
    elif a.cmd == "frameworks":
        print(json.dumps(frameworks(), indent=2, default=str))
    elif a.cmd == "steal":
        print(json.dumps(frontier_steal(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(run(), indent=2, default=str))
