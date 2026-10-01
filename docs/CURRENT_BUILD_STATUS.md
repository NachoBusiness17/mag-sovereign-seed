# MAG current build status

**As of:** 2026-08-06

## Shipped

- **v1:** Grok/X origin.
- **v2:** sovereign repository substrate, routing, autorun, tier refusal, Office.
- **v3:** orchestrator, behavioral router, factory audit, frozen BUILD enforcement, bounded DeepSeek execution, dashboard/history consolidation, and file-backed agent handoffs.
- **v4:** typed conductor evaluation, unattended local stewardship, estimate-to-actual seat economics, and safe green-behavior export for distillation.

The v3 release has six defined gates. All are green in `memory/improve/releases/gates.jsonl`; the v2 `run_a` prerequisite is also green.

| Gate | Evidence |
| --- | --- |
| run_a | v2 gate record |
| factory_pilot | `memory/factory/build_audit-factory-audit-json.json` |
| freeze_gate | `mag/factory_gate.py`; conductor, queue, and spawn enforcement |
| chat_preflight | behavioral router, pending cleanup, live-turn status, bounded timeouts |
| deepseek_run | `memory/runs/v3_deepseek_proof.md`; task `ta79c0045f0` |
| witness_filed | `docs/ref/releases/WITNESS_SPINE.md` |

## Reliability defects closed during graduation

1. Vague `[build]` prompts could reach the factory without a frozen file contract. They are now deferred before queue or spawn.
2. A frozen spec's declared tier was not propagated to the spawned agent. T2 contracts now arrive as T2 while T0/T1 remain remote-refused.
3. A provider refusal could print `Agent error` but exit zero. One-shot agents now return a failing exit code and lifecycle state.
4. The DeepSeek release script could drain an unrelated old queue item. It now runs its named frozen proof directly.
5. Verkle knots were treated mainly as visualization nodes. They are now bounded, verifiable, file-backed handoff artifacts with copy and background-route actions.

## What remains

The roadmap probe reports **zero red items**. Four research curricula remain yellow; they are inputs to v4 rather than hidden v3 blockers:

- `v3-007` Spider: graduate evaluation.
- `v3-009` Conductor: graduate evaluation.
- `v3-008` Resonance: wire steering, train, and graduate.
- `ponytail-caveman`: graduate the planner/builder/auditor role split.

The mold release **v4 is shipped**. Its four gates are green:

1. `conductor_eval`
2. `steward_daily`
3. `cost_ledger`
4. `training_export`

Evidence: conductor 10/10; one local steward leaf; a real DeepSeek proof measured at about $0.0167; four green joined T2 examples exported with a SHA-256 manifest.

The next active release is **v5, the pipe**: dry-run the local-model training package first, then prove optional compute and external tool seats without weakening Mag's tier or promotion boundaries.
# HISTORICAL SNAPSHOT — last updated 2026-08-06
#
# This file is not present-tense status. Use `watch/ORPHAN_AUDIT.json`,
# `mag.openclaw_patches status`, and receipt logs for current state.
