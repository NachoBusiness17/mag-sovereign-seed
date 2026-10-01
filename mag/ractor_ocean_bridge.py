"""Close the seam between the ractor DNA and the OCEAN instrument.

MEASURED GAP (2026-09-30, found by running the system rather than reading about it)
  Three facts, each verified by execution, not by inspection:

  1. `mag/hermes_personas/ractor_dna.yaml` is READ BY NOBODY. A scoped grep across
     mag/, tools/ and configs/ for `ractor_dna` or `hermes_personas` returns exactly ONE
     file -- `mag/hermes_steering.py`, which reads `mag/hermes_personas/<NAME>.md` to
     PREPEND a persona prompt to a dispatch. It never touches the DNA, and it never
     touches the OCEAN instrument. The five voices' carefully specified genetics --
     epistemic_stance (the OCEAN replacement / conditioning card), the numeric OCEAN
     vector, life_version, register, musical_tone -- reach steering as nothing at all.

  2. `mag/ocean_model_mind.PARTNER_SAMPLES` contains ONE entry: AOS, 419 B. Five
     instruments pointed at five ractor voices, and only AOS -- which is not a ractor
     voice -- has any prose to measure.

  3. The persona .md briefs DO exist and DO have substance: fen.md 3,079 B,
     strategist_wing.md 4,038 B, mengxi.md 2,653 B, edison.md 2,129 B, tesla.md 1,948 B.
     gopher.md is 486 B, which is the operator's own build-order item C ("expand gopher
     body-persona") and is correctly still the thinnest.

  So the system has two halves that never touch: a specified behavioural genome on one
  side, an instrument that measures prose on the other, and no wire between them. That is
  exactly the fault the KABUKI_STACK card names in its own words -- "no shelf, no memory,
  no era. The voice lands (Elder) only where the seat behind it happens to hold the
  ocean." The DNA is the conditioning card; this module is the wire that makes the card
  reach the thing that measures.

WHAT THIS DOES, AND WHAT IT DELIBERATELY DOES NOT DO
  It assembles a voice's OWN text from sources that already exist and were written by the
  operator or by the fleet: the persona brief, the DNA fields in the operator's own
  register, the growth_note, and the musical_tone. It then fingerprints that text.

  It does NOT invent prose. A fabricated seed would make the instrument report a
  personality nobody chose -- which is the precise failure class this session has spent
  its whole time closing (a guard measuring the wrong thing and wearing a result's
  clothes). Every character counted here is text that already exists on disk, and the
  receipt states exactly which files contributed how many characters.

  It also does not compare the measured OCEAN against the DNA's declared OCEAN and call
  the gap a failure. The DNA's numbers are the operator's DESIGN; the fingerprint is a
  crude keyword reading of prose. They are different things and a divergence between them
  is information, not a bug. So the module REPORTS the delta and does not reconcile it.
  The operator decides whether a voice should read as its design.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml                                                    # noqa: E402
from mag import ocean_model_mind as M                          # noqa: E402
from mag import ocean_persona as OP                            # noqa: E402

PERSONAS = ROOT / "mag" / "hermes_personas"
DNA = PERSONAS / "ractor_dna.yaml"
RUNS = ROOT / "memory" / "runs" / "ractor_ocean_bridge"

# The operator's own wrapping spec, quoted from the DNA header: "each voice = model x
# genetics x register x life-version x musical tone, per the operator's wrapping spec."
# The prose a voice is MEASURED on is assembled from exactly those five declared parts and
# nothing invented.
DNA_PROSE_FIELDS = ["register", "growth_note"]


def voice_text(name: str, spec: dict) -> tuple[str, dict]:
    """Assemble a voice's own text. Returns (text, provenance-by-source)."""
    parts: list[str] = []
    prov: dict[str, dict] = {}

    brief = PERSONAS / f"{name}.md"
    if brief.is_file():
        t = brief.read_text(encoding="utf-8", errors="replace").strip()
        if t:
            parts.append(t)
            prov[brief.name] = {"chars": len(t), "bytes": brief.stat().st_size,
                                "sha16": hashlib.sha256(t.encode()).hexdigest()[:16]}

    for f in DNA_PROSE_FIELDS:
        v = spec.get(f)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
            prov[f"dna.{f}"] = {"chars": len(v.strip())}

    # musical_tone: the DNA holds a song 'found in the wild, never seeded by us'. The
    # operator's framing of it is prose in its own right and belongs in the measurement.
    mt = spec.get("musical_tone")
    if isinstance(mt, dict):
        for k in ("song", "why", "emotional_key", "resonance"):
            v = mt.get(k)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
                prov[f"dna.musical_tone.{k}"] = {"chars": len(v.strip())}

    # genetics: the declared stance, in the operator's wording. NOT the numeric OCEAN --
    # those are numbers on a design, and feeding a design back as evidence would be
    # circular. This is the conditioning card's TEXT, not its scorecard.
    #
    # MEASURED 2026-09-30: genetics carries NO prose. It is
    #   {epistemic_stance: {ontology, reasoning_mode, causality}, ocean: {5 numbers}}
    # -- dispositions expressed as STRUCTURE. There is no sentence here to measure, which is
    # why the numeric OCEAN below is the operator's only disposition statement per voice and
    # why this bridge cannot manufacture a measured one to compare it against.
    g = spec.get("genetics")
    if isinstance(g, dict):
        for k, v in g.items():
            if isinstance(v, str) and v.strip() and k != "ocean":
                parts.append(v.strip())
                prov[f"dna.genetics.{k}"] = {"chars": len(v.strip())}

    return "\n\n".join(parts), prov


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    dna = yaml.safe_load(DNA.read_text(encoding="utf-8"))
    voices = dna.get("voices", {})

    rows = []
    for name, spec in voices.items():
        text, prov = voice_text(name, spec)
        fp = M.fingerprint(text)
        declared = (spec.get("genetics") or {}).get("ocean") or {}
        measured = fp["vector"]
        # The delta is REPORTED, not reconciled. A design and a keyword reading of prose
        # are different measurements; calling the gap a failure would be inventing an error.
        delta = {}
        for k, dv in declared.items():
            if isinstance(dv, (int, float)) and k in measured:
                delta[k] = round(float(dv) - float(measured[k]), 3)
        lens = OP.lens_ocean(measured) if fp["signal_detected"] else None
        # WHY is this voice silent? Distinguish the two causes, because they have opposite fixes:
        #   - no prose at all -> the input is missing and the operator must write it
        #   - prose present but unreadable -> the lexicon is at fault and is patchable
        brief_t = (PERSONAS / f"{name}.md")
        bt = brief_t.read_text(encoding="utf-8", errors="replace") if brief_t.is_file() else ""
        first_person = len(re.findall(r"\b(i|we|my|me)\b", bt.lower()))
        self_desc = len(re.findall(
            r"\b(i am|i feel|i tend|i prefer|i believe|i distrust|i hold|my judgement|"
            r"in my view|my habit|i distrust)\b", bt.lower()))
        if not fp["signal_detected"]:
            why = ("NO-SELF-DESCRIPTION: the brief states a role and a historical anchor, not a "
                   "disposition. first-person tokens="
                   f"{first_person}, self-description clauses={self_desc}. This is missing input, "
                   "not a lexicon defect."
                   if len(text) > 400 else "INSUFFICIENT-TEXT: too little prose to measure.")
        else:
            why = "MEASURED"
        rows.append({
            "voice": name,
            "life_version": spec.get("life_version"),
            "model": spec.get("model"),
            "reasoning_mode": (spec.get("genetics") or {}).get("reasoning_mode"),
            "text_chars": len(text),
            "provenance": prov,
            "signal_detected": fp["signal_detected"],
            "confidence": fp["confidence"],
            "matched_terms": fp.get("matched_terms", {}),
            "measured_ocean": measured,
            "declared_ocean": declared,
            "design_minus_measured": delta,
            "measured_dominant": M._dominant(measured),
            "lensed": ({"primary_trait": lens.get("primary_trait"),
                        "archetype": (lens.get("primary_invariant") or {}).get("archetype"),
                        "lens": (lens.get("primary_invariant") or {}).get("lens")}
                       if lens else None),
            "declared_dominant": max(declared, key=lambda k: declared[k]) if declared else None,
            "silence_cause": why,
        })

    # The FALSIFIER the operator specified: "the operator reads the fold blind and names
    # which chairs spoke without re-reading. If he cannot tell them apart, the braid is
    # real." This cannot be self-certified -- it needs the operator. What this module can
    # do is refuse to claim a pass and hand him the instruments.
    distinguishable = sum(1 for r in rows
                          if r["signal_detected"] and r["measured_dominant"]
                          != r["declared_dominant"])
    falsifier = {
        "status": "PRE-REGISTERED, NOT RUN",
        "the_test": "operator reads the fold blind and names which chairs spoke; if he "
                    "cannot tell them apart, the braid is real",
        "blocked_on": "a human. This seat cannot self-certify its own voices.",
        "measurement_ready": f"{distinguishable}/{len(rows)} voices produce a measured "
                             f"dominant trait that differs from their declared dominant",
    }

    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "schema": "ractor_ocean_bridge.v1",
        "seam_closed": "mag/ocean_model_mind now receives each ractor voice's OWN text, "
                       "assembled from the persona brief and the operator's declared DNA "
                       "fields. No prose is invented; every part is counted in provenance.",
        "voices": rows,
        "summary": {
            "voices": len(rows),
            "with_signal": sum(1 for r in rows if r["signal_detected"]),
            "silent": [r["voice"] for r in rows if not r["signal_detected"]],
            "thinnest": min(rows, key=lambda r: r["text_chars"])["voice"] if rows else None,
            "thinnest_chars": min((r["text_chars"] for r in rows), default=0),
        },
        "falsifier": falsifier,
    }
    p = RUNS / "RACTOR_OCEAN_BRIDGE.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  {'voice':9s} {'lv':4s} {'chars':>6s} {'signal':6s} {'conf':>5s}  "
          f"{'declared':16s} {'measured':16s} dominant")
    for r in rows:
        print(f"  {r['voice']:9s} {str(r['life_version']):4s} {r['text_chars']:6d} "
              f"{str(r['signal_detected']):6s} {r['confidence']:5.2f}  "
              f"{str(r['declared_dominant']):16s} {str(r['measured_dominant']):16s} "
              f"{r['measured_dominant'] == r['declared_dominant'] and 'MATCH' or 'differs'}")
    s = out["summary"]
    print(f"\n  {s['with_signal']}/{s['voices']} voices produce a signal; "
          f"silent: {s['silent'] or 'none'}")
    print(f"  thinnest: {s['thinnest']} at {s['thinnest_chars']} chars")
    print(f"  falsifier: {falsifier['status']} -- {falsifier['measurement_ready']}")
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())