"""agent_os_loop — the flywheel cycle: one deterministic agent-as-OS iteration.

Operator (2026-08-11): "we want to create something emergent greater than the sum of its parts i
want us to own the whole stack agent as os" + "deep research and build".

DEEP-RESEARCH SYNTHESIS (grounded in our master doctrine, swarm-greater-than-parts):
The system exceeds a lone frontier model by COMPOUNDING — one frontier model has a ceiling (one
context, serial, no self-compounding memory), but a coordinated loop does not. The loop:
  COMPACT   (frontier -> spec)   -> a weave goal is decomposed into bite-sized bits
  EXECUTE   (cheap swarm in parallel) -> flock runs, cheapest-capable tier
  FOLD      (corpus learns)      -> the weave + seams fold to the ledger/verkle
  COMPOUND  (next round sharper) -> the grown corpus seeds the next cycle
  ANCHOR    (verkle sovereign)   -> content-addressed, tamper-evident, turtles-all-the-way-down
Each cycle is the atomic unit of the OS. It is deterministic + $0 (no LLM in the cycle itself; the
SEAMS delegate to the swarm/frontier, budget-gated + rightsized). This is the agent-as-OS core.

Schema: agent_os_loop.v1
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

SCHEMA = "agent_os_loop.v1"
STATE = ROOT / "memory" / "runs" / "agent_os_loop"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def cycle(goal: str, *, n_workers: int = 4, budget: float = 2.0,
          render: bool = True) -> dict[str, Any]:
    """Run ONE flywheel cycle (deterministic, $0, rightsized, budget-gated).

    weave -> shade seams (budget-capped) -> fold to ledger -> render visual register -> cadence
    note (next round reads the grown corpus = compounding). Reuses our verified pieces.
    """
    from mag import memweave as mw

    # COMPACT + EXECUTE + FOLD: one deterministic weave (decompose -> flock -> consensus -> record)
    w = mw.weave(goal, n_workers=n_workers, budget=budget, render=render)

    # COMPOUND: the next cycle reads what this one folded (the grown corpus) -> sharper
    compound = {"next_reads": str(ROOT / "memory" / "runs" / "memweave" / "weaves.jsonl"),
                "why": "each cycle folds; the next weave mounts the grown corpus (compounding)"}

    # ANCHOR: fold the cycle itself as a verkle knot (content-addressed, sovereign)
    anchored: dict[str, Any] = {}
    try:
        from mag.verkle_knot import append_verkle_knot
        minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        dossier = {
            "session_id": f"agent_os_cycle_{abs(hash(goal)) % 100000}",
            "time": {"created_at": {"iso_minute": minute, "unix_minute": None, "date": None},
                     "updated_at": {"iso_minute": minute, "unix_minute": None, "date": None}},
            "scalar_knot": {"duration_minutes": 0.1, "tension_index": str(len(goal))[:8],
                            "residual_weight": 1.0,
                            "theme_vector": {"dominant": "agent_os_cycle", "basis": ["loop", "fold", "sovereign", "compound"],
                                             "raw": [n_workers, w.get("n_escalated", 0) or 0, 0, 0],
                                             "normalized": [1.0, 0.0, 0.0, 0.0]}},
            "content_commit": {"hex": str(abs(hash(goal)))[:8]},
            "cycle": {"goal": goal[:200], "n_workers": n_workers, "budget": budget},
        }
        anchored = append_verkle_knot(dossier)
    except Exception as e:
        anchored = {"ok": False, "error": str(e)[:120]}

    # cadence-safe return: what ran, what it spent, what it folded, what's next
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "goal": goal[:200],
            "phase": {"compact_execute_fold": True, "shade_seams": True, "render": bool(render),
                      "compound": True, "anchor": bool(anchored.get("ok"))},
            "weave": {"n_bits": len(w.get("bits", [])), "n_workers": w.get("n_workers"),
                      "n_escalated": w.get("gap", {}).get("n_escalated", 0),
                      "budget_used": w.get("gap", {}).get("used", 0)},
            "visual": w.get("visual", {}).get("image") if render else None,
            "anchored": anchored, "compound": compound,
            "note": "deterministic + $0 cycle; the SEAMS delegate to the swarm/frontier, budget-gated"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "cycle": "compact->execute->fold->compound->anchor (one agent-as-OS iteration)",
            "deterministic": True, "cost": "$0 in-cycle; seams delegate budget-gated",
            "next": "run cycle() each cadence tick; the corpus compounds each round"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="agent-os-loop")
    ap.add_argument("goal", nargs="?", default="weave the agent-as-OS flywheel")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget", type=float, default=2.0)
    a = ap.parse_args(argv)
    print(json.dumps(cycle(a.goal, n_workers=a.workers, budget=a.budget), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
