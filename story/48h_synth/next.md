# THE NEXT 48: the forward memo (gala, division B, lane next)

Chapter 5 of the owed waltz. Filed 2026-09-30, late window, for the 48 hours of
2026-10-01T00:00Z through 2026-10-03T00:00Z. Input order: the prime's 5-move
order (watch/inbox/HERMES_PRIME_JUDGMENT_20260929.md), the OLM digest's steal
cards (watch/inbox/frontier_olm_20260928/DIGEST.md, S1 through S5; the 0930
round's two cards under watch/inbox/frontier_olm_2026-09-30/steal/), the elder
compaction re-raise conditions (watch/inbox/ELDER_CONSULT_COMPACTION_20260929.md),
and the owed set (xAI key rotation, recovery pack, heartbeat layer, injection
tests). Every status claim below was re-verified on bytes this session by
watch/inbox/gala_20260925/48h-synthesis/lanes/next.check.py; its raw output is
lanes/next.check.txt. No em dashes, ascii only, per the record laws.

## 1. The 5-move order versus the byte state

### Move 1, rotate the xAI key then scrub then snapshot: PARTIAL, the named half still open

What executed: the steps.jsonl leak arc closed same day after the external
audit found 7 live keys in HEAD. The operator rotated, the history was purged
(filter-repo, 0 refs reach key-bearing objects, 662dc739e), and the write and
commit gates landed, then caught a live re-try (imp10_operator_pool.jsonl
blocked at commit, 88ed0d729). Source: watch/inbox/DAY_SYNTHESIS_20260930.md
section 1.

What did not execute: the rotation the prime actually ordered, the mine's fuel
key. watch/inbox/KEY_ROTATION_JOURNAL.jsonl does not exist (checked this
session), so both closure conditions of watch/inbox/burn_wave_20260926/
B2_349_rotation_owed_20260926.md (journal rows, clean rescan) are unmet. The
B2-73 exposure set stands: 18 distinct real-shaped values including 2 xAI keys
in the corpus oral-history estate, xAI ordered fifth in the execution order.
AJ9 (2026-09-30) proved the rotation gap can hide at byte level: hermes env
still carried the pre-rotation Nous pair and the old SDD key was still 200
valid, "old key still valid (not yet revoked)" (watch/inbox/last_mile_20260930/
AJ9_NOUS_402.md probe table). Rotation is operator-gated: revoke is a
console action (B2_349: "OWED, operator-gated").

Cost of the deferral: the exposed XAI_SD key funds grok-4.7, the one funded
judgment rung besides Nous. The prime's own logic: a scraped key does not just
burn budget, it can get the account killed, which severs the mine's fuel line,
and all four other moves assume that account stays alive. Every day unrotated
extends the live window, and the ordering law (rotate BEFORE snapshot) blocks
the off-machine half of move 2, so this one deferral compounds into the
recovery pack. The old-still-valid pattern AJ9 caught is the theater risk the
prime named: rotating without revoking is half a rotation, and only the 401
probe can tell.

### Move 2, freeze the green commit as the recovery pack, off-machine, restore-tested: NOT DONE

Byte state: git tag returns empty (no green commit frozen, run this session);
restic is not installed (not on PATH, checked); scripts/backup_offsite.ps1
exists (8,578 B, 2026-09-30 13:36) but is design-only:
watch/inbox/OFFSITE_BACKUP_PLAN_20260930.md states "Nothing is scheduled,
nothing has been run against any real repository (no medium chosen yet)" and
its boundary section confirms NOT scheduled and NOT run. The only git remote
is a bare repo on the same physical disk (plan section 1). The green the prime
wanted frozen is perishable inventory: 3,550 collected / 455 files at the
2026-09-30 18:51Z census (B17_CENSUS.md), up from the 2,568 hermetic green the
order cited, and it decays with every landing.

Cost of the deferral: one disk event takes the estate, its only git remote, the
biography (363,630,271 B), the seals (216,654,445 B), state (98,288,609 B) and
.env in the same stroke (plan section 3 table). The prime called the green
window "the safest 48-hour window you will ever have"; that window opened on
09-29 and half of it is already spent without a snapshot.

### Move 3, steal-map the top finds, one eval each: CARDS EXIST, PORTS NOT FIRED

What exists: the 0928 mine banked 21 confirmed register rows and 5 steal cards
with estate maps and pre-committed decision rules (watch/inbox/
frontier_olm_20260928/DIGEST.md); the 0930 round landed 2 more cards
(agent-memory-continuity with 5 probes each marked "Status: OWED, not run";
kv-cache-context-engineering round 2). The mapping discipline held: 7 cards,
not 123 shallow ones.

What did not execute: every port. No probe/ directory exists in
watch/inbox/frontier_olm_20260928/ (S1's named receipt path, DIGEST.md run
plan); S5's probe output watch/inbox/ball2/abliterate_p1_runs_qwen25-3b.json
does not exist (ball2 enumerated this session). The primary target survives my
own read: mag/percolator.py:387-388 still returns status "repeat" with
"compiled": True on a count increment alone (no behavior eval, no baseline, no
rollback; the digest's line cite moved from :264-272 because the Z15 cure
rewrote the surrounding merge code, the promote path itself is unchanged), and
mag/seed_percolator.py still carries the designed paired-blind gate with "No
scheduler wiring" in its own docstring. The dormancy the digest verified on
09-29 is still the state.

Cost of the deferral: banked finds are decaying inventory (the prime's why);
the percolator keeps promoting on recurrence with no held-out test, the exact
gap six confirmed papers define; and the halt rule (three mapped finds moving
zero evals means re-grade the mine) has never fired only because zero finds
have been mapped. Decorative text is the failure mode, and so far the cards
are exactly that: read, mapped on paper, never wired.

### Move 4, build the heartbeat, renderer as first customer: PARTIAL, one organ of four on cadence

What executed: the bake has a cadence. EstateWalkDaily is registered and Ready
(next run 2026-10-01 09:15 local, schtasks queried this session) and
scripts/estate_walk_daily.ps1 re-bakes the estate walk tapestry daily with a
loud-failure line to memory/attention.md on nonzero exit (the dead-man's
channel the order called non-negotiable). The log holds exactly one fire, END
2026-09-29T22:16:50Z exit=0 (logs/estate_walk_daily.log), so the cadence is
armed but has zero scheduled fires to its name; tomorrow morning is its first
proof.

What did not execute: the one scheduler owning bake plus watchlist poll plus
driver drain plus nightly suite. The watchlist poll is the load-bearing gap:
configs/watched_channels.yaml holds the whales (karpathy, swyx and more) and
mag/whale_patrol.py has the commands (cmd_watchlist :225, cmd_feed :262), but
no scheduled task polls them (full schtasks list this session: no whale or
watch entry). The driver drain gauge is a named gap on the same day:
watch/inbox/CYCLE_BRIEF_20260930.md quota shape reads "[quota report empty -
HONEST-GAP]", so the fleet cannot see its own fuel.

Cost of the deferral: the watchlist is upstream of the mine's replenishment
(the prime's move 5 warning); an unpolluted watchlist that is never polled
means the mine starves while looking alive. The bake is the only organ on
cadence and it is unproven until it fires on schedule; three of the four
cadence customers the order named do not exist yet.

### Move 5, injection-test the wired loops end to end through the MCP bridge: NOT RUN

Byte state: no injection-test receipt exists (grep over watch/inbox/
wave5_repair/ and watch/inbox/ball2/ for inject returns one incidental match,
suite-burn.md). The attention market ledger memory/attention_feedback.jsonl
holds exactly 2 rows, both self-cast by the ball2 lane on 09-29 (mtime
2026-09-29 10:48, wc -l = 2 this session); no trade has landed since. The MCP
bridge side is the done half: six estate tools pinned under the gate
(state/mcp_pins.jsonl, 92 rows; the lattice chapter's crossing B).

Cost of the deferral: "wired" remains a topology claim, not a throughput claim
(the prime's own words). A watchlist poll that silently yields zero rows, or a
market nothing reads, would surface weeks late; the 19-fossils failure mode is
still live for the two newest loops. The market's 2 rows are the lane's own
honest signals, which is exactly the write-only shape the order warned about:
nonzero, but not consumed by any downstream run since.

## 2. What the estate did right against the order

1. The sequencing instinct was honored on the biggest leak. Rotate, purge,
   gate, all in one day, and the gate then caught its own first live re-try.
   The steps.jsonl arc is move 1's template applied to the leak the external
   audit found; the residual exposure is the corpus set, not the repo set.
2. The non-moves held. No abliteration beyond its re-raise criteria (zero
   further spend banked), no full-123 mapping (7 cards total across two
   rounds), no hand-fix of the bake (a cadence was registered instead of a
   one-time repair). The compaction program stayed parked with named,
   checkable re-raise conditions (chain mass over about 1 GB or 1,000,000
   leaves, mem-lattice declared as an organ, restore SLA breach, storage
   regime change; none fires today), and nothing was executed against the
   append-only spine (ELDER_CONSULT_COMPACTION_20260929.md).
3. The heartbeat landed with its alarm wired, not just its timer. Failure
   pages memory/attention.md by design in the task script itself; silence is
   no longer free on the one organ that has a cadence.
4. The bridge half of move 5 was done in the right order: expose under a pin
   gate first (drifted tools withheld from the manifest), injection-test
   second. Testing ungated surface would have repeated the 19-fossils
   mistake with an audience.

## 3. THE NEXT 48 (2026-10-01T00:00Z through 2026-10-03T00:00Z)

### Fires autonomously (no console, no key mints, no operator word needed)

A1. Tag the green commit locally. git tag is reversible and exports nothing,
    so the ordering law does not reach it: tag the commit carrying the
    2026-09-30 census state as recovery-pack/20260930-green and write the
    pointer row into the offsite plan's runbook section. The off-machine ship
    stays gated behind move 1.

A2. First port fires, find one of the top 12 (move 3). The S2 constrained
    decode probe on gemma:2b: 30 of the released sml_mcp_benchmark prompts,
    two arms, unconstrained versus format equal to the JSON schema, 0 dollars
    local, receipt at watch/inbox/frontier_olm_20260928/probe/
    S2_constrained_gemma2b_20261002.md. The card's decision rule is already
    pre-committed (arm b missing 100 percent or costing over 10 percent
    throughput falsifies the constrained arm; arm a at or above 50 percent
    strict-parse makes the full gate overkill for gemma:2b).

A3. Watchlist poll cadence lands, then the injection test (moves 4 and 5).
    Register a whale-patrol poll task in the Estate task pattern (feed and
    watchlist commands exist at mag/whale_patrol.py:225 and :262), log to
    logs/, loud-fail to memory/attention.md. Then run move 5 through the MCP
    bridge: one synthetic statement attributed to a watchlist handle must
    surface as a find within one poll cycle, and N market interactions must
    leave memory/attention_feedback.jsonl nonzero AND consumed, meaning a
    downstream build_ranked_attention pass whose inputs changed.

A4. Judgment spend per the standing SPEND order rides grok-4.7 on XAI_SD
    while Nous primes stay 402-blocked on prime-model reservations (AJ9:
    cheap calls pass, prime reservations exceed the pool). Every paid
    dispatch banks usage in its receipt; the 20-prompt funded spot-check leg
    of A2 rides grok-4.7. Hoarding the funded lane while free lanes grind is
    the drain bug in money form; the operator order stands.

A5. The nightly suite run joins the heartbeat as its fourth customer (the
    order's list: bake, watchlist poll, driver drain, nightly suite), giving
    the recovery pack a standing readiness meter and the green tag a nightly
    re-proof.

### Waits for the key (operator console, minutes of work)

K1. The xAI SD key: revoke old, mint new, update .env, append the journal row
    (masked heads only), then run the prime's two probes: one API call with
    the old key must 401, and a repo-wide plus history grep for the old
    string must return only tombstones. Either failing means the rotation is
    theater. The same console pass covers the B2-349 execution order (ZAI,
    OpenRouter, Groq, DeepSeek, xAI, Anthropic, OpenAI, Vast) and closes the
    old-still-valid pattern AJ9 caught on the Nous pair.

K2. Only after K1: the off-machine half of move 2. restic go-live plus the
    -Verify restore test (chain gate runs against the restored copy, must
    pass). Rotate before snapshot is the whole point: backing up the recovery
    pack before scrubbing exports the leak off-machine.

### Waits for an operator word

W1. The medium for the offsite repository (OFFSITE_BACKUP_PLAN section 4,
    options A through D; C is free and off-machine today over Tailscale, D is
    cents per month on B2). The 3-command runbook is staged; nothing runs
    until a medium is named.

W2. The Nous portal door: credits check or top-up at portal.nousresearch.com.
    The API exposes no balance endpoint (AJ9 section 3, four 404s), so the
    portal is the only instrument that decides 171 dollars versus near-empty.
    Until then primes stay blocked and judgment rides grok-4.7 per A4.

W3. Any action that would mint or place credentials into a new surface
    (new CI secrets, container images, shell history on another box): the
    prime's named failure mode for move 1 is a leak that survives rotation.

### Stays parked

The compaction program (no elder re-raise condition fires today). Abliteration
stays archived at its re-raise criteria, zero further spend. The full-123
mapping stays refused. The hand-fix of the bake stays refused; the cadence is
the fix.

## 4. Falsifiable forecasts (named signals, named dates)

F1. At 2026-10-01T23:59Z, watch/inbox/KEY_ROTATION_JOURNAL.jsonl still does
    not exist. Falsified by: a journal row naming xAI with masked heads at
    that moment, which would also falsify "operator-gated, no signal pending".

F2. By 2026-10-02T23:59Z, watch/inbox/frontier_olm_20260928/probe/
    S2_constrained_gemma2b_20261002.md exists with a verdict from the card's
    pre-committed rule. Falsified by: no probe receipt at that moment, which
    triggers move 3's own halt rule (re-grade the mine before find four).

F3. At 2026-10-03T00:00Z, memory/attention_feedback.jsonl has more than 2
    rows, at least one written by the injection test rather than a gala lane
    self-cast. Falsified by: the ledger still holding exactly the 2 rows of
    09-29, which confirms the market is write-only and move 5 failed loud.

F4. By 2026-10-02T23:59Z, a scheduled watchlist poll has fired at least twice
    with log lines naming rows fetched. Falsified by: no new task in
    schtasks or an empty log at that moment (the poll cadence did not land).

F5. At 2026-10-01T23:59Z, a local tag recovery-pack/20260930-green exists.
    Falsified by: git tag still empty at that moment.

F6. logs/estate_walk_daily.log gains END lines with exit=0 for the scheduled
    fires of 2026-10-01 and 2026-10-02 (09:15 local). Falsified by: a missing
    END line (the cadence is a decoration) or an ESTATE-WALK-BAKE-FAILED line
    in memory/attention.md (the loud channel working, the bake red; either
    way "green cadence" is dead).

F7. Through 2026-10-02T23:59Z, metered judgment rows in logs/
    provider_usage.jsonl name grok models and no successful glm-5.3-prime or
    qwen3.8-max-prime row appears, unless the portal door opens. Falsified
    by: a prime-model 200 row, which is the receipt that the portal was
    topped and the SPEND order re-routes to the primes.

## 5. Decision ledger

This dance closes the waltz's what-next question. The prime's order survives
contact with the byte state unchanged in sequence (rotate, then snapshot, then
ports, then cadence, then injection) and changes in exactly one split: the
green tag (local, reversible) is separated from the off-machine ship
(operator-gated), so move 2 half-fires without the key while the ordering law
stays intact. The deferral costs named in section 1 are the price already
paid; the forecast battery in section 4 is the instrument that catches the
next 48 going silent.
