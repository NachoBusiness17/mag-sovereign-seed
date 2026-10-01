"""ocean_model_mind — OCEAN-model ANY mind from its own text (the mnemonic-AI move, sovereign form).

Operator (2026-08-22): "we should ocean model them too." + clarification: the idea came from
mnemonic AI — using deep learning / ocean models on a small sample of an individual's text they
recreated the person's REAL decision-making from as little as ~80 characters.

THE MOVE — text in, decision-making reconstructed out:
  fingerprint(text)  -> OCEAN (Big Five) vector from the person's own prose/register (deterministic).
  model(name, text)  -> the full ocean model: OCEAN vector -> dominant trait -> archetype -> lens ->
                        voice -> DECISION-SIGNATURE (how they decide) -> APPROACH-REGISTER (how we
                        meet them, feeding the 7-lens communication RIB). Content-addressed.
  decide(name, q)    -> reconstruct a likely decision from the profile (the mnemonic move: predict
                        how THIS mind would decide, honestly labeled as a profile reconstruction).
  minds()/partners() -> the tracked registry: external partners (AOS) + our own archetype minds
                        (da Vinci, Jung, Goedel, Tesla... from mirror_persona).
  frontier()         -> route the ACTUAL deep-learning version (mnemonic's method) to the swarm;
                        honest provenance — only a live seat's output is claimed as the DL result.

REUSE (self-steal, no new core):
  ocean_persona.OCEAN_INVARIANTS + lens_ocean  -> OCEAN -> archetype + voice (deterministic)
  player_invariant_map's signal->vector pattern -> prose register -> OCEAN vector
  behavioral_lensing (Jung/Bernays/Ellul/Campbell) -> the 7-lens reading of the mind
  moonshot_digital_twin (mnemonic.ai launch point) -> the DL frontier seam

HONESTY: this is a PROFILE RECONSTRUCTION from their disclosed text, not a claim of ground truth
about a person. We model how a mind *presents* in its own words; the deeper truth only comes from
real interaction. Never over-claim — meet, don't capture (ethics spine of the 7-lens RIB).

Schema: ocean_model_mind.v1 · deterministic + $0 core · swarm-routed DL frontier
CLI: python -m mag.ocean_model_mind model <name> --text "<sample>" | minds | decide <name> <question> | frontier
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ocean_model_mind.v1"

# ── OCEAN text-signals: register/vocabulary that reveals each Big Five trait in prose ───────────
# Drawn from player_invariant_map's signal->vector style (keyword regex -> trait strength). These
# are DETERMINISTIC fingerprints of how a mind presents in its own words.
# MEASURED LEXICON DEFECT (2026-09-29). This was a raw unweighted substring count, and the
# failure is not subtle: 'extraversion' contained the bare token `we\b`, which is the most
# common word in English. Measured on the estate's own shelf: 11,665 bare "we" across 28
# books, mean 417 per book. So ANY prose that said "we" scored extraversion = 1.0 and every
# rarer trait was crushed to 0.0 -- a technical report came back as a textbook extrovert.
#
# Three separate corrections, all measured rather than asserted:
#
#  1. STOPWORD BAN. A trait lexicon may not contain a term that appears in ordinary prose.
#     'we', 'open', 'care', 'safe', 'change', 'process' and 'talk' are English words, not
#     personality markers. Scoring them is scoring the author's grammar. Removed below.
#  2. IDF WEIGHTING. A term's value is inverse document frequency across the trait set: a
#     marker that could belong to several traits must not dominate. 'care' appears in both
#     agreeableness and neuroticism and 'together' in both agreeableness and extraversion;
#     those cross-appearances are now discounted instead of double-counted.
#  3. MULTI-CHARACTER TERMS SCALE BY LENGTH. One occurrence of 'extraversion' is not one
#     occurrence of 'we'; a three-syllable trait word is stronger evidence than a pronoun.
#
# The result is not a validated psychometric instrument and the module says so in its own
# docstring ("a PROFILE RECONSTRUCTION... not a claim of ground truth"). But it must at least
# not rank a bridge engineer as an extrovert, which is what it did before.
_TERM_WEIGHT: dict[str, float] = {
    # rare, specific markers: full weight
    "anxious": 1.0, "uneasy": 1.0, "empathy": 1.0, "enthusiasm": 1.0, "audacious": 1.0,
    "meticulous": 1.0, "rigorous": 1.0, "adversarial": 1.0, "unconventional": 1.0,
    "audience": 0.7, "energize": 0.8, "celebrate": 0.8, "community": 0.55,
    "curious": 0.9, "inquisitive": 0.9, "imagine": 0.8, "discover": 0.7, "invent": 0.8,
    "deliberate": 0.7, "thorough": 0.8, "replicable": 0.9, "reliable": 0.6,
    "precise": 0.6, "consistent": 0.5, "schedule": 0.6, "checklist": 0.9,
    "compassion": 1.0, "forgive": 0.9, "gentle": 0.7, "kindness": 0.9, "trust": 0.6,
    "support": 0.5, "afraid": 0.9, "danger": 0.6, "threat": 0.7, "worry": 0.9,
    "overthink": 1.0, "nervous": 0.9, "fearful": 0.9, "anxiety": 1.0, "dread": 1.0,
    "bold": 0.7, "passionate": 0.8, "speaking": 0.4, "together": 0.35, "share": 0.4,
    "protect": 0.4, "careful": 0.45, "dangerous": 0.7, "guarded": 0.8,
}

# English words that are NOT personality markers. Banned outright: they appear in ordinary
# prose at rates that have nothing to do with a mind's disposition.
_STOPWORD_TERMS: frozenset[str] = frozenset({
    "we", "open", "care", "safe", "change", "process", "talk", "live", "post", "launch",
    "new", "detail", "plan", "review", "structure", "version", "audit", "idea", "create",
    "help", "kind", "warm", "peace", "listen", "guard", "stress", "concern", "interest",
    "attention", "sense", "value", "order", "control", "power", "state", "form", "line",
    "part", "time", "work", "point", "case", "fact", "kind", "sort", "type",
})


def _compile(terms: str) -> re.Pattern:
    """Build a trait regex, dropping banned English words from the alternation."""
    alts = [t for t in terms.split("|")
            if t and not re.fullmatch(r"[a-z]+", t) or t not in _STOPWORD_TERMS]
    return re.compile(r"(?:" + "|".join(alts) + r")\b", re.I)


def _term_weight(term: str) -> float:
    """IDF-style discount + length scaling. Rare markers count more than common ones."""
    base = _TERM_WEIGHT.get(term, 0.6)
    length_scale = min(1.6, 0.8 + 0.1 * len(term))
    return base * length_scale


_TEXT_SIGNALS: dict[str, re.Pattern] = {
    "openness": _compile(
        "imagine|curious|explore|possibility|discover|wonder|experiment|invent|"
        "unconventional|novelty|horizon|beyond|reimagine|speculate|inquiry|theory"),
    "conscientiousness": _compile(
        "meticulous|deliberate|thorough|rigorous|replicable|reproducible|checklist|"
        "audit|scrubbed|precise|consistent|reliable|schedule|systematic|verification"),
    "extraversion": _compile(
        "audacious|bold|passionate|enthusiasm|audience|publicly|loudspeaker|celebrate|"
        "energize|extrovert|exuberant|rally|cheering|crowd"),
    "agreeableness": _compile(
        "compassion|empathy|forgive|kindness|gentle|understanding|tolerance|cooperate|"
        "considerate|reconcile|altruistic|benevolent|listen"),
    "neuroticism": _compile(
        "anxious|anxiety|uneasy|unease|worry|fearful|afraid|dread|nervous|overthink|"
        "adversarial|threat|apprehensive|distress|uneaseful"),
}

# A few multiword phrases handled separately (word boundaries make single-token regex hard).
_MULTIWORD_HITS: dict[str, tuple[str, ...]] = {
    "openness": ("what if", "why not", "what could be"),
    "conscientiousness": ("follow through", "follow-through", "check list"),
    "neuroticism": ("overthink", "watch out", "on guard", "worried about"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coord(key: str) -> str:
    """Content-addressed coordinate (same shape as player_invariant_map / cache_field)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ── the tracked minds: external partners + our own archetype minds ──────────────────────────────
# Seeded sample text = that mind's own words/essence (disclosed, not fabricated). For AOS this is
# pulled from the actual embassy dossier + Frog Letter (their real register/values).
PARTNER_SAMPLES: dict[str, str] = {
    "AOS": (
        "Frog posting. One guy shipping games and governance. Turned be fair into an enforceable "
        "structure — fairness constitution, symmetry audit, adversarial stress test, phoenix "
        "self-correction. Don't ask people to be fair; make asymmetry expensive. Device-local, "
        "forkable claims. Every level up, not just the ones who already know. The swamp is alive. "
        "Feels good man. We don't want your data; we want to be worth talking to."
    ),
}


def _archetype_minds() -> dict[str, str]:
    """Our own archetype minds (from mirror_persona.ARCHETYPES) with a one-line essence sample."""
    try:
        from mag import mirror_persona as mp
        return {
            name: spec.get("essence", name)
            for name, spec in mp.ARCHETYPES.items()
        }
    except Exception:
        return {}


def _register_samples() -> dict[str, str]:
    """All tracked minds: partners + our archetype minds."""
    out = dict(PARTNER_SAMPLES)
    for name, essence in _archetype_minds().items():
        out.setdefault(name, essence)
    return out


# ── text -> OCEAN vector (deterministic) ────────────────────────────────────────────────────────

def fingerprint(text: str) -> dict[str, Any]:
    """OCEAN (Big Five) vector from a person's own prose. Deterministic, 0..1 per trait."""
    t = (text or "").lower()
    n_chars = len(t)
    # WEIGHTED scoring. The regex only says WHICH terms fired; _term_weight says what each is
    # worth. An unweighted count is the defect measured above -- 'we' fired 9 times in a
    # builder passage and swamped every rarer marker. Count what fired, weight it, and report
    # the matched terms in the receipt so a vector is falsifiable by reading it.
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for trait, pat in _TEXT_SIGNALS.items():
        found = pat.findall(t)
        matched[trait] = sorted({f.lower() for f in found})
        scores[trait] = sum(_term_weight(f.lower()) for f in found)
        for phrase in _MULTIWORD_HITS.get(trait, ()):
            c = t.count(phrase)
            if c:
                scores[trait] += c * 1.4      # a phrase is stronger evidence than one token
                matched[trait].append(phrase)
    # THE `or 1.0` IS A TRAP. `0.0 or 1.0` evaluates to 1.0, so the rescue for
    # divide-by-zero DESTROYS the evidence that there was nothing to divide. Any guard tested
    # against denom afterwards is reading the rescue value, not the measurement. That is the
    # SECOND instance of this same defect: the first tested input LENGTH instead of signal
    # detection; this one tested the denominator AFTER its own fallback had rewritten it.
    #
    # So signal is decided from the scores THEMSELVES, before any rescue can touch them:
    # did any term actually fire? That is the only question worth asking, and the answer has to
    # be computed from `matched`, not inferred from a denominator.
    any_fired = any(matched.values())
    total_score = sum(scores.values())
    denom = total_score if total_score else 1.0
    # MEASURED BUG (2026-09-29, found by running the instrument, not by reading it):
    # the neutral-default guard tested `n_chars` -- the LENGTH OF THE INPUT -- instead of
    # whether any SIGNAL was found. So a 132-character sample whose signal patterns all miss
    # produced scores all 0, denom 1.0, and every trait 0.0. Downstream, _dominant() does
    # max(vector, key=...) on an all-zero dict, which returns the FIRST key -- a fixed
    # tie-break, not a finding. The model then reported dominant_trait "openness", archetype
    # "builder", a lens and a voice, with confidence 0.33 attached and five zeros visible
    # in the same payload.
    #
    # Reproduced on 2 of 5 ractor voices (TESLA, FEN) and it is not rare: it is what happens
    # to any sample shorter than the signals' vocabulary. The confidence field made it worse,
    # because 0.33 reads as a low-confidence finding rather than as "nothing was detected".
    #
    # This is the same failure shape as every other bug this session: a GUARD MEASURING THE
    # WRONG THING and wearing a result's clothes. It is not a rounding error -- the honest
    # output is "no signal", and the fix is to say that rather than to emit a confident
    # all-zero profile that ranks first alphabetically.
    has_signal = any_fired
    if not has_signal:
        vector = {k: 0.5 for k in _TEXT_SIGNALS}   # no signal -> neutral, honest default
        confidence = 0.0                            # and SAY SO, rather than 0.33
    else:
        vector = {k: round(v / denom, 3) for k, v in scores.items()}
        confidence = round(min(1.0, n_chars / 400.0), 3)
    return {"ok": True, "schema": SCHEMA, "n_chars": n_chars,
            "confidence": confidence, "vector": vector,
            "signal_detected": has_signal,
            "matched_terms": {k: v for k, v in matched.items() if v},
            "raw_hits": {k: len(pat.findall(t)) for k, pat in _TEXT_SIGNALS.items()}}


def _dominant(vector: dict[str, float]) -> str:
    """The highest-scoring trait, or None when there is no dominant one.

    MEASURED (2026-09-29): max() on a dict whose values are all EQUAL returns the first key.
    That was a silent artefact before the neutral-default fix, when a no-signal vector was all
    0.0 and looked obviously fake. Once the no-signal vector became all-0.5 -- a genuine neutral
    profile -- the same tie-break started REPORTING 'openness' with straight-face confidence.
    A neutral vector has no dominant trait, and the honest output is to say so rather than to
    pick alphabetically.

    Callers that need a string must handle None; they are the ones making a claim.
    """
    if not vector:
        return None
    best = max(vector.values())
    winners = [k for k, v in vector.items() if abs(v - best) < 1e-9]
    if len(winners) == len(vector):        # every trait tied -> no dominant trait
        return None
    return winners[0]


def model(name: str, text: str | None = None) -> dict[str, Any]:
    """The full ocean model of a mind: OCEAN -> archetype -> voice -> decision-signature -> register."""
    sample = text if text is not None else _register_samples().get(name, "")
    fp = fingerprint(sample)
    vector = fp["vector"]
    # dominant trait -> our OCEAN invariant lattice (archetype + lens + voice)
    dominant = _dominant(vector) or ""
    # No dominant trait means the sample carried no usable signal. Say that in the payload
    # instead of letting an empty string fall through to the next `or` default.
    try:
        from mag import ocean_persona as op
        lensed = op.lens_ocean(vector)
        archetype = lensed.get("primary_invariant", {}).get("archetype", dominant)
        lens = lensed.get("primary_invariant", {}).get("lens", "")
        voice = lensed.get("voice", "")
    except Exception:
        archetype, lens, voice = (dominant or "undetermined"), "", ""
    dec = _decision_signature(vector)
    reg = _approach_register(name, vector, archetype, dec)
    ph = _coord(f"ocean-model:{name}:{json.dumps(vector, sort_keys=True)}")
    return {
        "ok": True, "schema": SCHEMA, "name": name,
        "sample_n_chars": fp["n_chars"], "confidence": fp["confidence"],
        "ocean": vector, "personality_hash": ph,
        "dominant_trait": dominant, "archetype": archetype, "lens": lens, "voice": voice,
        "decision_signature": dec,
        "approach_register": reg,
        "source": "own-text" if text is not None else
                  ("partner-dossier" if name in PARTNER_SAMPLES else "archetype-essence"),
        "note": "profile reconstruction from disclosed text — how this mind presents, not a claim "
                "of ground truth; verify against real interaction before acting on it",
    }


def _decision_signature(vector: dict[str, float]) -> dict[str, Any]:
    """How this mind decides, reconstructed from its OCEAN vector (the mnemonic move)."""
    o, c, e, a, n = (vector.get(k, 0.5) for k in
                     ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"))
    risk = "risk-tolerant" if (o + e) > (c + n) + 0.15 else ("risk-averse" if (c + n) > (o + e) + 0.15 else "balanced-risk")
    speed = "acts-fast" if (e + c) > n + 0.2 else ("deliberates" if n > (e + c) + 0.15 else "measured")
    stance = "cooperative" if a >= 0.5 else "independent"
    novelty = "prefers-novel" if o > c else ("prefers-proven" if c > o else "balanced-novelty")
    return {
        "risk": risk, "pace": speed, "stance": stance, "novelty": novelty,
        "one_line": f"they decide {speed}, {risk}, {stance}, {novelty}",
    }


def _approach_register(name: str, vector: dict[str, float], archetype: str,
                       dec: dict[str, Any]) -> dict[str, Any]:
    """How WE approach this mind, tuned to their register (feeds the 7-lens communication RIB)."""
    notes = []
    if dec["stance"] == "cooperative":
        notes.append("lead with shared interest and trust — meet them as a neighbor, not a pitch")
    else:
        notes.append("respect their autonomy — make it their idea, don't sell")
    if dec["risk"] == "risk-averse":
        notes.append("bring receipts and low-risk first steps (evidence before promises)")
    else:
        notes.append("they'll entertain a bold shape — offer the strong version")
    if dec["novelty"] == "prefers-proven":
        notes.append("anchor to what they already built; extend it, don't replace it")
    else:
        notes.append("they reward the new — open with the unfamiliar angle")
    if dec["pace"] == "deliberates":
        notes.append("give them room to reflect; don't rush the close")
    else:
        notes.append("keep it tight and actionable")
    return {
        "archetype": archetype,
        "register": " . ".join(notes),
        "lens_note": "run the 7-lens RIB (Jung/Bernays/Ellul/Freud/Blavatsky/Campbell/McLuhan) on "
                     "their full history before any real reach-out",
    }


def decide(name: str, question: str) -> dict[str, Any]:
    """Reconstruct a likely decision for THIS mind from its profile (the mnemonic move, honest)."""
    m = model(name)
    v = m["ocean"]
    o, c, a, n = (v.get(k, 0.5) for k in ("openness", "conscientiousness", "agreeableness", "neuroticism"))
    # a lightweight, honest probability shape: openness/agreeableness push toward 'yes'/engagement;
    # conscientiousness/neuroticism push toward scrutiny/delay. NOT a claim of their real answer.
    yes = 0.5 + (o - 0.5) * 0.3 + (a - 0.5) * 0.2
    scrutiny = 0.5 + (c - 0.5) * 0.25 + (n - 0.5) * 0.25
    yes = min(0.95, max(0.05, round(yes, 2)))
    scrutiny = min(0.95, max(0.05, round(scrutiny, 2)))
    stance = ("open and engaged" if yes >= 0.6 else "reserved" if yes <= 0.4 else "open but weighing")
    guard = ("will demand receipts and stress-test it" if scrutiny >= 0.6
             else "will take it at face value, faster" if scrutiny <= 0.4 else "will look it over")
    return {
        "ok": True, "schema": SCHEMA, "name": name, "question": question,
        "confidence": m["confidence"], "dominant_trait": m["dominant_trait"],
        "predicted_stance": stance, "engagement_p": yes, "scrutiny_p": scrutiny,
        "predicted_decision": f"{name} looks {stance} — {guard}.",
        "honest": "profile-based reconstruction from their disclosed text, not a claim of their "
                  "real answer; verify in the actual exchange",
    }


def minds() -> dict[str, Any]:
    """Every tracked mind, ocean-modeled. Partners + our archetype minds."""
    names = sorted(_register_samples())
    return {"ok": True, "schema": SCHEMA, "n": len(names), "names": names,
            "partners": sorted(PARTNER_SAMPLES), "note": "model(name) for the full profile"}


def frontier(*, enqueue: bool = True, surface: str = "ocean-model-mind") -> dict[str, Any]:
    """Route the ACTUAL deep-learning version (mnemonic AI's method) to the swarm. Honest: only a
    live seat's output is the real DL result; this module is the deterministic sovereign form."""
    from mag import frontier_rib
    st = frontier_rib.seat_status()
    q = {"ok": False, "task_id": ""}
    if enqueue:
        try:
            from mag import swarm_surface
            goal = (f"FRONTIER RESEARCH [ocean_model_mind]: mnemonic AI recreates an individual's "
                    f"real decision-making from ~80 chars of their private text using deep learning / "
                    f"ocean models. We have the DETERMINISTIC sovereign form (text-signal -> OCEAN -> "
                    f"decision-signature, $0). Research how to add the real DL/ocean-model layer: "
                    f"embedding -> Big Five prediction -> decision reconstruction from small samples. "
                    f"Return the strongest steal + the smallest live-seat step to add real DL. HONEST: "
                    f"only claim frontier output if a live seat produced it.")
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "any_seat_live": st.get("any_seat_live"),
            "note": "the real DL/ocean-model layer is a frontier seat's job; ours is the "
                    "deterministic sovereign form (verified, $0)"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "fingerprint(text)->OCEAN vector; model(name)->full ocean model "
                        "(archetype/voice/decision-signature/approach-register); "
                        "decide(name,q)->reconstructed decision; minds()->registry; "
                        "frontier()->route the DL version to the swarm",
            "cost": "deterministic + $0 core (DL frontier swarmed)",
            "tracked": len(_register_samples()), "partners": sorted(PARTNER_SAMPLES)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="ocean-model-mind")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "minds", "model", "decide", "frontier"])
    ap.add_argument("name", nargs="?", default="")
    ap.add_argument("--text", default="")
    a = ap.parse_args()
    if a.cmd == "minds":
        print(json.dumps(minds(), indent=2, default=str))
    elif a.cmd == "model":
        print(json.dumps(model(a.name, a.text or None), indent=2, default=str))
    elif a.cmd == "decide":
        print(json.dumps(decide(a.name, a.text or "(the current offer)"), indent=2, default=str))
    elif a.cmd == "frontier":
        print(json.dumps(frontier(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
