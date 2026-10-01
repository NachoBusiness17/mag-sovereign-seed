# ILAP proposal — Beta 1 definition from Verkle history + gates

**Commitment:** ilap-beta1-definition-001  
**Version arc:** v3 (gate bundle) · service_milestones 1–4  
**Status:** draft  
**Parent protocol:** `docs/ref/MAG_ILAP_PROTOCOL.md`

---

## One line

Define **Beta 1** — the first Mag milestone a friend can clone, run doctor green, and get honest work filed without operator babysitting — from 90 filed Verkle leaves + release gates, not v6–v10 curriculum fantasy.

---

## Invariant

If we ship "Beta" before RUN A + desk trust Tier 1 + one factory audit JSON, we sell theater: autorun blocked, plan replays without drain, slow→fast untrusted. Alpha honesty collapses into support debt.

---

## Beta 1 user promise (target)

> Clone → `mag.cmd doctor` green → Office `:8765` works offline with local janitor → queue one goal → get a filed result with Verkle proof → one factory build audited on disk — without re-explaining Mag in chat.

**Maps to:** `configs/version_roadmap.yaml` → `service_milestones` orders 1–4 only.

---

## Gate checklist (evidence-based)

| Gate | Source | Verify | Status |
|------|--------|--------|--------|
| install | service_milestones.1 | `mag.cmd doctor`, `scripts/routing_smoke.py` | TBD |
| offline_desk | service_milestones.2 | `main.py lab`, L0 ask/brief | TBD |
| handoff_loop | service_milestones.3 | handoff → results → `main.py ingest` | TBD |
| factory_pilot | service_milestones.4 + v3 | first `build_audit.v1` JSON pass | **PASS** — gate recorded 2026-08-05 |
| run_a | v2.gates | PRs #8–#11 merged; unified router/FKB/autorun | **PASS** — ancestry + ritual recorded 2026-08-06 |
| desk_trust_t1 | desk ladder | `scripts/desk_baseline_probe.py` 3× green | PROCESS PASS — simulated Local 3× 12/12; real Local hardware lane TBD |
| verkle_honest | verkle_tip | `n_leaves ≥ 20`, `verkle-audit --dry` clean | **90 leaves ✓** |
| tier_refuse | v2.gates | T0/T1 never hit remote | **PASS** — fail-closed provider, gateway, switchboard, and agent tests recorded 2026-08-06 |

**Live Verkle tip (2026-08-05):** root `12da4110…`, `n_leaves=90`, last session `mag-agent-desk-deepseek`.

---

## SHIPS at Beta 1 vs stays internal

| SHIPS | INTERNAL |
|-------|----------|
| Office core four: Ideas, Days, Desk, Stack | Fleet, Body, Shell theater |
| Handoff v1 round-trip | Unmanned autorun (trust Tier 3+) |
| Context-pack + tier law T0–T3 | L-conductor trained weights |
| Days bead + Verkle lattice viewer | v5 GSTD/Vast/XRPL seats |
| Switchboard route (operator-initiated) | Spider proactive steer |
| Cost visible on desk | v6–v10 curriculum |
| ILAP research ritual (manual) | Auto ILAP CLI |
| Arena probe as routing calibration | Arena as product |

---

## Concepts to research (P1)

| # | Concept | Sources | Mag slot | Steal or skip? |
|---|---------|---------|----------|----------------|
| 1 | Beta vs alpha graduation | `MAG_BEHAVIORAL_COMPOUNDING.md`, releases.yaml | release registry | wire |
| 2 | Verkle theme timeline | `verkle_chain.jsonl`, last 20 knots | nervous glance | wire |
| 3 | Desk trust blockers | `agent_desk_trust_ladder.md`, baseline probe | desk_conductor + local_adapter | extend |
| 4 | Factory audit shape | `MAG_FACTORY_PILOT.md` | factory + build_audit.v1 | new-build (bounded) |
| 5 | Cost counterfactual | `mag/token_economy.py`, economy.jsonl | desk economy panel | wire |

---

## Scout plan (P1 — cheap agent seat: local janitor)

```powershell
python main.py context-pack --mode janitor
python main.py improve --once
python main.py verkle-audit --dry --json
python main.py nervous --json
python main.py release status
python main.py training-events --stats
python main.py arena league
```

**Required leaves:**

- [ ] `memory/research_packs/beta1-scope/REPORT.md` — gate table + Verkle stats + theme timeline
- [ ] `research_dive` event in `memory/training/events.jsonl`
- [ ] Overlap table filled (below)

**Load order:**

1. `docs/FRAMEWORK_LOAD.md`
2. `configs/version_roadmap.yaml`
3. `configs/releases.yaml`
4. `docs/ref/memory_verkle_map.md`
5. `memory/biography/verkle_tip.json`

---

## Routing matrix (P2)

| # | Frozen goal | Expected seat | Expected phase | Expected pack_mode | Actual | Match? |
|---|-------------|---------------|----------------|-------------------|--------|--------|
| 1 | `doctor health status` | local | execute | janitor | | |
| 2 | `define beta 1 scope from verkle history` | local | plan | janitor | | |
| 3 | `implement factory audit json` | deepseek | build | build | | |
| 4 | `desk baseline trust probe` | local | execute | janitor | | |
| 5 | `fast canvas handoff` | local | execute | janitor | | |

**Pass criteria:** ≥90% match · `scripts/routing_smoke.py` exit 0 · arena routing hint consulted for seat 5.

---

## Overlap results (P1 → P2)

| Scout finding | Existing module | Overlap % | Decision |
|---------------|-----------------|-----------|----------|
| Service milestones 1–4 | version_roadmap.yaml | 95% | wire — do not redefine |
| Verkle 90 leaves | verkle_tip + chain | 100% | wire — cite, don't rebuild |
| Arena routing | arena_learning + switchboard | 80% | wire — calibration only |
| Factory pilot | MAG_FACTORY_PILOT.md (draft) | 40% | new-build bounded |
| ILAP automation | protocol manual v1 | 60% | defer auto CLI |

---

## Eval case (P3)

**Pattern:** `ilap_cycle`  
**Eval id:** eval-ilap-beta1-001  
**Join keys:** `build_slug=beta1-scope`, `commitment=ilap-beta1-definition-001`

**Reject criteria:**

- Scope creep into v6–v10 or GSTD join (milestone 5+)
- Beta claim without gate table pass/fail sourced from files
- BUILD without frozen BUILD handoff

---

## Estimation method (use Mag, not gut)

1. `python main.py switchboard route "<gate task>"` → seat + tier
2. `python main.py arena routing --budget low --task structured_handoff`
3. Match goal to `configs/training_patterns.yaml` waste_kind — plan_theater/verkle_fanout = HIGH rework
4. If desk tier 0, add operator spot-check to every fast-seat task
5. Record `estimate_miss` when actual >> route estimate

---

## Outcome decision (P3 — human L3)

- [ ] **BUILD** — `queue/handoff/BUILD-beta1-research.md` (factory audit + trust fixes only)
- [ ] **WIRE** — connect existing modules; no new epic
- [ ] **DEFER** — v5+ seats, auto ILAP CLI
- [ ] **REJECT** — scope is v9 service packaging prematurely

**Signed:** __________ **Date:** __________

---

## If BUILD: scope cap

| Field | Value |
|-------|-------|
| Max files | 10 |
| Max frontier seat $ | cost-sim before DeepSeek |
| Forbidden | .env, verkle_tip mutation, foreign prompt DNA |
| Branch | `cursor/beta1-research-e2ce` |
