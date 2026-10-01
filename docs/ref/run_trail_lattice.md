# Run/trail × Verkle lattice — framework ref

**Commitment:** `run-trail-lattice-001`  
**Job:** Map mid-run trail substrate + feature-compose onto existing Verkle/bead language.  
**Parents:** `docs/DNA.md` · `docs/archive/FRACTAL_BEADS.md` · `docs/archive/ZEITGEIST.md` · `docs/templates/FEATURE_COMPOSE.md`  
**Code:** `mag/run_trail.py` · `mag/verkle_knot.py`  
**Honesty:** Mag tip is a disk Merkle–Verkle hybrid. Not PEPS/KZG. Not a second cold DNA store.

---

## 1. Card

**Title:** Run sits under the day bead; tip stays session-only  
**Blurb:** Residual + knot leaf file the day. Run + trail keep one goal continuous without fracturing the lattice or advancing the tip.  
**Bullets:**
- Tip = closed day beads only
- Run = depth-2 bead-in-practice (warm-mid)
- Trail cores = intra-run anti-amnesia (bonds = inter-bead)
- Pack = card projection, not payload dump
- Compose = weld edges on shared substrate, not new thrones

---

## 2. Anchors

| Field | Value |
|-------|--------|
| cold DNA | residual + card + content_commit + knot leaf |
| tip | `memory/biography/verkle_tip.json` |
| chain | `verkle_chain.jsonl` + `knots/*.knot.json` |
| warm-mid | `memory/runs/{run_id}/` |
| pack viewport | context-pack `run_trail` excerpt |

---

## 3. Depth chart

```text
person tip (verkle_tip)
  └── day bead (session residual + knot leaf)     COLD
        ├── run (goal · seat lock · trail)        WARM-MID
        │     └── trail events / cores
        ├── research pack / artifacts
        └── bonds → next day bead
```

| Depth | Unit | Tip citizen? |
|------:|------|--------------|
| 0 | Person tip | root |
| 1 | Day / session | **yes** |
| 2 | Run (goal) | no (edge/child only) |
| 3 | Trail event | no (append-only under run) |

---

## 4. Same shape (bead six)

| Property | Session | Run | Event |
|----------|---------|-----|-------|
| Closed enough | SessionEnd | `trail close` | each append |
| Id | session_id | run_id | run_id + seq |
| Commit | content_commit / leaf_hash | optional later `run_commit` | line-hashable |
| Card | session_card | goal + seat + proactivity | summary |
| Parent | person tip | session_id (optional) | run |
| Payload | residual | run.json + trail.jsonl | event object |

---

## 5. Two anti-amnesia edges (same law, two clocks)

| Edge | Scale | Mechanism |
|------|-------|-----------|
| Residual bonds | day → next day | bonds_active + pack |
| Trail cores | turn → next turn | `core` re-inject in pack |

Prune rule holds both: **never strip the protected core** (DNA residual core; trail `core` fields).

---

## 6. K3 steals as lattice hygiene

| Steal | Lattice reading |
|-------|-----------------|
| Trail integrity | No mid-bead fracture of the work graph |
| Seat purity | One observer node per trajectory |
| Proactivity dial | Bound child expansion (no freestyle graph grow) |
| Pack-first | List/open rule: project card+cores, not full payload |
| Feature compose | Shared parent substrate + cancel failure edges |

---

## 7. What must never happen

- Advance `verkle_tip` on trail append  
- Treat open run as lean-complete DNA  
- Embed full trail into residual core  
- Second tip / second cold vertex for “agent memory”  

---

## 8. Wiring status

| Item | Status |
|------|--------|
| `trail close` → `related_runs` ledger + bonds section | **shipped** (`memory/runs/related_runs.jsonl`, bonds ingest) |
| `run_commit` hash at close | **shipped** (on run.json; not tip) |
| Tip = sessions only | **held** — close does not advance verkle_tip |
| Theme vector bump from runs | later |

---

## 9. One line

**The lattice files the day; the run keeps one seat and one trail so the day’s mind does not fracture mid-goal; compose welds foreign edges onto that graph without a second tip.**
