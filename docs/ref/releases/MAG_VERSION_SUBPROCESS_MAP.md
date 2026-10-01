# Mag versions — subprocess map (refined)

**Commitment:** `mag-version-subprocess-001`  
**Job:** Refine v1–v5 using **Mag's own subprocess grammar** — not generic semver. Versions are **runs with trails**, not marketing labels.  
**Parents:** `loops_registry.py` · `modules.yaml` · `run_trail.py` · `FEATURE_COMPOSE.md` · `VERSION_REGISTRY.md`

**Honesty:** This map steals from **what Mag already does** internally. If a version claim doesn't have a trail analog, it's theater.

---

## 0. Core steal

> **A product version = a long-running Mag run** with a frozen spec, subprocess spawns, terminal gates, and a residual leaf (release notes).

```text
Version arc     ≈  mag_run.v1  (one trajectory, seat purity)
Graduation gate ≈  factory audit + promote --apply
Witness post    ≈  bond edge (public → private soil)
Release notes   ≈  session_card + residual blurb
v1 Grok origin  ≈  remote seat before run_trail existed
v2 repo home    ≈  cold_vertex + modules.yaml (DNA store)
v3 planning     ≈  active run (open trajectory)
```

---

## 1. Version ↔ subprocess matrix

| Ver | Operator meaning | Mag subprocess analog | Layer | Loop (internal) | Trail / artifact |
|-----|------------------|----------------------|-------|-----------------|------------------|
| **v1** | Grok spawned project | **Remote activation seat** (strike → pack, no disk run) | viewport | strike-chord → LOAD | `strike_origin.md`, X witness |
| **v2** | Repo in `projects/` | **residual_dna + modules** — cold vertex + upgrade contracts | cold / harness | SessionEnd → registry | `memory/`, `configs/modules.yaml` |
| **v3** | Planned build | **orchestrator run** — spawn, queue, drain, task_lifecycle | warm_mid | fill → route → execute | `governor_autorun_trail.jsonl`, BUILD specs |
| **v4** | Mold | **factory + conductor** — plan→freeze→audit; eval before volume | harness | scout → eval → promote | `conductor_trail`, `training_patterns.yaml` |
| **v5** | Forest pipe | **switchboard peers** — optional L1-cap seats, not DNA | meta | mesh → route → steer_drop | `seat_playbook.yaml`, spore catalog |

**Law (from modules.yaml):** Versions are **edges** on the cold vertex — never a second DNA store.

---

## 2. Subprocesses that compose the version story

Each internal loop **feeds** version graduation the same way it feeds Mag daily ops:

| Loop | Status | Teaches versions |
|------|--------|------------------|
| **improve** | shipped | Backlog + candidates → what v3/v4 items promote |
| **autorun** | shipped | v3 = honest drain; plan theater blocks graduation |
| **orchestrator** | shipped | Subprocess spawn = coding runs; `task_lifecycle` labels |
| **fkb** | shipped | Failed patterns → don't repeat in next version RUN |
| **loop_audit** | shipped | Plan theater detection → v4 eval case 1 |
| **verkle** | shipped | History honesty → release notes amend protocol |
| **factory** | pilot | **v3 graduation shape** — plan→freeze→build→audit |
| **training_events** | research | `release_milestone` + `route_decision` → behavioral memory |
| **steward** | pilot | Spore catalog, train-prep → v5 curriculum |
| **switchboard** | research | v5 seats as peers, not architecture |
| **releases** | shipped | Version gates JSONL + notes on disk |

```powershell
python main.py v3-status          # loops registry
python main.py release status --map   # version subprocess view
```

---

## 3. v1–v3 refined (operator + system)

### v1 = pre-run activation (Grok subprocess)

| Internal | v1 expression |
|----------|---------------|
| `dispatch` / Grok TUI | Strike chord, sovereign mirror |
| No `run_trail` yet | Chat heat only — no `mag_run.v1` |
| `context_pack` ancestor | Activation paste, public grammar |
| **Witness** | Bonds from X → later soil (`WITNESS_SPINE.md`) |

**Feature compose steal:** v1's key feature = *activation reloads full fidelity mode* → v2 files that as pack-first + residual.

### v2 = DNA subprocess (repo home)

| Internal | v2 expression |
|----------|---------------|
| `residual_dna` | SessionEnd, beads, Verkle tip |
| `modules.yaml` | Upgrade contracts — v2 modules don't break cold vertex |
| `nervous_system` | Body glance — "is Mag alive?" |
| `context_pack` | Brief envelope for any seat |
| `improve` + `promote` | Human gate on habit changes |
| Office :8765 | Viewport — artifact > visualization |

**Graduation subprocess:** v2.x gates (`run_a`) = **tier refuse tests + router smoke** — same as module upgrade verification in `modules.yaml`.

### v3 = active run subprocess (planning → build)

| Internal | v3 expression |
|----------|---------------|
| `orchestrator.spawn_task` | DeepSeek / cloud agent coding runs |
| `governor_autorun` | Fill queue from improve + steward |
| `conductor` (research) | Phase overlay: plan \| build \| audit |
| `skill_seat` | Ponytail/caveman on spawn |
| `factory` (pilot) | RUN B — first audit JSON = **terminal event** |
| Chat (viewport) | Cursor-like preflight — subprocess status strip |

**Terminal rule (from orchestrator):** v3 not "shipped" until **one leaf outcome** per RUN — knot, test green, or audit JSON.

---

## 4. Graduation = factory subprocess

Map each version gate to factory phases:

| Phase | Factory | Version gate example |
|-------|---------|-------------------|
| Plan | Grok/caveman BUILD spec | v3 direction docs |
| Freeze | L3 `Status: frozen` | BUILD handoff on disk |
| Build | DeepSeek/orchestrator spawn | RUN C, PR merge |
| Audit | Cursor ponytail + pytest | `run_a`, `factory_pilot` |
| Promote | Human `promote --apply` | Update release notes + `release record` |

```text
v3 ship  =  factory audit pass  +  release record gates  +  RELEASE_NOTES_v3 amended
v4 ship  =  conductor eval 1–4 green  +  steward daily trail
v5 ship  =  probe gates per track (GSTD/Vast/XRPL) — read-only first
```

---

## 5. Behavioral memory subprocess chain

Same stack as `MAG_BEHAVIORAL_COMPOUNDING.md`, applied to versions:

```text
L1 FILE     release notes + gates.jsonl + witness spine
L2 SCORE    release_milestone training events + improve scout reads gates
L3 PROMOTE  RUN row / template clause when gate cluster repeats
L4 TALK     Grove poem / Office one-liner ("v3: factory audit pass")
```

**Inspiration from subprocesses:**

| Source subprocess | Version behavior |
|-------------------|------------------|
| `agent_state` tip | Latest release notes = LATEST; history in git commits |
| `bonds_active` | Witness posts = carry edges to next session |
| `resonance` (research) | Resurrect deferred backlog when soil rhymes |
| `behavioral_synth` | Weekly theme from gates + decisions_log |
| `decision_framework` | Escalate when same gate fails 3× |

---

## 6. Witness = bond subprocess

Public X posts are **not** residual DNA. They are **bonds** — activation edges:

| Field | Mag analog |
|-------|------------|
| Post URL | `bonds` / ingest registry row |
| v1 napkin | `parent_id: none` framework root |
| Toward v3 post | `related_runs` edge to active v3 run |
| Ingest via research-pack | `mine/staging` → `memory/ingest/` |

**Tier law:** Witness text = T2 public. Never T0/T1 operator soil in pack.

---

## 7. What to build next (inspired by subprocesses)

| Build | Steals from | Delivers |
|-------|-------------|----------|
| `release status --map` | `loops_registry.format_registry_text` | Version × subprocess table in CLI |
| `steward-release-digest` | steward-patterns | Weekly gate summary → improve candidate |
| Release row in `v3-status` | loops_registry | One glance: loops + versions |
| `RELEASE_NOTES_vN` amend | `agent_state` amend | New leaf, don't erase history |
| Conductor `run_proposal` | autorun fill | Suggest next gate from failed audits |

---

## 8. Anti-patterns (from FKB / loop_audit)

| Theater | Subprocess says |
|---------|-----------------|
| "v3 shipped" with no audit JSON | factory terminal missing |
| Version without release notes path | no session_card |
| Gate recorded without verify command | plan theater |
| Witness post pasted into DNA | tier violation |
| v5 implement before v4 eval | seat thrash mid-run |

---

## 9. One paragraph

**v1** was Grok's activation subprocess before Mag had a run trail. **v2** is the cold vertex and module registry in your projects folder. **v3** is the open orchestrator run we're executing — factory-shaped, spawn-heavy, Chat viewport. **v4** and **v5** follow the same grammar as conductor and switchboard: eval and optional peers, not new thrones. Refine versions the way Mag refines everything else: **trail, terminal gate, promote, FILE.**

---

*Load with: [VERSION_REGISTRY.md](VERSION_REGISTRY.md) · [WITNESS_SPINE.md](WITNESS_SPINE.md) · `python main.py release status --map`*
