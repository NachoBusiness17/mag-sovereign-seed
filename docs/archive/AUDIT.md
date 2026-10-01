# Mag codebase audit — simplify + REST

**Date:** 2026-07-21  
**Commitment:** `audit-rest-001`  
**Scope:** `local_sovereign_agent` (product harness), not mycelial-republic / strike desk

---

## 1. Architecture (what we have)

| Layer | Role | Health |
|-------|------|--------|
| `main.py` CLI | Operator control plane | Crowded but workable |
| `mag/*` | Org logic (records, residual, seats, biographer) | Growing; lean residual is right direction |
| `dashboard/server.py` + `rest.py` | HTTP UI + API | **REST table added** |
| `watch/*` | Hooks + lab integral | OK |
| `agents/` + `graph.py` | Older LangGraph “run a goal” path | Parallel to Mag; low daily use |
| `memory/biography` | Residual constitution | Dual-write still present |

**Tests:** 6 unit tests pass (`pytest tests`). Coverage is thin.

---

## 2. Errors / smells found

| Issue | Severity | Status |
|-------|----------|--------|
| Dashboard API was a long `if path ==` chain (hard to extend) | Med | **Fixed** → `dashboard/rest.py` route table |
| GET `/api/catch-up` mutates (non-REST) | Low | **Deprecated alias** to POST |
| Dual-write residual + flat `.dossier.json` + `derived/` + root flat files | Med | **Documented**; still dual for compat — next cleanup |
| Full PDF/visual required for “complete” | High (growth) | **Fixed earlier** — lean complete |
| `.gitignore` missing residual / biography secrets | High for GitHub | **Fix in this pass** |
| Stock session blurbs polluted with system chrome | Med | **Fixed earlier** (session_card filters) |
| Two “organs”: Mag lab vs LangGraph `run` | Low | Leave; document Hands vs optional goal runner |
| No hard private→remote refuse | High for limits day | **Not coded yet** (next survival slice) |
| No `org-review` CLI | High for offline | **Not coded yet** |
| Thin tests | Med | Expand later |

---

## 3. REST surface (v1)

**Index:** `GET /api/v1`

| Method | Path | Resource |
|--------|------|----------|
| GET | `/api/v1/health` | Integral + lanes |
| GET | `/api/v1/kpi` | Records KPI |
| GET | `/api/v1/registry` | Hot session index |
| GET | `/api/v1/sessions` | Session cards |
| GET | `/api/v1/sessions/{id}` | Session detail |
| GET | `/api/v1/sessions/{id}/residual` | Canonical residual |
| GET | `/api/v1/sessions/{id}/visual` | Derived visual |
| GET | `/api/v1/board` | Ops board |
| GET | `/api/v1/chain` | Tip + chain + evolution |
| GET | `/api/v1/brief` | Latest brief |
| GET | `/api/v1/models` / `providers` / `quota` / `usage` / `flow` / `ingest` / `overview` | Support |
| POST | `/api/v1/catch-up` | Reconnect |
| POST | `/api/v1/ask` | Local biographer |
| POST | `/api/v1/brief` | Rebuild brief |
| POST | `/api/v1/visual` | Rebuild visual |
| POST | `/api/v1/multi-smoke` | L0 multi-model smoke |

**Legacy:** old `/api/*` paths still route through the same table.

---

## 4. Storage model (post-lean)

```
registry.jsonl     # hot REST list
residual/{id}.json # canonical
derived/*          # optional PDF/md/visual
knots/ + tip       # chain
*.dossier.json     # legacy mirror (compat)
```

**Next simplify:** stop writing root flat duplicates; only residual + registry + optional derived.

---

## 5. Simplify backlog (priority)

1. **Survival:** `org-review` + private refuse + seat matrix  
2. **Storage:** single write path (no triple flat copies)  
3. **REST:** move usage-report / probe-status into v1  
4. **Tests:** registry + pack_status + REST dispatch smoke  
5. **CLI:** group subcommands (`main.py records …`) when main gets worse  

---

## 6. What we did in this audit pass

- Added `dashboard/rest.py` RESTful dispatch  
- Slimmed POST/GET entry to table-first  
- Documented findings  
- Tightened `.gitignore` for residual/private memory  

**Not done:** full dual-write removal, org-review, private refuse (separate survival PR).
