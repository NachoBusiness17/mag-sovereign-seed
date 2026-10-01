# Mag — Next coding run (code plan + subsystems)

**Commitment:** `mag-next-coding-run-001`  
**As-of:** 2026-08-05  
**Status:** Operator run sheet — update after each merge or pilot  
**Load with:** `HANDOFF_MAG_AGENT_TODOS.md` · `MAG_LLM_FEED_PACK.md`

**One job:** Tell the next coding session **what to build, in what order, which subsystem, and how to verify** — without re-litigating v2/v3/v4 in chat.

---

## 0. Answer in one line

**Yes — but it was split.** This file is the consolidated run sheet. Older docs stay authoritative for depth:

| Doc | Role |
|-----|------|
| **This file** | Next coding run order + subsystem map |
| `HANDOFF_MAG_AGENT_TODOS.md` | Merge order, rituals, agentic steals |
| `docs/ref/MAG_v3_BACKLOG.md` | Feature ideas + scores (not run order) |
| `docs/ref/MAG_v5_GSTD_FOREST.md` | GSTD forest — **v5 pipe** (catalog now, test/implement later) |
| `docs/ref/MAG_v5_PIPE.md` | v5 umbrella — GSTD + Vast train + XRPL |
| `docs/ref/MAG_v5_VAST_TRAINING.md` | Vast.ai agent training pipeline |
| `docs/ref/MAG_v5_XRPL.md` | XRPL via Mag tools (read T2, pay L3) |
| `docs/ref/MAG_DIRECTION_ARTIFACT_v2.md` | Direction artifact v2 — v3 gate + v4/v5 mold |
| `docs/ref/MAG_FACTORY_PILOT.md` | Factory epic ritual + prompts |
| `configs/modules.yaml` | Module registry + upgrade contracts |

---

## 1. Gate (do not skip)

**RUN A passed 2026-08-06.** The #8–#11 branch tips are ancestors of the current HEAD. Home-PC ritual: doctor green, routing smoke 9/9, `verkle-audit --dry` exit 0 with continuity warnings retained, and autorun dry exit 0.

```text
HISTORICAL:     PR #8 → #9 → #10 → #11 are contained in current HEAD
VERIFIED:       RUN A gate recorded in memory/improve/releases/gates.jsonl
NEXT:           Beta trust + tier gates; v3 factory freeze gate
```

**Post-merge ritual (home PC):**

```powershell
mag.cmd doctor
.\.venv\Scripts\python.exe scripts\routing_smoke.py
python main.py verkle-audit --dry
python main.py autorun --once --dry
python main.py v3-status
python main.py switchboard status
```

**Cloud / Linux agent:** use `.venv/bin/python` — never bare `python`.

---

## 2. Subsystems map (three layers)

```text
┌─────────────────────────────────────────────────────────────────┐
│  VIEWPORT — what seats see (min tokens)                          │
│  nervous_system · context_pack · resonance (L0e)                 │
├─────────────────────────────────────────────────────────────────┤
│  HARNESS — $0 routing + loops (v2 ship · v3 research)            │
│  router · dispatch · orchestrator · pigeonhole · governor        │
│  improve · FKB · verkle_audit · conductor · spider · switchboard │
├─────────────────────────────────────────────────────────────────┤
│  COLD / WARM — disk truth                                        │
│  residual_dna · run_trail · bonds · agent_state · training_events│
├─────────────────────────────────────────────────────────────────┤
│  OFFICE — :8765 REST + dashboard                                 │
│  dashboard/rest.py · lattice_dashboard                           │
└─────────────────────────────────────────────────────────────────┘
```

### Module registry (machine truth)

Source: `configs/modules.yaml` — full dependency graph.

| Layer | Module | Path | Provides |
|-------|--------|------|----------|
| cold | residual_dna | `mag/registry.py` | beads, knot, tip |
| warm | run_trail | `mag/run_trail.py` | run object, trail |
| warm | bonds | `mag/bonds.py` | next-session edges |
| viewport | nervous_system | `mag/nervous_system.py` | body glance L0a |
| viewport | context_pack | `mag/context_pack.py` | pack for remotes |
| harness | router | `mag/router.py` | `route.v2` |
| harness | orchestrator | `mag/orchestrator.py` | spawn, queue, reap |
| harness | pigeonhole | `mag/pigeonhole.py` | `!steer` mailbox |
| harness | governor_autorun | `mag/governor_autorun.py` | fill → route → execute |
| harness | improve | `mag/improve.py` | scout → promote gate |
| harness | failure_kb | `mag/failure_kb.py` | fail → remedy |
| harness | verkle_audit | `mag/verkle_audit.py` | history gaps |
| harness | **conductor** | `mag/conductor.py` | phase overlay (v3) |
| harness | **spider** | `mag/spider.py` | meta-watch (v3) |
| harness | **switchboard** | `mag/switchboard.py` | mesh + tier drops (v3) |
| harness | **resonance** | `mag/resonance.py` | corpus lens (v3) |
| harness | **grove** | `mag/grove.py` | poem nodes (v3) |
| harness | **training_events** | `mag/training_events.py` | orchestration labels |
| harness | skill_seat | `mag/skill_seat.py` | ponytail/caveman |
| office | REST | `dashboard/rest.py` | `/api/v1/*` |

### v3 loops (research → product)

```bash
python main.py v3-status          # manifest + trail health
python main.py switchboard status # live mesh
python main.py conductor "goal"   # phase + route + mesh target
python main.py spider --once --dry
python main.py training-events --stats
```

---

## 3. Coding runs (ordered)

Pick **one run per session**. FILE outcomes before chat dies.

---

### RUN A — v2 graduation (complete 2026-08-06)

**Seat:** JONES-V2 · **Branch:** merge on `main`  
**Blocks:** everything else

| Step | Task | Subsystem | Verify |
|------|------|-----------|--------|
| A1 | Review + merge PR #8 unified router | `router` | `routing_smoke.py` |
| A2 | Merge PR #9 FKB | `failure_kb` | `pytest tests/test_failure_kb.py` |
| A3 | Merge PR #10 autorun | `governor_autorun` | `pytest tests/test_autorun_v1.py` |
| A4 | Merge PR #11 v2 plan + verkle | `verkle_audit` | `verkle-audit --dry` |
| A5 | Pull PR #12 / #13 or cherry-pick v3 CLI | v3 modules | `v3-status` · `switchboard self-test` |
| A6 | Register scheduled tasks (improve daily, verkle weekly) | ops | `HANDOFF` §2 |

**Done when:** ritual green · autorun card honest · one `[mag]` queue item drains dry-run.

---

### RUN B — Factory pilot #1: `factory-audit-json` (first v3→product epic)

**Seat:** JONES-PLAN → L3 freeze → JONES-BUILD → JONES-AUDIT  
**Spec:** `docs/ref/BUILD-factory-audit-json-EXAMPLE.md`  
**Pilot doc:** `docs/ref/MAG_FACTORY_PILOT.md`

| Phase | Who | Code target | Subsystem |
|-------|-----|-------------|-----------|
| B1 Plan | Grok/caveman | `queue/handoff/BUILD-factory-audit-json.md` | doctrine only |
| B2 Freeze | Operator L3 | `Status: frozen` on spec | — |
| B3 Build | DeepSeek/ponytail | **new** `mag/build_audit.py` | harness |
| B3 Build | | `main.py build-audit` CLI | harness |
| B3 Build | | writes `memory/runs/build_audit/{slug}.json` | warm trail |
| B4 Audit | Cursor | ponytail-audit + routing_smoke + pytest | validator |
| B5 Merge | Operator L3 | merge `cursor/factory-audit-json-e2ce` | — |

**Acceptance (from BUILD example):**

- CLI `main.py build-audit --slug X` emits JSON schema `build_audit.v1`
- Integrates with factory pipeline doc paths
- Tests in `tests/test_build_audit.py`
- No feature creep beyond spec

**Wire after B3:**

| Hook | File | Change |
|------|------|--------|
| Conductor audit phase | `mag/conductor.py` | suggest `build-audit` on audit phase |
| Training | `mag/training_events.py` | pattern `factory_cycle` on audit FILE |
| Jones AUDIT role | `configs/agent_fleet/jones.yaml` | add `build-audit` command |

---

### RUN C — v3 wiring gaps (after RUN A; can parallel factory audit module only)

**Seat:** JONES-V3 / cloud agent · **Branch:** `cursor/v3-swarm-vision-e2ce` or new `cursor/{slug}-e2ce`

Priority order — **one subsystem per PR slice:**

| # | Task | Subsystem | Files | Verify |
|---|------|-----------|-------|--------|
| C1 | Training hooks on autorun + orchestrator spawn/terminal | `training_events` | `governor_autorun.py`, `orchestrator.py` | `training-events --stats` shows `task_lifecycle` |
| C2 | `skill_gate` auto-emit on audit exit codes | `skill_seat` | `mag/skill_seat.py`, audit CLIs | `tests/test_skill_seat.py` |
| C3 | REST `GET /api/v1/grove` | office | `dashboard/rest.py`, `mag/grove.py` | curl localhost:8765 |
| C4 | Factory freeze gate: reject `[build]` without frozen handoff | `conductor` + `switchboard` | `conductor.py`, new check in `route` or conductor | test: build goal without BUILD file → defer |
| C5 | Spider → switchboard `steer_drop` for stall (not raw post_steer) | `spider`, `switchboard` | `spider.py` | spider tick inject uses tier |
| C6 | `switchboard_status.cmd` calls `switchboard status` | ops | `switchboard_status.cmd` | Windows smoke |
| C7 | **v3 DeepSeek run** scripts + BUILD handoff | ops | `scripts/v3_deepseek_run.cmd`, `docs/ref/V3_DEEPSEEK_RUN.md` | `training-events` shows `task_lifecycle` |

**C1–C7 shipped on branch `cursor/v3-deepseek-run-e2ce`** (2026-08-05): orchestrator lifecycle, grove REST, spider→switchboard, switchboard_status, DeepSeek run scripts.

**Wave 1 shipped on branch `cursor/v3-deepseek-run-e2ce`:** `pack mode` on context_pack + `--mode janitor` default path for ask/steward; `steward-scope` job + CLI.

**Explicitly defer (not this run):**

- Mobile `voice/turn` API (v3-013)
- Layman layout JSON (v3-011)
- Learned conductor weights (v3-009 train)
- Parallel git worktrees automation
- Riddle packs (v3-010)

---

### RUN D — Factory pilot #2: `factory-freeze-gate` (after RUN B passes audit)

**Status: shipped 2026-08-06.** Conductor, orchestrator spawn, and queue entry now reject build goals unless they name a frozen `queue/handoff/BUILD-*.md` contract. Focused freeze/conductor suite: 13 passed.

| Task | Subsystem | Behavior |
|------|-----------|----------|
| D1 | `conductor` | `phase=build` + no frozen BUILD → `suggested_seat=defer` |
| D2 | `orchestrator.spawn_task` | optional `--require-build slug` flag |
| D3 | `autorun` fill | skip build-tagged goals without handoff file |
| D4 | Tests | `tests/test_factory_freeze_gate.py` |

Spec: write `docs/ref/BUILD-factory-freeze-gate.md` during RUN B audit if #1 passes.

---

## 4. Test ritual (every run)

```bash
# Minimal (cloud)
.venv/bin/python -m pytest tests/test_switchboard.py tests/test_v3_modules.py \
  tests/test_training_events.py tests/test_skill_seat.py -q

# After v2 merge (full trust)
.venv/bin/python -m pytest tests/test_router.py tests/test_failure_kb.py \
  tests/test_autorun_v1.py tests/test_verkle_audit.py -q
.venv/bin/python scripts/routing_smoke.py
.venv/bin/python main.py ponytail-audit
.venv/bin/python main.py switchboard self-test
```

---

## 5. Seat assignment (token law)

| Run | Primary seat | Why |
|-----|--------------|-----|
| A | Human + Cursor local | merge + ritual |
| B plan | Grok / caveman | spec only |
| B build | DeepSeek / ponytail | implementation |
| B audit | Cursor / ponytail | gates only |
| C | Cloud agent / DeepSeek | scoped PR slices |

**$0 API layers (use freely):** conductor, spider, switchboard, router, loops_registry.

---

## 6. FILE checklist (end of every run)

- [ ] Branch pushed · PR updated (draft OK)
- [ ] Tests named in run table — green
- [ ] Trail / training event if orchestration behavior changed
- [ ] `HANDOFF_MAG_AGENT_TODOS.md` or this file — status line if run completed
- [ ] Bond filed if work continues tomorrow

---

## 7. Quick decision tree

```text
Haven't merged #8–#11?     → RUN A only
Merged v2, want product?   → RUN B (factory audit JSON)
Merged v2, want v3 wire?  → RUN C (pick one C-row)
Pilot #1 audit passed?     → RUN D (freeze gate)
```

---

## 8. Links

- Handoff: `HANDOFF_MAG_AGENT_TODOS.md`
- LLM feed: `docs/ref/MAG_LLM_FEED_PACK.md`
- Factory: `docs/ref/MAG_BUILD_PIPELINE.md` · `MAG_FACTORY_PILOT.md`
- Subsystems: `configs/modules.yaml`
- v3 backlog: `docs/ref/MAG_v3_BACKLOG.md`
- PR #13: https://github.com/NachoBusiness17/Mag/pull/13

---

*Update RUN status after each session. One run. One branch. FILE before close.*
