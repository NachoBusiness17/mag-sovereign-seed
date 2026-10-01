"""Frontier Scout — systematic theft from the best.

"Good artists copy. Great artists steal."
  — attributed to Picasso, actually stolen from Stravinsky

The Frontier Scout watches the AI frontier for techniques, models, tools, and
patterns worth stealing for the sovereign agent stack. It doesn't passively
observe — it actively assesses, recommends, and when configured, automatically
queues adaptation tasks.

Each finding is rated on four axes:
  BENEFIT:     How much does this improve the sovereign stack? (1-10)
  ADAPT_COST:  How hard is it to steal/adapt? (1-10, lower = easier to steal)
  IGNORE_RISK: What's the risk of NOT adopting this? (1-10)
  ADOPT_RISK:  What's the risk of adopting too early / dependency? (1-10)

VERDICT:
  STEAL_NOW:  Benefit > 6, Adapt cost < 5, Ignore risk > 4
  WATCH:      Benefit > 4, Adapt cost > 4, Ignore risk < 7
  PASS:       Benefit < 4, or Adopt risk > 7
  STEALTH:    Already stolen and integrated

SCHEMA: frontier_scout.v1
LAW: Never steal blindly. Assess, then adapt.
LAW: Credit the source. Theft with attribution is research.
LAW: Queue adaptation tasks through the architecture, not ad-hoc.
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

SCOUT_PATH = ROOT / "memory" / "frontier" / "scout_findings.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# FINDING MODEL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FrontierFinding:
    """One item worth stealing (or not)."""
    id: str
    category: str           # model, technique, tool, pricing, pattern, security
    name: str
    source: str             # where we found it
    description: str
    benefit: int            # 1-10
    adapt_cost: int         # 1-10, lower = easier
    ignore_risk: int        # 1-10
    adopt_risk: int         # 1-10
    verdict: str = ""       # STEAL_NOW, WATCH, PASS, STEALTH (computed)
    url: str = ""
    adaptation_plan: str = ""
    adapted_date: str = ""  # filled when STOLEN
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "frontier_scout.v1",
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "source": self.source,
            "description": self.description,
            "benefit": self.benefit,
            "adapt_cost": self.adapt_cost,
            "ignore_risk": self.ignore_risk,
            "adopt_risk": self.adopt_risk,
            "verdict": self.verdict,
            "url": self.url,
            "adaptation_plan": self.adaptation_plan,
            "adapted_date": self.adapted_date,
            "ts": self.ts,
        }


def compute_verdict(benefit: int, adapt_cost: int, ignore_risk: int, adopt_risk: int) -> str:
    """Compute verdict from the four axes."""
    if adopt_risk > 7:
        return "PASS"
    if benefit >= 6 and adapt_cost <= 5 and ignore_risk >= 4:
        return "STEAL_NOW"
    if benefit >= 4 and ignore_risk >= 3:
        return "WATCH"
    return "PASS"


# ═══════════════════════════════════════════════════════════════════
# SEEDED FINDINGS — current frontier, August 2026
# ═══════════════════════════════════════════════════════════════════

SEED_FINDINGS = [
    FrontierFinding(
        id="f-001",
        category="technique",
        name="DSPy — Declarative Self-improving Python",
        source="Stanford NLP / DSPy paper",
        description=(
            "Framework that replaces hand-crafted prompts with compiled prompt programs. "
            "Optimizer tunes prompts against a metric automatically. Would let us replace "
            "hand-tuned identity prompts with optimized versions, and auto-tune chain-of-thought "
            "for each task type rather than relying on static prompts."
        ),
        benefit=8,
        adapt_cost=3,
        ignore_risk=6,
        adopt_risk=2,
        url="https://github.com/stanfordnlp/dspy",
        adaptation_plan=(
            "1. Wrap DeepSeek/Grok calls as DSPy LM clients. "
            "2. Define sovereign metrics (sovereignty_score, chain_discipline_score). "
            "3. Compile Ghost identity prompt against metrics. "
            "4. Replace static prompts with compiled modules. "
            "Estimated effort: 2-3 days."
        ),
    ),
    FrontierFinding(
        id="f-002",
        category="model",
        name="DeepSeek-v4 (full) — 3x reasoning vs flash",
        source="DeepSeek API docs / pricing page",
        description=(
            "DeepSeek-v4 full model has significantly better reasoning than v4-flash at "
            "3x the cost. For tasks requiring multi-step reasoning (orchestration, research, "
            "code architecture), the extra cost may be justified. Currently we route everything "
            "to flash by default."
        ),
        benefit=7,
        adapt_cost=1,
        ignore_risk=5,
        adopt_risk=1,
        url="https://api-docs.deepseek.com/",
        adaptation_plan=(
            "1. Add deepseek-v4 to task_router provider list. "
            "2. Set capability tier for complex tasks. "
            "3. A/B test flash vs full on research tasks. "
            "4. Auto-route based on tokenomics cost/benefit. "
            "Estimated effort: 1 hour."
        ),
    ),
    FrontierFinding(
        id="f-003",
        category="technique",
        name="Constitutional AI — Claude-style self-correction",
        source="Anthropic Constitutional AI paper",
        description=(
            "Models critique and revise their own outputs against a constitution. "
            "We already have CONSTITUTION.md — wiring it as a self-critique loop "
            "would let Ghost police its own outputs against sovereign principles "
            "before they reach the operator."
        ),
        benefit=9,
        adapt_cost=4,
        ignore_risk=7,
        adopt_risk=3,
        url="https://arxiv.org/abs/2212.08073",
        adaptation_plan=(
            "1. Load CONSTITUTION.md as critique prompt. "
            "2. Add self-critique step after each Ghost response. "
            "3. Revise against violations before returning. "
            "4. Log critique/revision pairs to Verkle chain. "
            "Estimated effort: 1 day."
        ),
    ),
    FrontierFinding(
        id="f-004",
        category="tool",
        name="Unsloth — 2-5x faster LoRA training",
        source="unsloth.ai / GitHub",
        description=(
            "Unsloth dramatically accelerates LoRA fine-tuning (2-5x) and reduces VRAM "
            "usage (up to 70%). Already referenced in our LoRA pipeline but not yet "
            "integrated into the Vast.ai training script."
        ),
        benefit=6,
        adapt_cost=2,
        ignore_risk=3,
        adopt_risk=1,
        url="https://github.com/unslothai/unsloth",
        adaptation_plan=(
            "1. Add unsloth import to train_ghost.py. "
            "2. Replace standard transformers load with FastLanguageModel. "
            "3. Test on Vast.ai RTX 4090. "
            "Estimated effort: 30 min."
        ),
    ),
    FrontierFinding(
        id="f-005",
        category="technique",
        name="Context Compression — LLMLingua / prompt compaction",
        source="Microsoft LLMLingua paper",
        description=(
            "Compress long prompts by 2-5x while preserving essential information. "
            "Would directly reduce token costs — every 1000 tokens saved is $0.013 saved "
            "on DeepSeek. Our Ghost identity prompt is ~1500 tokens; compaction could "
            "drop it to ~400 without losing sovereignty."
        ),
        benefit=8,
        adapt_cost=3,
        ignore_risk=5,
        adopt_risk=3,
        url="https://arxiv.org/abs/2310.05736",
        adaptation_plan=(
            "1. Install llmlingua. "
            "2. Compress Ghost identity prompt against sovereignty preservation metric. "
            "3. A/B test compressed vs full prompt on 50 tasks. "
            "4. Deploy compressed as default, keep full as fallback. "
            "Estimated effort: 2-3 hours."
        ),
    ),
    FrontierFinding(
        id="f-006",
        category="pattern",
        name="Mixture of Agents — multi-model consensus",
        source="Together AI MoA paper / open-source",
        description=(
            "Use multiple cheap models in parallel, then synthesize their outputs. "
            "Often outperforms a single expensive model. We already use exit dialogues "
            "(Grok + DeepSeek) — MoA would generalize this to N models with weighted voting. "
            "Could replace Grok-4 orchestration with Grok-3-mini + DeepSeek consensus."
        ),
        benefit=7,
        adapt_cost=5,
        ignore_risk=4,
        adopt_risk=4,
        url="https://arxiv.org/abs/2406.04692",
        adaptation_plan=(
            "1. Extend task_router to fan-out to N models. "
            "2. Build synthesis layer (weighted vote / ensemble). "
            "3. A/B test consensus vs single-model on orchestration tasks. "
            "4. Add ensemble cost to tokenomics dashboard. "
            "Estimated effort: 2-3 days."
        ),
    ),
    FrontierFinding(
        id="f-007",
        category="technique",
        name="RAG 2.0 — GraphRAG with knowledge graphs",
        source="Microsoft GraphRAG paper",
        description=(
            "Replace flat vector search with knowledge graph traversal for retrieval. "
            "Our Verkle chain is already a graph — GraphRAG would let us query it "
            "semantically rather than by exact match. Would make chain_query.py "
            "dramatically more powerful."
        ),
        benefit=7,
        adapt_cost=6,
        ignore_risk=3,
        adopt_risk=5,
        url="https://arxiv.org/abs/2404.16130",
        adaptation_plan=(
            "1. Build entity/relationship extractor for Verkle chain. "
            "2. Construct knowledge graph from chain entries. "
            "3. Add semantic traversal to chain_query.py. "
            "4. Hybrid: exact match fallback + semantic search. "
            "Estimated effort: 3-5 days."
        ),
    ),
    FrontierFinding(
        id="f-008",
        category="model",
        name="Qwen2.5-Coder-7B — better local coding model",
        source="Alibaba Qwen team / HuggingFace",
        description=(
            "Qwen2.5-Coder-7B outperforms our current local qwen2.5-coder:7b on "
            "most coding benchmarks. Could replace it as the free local model for "
            "doctor, steward, and basic coding tasks — zero cost, better results."
        ),
        benefit=5,
        adapt_cost=2,
        ignore_risk=2,
        adopt_risk=1,
        url="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct",
        adaptation_plan=(
            "1. Pull updated model: ollama pull qwen2.5-coder:7b (check if newer). "
            "2. Run benchmark on 10 tasks vs current. "
            "3. Switch default if improved. "
            "Estimated effort: 30 min."
        ),
    ),
    FrontierFinding(
        id="f-009",
        category="tool",
        name="MCP (Model Context Protocol) — standardized tool interface",
        source="Anthropic MCP specification",
        description=(
            "MCP is becoming the standard for AI-tool interfaces. Our tools (file ops, "
            "chain query, etc.) are custom — adopting MCP would make them "
            "interoperable with any MCP-compatible agent. Claude Code, Cursor, and "
            "others already support it."
        ),
        benefit=6,
        adapt_cost=7,
        ignore_risk=6,
        adopt_risk=3,
        url="https://modelcontextprotocol.io/",
        adaptation_plan=(
            "1. Map existing tool surface to MCP spec. "
            "2. Build MCP server wrapping sovereign tools. "
            "3. Test with Claude Code / Cursor as proof. "
            "4. Maintain custom interface as primary, MCP as sidecar. "
            "Estimated effort: 1-2 weeks."
        ),
    ),
    FrontierFinding(
        id="f-010",
        category="pattern",
        name="Agentic SWE — Devin/Devin-like autonomous coding",
        source="Cognition AI / SWE-bench results",
        description=(
            "Autonomous coding agents are solving real SWE-bench problems. Our "
            "steward module is a primitive version. Full agentic SWE would let Ghost "
            "autonomously fix bugs, add features, and refactor — all gated by "
            "constitutional critique and operator approval."
        ),
        benefit=8,
        adapt_cost=8,
        ignore_risk=7,
        adopt_risk=6,
        url="https://www.cognition.ai/",
        adaptation_plan=(
            "1. Study SWE-bench agent architectures (Devin, SWE-Agent, OpenDevin). "
            "2. Extend steward with plan-execute-verify loop. "
            "3. Gate all changes through constitutional critique. "
            "4. Require operator approval for file mutations. "
            "5. Run against our own codebase as test. "
            "Estimated effort: 1-2 weeks."
        ),
    ),
    FrontierFinding(
        id="f-011",
        category="pricing",
        name="DeepSeek price drops — continuous monitoring",
        source="DeepSeek API pricing page",
        description=(
            "DeepSeek prices have been falling. v4-flash launched at a higher rate "
            "and dropped to $0.013/1M tokens. Further drops may occur. "
            "Continuous monitoring ensures we always have the cheapest capable route."
        ),
        benefit=4,
        adapt_cost=1,
        ignore_risk=3,
        adopt_risk=1,
        url="https://api-docs.deepseek.com/quick_start/pricing",
        adaptation_plan=(
            "1. Add pricing check to Scout cadence (weekly). "
            "2. Auto-update PROVIDER_PRICES in tokenomics.py. "
            "3. Alert if >20% price change. "
            "Estimated effort: already wired via tokenomics."
        ),
    ),
    FrontierFinding(
        id="f-012",
        category="technique",
        name="Speculative Decoding — 2-3x inference speedup",
        source="Google / DeepMind speculative decoding papers",
        description=(
            "Use a small draft model to generate tokens, then verify with the large "
            "model. 2-3x speedup with no quality loss. Our local Ollama models could "
            "serve as draft models for DeepSeek API calls — but requires both models "
            "to share a tokenizer, which complicates cross-provider use."
        ),
        benefit=5,
        adapt_cost=8,
        ignore_risk=2,
        adopt_risk=4,
        url="https://arxiv.org/abs/2302.01318",
        adaptation_plan=(
            "1. Check tokenizer compatibility between qwen2.5-coder and deepseek-v4. "
            "2. If compatible, prototype speculative loop. "
            "3. Measure latency improvement vs cost. "
            "4. Only deploy if net savings >30%. "
            "Estimated effort: 3-5 days (high uncertainty)."
        ),
    ),
]

# Compute verdicts
for f in SEED_FINDINGS:
    f.verdict = compute_verdict(f.benefit, f.adapt_cost, f.ignore_risk, f.adopt_risk)


# ═══════════════════════════════════════════════════════════════════
# SCOUT ENGINE
# ═══════════════════════════════════════════════════════════════════

class FrontierScout:
    """Watches the frontier, assesses what's worth stealing."""

    def __init__(self):
        SCOUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    def seed_findings(self) -> int:
        """Write seed findings to the scout file if not already present."""
        existing_ids = self._existing_ids()
        written = 0
        with open(SCOUT_PATH, "a", encoding="utf-8") as f:
            for finding in SEED_FINDINGS:
                if finding.id not in existing_ids:
                    f.write(json.dumps(finding.to_dict(), default=str) + "\n")
                    existing_ids.add(finding.id)
                    written += 1
        return written

    def _existing_ids(self) -> set[str]:
        if not SCOUT_PATH.is_file():
            return set()
        ids = set()
        try:
            for line in SCOUT_PATH.read_text(encoding="utf-8").strip().splitlines():
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ids.add(entry.get("id", ""))
                except json.JSONDecodeError:
                    continue
        except (UnicodeDecodeError, OSError):
            pass
        return ids

    def all_findings(self) -> list[dict[str, Any]]:
        """Read all findings."""
        if not SCOUT_PATH.is_file():
            self.seed_findings()
        findings = []
        try:
            for line in SCOUT_PATH.read_text(encoding="utf-8").strip().splitlines():
                if not line:
                    continue
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except (UnicodeDecodeError, OSError):
            pass
        return findings

    def by_verdict(self) -> dict[str, list[dict[str, Any]]]:
        """Group findings by verdict."""
        grouped: dict[str, list[dict[str, Any]]] = {"STEAL_NOW": [], "WATCH": [], "PASS": [], "STEALTH": []}
        for f in self.all_findings():
            verdict = f.get("verdict", "PASS")
            grouped.setdefault(verdict, []).append(f)
        return grouped

    def steal_now(self) -> list[dict[str, Any]]:
        """Get everything worth stealing immediately."""
        return [f for f in self.all_findings() if f.get("verdict") == "STEAL_NOW"]

    def queue_steal_task(self, finding_id: str) -> dict[str, Any]:
        """Queue a steal-now finding as an adaptation task."""
        findings = {f["id"]: f for f in self.all_findings()}
        finding = findings.get(finding_id)
        if not finding:
            return {"ok": False, "error": f"Finding {finding_id} not found"}

        if finding["verdict"] not in ("STEAL_NOW", "WATCH"):
            return {"ok": False, "error": f"Finding {finding_id} verdict is {finding['verdict']}, not stealable"}

        # Queue through orchestrator
        goal = f"[scout] Steal: {finding['name']} — {finding['adaptation_plan'][:80]}..."
        try:
            from mag.orchestrator import spawn_task
            task = spawn_task(goal, provider="deepseek", tag="frontier-scout")
            return {
                "ok": True,
                "finding_id": finding_id,
                "finding_name": finding["name"],
                "task": task,
                "adaptation_plan": finding["adaptation_plan"],
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "manual_plan": finding["adaptation_plan"]}

    def mark_stolen(self, finding_id: str) -> dict[str, Any]:
        """Mark a finding as STEALTH (successfully stolen and integrated)."""
        findings = self.all_findings()
        updated = None
        for f in findings:
            if f["id"] == finding_id:
                f["verdict"] = "STEALTH"
                f["adapted_date"] = _now()
                updated = f
                break

        if not updated:
            return {"ok": False, "error": f"Finding {finding_id} not found"}

        # Rewrite file
        SCOUT_PATH.write_text(
            "\n".join(json.dumps(f, default=str) for f in findings) + "\n",
            encoding="utf-8",
        )
        return {"ok": True, "finding": updated}

    # ── Dashboard ───────────────────────────────────────────────

    def dashboard(self) -> dict[str, Any]:
        """Full frontier scout dashboard."""
        by_verdict = self.by_verdict()
        all_f = self.all_findings()

        return {
            "schema": "frontier_scout.v1",
            "ts": _now(),
            "summary": {
                "total_findings": len(all_f),
                "steal_now": len(by_verdict.get("STEAL_NOW", [])),
                "watching": len(by_verdict.get("WATCH", [])),
                "passed": len(by_verdict.get("PASS", [])),
                "stolen": len(by_verdict.get("STEALTH", [])),
            },
            "steal_now": by_verdict.get("STEAL_NOW", []),
            "watching": by_verdict.get("WATCH", []),
            "by_category": self._by_category(all_f),
            "top_recommendation": by_verdict.get("STEAL_NOW", [{}])[0] if by_verdict.get("STEAL_NOW") else None,
        }

    def _by_category(self, findings: list[dict[str, Any]]) -> dict[str, int]:
        cats: dict[str, int] = {}
        for f in findings:
            cat = f.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1
        return cats


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_SCOUT: Optional[FrontierScout] = None


def get_scout() -> FrontierScout:
    global _SCOUT
    if _SCOUT is None:
        _SCOUT = FrontierScout()
        _SCOUT.seed_findings()  # auto-seed on first access
    return _SCOUT


def scout_dashboard() -> dict[str, Any]:
    return get_scout().dashboard()


def scout_steal_now() -> list[dict[str, Any]]:
    return get_scout().steal_now()


def scout_queue_steal(finding_id: str) -> dict[str, Any]:
    return get_scout().queue_steal_task(finding_id)


def scout_mark_stolen(finding_id: str) -> dict[str, Any]:
    return get_scout().mark_stolen(finding_id)
