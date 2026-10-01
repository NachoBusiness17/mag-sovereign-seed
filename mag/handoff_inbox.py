"""Unified handoff inbox — peer/cloud/BUILD queue + orchestrator + scrum sprint."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

HANDOFF_DIR = ROOT / "queue" / "handoff"
SCHEMA = "handoff_inbox.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_handoff(name: str, payload: dict[str, Any]) -> str:
    low = name.lower()
    if low.startswith("peer-"):
        return "peer"
    if low.startswith("cloud-"):
        return "cloud"
    if "build" in low or payload.get("kind") == "BUILD":
        return "build"
    if payload.get("schema") == "handoff.v1":
        return "grok"
    return "handoff"


def list_disk_handoffs(*, limit: int = 20) -> list[dict[str, Any]]:
    if not HANDOFF_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(HANDOFF_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if len(rows) >= limit:
            break
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        kind = _classify_handoff(p.name, data)
        goal = (
            data.get("goal")
            or data.get("title")
            or data.get("one_line")
            or data.get("brief")
            or ""
        )
        rows.append(
            {
                "id": p.stem,
                "kind": kind,
                "path": f"queue/handoff/{p.name}",
                "from_seat": data.get("from_seat") or data.get("seat") or "",
                "to_seat": data.get("to_seat") or "",
                "goal": str(goal)[:240],
                "status": data.get("status") or "filed",
                "mtime": p.stat().st_mtime,
            }
        )
    return rows


def list_orchestrator_queue(*, limit: int = 10) -> list[dict[str, Any]]:
    try:
        from mag.orchestrator import list_queue

        items = list_queue(limit=limit)
        out: list[dict[str, Any]] = []
        for q in items:
            out.append(
                {
                    "id": q.get("queue_id") or q.get("task_id") or "",
                    "kind": "orchestrator",
                    "goal": str(q.get("goal") or "")[:240],
                    "status": q.get("status") or "",
                    "provider": q.get("provider") or "",
                    "tag": q.get("tag") or "",
                }
            )
        return out
    except Exception:
        return []


def scrum_snapshot() -> dict[str, Any]:
    try:
        from mag.coding_session_orchestrator import assess_sprint_status, recommend_desk_action

        st = assess_sprint_status()
        if not st.get("ok"):
            return {"ok": False, "error": st.get("error") or "no session"}
        return {
            "ok": True,
            "session_id": st.get("session_id"),
            "active_sprint": st.get("active_sprint"),
            "owner": st.get("owner"),
            "artifact": st.get("artifact"),
            "desk_task": (st.get("desk_task") or "")[:300],
            "next_action": recommend_desk_action(status=st),
            "completed_sprints": st.get("completed_sprints") or [],
            "sprint_checks": st.get("sprint_checks") or [],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def build_inbox(*, limit: int = 20) -> dict[str, Any]:
    disk = list_disk_handoffs(limit=limit)
    orch = list_orchestrator_queue(limit=10)
    scrum = scrum_snapshot()
    items: list[dict[str, Any]] = []
    for row in disk:
        items.append({**row, "source": "disk"})
    for row in orch:
        items.append({**row, "source": "orchestrator", "path": ""})

    autorun_hint: dict[str, Any] = {}
    try:
        from mag.autorun_status import autorun_dashboard_status

        ar = autorun_dashboard_status()
        gov = ar.get("governor") or {}
        autorun_hint = {
            "drainer_enabled": gov.get("drainer_enabled"),
            "autorun_alive": gov.get("autorun_alive"),
            "open_todo": gov.get("open_todo_mag"),
        }
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _now(),
        "count": len(items),
        "items": items,
        "scrum": scrum,
        "autorun": autorun_hint,
    }
