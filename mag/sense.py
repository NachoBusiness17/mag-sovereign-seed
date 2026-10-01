"""Sense environment for Mag cycle."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import HANDOFF_DIR, RESULTS_DIR, ROOT, WORKING_MD
from mag.policy import load_policy, resolve


def sense() -> dict[str, Any]:
    pol = load_policy()
    todo_path = resolve(pol["todo_path"])
    live = ROOT / "memory" / "live_from_grok.md"
    locus = ROOT / "memory" / "locus.md"

    todo_text = todo_path.read_text(encoding="utf-8") if todo_path.is_file() else ""
    assigned = _parse_assigned(todo_text, pol.get("assigned_markers") or ["[mag]"])
    open_todos = _parse_open_todos(todo_text)

    handoffs = sorted(HANDOFF_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    pending_handoffs = []
    for h in handoffs[:10]:
        rid = RESULTS_DIR / h.name
        if not rid.is_file():
            pending_handoffs.append(h.name)

    live_text = live.read_text(encoding="utf-8") if live.is_file() else ""
    working = WORKING_MD.read_text(encoding="utf-8") if WORKING_MD.is_file() else ""
    live_age_min = _file_age_minutes(live)

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "todo_path": str(todo_path),
        "assigned": assigned,
        "open_todos": open_todos,
        "pending_handoffs": pending_handoffs,
        "live_preview": live_text[:3000],
        "live_age_minutes": live_age_min,
        "working_preview": working[:2000],
        "locus_exists": locus.is_file(),
        "policy": pol,
    }


def _parse_assigned(todo: str, markers: list[str]) -> list[dict[str, str]]:
    out = []
    for line in todo.splitlines():
        s = line.strip()
        if not s.startswith("- [ ]"):
            continue
        body = s[5:].strip()
        if any(m in body for m in markers):
            # strip markers for goal text
            goal = body
            for m in markers:
                goal = goal.replace(m, "")
            out.append({"raw": s, "goal": goal.strip()})
    return out


def _parse_open_todos(todo: str) -> list[str]:
    out = []
    for line in todo.splitlines():
        s = line.strip()
        if s.startswith("- [ ]"):
            out.append(s[5:].strip())
    return out


def _file_age_minutes(path: Path) -> float | None:
    if not path.is_file():
        return None
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    # st_mtime is local epoch; close enough
    return age / 60.0
