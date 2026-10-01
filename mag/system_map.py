"""Unified system map — one live snapshot of direction, learning, and operator state."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path, *, limit: int = 6000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _current_summary() -> dict[str, Any]:
    current = ROOT / "state" / "CURRENT.md"
    text = _read_text(current, limit=12000)
    summary: dict[str, Any] = {"path": str(current), "exists": current.is_file(), "text": text}
    for marker in ("## Goal", "## Status", "## Route", "## Next", "## Blockers"):
        idx = text.find(marker)
        if idx >= 0:
            tail = text[idx + len(marker) :].split("\n## ", 1)[0].strip()
            summary[marker.lower().replace("## ", "").replace(" ", "_")] = tail[:400]
    return summary


def _improve_summary() -> dict[str, Any]:
    trail = ROOT / "memory" / "runs" / "improve_loop_trail.jsonl"
    lines = []
    if trail.is_file():
        lines = trail.read_text(encoding="utf-8", errors="replace").splitlines()
    last = {}
    if lines:
        try:
            last = json.loads(lines[-1]) if lines[-1].strip() else {}
        except Exception:
            last = {}
    return {
        "path": str(trail),
        "exists": trail.is_file(),
        "last_event": last.get("event"),
        "last_ts": last.get("ts"),
        "lines": len(lines),
    }


def _direction_summary() -> dict[str, Any]:
    files = {
        "proposal": ROOT / "docs" / "ref" / "MAG_PROJECT_PROPOSAL.md",
        "direction": ROOT / "docs" / "ref" / "MAG_DIRECTION_ARTIFACT_v2.md",
        "hand_off": ROOT / "HANDOFF_MAG_AGENT_TODOS.md",
        "compass": ROOT / "docs" / "ref" / "MAG_MYCELIAL_REPUBLIC_COMPASS.md",
        "constitution": ROOT.parent / "mycelial-republic" / "docs" / "CONSTITUTION.md",
    }
    out: dict[str, Any] = {}
    for name, path in files.items():
        out[name] = {"path": str(path), "exists": path.is_file(), "head": _read_text(path, limit=1200)}
    return out


def build_system_map(*, goal: str = "", write: bool = True) -> dict[str, Any]:
    from mag.decision_framework import build_framework_context, surface_tips
    from mag.improve_loop import _trail as improve_trail
    from mag.nervous_system import build_glance, write_face
    from mag.operator_inbox import pending_hints, status as inbox_status
    from mag.resonance import format_l0e, top_cards, tick as resonance_tick

    goal = (goal or "").strip()
    nervous = build_glance(write=write)
    tips = surface_tips(goal=goal, limit=6)
    framework_context = build_framework_context(goal=goal, reason="loop")
    inbox = inbox_status()
    pending = pending_hints()
    resonance_cards = top_cards(goal, n=3)
    resonance_preview = format_l0e(resonance_cards, goal=goal)

    # Keep the map live: if a goal is supplied, refresh resonance findings.
    resonance_result: dict[str, Any] = {"written": False}
    if goal:
        try:
            resonance_result = resonance_tick(goal=goal, dry=not write)
        except Exception as exc:
            resonance_result = {"ok": False, "error": str(exc)[:240], "written": False}

    glance: dict[str, Any] = {
        "schema": "system_map.v1",
        "ts": _now(),
        "goal": goal,
        "current": _current_summary(),
        "nervous": nervous,
        "inbox": inbox,
        "pending_hints": pending,
        "improve": _improve_summary(),
        "resonance": {
            "cards": resonance_cards,
            "preview": resonance_preview,
            "result": resonance_result,
        },
        "framework_context": framework_context,
        "tips": tips,
        "direction": _direction_summary(),
        "routes": {
            "route_cmd": "python main.py route --dry <goal>",
            "agent_cmd": "python main.py agent --provider deepseek --query <goal>",
            "queue_cmd": "python main.py orchestrator queue add <goal> --provider deepseek",
            "drain_cmd": "python main.py orchestrator drain --once",
            "smoke_cmd": "python -m pytest tests/test_routing_smoke.py -q",
        },
    }

    if write:
        out_dir = ROOT / "memory" / "system_map"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "latest.json").write_text(json.dumps(glance, indent=2, default=str), encoding="utf-8")
        lines = [
            "# System map — live autonomy snapshot",
            f"_ts: {glance['ts']}_",
            f"_goal: {goal or '(none)'}_",
            "",
            "## Current",
            f"- path: `{glance['current']['path']}`",
            f"- status: `{glance['current'].get('status', '')}`",
            f"- route: `{glance['current'].get('route', '')}`",
            f"- next: `{glance['current'].get('next', '')}`",
            "",
            "## Nervous",
            f"- dashboard: {'UP' if nervous.get('body', {}).get('dashboard_8765') else 'DOWN'}",
            f"- ollama: {'UP' if nervous.get('body', {}).get('ollama_11434') else 'DOWN'}",
            f"- multi_smoke: {'PASS' if nervous.get('body', {}).get('multi_smoke_ok') else 'FAIL/unknown'}",
            "",
            "## Inbox",
            f"- pending: {inbox.get('pending_n', 0)}",
        ]
        for hint in pending[:5]:
            lines.append(f"- {hint}")
        lines.extend([
            "",
            "## Improve",
            f"- last_event: `{glance['improve'].get('last_event')}`",
            f"- trail: `{glance['improve'].get('path')}`",
            "",
            "## Resonance",
        ])
        if resonance_preview:
            lines.append(resonance_preview)
        else:
            lines.append("- _(none)_")
        lines.extend([
            "",
            "## Direction",
            f"- proposal: {glance['direction']['proposal']['path']}",
            f"- compass: {glance['direction']['compass']['path']}",
            f"- constitution: {glance['direction']['constitution']['path']}",
            "",
            "## Next actions",
            f"- {glance['routes']['route_cmd']}",
            f"- {glance['routes']['agent_cmd']}",
            f"- {glance['routes']['queue_cmd']}",
            f"- {glance['routes']['drain_cmd']}",
            f"- {glance['routes']['smoke_cmd']}",
            "",
        ])
        (out_dir / "latest.md").write_text("\n".join(lines), encoding="utf-8")
        try:
            improve_trail("system_map", goal=goal, summary={"pending": inbox.get("pending_n", 0)})
        except Exception:
            pass

    return glance