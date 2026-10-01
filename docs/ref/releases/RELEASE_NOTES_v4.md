# Mag v4 — Release notes

**Commitment:** `mag-release-v4-001`
**As-of:** 2026-08-06
**Status:** **Shipped** — all four mold/process gates green
**Parent:** v3

## Purpose

v4 turns the shipped v3 substrate into a repeatable factory discipline. New behavior must have a typed pattern, executable evaluation, disk join keys, and an explicit auto/draft/human boundary before it becomes routine.

## Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| `conductor_eval` | Passed | `memory/improve/evals/conductor/2026-08-06.json` — 10/10, threshold 1.0 |
| `steward_daily` | Passed | `memory/steward/daily/2026-08-06.json` — one bounded local leaf, zero remote calls |
| `cost_ledger` | Passed | `memory/training/cost_ledger.jsonl` — estimate → actual → outcome joined by queue/task/session |
| `training_export` | Passed | `memory/training/export/orch_train_2026-08-06.manifest.json` — green joined T2-only corpus with digest |

## Conductor evaluation contract

The evaluation is provider-free and deterministic. It tests phase recognition, architect routing, frozen-build refusal, tier propagation, audit isolation, human defer, and ordinary cheap execution. Runtime and evaluation share the same pure `phase_policy`; the harness does not duplicate the policy it scores.

Run:

```powershell
python main.py conductor --eval --json
```

## Honesty

Shipping v4 does not claim a trained local foreman. It proves typed routing reflexes and produces a bounded, privacy-filtered training corpus. Training the local model remains v5 work.
