"""Voice/chat trigger dispatcher — parse operator speech into trigger intents, then fire them.

The "when I say 'send' or 'research' it triggers stuff in our systems" seam.
Operator talks -> parse() scans for trigger keywords -> dispatch() enqueues via the
framework's OWN queue (orchestrator.spawn_task / dispatch) so the drainer eats it
(routing doctrine: async -> queue, never ad-hoc terminal), and captures the mention so
ghost SEES it (operator_inbox.capture_mention).

Design: DETERMINISTIC keyword triggers — no LLM needed to fire, cheap + low-ceremony.
The model's judgment only matters for the actual enqueued work, not for the trigger.
The trigger itself is reliable (mappable to process); obedience of the spawned work is
the measured part (the reliable-control doctrine).

CLI:  python -m mag.voice_trigger "<spoken text>"   (parse + dispatch)
      python -m mag.voice_trigger --parse "<text>"   (just show matched triggers, don't fire)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except ImportError:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

# trigger keyword -> action. Action decides HOW we fire it.
TRIGGERS: dict[str, dict[str, Any]] = {
    # ---- enqueue (async -> queue -> drainer) ----
    "send":     {"action": "dispatch", "tag": "send",   "desc": "send to an agent / seat"},
    "dispatch": {"action": "dispatch", "tag": "send",   "desc": "dispatch a goal"},
    "handoff":  {"action": "dispatch", "tag": "send",   "desc": "hand off to a deeper seat"},
    "research": {"action": "research", "tag": "research", "desc": "spawn a research task"},
    "dig":      {"action": "research", "tag": "research", "desc": "deep research dig"},
    "run":      {"action": "run",      "tag": "api",    "desc": "run a goal"},
    "execute":  {"action": "run",      "tag": "api",    "desc": "execute a task"},
    # ---- awareness / steer (capture; veto handled by operator_inbox) ----
    "steer":    {"action": "steer",    "tag": "steer",  "desc": "steer the running agent"},
    "note":     {"action": "steer",    "tag": "steer",  "desc": "leave an operator note"},
    "remember": {"action": "steer",    "tag": "steer",  "desc": "capture for ghost to remember"},
    "idea":     {"action": "idea",     "tag": "idea",   "desc": "capture an idea"},
    # strike-the-chord / CL4R1T4S clarity phrase (both spellings)
    # PURPOSE (operator, 2026-08-14): brings the seat TO COHERENCE — align this instance to the
    # shared map + memory + real state so it is a coherent instance, then act. Not a performance.
    "strike the chord": {"action": "strike", "tag": "strike", "desc": "strike the chord = bring this seat to coherence, then act"},
    "strike the cord":  {"action": "strike", "tag": "strike", "desc": "strike the chord = bring this seat to coherence, then act"},
}

# words that negate a trigger (avoid firing on "don't research", "not a run", etc.)
_NEG = r"\b(don'?t|do not|never|not|without|skip|ignore)\b"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse(text: str) -> list[dict[str, Any]]:
    """Scan freeform speech for trigger keywords -> matched intents (deterministic)."""
    text = (text or "").strip()
    if not text:
        return []
    low = " " + text.lower() + " "
    found: list[dict[str, Any]] = []
    seen = set()
    for kw, meta in TRIGGERS.items():
        if not re.search(rf"\b{re.escape(kw)}\b", low):
            continue
        # skip when the trigger is negated right before it
        if re.search(rf"{_NEG}\s+\b{re.escape(kw)}\b", low):
            continue
        if meta["action"] in seen:
            continue  # one action per utterance (dedupe send/dispatch/handoff -> dispatch)
        seen.add(meta["action"])
        found.append({"trigger": kw, "action": meta["action"], "tag": meta["tag"], "desc": meta["desc"]})
    return found


def dispatch(text: str, *, source: str = "voice") -> dict[str, Any]:
    """Parse + fire triggers. Enqueue actions go to the queue (drainer eats them);
    steer/idea go to the awareness seam (capture_mention)."""
    text = (text or "").strip()
    triggers = parse(text)
    out: dict[str, Any] = {
        "ok": True,
        "schema": "voice_trigger.v1",
        "ts": _now(),
        "source": source,
        "text": text,
        "triggers": triggers,
        "fired": [],
        "captured": None,
    }

    # Always capture the mention so ghost sees it (awareness seam).
    try:
        from mag.operator_inbox import capture_mention
        out["captured"] = capture_mention(text, source=source).get("ok")
    except Exception as e:
        out["capture_error"] = str(e)[:120]

    if not triggers:
        out["ok"] = False
        out["note"] = "no trigger matched — mention still captured for ghost awareness"
        return out

    # Enqueue vs capture split.
    for t in triggers:
        action = t["action"]
        if action == "dispatch":
            out["fired"].append(_fire_dispatch(text, t))
        elif action == "research":
            out["fired"].append(_fire_run(text, t, tag="research"))
        elif action == "run":
            out["fired"].append(_fire_run(text, t, tag="api"))
        elif action in ("steer", "idea", "strike"):
            out["fired"].append({"action": action, "handled_by": "capture_mention", "ok": True})
    return out


def _fire_dispatch(text: str, t: dict[str, Any]) -> dict[str, Any]:
    try:
        from mag.dispatch import dispatch as mag_dispatch
        res = mag_dispatch(text, execute=True)
        return {"action": t["action"], "ok": bool(res.get("ok", True)), "result": _short(res)}
    except Exception as e:
        return {"action": t["action"], "ok": False, "error": str(e)[:200]}


def _fire_run(text: str, t: dict[str, Any], *, tag: str) -> dict[str, Any]:
    try:
        from mag.orchestrator import spawn_task
        sp = spawn_task(text, provider="deepseek", model="deepseek-v4-flash", tag=tag)
        return {"action": t["action"], "ok": bool(sp.get("ok")), "task_id": sp.get("task_id"), "tag": tag}
    except Exception as e:
        return {"action": t["action"], "ok": False, "error": str(e)[:200]}


def _short(res: Any) -> Any:
    if isinstance(res, dict):
        keep = {k: v for k, v in res.items()
                if k in ("ok", "job", "seat", "tier", "task_id", "route", "pending_handoff")}
        return keep or {k: str(v)[:80] for k, v in list(res.items())[:4]}
    return str(res)[:120]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="voice-trigger", description="Parse + fire spoken trigger words")
    ap.add_argument("--parse", action="store_true", help="Only show matched triggers, don't fire")
    ap.add_argument("text", nargs="*", help="the spoken utterance")
    args = ap.parse_args(argv)
    text = " ".join(args.text).strip()
    if not text:
        print(json.dumps({"ok": False, "error": "no text", "known": sorted(TRIGGERS)}, indent=2))
        return 0
    if args.parse:
        print(json.dumps({"ok": True, "text": text, "triggers": parse(text)}, indent=2, default=str))
        return 0
    print(json.dumps(dispatch(text, source="cli"), indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
