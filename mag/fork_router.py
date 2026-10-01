"""Fork router: detect planning tangents and create fork artifacts.

This module gives Mag a callable tool surface for deciding whether a request
should stay inline or branch into a new planning contract/task.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

_FUTURE_MARKERS = (
    "wouldn't it be nice",
    "would it be nice",
    "it might be neat",
    "what if",
    "someday",
    "future",
    "for later",
    "down the line",
    "in the long run",
    "vision",
    "imagine",
)

_TANGENT_MARKERS = (
    "also",
    "as well",
    "another",
    "in addition",
    "feature set",
    "roadmap",
    "branch",
    "fork",
    "gap analysis",
    "not ready for production",
)

_EXEC_ANCHOR_MARKERS = (
    "file",
    "line",
    "function",
    "class",
    "test",
    "pytest",
    "api",
    "endpoint",
    "schema",
    "implement",
    "fix",
    "refactor",
    "edit",
    "patch",
    "command",
)

_FORK_TASK_MARKERS = (
    "gap analysis",
    "architecture",
    "ecosystem",
    "research",
    "multi-step",
    "multi step",
    "roadmap",
    "feature set",
    "future feature",
)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower())}


def _match_markers(goal_l: str, markers: tuple[str, ...]) -> list[str]:
    return [m for m in markers if m in goal_l]


def _has_exec_anchor(goal_l: str) -> bool:
    if any(m in goal_l for m in _EXEC_ANCHOR_MARKERS):
        return True
    # Common file anchors and explicit commands.
    if re.search(r"\b[a-zA-Z0-9_./-]+\.(py|ts|tsx|js|md|json|yaml|yml)\b", goal_l):
        return True
    if re.search(r"\b(get|post|patch|put|delete)\s+/api", goal_l):
        return True
    return False


def _drift_score(goal: str, current_goal: str) -> tuple[int, float]:
    if not current_goal.strip():
        return 0, 0.0
    g = _tokenize(goal)
    c = _tokenize(current_goal)
    if not g or not c:
        return 0, 0.0
    overlap = len(g & c)
    ratio = overlap / max(1, min(len(g), len(c)))
    return (2 if ratio < 0.2 else 0), ratio


def detect_fork(
    goal: str,
    *,
    current_goal: str = "",
    allow_auto: bool = False,
) -> dict[str, Any]:
    """Return a fork decision contract for the given utterance."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": "fork_decision.v1", "error": "goal required"}

    gl = goal.lower()
    reasons: list[str] = []
    signals: dict[str, Any] = {}
    score = 0

    future_hits = _match_markers(gl, _FUTURE_MARKERS)
    if future_hits:
        score += 3
        signals["future_markers"] = future_hits
        reasons.append("future-facing ideation language")

    tangent_hits = _match_markers(gl, _TANGENT_MARKERS)
    if tangent_hits:
        score += 2
        signals["tangent_markers"] = tangent_hits
        reasons.append("feature-tangent language")

    has_anchor = _has_exec_anchor(gl)
    signals["has_execution_anchor"] = has_anchor
    if not has_anchor:
        score += 2
        reasons.append("missing execution anchor")

    drift_points, drift_ratio = _drift_score(goal, current_goal)
    signals["goal_overlap_ratio"] = round(drift_ratio, 3)
    if drift_points:
        score += drift_points
        reasons.append("low overlap with active goal")

    try:
        from mag.plan import should_plan

        needs_plan = bool(should_plan(goal))
    except Exception:
        needs_plan = score >= 2

    # Fork is stricter than plan: context shift + uncertainty.
    needs_fork = score >= 4 or (bool(future_hits) and bool(tangent_hits))
    confidence = "high" if score >= 6 else ("medium" if score >= 4 else "low")

    target = "stay"
    if needs_fork:
        target = "task" if confidence == "high" or any(m in gl for m in _FORK_TASK_MARKERS) else "contract"

    action = "suggest_fork" if needs_fork else "stay"
    if allow_auto and confidence == "high" and needs_fork:
        action = "auto_fork"

    return {
        "ok": True,
        "schema": "fork_decision.v1",
        "goal": goal[:2000],
        "current_goal": current_goal[:400],
        "needs_plan": needs_plan,
        "needs_fork": needs_fork,
        "confidence": confidence,
        "action": action,
        "target": target,
        "score": score,
        "signals": signals,
        "reasons": reasons,
        "hint": (
            "Suggest fork: create a new planning branch with inherited constraints."
            if needs_fork
            else "Stay in current session; request is execution-anchored enough."
        ),
    }


def _fork_dir() -> Path:
    p = ROOT / "memory" / "forks"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fork_id(goal: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    h = hashlib.sha1(goal.encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"fork-{stamp}-{h}"


def confirm_fork(
    goal: str,
    *,
    current_goal: str = "",
    decision: dict[str, Any] | None = None,
    strategy: str | None = None,
    spawn: bool = False,
    provider: str = "deepseek",
    timeout: int = 900,
    tag: str = "fork",
) -> dict[str, Any]:
    """Create fork artifact and optionally spawn a child task."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": "fork_confirm.v1", "error": "goal required"}

    decision = dict(decision or detect_fork(goal, current_goal=current_goal))
    if not decision.get("ok"):
        return {"ok": False, "schema": "fork_confirm.v1", "error": decision.get("error") or "bad decision"}

    chosen = (strategy or str(decision.get("target") or "contract")).strip().lower()
    if chosen not in ("contract", "task"):
        chosen = "contract"
    do_spawn = bool(spawn or chosen == "task")

    fid = _fork_id(goal)
    d = _fork_dir()
    json_path = d / f"{fid}.json"
    md_path = d / f"{fid}.md"

    packet = {
        "schema": "fork_session.v1",
        "id": fid,
        "created_at": _utc(),
        "goal": goal,
        "current_goal": current_goal,
        "strategy": chosen,
        "decision": {
            "needs_plan": bool(decision.get("needs_plan")),
            "needs_fork": bool(decision.get("needs_fork")),
            "confidence": decision.get("confidence"),
            "score": decision.get("score"),
            "reasons": decision.get("reasons") or [],
        },
        "status": "created",
        "task": None,
    }

    if do_spawn:
        try:
            from mag.orchestrator import spawn_task

            t = spawn_task(
                goal,
                provider=str(provider or "deepseek"),
                model=None,
                timeout=max(60, min(int(timeout), 7200)),
                tag=str(tag or "fork").strip() or "fork",
            )
            packet["task"] = t
            packet["status"] = "spawned"
        except Exception as e:
            packet["status"] = "spawn_error"
            packet["task_error"] = str(e)

    json_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Fork {fid}",
                "",
                f"- created: `{packet['created_at']}`",
                f"- strategy: `{chosen}`",
                f"- status: `{packet['status']}`",
                f"- confidence: `{packet['decision'].get('confidence')}`",
                "",
                "## Goal",
                "",
                goal,
                "",
                "## Why",
                "",
                "\n".join(f"- {r}" for r in (packet["decision"].get("reasons") or ["No reasons captured"])),
                "",
                "## Task",
                "",
                json.dumps(packet.get("task"), indent=2, default=str) if packet.get("task") else "_(not spawned)_",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "schema": "fork_confirm.v1",
        "fork": packet,
        "paths": {
            "json": str(json_path),
            "markdown": str(md_path),
        },
    }
