# Mag v3 — Research plan (not v2 scope)

**Version:** 3.0.0-research  
**Commitment:** `mag-v3-research-001`  
**As-of:** 2026-08-05  
**Status:** Research + design only — **do not block v2 merge or ship**

**Parents:** `MAG_v2_PLAN.md` · `HANDOFF_MAG_AGENT_TODOS.md` · `RESEARCH_MAG_VIRTUAL_DESK.txt`  
**Rule:** v2 ships the lattice (router, FKB, autorun, container, Office). v3 asks *what becomes possible after* that foundation is honest.

**Alpha honesty:** We are not out of alpha. v2 plan = beta-shaped roadmap; v3 = research. The product today is a **constitution + loops that file work** — not a finished orchestrator brain. Say so on the label.

---

## 0.1 Operator north star (2026-08-05 — founding frame)

> Mag is a **self-improving lattice** whose trained local expert does not replace frontier models — it **conducts** them. Like the founders could not predict every outcome of the Constitution, we do not predict every product end state. We write **law + loops** (residual, tiers, promote, trail) and let honest cycles compound.

| Metaphor | Mag equivalent |
|----------|----------------|
| Constitution / Declaration | `CONSTITUTION.md`, G1–G4, DNA, tiers T0–T3 |
| Amendments / case law | `decisions_log.jsonl`, FKB remedies, promote |
| Federalism | Mag (private office) + mycelial-republic (public fork) |
| Unpredictable outcome | Resonance, spider, frontier harness steals — **emergent**, not designed upfront |
| **Conductor** (not in founding docs) | **L-conductor** — local trained model expert at *direction + orchestration* of frontier seats |

**Trained model job (v3 research):** not mirror your voice; not do all coding. **Route, steer, notice, delegate, synthesize** — when to spend DeepSeek, when to hold Grok, when Ollama suffices, when to FILE and stop. Expert at **orchestration economics** on your soil.

**All v3 threads are nested self-improvement loops inside the lattice** — not separate products:

```text
improve (scout→eval→promote)     — loop on practices
autorun (fill→route→execute)     — loop on work queue
FKB (fail→remedy→score)          — loop on mistakes
verkle-audit                     — loop on history honesty
resonance (v3)                   — loop on corpus echoes
spider (v3)                      — loop on live agent health
virtual-desk research (v3)       — loop on workstation patterns
L-conductor train (v3)           — loop on steer/route outcomes
```

Each loop **files** to residual. None owns the throne. Conductor reads all trails; frontier models remain the **specialists** it calls.

---

## 0. Boundary (read first)

| In v2 (ship now) | In v3 (research / experiment) |
|------------------|-------------------------------|
| Merge #8–#12, autorun card, verkle-audit | Spider meta-supervisor |
| `route.v2`, governor_autorun, FKB | Resonance corpus lens |
| Container cage, operator modes | Mag Workstation / virtual desk GUI profile |
| improve scout → promote (human gate) | Auto-discovery without promote (pack injection) |
| Gemma L0 janitors | L-exp drift model / steer ranker (optional) |
| context-pack, chord at SessionEnd | Cross-corpus chord + atric/archive index |
| Steer plumbing (!steer, pigeonhole) | Proactive steer policy (spider) |

**Law carries forward:** no second DNA store · no auto weight train in lattice · promote stays human · T0/T1 never remote.

---

## 1. North star (v3 question)

> How does a **local conductor** — trained on your steer/route outcomes, not your diary — get better at directing frontier models while nested self-improve loops file everything honestly?

Secondary: resonance surfaces what rhymes across years of soil through any seat lens — without promote on every insight.

Not: replace Gemma or frontier. Not: mirror-as-product. Not: predict the final shape in alpha.

---

## 2. Research threads (from operator sessions 2026-08-05)

### 2.1 Virtual desk / second workstation

**Intent:** Mag plugs away on its own desk while operator codes elsewhere.

| Layer | v2 partial | v3 research |
|-------|------------|-------------|
| Ops | Win Virtual Desktop + container + `MAG_DRAINER` | Workstation profile (xvfb/Playwright cage) |
| Intel | `virtual-desk-loop` DeepSeek on brief | Import + eval vs manual research |
| Brief | `RESEARCH_MAG_VIRTUAL_DESK.txt` | Filled REPORT → implement Phase A/B |

**Deliverable:** `RESEARCH_MAG_VIRTUAL_DESK` section 8 report on disk.  
**Not v2:** noVNC on LAN, host Chrome profile for agent.

---

### 2.2 Spider (meta-supervisor on the agent web)

**Intent:** Something watches orchestrator children + chat agent + autorun trail — emits steer/pause/kill *before* operator types `!steer`.

**Problem today:** Steer is reactive plumbing; governor picks jobs, not mid-flight health; no unified watcher.

**v3 hypothesis:** Rule spider (Phase 0) fixes 80% without weights. Learned ranker on `decisions_log.jsonl` (Phase 1) only if rules plateau.

**Seat:** L-meta — read-only, emits pigeonhole/broadcast_steer, never spawns second orchestrator.

**Not:** from-scratch training · mirror · auto-promote.

---

### 2.3 Resonance (corpus lens — "find shit like this")

**Intent:** Any model via context-pack sees auto-surfaced echoes: your atric/archive + chord strikes + frontier scout hits + tonight's conversation — **without** promote gate for discovery.

**Problem today:** chord_lens = SessionEnd only; improve scout = outbound; mirror_lens = filter; tangent = manual markers. No inbound crosswalk → pack.

**v3 architecture sketch:**

```text
SOIL (residuals, chord, decisions, IJL, field-strike, archive whitelist)
  + FRONTIER (improve scout candidates)
       -> resonance index + tick
       -> findings.jsonl (no promote)
       -> context-pack L0e (top 3 cards, every seat)
```

**Training angle (v3 only):** index + chord extractors first; optional gemma:2b rerank; LoRA on "that's the shit" thumbs from case law — **not** pretrain on atric.

**Promote:** still human for config/skills. Resonance = notice only.

---

### 2.4 Training vs mirror (republic path)

**Intent:** Years of data + chord framework + frontier — what actually needs custom weights?

**v2 law:** weight train not in lattice; `max_auto_pull_gb: 0`; auto fine-tune from traces blocked.

**v3 research answer (tentative):**

| Use | Tool | Seat |
|-----|------|------|
| Daily scut | Gemma janitors | L0 |
| **Direction + orchestration** | **L-conductor** (trained on route/steer/decision outcomes) | **L-meta** |
| Resonance / spider rank | Small classifier or LoRA | L-meta helper |
| Mirror / style | LoRA on Gemma if ever | L-exp |
| From-scratch body | republic / train-llm-from-scratch | Off daily path; not conductor v0 |

**Conductor training signal:** `decisions_log` + `governor_trail` + `governor_autorun_trail` + promote outcomes + FKB — labels are *did this delegation work*, not *sound like me*.

**Phases:** bead exporter → conductor eval set (route/steer cases) → train in republic → import as L-meta after promote.

**Not v2:** replacing L0, autorun training loop, daily GPU burn, predicting product end state.

---

## 3. Open Socratic questions (operator answers when ready)

| # | Question | Blocks |
|---|----------|--------|
| 1 | Trained/spider output: steer timing, resonance cards, or both? | Spider vs resonance priority |
| 2 | Bead count + tier mix in archive/atric? | Training viability |
| 3 | GPU budget (home 6GB vs Vast)? | Workstation + train cadence |
| 4 | Learning vs shipping for v3? | Scope of first experiment |
| 5 | Archive paths whitelist for resonance index? | Privacy / tier law |

---

## 4. v3 phase sketch (research gates — not calendar)

### Phase 3.0 — Foundation gate

**Exit:** v2 merged on home PC; autorun card honest; routing_smoke green.

### Phase 3.1 — Resonance research

- Index schema + chord re-scan across residuals  
- `resonance --dry` spec (no ship requirement)  
- L0e pack wire design doc  

### Phase 3.2 — Spider research

- Rule policy table (heartbeat, FKB repeat, path collision)  
- Steer outcome labels from `decisions_log.jsonl`  

### Phase 3.3 — Virtual desk / workstation

- REPORT from virtual-desk research  
- Ops ritual doc vs xvfb profile decision  

### Phase 3.4 — L-exp / republic bridge

- bead-export JSONL schema  
- eval harness vs Gemma baseline  
- republic training handoff (no Mag daily coupling)  

---

## 5. What we explicitly defer from v2 conversations

- Building `mag/resonance.py` in v2 merge path  
- Building `mag/spider.py` in v2 merge path  
- Merging virtual-desk-loop to main before v2 core (#8–#11) unless operator chooses  
- Any auto-promote from discovery  
- Weight pulls, from-scratch as L0  

**v2 ships the honest lattice. v3 researches the noticing layer.**

---

## 6. Activation (for future seats)

```text
Mag v3 research — load MAG_v3_RESEARCH_PLAN.md + MAG_v3_BACKLOG.md + MAG_v2_PLAN.md (phases 0–3 shipped).
Do not implement v3 modules until v2 foundation gate passes.
New ideas → append MAG_v3_BACKLOG.md (v3-NNN); score vs P1–P6.
Conversation threads: spider, resonance, virtual desk, riddle packs, L-conductor — all v3.
```

**Feature ledger:** `docs/ref/MAG_v3_BACKLOG.md`

---

*End v3 research plan — update when operator answers Socratic questions or REPORT lands.*
