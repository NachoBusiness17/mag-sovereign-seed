"""Durable operator mode shared by every autonomous Mag surface.

The old pause controls were process-local or subsystem-local.  That made an
intentional operator pause look like a crash after a restart, and allowed a
different loop to keep working.  This module is the small shared control
plane: one atomic JSON state file, one append-only trail, no provider calls,
and no lifecycle actions.

Schema: operator_mode.v1
Modes: running | paused
Scopes: autonomous | all_agents
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "operator_mode.v1"
STATE_PATH = ROOT / "state" / "operator_mode.json"
TRAIL_PATH = ROOT / "state" / "operator_mode.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "mode": "running",
        "scope": "autonomous",
        "reason": "not explicitly set",
        "requested_by": "system",
        "changed_at": None,
        "until": None,
        "exists": False,
    }


def _expired(until: Any) -> bool:
    if not until:
        return False
    try:
        value = str(until).replace("Z", "+00:00")
        deadline = datetime.fromisoformat(value)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= deadline.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return False


def read() -> dict[str, Any]:
    """Read effective mode without raising into an autonomous loop."""
    if not STATE_PATH.is_file():
        return _default()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            return {
                **_default(),
                "mode": "invalid",
                "reason": "operator_mode.json has an unknown schema",
                "exists": True,
                "path": str(STATE_PATH),
            }
        mode = data.get("mode")
        if mode not in {"running", "paused"}:
            return {
                **_default(),
                "mode": "invalid",
                "reason": "operator_mode.json has an unknown mode",
                "exists": True,
                "path": str(STATE_PATH),
            }
        out = dict(data)
        out["exists"] = True
        out["expired"] = bool(mode == "paused" and _expired(out.get("until")))
        if out["expired"]:
            out["effective_mode"] = "running"
        else:
            out["effective_mode"] = mode
        return out
    except (OSError, json.JSONDecodeError, TypeError):
        return {
            **_default(),
            "mode": "invalid",
            "reason": "operator_mode.json could not be read",
            "exists": True,
            "path": str(STATE_PATH),
        }


def _write(state: dict[str, Any]) -> dict[str, Any]:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["schema"] = SCHEMA
    payload["changed_at"] = payload.get("changed_at") or _now()
    fd, tmp_name = tempfile.mkstemp(prefix="operator_mode_", suffix=".tmp", dir=str(STATE_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, STATE_PATH)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
    return {**payload, "exists": True, "effective_mode": payload["mode"]}


def _record(state: dict[str, Any]) -> None:
    TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    event_id = uuid.uuid4().hex
    row = {"schema": SCHEMA, "event_id": event_id, "receipt_id": event_id,
           "ok": True, "ts": _now(), **state}
    with TRAIL_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def set_paused(*, reason: str = "operator requested pause", scope: str = "autonomous",
              requested_by: str = "operator", until: str | None = None) -> dict[str, Any]:
    """Pause autonomous work; deliberately leaves containers and dashboards up."""
    if scope not in {"autonomous", "all_agents"}:
        raise ValueError("scope must be autonomous or all_agents")
    state = {
        "schema": SCHEMA,
        "mode": "paused",
        "scope": scope,
        "reason": (reason or "operator requested pause")[:500],
        "requested_by": (requested_by or "operator")[:120],
        "changed_at": _now(),
        "until": until,
    }
    out = _write(state)
    _record(out)
    return out


def resume(*, requested_by: str = "operator", reason: str = "operator resumed autonomous work") -> dict[str, Any]:
    """Resume autonomous work and leave a receipt of the transition."""
    state = {
        "schema": SCHEMA,
        "mode": "running",
        "scope": "autonomous",
        "reason": (reason or "operator resumed autonomous work")[:500],
        "requested_by": (requested_by or "operator")[:120],
        "changed_at": _now(),
        "until": None,
    }
    out = _write(state)
    _record(out)
    return out


def pause_reason(*, scope: str = "autonomous") -> str | None:
    """Return a stable gate reason, or ``None`` when work may proceed."""
    state = read()
    if state.get("mode") == "invalid":
        return "operator_mode_invalid (autonomy held until the control file is repaired)"
    effective = state.get("effective_mode", state.get("mode"))
    if effective != "paused":
        return None
    active_scope = state.get("scope") or "autonomous"
    if scope == "all_agents" or active_scope in {scope, "all_agents"}:
        return f"operator_paused: {str(state.get('reason') or 'no reason')[:180]}"
    return None


def is_paused(*, scope: str = "autonomous") -> bool:
    return pause_reason(scope=scope) is not None


if __name__ == "__main__":
    print(json.dumps(read(), indent=2))
