"""Frozen BUILD contract gate for autonomous coding."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import ROOT

HANDOFF = ROOT / "queue" / "handoff"
BUILD_MARKERS = ("[build]", " implement ", "implementation", "build feature", "write code")


def is_build_goal(goal: str) -> bool:
    text = f" {str(goal or '').strip().lower()} "
    return any(marker in text for marker in BUILD_MARKERS)


def _is_frozen(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:3000]
    except OSError:
        return False
    plain = head.replace("**", "")
    return bool(re.search(r"\bstatus\s*:\s*frozen\b", plain, re.I))


def _declared_tier(path: Path) -> str:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:3000].replace("**", "")
    except OSError:
        return "T1"
    match = re.search(r"\btier\s*:\s*(T[0-3])\b", head, re.I)
    return match.group(1).upper() if match else "T1"


def _safe_build_path(value: str) -> Path | None:
    name = Path(str(value or "").replace("\\", "/")).name
    if not name.lower().startswith("build-") or not name.lower().endswith(".md"):
        return None
    path = HANDOFF / name
    try:
        path.resolve().relative_to(HANDOFF.resolve())
    except (OSError, ValueError):
        return None
    return path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def check_frozen_build(goal: str, *, require_build: str | None = None) -> dict[str, Any]:
    """Allow code work only when it identifies a frozen disk contract."""
    if not is_build_goal(goal) and not require_build:
        return {"ok": True, "required": False, "reason": "not a build goal"}
    candidates: list[Path] = []
    if require_build:
        value = require_build if str(require_build).lower().endswith(".md") else f"BUILD-{require_build}.md"
        path = _safe_build_path(value)
        if path:
            candidates.append(path)
    for match in re.findall(r"(?:queue[/\\]handoff[/\\])?(BUILD-[A-Za-z0-9._-]+\.md)", str(goal or ""), re.I):
        path = _safe_build_path(match)
        if path and path not in candidates:
            candidates.append(path)
    if not candidates:
        return {"ok": False, "required": True, "reason": "Build deferred: name a frozen queue/handoff/BUILD-*.md contract."}
    for path in candidates:
        if path.is_file() and _is_frozen(path):
            return {"ok": True, "required": True, "spec_path": _display_path(path), "tier": _declared_tier(path), "reason": "frozen BUILD contract verified"}
    shown = _display_path(candidates[0])
    return {"ok": False, "required": True, "spec_path": shown, "reason": f"Build deferred: {shown} is missing or not frozen."}
