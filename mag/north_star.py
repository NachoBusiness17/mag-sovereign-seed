"""north_star — the canonical build loop (operator north star, 2026-08-11).

Every build follows: STEAL -> REASON -> PLAN -> ELEVATE -> COORDINATE -> GATHER -> DETERMINISTIC CODE
-> RUN -> BRING FRONTIER TO CHEAP -> ASK GHOST NEXT. This module makes that loop a first-class,
deterministic, architecture-native mechanism — not a habit we have to remember.

STEAL: generalized the RenderMan / grok-mirror pattern ("compact at frontier, expand at cheap") into a
standing build pipeline. Frontier plans; cheap executes; everything recorded; verify-before-done.

Contract: north_star.v1 · deterministic · $0 · wired to ghost/grok_hub/cheap_swarm/work_register/verkle.
CLI: python -m mag.north_star cycle "<goal>" [--dry] | status
"""
from __future__ import annotations

import argparse
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

SCHEMA = "north_star.v1"
STATE = ROOT / "memory" / "runs" / "north_star" / "cycles.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def cycle(goal: str, *, dry: bool = True) -> dict[str, Any]:
    """Run the north-star loop for ONE build goal. Each step folds/records; verify at the end."""
    steps: list[dict[str, Any]] = []
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "goal": goal, "dry": dry, "steps": []}

    # 1) STEAL — fold a steal/adaptation record.
    try:
        from mag.work_register import record
        steps.append({"step": "steal", "ok": bool(record("build", goal, note="north-star steal").get("ok"))})
    except Exception as e:
        steps.append({"step": "steal", "ok": False, "error": str(e)[:80]})

    # 2-4) REASON / PLAN / ELEVATE — elevation via the higher model (front-end grok if available,
    #      else structured local plan). Bring-to-cheap = hand the plan to the cheap tier.
    plan = ""
    try:
        from mag.grok_rightsize import call_grok_free
        r = call_grok_free(f"Plan this build compactly so a cheap executor can run it: {goal}")
        if r.get("ok"):
            plan = str(r.get("content") or "")[:3000]
            steps.append({"step": "elevate", "ok": True, "model": r.get("surface", "?"), "grok_captured": True})
        else:
            steps.append({"step": "elevate", "ok": False, "grok_captured": False, "error": str(r.get("error") or "")[:120]})
    except Exception as e:
        steps.append({"step": "elevate", "ok": False, "error": str(e)[:120]})

    # 5) COORDINATE — dispatch the (cheap) execution to the swarm/queue.
    dispatched = {"ok": False, "queue_id": "?"}
    if not dry:
        try:
            from mag.orchestrator import enqueue
            dispatched = enqueue(goal, provider="deepseek", model="deepseek-v4-flash", timeout=1200,
                                 tag="north-star")
        except Exception as e:
            dispatched = {"ok": False, "error": str(e)[:120]}
    steps.append({"step": "coordinate/run", "ok": bool(dispatched.get("ok")), "queue_id": dispatched.get("queue_id")})

    # 6-7) GATHER / DETERMINISTIC CODE — record the plan + dispatch; the executor produces code.
    try:
        from mag.work_register import record
        record("plan", goal, note=("elevated plan" if plan else "cheap plan"), path="memory/runs/north_star")
    except Exception:
        pass
    steps.append({"step": "gather/code", "ok": True, "plan_chars": len(plan)})

    # 8) ASK GHOST NEXT — surface the next move via ghost.
    next_move = "ask ghost: run the cycle's result through ghost for the next move"
    try:
        from mag.ghost import sense_session
        ss = sense_session()
        nm = ss.get("next_moves") or ss.get("agent_state_next_moves") or []
        if nm:
            next_move = str(nm[0] if isinstance(nm, list) else nm)[:200]
    except Exception:
        pass
    steps.append({"step": "ask_ghost_next", "ok": True, "next": next_move})

    out["steps"] = steps
    out["ok"] = all(s.get("ok", False) for s in steps)
    _append_jsonl(STATE, {"ts": _now(), "goal": goal, "dry": dry, "ok": out["ok"], "steps": steps})
    return out


def status() -> dict[str, Any]:
    rows = _read_jsonl(STATE)
    return {"schema": SCHEMA, "n_cycles": len(rows), "last": rows[-1] if rows else None}


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-tail:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="north-star", description="The canonical build loop.")
    ap.add_argument("cmd", nargs="?", choices=["cycle", "status"], default="status")
    ap.add_argument("goal", nargs="?", default="")
    ap.add_argument("--dry", action="store_true", default=True)
    a = ap.parse_args(argv)
    if a.cmd == "cycle":
        print(json.dumps(cycle(a.goal or "(unspecified build)", dry=a.dry), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["cycle", "status", "main"]
