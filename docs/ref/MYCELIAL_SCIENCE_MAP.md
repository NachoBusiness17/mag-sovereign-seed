# Mycelial science map — biology ↔ Mag protocol

**Commitment:** `mag-mycelial-science-map-001`  
**As-of:** 2026-08-05  
**Status:** Reference law — load with compass  
**Job:** Tie real fungal network science to Mag seats, REST handoffs, and republic architecture — not decoration  
**Honesty:** Levels 1–2 are protocol design today. Level 3 (bio-hybrid substrate) is research pipe only — not shipped.

**Parent:** [`MAG_MYCELIAL_REPUBLIC_COMPASS.md`](MAG_MYCELIAL_REPUBLIC_COMPASS.md)  
**Machine arc:** `configs/version_roadmap.yaml`  
**Spore catalog:** `docs/ref/spores/mesh/`

---

## 0. Load order (agents)

Read **after** compass, **before** direction artifact when implementing mesh, GSTD, or training-event taxonomy:

```text
1. docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md
2. docs/ref/MYCELIAL_SCIENCE_MAP.md   ← this file
3. docs/ref/MAG_DIRECTION_ARTIFACT_v2.md
```

**Rule:** Metaphor must map to a file, REST surface, or gate — or it stays in prose, not protocol.

---

## 1. Why mycelium is not a brand name

Fungal mycelium is a **living network** that:

- Explores locally without a central brain
- Transfers resources and signals between peers
- Reinforces successful paths and prunes failed ones
- Disperses spores to colonize new substrate when conditions fit
- Self-repairs when edges break

Mag is building a **REST agent graph** with the same invariants: no throne memory, problems percolate up, plans descend down, artifacts survive node death.

This document names the biology, cites the science, and maps each phenomenon to Mag protocol.

---

## 2. Biology → protocol map

| Biological phenomenon | What science says | Mag protocol | Where in repo |
|----------------------|-------------------|--------------|---------------|
| **Hypha** | Thread-like exploratory filament; tip senses, body transports | One REST hop or one handoff file — single seat action | `handoff.v1`, `POST /api/v1/desk-dialogue`, `queue/handoff/` |
| **Mycelium** | Full network of fused hyphae; no central organ | The seat graph: Grok, Cursor, Ollama, DeepSeek, janitor, scheduler | `configs/version_roadmap.yaml` → `agent_loop` |
| **Wood Wide Web** | Trees trade carbon ↔ nutrients via mycorrhizal fungi; mutualism, not extraction ([Simard, WWF overview](https://www.worldwildlife.org/stories/what-is-a-mycorrhizal-network)) | Device provides local GPU; GSTD forest provides peer inference when enrolled — **optional seat**, not throne | `mag/gstd_probe.py`, v5 pipe |
| **Nutrient flow down** | Host supplies sugars; fungus delivers minerals from soil | Plans, briefs, frozen BUILD specs descend the chain | `memory/briefs/`, desk canvas, `cloud_handoff` |
| **Stress signal up** | Damage, competition, resource lack → chemical/electrical signals toward network | Blockers, questions, deltas only — never full-stack re-reasoning upward | DeepSeek handoff_loop, meta lanes |
| **Electrical spike** | Fungi propagate trains of voltage spikes; memristive dynamics ([Adamatzky et al., 2023](https://doi.org/10.48550/arxiv.2304.10675)) | Timing badge + training event per agent turn | `mag/desk_timing.py`, `memory/training/events.jsonl` |
| **Distributed logic** | Nonlinear signal transform in mycelium implements Boolean gates ([Adamatzky, Schubert, 2021](https://doi.org/10.48550/arxiv.2112.07236)) | Logic emerges from handoff topology, not one model | `handoff_loop`, scheduler triage |
| **Small-world topology** | High clustering + short average path length → efficient routing ([reservoir computing models](https://doi.org/10.1007/s11047-025-10040-x)) | Verkle lattice + Days bead tree + seat registry | `mag/tapestry.py`, `mag/lattice_dashboard.py` |
| **Spore** | Dormant packet; colonizes new substrate when environment fits | Portable protocol doc — Briar, Bitchat, Bridgefy patterns | `docs/ref/spores/mesh/` |
| **Self-repair** | Hyphae regrow around damage; reservoir memory under edge deletion ([bio-hybrid RC framework](https://doi.org/10.5281/zenodo.18865435)) | Desk auto-heal, improve loop, scheduler `!escape` | `mag/desk_dialogue.py`, `mag/improve_loop.py` |
| **Exploration vs exploitation** | Tips probe; network reinforces high-yield paths | Local janitor probes cheap; `route_decision` events reinforce winners | `mag/training_events.py`, `configs/lanes.yaml` |
| **No central brain** | Decisions from local fusion + propagation over network | Collective seat actions percolate to operator / next tier | REST + residual, not shared chat |

---

## 3. Three houses ↔ three substrates

Compass §1 names three houses. Mycelial science gives each a **substrate role**:

| House | Repo locus | Biological analog | Role |
|-------|------------|-------------------|------|
| **Beads** | `local_sovereign_agent` | Rhizosphere around a root — intimate, private | Custody, routing, pack, residual — **your soil** |
| **Forest** | mycelial-republic | Above-ground fruiting + shared law | Public fork, republic train, optional collective |
| **GSTD forest** | gstdcoin (v5) | Mycorrhizal link between separate hosts | Peer nutrient exchange — surplus GPU, not memory export |

**Law:** GSTD is mycorrhiza — symbiosis. Never architecture dependency. T0/T1 never crosses the link.

---

## 4. Agent loop as fungal physiology

```text
                    ┌─ Grok (strategy hypha — scarce, long reach)
                    │
Plans DOWN ────────►├─ Cursor (fruiting body — materializes docs/code on disk)
                    │
                    ├─ Ollama local (exploratory tip — cheap, always on)
                    │
Problems UP ◄───────└─ DeepSeek (network sensor — long context, raises stress signals)
```

| Direction | Biology | Token law |
|-----------|---------|-----------|
| **Down** | Nutrient delivery to exploring tips | Intent narrows: spec → doc → task → instruction |
| **Up** | Stress / damage signals | Blockers only: question, delta, one next move |
| **Lateral** | Hyphal fusion between colonies | REST handoffs between seats — same tier, file surface |
| **Dispersal** | Spore release | Spore docs, fork, new operator clone |

---

## 5. Training events as spikes

`memory/training/events.jsonl` is the republic's **electrical trace** on disk.

### 5.1 Suggested `pattern_tags` (protocol vocabulary)

Use alongside existing patterns (`route_decision`, `release_milestone`, etc.):

| Tag | Meaning | When to emit |
|-----|---------|--------------|
| `hypha_plan_down` | Plan or spec descended one tier | Grok→Cursor, Cursor→local brief |
| `hypha_problem_up` | Blocker or delta ascended | DeepSeek critique, meta lane |
| `spike_timing` | Agent turn completed with elapsed + tokens | Desk timing capture |
| `spore_dispersal` | Portable protocol filed or fork documented | New spore in `docs/ref/spores/` |
| `mycorrhiza_join` | Optional peer seat probed or enrolled | GSTD probe green, edge test |
| `hypha_prune` | Low-value queue dropped or route abandoned | Scheduler `!escape`, improve defer |

**Honesty:** Tags are **recommended vocabulary** — adopt in `emit()` calls as loops mature; not all are wired yet.

### 5.2 Optional fields (future schema extension)

When extending `mag_training_event.v1`:

```yaml
hypha:
  id: "hy-abc123"           # correlates one plan-down + problem-up pair
  direction: plan_down | problem_up | lateral | spore
  from_seat: grok | cursor | ollama | deepseek | scheduler
  to_seat: cursor | ollama | deepseek | operator
```

Do not require these until v6 loop-self-build gate — file episodes first, schema second.

---

## 6. Percolation — how collective action reaches the top

Biology: local chemical fusion + spike propagation → whole-colony behavior without a single command neuron.

Mag:

1. Each seat completes one hypha (one REST turn, one file)
2. Artifacts land on disk (canvas, handoff, training event)
3. Scheduler serializes local GPU — **one spike at a time** on constrained substrate
4. Operator or next tier reads **residual**, not chat scroll
5. `release record` + gate = fruiting — visible outcome of network activity

**Prototype nodes** (Cursor, cloud agents, this chat) are hyphal tips. They do not own the mycelium. They explore, file, and exit.

---

## 7. Competitor landscape (honest positioning)

| Lane | Who else | What they ship | Mag difference |
|------|----------|----------------|----------------|
| Sovereign local agent | [Semblance](https://github.com/skygkruger/semblance-core), [Soma](https://github.com/radotsvetkov/soma) | Air-gapped or auditable **single** agent | Multi-seat REST graph + percolation |
| DePIN inference | Akash, io.net, Render, GSTD | Cheap GPU rental | GPU seat + sovereignty + loop curriculum |
| Agent frameworks | LangGraph, CrewAI, cloud suites | In-process or vendor orchestration | File/residual protocol; T0/T1 refuse |
| Verifiable agents | [Right to History](https://arxiv.org/pdf/2602.20214) (research) | Tamper-evident action logs | Verkle + training events + operator gates |

**Wedge:** sovereign disk + REST seat mesh + problems-up/plans-down + optional DePIN + v1–v10 loop training. Others take slices; Mag files the whole organism.

---

## 8. Implementation levels

### Level 1 — Metaphor with teeth (now · v3–v5)

- Use vocabulary in compass, handoffs, operator docs
- Tag training events with `hypha_*` / `spike_*` where easy
- GSTD probe = mycorrhiza handshake test

**Cost:** documentation discipline only.

### Level 2 — Computational mycelium models (v7–v8)

- Model seat graph as weighted directed graph (nodes = seats, edges = handoff frequency)
- Compute clustering coefficient + path length — compare to small-world targets from fungal RC literature
- Prune edges with zero `release_milestone` compounding; reinforce green routes

**References:** cellular automata + reaction-diffusion mycelium growth ([2025 RC framework](https://doi.org/10.1007/s11047-025-10040-x)); graph metrics on `memory/training/events.jsonl`.

### Level 3 — Bio-hybrid substrate (v10+ · research only)

- Living mycelium as physical reservoir computer ([ERIS-adjacent framework](https://doi.org/10.5281/zenodo.18865435))
- Electrical signaling 100 Hz–10 kHz range; memristors; self-repairing edges

**Law:** File as spore + ILAP proposal. Do not productize. Do not claim in compass §4 built state until wet-lab gate exists.

---

## 9. Key citations (starter bibliography)

| Topic | Reference |
|-------|-----------|
| Fungal logic gates | Adamatzky, Schubert — [Logics in fungal mycelium networks (2021)](https://doi.org/10.48550/arxiv.2112.07236) |
| Electrical signaling | Beattie, Adamatzky et al. — [Propagation of electrical signals by fungi (2023)](https://doi.org/10.48550/arxiv.2304.10675) |
| Reservoir computing on mycelium models | [Mycelium as computational medium (2025)](https://doi.org/10.1007/s11047-025-10040-x) |
| Bio-hybrid RC + self-repair | [Mycelium-mediated RC framework (2025)](https://doi.org/10.5281/zenodo.18865435) |
| Forest nutrient networks | Simard et al. — mycorrhizal network research; [WWF explainer](https://www.worldwildlife.org/stories/what-is-a-mycorrhizal-network) |
| Computational history sovereignty | [Right to History (arxiv 2602.20214)](https://arxiv.org/pdf/2602.20214) |

Add new citations to this table when filing spores — one row per primary source.

---

## 10. Cross-link map

```text
COMPASS           — vision, loop, v1–v10, sovereignty
    ↓
MYCELIAL SCIENCE  — this file (biology ↔ protocol)
    ↓
DIRECTION v2      — phase gates, v3–v5 mold
    ↓
spores/mesh/      — dispersal packets (Briar, Bitchat, …)
    ↓
gstd_probe        — mycorrhiza enrollment test
```

| Need | File |
|------|------|
| Vision + loop | `docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md` |
| Mesh spores | `docs/ref/spores/mesh/README.md` |
| Loop discipline | `docs/ref/MAG_LOOP_DISCIPLINE.md` |
| Training spec | `docs/ref/MAG_TRAINING_DATA_SPEC.md` (if present) |
| Version arc | `configs/version_roadmap.yaml` |

---

## 11. Amend protocol

| Trigger | Action |
|---------|--------|
| New spore filed | Add row to §2 if biology analog is new |
| GSTD edge test passed | Update §3 GSTD row; emit `mycorrhiza_join` |
| v8 mesh gate | Add §8 Level 2 metrics + graph script path |
| Wet-lab / bio-hybrid milestone | Level 3 row only with gate artifact — never ahead of evidence |

**Do not:** claim living mycelium compute is shipped · use biology to bypass tier law · send T0/T1 to peer network.

---

*Science map v1 — parent: mag-mycelial-science-map-001 · compass sibling*
