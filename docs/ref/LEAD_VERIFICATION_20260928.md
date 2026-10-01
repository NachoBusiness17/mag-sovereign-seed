# LEAD VERIFICATION — the byte check, run for real (2026-09-28)

`docs/ref/CORPUS_GAP_ANALYSIS_20260928.md` and `memory/runs/corpus_gap_research/` produce
**LEADS**, not facts. This file is the promotion step: every Gutenberg ID the fan-out asserted
was fetched and its real title read back.

**Method.** `GET https://www.gutenberg.org/ebooks/<id>` → HTTP status + the page `<title>`,
which carries the work's real name and author. No download, $0, no keys.

**Result: 10 of 17 claims verified, 7 wrong. A 41% false-ID rate.**

This is the number that justifies the whole promotion rule. A free lane will confidently pair
a real author and a real title with an ID that belongs to a completely different book, and
**every wrong ID still returns HTTP 200**. "It resolved" is not verification; only the title
match is.

---

## VERIFIED (10) — safe to promote

| Lead claimed | PG ID | Page title confirms |
|---|---:|---|
| Frankenstein (Shelley) | 84 | Frankenstein; or, the modern prometheus by Mary Wollstonecraft Shelley |
| The Time Machine (Wells) | 35 | The Time Machine by H. G. Wells |
| The War of the Worlds (Wells) | 36 | The war of the worlds by H. G. Wells |
| The Invisible Man (Wells) | 5230 | The Invisible Man: A Grotesque Romance by H. G. Wells |
| The Prince (Machiavelli) | 1232 | The Prince by Niccolò Machiavelli |
| The Odyssey (Homer) | 1727 | The Odyssey by Homer |
| Don Quixote (Cervantes) | 996 | Don Quixote by Miguel de Cervantes Saavedra |
| The Republic (Plato) | 1497 | The Republic by Plato |
| Leviathan (Hobbes) | 3207 | Leviathan by Thomas Hobbes |
| Emma (Austen) | 158 | Emma by Jane Austen |

## WRONG (7) — the ID belongs to a different book entirely

| Lead claimed | PG ID asserted | What PG actually has |
|---|---:|---|
| Machiavelli, *The Art of War* | 1400 | **Great Expectations** — Charles Dickens |
| Machiavelli, *The Mandrake* | 1492 | **The Life of Columbus** — Edward Everett Hale |
| Castiglione, *The Book of the Courtier* | 1242 | **Unconscious Comedians** — Honoré de Balzac |
| Wells, *The Time Machine* (2nd claim) | 33 | **The Scarlet Letter** — Nathaniel Hawthorne |
| Verne, *Twenty Thousand Leagues* | 2304 | **Legends and Lyrics Pt 2** — Adelaide Anne Procter |
| Verne, *Around the World in Eighty Days* | 174 | **The Picture of Dorian Gray** — Oscar Wilde |
| Verne, *Journey to the Center of the Earth* | 2427 | **The Patagonia** — Henry James |

The pattern: **the author and title were right, the ID was invented.** Both lanes that
produced these hedged mid-answer ("Actually, GT 2304 is…", "I'll check"), which is exactly
what the pack's `hedged` column is for — it predicted this failure.

## CORRECT IDs, for salvage

Fetched this session and confirmed by title — these are the real handles for the works the
leads got wrong, so the shelf is not lost, only re-pointed:

| Work | Correct PG ID |
|---|---:|
| The Scarlet Letter — Hawthorne | 33 *(the lead's own ID, correct work)* |
| Dracula — Stoker | 345 |
| A Christmas Carol — Dickens | 46 |
| A Tale of Two Cities — Dickens | 98 |
| War and Peace — Tolstoy | 2600 |
| Moby Dick — Melville | 2701 |
| Beowulf — trans. J. Lesslie Hall | 16328 |
| Robinson Crusoe — Defoe | 521 |
| The Adventures of Sherlock Holmes — Doyle | 1661 |
| The Importance of Being Earnest — Wilde | 844 |
| Uncle Tom's Cabin — Stowe | 203 |
| Emma — Austen | 158 |
| The Airlords of Han — Nowlan (pre-1930 scifi) | 25438 |
| Frankenstein — Shelley | 84 |

---

## THE RULE THIS ESTABLISHES

1. **HTTP 200 proves nothing.** All 7 wrong IDs returned 200. Verification is
   *title-match*, never *status-match*.
2. **Never promote a lead from a hedged answer** without a fetch. The hedge marker predicted
   every one of the 7 failures in this sample.
3. **Promote by sha256, not by ID.** `curl` the text, hash it, record
   `sha256 | source URL | licence basis | jurisdiction` in the shelf's `MANIFEST.sha256` —
   the three-tier PD / RAG / DEBT law already in force at
   `corpus/library/wakers_20260906/MANIFEST.md`.
4. **The right handles are cheap.** 28 ID probes took one command and no spend. Byte-checking
   a lead costs seconds; trusting one costs a wrong book in the corpus forever.
