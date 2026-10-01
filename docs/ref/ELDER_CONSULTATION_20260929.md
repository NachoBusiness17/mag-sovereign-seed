# ELDER CONSULTATION — the elder's ruling on the corpus-gap work

Run: `python -m mag.elder` · law: **contradictions resolve by evidence and hierarchy, not vote**

The elder is a deterministic audit seat (`mag/elder.py`). It reports and ranks evidence gaps; it
does not become a second conductor and **never grants permissions**. Its output is an audit
receipt, not a command. What follows is the elder's ruling on the 2026-09-28 corpus work, and
what I did about it — reported as evidence, not as permission.

---

## FINDING 1 — the elder's first ruling was against me, not for me

Asked to rule on the gap-analysis work, the elder's organ map said something uncomfortable:
**of 33 declared organs, none of the four modules I had written were declared at all.** They
existed, imported, ran, and left receipts — and were structurally invisible to the system's own
inventory. That is the `caller_undeclared` code the elder leads with, and it is the same code it
fired at `fleet_structure`.

That is the elder working as designed. It does not care that the work is good; it cares that
the work is *unwitnessed*. An instrument nothing declares is an instrument nothing can hold
accountable.

**Acted on:** declared all four in `mag/organ_map.py` REGISTRY, each with a real callable, a
real state path, a real receipt path, and a named caller.

| organ | callable | caller |
|---|---|---|
| `corpus_gap_research` | `main` | `mag/corpus_gap_repack.py` |
| `corpus_gap_repack` | `repack` | `mag/corpus_gap_research.py` |
| `corpus_lead_verify` | `extract` | the CLOSED job receipt |
| `corpus_salvage` | `main` | `mag/corpus_gutenberg_truth.py` |

**Measured before/after:** `DECLARED 33 → 37`, `VERIFIED 32 → 36`, `GHOST 0 → 0`.

I declared `repack` as the callable for `corpus_gap_research` at first. It doesn't exist there —
`repack` lives in the sibling module. The `import` proof caught it on the first re-run, and I
corrected the declaration rather than leaving an entry that fails its own proof. **A
declaration that fails its proof is worse than no declaration**, because it spends the reader's
trust to buy nothing.

## FINDING 2 — the elder's own 19 gaps, ranked

| code | n | what it means here |
|---|---:|---|
| `receipt_stale` | 13 | organs verified but not observed alive recently |
| `receipt_not_successful` | 4 | last run failed |
| `caller_undeclared` | 1 | `fleet_structure` — no named caller, no receipt, proof failed |
| `receipt_missing` | 2 | `fleet_structure`, `host_resolver` |

**Not mine to fix, and deliberately not touched.** The elder ranks; it does not command. These
19 are the standing estate's condition, most of them predating this work by weeks. `LIVE: 4` of
37 declared organs is the real headline: the system has 36 verified organs and 4 recently-alive
ones. The elder's `next` for most of them is identical — "run one bounded live dogfood step" —
which is a queue, not an emergency.

## FINDING 3 — where the elder's law changed my answer, three times

This is the part that mattered. The elder's law is not decoration; it changed what I was willing
to claim, and every time it did, the first reading had been wrong.

**1. "Gutenberg doesn't have *The Art of War* by Machiavelli."**
I concluded from `count=0` across Gutendex that these works were simply absent from the corpus —
a real, publishable-sounding conclusion about availability. It was **my own 8-worker thread pool
getting rate-limited**; `_get_json` turned every timeout into `{}`, and an empty dict is
indistinguishable from "no such book." A serial probe with a pause returned `beowulf=9`,
`moby dick=5`, `Emma Austen=2`. *Moby Dick* returning zero is what exposed it — too famous to be
missing. I had nearly filed a false negative about the corpus's contents. Fixed: serial with a
pause, three retries, and a `__fetch_failed__` sentinel so a timeout can never again be
reported as absence.

**2. "Only 3 of 70 salvage candidates confirmed."**
Also wrong, twice over. The `agree()` matcher required ≥2 shared tokens, which rejects
*The Book of the Courtier* vs *The Courtier* (shares only `courtier`) and — the real bug —
scored *The Art of War* against **itself** as `False`, because the title normalises to
`{art, war}` and both fall under the 5-char distinctiveness floor. A gate that rejects a title
matching itself is not strict, it is broken. Fixed, and pinned with `mag/corpus_salvage_prove.py`
— **13/13** cases, both directions: true matches must promote, wrong handles must refuse.

**3. "The leads are 41% wrong."**
The number was right; the *scope* was wrong. 41% came from 17 IDs I had picked by hand, and it
does not generalise to the other handles. Run mechanically over the whole pack: **255 handles**
(68 Gutenberg, 89 DOI, 94 URL, 4 arXiv), of which **67/68 Gutenberg IDs resolve** — and 69 of 73
title-matched pairs are **wrong**, a ~95% handle error rate on that subset. The honest reading is
that live-ness and truth are nearly independent, so liveness is worthless as a gate. That is a
stronger and more useful claim than 41%, and I would not have reached it by trusting the sample.

## THE STANDING ORDER I DID NOT GIVE MYSELF

The elder ranks and never grants permissions, and the discipline matters: this consultation
produced a **ranked list of evidence gaps and a set of receipts**. It did not authorise a single
book download, and none happened. Promotion remains the operator's call, exactly as it was
before the elder was asked.
