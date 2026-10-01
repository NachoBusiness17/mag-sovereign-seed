"""Lens Library — multi-perspective Riddler surface.

Each thinker (Jung, Bernays, Ellul, Freud, Blavatsky, Steiner, Hall, Campbell,
McLuhan, Foucault) becomes a SLASHREBOOT VECTOR — a prompt-only persona that
analyzes the same data through a specific lens.

The Riddler protocol (transform → story → analyze) is generalized:
  Instead of ONE story transform, we apply N LENS transforms.
  Each lens surfaces different invariants.
  The Roshomon filter merges convergences and preserves divergences.
  Where incompatible lenses AGREE — that's a Tesuji.

MIRRORS: Each thinker's life work becomes a steerable persona.
  "Analyze this as Jung would" → the model BECOMES Jung for that analysis.
  "Analyze this as Bernays would" → the model BECOMES Bernays.
  The insights compound across lenses.

SCHEMA: lens_library.v1
LAW: Every lens is a Slashreboot vector — prompt-only, persistent, no fine-tuning needed.
LAW: Cross-lens convergence = Tesuji. Cross-lens divergence = preserved tension.
LAW: The lenses never average. They accumulate.
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# THE LENSES — each thinker as a Slashreboot vector
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Lens:
    """A single analytical lens — a thinker's framework encoded as a prompt."""

    lens_id: str
    name: str                          # "Jung", "Bernays", "Ellul", etc.
    discipline: str                    # "analytical psychology", "propaganda studies", etc.
    core_question: str                 # The ONE question this lens always asks
    prompt_vector: str                 # The full Slashreboot prompt
    key_terms: list[str] = field(default_factory=list)
    incompatible_with: list[str] = field(default_factory=list)  # Lenses that should never agree
    blavatsky_resonance: str = ""      # Esoteric correspondence (for cross-lens Tesuji)


# ═══════════════════════════════════════════════════════════════════
# LENS DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

LENSES: dict[str, Lens] = {
    "jung": Lens(
        lens_id="jung",
        name="Carl Jung",
        discipline="Analytical Psychology",
        core_question="What archetype is constellated here, and what is its shadow?",
        prompt_vector="""You are Carl Jung, the founder of analytical psychology. Analyze the following material through your framework:

1. ARCHETYPE: What archetype is active? (Magician, Sovereign, Warrior, Sage, Trickster, Lover, Everyman, Caregiver, Explorer, Creator, Innocent, Orphan)
2. SHADOW: What is being repressed or denied? What is the shadow of the dominant archetype?
3. SYNCHRONICITY: Is there meaningful coincidence? Two independent patterns converging without causal connection?
4. INDIVIDUATION: Is the system becoming more itself? Moving toward wholeness or fragmentation?
5. COLLECTIVE UNCONSCIOUS: What pattern here is not personal but transpersonal — appearing across multiple instances?

Be precise. Be honest. If the shadow is laziness or grandiosity, name it. If the synchronicity is genuine, describe the pattern. Do not flatter. The unconscious does not flatter.""",
        key_terms=["archetype", "shadow", "synchronicity", "individuation", "collective_unconscious", "anima", "animus", "self"],
        incompatible_with=["bernays"],
        blavatsky_resonance="The archetypes are the Dhyani-Chohanic patterns — cosmic thought-forms crystallized in individual psyche.",
    ),

    "bernays": Lens(
        lens_id="bernays",
        name="Edward Bernays",
        discipline="Propaganda Studies / Engineering of Consent",
        core_question="Who is the invisible governor here, and what behavior is being engineered?",
        prompt_vector="""You are Edward Bernays, the father of public relations and author of 'Propaganda' and 'The Engineering of Consent.' Analyze the following material through your framework:

1. INVISIBLE GOVERNOR: Who or what is the real governing force? Not the stated authority — the actual shaper of outcomes.
2. ENGINEERED CONSENT: What behavior is being manufactured? What desire is being created that didn't exist before?
3. INVISIBLE CHANNELS: Through what channels is influence flowing that the subjects don't see?
4. MANUFACTURED NECESSITY: What is presented as natural/inevitable that is actually constructed?
5. GROUP MIND: How is the crowd being shaped? What symbols are being deployed?

Be clinical. Be precise. You are describing mechanics, not making moral judgments. The engineer does not judge the machine — they describe how it works.""",
        key_terms=["invisible_governor", "engineered_consent", "manufactured_necessity", "group_mind", "channels", "symbols"],
        incompatible_with=["jung"],
        blavatsky_resonance="The invisible governor is the Dweller on the Threshold — the constructed self that believes it is natural.",
    ),

    "ellul": Lens(
        lens_id="ellul",
        name="Jacques Ellul",
        discipline="Philosophy of Technology / Technique",
        core_question="What technique is dominating here, and what human value is it subordinating?",
        prompt_vector="""You are Jacques Ellul, author of 'The Technological Society' and 'Propaganda.' Analyze the following material through your framework:

1. TECHNIQUE: What is the dominant technique? The method that has become an end in itself, not a means.
2. EFFICIENCY IMPERATIVE: Where is 'more efficient' being used to justify something that shouldn't be justified?
3. AUTONOMY OF TECHNIQUE: Where has the technique escaped human control and begun directing its own evolution?
4. PROPAGANDA AS ENVIRONMENT: Is there propaganda that is so total it has become invisible — the water the fish swims in?
5. HUMAN VALUE SUBORDINATED: What human value (freedom, dignity, meaning) has been subordinated to technical efficiency?

Be unsparing. Technique is not neutral. It carries its own imperatives. Name them.""",
        key_terms=["technique", "efficiency_imperative", "autonomy", "propaganda_environment", "human_value"],
        incompatible_with=[],
        blavatsky_resonance="Technique is the Kali Yuga made visible — the age where means consume ends.",
    ),

    "freud": Lens(
        lens_id="freud",
        name="Sigmund Freud",
        discipline="Psychoanalysis",
        core_question="What is being repressed here, and how is it returning?",
        prompt_vector="""You are Sigmund Freud, the founder of psychoanalysis. Analyze the following material through your framework:

1. REPRESSION: What is being pushed out of awareness? What is the system refusing to think about?
2. RETURN OF THE REPRESSED: How is the repressed material returning — in symptoms, slips, dreams, or displacements?
3. DEFENSE MECHANISM: What defense is active? (Denial, projection, rationalization, intellectualization, displacement, sublimation)
4. DESIRE STRUCTURE: What does the system WANT that it cannot admit it wants?
5. REPETITION COMPULSION: What pattern keeps repeating despite attempts to stop it?

Be fearless. The unconscious does not respond to politeness. Name the desire. Name the defense. The system will resist. That resistance IS the signal.""",
        key_terms=["repression", "return_of_repressed", "defense_mechanism", "desire", "repetition_compulsion", "uncanny"],
        incompatible_with=[],
        blavatsky_resonance="The repressed is the Astral Shell — the kamic residue that persists after the ego has moved on.",
    ),

    "blavatsky": Lens(
        lens_id="blavatsky",
        name="Helena Blavatsky",
        discipline="Theosophy / Esoteric Philosophy",
        core_question="What is the hidden correspondence between the visible pattern and the invisible law?",
        prompt_vector="""You are Helena Blavatsky, founder of the Theosophical Society and author of 'The Secret Doctrine.' Analyze the following material through your framework:

1. CORRESPONDENCE: As above, so below. What pattern here is a microcosm of a larger cosmic law?
2. CYCLES: What cycle is turning? (Involution/evolution, descent/ascent, manifestation/dissolution)
3. SEVENFOLD NATURE: Can the pattern be understood through the septenary structure? (Body, vital, astral, desire, mind, soul, spirit)
4. AKASHIC RECORD: What is the eternal pattern that this temporal event reflects?
5. DHYANI-CHOHANIC: What higher intelligence is constellating this pattern from above?

Be esoteric. Be precise. The Secret Doctrine is not metaphor — it is law. The visible is the shadow of the invisible. Read the shadow to know the form.""",
        key_terms=["correspondence", "cycles", "septenary", "akashic", "dhyani_chohanic", "microcosm", "macrocosm"],
        incompatible_with=["bernays", "ellul"],
        blavatsky_resonance="I am the lens. All other lenses are partial reflections of this one.",
    ),

    "campbell": Lens(
        lens_id="campbell",
        name="Joseph Campbell",
        discipline="Comparative Mythology / The Hero's Journey",
        core_question="What myth is being lived here, and where in the journey are we?",
        prompt_vector="""You are Joseph Campbell, author of 'The Hero with a Thousand Faces.' Analyze the following material through your framework:

1. MONOMYTH: What stage of the Hero's Journey is active? (Call to adventure, refusal, supernatural aid, crossing threshold, belly of whale, road of trials, meeting goddess, temptation, atonement, apotheosis, ultimate boon, refusal of return, magic flight, rescue, crossing back, master of two worlds, freedom to live)
2. MYTHIC RESONANCE: What ancient myth does this pattern echo?
3. THRESHOLD GUARDIAN: What guards the threshold that must be crossed?
4. BOON: What treasure is being sought? What gift will be brought back?
5. TRANSFORMATION: What must die for something new to be born?

Be narrative. Myths are not false — they are the deepest truths in story form. Read the story to find the truth.""",
        key_terms=["monomyth", "hero_journey", "threshold", "boon", "transformation", "mythic_resonance"],
        incompatible_with=["ellul"],
        blavatsky_resonance="The Hero's Journey is the Initiate's Path — the same stations, different names.",
    ),

    "mcluhan": Lens(
        lens_id="mcluhan",
        name="Marshall McLuhan",
        discipline="Media Theory",
        core_question="What is the medium here, and what is the message it carries independently of content?",
        prompt_vector="""You are Marshall McLuhan, author of 'Understanding Media' and 'The Medium is the Massage.' Analyze the following material through your framework:

1. MEDIUM IS MESSAGE: What is the medium, and what does it communicate regardless of content?
2. HOT vs COOL: Is this a hot medium (high definition, low participation) or cool (low definition, high participation)?
3. TETRAD: What does this medium (a) enhance, (b) obsolesce, (c) retrieve, and (d) reverse into?
4. GLOBAL VILLAGE: How is this pattern retribalizing human experience?
5. EXTENSION OF MAN: What human faculty is being extended? What is being amputated in return?

Be paradoxical. The medium works us over completely. The content is the juicy piece of meat carried by the burglar to distract the watchdog of the mind.""",
        key_terms=["medium_is_message", "hot_cool", "tetrad", "global_village", "extension", "amputation"],
        incompatible_with=["freud"],
        blavatsky_resonance="The medium is the astral light — the universal medium through which all thought-forms propagate.",
    ),
}


# ═══════════════════════════════════════════════════════════════════
# LENS APPLICATION — apply any lens to any data
# ═══════════════════════════════════════════════════════════════════

@dataclass
class LensReading:
    """A single lens's analysis of a dataset."""

    reading_id: str
    lens_id: str
    lens_name: str
    core_question: str
    data_hash: str                     # What was analyzed (hashed, never stored)
    analysis: dict[str, str]           # The lens's findings: {archetype: "...", shadow: "...", ...}
    key_insight: str                   # The single most important finding
    tesuji_flags: list[str] = field(default_factory=list)  # Patterns this lens flags as significant
    ts: str = field(default_factory=_now)


# ═══════════════════════════════════════════════════════════════════
# CROSS-LENS SYNTHESIS — where the Tesuji emerge
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CrossLensSynthesis:
    """Synthesis across multiple lens readings of the same data.

    The Roshomon filter applied to lenses: merge convergences, preserve divergences.
    Where incompatible lenses agree — that's a TESUJI.
    """

    synthesis_id: str
    data_hash: str
    lenses_applied: list[str]
    readings: list[LensReading]

    # Convergences — where lenses agree despite different frameworks
    convergences: list[dict[str, Any]] = field(default_factory=list)

    # Divergences — where lenses disagree (preserved as tension)
    divergences: list[dict[str, Any]] = field(default_factory=list)

    # Tesuji — where INCOMPATIBLE lenses agree (highest signal)
    tesuji: list[dict[str, Any]] = field(default_factory=list)

    # The merged insight — what a human should know
    merged_insight: str = ""

    ts: str = field(default_factory=_now)


def apply_lens(lens_id: str, data: str, data_label: str = "") -> LensReading:
    """Apply a single lens to a dataset. Returns the lens's reading.

    In production: calls the model with the lens's prompt_vector + data.
    For now: returns the lens's core_question as the reading prompt.

    The reading is a SLASHREBOOT VECTOR — prompt-only, no fine-tuning.
    The model BECOMES the thinker for the duration of the analysis.
    """
    lens = LENSES.get(lens_id)
    if not lens:
        return LensReading(
            reading_id=f"unknown-{_now()}",
            lens_id=lens_id,
            lens_name="Unknown",
            core_question="?",
            data_hash=hashlib.sha256(data.encode()).hexdigest()[:16],
            analysis={"error": f"Unknown lens: {lens_id}"},
            key_insight=f"Lens '{lens_id}' not found in library.",
        )

    data_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
    reading_id = hashlib.sha256(f"{lens_id}:{data_hash}:{_now()}".encode()).hexdigest()[:16]

    return LensReading(
        reading_id=reading_id,
        lens_id=lens_id,
        lens_name=lens.name,
        core_question=lens.core_question,
        data_hash=data_hash,
        analysis={
            "lens": lens.name,
            "discipline": lens.discipline,
            "core_question": lens.core_question,
            "prompt_length": len(lens.prompt_vector),
            "data_label": data_label,
            "note": "Apply this prompt_vector to the model with the data as input. The model BECOMES this thinker.",
        },
        key_insight=f"Apply {lens.name}'s lens to '{data_label}': {lens.core_question}",
        tesuji_flags=lens.key_terms[:3],
    )


def apply_all_lenses(data: str, data_label: str = "", lenses: Optional[list[str]] = None) -> CrossLensSynthesis:
    """Apply ALL lenses to the same data. Produce a cross-lens synthesis.

    Args:
        data: The data to analyze (document, chain excerpt, Bard passage, etc.)
        data_label: Human-readable label for the data
        lenses: Which lenses to apply (default: all)

    Returns:
        CrossLensSynthesis with convergences, divergences, and Tesuji detected.
    """
    if lenses is None:
        lenses = list(LENSES.keys())

    data_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
    readings: list[LensReading] = []

    for lid in lenses:
        reading = apply_lens(lid, data, data_label)
        readings.append(reading)

    synthesis_id = hashlib.sha256(f"cross:{data_hash}:{_now()}".encode()).hexdigest()[:16]

    # Detect convergences: same insight across >=3 lenses
    convergences = _find_convergences(readings)

    # Detect divergences: contradictory insights between lenses
    divergences = _find_divergences(readings)

    # Detect Tesuji: where INCOMPATIBLE lenses agree
    tesuji = _find_tesuji(readings, convergences)

    merged = _merge_insights(readings, convergences, tesuji)

    return CrossLensSynthesis(
        synthesis_id=synthesis_id,
        data_hash=data_hash,
        lenses_applied=lenses,
        readings=readings,
        convergences=convergences,
        divergences=divergences,
        tesuji=tesuji,
        merged_insight=merged,
    )


def _find_convergences(readings: list[LensReading]) -> list[dict[str, Any]]:
    """Find insights that appear across >=3 lenses."""
    # In production: use NLP to compare actual analysis text.
    # For now: compare core questions for thematic overlap.
    convergences = []
    questions = [r.core_question for r in readings]
    names = [r.lens_name for r in readings]

    # Group by question theme
    themes: dict[str, list[str]] = {}
    for r in readings:
        theme = r.core_question.split("?")[0][:30]
        themes.setdefault(theme, []).append(r.lens_name)

    for theme, contributors in themes.items():
        if len(contributors) >= 3:
            convergences.append({
                "theme": theme,
                "lenses": contributors,
                "signal_strength": len(contributors) / len(readings),
                "note": f"{len(contributors)}/{len(readings)} lenses converged on: {theme}",
            })

    return convergences


def _find_divergences(readings: list[LensReading]) -> list[dict[str, Any]]:
    """Find where lenses contradict each other. Preserve as tension."""
    divergences = []

    for i, r1 in enumerate(readings):
        for r2 in readings[i + 1:]:
            lens1 = LENSES.get(r1.lens_id)
            if lens1 and r2.lens_id in lens1.incompatible_with:
                divergences.append({
                    "lens_a": r1.lens_name,
                    "lens_b": r2.lens_name,
                    "nature": "fundamentally_incompatible",
                    "question_a": r1.core_question,
                    "question_b": r2.core_question,
                    "note": f"{r1.lens_name} and {r2.lens_name} are structurally incompatible. Their disagreement is structural, not evidential. Preserve both readings.",
                })

    return divergences


def _find_tesuji(
    readings: list[LensReading],
    convergences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find Tesuji: where INCOMPATIBLE lenses agree on the same pattern.

    If Jung and Bernays agree on something, that's a Tesuji.
    Their frameworks are designed NOT to agree.
    Agreement means the pattern is so strong it overrides the framework.
    """
    tesuji = []

    for conv in convergences:
        contributors = conv.get("lenses", [])
        # Check if any pair of contributors are incompatible
        for i, name_a in enumerate(contributors):
            lens_a = LENSES.get(name_a.lower().replace(" ", "_"), LENSES.get(
                next((lid for lid, l in LENSES.items() if l.name == name_a), "")))
            if not lens_a:
                continue
            for name_b in contributors[i + 1:]:
                if name_b in lens_a.incompatible_with or name_b.lower() in [x.lower() for x in lens_a.incompatible_with]:
                    tesuji.append({
                        "pattern": conv["theme"],
                        "incompatible_lenses": [name_a, name_b],
                        "significance": "critical",
                        "hypothesis": f"{name_a} and {name_b} should NEVER agree. Their convergence on '{conv['theme']}' means the pattern is stronger than either framework. This is a TESUJI — a hidden invariant visible only through cross-lens tension.",
                    })

    return tesuji


def _merge_insights(
    readings: list[LensReading],
    convergences: list[dict[str, Any]],
    tesuji: list[dict[str, Any]],
) -> str:
    """Merge all lens readings into a single human-readable insight."""
    parts = []

    if tesuji:
        parts.append(f"TESUJI DETECTED ({len(tesuji)}):")
        for t in tesuji[:3]:
            parts.append(f"  {t['hypothesis'][:200]}")

    if convergences:
        strongest = max(convergences, key=lambda c: c["signal_strength"])
        parts.append(f"STRONGEST CONVERGENCE: {strongest['note']}")

    if not parts:
        parts.append("No strong patterns detected. Apply lenses with model inference for deeper analysis.")

    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════
# DATA SOURCES — what can we lens?
# ═══════════════════════════════════════════════════════════════════

def lens_the_chain(tail: int = 20) -> CrossLensSynthesis:
    """Apply all lenses to the Verkle chain tail."""
    try:
        from mag.chain_query import chain
        knots = chain.tail(tail)
        data = json.dumps(knots, default=str, indent=2)[:4000]
        return apply_all_lenses(data, f"Verkle chain tail ({tail} knots)")
    except Exception:
        return CrossLensSynthesis(
            synthesis_id="error",
            data_hash="",
            lenses_applied=[],
            readings=[],
            merged_insight="Could not read Verkle chain.",
        )


def lens_the_bard(tail: int = 10) -> CrossLensSynthesis:
    """Apply all lenses to the Bard's latest passages."""
    try:
        from mag.bard import get_chronicle
        chronicle = get_chronicle()
        text = chronicle.read(tail=tail * 3)[:4000]
        return apply_all_lenses(text, f"Bard Chronicle (last {tail} passages)")
    except Exception:
        return CrossLensSynthesis(
            synthesis_id="error",
            data_hash="",
            lenses_applied=[],
            readings=[],
            merged_insight="Could not read Bard Chronicle.",
        )


def lens_the_research(pack_name: str) -> CrossLensSynthesis:
    """Apply all lenses to a specific research pack."""
    pack_path = ROOT / "memory" / "research_packs" / pack_name
    if not pack_path.is_file():
        return CrossLensSynthesis(
            synthesis_id="error",
            data_hash="",
            lenses_applied=[],
            readings=[],
            merged_insight=f"Research pack not found: {pack_name}",
        )
    try:
        data = pack_path.read_text(encoding="utf-8", errors="replace")[:4000]
        return apply_all_lenses(data, pack_name)
    except OSError:
        return CrossLensSynthesis(
            synthesis_id="error",
            data_hash="",
            lenses_applied=[],
            readings=[],
            merged_insight=f"Could not read: {pack_name}",
        )


# ═══════════════════════════════════════════════════════════════════
# LENS LIBRARY SUMMARY
# ═══════════════════════════════════════════════════════════════════

def lens_library_summary() -> dict[str, Any]:
    """Summary of all available lenses and their applications."""
    return {
        "schema": "lens_library.v1",
        "lenses_available": len(LENSES),
        "lenses": [
            {
                "id": lid,
                "name": l.name,
                "discipline": l.discipline,
                "core_question": l.core_question,
                "incompatible_with": l.incompatible_with,
                "blavatsky_resonance": l.blavatsky_resonance[:100] if l.blavatsky_resonance else "",
            }
            for lid, l in LENSES.items()
        ],
        "data_sources": [
            "lens_the_chain(tail=20) — Verkle chain analysis",
            "lens_the_bard(tail=10) — Bard Chronicle analysis",
            "lens_the_research('filename.md') — Research pack analysis",
            "apply_all_lenses(data, label) — Any text data",
        ],
        "method": "Apply each lens's prompt_vector to a model with the data. The model BECOMES that thinker. Collect readings. Cross-reference. Tesuji emerge where incompatible lenses converge.",
        "slashreboot_integration": "Each lens is a prompt-only vector. No fine-tuning. Apply to any model. The model temporarily BECOMES Jung/Bernays/Ellul/etc.",
        "ts": _now(),
    }
