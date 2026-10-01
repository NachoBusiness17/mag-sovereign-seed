# Mag — Mycelial Republic compass

**Commitment:** `mag-mycelial-republic-compass-001`  
**As-of:** 2026-08-05  
**Status:** **Primary compass** — load immediately after `FRAMEWORK_LOAD.md`  
**Job:** One filed north star for operators and agents: vision, agent loop, version arc, sovereignty law, service path  
**Honesty:** Planning law on disk — not a shipped product claim. Alpha until gates pass on home PC.

**Machine truth:** `configs/version_roadmap.yaml` · `configs/releases.yaml`  
**Direction detail:** `docs/ref/MAG_DIRECTION_ARTIFACT_v2.md`  
**Version index:** `docs/ref/releases/VERSION_REGISTRY.md`

---

## 0. Load this first (agents)

Any seat entering Mag should read in order:

```text
1. docs/FRAMEWORK_LOAD.md              — navigation + metaphors
2. docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md   ← this file (compass)
3. docs/ref/MYCELIAL_SCIENCE_MAP.md             — biology ↔ protocol
4. docs/ref/MAG_DIRECTION_ARTIFACT_v2.md       — phase gates + v3–v5 mold
5. docs/ref/MAG_PROJECT_PROPOSAL.md            — problem depth
6. AGENTS.md                                   — env law + commands
7. mag.cmd context-pack
8. ONE job from queue/todo.md
```

**Rule:** Chat is heat. Residual on disk is truth. T0/T1 never leave the building.

---

## 1. Vision — Mycelial Republic

Mag is an agent-based **coordination alternative** — government without bureaucracy. Not a chat app. Not a subscription scroll. A **frontier-level agent on your disk** that owns artifacts, routes scarce intelligence, and compounds behavior through filed episodes.

| Pillar | What it means | Operator test |
|--------|---------------|---------------|
| **Coordination without extraction** | Peers coordinate via handoffs and residual — no throne, no SaaS memory | You can fork the repo and run `:8765` without our permission |
| **Data sovereignty** | T0/T1 never hit train-on-input APIs; pack-first remotes | Tier refuse tests pass; `.env` secrets stay local |
| **Service economics** | Pennies/day local + optional seats — not $8/mo scroll rent | Janitor handles scut; Grok only on `[priority]` |
| **Device fuels network** | Your machine runs local inference; optional GSTD DePIN seat (v5) | GSTD probe green; device is peer, not client |
| **Weapon against extraction** | You own beads, trails, weights export — not chat history | `context-pack` + residual survive session death |

**Three houses** (stable direction — see `MAG_DIRECTION_ARTIFACT_v2.md` §4.3):

| House | Locus | Mag role |
|-------|-------|----------|
| **Beads** | `local_sovereign_agent` (private office) | Custody, routing, pack, residual |
| **Forest** | mycelial-republic | Public law, fork, optional republic train |
| **GSTD forest** | gstdcoin (v5 pipe) | Optional DePIN seat — not throne |

**North star sentence:** Local janitor first · frontier scarce · human L3 on irreversible · artifact > transcript.

---

## 2. Agent loop — forever loop / intra-agent communication

Mag does not run one monolithic agent. It runs a **serialized loop** where separate APIs talk via files and REST — not shared chat memory.

### 2.1 The loop (operator view)

```text
Grok plans
    ↓  (intent narrows — plans, strategy)
Cursor writes coding docs + materializes on disk
    ↓
Ollama local plans task (janitor / qwen-desk)
    ↓
DeepSeek long-context cheap tokens raises PROBLEMS up chain
    ↑  (blockers, questions, deltas only — not re-reasoning down)
Grok strategizes on deltas
    ↓
Cursor materializes fix
    ↓  (one loop pass → release gate → training event → distill)
```

**Down the chain:** intent narrows — plans, frozen BUILD specs, scoped tasks.  
**Up the chain:** blockers, questions, deltas only. Never re-reason the full stack upward.

| Seat | Role in loop | Token law |
|------|--------------|-----------|
| **Grok** | Strategy, architecture, hard judgment | Scarce — `[priority]` only |
| **Cursor** | Materialize — code, docs, FILE blocks | Operator hands; `MAG_OPERATOR_ACTIVE=1` |
| **Ollama (qwen-desk)** | Local plan, brief, route, desk timing | Always on, cheap (~69 t/s desk target) |
| **DeepSeek** | Long-context judge — raises problems, not plans | Cheap tokens; tool loops for build |

### 2.2 Handoff surfaces (separate APIs, one spine)

| Surface | Purpose |
|---------|---------|
| `handoff.v1` | Queue JSON + MD in `queue/handoff/` → results in `queue/results/` |
| `cloud_handoff` | Remote seat ingest without chat dump |
| **Desk canvas** | `:8765` Office — Body, Pulse, Days, Chat, timing badges |
| **Training events** | `memory/training/events.jsonl` — route decisions, release milestones |
| **Meta lanes** | `configs/lanes.yaml` — serialized GPU / seat scheduling |
| **grok_hook / escalate_grok** | Up-chain problem elevation |
| **handoff_loop / improve loop** | Scout → eval → promote (human gate) |

**Scheduler law:** Local GPU is serialized. Timing badges per agent on desk — honest latency, not cosplay parallelism.

**Loop discipline:** `docs/ref/MAG_LOOP_DISCIPLINE.md` · `docs/ref/MAG_BEHAVIORAL_COMPOUNDING.md`

---

## 3. Version arc — v1 through v10

### 3.1 Two eras

| Era | Versions | Who builds | What happens |
|-----|----------|------------|--------------|
| **Hand-built** | v1–v2 | Nacho by hand | Grok origin → this repo (substrate) |
| **Loop-trained** | v3–v10 | Mag loop builds next | One loop pass + release gate + training events + distill to local model |

Each loop-trained version = **one loop pass** + **release gate** + **training events filed** + **distill/export to local steward weights** (when eval green).

**Honesty:** v3–v5 have planning artifacts and partial implementation. v6–v10 are **curriculum slots** — direction filed, gates TBD, no fake dates.

### 3.2 Version map (summary)

| ID | Meaning | Status | Primary artifact |
|----|---------|--------|------------------|
| **v1** | Grok/X strike origin | shipped | [RELEASE_NOTES_v1.md](releases/RELEASE_NOTES_v1.md) |
| **v2** | This repo — harness + Office :8765 | shipped (hardening on branches) | [RELEASE_NOTES_v2.md](releases/RELEASE_NOTES_v2.md) |
| **v3** | Substrate — orchestrator, Chat, factory | in_progress | [RELEASE_NOTES_v3.md](releases/RELEASE_NOTES_v3.md) |
| **v4** | Mold — process before volume | planned | [MAG_V4_CONDUCTOR_LOOP_DRAFT.md](MAG_V4_CONDUCTOR_LOOP_DRAFT.md) |
| **v5** | Pipe — GSTD, Vast train, XRPL (optional seats) | planned | [MAG_v5_PIPE.md](MAG_v5_PIPE.md) |
| **v6** | Loop self-build — first Mag-built Mag | curriculum TBD | gate TBD |
| **v7** | Steward autonomy — daily soil without asking | curriculum TBD | gate TBD |
| **v8** | Mesh / peer handoff at scale | curriculum TBD | gate TBD |
| **v9** | Service packaging — install → offline desk | curriculum TBD | gate TBD |
| **v10** | Mycelial Republic — pennies/day, GSTD join | curriculum TBD | gate TBD |

Full registry: [VERSION_REGISTRY.md](releases/VERSION_REGISTRY.md) · machine: `configs/releases.yaml` · arc: `configs/version_roadmap.yaml`

---

## 4. Current built state (v2.x — honest now)

> **FROZEN as-of 2026-09-26 (Mag P0-1).** Section body below is the 2026-08-05/06 snapshot (desk :8765 / qwen-desk / GSTD 6/6). It does **not** describe September burn organs, seed 3.3.0, ratchet/workflow gates, inbox INDEX fold, or Mickey17. Do not treat rows as "today." Live truth: tip + state/CURRENT.md + watch/inbox/INDEX.json + SEED_SELF_STEAL_AUDIT_20260926.md. Vision prose (§1–3, §5+) untouched this turn — freeze stamp only, no compass rewrite. Stamp: 2026-09-26 13:58 EDT Mag seat.

What exists on disk today (FROZEN snapshot — trust tip/CURRENT/inbox, not this table).


| Component | State | Notes |
|-----------|-------|-------|
| **Mag Agent Desk** | Live `:8765` | Office, Body, Pulse, Days, Chat |
| **qwen-desk** | ~69 t/s target | Local planner seat |
| **Local scheduler** | Shipped | Serializes GPU; meta lanes |
| **Desk timing** | Shipped | Per-agent timing badges |
| **Unsloth seat** | Configured | Training path when eval green |
| **GSTD probe** | 6/6 repos | Index + pull; not Mag-native soil yet |
| **Improve loop** | Shipped | Scout → eval → promote (human) |
| **grok_hook / escalate_grok** | Shipped | Up-chain elevation |
| **handoff_loop** | Shipped | Queue handoff v1 |
| **Meta lanes** | Shipped | `configs/lanes.yaml` |
| **Days bead tree** | Shipped | 3D subsessions, Verkle lattice |
| **Stack strip** | Shipped | Dashboard stack visibility |

**Not yet green:** RUN A merge ritual (#8–#11 → home `main`). v3 factory pilot first audit JSON. See `MAG_DIRECTION_ARTIFACT_v2.md` §5.

---

## 5. Service milestones (operator path)

How a layman goes from clone to republic peer — no calendar dates, emergent gates.

| Milestone | User experience | Gate (honest) |
|-----------|-----------------|---------------|
| **install** | Clone, venv, `mag.cmd doctor` green | doctor + routing_smoke |
| **offline desk** | `:8765` works without remote keys | Ollama L0 sufficient for brief/ask |
| **handoff loop** | Queue goal → agent → result → ingest | One handoff v1 round trip |
| **factory pilot** | Plan → build → audit JSON on disk | RUN B first artifact |
| **GSTD join** | Device probes DePIN forest (optional) | gstd_t0_probe 6/6 + seat_score |
| **pennies not dollars** | Local janitor + rare frontier; cost ledger visible | seat economics + daily budget |

Machine config: `configs/version_roadmap.yaml` → `service_milestones`

---

## 6. Sovereignty guarantees (tier rules)

Constitutional law — not suggestions. Code and tests enforce where possible.

| Tier | Contents | Rule |
|------|----------|------|
| **T0** | Secrets — api_key, password, `.env`, credentials | **Never** remote. Local only. |
| **T1** | Private/intimate — `data/raw`, archive, annotation | **Never** train-on-input APIs. |
| **T2** | Public/read — readme, docs, open material | Remote OK with pack; cite sources. |
| **T3** | Irreversible — spend, publish, delete | **Human L3** seal required. |

**Sovereignty guarantees (filed):**

1. Frontier agent runs on **your disk** — not vendor memory throne.  
2. T0/T1 **never** sent to train-on-input remote providers.  
3. Remote seats receive **context-pack + goal** — not full chat history.  
4. Artifacts (residual, trails, export) **survive session death**.  
5. Forkable — no permission required to run your copy.  
6. v5 external stacks (GSTD, Vast, XRPL) are **optional scored seats** — not architecture dependency.

Config: `configs/data_tiers.yaml` · `CONSTITUTION.md` · gate: `tier_refuse` in `configs/releases.yaml`

---

## 7. How versions relate (cross-link map)

```text
COMPASS (this file)     — vision + loop + arc + sovereignty
    ↓
MYCELIAL SCIENCE MAP    — biology ↔ protocol law
    ↓
DIRECTION ARTIFACT v2   — phase gates, v3 entry, v4/v5 mold rules
    ↓
VERSION REGISTRY        — release notes, gates, behavioral trail
    ↓
NEXT CODING RUN         — immediate code order (RUN A–D)
    ↓
v3 BACKLOG / v4 THEORY / v5 PIPE — depth by version
```

| Need | File |
|------|------|
| Navigation + metaphors | `docs/FRAMEWORK_LOAD.md` |
| Biology ↔ protocol | **`docs/ref/MYCELIAL_SCIENCE_MAP.md`** |
| Future walkthrough (v2→v10) | **`docs/ref/MAG_FUTURE_WALKTHROUGH.md`** |
| Vision (v2→v3 loop factory) | **`docs/ref/MAG_VISION_AUTOMATION.md`** |
| Phase gates (RUN A, factory) | `docs/ref/MAG_DIRECTION_ARTIFACT_v2.md` |
| Loop waste patterns | `docs/ref/MAG_LOOP_DISCIPLINE.md` |
| Behavioral compounding | `docs/ref/MAG_BEHAVIORAL_COMPOUNDING.md` |
| v2 plan | `docs/ref/MAG_v2_PLAN.md` |
| v3 run sheet | `docs/ref/MAG_NEXT_CODING_RUN.md` |
| Release gates | `docs/ref/releases/VERSION_REGISTRY.md` |
| Machine arc | `configs/version_roadmap.yaml` |

---

## 8. Amend protocol

| Trigger | Action |
|---------|--------|
| RUN A green | Update §4 built state; bump `as-of` |
| New version gate passed | `release record` + update VERSION_REGISTRY |
| Loop discipline lesson | Cross-link MAG_LOOP_DISCIPLINE; do not duplicate |
| v6–v10 curriculum defined | Update version_roadmap.yaml + registry — still no fake dates |
| Major operator session | One paragraph delta in §4 — not full rewrite |

**Do not:** claim shipped without gate artifact · add calendar predictions · let chat supersede this file.

---

## 9. Closing

The Mycelial Republic is not a product launch date. It is **law and loops on your disk** — agents that coordinate through files, raise problems up and plans down, and compound behavior until the loop can build the next version itself. v1–v2 were hand-built. v3–v10 are the curriculum for the loop to learn how. Read the compass, run the gate, file the episode.

---

*Compass v1 — update at phase gates; parent: mag-mycelial-republic-compass-001*
