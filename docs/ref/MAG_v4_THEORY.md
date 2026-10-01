# Mag v4 — Theory sketch (factory line era)

**Commitment:** `mag-v4-theory-001`  
**As-of:** 2026-08-05  
**Status:** Theory only — not roadmap commitment  
**Parents:** `MAG_PROJECT_PROPOSAL.md` · `MAG_BUILD_PIPELINE.md` · `MAG_v3_RESEARCH_PLAN.md`

**Read this when:** planning multi-seat builds (Grok plan → DeepSeek build → Cursor audit) and asking *what happens to the product if we get good at that?*

---

## 1. Version arc (honest)

| Phase | Maturity label | Product sentence |
|-------|----------------|------------------|
| **Now** | Alpha | Constitution + loops; you still push many buttons |
| **v2** | Beta-shaped | Honest lattice — router, autorun, FKB, Office |
| **v3** | Research → product | Conductor, Grove, layman office, resonance, spider |
| **v4** | Theory | **Sovereign build factory** — plan/build/audit as factory line |

v4 is **not scheduled**. It is the attractor if v2–v3 loops compound.

---

## 2. v4 center of gravity

```text
v2:  "Mag routes my work"
v3:  "Mag notices and conducts"
v4:  "Mag runs the factory line — I sign permits"
```

The **factory** is the multi-seat pipeline in `MAG_BUILD_PIPELINE.md` become product:

| Station | Seat | Output |
|---------|------|--------|
| Drafting | Grok + operator | Frozen BUILD_SPEC |
| Floor | DeepSeek | Branch + tests |
| Inspection | Cursor + framework | Audit JSON + verdict |
| Archive | Mag disk | Trail + grove node + optional merge |

---

## 3. What changes for the operator

| Today (alpha) | v4 (theory) |
|---------------|-------------|
| You steer mid-build often | Spec frozen; spider/conductor nudge workers |
| Grok used ad hoc | Grok **only** on `[priority]` plan tickets |
| DeepSeek loops unbounded | Factory queue + cost ceiling per BUILD_SPEC |
| Audit = you reading diff | Audit ritual + auto gates + Cursor spot-check |
| Learnings in improve/ | **Grove** poems + FKB + conductor training |

**You:** chief permit officer + architect on epics.  
**Not:** keyboard for every tool call.

---

## 4. L-conductor in v4 (the missing foreman)

v3 researches **L-conductor** — local model trained on orchestration outcomes.

v4 assumes conductor **runs the factory**:

```text
ticket arrives
  → conductor: plan | build | audit | defer
  → spawn seat with minimal pack
  → watch spider signals
  → FILE cycle to grove + trail
  → never merge without L3
```

Training signal = your BUILD_SPEC → build → audit verdict chains (not diary mimicry).

**Steiniger mapping ([slashreboot.com](https://slashreboot.com/)):**  
- Static body = frozen BUILD_SPEC + constitution  
- Dynamic body = worker context window  
- Conductor learns when dynamic drift violates static law  

Not Athena persona — **factory foreman**.

---

## 5. Economics (expectations)

### 5.1 If discipline holds

| Cost bucket | Trend |
|-------------|-------|
| Grok | ↓ per feature (one plan per epic) |
| DeepSeek | ↑ total but bounded per spec |
| Cursor | Stable — audit not rewrite |
| Ollama | Flat — classification |
| Rework | ↓ via FKB + grove |

### 5.2 If discipline fails

| Failure | Cost explosion |
|---------|----------------|
| No frozen spec | DeepSeek re-plans in loops |
| Grok on implementation | Double pay architects + builders |
| Skip audit | Cursor rebuilds entire feature |
| Chat as handoff | Every seat re-reads entire history |

**v4 productizes discipline** — factory refuses build without frozen handoff.

---

## 6. Layman / Grove in v4

| v3 Grove | v4 Grove |
|----------|----------|
| Poem nodes from learnings | + **factory shift** nodes per BUILD cycle |
| Curious errors | + **audit fails** as fireflies |
| Manual classify | Conductor proposes class; you edit poem |

Office shows: **"Last factory run: audit pass · 3 files · poem: Spec frozen, contractor built."**

---

## 7. Spore / riddle layer in v4

v3 **riddle packs** — public surface to API, real spec on disk.

v4 factory use:

- DeepSeek on rented GPU sees **riddle + acceptance** only  
- BUILD_SPEC full text stays T0/T1 on your mount  
- Audit compares **output** to **local spec** — not to riddle  

**Effect:** rent compute without renting biography. Misuse guardrails remain L3.

---

## 8. Republic / forest (v4 boundary)

| Mag v4 node | Republic forest |
|-------------|-----------------|
| Your factory runs | Export **factory grammar** (plan template, audit checklist) |
| Your BUILD specs | **Never** public by default |
| Grove poems | Optional spore witness — activation keys |
| Conductor weights | L-exp on your disk; fork empty |

**G4 still deferred:** inter-node factory orchestration without throne registry.

---

## 9. What v4 is NOT

- Unattended merge  
- AGI running your life  
- Steiniger physics as product law  
- Mirror training replacing factory  
- Cheaper without spec discipline  
- End of human `[priority]` on architecture  

---

## 10. Path from here (no dates)

```text
Alpha now
  → v2 merge + honest autorun
  → v3 conductor research + grove + layman office
  → pilot MAG_BUILD_PIPELINE on 3 epics (manual)
  → automate factory CLI when audit JSON reliable
  → v4 naming justified when conductor routes plan/build/audit without you babysitting
```

**Gate question for v4:** Can you run **plan → freeze → build → audit → merge** on three features without re-explaining Mag in chat?

If yes → v4 theory is load-bearing. If no → stay v2/v3.

---

## 11. One paragraph for Grok / Cursor / DeepSeek

We are building toward a **sovereign factory line**: Grok and Cursor **plan** frozen BUILD specs on disk; DeepSeek **builds** only from those specs in container branches; Cursor **audits** with ponytail-audit, routing_smoke, and pytest — no architecture in build, no implementation in audit. Mag FILES trails and learnings to Grove. v4 is when an **L-conductor** routes those stations automatically. Cost stays bounded only if specs are frozen and chat is not the handoff. Steiniger/slashreboot informs static/dynamic body split — not physics product.

---

*End v4 theory — update after factory pilot epics.*
