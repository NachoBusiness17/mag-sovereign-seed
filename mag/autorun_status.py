"""Dashboard-facing governor / autorun status (read trails + heartbeat + queue)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

GOVERNOR_TRAIL = ROOT / "memory" / "runs" / "governor_trail.jsonl"
AUTORUN_TRAIL = ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl"
AUTOPILOT_LOG = ROOT / "logs" / "autopilot_latest.json"
HEARTBEAT = ROOT / "watch" / "heartbeat.json"


def _tail_jsonl(path: Path, n: int = 5) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, n) :]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except json.JSONDecodeError:
            continue
    return out


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        o = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return o if isinstance(o, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _drainer_enabled() -> bool:
    try:
        from mag.preferences import autorun_allowed

        return autorun_allowed()
    except Exception:
        import os

        return os.environ.get("MAG_DRAINER", "").strip().lower() in ("1", "true", "yes")


def _open_todo_count() -> int:
    try:
        from mag.governor import queue_candidates

        return len(queue_candidates())
    except Exception:
        todo = ROOT / "queue" / "todo.md"
        if not todo.is_file():
            return 0
        n = 0
        for line in todo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("- [ ] ["):
                n += 1
        return n


def routing_legend() -> list[dict[str, str]]:
    try:
        from mag.coordination import DEPTH_ROUTES

        rows: list[dict[str, str]] = []
        for depth, route in DEPTH_ROUTES.items():
            rows.append(
                {
                    "depth": depth,
                    "seat": str(route.get("seat") or ""),
                    "mode": str(route.get("mode") or ""),
                    "provider": str(route.get("provider") or route.get("seat") or ""),
                    "tier": str(route.get("tier") or ""),
                }
            )
        return rows
    except Exception:
        return []


def autorun_dashboard_status() -> dict[str, Any]:
    """Single payload for dashboard Autorun card + ops queue panel."""
    hb = _read_json(HEARTBEAT)
    drainer_on = _drainer_enabled()
    autorun_thread = bool(hb.get("autorun_on")) or str(hb.get("status") or "").endswith("autorun")

    gov_last = _tail_jsonl(GOVERNOR_TRAIL, 1)
    auto_last = _tail_jsonl(AUTORUN_TRAIL, 1)
    gov_recent = _tail_jsonl(GOVERNOR_TRAIL, 8)
    auto_recent = _tail_jsonl(AUTORUN_TRAIL, 6)

    drainer: dict[str, Any] = {}
    try:
        from mag.preferences import drainer_status

        drainer = drainer_status()
    except Exception as e:
        drainer = {"error": str(e)[:120]}

    queue_summary: dict[str, Any] = {}
    queue_items: list[dict[str, Any]] = []
    try:
        from mag.orchestrator import list_queue, queue_status

        queue_summary = queue_status()
        queue_items = list_queue(limit=20)
    except Exception as e:
        queue_summary = {"error": str(e)[:120]}

    autopilot = _read_json(AUTOPILOT_LOG)

    last_gov = gov_last[-1] if gov_last else {}
    last_auto = auto_last[-1] if auto_last else {}

    # Autorun "alive" = pref on AND (integral thread OR supervisor drainer pid)
    supervisor_drainer_pid = None
    ml = _read_json(ROOT / "state" / "mag_launch.json")
    pids = ml.get("pids") or {}
    if pids.get("drainer"):
        supervisor_drainer_pid = pids.get("drainer")

    alive = drainer_on and (autorun_thread or bool(supervisor_drainer_pid))

    return {
        "ok": True,
        "schema": "autorun_status.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "governor": {
            "drainer_enabled": drainer_on,
            "autorun_alive": alive,
            "autorun_thread": autorun_thread,
            "supervisor_drainer_pid": supervisor_drainer_pid,
            "legacy_daemon": True,
            "legacy_note": "mag lab still runs sense/judge/act companion cycle (separate from governor)",
            "open_todo_mag": _open_todo_count(),
            "last_cycle": {
                "ts": last_gov.get("ts"),
                "action": last_gov.get("action"),
                "title": (last_gov.get("title") or "")[:200],
                "ok": last_gov.get("ok"),
                "detail": (last_gov.get("detail") or "")[:300],
            },
            "recent": [
                {
                    "ts": r.get("ts"),
                    "action": r.get("action"),
                    "ok": r.get("ok"),
                    "title": (r.get("title") or "")[:80],
                }
                for r in reversed(gov_recent)
            ],
        },
        "autorun": {
            "last_tick": {
                "ts": last_auto.get("ts"),
                "action": last_auto.get("action"),
                "steps": last_auto.get("steps"),
                "drain": (last_auto.get("drain") or {}).get("action")
                if isinstance(last_auto.get("drain"), dict)
                else None,
                "governor_action": (last_auto.get("governor") or {}).get("action")
                if isinstance(last_auto.get("governor"), dict)
                else None,
            },
            "recent": [
                {
                    "ts": r.get("ts"),
                    "action": r.get("action"),
                    "phase": r.get("phase"),
                }
                for r in reversed(auto_recent)
            ],
        },
        "autopilot_latest": {
            "ts": autopilot.get("ts"),
            "steps": autopilot.get("steps"),
            "ok": autopilot.get("ok"),
        },
        "queue": queue_summary,
        "queue_items": [
            {
                "queue_id": q.get("queue_id"),
                "status": q.get("status"),
                "goal": (q.get("goal") or "")[:120],
                "provider": q.get("provider"),
                "tag": q.get("tag"),
                "task_id": q.get("task_id"),
            }
            for q in queue_items
        ],
        "routing": routing_legend(),
        "drainer": drainer,
        "heartbeat": {
            "status": hb.get("status"),
            "last_action": hb.get("last_action"),
            "autorun_on": hb.get("autorun_on"),
            "age_seconds": None,
        },
        "hints": {
            "enable": "Set MAG_DRAINER=1 in .env or toggle Auto-drain on Body tab",
            "cli_once": "mag.cmd autorun --once",
            "cli_dry": "mag.cmd autorun --once --dry",
            "trail_governor": str(GOVERNOR_TRAIL.relative_to(ROOT)).replace("\\", "/"),
            "trail_autorun": str(AUTORUN_TRAIL.relative_to(ROOT)).replace("\\", "/"),
        },
    }
