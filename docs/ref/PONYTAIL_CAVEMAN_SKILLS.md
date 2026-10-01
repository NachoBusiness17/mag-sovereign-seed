# Ponytail & Caveman — agent skills + decision-maker training

**Commitment:** `ponytail-caveman-skills-001`  
**As-of:** 2026-08-05  
**Status:** Shipped as Mag skills — weave + CLI + conductor hook  
**Parents:** `PONYTAIL_CAVEMAN_AUDIT.md` · `configs/skills.yaml` · `MAG_TRAINING_DATA_SPEC.md`

**One breath:** **Ponytail** = coding agent skill (minimum code, safety kept). **Caveman** = plan/doc agent skill (terse specs). Both run as seats, inject into pack, gate with audits, label training for conductor.

---

## 1. Two skills, two jobs

| Skill | Agent type | Domain | Gate command |
|-------|------------|--------|--------------|
| **ponytail** | JONES-BUILD, JONES-AUDIT | Python/code diffs | `python main.py ponytail-audit` |
| **caveman** | JONES-PLAN | BUILD specs, handoffs, docs | `python main.py caveman-audit` |

**Not the same:** caveman cuts words; ponytail cuts unnecessary code. Benchmark: ponytail -54% LOC; caveman -20% LOC but +7% tokens on some tasks — use each on the right artifact.

---

## 2. Weave files (skill body)

| Skill | Path |
|-------|------|
| ponytail-ladder | `docs/ref/weaves/W8-ponytail-ladder.md` |
| caveman-prose | `docs/ref/weaves/W9-caveman-prose.md` |

Registered in `configs/skills.yaml` — auto-injected into `context-pack` when job matches (`hard_code`, `plan`, `audit`).

---

## 3. Run as coding agents

### 3.1 Attach skill to any seat

```powershell
# Pick skill from goal text
python main.py skill-seat pick "implement factory audit json writer"
# → skill: ponytail

python main.py skill-seat pick "[priority] plan BUILD spec for mobile voice"
# → skill: caveman

# Print full preamble — paste above goal in DeepSeek/Cursor/Grok
python main.py skill-seat preamble --skill ponytail "fix router test"
python main.py skill-seat preamble --skill caveman "write BUILD spec"
```

### 3.2 Jones fleet mapping

| Role | Skill | After session |
|------|-------|---------------|
| JONES-PLAN | **caveman** | `caveman-audit` on spec path |
| JONES-BUILD | **ponytail** | `ponytail-audit` + pytest |
| JONES-AUDIT | **ponytail** | both audits on touched paths |

### 3.3 Factory pipeline

```text
PLAN seat   → caveman preamble → BUILD-TEMPLATE output → caveman-audit
BUILD seat  → ponytail preamble → code → ponytail-audit
AUDIT seat  → ponytail gate → verdict JSON
```

---

## 4. Conductor / decision-maker integration

`python main.py conductor "goal"` now returns:

```text
overlay.skill_seat: ponytail | caveman
```

**Heuristic:** code markers → ponytail; plan/spec markers → caveman.

**Future L-conductor train labels:**

| Signal | Label |
|--------|-------|
| ponytail-audit pass after build | `delegation_success` + `ponytail_pass` |
| ponytail-audit fail | `ponytail_fail` → route smaller diff or janitor first |
| caveman-audit pass on spec | `caveman_pass` → safe to freeze BUILD |
| caveman-audit fail on spec | `caveman_fail` → re-plan seat, not build |

Emit via `training_events` when gates run:

```powershell
python main.py skill-seat gate --skill ponytail
python main.py skill-seat gate --skill caveman --path docs/ref/BUILD-foo.md
```

---

## 5. Training package (conductor + spider)

Add to export JSONL (`MAG_TRAINING_DATA_SPEC.md`):

```json
{
  "pattern": "skill_gate",
  "input": { "goal": "…", "skill_seat": "ponytail" },
  "outcome": { "pass": true, "findings_n": 0 },
  "pattern_tags": ["ponytail_pass", "factory_build"]
}
```

**Decision-maker learns:**

- Plan goals → caveman seat → freeze spec before build  
- Code goals → ponytail seat → audit before merge  
- Fail ponytail after DeepSeek → escalate to audit or shrink scope, not re-build blind  

---

## 6. Grove / layman

| Skill | Grove node kind | Poem example |
|-------|-----------------|--------------|
| ponytail | tesuji | *"Need exist? Reuse stdlib. Ship."* |
| caveman | skill | *"One line. Checkboxes. No essay."* |

`grove-build` picks up weaves W8/W9 when promoted.

---

## 7. Commands cheat sheet

```powershell
python main.py skill-seat status
python main.py skill-seat pick "your goal"
python main.py skill-seat preamble --skill ponytail "goal"
python main.py ponytail-audit
python main.py caveman-audit
python main.py caveman-audit --path queue/handoff/BUILD-slug.md
python main.py skill-seat gate --skill ponytail
python main.py conductor "audit only diff review"   # skill_seat in overlay
```

---

## 8. What we will not cut (both skills)

- G1–G4 gates · tiers · FKB · residual · container law  
- Security / irreversible prose (caveman exempts G3 lines from trim hints)  
- Tests that prove tier refuse  

---

*End ponytail/caveman skills — pair with JONES_AGENT_FLEET_PACK.md.*
