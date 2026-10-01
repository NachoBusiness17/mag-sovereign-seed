# Mag DNA — residual constitution

**Commitment:** `dna-residual-003` (retired 2026-09-29: no residual, registry, knot, chain, or kpi row binds this id) · **Coldest vertex:** `coldest-vertex-001` (anchor: `docs/archive/README.md:5`)  
**Rule:** Fidelity lives in **files + chain**, not in a process that must stay awake.

## Daily path (start here)

**→ [`docs/HOW_TO_MAG_DASHBOARD.md`](HOW_TO_MAG_DASHBOARD.md)** — layman how-to for Mag + dashboard.  
**→ [`docs/ref/OPERATOR_CARD.md`](ref/OPERATOR_CARD.md)** — FIND · FILE · LOAD · tip badge · presented law.  
**→ [`memory/agent_state/LATEST.md`](../memory/agent_state/LATEST.md)** — versioned agent/Mag self (LOAD before redesign; agent tip ≠ session tip).  
**→ [`docs/ref/DASHBOARD_DESIGN.md`](ref/DASHBOARD_DESIGN.md)** — UI principles (summary first).

UI, specialist seats, and lab are **viewports**. Residual is **DNA**.  
**Spine:** Verkle tip (sessions only) + residual beads + edges (dig/pins/bonds). Kimi-style continuity = trail integrity + pack-first + artifact > transcript — contracts in `docs/ref/memory_verkle_map.md`, not a remote API seat.

**Archive:** older maps live under `docs/archive/` (not product law).  
**Templates:** `docs/templates/REF_LEAF.md` · `FEATURE_COMPOSE.md` · `MODEL_TESUJI.md`.  
**Strike origin (optional archive leaf):** `docs/ref/strike_origin.md`.  
**Lattice × trail:** `docs/ref/run_trail_lattice.md`.  
**Module registry:** `configs/modules.yaml` · `mag.cmd compose-status`.  
**Memory x Verkle:** `docs/ref/memory_verkle_map.md`.  
**Lessig 1-6:** `docs/ref/lessig_1_6.md` · bag `memory/portable_bags/`.  
**Mirror product law:** `docs/ref/MIRROR_PRESENTED.md` — corpus **as presented**, not interpreted.  
**Mag OS v2:** `docs/ref/MAG_OS_v2.md` · card `MAG_Card.md` · activation `MAG_Activation.md` · API `GET /api/v1/mag-os`.  
**Mag v2 roadmap:** `docs/ref/MAG_v2_PLAN.md` — freedom lattice phases + acceptance.  
**Self-analysis pin:** `memory/improve/pins/LATEST.md` (sticker + residual `edges.pins`; not tip).

---

## Shared coldest vertex

**One protected node. Everything else is heat.**

```
tip + registry card  →  residual/{id}.json  (+ session_card)
                              ↑
                     COLDEST VERTEX
```

| Layer | What | Rule |
|-------|------|------|
| **Cold** | residual + card + content_commit + chain leaf | Session close **must** write (daemon poll, `mag/daemon.py:44`); amend cannot strip `core` |
| **Warm** | Board + API | Read-only viewports |
| **Sticker** | PDF / visual under `derived/` | Export on demand only |

**Matthew-shaped prune rule** (Steiniger EUT / Scalar Knots as *ops grammar*, CC-BY — not product physics):  
*Prune theater, never prune residual core.* Primordial residual bonds stay; coarse-grain is the card.

**Lean complete = cold vertex only.** Missing PDF/visual ≠ incomplete.

---

## Promise

| Promise | Meaning |
|---------|---------|
| **Fidelity without lab** | Closed day → residual + card + commit + leaf |
| **Browsable later** | Registry (list) → residual (depth) → derived on demand |
| **Prompt → display** | "What was I doing?" answers from files, not scroll |
| **Set and forget** | Daemon-poll close files DNA; optional daily backfill |
| **Portable** | Backup residual + registry + knots + tip = move house |
| **Data first** | Stats from residual via API/UI. PDF/visual only on **export** |
| **One vertex** | New features = edges (panel/field/export), never a second DNA store |

Lab improves **mid-session** comfort (live board, companion, :8765). It does **not** make DNA true.

**Layers:** (1) residual truth · (2) dashboard query · (3) PDF/visual render on demand (`POST /api/v1/export`).

---

## Create

### Required (session close)

```
daemon poll → summarize_session (mag/daemon.py:44; def in mag/biography.py)
  → residual/{id}.json      # canonical
  → session_card            # title, blurb, bullets
  → registry.jsonl          # hot row
  → chain leaf + tip
  → kpi.json
```

Trigger note: the old `session_end_hook` trigger is retired. The endpoint `watch/session_end_hook.py` survives on disk but the harness wires no SessionEnd event (config checked 2026-09-29: PreToolUse and PostToolUse only), so the daemon poll above is the live close path. Manual fallback: `python main.py summarize-session`.

### Optional derived (export layer; outside the close write)

`derived/{id}.md|pdf|visual_pack.json` — regenerable stickers.  
Build with `POST /api/v1/export` `{session_id, pdf?, visual?}` or UI **Export PDF / Export visual**.

### Lean complete

```
residual + card + content_commit + chain_leaf
```

Missing PDF/visual ≠ incomplete. Never required for "filed."

### Fallback

```text
python main.py backfill-sessions
python main.py migrate-lean-registry
python main.py refresh-session-cards
python main.py pack-status
```

---

## Display

| Ask | Source | Surface |
|-----|--------|---------|
| What days exist? | **registry** | **Board kanban** (only primary surface) |
| What was that day? | **residual** + card + stats | Board drawer (cold read) |
| What was I doing? | latest card + brief + attention | Board sticky panels |
| Export map / PDF | **derived** only after export | Drawer **Export** · `POST /api/v1/export` |
| Memory health? | **kpi** | Board stats strip |
| Heat / optional | same residual | **Advanced** menu (Operate, Visual, Tapestry, …) |

**Contract:** one cold vertex; one warm board; stickers on demand; Advanced = heat.

**Modular board:** kanban (Now / Open / Filed / Export ready) · drawer · panels · no PDF required.

---

## Set and forget

| Lever | Default |
|-------|---------|
| **Architecture** | Daemon close files DNA; lab optional |
| **Norms** | Close the seat cleanly so End fires |
| **Markets** | Heuristic residual free; don't rent memory from a remote seat |
| **Law** | Private residual never remote |

Optional: OS daily `backfill-sessions` for crashed sessions.

---

## Backup DNA (private)

Keep:

- `memory/biography/residual/`
- `memory/biography/registry.jsonl`
- `memory/biography/knots/`, `memory/biography/verkle_tip.json`, `memory/biography/verkle_chain.jsonl`
- `memory/biography/kpi.json`

Skip forever-keeping every PDF or visual; `derived/` regenerates on demand (`POST /api/v1/export`).
