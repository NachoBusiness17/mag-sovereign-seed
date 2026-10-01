"""steer_router — the FORMALIZED STEER PROTOCOL: when the operator steers, CONSIDER it, look at the
router, RIGHTSIZE it, do what the task calls for WITHOUT interrupting existing tasks — even if that
means putting a PIN in one and coming back to it later (as we did naturally this session).

Operator (2026-08-10): "when i steer i want you to consider it look at your router and rightsize it
and do what you think the task calls for without interrupting existing tasks. even if its putting a
pin in one and coming back to it later like we did here in this session a few times i want to
formalize it. i want our behavioral learning corpus expanding human ai whatever."

THE PROTOCOL (the pin-and-resume router):
  * steer(instruction)  -> CONSIDER it: classify + rightsize into one of three routes.
       - 'now'      : deterministic / quick ($0 module call) -> do it NOW, don't park anything.
       - 'enqueue'  : async / heavy (swarm, frontier, batch) -> send to the task queue, DON'T
                      interrupt current work.
       - 'pin'      : needs interactive context (like this session's coding) -> PIN the current
                      task (remember exactly where it was) and switch to the steer; RESUME later.
  * pin(reason)        -> push the current task onto the PIN STACK (context preserved for resume).
  * resume()           -> pop the pin stack, restore the pinned task and continue.
  * record_steering()  -> append every steering decision to the BEHAVIORAL LEARNING CORPUS
                      (memory/pile/behavioral_corpus.jsonl) — the human-ai interaction data.

The router makes the informal "pin and come back" we did this session a first-class, tracked,
autonomous behavior. Deterministic, $0.

Schema: steer_router.v1 · CLI: python -m mag.steer_router steer "<instruction>" | pins | resume | corpus
"""
from __future__ import annotations

import json
import re
import sys
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

SCHEMA = "steer_router.v1"
PINS = ROOT / "memory" / "runs" / "steer_router" / "pins.json"
CORPUS = ROOT / "memory" / "pile" / "behavioral_corpus.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_pins() -> list[dict[str, Any]]:
    if PINS.is_file():
        try:
            return json.loads(PINS.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_pins(pins: list[dict[str, Any]]) -> None:
    PINS.parent.mkdir(parents=True, exist_ok=True)
    PINS.write_text(json.dumps(pins, ensure_ascii=False, indent=2), encoding="utf-8")


# --- rightsize: classify a steer into now / enqueue / pin --------------------------------
# Signal words for each route. Deterministic keyword classifier (the rightsizing).
_NOW = ["run", "fold", "build", "fix", "check", "test", "validate", "measure", "diagnose",
        "steal", "synthesize", "mine", "dedupe", "apply", "compile"]
_ENQ = ["swarm", "dispatch", "start", "batch", "cron", "frontier", "enqueue", "harvest",
        "research", "expand", "background"]
_PIN = ["steer", "puppeteer", "experiment", "play", "design", "proposal", "architecture",
        "formalize", "protocol"]


def _classify(instruction: str) -> str:
    low = (instruction or "").lower()
    scores = {m: sum(1 for w in words if w in low) for m, words in
              [("now", _NOW), ("enqueue", _ENQ), ("pin", _PIN)]}
    return max(scores, key=scores.get) if any(scores.values()) else "pin"


def rightsize(instruction: str) -> dict[str, Any]:
    """RIGHTSIZE a steer: what does the task actually call for? now / enqueue / pin."""
    mode = _classify(instruction)
    reason = {
        "now": "deterministic / quick — do it now without parking anything",
        "enqueue": "async / heavy — send to the task queue, don't interrupt current work",
        "pin": "needs interactive context — pin the current task, handle this, resume later",
    }[mode]
    return {"ok": True, "schema": SCHEMA, "mode": mode, "reason": reason}


# --- the pin-and-resume protocol ----------------------------------------------------------
def pin(current_task: str, *, reason: str = "operator steer") -> dict[str, Any]:
    """PUT A PIN in the current task: push it onto the pin stack with context to resume later."""
    pins = _load_pins()
    pins.append({"task": current_task, "reason": reason, "pinned_at": _now(),
                 "resumed": False})
    _save_pins(pins)
    return {"ok": True, "schema": SCHEMA, "pinned": current_task, "reason": reason,
            "n_pins": len(pins), "note": "pinned — will resume later"}


def resume() -> dict[str, Any]:
    """RESUME the most recently pinned task (pop the pin stack)."""
    pins = _load_pins()
    if not pins:
        return {"ok": False, "schema": SCHEMA, "error": "no pinned tasks to resume"}
    top = pins.pop()
    top["resumed"] = True
    top["resumed_at"] = _now()
    _save_pins(pins)
    return {"ok": True, "schema": SCHEMA, "resumed": top.get("task"), "reason": top.get("reason"),
            "n_pins_left": len(pins)}


def pins() -> dict[str, Any]:
    """The current pin stack (what's parked, waiting to resume)."""
    pins_ = _load_pins()
    return {"ok": True, "schema": SCHEMA, "n_pins": len(pins_),
            "pins": [{"task": p.get("task"), "reason": p.get("reason"),
                      "pinned_at": p.get("pinned_at")} for p in pins_]}


# --- the main steer entry ----------------------------------------------------------------
def steer(instruction: str, *, current_task: str | None = None) -> dict[str, Any]:
    """CONSIDER a steer: rightsize it and route it, WITHOUT interrupting existing work.

    Route semantics:
      now     -> run inline (the caller does it), no pin.
      enqueue -> push to the task queue (orchestrator), no interrupt.
      pin     -> pin the current_task, the steer is handled, resume() later.
    Every decision is recorded to the behavioral corpus.
    """
    rs = rightsize(instruction)
    mode = rs["mode"]
    routed = None
    if mode == "enqueue":
        try:
            from mag import orchestrator as orch
            q = orch.enqueue(instruction.strip(), provider="ollama", tag="steer")
            routed = {"action": "enqueued", "queue_id": q.get("queue_id"), "ok": bool(q.get("ok"))}
        except Exception as e:
            routed = {"action": "enqueue_failed", "error": str(e)[:120]}
    elif mode == "pin" and current_task:
        p = pin(current_task, reason=instruction[:80])
        routed = {"action": "pinned_current", "pinned": current_task, "n_pins": p.get("n_pins")}
    else:
        routed = {"action": "run_now"}
    record_steering(instruction, mode, routed, current_task)
    return {"ok": True, "schema": SCHEMA, "instruction": instruction[:120], "mode": mode,
            "reason": rs["reason"], "routed": routed}


# --- behavioral learning corpus ----------------------------------------------------------
def record_steering(instruction: str, mode: str, routed: dict[str, Any] | None,
                    current_task: str | None) -> None:
    """Append the steering decision to the BEHAVIORAL LEARNING CORPUS (human-ai interaction data)."""
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "schema": "behavioral_corpus.v1", "ts": _now(),
            "steer_input": instruction[:400], "mode": mode,
            "routed": routed, "current_task": current_task or "",
        }, ensure_ascii=False) + "\n")


def corpus(*, limit: int = 20) -> dict[str, Any]:
    """Read the behavioral learning corpus (the human-ai interaction records)."""
    if not CORPUS.is_file():
        return {"ok": False, "schema": SCHEMA, "error": "no behavioral corpus yet"}
    rows = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return {"ok": True, "schema": SCHEMA, "n_rows": len(rows), "rows": rows[-limit:]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="steer-router")
    ap.add_argument("cmd", nargs="?", default="pins", choices=["steer", "pins", "resume", "corpus", "rightsize"])
    ap.add_argument("instruction", nargs="*", default=[])
    ap.add_argument("--current", default="")
    args = ap.parse_args(argv)
    instr = " ".join(args.instruction)
    if args.cmd == "steer":
        print(json.dumps(steer(instr, current_task=args.current or None), indent=2))
    elif args.cmd == "resume":
        print(json.dumps(resume(), indent=2))
    elif args.cmd == "corpus":
        print(json.dumps(corpus(), indent=2, default=str))
    elif args.cmd == "rightsize":
        print(json.dumps(rightsize(instr), indent=2))
    else:
        print(json.dumps(pins(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
