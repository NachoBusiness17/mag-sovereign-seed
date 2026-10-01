"""SELF-STEAL: give each ractor voice the register of its own anchor, from prose already held.

OPERATOR ASK (2026-09-30): "self steal"

THE DOCTRINE BEING APPLIED
  Do not build what already exists. Do not invent a seed. Find the best implementation on disk
  and borrow it. A seat once proposed building a secret scanner three separate times before
  checking that B2_73_secret_scan.py and tools/secret_gate.py already existed.

WHAT WAS ALREADY ON DISK, AND NOT USED
  The last turn established, by measurement, that 4 of 5 ractor voices produce NO signal, and
  that the cause is not a lexicon defect: the persona briefs are historical-anchor and role
  documents, not disposition prose. First-person self-description across all five briefs: ZERO.
  The instrument reads disposition; nothing hands it any.

  Meanwhile the estate already holds the answer, and I had never opened it:

      corpus/library/ractor_starter/   21 NAMED FIGURE DIRECTORIES, ~2.5 MB of PRIMARY PROSE
      jung, freud, lebon, lippmann, wallas, innis, greer, weil, vonfranz, bernays, debord,
      aristophanes, socrates, xenophon, plato, diogenes, heraclitus_parmenides, euler,
      goldbach, plus youtube_transcripts

  Every ractor voice is ANCHORED to a historical figure. Mengxi is anchored to Shen Kuo. Edison
  to Edison. That figure's own words are on this shelf. So the honest seed is not prose I write
  about a person -- it is prose THE PERSON WROTE, which the operator already chose and landed.

  That is what "self steal" means here, and it is a stronger claim than my earlier plan: a
  borrowed register is evidence, not a costume.

HOW MUCH PROSE, AND WHY THAT AMOUNT
  Enough for the instrument to see a distribution rather than a slogan. Measured behaviour: the
  fingerprint reads only the first 60,000 characters (see ocean_model_mind.fingerprint, probe =
  text[:60000]), and confidence scales with min(1, n_chars/400). So a few thousand characters
  per voice saturates confidence while staying auditable by a human who can read it.

  Sampled from MULTIPLE files per figure, spread across each figure's shelf, so the sample is
  not one chapter's mood. Deterministic: stride sampling, no RNG, so re-running gives the same
  seed and the same measurement. A seed that changed on every run would be unfalsifiable.

PROVENANCE IS THE POINT
  Every voice's seed records, per borrowed file, the path, the byte offset, the characters
  taken, and the sha256 of the excerpt. So any number in the JSON can be traced back to a
  specific passage in a specific file the operator already holds. That is the difference
  between a borrow and a fabrication.
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
STARTER = ROOT / "corpus" / "library" / "ractor_starter"
RUNS = ROOT / "memory" / "runs" / "ractor_ocean_bridge"

# voice -> (anchor figure directory on the shelf, what the brief says the anchor is)
# The mapping is EXPLICIT and each one is verified present-or-absent at run time. An unmapped
# voice is reported as unmapped; it is never silently pointed at a neighbouring figure, because
# borrowing Freud's register for a voice anchored to Shen Kuo is a costume, not a borrow.
# MEASURED 2026-09-30, and this replaces a mapping I got wrong first.
#
# I first assigned each voice figure DIRECTORIES from the shelf (mengxi -> heraclitus/euler,
# tesla -> euler/goldbach, edison -> wallas/greer). Re-reading the operator's own anchor clauses
# against that map BEFORE running showed they are different people: mengxi is anchored to Shen
# Kuo, tesla to Nikola Tesla, edison to Thomas Edison. Borrowing Euler's prose for a voice
# anchored to Tesla would be the costume-not-borrow failure this module exists to avoid, and I
# had written it into the code.
#
# The state, verified on the shelf just now:
#   corpus/library/ractor_starter/ holds 21 figure directories.
#   NONE of them is Tesla, Edison, or Shen Kuo.
#   greer/ exists but contains 0 text files.
#   fen and gopher briefs have no "Anchored to" clause at all.
# So an honest anchor-prose borrow is available for ZERO of the five voices. The correct output
# is that fact -- not a neighbouring figure's prose wearing the voice's name.
#
# The shelf DOES hold superb first-person disposition prose (freud, jung, lebon, weil, von franz,
# debord, innis). It is simply not the prose of these five anchors. Pointing a voice at it would
# measure the shelf, not the voice. Recorded as an available but UNUSED resource below, because
# the operator -- not this seat -- decides whether a voice may borrow across anchors.
ANCHORS: dict[str, list[str]] = {
    "mengxi": [],   # anchor is Shen Kuo; see ANCHOR_FINDINGS -- original is Chinese, English is in copyright
    "fen":    [],   # brief states no anchor
    "tesla":  [],   # anchor is Nikola Tesla; no Tesla prose was on the shelf before MOVE TWO
    "edison": [],   # anchor is Thomas Edison; no Edison prose was on the shelf before MOVE TWO
    "gopher": [],   # brief states no anchor
}

# MOVE TWO RESULTS, each verified against the issuing source rather than taken from a search URL.
ANCHOR_FINDINGS = {
    "tesla": {
        "status": "LANDED-CANDIDATE",
        "source": "my-inventions-nikola-tesla / 'My Inventions - Nikola Tesla_djvu.txt'",
        "bytes": 202396, "probe_hits": 458,
        "script_census": "han=0 latin=31,295 -- English, as the scorer requires",
        "why": "'My Inventions' (1919) is Tesla's own AUTOBIOGRAPHY, in the first person, and it "
               "is the document the brief's 'as DOCUMENTED' qualifier points at. Note the OCR "
               "runs the title as 'MY IMVEMTIONC MIVOIUs' -- a capital-I/lowercase-l "
               "confusion typical of 1919 typeface, so a naive case-sensitive title match would "
               "reject a perfectly good scan. The CONTENT probe is what passed it.",
    },
    "edison": {
        "status": "LANDED-CANDIDATE (substituted edition)",
        "substituted_for": "diaryofthomasaed0000edis -- HTTP 401, access-restricted LENDING copy",
        "source": "india.history.resource.87720 / 'Edison: His Life and Inventions' (Dyer & Martin, "
                  "1910, 2 vols) -- 798,498 B, probe 2,257, han=0",
        "why": "the ruling named 'Edison's notebooks'. The 4-volume Notebook DIARY is a 1948 "
               "RCA copyright edition and every copy on archive is a 401 lending scan, so it is "
               "not obtainable here. The 1910 Dyer & Martin biography was BUILT FROM those "
               "notebooks and quotes them, and four ungated editions exist (1910 india.history, "
               "1929 dli.ernet.163769, 1929 edisonhislifeinv0001fran, 1910 "
               "edisonhislifean03martgoog), all probe 1,987-2,284 hits with han=0. This is the "
               "honest substitute and the substitution is recorded rather than glossed.",
    },
    "mengxi": {
        "status": "HELD-EDITION-NOT-OBTAINABLE",
        "what_exists": "shen_kuo_dream_pool_essays_1095_chinese_trad -- 402,714 B, fetched and probed",
        "measured": "han=16,205 latin=26 -- the CHINESE TRADITIONAL ORIGINAL, as the archive item's "
                    "own title states. Content probe found only 5 hits because the probe was "
                    "English-period vocabulary.",
        "why_held": "the scorer reads ENGLISH period prose. Landing the Chinese original as "
                    "mengxi's seed would be landing a file in a language the instrument cannot "
                    "read and calling it a fix -- the Sefer Raziel lesson in its purest form: the "
                    "handle was real, the edition was not the one needed, and saying so is the "
                    "whole point.",
        "searched_and_absent": "archive.org advanced search for title:('dream pool essays') "
                               "returns exactly ONE item -- the Chinese original. title:('mengxi "
                               "bitan') returns ambient albums, gmod addons and closing logos. "
                               "There is no English translation on the shelf.",
        "the_english_edition_named_honestly": "H. Frankfort, 'Dream Pool Essays: The Versatile "
            "Mind of a Northern Song Dynasty Scientist' (Routledge, 1962) is the standard English "
            "translation and is IN COPYRIGHT. The 1912 Wade-Giles partial translation is rare and "
            "not on archive.org. Recorded as acquisition DEBT with a buy-back path, not as a "
            "silent gap and not as a landing.",
    },
}

# Held in reserve, NOT wired in: first-person disposition prose that IS on the shelf. Usable if
# the operator authorizes cross-anchor borrowing; unusable as evidence for these five as written.
AVAILABLE_NOT_USED = ["freud", "jung", "lebon", "weil", "vonfranz", "debord", "innis",
                      "aristophanes", "plato", "diogenes", "bernays", "euler", "goldbach",
                      "wallas", "lippmann", "socrates", "xenophon", "heraclitus_parmenides"]

TARGET_CHARS = 12_000       # per voice
MAX_PER_FILE = 4_000        # keep one voice from being dominated by a single long work


def _clean(t: str) -> str:
    """Drop Project Gutenberg / archive.org front and back matter, which is boilerplate
    in EVERY volume and would otherwise dominate a sample with license text."""
    t = re.sub(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG[^\*]*\*\*\*", "", t, flags=re.I)
    t = re.sub(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG[^\*]*\*\*\*", "", t, flags=re.I)
    t = re.sub(r"\n?\[?Illustration|\n?\[?Table of contents", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r" Produced by .*", " ", t)
    t = re.sub(r"\*\*END OF THE PROJECT GUTENBERG.*", " ", t)
    return t


def borrow(voice: str, dirs: list[str]) -> tuple[str, list[dict]]:
    """Deterministically borrow prose from the figure's own shelf. Returns (text, provenance)."""
    parts: list[str] = []
    prov: list[dict] = []
    total = 0
    for dname in dirs:
        d = STARTER / dname
        if not d.is_dir():
            prov.append({"dir": dname, "status": "ABSENT-ON-SHELF"})
            continue
        files = sorted(f for f in d.rglob("*.txt") if f.stat().st_size > 20_000)
        if not files:
            prov.append({"dir": dname, "status": "NO-TEXT-ABOVE-20KB"})
            continue
        # STRIDE sample: take an equal slice from the MIDDLE of each file, not the opening.
        # The opening of a 19th-century volume is front matter; the middle is the argument.
        per = min(MAX_PER_FILE, max(1200, TARGET_CHARS // max(1, len(files))))
        for f in files:
            if total >= TARGET_CHARS:
                break
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            body = _clean(raw)
            if len(body) < 5000:
                continue
            start = max(0, (len(body) // 2) - (per // 2))
            excerpt = body[start:start + per]
            if len(excerpt.strip()) < 400:
                continue
            parts.append(excerpt)
            total += len(excerpt)
            prov.append({
                "dir": dname,
                "file": str(f.relative_to(ROOT)).replace("\\", "/"),
                "file_bytes": f.stat().st_size,
                "offset": start,
                "chars": len(excerpt),
                "excerpt_sha256_16": hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16],
            })
    return "\n\n".join(parts), prov


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    dna = yaml.safe_load((PERSONAS / "ractor_dna.yaml").read_text(encoding="utf-8"))
    rows = []

    for name, spec in dna["voices"].items():
        dirs = ANCHORS.get(name)
        if not dirs:
            rows.append({"voice": name, "status": "NO-ANCHOR-MAPPED",
                         "note": "no explicit figure mapping; pointing it at a neighbour would "
                                 "be a costume, not a borrow"})
            print(f"  {name:8s} NO-ANCHOR-MAPPED")
            continue

        text, prov = borrow(name, dirs)
        if len(text) < 2000:
            rows.append({"voice": name, "status": "ANCHOR-SHELF-EMPTY", "provenance": prov,
                         "chars": len(text)})
            print(f"  {name:8s} ANCHOR-SHELF-EMPTY ({len(text)} chars)")
            continue

        fp = M.fingerprint(text)
        declared = (spec.get("genetics") or {}).get("ocean") or {}
        measured = fp["vector"]
        dom = M._dominant(measured)
        lens = OP.lens_ocean(measured) if fp["signal_detected"] else None
        files_borrowed = [p for p in prov if p.get("file")]
        rows.append({
            "voice": name, "status": "BORROWED", "anchor_dirs": dirs,
            "seed_chars": len(text), "files_borrowed": len(files_borrowed),
            "seed_sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "provenance": prov,
            "signal_detected": fp["signal_detected"], "confidence": fp["confidence"],
            "matched_terms": fp.get("matched_terms", {}),
            "measured_ocean": measured, "declared_ocean": declared,
            "measured_dominant": dom,
            "declared_dominant": max(declared, key=lambda k: declared[k]) if declared else None,
            "design_minus_measured": {k: round(float(v) - float(measured.get(k, 0.5)), 3)
                                      for k, v in declared.items()
                                      if isinstance(v, (int, float)) and k in measured},
            "lensed": ({"primary_trait": lens.get("primary_trait"),
                        "archetype": (lens.get("primary_invariant") or {}).get("archetype"),
                        "lens": (lens.get("primary_invariant") or {}).get("lens")}
                       if lens else None),
            "life_version": spec.get("life_version"),
        })
        print(f"  {name:8s} {len(text):6d}ch from {len(files_borrowed)} files "
              f"[{'+'.join(dirs)}]  signal={fp['signal_detected']!s:5s} conf={fp['confidence']:.2f} "
              f"dominant={dom}")

    borrowed = [r for r in rows if r["status"] == "BORROWED"]
    withsig = [r for r in borrowed if r["signal_detected"]]
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "schema": "ractor_selfsteal_seeds.v1",
        "doctrine": "self steal: the seed is the anchor figure's OWN prose, borrowed from "
                    "corpus/library/ractor_starter/ (21 figure dirs, ~2.5 MB). Nothing invented. "
                    "Every excerpt is traceable by file, offset, length and sha256.",
        "determinism": "stride sampling from the middle of each file; no RNG. Re-running "
                       "produces byte-identical seeds and therefore identical measurements.",
        "voices": rows,
        "summary": {
            "voices": len(dna["voices"]),
            "borrowed": len(borrowed),
            "with_signal": len(withsig),
            "silent": [r["voice"] for r in borrowed if not r["signal_detected"]],
            "total_chars_borrowed": sum(r["seed_chars"] for r in borrowed),
            "files_borrowed": sum(r["files_borrowed"] for r in borrowed),
            "falsifier_status": "PRE-REGISTERED, NOT RUN -- requires the operator to read the "
                                "fold blind. This seat cannot self-certify its own voices.",
        },
    }
    p = RUNS / "RACTOR_SELFSTEAL_SEEDS.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    s = out["summary"]
    print(f"\n  {s['borrowed']}/{s['voices']} voices borrowed, {s['with_signal']} with signal")
    print(f"  silent: {s['silent'] or 'none'}")
    print(f"  {s['total_chars_borrowed']:,} chars from {s['files_borrowed']} existing files")
    print(f"  -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())