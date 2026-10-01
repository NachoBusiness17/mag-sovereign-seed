"""Agent-state-aware ROUTING — the custom agent state that auto-selects resources.

Distinct from mag/agent_state.py (the MEMORY recall-edge pack). This is the ROUTING side of the
operator's vision: hold the agent in a CUSTOM STATE so routing (self_drive / model_pick / router)
READS that state and auto-selects — model, thinking level, effort, API key, skills, tools, memory
context, context_plan — to MATCH the job, minimize cost, and keep asks focused/relevant, routed to
the right model/chat-window/API-context. The custom agent state is the SPEC; routing serves it
(spend on the spec, not the tier).

Deterministic base: a state config + resolver. self_drive consumes it when building the ask.

CLI:  python -m mag.agent_state_router                (list states)
      python -m mag.agent_state_router research-agent (show one state's resource spec)
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SCHEMA = "agent_state_router.v1"

FLASH = "deepseek-v4-flash"
PRO = "deepseek-v4-pro"

# Each custom agent state -> the resource spec routing should use to SERVE it.
AGENT_STATES: dict[str, dict[str, Any]] = {
    "research-agent": {
        "desc": "deep research / synthesis — carry the research bed, reason hard, spend for quality",
        "model_shape": "reasoning",
        "model": PRO,
        "thinking_level": "high",
        "effort": "high",
        "api_key": "deepseek",
        "skills": ["research-pack", "topic_research", "classify_pack", "steal-protocol"],
        "tools": ["research", "swarm", "gauntlet", "dig"],
        "memory_context": "research-bed + case law + recent packs",
        "context_plan": "fresh_context_pack",
    },
    "janitor-agent": {
        "desc": "maintenance / cleanup / filenaming / classification / tagging — cheap, exec-shaped",
        "model_shape": "cheap",
        "model": FLASH,
        "thinking_level": "none",
        "effort": "low",
        "api_key": "deepseek",
        "skills": ["janitor", "classify", "state_snapshot", "topic_orphan"],
        "tools": ["file", "rename", "classify", "tag"],
        "memory_context": "maintenance surface + gap_analysis + orphan list",
        "context_plan": "fresh_context_pack",
    },
    "coding-agent": {
        "desc": "code work — exec-shaped -> flash, heavy refactor/design -> pro (auto shape)",
        "model_shape": "auto",
        "model": FLASH,
        "thinking_level": "low",
        "effort": "low",
        "api_key": "deepseek",
        "skills": ["patch-verify", "spec_gate", "job_floor", "coding-session"],
        "tools": ["edit", "test", "verify", "spec-gate"],
        "memory_context": "code surface + spec_gate bases + case law",
        "context_plan": "auto",
    },
    "default": {
        "desc": "balanced fallback",
        "model_shape": "balanced",
        "model": FLASH,
        "thinking_level": "low",
        "effort": "medium",
        "api_key": "deepseek",
        "skills": [],
        "tools": [],
        "memory_context": "brief + case law",
        "context_plan": "fresh_context_pack",
    },
}


def resolve(state: str) -> dict[str, Any]:
    """Resolve a custom agent state name -> its resource spec."""
    key = (state or "").strip().lower()
    spec = AGENT_STATES.get(key)
    if not spec:
        return {"ok": False, "error": f"unknown agent state: {state}", "known": sorted(AGENT_STATES)}
    return {"ok": True, "schema": SCHEMA, "state": key, **spec}


def pick(state: str, goal: str) -> dict[str, Any]:
    """Resolve the state spec AND fold in the goal (via self_drive/model_pick) for the full ask.

    For model_shape=auto states (coding-agent), defer to the goal's shape: cheap/heavy/reasoning.
    """
    spec = resolve(state)
    if not spec.get("ok"):
        return spec
    shape = spec.get("model_shape")
    if shape == "auto":
        try:
            from mag.model_pick import recommend_model
            rec = recommend_model(goal)
            shape = str(rec.get("model_shape") or "balanced")
            spec["model"] = rec.get("model")
            spec["model_shape"] = shape
            spec["is_handoff"] = rec.get("is_handoff")
            if rec.get("is_handoff"):
                spec["context_plan"] = "handoff_maze"
        except Exception as e:
            spec["pick_error"] = str(e)[:120]
    return spec


def states() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "states": {k: {kk: v for kk, v in s.items() if kk != "desc"} for k, s in AGENT_STATES.items()}}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    state = (argv[0] if argv else "").strip()
    if state:
        print(json.dumps(resolve(state), indent=2, default=str))
    else:
        print(json.dumps(states(), indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
