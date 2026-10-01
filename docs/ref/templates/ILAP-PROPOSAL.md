# ILAP proposal — {title}

**Commitment:** ilap-{slug}-001  
**Version arc:** v2 | v3 | v4 | v5 | epic-{name}  
**Status:** draft | research | aimed | frozen | rejected  
**Parent protocol:** `docs/ref/MAG_ILAP_PROTOCOL.md`

---

## One line

{What we need to learn or prove before coding — one sentence.}

---

## Invariant

{What fails if we skip research and build anyway?}

---

## Concepts to research (P1)

List foreign signals and Mag overlap hypotheses:

| # | Concept | Sources to scout | Mag slot hypothesis | Steal or skip? |
|---|---------|------------------|---------------------|----------------|
| 1 | | arxiv / reddit / openclaw / X / github | e.g. switchboard, verkle, improve | |
| 2 | | | | |

**Rotation hint:** check `configs/improve.yaml` → `rotation` for today's tier-B sources.

---

## Scout plan (P1 commands)

```powershell
mag.cmd improve --once
mag.cmd research-pack --ask "{scoped question}" --url "{url}"
mag.cmd field-steal --root {path} --max-files 50
mag.cmd dispatch "overlap: {concept} vs existing Mag modules"
```

**Budget:** respect `budgets` in improve.yaml — no remote_llm_for_scout unless explicit.

**Required leaves:**

- [ ] ≥1 FEATURE_COMPOSE card → `memory/improve/evals/features/`
- [ ] Overlap table (below) filled
- [ ] training_event note (manual v1) → `memory/training/events.jsonl`

---

## Routing matrix (P2 — fill before BUILD)

| # | Frozen goal | Expected seat | Expected phase | Expected pack_mode | Actual | Match? |
|---|-------------|---------------|----------------|-------------------|--------|--------|
| 1 | `doctor health status` | local | execute | janitor | | |
| 2 | | | | | | |
| 3 | | | | | | |

**Commands:**

```powershell
python main.py conductor "<goal>"
python main.py cost-sim goal "<goal>" --dry
python scripts/routing_smoke.py
python main.py resonance --tick --goal "{slug}"
```

**Pass criteria:** ≥90% matrix match · routing_smoke exit 0

---

## Overlap results (P1 → P2)

| Scout finding | Existing Mag module / pattern | Overlap % | Decision |
|---------------|------------------------------|-----------|----------|
| | | | wire / extend / new-build / defer |

**Decision rule:**

- ≥3 resonance/backlog hits same pattern → **wire only**
- Full foreign contract maps to one slot → **improve candidate**, not new module
- Matrix fail → fix router or amend proposal — **no BUILD**

---

## Eval case (P3)

**Pattern:** `ilap_cycle` | `research_dive` | `steal_compose`  
**Eval id:** eval-ilap-{slug}  
**Join keys:** `build_slug`, `commitment`, `run_id`, `session_id`

**Reject criteria:**

- {e.g. overlap > 70% with switchboard + conductor}
- {e.g. no disk decode for public riddle surface}

---

## Verkle / logging braid

| Subsystem | What this ILAP writes |
|-----------|------------------------|
| improve | candidates from scout |
| field_steal | contract families |
| research_pack | REPORT.md |
| training_events | ilap_cycle / research_dive |
| resonance | findings if soil rhymes |
| verkle | gap check at P6 close |
| releases | gate record if version arc |

---

## Outcome decision (P3 — human L3)

- [ ] **BUILD** — proceed to `queue/handoff/BUILD-{slug}.md`
- [ ] **WIRE** — connect existing modules; no new epic
- [ ] **DEFER** — add to deprecation_registry with triggers
- [ ] **REJECT** — FKB signature; do not revisit without new trigger

**Signed:** __________ **Date:** __________

---

## If BUILD: scope cap

| Field | Value |
|-------|-------|
| Max files | 10 |
| Max frontier seat $ | (cost-sim estimate) |
| Forbidden | .env, verkle_tip, foreign prompt DNA |

Copy to `queue/handoff/BUILD-{slug}.md` when frozen — see `docs/ref/BUILD-TEMPLATE.md`.
