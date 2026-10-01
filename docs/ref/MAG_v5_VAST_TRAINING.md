# Mag v5 — Vast.ai training pipeline

**Commitment:** `mag-v5-vast-training-001`  
**As-of:** 2026-08-05  
**Status:** **Piped for v5** — inference path exists today; **train orchestration** is v5  
**Parents:** `MAG_v5_PIPE.md` · `MAG_TRAINING_DATA_SPEC.md` · `scripts/vast/TEMPLATE.md` · `SEATS.md`

**Job:** Use Vast.ai as **rented GPU capacity** to fine-tune future Mag agents from **exported, redacted curriculum** — weights return to operator disk; instance destroyed after job.

---

## 0. One line

**Curriculum stays home; GPU rents by the hour; trained weights promote through human gate — Vast is capacity, not identity.**

---

## 1. What exists today (v3)

| Piece | Location | Role |
|-------|----------|------|
| Vast provider | `configs/providers.yaml` → `vast` | OpenAI-compat inference via `VAST_OPENAI_*` |
| Router preference | `mag/router.py`, `governor_autorun.py` | Prefer vast when configured + budget_ok |
| Ollama on Vast | `scripts/vast/TEMPLATE.md`, `onstart_mag_ollama.sh` | SSH tunnel → `OLLAMA_HOST` for blast/dispatch |
| Blast plant | `mag/blast.py` | Continuous improve dig on rented GPU |
| Lanes overlay | `configs/lanes_vast_rtx8000.yaml` | 48GB stack map |
| Seat law | `memory/improve/SEATS.md` | **L1-cap** — Vast later, not identity |

**Today:** rent GPU → run **inference** (Ollama or OpenAI-compat endpoint).  
**v5 add:** rent GPU → run **training job** → download adapter/weights → `promote`.

---

## 2. Architecture (do not invert)

```text
[Home PC — Mag DNA]
  memory/training/export/     ← redacted JSONL curriculum (T2 max)
  memory/biography/           ← NEVER only on Vast disk
  promote gate                ← human signs weight import

        │  upload bundle (scp / vast CLI)
        ▼
[Vast instance — interruptible]
  onstart: CUDA + train stack (Unsloth / Axolotl / HF TRL — TBD at v5)
  job: LoRA/SFT on export bundle
  artifact: adapter + eval log

        │  download weights
        ▼
[Home PC]
  memory/training/runs/{run_id}/
  ollama create / import via promote
  destroy vast instance
```

**Law (from `scripts/vast/TEMPLATE.md`):**

- Verkle tip, agent_state, private T0/T1 **never** Vast-only  
- Interruptible disk — assume loss  
- Cost every job in `cost_ledger`

---

## 3. v5 phases

### Phase V0 — Curriculum (v4 steward, no GPU)

- [ ] `steward-train-prep` weekly → `memory/training/export/`  
- [ ] `training-export --tier-max T2 --eval` green  
- [ ] Frozen orchestration eval set (10–30 prompts) per `MAG_TRAINING_DATA_SPEC`  
- [ ] Pattern tags: `route_decision`, `task_lifecycle`, `factory_cycle`, `skill_gate`

### Phase V1 — Train template (v5)

- [ ] `scripts/vast/onstart_mag_train.sh` — CUDA + train deps (not just Ollama)  
- [ ] Vast template **`mag-train-lora`** (private) — 48GB+ VRAM target  
- [ ] `mag/vast_train.py` — job spec: `{export_path, base_model, hyperparams, max_hours}`  
- [ ] CLI: `main.py vast-train --dry` → validates bundle + estimates cost

### Phase V2 — Orchestrated run (v5)

- [ ] `vastai search` + `create` wrapper (or manual offer id + Mag tracks id)  
- [ ] Upload export bundle + job yaml  
- [ ] Poll job status → log to `memory/training/runs/`  
- [ ] Download adapter + eval metrics  
- [ ] Auto `destroy` on success/fail (configurable)  
- [ ] Training events: `pattern: vast_train_job`

### Phase V3 — Import seat (v5+)

- [ ] Eval gate: new weights must beat baseline on frozen eval set  
- [ ] `promote --apply c-…` → update `configs/lanes.yaml` local model id  
- [ ] Optional: **conductor ranker** seat (v3-009) uses imported weights at L-meta  
- [ ] Office shows: last train run, cost, eval delta

---

## 4. Mag modules (v5 implement)

| Module | File | Behavior |
|--------|------|----------|
| Job spec | `mag/vast_train.py` | Validate export, estimate VRAM/hours |
| CLI | `main.py vast-train` | `--dry`, `--run`, `--status`, `--fetch` |
| Config | `configs/vast_train.yaml` | Base models, max spend, template hash |
| Template | `scripts/vast/onstart_mag_train.sh` | Boot train env on instance |
| Events | `mag/training_events.py` | `vast_train_start`, `vast_train_complete` |
| Seat card | `configs/seat_playbook.yaml` | `vast_train` vs `vast_infer` |

---

## 5. Routing doctrine

| Task | Seat |
|------|------|
| Scut, ask, route | T0 local Ollama |
| Heavy infer (no train) | Vast Ollama tunnel or `VAST_OPENAI_*` |
| **Train run** | **Dedicated v5 job** — not interleaved with blast |
| Eval before promote | Local or Vast infer seat — frozen prompts |
| Promote weights | **L3 human** |

**Do not:** auto-train on live T0/T1 chat logs. Export pipeline only.

---

## 6. Cost & safety

| Control | Mechanism |
|---------|-----------|
| Max spend | `configs/vast_train.yaml` → `max_usd_per_job` |
| Max hours | Instance auto-destroy + watchdog |
| Tier cap | Export `--tier-max T2` |
| Promote | Human only |
| Ledger | `cost_ledger` row per rent hour + GPU type |

---

## 7. v3/v4 prerequisites

| Prereq | Why |
|--------|-----|
| Training events hooked (C1) | Labels for curriculum |
| `steward-train-prep` (v4) | Weekly export without manual copy |
| Factory pilot + eval set | pass/fix/reject labels in export |
| Blast stable on infer-only Vast | Prove rent/destroy ritual before train |

---

## 8. Links

- `scripts/vast/TEMPLATE.md` — Ollama infer template (v3)  
- `scripts/vast/MODEL_STACK.md` — 48GB model policy  
- `docs/ref/MAG_TRAINING_DATA_SPEC.md` — export schema  
- `memory/improve/evals/features/lattice-vast-harness-20260729.md` — prior dig (story.py art)

---

*v5-VAST: train future agents on rented GPU using Mag's own filed curriculum.*
