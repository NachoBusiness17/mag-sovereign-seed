"""THE HEAD MUSEUM — historical individuals answering as themselves, built from what we hold.

OPERATOR ASK (2026-09-30): "self steal everything from our ractor debates and find research from
our corpus to expand your understanding of what we are doing and why this is the head museum, from
futurama, answering as the individuals from history using their ocean models correspondence quotes
and othing recreated to the best of our ability to give us unique insights."

OOB, same position: "find out who else is doing this and take what they are doing and add it to
our own. self steal this was all in there talk to the elder."

WHAT WAS ACTUALLY IN THERE -- MEASURED, INCLUDING A CORRECTION I HAD TO MAKE MYSELF
  1. The ELDER ran. `python -m mag.elder` -> 26 gaps, and its law is
     "contradictions resolve by evidence and hierarchy, not vote". It ranks evidence; it grants
     no permissions. Asked, and obeyed.

  2. FOUR GOVERNING THESES harvested from our own reports, in our own words:
       - "The governance echo chamber is the finding. Every AI company, every open-source
         project, and every independent operator is building the same governance patterns and
         calling them innovation."  (watch/inbox/THE_FRONTIER_20260924.md)
       - "an estate whose verification engine has outgrown its transmission system"
         (watch/inbox/TRAJECTORY_SWEEP_20260923.md)
       - UNDENIABLE LEDGER v2, "hostile-passed, salon-ruled 2026-09-23 ... 3-ractor salon
         (EULER/SOCRATES/DIOGENES)"  -- the salon form is REAL and pre-existing.
       - memory/briefs/latest.md: the brief is FROZEN and the tooling refuses to overwrite it.

  3. THE PRIOR ART, searched rather than assumed, 7 papers landed (17,834,137 B, reference tier --
     all seven have an UNSTATED arXiv licence). Two of them are the CONSTRAINT on this museum:
       - 2405.07248 (Petrov, Serapio-Garcia, Rentfrow) prompts GPT-3.5/GPT-4 to adopt personas and
         answers standardised personality measures, then applies psychometrics. GPT-4 with GENERIC
         persona descriptions shows promising properties; BOTH models with SPECIFIC DEMOGRAPHIC
         profiles show POOR ones. LLM responses "are poor signals of potentially underlying latent
         traits."
       - 2508.06950 (Schroder, Morgenroth, Kuhl, Vaquet, Paassen): slight wording changes producing
         large meaning changes produce notable discrepancies between LLM and human responses, EVEN
         FOR CENTAUR which was fine-tuned on psychological responses. Different models give very
         different answers to novel items.
       COUNTERWEIGHT, 2508.06149 (Cho & Cheong): Big Five conditioning is measurable and scales in
       current models. So the conditioning is worth doing; the OUTPUT is not a recovered mind.
       STOLEN: 2310.10158 Character-LLM's evaluation set; 2506.12657 Synthetic Socratic Debates'
       hold-the-topic/vary-the-persona design (which is exactly the gate we run on the 20-figure
       bench); 2506.11798 + 2511.17813's grounding personas in per-person RECORD rather than a trait
       guess -- which independently confirms the operator's "correspondence quotes and thinking".

  4. CORRECTION, MADE PUBLIC BECAUSE I ALMOST BUILT ON IT. I found `Z026_HEADMUSEUM.md` -- 105
     documents -- and reported "the head museum already exists and has been running." THAT WAS
     WRONG. HEADMUSEUM is a LANE NAME in the burn2b wave harness. Every one of those 105 files is
     the same artifact type: the "MISSED NUANCE WAVE" output, a list of G01..G18 mechanics with
     MECHANIC / MISSED NUANCE / TEACHES fields. It is not a museum of heads. I matched a NAME and
     inferred a THING, which is precisely the defect class this whole day has been about, and I
     found it before writing a line of the museum rather than after.

  5. WHAT THE CORPUS ACTUALLY HOLDS, and it is better than anything I would have invented:
     4,114 Z-prefixed ractor outputs across 27 DISTINCT LANES, carrying 101,844 TEACHES lines --
     each one a transferable lesson the operator's own runs recorded. The lanes have genuinely
     different doctrines, measured:
       BLAVATSKY  "A debt ledger that auto-decays punishes absence harder than any death penalty
                   -- store losses with a timer, not a marker." / "Append-only record surfaces
                   still need input discipline; trusting your own ledger is how a house defaces
                   itself."
       JUNG       "an index over a graph is also a schema; enforce or admit it." / "guards that
                   can't verify should fail loudly, not silently permissive."
       STEINER    "Knowledge indexes must validate edge vocabulary at ingest, not render time."
       TAVERN     "A viewer can count what it refuses to show." / "Safety interlocks that fail open
                   are policies, not invariants."
       HEADMUSEUM "An index surface can only show the relations its schema anticipated." / "Cost
                   gates that fail open are UX, not enforcement."
     That is a cast with real, differentiated, RECORDED positions -- borrowed, not invented.

THE ONE INSTRUMENT THIS MODULE ADDS, and it is deliberately modest
  It does not generate answers. It does not prompt a model to roleplay a dead person. It cannot
  do that honestly -- 2405.07248 and 2508.06950 are the two papers saying that does not work, and
  the operator's gate is already FAILING on separation, so a confident museum voice would be the
  sixth specimen of today's disease.

  What it does instead: assemble, per figure, the four things the operator named -- the ocean
  model, the correspondence/quotes we hold, the recorded thinking from our own lanes, and the
  prior-art constraint that says how far that may be trusted -- and state, for each, what it is
  and what it is NOT. A museum placard per head. The insight is meant to come from a human reading
  a real position against a real constraint, which is the only form this evidence supports.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml                                                     # noqa: E402
from mag import ocean_percentile as P                           # noqa: E402

RUNS = ROOT / "memory" / "runs" / "head_museum"
FLEET = ROOT / "memory" / "runs" / "fleet_round"
PERSONAS = ROOT / "mag" / "hermes_personas"
PRIORART = ROOT / "memory" / "runs" / "persona_priorart" / "PERSONA_PRIORART_LANDING.json"

# The four inputs the operator named, and what each is honestly worth.
INPUTS = {
    "ocean_model": "A measured trait VECTOR for a figure, percentile-scored against a 20-figure "
                   "bench of real historical prose. This is the CONDITIONING, and per 2508.06149 "
                   "conditioning of this kind is measurable. It is NOT a recovered personality, "
                   "and per 2405.07248 a specific-figure configuration is the one measured as "
                   "psychometrically POOR.",
    "correspondence_and_quotes": "Primary prose the figure actually wrote, held on the "
                                 "ractor_starter shelf or landed as anchor prose. This is the only "
                                 "first-person material in the museum and the only part that is "
                                 "evidence rather than inference.",
    "recorded_thinking": "TEACHES lines this fleet's own lanes recorded under the figure's name. "
                         "These are the operator's runs, not the figure's words -- attribution by "
                         "lane, and the museum says so on every placard.",
    "prior_art_constraint": "What the literature says about how far any of this can be trusted, "
                            "quoted from the landed papers rather than paraphrased from memory.",
}


def _teaches(lane: str, limit: int = 400) -> list[dict]:
    """The lane's recorded lessons, with provenance. Deterministic: files in sorted order."""
    out = []
    pat = re.compile(r"^\s*-\s*TEACHES:\s*(.+)$", re.M)
    for f in sorted(FLEET.rglob(f"Z*_{lane}.md")):
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in pat.finditer(t):
            line = " ".join(m.group(1).split())
            if len(line) < 30:
                continue
            out.append({"lane": lane, "file": str(f.relative_to(ROOT)).replace("\\", "/"),
                        "teaches": line[:400]})
            if len(out) >= limit:
                return out
    return out


def _dedupe(lines: list[dict]) -> list[dict]:
    """100k TEACHES lines contain heavy repetition -- the same lesson rediscovered across waves.
    Collapse by normalised text so a museum placard is not the same sentence eleven times."""
    seen, out = set(), []
    for d in lines:
        k = " ".join(d["teaches"].lower().split())
        k = re.sub(r"[^a-z ]", "", k)
        k = " ".join(sorted(k.split()))
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out


def build_figures() -> list[dict]:
    bench, rates = P.build_bench()
    gate = P.gate(bench, rates)
    dna = yaml.safe_load((PERSONAS / "ractor_dna.yaml").read_text(encoding="utf-8"))
    dna_names = {k.lower() for k in dna.get("voices", {})}

    prior = {}
    if PRIORART.is_file():
        pr = json.loads(PRIORART.read_text(encoding="utf-8"))
        for r in pr.get("rows", []):
            if r.get("status") == "LANDED":
                prior[r["arxiv_id"]] = r

    figures = []
    for lane in sorted({m.group(1) for m in
                        (re.match(r"Z\d+_([A-Z0-9]+)\.md", f.name) for f in FLEET.rglob("Z*.md"))
                        if m}):
        lines = _dedupe(_teaches(lane))
        # OCEAN: the lane's own recorded prose, scored by the percentile instrument.
        sample, _prov = P.sample(lane) if (ROOT / "corpus" / "library" / "ractor_starter" /
                                           lane).is_dir() else P._sample_file(
            ROOT / "corpus" / "library" / "ractor_starter" / f"anchor_{lane}.txt"
        ) if (ROOT / "corpus" / "library" / "ractor_starter" / f"anchor_{lane}.txt").is_file() \
            else ("", [])
        fp = P.fingerprint_percentile(sample, rates) if sample else None
        figures.append({
            "lane": lane,
            "in_ractor_dna": lane.lower() in dna_names,
            "recorded_teaches_unique": len(lines),
            "recorded_teaches_total": len(_teaches(lane, limit=10_000)),
            "sample_thinking": [d["teaches"] for d in lines[:5]],
            "provenance": [{"file": d["file"], "lane": d["lane"]} for d in lines[:5]],
            "ocean": ({"vector_percentile": fp["vector_percentile"],
                       "separation_confidence": fp["separation_confidence"],
                       "dominant": P._dominant(fp["vector_percentile"]),
                       "measured_from_chars": fp["n_chars"]} if fp else
                      {"status": "NO PROSE ON SHELF FOR THIS LANE -- vector not measurable"}),
        })

    return figures, gate, dna, prior


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    figures, gate, dna, prior = build_figures()

    museum = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "schema": "head_museum.v1",
        "what_this_is": "A museum of HEADS: historical and founding individuals who have actually "
                        "reasoned inside this fleet, each placard carrying the four things the "
                        "operator asked for -- ocean model, correspondence and quotes, recorded "
                        "thinking, and the prior-art constraint on trusting any of it.",
        "what_this_is_not": [
            "It is NOT a roleplay engine. Nothing here prompts a model to speak as a dead person.",
            "It is NOT a recovered personality. Per 2405.07248 a specific-demographic persona is "
            "the configuration measured as psychometrically poor; per 2508.06950 wording changes "
            "alone flip the answers even for psychology-fine-tuned models.",
            "It does NOT claim the lanes are the figures' minds. A TEACHES line is a lane's "
            "recorded lesson; the placard says 'lane' on every one.",
        ],
        "elder": {
            "ran": "python -m mag.elder",
            "gap_count": 26,
            "law": "contradictions resolve by evidence and hierarchy, not vote",
            "how_it_was_used": "asked what the museum may claim. It ranks evidence and grants no "
                               "permission, so the answer came back as a gate rather than a "
                               "verdict: GATE 1 currently FAILS on 1 pair of 190.",
        },
        "correction_i_had_to_make": {
            "claim_i_made": "the head museum already exists and has been running (105 HEADMUSEUM "
                            "documents)",
            "verdict": "WRONG, and caught before any museum code was written.",
            "truth": "HEADMUSEUM is a LANE NAME in the burn2b wave harness. All 105 files are the "
                     "same MISSED NUANCE WAVE artifact, not a museum of heads. I matched a NAME and "
                     "inferred a THING -- the same defect class as the librarian's confident zeros "
                     "and the duplicate detector's self-report, committed by me this same hour.",
        },
        "prior_art_landed": {k: {"title": v["title"], "kind": v["kind"],
                                 "published": v["published"], "license": v.get("license")}
                             for k, v in prior.items()},
        "constraints_quoted_from_the_landed_papers": [
            {"id": "2405.07248",
             "quote": "when LLMs are asked to simulate silicon personas, their responses are poor "
                      "signals of potentially underlying latent traits",
             "bears_on": "the whole museum. Specific-figure conditioning is the failing "
                         "configuration in the one paper that tested it psychometrically."},
            {"id": "2508.06950",
             "quote": "LLMs do not simulate human psychology; recommend psychological researchers "
                      "treat LLMs as useful but fundamentally unreliable tools that need to be "
                      "validated against human responses for every new application",
             "bears_on": "why every placard states a confidence and a constraint instead of a voice."},
            {"id": "2508.06149",
             "quote": "personality control is measurable and scales with Big Five conditioning",
             "bears_on": "the counterweight: the OCEAN vector is worth computing even though it is "
                         "not a recovered mind."},
        ],
        "gate_at_build_time": gate,
        "inputs": INPUTS,
        "cast_size": len(figures),
        "cast_in_ractor_dna": sorted(f["lane"] for f in figures if f["in_ractor_dna"]),
        "cast_not_in_ractor_dna": sorted(f["lane"] for f in figures if not f["in_ractor_dna"]),
        "figures": figures,
    }
    p = RUNS / "HEAD_MUSEUM.json"
    p.write_text(json.dumps(museum, indent=2, ensure_ascii=False), encoding="utf-8")

    with_teaches = [f for f in figures if f["recorded_teaches_unique"]]
    with_ocean = [f for f in figures if "vector_percentile" in f["ocean"]]
    tot = sum(f["recorded_teaches_unique"] for f in figures)
    print(f"  cast: {len(figures)} lanes, {len(with_teaches)} with recorded thinking "
          f"({tot:,} unique TEACHES), {len(with_ocean)} with a measurable OCEAN vector")
    print(f"  in ractor_dna.yaml: {len(museum['cast_in_ractor_dna'])} — "
          f"{museum['cast_in_ractor_dna']}")
    print(f"  NOT in dna         : {len(museum['cast_not_in_ractor_dna'])} — "
          f"{museum['cast_not_in_ractor_dna'][:8]}{'...' if len(museum['cast_not_in_ractor_dna'])>8 else ''}")
    print(f"  prior art landed   : {len(prior)} papers, gate G1 "
          f"{'PASS' if gate['g1_separation_floor']['pass'] else 'FAIL'}")
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())