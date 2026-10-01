"""Session-aware overseer — reads a VS Code session, extracts the ask, and
decides whether to turn the drainer on and dispatch the introduced task.

This is the "autonomous Sancho": it knows everything that's going on (drainer
state, operator state, queue, fleet, pending handoffs) and uses that full state
to decide — deterministically — whether a task introduced in a session warrants
turning the drainer on and dispatching it. It does NOT guess; it reads the
session transcript, the live system state, and applies a rule-based gate.

Schema: mag_session_overseer.v1
Trail:  memory/runs/session_overseer_trail.jsonl

CLI:
  python -m mag.session_overseer --session <id>          # read + decide (no act)
  python -m mag.session_overseer --session <id> --apply  # read + decide + act
  python -m mag.session_overseer --latest                # latest transcript + decide

REST:
  GET  /api/v1/overseer/session?session=<id>   read + decide (no act)
  POST /api/v1/overseer/session {session, apply:true}   read + decide + act
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "mag_session_overseer.v1"
TRAIL = ROOT / "memory" / "runs" / "session_overseer_trail.jsonl"

# Keywords that indicate a real task was introduced (vs. pure Q&A / chat).
_TASK_HINTS = (
    "build", "implement", "create", "write", "make", "fix", "add", "run",
    "dispatch", "launch", "handoff", "task", "spike", "auto", "route",
    "turn on", "turn the drainer", "queue", "deploy", "refactor", "wire",
)
# Keywords that indicate explicit operator intent to NOT run autonomously yet.
_PAUSE_HINTS = (
    "don't", "do not", "not yet", "hold", "park", "wait", "research only",
    "proposal", "design pack", "leave it", "backburner",
)
_VAGUE = {
    "continue", "go", "next", "yes", "no", "stop", "help", "wait",
    "hold on", "actually", "nevermind", "nvm", "please",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _utc(), "event": event, **fields}, ensure_ascii=False, default=str) + "\n")


def find_transcripts() -> list[Path]:
    """Locate VS Code Copilot session transcripts across all workspaceStorage dirs."""
    out: list[Path] = []
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "workspaceStorage",
        Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "globalStorage",
    ]
    for root in roots:
        for p in root.glob("**/transcripts/*.jsonl") if root.exists() else []:
            out.append(p)
    return out


def read_transcript(session_id: str) -> dict[str, Any]:
    """Read one session transcript -> user messages + tool activity + summary."""
    # 1) by explicit session id
    for p in find_transcripts():
        if p.stem == session_id:
            return _parse_transcript(p)
    # 2) fall back to session store transcript under the current workspace
    cand = ROOT / ".." / ".." / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage"
    return {"ok": False, "error": f"transcript not found for {session_id}"}


def _parse_transcript(path: Path) -> dict[str, Any]:
    users: list[str] = []
    tools: set[str] = set()
    tool_count = 0
    assistant_chars = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return {"ok": False, "error": str(e), "path": str(path)}
    for line in lines:
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type", "")
        d = ev.get("data") or {}
        if t == "user.message":
            c = d.get("content") or ""
            if c.strip() and c.strip().lower() not in _VAGUE:
                users.append(c.strip()[:500])
        elif t == "assistant.message":
            for tr in d.get("toolRequests") or []:
                name = tr.get("name", "")
                if name:
                    tools.add(name)
                    tool_count += 1
            ac = d.get("content") or ""
            assistant_chars += len(ac)
    return {
        "ok": True,
        "path": str(path),
        "session_id": path.stem,
        "n_user_messages": len(users),
        "user_messages": users[-12:],
        "tools_used": sorted(tools),
        "n_tool_calls": tool_count,
        "assistant_chars": assistant_chars,
    }


def _extract_ask(rows: dict[str, Any]) -> dict[str, Any]:
    """Heuristic ask extraction from the last real user messages."""
    users = [u for u in (rows.get("user_messages") or []) if u.strip()]
    if not users:
        return {"ok": True, "ask": "", "has_task": False, "task_hint": 0, "pause_hint": 0, "reason": "no user messages"}
    # The ask is the most recent substantive message that isn't a bare ack.
    ask = users[-1]
    for u in reversed(users):
        low = u.lower()
        if any(h in low for h in _TASK_HINTS) and not (len(u.strip()) < 6):
            ask = u
            break
    low = ask.lower()
    task_hint = sum(1 for h in _TASK_HINTS if h in low)
    pause_hint = sum(1 for h in _PAUSE_HINTS if h in low)
    has_task = task_hint > 0 and pause_hint == 0
    return {
        "ok": True,
        "ask": ask[:300],
        "has_task": has_task,
        "task_hint": task_hint,
        "pause_hint": pause_hint,
        "reason": (
            "task detected (build/run/dispatch keywords)"
            if has_task
            else ("explicit pause (research/proposal/not-yet)" if pause_hint else "no clear task signal")
        ),
    }


def gather_state() -> dict[str, Any]:
    """Full system state the overseer needs to decide (drainer, operator, queue, fleet, handoffs)."""
    out: dict[str, Any] = {}
    try:
        from mag.preferences import drainer_status, operator_status

        out["drainer"] = drainer_status()
        out["operator"] = operator_status()
    except Exception as e:
        out["drainer_error"] = str(e)[:200]
    try:
        from mag.orchestrator import list_queue, list_tasks_live, queue_status

        out["queue"] = queue_status()
        q = list_queue(limit=40)
        out["queue_items"] = [
            {"queue_id": i.get("queue_id"), "goal": (i.get("goal") or "")[:100], "status": i.get("status"), "tag": i.get("tag")}
            for i in q if i.get("status") not in ("done", "failed", "killed")
        ]
        live = list_tasks_live(limit=20)
        out["live_tasks"] = [
            {"task_id": t.get("task_id"), "goal": (t.get("goal") or "")[:80], "status": t.get("status"), "provider": t.get("provider")}
            for t in live
        ]
    except Exception as e:
        out["queue_error"] = str(e)[:200]
    try:
        from mag.peer_handoff import list_peer_handoffs

        ph = list_peer_handoffs(limit=10)
        out["pending_handoffs"] = [h for h in ph if h.get("status") == "filed"]
    except Exception as e:
        out["handoff_error"] = str(e)[:200]
    return out


def decide(session_id: str, *, apply: bool = False) -> dict[str, Any]:
    """Read session -> extract ask -> gather state -> decide -> optionally act."""
    rows = read_transcript(session_id)
    if not rows.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": rows.get("error"), "session_id": session_id}

    ask = _extract_ask(rows)
    state = gather_state()

    drainer_on = bool((state.get("drainer") or {}).get("enabled"))
    operator_active = bool((state.get("operator") or {}).get("operator_active"))
    pending_queue = (state.get("queue_items") or [])
    pending_handoffs = (state.get("pending_handoffs") or [])
    anything_pending = bool(pending_queue or pending_handoffs)

    # DECISION GATE (deterministic — bytes not vibes)
    #  - If session has a task AND there's pending work AND drainer is off AND
    #    operator isn't actively coding -> recommend turning drainer on + dispatching.
    #  - If the session is research/proposal (pause hint) -> do NOT touch drainer.
    #  - If drainer already on -> nothing to do.
    reasons: list[str] = []
    should_enable = False
    action = "none"

    if ask.get("pause_hint"):
        action = "hold"
        reasons.append("session is research/proposal/not-yet — leaving drainer as-is")
    elif drainer_on:
        action = "already_on"
        reasons.append("drainer already enabled — nothing to change")
    elif not ask.get("has_task"):
        action = "hold"
        reasons.append("no clear task introduced in this session — not enabling")
    elif operator_active:
        action = "hold"
        reasons.append("operator is actively coding (MAG_OPERATOR_ACTIVE) — not enabling")
    elif not anything_pending:
        action = "hold"
        reasons.append("no pending queue items or filed handoffs for the drainer to consume")
    else:
        should_enable = True
        action = "enable_drainer"
        reasons.append(f"{len(pending_queue)} queue item(s) + {len(pending_handoffs)} pending handoff(s) waiting — enable drainer to dispatch")

    result = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "session_id": session_id,
        "ask": ask,
        "state": {
            "drainer_enabled": drainer_on,
            "operator_active": operator_active,
            "pending_queue_n": len(pending_queue),
            "pending_handoffs_n": len(pending_handoffs),
            "live_tasks_n": len(state.get("live_tasks") or []),
        },
        "decision": {
            "action": action,
            "should_enable_drainer": should_enable,
            "reasons": reasons,
            "readback": " → ".join(reasons) or "no action needed",
        },
    }

    if apply and should_enable:
        try:
            from mag.preferences import set_drainer

            set_drainer(True)
            result["acted"] = {"drainer": "enabled"}
            result["decision"]["action"] = "enable_drainer_applied"
            _trail("enable_drainer", session_id=session_id, reasons=reasons)
        except Exception as e:
            result["acted"] = {"error": str(e)[:200]}
    else:
        result["acted"] = None

    _trail("decide", session_id=session_id, action=action, should_enable=should_enable, ask=ask.get("ask", "")[:120])
    return result


def latest_session_id() -> str | None:
    files = find_transcripts()
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0].stem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="session-overseer", description="Session-aware overseer: read a VS Code session and decide on the drainer.")
    ap.add_argument("--session", default="", help="Session id to read")
    ap.add_argument("--latest", action="store_true", help="Use the latest transcript")
    ap.add_argument("--apply", action="store_true", help="Apply the decision (enable drainer if warranted)")
    args = ap.parse_args(argv)

    sid = args.session.strip() or (latest_session_id() if args.latest else "")
    if not sid:
        print("usage: session-overseer --session <id> [--apply]  |  --latest [--apply]")
        return 2
    res = decide(sid, apply=bool(args.apply))
    print(json.dumps(res, indent=2, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
