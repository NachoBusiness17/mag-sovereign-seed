"""Task Router — match every task to the optimal model, batch parallel swarms.

Current waste:
  - qwen2.5-coder used for general analysis (it's a CODE model)
  - DeepSeek used for simple lookups (1M context window wasted on 200-char prompts)
  - Gemma:2b sitting idle (perfect for classification, $0)
  - No parallel swarms (agents run sequentially, not simultaneously)
  - DeepSeek batch API unused (50% cheaper, async)

Optimal routing:
  CODE tasks        → qwen2.5-coder:7b (free, local) or DeepSeek ($0.00013)
  REASONING tasks   → DeepSeek-v4-flash ($0.00013, 1M context)
  CLASSIFY tasks    → gemma:2b (free, local, fast)
  STRATEGY tasks    → Grok-3-mini ($0.003) when available, else DeepSeek
  ORCHESTRATE tasks → Grok-4 ($0.025) when available, else DeepSeek batch

Parallel swarm pattern:
  Fire 3-5 agents simultaneously, each with different angle.
  Synthesize with one agent. Cost: 6 × $0.00013 = $0.00078 for full analysis.

Schema: task_router.v1
"""

from __future__ import annotations

import json
from mag.chain_query import chain  # auto-added by doctor_agent
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Model capabilities ──
MODELS = {
    "gemma:2b": {
        "provider": "ollama",
        "cost": 0.0,
        "context": 8192,
        "best_for": ["classify", "count", "list", "yesno", "filter", "tag"],
        "avoid_for": ["code", "reason", "strategy", "create"],
    },
    "qwen2.5-coder:7b": {
        "provider": "ollama",
        "cost": 0.0,
        "context": 32768,
        "best_for": ["code", "refactor", "debug", "generate_module", "fix_bug", "write_test"],
        "avoid_for": ["strategy", "deep_reasoning", "multi_agent"],
    },
    "deepseek-v4-flash": {
        "provider": "deepseek",
        "cost": 0.00013,
        "context": 1_000_000,
        "best_for": ["analyze", "reason", "research", "synthesize", "investigate",
                     "long_context", "multi_file", "architecture", "diagnosis"],
        "avoid_for": ["classify", "yesno", "count", "simple_list"],
        "tier": "flash",  # fast, cheap, good enough
    },
    "deepseek-v4": {
        "provider": "deepseek",
        "cost": 0.00040,  # 3x flash, 3x reasoning depth
        "context": 128_000,
        "best_for": ["deep_reasoning", "multi_step", "architecture_design",
                     "complex_diagnosis", "strategy", "orchestrate",
                     "code_architecture", "research_deep"],
        "avoid_for": ["classify", "yesno", "count", "simple_list", "code", "lookup"],
        "tier": "full",  # deeper reasoning, smaller context than flash
    },
    "grok-3-mini": {
        "provider": "grok",
        "cost": 0.003,
        "context": 131072,
        "best_for": ["strategy", "planning", "critique", "brainstorm"],
        "avoid_for": ["code", "refactor", "classify"],
    },
    "grok-4": {
        "provider": "grok",
        "cost": 0.025,
        "context": 131072,
        "best_for": ["orchestrate", "multi_agent", "campaign", "deep_strategy"],
        "avoid_for": ["code", "classify", "simple", "count"],
    },
}

# ── Task classification keywords ──
TASK_PATTERNS: dict[str, list[str]] = {
    "code": ["write code", "generate", "create module", "refactor", "fix bug",
             "implement", "build a", "write a function", "edit file", "add endpoint",
             "create file", "modify", "patch"],
    "classify": ["classify", "is this", "which one", "yes or no", "true or false",
                 "categorize", "filter", "tag", "label"],
    "analyze_reason": ["analyze", "reason about", "investigate", "diagnose",
                       "root cause", "why is", "how does", "explain"],
    "research": ["research", "deep dive", "comprehensive", "thorough", "explore",
                 "catalog", "survey", "audit"],
    "strategy": ["strategy", "plan", "roadmap", "next steps", "prioritize",
                 "what should we", "how to approach", "critique"],
    "orchestrate": ["orchestrate", "campaign", "multi-agent", "swarm", "party",
                    "coordinate", "dnd", "quest"],
    "simple_lookup": ["count", "list", "how many", "what is the current",
                      "status", "show me", "read file", "check"],
}


def classify_task(goal: str) -> str:
    """Classify a task goal into the optimal task type."""
    g = goal.lower()
    scores: dict[str, int] = {}
    for task_type, patterns in TASK_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if pattern in g:
                score += 1
        scores[task_type] = score
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "analyze_reason"


def route_task(goal: str, *, prefer_provider: str = "auto") -> dict[str, Any]:
    """Route a task to the optimal model. Returns {provider, model, cost_est, reasoning}.

    VISION MODEL UPDATE (2026-08-08): Grok-4-latest is now the default vision model
    for analysis, research, and strategy tasks. DeepSeek remains for parallel swarms.
    Local models (qwen, gemma) remain for code and classification.
    """
    task_type = classify_task(goal)

    # Check if Grok is available (prefer Grok for vision tasks)
    grok_available = False
    try:
        from mag.x_control_surface import grok_api_configured
        grok_available = grok_api_configured()
    except Exception:
        pass

    # Routing table: Grok-3-mini is the default vision model ($0.003).
    # Upsize to Grok-4-latest only for orchestrate/multi-agent ($0.025).
    # DeepSeek for parallel swarms ($0.00013). Local models for code/classify ($0).

    # Routing table: Grok-3-mini is the default vision model.
    # Upsize to Grok-4-latest only for orchestrate/multi-agent tasks.
    # DeepSeek for parallel swarms. Local models for code/classify/lookup.
    routing = {
        "code":             ("ollama", "qwen2.5-coder:7b", 0.0),
        "classify":         ("ollama", "gemma:2b", 0.0),
        "simple_lookup":    ("ollama", "gemma:2b", 0.0),
        "analyze_reason":   ("grok" if grok_available else "deepseek",
                            "grok-3-mini" if grok_available else "deepseek-v4-flash",
                            0.003 if grok_available else 0.00013),
        "research":         ("grok" if grok_available else "deepseek",
                            "grok-3-mini" if grok_available else "deepseek-v4-flash",
                            0.003 if grok_available else 0.00013),
        "strategy":         ("grok" if grok_available else "deepseek",
                            "grok-3-mini" if grok_available else "deepseek-v4-flash",
                            0.003 if grok_available else 0.00013),
        "orchestrate":      ("grok" if grok_available else "deepseek",
                            "grok-4-latest" if grok_available else "deepseek-v4",
                            0.025 if grok_available else 0.00040),
    }

    # Complexity-aware routing: bump flash -> v4 for deep reasoning tasks
    provider, model, cost = routing.get(task_type, ("deepseek", "deepseek-v4-flash", 0.00013))

    # For complex reasoning tasks where Grok is unavailable, use deepseek-v4 (full)
    # instead of flash for 3x reasoning depth at 3x cost
    if provider == "deepseek" and model == "deepseek-v4-flash":
        complex_indicators = [
            "architecture", "design from scratch", "multi-step", "deep dive",
            "comprehensive", "thorough analysis", "system design", "orchestrate",
        ]
        goal_lower = goal.lower()
        if any(indicator in goal_lower for indicator in complex_indicators):
            model = "deepseek-v4"
            cost = 0.00040  # 3x flash cost for 3x reasoning depth

    # Cost guard: if daily spend > 80% of cap, fall back to DeepSeek
    if provider == "grok":
        try:
            from mag.cost_enforcer import get_current_spend
            spend = get_current_spend()
            daily_pct = spend.get("total_today", 0) / 0.50 * 100 if spend else 0
            if daily_pct > 80:
                provider, model, cost = "deepseek", "deepseek-v4-flash", 0.00013
        except Exception:
            pass

    if prefer_provider != "auto":
        provider = prefer_provider

    return {
        "task_type": task_type,
        "provider": provider,
        "model": model,
        "cost_est": cost,
    }


def build_parallel_swarm(goal: str, *, swarm_size: int = 3) -> list[dict[str, Any]]:
    """Build a parallel research swarm — multiple agents, different angles."""
    angles = [
        ("code", f"[ANGLE: code] {goal} Focus on implementation details, function signatures, error handling."),
        ("architecture", f"[ANGLE: architecture] {goal} Focus on how this fits in the broader system, dependencies, interfaces."),
        ("data_flow", f"[ANGLE: data flow] {goal} Focus on what data flows through, where it comes from, where it goes."),
        ("patterns", f"[ANGLE: patterns] {goal} Focus on recurring patterns, anti-patterns, and emergent behavior."),
        ("risks", f"[ANGLE: risks] {goal} Focus on failure modes, edge cases, what could break."),
    ]
    swarm_tasks = []
    for i in range(min(swarm_size, len(angles))):
        name, goal_text = angles[i]
        swarm_tasks.append({
            "angle": name,
            "goal": goal_text,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "cost_est": 0.00013,
        })
    synth_goal = (
        f"[SYNTHESIZE] Combine the following analyses into one unified report. "
        f"Original goal: {goal}. Angles covered: {', '.join(t['angle'] for t in swarm_tasks)}. "
        f"Write a concise synthesis to memory/copilot/outbox/swarm-synthesis.json"
    )
    swarm_tasks.append({
        "angle": "synthesize",
        "goal": synth_goal,
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "cost_est": 0.00013,
    })
    return swarm_tasks


def fire_swarm(goal: str, *, swarm_size: int = 3, dry: bool = False) -> dict[str, Any]:
    """Fire a parallel research swarm through the copilot inbox.

    Injects N+1 tasks simultaneously. Ghost picks them all up on next cycle.
    Total cost: (N+1) × $0.00013.
    """
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    swarm_id = f"swarm-{uuid.uuid4().hex[:8]}"
    tasks = build_parallel_swarm(goal, swarm_size=swarm_size)
    inbox = ROOT / "memory" / "copilot" / "inbox.jsonl"

    if dry:
        return {
            "swarm_id": swarm_id,
            "tasks": len(tasks),
            "total_cost": round(sum(t["cost_est"] for t in tasks), 6),
            "angles": [t["angle"] for t in tasks],
            "dry": True,
        }

    fired = []
    for i, task in enumerate(tasks):
        msg = {
            "id": f"{swarm_id}-{i:02d}-{task['angle']}",
            "action": "exec",
            "goal": task["goal"],
            "provider": task["provider"],
            "model": task["model"],
            "timeout_s": 180,
            "ts": now,
            "source": f"swarm-{swarm_id}",
            "_swarm": {"swarm_id": swarm_id, "angle": task["angle"], "index": i, "total": len(tasks)},
        }
        inbox.parent.mkdir(parents=True, exist_ok=True)
        with open(inbox, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        fired.append(msg["id"])

    return {
        "swarm_id": swarm_id,
        "fired": len(fired),
        "total_cost": round(sum(t["cost_est"] for t in tasks), 6),
        "angles": [t["angle"] for t in tasks],
        "task_ids": fired,
    }
