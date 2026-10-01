# LANE ASK TEMPLATE v2 - the canonical ask shape (Mickey17, 2026-09-29)

v1 was practice, never a file: MISSION + context + ownership + a report cap. v2 lands the two fields the S7 steal showed Anthropic's subagent contract has and ours lacked: an EFFORT BUDGET (tool-call tiers; our asks capped words but never tool calls) and a NON-OVERLAP declaration (their duplicated-search failure is our G1/G3 double-fire; every ask names what siblings already cover). Copy the eight fields below into every lane ask. Receipt: `watch/inbox/W3O_LANE_TEMPLATE.md`.

## The shape

1. **LANE + MISSION** - one ID (wave letter + ordinal) and one sentence naming the deliverable, not the activity.
2. **CONTEXT POINTERS** - paths only, no pasted content. The lane reads; the ask points.
3. **FILE OWNERSHIP** - the exact files this lane may create or edit. Everything else is read-only. State the git rule (default: DO NOT commit).
4. **EFFORT BUDGET** - tier from the ladder below: max tool calls + max cycles. Hitting the cap is stop-and-file, never self-extend; ask for more in the report.
5. **NON-OVERLAP** - name what sibling lanes already cover and what this lane therefore will NOT do. Duplication is a defect in the ask, not the lane.
6. **LAWS** - em-dash 0 (instrument-checked, not eye-checked); receipts before speech; real counts from instruments only (never hand-copied); no fabrication, every claim path-cited.
7. **REPORT CONTRACT** - word cap + the must-include list: real counts, files landed (absolute paths), budget spent, what was left to siblings.
8. **DEATH RECEIPT** - the clause that makes death cheap: if the lane dies (429/1302, interrupt, budget exhaustion), the next actor finds partials + resume point + remaining budget + what not to redo. Death is a HOLD signal, not a failure (envelope law).

**Effort ladder (house adaptation of the S7 tiers):** TIGHT dig or fix: 1 cycle, 10 tool calls. STANDARD build + tests + receipt: 3 cycles, 40 calls. DEEP iteration loop: 6 cycles, 120 calls, resume by ID rather than respawn (topology doctrine).

## Filled example: the W3m God's Number lane

> **LANE W3m + MISSION:** compute the Mountain's God's Number: the exact diameter of the water-board state space (worst-case minimum staged actions from the start board to every reachable legal board), and exhibit one hardest witness state with its optimal line replayed on the real engine.
> **CONTEXT POINTERS:** `watch/inbox/MICKEY17_WAVE_LEDGER_20260929.md` final DROP (cube reference: 43 quintillion states, 18-regular, diameter 20, Rokicki et al. 2010) - `mag/water_graph.py` (engine ground truth) - `server/world.py` + `server/protocol.py` (tick is the sole mutator; stage-then-apply is the BFS branching operator) - `watch/inbox/W3K_LEGALITY_DS.md` (the legality-dataset lane's enumeration: consume it).
> **FILE OWNERSHIP:** new `tools/water_gods_number.py`, new `tests/test_water_gods_number.py`, receipt `watch/inbox/W3M_GODS_NUMBER_20260929.md`. No engine edits. DO NOT git commit.
> **EFFORT BUDGET:** STANDARD: max 40 tool calls, max 3 cycles (BFS + counts; witness replay + tests; receipt). If the space blows past feasible BFS, stop at budget and file the bound reached: that is a result.
> **NON-OVERLAP:** the legality-dataset lane enumerates states: consume, never re-enumerate. S2/S3 lanes own sync and persistence: no snapshot proposals. W2 owns mag/ gates: no baseline edits. Engine bugs found get a receipt line, not a fix.
> **LAWS:** em-dash 0; the diameter claim names states counted, edges counted, and the board hash, all from the tool's own output lines; no hand-copied numbers.
> **REPORT CONTRACT:** max 120 words: diameter, reachable-state count, measured branching factor, witness line length, files landed, pytest pass count from real output, budget spent.
> **DEATH RECEIPT:** partials on disk + one-sentence resume point + budget remaining + what not to redo.
