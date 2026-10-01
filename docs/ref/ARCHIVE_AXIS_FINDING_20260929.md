# ARCHIVE.ORG AXIS — the citations that were never checked, and a control that saved me from a false claim

The pack cites `archive.org` item identifiers alongside Gutenberg numbers and DOIs — the B09
science-history shelf, B12 psychology, and the scifi rows in B01/F07. `corpus_lead_verify` only
recognises Gutenberg / DOI / arXiv / URL grammars, so **this entire axis had been sitting
unverified while the pack reads as well-sourced.** `mag/corpus_archive_check.py` closes it.

## Result

| verdict | n | meaning |
|---|---:|---|
| **MATCHED** | **5** | title confirmed against archive's own metadata — promotable |
| NO_METADATA | 68 | **inconclusive — see the control below. Not counted as failures** |
| DARK | 4 | real record, catalogue deliberately withheld |
| NO_CLAIM | 2 | identifier cited with no work named beside it |

**Promotable rate: 100% of scorable (5/5). Zero identifiers proven wrong.**

The five confirmed, each verified against archive.org's own title record:

- *Discourse on the Method* — Descartes
- *An Enquiry Concerning Human Understanding* — Hume
- *A History of Mathematics* — Boyer
- *A History of Mathematics* — Cajori
- *L'automatisme psychologique* — Ribot

## THE CONTROL — and the false claim it prevented

The first run of this module reported **68 of 79 identifiers as having no metadata**, which
reads as "these 68 archive IDs are fabricated." That conclusion was **wrong**, and a control
caught it.

```
control item: adventuresofsherl00doyle   (Doyle — certainly real, NOT from the pack)
  → HTTP 200, metadata title = ""  (empty)
```

`adventuresofsherl00doyle` certainly exists. It returned **200 with an empty metadata envelope**
anyway. So archive.org is **withholding catalogue data from this client**, and an empty reply
therefore carries **no information** about whether an identifier exists.

Had I reported the 68 as fabricated, I would have filed a hard negative about a corpus I had
not actually tested — the same class of error as the Gutendex rate-limit, caught the same way,
by refusing to believe an absence I had not controlled for.

The rule, now written into the module: **if `control.metadata_visible` is false, every
`NO_METADATA` row is inconclusive and is not counted against the pack.** Re-test those 68 with
a browser UA or the item page before drawing any conclusion.

## Two real defects this round, both mine

**1. `is_dark` misread as absence.** My first `_meta` returned a 3-tuple and treated empty
title+creator as a mismatch — which would have reported *73 wrong identifiers* when most were
dark-but-real. `is_dark` is now a distinct verdict, never a mismatch.

**2. `_claim_for` compared the AUTHOR against the TITLE.** On a B09 bullet:

```
**Whewell, W.** *History of the Inductive Sciences* (1857). Internet Archive ID: `historyofinductiv01whewuoft`
```

my first version took the first italic span and matched `Mach, E.` against a catalogue title —
so real matches were being scored as mismatches. Fixed to prefer the work span over an author
blob; the three spot-checks now return `The Analysis of Sensations`,
`Faraday as a Self-Taught Natural Philosopher`, `Elements of Physiology` — all correct.

Both bugs pushed in the same direction: **making the pack look worse than it is.** A verifier
that manufactures failures is as broken as one that manufactures passes, and the control is the
only thing that distinguishes them.

## What this means

The B09 science-history shelf — the one that could actually seed the empty science corpus — is
built on archive.org identifiers, and **5 of them are real and promotable now.** The other 68
are untested rather than bad. That is a different and much more actionable position than either
"all fake" or "all fine", and it is the honest one.
