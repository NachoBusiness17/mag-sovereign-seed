"""Canonical memory event ledger for routing, steering, and checkpoints.

This module provides a small append-only JSONL event stream so seats can
recover recent state without replaying full transcripts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

EVENTS_PATH = ROOT / "logs" / "memory_events.jsonl"
CHECKPOINT_INDEX = ROOT / "logs" / "memory_checkpoint_index.json"
SCHEMA = "memory_event.v1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def _hash_obj(data: Any) -> str:
    raw = json.dumps(data, default=str, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def emit_event(
    *,
    event_kind: str,
    seat: str,
    session_id: str,
    tier: str,
    payload: dict[str, Any] | None = None,
    artifact_refs: list[str] | None = None,
    scope: Any | None = None,
) -> dict[str, Any]:
    """Append one canonical event to the memory ledger."""
    payload = payload or {}
    row = {
        "schema": SCHEMA,
        "ts": _utc(),
        "event_kind": str(event_kind or "unknown")[:80],
        "seat": str(seat or "unknown")[:40],
        "session_id": str(session_id or "unknown")[:120],
        "tier": str(tier or "T2")[:16],
        "scope_hash": _hash_obj(scope if scope is not None else payload),
        "artifact_refs": [str(p)[:240] for p in (artifact_refs or [])][:12],
        "payload": payload,
    }
    _append_jsonl(EVENTS_PATH, row)
    return {"ok": True, "event": row}


def emit_checkpoint_summary(
    *,
    seat: str,
    session_id: str,
    tier: str,
    summary_kind: str,
    summary: dict[str, Any],
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Write a checkpoint summary only when its state hash changed."""
    key = f"{seat}:{session_id}:{summary_kind}"
    state_hash = _hash_obj(summary)
    idx: dict[str, str] = {}
    if CHECKPOINT_INDEX.is_file():
        try:
            idx = json.loads(CHECKPOINT_INDEX.read_text(encoding="utf-8"))
        except Exception:
            idx = {}
    if idx.get(key) == state_hash:
        return {"ok": True, "skipped": True, "reason": "duplicate_state_hash", "state_hash": state_hash}

    out = emit_event(
        event_kind="checkpoint.summary",
        seat=seat,
        session_id=session_id,
        tier=tier,
        payload={"summary_kind": summary_kind, "summary": summary, "state_hash": state_hash},
        artifact_refs=artifact_refs,
        scope=summary,
    )
    idx[key] = state_hash
    CHECKPOINT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_INDEX.write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")
    return out


def emit_route_decision(*, goal: str, lane: str, reason: str, clerk_model: str, fallback_count: int) -> dict[str, Any]:
    return emit_event(
        event_kind="route.decision",
        seat="router",
        session_id="route_goal",
        tier="T2",
        payload={
            "goal": (goal or "")[:300],
            "lane": lane,
            "reason": (reason or "")[:200],
            "clerk_model": clerk_model,
            "fallback_count": int(fallback_count or 0),
        },
        artifact_refs=["mag/route.py", "configs/router_policy.yaml"],
        scope={"goal": (goal or "")[:300], "lane": lane, "reason": reason},
    )


def emit_steer_lifecycle(
    *,
    task_id: str,
    steer_id: str,
    status: str,
    phase: str = "",
    source_tier: str = "",
    reason: str = "",
) -> dict[str, Any]:
    return emit_event(
        event_kind=f"steer.{status}",
        seat="overseer",
        session_id=task_id,
        tier=source_tier or "T2",
        payload={
            "task_id": task_id,
            "steer_id": steer_id,
            "status": status,
            "phase": (phase or "")[:40],
            "reason": (reason or "")[:200],
        },
        artifact_refs=["mag/pigeonhole.py", "dashboard/rest.py"],
        scope={"task_id": task_id, "steer_id": steer_id, "status": status, "phase": phase},
    )


def recent_events(*, limit: int = 200, event_kind_prefix: str | None = None) -> list[dict[str, Any]]:
    if not EVENTS_PATH.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in EVENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if event_kind_prefix:
            if not str(row.get("event_kind") or "").startswith(event_kind_prefix):
                continue
        out.append(row)
    return out[-max(1, min(int(limit), 5000)):]
