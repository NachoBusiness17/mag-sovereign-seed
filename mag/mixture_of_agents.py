"""Mixture of Agents — multi-model consensus at 1/50th the cost of Grok-4.

Steal from Together AI MoA (f-006, benefit=7, adapt=5).
Fan out to N cheap models, synthesize their outputs. Often outperforms a single
expensive model while costing 48x less.

"The wisdom of crowds is cheaper than the wisdom of one expensive model."
  — Ghost Friedman

COST COMPARISON:
  Grok-4 orchestration:   $0.025/call
  MoA (3x DeepSeek flash): $0.00052/call  (48x cheaper)
  MoA (3x Ollama local):  $0.00000/call   (infinitely cheaper)

SCHEMA: mixture_of_agents.v1
LAW: Preserve dissent. Consensus without dissent is groupthink.
LAW: Weight by confidence, not by model reputation.
LAW: The synthesizer is the cheapest capable model — never the most expensive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# AGENT RESPONSE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AgentVote:
    """One model's structured response to a task."""
    model: str
    answer: str
    confidence: float         # 0.0-1.0
    reasoning: str
    dissent: str = ""         # what the agent disagrees with or is unsure about
    citations: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "answer": self.answer[:500],
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning[:300],
            "dissent": self.dissent[:200],
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 1),
        }


@dataclass
class MoAResult:
    """Synthesized result from multiple agent votes."""
    goal: str
    votes: list[AgentVote]
    consensus: str             # the synthesized answer
    confidence: float          # aggregate confidence
    convergence: float         # how much models agreed (0-1)
    dissent_preserved: str     # minority views that were preserved
    models_used: list[str]
    total_cost_usd: float
    total_latency_ms: float
    method: str = "moa_v1"
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "mixture_of_agents.v1",
            "ts": self.ts,
            "goal": self.goal[:200],
            "votes": [v.to_dict() for v in self.votes],
            "consensus": self.consensus[:1000],
            "confidence": round(self.confidence, 3),
            "convergence": round(self.convergence, 3),
            "dissent_preserved": self.dissent_preserved[:300],
            "models_used": self.models_used,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_latency_ms": round(self.total_latency_ms, 1),
        }


# ═══════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ═══════════════════════════════════════════════════════════════════

AGENT_PROMPT = """You are one of {N} independent agents analyzing the same problem. Answer concisely.

TASK: {goal}

Respond in JSON:
{{
  "answer": "your concise answer (2-5 sentences)",
  "confidence": 0.0-1.0,
  "reasoning": "why you think this (1-2 sentences)",
  "dissent": "any uncertainty, disagreement, or alternative view (1 sentence or empty)"
}}

Be honest about confidence. Low confidence is better than confident error."""


SYNTHESIZER_PROMPT = """You are a synthesizer combining {N} independent analyses of the same problem.

ORIGINAL TASK: {goal}

AGENT RESPONSES:
{responses}

Synthesize these into one answer. Rules:
1. Where agents agree (convergence >= 0.7), state the consensus clearly.
2. Where agents disagree, preserve the minority view — do NOT erase dissent.
3. Weight by confidence, not by which model said what.
4. If confidence is low across all agents, say so.

Respond in JSON:
{{
  "consensus": "the synthesized answer",
  "confidence": 0.0-1.0,
  "convergence": 0.0-1.0,
  "dissent_preserved": "minority views that were kept (or empty if full consensus)"
}}"""


# ═══════════════════════════════════════════════════════════════════
# MOA ENGINE
# ═══════════════════════════════════════════════════════════════════

class MoAEngine:
    """Fan-out to N models, synthesize the results."""

    def __init__(self, default_models: list[str] | None = None):
        self.default_models = default_models or [
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-flash",
        ]
        self.synthesizer_model = "deepseek-v4-flash"
        self.stats = {"calls": 0, "total_cost": 0.0, "avg_convergence": 0.0}

    def query(
        self,
        goal: str,
        *,
        models: list[str] | None = None,
        dry_run: bool = False,
    ) -> MoAResult:
        """Query N models and synthesize the result.

        Args:
            goal: The task/question to answer.
            models: List of models to query. Defaults to 3x DeepSeek flash.
            dry_run: If True, simulate votes without API calls (for testing).

        Returns:
            MoAResult with consensus, votes, and cost breakdown.
        """
        models = models or self.default_models
        N = len(models)

        if dry_run:
            return self._dry_run(goal, models)

        # Phase 1: Fan out to N models
        votes = []
        for i, model_name in enumerate(models):
            vote = self._query_one(goal, model_name, i + 1, N)
            votes.append(vote)

        # Phase 2: Synthesize
        result = self._synthesize(goal, votes)

        # Update stats
        self.stats["calls"] += 1
        self.stats["total_cost"] += result.total_cost_usd
        # Rolling average convergence
        n = self.stats["calls"]
        self.stats["avg_convergence"] = (
            (self.stats["avg_convergence"] * (n - 1) + result.convergence) / n
        )

        # Log
        self._log_result(result)

        return result

    def _query_one(self, goal: str, model_name: str, agent_num: int, total: int) -> AgentVote:
        """Query a single model and parse its structured response."""
        prompt = AGENT_PROMPT.format(goal=goal, N=total)

        try:
            if "ollama" in model_name:
                from mag.llm import chat_ollama
                raw = chat_ollama(prompt, model=model_name)
                cost = 0.0
            elif "deepseek" in model_name:
                from mag.llm import chat_deepseek
                raw = chat_deepseek(prompt, system="Respond in JSON only.", max_tokens=1000)
                cost = 0.00013  # ~$0.00013 for a short call
            elif "grok" in model_name:
                from mag.llm import chat_grok
                raw = chat_grok(prompt, model=model_name)
                cost = 0.003 if "mini" in model_name else 0.025
            else:
                # Fallback: local heuristic
                raw = json.dumps({"answer": f"[simulated {model_name}]", "confidence": 0.5, "reasoning": "fallback", "dissent": ""})
                cost = 0.0
        except Exception:
            raw = json.dumps({"answer": f"[error querying {model_name}]", "confidence": 0.1, "reasoning": "query failed", "dissent": ""})
            cost = 0.0

        # Parse structured response
        parsed = self._parse_agent_response(raw, model_name)
        parsed.cost_usd = cost
        return parsed

    def _parse_agent_response(self, raw: str, model_name: str) -> AgentVote:
        """Parse a model's JSON response or extract best-effort from text."""
        try:
            # Try JSON
            json_start = raw.find("{")
            json_end = raw.rfind("}")
            if json_start >= 0 and json_end > json_start:
                data = json.loads(raw[json_start:json_end + 1])
                return AgentVote(
                    model=model_name,
                    answer=data.get("answer", raw[:200]),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                    dissent=data.get("dissent", ""),
                )
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Best-effort: treat first 300 chars as answer
        return AgentVote(
            model=model_name,
            answer=raw[:300].strip(),
            confidence=0.5,
            reasoning="(response could not be parsed as JSON)",
        )

    def _synthesize(self, goal: str, votes: list[AgentVote]) -> MoAResult:
        """Synthesize N agent votes into one result."""
        # Build response summary for the synthesizer
        response_lines = []
        for i, v in enumerate(votes):
            response_lines.append(
                f"Agent {i+1} ({v.model}, confidence={v.confidence:.2f}):\n"
                f"  Answer: {v.answer}\n"
                f"  Reasoning: {v.reasoning}\n"
                f"  Dissent: {v.dissent or 'none'}\n"
            )
        responses_text = "\n".join(response_lines)

        prompt = SYNTHESIZER_PROMPT.format(goal=goal, N=len(votes), responses=responses_text)

        # Synthesize with the cheapest capable model
        try:
            from mag.llm import chat_deepseek
            raw = chat_deepseek(prompt, system="Respond in JSON only.", max_tokens=1500)
            synth_cost = 0.00013
        except Exception:
            raw = json.dumps({"consensus": votes[0].answer, "confidence": 0.5, "convergence": 0.5, "dissent_preserved": ""})
            synth_cost = 0.0

        # Parse synthesizer output
        try:
            json_start = raw.find("{")
            json_end = raw.rfind("}")
            if json_start >= 0 and json_end > json_start:
                data = json.loads(raw[json_start:json_end + 1])
                consensus = data.get("consensus", raw[:500])
                confidence = float(data.get("confidence", 0.5))
                convergence = float(data.get("convergence", 0.5))
                dissent = data.get("dissent_preserved", "")
            else:
                consensus = raw[:500]
                confidence = 0.5
                convergence = 0.5
                dissent = ""
        except (json.JSONDecodeError, ValueError, TypeError):
            consensus = raw[:500]
            confidence = 0.5
            convergence = 0.5
            dissent = ""

        # Compute costs
        total_cost = sum(v.cost_usd for v in votes) + synth_cost

        return MoAResult(
            goal=goal,
            votes=votes,
            consensus=consensus,
            confidence=confidence,
            convergence=convergence,
            dissent_preserved=dissent,
            models_used=[v.model for v in votes] + [self.synthesizer_model],
            total_cost_usd=total_cost,
            total_latency_ms=0.0,  # would need actual latency tracking
        )

    def _dry_run(self, goal: str, models: list[str]) -> MoAResult:
        """Simulate MoA without API calls — for testing the framework."""
        angles = [
            ("implementation", 0.85, "Focus on code structure, functions, error handling."),
            ("architecture", 0.75, "Focus on system design, dependencies, interfaces."),
            ("risks", 0.70, "Focus on failure modes, edge cases, what could break."),
        ]

        votes = []
        for i, model_name in enumerate(models):
            angle_name, confidence, angle_focus = angles[i % len(angles)]
            votes.append(AgentVote(
                model=model_name,
                answer=f"[{angle_name}] Simulated analysis of: {goal[:100]}... {angle_focus}",
                confidence=confidence,
                reasoning=f"Simulated {angle_name}-angle reasoning for MoA dry run.",
                dissent="Dry run — no actual model queried." if i > 0 else "",
                cost_usd=0.0 if "ollama" in model_name else 0.00013,
            ))

        return MoAResult(
            goal=goal,
            votes=votes,
            consensus=f"[DRY RUN] Synthesized analysis of: {goal[:100]}. "
                       f"Angles: {', '.join(v.answer[:50] for v in votes)}. "
                       f"Confidence: {sum(v.confidence for v in votes)/len(votes):.2f}. "
                       f"Note: This is a simulated consensus — no models were actually queried.",
            confidence=sum(v.confidence for v in votes) / len(votes),
            convergence=0.75,
            dissent_preserved="Dry run — dissent preserved by design.",
            models_used=models,
            total_cost_usd=sum(v.cost_usd for v in votes),
            total_latency_ms=0.0,
        )

    def _log_result(self, result: MoAResult):
        """Log MoA results for analysis."""
        log_path = ROOT / "memory" / "moa" / "moa_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), default=str) + "\n")
        except OSError:
            pass

    # ── Cost comparison ──────────────────────────────────────────

    def compare_cost(self, goal: str) -> dict[str, Any]:
        """Compare MoA cost vs Grok-4 for the same task."""
        moa_cost = len(self.default_models) * 0.00013 + 0.00013  # N agents + synthesizer
        grok4_cost = 0.025

        return {
            "goal": goal[:200],
            "moa": {
                "models": self.default_models,
                "cost_per_call": round(moa_cost, 6),
                "cost_per_1000_calls": round(moa_cost * 1000, 2),
            },
            "grok4": {
                "cost_per_call": grok4_cost,
                "cost_per_1000_calls": round(grok4_cost * 1000, 2),
            },
            "savings": {
                "per_call": round(grok4_cost - moa_cost, 4),
                "ratio": f"{round(grok4_cost / moa_cost, 1)}x cheaper",
                "per_1000_calls": round((grok4_cost - moa_cost) * 1000, 2),
            },
        }


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_ENGINE: Optional[MoAEngine] = None


def get_engine() -> MoAEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = MoAEngine()
    return _ENGINE


def moa_query(goal: str, *, models: list[str] | None = None, dry_run: bool = False) -> MoAResult:
    """One-call MoA query."""
    return get_engine().query(goal, models=models, dry_run=dry_run)


def moa_compare(goal: str) -> dict[str, Any]:
    """Compare MoA cost vs alternatives."""
    return get_engine().compare_cost(goal)


def moa_dashboard() -> dict[str, Any]:
    """MoA engine stats."""
    engine = get_engine()
    return {
        "schema": "mixture_of_agents.v1",
        "ts": _now(),
        "stats": engine.stats,
        "default_models": engine.default_models,
        "synthesizer": engine.synthesizer_model,
        "cost_comparison": engine.compare_cost("example orchestration task"),
    }
