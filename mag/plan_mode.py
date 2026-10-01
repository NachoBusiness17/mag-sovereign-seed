"""Constrained plan-mode wrapper — plan-before-build discipline.

This module enforces a strict separation between planning and execution.
The plan_mode function returns ONLY a plan structure and NEVER writes files
or executes commands. Use this as the first step before any build work.
"""
from __future__ import annotations

from typing import Any


def plan_mode(task: str, context: str = "") -> dict[str, Any]:
    """Return a constrained plan dict for the given task.

    This is the plan-before-build discipline: generate a plan first,
    review it, then proceed with execution. The plan contains only
    metadata and NEVER performs side effects (no file writes, no commands).

    Args:
        task: The goal or task to plan for.
        context: Optional additional context to inform the plan.

    Returns:
        A dict with keys:
            - goal: Clear statement of what the plan achieves
            - steps: List of concrete, ordered steps to execute
            - risks: List of potential issues or blockers
            - success_criteria: List of measurable outcomes that define success

    Note:
        This function is intentionally read-only. It MUST NOT write files,
        execute commands, or modify system state. The returned plan is
        meant to be reviewed before proceeding with actual work.
    """
    return {
        "goal": task.strip(),
        "steps": [],
        "risks": [],
        "success_criteria": [],
    }
