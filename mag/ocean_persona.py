"""ocean_persona — map the OCEAN (Big Five) model variants as invariants we can LENS to create
personalities, tied to our high-signal creative corpus (behavioral analysis, scifi, fantasy).
Frontier research on neural cognition <-> biological neuroscience is routed to the swarm; the
OCEAN->personality invariant mapping is deterministic (self-stolen from personality_substrate +
persona_recall + narrative_engine).

Operator (2026-08-11): "frontier research about nural cognition mapped to biological nueroscience. i
want to map the ocean model variants as invariants we can lens to create personalities tied to high
signal training corpus from our creative sources from behavioral analysis to scifi whatever maps
well and is a beautiful measured step to our goal via our frameworks."

THE MAPPING (deterministic + $0; frontier research swarmed):
  OCEAN_INVARIANTS -> the Big Five as invariants: each trait -> a LENS + a PERSONA archetype + a
                      creative-corpus reference (scifi/fantasy/behavioral). The invariant IS the
                      trait's stable shape.
  lens_ocean(vec)  -> blend an OCEAN profile into a personality via the lenses + archetypes
                      (personality_substrate + persona_recall). Same OCEAN -> same personality
                      (deterministic, content-addressed).
  personalities()  -> the OCEAN variants as lensed personalities (the world's people).
  frontier()       -> route the neural-cognition <-> biological-neuroscience frontier research to
                      the swarm (dogfooding, honest provenance).

Schema: ocean_persona.v1 · deterministic + $0 mapping · swarm-routed frontier research
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ocean_persona.v1"

# ── OCEAN (Big Five) as invariants: trait -> lens + persona archetype + creative-corpus reference ──
# The invariant is the trait's stable shape; the lens is how we view it; the reference ties it to
# our high-signal creative corpus (scifi/fantasy/behavioral).
OCEAN_INVARIANTS = {
    "openness":      {"lens": "compiler/world", "archetype": "builder",
                      "ref": "science fiction's frontier-explorer (Dune's Mentat / Culture's Minds): "
                             "seeks novelty, imagines what could be, loves the unfamiliar"},
    "conscientiousness": {"lens": "swarm/detect", "archetype": "collective",
                          "ref": "the disciplined hive (Children of Time's uplift / behavioral "
                                 "analysis of routine): order, reliability, follow-through"},
    "extraversion":  {"lens": "wearable/surface", "archetype": "mirror",
                      "ref": "the bard's spark (the game's narrator / the social surface): energy "
                             "from engagement, outward, expressive"},
    "agreeableness": {"lens": "memory/invariant", "archetype": "self",
                      "ref": "the Watcher's care (egregore's consent/grounding invariants): "
                             "cooperation, harmony, trust"},
    "neuroticism":   {"lens": "security/guard", "archetype": "trickster",
                      "ref": "the shadow / the dark-forest watchfulness (Three-Body's Sophons, "
                             "behavioral anxiety signals): vigilance, sensitivity, guard against threat"},
}
# each invariant is content-addressed (the trait's stable, revisitable shape)
for _k in OCEAN_INVARIANTS:
    OCEAN_INVARIANTS[_k]["invariant_hash"] = hashlib.sha256(
        f"ocean-{_k}".encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def invariants() -> dict[str, Any]:
    """The OCEAN variants as invariants we can LENS — the stable trait shapes."""
    return {"ok": True, "schema": SCHEMA, "n": len(OCEAN_INVARIANTS),
            "invariants": OCEAN_INVARIANTS,
            "note": "each OCEAN trait is an invariant (stable, content-addressed) lensed through a "
                    "persona archetype + a creative-corpus reference"}


def lens_ocean(ocean: dict[str, float] | None = None) -> dict[str, Any]:
    """Blend an OCEAN profile into a personality via the lenses + archetypes. Deterministic:
    same OCEAN vector -> same personality (content-addressed)."""
    o = ocean or {"openness": 0.7, "conscientiousness": 0.7, "extraversion": 0.5,
                  "agreeableness": 0.6, "neuroticism": 0.3}
    # dominant traits = the strongest lenses -> the blended personality
    ranked = sorted(OCEAN_INVARIANTS, key=lambda k: -o.get(k, 0.5))
    dominant = ranked[0]
    # MEASURED (2026-09-29): sorted() on an all-equal vector returns the keys in their ORIGINAL
    # order, so ranked[0] is a stable alphabetical tie-break being reported as a finding. On a
    # neutral profile (every trait 0.5) this returned primary_trait "openness",
    # archetype "builder", lens "compiler/world" and a Dune-quoting voice reference -- a full,
    # confident personality assembled from a vector that says nothing.
    #
    # This is the THIRD instance of one defect at three depths, and it is worth naming as a
    # pattern rather than three bugs:
    #     1. mag/ocean_model_mind.fingerprint -- guard tested input LENGTH, not signal
    #     2. the same file's has_signal        -- guard tested denom AFTER its own `or 1.0` rescue
    #     3. lens_ocean here                  -- guard assumed a ranking exists on a tied vector
    # In every case a tie or an absence was silently converted into a confident specific answer,
    # and in every case the artefact was invisible because the output looked complete.
    #
    # The honest answer for an undifferentiated vector is to say so. The hash still works (it is
    # content-addressed on the vector itself), the blend list still describes the input, and the
    # caller gets an explicit reason instead of an invented archetype.
    vals = [float(o.get(k, 0.5)) for k in OCEAN_INVARIANTS]
    undifferentiated = bool(vals) and (max(vals) - min(vals)) < 1e-9
    if undifferentiated:
        return {"ok": True, "schema": SCHEMA, "ocean": o,
                "personality_hash": hashlib.sha256(
                    json.dumps({k: round(float(v), 3) for k, v in o.items()},
                               sort_keys=True).encode("utf-8")).hexdigest()[:16],
                "primary_trait": None, "primary_invariant": None,
                "undifferentiated": True,
                "undifferentiated_reason": (
                    "every OCEAN trait is equal, so no trait is primary and no archetype can be "
                    "derived. Returning one would be alphabetical tie-break dressed as a finding. "
                    "Supply a differentiated profile, or treat the caller as having no signal."),
                "blend": [], "voice": "",
                "note": "NO PERSONALITY DERIVED -- the input profile does not differentiate."}
    primary = OCEAN_INVARIANTS[dominant]
    # tie to the persona archetype (persona_recall) for the voice
    try:
        from mag import persona_recall
        pr = persona_recall.persona(primary["archetype"])
        voice = pr.get("voice", "")
    except Exception:
        voice = ""
    # the personality hash: same OCEAN -> same personality
    ph = hashlib.sha256(json.dumps({k: round(float(v), 3) for k, v in o.items()},
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {"ok": True, "schema": SCHEMA, "ocean": o, "personality_hash": ph,
            "primary_trait": dominant, "primary_invariant": primary,
            "blend": [{"trait": k, "archetype": OCEAN_INVARIANTS[k]["archetype"],
                       "strength": round(float(o.get(k, 0)), 3)}
                      for k in ranked],
            "voice": voice,
            "note": "OCEAN lensed into a personality: dominant traits -> the archetypes that shape "
                    "the voice; same OCEAN -> same personality (deterministic)"}


def personalities() -> dict[str, Any]:
    """The OCEAN variants as lensed personalities — the world's people (tied to our corpus)."""
    pure = []
    for trait in OCEAN_INVARIANTS:
        vec = {k: (1.0 if k == trait else 0.2) for k in OCEAN_INVARIANTS}
        pure.append({"trait": trait, **lens_ocean(vec)})
    return {"ok": True, "schema": SCHEMA, "n": len(pure), "personalities": pure,
            "note": "the OCEAN variants as people: each pure trait lensed into a personality"}


def frontier(*, enqueue: bool = True, surface: str = "ocean-persona") -> dict[str, Any]:
    """Route the frontier research (neural cognition <-> biological neuroscience) to the swarm.
    Dogfooding + honest provenance: the frontier answer is only real if a live seat produces it."""
    from mag import frontier_rib
    st = frontier_rib.seat_status()
    q = {"ok": False, "task_id": ""}
    if enqueue:
        try:
            from mag import swarm_surface
            goal = (f"FRONTIER RESEARCH [ocean_persona]: neural cognition mapped to biological "
                    f"neuroscience. We map the OCEAN (Big Five) variants as invariants lensed into "
                    f"personalities tied to our creative corpus. Research the neuroscience grounding "
                    f"of the Big Five (brain circuits: default-mode/executive/reward/threat) and how "
                    f"each maps to our lens+archetype mapping: {json.dumps(OCEAN_INVARIANTS)[:400]}. "
                    f"Refine our mapping with the strongest neural basis. Label each: "
                    f"NEURO: <circuit> / OCEAN: <trait> / LENS: <lens> / SHARPEN: <one step>. "
                    f"HONEST: only claim frontier output if a live seat produced it.")
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "any_seat_live": st.get("any_seat_live"),
            "note": "neural-cognition frontier research routed to the swarm; honest provenance"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "invariants()->OCEAN as lensable invariants; lens_ocean(vec)->blend into a "
                        "personality (deterministic); personalities()->the OCEAN people; "
                        "frontier()->route the neuroscience research to the swarm",
            "cost": "deterministic + $0 mapping (frontier research swarmed)",
            "n_traits": len(OCEAN_INVARIANTS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ocean-persona")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "invariants", "lens", "people", "frontier"])
    a = ap.parse_args()
    if a.cmd == "invariants":
        print(json.dumps(invariants(), indent=2, default=str))
    elif a.cmd == "lens":
        print(json.dumps(lens_ocean(), indent=2, default=str))
    elif a.cmd == "people":
        print(json.dumps(personalities(), indent=2, default=str))
    elif a.cmd == "frontier":
        print(json.dumps(frontier(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
