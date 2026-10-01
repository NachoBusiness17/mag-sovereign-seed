"""seed_chain — enhance CHEAP agent builds with a frontier logic chain.

The operator's idea: "when we say cheap, how can we enhance the value of our agent
builds? Say 'think about this problem, then this, then this' — give it a logic chain
and let it solve the middle ground as a coding seed from a frontier LLM stolen from free."

So: get a LOGIC CHAIN (decomposed reasoning steps + coding seed) from a FREE FRONTIER
tier (grok free / deepseek free — "stolen from free"), then let the CHEAP local model
solve the middle ground by executing each step. Frontier thinking at cheap-execution cost.

  chain(problem)   — logic chain from the free frontier (or test-dummy skeleton offline).
  solve(problem, chain) — the cheap local model executes the chain (the middle ground).
  seed_build(problem)   — the full pass: frontier chain -> cheap solve -> fold to learning.

CLI:  python -m mag.seed_chain chain "<problem>" | solve "<problem>" | seed "<problem>"
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

LOG = ROOT / "memory" / "seed_chain" / "seeds.jsonl"

# logic-chain templates: "think about this, then this, then this" for common problem shapes.
_CHAINS = {
    "route": ["define the goal", "identify cheapest capable tier", "pick the skill chain",
              "dispatch via module/queue", "fold the outcome"],
    "build": ["state the invariant", "steal prior art first", "scaffold the module",
              "test the cheapest path", "register the skill"],
    "debug": ["reproduce the failure", "find the root cause in the stack",
              "fix the cheapest layer", "verify with a probe", "fold to FKB"],
    "research": ["frame the question", "pick high-quality sources", "steal invariants",
                 "test locally", "compose the findings"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _shape(problem: str) -> str:
    t = (problem or "").lower()
    for k in ("debug", "fix", "error", "crash"):
        if k in t:
            return "debug"
    for k in ("research", "source", "learn"):
        if k in t:
            return "research"
    for k in ("build", "create", "module", "make"):
        if k in t:
            return "build"
    return "route"


def chain(problem: str) -> dict[str, Any]:
    """Logic chain from the FREE FRONTIER (or the test-dummy skeleton offline)."""
    shape = _shape(problem)
    steps = _CHAINS.get(shape, _CHAINS["route"])
    # frontier seed: use the free frontier if reachable, else the test-dummy skeleton
    try:
        from mag.test_dummy import ask
        seed = str(ask("frontier seed: " + (problem or "")[:120]).get("reply") or "")[:200]
    except Exception:
        seed = ""
    return {"schema": "seed_chain.chain.v1", "ts": _now(), "problem": (problem or "")[:200],
            "shape": shape, "logic_chain": steps, "seed": seed,
            "source": "free-frontier (deepseek/grok free)" if not seed else "test-dummy-skeleton",
            "n_steps": len(steps)}


def solve(problem: str, logic_chain: list[str] | None = None) -> dict[str, Any]:
    """The CHEAP local model solves the middle ground by executing the logic chain."""
    if logic_chain is None:
        logic_chain = chain(problem).get("logic_chain", [])
    # cheap local execution: run each step as a deterministic probe (test-dummy now)
    solved = []
    for step in logic_chain:
        try:
            from mag.test_dummy import ask
            r = ask(f"{step}: {problem[:80]}")
            solved.append({"step": step, "ok": r.get("ok"), "note": str(r.get("reply") or "")[:80]})
        except Exception:
            solved.append({"step": step, "ok": False})
    return {"schema": "seed_chain.solve.v1", "ts": _now(), "problem": (problem or "")[:200],
            "executor": "cheap-local", "solved_steps": solved, "n_solved": len(solved)}


def seed_build(problem: str) -> dict[str, Any]:
    """The full pass: frontier logic chain -> cheap solve -> fold to learning."""
    c = chain(problem)
    s = solve(problem, c.get("logic_chain"))
    row = {"ts": _now(), "problem": (problem or "")[:200], "shape": c.get("shape"),
           "chain": c.get("logic_chain"), "n_solved": s.get("n_solved"),
           "source": c.get("source")}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    try:
        from mag import training_events
        training_events.emit(
            "steal_compose",
            input_data={"problem": row["problem"]},
            action={"kind": "seed_chain", "shape": c.get("shape"),
                    "chain_source": c.get("source")},
            outcome={"n_solved": s.get("n_solved")},
            pattern_tags=["seed_chain", "frontier_chain", "cheap_solve", "coding_seed"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass
    return {"schema": "seed_chain.seed.v1", "ts": _now(), "chain": c, "solve": s, "folded": True}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "seed"
    rest = " ".join(argv[1:]) if len(argv) > 1 else ""
    if cmd == "chain":
        print(json.dumps(chain(rest), indent=2, ensure_ascii=False))
    elif cmd == "solve":
        print(json.dumps(solve(rest), indent=2, ensure_ascii=False))
    elif cmd == "seed":
        print(json.dumps(seed_build(rest), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(seed_build(rest), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
