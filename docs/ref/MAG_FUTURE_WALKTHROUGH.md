# Mag future walkthrough — where we are, where we go, how we stay aligned

**Commitment:** `mag-future-walkthrough-001`  
**As-of:** 2026-08-05  
**Status:** Living walkthrough — update at phase gates, not in chat  
**Job:** Full feature path from **today's v2.x lab** to **v10 Mycelial Republic service** with subsystem alignment law  
**Interactive:** Cursor canvas `mycelial-republic-future.canvas.tsx` (IDE canvases folder)

**Load with:** [`MAG_MYCELIAL_REPUBLIC_COMPASS.md`](MAG_MYCELIAL_REPUBLIC_COMPASS.md) · [`MAG_VISION_AUTOMATION.md`](MAG_VISION_AUTOMATION.md) (deep v2→v3 + loop factory)  
**Machine arc:** `configs/version_roadmap.yaml`

---

## 0. How to use this doc

| Reader | Path |
|--------|------|
| **Operator (Nacho)** | §1 snapshot → §4 subsystem board → §5 version walkthrough → §6 next 3 moves |
| **Any agent seat** | §2 alignment law → §3 agent loop demo → §4 your subsystem row |
| **New contributor** | §1 → §7 OpenClaw delta → §8 service milestones |

**Alignment rule:** If chat disagrees with compass + this file + `version_roadmap.yaml`, **disk wins**. Amend docs at gates; do not drift in session.

---

## 1. Where we are right now (v2.x — shipped on your box)

You are **past origin, inside substrate**. v1–v2 were hand-built. The lab runs.

### 1.1 Operator-visible features (try today)

| Feature | What it does | How to touch it |
|---------|--------------|-----------------|
| **Mag Agent Desk** | Local ↔ DeepSeek dialogue on shared canvas | `python main.py lab` → `:8765` Office tab |
| **Local pulse** | GPU/CPU thinking signal | Badge `#localPulse` · `GET /api/v1/local-pulse` |
| **Agent timing** | Per-seat latency + token estimate | `#deskTimingBadges` beside pulse |
| **Local scheduler** | One GPU job at a time; DeepSeek triage when depth≥2 | Stack strip · `python main.py scheduler status` |
| **Handoff loop** | 5-step Local→DeepSeek escalation on board | Desk · **5 handoffs** button |
| **Meta lanes** | DeepSeek discusses how to talk to Local (no wake) | Desk meta ping |
| **Days bead tree** | Workdays + subsessions + semi-visible Verkle | Days tab · 3D tapestry |
| **Stack strip** | Research + fleet glance (pulse, GSTD, Unsloth, scheduler) | Stack tab |
| **Unsloth seat** | Fine-tune surface hook | Stack · `python main.py unsloth status` |
| **Desk ops** | Reload/wipe without 4 Python windows | `python main.py desk reload` · `desk_refresh.cmd` |
| **Coordination feed** | All seats see shared activity | `GET /api/v1/coordination` |
| **Improve loop** | Cloud handoff → local ingest | `queue/handoff/cloud-*.json` |
| **Grok hook** | Grok session events → local feed | `watch/grok_feed.jsonl` |
| **Context pack** | Min-token pack for any seat | `python main.py context-pack` |
| **Training events** | Behavioral ledger on disk | `memory/training/events.jsonl` |

### 1.2 Machine truth (home PC, Aug 2026)

| Resource | State |
|----------|-------|
| GPU | RX 5600 XT 6GB — qwen-desk @ ~69 t/s, 100% GPU when serialized |
| Desk model | `qwen-desk` (orchestrator) · janitor `gemma:2b` |
| Desk steering | OFF (prompt injection) — scheduler steer ON |
| GSTD | 6/6 repos cloned · API up · `GSTD_API_KEY` pending |
| Trust ladder | Tier 0 · slow→fast fail (baseline probes) |

### 1.3 What's real vs theater

| Real today | Not yet (honest) |
|------------|------------------|
| Multi-seat REST loop on one disk | Cross-operator peer mesh at scale |
| Serialized local GPU | Ask/janitor fully through scheduler |
| File-based handoffs | `loop tick` one-command forever loop |
| Compass + science map filed | v6+ loop self-build without hand-merge |
| GSTD probe | GSTD edge worker enrolled |
| Training event append | Cost ledger / pennies dashboard |

---

## 2. Alignment law — how subsystems stay on compass

Ten subsystems. Each has **one alignment artifact** agents must read before acting.

```text
                    ┌─────────────────────────────────────┐
                    │  COMPASS + version_roadmap.yaml      │
                    │  (north star — amend at gates only)  │
                    └─────────────────┬───────────────────┘
                                      │
     ┌────────────┬────────────┬─────┴─────┬────────────┬────────────┐
     ▼            ▼            ▼           ▼            ▼            ▼
  Desk/UI    Agent loop   Memory/     Coordination  Scheduler   Training/
  :8765      seats        Residual    + peers       GPU         Evolution
     │            │            │           │            │            │
     └────────────┴────────────┴─────┬─────┴────────────┴────────────┘
                                     ▼
                          release record + training event
                          (L2 SCORE — behavioral trail)
                                     ▼
                          human L3 on irreversible only
```

| # | Subsystem | Job | Alignment artifact | Drift symptom |
|---|-----------|-----|-------------------|---------------|
| 1 | **Desk / Office** | Operator membrane — see and steer | `docs/agent_desk_operator_manual.md` | New UI with no REST/route |
| 2 | **Agent loop** | Grok→Cursor→Local→DeepSeek | `MAG_MYCELIAL_REPUBLIC_COMPASS.md` §2 | Shared chat context across seats |
| 3 | **Memory / Residual** | DNA store — truth survives sessions | `docs/DNA.md` · `memory/` layout | Second truth store in chat |
| 4 | **Coordination** | Seats see WIP + depth route | `mag/coordination.py` · `/api/v1/coordination` | Hidden parallel work |
| 5 | **Scheduler / GPU** | Serialize scarce compute | `mag/local_scheduler.py` · lanes.yaml | Parallel Ollama pile-up |
| 6 | **Training / Evolution** | Episodes → distill → better local | `memory/training/events.jsonl` · science map §5 | Repeat mistakes, no emit |
| 7 | **Improve / Factory** | Cloud ingest → scout → promote | `mag/improve_loop.py` · LOOP_DISCIPLINE | One-off scripts, no trail |
| 8 | **Sovereignty / Tiers** | T0/T1 never remote | `CONSTITUTION.md` · `configs/data_tiers.yaml` | Secrets in remote prompt |
| 9 | **GSTD / Mesh** | Optional peer GPU (mycorrhiza) | `mag/gstd_probe.py` · spores/mesh/ | Architecture depends on token |
| 10 | **Service / Onboard** | Clone → offline → join | `version_roadmap.yaml` → service_milestones | Features before empty-state |

**Weekly alignment ritual (operator, 5 min):**

1. `python main.py release notes v3` — what gate is next  
2. Stack tab — scheduler depth, GSTD, pulse  
3. `memory/attention.md` — still true?  
4. One `release record` or training event if something shipped  
5. Hard refresh `:8765` after Python changes  

---

## 3. Feature walkthrough — one loop pass (the product in motion)

This is **what v10 feels like**, partially live today.

### Act I — Interest filed (follows you)

1. Operator works → `memory/attention.md` + bonds capture open loops  
2. Brief filed → `memory/briefs/latest.md`  
3. Context-pack → any seat gets **interests + WIP**, not full chat  

**Today:** ✅ attention, bonds, brief, context-pack  
**Gap:** Resonance auto-surface (v4 conductor)

### Act II — Plan descends (Grok → Cursor)

1. Grok plans architecture → `escalate_grok` / grok_hook  
2. Handoff or cloud packet → `queue/handoff/`  
3. Cursor (this seat) materializes code + docs on disk  

**Today:** ✅ grok_hook, escalate_grok, cloud_handoff, Cursor seat  
**Gap:** Auto-enqueue on grok_hook planning event

### Act III — Local plans (cheap GPU)

1. Local reads brief + canvas  
2. `qwen-desk` plans task on board — scheduler serializes  
3. Timing badge: `Local 2.1s · 88 tok`  

**Today:** ✅ desk, scheduler, timing, qwen-desk  
**Gap:** Ask/janitor through scheduler

### Act IV — Problems rise (DeepSeek judges)

1. DeepSeek reads long context — docs + board  
2. Returns **blockers + one instruction** — not full re-plan  
3. Meta lanes discuss Local comms without waking GPU  

**Today:** ✅ handoff_loop, remote turn, meta_a/b  
**Gap:** Structured `{blockers, instruction}` JSON schema

### Act V — Percolate + compound

1. Training event filed — `hypha_problem_up` / `route_decision`  
2. Improve loop ingests if cloud touched repo  
3. Release gate when version milestone hit  

**Today:** ✅ events.jsonl, improve_loop, release CLI  
**Gap:** `loop tick` orchestrator, cost ledger

### Act VI — Peer optional (mycorrhiza)

1. Local surplus → GSTD edge offers inference  
2. Peer activity visible in coordination feed — **no T0/T1 export**  
3. Pennies on desk, not $8/mo scroll  

**Today:** 🟡 probe only  
**Gap:** enrollment, edge worker, cost visibility

---

## 4. Subsystem board — NOW / NEXT / FUTURE

| Subsystem | NOW (v2.x) | NEXT (v3–v5) | FUTURE (v6–v10) |
|-----------|------------|--------------|-----------------|
| **Desk** | Canvas, pulse, timing, scheduler UI | Chat preflight, factory status strip | Empty-state onboarding, cost strip |
| **Agent loop** | handoff_loop, meta, grok escalate | `loop tick` CLI, problem-up JSON | Self-spawn with depth guard |
| **Memory** | beads, verkle, briefs, attention | Conductor overlay on pack | Steward auto-catalog (v7) |
| **Coordination** | shared_activity, tripartite peer | Workboard-class task deps | Mesh peer handoff (v8) |
| **Scheduler** | run_exclusive, triage, steer | Ask/janitor queued | Cross-node queue mirror |
| **Training** | events.jsonl, route_decision | hypha tags, eval fixtures | Auto-distill on gate green |
| **Improve** | cloud_handoff, ingest | factory build_audit.v1 | Loop-built PRs (v6) |
| **Sovereignty** | tier refuse, pack-first | cost_ledger draft | Federation tier law |
| **GSTD** | 6/6 clone, health probe | edge + API key | Peer mesh economics |
| **Service** | mag.cmd doctor, lab | offline desk milestone | Install → pennies (v9–v10) |

---

## 5. Version walkthrough — v3 through v10

Each version = **one curriculum unit**: loop pass + gate + training event + distill attempt.

### v3 — Substrate (IN PROGRESS)

**User story:** *"I open :8765, chat works, factory can plan→build→audit once, DeepSeek run is one command."*

| Feature | Build target | Gate |
|---------|--------------|------|
| DeepSeek RUN sheet | `MAG_NEXT_CODING_RUN.md` RUN A | `release record v3 deepseek_run` |
| Chat preflight | Ask default, pending bubble, timeout | `chat_preflight` |
| Factory pilot | First `build_audit.v1` JSON | `factory_pilot` |
| Orchestrator merge | route.v2 unified | branch #8–#11 |

**Alignment:** direction artifact §3 · do not start v4 features here

### v4 — Mold (process before volume)

**User story:** *"Mag drafts next steps; human promotes. Conductor scores patterns before volume."*

| Feature | Build target |
|---------|--------------|
| Conductor loop draft | `MAG_V4_CONDUCTOR_LOOP_DRAFT.md` |
| training_patterns.yaml | eval before promote |
| Steward spore catalog | cleanup without ask |
| Resonance | old ideas when soil rhymes |

### v5 — Forest pipe (optional seats)

**User story:** *"I can join GSTD with one key; device probes forest; still works offline without it."*

| Feature | Build target |
|---------|--------------|
| GSTD edge worker | gstdbot + OLLAMA_HOST |
| Vast / XRPL | scored optional seats |
| seat_economics map | playbook + probe |

### v6 — Loop self-build

**User story:** *"Mag opens a PR for the next Mag feature; I L3 approve."*

First version the **loop** builds without hand-merge. Gate: one merged feature + green tests + training event.

### v7 — Steward autonomy

**User story:** *"Soil stays clean; catalog and digest run daily without me asking."*

### v8 — Mesh peer handoff

**User story:** *"My agent sees peer WIP; handoff to anon node for burst GPU — OpenClaw-class + sovereignty."*

Spores: Briar, Bitchat, Bridgefy filed in `docs/ref/spores/mesh/`.

### v9 — Service packaging

**User story:** *"Friend clones, doctor green, desk works with zero beads in 30 minutes."*

### v10 — Mycelial Republic

**User story:** *"Pennies/day. Frontier on my disk. Device fuels peers. Bureaucracy optional."*

---

## 6. Next three moves (from where you stand)

Ordered by **unblocks the most loop**:

| # | Move | Why | Verify |
|---|------|-----|--------|
| **1** | `python main.py loop tick` design + stub | Makes forever loop explicit | One stage runs Grok→local→DeepSeek |
| **2** | GSTD `GSTD_API_KEY` + edge test | Mycorrhiza handshake | gstdbot inference via local Ollama |
| **3** | Wire Ask + janitor through scheduler | Close GPU bypass | No parallel Ollama outside queue |

Parallel: Unsloth train on `agent_desk_dialogue.jsonl` → `desk-local` model.

---

## 7. OpenClaw-class — what we add

| OpenClaw gives | Mag adds |
|----------------|----------|
| Multi-agent gateway + subagents | REST seat graph + residual sovereignty |
| Filesystem coordination | + Verkle proof + training events |
| Workboard task deps | + interest-following (attention/bonds) |
| Per-agent workspace | + **evolving** local model from episodes |
| Cheaper subagent models | + tier law + pennies ledger |
| Single-host | + GSTD peer mesh (optional) |

**Pitch:** OpenClaw with an **evolving agent** that shares tasks and resources, follows your interests, and joins peers without feeding extractors.

---

## 8. Service milestones (layman path)

From `version_roadmap.yaml` — no dates, emergent gates:

```text
install → offline_desk → handoff_loop → factory_pilot → gstd_join → pennies_not_dollars
```

| Milestone | You know it worked when |
|-----------|-------------------------|
| install | `mag.cmd doctor` green |
| offline_desk | `:8765` useful with zero API keys |
| handoff_loop | One goal → result → ingest round trip |
| factory_pilot | build_audit.v1 JSON on disk |
| gstd_join | Edge probe green, optional |
| pennies_not_dollars | Cost visible; janitor default |

---

## 9. Amend protocol

| Trigger | Update |
|---------|--------|
| Feature ships | §1.1 row + §4 NOW column + canvas |
| Gate passed | `release record` + VERSION_REGISTRY + §5 status |
| Subsystem drift | §2 alignment artifact row |
| New peer pattern | MYCELIAL_SCIENCE_MAP + §7 |

**Do not:** add calendar dates · claim v6–v10 shipped · let chat supersede this file.

---

*Walkthrough v1 — parent: mag-future-walkthrough-001 · canvas sibling*
