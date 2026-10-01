# RETROSPECTIVE + V4.1 DESIGN — the night of Aug 27/28 (2026-08-28 morning)

The longest night in fleet history: lineage audit, four councils, the pal ranch,
the palace's first death test — and a failure ledger long enough to design from.

## THE FAILURE LEDGER (every miss, named)

| # | Failure | Class | Fixed tonight? |
|---|---|---|---|
| 1 | Sizer re-derived envelope + one_sizer | Reinvention | gate built |
| 2 | Governor re-derived mag/governor + compute_reconcile | Reinvention | gate built |
| 3 | Drains re-derived fuel_feed | Reinvention | gate built |
| 4 | count_words verifier demanded 8 in a 7-word phrase | Verifier lie | fixed + self-healed |
| 5 | council_runner starved answers (600→1536 tok) | Budget ceiling | fixed, then |
| 6 | zai argument EMPTY at 8192 (reasoning tax) | Budget ceiling | fixed at 16384 |
| 7 | deepseek Q4 empty 7/10 runs | Budget ceiling (unresolved) | OPEN |
| 8 | covenant key drift (_Lite vs _L extractor) | Key/name drift | fixed |
| 9 | Saelis pull EOF at 44% | Transport flake | resumed |
| 10 | First-session 404 on absent model | Honest fail (correct) | n/a |
| 11 | governor --test wrote live spend ledger | Test/live isolation | fixed |
| 12 | Lock SystemError crash (Windows os.kill) | Platform quirk | fixed |
| 13 | Double hunters alive simultaneously | Single-writer race | spec'd, not enforced |
| 14 | event.v1 emit-is-commit race | Single-writer race | spec'd, not enforced |
| 15 | Caps drifted: buyer 3 / governor 1 / docstring 2 | Single-source | covenant.json built |
| 16 | $5 experiment died silently at min 33 | SILENT FAILURE | OPEN — the bell |
| 17 | Blades idled 3h past boot before work | Idle burn | auto-wire built |
| 18 | Blades overstay lifetime 1.5h (reaper blocked by net errors) | Reaper fragility | OPEN |
| 19 | Ghost blade tunnels lingered after reap | Resource janitor | self-pruned, fragile |
| 20 | Dream host 138174 self-blacklisted via own tunnel | Lemon throttle missing | OPEN |
| 21 | Seat budget drained mid-arc (free tier) | Seat economics | leaned, structural fix OPEN |
| 22 | Self-steal gate skipped twice despite being law | Enforcement gap | HOOK BUILT |

## THE PATTERN: four root classes

**A. SILENCE (16, 18, 7, 19):** failures that produced no signal. The $5 experiment
died and nothing rang. The reaper failed and nothing logged. The model thought
itself empty and returned ok-shaped nothing. The ghost tunnels forwarded to
nothing until asked.
**B. REINVENTION (1, 2, 3):** the shelf held the answer; the build didn't ask.
**C. BUDGET CEILINGS (5, 6, 7, 21):** reasoning burned the budget before the
answer; the answer was silently truncated, never announced.
**D. RACES/DRIFT (8, 13, 14, 15):** three caps, two hunters, no single source.

## V4.1 DESIGN — the fleet that bells itself

**The one insight: every class-A failure (silence) is cured by the same organ —
the event.v1 stream with heartbeat expectations. Silence becomes visible the
moment the stream expects a sound.**

### New organs

1. **THE BELL (heartbeat monitor):** the governor's cadence tracks
   expected-events per organ (drain rows/min, seeker passes, lattice beats).
   Silence beyond threshold = `organ_silent` event = the divergence that wakes
   the seat. Cures class A: 16, 18, 19, and any future silent death.
2. **THE BUDGET ENVELOPE (per-call):** every LLM call carries
   `max_tokens sized to the task + an honesty assert`: empty content = failure
   event, never ok. Retry policy per class: ceiling-bump once, then route to a
   different body. Cures C: 5, 6, 7.
3. **THE PREBUILD GATE as a HOOK (built tonight):** Write/Edit of new .py runs
   the shelf check; dupe = block with MERGE/why-new paths. Cures B: 1, 2, 3
   structurally — the gate fires before the build exists, not after.
4. **THE COVENANT FILE as single source (built):** caps, floors, lifetimes in
   covenant.json; every organ reads; drift impossible. Cures D: 8, 15.
5. **THE COMMITTER (V4.0 spec'd):** governor sole mutator, O_EXCL lock,
   content-bound hashes; hunters/watchers/buyers EMIT intents. Cures D: 13, 14.
6. **THE LEMON THROTTLE:** blacklists become strike-counts with expiry;
   the dream host never gets banned by its own tenant again. Cures 20.
7. **THE SEAT BUDGET CADENCE:** premium seats run judgment beats only; bulk
   flows through free lanes and blades; the seat's own drift (token burn) is a
   lattice-visible metric. Cures 21.

### The iterate loop (per the operator's law: run, play, get data, dogfood, build)

Each night: the boxes work (Law 1), the stream records (the bell), the morning
reads the divergence (the palace), the build fixes the top class (the iterate).
The failures fund the version. The version eliminates the failure class. Repeat
until the classes stop repeating — that's how we know V4 is done: not when
nothing fails, but when every failure is a new class instead of an old one.

## SCORECARD

Tonight: 22 failures, 13 fixed or structurally cured, 4 open with named owners,
5 spec'd pending the committer build. Every failure class now has an organ or a
spec line. The fleet went from "failures nobody noticed" to "failures that file
themselves" in one night. Next: failures that prevent themselves.
