# Mag training data — pattern capture & conductor labels

**Commitment:** `mag-training-data-001`  
**As-of:** 2026-08-05  
**Status:** Spec — build after v2 gate (#8–#11)  
**Parents:** `MAG_v3_RESEARCH_PLAN.md` · `MAG_v3_SWARM_VISION.md` · `DNA.md` · `AGENTIC_LANDSCAPE_2026.md`

**Job:** Answer what to build, why, which systems fit, and how to FILE data so future training runs learn **orchestration patterns** — not diary mimicry.

---

## 1. The question (plain)

You want the swarm to get smarter about:

- when to spend Grok vs DeepSeek vs Ollama  
- when to steer vs let run  
- when soil echoes matter  
- when factory plan/build/audit cycles succeed  

That requires **labeled episodes** on disk — not chat exports.

---

## 2. What needs to be built (priority order)

| # | Build | Why | Depends |
|---|-------|-----|---------|
| **1** | **Unified training events** (`mag_training_event.v1`) | One append-only log all loops write to — joinable, exportable | v2 router merged |
| **2** | **Hook emitters** in conductor, autorun, orchestrator, FKB, spider, factory audit | Without hooks, trails exist but don't join | #1 schema |
| **3** | **Pattern taxonomy** (`configs/training_patterns.yaml`) | Stable labels for emerging failures (empty_reply, stall, plan_inflation…) | FKB + chord vocabulary |
| **4** | **`training-export` CLI** | T2-redacted JSONL → republic train dir | #1–#3 |
| **5** | **Orchestration eval set** (10–30 frozen prompts + expected seat/phase) | Eval before every train run — industry steal A6 | #4 |
| **6** | **Factory audit JSON** (pilot #1) | pass/fix/reject labels for plan→build→audit | `MAG_FACTORY_PILOT` |
| **7** | **Republic train handoff** | LoRA/SFT off Mag disk; weights import via `promote` | republic repo |
| **8** | **Conductor inference seat** | Local model wraps `route.v2` | #5 eval green |
| **9** | **Spider ranker** (optional) | Only if rule spider + labels plateau | #1 volume |

**Do not build yet:** vector DB, in-lattice auto-train, mirror-as-conductor, chat log scrapers.

---

## 3. Why this order

```text
Trails today (good)     →  scattered JSONL, hard to join
Unified events (need)   →  one episode graph with join keys
Export + eval (need)    →  train only what improves eval
Republic train (need)   →  lattice stays law; weights fork
Promote import (law)    →  human gate on irreversible
```

**Alpha honesty:** You already FILE a lot (`decisions_log`, `governor_autorun_trail`, `orchestrator_trail`, `failure_kb`, `conductor_trail`). What's missing is **correlation** — linking route decision → execution outcome → remedy → human verdict.

---

## 4. Systems that fit (elegant stack)

| Layer | System | Role |
|-------|--------|------|
| **Capture** | Mag disk — append-only JSONL | Event source of truth (DNA law) |
| **Join** | Python `training_export.py` | Correlate by `run_id`, `task_id`, `build_slug` |
| **Taxonomy** | YAML + FKB signatures | Closed vocabulary for pattern_tags |
| **Train** | **mycelial-republic** (off daily path) | LoRA/SFT on exported JSONL |
| **Infer** | **Ollama** local | Conductor ranker at L-meta |
| **Specialists** | Grok / DeepSeek / APIs | Stay stateless — labels from outcomes |
| **Eval** | pytest-style harness + human spot | Gate before promote |
| **UI** | Grove + Office | Human-readable face of patterns |

**Anti-pattern:** train inside Mag lattice, or use a cloud vector DB as second DNA store.

**Industry steal:** Anthropic planner→generator→evaluator = Mag plan→build→audit factory + conductor labels.

---

## 5. Unified event schema (future-proof core)

**Path:** `memory/training/events.jsonl`  
**Schema:** `mag_training_event.v1`

```json
{
  "schema": "mag_training_event.v1",
  "event_id": "evt-…",
  "ts": "2026-08-05T…",
  "pattern": "route_decision",
  "join": {
    "run_id": "run-…",
    "task_id": "t-…",
    "queue_id": "q-…",
    "build_slug": "factory-audit-json",
    "commitment": "build-factory-audit-json-001",
    "session_id": "sess-…"
  },
  "input": {
    "goal": "[build] implement frozen spec…",
    "phase": "build",
    "signals": {"grok_budget_ok": true, "drainer": true},
    "depth": "heavy_code"
  },
  "action": {
    "seat": "agent",
    "provider": "deepseek",
    "route_schema": "route.v2",
    "conductor_overlay": "factory floor — frozen spec required"
  },
  "outcome": {
    "success": true,
    "label_source": "heuristic|human|eval|audit_json",
    "verdict": "pass",
    "fkb_sig": null,
    "duration_s": 840
  },
  "pattern_tags": ["factory_build", "pytest_green"],
  "tier_max": "T2",
  "exportable": true
}
```

### Pattern types (`pattern` field)

| pattern | Source module | Training use |
|---------|---------------|--------------|
| `route_decision` | conductor + router | Conductor: seat/phase choice |
| `autorun_cycle` | governor_autorun | Conductor: fill vs defer |
| `task_lifecycle` | orchestrator | Spider: spawn/stall/kill |
| `steer_outcome` | decisions_log + compass | Conductor + spider: did steer help |
| `fkb_failure` | failure_kb | Resonance + conductor: avoid seat |
| `spider_signal` | spider | Spider ranker labels |
| `factory_cycle` | build_audit JSON | Factory + conductor phase routing |
| `promote_gate` | improve promote | Human preference labels |
| `resonance_hit` | resonance findings | Resonance reranker (optional) |

### Join keys (always propagate)

```text
run_id      → run_trail (one goal trajectory)
task_id     → orchestrator child
queue_id    → orchestrator queue item
build_slug  → factory BUILD spec
commitment  → residual slug across docs
session_id  → bead / SessionEnd
```

**Rule:** any new loop must emit at least one join key or it cannot enter training export.

---

## 6. Labels that matter (not mirror)

Train **orchestration economics**, not voice:

| Label | Question | Source |
|-------|----------|--------|
| `delegation_success` | Did this seat finish without FKB block / stall kill? | autorun + orchestrator + FKB |
| `phase_correct` | Was plan/build/audit the right phase? | factory audit + human |
| `seat_efficient` | Could janitor have done it cheaper? | cost_band vs depth |
| `steer_effective` | Did steer unblock within N heartbeats? | spider + decisions_log |
| `remedy_applied` | Did known FKB remedy prevent repeat? | FKB count before/after |
| `promote_approved` | Human said yes to config change | improve promote |

**Reject as conductor labels:** "sounds like Nacho", chat tone, Athena persona, raw T0/T1 text.

---

## 7. Pattern taxonomy (emerging failures)

**Path:** `configs/training_patterns.yaml`

```yaml
patterns:
  empty_reply:
    fkb_signatures: ["deepseek:…", "ollama:…"]
    tags: [seat, guard]
    conductor_hint: prefer janitor retry before frontier loop

  plan_inflation:
    chord_loops: [plan_growth_without_soil]
    tags: [grok, cost]
    conductor_hint: freeze spec before build seat

  stall_heartbeat:
    spider_rule: task age > 180s
    tags: [orchestrator, steer]
    spider_hint: receipt nudge then kill

  tier_refuse:
  factory_audit_fail:
  resonance_echo_helped:  # future: operator thumb
```

Patterns grow via:

1. FKB auto-draft at ×3 recurrence  
2. chord_lens loop ids at SessionEnd  
3. factory audit reject reasons  
4. human promote of improve candidates  

Grove poems are **human face** of taxonomy nodes — not the training store.

---

## 8. Data flow (future-proof)

```text
┌─────────────┐   emit    ┌──────────────────────────┐
│ Loops       │ ────────► │ memory/training/events   │
│ router      │           │ .jsonl (unified)         │
│ autorun     │           └────────────┬─────────────┘
│ orchestrator│                        │
│ FKB/spider  │                        │ export (T2 redact)
│ factory     │                        ▼
└─────────────┘           ┌──────────────────────────┐
                          │ republic/data/orch_train │
                          │ .jsonl                   │
                          └────────────┬─────────────┘
                                       │
                          train LoRA / classifier
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │ weights → promote →      │
                          │ Ollama conductor seat    │
                          └────────────┬─────────────┘
                                       │
                          eval harness must beat gemma baseline
                                       ▼
                          conductor wraps route.v2 in lattice
```

**Export law:**

- Write full events locally (operator disk)  
- `training-export --tier-max T2` strips paths/content above tier  
- Never push T0/T1 to republic remote by default  
- `exportable: false` on sensitive rows at emit time  

---

## 9. What to hook (minimal diffs)

| Existing writer | Add |
|-----------------|-----|
| `mag/conductor.py` `_trail` | `emit_event(pattern=route_decision, …)` |
| `mag/governor_autorun.py` `_log_trail` | emit on execute success/fail |
| `mag/orchestrator.py` `_trail` | emit on spawn, stall-nudge, terminal |
| `mag/compass.record_decision` | emit steer_outcome |
| `mag/failure_kb.log_failure` | emit fkb_failure |
| `mag/spider.tick` | emit spider_signal |
| `mag/factory_audit` (pilot) | emit factory_cycle |
| `mag/improve` promote | emit promote_gate |

**Elegant rule:** one function `training_events.emit()` — modules stay thin.

---

## 10. Eval set (before any train)

**Path:** `memory/training/eval/orchestration_v1.jsonl`

~20 frozen cases:

```json
{
  "id": "orch-001",
  "goal": "[priority] plan only: router merge scope",
  "expected_phase": "plan",
  "expected_seat": "grok_tui",
  "forbidden_seat": "agent",
  "tier_max": "T2"
}
```

Run: `python main.py training-export --eval`  
Score: conductor overlay + route.v2 vs expected  
**Gate:** beat gemma:2b keyword baseline before republic train.

---

## 11. Republic boundary

| Stays on Mag | Goes to republic |
|--------------|------------------|
| Full events.jsonl | Redacted export JSONL |
| BUILD specs (T0/T1) | Never |
| Eval results | Copy for reproducibility |
| Conductor weights after promote | Import path in lanes.yaml |
| Pattern taxonomy | Export grammar only (forkable) |

---

## 12. Build vs buy vs steal

| Need | Fit |
|------|-----|
| Event store | **Build** — JSONL edges per DNA |
| Join/export | **Build** — `training_export.py` |
| Vector search for resonance | **Defer** — token overlap works at alpha scale; optional nomic embed later |
| Train stack | **Use republic** — already fork path |
| Orchestration SDK | **Steal contracts** — not OpenAI/Anthropic runtime |
| Evaluator browser | **Steal** v3-002 Playwright in cage — after workstation profile |

---

## 13. Success criteria (training runs become useful)

Training is working when:

1. **Eval accuracy** on orchestration_v1 rises after train (not just loss down)  
2. **FKB recurrence** drops for patterns in taxonomy (empty_reply, stall)  
3. **Grok spend/share** falls per factory epic (conductor routes plan once)  
4. **Factory audit pass rate** rises without skipping audit  
5. **Spider steer** rate falls (fewer stalls) with same throughput  
6. **Export row count** grows with real join keys — not chat dumps  

---

## 14. Immediate next steps (operator)

1. Merge v2 (#8–#11)  
2. Ship factory audit JSON pilot (label source)  
3. Implement `mag/training_events.py` + hooks (PR after v2)  
4. Run factory pilot #1–#3 — each cycle emits `factory_cycle` events  
5. Handful of labeled `steer_outcome` rows (fix decisions_log `outcome` field quality)  
6. First `training-export` → republic dry run  
7. Eval harness → only then LoRA conductor v0  

---

## 15. One paragraph

Build a **unified event log** with join keys, not a new database. Every loop you already have emits **orchestration episodes** (route, execute, fail, steer, audit, promote) tagged with a **pattern taxonomy** fed by FKB and factory cycles. Export T2-redacted JSONL to **republic** for train; import weights via **promote**. Eval on frozen orchestration prompts before every run. Conductor learns **did this delegation work**; spider learns **did this intervention help**; resonance learns **did this echo matter** — mirror and chat stay out of the label path. That's how emerging patterns compound into useful training signal without predicting the final product shape.

---

*End training data spec — implement `mag/training_events.py` after v2 gate.*
