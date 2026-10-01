# HARNESS SPEC v1 — the constitution of the game harness (2026-08-28)

Fused from four council seats (HARNESS_{grok,codex,deepseek,zai}.md). The law
as target: *as bare metal as possible so any game surface can interpret the same
data — from mud to Dark Souls — without stepping on each other.* Grok's finding
governs the build: **the law is a target, not a description** — tonight's code
violates it in six named places, and this spec is the fix order.

## THE CONSTITUTION

1. **ONE stream**: `event.v1` — `{ts, organ, kind, body, prev_hash}`. The six
   current ledgers (spend, wedge, lessons, lattice, blades, q_knots) become
   event kinds in one stream. No seventh ledger, ever.
2. **ONE committer**: the governor. Hunters, watchers, buyers, surfaces EMIT
   intents and kinds; only the governor commits. Surfaces never mint `kind`.
3. **Players write INTENT as signed events; the governor writes STATE as
   reconciled mutations.** Player → surface → signed event → stream → governor
   reconciles. A surface that writes state directly is a fork; forks are reaped.
4. **Surfaces are read-only interpreters** over the stream + the governor's
   canonical projection (hash-persisted each beat). Caches allowed; on any
   conflict, re-derive from canonical. Derivation is idempotent.
5. **Contradictions resolve by hierarchy of invariants, not consensus** (elder):
   spend > wedge > lessons > lattice > blades > q_knots. A surface displaying
   what the covenant denies is a buggy interpreter.
6. **Render free, steer paid** (zai): no model calls in any render path; views
   are free forever; the scarce good is steering. $1 = one governor-accepted
   `paid_intent` event.
7. **Fun is the gate** (Adam): every surface passes through it or doesn't ship.

## THE SCHEMA (event.v1 + economics envelope)

`{ts, seq, prev_hash, organ, kind, actor_id, actor_type, pos, cause_id,
cost_delta, balance_after, stakes, ttl, tags, body}`

- `pos` — room/coordinates (without it Zelda is unbuilt forever)
- `cause_id` — causal parent (quest chains, death replays)
- `cost_delta` + `balance_after` — covenant as a fold over the stream
- `stakes` — mud shows all; Souls filters stakes > 0
- `ttl` + explicit death events — permadeath needs death EVENTS, not absences
- `seq` + `prev_hash` — mandatory before real money (replay + tamper evidence)

## EVENT KINDS (the game nouns, first-class)

`hunt_ask / hunt_gate / hunt_ready / hunt_wedge / hunt_reap` (whaler hunts) ·
`assumption_falsified` + receipt hash (dragons) · `quest_open / advance /
complete / fail` · `panel_open / intent / confirm / reject` (salon) ·
`replica_spawn / uncouple / idle / reap` (pals) · `covenant_breach /
permadeath` (governor-only) · `stream_offset / projection_hash` (cursor) ·
`spend / drain / probe / lesson` (the existing organs, rekindled).

## MIGRATION — the six violations, in fix order

1. Governor `--test` writes to live spend ledger → isolate to test fixture. [bug, mine]
2. Caps drifted (buyer 3 / governor 1 / docstring 2) → one covenant config,
   single source, all organs read it.
3. TOCTOU lock → atomic create (os.O_EXCL) or lock service; Windows-kill ambiguity fixed.
4. Hunters mutate instances outside the lock → hunters EMIT `hunt_ask` intents;
   governor commits. Auto-wire moves into the governor's beat.
5. game_mud/campaign set_state → surfaces become pure readers over event.v1.
6. Two governors (desk compute_reconcile + vast governor) → merge: one cadence,
   compute_reconcile absorbs the vast arm (the standing ruling).

## THE ORG CHART (as ruled)

Governor = the covenant, personified (sole mutator). Elder = design arbitration.
Saelis = research direction (chair armed when weights land). Sancho = custody +
filing. Adam = taste and shipping judgment, never truth mutation. Operator =
covenant owner; reads receipts, never pokes organs.

## THE LAW, FINAL FORM

*Players write intent. The governor writes state. Surfaces give sight.
The stream remembers. The covenant decides. Fun ships it.*
