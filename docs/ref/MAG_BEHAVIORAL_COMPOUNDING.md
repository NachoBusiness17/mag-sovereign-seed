# Mag — Behavioral compounding (v4/v5 meta-loop)

**Commitment:** `mag-behavioral-compounding-001`  
**As-of:** 2026-08-05  
**Status:** Theory + partial implementation — how process becomes product  
**Parents:** `DNA.md` · `MAG_TRAINING_DATA_SPEC.md` · `MAG_v4_THEORY.md` · `DECISION_LAYERS.md`

**Read when:** asking *what are we learning behaviorally?* · *how do RUN steps auto-emerge?* · *how do deprecated patterns come back?*

---

## 1. What we're learning (behaviorally)

Not "models got smarter." **The harness learned what to repeat.**

| Behavior observed (v2→v3) | Lesson filed | Where it lives |
|---------------------------|--------------|----------------|
| Same goal spawned 8× | Dedupe + orphan reap | orchestrator, switchboard |
| Autorun plan theater 100+× | Fingerprint trail + loop-audit | `MAG_LOOP_DISCIPLINE.md`, loop_audit |
| Grok used for scut | Janitor-first routing | `route.v2`, seat economics |
| Chat as handoff | Freeze BUILD spec on disk | factory pipeline |
| Planner coded anyway | Phase detection + caveman gate | conductor, skill-seat |
| Audit became feature creep | ponytail audit + audit-only seat | Jones AUDIT |
| Agent forgot env | context-pack + FRAMEWORK_LOAD order | pack L0 |
| Failed pattern repeated | FKB signature → remedy card | failure_kb |
| Good routing forgotten | training_events `route_decision` | events.jsonl |
| "We should do X next" lost | RUN A–D manual sheet | MAG_NEXT_CODING_RUN.md |
| Idea deprecated too early | Backlog scored, not deleted | MAG_v3_BACKLOG.md |
| Version shipped claimed without gate | Release registry + `release_milestone` | `configs/releases.yaml`, `release record` |

**Meta-lesson:** Constitution thinking beats roadmap guessing. You don't predict v5 — you **file episodes**, **score patterns**, **promote** what compounds, **defer** what doesn't — and let **resonance** surface old ideas when soil rhymes. **Version gates** are episodes too — `python main.py release record`.

```text
Behavior = what happened
Lesson   = labeled episode on disk
Habit    = promoted loop or RUN step
Law      = constitution / BUILD template change
```

---

## 2. The compounding stack (four layers)

```text
┌─────────────────────────────────────────────────────────────┐
│  L4  TALK     — Grove poems, Office cards, operator brief      │
├─────────────────────────────────────────────────────────────┤
│  L3  STEPS    — RUN sheets, factory pilot, conductor phase   │
├─────────────────────────────────────────────────────────────┤
│  L2  SCORE    — training events, FKB, improve candidates     │
├─────────────────────────────────────────────────────────────┤
│  L1  FILE     — trails, residuals, decisions_log, backlog    │
└─────────────────────────────────────────────────────────────┘
```

**Rule:** Nothing jumps L1→L4 without L2. No poem without a trail. No auto-RUN without scored episodes.

---

## 3. How steps auto-create (v4 → v5)

Today RUN A–D is **manual** (`MAG_NEXT_CODING_RUN.md`). v4/v5 goal: **conductor proposes next RUN from trails** — human still signs L3.

### 3.1 Episode → pattern (already partial)

Every loop emits `mag_training_event.v1`:

| Pattern | Teaches |
|---------|---------|
| `route_decision` | seat economics |
| `task_lifecycle` | spawn/reap/orphan |
| `steer_outcome` | did steer help? |
| `factory_cycle` | plan→build→audit chain |
| `spider_signal` | stall/orphan/autorun burst |
| `promote_gate` | human approved habit |
| `release_milestone` | version graduation gate recorded |
| `tesuji_shell` | emergent win / brilliant move filed by operator or seat |

**v4 add:** `run_proposal` — conductor outputs suggested next RUN row + confidence + evidence links.

### 3.2 Pattern clustering → candidate step

```text
N similar episodes (same signature, same outcome)
  → improve scout proposes "candidate step"
  → eval: would this step have prevented FKB repeats?
  → human promote --apply c-...
  → becomes: RUN row | factory template clause | conductor phase rule
```

**Not auto-promote.** Same gate as config changes (`max_auto_pull_gb: 0`).

### 3.3 Step types that can auto-emerge

| Emerges as | Trigger signal |
|------------|----------------|
| New RUN row | 3+ sessions ended with same manual checklist |
| Factory template clause | 2+ audit fails same reason |
| Conductor phase marker | route_decision cluster on goal tokens |
| Spider rule | stall_outcome negative after no steer |
| Skill weave update | skill_gate fail cluster |
| Backlog resurrection | resonance score spike on deferred v3-NNN |

### 3.4 v5 sketch: procedural constitution

```text
episodes.jsonl + decisions_log + FKB
  → weekly behavioral_synth theme
  → conductor drafts "amendment" (markdown diff to RUN sheet or BUILD template)
  → operator Saturday ritual: accept | reject | defer
  → accepted → grove poem + loops_registry status bump
```

**Automatic creation = draft + score + promote.** Never silent rewrite of law.

---

## 4. Surfacing — how we talk about steps

Deposited learning is useless if only grep finds it.

| Surface | Audience | Content |
|---------|----------|---------|
| **Release notes** | Operator + agents | `docs/ref/releases/RELEASE_NOTES_vN.md` |
| **Version registry** | Router / conductor | `configs/releases.yaml` + `release status` |
| **Gate log** | Behavioral synth | `memory/improve/releases/gates.jsonl` |
| **Office :8765** | Layman | "Last night: RUN B step 3 done · next: audit" |
| **context-pack L0** | Remote seats | bonds + nervous + next RUN one-liner |
| **Grove poems** | Human browse | factory shift / curious error / revived pattern |
| **resonance L0e** | Active goal | "soil rhymes with v3-010 riddle packs" |
| **v3-status** | Agent boot | loop health + trail exists? |
| **switchboard status** | Live ops | peers + orphans |
| **briefs/latest.md** | Daily | operator narrative |
| **decisions_log** | Case law | "we chose X because Y" |

### v4 Office sentence (target)

> *"Mag OK · last factory: audit pass · next RUN: C4 freeze gate · grove: Spec frozen, contractor built."*

### v4 agent sentence (target)

> Conductor returns: `{ "next_run": "C4", "evidence": ["evt-abc", "fkb:E21"], "confidence": 0.72 }`

---

## 5. Resurrection — deprecated patterns that return

**Problem:** Backlog items, old RUN rows, and abandoned approaches get **buried**, then become right again when context shifts.

**Mag answer:** never delete — **score, defer, resurface**.

### 5.1 Deprecation record (proposed schema)

```yaml
# memory/improve/deprecation_registry.yaml (v4)
- id: dep-lattice-loop-external
  what: lattice-loop sovereign mirror scaffold
  deprecated: 2026-08-03
  reason: external dep not in container
  resurrection_triggers:
    - container has mycelial-republic mount
    - operator explicit ask
  usefulness_at_deprecation: 2
  alignment: 4
  linked_backlog: null
```

### 5.2 Resurrection pipeline

```text
goal or autorun fill
  → resonance scores backlog + deprecation_registry + grove
  → if deferred item scores > threshold AND triggers match:
       emit spider_signal kind=resurrection_candidate
       conductor overlay: "v3-010 riddle packs — deferred; soil now matches router+v2"
  → human L3: revive | snooze 90d | reject permanently
```

**"Once thought deprecated"** = usefulness was low **in context**, not wrong forever.

Examples from this project:

| Was deprecated | Why then | Might return when |
|----------------|----------|-------------------|
| Hermes as default python | wrong venv / deps | never as default; maybe as optional seat |
| lattice-loop external mirror | container gap | workstation profile ships |
| Full Verkle physics | non-goal | never product; keep as research pin |
| Riddle packs (v3-010) | no router honesty yet | after #8 merge + spore guard |
| Chat handoff | token bleed | never; factory freeze replaces it |
| Parallel worktrees | not built | v5 when factory pilot #3 passes |

### 5.3 Retrocausal reinterpretation (DNA law)

From `configs/modules.yaml`: *"Future summarize reinterprets day; tip root recomputes."*

Same episode, new lens:

- Saturday verkle-audit re-reads week → new gap goals
- behavioral_synth re-themes failures → FKB remedy promoted
- Grove poem links old audit fail to **current** BUILD spec

**Resurrection is retrocausal safety:** old files gain meaning when the lattice matures — not because the model "remembered."

---

## 6. Version behavior map

| Version | Behavioral learning |
|---------|---------------------|
| **v2** | File failures (FKB), route honestly, human promote |
| **v3** | Label orchestration episodes; mesh + steer; manual RUN sheet |
| **v4** | Factory cycles FILE audit JSON; conductor **proposes** next RUN; grove factory nodes |
| **v5** | Promoted steps draft constitution amendments; deprecation registry + resurrection; optional conductor weights |

```text
v2: learn from mistakes
v3: learn from routing + steering
v4: learn from factory outcomes
v5: learn which lessons become law
```

---

## 7. What to build next (ties to MAG_NEXT_CODING_RUN)

| Item | Enables |
|------|---------|
| C1 training hooks on autorun/orchestrator | richer episodes for auto-RUN |
| RUN B factory-audit-json | first `factory_cycle` training chain |
| `deprecation_registry.yaml` + resonance hook | resurrection candidates |
| Conductor `next_run` field (research) | surface steps to agents |
| `growth-cycle run` (`mag/growth_cycle.py`) | explicit three-body loop: probe → behavioral synth → scout/candidates → improve cycle → `three_body_episode` + human report |
| Grove factory-shift node kind | human talk layer |
| Saturday ritual: review resurrection candidates | talk + L3 gate |

---

## 8. Anti-patterns (do not automate)

- Auto-promote without human gate  
- Delete backlog items (defer + score instead)  
- Train on chat scroll as label  
- Resurrect without trigger match (nostalgia ≠ signal)  
- v5 roadmap dates pretending alpha is beta  

---

## 9. One paragraph for your LLM

> Mag learns behaviorally by **filing episodes** (trails, training events, FKB, factory audits), **scoring patterns** (improve scout, resonance, conductor), and **promoting habits** (RUN steps, template clauses, grove poems) through **human L3 gates**. Deprecated ideas stay in registry with resurrection triggers — resonance surfaces them when soil rhymes. v4 auto-**drafts** next steps; v5 auto-**amends** procedure — neither silently rewrites law. Talk happens via Office, pack, grove, and brief — not chat scroll.

---

## 10. Tesuji shells — emergent wins (symmetric path)

**Errors** flow: `logs/behavioral_events.jsonl` → `*-behavioral.md` → scout `kind=risk`.  
**Wins** flow: `logs/tesuji_shells.jsonl` → `*-tesuji-shells.md` → scout `kind=tesuji`.

Log when something **surprised you** — a move neither operator nor agent planned that worked:

```powershell
python main.py tesuji-shell log "Peer brief surfaced mesh pattern" ^
  --surprise "emerged from coordination, not plan" ^
  --maps-to skill:mesh-comm
python main.py tesuji-shell synth
python main.py tesuji-shell status
```

| Artifact | Role |
|----------|------|
| `logs/tesuji_shells.jsonl` | append-only episodes |
| `memory/improve/daily/{date}-tesuji-shells.md` | daily leaf (W1..Wn) |
| `memory/training/events.jsonl` | `pattern=tesuji_shell` |
| context-pack L0 | `[TESUJI SHELLS — emergent wins to repeat]` when behavioral pack inject on |

**maps_to** prefixes: `remedy:ID`, `skill:id`, `tesuji:path` — weekly roll-up clusters repeats (stub in leaf; promote when ≥3×).

Python: `from mag.tesuji_shell import log_tesuji_shell`

---

## 11. Run worth — long runs before bad classification

**Errors** assume failure; **worth gate** assumes *we do not know yet* when a run is long.

| Artifact | Role |
|----------|------|
| `mag/run_worth.py` | score + classify + gate_before_truncate |
| `logs/run_worth.jsonl` | defer/block/hung decisions |
| `logs/run_worth_overrides.jsonl` | operator `mark-good` (long run was valuable) |
| `configs/improve.yaml` → `run_worth` | thresholds |

Integration: `run_trail.append_event` (max_tool_calls), `orchestrator` stall kill (hung vs defer).

```powershell
python main.py run-worth evaluate 20260805T120000Z-my-run-abc123
python main.py run-worth mark-good RUN_ID --note "early DeepSeek improvement"
```

---

*Link from HANDOFF when a RUN graduates to promoted habit or a backlog item resurrects.*
