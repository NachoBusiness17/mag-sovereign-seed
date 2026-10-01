"""loop_feedback — close the feedback side of the loop: READ BACK what the swarm produced so the
cadence sees its own outputs (grounded, not just what was enqueued).

Operator (2026-08-11): "next" — after feeding forward (detect novel orphans -> route to swarm), the
loop must READ BACK what came out: completed swarm tasks, filed research packs, folded invariants,
and the advanced verkle chain. The loop is only honest if it measures its own outputs.

THE READ-BACK (deterministic + $0, reads the real output surfaces on disk):
  swarm_worker.status()     -> the swarm queue: queued/running/done tasks + their results.
  research_packs/           -> the steals the swarm filed back (.answer.remote.md).
  percolator invariants     -> the invariants folded from routed novel research.
  verkle chain              -> the chain advanced = the heartbeat wrote new knots.
  returns the LOOP OUTPUT = what the cadence actually produced (the feedback signal).

Schema: loop_feedback.v1 · deterministic + $0 · reuse: swarm_worker, verkle_knot, percolator
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

SCHEMA = "loop_feedback.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_back() -> dict[str, Any]:
    """READ BACK what the swarm produced: the loop's own outputs, grounded from disk."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "ts": _now()}

    # 1) swarm queue status (completed tasks + their results)
    try:
        from mag import swarm_worker
        s = swarm_worker.status()
        out["swarm_queue"] = {k: s.get(k) for k in ("n_queued", "n_running", "n_done", "n_failed")
                              if k in s}
        done = [t for t in (s.get("tasks") or []) if t.get("status") == "done"][-8:]
        out["recent_done"] = [{"task_id": t.get("task_id"), "goal": (t.get("goal") or "")[:80]}
                              for t in done]
    except Exception as e:
        out["swarm_queue_error"] = str(e)[:80]

    # 2) research packs the swarm filed back (the steals/research outputs)
    try:
        pd = ROOT / "memory" / "research_packs"
        if pd.is_dir():
            packs = sorted(pd.glob("*.answer.*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            out["n_packs"] = len(packs)
            out["recent_packs"] = [p.name for p in packs[:8]]
    except Exception as e:
        out["packs_error"] = str(e)[:80]

    # 3) invariants folded (percolator registry grew = the loop learned)
    try:
        from mag import percolator
        reg = percolator._load_registry() if hasattr(percolator, "_load_registry") else {}
        out["n_invariants"] = len(reg.get("invariants") or {})
    except Exception as e:
        out["invariants_error"] = str(e)[:80]

    # 4) the verkle chain advanced (the heartbeat wrote new knots = the loop is alive)
    try:
        tip = ROOT / "memory" / "biography" / "verkle_tip.json"
        if tip.is_file():
            t = json.loads(tip.read_text(encoding="utf-8"))
            out["chain"] = {"n_leaves": t.get("n_leaves"), "root": (t.get("root") or "")[:16],
                            "last_session": t.get("last_session_id")}
    except Exception as e:
        out["chain_error"] = str(e)[:80]

    out["loop_output"] = {
        "n_done_tasks": out.get("swarm_queue", {}).get("n_done"),
        "n_packs": out.get("n_packs"),
        "n_invariants": out.get("n_invariants"),
        "chain_leaves": out.get("chain", {}).get("n_leaves"),
    }
    out["note"] = ("FEEDBACK: the loop read back what the swarm produced (done tasks, filed packs, "
                   "folded invariants, advanced chain) — measured outputs, not just enqueues")
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "read_back()->the swarm's produced outputs (done tasks, research packs, "
                        "folded invariants, advanced verkle chain) = the loop's feedback signal",
            "cost": "deterministic + $0 (reads the real output surfaces)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="loop-feedback")
    ap.add_argument("cmd", nargs="?", default="read", choices=["read", "status"])
    a = ap.parse_args()
    print(json.dumps(read_back() if a.cmd == "read" else status(), indent=2, default=str))
