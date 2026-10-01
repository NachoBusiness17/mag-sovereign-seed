# Mag Full Blast Plan — v3 underpinnings + phone→Cursor→swarm

**Commitment:** `mag-full-blast-plan-001`  
**As-of:** 2026-08-05  
**Status:** Operator runbook — how Nacho runs Mag at full blast from phone + Cursor + Grok  
**Parents:** `MAG_v3_SWARM_VISION.md` · `MAG_V3_DISPATCH_PLAN.md` · `V3_HOME_SHIP_CHECKLIST.md`

**One breath:** You plan on the phone. Cursor writes frozen BUILD specs. Mag routes cheap DeepSeek + free Ollama on **your keys** via orchestrator. Grok CLI stays scarce. Files are law. Simulate cost before you blast.

---

## 0. Your stack (what you said out loud)

| Seat | Role | Why you love it |
|------|------|-----------------|
| **Cursor agent** | Hands + multi-file + cloud agents | Light-years beyond CLI for coding |
| **Grok CLI** | Plan / `[priority]` / judgment | You can't stop coding from phone |
| **Mag home PC** | Router + memory + swarm drain | Passive planner, RESTful loops |
| **Phone** | Plan v3, dispatch waves, approve | Sign permits, not keystrokes |

**Full blast** = all loops running honestly: improve → behavioral → nervous → spider → queue drain, with **cost simulation** before each wave.

---

## 1. Can you "hijack" Cursor's models?

**Short answer: No — not inside Cursor's black box. Yes — by routing work *around* it the Mag way.**

| Fantasy | Reality |
|---------|---------|
| Intercept Composer's internal API calls | Cursor bills its own models; you can't MITM their stack |
| Force Cursor cloud agents to use your DeepSeek key silently | Cloud agents run on Cursor infra — not your orchestrator |
| "Route via their hardware" to cheap tokens | Their hardware, their keys, their economics |

**What actually works (and what v3 ships):**

```text
┌─────────────────────────────────────────────────────────────────┐
│  CURSOR (subscription) — plans, edits, audit, cloud agent UI    │
│  · Writes BUILD specs to disk                                     │
│  · cursor_bridge improve / task --mode queue for EXECUTION       │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST :8765 (your Mag)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  MAG ROUTER ($0) — conductor · switchboard · spider · nervous   │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌──────────┐      ┌─────────────┐     ┌─────────────┐
   │  Ollama   │      │  DeepSeek   │     │  Grok CLI   │
   │  YOUR $0  │      │  YOUR API $ │     │  YOUR xAI $ │
   │  janitor  │      │  builder    │     │  plan only  │
   └──────────┘      └─────────────┘     └─────────────┘
```

**Dual-stack law:**

- **Cursor** = L3 hands + plan authoring + audit diff (use the tool you love).
- **Mag orchestrator** = execution swarm on **your** DeepSeek/Ollama keys (`agent --query`, queue drain).
- Never use Cursor subscription tokens for bulk `[improve]` loops — queue them to DeepSeek.

**Optional future (Wave — proxy seat):** OpenAI-compatible shim `localhost:PORT/v1` → DeepSeek so Cursor *custom model* points at Mag. Explicit config, not hijack. Not required if you use `cursor_bridge task --mode queue`.

---

## 2. Full blast topology (v3 underpinnings wired)

```text
                         PHONE (L3 permits)
                              │
              Grok CLI plan · brief note · "freeze BUILD"
                              │
                              ▼
                    queue/handoff/*.json  (FILE)
                    memory/briefs/latest.md
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   CURSOR DESKTOP      CURSOR CLOUD         HOME PC Mag ON
   hooks register      improve/cloud API    mag_on.cmd
   BUILD spec           handoff JSON         orchestrator
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │  IMPROVE LOOP (unified)        │
              │  behavioral · training ·       │
              │  nervous · spider · queue      │
              └───────────────┬───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │  BLAST PLANT (continuous dig)  │
              │  Ollama scout · influence dial │
              └───────────────┬───────────────┘
                              ▼
              RESIDUAL · promote gate · mag_kill.cmd
```

### Shipped modules (PR #13+)

| Layer | Module | Operator touch |
|-------|--------|----------------|
| Kill/start | `mag/power.py` | `mag_kill.cmd` / `mag_on.cmd` |
| Desktop union | `mag/seat_registry.py` | hooks + `cursor_bridge register` |
| Mesh | `mag/switchboard.py` | `switchboard peers --live` |
| Improve cycle | `mag/improve_loop.py` | `improve --claim … --enqueue` |
| Cost sim | `mag/cost_simulator.py` | `cost-sim wave "epic"` |
| Economy | `mag/token_economy.py` | dashboard economy / `GET /api/v1/economy` |
| Blast | `mag/blast.py` | `main.py blast --run` |

---

## 3. The phone → swarm workflow (your actual life)

### Phase A — Plan (phone, Grok CLI, cheap)

```text
# On phone / Grok CLI — NO code execution
[priority] Plan epic: <name>
Output: queue/handoff/BUILD-<slug>.md with acceptance criteria
```

File to repo via git push, cloud sync, or paste into Cursor when at desk.

**Cost:** Grok/xAI — simulate with `mag.cmd cost-sim goal "[priority] …"`.

### Phase B — Freeze (Cursor desktop, you L3)

```text
scripts\install_cursor_hooks.cmd   # once
launch_desktop.cmd               # Mag ON + register
# Cursor: refine BUILD → Status: frozen
# conductor phase=plan|build|audit
```

Cursor agent writes the plan; **you** freeze. Token-heavy planning stays in Cursor — that's fine if it's one wave per epic.

### Phase C — Dispatch swarm (Mag, cheap)

```text
mag.cmd cost-sim wave "epic-slug" --improve 2 --build 3
mag.cmd improve-loop cycle --drain
# or from Cursor:
python watch/cursor_bridge.py improve --claim "…" --enqueue
python watch/cursor_bridge.py task "[build] …" --mode queue
```

Execution = **DeepSeek via orchestrator** (your API) + **Ollama** janitor — not Cursor REPL.

### Phase D — Cloud agent (optional)

Cloud agent finishes → **must FILE**:

```text
POST /api/v1/improve/cloud  { "claim": "…", "brief": "…", "enqueue": true }
```

Home PC drains queue when `mag_on` + drainer or manual `improve-loop cycle --drain`.

### Phase E — Audit + merge (Cursor hands)

```text
python watch/cursor_bridge.py task "audit only: diff vs BUILD" --mode queue
# or Cursor IDE review → you merge (L3)
```

### Phase F — Exit

```text
mag_kill.cmd
```

---

## 4. Token counter / cost simulation

**Two layers:**

| Layer | What | Where |
|-------|------|-------|
| **Retrospective** | Actual turns logged | `mag/token_economy.py` → `logs/economy.jsonl` |
| **Prospective** | Simulate before dispatch | `mag/cost_simulator.py` + `configs/cost_rates.yaml` |

### Commands

```text
mag.cmd cost-sim wave "pack-modes-janitor" --improve 2 --build 3
mag.cmd cost-sim goal "[build] implement BUILD-foo"
mag.cmd economy          # via dashboard GET /api/v1/economy
```

Edit **`configs/cost_rates.yaml`** with your real DeepSeek/Grok/Cursor amortized rates.

**Target economics per epic (from dispatch plan):**

| Seat | Share of epic $ |
|------|-----------------|
| Grok + Cursor plan/audit | 15–25% |
| DeepSeek build | 50–70% |
| Ollama | ~0% |
| Mag routing | $0 |

---

## 5. Full blast modes

### Mode 1 — **Day job** (you're coding for fun)

```text
Mag ON → Cursor hooks → code in IDE → improve claims via bridge → Mag KILL
```

Drainer **off** unless AFK. `MAG_OPERATOR_ACTIVE=1` when in Cursor.

### Mode 2 — **Night shift** (swarm drains while you sleep)

```text
Mag ON → drainer ON (dashboard toggle) → improve-loop cycle
→ fill_queue → drain_one repeatedly → spider watches
```

Phone: check dashboard Body tab + Power card in morning.

### Mode 3 — **Blast plant** (continuous Ollama dig)

```text
main.py blast --run --bg
# influence dial: memory/improve/blast/influence.json
# focus: "v3 pack modes"
```

Pairs with improve scout; never auto-promotes — human `promote --apply`.

### Mode 4 — **Cloud parallel** (phone plans, home executes)

```text
Phone: Grok plan → handoff JSON pushed to repo
Cloud Cursor agent: POST /api/v1/improve/cloud
Home PC: mag_on + improve-loop cycle --drain
```

---

## 6. Seat roster at full blast

| Agent | Seat | Trigger | Pack | API $ |
|-------|------|---------|------|-------|
| Clerk | Ollama | ask, improve classify | janitor | 0 |
| Builder | DeepSeek | `[build]`, queue drain | build | yours |
| Planner | Grok CLI | `[priority]`, phone | plan | yours |
| Inspector | Cursor | audit, multi-file | audit | subscription |
| Dispatcher | conductor | every enqueue | route | 0 |
| Supervisor | spider+switchboard | always | — | 0 |
| Cloud filer | improve/cloud REST | cloud agent done | handoff | 0 |

---

## 7. Waves (revised with underpinnings)

| Wave | Slug | Status | Deliverable |
|------|------|--------|-------------|
| W0 | v2 merge + pull #13 | home PC | honest lattice |
| W1 | pack-modes-janitor | next code | thin ask |
| W2 | dispatch-hooks | next code | training on hot path |
| W2.5 | seat-registry-union | **shipped** | desktop ↔ orchestrator |
| W2.6 | power-kill-switch | **shipped** | mag_kill / mag_on |
| W2.7 | improve-loop-cloud | **shipped** | behavioral+nervous+spider |
| W3 | factory-audit-json | queued | BUILD → JSON |
| W4 | freeze-gate | queued | code rejects unfrozen build |
| W5 | cost-sim productized | **this doc + cost_sim** | simulate before blast |
| W6 | proxy-seat (optional) | research | Cursor custom → DeepSeek shim |

---

## 8. Anti-patterns (what breaks full blast)

| Don't | Do instead |
|-------|------------|
| Raw `launch_agent.cmd` for improve | `launch_agent_queue.cmd` or bridge queue |
| Cursor cloud agent chat-only handoff | `improve/cloud` JSON on disk |
| Close windows one-by-one | `mag_kill.cmd` |
| Skip cost-sim on big epic | `cost-sim wave` first |
| Grok for every scut | conductor → Ollama |
| Second orchestrator | switchboard mesh, one drain |

---

## 9. One-page daily card

```text
START   mag_on.cmd  (or launch_desktop.cmd)
PLAN    Grok / phone → BUILD md frozen
SIM     mag.cmd cost-sim wave "today"
DISPATCH cursor_bridge improve --claim "…" --enqueue
        cursor_bridge task "[build] …" --mode queue
WATCH   dashboard Body · switchboard peers --live
BLAST   main.py blast --run --bg  (optional)
STOP    mag_kill.cmd
```

---

## 10. Load order for agents reading this

```text
1. docs/ref/MAG_FULL_BLAST_PLAN.md  (this file)
2. docs/ref/V3_HOME_SHIP_CHECKLIST.md
3. docs/ref/MAG_V3_DISPATCH_PLAN.md
4. configs/cost_rates.yaml
5. mag.cmd context-pack --mode janitor  (when W1 ships; until then --agent)
```

**Law:** Chat is heat. FILES are law. Simulate cost. Cursor plans. Mag executes on your keys. Grok judges. Ollama sweeps.
