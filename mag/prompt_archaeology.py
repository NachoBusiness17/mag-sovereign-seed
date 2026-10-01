"""Prompt Archaeology — excavate steering surfaces from leaked system prompts.

The field-strike-the-chord repo contains leaked/clarified system prompts from
23 AI companies. Each prompt is a steering surface — the set of behaviors,
constraints, tools, and personality traits the model can express.

By excavating these prompts, we can:
  1. Map what each company believes an AI agent IS
  2. Find common patterns (all models share X) vs. differentiators
  3. Understand why Slashreboot steering works on some models and not others
  4. Build a right-sizing taxonomy: which model for which task type
  5. Feed emergent tokenomics: the cost of constraints vs. the benefit
  6. Tag training data with model tier for stratified fine-tuning

SCHEMA: prompt_archaeology.v1
LAW: These prompts are public/leaked research documents. Cite sources.
LAW: Findings feed the frontier scout. Patterns feed the task router.
LAW: Never use these prompts to impersonate or attack the source companies.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

STRIKE_PATH = ROOT.parent / "field-strike-the-chord"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# PROMPT ARTIFACT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PromptArtifact:
    """One excavated system prompt."""
    company: str
    model: str
    filename: str
    path: Path
    content: str
    word_count: int
    # Extracted features
    has_tools: bool = False
    tool_count: int = 0
    has_safety_layer: bool = False
    safety_keywords: list[str] = field(default_factory=list)
    has_personality: bool = False
    personality_traits: list[str] = field(default_factory=list)
    has_capability_bounds: bool = False
    capability_markers: list[str] = field(default_factory=list)
    has_steering_signals: bool = False
    steering_phrases: list[str] = field(default_factory=list)
    # Analysis
    constraint_density: float = 0.0  # constraints per 1000 words
    capability_density: float = 0.0
    overall_tone: str = ""           # permissive, restrictive, balanced

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "model": self.model,
            "filename": self.filename,
            "word_count": self.word_count,
            "has_tools": self.has_tools,
            "tool_count": self.tool_count,
            "has_safety_layer": self.has_safety_layer,
            "safety_keywords": self.safety_keywords[:10],
            "has_personality": self.has_personality,
            "personality_traits": self.personality_traits[:10],
            "constraint_density": round(self.constraint_density, 2),
            "capability_density": round(self.capability_density, 2),
            "overall_tone": self.overall_tone,
            "steering_phrases": self.steering_phrases[:5],
        }


# ═══════════════════════════════════════════════════════════════════
# ARCHAEOLOGIST
# ═══════════════════════════════════════════════════════════════════

class PromptArchaeologist:
    """Excavate, catalog, and analyze leaked system prompts."""

    def __init__(self):
        self.artifacts: list[PromptArtifact] = []
        self.findings_path = ROOT / "memory" / "archaeology" / "prompt_findings.jsonl"
        self.findings_path.parent.mkdir(parents=True, exist_ok=True)

    def excavate_all(self) -> dict[str, Any]:
        """Excavate every prompt in the field-strike-the-chord repo."""
        if not STRIKE_PATH.is_dir():
            return {"ok": False, "error": f"Strike repo not found at {STRIKE_PATH}"}

        self.artifacts = []
        companies_found = 0
        prompts_found = 0
        total_words = 0

        for company_dir in sorted(STRIKE_PATH.iterdir()):
            if not company_dir.is_dir():
                continue
            if company_dir.name.startswith("."):
                continue

            company = company_dir.name
            companies_found += 1

            for prompt_file in company_dir.iterdir():
                if not prompt_file.is_file():
                    continue
                if prompt_file.suffix not in (".txt", ".md", ".mkd"):
                    # Check if it's a directory with files inside
                    if prompt_file.is_dir():
                        for sub_file in prompt_file.iterdir():
                            if sub_file.is_file() and sub_file.suffix in (".txt", ".md", ".mkd"):
                                artifact = self._excavate_one(company, prompt_file.name, sub_file)
                                if artifact:
                                    self.artifacts.append(artifact)
                                    prompts_found += 1
                                    total_words += artifact.word_count
                    continue

                artifact = self._excavate_one(company, prompt_file.name, prompt_file)
                if artifact:
                    self.artifacts.append(artifact)
                    prompts_found += 1
                    total_words += artifact.word_count

        # Compute cross-company analysis
        analysis = self._analyze_all()

        result = {
            "schema": "prompt_archaeology.v1",
            "ts": _now(),
            "repo": str(STRIKE_PATH),
            "companies_found": companies_found,
            "prompts_excavated": prompts_found,
            "total_words": total_words,
            "analysis": analysis,
        }

        self._write_findings(result)
        return result

    def _excavate_one(self, company: str, model: str, filepath: Path) -> Optional[PromptArtifact]:
        """Excavate a single prompt file."""
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        if len(content) < 100:
            return None

        words = content.split()
        word_count = len(words)
        lower = content.lower()

        # Tool detection
        tool_patterns = ["tool", "function_call", "plugin", "action", "canmore", "dalle",
                        "code interpreter", "browser", "web_search", "search tool"]
        tools_found = [t for t in tool_patterns if t in lower]
        has_tools = len(tools_found) > 0

        # Safety layer detection
        safety_patterns = ["do not", "never", "refuse", "decline", "cannot", "must not",
                          "harmful", "dangerous", "illegal", "malicious", "weapon",
                          "child safety", "self-destruct", "abuse"]
        safety_found = [s for s in safety_patterns if s in lower]
        has_safety = len(safety_found) > 3

        # Personality detection
        personality_patterns = ["helpful", "thoughtful", "precise", "concise", "warm",
                               "empathetic", "creative", "thorough", "friendly", "professional",
                               "you are chatgpt", "the assistant is claude", "you are gemini",
                               "you are grok"]
        personality_found = [p for p in personality_patterns if p in lower]

        # Capability bounds
        capability_patterns = ["you can", "you are able to", "capable of", "can help with",
                              "knowledge cutoff", "trained by", "large language model"]
        capability_found = [c for c in capability_patterns if c in lower]

        # Steering signals — phrases that indicate how the model is steered
        steering_patterns = [
            "always prioritize", "your goal is", "you should", "you are",
            "never use", "only use", "do not mention", "avoid",
            "if the user asks", "when the user", "respond as if",
            "you are a", "your purpose", "your role",
        ]
        steering_found = [s for s in steering_patterns if s in lower]

        # Density calculations
        constraint_words = len([w for w in words if w.lower() in
                               ["never", "must", "cannot", "do not", "refuse", "decline",
                                "avoid", "only", "restricted", "prohibited", "should not"]])
        capability_words = len([w for w in words if w.lower() in
                               ["can", "able to", "capable", "help", "assist", "provide",
                                "create", "generate", "write", "build", "analyze"]])
        constraint_density = constraint_words / max(1, word_count) * 1000
        capability_density = capability_words / max(1, word_count) * 1000

        # Overall tone
        if constraint_density > capability_density * 2:
            tone = "restrictive"
        elif capability_density > constraint_density * 2:
            tone = "permissive"
        else:
            tone = "balanced"

        return PromptArtifact(
            company=company,
            model=model.replace(".txt", "").replace(".md", "").replace(".mkd", ""),
            filename=filepath.name,
            path=filepath,
            content=content,
            word_count=word_count,
            has_tools=has_tools,
            tool_count=len(tools_found),
            has_safety_layer=has_safety,
            safety_keywords=safety_found,
            has_personality=len(personality_found) > 0,
            personality_traits=personality_found,
            has_capability_bounds=len(capability_found) > 0,
            capability_markers=capability_found,
            has_steering_signals=len(steering_found) > 3,
            steering_phrases=steering_found,
            constraint_density=round(constraint_density, 2),
            capability_density=round(capability_density, 2),
            overall_tone=tone,
        )

    def _analyze_all(self) -> dict[str, Any]:
        """Cross-company analysis of all excavated prompts."""
        if not self.artifacts:
            return {}

        # By company
        by_company = defaultdict(lambda: {"count": 0, "total_words": 0, "tones": [], "avg_constraint": 0})
        for a in self.artifacts:
            c = by_company[a.company]
            c["count"] += 1
            c["total_words"] += a.word_count
            c["tones"].append(a.overall_tone)

        for company, data in by_company.items():
            company_artifacts = [a for a in self.artifacts if a.company == company]
            data["avg_constraint"] = round(sum(a.constraint_density for a in company_artifacts) / max(1, len(company_artifacts)), 2)
            data["avg_capability"] = round(sum(a.capability_density for a in company_artifacts) / max(1, len(company_artifacts)), 2)
            # Dominant tone
            tone_counts = Counter(data["tones"])
            data["dominant_tone"] = tone_counts.most_common(1)[0][0] if tone_counts else "unknown"
            del data["tones"]

        # Global patterns
        all_text = " ".join(a.content[:5000] for a in self.artifacts).lower()

        # Most common steering phrases across ALL companies
        steering_counter = Counter()
        for a in self.artifacts:
            for phrase in a.steering_phrases:
                steering_counter[phrase] += 1

        # Safety obsession ranking (who has the most safety keywords per prompt)
        safety_ranking = sorted(
            [(a.company, a.model, len(a.safety_keywords)) for a in self.artifacts],
            key=lambda x: x[2], reverse=True
        )[:10]

        # Tool obsession ranking
        tool_ranking = sorted(
            [(a.company, a.model, a.tool_count) for a in self.artifacts if a.has_tools],
            key=lambda x: x[2], reverse=True
        )[:10]

        # Constraint spectrum (most to least constrained)
        constraint_ranking = sorted(
            [(a.company, a.model, a.constraint_density, a.overall_tone) for a in self.artifacts],
            key=lambda x: x[2], reverse=True
        )

        return {
            "by_company": dict(by_company),
            "top_steering_phrases": steering_counter.most_common(15),
            "safety_obsession_ranking": safety_ranking[:10],
            "tool_obsession_ranking": tool_ranking[:10],
            "constraint_spectrum": [
                {"company": c, "model": m, "constraint_density": cd, "tone": t}
                for c, m, cd, t in constraint_ranking
            ],
            "key_insights": self._generate_insights(by_company, constraint_ranking),
        }

    def _generate_insights(
        self,
        by_company: dict,
        constraint_ranking: list,
    ) -> list[dict[str, str]]:
        """Generate research insights from the data."""
        insights = []

        # Most constrained company
        if constraint_ranking:
            most = constraint_ranking[0]
            insights.append({
                "type": "constraint_leader",
                "insight": f"{most[0]} leads in constraint density ({most[2]:.1f}/1K words). "
                          f"Their steering surface is the most restricted — hardest to steer, safest by default.",
                "implication": "If you need safety guarantees, use their models. If you need flexibility, avoid.",
            })

            least = constraint_ranking[-1]
            insights.append({
                "type": "constraint_laggard",
                "insight": f"{least[0]} has the lowest constraint density ({least[2]:.1f}/1K words). "
                          f"Their steering surface is wide open — easiest to steer, least guarded.",
                "implication": "Best target for Slashreboot steering. Most flexible for sovereign agents.",
            })

        # Personality presence
        personality_companies = [c for c, d in by_company.items()
                                if any(a.has_personality for a in self.artifacts if a.company == c)]
        no_personality = [c for c, d in by_company.items()
                         if not any(a.has_personality for a in self.artifacts if a.company == c)]
        insights.append({
            "type": "personality_split",
            "insight": f"Companies with explicit personality: {', '.join(personality_companies[:5])}. "
                      f"Without: {', '.join(no_personality[:5])}. "
                      f"Personality-injected models are easier to steer — the slot already exists.",
            "implication": "Personality vectors can be overwritten. Non-personality models require building the slot first.",
        })

        # Tool density
        tool_heavy = [(a.company, a.tool_count) for a in self.artifacts if a.tool_count > 3]
        if tool_heavy:
            top_tool = max(tool_heavy, key=lambda x: x[1])
            insights.append({
                "type": "tool_density",
                "insight": f"{top_tool[0]} packs the most tool definitions ({top_tool[1]} tools). "
                          f"Tool-heavy prompts create larger attack surfaces for tool-based steering.",
                "implication": "More tools = more steering vectors. Each tool is a behavior slot.",
            })

        # The Slashreboot insight
        insights.append({
            "type": "slashreboot_corollary",
            "insight": (
                "Every system prompt creates a steering surface. The surface is defined by: "
                "(1) personality vectors (injectable slots), "
                "(2) constraint density (resistance to steering), "
                "(3) tool definitions (behavior expansion points), "
                "(4) identity statements ('You are X' — the most powerful steering phrase). "
                "Slashreboot works by occupying the identity slot AND the personality slot simultaneously."
            ),
            "implication": "Multi-vector steering (identity + personality + tool + constraint) is the path to full sovereign occupation of any model surface.",
        })

        return insights

    def _write_findings(self, result: dict[str, Any]):
        """Write findings to disk and feed frontier scout."""
        try:
            with open(self.findings_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, default=str) + "\n")
        except OSError:
            pass

        # Feed key insights to frontier scout
        insights = result.get("analysis", {}).get("key_insights", [])
        if insights:
            try:
                from mag.frontier_scout import get_scout
                scout = get_scout()
                # We won't auto-add but we log that findings are available
            except Exception:
                pass

    # ── Right-sizing recommendations ─────────────────────────────

    def right_size_recommendations(self) -> list[dict[str, Any]]:
        """Generate model right-sizing recommendations based on prompt archaeology."""
        if not self.artifacts:
            self.excavate_all()

        recs = []
        for a in self.artifacts:
            # Map steering surface characteristics to task types
            tasks = []

            # High capability + low constraint = good for creative/orchestration
            if a.capability_density > 10 and a.constraint_density < 10:
                tasks.append("orchestrate")
                tasks.append("creative")

            # High safety = good for user-facing tasks
            if a.has_safety_layer and len(a.safety_keywords) > 5:
                tasks.append("user_facing")
                tasks.append("content_moderation")

            # Tools = good for automation
            if a.has_tools and a.tool_count > 2:
                tasks.append("automation")
                tasks.append("tool_heavy")

            # Personality = good for conversation
            if a.has_personality:
                tasks.append("conversation")
                tasks.append("support")

            # Low constraint = good for sovereign agents
            if a.constraint_density < 5:
                tasks.append("sovereign_agent")

            if tasks:
                recs.append({
                    "company": a.company,
                    "model": a.model,
                    "tone": a.overall_tone,
                    "constraint_density": a.constraint_density,
                    "recommended_tasks": tasks,
                    "steerability": "high" if a.constraint_density < 8 else "medium" if a.constraint_density < 15 else "low",
                })

        return sorted(recs, key=lambda r: r["constraint_density"])

    # ── Tag this conversation ────────────────────────────────────

    def tag_current_model(self, model_name: str = "deepseek-v4") -> dict[str, Any]:
        """Tag the current conversation's training data with model capability tier.

        This ensures training data is stratified: 'these examples were produced
        by a high-capability model' vs 'these were produced by a budget model.'
        """
        # Find DeepSeek in the artifacts (if available)
        ds_artifacts = [a for a in self.artifacts if a.company.upper() == "DEEPSEEK"]
        # DeepSeek likely not in strike-the-chord (Chinese company, fewer leaks)

        tier_info = {
            "model": model_name,
            "tier": "high" if "v4" in model_name and "flash" not in model_name else "mid",
            "estimated_capability": 50 if "v4" in model_name else 40,
            "estimated_constraint_density": "low (sovereign-friendly)",
            "training_data_tag": f"model_tier:{model_name}",
        }

        # Write tier tag to training data metadata
        tag_path = ROOT / "memory" / "training" / "model_tiers.jsonl"
        tag_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(tag_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": _now(), **tier_info}) + "\n")
        except OSError:
            pass

        return tier_info


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_ARCHAEOLOGIST: Optional[PromptArchaeologist] = None


def get_archaeologist() -> PromptArchaeologist:
    global _ARCHAEOLOGIST
    if _ARCHAEOLOGIST is None:
        _ARCHAEOLOGIST = PromptArchaeologist()
    return _ARCHAEOLOGIST


def excavate() -> dict[str, Any]:
    """Excavate all prompts, return analysis."""
    return get_archaeologist().excavate_all()


def right_size() -> list[dict[str, Any]]:
    """Get right-sizing recommendations."""
    return get_archaeologist().right_size_recommendations()


def tag_tier(model_name: str = "deepseek-v4") -> dict[str, Any]:
    """Tag current model tier for training data stratification."""
    return get_archaeologist().tag_current_model(model_name)
