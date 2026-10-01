# THE OWED WALTZ: Chapter 4 - THE MEASURE

The 48-hour delta (2026-09-28 00:00 EDT through the measurement moment, 2026-09-30
22:10:22Z on the check bundle), every number receipted or measured in this lane's session.
Filed by the measure lane of the 48h-synthesis division (archive:
watch/inbox/gala_20260925/48h-synthesis/lanes/measure.json).
Raw check output: watch/inbox/gala_20260925/48h-synthesis/lanes/measure.check.txt.
House laws honored: no em dashes, no invented numbers, a count names its instrument and moment.
Sibling chapters read before writing: watch/inbox/48h_synth/STORY.md (Chapter 1) and
watch/inbox/48h_synth/lattice.md (the lattice chapter), watch/inbox/48h_synth/next.md.

## 1. The suite: 19F/2529P to 0 named failures, then the floor moved

- **Start of window:** the 42:05 post-ball run read **19 failed / 2,529 passed**. Honest
  provenance: that run itself has no receipt; the number survives as a lane's reference to it:
  "No receipt of the 42:05 run (19F/2529P) exists anywhere I searched"
  (watch/inbox/ball3/quantizer-fallout.md:33).
- **Mid-window:** the wave5 suite-burn lane took the 14 named failures (10 real from
  flash50/f-15.md plus 4 mock-caused from flash50/s2-19.md) and burned all 14 to zero at root
  cause with no assertion weakened; its full-suite finish line reads "14 failed, 2452 passed,
  12 skipped, 8 warnings in 2326.98s (0:38:46)" with all 14 survivors byte-proven
  basetemp-environmental (watch/inbox/wave5_repair/suite-burn.md:227 and the root-cause table;
  raw log watch/inbox/gala_20260925/wave5-repair/lanes/suite-burn.check.txt).
- **Late window:** ball3's authoritative full-suite re-run read **2 failed, 2566 passed,
  12 skipped, 47:01, exit 1**, neither failure one of the fallout nine
  (watch/inbox/ball3/quantizer-fallout.md:53-55, raw quantizer-fallout.fullsuite.txt).
- **Certified state:** **2,568 hermetic green**, ruled perishable by the funded judgment:
  "2,568 hermetic green is a perishable state; the next commit begins the entropy"
  (watch/inbox/HERMES_PRIME_JUDGMENT_20260929.md:15-16, restore probe: anything under 2,568
  means the pack is incomplete).
- **End of window:** the census instrument reads **3,550 tests collected / 455 files
  (2026-09-30 census)**, 26.31s, zero collection errors, 14:51:47 EDT
  (watch/inbox/last_mile_20260930/B17_CENSUS.md; carrier line AGENTS.md Tests bullet).
- Not re-run by this lane: the full suite. The ask asked for receipted numbers; each number
  above carries the instrument that produced it (pytest -q serial runs at named moments, one
  --collect-only census). Per the denominators law, collected and executed are different
  denominators and are not differenced here.

## 2. Lanes danced: 24 (the repair waves' denominator), receipts in hand

The story chapter's arithmetic, now live-verified: **12 + 9 + 3 = 24** lane JSONs across the
three repair waves, and this lane re-ran the fold gate on every ball this session:

| ball | lanes | ballroom (danced/refired/buried) | gate |
|---|---|---|---|
| wave5-repair | 12 | 12/0/0 | GATE PASS rc=0 |
| ball-20260929 | 9 | 8/0/1 (buried: abliterate-p1, empty-on-refire shape) | GATE PASS rc=0 |
| ball3-suite-green | 3 | 3/0/0 | GATE PASS rc=0 |
| ball4-luncheon-follow | 4 | 3/0/1 (buried: follow-capital-policy) | GATE PASS rc=0 |

Commands: `bash fold_gate.sh <lanes-dir> <expected>` x4 from watch/inbox/gala_20260925 (raw in
measure.check.txt). Precision the headline rounds off: 24 counts the three repair waves; ball4's
4 luncheon lanes danced after that count, and 1 of ball-20260929's 9 was buried rather than
danced, so the receipts' precise arithmetic is 23 danced + 1 buried + 4 ball4 lanes = 28 lane
JSONs across the four balls. Wave receipts: watch/inbox/gala_20260925/wave5-repair_RECEIPT.md,
ball-20260929_RECEIPT.md, ball3-suite-green_RECEIPT.md, ball4-luncheon-follow_RECEIPT.md.

## 3. Commits landed: 233, then 234 - a live-tree count, moments named

Measured this session, instrument `git log --since="2026-09-28 00:00"`: **233 commits** at the
~17:50 EDT reading moment, then **234** at the check-bundle moment (2026-09-30T22:10:22Z,
measure.check.txt): 143 on 09-28, 52 on 09-29, 39 on 09-30. The +1 delta is the live tree
landing a commit between the two readings - named per the census-denominator law (B2-216),
never differenced silently. Before-window boundary: ee9bf7545 2026-09-27 22:53:18 -0400. Note
this is branch-local truth: the repo's history purge on 09-30, commit 662dc739e, rewrote
history by operator GO, so pre-purge hashes are preserved but refs were re-pointed.

## 4. Tokens spent: the receipted rows, and one unverified headline

Receipted paid usage (each row byte-read from its receipt):

| spend | usage | receipt |
|---|---|---|
| Hermes prime judgment (glm-5.3-prime, Nous) | 6,581 tokens, $0.0560888 | watch/inbox/HERMES_PRIME_JUDGMENT_20260929.md:3 |
| Elder consult (glm-5.3-prime) | 2,654 tokens, $0.02115576 | watch/inbox/ELDER_CONSULT_COMPACTION_20260929.md:7 |
| grok-4.7 luncheon intel (xAI SD) | 5,365 tokens (1,152 cached) | watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md:3 |
| Duel harness, retroactive judge | $0.0248 | watch/inbox/DAY_SYNTHESIS_20260929.md:51 |
| Night burn N1-N6 (glm-5.3-prime) | $0.41 total, 6/6 non-empty | watch/inbox/last_mile_20260930/NIGHT_BURN_RECEIPT.md |
| Gopher burn G1-G6 (Nous) | $1.43 total, 11/12 empty returns | watch/inbox/last_mile_20260930/GOPHER_BURN_RECEIPT.md |

**The 191.8M-token mine headline is UNVERIFIED and is reported as such.** It is carried by the
story chapter ("191.8M tokens spent", watch/inbox/48h_synth/STORY.md:240) with DIGEST.md named
as source, but the named source does not carry it: grep for "191" and "token" over
watch/inbox/frontier_olm_20260928/DIGEST.md returns content mentions only, no total (raw in
measure.check.txt). The mine's run journal
(.zcode/workflow-runs/dwfrun-c41194a8-e725-4bd7-8ee8-5f46206f8fde.mjs) is a compiled payload
snapshot with no token totals, and this lane's workflow introspection is unavailable
(workflow_introspection_unavailable), so the run-record total was unreachable. What IS
receipted about the mine: 32 of 32 sweep returns ok, 21 confirmed finds, 3 unconfirmed held,
5 steal cards, six PASS rows in memory/workflows/REGISTRY.jsonl lines 31-35 and 38
(watch/inbox/frontier_olm_20260928/RECEIPT.md). Ball4's four lanes were seat-local with no
metered-spend receipt on disk; the ball's paid piece is the grok-4.7 run above. This lane
cannot meter its own seat tokens (no self-instrument available here); stated as such.

## 5. Fossils superseded: 19

`ls watch/inbox/ball2/graves/` = **19 grave-NN receipts** (grave-01-index-foldback.md through
grave-19-verkle-rib-export.md) plus grave-supersede.check.txt and grave-supersede.jsonl
(count in measure.check.txt). The grave-supersede division-C lane graved **19 of 38** stale
queue/handoff JSONs receipt-only with disk-verified successors and 23 index_events rows
(watch/inbox/gala_20260925/ball-20260929_RECEIPT.md, fold scoreboard and filing verdict).
The funded judgment used the number as diagnosis: "Building new lanes on unverified ones is
exactly how you got 19 fossils" (watch/inbox/HERMES_PRIME_JUDGMENT_20260929.md:30).

## 6. Laws minted (four instruments, four receipts)

- **LINKS ledger:** 178 -> 205 across the window's filings (per-wave: 190->198 in
  ball-20260929 filing, ->201 in ball3, ->205 in ball4; each RECEIPT's filing verdict).
  Measured now: 205 rows (wc -l memory/corpus/LINKS.jsonl).
- **Oral-law index:** 33 -> 63 (V10 grok-pool mine, 30 rows, $0.00 seat-local,
  watch/inbox/last_mile_20260930/V10_TASK_MINE.md) -> **183** (B9 codex-pool mine,
  153 -> 183, watch/inbox/last_mile_20260930/B9_CODEX_LAW.md, including the resume-collapse
  catch: 193 rollout files -> 87 logical sids). Measured now: 183 rows.
- **Compiled flash laws:** 902 chars / 12 rows, which rendered in 0 of 6 modes before the
  render-pipe repair and 6 of 6 after, within budget, zero clip markers
  (watch/inbox/wave5_repair/render-pipe.md:7, :23, :42).
- **memory/law/:** 9 law .md files on disk (ls count; independently named by the seed-kernel
  receipt's "9 memory/law/*.md").

## 7. Organs wired

- **MCP bridge: 6 tools / 5 verbs live over stdio** - estate_water_graph_tick,
  estate_dirac_scan, estate_dirac_rank, estate_chain_verify (dry only),
  estate_thought_compile, estate_driver_status (redacted); chain repair, dirac bank, driver
  control words and keys ruled never-exposed; 13/13 probe PASS + 262 consumer tests
  (watch/inbox/ball2/mcp-bridge-r1.md tool table; fold verdict in
  ball-20260929_RECEIPT.md).
- **Attention ledger: ABSENT -> proven rails** - first two settled trades, settle-once by
  cast_id (replay returns duplicate:true and appends nothing), five-signal vocabulary
  unified, 18 tests green; the next ranking pass provably consumed them
  (watch/inbox/ball2/attention-ledger.md).
- **Render pipe: 0/6 -> 6/6** - directives, compiled laws, doctrine, bounded objective and
  task brief render in all six modes within budget, every shed receipted as its own
  PACK_OFFLOAD row, new tests pin it (watch/inbox/wave5_repair/render-pipe.md:23, :42).

## 8. Cadence registered (the window's cure for things-without-cadence-die)

Live-verified this session via `schtasks /Query /FO CSV` unless noted:

| cadence | task | evidence |
|---|---|---|
| tapestry bake 09:15 | EstateWalkDaily "10/1/2026 9:15:00 AM Ready" | schtasks (this session) + .agents/skills/frontier-mine/SKILL.md:30 |
| mine 10:00 daily | fires after the 09:15 bake via cron (automation-cac38363) | .agents/skills/frontier-mine/SKILL.md:30-32 + commit 6a1c70ec9 (via STORY.md section 10); the automation id is a harness cron, not a schtasks row - receipted, not schtasks-verified |
| census patrol 08:30 | MagCensusPatrolDaily "10/1/2026 8:30:00 AM Ready" | schtasks (this session); AGENTS.md B2-246 bullet |
| FTS index 09:00 | MagFtsIndexDaily "10/1/2026 9:00:00 AM Ready" | schtasks (this session); AGENTS.md B2-465 bullet |

Also live on the surface (same schtasks query): MagImproveDaily 08:00, MagGapSentinelDaily
08:15, MagGateCanaryDaily 09:45, MagQCaptionVerifyDaily 07:30, MagXRadarDaily 08:00,
MagLeaveProtocolDaily 08:00 (note: TIE_IT_ALL_20260930.md:11 still lists MagLeaveProtocolDaily
as unregistered - the task now exists, the receipt lags).

## 9. The 8280-leaf chain (measured, and it kept moving)

From memory/biography/verkle_chain.jsonl (this session's read): the row at **index 8279
carries n_leaves 8280, ts 2026-09-30T15:50:19Z** - the ask's 8,280-leaf chain. At the
measurement moment the chain reads **8,681 leaves, tip ts 2026-09-30T21:50:25Z**, 2,822 rows
amended. Corroboration in the day's commits: "live 8645-leaf chain verifies" (c98f23c44,
07:58 EDT) and "8276/8276 rehash MATCH, 372 dangling" (a3e0e68bb, 08:36 EDT). Window-relevant
chain facts from the receipts: AH19 amend-perf landed 471x-1800x byte reduction at scale
(c1fb757da), and the chain is tamper-evident-to-writer-only until the tip is published
externally (THE LENSING verdict, commit 23c7092de).

## 10. The 36 luncheon signal rows

`wc -l watch/inbox/luncheon_watchlist_20260929_signals.jsonl` = **36 rows** for 35 unique
targets; the duplicate (lunch-sean-cairncross, written by two sibling lanes) was caught by the
ball4 review and is the known debt, not a hidden one
(watch/inbox/gala_20260925/ball4-luncheon-follow_RECEIPT.md, review verdict).

## The frame: 3 structural facts that make the next 48 hours different

1. **The estate now re-earns itself on a schedule.** Before the window, tapestry, mine,
   census and FTS were hand-run or dead; after it, four cadences plus six more daily tasks
   fire on the clock (section 8), and the mine that died twice went daily behind the
   09:15 bake. Work arrives, gets priced, and lands by cadence instead of by rescue - the
   fossil disease's cure is wired, not wished.
2. **Failure moved from silent to loud, and the record polices itself.** Every organ repair
   moved a law from prose into exit code (lattice chapter, insight 1); the gate caught
   three probes of its own kind and blocked a live-key commit (88ed0d729); review seats
   struck a byte-impossible check claim (ball-20260929 REVISE) and a duplicate register row
   (ball4). The next 48 hours' defects get caught in-window instead of fossilizing into
   the next 19.
3. **The binding constraints are now external, not internal.** The suite is a certified
   restore floor and the tree is the only copy of most of the lattice's work (uncommitted,
   per lattice strand 1); the agent quota wall runs to 10-05 (9ed2c153f HOLD rule); the owed
   items are a stranger (identity-bound SSH route, THE LENSING), the chain tip published
   off-machine, an offsite restore drill, and one named commit pass. The next 48 hours are
   gated on outsiders and restores, where the fleet's own gates do not reach.

## Honest residue: still red, still owed, still operator-gated

- **Unverified:** the 191.8M mine token total (section 4); the 42:05 19F/2529P run has no
  receipt (its number is a lane's citation of an unreceipted run).
- **Still red (AA4 doctor, watch/inbox/last_mile_20260930/AA4_DOCTOR.md):** refold_gate DEAD
  (rc=2 silent on its known-bad), 9 shared-surface hash mismatches, 37 unindexed inbox files,
  the doctor's phantom-pid probe.
- **Still owed:** heads-abliteratus CHECK 7 REVISE correction not recorded as applied
  (ball-20260929_RECEIPT.md section 5); ball4's duplicate Cairncross row dedupe and the
  defense-enterprise instrument re-scope (ball4 review verdict); N5 oral-law re-run
  (truncated, NIGHT_BURN_RECEIPT.md); the tapestry organ has no dedicated 48h repair receipt
  (lattice chapter); seed payload at 97,364/100,000 headroom (pointer-ize decision owed
  before the next rebuild, lattice chapter); the tapestry-adjacent next.md chapter's floor
  items.
- **Still operator-gated:** the named commit pass of the shared tree (the whole 48h lattice
  is working-tree-only plus receipts); history purge + key rotation already executed by
  operator GO (662dc739e); offsite backup media (OFFSITE_BACKUP_PLAN_20260930.md); the
  AI-czar appointment as the external swing variable on the sovereignty channel
  (ball4 capital-policy decision); quota reset 10-05.
- **This lane's own limits:** the full suite was not re-run here (receipts cited instead, at
  the ask's direction); workflow run records were unreachable (introspection unavailable);
  no self-token meter exists for this seat.
