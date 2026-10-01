"""Mag brain — unified API surface for multi-agent OS clients.

Slow local (Ollama) + fast observers (DeepSeek, etc.) + breadcrumbs + routing.
Schema: mag_brain.v1
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "mag_brain.v1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def brain_pulse() -> dict[str, Any]:
    """Proprioception: body, desk, trust, breadcrumbs, recent pulse."""
    from mag.decision_framework import decide
    from mag.display import build_display_payload
    from mag.desk_dialogue import read_cursor, read_trust_status
    from mag.nervous_system import glance_cached
    from mag.operator_inbox import status as inbox_status
    from mag.power import stack_status

    display = build_display_payload(event_limit=6, fast=True)
    nervous = glance_cached(max_age_s=30.0, refresh=False)
    inbox = inbox_status()
    framework = decide("", include_breadcrumbs=True)
    power = stack_status()

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "mode": "pulse",
        "body": nervous.get("body"),
        "integral_ok": nervous.get("integral_ok"),
        "desk_trust": read_trust_status(),
        "desk_cursor": read_cursor(),
        "desk": display.get("desk"),
        "headline": display.get("headline"),
        "events": display.get("events"),
        "stack": {
            "headline": power.get("headline"),
            "fleet": power.get("fleet"),
            "endpoint": "GET /api/v1/stack",
        },
        "breadcrumbs": {
            "pending": int(inbox.get("pending_n") or 0),
            "committed": int(inbox.get("committed_n") or 0),
            "layer": "operator_inbox",
        },
        "interference": framework.get("interference"),
        "poll_seconds": 15,
        "endpoints": {
            "pulse": "GET /api/v1/brain",
            "stack": "GET /api/v1/stack",
            "decide": "POST /api/v1/brain {action:decide, goal}",
            "slow_wake": "POST /api/v1/brain {action:slow_wake, goal?, note?}",
            "steer": "POST /api/v1/brain {action:steer, text}",
            "breadcrumb": "POST /api/v1/brain {action:breadcrumb, text}",
            "route": "POST /api/v1/brain {action:route, goal}",
            "dispatch": "POST /api/v1/brain {action:dispatch, goal, execute?}",
        },
    }


def brain_act(body: dict[str, Any]) -> dict[str, Any]:
    """Single action entrypoint for external multi-agent OS clients."""
    action = str(body.get("action") or body.get("cmd") or "").strip().lower()
    goal = str(body.get("goal") or body.get("question") or body.get("note") or "").strip()
    text = str(body.get("text") or body.get("steer") or body.get("breadcrumb") or goal).strip()

    if action in ("", "pulse", "status"):
        return brain_pulse()

    if action == "decide":
        if not goal:
            return {"ok": False, "error": "goal required for decide"}
        from mag.decision_framework import decide

        out = decide(goal, depth=str(body.get("depth") or "").strip() or None)
        out["schema"] = SCHEMA
        out["action"] = "decide"
        out["ts"] = _utc()
        return out

    if action == "route":
        if not goal:
            return {"ok": False, "error": "goal required for route"}
        from mag.router import route

        return {
            "ok": True,
            "schema": SCHEMA,
            "action": "route",
            "ts": _utc(),
            "route": route(goal, depth=str(body.get("depth") or "").strip() or None),
        }

    if action == "dispatch":
        if not goal:
            return {"ok": False, "error": "goal required for dispatch"}
        from mag.dispatch import dispatch

        execute = body.get("execute", True)
        if isinstance(execute, str):
            execute = execute.lower() not in ("0", "false", "no")
        out = dispatch(
            goal,
            execute=execute,
            force_provider=str(body.get("force_provider") or "").strip() or None,
            force_seat=str(body.get("force_seat") or "").strip() or None,
        )
        out["schema"] = SCHEMA
        out["action"] = "dispatch"
        out["ts"] = _utc()
        return out

    if action in ("steer", "steer_desk"):
        if not text:
            return {"ok": False, "error": "text required for steer"}
        from mag.desk_dialogue import post_desk_steer

        steer = post_desk_steer(text)
        return {
            "ok": bool(steer.get("ok")),
            "schema": SCHEMA,
            "action": "steer",
            "ts": _utc(),
            "steer": steer,
            "hint": "Queued for desk-local; picked up on next slow_wake turn",
        }

    if action in ("breadcrumb", "breadcrumbs", "inbox"):
        if not text:
            return {"ok": False, "error": "text required for breadcrumb"}
        from mag.operator_inbox import commit_guidance

        queued = commit_guidance(text, source=str(body.get("source") or "brain_api"))
        return {
            "ok": bool(queued.get("ok", True)),
            "schema": SCHEMA,
            "action": "breadcrumb",
            "ts": _utc(),
            "breadcrumb": queued,
            "hint": "Deferred operator note — drained at desk/agent checkpoints",
        }

    if action in ("handoff_loop", "handoffs"):
        from mag.desk_dialogue import handoff_loop

        out = handoff_loop(
            handoffs=int(body.get("handoffs") or 5),
            operator_note=str(body.get("operator_note") or body.get("note") or goal or ""),
            canvas=str(body.get("desk_canvas") or body.get("canvas") or "").strip() or None,
        )
        out["schema"] = SCHEMA
        out["action"] = "handoff_loop"
        out["ts"] = _utc()
        return out

    if action in ("slow_wake", "slow-wake", "handoff"):
        from mag.desk_dialogue import slow_wake

        note = str(body.get("operator_note") or body.get("note") or goal).strip()
        canvas = str(body.get("desk_canvas") or body.get("canvas") or "").strip() or None
        out = slow_wake(operator_note=note, canvas=canvas)
        out["schema"] = SCHEMA
        out["action"] = "slow_wake"
        out["ts"] = _utc()
        out["pattern"] = "slow_local → board_edit? → fast_observer_wake"
        return out

    if action in ("wipe", "wipe_board"):
        from mag.desk_dialogue import wipe_board

        out = wipe_board()
        out["schema"] = SCHEMA
        out["action"] = "wipe_board"
        out["ts"] = _utc()
        return out

    if action == "refresh_local":
        from mag.desk_dialogue import refresh_local_desk

        out = refresh_local_desk(clear_dialogue=bool(body.get("clear_dialogue", True)))
        out["schema"] = SCHEMA
        out["action"] = "refresh_local"
        out["ts"] = _utc()
        return out

    if action == "broadcast_steer":
        cmd = str(body.get("cmd") or body.get("text") or text).strip()
        if not cmd:
            return {"ok": False, "error": "cmd required (e.g. !steer focus on goal)"}
        from mag.governance import broadcast_steer

        out = broadcast_steer(cmd)
        out["schema"] = SCHEMA
        out["action"] = "broadcast_steer"
        out["ts"] = _utc()
        return out

    return {
        "ok": False,
        "error": f"unknown action {action!r}",
        "schema": SCHEMA,
        "actions": [
            "pulse",
            "decide",
            "route",
            "dispatch",
            "slow_wake",
            "steer",
            "breadcrumb",
            "refresh_local",
            "broadcast_steer",
        ],
    }
