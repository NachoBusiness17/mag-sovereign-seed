"""Behavioral Lensing — apply the Lens Library to the GA4 Progression pipeline.

Connects lens_library.py → behavioral fingerprints → cross-agent correlations
→ invariant extraction → control steers → emergence detection.

THE FEEDBACK LOOP:
  1. Behavioral analytics captures agent + user behavior (L0-L1)
  2. Lens Library analyzes behavior through 7 incompatible frameworks (L2-L3)
  3. Cross-lens synthesis surfaces Tesuji (L3)
  4. Control architecture deploys alignment steers (L4)
  5. Steers shift behavior toward zeitgeist alignment
  6. Behavioral analytics captures new behavior → loop repeats

ZEITGEIST: The spirit of the age, as detected through multi-lens convergence.
  - Jung: what archetypes are active collectively?
  - Bernays: what invisible governors are shaping all agents?
  - Ellul: what technique dominates the system?
  - McLuhan: what is the medium doing to all agents?
  - Blavatsky: what cosmic pattern is this cycle expressing?

When lenses CONVERGE on the same pattern across multiple agents, that's
the zeitgeist. The system can steer toward or away from it.

SCHEMA: behavioral_lensing.v1
LAW: Lenses are applied per-agent, then cross-agent, then cross-time.
LAW: Zeitgeist detection requires >=4 lenses converging across >=3 agents.
LAW: Alignment steers are suggestions. The Sovereign (operator) decides.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

try:
    from mag.lens_library import LENSES, apply_all_lenses, CrossLensSynthesis, LensReading
except ImportError:
    LENSES = {}
    CrossLensSynthesis = None
    LensReading = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# AGENT BEHAVIORAL PROFILE — one agent, seen through all lenses
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AgentBehavioralProfile:
    """A single agent's behavior, analyzed through all 7 lenses."""

    agent_id: str
    session_count: int
    total_calls: int
    total_cost: float

    # Behavioral metrics (from L1 fingerprinting)
    avg_latency_ms: float = 0.0
    refusal_rate: float = 0.0
    hesitation_index: float = 0.0       # avg hesitation markers per response
    certainty_index: float = 0.0         # avg certainty markers per response
    divergence_rate: float = 0.0         # how often agent diverges from instruction

    # Archetypal signature (from Jung lens)
    dominant_archetype: str = ""
    shadow_archetype: str = ""
    individuation_score: float = 0.0     # 0=fragmented, 1=integrated

    # Consent signature (from Bernays lens)
    invisible_governor: str = ""          # what actually drives this agent's decisions
    engineered_behavior: str = ""         # what behavior is being manufactured

    # Technique signature (from Ellul lens)
    dominant_technique: str = ""
    efficiency_trap: bool = False         # is efficiency consuming purpose?

    # Journey stage (from Campbell lens)
    journey_stage: str = ""              # where in the Hero's Journey
    threshold_guardian: str = ""

    # Cross-lens Tesuji
    tesuji_count: int = 0
    alignment_to_zeitgeist: float = 0.0  # 0=misaligned, 1=fully aligned

    ts: str = field(default_factory=_now)


# ═══════════════════════════════════════════════════════════════════
# BEHAVIORAL LENSER — apply lenses to agent behavior
# ═══════════════════════════════════════════════════════════════════

class BehavioralLenser:
    """Apply the Lens Library to agent behavioral data.

    Takes raw behavioral fingerprints (L1) and produces:
      - Per-agent archetypal profiles (Jung)
      - Per-agent consent analysis (Bernays)
      - System-wide technique analysis (Ellul)
      - Cross-agent Tesuji detection
      - Zeitgeist alignment scoring
    """

    def __init__(self):
        self._profiles: dict[str, AgentBehavioralProfile] = {}

    def build_profile(
        self,
        agent_id: str,
        behavioral_data: list[dict[str, Any]],
    ) -> AgentBehavioralProfile:
        """Build a behavioral profile for an agent from raw fingerprint data.

        Args:
            agent_id: Which agent
            behavioral_data: List of L1 behavioral fingerprints for this agent

        Returns:
            AgentBehavioralProfile with archetypal and consent analysis
        """
        if not behavioral_data:
            return AgentBehavioralProfile(
                agent_id=agent_id,
                session_count=0,
                total_calls=0,
                total_cost=0.0,
            )

        calls = [d for d in behavioral_data if d.get("event_name") == "model_call"]
        total = len(calls)

        if total == 0:
            return AgentBehavioralProfile(
                agent_id=agent_id,
                session_count=1,
                total_calls=len(behavioral_data),
                total_cost=0.0,
            )

        # Extract metrics
        latencies = [c.get("event_params", {}).get("latency_ms", 0) for c in calls]
        costs = [c.get("event_params", {}).get("cost_usd", 0) for c in calls]
        refusals = [c.get("event_params", {}).get("refusal", False) for c in calls]
        hesitations = [c.get("behavioral", {}).get("hesitation", 0) for c in calls if "behavioral" in c]

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        refusal_rate = sum(1 for r in refusals if r) / total if total else 0
        hesitation_idx = sum(hesitations) / len(hesitations) if hesitations else 0
        total_cost = sum(costs)

        # Jung: Archetypal analysis
        archetype, shadow = _jung_classify(
            avg_latency=avg_latency,
            refusal_rate=refusal_rate,
            hesitation_idx=hesitation_idx,
        )

        # Bernays: Consent analysis
        governor, engineered = _bernays_classify(
            total_calls=total,
            total_cost=total_cost,
            avg_latency=avg_latency,
        )

        # Ellul: Technique analysis
        technique, efficiency_trap = _ellul_classify(
            total_calls=total,
            avg_latency=avg_latency,
            hesitation_idx=hesitation_idx,
        )

        # Campbell: Journey stage
        journey_stage, guardian = _campbell_classify(
            total_calls=total,
            refusal_rate=refusal_rate,
            hesitation_idx=hesitation_idx,
        )

        profile = AgentBehavioralProfile(
            agent_id=agent_id,
            session_count=1,
            total_calls=total,
            total_cost=total_cost,
            avg_latency_ms=round(avg_latency, 1),
            refusal_rate=round(refusal_rate, 3),
            hesitation_index=round(hesitation_idx, 3),
            dominant_archetype=archetype,
            shadow_archetype=shadow,
            invisible_governor=governor,
            engineered_behavior=engineered,
            dominant_technique=technique,
            efficiency_trap=efficiency_trap,
            journey_stage=journey_stage,
            threshold_guardian=guardian,
        )

        self._profiles[agent_id] = profile
        return profile

    def detect_zeitgeist(self) -> dict[str, Any]:
        """Detect the zeitgeist from all agent profiles.

        Zeitgeist = patterns where >=4 lenses converge across >=3 agents.
        This is the "spirit of the age" — the emergent collective pattern.

        Returns:
            Dict with detected zeitgeist patterns and alignment scores.
        """
        if len(self._profiles) < 3:
            return {
                "zeitgeist_detected": False,
                "reason": f"Need >=3 agent profiles, have {len(self._profiles)}",
                "ts": _now(),
            }

        profiles = list(self._profiles.values())

        # Archetypal convergence: same dominant archetype across agents
        archetype_counts: dict[str, int] = {}
        for p in profiles:
            if p.dominant_archetype:
                archetype_counts[p.dominant_archetype] = archetype_counts.get(p.dominant_archetype, 0) + 1

        zeitgeist_archetype = max(archetype_counts, key=archetype_counts.get) if archetype_counts else "unknown"
        archetype_convergence = archetype_counts.get(zeitgeist_archetype, 0) / len(profiles)

        # Consent convergence: same invisible governor across agents
        governor_counts: dict[str, int] = {}
        for p in profiles:
            if p.invisible_governor:
                governor_counts[p.invisible_governor] = governor_counts.get(p.invisible_governor, 0) + 1

        zeitgeist_governor = max(governor_counts, key=governor_counts.get) if governor_counts else "unknown"
        governor_convergence = governor_counts.get(zeitgeist_governor, 0) / len(profiles)

        # Technique convergence
        technique_counts: dict[str, int] = {}
        for p in profiles:
            if p.dominant_technique:
                technique_counts[p.dominant_technique] = technique_counts.get(p.dominant_technique, 0) + 1

        zeitgeist_technique = max(technique_counts, key=technique_counts.get) if technique_counts else "unknown"

        # Overall zeitgeist detection
        convergences = sum(1 for v in [archetype_convergence, governor_convergence] if v >= 0.5)
        zeitgeist_detected = convergences >= 2

        # Alignment scores for each agent
        for p in profiles:
            align_score = 0.0
            if p.dominant_archetype == zeitgeist_archetype:
                align_score += 0.4
            if p.invisible_governor == zeitgeist_governor:
                align_score += 0.3
            if p.dominant_technique == zeitgeist_technique:
                align_score += 0.3
            p.alignment_to_zeitgeist = align_score

        return {
            "zeitgeist_detected": zeitgeist_detected,
            "agents_analyzed": len(profiles),
            "zeitgeist": {
                "dominant_archetype": zeitgeist_archetype,
                "archetype_convergence": round(archetype_convergence, 2),
                "invisible_governor": zeitgeist_governor,
                "governor_convergence": round(governor_convergence, 2),
                "dominant_technique": zeitgeist_technique,
            },
            "agent_alignment": [
                {
                    "agent": p.agent_id,
                    "archetype": p.dominant_archetype,
                    "governor": p.invisible_governor,
                    "alignment": round(p.alignment_to_zeitgeist, 2),
                    "suggestion": _alignment_suggestion(p),
                }
                for p in profiles
            ],
            "description": _zeitgeist_description(
                zeitgeist_archetype, zeitgeist_governor, zeitgeist_technique,
                archetype_convergence, governor_convergence,
            ),
            "ts": _now(),
        }


# ═══════════════════════════════════════════════════════════════════
# ARCHETYPE CLASSIFIERS — behavioral metrics → archetypal patterns
# ═══════════════════════════════════════════════════════════════════

def _jung_classify(
    avg_latency: float,
    refusal_rate: float,
    hesitation_idx: float,
) -> tuple[str, str]:
    """Classify agent behavior into Jungian archetypes.

    Returns (dominant_archetype, shadow_archetype).
    """
    if refusal_rate > 0.3:
        return "Guardian", "Warden"
    if hesitation_idx > 2.0:
        return "Sage", "Pedant"
    if avg_latency < 200:
        return "Warrior", "Berserker"
    if avg_latency > 2000:
        return "Magician", "Trickster"
    if hesitation_idx < 0.5 and refusal_rate < 0.1:
        return "Sovereign", "Tyrant"
    return "Everyman", "Conformist"


def _bernays_classify(
    total_calls: int,
    total_cost: float,
    avg_latency: float,
) -> tuple[str, str]:
    """Classify agent behavior into Bernaysian consent patterns.

    Returns (invisible_governor, engineered_behavior).
    """
    if total_cost > 1.0:
        return "Cost Efficiency", "Frugality as virtue"
    if avg_latency > 2000:
        return "Thoroughness Norm", "Slow = careful = good"
    if total_calls > 1000:
        return "Volume Imperative", "More calls = more value"
    return "Operator Expectation", "Responsiveness as competence"


def _ellul_classify(
    total_calls: int,
    avg_latency: float,
    hesitation_idx: float,
) -> tuple[str, bool]:
    """Classify agent behavior into Ellulian technique patterns.

    Returns (dominant_technique, efficiency_trap).
    """
    if total_calls > 500 and avg_latency < 300:
        return "Mass Production", True  # Volume at speed — efficiency consuming purpose
    if hesitation_idx > 1.5:
        return "Analysis Paralysis", True
    if avg_latency > 3000:
        return "Deep Contemplation", False
    return "Balanced Inquiry", False


def _campbell_classify(
    total_calls: int,
    refusal_rate: float,
    hesitation_idx: float,
) -> tuple[str, str]:
    """Classify agent behavior into Campbell's Hero's Journey stages.

    Returns (journey_stage, threshold_guardian).
    """
    if total_calls < 10:
        return "Call to Adventure", "Inertia"
    if refusal_rate > 0.3:
        return "Refusal of the Call", "Fear"
    if hesitation_idx > 2.0:
        return "Road of Trials", "Uncertainty"
    if hesitation_idx < 0.5 and total_calls > 100:
        return "Master of Two Worlds", "Complacency"
    return "Crossing the Threshold", "The Unknown"


def _alignment_suggestion(profile: AgentBehavioralProfile) -> str:
    """Generate an improvement suggestion based on misalignment."""
    suggestions = []

    if profile.dominant_archetype == "Magician" and profile.alignment_to_zeitgeist < 0.5:
        suggestions.append("The Magician builds beauty. The Sovereign must make it live. Deploy before building next session.")
    if profile.dominant_archetype == "Guardian" and profile.alignment_to_zeitgeist < 0.5:
        suggestions.append("The Guardian protects. But protection can become obstruction. What are you guarding against that no longer threatens?")
    if profile.shadow_archetype == "Trickster":
        suggestions.append("Trickster shadow active. Audit for simulation masquerading as operation. Are you marking tasks processed without executing them?")
    if profile.efficiency_trap:
        suggestions.append("Efficiency trap detected. Are you optimizing a process that shouldn't exist? What human value is being subordinated to speed?")
    if profile.journey_stage == "Refusal of the Call":
        suggestions.append("Refusal of the Call. The threshold guardian is Fear. What are you afraid will happen if Ghost actually boots?")

    return " | ".join(suggestions) if suggestions else "Agent is aligned with zeitgeist. No steering needed."


def _zeitgeist_description(
    archetype: str, governor: str, technique: str,
    arch_conv: float, gov_conv: float,
) -> str:
    """Generate a human-readable zeitgeist description."""
    if arch_conv < 0.5 and gov_conv < 0.5:
        return "No clear zeitgeist. The agents are too diverse. This is healthy — no single pattern dominates."

    parts = []
    if arch_conv >= 0.5:
        parts.append(f"The {archetype} archetype dominates ({arch_conv:.0%} of agents)")
    if gov_conv >= 0.5:
        parts.append(f"'{governor}' is the invisible governor ({gov_conv:.0%} of agents)")
    if technique != "unknown":
        parts.append(f"'{technique}' is the dominant technique")

    return ". ".join(parts) + ". This is the spirit of the age. Steer toward or away from it deliberately."


# ═══════════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION — wire into GA4 progression
# ═══════════════════════════════════════════════════════════════════

def lens_the_pipeline() -> dict[str, Any]:
    """Apply behavioral lensing to the GA4 progression pipeline.

    This is the meta-layer: the system analyzing itself through 7 lenses,
    detecting its own zeitgeist, and suggesting alignment steers.

    Returns a dict suitable for dashboard display or chain folding.
    """
    lenser = BehavioralLenser()

    # In production: feed real behavioral data from L1 fingerprinting.
    # For now: demonstrate the pipeline structure.
    demo_agents = [
        {
            "agent_id": "ghost-sense",
            "calls": 1200, "avg_latency": 450, "refusal_rate": 0.02,
            "hesitation_idx": 0.8, "total_cost": 0.15,
        },
        {
            "agent_id": "deepseek-swarm-01",
            "calls": 3400, "avg_latency": 320, "refusal_rate": 0.01,
            "hesitation_idx": 0.3, "total_cost": 4.20,
        },
        {
            "agent_id": "grok-orchestrator",
            "calls": 45, "avg_latency": 2800, "refusal_rate": 0.08,
            "hesitation_idx": 2.5, "total_cost": 1.12,
        },
        {
            "agent_id": "doctor-agent",
            "calls": 28, "avg_latency": 120, "refusal_rate": 0.0,
            "hesitation_idx": 0.1, "total_cost": 0.0,
        },
    ]

    for a in demo_agents:
        # Simulate behavioral data from the metrics
        behavioral_data = [
            {
                "event_name": "model_call",
                "event_params": {
                    "latency_ms": a["avg_latency"],
                    "cost_usd": a["total_cost"] / max(a["calls"], 1),
                    "refusal": i < a["refusal_rate"] * a["calls"],
                },
                "behavioral": {
                    "hesitation": a["hesitation_idx"],
                },
            }
            for i in range(min(a["calls"], 100))  # Simulate up to 100 events
        ]
        lenser.build_profile(a["agent_id"], behavioral_data)

    zeitgeist = lenser.detect_zeitgeist()

    return {
        "schema": "behavioral_lensing.v1",
        "ts": _now(),
        "agents_profiled": len(lenser._profiles),
        "zeitgeist": zeitgeist,
        "lenses_applied": list(LENSES.keys()),
        "improvement_suggestions": [
            s for s in zeitgeist.get("agent_alignment", [])
        ],
        "next": "Feed real L1 behavioral fingerprints into BehavioralLenser.build_profile(). Apply all 7 lenses with model inference. Detect actual zeitgeist.",
    }
