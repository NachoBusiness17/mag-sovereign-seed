# Ponytail / Caveman audit — Mag v2 baseline

**Commitment:** `ponytail-caveman-audit-001`  
**Ref:** [dietrichgebert/ponytail](https://github.com/dietrichgebert/ponytail) · caveman = terse-prose control arm  
**Run:** `python main.py ponytail-audit`

---

## 1. What each tool is

| Tool | Job | Mag use |
|------|-----|---------|
| **Ponytail** | Lazy senior dev ladder — minimum necessary code, safety preserved | **Code** diffs, deps, abstractions |
| **Caveman** | Ultra-compressed prose — drop filler, keep accuracy | **Docs** — plan, handoff, cards |
| **Lessig 1–6** | Law / norm / market / architecture | **Governance** — binds without asking |

Mag does **not** install ponytail as a seat skill. We **audit** the repo with the same ladder and write law in `MAG_v2_PLAN.md` §1.

---

## 2. Ponytail ladder (Mag binding)

```
1. Need exist?     → no: skip (YAGNI)
2. In codebase?    → reuse
3. Stdlib?         → use
4. Native?         → use
5. Installed dep?  → use
6. One line?       → one line
7. Else            → minimum that works
```

**Never on chopping block:** G1–G4 gates · T0–T3 refuse · FKB · residual · trust-boundary validation · irreversible=L3.

---

## 3. Caveman vs ponytail (benchmark context)

From ponytail's agentic benchmark vs [caveman](https://github.com/JuliusBrussee/caveman):

| Arm | LOC | tokens | safe |
|-----|-----|--------|------|
| ponytail | **-54%** | **-22%** | 100% |
| caveman | -20% | +7% | 100% |

**Lesson for Mag:** caveman cuts words, not always work. Ponytail cuts **unnecessary code** while keeping guards. Mag docs use caveman density; Mag code uses ponytail ladder.

---

## 4. Baseline audit (2026-08-05)

Command: `python main.py ponytail-audit`

| Tag | Finding | Action |
|-----|---------|--------|
| **dup** | `DEPTH_JOB_MAP` | ✅ Fixed — `governor_autorun` imports `mag.router` |
| **delete** | `lattice-loop --backfill` dead handler | ✅ Removed — use `lattice-backfill` |
| **delete** | `sovereign-mirror-scaffold` | Marked optional spore; not v2 blocker |
| **shrink** | `main.py`, `dashboard/rest.py`, `agent_cli.py`, `improve.py` | Defer — phase ships first, split when asked |
| **yagni** | Thin wrappers in `agent_cli` (colors) | Low priority — terminal UX |

**Gate:** medium/high findings = 0 before v2 merge to `main`.

---

## 5. v2 refresh touches (this tranche)

| Change | Ponytail rung |
|--------|---------------|
| `mag/ponytail_audit.py` + CLI | Reuse ladder, no new framework |
| `DEPTH_JOB_MAP` single import | Reuse (#2) |
| Remove dead `lattice-loop` backfill branch | Delete (#1) |
| `MAG_v2_PLAN` Lessig §1 | Caveman density on law |
| `lattice_loop` ponytail comment | Document ceiling |

---

## 6. Schedule

| When | Command |
|------|---------|
| Pre-merge | `ponytail-audit` |
| Weekly (Sat) | `verkle-audit --full` then `ponytail-audit` |
| Pre-PR | `routing_smoke` + `ponytail-audit` |

---

## 7. What we will not ponytail

- Container boundary (`CONTAINER.md`)
- Failure KB + remedy cards
- Verkle cold DNA
- Operator pause / autorun gates
- Tests that prove tier refuse

**Usable tool. Not a cathedral.** — `MAG_Card.md`
