# Mag factory pipeline — pilot program (3 epics)

**Commitment:** `mag-factory-pilot-001`  
**As-of:** 2026-08-05  
**Status:** Alpha pilot — manual ritual before automation  
**Parents:** `MAG_BUILD_PIPELINE.md` · `MAG_v4_THEORY.md` · `HANDOFF_MAG_AGENT_TODOS.md`

**Gate question (from v4 theory):** Can you run plan → freeze → build → audit → merge on three features without re-explaining Mag in chat?

---

## Pilot sequence

| # | Slug | Status | Spec | Purpose |
|---|------|--------|------|---------|
| 1 | `factory-audit-json` | **pass (2026-08-05)** | `docs/ref/BUILD-factory-audit-json-EXAMPLE.md` | Audit phase FILEs structured JSON |
| 2 | `factory-freeze-gate` | not started | TBD after #1 audit | Orchestrator rejects `[build]` without frozen handoff |
| 3 | `plain-office-tagline` | not started | TBD after #2 audit | Small v3-011 slice — plain copy on dashboard |

**Rule:** Do not start pilot N+1 until pilot N audit = `pass`.

---

## Week ritual (per epic)

| Day | Seat | Action |
|-----|------|--------|
| Mon | Grok + Cursor | Plan → `queue/handoff/BUILD-{slug}.md` |
| Tue | You (L3) | Review · set `Status: frozen` · commit |
| Wed–Thu | DeepSeek | Build from frozen spec only |
| Fri | Cursor | Audit pack — no feature creep |
| Sat | You (L3) | Merge or reject · verkle-audit --dry |

---

## Grok plan prompt (copy-paste)

```text
[priority] PLAN only — load docs/FRAMEWORK_LOAD.md + docs/ref/MAG_BUILD_PIPELINE.md.
Epic: {title from pilot table}
Output: queue/handoff/BUILD-{slug}.md using docs/ref/BUILD-TEMPLATE.md structure.
Acceptance must be checkbox-measurable. Max 10 files in scope.
Do not implement. Do not debate v4 physics.
```

## DeepSeek build prompt (copy-paste)

```text
LOAD:
  docs/FRAMEWORK_LOAD.md (tier 0 only)
  queue/handoff/BUILD-{slug}.md
  memory/context_pack_latest.md

GOAL:
  Implement BUILD spec exactly on branch cursor/{slug}-e2ce.
  Run commands from spec before FILE.

FILE on done:
  - paths changed
  - commands run + exit codes
  - open risks
```

## Cursor audit prompt (copy-paste)

```text
AUDIT only — load docs/FRAMEWORK_LOAD.md + queue/handoff/BUILD-{slug}.md.
Diff: main...cursor/{slug}-e2ce
Run: ponytail-audit, routing_smoke, pytest from spec.
Verdict: pass | fix | reject
FILE: memory/runs/build_audit/{slug}.json
No new features. No re-architecture.
```

---

## Cost tracking (per pilot)

After each epic, note approximate seat share:

| Seat | Target % | Actual % | Notes |
|------|----------|----------|-------|
| Grok | 5–15 | | |
| DeepSeek | 50–70 | | |
| Cursor audit | 15–25 | | |
| Ollama | ~0 | | |

If DeepSeek >80% → spec was under-planned; tighten next BUILD spec.

---

## Steiniger lens (slashreboot.com)

Steal **static/dynamic body ops**, not EUT physics:

| Steiniger | Pilot use |
|-----------|-----------|
| Static body | Frozen BUILD spec on disk |
| Dynamic body | DeepSeek context window during build |
| Tension | Audit compares dynamic output vs static law |
| Persona theater | **Reject** — we FILE factory cycles, not Athena |

---

## After pilot 3

If all three audits pass:

1. Update `MAG_v4_THEORY.md` §10 with pilot results
2. Consider `mag factory plan|build|audit` CLI (v4 naming)
3. Grove poem node per cycle (v3-012 dependency)

If any pilot fails open (skip audit, chat handoff): **stay v2/v3** — factory theory not load-bearing.

---

*End factory pilot — update row status after each epic.*
