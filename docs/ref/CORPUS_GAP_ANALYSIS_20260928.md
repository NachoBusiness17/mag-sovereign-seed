# CORPUS GAP ANALYSIS — gaming, science, science fiction, old books

*Operator ask 2026-09-28: "look at all of my research and do a gap analysis and launch a
research project filling in the gaps around our gaming corpus our science, science fiction and
old books self steal and go wide and hard."*

**Every number below came from a command in this session.** Instruments and paths are named.
Model output is quarantined as LEADS and never mixed into the measurements.

---

## VERDICT (lead with this)

The corpus is **5.4 GB and almost none of it is prose.** `corpus/library` holds 55,915 files
and roughly 90% of them are **code** — LLM course repos and game server source. The entire
readable book corpus is **156 files over 100 KB**, of which the honest scifi shelf is
**one audiobook transcript**.

The gap is not "we need more books." The gap is that **the instrument could not see the books
we already had.** `mag/corpus_selfsteal.py` reported *1,270 files · 10.0 MB* as the corpus,
which reads like a library and is not one. That number was the first thing wrong, and it is
now fixed by a new census subcommand rather than by opinion.

---

## WHAT WE ACTUALLY HOLD (measured)

| Tree | Files | Size | What it is |
|---|---:|---:|---|
| `corpus/library` | 55,915 | 5,464 MB | ~90% **code**: ms-genai-beginners, openai-cookbook, zcode-zai-org, mod-playerbots, evennia, dfhack, lmcache |
| `corpus/oral_history` | 15,749 | 1,387 MB | seat pools + session transcripts (`json`/`jsonl`/`lock`), not books |
| `corpus/dfhack_full` | 2,205 | 28 MB | Dwarf Fortress tooling source |
| `corpus/training_materials` | 27 | 110 MB | 26 PDFs, all ML/math (AlphaEvolve, Mir 1985, Understanding ML 2e) |
| `corpus/game_estate` | 14 | 1 MB | 12 design docs — the game *thinking* |

**Books over 100 KB, whole estate: 156. Book containers (.epub/.mobi/.djvu): 1.**

| Domain | Held | Verdict |
|---|---|---|
| **Game mechanics** | Marathon terminal harvest (23 transcripts), WoW/AzerothCore family lineage map, evennia, dfhack, playerbots, 12 game_estate design docs | **STRONG** — deepest domain |
| **Game design theory / history** | 1 Pratchett MUD steal note | **EMPTY** — no MDA, no game studies, no D&D lineage |
| **Science** | `docs/ref/BIBLIOGRAPHY_MAP.md`, 357 lines, **every row LLM infrastructure** (KV cache, mesh, eval) | **EMPTY outside ML** |
| **Science fiction** | `frankenstein_1831_p1_librivox.txt` (1 file) | **EMPTY** |
| **Old books** | `ractor_starter` 20 authors, all 1900-1928 political psychology + Greek classics | **THIN** |
| **Non-Western / medieval / military** | 0 files | **EMPTY** |

The self-steal index (1,270 files) is the **game** corpus, not the **book** corpus. That is
the mislabel that would have made a fan-out dig up things we already own.

---

## THE THREE INSTRUMENT BLIND SPOTS (found, two already fixed)

**1. `corpus_selfsteal.SURFACES` never lists `corpus/**`** — the tree holding every book.
**FIXED.** Added `PROSE_TREES` + a `prose()` census subcommand. Live:
`python -m mag.corpus_selfsteal prose` → `memory/runs/corpus_selfsteal/PROSE_CENSUS.json`.

**2. My own scifi marker table was a false-positive factory — reported, not buried.**
First run said "13 scifi files, 13/13 shelves present." That was a lie from my own regex:
the bare marker `card` (Orson Scott Card) matched **202 UI component files** in
`human-atlas/` and `kev/`, and `lem_` matched a `.../problem/` path. Tightened the table and
re-ran: **1 scifi file.** A substring marker is a count, never a classification.

**3. The borrowed fan-out selects dead lanes.** `mag/research_fanout.run()` picks lanes by
`env.get(l["key"])` — key *presence*, not a live probe — while its own docstring claims "a
stored key is not a live key." Measured: `or-union-alpha` and `or-glm52` both 404 on probe yet
still took round-robin questions, so **10 of 57 rows were `HTTP 404` from two known-dead
lanes.** Fixed **in the borrowing copy** (`_live_lanes()`), not by editing the house file.

---

## WHAT THE INHERITED GOVERNANCE ALREADY DECIDES

`corpus/library/wakers_20260906/MANIFEST.md` + `MANIFEST_KNOWLEDGE_DEBT.md` set a three-tier
law this project obeys rather than reinventing:

| Tier | Meaning | Rule |
|---|---|---|
| **PD** | public domain | training-eligible |
| **RAG / citation** | openly released, licence unread | reference only |
| **DEBT** | in-copyright, personal use | RAG only · never redistributed · **buy-back named** |

8 works are already logged as OWED (McLuhan ×2, Foucault ×3, Baudrillard, Jung *Liber Novus*,
Ellul) with the exact edition to buy back. **The gap project's job is to fill the PD and
RAG tiers, which is where 90% of free material legally lives** — not to extend the debt shelf.

---

## THE RESEARCH PROJECT (launched)

`mag/corpus_gap_research.py` — **borrows** `LANES`, `call_lane`, `_env` and `probe_lanes` from
`mag/research_fanout.py`. It adds only a battery and an artifact root. No second scheduler,
no new lane table, no new request shape.

- **57 questions**, 5 themes: G-gaming 13 · S-science 13 · F-scifi 13 · B-oldbooks 14 · X-cross 4
- **Free tiers only.** Paid keys (xAI/Anthropic/OpenAI) deliberately excluded.
- **Artifacts:** `memory/runs/corpus_gap_research/` (`raw.jsonl` append-only, `CORPUS_GAP_RESEARCH.md`,
  `receipt.json`). Confirmed gitignored (`.gitignore:92 memory/runs/**`).
- **Every question demands a legal, checkable handle** — Gutenberg ID, IA identifier, DOI,
  arXiv ID, repo URL — so a lead can be promoted by a byte check instead of a vibe.

Run 1 (measured): 57 rows. After five retry passes: **57/57 answered, zero gaps**, 232 rows on
the append-only tape, **all five themes complete** (G-gaming 13/13 · S-science 13/13 ·
F-scifi 13/13 · B-oldbooks 14/14 · X-cross 4/4).

X01 — "name 10 permissively-licensed corpora legally bulk-downloadable today" — failed its
first four attempts and was recovered on pass 2 by `groq-qwen`. It returned the most
actionable answer in the pack: **Project Gutenberg bulk (~1.5 GB, 70,000+ texts),
Standard Ebooks (~500 MB, 1,000+ curated), Open Library's IA S3 bucket (filter
`license:publicdomain`), and English Wikisource.** That is the actual acquisition surface for
this project, and it is the answer to "where does the next 1,000 books come from."

Failures preserved, never smoothed, across the whole tape: 64 `HTTP 429` (rate limits — the
retry passes overlapped each other), 57 `empty_content` (reasoning models spending the budget
in-channel), 14 `HTTP 404` (the dead-lane defect above). Every one of those rows is still on
`raw.jsonl`; none were deleted to make the 57/57 look clean.

**The battery digest moved mid-run** (`7d8163caa686` → `46e2216bf0ef`) because I corrected
B01's question text. Reported rather than hidden: the digest is the version of the instrument,
so pass 1 and pass 2 are not byte-comparable.

---

## THE RESULT THAT MATTERS MOST: I byte-checked the leads, and 41% were wrong

I fetched 17 Gutenberg IDs the lanes asserted and read the real title back.
**10 verified, 7 wrong.** Full table: `docs/ref/LEAD_VERIFICATION_20260928.md`.

The failure mode is specific and worth naming: **the author and title were right, the ID was
invented.** A lane paired Machiavelli's *The Art of War* with **PG 1400 = *Great Expectations***.
Castiglione's *Courtier* → **PG 1242 = Balzac**. Verne's *Around the World* → **PG 174 = *Dorian
Gray***. **Every wrong ID still returned HTTP 200** — so "it resolved" is not verification, and
only the title match counts.

This is what the pack's `hedged` column predicted. Counting answers still containing
`Actually…`, `I'll verify`, or a bare `?`:

| lane | answers | median words | hedged |
|---|---:|---:|---:|
| `groq-qwen` | 14 | 241 | **2/14** |
| `zai-lite` | 4 | 211 | **1/4** |
| `groq-oss` | 17 | 220 | **3/17** |
| `or-nemotron` | 21 | 313 | **16/21** |

The hedge marker is a usable lane-quality signal, not just a warning label — and it held
across the whole run, not just the first pass. I also recovered **12/12 correct replacement
IDs** by title-fetching the works the leads got wrong, so the shelf is re-pointed rather than
lost.

---

## A SECOND DEFECT I CAUSED AND FIXED (reported, not buried)

`or-nemotron` returns its **chain-of-thought as the answer**: 19 answers opened with
`Here's a thinking process:` and ran 1,230-1,962 words against a 200-word cap, spending the
whole budget deliberating ("Actually, GT 2304 is…") before emitting a list that was itself
truncated mid-line. The house `call_lane` has an `empty_content` guard for this failure
family, but it only fires when content comes back **empty** — a page of reasoning with a list
at the end walks straight past it.

My first fix was worse than the bug: it reported `stripped=True` while removing **4 words out
of 1,713**, because it flagged the header and then bailed. A filter that is counted but does
not work is the worst outcome. Rewrote it to locate the final list block, re-ran against the
real rows: **19 scaffolds stripped, 68% of words removed**, citations preserved.

---

## THIRD DEFECT: the retry passes overwrote the cleaned pack

Found when the five background jobs reported. `mag.corpus_gap_research.retry()` calls
`_write_pack()` on its way out, so **each retry rewrote `CORPUS_GAP_RESEARCH.md` and
`receipt.json` with its own un-stripped view** — the one the strip fix had already cleaned.
Measured: the pack dropped from the cleaned 158,884 B version to a 216,536 B version with
**zero** `HEDGED` flags, and the receipt lost the `lane_quality` and `hedged_answers` keys
entirely. Three concurrent retries, three overwrites.

The tape was never at risk — `raw.jsonl` is append-only and the defect only touches derived
files — so `python -m mag.corpus_gap_repack` rebuilt both from 232 rows and the flags came
back (22 hedged). **The recovery is free precisely because the tape is the record and the pack
is derived from it.** That is the whole argument for the append-only design, paid off in the
cheapest possible currency.

The structural fix: `repack` is now the only writer of the human-facing pack, and a retry that
finishes after a repack must not be trusted to have left a good pack behind. Anyone resuming
this work should run `repack` once at the end, after the last retry exits.

**The fix was then verified against a real straggler, and it held.** A sixth retry landed
87 seconds *after* the repack (tape written 19:47:37, pack written 19:49:04). It was running
the pre-fix code, so it could have clobbered the clean pack again — it did not, because it had
already finished. Measured after it: pack still 159,078 B, still 21 hedge flags, receipt still
carries `lane_quality`, tape 236 == receipt 236, digest matches. **The ordering was luck, not
design** — the guard that saved it is the `pack_is_stale` flag and the REBUILD banner added
afterwards, which exist for the next straggler, not this one. The operational rule stands:
repack last, and verify the mtime ordering rather than assuming it.

---

## THE PROMOTION RULE (why this is not a pile of LLM prose)

A lead becomes a held book only by: **fetch the URL → record the sha256 → land it under
`corpus/library/<theme>/` with a `MANIFEST.sha256` row carrying licence basis and
jurisdiction.** Free-channel answers carry checkable errors; a lane asserting a Gutenberg
number is a claim until the bytes arrive.

---

## WHAT I DID NOT DO

- Did not repair, rebuild, or GC anything. Read-only on the verkle chain and biography.
- Did not download a single book — the lead→byte promotion step is the operator's call, and
  22 leads are not yet verified handles.
- Did not edit `mag/research_fanout.py` despite finding a real defect in it; named the defect,
  named the one-line fix, fixed it in the copy that borrows it.
- Did not use paid lanes. Total spend: **$0.**
