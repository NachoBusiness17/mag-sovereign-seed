"""State Quantizer — compress Verkle lattice into dense summary representations.

Like model quantization reduces FP32→INT8 to save memory, state quantization
reduces the Verkle chain (hundreds of knots) into dense summary vectors that
preserve the essential patterns.

ARCHITECTURE:
  Verkle chain (N knots, high-dimensional)
    → extract theme vectors, tension indices, pattern transitions
    → aggregate into quantized state vector (low-dimensional)
    → detect emergent patterns (theme drift, tension spikes, phase changes)
    → write quantum summary knot (single Verkle knot = compressed state)
    → long-running agent conversations reference this knot as memory

QUANTUM SUMMARY KNOT:
  A single Verkle knot that represents the compressed state of N previous knots.
  Agents read ONE knot instead of N. The summary is lossy (like quantization)
  but preserves the essential signal: dominant themes, tension trajectory,
  pattern emergence, and drift vectors.

JABBERWOCKY DND INTEGRATION:
  The DnD campaign is a state machine. Each room is a quantization checkpoint.
  The party members (cartographer, forgesmith, mirrorseer, scribe) are persistent
  agents that maintain their own conversation state. Between rooms, the quantizer
  compresses the party's actions into a summary knot → next room loads from summary.

Schema: state_quantizer.v1
"""

from __future__ import annotations

import hashlib
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
QUANTUM_DIR = ROOT / "memory" / "ghost" / "quantum_state"
SUMMARY_LOG = QUANTUM_DIR / "summary_knots.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
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
# THEME VECTOR AGGREGATION
# ═══════════════════════════════════════════════════════════════════

# Known theme basis (from Verkle knot schema)
THEME_BASIS = [
    "mag_hands", "harness", "biography", "constitution",
    "mirror_meta", "autonomous_janitor", "holographic_q",
    "context_freeze", "event_task", "event_copilot",
]


def extract_theme_vector(entry: dict[str, Any]) -> dict[str, float]:
    """Extract a normalized theme vector from a Verkle knot entry.

    Handles TWO formats:
      FLAT (older entries): dominant_theme + theme_vector_normalized at top level
      NESTED (newer entries): scalar_knot.theme_vector.{dominant, basis, normalized}
    """
    # Try nested format first (newer entries: Ghost autonomous, Q-knots, freeze knots)
    scalar = entry.get("scalar_knot", {})
    if isinstance(scalar, dict):
        tv = scalar.get("theme_vector", {})
        if isinstance(tv, dict):
            dominant = tv.get("dominant", "")
            basis = tv.get("basis", [])
            normalized = tv.get("normalized", [])
            if dominant and dominant != "?" and basis and normalized and len(basis) == len(normalized):
                return dict(zip(basis, normalized))

    # Try flat format (older entries: mag_hands, biography, mirror_meta)
    dominant = entry.get("dominant_theme", "")
    normalized = entry.get("theme_vector_normalized", [])
    if dominant and normalized:
        return {dominant: 1.0}  # single-theme vector

    # Fallback: tension_index as a proxy theme
    tension = entry.get("tension_index", 0)
    if isinstance(tension, str):
        try:
            tension = float(tension.replace("quantum-", "").replace("q-", ""))
        except ValueError:
            tension = 0.0
    if isinstance(tension, (int, float)) and tension > 0:
        return {"tension_signal": min(1.0, float(tension))}

    return {}


def aggregate_theme_vectors(knots: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate theme vectors across multiple knots into a quantized state.

    Returns:
      - dominant_theme: most frequent dominant theme
      - theme_trajectory: list of (session_id, dominant_theme)
      - aggregate_vector: mean of all normalized vectors
      - theme_drift: cosine distance between first and last knot
      - emergent_themes: themes that appeared mid-sequence
      - tension_trajectory: list of tension indices
    """
    if not knots:
        return {"knot_count": 0}

    themes: list[str] = []
    vectors: list[dict[str, float]] = []
    tensions: list[float] = []
    trajectory: list[dict[str, str]] = []

    for k in knots:
        tv = extract_theme_vector(k)
        if tv:
            vectors.append(tv)
        # Dominant theme: try nested first, then flat
        scalar = k.get("scalar_knot", {})
        dominant = ""
        if isinstance(scalar, dict):
            tv_inner = scalar.get("theme_vector", {})
            if isinstance(tv_inner, dict):
                dominant = tv_inner.get("dominant", "")
        if not dominant:
            dominant = k.get("dominant_theme", "")
        if not dominant and tv:
            # Use the first key of the theme vector as dominant
            dominant = list(tv.keys())[0] if tv else ""
        themes.append(dominant or "?")
        tension = 0.0
        if isinstance(scalar, dict):
            tension = float(scalar.get("tension_index", 0))
        if tension == 0.0:
            raw_tension = k.get("tension_index", 0)
            if isinstance(raw_tension, str):
                try:
                    tension = float(raw_tension.replace("quantum-", "").replace("q-", ""))
                except ValueError:
                    tension = 0.0
            elif isinstance(raw_tension, (int, float)):
                tension = float(raw_tension)
        tensions.append(tension)
        trajectory.append({
            "session": k.get("session_id", "?")[:30],
            "theme": dominant or "?",
            "tension": round(tension, 3),
        })

    # Dominant theme (most frequent)
    theme_counts = Counter(t for t in themes if t != "?")
    dominant = theme_counts.most_common(1)[0][0] if theme_counts else "?"

    # Aggregate vector (mean of all normalized vectors)
    if vectors:
        all_keys = set()
        for v in vectors:
            all_keys.update(v.keys())
        agg = {}
        for k in all_keys:
            vals = [v.get(k, 0.0) for v in vectors]
            agg[k] = round(sum(vals) / len(vals), 4)
    else:
        agg = {}

    # Theme drift: cosine similarity between first and last vector
    drift = 0.0
    if len(vectors) >= 2:
        v0 = vectors[0]
        v1 = vectors[-1]
        keys = set(v0.keys()) | set(v1.keys())
        dot = sum(v0.get(k, 0) * v1.get(k, 0) for k in keys)
        mag0 = math.sqrt(sum(v ** 2 for v in v0.values()))
        mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
        if mag0 > 0 and mag1 > 0:
            cos_sim = dot / (mag0 * mag1)
            drift = round(1.0 - cos_sim, 4)  # 0 = identical, 1 = completely different

    # Emergent themes: themes that appear in the second half but not the first
    mid = len(themes) // 2
    first_half = set(t for t in themes[:mid] if t != "?")
    second_half = set(t for t in themes[mid:] if t != "?")
    emergent = list(second_half - first_half)

    # Tension trajectory
    tension_mean = round(sum(tensions) / len(tensions), 3) if tensions else 0.0
    tension_max = max(tensions) if tensions else 0.0
    tension_trend = "rising" if len(tensions) >= 2 and tensions[-1] > tensions[0] else (
        "falling" if len(tensions) >= 2 and tensions[-1] < tensions[0] else "stable"
    )

    return {
        "knot_count": len(knots),
        "dominant_theme": dominant,
        "theme_distribution": dict(theme_counts.most_common(5)),
        "aggregate_vector": agg,
        "theme_drift": drift,
        "emergent_themes": emergent,
        "tension_mean": tension_mean,
        "tension_max": tension_max,
        "tension_trend": tension_trend,
        "trajectory": trajectory[-10:],  # last 10 for display
    }


# ═══════════════════════════════════════════════════════════════════
# QUANTUM SUMMARY KNOT
# ═══════════════════════════════════════════════════════════════════

def quantize_state(
    verkle_tail: int = 50,
    *,
    label: str = "",
    fold_to_verkle: bool = True,
) -> dict[str, Any]:
    """Quantize the Verkle chain into a single summary knot.

    Reads the last N knots, aggregates theme vectors, detects emergent
    patterns, and writes a quantum summary knot — a compressed representation
    that long-running agent conversations can reference as memory state.

    Args:
        verkle_tail: Number of recent knots to quantize.
        label: Human-readable label for this quantization (e.g., "pre-campaign", "room-2-checkpoint").
        fold_to_verkle: Whether to append the summary as a Verkle knot.

    Returns:
        Dict with quantum_state (aggregated), summary_knot_id, drift metrics.
    """
    knots = _read_jsonl(VERKLE_CHAIN, tail=verkle_tail)
    state = aggregate_theme_vectors(knots)

    # Generate summary knot
    summary_id = f"quantum-{label or _now()[:19].replace(':', '')}-{_hash(str(state))}"
    quantum_state = {
        "summary_id": summary_id,
        "ts": _now(),
        "label": label or "unnamed",
        "source_knots": state["knot_count"],
        "quantized_state": state,
        "compression_ratio": round(state["knot_count"] / 1, 1),  # N:1 compression
        "verkle_tail_range": f"last {verkle_tail} knots",
    }

    # Log locally
    _append_jsonl(SUMMARY_LOG, quantum_state)

    # Fold to Verkle as a summary knot
    if fold_to_verkle:
        try:
            from mag.verkle_knot import append_verkle_knot

            top_themes = list(state.get("theme_distribution", {}).keys())[:4]
            dossier = {
                "session_id": summary_id,
                "time": {
                    "created_at": {"iso_minute": _now(), "unix_minute": None, "date": None},
                    "updated_at": {"iso_minute": _now(), "unix_minute": None, "date": None},
                },
                "scalar_knot": {
                    "duration_minutes": 0.01,
                    "tension_index": f"quantum-{state.get('tension_mean', 0):.3f}",
                    "residual_weight": state.get("theme_drift", 0.0),
                    "theme_vector": {
                        "dominant": state.get("dominant_theme", "quantum"),
                        "basis": top_themes if top_themes else ["quantum", "state", "compressed", "summary"],
                        "raw": [1.0] * min(4, len(top_themes)) if top_themes else [1.0, 0.8, 0.6, 0.4],
                        "normalized": [0.4, 0.3, 0.2, 0.1],
                    },
                },
                "content_commit": {"hex": _hash(json.dumps(state, sort_keys=True, default=str))[:40]},
                "_quantum_summary": {
                    "source_knots": state["knot_count"],
                    "dominant_theme": state["dominant_theme"],
                    "theme_drift": state["theme_drift"],
                    "emergent_themes": state["emergent_themes"],
                    "tension_trend": state["tension_trend"],
                },
            }
            append_verkle_knot(dossier)
            quantum_state["verkle_folded"] = True
        except Exception:
            quantum_state["verkle_folded"] = False

    return quantum_state


# ═══════════════════════════════════════════════════════════════════
# PATTERN DETECTION — emergent behavioral signals
# ═══════════════════════════════════════════════════════════════════

def detect_phase_changes(verkle_tail: int = 100) -> list[dict[str, Any]]:
    """Detect phase changes in the Verkle chain — when the system's behavior shifts.

    A phase change occurs when:
    - The dominant theme changes abruptly (high drift between consecutive knots)
    - Tension spikes above 2σ of the running mean
    - An emergent theme appears (not seen in prior knots)
    - The theme trajectory reverses direction

    Returns list of detected phase changes with knot references.
    """
    knots = _read_jsonl(VERKLE_CHAIN, tail=verkle_tail)
    if len(knots) < 5:
        return []

    phases: list[dict[str, Any]] = []
    tensions: list[float] = []
    prev_theme = ""

    for i, k in enumerate(knots):
        scalar = k.get("scalar_knot", {})
        tension = 0.0
        theme = "?"
        if isinstance(scalar, dict):
            tension = float(scalar.get("tension_index", 0))
            tv = scalar.get("theme_vector", {})
            if isinstance(tv, dict):
                theme = tv.get("dominant", "?")
        tensions.append(tension)

        # Theme change detection
        if prev_theme and theme != "?" and theme != prev_theme:
            phases.append({
                "type": "theme_shift",
                "at_knot": i,
                "session": k.get("session_id", "?")[:30],
                "from_theme": prev_theme,
                "to_theme": theme,
                "tension": round(tension, 3),
                "ts": k.get("ts", ""),
            })
        prev_theme = theme

    # Tension spike detection (2σ above mean)
    if len(tensions) >= 5:
        mean_t = sum(tensions) / len(tensions)
        std_t = math.sqrt(sum((t - mean_t) ** 2 for t in tensions) / len(tensions))
        threshold = mean_t + 2 * std_t

        for i, t in enumerate(tensions):
            if t > threshold and t > 0.5:
                phases.append({
                    "type": "tension_spike",
                    "at_knot": i,
                    "session": knots[i].get("session_id", "?")[:30],
                    "tension": round(t, 3),
                    "mean": round(mean_t, 3),
                    "threshold": round(threshold, 3),
                    "sigma_above": round((t - mean_t) / max(std_t, 0.001), 1),
                })

    return sorted(phases, key=lambda p: p["at_knot"])


# ═══════════════════════════════════════════════════════════════════
# QUANTIZED MEMORY STATE — for long-running agent conversations
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QuantizedMemory:
    """A compressed memory state that long-running agents can reference.

    Instead of reading 50 Verkle knots, an agent reads ONE QuantizedMemory.
    This is the "quantized shared state" — the compressed summary of everything
    the system has done, suitable for injection into agent conversations.
    """
    summary_id: str
    ts: str
    label: str
    dominant_theme: str
    theme_drift: float
    tension_trend: str
    emergent_themes: list[str]
    phase_changes: list[dict[str, Any]]
    knot_count: int
    compressed_text: str  # human-readable summary for agent injection

    def to_agent_context(self) -> str:
        """Format as a dense context block for injection into agent conversations."""
        lines = [
            f"[QUANTIZED STATE: {self.label}]",
            f"Dominant theme: {self.dominant_theme}",
            f"Theme drift: {self.theme_drift:.3f} ({'significant change' if self.theme_drift > 0.3 else 'stable'})",
            f"Tension trend: {self.tension_trend}",
        ]
        if self.emergent_themes:
            lines.append(f"Emergent: {', '.join(self.emergent_themes)}")
        if self.phase_changes:
            lines.append(f"Phase changes: {len(self.phase_changes)}")
            for pc in self.phase_changes[:3]:
                lines.append(f"  - {pc['type']} at knot {pc['at_knot']}: {pc.get('from_theme','?')} → {pc.get('to_theme','?')}")
        return "\n".join(lines)


def create_memory_state(label: str = "", verkle_tail: int = 50) -> QuantizedMemory:
    """Create a quantized memory state from the current Verkle chain.

    This is the entry point for long-running agent conversations.
    Before launching a persistent agent, call this to get the compressed
    state. The agent injects `to_agent_context()` into its system prompt.
    """
    state = quantize_state(verkle_tail=verkle_tail, label=label, fold_to_verkle=True)
    qs = state["quantized_state"]
    phases = detect_phase_changes(verkle_tail=verkle_tail)

    compressed = (
        f"System state at {state['ts'][:19]}: {qs['knot_count']} knots quantized. "
        f"Dominant theme: {qs['dominant_theme']}. "
        f"Theme drift: {qs['theme_drift']:.3f}. "
        f"Tension: {qs['tension_trend']} (mean {qs['tension_mean']:.3f}, max {qs['tension_max']:.3f}). "
        f"Emergent themes: {qs['emergent_themes'] or 'none'}. "
        f"Phase changes detected: {len(phases)}."
    )

    return QuantizedMemory(
        summary_id=state["summary_id"],
        ts=state["ts"],
        label=label or state["summary_id"][:20],
        dominant_theme=qs["dominant_theme"],
        theme_drift=qs["theme_drift"],
        tension_trend=qs["tension_trend"],
        emergent_themes=qs["emergent_themes"],
        phase_changes=phases,
        knot_count=qs["knot_count"],
        compressed_text=compressed,
    )


# ═══════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════

def quantizer_status() -> dict[str, Any]:
    summaries = _read_jsonl(SUMMARY_LOG, tail=10)
    return {
        "schema": "state_quantizer.v1",
        "ts": _now(),
        "total_summaries": len(_read_jsonl(SUMMARY_LOG, tail=1000)),
        "recent_summaries": [
            {"id": s.get("summary_id", "?")[:30], "label": s.get("label", "?"),
             "knots": s.get("source_knots", 0), "ts": s.get("ts", "")}
            for s in summaries
        ],
    }
