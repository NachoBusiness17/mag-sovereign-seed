# Mag Dashboard — Design Principles

**Commitment:** `dash-design-001`  
**Parents:** `docs/HOW_TO_MAG_DASHBOARD.md` · Operator Card · UX progressive disclosure practice  

---

## Product sentence (UI must express this)

**Local office that files work as beads; Home answers status + last day + next step; AI gets a pack, not a chat dump.**

---

## Jobs to be done (priority order)

1. **Am I OK to work?** (health / ship / phoenix)  
2. **What did I do?** (latest bead)  
3. **What’s open?** (loops / working)  
4. **Talk to Mag / load pack** (chat, catch-up)  
5. **Depth** (days, models, maps, board)  

If the UI serves (5) before (1–4), it fails.

---

## From industry practice (interpreted for Mag)

| Practice | Mag application |
|----------|-----------------|
| Visual hierarchy | Ship + bead + next above maps/quotas |
| Progressive disclosure | Home summary → “Days / Chat / Tools” → expert panels |
| 5-second comprehension | Status plain English; jargon second |
| One primary CTA | Refresh / Chat / Catch up |
| Empty states with action | “No beads yet → finish a Grok day / backfill” |
| Alerts only when needed | Phoenix only if ship ≠ OK |
| Don’t compete equal tabs | No 12 peer windows on first paint |

Sources informing this (general UX consensus): progressive disclosure, KPI-first hierarchy, drill-down not dump—e.g. dashboard hierarchy and disclosure patterns widely documented in 2024–2026 product UX writing.

---

## Information architecture (tesuji-002)

```
┌──────────────────────────────────────────────────────┐
│ Status strip: headline · ship · catch-up · refresh   │
├──────────────────────────────────────────────────────┤
│ Dock (5 only): Office · Days · Ideas · Chat · Status │
├──────────────────────────────────────────────────────┤
│ Office: BEEN · NOW · GOING + LOAD CTAs               │
│ Days:   day list + connection graph + inspect        │
│ Ideas:  topic nodes + pack                           │
│ Chat:   ask / seats live inside chat only            │
│ Status: body · spend · seats (lab instruments buried)│
└──────────────────────────────────────────────────────┘
```

**Demoted (not dock peers):** Visual, Detail (from Days), Board, Brief, Flow, Models, Blast, Lattice, Ingest, 3D-alone.

---

## Aesthetic

- **Terminal-inspired** (mono, dark, green accent) for Mag identity  
- **Not** window-manager chaos as default  
- Custom scrollbars inside panels only; no page-level Windows scrollbar  
- Readable first; glow/scanline optional and low opacity  

---

## Acceptance tests

- [ ] New user names “last work” and “what’s broken” in 30s  
- [ ] FIND/FILE/LOAD visible without scrolling past the fold on 1080p  
- [ ] Advanced tools require one explicit expand/click  
- [ ] Hard refresh not required for basic function (cache-bust static)  
- [ ] Phoenix hidden when ship is OK  

**v3 vision (custom layout + Tesuji Grove):** `docs/ref/LAYMAN_OFFICE_VISION.md`

---

## One line

**Summary first, files second, spectacle never first.**
