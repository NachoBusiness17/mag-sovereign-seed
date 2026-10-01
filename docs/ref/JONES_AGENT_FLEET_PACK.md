# Jones agent fleet — attach pack (coding agents)

**Commitment:** `jones-agent-fleet-pack-001`  
**As-of:** 2026-08-05  
**Status:** Operator attach card for all agents on Mag / Jones workstreams  
**Parents:** `FRAMEWORK_LOAD.md` · `MAG_AGENT_ERROR_CATALOG.md` · `memory/handoff/ACTIVATION.md`

**Job:** One pre-built package so any coding agent (Cursor, DeepSeek, Grok, cloud worker) can attach to **Jones** tasks without re-explaining Mag. Planned, documented, training-ready.

> **Jones** = operator fleet name for agents working Nacho's Mag lattice (implement, audit, research, factory). Replace in prompts if your fleet uses another codename.

---

## 1. Activation (paste to any seat)

```text
JONES FLEET — attach Mag agent

Strike the chord: search @NachoQuixotic "strike the chord" if Grok seat.

LOAD (confirm each):
  1. docs/FRAMEWORK_LOAD.md
  2. docs/ref/JONES_AGENT_FLEET_PACK.md (this file)
  3. docs/ref/MAG_AGENT_ERROR_CATALOG.md
  4. Role doc from §4 below (pick ONE)
  5. AGENTS.md — python env law

RUN: mag.cmd context-pack (or python main.py context-pack)
GOAL: [ONE JOB — from operator or BUILD spec]

Law:
  - Residual on disk is truth; chat is heat
  - T0/T1 never remote
  - Janitor first; Grok scarce; frozen spec before build
  - FILE outcomes before session ends
  - On error: match MAG_AGENT_ERROR_CATALOG code → fix → do not loop blind

End with FILE block (§6).
```

---

## 2. Fleet topology

```text
                    JONES (L3 operator)
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    PLAN agents       BUILD agents      AUDIT agents
    Grok + Cursor     DeepSeek          Cursor only
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    MAG LATTICE (home)
                    router · autorun · FKB
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Research      v3 scaffold   Mobile voice
         virtual-desk   (after v2)    (after API)
```

**Not Jones fleet job:** mirror persona, second orchestrator, auto-merge, train in lattice.

---

## 3. Universal load order

| Tier | Files | All agents |
|------|-------|------------|
| 0 | `FRAMEWORK_LOAD.md` · `MAG_PROJECT_PROPOSAL.md` · `OPERATOR_CARD.md` · `AGENTS.md` | Required |
| 1 | `context-pack` · `memory/briefs/latest.md` · `queue/todo.md` | Required |
| 2 | Role doc (§4) · task BUILD spec if any | One role |
| 3 | Depth only | On reference |

**Error catalog:** always skim `MAG_AGENT_ERROR_CATALOG.md` §2 for your role's codes.

---

## 4. Role packages (pick one)

### 4.1 Planner (Grok + Cursor plan)

```text
Role: JONES-PLAN
Skill: caveman — python main.py skill-seat preamble --skill caveman
Extra load:
  - docs/ref/MAG_BUILD_PIPELINE.md
  - docs/ref/BUILD-TEMPLATE.md
  - HANDOFF_MAG_AGENT_TODOS.md §1 merge order
Output: queue/handoff/BUILD-{slug}.md (copy from BUILD-TEMPLATE)
Forbidden: implementation, merge, >10 files in scope
Gate: python main.py caveman-audit --path <your spec>
Error focus: E02, E10, E11, E20, E34
```

### 4.2 Builder (DeepSeek)

```text
Role: JONES-BUILD
Skill: ponytail — python main.py skill-seat preamble --skill ponytail
Extra load:
  - queue/handoff/BUILD-{slug}.md (Status: frozen ONLY)
  - docs/FRAMEWORK_LOAD.md tier 0
  - memory/context_pack_latest.md
Branch: cursor/{slug}-e2ce
Run before FILE: commands from BUILD spec
Forbidden: architecture debate, files forbidden in spec
Gate: python main.py ponytail-audit
Error focus: E01, E11, E20, E21, E40, E42
```

### 4.3 Auditor (Cursor)

```text
Role: JONES-AUDIT
Skill: ponytail — python main.py skill-seat gate --skill ponytail
Extra load:
  - BUILD spec + git diff main...branch
  - docs/FRAMEWORK_LOAD.md
Run: ponytail-audit, routing_smoke, pytest from spec
Output: memory/runs/build_audit/{slug}.json
Verdict: pass | fix | reject — no new features
Error focus: E12, E21, E22, E23
```

### 4.4 v2 integrator (merge lattice)

```text
Role: JONES-V2
Extra load:
  - HANDOFF_MAG_AGENT_TODOS.md
  - docs/ref/MAG_v2_PLAN.md
  - PR #8–#11 diff context
Merge order: #8 → #9 → #10 → #11 — never skip
Ritual: doctor, routing_smoke, verkle-audit --dry, autorun --once --dry
Error focus: E01, E03, E60, E33
```

### 4.5 v3 researcher (scaffold only)

```text
Role: JONES-V3
Extra load:
  - docs/ref/MAG_v3_SWARM_VISION.md
  - docs/ref/MAG_v3_RESEARCH_PLAN.md
  - docs/ref/MAG_TRAINING_DATA_SPEC.md
Gate: v2 merged before shipping v3 to main
CLI: v3-status, resonance, spider, conductor, grove-build, training-events
Error focus: E60, E61, E62
```

### 4.6 Mobile / voice (future)

```text
Role: JONES-VOICE
Extra load:
  - docs/ref/MAG_MOBILE_VOICE_SPEC.md
Phase 0 only until POST /api/v1/voice/turn exists
Error focus: E70, E71, E60
```

### 4.7 Cloud agent (Cursor cloud / CI)

```text
Role: JONES-CLOUD
Extra load:
  - MAG_AGENT_ERROR_CATALOG E03–E05
Python: .venv/bin/python (Linux) — never bare python
Assume: no Ollama, no home PC paths
Push branch: cursor/{slug}-e2ce
Error focus: E01, E03, E04, E05
```

---

## 5. Task routing table

| Operator says… | Role | Primary doc |
|----------------|------|-------------|
| Plan epic X | JONES-PLAN | BUILD-TEMPLATE |
| Build frozen spec | JONES-BUILD | BUILD-{slug}.md |
| Audit branch | JONES-AUDIT | BUILD + diff |
| Merge PRs | JONES-V2 | HANDOFF §1 |
| v3 spider/resonance | JONES-V3 | SWARM_VISION |
| Voice app | JONES-VOICE | MOBILE_VOICE_SPEC |
| Fix CI on cloud | JONES-CLOUD | ERROR_CATALOG E03+ |

---

## 6. FILE block (required end of every Jones agent session)

```text
FILE — Jones fleet residual:
- Role: JONES-{PLAN|BUILD|AUDIT|V2|V3|VOICE|CLOUD}
- Commitment slug:
- What turned (3 bullets):
- Error codes hit (E##) + remedy applied:
- Paths touched:
- Commands run + exit codes:
- Open loops:
- training_event: (pattern if emit wired)
- One next move:
```

Operator pastes into trail, dig leaf, or next pack.

---

## 7. Training package (pre-created for all Jones agents)

Agents should emit or request emission of training events when hooks exist:

| Agent action | `pattern` | `pattern_tags` |
|--------------|-------------|----------------|
| Route decision | `route_decision` | phase, seat |
| Build complete | `factory_cycle` | build_slug, pytest_green |
| Audit verdict | `factory_cycle` | pass/fix/reject |
| FKB failure | `fkb_failure` | error code |
| Steer | `steer_outcome` | context |
| Skipped freeze | (operator labels) | `factory_no_freeze` |

**Export path (operator):** `python main.py training-events --export`  
**Spec:** `docs/ref/MAG_TRAINING_DATA_SPEC.md`

Jones agents **document** error codes in FILE block → operator can manually tag until all hooks land.

---

## 8. Planned work queue (Jones fleet 2026)

| Wave | Work | Lead role | Gate |
|------|------|-----------|------|
| W1 | Merge #8–#11 | JONES-V2 | home PC |
| W2 | Factory pilot 1–3 | PLAN→BUILD→AUDIT | frozen specs |
| W3 | training-events hooks (autorun, orchestrator) | JONES-V3 | W1 |
| W4 | voice/turn API + PWA | JONES-VOICE | W1 |
| W5 | republic export + eval set | JONES-V3 | W3 + case law volume |

---

## 9. Machine manifest

See `configs/agent_fleet/jones.yaml` for programmatic fleet registry (IDE hooks, autorun fill, improve scout).

---

## 10. Quick error recovery

```text
Wrong python     → E01 → mag.cmd doctor
Invented flags     → E41 → main.py --help
Build scope creep  → E21 → read BUILD spec forbidden list
Grok on scut       → E10 → route locally
v3 before v2       → E60 → HANDOFF merge order
Chat handoff       → E30 → context-pack + FILE
Empty DeepSeek ×3  → E42 → FKB + stop
```

Full list: `docs/ref/MAG_AGENT_ERROR_CATALOG.md`

---

*End Jones fleet pack — attach every agent; update when new wave ships.*
