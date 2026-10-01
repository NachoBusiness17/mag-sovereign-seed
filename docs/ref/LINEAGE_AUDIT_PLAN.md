# LINEAGE AUDIT PLAN — the corpus that built the elder (2026-08-28)

Operator order: "we have a huge corpus of history of how the elder came to be…
all of these have taught us something, and I really need that audited in a
meaningful way by all these seats… if we do, it will literally allow us to
build the thing I've been dreaming about for years."

THEESIS: the room that remembers audits itself. The output is not nostalgia —
it is (a) the lineage map (how each law/organ actually came to be), (b) the
lessons ledger (one row per paid lesson, receipts attached), (c) V4 design
inputs (what the corpus says the next version must be).

## The corpus (surfaces + slices)

| Surface | Location | Size/shape |
|---|---|---|
| Verkle chain (signed truth) | memory/biography/verkle_chain.jsonl | 6,545+ rows, Aug 10 → now |
| VS Code seat sessions | the 66 chatSessions / ~700MB corpus + saved index | the deepest era transcript |
| Distillates | SELF/ (17 parts), seat-digest knot root fa0059c9 | already-compressed lessons |
| Docs + dossiers | docs/ref/ (~60 files), docs/concepts/ | the doctrine shelf |
| Eras | fleet-chronology (Aug 7 → 26): mega-build → OOM war → marathon → Sancho | the timeline spine |
| Named arcs | strike-the-cord → stateful → stateless → grounding waves → X account → council → vast | the elder's biography chapters |
| Other seats' exports | Cursor / ChatGPT / Copilot session exports where they exist on disk | drive inventory says: Desktop/Downloads corpus partly unmined |
| Memory fold | 84 chunks / 768 elder files on shared substrate | retrieval floor |

## Seat assignments (each audits a slice, same output schema)

| Seat | Slice | Question they answer |
|---|---|---|
| elder (deepseek) | the whole map, judge | "Given the lineage, what is V4's single load-bearing design?" (anchor: this plan + fold chunks) |
| grok seats ×2 | era mining: mega-build → OOM war → marathon | what did each era's failure teach that is still law today? |
| codex (ChatGPT) | session-tape mining: VS Code/Cursor/Copilot coding sessions | what building patterns recur across every era? |
| zai (GLM) | doctrine shelf: docs/ref + concepts | which docs are LAW, which are drafts, which contradict each other? |
| zcode (this seat) | chain + fusion | the lineage map + lessons ledger assembly, contradictions escalated |
| blade/seeker organs | (V4.1) tok/s probe data | the newest era writes its own row |

## Output schema (one row per lesson, append-only)

`memory/runs/lineage_audit/lessons.jsonl`:
{"era", "surface", "receipt" (file/chain ref), "lesson" (one sentence),
 "law_today" (which current law/organs carry it), "status": Supported|Disputed|Unproven}

## Sequencing (baby steps, dog food)

1. TONIGHT: timeline skeleton from existing distillates + chain (zcode, $0).
2. Next: grok seats mine era transcripts on free cached lanes (proven pattern).
3. Then: codex mines coding sessions; zai audits the doctrine shelf.
4. Elder judges the assembled ledger; contradictions escalate to operator.
5. Fold: lessons.jsonl feeds V4 build plan + the compiler's corpus packs.

## Why this is the dream

The Primer frame (surfaces project): every surface feeds one growing model.
This audit is that claim made operational — the fleet reading its own
biography, extracting the laws, and handing V4 a design that was *earned*
across every era instead of guessed in one night.
