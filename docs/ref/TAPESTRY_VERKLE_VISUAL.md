# Days panel — Verkle knot spiral visual grammar

**Commitment:** `tapestry-verkle-visual-001`  
**As-of:** 2026-08-05  
**Module:** `mag/tapestry_visual.py` · `mag/tapestry.py` · `dashboard/static/tapestry.js`  
**API:** `GET /api/v1/tapestry` · Days panel in Office `:8765`

---

## Intent

The Days 3D tapestry is already a **time helix** with Verkle lattice ghosts. This pass makes sub-objects **varied, representative, and suggestive** of tension structure — stealing **temperature / static-dynamic** ops grammar from [slashreboot / Steiniger](https://slashreboot.com/) **without physics cosplay**.

Not: EUT product law · Athena persona · "the knot proves consciousness"  
Yes: cold commitment beads · hot dynamic swells · topological leaf chain

---

## Visual mapping

| Node kind | Shape | Size driver | Temperature |
|-----------|-------|-------------|---------------|
| **tip** | icosahedron | fixed | cold anchor |
| **session** (day bead) | ellipsoid | `tension_index`, duration | Steiniger temp |
| **lattice** (Verkle leaf) | torus-knot (p,q from leaf hash) | chain index | cold, wireframe ghost |
| **subsession** | tetrahedron | turn index | warm prompt surface |
| **run** | octahedron | tool calls | medium |
| **theme** | dodecahedron | n_days in cluster | theme S |
| **doc** | flat box | fixed | cold shell |
| **turn** (bullet) | sphere | tension | warm |

**Color:** `visual.temp` 0→1 maps cyan → magenta (cold static → hot multi-frame).

**Lattice chain:** micro-helix under each day bead; `lattice_chain` edges link leaves tip→tip.

---

## Data flow

```text
residual registry (tension_index)
  + knot_timeline.jsonl (Q_proxy, duration)
  → mag/tapestry_visual.visual_profile()
  → tapestry_pack.json (visual on each node)
  → tapestry.js geometryForVisual()
```

Rebuild: `python main.py tapestry` or `POST /api/v1/tapestry/rebuild`

---

## Operator controls

- **Toggle Verkle lattice** — show/hide torus-knot chain
- **Click day bead** — pin inspect; shows `temp band` + layman what/where/why
- **Drag orbit** — spiral rotation pauses on interaction

---

## Future (v4 layman office)

- Pulse emissive on `hot` band days with open FKB repeats  
- Grove poem on click for lattice knot ("commitment bead filed")  
- Conductor suggests which day bead matches active factory run  

---

*Ops grammar only — see `MAG_BUILD_PIPELINE.md` §6 for Steiniger steal boundaries.*
