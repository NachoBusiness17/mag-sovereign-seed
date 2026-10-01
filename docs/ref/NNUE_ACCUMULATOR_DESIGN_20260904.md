# NNUE ACCUMULATOR DESIGN — patch, don't re-encode (2026-09-04)

Source: `watch/INTAKE_NNUE_ACCUMULATOR_20260904.md` (score 18/25, BUILD WINDOWED).
Primitive: Stockfish NNUE maintains a running latent vector; when a piece moves it
adds/subtracts that piece's weight vector — incremental linear algebra, no full
forward pass. Fleet translation: our agents re-encode the world every turn; they
should patch a running latent instead. **Tri-state: this is a design note.
Nothing below runs until a prototype exists.**

## SURFACE 1 — AGENT CONTEXT AS ACCUMULATOR

One running latent per seat. Never re-read full history on a turn; patch it.

**What the latent holds** (small, inspectable, per seat):

| Field | Shape | Purpose |
|---|---|---|
| section pointers | map: topic -> file/line + row-id | WHERE truth lives, not the truth itself |
| recency weight | float per topic, decayed each patch | what is "live" right now |
| certainty | float per entry (see Surface 3) | calibrated trust per fact |
| open-question flags | set of unanswered threads | what the seat still owes |

**Patch operation per room row type** (room row lands -> one O(1) patch):

| Row type | Patch |
|---|---|
| card | add pointer + recency=1.0; open-question if it spawns a build |
| receipt | set certainty on the cited card's entry; close matching open-question |
| correction | flip the corrected entry: subtract old delta, add new, mark superseded |
| wire | update recency only; no certainty change (transport ≠ truth) |

**Decay rule:** every topic's recency multiplies by a fixed factor per N rows
(start 0.9 / 50 rows); entries below floor (recency < 0.1 AND no open flag) are
compacted to a bare pointer. Correction always beats decay — a corrected entry
re-enters at recency 1.0. Decay is mechanical, never judgment.

**LAW 1 — the seat reads the latent, not the log.** Full-history reads are the
exception (rebuild, audit, dispute), not the turn path.
**LAW 2 — patches are idempotent by row-id.** Replaying a row must not double-apply.

## SURFACE 2 — THE VERKLE PRECEDENT (and where it stops)

The chain already runs this pattern; document it so nobody reinvents it badly:

| NNUE concept | Verkle chain analog |
|---|---|
| running latent vector | `parent_verkle_root` — the running root each knot hangs off |
| per-piece delta | the knot payload itself (a delta, not a snapshot) |
| gated update / eval rollback | amend — a GATED patch (operator-confirmed), not silent overwrite |

Tri-state on the mapping: Supported — chain is append-only patch accumulation on
a running root, receipted in `memory/biography/verkle_chain.jsonl`.

**The boundary — do NOT conflate:** the chain accumulates MEMORY OF RECORD
(append-only signed truth; a knot once written never changes meaning). The agent
accumulator is WORKING BELIEF (mutable, decayed, correctable in place). One is
evidence, the other is hypothesis. The accumulator cites the chain; the chain
never consults the accumulator. If an accumulator repair is warranted, it lands
as a correction KNOT — the chain's gated patch — and the latent rebuilds from it.

## SURFACE 3 — CALIBRATION COUPLING (two axes, not one)

From the intake's calibration law: "one wild leaf poisons a cutoff" — usually-
brilliant-but-occasionally-insane is poison inside a planner. Recency alone is
half a score: a stale-but-RECEIPTED fact outranks a fresh-but-WILD one.

**Two-axis entry score:** `rank = recency x certainty`.

- recency: mechanical decay (Surface 1).
- certainty: 0.2 Unproven (default for any new entry) → 0.8 Supported (a
  receipt, a measured probe, a verified claim) → 1.0 anchor (chain-knotted or
  operator-confirmed). A DISPUTED finding sets certainty near 0 until repaired.
- Certainty only moves via receipts and corrections — the claim-organ's
  vocabulary, unchanged. The accumulator is a consumer of calibration, not a
  second calibrator.

**THE FALSIFIER (measure BEFORE building, per the AlphaEvolve measurable-objective law):**

> An agent running on the accumulator should cite fewer stale facts per 100
> turns than an identical agent re-reading full logs.

Measurable from `room.jsonl` traces: define "stale citation" = a fact cited
after its correcting row landed (row-id arithmetic, mechanical). Baseline agent
(full-log reads) vs accumulator agent, same 100-turn corpus. Decision rule:
accumulator must win on stale-citations-per-100 AND not lose on correctness
spot-checks; otherwise the design is falsified and the note gets an amended
knot, not a quiet tweak.

## BUILD ORDER

1. **Falsifier measurement first** — $0, pure room.jsonl replay, produces the
   baseline number the accumulator must beat. No accumulator code yet.
2. **Latent + patch op prototype** — smallest script that consumes room rows
   and maintains the latent; verify idempotence against a replayed trace.
3. **Certainty axis** — joins once receipts exist to feed it; without Leg-1
   receipts this axis is Unproven and stays at default 0.2 (honest floor).
4. **Seat wiring** — only after 1–3 show the win. Never before.

## HONEST BOUNDARY

This is a design note. No latent exists, no patch op runs, no decay fires.
Tri-state: the NNUE mapping is Supported (receipted primitive); the two-axis
scoring is Unproven until the falsifier measures it; the whole build order is
proposed, not scheduled. First move costs $0: replay room.jsonl and count
stale citations.
