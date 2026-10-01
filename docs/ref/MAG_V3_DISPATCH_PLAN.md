# Mag v3 — Restful dispatch plan (cheap agents ship the next version)

**Commitment:** `mag-v3-dispatch-plan-001`  
**As-of:** 2026-08-05  
**Status:** Operator runbook — how v3 graduates without schizo seats  
**Parents:** `MAG_NEXT_CODING_RUN.md` · `MAG_BUILD_PIPELINE.md` · `MAG_v3_SWARM_VISION.md`

**One job:** Ship the **next version** by **dispatching cheap agents** with **thin context**, **frozen specs**, and **$0 local routing** — you sign permits, not keystrokes.

---

## 0. Restful means

| Not | Yes |
|-----|-----|
| One agent loads 7 docs then "what do you want?" | **Your question → conductor → one seat → thin pull** |
| Chat as handoff | **BUILD spec on disk** |
| Frontier thinks about routing | **conductor + switchboard ($0 API)** |
| Parallel chaos | **One epic per branch; queue drains one at a time** |
| Loops narrated in prompt | **Loops FILE after; next pull is 1–2 cards** |

**Personality = lane discipline**, not lore. Janitor stays janitor because the pack is small and the job is narrow.

---

## 1. Dispatch stack (who routes whom)

```text
                    ┌─────────────────────────┐
                    │  YOU (L3) — freeze · merge │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  CONDUCTOR ($0)          │
                    │  phase: plan|build|audit │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
     ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
     │ SWITCHBOARD │   │ ORCHESTRATOR│   │ AUTORUN     │
     │ mesh · reap │   │ spawn · queue│   │ fill · drain│
     └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │  CHEAP SEATS (dispatched)      │
              │  Ollama · DeepSeek agent · Cursor audit │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  DISK (truth)                  │
              │  BUILD spec · trail · audit JSON │
              └───────────────────────────────┘
```

**Dispatcher law:** conductor picks phase + seat; switchboard steers live children; orchestrator spawns **one** worker with **one** goal; autorun drains queue when AFK.

---

## 2. Agent roster (cheap first)

| Agent | Seat | When dispatched | Pack mode | Must not |
|-------|------|-----------------|-----------|----------|
| **Clerk** | Ollama `gemma4` | ask, brief, scut, classify | **janitor** (thin) | architect, multi-file |
| **Builder** | DeepSeek `agent` | `[build]` + frozen BUILD | **build** (spec + bonds) | change spec, replan |
| **Planner** | Grok TUI | `[priority]` plan only | **plan** (template + goal) | implement |
| **Inspector** | Cursor | audit phase | **audit** (spec + diff) | new features |
| **Supervisor** | conductor/spider | always on ($0) | none | spawn second orchestrator |

**Target economics per epic:** Grok 5–15% · DeepSeek 50–70% · Cursor audit 15–25% · Ollama ~0.

---

## 3. Pack modes (ask-first — build in v3)

| Mode | Layers | Used by |
|------|--------|---------|
| **janitor** | nervous one-liner · bonds · brief headline · optional 1 FKB card | `ask`, L0 route |
| **route** | janitor + conductor phase note | `route`, `conductor` |
| **build** | route + **frozen BUILD file only** + branch name | orchestrator spawn |
| **audit** | build + diff summary + gate commands | Cursor audit |
| **full** | today’s context-pack (explicit opt-in) | Grok `[priority]`, debugging |

**v3 must ship:** `build_context_pack(mode=…)` + default `janitor` for `ask`.  
Until coded: operator manually passes **one file + one goal** to builders (no FRAMEWORK_LOAD dump).

---

## 4. Version = dispatch waves (not a big bang)

v3 graduates in **waves**. Each wave = one frozen BUILD epic, dispatched cheap agents, audit FILE, merge.

### Wave 0 — Foundation (home PC, human)

| Step | Agent | Action |
|------|-------|--------|
| W0.1 | You | Merge PR #8 → #9 → #10 → #11 |
| W0.2 | You | Pull PR #13 (v3 CLI modules) |
| W0.3 | Clerk | `mag.cmd doctor` · `routing_smoke` · `verkle-audit --dry` |

**Exit:** v2 lattice honest. v3 modules on disk.

---

### Wave 1 — Thin seat (v3 personality)

**Slug:** `pack-modes-janitor`  
**BUILD:** `queue/handoff/BUILD-pack-modes-janitor.md` (create from template)

| Phase | Dispatch | Deliverable |
|-------|----------|-------------|
| Plan | Grok/caveman | BUILD spec: `mode=` on context_pack, default janitor for ask |
| Freeze | You L3 | `Status: frozen` |
| Build | DeepSeek/ponytail | `mag/context_pack.py` + `main.py context-pack --mode` |
| Audit | Cursor | pytest + ponytail-audit |
| Merge | You L3 | branch → main |

**Exit:** `mag.cmd ask` feels like local janitor — emergent, not schizo.

---

### Wave 2 — Dispatch hooks (v3 nervous system on hot path)

**Slug:** `dispatch-hooks`  
**Depends:** Wave 1

| Phase | Dispatch | Deliverable |
|-------|----------|-------------|
| Build | DeepSeek | training_events on autorun + orchestrator lifecycle |
| Build | DeepSeek | conductor before autorun spawn; freeze gate on `[build]` |
| Build | DeepSeek | skill-seat preamble **only** when conductor phase matches |
| Build | DeepSeek | switchboard reap + route_intent on orchestrator spawn |
| Audit | Cursor | integration tests |

**Exit:** Cheap agents dispatched **through** conductor/switchboard, not raw `spawn_task`.

---

### Wave 2.5 — Seat registry union (desktop ↔ orchestrator)

**Slug:** `seat-registry-union`  
**Depends:** Wave 0 (switchboard on disk from PR #13)

| Phase | Dispatch | Deliverable |
|-------|----------|-------------|
| Build | DeepSeek | `mag/seat_registry.py` — register/heartbeat/unregister |
| Build | DeepSeek | `orchestrator.register_external` + external reap (stale heartbeat) |
| Build | DeepSeek | switchboard mesh includes external + seat-guard peers |
| Build | DeepSeek | REST `POST /api/v1/seats/register` · CLI `mag seats register` |
| Build | Clerk | `launch_cursor_seat.cmd` + `cursor_bridge register` on boot |
| Build | DeepSeek | restful contract: `MAG_NONINTERACTIVE=1` · improve timeout 420s |
| Audit | Cursor | `tests/test_seat_registry.py` |

**Exit:** Desktop-launched agents appear in orchestrator/switchboard; improve loops use one-shot + shorter timeout; no stdin hang on queued work.

**Operator habit after merge:**

```text
mag_kill.cmd                              # kill switch — everything down
mag_on.cmd                                # turn on — supervisor + dashboard
mag.cmd power status                      # CLI stack glance
launch_cursor_seat.cmd                    # registers ext-* task automatically
python watch/cursor_bridge.py register    # or from Cursor terminal when lab up
mag.cmd switchboard peers --live          # see cursor + orchestrator children
mag.cmd seats list --live                 # external seats only
```

**Power panel:** Dashboard → Body tab → Power card (Stop all / Turn on).

Improve / autopilot: prefer `cursor_bridge task "…" --mode queue` over raw `agent` REPL.

---

### Wave 3 — Factory FILE (first v4-shaped artifact)

**Slug:** `factory-audit-json`  
**Spec:** `docs/ref/BUILD-factory-audit-json-EXAMPLE.md`

| Phase | Dispatch | Deliverable |
|-------|----------|-------------|
| Plan | Grok | BUILD spec for `mag/build_audit.py` |
| Build | DeepSeek | CLI + `memory/runs/build_audit/{slug}.json` |
| Audit | Cursor | factory pilot checklist |

**Exit:** Plan → build → audit **FILEs JSON** — factory grammar exists.

---

### Wave 4 — Freeze gate productized

**Slug:** `factory-freeze-gate`  
**Depends:** Wave 3 audit pass

| Build | orchestrator/autorun reject build without frozen handoff |
| Audit | test: `[build]` without BUILD → defer |

**Exit:** Token bleed guard is **code**, not habit.

---

### Wave 5 — v3 → product label

| Action | Agent |
|--------|-------|
| loops_registry: switchboard/conductor/spider → `shipped` | DeepSeek |
| `MAG_NEXT_CODING_RUN.md` update | Clerk doc pass |
| One full factory epic end-to-end | All seats |

**Exit:** v3 is **product**, v4 factory line can compound.

---

## 5. Restful dispatch ritual (per epic)

Copy this every time. **No improvisation in chat.**

### Step 1 — You write the epic (one line)

```text
Epic: pack-modes-janitor — thin context-pack modes; ask defaults janitor
```

### Step 2 — Dispatch planner (Grok or caveman Cursor)

```text
[priority] PLAN only.
Read: docs/ref/BUILD-TEMPLATE.md + docs/ref/MAG_BUILD_PIPELINE.md
Output: queue/handoff/BUILD-{slug}.md
Max 8 files. Checkbox acceptance. No code.
```

### Step 3 — You freeze (L3)

- Review BUILD spec  
- Set `Status: frozen`  
- Copy to local `queue/handoff/` if gitignored  

### Step 4 — Dispatch conductor (local $0)

```bash
python main.py conductor "[build] {slug}: implement frozen BUILD spec"
python main.py switchboard route "implement BUILD-{slug}"
```

Read: seat, phase, suggested branch `cursor/{slug}-e2ce`.

### Step 5 — Dispatch builder (cheap)

```bash
python main.py orchestrator queue add "Implement BUILD-{slug} per queue/handoff/BUILD-{slug}.md" \
  --provider deepseek --tag build
python main.py orchestrator drain --once
# OR one-shot:
python main.py orchestrator run "Implement BUILD-{slug} …" --provider deepseek --tag build --wait
```

**Builder LOAD (manual until Wave 1):**

```text
GOAL: Implement BUILD-{slug}.md exactly.
LOAD: queue/handoff/BUILD-{slug}.md + memory/bonds_active.md only.
BRANCH: cursor/{slug}-e2ce
RUN: pytest paths from spec. FILE: trail + changed paths.
```

### Step 6 — Dispatch inspector

```text
AUDIT only. Diff main...cursor/{slug}-e2ce.
Run: ponytail-audit, routing_smoke, pytest from BUILD spec.
FILE: memory/runs/build_audit/{slug}.json
Verdict: pass | fix | reject
```

### Step 7 — You merge (L3)

```bash
python main.py verkle-audit --dry
git merge cursor/{slug}-e2ce
python main.py training-events --stats   # episodes filed
```

---

## 6. Queue discipline (restful concurrency)

| Rule | Why |
|------|-----|
| **One running task** | orchestrator drain default — no 8× duplicate spawns |
| **One branch per epic** | `cursor/{slug}-e2ce` |
| **Duplicate goal refused** | orchestrator dedupe already shipped |
| **MAG_OPERATOR_ACTIVE=1** | you code; autorun pauses |
| **Steer not re-paste** | switchboard `drop` / pigeonhole `!steer` |

Parallel epics only when **different repos/worktrees** — not same repo same branch.

---

## 7. What you touch vs what agents touch

| You | Cheap agents |
|-----|--------------|
| Epic one-liner | Plan BUILD spec |
| Freeze spec | Implement spec |
| Merge PR | Branch + tests + trail |
| `[priority]` on plan | Never merge |
| promote improve candidates | Never auto-promote lanes |

**Your calendar:** freeze Tuesday · merge Saturday · everything else dispatched.

---

## 8. Success metrics (honest)

| Metric | Target |
|--------|--------|
| ask pack size | ↓ 60%+ after Wave 1 |
| DeepSeek % per epic | 50–70% |
| Grok % per epic | 5–15% |
| Re-plan loops | ↓ (freeze gate Wave 4) |
| training_events | ↑ each wave |
| audit JSON | exists after Wave 3 |

---

## 9. Immediate next action (start tomorrow)

```text
1. Home PC: merge v2 #8–#11 (Wave 0)
2. Write BUILD-pack-modes-janitor.md (Wave 1 plan)
3. Freeze → dispatch DeepSeek on branch cursor/pack-modes-janitor-e2ce
4. Do not start Wave 2 until Wave 1 audit pass
```

**Parallel safe now (cloud agent):** draft BUILD spec for Wave 1 or Wave 3 — plan seat only, no build until frozen.

---

## 10. Links

- Run sheet: `MAG_NEXT_CODING_RUN.md`
- Factory: `MAG_BUILD_PIPELINE.md` · `MAG_FACTORY_PILOT.md`
- Fleet roles: `JONES_AGENT_FLEET_PACK.md`
- Thin pack philosophy: conversation + `MAG_BEHAVIORAL_COMPOUNDING.md`
- Switchboard: `MAG_SWITCHBOARD_VISION.md`

---

*v3 ships by dispatch waves. v4 is what happens when the waves compound into habit.*
