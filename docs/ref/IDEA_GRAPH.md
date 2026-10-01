# Idea graph v0 — topic-shaped continuity

**Commitment:** `idea-graph-v0-001`  
**Schema:** `idea_graph.v0`  
**Code:** `mag/idea_graph.py` · CLI `python main.py ideas …`  
**Parents:** `docs/DNA.md` · sovereign-workspace-spine-001 · FIND → FILE → LOAD  

---

## Job

Store **ideas as presented** and **how they interlink** on disk — not chat heat, not seat economics (`idea_flow.py`).

Session residual answers *what did I work on?*  
Idea graph answers *what do I hold on this topic, and what touches what?*

---

## Store (cold files)

| Path | Role |
|------|------|
| `memory/ideas/nodes.jsonl` | One node object per line |
| `memory/ideas/edges.jsonl` | One edge object per line |
| `memory/ideas/LATEST.md` | Human face after seed/pack |

Not a second session DNA. Link to residual/exports via `evidence` / `ref` fields.

---

## Node types (≤12)

| type | Meaning |
|------|---------|
| `topic` | Large subject / thread |
| `claim` | Thesis or assertion (prefer quote/path as presented) |
| `project` | Shipable workstream |
| `open_loop` | Unfinished tension (from working.md) |
| `evidence` | Pointer to export row, dig leaf, residual, skill bead |
| `entity` | Bureaucratic or external actor (later: avatar scope) |
| `avatar` | Proxy policy card (Phase 3; type reserved) |

**Required fields:** `id`, `type`, `title`, `status` (`open`|`held`|`done`|`parked`), `ts`  
**Optional:** `body`, `refs[]` (paths/urls), `tags[]`, `source` (`seed`|`human`|`agent`)

---

## Edge types

| type | Meaning |
|------|---------|
| `supports` | A strengthens B |
| `depends` | A needs B |
| `contradicts` | Tension |
| `same_thread` | Same large topic cluster |
| `evidence_for` | A is evidence for B |
| `related` | Soft link |
| `acted_on` | Agent/human acted on node |
| `produced` | Run produced artifact linked to node |

**Required fields:** `id`, `src`, `dst`, `type`, `ts`  
**Optional:** `note`, `ref` (artifact path)

---

## CLI

```text
python main.py ideas list [--status open] [--type topic]
python main.py ideas add --type open_loop --title "…" [--body "…"]
python main.py ideas link SRC DST --type depends [--note "…"]
python main.py ideas pack NODE_ID
python main.py ideas seed          # from working Open + agent_state paths
python main.py ideas show NODE_ID
```

---

## Law

1. **Files are truth** — UI reads jsonl; no SPA-only graph.  
2. **Presented first** — claim bodies cite paths/quotes when from corpus.  
3. **Write-back** — agent runs that touch a node should `produced` / `acted_on` (Phase 2).  
4. **No secret fields** — never store API keys in nodes.  
5. **Session tip stays sessions-only** — idea graph does not advance Verkle tip.

---

## One line

**Idea graph = topic lattice on disk; dashboard and avatars are viewports and hands on that lattice.**
