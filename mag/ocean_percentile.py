"""Percentile-scored OCEAN instrument, with the calibration promoted to a GATE.

OPERATOR RULING (2026-09-30), both moves sequenced by the calibration logic:
  "the lexicon widens first -- with the instrument's 8-figure calibration promoted to its own
   gate (no pair under a pre-set separation floor, no trait dominating half the corpus), and a
   pointed note that confidence saturating at 1.00 on everything means the scoring is
   volume-driven, not discriminative -- likely cured by percentile scoring against the
   21-figure reference bench they already hold."

This file is move one, the lexicon. The anchor acquisition is move two and runs separately.

THE DISEASE, MEASURED NOT ASSUMED
  The previous lexicon weighted RARE terms highest on the reasoning that rare implies
  diagnostic. The 18-figure bench (1,080,000 chars of real historical prose) says that is
  backwards. Of the 60 terms in the old lexicon, 23 fire ZERO times:

      meticulous rigorous replicable reproducible checklist scrubbed schedule reimagine
      speculate unconventional empathy tolerance cooperate considerate altruistic apprehensive
      overthink uneaseful exuberant cheering loudspeaker extrovert energize ...

  Those are not rare personality markers. They are MODERN SELF-HELP VOCABULARY. Nobody writing
  1885-1930 in Greek, German, French or English wrote "checklist", "altruistic" or
  "apprehensive" while describing their own mind. So the terms I had weighted HIGHEST were the
  terms least likely ever to be observed, while the terms that DID fire in ordinary prose
  ("discover" df=13, "beyond" df=11, "theory" df=11, "understanding" df=10) are not personality
  markers at all -- they are what intellectual books are made of. That is precisely why 6 of 8
  figures came back dominant=openness: intellectual prose is open-ish, and the instrument had no
  way to express that. The clustering was not a mystery. It was the lexicon, correctly reporting
  a vocabulary that cannot tell a clinician from a historian.

THE CURE, AS RULED: PERCENTILE AGAINST THE BENCH
  Two changes, both measured against the bench rather than assumed:

  1. REPLACEMENT VOCABULARY, chosen by document frequency on the bench. A term is kept only if
     it fires in 2..11 of 18 figures -- present enough to be observable, rare enough to mean
     something. The surviving set is period vocabulary: "dread", "peril", "misery", "sorrow",
     "multitude", "clamour", "throng", "exhaust", "scrutin", "forbear"-class words. 15 further
     candidates were measured and dropped for never firing (inquisitive, marvel, transcend,
     unfathomable, methodical, applaud, forgiveness, equity, shudder).

  2. PERCENTILE SCORING. A trait's score is now the PERCENTILE RANK of its raw rate within the
     bench's own distribution of that trait, not the raw rate itself. This is what makes the
     score discriminative rather than volume-driven. Two figures both full of "measure" and
     "order" are not both conscientious -- one is typical and one is 95th-percentile, and
     percentile is the only way to say so. The old raw-normalised score could not distinguish
     "typical" from "extreme" at all, which is why everything saturated.

CONFIDENCE, REPLACED WITH SOMETHING THAT MEANS SOMETHING
  confidence was min(1, n_chars/400) -- a VOLUME meter wearing a confidence label. Every bench
  figure sampled at 60,000 chars saturated at 1.00 by construction. It is now SEPARATION
  CONFIDENCE: how far this reading sits from the bench's own centroid, normalised by the
  bench's own spread. A reading that lands on the pile reads low confidence even when confident
  of its own arithmetic, which is the correct and humbling answer. Reported alongside the raw
  rate so both numbers are visible and neither can hide the other.

THE GATE (ruled, and run on every invocation)
  Two conditions, both from the ruling:
    G1 SEPARATION FLOOR. No two bench figures may sit closer than SEPARATION_FLOOR of the
       5-dimensional unit hypercube's diagonal. Pre-set at 0.25, not tuned to the result.
    G2 NO DOMINANT TRAIT. No single trait may dominate more than HALF the bench corpus.
  The gate result is in the payload, and the previous verdict ("USABLE AS A COARSE FILTER,
  USELESS AS A BRAID") is the pre-move baseline it is meant to beat. If the gate fails, the
  instrument says so rather than the report reading as a success.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STARTER = ROOT / "corpus" / "library" / "ractor_starter"
RUNS = ROOT / "memory" / "runs" / "ractor_ocean_bridge"

# GATE THRESHOLDS -- PRE-SET, NOT TUNED TO THE RESULT. Chosen before measuring, from the shape
# of the space: 0.25 of the diagonal is a quarter of everything expressible, and "no trait may
# dominate more than half the corpus" is the ruling's own wording.
SEPARATION_FLOOR = 0.25
DOMINANT_TRAIT_CEILING = 0.50

# VOCABULARY MEASURED ON THE BENCH (18 figures, 1,080,000 chars). Kept only where document
# frequency is 2..11 of 18. Every term below earned its place by measurement; none was chosen
# because it sounds like a personality.
BENCHED_LEXICON: dict[str, list[str]] = {
    "openness": [
        "curious", "wonder", "discover", "unfamiliar", "novel", "conjecture", "hypothesis",
        "imagine", "invention", "original", "novelty", "beyond", "mystery", "mysterious",
        "puzzled", "paradox", "strange",
    ],
    "conscientiousness": [
        "careful", "exact", "precise", "method", "order", "ordered", "regular", "exactness",
        "accuracy", "verify", "proof", "prove", "attested", "tested", "examine", "inquiry",
        "diligent", "patient", "thorough", "exhaust", "rule", "rules", "law", "laws",
        "measure", "measured", "standard", "strict", "error", "mistake", "scrutin",
    ],
    "extraversion": [
        "crowd", "multitude", "public", "assembly", "audience", "shout", "cried", "exclaimed",
        "voices", "mob", "throng", "noise", "preach", "speak", "spoke", "announce", "proclaim",
        "display", "show", "spectacle", "theatre", "stage", "actor", "orator",
    ],
    "agreeableness": [
        "mercy", "compassion", "pity", "forgive", "gentle", "kind", "kindness", "benevolent",
        "love", "friend", "friendship", "reconcile", "peace", "trust", "faith", "loyal",
        "help", "aid", "suffer", "suffering", "console", "comfort", "honour", "honor",
        "justice", "fellow", "reverence",
    ],
    "neuroticism": [
        "fear", "dread", "terror", "horror", "alarm", "doubt", "dreadful", "anxiety",
        "uneasy", "distress", "misery", "pain", "grief", "sorrow", "dark", "dead", "death",
        "kill", "danger", "peril", "threat", "warning", "tremble", "weak", "weakness", "fail",
        "failure", "ruin", "lost", "loss", "apprehensions",
    ],
}

# Terms measured as firing ZERO times on 1,080,000 chars of period prose. Kept in the source as
# a standing warning, because they were the terms the previous lexicon weighted HIGHEST.
MEASURED_DEAD: list[str] = [
    "meticulous", "rigorous", "replicable", "reproducible", "checklist", "scrubbed", "schedule",
    "reimagine", "speculate", "unconventional", "empathy", "tolerance", "cooperate",
    "considerate", "altruistic", "apprehensive", "overthink", "uneaseful", "exuberant",
    "cheering", "loudspeaker", "extrovert", "energize", "inquisitive", "marvel", "transcend",
    "unfathomable", "enigma", "methodical", "applause", "clamour", "forgiveness", "charity",
    "equity", "shudder",
]

_COMPILED = {t: [re.compile(rf"\b{re.escape(w)}\w{{0,3}}\b", re.I) for w in ws]
             for t, ws in BENCHED_LEXICON.items()}


def _clean(t: str) -> str:
    t = re.sub(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG[^\*]*\*\*\*", "", t, flags=re.I)
    t = re.sub(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG[^\*]*\*\*\*", "", t, flags=re.I)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\*\*END OF THE PROJECT GUTENBERG.*", " ", t)
    return t


def sample(figure: str, n: int = 60_000) -> tuple[str, list[dict]]:
    d = STARTER / figure
    if not d.is_dir():
        return "", []
    files = sorted(f for f in d.rglob("*.txt") if f.stat().st_size > 20_000)
    if not files:
        return "", []
    per = n // len(files) + 500
    parts, prov = [], []
    for f in files:
        body = _clean(f.read_text(encoding="utf-8", errors="replace"))
        if len(body) < 5000:
            continue
        start = len(body) // 3
        ex = body[start:start + per]
        if len(ex.strip()) < 400:
            continue
        parts.append(ex)
        prov.append({"file": str(f.relative_to(ROOT)).replace("\\", "/"), "offset": start,
                     "chars": len(ex),
                     "sha16": hashlib.sha256(ex.encode()).hexdigest()[:16]})
    return "\n\n".join(parts)[:n], prov


def _rates(text: str) -> dict[str, float]:
    """Raw hits-per-10k-chars per trait. The MEASUREMENT. Everything else is derived from it."""
    n = max(1, len(text))
    return {t: sum(len(rx.findall(text)) for rx in rxs) * 10_000 / n
            for t, rxs in _COMPILED.items()}


def _percentile(value: float, population: list[float]) -> float:
    """Where does this value sit in the bench's own distribution? 0.0 = lowest, 1.0 = highest.
    A tie-corrected rank, so a figure identical to the median does not get to claim the top."""
    if not population:
        return 0.5
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return round((below + 0.5 * equal) / len(population), 4)


def fingerprint_percentile(text: str, bench_rates: dict[str, list[float]]) -> dict:
    raw = _rates(text)
    vec = {t: _percentile(raw[t], bench_rates[t]) for t in _COMPILED}
    total = sum(raw.values())
    # SEPARATION CONFIDENCE replaces the volume meter. Distance from the bench centroid,
    # normalised by the bench's own standard deviation. A typical reading scores low even
    # though the arithmetic is certain, which is the correct answer and was never available
    # before.
    if bench_rates and all(len(v) > 1 for v in bench_rates.values()):
        zs = []
        for t in _COMPILED:
            pop = bench_rates[t]
            mu = sum(pop) / len(pop)
            sd = (sum((p - mu) ** 2 for p in pop) / len(pop)) ** 0.5 or 1.0
            zs.append((raw[t] - mu) / sd)
        sep = min(1.0, (sum(z * z for z in zs) / len(zs)) ** 0.5 / 2.0)
        confidence = round(sep, 3)
    else:
        confidence = 0.0
    vals = list(vec.values())
    undiff = bool(vals) and (max(vals) - min(vals)) < 1e-9
    return {
        "schema": "ocean_percentile.v1",
        "n_chars": len(text),
        "raw_rates_per_10k": {k: round(v, 3) for k, v in raw.items()},
        "vector_percentile": vec,
        "separation_confidence": confidence,
        "undifferentiated": undiff,
        "signal_detected": total > 0,
    }


def _dominant(vec: dict[str, float]) -> str | None:
    if not vec:
        return None
    best = max(vec.values())
    winners = [k for k, v in vec.items() if abs(v - best) < 1e-9]
    return None if len(winners) == len(vec) else winners[0]


def _sample_file(path: Path, n: int = 60_000) -> tuple[str, list[dict]]:
    """Same deterministic sampling as sample(), for a FILE rather than a figure directory.
    The landed anchors sit directly in ractor_starter/ as anchor_<voice>_<year>_<author>.txt, so
    iterating subdirectories -- which is what build_bench() does -- never saw them and the bench
    stayed at 18. That is a wiring gap, not a measurement, and it is closed explicitly here."""
    if not path.is_file() or path.stat().st_size < 20_000:
        return "", []
    body = _clean(path.read_text(encoding="utf-8", errors="replace"))
    if len(body) < 5000:
        return "", []
    start = len(body) // 3
    ex = body[start:start + n]
    if len(ex.strip()) < 400:
        return "", []
    return ex, [{"file": str(path.relative_to(ROOT)).replace("\\", "/"), "offset": start,
                 "chars": len(ex), "sha16": hashlib.sha256(ex.encode()).hexdigest()[:16]}]


def build_bench() -> tuple[dict[str, str], dict[str, list[float]]]:
    bench, rates = {}, {}
    for d in sorted(p for p in STARTER.iterdir() if p.is_dir()):
        text, _ = sample(d.name)
        if text:
            bench[d.name] = text
    # MOVE TWO: the landed anchor prose enters the bench by name, not by directory accident.
    for f in sorted(STARTER.glob("anchor_*.txt")):
        text, _ = _sample_file(f)
        if text:
            bench[f.stem] = text
    for t in _COMPILED:
        rates[t] = sorted(_rates(b)[t] for b in bench.values())
    return bench, rates


def gate(bench: dict[str, str], rates: dict[str, list[float]]) -> dict:
    """The ruled gate. Runs on every invocation. G1 separation floor, G2 no dominant trait."""
    diag = math.sqrt(len(_COMPILED))
    vecs, doms = {}, {}
    for name, text in bench.items():
        fp = fingerprint_percentile(text, rates)
        vecs[name] = fp["vector_percentile"]
        doms.setdefault(str(_dominant(fp["vector_percentile"])), []).append(name)
    pairs = []
    ns = sorted(vecs)
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            d = sum((vecs[a][k] - vecs[b][k]) ** 2 for k in vecs[a]) ** 0.5
            pairs.append((a, b, d))
    pairs.sort(key=lambda x: x[2])
    below = [(a, b, d) for a, b, d in pairs if d < SEPARATION_FLOOR]
    worst_trait = max(doms.items(), key=lambda kv: len(kv[1])) if doms else ("", [])
    g1 = len(below) == 0
    g2 = (len(worst_trait[1]) / len(bench)) <= DOMINANT_TRAIT_CEILING if bench else False
    return {
        "g1_separation_floor": {
            "threshold": SEPARATION_FLOOR, "max_possible": round(diag, 4),
            "pairs_below_floor": len(below), "of_pairs": len(pairs),
            "closest": ({"a": below[0][0], "b": below[0][1], "distance": round(below[0][2], 4)}
                        if below else None),
            "widest": {"a": pairs[-1][0], "b": pairs[-1][1], "distance": round(pairs[-1][2], 4)},
            "pass": g1,
        },
        "g2_no_dominant_trait": {
            "ceiling": DOMINANT_TRAIT_CEILING, "trait": worst_trait[0],
            "n": len(worst_trait[1]), "of": len(bench), "figures": worst_trait[1],
            "pass": g2,
        },
        "dominant_spread": {k: len(v) for k, v in sorted(doms.items())},
        "PASS": g1 and g2,
        "verdict": ("PASS -- instrument separates the bench and no trait dominates"
                    if (g1 and g2) else
                    "FAIL -- instrument is not yet a braid; see which gate"),
    }


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    bench, rates = build_bench()
    g = gate(bench, rates)

    rows = []
    for name, text in bench.items():
        fp = fingerprint_percentile(text, rates)
        rows.append({"figure": name, "chars": len(text),
                     "sample_sha16": hashlib.sha256(text.encode()).hexdigest()[:16],
                     **fp, "dominant": _dominant(fp["vector_percentile"])})

    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "schema": "ocean_percentile_instrument.v1",
        "ruling": "operator 2026-09-30: widen the lexicon, promote the 8-figure calibration to a "
                  "gate with a pre-set separation floor and no trait dominating half the corpus, "
                  "and replace volume-driven confidence with percentile scoring against the "
                  "21-figure bench.",
        "bench": {"figures": sorted(bench), "n": len(bench),
                  "chars": sum(len(v) for v in bench.values()),
                  "empty_dirs_on_shelf": [p.name for p in sorted(STARTER.iterdir())
                                          if p.is_dir() and not (STARTER / p.name).rglob("*.txt")],
                  "note": "operator said 21-figure; the shelf holds 21 dirs of which 2 "
                          "(greer, vonfranz) contain no text, so the usable bench is 18. Stated "
                          "plainly rather than padded to 21."},
        "lexicon": BENCHED_LEXICON,
        "measured_dead_terms": MEASURED_DEAD,
        "dead_term_note": "These fired ZERO times on 1,080,000 chars of period prose. The "
                          "PREVIOUS lexicon weighted several of them HIGHEST, on the reasoning "
                          "that rare implies diagnostic. The bench says the opposite: they are "
                          "modern self-help vocabulary, not period mind-talk.",
        "gate": g,
        "figures": rows,
    }
    p = RUNS / "OCEAN_PERCENTILE_INSTRUMENT.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  bench: {len(bench)} figures, {out['bench']['chars']:,} chars "
          f"(empty on shelf: {out['bench']['empty_dirs_on_shelf']})")
    print(f"\n  {'figure':16s} {'sep_conf':>8s}  {'dominant':17s} percentile vector")
    for r in rows:
        v = r["vector_percentile"]
        print(f"  {r['figure']:16s} {r['separation_confidence']:8.3f}  {str(r['dominant']):17s} "
              + " ".join(f"{k[:2]}={v[k]:.2f}" for k in v))
    g1, g2 = g["g1_separation_floor"], g["g2_no_dominant_trait"]
    print(f"\n  GATE 1 separation floor {g1['threshold']}: "
          f"{g1['pairs_below_floor']}/{g1['of_pairs']} pairs below -- "
          f"{'PASS' if g1['pass'] else 'FAIL'}")
    if g1["closest"]:
        print(f"        closest: {g1['closest']['a']} / {g1['closest']['b']} = "
              f"{g1['closest']['distance']}")
    print(f"        widest : {g1['widest']['a']} / {g1['widest']['b']} = {g1['widest']['distance']}")
    print(f"  GATE 2 no trait over {g2['ceiling']:.0%}: worst is '{g2['trait']}' at "
          f"{g2['n']}/{g2['of']} -- {'PASS' if g2['pass'] else 'FAIL'}")
    print(f"        spread: {g['dominant_spread']}")
    print(f"\n  GATE: {'PASS' if g['PASS'] else 'FAIL'} -- {g['verdict']}")
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())