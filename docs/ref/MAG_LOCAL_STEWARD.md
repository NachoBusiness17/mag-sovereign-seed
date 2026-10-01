# Mag v4 — Local steward & actor memory (planning draft)

**Status:** Planning only — v4-first mold for janitor intelligence + auditable memory  
**As-of:** 2026-08-05  
**Commitment:** `mag-local-steward-001`  
**Parents:** `MAG_V4_CONDUCTOR_LOOP_DRAFT.md` · `memory_verkle_map.md` · `MAG_TRAINING_DATA_SPEC.md` · `DNA.md`

**Read when:** defining what the **local agent** does daily, what it may read (Verkle + engines), and how **people/engine memory** stays editable like xAI — without chat-as-DNA.

---

## North star

> **Local janitor = curator.** Regular small jobs: catalogue, hunt, pattern, file.  
> **Verkle = complete read** for local seat only.  
> **Actor memory = distilled facts about people & engines** — editable, auditable, never raw chat as law.

Grok remembers the *user* in-product. Mag remembers **operators, seats, and engines** on disk — with amend trail and human veto — because your harness spans many models, not one SaaS chat.

---

## Local steward seat

**Seat:** Ollama janitor (`gemma4` / scut) + optional DeepSeek for one `[improve]` pass/day.  
**Not:** a second always-on chat window. **Is:** scheduled queue jobs + improve rotation.

### Regular job menu (autorun / improve fill)

| Job id | Task | Reads | Writes | Cadence |
|--------|------|-------|--------|---------|
| `steward-prompts` | Catalogue `prompts/`, skills, cursor rules — drift vs playbook | prompts, configs | `memory/steward/prompt_catalog.jsonl` | daily |
| `steward-bugs` | Scan FKB, behavioral events, pytest failures — small fix candidates | FKB, logs, tests | improve candidates `[steward]` | daily |
| `steward-patterns` | Cluster training events, loop-audit, chord loops | trails, events | daily `{date}-patterns.md` | daily |
| `steward-verkle` | Walk chain tip → knots; orphan/residual gaps | **full Verkle** | verkle-audit synth slice | 2–3×/week |
| `steward-engines` | Digest `live_from_grok`, cursor handoffs, cloud transcripts | engine feeds | **actor memory** drafts | daily |
| `steward-train-prep` | Export redacted T2 episode bundles for republic | events, ledger | `memory/training/export/` | weekly |
| `steward-bug-hunt` | Targeted grep/test scout from attention + queue | attention, todo | candidate or todo row | on demand |

**Law:** Each job emits **one leaf** (catalog row, candidate, or memory amend draft) — not open-ended REPL.

Enqueue shape:

```text
[steward] steward-prompts — catalogue prompt drift vs playbook
```

Autorun: max 2 steward jobs/day alongside improve cap (already in `fill_queue` pattern).

---

## Verkle complete read (local only)

Local steward may read **entire session DNA** — never sent remote by default.

| Path | Content |
|------|---------|
| `memory/biography/verkle_tip.json` | Chain root, n_leaves |
| `memory/biography/verkle_chain.jsonl` | Full commit chain |
| `memory/biography/knots/*.knot.json` | All leaves |
| `memory/biography/residual/*.json` | Session cold vertex |
| `memory/biography/topic_evolution.json` | Theme series |
| `memory/lattice/nodes.jsonl` + `edges.jsonl` | Instrument graph |
| `mag/lattice_query.py` | Theme/neighbor queries |
| `mag/verkle_knot.py` | evolution_summary, verify |

**Pack law for remote seats:** thin bond excerpt only (theme, last knot slug, loops_audited ids) — not full residual.

**API sketch (v4):** `GET /api/v1/verkle/history?tail=N` · `GET /api/v1/verkle/leaf/{filename}` — local bind only.

---

## Actor memory (people + engines)

Separate store from **residual DNA** and **prompts**. Inspired by xAI editable memory; Mag adds **provenance + amend log**.

### Two actor classes

| Class | Examples | Memory use |
|-------|----------|------------|
| **person** | Nacho, collaborator, future user | Preferences, role, steering habits, veto lines |
| **engine** | grok, cursor, deepseek, cloud_agent | Model quirks, typical failures, handoff style, cost profile |

### Store layout

```text
memory/actors/
  registry.json              # id, class, display_name, created
  persons/
    nacho/
      profile.v1.json        # editable fields (structured)
      facts.jsonl            # atomic facts {id, text, source, confidence, ts}
      amends.jsonl           # audit: who changed what, prior value
  engines/
    grok/
      profile.v1.json
      facts.jsonl
      amends.jsonl
      sessions_index.jsonl   # pointer to live_from_grok / handoff — not full chat
```

**Fact row (not chat dump):**

```yaml
schema: actor_fact.v1
fact_id: fact-abc123
actor_id: engine:grok
text: "Prefers architecture answers with mermaid when [priority]"
source:
  kind: session_digest          # live_from_grok | cursor_handoff | operator_edit
  ref: memory/live_from_grok.md#2026-08-04
  session_id: optional
confidence: heuristic
tier_max: T2
editable: true
```

### How facts enter (never silent)

1. **Steward digest** — local clerk extracts 0–3 facts from engine session → **draft** facts (`status: draft`)  
2. **Operator edit** — Office or markdown amend → `amends.jsonl` row  
3. **Promote** — draft → `active` (human L3); rejected → `archived`  
4. **Training export** — active facts with `exportable: false` for T0; engine facts may export T2 patterns only  

**Reject:** auto-promote from LLM extraction without review for person facts. Engine facts may auto-active at `confidence: low` if tagged `non_binding`.

### xAI-like edit & audit

| Action | UI / CLI | Audit |
|--------|----------|-------|
| View memory | Office **Actors** tab | read-only |
| Edit fact | inline edit → amend | `amends.jsonl` |
| Delete | soft-delete `status: archived` | amend retains prior |
| Add fact | operator or steward draft | source ref required |
| Export | redacted JSON for backup | — |

**CLI sketch:** `python main.py actors list|show|edit|amend|digest --engine grok`

---

## Engine conversation gather (not chat-as-memory)

| Engine | Ingest path | Steward job |
|--------|-------------|-------------|
| Grok | `memory/live_from_grok.md`, `watch/tail_session` | `steward-engines` digest |
| Cursor | `queue/handoff/*.json`, seat registry, cloud transcripts | index + facts |
| DeepSeek | orchestrator logs, residual on SessionEnd | outcome + cost join |
| Cloud agent | `cursor_bridge`, improve handoff | brief attached only |

**Law (from memory_verkle_map):** *Prompt is never memory.* Full transcripts stay **warm** (logs, live files); steward writes **cold facts** to actor store with pointers.

---

## Context-pack integration

L0 pack adds optional bond:

```text
## Actors (auditable)
- nacho: [2 active facts — edit in Office]
- engine:grok: last digest 2026-08-04 — prefers frozen BUILD specs
```

Remote seats get **active facts only**, not amends trail, not full Verkle.

---

## v4-first gates

| # | Question |
|---|----------|
| 1 | Pattern — `steward_*` in training_patterns + improve kind |
| 2 | Eval — steward job completes with catalog row or 0 draft facts (no hallucinated memory) |
| 3 | Join keys — `actor_id`, `fact_id`, `session_id`, `source.ref` |
| 4 | Tier — person fact promote human; engine fact draft OK; never auto-edit prompts |

---

## Anti-patterns

- Raw chat copied into `profile.v1.json`  
- Remote API sending full residual or actor memory  
- Steward REPL without queue goal  
- Memory that bypasses amend log  
- “Remember everything” without tier / redaction  

---

## Build order (when leaving planning)

| Order | Deliverable |
|-------|-------------|
| S1 | `memory/actors/` schema + registry |
| S2 | `steward-*` job templates in improve/autorun fill |
| S3 | Verkle history read API (local) |
| S4 | `steward-engines` digest → draft facts |
| S5 | Office Actors tab (view/edit/amend) |
| S6 | Pack bond for active actor facts |

---

## One-line Office target

> *Steward: 2 jobs tonight · Verkle 12 leaves · 1 new engine fact (draft) · actor memory auditable*

---

*Planning draft — person memory always L3 promote for active. Link from HANDOFF when S1 ships.*
