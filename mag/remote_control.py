"""Authenticated, queue-only remote control for Direct Mag.

This is deliberately narrower than the dashboard API: a remote device may
inspect readiness and file an intent, but it cannot run a shell command or
approve arbitrary tools.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

TOKEN_ENV = "MAG_REMOTE_TOKEN"
RECEIPTS_PATH = ROOT / "memory" / "handoff" / "remote_receipts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configured() -> bool:
    return len(os.environ.get(TOKEN_ENV, "")) >= 24


def authorized(candidate: str | None) -> bool:
    expected = os.environ.get(TOKEN_ENV, "")
    supplied = str(candidate or "")
    return len(expected) >= 24 and hmac.compare_digest(expected, supplied)


def token_from_headers(headers: Any) -> str:
    auth = str(headers.get("Authorization") or "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return str(headers.get("X-Mag-Token") or "").strip()


def _receipt(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    safe = {k: v for k, v in payload.items() if k not in {"token", "authorization"}}
    row = {"schema": "remote_receipt.v1", "ts": _now(), "event": event, **safe}
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    row["sha256"] = hashlib.sha256(canonical).hexdigest()
    try:
        RECEIPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    return row


def status() -> dict[str, Any]:
    from mag.repo_readiness import repo_readiness

    repo = repo_readiness(ROOT)
    try:
        from mag.orchestrator import list_queue

        queue = list_queue(limit=20)
    except Exception:
        queue = []
    active = [q for q in queue if q.get("status") in {"queued", "running"}]
    return {
        "ok": True,
        "schema": "remote_control_status.v1",
        "ts": _now(),
        "configured": configured(),
        "mode": "queue_only",
        "repo": repo,
        "queue": {"active": len(active), "recent": active[:8]},
        "guardrails": ["no remote shell", "no remote approvals", "bearer token required"],
    }


def submit_intent(body: dict[str, Any]) -> dict[str, Any]:
    goal = str(body.get("goal") or "").strip()
    if not goal:
        return {"ok": False, "error": "goal required"}
    if len(goal) > 4000:
        return {"ok": False, "error": "goal too long (4000 max)"}

    from mag.operating_protocol import build_envelope

    depth = str(body.get("depth") or "job").strip().lower()
    if depth not in {"job", "build"}:
        depth = "job"
    envelope = build_envelope(goal, source="tablet", depth=depth, dry=True)
    if not envelope.get("ok"):
        receipt = _receipt("intent_blocked", {"intent_id": envelope.get("intent_id"), "goal": goal[:500], "envelope": envelope})
        return {"ok": False, "error": "router blocked intent", "envelope": envelope, "receipt": receipt}

    from mag.peer_handoff import file_peer_handoff

    handoff = file_peer_handoff(
        goal=goal,
        brief=json.dumps(envelope, ensure_ascii=False, default=str)[:4000],
        from_seat="tablet",
        to_seat="personal-router",
        status="filed",
        meta={"intent_id": envelope.get("intent_id"), "source": "remote-control"},
    )
    from mag.governor_autorun import enqueue_routed

    queued = enqueue_routed(goal, tag=f"remote-{envelope.get('intent_id')}", depth=depth)
    outcome = "queued" if queued.get("ok") else "filed_not_queued"
    receipt = _receipt(
        outcome,
        {
            "intent_id": envelope.get("intent_id"),
            "goal": goal[:500],
            "handoff_id": handoff.get("handoff_id"),
            "queue_id": queued.get("id") or queued.get("task_id") or queued.get("queue_id"),
            "route": envelope.get("execution"),
            "queue_result": queued,
        },
    )
    try:
        from mag.training_events import emit

        emit(
            "route_decision",
            join={"queue_id": str(receipt.get("queue_id") or ""), "task_id": str(envelope.get("intent_id") or "")},
            input_data={"goal": goal[:1000], "source": "tablet"},
            action={"route": envelope.get("execution"), "economics": envelope.get("routing_economics")},
            outcome={"status": outcome, "filed": bool(handoff.get("ok"))},
            pattern_tags=["remote", "cheap-handoff", "direct-mag"],
            exportable=False,
        )
    except Exception:
        pass
    return {"ok": bool(queued.get("ok")), "status": outcome, "envelope": envelope, "handoff": handoff, "queue": queued, "receipt": receipt}
