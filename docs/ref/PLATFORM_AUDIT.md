# Mag platform audit — elegance + REST

**Date:** 2026-08-01  
**Scope:** dashboard API, Ideas OS board, file spine, UI doors  

---

## Product shape (what the platform *is*)

| Layer | Role | Truth |
|-------|------|--------|
| **Files** | Residual days, idea cards, packs, tip | Source of truth under `memory/` |
| **API** `/api/v1/*` | Viewport + actions | RESTful resources; no second DNA |
| **UI dock** | Human hands | Office · Days · Diary · Story · **Ideas** · Chat · Status |
| **CLI** `main.py` | Same operations without browser | Parity preferred |

**Intended OS spine:** Ideas board = working set for models; Days = history; Chat/dispatch = act with a pack.

---

## Findings (audit)

### What works

- File-first architecture (jsonl residual, idea graph, tip badge).
- Dual route table (`ROUTES` + `LEGACY`) keeps old UI alive.
- Home / diary / story / ideas / status doors map to real endpoints.
- Lab process (`main.py lab`) = watch + dashboard + cycles in one process.

### Friction (before this pass)

| Issue | Why it hurts |
|-------|----------------|
| Ideas was read-only list + seed | Cannot mark done → board drifts from reality |
| No `GET/PATCH /ideas/{id}` | Not a real resource; only `/pack` subresource |
| Filters ignored server-side | Query string never merged into handler params |
| Errors often `200 + ok:false` | Breaks REST clients and cache semantics |
| UI mixed `/api` and `/api/v1` | Double fallbacks, restart theater |
| ~40 legacy aliases | Fine for compat; primary surface was under-documented |
| No HTTP PATCH | Status updates would have been fake RPC |

### Architecture debt (still open — not all fixed this pass)

1. **RPC-shaped POSTs** (`catch-up`, `multi-smoke`, `dispatch`) — OK as *actions*; later nest under resources (`POST /sessions:catch-up`) if we want purity.  
2. **One-off routes still in `server.py`** (`/api/dossier/latest`, probe) — should move into `rest.py`.  
3. **Many GET synonyms** (`/status` = `/router-status`, `/summary` = `/home`) — keep but list once in index.  
4. **Office / Days still denser than Ideas** — product goal is Ideas-as-OS; continue shifting CTAs.  
5. **No `ETag` / conditional GET** — optional later for tip/ideas.  
6. **Jsonl append-only history** — patch rewrites full nodes file (fine at current scale).

---

## Changes shipped (this pass)

### REST Ideas resource

```
GET    /api/v1/ideas              ?status=&type=&limit=
POST   /api/v1/ideas              { title, type?, status?, body? } → 201
GET    /api/v1/ideas/{id}
PATCH  /api/v1/ideas/{id}         { status?, title?, body?, tags? }
GET    /api/v1/ideas/{id}/pack
POST   /api/v1/ideas/seed
```

### Platform mechanics

- `dispatch(..., query=)` merges query string into handler params.  
- `server.do_PATCH` + JSON body helper.  
- Uniform `_ok` / `_err` envelopes for Ideas (real 4xx/5xx).  
- `/api/v1` index rewritten around **primary** resources (ideas first).  
- `idea_graph.patch_node` + tests.  
- UI: Mark done / On the shelf / Needs work → PATCH.  
- Client `API = "/api/v1"` + `patchJSON`.

---

## How to operate elegantly (daily)

1. **Ideas** — Needs work → pick one → brief → Chat.  
2. When finished — **Mark done** (board stays true).  
3. **Days** — history / graph, not the task list.  
4. **Status** — only when body/router is sick.  
5. Prefer **`/api/v1/*`** in scripts and agents.

```powershell
# board
curl http://127.0.0.1:8765/api/v1/ideas?status=open
# done
curl -X PATCH http://127.0.0.1:8765/api/v1/ideas/n_xxxx -H "Content-Type: application/json" -d "{\"status\":\"done\"}"
# catalog
curl http://127.0.0.1:8765/api/v1/
```

---

## Next elegance slices (priority)

1. Move remaining `server.py` one-offs into `rest.py`.  
2. `POST /api/v1/ideas` form in UI (add card without seed).  
3. Home “Going” → deep-link selected idea.  
4. Context-pack line: open ideas count + primary card id.  
5. Gradually drop dual `/api` fetches from `app.js` once lab always serves v1.

---

## One line

**Files are truth; `/api/v1` is the RESTful hand; Ideas is the OS working set; everything else is history, body, or action.**
