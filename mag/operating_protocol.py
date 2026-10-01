"""Platform-agnostic default protocol for every Mag instruction surface."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


SURFACES = frozenset({"codex", "dashboard", "tablet", "cli", "cursor", "grok", "api", "automation", "unknown"})


def normalize_surface(source: str | None) -> str:
    value = str(source or "unknown").strip().lower().replace("-", "_")
    aliases = {"web": "dashboard", "mag_dash": "dashboard", "terminal": "cli", "phone": "tablet"}
    value = aliases.get(value, value)
    return value if value in SURFACES else "unknown"


def build_envelope(
    goal: str,
    *,
    source: str = "unknown",
    depth: str | None = None,
    force_seat: str | None = None,
    force_provider: str | None = None,
    dry: bool = True,
) -> dict[str, Any]:
    """Return the same supervisory contract regardless of ingress platform."""
    from mag.conductor import conduct
    from mag.cost_simulator import estimate_goal

    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "schema": "mag_intent.v1", "error": "goal required"}
    surface = normalize_surface(source)
    decision = conduct(
        goal,
        depth=depth,
        force_seat=force_seat,
        force_provider=force_provider,
        dry=dry,
        mesh=False,
    )
    route = decision.get("route") or {}
    overlay = decision.get("overlay") or {}
    suggested = str(overlay.get("suggested_seat") or route.get("seat") or route.get("provider") or "local")
    provider = str(route.get("provider") or "ollama")
    estimate = estimate_goal(goal, seat=provider, dry=True)
    blocked = suggested == "defer" or route.get("ok") is False
    return {
        "ok": not blocked,
        "schema": "mag_intent.v1",
        "intent_id": "intent-" + uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": surface,
        "goal": goal[:1000],
        "policy": {
            "id": "personal-router-dungeon-master.v1",
            "platform_agnostic": True,
            "default": True,
            "stages": ["remember", "classify", "benchmark", "right_size", "summon_or_execute", "verify", "learn"],
        },
        "personal_router": {
            "role": "persistent_operator_interface",
            "memory_scope": ["projects", "agent_interactions", "platform_history", "wins", "failures", "prompt_lessons", "skills"],
            "model_policy": "test speed and capability, then use the smallest model that passes the task eval",
            "default_seat": "local",
        },
        "decision": decision,
        "execution": {
            "status": "blocked" if blocked else "ready",
            "seat": suggested,
            "provider": provider,
            "implementation_default": "deepseek" if decision.get("phase") == "build" else "right_sized_local",
            "architect": "personal_router",
            "janitor": "local",
            "stop_conditions": ["done", "genuinely_blocked", "human_gate", "policy_refusal"],
        },
        "routing_economics": {
            "objective": "minimize total cost per verified outcome, not tokens per call",
            "selection_order": [
                "privacy_and_authority",
                "task_class_capability",
                "smallest_model_with_passing_evidence",
                "expected_retries_and_context_growth",
                "time_to_verified_outcome",
                "marginal_dollar_cost",
            ],
            "context_policy": "send the frozen brief plus changed evidence; do not replay the full transcript",
            "retry_policy": "one diagnosed retry at the same tier; then change prompt, skill, tool, or capability tier",
            "escalation_policy": "summon judgment when uncertainty or failure demands it; keep implementation on the cheapest capable builder",
            "accounting_unit": "verified_leaf",
            "required_comparison": ["estimate", "actual", "outcome", "waste", "lesson", "next_best_seat"],
        },
        "dungeon_master": {
            "role": "summoned_frontier_adviser",
            "candidates": ["codex", "grok", "cursor", "other_cloud_specialist"],
            "summon_when": ["novel_task", "low_confidence", "failed_eval", "architecture", "security", "repeated_failure"],
            "deliverables": ["bounded_plan", "skill", "eval_case", "prompt_pattern", "failure_remedy"],
            "rule": "teach the personal router; do not become its permanent runtime",
        },
        "estimate": estimate,
        "evidence_contract": {
            "required": True,
            "terminal": ["test_green", "artifact_filed", "queue_terminal", "verified_knot"],
            "audit_scope": "consequential_changes_only",
        },
        "learning_contract": {
            "capture": ["what_worked", "what_failed", "model_speed", "model_quality", "cost", "prompt", "skill_used"],
            "promotion": "repeated evaluated success before default behavior changes",
            "graduation_rule": "a cheaper model inherits a task class only after repeated eval passes; a costly model leaves behind a reusable skill or remedy",
        },
    }
