# Mag version registry

**Commitment:** `mag-version-registry-001`  
**As-of:** 2026-09-26
**Machine truth:** `configs/releases.yaml` · `configs/version_roadmap.yaml`  
**Compass:** `docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md`  
**Science map:** `docs/ref/MYCELIAL_SCIENCE_MAP.md`  
**Behavioral trail:** `memory/improve/releases/gates.jsonl` (operator) + `memory/training/events.jsonl` (`release_milestone`)

**Job:** Index every major version, its release notes, direction artifacts, and graduation gates — so v3–v10 iterate from filed history, not chat.

---

## Build eras

| Era | Versions | Builder | Rule |
|-----|----------|---------|------|
| **Hand-built** | v1–v2 | Operator (Nacho) | Grok origin → this repo substrate |
| **Loop-trained** | v3–v10 | Mag forever loop | One pass + release gate + training event + distill |

Each loop-trained version: loop pass → gate artifact on disk → `release record` → training event → (when eval green) distill to local steward.

---

## Version map (operator definitions)

| ID | Meaning | Status | Release notes |
|----|---------|--------|---------------|
| **v1** | **Grok/X** era that spawned the project | shipped | [RELEASE_NOTES_v1.md](RELEASE_NOTES_v1.md) |
| **v2** | **This repo** in `projects/` — database + harness | shipped | [RELEASE_NOTES_v2.md](RELEASE_NOTES_v2.md) |
| **v3** | **Substrate** — orchestrator, behavioral router, frozen factory, DeepSeek proof | shipped | [RELEASE_NOTES_v3.md](RELEASE_NOTES_v3.md) |
| **v4** | Mold — typed conductor, daily steward, economics ledger, safe export | shipped | [RELEASE_NOTES_v4.md](RELEASE_NOTES_v4.md) |
| **v5** | Pipe — GSTD, Vast, XRPL | planned | [MAG_v5_PIPE.md](../MAG_v5_PIPE.md) |
| **v6** | Loop self-build — first Mag-built Mag | curriculum TBD | TBD |
| **v7** | Steward autonomy — daily soil without asking | curriculum TBD | TBD |
| **v8** | Mesh / peer handoff at scale | curriculum TBD | TBD |
| **v9** | Service packaging — install → offline desk | curriculum TBD | TBD |
| **v10** | Mycelial Republic — pennies/day, GSTD join | curriculum TBD | TBD |

**Honesty:** v6–v10 are **curriculum slots** — direction and meaning filed; gates and release notes TBD until a loop pass proves them. No fake dates.

**Witness:** [WITNESS_SPINE.md](WITNESS_SPINE.md) · [strike_origin.md](../strike_origin.md)  
**Subprocess map:** [MAG_VERSION_SUBPROCESS_MAP.md](MAG_VERSION_SUBPROCESS_MAP.md)  
**Full arc (machine):** `configs/version_roadmap.yaml`

---

## v6–v10 curriculum (planned slots — honest TBD)

These versions are **filed direction**, not promises. Each earns release notes when a loop pass files gate artifacts.

| ID | Curriculum meaning | Depends on | Gate status |
|----|-------------------|------------|-------------|
| **v6** | First Mag-built Mag — loop ships next version | v5 eval + training export | TBD |
| **v7** | Steward autonomy — daily soil without operator ask | v4 steward daily + v6 loop proof | TBD |
| **v8** | Mesh peer handoff at scale | v5 GSTD probe + mesh spores | TBD |
| **v9** | Service packaging — install → offline desk | v3 Chat + v7 steward | TBD |
| **v10** | Mycelial Republic — pennies/day, device fuels GSTD | v5 pipe + v9 packaging | TBD |

See `configs/version_roadmap.yaml` for machine-readable arc and service milestones.

---

| Layer | Artifact | v1 | v2 | v3 | v4 | v5 | v6 | v7 | v8 | v9 | v10 |
|-------|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:---:|
| Release notes | `RELEASE_NOTES_vN.md` | ✓ | ✓ | ✓ | ✓ | TBD | TBD | TBD | TBD | TBD | TBD |
| Run sheet / plan | NEXT_CODING_RUN / vN_PLAN | — | ✓ | ✓ | draft | pipe | TBD | TBD | TBD | TBD | TBD |
| Behavioral gates | `release record` CLI | — | run_a | factory, chat | eval | probe | TBD | TBD | TBD | TBD | TBD |
| Training pattern | `release_milestone` events | — | ✓ | ✓ | ✓ | ✓ | TBD | TBD | TBD | TBD | TBD |
| Backlog defer row | `MAG_v3_BACKLOG.md` §6 | — | — | ✓ | ✓ | v5 rows | TBD | TBD | TBD | TBD | TBD |

---

## Behavioral memory — how versions compound

```text
Release notes (L1 FILE, git)
    ↓
release record → gates.jsonl + training event (L2 SCORE)
    ↓
improve scout / behavioral_synth themes (L2)
    ↓
promote → RUN row / template clause (L3 habit)
    ↓
next RELEASE_NOTES_vN (L1)
```

**Rule:** Gate passed on disk before release notes claim "shipped."

---

## Operator commands

```powershell
python main.py release status
python main.py release notes v2
python main.py release record --version v2 --gate run_a --ok --note "routing_smoke 9/9"
python main.py training-events --stats --pattern release_milestone
```

---

## Regime milestones (revival, 2026-09-26)

The version-gate trail went dark 2026-08-10 while fleet motion continued (468K+ training events since): the only writers were roadmap passes (`mag/roadmap_runner.py`) and manual `training_set build` folds, and neither ran again after the August window-storm pivot. Drift pairs T4/T5 (B2-05, 2026-09-26) proved the referent frozen while lanes moved.

**Revival rule:** alongside version graduation gates, a **regime milestone** is a landed, durable, receipt-filed change to the estate (new standing tool, contract, law, or verified external steal that survives sessions). Distinguished by `gate_id` prefix `regime_`, recorded against the **active version era** (currently v5). It is not a graduation gate and never flips a version to shipped. Display split (B2-209, 2026-09-26): `release status` counts regime rows in a separate `regime_passed` field beside `gates_passed`, never inside it; `_gates_passed_for` excludes the `regime_` prefix.

- **What counts:** artifact on disk + receipt in `watch/inbox/` or `corpus/steal/` + one-line note naming the landed date. Nothing else.
- **Who writes:** the session that landed the work, at close. No daemon, no cron.
- **Trigger:** filing the receipt. The same close step runs:
  `mag.cmd`-adjacent `python main.py release record v5 --gate regime_<name> --ok --note "<landed YYYY-MM-DD> <one line>" --evidence <receipt path>`
- **Tripwire:** the weekly drift stamp (T4/T5) already reads this trail; a stale regime trail (>14 days, fleet moving) re-flags the decoupling.

---

## Amend protocol

1. Edit release notes + bump `as-of` in front matter  
2. Update `configs/releases.yaml` status/gates  
3. `release record` for each gate crossed  
4. One line in `memory/decisions_log.jsonl` if direction changes  

---

*Template: [RELEASE_NOTES_TEMPLATE.md](RELEASE_NOTES_TEMPLATE.md)*
