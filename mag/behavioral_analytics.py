"""Ghost Behavioral Analytics — GA4-inspired minute-signal leak detection.

THE INSIGHT (operator):
  In early Google Analytics, you could pull IP → approximate street address.
  These were "leaks" — behavioral telemetry that revealed more than intended.
  Ghost's leak detector finds cryptographic leaks. But the REAL leaks are
  BEHAVIORAL — patterns in agent activity that reveal hidden information.

  Mnemonic AI tried to train deep learning models on behavioral data to detect
  these patterns. It was clumsy, but the idea was correct: behavioral signals
  carry information that the actors don't know they're revealing.

GA4 → VERKLE MAPPING:
  GA4 event_name       → Verkle knot type (task_completed, steer_injected, leak_detected)
  GA4 event_params     → scalar_knot fields (theme_vector, tension_index, duration)
  GA4 user_properties  → agent identity (agent_id, provider, model, role)
  GA4 geo (IP→street)  → lattice topology (which node/session produced the knot)
  GA4 session          → Q-session (grouped related events)
  GA4 scroll_depth     → tension_index (how deep did the agent engage?)
  GA4 traffic_source   → copilot inbox source field (where did the task come from?)
  GA4 conversion       → steer success (silence < 0.3 = agent adopted the steer)

BEHAVIORAL LEAK DETECTION:
  Same patterns that GA4 uses to predict user behavior, Ghost uses to detect
  information leakage. The "minute signals" — micro-patterns in timing, theme
  choice, provider selection — reveal more than the actors intend.

  Example: an agent that switches from ollama→deepseek mid-session, has tension
  above 0.7, and writes knots with theme "mirror_meta" at 3x the normal rate
  is 5x more likely to be exfiltrating data than baseline.

Schema: behavioral_analytics.v1
Reference: GA4 event model, mnemonic AI history, Ghost leak detector
"""

from __future__ import annotations

import json
import math
from mag.chain_query import chain  # auto-added by doctor_agent
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Paths ──
VERKLE_CHAIN = ROOT / "memory" / "biography" / "# CHAIN_QUERY_MIGRATION_NEEDED: replace with chain.tail() or chain.by_type()"
BEHAVIORAL_DIR = ROOT / "memory" / "ghost" / "behavioral"
BEHAVIORAL_LOG = BEHAVIORAL_DIR / "signals.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, tail: int = 500) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════════
# BEHAVIORAL SIGNAL EXTRACTION (GA4 → Verkle)
# ═══════════════════════════════════════════════════════════════════

def extract_behavioral_signals() -> list[dict[str, Any]]:
    """Extract GA4-style behavioral signals from the Verkle chain.

    Each Verkle knot becomes a behavioral "event" with:
    - event_name: mapped from dominant_theme + session_id prefix
    - event_params: scalar_knot fields as key-value pairs
    - user_properties: agent/session metadata
    - geo_equivalent: which part of the lattice (node type)
    - traffic_source: where the event originated
    """
    knots = _read_jsonl(VERKLE_CHAIN, tail=200)
    signals = []

    for k in knots:
        sid = k.get("session_id", "")
        theme = k.get("dominant_theme", "") or ""
        scalar = k.get("scalar_knot", {}) if isinstance(k.get("scalar_knot"), dict) else {}
        tension = k.get("tension_index", 0)
        ts = k.get("ts", "")

        # Determine event_name (GA4 equivalent)
        if sid.startswith("q-knot-"):
            event_name = "steer_injected"
        elif sid.startswith("swarm-"):
            event_name = "swarm_event"
        elif sid.startswith("autonomous-"):
            event_name = "autonomous_action"
        elif sid.startswith("freeze-"):
            event_name = "context_frozen"
        elif sid.startswith("mag-agent-"):
            event_name = "agent_task"
        elif sid.startswith("quantum-"):
            event_name = "state_quantized"
        elif theme:
            event_name = f"theme_{theme}"
        else:
            event_name = "system_event"

        # Determine source (GA4 traffic_source equivalent)
        source = "unknown"
        if "orc-" in sid:
            source = "orchestrator"
        elif "agent-" in sid:
            source = "agent"
        elif "mag-" in sid:
            source = "mag_hands"
        elif "mirror" in sid.lower():
            source = "mirror_reflection"
        elif "bio" in sid.lower():
            source = "biographer"

        # Determine node_type (GA4 geo equivalent)
        node_type = "verkle_knot"
        if sid.startswith("q-"):
            node_type = "q_session"
        elif sid.startswith("swarm-"):
            node_type = "swarm_node"

        signal = {
            "event_name": event_name,
            "event_params": {
                "theme": theme,
                "tension": tension,
                "duration_minutes": scalar.get("duration_minutes", 0) if isinstance(scalar, dict) else 0,
                "residual_weight": scalar.get("residual_weight", 0) if isinstance(scalar, dict) else 0,
            },
            "user_properties": {
                "session_id": sid[:40],
                "node_type": node_type,
                "verkle_root": k.get("verkle_root", "")[:16],
            },
            "traffic_source": source,
            "ts": ts,
        }
        signals.append(signal)

    return signals


# ═══════════════════════════════════════════════════════════════════
# MINUTE SIGNAL PATTERN DETECTION
# ═══════════════════════════════════════════════════════════════════

def analyze_minute_signals() -> dict[str, Any]:
    """Analyze behavioral signals for patterns that leak hidden information.

    Like GA4 detecting that "users from Chicago on Chrome at 3am convert 3x more,"
    Ghost detects that "agents with tension > 0.7 using deepseek after a Q-steer
    are 5x more likely to produce anomalous behavior."

    Returns a behavioral analytics report with:
    - event_distribution: which event types occur most
    - source_breakdown: which traffic sources dominate
    - temporal_patterns: time-of-day behavioral shifts
    - tension_correlation: what events correlate with high tension
    - anomaly_score: overall system behavioral anomaly
    """
    signals = extract_behavioral_signals()
    if not signals:
        return {"signals": 0, "note": "No behavioral signals to analyze"}

    # Event distribution
    event_counts = Counter(s["event_name"] for s in signals)

    # Source breakdown
    source_counts = Counter(s["traffic_source"] for s in signals)

    # Tension correlation: which event types have highest avg tension
    tension_by_event: dict[str, list[float]] = defaultdict(list)
    for s in signals:
        t = s["event_params"]["tension"]
        if isinstance(t, (int, float)) and t > 0:
            tension_by_event[s["event_name"]].append(float(t))

    avg_tension = {
        event: round(sum(vals) / len(vals), 3)
        for event, vals in tension_by_event.items()
        if vals
    }
    high_tension_events = sorted(
        [(e, t) for e, t in avg_tension.items() if t > 0.5],
        key=lambda x: x[1], reverse=True,
    )[:5]

    # Temporal pattern: event frequency by hour (if timestamps available)
    hour_distribution: dict[int, int] = defaultdict(int)
    for s in signals:
        ts = s["ts"]
        if ts:
            try:
                hour = datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
                hour_distribution[hour] += 1
            except (ValueError, TypeError):
                pass

    # Anomaly score: entropy of event distribution (higher = more uniform = more chaotic)
    total = len(signals)
    entropy = 0.0
    for count in event_counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    max_entropy = math.log2(len(event_counts)) if event_counts else 1
    anomaly_score = round(entropy / max_entropy, 3) if max_entropy > 0 else 0.0

    # Source-theme cross-tabulation: which sources produce which themes
    source_theme: dict[str, Counter] = defaultdict(Counter)
    for s in signals:
        source_theme[s["traffic_source"]][s["event_params"]["theme"]] += 1

    # Detect "leaky" patterns: source+theme combos that appear disproportionately
    leaky_patterns = []
    for source, themes in source_theme.items():
        total_source = sum(themes.values())
        for theme, count in themes.most_common(3):
            if total_source > 5 and count / total_source > 0.4:
                # This theme dominates this source — potential behavioral fingerprint
                leaky_patterns.append({
                    "source": source,
                    "theme": theme,
                    "count": count,
                    "pct": round(count / total_source * 100, 1),
                    "interpretation": f"'{theme}' dominates '{source}' at {round(count/total_source*100)}% — behavioral fingerprint",
                })

    report = {
        "schema": "behavioral_analytics.v1",
        "ts": _now(),
        "total_signals": len(signals),
        "event_distribution": dict(event_counts.most_common(10)),
        "source_breakdown": dict(source_counts.most_common(10)),
        "high_tension_events": high_tension_events,
        "hour_distribution": dict(sorted(hour_distribution.items())),
        "anomaly_score": anomaly_score,
        "anomaly_interpretation": (
            "HIGH — diverse event patterns, possible information leakage"
            if anomaly_score > 0.8
            else "MODERATE — typical behavioral variation"
            if anomaly_score > 0.5
            else "LOW — behavioral patterns are concentrated and predictable"
        ),
        "leaky_patterns": leaky_patterns,
        "note": (
            "GA4-style behavioral analytics applied to Verkle lattice. "
            "Every knot is an event. Every event leaks information. "
            "The question is: what do the minute signals reveal that the actors don't know they're revealing?"
        ),
    }

    # Log the analysis
    _append_jsonl(BEHAVIORAL_LOG, report)

    return report


# ═══════════════════════════════════════════════════════════════════
# AGENT BEHAVIORAL FINGERPRINT
# ═══════════════════════════════════════════════════════════════════

def fingerprint_agent(agent_id: str) -> dict[str, Any]:
    """Build a behavioral fingerprint for a specific agent.

    Like GA4 user analytics, this profiles an agent's behavior patterns
    to detect deviations that might indicate compromise or data exfiltration.
    """
    signals = extract_behavioral_signals()
    agent_signals = [s for s in signals if agent_id in s["user_properties"]["session_id"]]

    if not agent_signals:
        return {"agent_id": agent_id, "signals": 0, "note": "No behavioral data"}

    events = Counter(s["event_name"] for s in agent_signals)
    tensions = [s["event_params"]["tension"] for s in agent_signals
                if isinstance(s["event_params"]["tension"], (int, float))]
    avg_tension = round(sum(tensions) / len(tensions), 3) if tensions else 0.0

    return {
        "agent_id": agent_id,
        "total_events": len(agent_signals),
        "event_signature": dict(events.most_common(5)),
        "avg_tension": avg_tension,
        "behavioral_anomaly": (
            "HIGH — agent behavior deviates from system baseline"
            if avg_tension > 0.6
            else "NORMAL — agent behavior within expected range"
        ),
    }
