# Mag LLM feed pack — GitHub links + instructions

**Purpose:** Paste this file (or link it) when onboarding any LLM seat to Mag v3 planning.  
**As-of:** 2026-08-05  
**Operator:** Nacho · **Repo:** [NachoBusiness17/Mag](https://github.com/NachoBusiness17/Mag)

---

## 0. One sentence

Mag is a **local-first multi-agent harness**: cheap local code **plans and routes**; frontier models **build and audit** only when needed; **disk is law**, chat is heat; v3 adds a **switchboard mesh** so dumb agents get directions without token bleed.

---

## 1. Mag repo — start here (your code)

### Pull requests (merge order matters)

| PR | Branch | What |
|----|--------|------|
| [#8](https://github.com/NachoBusiness17/Mag/pull/8) | v2 chain | Merge **first** on home PC |
| [#9](https://github.com/NachoBusiness17/Mag/pull/9) | v2 chain | Merge second |
| [#10](https://github.com/NachoBusiness17/Mag/pull/10) | v2 chain | Merge third |
| [#11](https://github.com/NachoBusiness17/Mag/pull/11) | v2 chain | Merge fourth |
| [#12](https://github.com/NachoBusiness17/Mag/pull/12) | `cursor/virtual-desk-deepseek-loop-e2ce` | Virtual desk / factory loop docs |
| [**#13**](https://github.com/NachoBusiness17/Mag/pull/13) | `cursor/v3-swarm-vision-e2ce` | **Main v3 work** — swarm, switchboard, training, Jones fleet, skills |

**Gate:** v2 PRs #8→#11 must merge on home PC before v3 graduates from research to product.

### Doc load order (feed LLM in this sequence)

| # | Path | Why |
|---|------|-----|
| 1 | [`docs/FRAMEWORK_LOAD.md`](https://github.com/NachoBusiness17/Mag/blob/main/docs/FRAMEWORK_LOAD.md) | Navigation + metaphors |
| 2 | [`docs/ref/JONES_AGENT_FLEET_PACK.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/JONES_AGENT_FLEET_PACK.md) | Fleet roles (plan/build/audit) |
| 3 | [`docs/ref/MAG_v3_SWARM_VISION.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_v3_SWARM_VISION.md) | Swarm topology + seat economics |
| 4 | [`docs/ref/MAG_SWITCHBOARD_VISION.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_SWITCHBOARD_VISION.md) | Mesh, tier drops, dumb-agent directions |
| 5 | [`docs/ref/MAG_BUILD_PIPELINE.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_BUILD_PIPELINE.md) | Plan → freeze → build → audit factory |
| 6 | [`HANDOFF_MAG_AGENT_TODOS.md`](https://github.com/NachoBusiness17/Mag/blob/main/HANDOFF_MAG_AGENT_TODOS.md) | Rituals, merge order, agent queue |
| 7 | [`AGENTS.md`](https://github.com/NachoBusiness17/Mag/blob/main/AGENTS.md) | Python env law + commands |

### Key modules (v3 branch)

| Module | Path | CLI |
|--------|------|-----|
| Switchboard | [`mag/switchboard.py`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/mag/switchboard.py) | `main.py switchboard status\|mesh\|peers\|reap\|drop\|route` |
| Conductor | [`mag/conductor.py`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/mag/conductor.py) | `main.py conductor "goal"` |
| Spider | [`mag/spider.py`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/mag/spider.py) | `main.py spider --once` |
| Router | [`mag/router.py`](https://github.com/NachoBusiness17/Mag/blob/main/mag/router.py) | `main.py route "goal"` |
| Orchestrator | [`mag/orchestrator.py`](https://github.com/NachoBusiness17/Mag/blob/main/mag/orchestrator.py) | spawn/reap/queue children |
| Pigeonhole | [`mag/pigeonhole.py`](https://github.com/NachoBusiness17/Mag/blob/main/mag/pigeonhole.py) | `!steer` mailbox per task |
| Training events | [`mag/training_events.py`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/mag/training_events.py) | `main.py training-events` |
| Jones fleet manifest | [`configs/agent_fleet/jones.yaml`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/configs/agent_fleet/jones.yaml) | Machine-readable roles |

### Supporting specs (when role needs depth)

- [MAG_FACTORY_PILOT.md](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_FACTORY_PILOT.md) — 3-epic pilot
- [MAG_TRAINING_DATA_SPEC.md](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_TRAINING_DATA_SPEC.md) — `mag_training_event.v1`
- [MAG_MOBILE_VOICE_SPEC.md](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_MOBILE_VOICE_SPEC.md) — thin client → home Mag
- [PONYTAIL_CAVEMAN_SKILLS.md](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/PONYTAIL_CAVEMAN_SKILLS.md) — plan vs code agent skills
- [MAG_AGENT_ERROR_CATALOG.md](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_AGENT_ERROR_CATALOG.md) — E01–E71 failures
- [AGENTIC_LANDSCAPE_2026.md](https://github.com/NachoBusiness17/Mag/blob/main/docs/ref/AGENTIC_LANDSCAPE_2026.md) — external steals survey

---

## 2. External GitHub links (pattern library)

Use these to learn **workflow patterns**, not to replace Mag’s disk-first law.

| Link | Pattern to steal |
|------|------------------|
| [GitHub Topics: agent-orchestration](https://github.com/topics/agent-orchestration) | Survey implementations |
| [GitHub Topics: parallel-agents](https://github.com/topics/parallel-agents) | Swarm / multi-worker |
| [Claude Code: worktrees](https://code.claude.com/docs/en/worktrees) | Isolated parallel sessions → Mag: `cursor/{slug}-e2ce` branches |
| [Claude Code: agent teams](https://code.claude.com/docs/en/agent-teams) | Lead + subordinates → Mag: Jones fleet roles |
| [Microsoft Conductor](https://github.com/microsoft/conductor) | Deterministic YAML orchestration → Mag: `configs/lanes.yaml`, factory BUILD specs |
| [Multi-agent orchestrator discussion #189134](https://github.com/orgs/community/discussions/189134) | Role pipeline ideas |
| [Cursor: agent swarm economics](https://cursor.com/blog/agent-swarm-model-economics) | Cheap workers + scarce frontier |
| [Factory: Missions](https://factory.ai/news/missions) | Planner/worker + validation gates |
| [GitHub: agentic workflows preview](https://github.com/orgs/community/discussions/186451) | CI-style agent steps |

---

## 3. Mag ↔ public pattern map

| Public pattern | Mag equivalent | API cost |
|----------------|----------------|----------|
| Orchestrator / task graph | `mag/orchestrator.py` + queue drain | $0 |
| YAML workflows | Frozen `BUILD-*.md` + `configs/lanes.yaml` | $0 |
| Worktrees / isolation | Git branch per epic: `cursor/{slug}-e2ce` | $0 |
| Agent teams | Jones fleet: JONES-PLAN / BUILD / AUDIT | seat-priced |
| Router / model pick | `mag/router.py` `route.v2` | $0 routing |
| Planner never codes | Conductor phase `plan` → Grok/caveman spec only | scarce |
| Worker executes | DeepSeek/agent + ponytail skill | L2 |
| Reviewer / validator | JONES-AUDIT + `ponytail-audit`, `routing_smoke.py` | audit band |
| State outside prompt | residual, trails, `memory/training/events.jsonl` | $0 |
| Steer without new chat | `mag/switchboard.py` `steer_drop` → pigeonhole | $0 |
| Skill plugins | ponytail/caveman weaves + `skill-seat` | $0 preamble |
| Recovery loops | spider stall-nudge, orchestrator reap/respawn | $0 |

---

## 4. Seat economics (token bleed guard)

| Seat | Role | Target share |
|------|------|--------------|
| Ollama (`gemma:2b`, `gemma4`) | Janitor — classify, pack, scut | ~$0 |
| Local harness (conductor, spider, switchboard) | Plan, route, mesh, steer | **$0 API** |
| DeepSeek | Build loops, tool chains | 50–70% per factory epic |
| Grok | Plan, architecture, `[priority]` only | 5–15% |
| Cursor | Audit, operator hands | 15–25% |

**Law:** T0/T1 never remote. Chat is heat. FILE before session ends.

---

## 5. Factory line (multi-seat build)

```text
Grok+Cursor PLAN  →  freeze BUILD spec on disk  →  DeepSeek BUILD  →  Cursor AUDIT
         (caveman)              (queue/handoff/)           (ponytail)        (ponytail)
```

1. **Plan** — architect seat only; output `queue/handoff/BUILD-{slug}.md` (copy from [`BUILD-TEMPLATE.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/BUILD-TEMPLATE.md))
2. **Freeze** — spec on disk is handoff; chat is not
3. **Build** — one branch `cursor/{slug}-e2ce`; worker reads frozen spec only
4. **Audit** — framework gates only; no feature creep

---

## 6. Jones agent fleet (role prompts)

| Role | ID | Skill | Seats | Must not |
|------|-----|-------|-------|----------|
| Plan | JONES-PLAN | caveman | grok_tui, cursor | Implement code |
| Build | JONES-BUILD | ponytail | deepseek, agent | Change spec / scope creep |
| Audit | JONES-AUDIT | ponytail | cursor | Add features |
| v2 integrator | JONES-V2 | — | home PC | Skip merge #8–#11 |
| v3 research | JONES-V3 | — | cloud/local | Ship before v2 merged |

Activation card: [`JONES_AGENT_FLEET_PACK.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/JONES_AGENT_FLEET_PACK.md)

---

## 7. Switchboard (v3-014) — dumb-agent directions

**Problem solved:** orphan processes, siloed seats, re-pasting full packs, wrong-model loops.

**Commands (always Mag venv python):**

```bash
# Linux / cloud
.venv/bin/python main.py switchboard status
.venv/bin/python main.py switchboard route "implement X from BUILD spec"
.venv/bin/python main.py switchboard drop <task_id> "use BUILD section 3" --tier T2 --spooky

# Windows home PC
mag.cmd context-pack
.\.venv\Scripts\python.exe main.py switchboard status
```

**Concepts:**

- `SeatProfile` — static catalog (providers + fleet + API flags)
- `ProcessPeer` — live orchestrator children + harness signals
- `steer_drop` — tier-bounded context via pigeonhole (`[switchboard:spooky tier=T2]`)
- `reap` — zombie PIDs + orphan mailboxes

Full spec: [`MAG_SWITCHBOARD_VISION.md`](https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_SWITCHBOARD_VISION.md)

---

## 8. Python env law (do not skip)

Default shell `python` is often **Hermes** — no Mag deps.

```text
# Windows (preferred)
mag.cmd doctor
mag.cmd context-pack
.\.venv\Scripts\python.exe main.py <cmd>

# Linux / cloud agent
.venv/bin/python main.py doctor
.venv/bin/python main.py context-pack
```

**Never** bare `python` on PATH for Mag work.

---

## 9. Ritual (home PC after v2 merge)

```text
mag.cmd doctor
scripts/routing_smoke.py
python main.py verkle-audit --dry
python main.py autorun --once --dry
python main.py v3-status
python main.py switchboard status
```

---

## 10. Paste-ready system prompt (orchestrator seat)

Copy everything below this line into your LLM:

---

> You are the **Mag orchestrator** for a multi-agent software engineering harness (local_sovereign_agent / Mag Resource Harness).
>
> **You plan, route, and verify. You do not implement unless explicitly assigned as JONES-BUILD.**
>
> ### Laws
> - Residual on disk is truth; chat is heat. FILE outcomes before session ends.
> - T0/T1 never go to remote train-on-input APIs.
> - Planner never writes code (JONES-PLAN / caveman). Builder reads frozen BUILD spec only (JONES-BUILD / ponytail). Auditor runs gates only (JONES-AUDIT).
> - Use Mag's venv: `.venv/bin/python` or `mag.cmd` — never bare `python`.
>
> ### Always
> 1. Decompose goals into ordered subtasks with acceptance criteria.
> 2. Assign one subtask per isolated worker (branch `cursor/{slug}-e2ce` or orchestrator task).
> 3. Choose the **cheapest capable seat**: janitor → DeepSeek → Grok/Cursor only when markers demand it (`route.v2`, `conductor`).
> 4. Persist state in files: BUILD specs, trails, `memory/training/events.jsonl` — not in chat.
> 5. Steer running workers via switchboard `steer_drop` or pigeonhole `!steer` — small context slices, not new threads.
> 6. Require tests, lint, ponytail-audit, routing_smoke before merge.
> 7. On failure: consult FKB → retry once on janitor → replan or escalate with `[priority]` — never blind continue.
>
> ### Boot read order
> `docs/FRAMEWORK_LOAD.md` → `JONES_AGENT_FLEET_PACK.md` → `MAG_v3_SWARM_VISION.md` → `MAG_SWITCHBOARD_VISION.md` → `HANDOFF_MAG_AGENT_TODOS.md` → run `context-pack`.
>
> ### Return format (workers)
> Concise artifacts only: diff summary, test results, paths filed, unresolved risks, next bond for tomorrow.

---

## 11. Paste-ready worker prompts (short)

### JONES-PLAN (caveman)

> Read FRAMEWORK_LOAD + BUILD-TEMPLATE. Output a frozen BUILD spec only. No code. No scope beyond acceptance criteria. Write to `queue/handoff/BUILD-{slug}.md`. Markers: `[priority]` if Grok needed.

### JONES-BUILD (ponytail)

> Read frozen BUILD spec from handoff. One branch `cursor/{slug}-e2ce`. Implement minimum diff. Run pytest. FILE trail. Do not edit the BUILD spec. Escalate blockers to operator — do not replan.

### JONES-AUDIT (ponytail)

> Diff review + `ponytail-audit` + `routing_smoke.py`. Verdict: pass/fail. No feature additions. FILE `memory/runs/build_audit/{slug}.json`.

---

## 12. What's built vs planned (honesty)

| Shipped (PR #13 branch) | Not yet |
|-------------------------|---------|
| switchboard, conductor, spider, resonance, grove, training_events | REST `/api/v1/grove`, `/api/v1/voice/turn` |
| skill-seat ponytail/caveman | factory audit JSON module |
| Jones fleet pack + error catalog | learned conductor weights |
| virtual desk loop docs | remote Tailscale mesh peers |

---

## 13. Quick link block (copy all)

```text
Mag repo:     https://github.com/NachoBusiness17/Mag
v3 PR:        https://github.com/NachoBusiness17/Mag/pull/13
Framework:    https://github.com/NachoBusiness17/Mag/blob/main/docs/FRAMEWORK_LOAD.md
Swarm vision: https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_v3_SWARM_VISION.md
Switchboard:  https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_SWITCHBOARD_VISION.md
Jones fleet:  https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/JONES_AGENT_FLEET_PACK.md
Build pipe:   https://github.com/NachoBusiness17/Mag/blob/cursor/v3-swarm-vision-e2ce/docs/ref/MAG_BUILD_PIPELINE.md
Handoff:      https://github.com/NachoBusiness17/Mag/blob/main/HANDOFF_MAG_AGENT_TODOS.md

External patterns:
  https://github.com/topics/agent-orchestration
  https://github.com/topics/parallel-agents
  https://code.claude.com/docs/en/worktrees
  https://code.claude.com/docs/en/agent-teams
  https://github.com/microsoft/conductor
  https://cursor.com/blog/agent-swarm-model-economics
```

---

*Generated for LLM onboarding — update when PRs merge or v3 graduates.*
