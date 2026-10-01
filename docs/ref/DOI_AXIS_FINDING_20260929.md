# THE DOI AXIS — science handles are the worst, and that is measurable

Whole-pack liveness census, 255 handles extracted mechanically from the 57 answers
(`mag/corpus_lead_verify.py` → `memory/runs/corpus_gap_research/verify.json`).

| theme | handles | resolve | dead | rate |
|---|---:|---:|---:|---:|
| X-cross | 11 | 8 | 3 | **72.7%** |
| F-scifi | 45 | 30 | 15 | 66.7% |
| B-oldbooks | 83 | 44 | 39 | 53.0% |
| G-gaming | 44 | 15 | 29 | 34.1% |
| S-science | 72 | 17 | 55 | **23.6%** |

**Science is the weakest axis in the entire pack**, and gaming second. The old-books shelf
looks comparatively healthy at 53% — but that is an artefact: those handles are mostly
Gutenberg IDs, which resolve almost by construction. The themes that cite *journals* (science,
gaming-theory papers) are the ones that fail.

## The 404s are a verdict; the 403s are not

| verdict | n | what it means |
|---|---:|---|
| resolves (200) | 20 | the handle exists |
| **HTTP 404** | **47** | **doi.org says this DOI does not exist** |
| HTTP 403 | 19 | publisher blocked the bot — **inconclusive, not a failure** |
| 202 / 406 / 410 | 3 | edge cases (accepted / not acceptable / gone) |

Reporting 403 as "dead" would have inflated the failure count by 19 and been wrong. Control
test run through the identical path:

```
10.1038/nature01331        -> 200   (known real, resolves)
10.1126/science.169.3946.635 -> 403   (known real, publisher blocks bots)
10.1145/3292500.3330717    -> 403   (known real, publisher blocks bots)

10.1007/978                -> 404   (fan-out lead)
10.1007/978-1-4020-4628-6  -> 404   (fan-out lead)
10.1007/978-1-4612-4420-1  -> 404   (fan-out lead)
10.1007/978-1-4612-9924-3  -> 404   (fan-out lead)
10.1007/978-3-319-40796-3  -> 404   (fan-out lead)
```

Known-real DOIs come back 200 or 403. The fan-out's come back a clean **404**. That is a
verdict, not a block.

## Two tells that these were never real handles

**1. Truncated ISBN-DOI stems.** Springer DOIs are `10.1007/<ISBN>-<chapter>`. The pack
contains bare prefixes with the chapter number missing:

- `10.1007/978`  ← not a DOI at all
- `10.1057/978`  ← not a DOI at all
- `10.1007/978-1-4020-4628-6`, `10.1007/978-1-4612-4420-1`, `10.1007/978-3-319-40796-3`,
  `10.1007/978-3-319-49237-9_9`, `10.1007/978-3-642-17489-1_4`

A model reproducing `10.1007/978-1-4020-4628-6` from memory is reciting a plausible ISBN-shaped
string, not a registered identifier.

**2. Round-number sentinels.** `10.5281/zenodo.6666666` — Zenodo's well-known example DOI,
used in documentation as a placeholder. It returned **410 Gone**. A lane that emits a
documentation placeholder as a citation is not citing.

## What this means for the corpus

**A DOI in a lead is worth less than a work title.** A title can be searched and confirmed
against a catalogue; a fabricated DOI can only be caught by asking the registry, and 47 of 89
failed that way. The promotion rule already encodes this — *fetch the URL, record the sha256* —
and this axis is the argument for it.

The `B-oldbooks` leads, which mostly cite Gutenberg IDs, survived title-matching far better
than the science leads, which cite journal DOIs. **The gap analysis and the reliability finding
point at the same place: the science shelf is empty *and* the science citations are the least
trustworthy in the pack.** Both are fixed by the same action — pull real PD science texts and
manifest them by hash, rather than accumulating cited-but-unverified references.
