# Ontology Compiler — Phase 1 Spec: Human-in-the-Loop PoC

## Goal
A dashboard that presents session logs + candidate rule suggestions, human approves/modifies, diff committed to prefix store, cache invalidated for modified sections only.

## Inputs (from existing repo substrate)
- `memory/percolator/explore.jsonl` — experience store (raw session outputs)
- `memory/thinking/app_reasoning.jsonl` — evaluator scores + failure traces
- `docs/ref/CACHE_CRAFT_LAWS_20260906.md` — prefix breakpoint mechanics = edit surface
- `memory/runs/harness/events.jsonl` — event log for high-signal extraction

## The Loop (3 steps, human gates the middle)

### Step 1: Extract (automated, GLM-5.3-Flash, $0)
Parse last N session cycles. Identify:
- Failure points: evaluator scores below threshold
- Surprising successes: all agents agreed, user corrected
- Cluster by category: missing data, ambiguous language, conflicting rules

### Step 2: Propose (automated, human reviews)
For each cluster, generate 3-5 candidate diffs against current prefix/roles/rubrics:
- Rule amendments (e.g., "flag logistics data older than 7 days")
- New example additions to prefix
- Agent role refinements
- Evaluation threshold adjustments

Dashboard shows: cluster → candidate → expected improvement → confidence.

### Step 3: Apply (human clicks approve)
- Commit diff to prefix store (versioned file)
- Invalidate cache segments for modified prefix sections only
- Log change to event stream
- Monitor next N cycles; rollback if performance degrades

## Rollback Rule
- Keep last 3 ontology versions on disk
- If cache-hit rate drops >10% or evaluator score drops below floor within N cycles → auto-rollback to previous version
- N = 20 cycles (tunable)

## Host
GLM-5.3-Flash (free lane, cache-mined). Same architecture as doc specifies: small fast model with cached prefix containing meta-rules for how to modify the system.

## Falsifiable Metrics
1. Time-to-ontology-update: human vs compiler (target: compiler < 5 min)
2. Cache-hit rate change after Compiler-driven prefix changes
3. Evaluator score trend on held-out queries (20-50 handcrafted sourcing queries)
4. Rollback rate (should decrease over cycles if Compiler learns)

## What Phase 1 Proves
- Whether humans can delegate ontology updates to a fast model + dashboard
- Whether the feedback loop actually improves performance (not just changes it)
- Whether the auditor problem is real (if evaluator is wrong, Compiler optimizes wrong)

## Next Step (Phase 2, not built yet)
Rule-based Compiler: detects simple patterns, appends predefined rules without human approval. Only if Phase 1 metrics prove the loop works.

## Files to create
1. `mag/ontology_compiler/` — the compiler organ (extract + propose)
2. `dashboard/static/ontology_dashboard.html` — the human review surface
3. `memory/ontology/versions/` — versioned prefix store (3-version retention)
4. `docs/ref/ONTOLOGY_COMPILER_PHASE1.md` — this spec, signed

## Blockers
- Evaluator scores must be logged consistently (currently scattered across thinking/app_reasoning.jsonl)
- Dashboard framework (room_lightmap.html? or new page)
- GLM-5.3-Flash quota check (TEMP ruling: default to deepseek; GLM off-limits for plans)
