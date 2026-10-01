# Fractal beads — turtles all the way down

**Commitment:** `fractal-beads-001`  
**Parent:** `DNA.md` · `ZEITGEIST.md` · `FUTURE_PROOFING.md`

---

## The idea (plain)

A **bead** is any unit of work that is:

1. **Closed enough** to file  
2. **Addressable** (stable id)  
3. **Committed** (content hash)  
4. **Carded** (title + short blurb + bullets — human face)  
5. **Chainable** (parent tip / child leaves)  
6. **Openable** (full residual payload, not only the card)

**Same six properties at every scale.** That’s the Verkle / scalar / “turtles” pattern without needing Mandelbrot shaders.

```
forest (many people)
  └── person chain (tip)
        └── day bead (session residual)
              └── turn / ask beads (optional)
              └── artifact beads (doc, PR, research pack)
                    └── section beads (heading blocks)  …as needed
```

**Not infinite in practice.** Depth stops when further split doesn’t add retrieval value. Default depth for Mag product:

| Depth | Unit | Status |
|------:|------|--------|
| 0 | Person tip | yes |
| 1 | Day / session | **yes (DNA)** |
| 2 | Operator asks / major moves | partial (salient + bullets) |
| 3 | Artifacts (docs, packs) | next |
| 4+ | Doc sections | later / on demand |

---

## Repeatable pattern (the only schema that matters)

Every bead, any scale:

```text
bead.v1
  id            # stable
  kind          # session | turn | doc | section | research | person
  parent_id     # null at tip of its local chain
  ts_start / ts_end
  card          # { title, blurb, bullets[] }
  content_commit  # hash of payload
  payload_ref   # path or inline small payload
  children[]    # optional list of child ids (or discover via index)
  invariants[]  # optional protected core (consent, no-throne, …)
```

**Card** = coarse-grain (what you show in a list).  
**Payload** = full fidelity (what you open).  
**Commit** = integrity.  
**Children** = Verkle-like branching (higher fan-out later; start with flat lists + parent links).

Display rule (same everywhere):

1. **List** = cards only  
2. **Open** = payload  
3. **Zoom out** = parent card + sibling cards  
4. **Zoom in** = children cards  

That’s the mandelbulb *behavior* (same shape under zoom), not a 3D demo.

---

## Ref-leaf template (docs that stay useful)

Human-facing docs for any bead kind use the fixed skeleton in `docs/templates/REF_LEAF.md` (eight sections: card → anchors → payload → use → edges → claims → forward → one line). Fill rules by kind: `docs/templates/FILL_RULES.md`. Machine twin: `ref_leaf.v1.schema.json`. First real framework leaf: `docs/ref/strike_origin.md`.

---

## Full fidelity to docs

Docs are not second-class. A living doc is a bead chain:

| Kind | Example |
|------|---------|
| `doc` | `docs/DNA.md` as residual snapshot when it materially changes |
| `section` | H2/H3 blocks as child beads when you need citation |
| `research` | research-pack PDF/json already almost a bead |

**Fidelity means:** when the AI or UI cites the project, it can point to  
`doc:DNA@commit` or `session:019f…@commit` — not “that thing we said once in chat.”

**Repeatable ingest of docs:**

```text
on doc save / explicit "file doc bead":
  → residual or docs_ledger/{slug}.json
  → card from first paragraph + H2 bullets
  → content_commit of file bytes
  → registry row kind=doc
```

Sessions **link** to doc beads they touched (child or edge), so the tapestry is session↔doc, not only session↔session.

---

## How AI weaves (without owning the cloth)

| AI job | Bead operation |
|--------|----------------|
| File the day | Create/amend depth-1 session bead |
| Summarize | Rebuild card from payload (pure function) |
| “What was I doing?” | Read latest session cards |
| Connect days | Propose edges / children (operator confirms or auto from shared themes) |
| Cite docs | Resolve doc beads by commit |
| Strike | Operate on beads + edges, not raw infinite chat |

AI is the **loom helper**. Beads on disk are the **tapestry substrate**.

---

## Verkle trees (honest engineering ladder)

| Stage | What we have / build |
|-------|----------------------|
| **Now** | Flat tip + session leaves (hash chain); residual payload |
| **Next** | Parent/child ids; session → ask beads; session → doc beads |
| **Then** | Merkle inclusion: prove leaf ∈ tip |
| **Later** | Wider fan-out / vector commitments if ever needed |

Call it Verkle when the **branching + succinct proof** exist. Until then: **fractal bead + chain** (same soul, honest name).

---

## Mandelbulb / turtles (discipline, not decoration)

**Allowed meaning:** zoom in or out, the UI and the file schema still look like “card → open → children.”  
**Forbidden meaning:** infinite recursive generation for its own sake; depth that can’t be listed.

**Stop rule:** if a human can’t name what the sub-bead is for in one sentence, don’t mint it.

---

## Mapping to Mag today

| Pattern piece | Today |
|---------------|--------|
| Day bead | `residual/{session}.json` + registry row |
| Card | `session_card` |
| Commit | `content_commit` / residual_hash |
| Chain | knots + tip |
| Sub-beads (asks) | `salient_points` / bullets (not yet first-class beads) |
| Doc beads | **not yet** — docs live as files only |
| Cross links | themes shared (implicit); graph not built |

---

## Implementation order (future-proof, not big-bang)

1. **Freeze `bead.v1` / `residual.v1`** with optional `children` + `kind`  
2. **Promote asks → turn beads** inside session residual (ids + cards)  
3. **Doc bead filer** for `docs/*.md` on explicit save or CLI `file-doc`  
4. **Edges** session↔doc, session↔session (tapestry)  
5. **Operate UI:** bead · children · “open parent” (same chrome at every depth)  
6. **verify-leaf** when chain proofs matter  

### Sample render (operational now)

| Piece | Location |
|-------|----------|
| Pack builder | `mag/tapestry.py` |
| CLI | `python main.py tapestry` |
| API | `GET /api/v1/tapestry` |
| Pack file | `memory/biography/tapestry_pack.json` |
| Mag UI | Dashboard tab **Tapestry** (Three.js, strike-desk engine grammar) |
| Transforms | Day **helix** (time) · theme **ring** · ask **radial** children · doc **shell** · tip at origin |

Node schema matches sovereign-mirror `platform/engine.js` `renderConnectionGraph`:
`{id, x, y, z, S, label, kind}` + edges `{source, target, weight, kind}`.

---

## One line

**Same bead shape at every scale: card to show, payload for fidelity, hash for integrity, children to zoom — sessions, asks, and docs all the way down, until split stops helping.**
