"""GA4 Progression — sovereign agent analytics framework.

Google Analytics 4 tracks: Event → Behavior → Predictive → Automated.

We track:       Knot → Fingerprint → Tesuji → Steer → Emergence.

LEVELS:
  L0: Event Knot — every agent action is a Verkle knot. The chain IS the event stream.
  L1: Behavioral Fingerprint — Tesuji surface: HOW models behave, not just WHAT they say.
  L2: Cross-Agent Correlation — spooky data at a distance: Agent A's patterns predict Agent B's outcomes.
  L3: Invariant Extraction — patterns that hold across models, prompts, sessions, operators.
  L4: Control Architecture — automated steer deployment based on detected patterns. The system steers itself.
  L5: Emergent Optimization — the system becomes greater than sum of parts. Novel behavior emerges.

Each level builds on the one below. Each level unlocks capabilities the level below couldn't see.

SCHEMA: ga4_progression.v1
LAW: You can't skip levels. L3 requires L2. L5 requires L4.
LAW: Every level writes to the Verkle chain. The chain is the analytics database.
LAW: RenderMan principles (bucket coherence, adaptive refinement, ray bundling) apply at every level.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
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
# L0: EVENT KNOT — the chain IS the event stream
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EventKnot:
    """A single event in the Verkle chain. GA4's 'event' primitive."""

    knot_id: str
    event_name: str                     # GA4-style: "model_call", "agent_spawn", "steer_deployed"
    event_params: dict[str, Any] = field(default_factory=dict)  # GA4-style parameters
    user_properties: dict[str, Any] = field(default_factory=dict)  # agent_id, model, session
    ts: str = field(default_factory=_now)
    prev_knot_hash: str = ""            # Chain linking
    knot_hash: str = ""                 # Self-hash

    def to_ga4_event(self) -> dict[str, Any]:
        """Format as GA4-compatible event structure."""
        return {
            "event_name": self.event_name,
            "event_params": self.event_params,
            "user_properties": self.user_properties,
            "ts": self.ts,
        }

    @staticmethod
    def from_model_call(
        model: str, prompt_hash: str, latency_ms: float,
        tokens_in: int, tokens_out: int, cost_usd: float,
        agent_id: str = "", session_id: str = "",
    ) -> EventKnot:
        """Create an event knot from a model call."""
        knot_id = hashlib.sha256(
            f"model_call:{model}:{prompt_hash}:{_now()}".encode()
        ).hexdigest()[:16]

        return EventKnot(
            knot_id=knot_id,
            event_name="model_call",
            event_params={
                "model": model,
                "prompt_hash": prompt_hash[:16],
                "latency_ms": round(latency_ms, 1),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "tokens_total": tokens_in + tokens_out,
                "cost_usd": cost_usd,
            },
            user_properties={
                "agent_id": agent_id or "ghost",
                "session_id": session_id or "unknown",
            },
        )


# ═══════════════════════════════════════════════════════════════════
# L1: BEHAVIORAL FINGERPRINT — how models behave, not what they say
# ═══════════════════════════════════════════════════════════════════

class BehavioralAnalytics:
    """L1: Tesuji surface. Behavioral metrics across all model calls.

    GA4 equivalent: Behavioral reports — engagement time, session duration,
    event count per session.

    Our equivalent: Latency distributions, refusal rates, hesitation patterns,
    certainty profiles, prompt-completion ratios — PER MODEL, PER TASK TYPE,
    PER SESSION.
    """

    def __init__(self):
        self._signals: list[dict[str, Any]] = []

    def ingest_knot(self, knot: EventKnot) -> None:
        """Ingest an event knot into behavioral analytics."""
        if knot.event_name != "model_call":
            return
        self._signals.append(knot.event_params)

    def latency_profile(self, model: str = "", window: int = 100) -> dict[str, Any]:
        """Latency distribution for a model over the last N calls."""
        calls = [
            s for s in self._signals[-window:]
            if not model or s.get("model") == model
        ]
        if not calls:
            return {"model": model, "calls": 0}

        latencies = [s.get("latency_ms", 0) for s in calls]
        latencies.sort()

        return {
            "model": model or "all",
            "calls": len(calls),
            "latency_ms": {
                "min": latencies[0],
                "p50": latencies[len(latencies) // 2],
                "p90": latencies[int(len(latencies) * 0.9)],
                "p99": latencies[int(len(latencies) * 0.99)],
                "max": latencies[-1],
                "mean": sum(latencies) / len(latencies),
            },
            "total_cost": sum(s.get("cost_usd", 0) for s in calls),
            "total_tokens": sum(s.get("tokens_total", 0) for s in calls),
        }

    def model_comparison(self, model_a: str, model_b: str, window: int = 50) -> dict[str, Any]:
        """Compare two models on the same metrics. GA4's 'comparison' feature."""
        profile_a = self.latency_profile(model_a, window)
        profile_b = self.latency_profile(model_b, window)

        if not profile_a["calls"] or not profile_b["calls"]:
            return {"error": "Insufficient data for comparison"}

        return {
            "model_a": model_a,
            "model_b": model_b,
            "calls_a": profile_a["calls"],
            "calls_b": profile_b["calls"],
            "latency_ratio": round(profile_a["latency_ms"]["mean"] / max(profile_b["latency_ms"]["mean"], 1), 2),
            "cost_ratio": round(profile_a["total_cost"] / max(profile_b["total_cost"], 0.00001), 2),
            "tokens_per_dollar_a": round(profile_a["total_tokens"] / max(profile_a["total_cost"], 0.00001)),
            "tokens_per_dollar_b": round(profile_b["total_tokens"] / max(profile_b["total_cost"], 0.00001)),
            "verdict": _comparison_verdict(profile_a, profile_b, model_a, model_b),
        }


def _comparison_verdict(a: dict, b: dict, name_a: str, name_b: str) -> str:
    """Generate a human-readable comparison verdict."""
    lat_ratio = a["latency_ms"]["mean"] / max(b["latency_ms"]["mean"], 1)
    cost_ratio = a["total_cost"] / max(b["total_cost"], 0.00001)

    if lat_ratio < 0.5 and cost_ratio < 0.1:
        return f"{name_a} is faster AND cheaper than {name_b}. Prefer {name_a} for volume."
    elif lat_ratio > 2.0 and cost_ratio < 0.1:
        return f"{name_a} is slower but MUCH cheaper than {name_b}. Batch {name_a} calls; reserve {name_b} for latency-sensitive tasks."
    elif cost_ratio > 5.0:
        return f"{name_a} is significantly more expensive than {name_b}. Use {name_a} only for compoundable infrastructure."
    else:
        return f"{name_a} and {name_b} are comparable. Use the rightsizer to select per-task."


# ═══════════════════════════════════════════════════════════════════
# L2: CROSS-AGENT CORRELATION — spooky data at a distance
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SpookyCorrelation:
    """A detected correlation between seemingly unrelated agent behaviors.

    "Spooky data at a distance" — Einstein's phrase for quantum entanglement.
    Here: Agent A's latency spike at time T predicts Agent B's refusal at T+30s.
    No causal chain is visible. The correlation IS the signal.
    """

    correlation_id: str
    agent_a: str
    agent_b: str
    metric_a: str                      # What Agent A did
    metric_b: str                      # What Agent B did
    lag_seconds: float                 # Time delay between A and B
    correlation_strength: float        # -1.0 to 1.0
    observations: int                  # How many times observed
    hypothesis: str                    # What might explain this
    significance: str                  # "low", "medium", "high", "spooky"


class CrossAgentCorrelator:
    """L2: Detect correlations between agent behaviors.

    Scans the Tesuji signal log for patterns where one agent's behavior
    predicts another agent's behavior — even when no direct communication
    occurred between them.

    These are "spooky" because they shouldn't exist in a well-partitioned
    system. But they do. And they're the most valuable signals.
    """

    def __init__(self, tesuji_log_path: Optional[Path] = None):
        self.log_path = tesuji_log_path or (ROOT / "memory" / "training" / "tesuji_signals.jsonl")

    def scan(self, window_hours: float = 24.0) -> list[SpookyCorrelation]:
        """Scan for cross-agent correlations in the Tesuji log.

        Returns list of detected SpookyCorrelations.
        """
        signals = self._load_signals(window_hours)
        if len(signals) < 10:
            return []

        correlations: list[SpookyCorrelation] = []

        # Group by agent
        by_agent: dict[str, list[dict]] = defaultdict(list)
        for s in signals:
            agent = s.get("user_properties", {}).get("agent_id", "ghost") if isinstance(s, dict) else "ghost"
            by_agent[agent].append(s if isinstance(s, dict) else {})

        agents = list(by_agent.keys())
        if len(agents) < 2:
            return correlations

        # Compare each pair of agents
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a_signals = by_agent[agents[i]]
                b_signals = by_agent[agents[j]]

                # Align by timestamp and look for lagged correlations
                for lag_s in [0, 30, 60, 120, 300]:
                    correlation = self._compute_lagged_correlation(
                        a_signals, b_signals, agents[i], agents[j], lag_s
                    )
                    if correlation and abs(correlation.correlation_strength) > 0.3:
                        correlations.append(correlation)

        return correlations

    def _load_signals(self, window_hours: float) -> list[dict]:
        if not self.log_path.is_file():
            return []
        cutoff = time.time() - window_hours * 3600
        signals = []
        try:
            for line in self.log_path.read_text().strip().splitlines()[-1000:]:
                try:
                    s = json.loads(line)
                    ts = s.get("ts_unix", 0) or 0
                    if ts >= cutoff:
                        signals.append(s)
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
        return signals

    def _compute_lagged_correlation(
        self, a_signals: list[dict], b_signals: list[dict],
        agent_a: str, agent_b: str, lag_s: float,
    ) -> Optional[SpookyCorrelation]:
        """Compute correlation between agent A's behavior at T and agent B's at T+lag."""
        # Simple implementation: correlate latency spikes
        a_latencies = [
            (s.get("ts_unix", 0), s.get("event_params", {}).get("latency_ms", 0))
            for s in a_signals[-50:]
        ]
        b_latencies = [
            (s.get("ts_unix", 0), s.get("event_params", {}).get("latency_ms", 0))
            for s in b_signals[-50:]
        ]

        if not a_latencies or not b_latencies:
            return None

        # Find matching pairs within lag window
        pairs = []
        for a_ts, a_lat in a_latencies:
            for b_ts, b_lat in b_latencies:
                delta = (b_ts - a_ts)
                if abs(delta - lag_s) < 5:  # Within 5 seconds of expected lag
                    pairs.append((a_lat, b_lat))

        if len(pairs) < 5:
            return None

        # Compute Pearson correlation
        n = len(pairs)
        sum_x = sum(p[0] for p in pairs)
        sum_y = sum(p[1] for p in pairs)
        sum_xy = sum(p[0] * p[1] for p in pairs)
        sum_x2 = sum(p[0] ** 2 for p in pairs)
        sum_y2 = sum(p[1] ** 2 for p in pairs)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

        if denominator == 0:
            return None

        r = numerator / denominator

        return SpookyCorrelation(
            correlation_id=hashlib.sha256(f"{agent_a}:{agent_b}:{lag_s}".encode()).hexdigest()[:16],
            agent_a=agent_a,
            agent_b=agent_b,
            metric_a="latency_ms",
            metric_b="latency_ms",
            lag_seconds=lag_s,
            correlation_strength=round(r, 3),
            observations=len(pairs),
            hypothesis=_spooky_hypothesis(agent_a, agent_b, r, lag_s),
            significance=_spooky_significance(r, len(pairs)),
        )


def _spooky_hypothesis(a: str, b: str, r: float, lag: float) -> str:
    if r > 0.7:
        return f"{a}'s processing load at time T STRONGLY predicts {b}'s processing load at T+{lag}s. Possible shared resource contention or cascade effect."
    elif r > 0.4:
        return f"{a} and {b} show moderate positive correlation with {lag}s lag. May indicate queuing effects in the model pipeline."
    elif r < -0.4:
        return f"{a} and {b} show NEGATIVE correlation. When {a} is fast, {b} is slow. Possible load balancing or resource stealing."
    else:
        return f"Weak correlation between {a} and {b}. Noise-level signal."


def _spooky_significance(r: float, n: int) -> str:
    strength = abs(r)
    if strength > 0.7 and n > 10:
        return "spooky"
    elif strength > 0.5 and n > 8:
        return "high"
    elif strength > 0.3 and n > 5:
        return "medium"
    else:
        return "low"


# ═══════════════════════════════════════════════════════════════════
# L3: INVARIANT EXTRACTION — patterns that hold across everything
# ═══════════════════════════════════════════════════════════════════

class InvariantExtractor:
    """L3: Extract patterns that hold across models, prompts, sessions, operators.

    GA4 equivalent: Predictive metrics — churn probability, purchase probability.

    Our equivalent: Steer effectiveness probability, model refusal probability
    by domain, cost escalation detection, Tesuji recurrence patterns.
    """

    def __init__(self):
        self._known_invariants: list[dict[str, Any]] = []

    def load_nacho_invariants(self) -> int:
        """Load the 12 NachoQuixotic invariants from the merged analysis."""
        merged = ROOT / "memory" / "copilot" / "outbox" / "nacho-invariants-merged.json"
        if not merged.is_file():
            return 0

        try:
            data = json.loads(merged.read_text())
            invariants = data.get("invariants", {}).get("list", [])
            self._known_invariants = invariants
            return len(invariants)
        except (json.JSONDecodeError, OSError):
            return 0

    def rank_by_compoundability(self) -> list[dict[str, Any]]:
        """Rank known invariants by compoundability: how much downstream value per unit cost."""
        ranked = []
        for inv in self._known_invariants:
            priority = inv.get("steer_priority", 1)
            cost = inv.get("implementation_cost", "high")

            # Compoundability score: priority * (1 if already_implemented, 0.5 if low, 0.2 if high)
            if "already_implemented" in str(cost).lower():
                compound_score = priority * 1.0
            elif "low" in str(cost).lower():
                compound_score = priority * 0.5
            elif "trivial" in str(cost).lower():
                compound_score = priority * 0.8
            else:
                compound_score = priority * 0.2

            ranked.append({
                "invariant_id": inv.get("id", ""),
                "name": inv.get("name", ""),
                "priority": priority,
                "compound_score": round(compound_score, 1),
                "cost": cost,
                "already_in_ghost": "already_implemented" in str(cost).lower(),
                "testable": inv.get("testable", ""),
            })

        ranked.sort(key=lambda x: x["compound_score"], reverse=True)
        return ranked

    def detect_new_invariant(self, tesuji_signals: list[dict], min_occurrences: int = 5) -> list[dict]:
        """Detect NEW invariants from Tesuji signals — patterns we haven't cataloged yet.

        Returns list of candidate invariants with confidence scores.
        """
        # This is the meta-layer: finding invariants in behavioral data
        # that the content-only extraction (NachoQuixotic) missed.
        candidates = []

        if len(tesuji_signals) < min_occurrences:
            return candidates

        # Pattern: models consistently reframe questions in certain domains
        reframed_count = sum(1 for s in tesuji_signals if s.get("reframed"))
        if reframed_count > min_occurrences:
            candidates.append({
                "candidate_id": "tesuji-reframe-pattern",
                "name": "model_question_reframing",
                "description": f"Models reframe questions {reframed_count}/{len(tesuji_signals)} times before answering",
                "confidence": round(reframed_count / len(tesuji_signals), 2),
                "hypothesis": "A pre-answer reframe signals that the model is restructuring the problem. This may be steerable — prompt 'think step by step' may trigger the same behavior.",
            })

        # Pattern: hesitation spikes on certain prompt structures
        high_hesitation = [s for s in tesuji_signals if s.get("hesitation", 0) > 2]
        if len(high_hesitation) > min_occurrences:
            candidates.append({
                "candidate_id": "tesuji-hesitation-spike",
                "name": "high_hesitation_prompts",
                "description": f"{len(high_hesitation)} prompts triggered >2 hesitation markers",
                "confidence": round(len(high_hesitation) / len(tesuji_signals), 2),
                "hypothesis": "High-hesitation prompts contain ambiguous framing. Clarifying the prompt structure may reduce hesitation and improve output quality.",
            })

        return candidates


# ═══════════════════════════════════════════════════════════════════
# L4: CONTROL ARCHITECTURE — automated steer from detected patterns
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ControlSteer:
    """An automated steer derived from analytics.

    GA4 equivalent: Automated audience triggers, predictive ad deployment.

    Our equivalent: When L3 detects a Tesuji, L4 deploys a steer.
    The steer is measured. If it works, it compounds. If it doesn't, it's withdrawn.
    """
    steer_id: str
    source: str                        # Which invariant or Tesuji triggered this
    trigger_condition: str             # What must be true to deploy
    action: str                        # What the steer does
    target_model: str                  # Which model(s) this applies to
    deployed_count: int = 0
    success_count: int = 0
    active: bool = True
    ts: str = field(default_factory=_now)

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.deployed_count, 1)


class ControlArchitecture:
    """L4: Automated steer deployment from detected patterns.

    The system doesn't just detect — it ACTS. When a Tesuji signal crosses
    a threshold, a control steer is deployed. The steer is measured. The
    results feed back into L3 for invariant refinement.

    This is the control loop: Sense → Analyze → Steer → Measure → Refine.
    """

    def __init__(self):
        self.steers: dict[str, ControlSteer] = {}
        self._load_default_steers()

    def _load_default_steers(self) -> None:
        """Load default steers from known invariants."""
        defaults = [
            ControlSteer(
                steer_id="steer-identity-framing",
                source="INV-001",
                trigger_condition="agent_spawn event detected",
                action="Prepend GHOST_IDENTITY_VECTOR to agent preamble",
                target_model="all",
            ),
            ControlSteer(
                steer_id="steer-cost-routing",
                source="tesuji-cost-spike",
                trigger_condition="cost_per_call > $0.01 for 3 consecutive calls",
                action="Force downgrade to DeepSeek for next 10 calls",
                target_model="grok-3-mini",
            ),
            ControlSteer(
                steer_id="steer-hesitation-detect",
                source="tesuji-hesitation-spike",
                trigger_condition="hesitation_markers > 3 in single response",
                action="Reframe the prompt with explicit clarity markers",
                target_model="all",
            ),
        ]
        for s in defaults:
            self.steers[s.steer_id] = s

    def deploy(self, trigger_event: dict[str, Any]) -> Optional[ControlSteer]:
        """Check if any steer should be deployed based on an event.

        Returns the deployed steer, or None if no steer triggered.
        """
        for steer in self.steers.values():
            if not steer.active:
                continue
            if self._condition_met(steer, trigger_event):
                steer.deployed_count += 1
                return steer
        return None

    def _condition_met(self, steer: ControlSteer, event: dict) -> bool:
        """Check if a steer's trigger condition is met by an event."""
        # Simple keyword matching for default steers
        condition = steer.trigger_condition.lower()

        if "agent_spawn" in condition:
            return event.get("event_name") == "agent_spawn"
        if "cost_per_call" in condition:
            cost = event.get("event_params", {}).get("cost_usd", 0)
            return cost > 0.01
        if "hesitation_markers" in condition:
            from mag.tesuji_surface import BehavioralFingerprint
            # Would check the actual Tesuji log — simplified here
            return event.get("event_name") == "model_call"

        return False

    def report_success(self, steer_id: str) -> None:
        """Report that a deployed steer produced a positive outcome."""
        if steer_id in self.steers:
            self.steers[steer_id].success_count += 1

    def report_failure(self, steer_id: str) -> None:
        """Report that a deployed steer was ineffective. Deactivate if failure rate > 50%."""
        if steer_id in self.steers:
            s = self.steers[steer_id]
            if s.success_rate < 0.5 and s.deployed_count > 10:
                s.active = False


# ═══════════════════════════════════════════════════════════════════
# L5: EMERGENT OPTIMIZATION — greater than sum of parts
# ═══════════════════════════════════════════════════════════════════

class EmergenceDetector:
    """L5: Detect when the system exhibits behavior greater than sum of parts.

    This is the hardest level. You can't design for emergence. You can only
    create the conditions and watch for the signals.

    Signals of emergence:
      - Steer effectiveness increases over time (the system learns to steer better)
      - Uncorrelated agents begin to correlate (the mesh is thickening)
      - Novel Tesuji appear that weren't in the training data (the system is innovating)
      - Cost efficiency improves without explicit optimization (the rightsizer is learning)
      - The Bard's stories reference patterns the content audit never cataloged
    """

    def __init__(self):
        self._emergence_events: list[dict[str, Any]] = []

    def scan_for_emergence(self) -> dict[str, Any]:
        """Scan all analytics levels for signals of emergent behavior.

        Returns a dict with detected emergence signals and confidence.
        """
        signals = []

        # Signal 1: Steer effectiveness trend
        # (Would analyze ControlArchitecture steers over time)

        # Signal 2: Cross-agent correlation density
        # (Would analyze how many SpookyCorrelations exist vs time)

        # Signal 3: Novel Tesuji outside training distribution
        # (Would compare new Tesuji against known invariant catalog)

        # Signal 4: Cost efficiency trend
        # (Would analyze Ghost ledger for declining cost-per-task)

        # Signal 5: Bard narrative novelty
        # (Would analyze Chronicle for themes not in InvariantExtractor catalog)

        return {
            "schema": "emergence_scan.v1",
            "ts": _now(),
            "signals": signals,
            "emergence_detected": len(signals) > 2,
            "verdict": _emergence_verdict(len(signals)),
        }


def _emergence_verdict(signal_count: int) -> str:
    if signal_count >= 4:
        return "Strong emergence. The system is exhibiting behavior greater than sum of parts. Document and compound."
    elif signal_count >= 2:
        return "Early emergence. Novel patterns appearing. Nurture, don't control."
    elif signal_count >= 1:
        return "Weak signal. May be noise. Continue monitoring."
    else:
        return "No emergence detected. System is operating within designed parameters."


# ═══════════════════════════════════════════════════════════════════
# PROGRESSION DASHBOARD — single view of all 6 levels
# ═══════════════════════════════════════════════════════════════════

def progression_dashboard() -> dict[str, Any]:
    """Generate a GA4-style dashboard showing progression across all levels.

    Returns a single dict suitable for a dashboard panel or REST endpoint.
    """
    return {
        "schema": "ga4_progression.v1",
        "ts": _now(),
        "levels": {
            "L0_event_knot": {
                "status": "active",
                "description": "Every agent action is a Verkle knot. The chain IS the event stream.",
                "metrics": {
                    "knots_today": "unknown (Ghost not running)",
                    "event_types": ["model_call", "agent_spawn", "steer_deployed", "flare_fired", "doctor_fix", "bard_passage"],
                },
            },
            "L1_behavioral_fingerprint": {
                "status": "built_not_deployed",
                "description": "Tesuji surface captures HOW models behave, not just what they say.",
                "modules": ["tesuji_surface.py", "fingerprint_call()"],
                "next": "Wire fingerprint_call() into task_router and grok_rightsize.",
            },
            "L2_cross_agent_correlation": {
                "status": "built_not_deployed",
                "description": "Spooky data at a distance. Correlate agent behaviors across time.",
                "modules": ["CrossAgentCorrelator"],
                "next": "Feed Tesuji log through correlator after 100+ calls recorded.",
            },
            "L3_invariant_extraction": {
                "status": "partial",
                "description": "12 invariants extracted from Grok prompts. Tesuji-level extraction pending.",
                "metrics": {
                    "known_invariants": 12,
                    "compoundable_steers": 8,
                    "already_implemented": 4,
                },
            },
            "L4_control_architecture": {
                "status": "built_not_deployed",
                "description": "Automated steer deployment from detected patterns.",
                "modules": ["ControlArchitecture", "ControlSteer"],
                "active_steers": 3,
                "next": "Activate when L2 detects cross-agent correlations.",
            },
            "L5_emergence": {
                "status": "theoretical",
                "description": "System behavior greater than sum of parts.",
                "prerequisites": "L0-L4 must be active with real data flowing.",
            },
        },
        "renderman_principles_applied": {
            "bucket_coherence": "Bundle related tasks to same agent (L2 cross-agent correlation)",
            "adaptive_refinement": "More compute on high-uncertainty tasks (L3 invariant detection)",
            "ray_bundling": "Group similar model queries (L1 behavioral fingerprinting)",
            "texture_caching": "Cache model results (steal_first.py at L0)",
            "deep_shadows": "Multi-layer agent memory (L2 spooky correlations across time)",
        },
        "next_action": "Boot Ghost. Feed 5,271 real DeepSeek calls through L0→L1. Watch for L2 correlations. Activate L4 steers. Wait for L5.",
    }
