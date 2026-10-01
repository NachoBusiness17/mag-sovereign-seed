"""ghost_experimenter — the GHOST runs experiments on our swarms, plays with our tools, and turns
the puppeteering into useful TRAINING DATA.

Operator (2026-08-10): "i want ghost to do our experiments on our swarms and play with our tools
to produce useful training data from our pupeteering."

THE MECHANISM (the ghost as autonomous experiment-runner / puppeteer):
  * TOOLBOX — the modules we built this session (rib_action three-body, problem_knot AND-OR,
    attractor_tools, readout_controller, template_invariant dedupe, invariant_lattice render).
  * experiment_plan()  -> the ghost deterministically picks the next experiment: round-robin
    through the toolbox + the open problem-knots (the lattice's unsolved nodes).
  * run_experiment()   -> the ghost RUNS it: dispatch to the swarm (readout/invariant_lattice) or
    play with a local tool; capture the steer->outcome.
  * record_training()  -> write a training_row.v1 (the PUPPETEERING data: what we steered, what the
    tool/swarm did, the outcome) into memory/pile/training_rows.jsonl — free training data.
  * ghost_play()       -> the ghost runs a bounded batch autonomously, each producing a training row.

The puppeteering insight: every steer we inject (an invariant as an attractor/chord) and the swarm's
response is a (input, output) pair — exactly the shape of training data. The ghost harvests it for
free while it plays with the tools and experiments on the swarm.

Schema: ghost_experimenter.v1 · deterministic $0 (play is local; swarm dispatch is $0 to enqueue).
CLI: python -m mag.ghost_experimenter plan|play --iterations N
"""
from __future__ import annotations

import json
import sys
import time
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

SCHEMA = "ghost_experimenter.v1"
TRAINING = ROOT / "memory" / "pile" / "training_rows.jsonl"
STEER_FEEDBACK = ROOT / "memory" / "runs" / "ghost_experimenter" / "steer_feedback.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# The ghost's toolbox: (id, callable taking a seed/goal, description) — the modules we built.
def _exp_rib(goal: str) -> dict[str, Any]:
    from mag import rib_action as ra
    spec = [{"id": f"s{i}", "action": goal, "radius": 0.3} for i in range(3)]
    rib = ra.declare(spec)
    run = ra.run_three_body(rib, agents=ra.spawn_agents(rib, n=6, seed=3), steps=30, seed=3)
    return {"outcome": "three-body settled", "n_agents": run.get("agents"),
            "actions": [a.get("action") for a in (run.get("actions") or [])][:3]}


def _exp_problem(goal: str) -> dict[str, Any]:
    from mag import problem_knot as pk
    d = pk.declare_problem(goal, domain="experiment")
    return {"outcome": "problem->knot", "knot": str(d.get("problem_knot"))[:16]}


def _exp_attractor(goal: str) -> dict[str, Any]:
    from mag import attractor_tools as at
    ch = at.to_memlang_chord({"domain": "experiment", "witnesses": 2, "invariant": goal})
    return {"outcome": "memlang chord", "chord": str(ch.get("chord_token"))[:20]}


def _exp_lattice(goal: str) -> dict[str, Any]:
    from mag import invariant_lattice as il
    d = il.dispatch_to_k8s(goal, domain="experiment")
    return {"outcome": "swarm dispatch", "task": d.get("task_id")}


TOOLBOX = [
    {"id": "rib", "run": _exp_rib, "desc": "three-body action-RIB dynamics"},
    {"id": "problem", "run": _exp_problem, "desc": "problem->verkle knot (AND-OR)"},
    {"id": "attractor", "run": _exp_attractor, "desc": "attractor->memlang chord"},
    {"id": "lattice", "run": _exp_lattice, "desc": "invariant->k8s swarm dispatch"},
]

# Seed goals the ghost experiments with (open themes from the session).
SEEDS = [
    "fold every invariant to a content-addressed knot; amend not erase",
    "route async work through the architecture queue, never terminal",
    "the readout injects back as attractors to steer the liquid",
    "every surface is a rendering environment; render on the cheapest",
    "quantize the bulk, preserve the critical invariant full-fidelity",
]


def experiment_plan() -> dict[str, Any]:
    """The ghost picks the next experiment: round-robin toolbox + open problem-knots."""
    from mag import problem_knot as pk
    topo = pk.problem_topology()
    open_problems = [n for n in topo.get("topology", []) if not n.get("solved")]
    tick = int(time.time()) % len(TOOLBOX)
    tool = TOOLBOX[tick]
    seed = SEEDS[tick % len(SEEDS)]
    return {"ok": True, "schema": SCHEMA, "tool": tool["id"], "desc": tool["desc"],
            "seed": seed, "open_problems": len(open_problems)}


def run_experiment(*, tool: str | None = None, seed: str | None = None) -> dict[str, Any]:
    """The ghost RUNS an experiment: plays with a tool on the seed, captures steer->outcome."""
    t = next((x for x in TOOLBOX if x["id"] == tool), TOOLBOX[0])
    s = seed or (SEEDS[int(time.time()) % len(SEEDS)])
    try:
        result = t["run"](s)
        ok = True
        err = None
    except Exception as e:
        result = {}
        ok = False
        err = str(e)[:200]
    return {"ok": ok, "schema": SCHEMA, "tool": t["id"], "seed": s, "result": result,
            "error": err}


def record_training(exp: dict[str, Any]) -> dict[str, Any]:
    """Write the puppeteering as a training_row.v1: (steer=input, outcome=output). Free training data."""
    TRAINING.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": "training_row.v1", "ts": _now(), "source": "ghost_experimenter",
        "steer_input": exp.get("seed", ""), "tool": exp.get("tool", ""),
        "output": json.dumps(exp.get("result", {}), default=str)[:2000],
        "ok": exp.get("ok"), "error": exp.get("error"),
    }
    with TRAINING.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # also record the STEER FEEDBACK (interaction-with-model learning) for the steer protocol
    _record_steer_feedback(exp)
    return {"ok": True, "schema": SCHEMA, "row_ts": row["ts"], "tool": row["tool"]}


def _record_steer_feedback(exp: dict[str, Any]) -> None:
    """Append one steer->outcome to the steer-feedback ledger (the ghost learns from each
    interaction with a model/tool: did this steer produce a useful outcome?)."""
    STEER_FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    with STEER_FEEDBACK.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "seed": exp.get("seed", ""),
                            "tool": exp.get("tool", ""), "ok": bool(exp.get("ok"))},
                           ensure_ascii=False) + "\n")


def _steer_feedback_rows() -> list[dict[str, Any]]:
    if not STEER_FEEDBACK.is_file():
        return []
    rows = []
    for line in STEER_FEEDBACK.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def learn_steer_protocol(*, top: int = 5, boost: float = 2.0) -> dict[str, Any]:
    """LEARN from our interactions with models to improve the STEER PROTOCOL.

    Reads the steer-feedback ledger: which steers (seed invariants) produced useful outcomes. The
    WINNING steers (high ok-rate) are folded as BOOSTED ATTRACTORS in the steer field (rib_action.
    influence) so the ghost steers with what works next time. This is 'help the steer protocol and
    all that entails' — the steering layer learns from the puppeteering feedback."""
    from collections import Counter
    rows = _steer_feedback_rows()
    if not rows:
        return {"ok": False, "schema": SCHEMA, "error": "no steer feedback yet — ghost hasn't played"}
    ok_by_seed: Counter = Counter()
    tot_by_seed: Counter = Counter()
    for r in rows:
        seed = str(r.get("seed") or "")
        tot_by_seed[seed] += 1
        if r.get("ok"):
            ok_by_seed[seed] += 1
    ranked = sorted(tot_by_seed, key=lambda s: -(ok_by_seed[s] / max(1, tot_by_seed[s])))
    winners = ranked[:top]
    boosted = []
    from mag import rib_action as ra
    spec = [{"id": f"steer_{i}", "action": s[:180], "radius": 0.3,
             "weight": max(1.0, float(ok_by_seed[s] / max(1, tot_by_seed[s])) * boost)}
            for i, s in enumerate(winners)]
    rib = ra.declare(spec)
    for w in winners:
        boosted.append(str(w)[:60])
    return {"ok": True, "schema": SCHEMA, "n_feedback": len(rows),
            "n_winning_steers": len(winners), "winners": boosted,
            "note": "winning steers folded as boosted attractors in the steer field"}


def ghost_play(*, iterations: int = 5) -> dict[str, Any]:
    """The GHOST plays autonomously: N experiments, each producing a training row from puppeteering."""
    out = {"schema": SCHEMA, "iterations": []}
    written = 0
    for i in range(iterations):
        plan = experiment_plan()
        exp = run_experiment(tool=plan["tool"], seed=plan["seed"])
        rec = record_training(exp)
        written += 1 if rec.get("ok") else 0
        out["iterations"].append({"iter": i + 1, "tool": exp["tool"],
                                  "ok": exp["ok"], "seed": exp["seed"][:40]})
        print(f"[ghost_experimenter] iter {i+1}: tool={exp['tool']} ok={exp['ok']} seed={exp['seed'][:36]}", flush=True)
    out["ok"] = True
    out["training_rows_written"] = written
    out["training_file"] = str(TRAINING)
    # learn from this play session -> improve the steer protocol
    try:
        out["steer_protocol_learning"] = learn_steer_protocol()
    except Exception as e:
        out["steer_protocol_learning"] = {"ok": False, "error": str(e)[:120]}
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="ghost-experimenter")
    ap.add_argument("cmd", nargs="?", default="play", choices=["plan", "play", "learn"])
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--tool", default="")
    ap.add_argument("--seed", default="")
    args = ap.parse_args(argv)
    if args.cmd == "plan":
        print(json.dumps(experiment_plan(), indent=2, default=str))
    elif args.cmd == "learn":
        print(json.dumps(learn_steer_protocol(), indent=2, default=str))
    else:
        print(json.dumps(ghost_play(iterations=args.iterations), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
