# Mag vision — v2 completion, desk loop factory, automated version build

**Commitment:** `mag-vision-automation-001`  
**As-of:** 2026-08-05  
**Status:** Primary vision document — strategy + mechanics for v2→v3 and the forever loop  
**Job:** Deep project map, honest v2 remainder, and how desk + orchestration automate the next version reliably  
**Audience:** Operator, every agent seat, future contributors

**Load after:** [`MAG_MYCELIAL_REPUBLIC_COMPASS.md`](MAG_MYCELIAL_REPUBLIC_COMPASS.md) · [`MYCELIAL_SCIENCE_MAP.md`](MYCELIAL_SCIENCE_MAP.md)  
**Run sheet:** [`MAG_NEXT_CODING_RUN.md`](MAG_NEXT_CODING_RUN.md) · [`MAG_FUTURE_WALKTHROUGH.md`](MAG_FUTURE_WALKTHROUGH.md)  
**Machine arc:** `configs/version_roadmap.yaml`

---

## 0. Vision in one paragraph

Mag is a **sovereign agent organism on your disk** — not a chat subscription. Separate seats (Grok, Cursor, Ollama, DeepSeek) coordinate through **REST and files**, problems percolate up, plans descend down, and behavior compounds in `memory/training/events.jsonl`. v1–v2 were built by hand. **v3 onward is built by the loop**: the same desk handoff machinery you use today becomes a **version factory** — ingest interest → plan → local board → remote judge → orchestrator build → audit → gate → distill. The orchestration stack (router, governor, orchestrator, improve loop, scheduler) already exists in pieces; the vision is to **bind them with `loop tick`** so the next version is not a heroic coding session but a **reliable, idempotent pass** with human L3 only on irreversible moves.

---

## 1. The entire project — four layers, three houses

### 1.1 Four layers (always this shape)

```text
┌──────────────────────────────────────────────────────────────────┐
│  OFFICE — operator membrane (:8765)                               │
│  Desk · Stack · Days · Chat · Pulse · timing · scheduler UI       │
├──────────────────────────────────────────────────────────────────┤
│  HARNESS — routing + loops ($0 local first, frontier scarce)      │
│  router · orchestrator · governor_autorun · improve · desk loop   │
│  coordination · local_scheduler · conductor · spider · switchboard│
├──────────────────────────────────────────────────────────────────┤
│  VIEWPORT — what seats see (min tokens)                           │
│  context_pack · nervous_system · briefs · attention · bonds       │
├──────────────────────────────────────────────────────────────────┤
│  COLD — disk truth (survives session death)                       │
│  residual_dna · verkle · run_trail · agent_state · training_events│
└──────────────────────────────────────────────────────────────────┘
```

**Law:** Chat is heat. Cold + harness artifacts are truth. Remote seats get **pack + goal**, never T0/T1 soil.

### 1.2 Three houses (zeitgeist)

| House | Location | Role in vision |
|-------|----------|----------------|
| **Beads** | `local_sovereign_agent` | Private office — custody, routing, desk, orchestration |
| **Forest** | `mycelial-republic` | Public law, fork, optional republic train |
| **GSTD forest** | `gstdcoin` | Optional DePIN seat — peer GPU, not memory export |

Mag vision executes in **Beads** first. Forest and GSTD are seats scored at v5+, never architecture dependencies.

### 1.3 The product we are building (OpenClaw-class + evolution)

| Capability | User sees | Mechanism |
|------------|-----------|-----------|
| Agents work together | Desk canvas + coordination feed | REST handoffs, shared_activity |
| Share resources | Local GPU + optional GSTD | scheduler + mycorrhiza probe |
| Share ideas / WIP | attention, bonds, briefs in every pack | context_pack |
| Follow interests | Resonance + conductor (v4) | filed episodes, not USER.md static |
| Evolve | desk-local model from dialogue | Unsloth + training_events |
| Sovereignty | T0/T1 refuse, fork without permission | tiers + CONSTITUTION |

---

## 2. v2 — what is actually shipped

Registry marks v2 **shipped** because the repo runs on your home PC — not because every lattice gate is green.

### 2.1 Shipped and verifiable today

| Subsystem | Evidence | Touch it |
|-----------|----------|----------|
| **Office / Desk** | Agent Desk :8765, handoff_loop.v1 | `python main.py lab` |
| **Local inference** | qwen-desk ~69 t/s, gemma:2b janitor | `configs/lanes.yaml` |
| **GPU scheduler** | run_exclusive, triage, steer | Stack strip · `scheduler status` |
| **Agent timing** | elapsed + tokens per seat | `#deskTimingBadges` |
| **Desk loop stages** | slow_wake, handoff_loop, meta_discuss | Desk buttons |
| **Memory soil** | beads, verkle, briefs, attention, bonds | `memory/` |
| **Coordination** | cross-seat activity feed | `GET /api/v1/coordination` |
| **Improve ingest** | cloud_handoff, improve cycle | `improve-loop cycle` |
| **Grok bridge** | grok_hook, escalate_grok, live_from_grok | `watch/grok_feed.jsonl` |
| **Training ledger** | events.jsonl append | `training-events --stats` |
| **Release CLI** | record/status/gates | `python main.py release status` |
| **Ops** | desk reload, doctor, routing probes | `desk_refresh.cmd` |

### 2.2 Shipped on branch but not v2-gated on home main

Code exists in workspace; **RUN A merge ritual** is the gate:

| PR | Branch | Module | Verify |
|----|--------|--------|--------|
| **#8** | `cursor/unified-router-e2ce` | `mag/router.py` route.v2 | `scripts/routing_smoke.py` |
| **#9** | `cursor/failure-kb-e2ce` | `mag/failure_kb.py` | `pytest tests/test_failure_kb.py` |
| **#10** | `cursor/mag-autorun-v1-e2ce` | `mag/governor_autorun.py` | `autorun --once --dry` |
| **#11** | `cursor/mag-v2-plan-e2ce` | `mag/verkle_audit.py` + plan docs | `verkle-audit --dry` |

v3 research modules (conductor, spider, switchboard) live on **`cursor/v3-deepseek-run-e2ce` (PR #15)** — product wiring, not v2 definition.

---

## 3. v2 remainder — everything before v3 starts

**Hard rule (direction artifact §5.4):** v3 product build starts when **RUN A is green** and **RUN B files first build_audit JSON** — not when PR count rises.

### 3.1 Gate checklist — v2

| Gate | ID | Status | Unblock action |
|------|-----|--------|----------------|
| Merge lattice PRs | `run_a` | **OPEN** | Merge #8→#9→#10→#11 on home main |
| Post-merge ritual | `run_a` | **OPEN** | doctor + routing_smoke + verkle-audit + autorun dry |
| Record graduation | `run_a` | **OPEN** | `release record --version v2 --gate run_a --ok` |
| Autorun dashboard card | `autorun_card` | **OPEN** | Phase 1 in HANDOFF_MAG_AGENT_TODOS |
| Tier refuse tests | `tier_refuse` | **PARTIAL** | Ticket A2 — T0/T1 never remote |

**Evidence:** `memory/improve/releases/gates.jsonl` does not exist yet — no gate has been recorded.

### 3.2 Operator soil (not code — still blocking confidence)

| Item | Status |
|------|--------|
| `.env` from `.env.example` on home PC | operator |
| Scheduled MagImproveDaily + MagVerkleWeekly | not registered (HANDOFF §2) |
| W0.3 archive governance decision | operator-only (`queue/todo.md`) |
| `[mag]` queue items | **all complete** |

### 3.3 v2 "done" definition

v2 is **complete for automation purposes** when:

1. `run_a` recorded in gates.jsonl  
2. `scripts/routing_smoke.py` green on home main  
3. `route.v2` is the single classifier for orchestrator, autorun, desk route hints  
4. FKB + autorun + verkle_audit callable from CLI without import errors  
5. Desk loop + scheduler + timing still pass tests after merge  

Until then, v3 features are **research on branch**, not product truth.

---

## 4. v3 — what we are building next

**One line:** Make the repo **route, file, and speak** like a product — one DeepSeek run command, Chat preflight, factory plan→build→audit, modules on home main.

### 4.1 v3 gates (`configs/releases.yaml`)

| Gate | Depends | Delivers | Status |
|------|---------|----------|--------|
| `run_a` | v2 | Lattice on main | Blocked |
| `factory_pilot` | run_a | First `build_audit.v1` JSON | **Passed** |
| `freeze_gate` | factory_pilot | No BUILD without frozen spec | **Passed** |
| `chat_preflight` | run_a | Ask default, timeout, pending UI | **Passed** |
| `deepseek_run` | run_a | Frozen T2 DeepSeek round trip | **Passed** — `memory/runs/v3_deepseek_proof.md` |
| `witness_filed` | — | v3 witness post linked | **Passed** |

### 4.2 RUN sequence (authoritative order)

```text
RUN A  — merge #8–#11 + ritual                    ← YOU ARE HERE
RUN B  — factory pilot → build_audit.v1 on disk
RUN D  — factory freeze gate (anti plan-theater)
CHAT   — preflight strip (CHAT-1–4)
RUN C  — pull #13/#15 or merge v3 modules to main
```

**Not v3 blockers:** L-conductor train, GSTD implement, XRPL, riddle packs, mobile voice.

---

## 5. The desk loop — from dialogue to version factory

Today the desk is an **operator membrane**. Tomorrow it is the **control surface for automated version builds**.

### 5.1 What the desk loop is

Six acts, one spine (`configs/version_roadmap.yaml` → `agent_loop`):

```text
Act I   Interest filed     attention · bonds · brief · context-pack
Act II  Plan descends      grok_hook · escalate · cloud_handoff · Cursor FILE
Act III Local plans        qwen-desk · canvas edit · scheduler serializes
Act IV  Problems rise      DeepSeek · handoff_loop · meta lanes
Act V   Compound           training_events · improve_loop · release gate
Act VI  Peer optional      GSTD mycorrhiza (v5+)
```

**Token law:** Plans down narrow. Problems up as deltas only. Local never re-derives what DeepSeek already read.

### 5.2 Desk components → version-build role

| Desk primitive | Today (manual) | Factory role (automated) |
|----------------|----------------|--------------------------|
| `slow_wake` | Operator clicks wake | Stage 2 entry — local reads brief + canvas |
| `handoff_loop` | 5-handoff test | Stage 2–4 — local↔remote until board encodes BUILD spec |
| `meta_discuss` | Meta ping button | Strategy lane without GPU wake |
| `run_exclusive` | Serializes all desk POSTs | **Required** for every loop tick GPU work |
| Canvas edit | Human-readable WIP | **Frozen BUILD artifact** when spec locked (RUN D) |
| `write_cloud_handoff` | Cursor files outcome | Stage 2 materialization proof |
| Timing badges | Operator trust | Loop SLO — regress if latency spikes |

### 5.3 What's wired vs missing for factory mode

| Wired | Missing |
|-------|---------|
| handoff_loop, slow_wake, meta | `loop tick` CLI wrapper |
| scheduler + triage | Ask/janitor through scheduler |
| cloud_handoff ingest | grok_hook → auto-enqueue on plan event |
| training_events module | `task_lifecycle` + `release_milestone` proven in events.jsonl |
| release record CLI | Automated gate evaluation after audit |
| orchestrator spawn/kill | BUILD stage tied to frozen canvas/handoff |
| — | DeepSeek `{blockers, instruction}` JSON schema |
| — | `mag/build_audit.py` (RUN B artifact) |

---

## 6. Orchestration system — the engine behind the desk

The desk is the **face**. Orchestration is the **engine**. Version automation requires both.

### 6.1 Component map

```text
                    ┌─────────────┐
         goal ─────►│  route.v2   │──► seat matrix (L0/L2/L3)
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │ coordination│  │ governor_   │  │ desk via    │
  │ activity    │  │ autorun     │  │ scheduler   │
  └─────────────┘  └──────┬──────┘  └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ orchestrator│ spawn · drain · reap · dedupe
                   └──────┬──────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │ improve_loop│  │ failure_kb  │  │ verkle_audit│
  └─────────────┘  └─────────────┘  └─────────────┘
                          │
                          ▼
                   training_events.jsonl
                          │
                          ▼
                   release record → gates.jsonl
```

| Module | Path | Version-build job |
|--------|------|-------------------|
| **Router** | `mag/router.py` | Classify every tick stage — never bypass |
| **Coordination** | `mag/coordination.py` | Log seat activity; depth route scut vs heavy |
| **Orchestrator** | `mag/orchestrator.py` | Spawn build worker; drain queue; emit task_lifecycle |
| **Governor autorun** | `mag/governor_autorun.py` | Fill queue from soil gaps; autorun_cycle events |
| **Improve loop** | `mag/improve_loop.py` | Ingest cloud handoff; spider + nervous refresh |
| **Local scheduler** | `mag/local_scheduler.py` | Serialize desk stages in tick |
| **Desk dialogue** | `mag/desk_dialogue.py` | handoff_loop = spec negotiation |
| **Training events** | `mag/training_events.py` | Every boundary filed |
| **Release registry** | `mag/release_registry.py` | Gate graduation |
| **Conductor** | `mag/conductor.py` | v3 plan/build/audit overlay on route.v2 |
| **Spider** | `mag/spider.py` | Detect plan theater, idle autorun |
| **Switchboard** | `mag/switchboard.py` | Mesh peer route (v8 horizon) |
| **FKB** | `mag/failure_kb.py` | Repeat failure → remedy block |
| **Verkle audit** | `mag/verkle_audit.py` | History gap fill |

### 6.2 CLI commands the loop must orchestrate (today, manual)

| Command | Loop stage |
|---------|------------|
| `improve-loop cycle --drain` | ingest + compound |
| `autorun --once` | build fill |
| `orchestrator spawn` / drain | build |
| `ingest <handoff_id>` | plan materialized |
| `conductor "goal"` | v3 phase overlay |
| `loop-audit` | anti-stuck |
| `release record` | gate |
| Desk POST slow_wake / handoff_loop | desk |

**Problem:** These are separate invocations. Operators glue them in chat. **Vision:** one `loop tick`.

---

## 7. `loop tick` — automating the next version reliably

### 7.1 Design principles

1. **Idempotent** — same soil state + same tick → same decision (dry-run provable)  
2. **One artifact per stage** — no stage completes without a file on disk  
3. **Serialized GPU** — all desk work through `run_exclusive`  
4. **RUN D enforcement** — orchestrator rejects BUILD if spec not frozen  
5. **Emit always** — training event at every boundary  
6. **Human L3** — merge, promote, spend require explicit operator or `--approve`  
7. **Fail closed** — tick aborts; partial state filed in trail; no silent continue  

### 7.2 Proposed CLI

```powershell
python main.py loop tick [--dry] [--stage all|ingest|desk|build|audit|gate]
python main.py loop status          # last tick trail + gate readiness
python main.py loop plan-v3       # expand queue/todo top item into handoff spec
```

### 7.3 Stage specification

| Stage | Input | Action | Output artifact | Gate |
|-------|-------|--------|-----------------|------|
| **0 ingest** | grok_feed, cloud handoffs, todo | improve-loop ingest; pick top `[mag]` or version goal | `memory/runs/loop_tick/{id}.json` | Open goal exists |
| **1 plan** | brief + attention | If grok plan event → escalate or enqueue; else skip | `queue/handoff/plan-{id}.json` | `[priority]` budget |
| **2 desk** | canvas + handoff | `run_exclusive(handoff_loop or slow_wake)` | updated canvas + cursor JSON | meaningful canvas edit |
| **3 freeze check** | canvas / handoff | RUN D: verify BUILD block marked frozen | freeze marker in handoff | reject if not frozen |
| **4 build** | frozen handoff | orchestrator spawn → drain_once | diff + task trail | exit 0 |
| **5 audit** | build output | routing_smoke + targeted pytest + build_audit JSON | `memory/runs/build_audit/{slug}.json` | audit pass |
| **6 compound** | audit result | improve-loop scout; spider tick; nervous refresh | events.jsonl rows | ≥1 new event |
| **7 gate** | releases.yaml | Evaluate gates; if green → `release record` | gates.jsonl row | operator L3 if irreversible |

### 7.4 Minimal first implementation (v3 unblocker)

**Scope:** One vertical slice — no full automation yet.

```text
loop tick --dry --stage desk
  → read brief + attention
  → run_exclusive(slow_wake, operator_note from todo)
  → if remote edit: handoff_loop(handoffs=1)
  → emit training_event(pattern=route_decision, tags=[hypha_plan_down, loop_tick])
  → append memory/runs/loop_tick_trail.jsonl
```

**Verify:** One tick → canvas updated, timing badges fresh, new events.jsonl row, scheduler depth returned to 0.

**Then expand:** add build stage after RUN B factory module lands.

### 7.5 Using desk loop to build v3 specifically

| v3 deliverable | Desk + orchestration path |
|----------------|----------------------------|
| Chat preflight | desk route hint + UI strip; loop tick does not replace UI work — **parallel track** |
| factory_pilot | tick stage 5 audit → first build_audit.v1 |
| deepseek_run | tick stage 4 build with `scripts/v3_deepseek_run.cmd` as orchestrator goal |
| run_a | **manual merge first** — tick cannot substitute git ritual |
| Module merge #15 | after run_a: tick can spawn branch merge verification pytest |

**Honest sequencing:**

```text
1. Human: merge RUN A (#8–#11) + release record v2 run_a
2. Human: implement mag/build_audit.py (RUN B pilot)
3. Code: loop tick stub (desk stage only)
4. loop tick --stage build → first factory_pilot JSON
5. release record v3 factory_pilot
6. Expand tick to full stage chain
7. v3 features merge to main; loop tick drives v4 curriculum
```

---

## 8. Alignment — how subsystems stay on compass during automation

Automation increases drift risk. These are the **non-negotiable alignment surfaces**:

| Subsystem | Alignment artifact | Loop tick hook |
|-----------|-------------------|----------------|
| Vision | COMPASS + this doc | tick refuses goals not in version_arc |
| Biology/protocol | MYCELIAL_SCIENCE_MAP | emit hypha_* tags |
| Machine arc | version_roadmap.yaml | stage 7 reads gates from releases.yaml |
| Routing | route.v2 | every spawn classified |
| Desk | handoff_loop.v1 | stage 2 only path to GPU dialogue |
| GPU | local_scheduler | run_exclusive wrapper mandatory |
| Truth | DNA.md / memory layout | tick writes only under memory/runs/loop_tick/ |
| Sovereignty | CONSTITUTION + tiers | pack-first; refuse T0/T1 before any remote |
| Discipline | MAG_LOOP_DISCIPLINE | loop-audit before build stage |
| Graduation | release record | stage 7; never auto-merge to main |

**Weekly operator ritual (5 min):** release status · Stack strip · attention.md · one gate or event if shipped.

---

## 9. Path diagram — today → automated v3 → v6 self-build

```text
TODAY (v2.x lab)
  Desk works · scheduler works · orchestration in pieces · RUN A open
        │
        ▼
MERGE RUN A (#8–#11) + release record v2
        │
        ▼
RUN B factory pilot (build_audit.py) + release record v3 factory_pilot
        │
        ▼
loop tick stub (desk stage) → trail + events
        │
        ▼
loop tick full (ingest→desk→build→audit→compound)
        │
        ▼
deepseek_run + chat_preflight gates green → v3 substrate on main
        │
        ▼
loop tick drives v4 conductor eval → v5 GSTD optional
        │
        ▼
v6: loop opens PR for next feature — operator L3 merge only
        │
        ▼
v10: republic service — pennies, peers, evolving local steward
```

---

## 10. Risks and honesty

| Risk | Mitigation |
|------|------------|
| Tick runs without RUN A | Stage 7 checks gates.jsonl for run_a before build |
| Plan theater | RUN D freeze + spider + loop-audit |
| GPU pile-up | scheduler run_exclusive — hard error if bypass |
| Chat supersedes disk | tick writes trail; amends docs at gates only |
| Auto-merge without review | No git write in tick v1; L3 explicit |
| Fake v3 progress | gates.jsonl is evidence; empty = not done |

**We are not claiming:** peer mesh is production-scale · auto-merge is safe · v4 conductor evaluation has graduated.

**We are claiming:** the **pieces exist**; the **vision is one binding loop**; v2 remainder is **measurable** (RUN A + gates file); desk loop is the **right control surface** because it already negotiates specs on canvas before anything hits orchestrator.

---

## 11. Cross-link map

| Need | File |
|------|------|
| North star | `MAG_MYCELIAL_REPUBLIC_COMPASS.md` |
| Biology ↔ protocol | `MYCELIAL_SCIENCE_MAP.md` |
| Feature tour + canvas | `MAG_FUTURE_WALKTHROUGH.md` |
| Next coding order | `MAG_NEXT_CODING_RUN.md` |
| Phase gates | `MAG_DIRECTION_ARTIFACT_v2.md` |
| Loop anti-patterns | `MAG_LOOP_DISCIPLINE.md` |
| Version gates machine | `configs/releases.yaml` |
| Agent loop machine | `configs/version_roadmap.yaml` |
| Merge todos | `HANDOFF_MAG_AGENT_TODOS.md` |

---

## 12. Amend protocol

| Trigger | Action |
|---------|--------|
| run_a recorded | Update §3.1 all OPEN → done; bump as-of |
| loop tick stub lands | Add CLI path to §7.4; update walkthrough |
| factory_pilot JSON filed | Update §4.1 factory_pilot status |
| New orchestration module | Add row §6.1 |
| v6 self-build begins | New § on PR automation bounds |

---

*Vision v1 — parent: mag-vision-automation-001 · the loop builds the next version; the desk is the factory floor.*
