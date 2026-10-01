# Mag v3 — Frontier agent swarm vision

**Commitment:** `mag-v3-swarm-vision-001`  
**As-of:** 2026-08-05  
**Status:** Research architecture — the product shape we're building toward  
**Parents:** `MAG_v3_RESEARCH_PLAN.md` · `MAG_v3_BACKLOG.md` · `MAG_BUILD_PIPELINE.md` · `FRAMEWORK_LOAD.md`

**Read this when:** you want to understand Mag not as a chat app, but as a **passive local planner** running a **RESTful automated improvement engineering environment** — a frontier agent swarm routed from your machine.

---

## 1. One breath

Your home PC is the **brain stem**. It does not type for you. It **plans, routes, watches, files, and improves** while frontier APIs (Grok, DeepSeek, vision/code multimodal providers) do the expensive inference. The Office at `:8765` is the **window**; residual on disk is the **memory**; nested loops are the **organs**. v3 adds the **nervous system that notices** — spider, resonance, conductor, grove — without a second throne.

```text
You sign permits. Mag runs the swarm. Files are law. Chat is heat.
```

---

## 2. The swarm topology

```text
                    ┌─────────────────────────────────────┐
                    │  OPERATOR (L3) — permits & freeze   │
                    └──────────────────┬──────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
  ┌──────────────┐            ┌─────────────────┐           ┌──────────────┐
  │ L-CONDUCTOR  │            │     SPIDER      │           │  RESONANCE   │
  │ passive plan │            │  meta-watch     │           │ corpus lens  │
  │ route/phase  │            │ steer/pause     │           │ L0e echoes   │
  └──────┬───────┘            └────────┬────────┘           └──────┬───────┘
         │                             │                             │
         └─────────────────────────────┼─────────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │  REST LATTICE :8765 + orchestrator   │
                    │  route.v2 · autorun · FKB · verkle    │
                    └──────────────────┬──────────────────┘
                                       │
         ┌─────────────┬───────────────┼───────────────┬─────────────┐
         ▼             ▼               ▼               ▼             ▼
    ┌─────────┐  ┌──────────┐   ┌──────────┐   ┌──────────┐  ┌──────────┐
    │ Ollama  │  │ DeepSeek │   │   Grok   │   │  Cursor  │  │ Vision/  │
    │ janitor │  │ builder  │   │ architect│   │  hands   │  │ API seat │
    │  ~$0    │  │  L2 code │   │  scarce  │   │ L3 pause │  │  future  │
    └─────────┘  └──────────┘   └──────────┘   └──────────┘  └──────────┘
         │             │               │               │
         └─────────────┴───────────────┴───────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │  RESIDUAL — beads, trail, grove, FKB │
                    └─────────────────────────────────────┘
```

**Swarm rule:** one router, one orchestrator, one DNA store. Specialists are **stateless decoders** with packs — not roommates with memory.

---

## 3. Passive planner (your local machine)

### What "passive" means

| Active (v2 alpha today) | Passive (v3 target) |
|-------------------------|---------------------|
| You paste context-pack into every seat | Pack auto-refreshes; seats pull via REST |
| You type `!steer` when agent drifts | Spider emits steer from trail rules |
| You notice repeated FKB failures | Resonance surfaces remedy before re-run |
| You pick Grok vs DeepSeek ad hoc | Conductor classifies phase → seat |
| You read improve/ for learnings | Grove shows poem nodes in Office |

**Passive ≠ unattended.** G3 irreversible stays L3. `MAG_OPERATOR_ACTIVE=1` still pauses autorun. Conductor **recommends**; spider **nudges**; you **sign**.

### RESTful engineering environment

Mag already exposes the lattice as HTTP (`dashboard/rest.py`). v3 treats this as the **primary nervous interface** for the swarm:

| Endpoint family | Swarm role |
|-----------------|------------|
| `GET /api/v1/context-pack` | Any seat bootstraps without chat |
| `POST /api/v1/route` | Conductor-backed routing decision |
| `GET /api/v1/agents` | Spider watches live children |
| `POST /api/v1/agents/{id}/cmd` | Steer injection (human or spider) |
| `GET /api/v1/lattice-history` | Resonance + verkle honesty |
| `GET /api/v1/grove` (v3) | Layman skill tree |
| `GET /api/v1/v3/status` (v3) | Loop registry + research health |

**Restful** here means: **idempotent reads, explicit writes, FILE outcomes** — not "REST as fashion." Night shift calls the same APIs the IDE calls.

---

## 4. Multi-modal / API routing

v3 extends `route.v2` depth classification to **modality + economics**, not just text depth:

| Signal | Route bias | Seat |
|--------|------------|------|
| `[priority]` / plan markers | Architect | Grok |
| `[build]` / frozen BUILD spec | Factory floor | DeepSeek |
| `audit only` / diff review | Inspector | Cursor defer |
| Image / screenshot / PDF (future) | Vision API | L2 multimodal |
| Scut / classify / pack | Janitor | Ollama gemma:2b |
| T0/T1 in goal | **Refuse remote** | Local only |

**Conductor overlay** (`mag/conductor.py`) adds **phase** on top of `route.v2`:

```text
goal → detect_phase(plan|build|audit|defer|execute)
     → route.v2(seat, provider, depth)
     → case_law hints from decisions_log
     → FILE conductor_trail.jsonl (training labels later)
```

Training (v3-005, republic path) learns **did this delegation work** — not diary mimicry.

---

## 5. Nested loops — the improvement engineering env

Every v3 capability is a **loop inside the lattice**, not a separate app:

```text
┌─────────────────────────────────────────────────────────────┐
│                    MAG ENGINEERING ENV                       │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│   improve   │   autorun   │     FKB     │      verkle       │
│ scout→eval  │ fill→route  │ fail→remedy │ audit→gaps        │
├─────────────┼─────────────┼─────────────┼───────────────────┤
│  resonance  │   spider    │  conductor  │      grove        │
│ soil→L0e    │ watch→steer │ route→train │ FILE→poem nodes   │
├─────────────┴─────────────┴─────────────┴───────────────────┤
│  factory (v4 pilot)  plan→freeze→build→audit→merge          │
└─────────────────────────────────────────────────────────────┘
```

**Registry:** `python main.py v3-status` · `mag/loops_registry.py`

| Loop | v3 module | CLI |
|------|-----------|-----|
| Resonance | `mag/resonance.py` | `main.py resonance --tick` |
| Spider | `mag/spider.py` | `main.py spider --once` |
| Conductor | `mag/conductor.py` | `main.py conductor "goal"` |
| Grove | `mag/grove.py` | `main.py grove-build` |

---

## 6. Module deep dive

### 6.1 Resonance — "find shit like this"

**Problem:** chord_lens fires at SessionEnd only. Improve scout is outbound. No inbound crosswalk → pack.

**Mechanism:**

```text
SOIL (remedies, FKB, decisions_log, todo, improve candidates)
  → token overlap vs goal hint (brief + todo)
  → top 3 cards
  → context-pack L0e (every seat)
  → findings.jsonl (notice only — no promote)
```

**Law:** T0/T1 never in cards. Promote still human for config.

**Layman:** Office shows "this rhymes with something you filed before" — not magic memory.

### 6.2 Spider — eyes on the agent web

**Problem:** Steer is reactive. Governor picks jobs, not mid-flight health.

**Phase 0 (rules, shipped as research):**

| Rule | Signal | Action |
|------|--------|--------|
| Heartbeat stall | orchestrator task age > 180s | steer via pigeonhole |
| Autorun fail burst | 3+ fails in trail tail | suggest pause |
| FKB repeat | signature count ≥ 3 | surface remedy |
| Operator active | `MAG_OPERATOR_ACTIVE=1` | defer proactive steer |

**Phase 1 (future):** learned ranker on `decisions_log.jsonl` if rules plateau.

**Law:** L-meta read-only. Never spawns second orchestrator.

### 6.3 L-conductor — passive planner foreman

**Not:** mirror your voice · replace Gemma · auto-merge · predict product end state.

**Is:** local expert at **orchestration economics** — when to spend Grok, when DeepSeek suffices, when to FILE and stop.

**Training signal (v3-005):**

```text
BUILD_SPEC → build outcome → audit verdict → conductor label
route decision → autorun success/fail → FKB hit/miss
steer outcome → decisions_log outcome field
```

**Steiniger mapping:** static body = frozen spec + constitution; dynamic body = worker context; conductor learns when dynamic drifts violate static law.

### 6.4 Tesuji Grove — museum of competence

**Problem:** Learnings buried in `memory/improve/`. Layman can't browse.

**Mechanism:** `grove-build` scans remedies, skills, FKB → poem nodes with `source_path` → Office widget.

**Anti-patterns:** XP gamification · poems without files · auto-promote on node appear.

### 6.5 Virtual desk — second workstation

Mag's **other desk** while you code:

```text
Operator desk          Mag desk
Cursor IDE             queue/todo + autorun + orchestrator
MAG_OPERATOR_ACTIVE=1  MAG_DRAINER=1
Human keyboard         container cage + spawn children
```

v3 adds optional **headless workstation profile** (xvfb/Playwright cage) — see `RESEARCH_MAG_VIRTUAL_DESK.txt`.

### 6.6 Riddle packs — rent compute, not biography

Public API surface sees obfuscated goal; real BUILD spec stays T0/T1 on mount. Audit compares output to **local spec** — not riddle. Aligns factory pipeline + spore spine.

---

## 7. Layman Office as swarm face

```text
┌────────────────────────────────────────────┐
│  Plain office (always on)                  │
│  "Mag OK · last night: 2 jobs · next: …"   │
├────────────────────────────────────────────┤
│  [office_now]  [grove]  [night_shift]      │
│  customizable layout on disk               │
├────────────────────────────────────────────┤
│  Expert panels behind toggle               │
└────────────────────────────────────────────┘
```

**Grove widget** = swarm memory made legible. **Night shift card** = autorun trail humanized. **Curious errors** = FKB as fireflies.

Spec: `docs/ref/LAYMAN_OFFICE_VISION.md`

---

## 8. Seat economics (swarm cost model)

| Seat | Role in swarm | Target share |
|------|---------------|--------------|
| Ollama | Classify, pack, grove poem draft, resonance cheap score | ~0 marginal |
| DeepSeek | Build loops, tool chains, autorun heavy | 50–70% per factory epic |
| Grok | Plan, architecture, `[priority]` only | 5–15% |
| Cursor | Audit, your hands when coding | 15–25% audit |
| Conductor | Local routing — no API $ | 0 API |
| Spider | Rule tick — no API $ | 0 API |
| Switchboard | Mesh + tier drops — no API $ | 0 API |

**Bleed guard:** janitor first · consultant scarce · frozen spec before build · audit before merge · **local directions before dumb agent spawn**.

---

## 9. v3 implementation map (code on branch)

| Component | Path | Status |
|-----------|------|--------|
| Loop registry | `mag/loops_registry.py` | research CLI |
| Resonance + L0e pack | `mag/resonance.py` + `context_pack.py` | research wired |
| Spider Phase 0 | `mag/spider.py` | research CLI |
| Conductor overlay | `mag/conductor.py` | research CLI |
| Switchboard mesh | `mag/switchboard.py` | research CLI — dumb-agent directions, 0 API |
| Grove builder | `mag/grove.py` | research CLI |
| REST grove endpoint | `dashboard/rest.py` | not yet |
| Layman layout JSON | `memory/operator/dashboard_layout.json` | not yet |
| Conductor train export | v3-005 bead JSONL | not yet |

**Gate:** v2 merge (#8–#11) before v3 modules graduate from research to product.

---

## 10. Activation — boot a swarm seat

```text
LOAD Mag v3 swarm:
  1. docs/FRAMEWORK_LOAD.md
  2. docs/ref/MAG_v3_SWARM_VISION.md (this file)
  3. docs/ref/MAG_v3_RESEARCH_PLAN.md
  4. python main.py v3-status
  5. python main.py context-pack  → includes L0e resonance

One job. FILE outcomes. Chat dies.
```

### Conductor route example

```powershell
python main.py conductor "[build] factory-audit-json: implement frozen spec"
python main.py spider --once --dry
python main.py resonance --tick --goal "autorun FKB empty reply"
python main.py grove-build --dry
```

---

## 11. Path to v4 factory

v3 swarm + factory pipeline (`MAG_BUILD_PIPELINE.md`) compound into v4:

```text
v3: conductor routes phases · spider watches builds · resonance surfaces prior factory fails
v4: mag factory plan|build|audit|ship — you sign permits only
```

**Gate question:** Three factory epics with audit JSON + grove nodes + conductor labels — without re-explaining Mag in chat?

---

## 12. What v3 is NOT

- Unattended merge or publish  
- Athena/Steiniger persona theater  
- Second orchestrator or DNA store  
- Auto weight train in daily lattice  
- Cheaper without spec discipline  
- Finished product — **alpha honesty holds**

---

## 13. Socratic questions (operator)

| # | Question | Unlocks |
|---|----------|---------|
| 1 | Spider vs resonance priority first? | Implementation order |
| 2 | GPU budget for conductor train? | republic handoff cadence |
| 3 | Archive whitelist for resonance index? | Tier law for echoes |
| 4 | Plain office copy in v2 before full grove? | v3-011 partial ship |

---

*v3 is the noticing layer on an honest lattice. The swarm is already sketched in code — now compound loops.*
