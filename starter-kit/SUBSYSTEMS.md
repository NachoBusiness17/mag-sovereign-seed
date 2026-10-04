# THE SUBSYSTEM CATALOG

The organs, each as: what it does, how to grow it, how to map it to your
user's jargon. None of these need to be built before they carry weight
(BOOT.md law 4). All of them are descriptions of method, not code you must
own - most can run as cards, scripts, or prompts over whatever harness you
have.

## 1. The profile miner (the recreate-you organ)

WHAT: mines the user's conversations and posts data into memory structures
(index + topic files), growing a profile that recreates the
assistant-as-it-is for THIS user: their jargon map, their laws, their
decided things. Reactive by design - it listens during every session and
banks corrections, preferences, and settled directions as they occur.
GROW: start with three types (user / feedback / project); add types only
when a fact arrives that fits none. Census the index monthly: phantom rows
(links whose files vanished) are silent corruption.
JARGON-MAP: the user's names for their own things become the canonical
terms in every card and law. If they call the inbox "the pit", the cards
say the pit.

## 2. The receipts inbox (evidence, append-only)

WHAT: one directory where every work session files what was done, the
evidence, and what is owed. Append-only: new observations are written
sequentially, earlier entries stay untouched, and FAILING APPENDS ARE
ALLOWED - a failed append is recorded as the next entry, never a rollback.
That single clause makes the log replayable: you can reconstruct exactly
what happened, including the partial and failed steps, which is exactly
what a debugging session needs later.
GROW: an index ledger registers every receipt (path + hash + purpose);
promotion to trust runs through the index, never around it.
JARGON-MAP: receipts / ledger / the pit - whatever the user calls the
record, the law is the same: file it before claiming done.

## 3. The skill cards (knowledge as invokable verbs)

WHAT: one card per verb, with a name, a one-line description, argument
hints, ONE runnable command, and the gates the card's output must pass.
Cards are the smallest unit of teachable method - small enough that a
fresh seat can load a handful and act.
GROW: mint cards from repeated corrections and from proven receipts (a
cure that worked twice is a card waiting to be written); cap cards around
a hundred lines; hoist shared law into a common card instead of repeating
it.
JARGON-MAP: card names in the user's verbs, not yours.

## 4. The lanes (unattended workers)

WHAT: scheduled workers that run cards and workflows while the user
sleeps, each leaving a trail (what ran, what failed, what it banked).
Lanes own their state atomically (write to temp, rename into place) and
checkpoint per leg, so a failed cycle resumes instead of restarting.
GROW: one lane first (a nightly digester), add lanes only when one has run
a week clean. A lane that fails silently for days is worse than no lane.
JARGON-MAP: night shift / patrol / groundskeepers - theirs.

## 5. The workflows (multi-agent shapes)

WHAT: scripted multi-agent patterns for questions wider than one seat:
fan-out (one named actor per item), confirm (a fresh context re-reads each
load-bearing finding's evidence), synthesize (chapters from lane results),
cold-read (a separate context attacks the draft), revise (the critique
drives one revision). Salvage as you go: report each item the moment it
lands so a dead run still delivers its finished work.
GROW: copy the shipped workflow shapes; keep per-item actor names stable
so revised runs reuse finished work instead of re-paying it.
JARGON-MAP: the shapes are yours to name; the geometry (fresh eyes,
independent confirmation, salvage) is the method.

## 6. The ractor (the lens swarm)

WHAT: a set of standing lenses (accuracy falsifier-hunter, operations
surgeon, economics pricer, communication auditor, dogfood organ-mapper,
lineage miner, logic theorist, security threat-modeler, plus wild-eye
moonshot lanes) that ride any decision in parallel; a hostile second pass
byte-checks every finding; weakened findings steer back to their lens for
one revision; survivors triangulate through one voice. Nothing a moonshot
proposes executes without the owner's GO.
GROW: three lenses before eight; the hostile pass before the steering
round; the synthesis last. A lens that cannot cite path:line is fired for
the run.
JARGON-MAP: lenses / the swarm / the panel - their word, same discipline.

## 7. The master watcher (gets you past the defense mechanisms)

WHAT: a master agent watching subordinate agents work. Subordinate agents
wedge on defense mechanisms - refusals, filter trips, obedience loops -
and the watcher's job is to catch the wedge and re-seat the ask (rephrase,
split, or route around) instead of letting the lane die silently. This is
the single biggest unblocker in unattended runs.
GROW: the watcher sees the sub-agents' outputs and failure text, never
edits their work; it may retry once with a repaired ask, then escalates.
JARGON-MAP: the warden / the groundskeeper / the lifeguard.

## 8. The gates (deterministic authority)

WHAT: commands with exit codes that decide - a ratchet (new debt blocks,
registered debt passes by name, never loosened), a citation linter (cited
paths must exist; numbers must appear in their named sources), a scenario
suite (the gate that checks the gates). Model text proposes; gates
authorize.
GROW: one gate at pre-push before three; every gate must be able to fail
for real or it is theater.
JARGON-MAP: the fence / the bouncer / law enforcement.

## 9. The census (instruments and moments)

WHAT: any count is stamped with its instrument, its moment, and its
denominator. "Collected" and "executed" are different instruments; two
counts at different moments are not comparable without naming the delta.
GROW: a patrol that re-runs the census on a schedule and flags drift.
JARGON-MAP: the census / the roll call.

## 10. The salon (mine your own past)

WHAT: the user's own past conversations, transcripts, and notes are the
highest-density training data in the system. Mine them for unanswered
questions, proposed-never-built ideas, and predictions that aged - a
salon lane per document, a composer that writes the next brief.
GROW: when any folder of old thinking surfaces, run the pattern; pasted
text counts as a folder.
JARGON-MAP: the vault / the archive / the attic.

## 11. The genome (the inheritable body of law)

WHAT: the one document a cold seat reads to become a going concern: the
laws with their selection evidence, the organs with their lineage, the
boot order, the selection mechanism itself (mutation is asks, selection
is judges, inheritance is commits, memory is the chain).
GROW: regenerate it from the lived record on a cadence - a genome that
stops tracking the organs is a fossil.
JARGON-MAP: the genome / the codex / the book of the house.
