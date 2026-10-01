# LIBRARIAN CONSULTATION — the bibliography dogfood audit, and the 901-row gap behind it

There are **two** Librarians in this fleet, and asking the wrong one would have wasted the pass.

| seat | file | job |
|---|---|---|
| **the bibliography auditor** | `mag/librarian.py` | audits BIBLIOGRAPHY_MAP.md: PULLED vs RETRIEVAL-PLAN vs DUST vs UNREGISTERED, plus a discipline-5 adjacent-field sweep |
| **the cold-load imprint seat** | `scripts/librarian.py` | loads a 390 KB fleet imprint as system prompt so a seat can answer questions about ourselves |

The operator asked for a gap analysis "with the librarian," so this is the **bibliography
auditor** — the one that reports evidence gaps. Its own law, from its docstring: *records and
bibliographies must not sit and collect dust; they are part of the dogfooding process itself.*

## What the librarian said

```
python -m mag.librarian
  docs scanned:      4807
  map rows:          275  (tier-3: 7)
  PULLED+HASHED:     9
  PULLED:            11
  RETRIEVAL-PLAN:    220
  UNREGISTERED:      933   <- map behind the desk
  DUST:              11
  NO-STATUS:         8
  ZERO-MAP-FIELDS:   formal methods
  ARCHIVE:           4 primary sources retained
```

Read plainly: **of 275 bibliography rows, 20 have a pulled primary and 9 are pulled+hash.
220 are plans. And 933 arXiv ids are cited in real cards while absent from the map entirely.**

The adjacent-field sweep names the blind spots by design (discipline 5: *correlated blind spots
are structural*):

| field | map hits | corpus hits | reading |
|---|---:|---:|---|
| **formal methods** | **0** | 66 | **zero coverage** |
| economics | 1 | 851 | 1 hit against 851 uses |
| ecology | 4 | 119 | thin |
| safety engineering | 4 | 2616 | negligible against 2616 |
| distributed systems | 7 | 792 | thin |

The ratio is the finding: **the map records almost none of what the corpus actually thinks
about.** That is the same shape as the corpus gap itself — a large body of work and a small,
unconnected index.

## The distinction that matters: register gap ≠ truth gap

933 unregistered is a **register** problem by construction — the librarian asks "does the map
mention this id?", never "does this id exist?". Those are different questions and the citation
law ("a wrong citation is worse than an honest gap") turns entirely on the difference: registering
933 hallucinated ids would be far worse than the gap.

So I resolved every one against arXiv, with a control (`1706.03762`, certainly live):

| verdict | n | reading |
|---|---:|---|
| **REAL** (title fetched from arXiv) | **907** | genuine literature the map is missing |
| HTTP 406 from `abs` | 26 | **inconclusive — not dead** |

**907 of 933 = 97.2% real.** The map is behind the desk on real papers, not on hallucination.
That is a large, cheap, entirely legitimate improvement to the corpus's bibliographic spine.

**26 ids are explicitly not claimed.** They return HTTP 406 from `arxiv.org/abs` — content
negotiation, not a dead paper — and an export-API fallback resolved only some. I report them as
inconclusive rather than guessing; counting a 406 as a dead citation is the same error as
counting a 403 as a dead DOI, which I refused earlier for exactly this reason.

## The backfill: 901 verified rows, and the map is untouched

`mag/corpus_map_backfill.py` deduplicated against the map and produced **901 fresh rows**, each
carrying the title arXiv actually returned:

| bucket | rows |
|---|---:|
| self-feed | 401 |
| general | 371 |
| physical-computing | 73 |
| physics | 62 |

Spot-checked six by independent re-fetch — all six titles match the backfill exactly. HTML
entities were unescaped (`Don&#39;t` → `Don't`) so the file is copy-pasteable.

**`docs/ref/BIBLIOGRAPHY_MAP.md` was NOT modified.** Growing the map by 901 rows on a seat's own
say-so is exactly the unbidden write the standing law forbids. The block is reviewable and
mergeable by the operator.

**Every row is a RETRIEVAL-PLAN, never PULLED.** Only 9 of 275 rows are PULLED+HASHED today, and
"the citation is real" is not the claim "we hold the paper." Conflating them is the exact
confusion the librarian's own vocabulary exists to prevent. A row moves to PULLED only when the
PDF is fetched and sha256'd into `docs/report_v1/sources/receipts/`.

## A real gap in MY census, found by the librarian

The librarian pointed at `corpus/papers` — a tree my `PROSE_TREES` never walked. Checking
properly, **10 corpus trees / 48.9 MB were unscanned**: `papers`, `ractor_ribs`, `telegram`,
`df_mine`, `dfhack_full`, `apk`, `tmp`, `tmp_enoch`, `dfhack_mirror`, `dumps`.

I nearly got this wrong twice by comparing prefixes (`corpus/` was already in `PROSE_TREES`, so
my first two checks reported all 18 trees as unscanned). The honest measure came from the census
artifact itself. After closing it:

| metric | before | after |
|---|---:|---:|
| trees walked | 8 | **18** |
| books > 100 KB | 156 | **157** |
| book containers | 1 | 1 |
| scifi files | 1 | 1 |
| tradition shelves empty | 7/7 | 7/7 |

**The 48.9 MB that was unscanned held no books** — one book surfaced in `dfhack_full`, nothing
else changed. The gap was real, and it was hiding nothing. That is the good outcome: it means
the headline finding ("the corpus is 5.4 GB of mostly code, with one science-fiction file") was
never an artefact of what I failed to look at.

The calibration check that pinned "8 trees walked" was hard-coded to `8`, so it kept passing
while the census silently skipped a tenth of the corpus. It is now pinned to `len(PROSE_TREES)`.
A test that cannot fail when the thing it guards changes is decoration.

## The librarian's own gaps — not mine to fix

The librarian is an auditor; its output is a receipt, not a command. Its 220 RETRIEVAL-PLAN rows
and 11 DUST rows are the standing estate's condition. What I did is close the part that was
mine: the census blind spot, and the register gap for citations that turned out to be real.

**No book downloaded. No map row merged. Nothing written outside my own organs' state paths.**
