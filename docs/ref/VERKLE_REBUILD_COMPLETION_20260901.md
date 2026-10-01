# Verkle / Mag territory rebuild — completion receipt

Date: 2026-09-01/02 UTC  
Mode: read-first, bounded gophers, non-destructive recovery

## Outcome

The repository now has a collision-safe artifact index, a repaired forward
write path for agent state, an executable audit for that state chain, and a
refreshed trajectory-bounds receipt. The historical chains were not silently
rewritten. The system is more honest about what is live, what is merely wired,
and what still requires a reviewed recovery.

## Changes made

- `mag/verkle_knot.py` now declares its runtime schema, closing the failure
  path that caused Q folds to be recorded as `fold_error: SCHEMA is not defined`.
- `mag/agent_state.py` now serializes commits with an atomic lock. Its content
  hash verifier excludes the derived `content_commit` field, so persisted state
  can verify against its own commitment.
- `scripts/audit_agent_state.py` emits a read-only chain audit at
  `memory/runs/verkle_recovery/agent_state_audit_20260901.json`.
- `mag/holographic_q.py` now falls back to the real biography chain, checks the
  full chain when matching Q roots, and does not treat a bare root or arbitrary
  string as a verified proof.
- `mag/ghost_cold_boot.py` reports `folded: false` with an error when its
  training-event fold fails instead of claiming success.
- `mag/session_rib.py` labels ledger rows `planned` versus `dispatched` and
  records the `dry` flag.
- `mag/frontier_council.py` counts the current ISO week rather than all-time
  allowance rows, preventing old spend from making a reset appear exhausted.
- `mag/embassy_deliver.py`, `mag/cast_guard.py`, and
  `mag/honest_cache_meter.py` were repaired so their modules parse and their
  dry-run / capture paths are callable.
- Collision-free Verkle session pointers were migrated into v2 derived files;
  legacy pointers remain untouched.
- The shared artifact index is at
  `memory/runs/verkle_recovery/artifact_index_20260901.jsonl` with metadata in
  the adjacent `.meta.json` file.

## Current measured state

### Follow-up pass — 2026-09-02

The operator selected the existing layered topology: person tip → day/session
DNA → run → trail event, with agent state remaining a recall edge. No new chain
version or in-place repair was created.

- `mag/trajectory_rib.py` is now a deterministic v0 compiler. It accepts only
  line/byte/body-hash verified `trajectory_span.v1` rows and writes a derived
  RIB projection. The current 28-row tape compiled **0** rows and rejected 28
  legacy-unbounded rows, as required.
- `mag/live_ops_readiness.py` is now a zero-spend, observer-only preflight. It
  writes `memory/runs/live_ops/readiness.json` and is surfaced in the live
  report. The required receipts exist; the recorded supervisor has no live
  child while ports 8765 and 9000 appear open, so a second controller must not
  be started until that external owner is identified.
- The prior biography pointer/consolidation machinery was reused in dry mode:
  17 dangling rows were found, 0 were recoverable from current pointers, and
  no chain bytes changed.

| Surface | Evidence-backed state |
| --- | --- |
| Agent-state chain | 15,303 parsed rows; 2 malformed physical rows; 889 broken parent links; 3 duplicate content commits; latest persisted root matches the one-pass computed root; 22 unreferenced JSON versions remain preserved |
| Biography Verkle chain | Gopher snapshot was root-consistent, but writers were active; 13 dangling rows and legacy pointer collision groups remain review items |
| Q state | Disk recovery works, but historical Q records include rootless/unproven entries; the raw Q log remains evidence, not authority, until each root is matched to a verified proof |
| OpenClaw trajectory | 28 physical lines; 0 historical lines carry valid bounds. The forward hook already writes `trajectory_span.v1`; the sidecar was refreshed and labels legacy rows unbounded |
| Artifact map | 47,436 load-bearing indexed entries in the last completed build; source lineages were not moved or merged |
| Verkle → RIB export | Refreshed after the audit; `queue/handoff/VERKLE_RIB.json` now contains 6,497 knots |
| Frontier allowance | Current ISO-week window: ChatGPT 22 remaining, Grok web 2 remaining, Grok/X 20 remaining; historical rows no longer exhaust the live window |
| Organ map | 28 declared, 27 instrumented, 28 wired, 26 stateful, 28 map-verified, 5 recently live, 0 classified ghost by the current map. “Verified” here means the map’s evidence rules, not universal end-to-end proof |

## Verification

- Focused integrity and recovery suite: **29 passed**.
- Full-suite checkpoint: **384 passed, 7 skipped, 3 deterministic failures**;
  all three were fixed and the affected suite reran **29 passed**. The full
  suite was then stopped when a later integration segment made no progress;
  it was not falsely reported as green.
- Full compile pass: **clean** after the repairs.

## Still open, deliberately not auto-repaired

1. Agent-state parent-link damage needs a reviewed layered recovery view using
   existing viewport/history/evidence strata. Reparenting existing rows would
   change commitments and is not safe to infer from timestamps alone.
2. Biography-chain dangling rows and legacy pointer collisions need a quiescent
   byte snapshot before any repair decision. The v2 pointer migration is the
   safe forward fix.
3. Historical trajectory lines cannot be bounded without rewriting evidence;
   only future hook records are bounded. The trajectory-to-RIB compiler is
   staged and deterministic, but its metric gate and acceptance commands are
   still open.
4. Q autonomous continuation remains policy-gated. No loop should emit new
   knots merely because a stale session has a positive TTL.
5. The Verkle implementation is currently a SHA-256 duplicate-last binary
   Merkle construction. It is not a production KZG polynomial commitment.
   The KZG boundary and migration plan are documented separately in
   `docs/ref/VERKLE_KZG_BOUNDARY_20260901.md`.

## Cold-boot instruction

Load the artifact index, the agent-state audit, the organ-map snapshot, and the
KZG boundary note first. Treat chain rows, Q logs, and RIB JSON as evidence with
their stated status. Do not promote an organ from `WIRED` to `LIVE` without a
fresh invocation receipt and do not repair a commitment chain in place.

Source changes in this pass: no source deletion, no chain rewrite, no backup
restore, no pointer deletion.
