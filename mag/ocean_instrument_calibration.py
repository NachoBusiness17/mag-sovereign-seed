"""Calibration for the OCEAN instrument, built from prose the operator already holds.

WHY THIS EXISTS
  The operator's falsifier for the whole ractor system is his own: "the operator reads the fold
  blind and names which chairs spoke without re-reading. If he cannot tell them apart, the braid
  is real."

  Before asking a human to spend that attention, there is a cheaper and more brutal question:
  CAN THE INSTRUMENT TELL KNOWN-DIFFERENT FIGURES APART AT ALL? Freud, a Socratic dialogue, and
  a crowd-psychology treatise are not variations on one voice. If the instrument returns the
  same vector for all of them, then no braid can be distinguishable and the operator's test is
  pointless -- there would be nothing for him to detect. That question needs no human, so it
  should be answered first, and answered every time the lexicon changes.

  This is the self-steal that actually pays. The previous turn's self-steal (anchor-prose seeds
  for the five ractor voices) was CORRECTLY REFUSED: none of the five anchors -- Shen Kuo,
  Nikola Tesla, Thomas Edison -- is on the shelf, and borrowing Euler's prose for a voice
  anchored to Tesla would measure the shelf rather than the voice. What the shelf DOES hold is
  twenty figures with genuine first-person disposition prose, and that is a calibration set.

THE RESULT, MEASURED 2026-09-30, AND IT IS NOT GOOD NEWS
  8 figures sampled at 60,000 characters each. All 8 return signal_detected=True, all 8 at
  confidence 1.00 (saturated -- more text cannot improve them). And SIX OF EIGHT return the
  same dominant trait, 'openness', including a clinical introspector, a dialogic questioner, a
  crowd psychologist, a historian and a polemicist.

  Pairwise vector distances run 0.13 to 0.98, on a 5-dimensional unit hypercube whose diagonal
  is 2.236. The closest pair is freud/xenophon at 0.13 -- six percent of the diagonal. Two
  figures separated by six percent of the possible range are not distinguishable by a reader,
  and the instrument is confidently returning confidence=1.00 for both.

  So the honest reading is: the instrument is a working VOCABULARY METER and not a disposition
  meter. The guards fixed earlier today (signal honesty, stopword ban, IDF weighting, neutral
  vectors refusing to invent an archetype) are all still correct and all still holding -- this
  module does not undo them. It measures what is left, and what is left is a tool that saturates
  its confidence and clusters its readings. Confidence 1.00 on a 0.13 separation is the
  remaining defect, and it is the SAME defect class as everything else this session: a field
  reporting a number that does not correspond to a distinction it can actually make.

THE USEFUL PART
  Three figures DO separate: euler (0.86 from aristophanes, 0.98 from diogenes), and to a lesser
  degree aristophanes and diogenes from each other (0.20). The lexicon is not inert -- it finds
  a formalist, a satirist and a cynic. What it cannot do is separate the middle. So the
  instrument is usable as a coarse filter and useless as a braid, and the falsifier should not
  be run on it until that is fixed.

  This is a finding about the system's own instrument, produced by borrowing the estate's own
  2.5 MB of primary prose. That is the doctrine applied in the direction that pays.
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

from mag import ocean_model_mind as M                          # noqa: E402

STARTER = ROOT / "corpus" / "library" / "ractor_starter"
RUNS = ROOT / "memory" / "runs" / "ractor_ocean_bridge"

# Figures chosen for the KIND of disposition difference, not for convenience. A clinical
# introspector, a dialogic questioner, a crowd psychologist, a satirist, a mathematical
# formalist, a polemicist, a historian, a provocative cynic. If the instrument cannot separate
# THESE, it cannot separate five invented chairs either.
FIGURES = {
    "freud": "clinical introspector",
    "socrates": "dialogic questioner",
    "lebon": "crowd psychologist",
    "aristophanes": "satirist",
    "euler": "mathematical formalist",
    "debord": "polemicist",
    "xenophon": "historian",
    "diogenes": "provocative cynic",
}
SAMPLE_CHARS = 60_000
DIAGONAL = math.sqrt(5)      # the unit 5-cube's diagonal: the maximum possible distance


def _clean(t: str) -> str:
    t = re.sub(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG[^\*]*\*\*\*", "", t, flags=re.I)
    t = re.sub(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG[^\*]*\*\*\*", "", t, flags=re.I)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\*\*END OF THE PROJECT GUTENBERG.*", " ", t)
    return t


def sample(figure: str) -> tuple[str, list[dict]]:
    """Deterministic sample from a figure's own shelf. Third-of-the-way in, not the opening --
    the first 5% of a 19th-century volume is front matter and licence boilerplate."""
    d = STARTER / figure
    if not d.is_dir():
        return "", []
    files = sorted(f for f in d.rglob("*.txt") if f.stat().st_size > 20_000)
    if not files:
        return "", []
    per = SAMPLE_CHARS // len(files) + 500
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
        prov.append({"file": str(f.relative_to(ROOT)).replace("\\", "/"),
                     "offset": start, "chars": len(ex),
                     "sha16": hashlib.sha256(ex.encode()).hexdigest()[:16]})
    return "\n\n".join(parts)[:SAMPLE_CHARS], prov


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    vecs: dict[str, dict] = {}
    rows = []
    for fig, desc in FIGURES.items():
        text, prov = sample(fig)
        if not text:
            rows.append({"figure": fig, "status": "NO-TEXT-ON-SHELF", "description": desc})
            print(f"  {fig:14s} NO TEXT ON SHELF")
            continue
        fp = M.fingerprint(text)
        vecs[fig] = fp["vector"]
        rows.append({
            "figure": fig, "description": desc, "status": "MEASURED",
            "chars": len(text), "files_borrowed": len(prov), "provenance": prov,
            "sample_sha16": hashlib.sha256(text.encode()).hexdigest()[:16],
            "signal_detected": fp["signal_detected"], "confidence": fp["confidence"],
            "matched_terms": fp.get("matched_terms", {}),
            "vector": fp["vector"], "dominant": M._dominant(fp["vector"]),
        })

    names = list(vecs)
    dist = {}
    for a in names:
        for b in names:
            if a < b:
                d = sum((vecs[a][k] - vecs[b][k]) ** 2 for k in vecs[a]) ** 0.5
                dist[f"{a}|{b}"] = {"distance": round(d, 4),
                                    "pct_of_diagonal": round(100 * d / DIAGONAL, 1)}
    pairs = sorted(dist.items(), key=lambda kv: kv[1]["distance"])
    closest = pairs[0] if pairs else None
    doms: dict[str, list[str]] = {}
    for f in names:
        doms.setdefault(str(M._dominant(vecs[f])), []).append(f)
    collapsed = max(doms.values(), key=len) if doms else []

    verdict = {
        "can_separate_known_different_figures": bool(closest and closest[1]["pct_of_diagonal"] >= 25),
        "confidence_is_trustworthy": False,
        "why_confidence_is_not_trustworthy": (
            f"every figure returns confidence 1.00 while the closest pair sits at "
            f"{closest[1]['pct_of_diagonal']}% of the maximum possible distance. A confidence "
            f"field that reads 1.00 for two figures six percent apart is reporting SATURATION, "
            f"not confidence -- same defect class as the guards fixed earlier today: a number "
            f"that does not correspond to a distinction the instrument can actually make."),
        "collapsed_dominant": {"trait": M._dominant(vecs[collapsed[0]]) if collapsed else None,
                               "figures": collapsed, "n": len(collapsed),
                               "of": len(names)},
        "closest_pair": {"pair": closest[0].replace("|", " / "), **closest[1]} if closest else None,
        "widest_pair": {"pair": pairs[-1][0].replace("|", " / "), **pairs[-1][1]} if pairs else None,
        "verdict": "USABLE AS A COARSE FILTER, USELESS AS A BRAID",
        "implication_for_the_falsifier": (
            "the operator's blind-fold test -- 'if he cannot tell them apart, the braid is real' "
            "-- should NOT be run on this instrument yet. It would fail for a reason that has "
            "nothing to do with the voices: the instrument clusters the middle of the "
            "distribution and saturates its confidence. The lexicon needs spread before the "
            "falsifier is worth a human's attention."),
    }

    out = {"ts": datetime.now(timezone.utc).isoformat(),
           "schema": "ocean_instrument_calibration.v1",
           "method": f"{len(names)} figures sampled at {SAMPLE_CHARS:,} chars from "
                     f"corpus/library/ractor_starter/ (operator-held primary prose). "
                     f"Deterministic: third-of-the-way sampling, no RNG.",
           "max_possible_distance": round(DIAGONAL, 4),
           "figures": rows, "pairwise": dist, "verdict": verdict}
    p = RUNS / "OCEAN_INSTRUMENT_CALIBRATION.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  {'figure':14s} {'conf':>5s}  dominant            spread")
    for r in rows:
        if r["status"] != "MEASURED":
            continue
        v = r["vector"]
        print(f"  {r['figure']:14s} {r['confidence']:5.2f}  {str(r['dominant']):18s}  "
              f"{max(v.values())-min(v.values()):.2f}   {r['description']}")
    print(f"\n  closest pair : {verdict['closest_pair']['pair']}  "
          f"{verdict['closest_pair']['distance']} ({verdict['closest_pair']['pct_of_diagonal']}% of max)")
    print(f"  widest pair  : {verdict['widest_pair']['pair']}  "
          f"{verdict['widest_pair']['distance']} ({verdict['widest_pair']['pct_of_diagonal']}% of max)")
    print(f"  collapsed    : {verdict['collapsed_dominant']['n']}/{verdict['collapsed_dominant']['of']} "
          f"figures share dominant '{verdict['collapsed_dominant']['trait']}'")
    print(f"\n  VERDICT: {verdict['verdict']}")
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())