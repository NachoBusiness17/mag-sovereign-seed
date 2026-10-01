# Mag v5 — Product pipe (umbrella)

**Commitment:** `mag-v5-pipe-001`  
**As-of:** 2026-08-05  
**Status:** Planning — **v5 tracks piped**; v3 substrate + v4 mold first  
**Parents:** `MAG_v5_GSTD_FOREST.md` · `MAG_v5_VAST_TRAINING.md` · `MAG_v5_XRPL.md` · `MAG_TRAINING_DATA_SPEC.md`

**Job:** Three v5 outcomes on one spine — optional external compute and rails **through Mag routing**, not as separate products.

---

## 0. One line

**v5 = Mag trains and routes agents on rented GPU (Vast), optional DePIN inference (GSTD), optional mesh/offline transport (research forest), and XRPL literacy — all via the same seat switchboard, export pipeline, and human promote gate.**

---

## 1. The three v5 tracks

| Track | Doc | v5 job | Mag already has |
|-------|-----|--------|-----------------|
| **GSTD forest** | `MAG_v5_GSTD_FOREST.md` | MIT DePIN inference + task economy seat | Clones, index, router `vast`/`deepseek` pattern |
| **Mesh forest** | `MAG_v5_MESH_FOREST.md` | Offline/mesh transport + willing device participation (piped) | `pull_mesh_comm_repos.sh`, ILAP research tags |
| **Vast training** | `MAG_v5_VAST_TRAINING.md` | Rent GPU → export curriculum → LoRA/SFT → import weights | `providers.yaml` vast, `scripts/vast/`, blast, training events |
| **XRPL rails** | `MAG_v5_XRPL.md` | Ledger queries + payment hooks via Mag tools (L3 human) | Ingest, tiers, gstd-bridge reference (deferred upstream) |

```text
                    ┌──────────────── Mag Office / Chat ────────────────┐
                    │  preflight · seat picker · cost chip              │
                    └─────────────────────┬─────────────────────────────┘
                                          │
                    ┌─────────────────────▼─────────────────────────────┐
                    │  route.v2 · switchboard · seat_score · conductor   │
                    └─┬──────────────────┬──────────────────┬─────────┘
                      │                  │                  │
              T0 Ollama local      L1-cap seats         L3 human seal
                      │                  │                  │
                      │         ┌────────┴────────┐         │
                      │         │                 │         │
                      │      Vast.ai          GSTD DePIN    XRPL
                      │   infer + TRAIN      inference    payments
                      │         │                 │         │
                      └─────────┴─────────────────┴─────────┘
                                FILE → training export → promote
```

---

## 2. Version roles (unchanged law)

| Version | Delivers for v5 |
|---------|-----------------|
| **v3** | REST agent API, orchestrator, training hooks, vast inference stub, cursor bridge |
| **v4** | Steward train-prep export, cost ledger, seat cards, spore catalog, freeze gates |
| **v5** | Implement the three tracks after §4 gates |

**v5 is not v3 scope.** Today: file plans, catalog spores, use vast for **inference** only if configured.

---

## 3. Shared v5 infrastructure (build once, three tracks use it)

| Build | Path / module | Used by |
|-------|---------------|---------|
| Training export CLI | `training-export` (`MAG_TRAINING_DATA_SPEC`) | Vast train curriculum |
| Cost ledger | `memory/training/cost_ledger.jsonl` | Vast rent + GSTD tasks + API seats |
| Seat playbook | `configs/seat_playbook.yaml` | All L1-cap routing |
| Switchboard peer | `mag/switchboard.py` | GSTD worker, Vast job, XRPL tool seat |
| Promote gate | `main.py promote --apply` | Weight import, lane changes, XRPL enable |
| Spore + ingest | `mine/curated/`, `memory/ingest/` | GSTD + XRPL protocol truth |
| Operator vault | password manager / `.env` | `VAST_*`, `GSTD_*`, `XRPL_*` — never git |

---

## 4. Gates (all three tracks)

| Gate | Check |
|------|-------|
| v2 on `main` | Router, autorun, FKB merged |
| v4 steward | `steward-train-prep` weekly export exists |
| Training spec | `training-export --eval` green on frozen set |
| Seat economics | `cost_ledger` records Vast + remote seats |
| Chat preflight | CHAT-1→4 (seat + cost visible before send) |
| Human L3 | No auto train deploy · no auto XRPL spend |

---

## 5. Track summary

### GSTD (DePIN)

Probe → shadow worker → `gstd-inference` lane. See `MAG_v5_GSTD_FOREST.md`.

### Vast (train agents)

Curriculum local → rent GPU → run train job → weights home → destroy instance. See `MAG_v5_VAST_TRAINING.md`.

### XRPL (rails)

Read-only account/ledger tools → Mag MCP/agent tools → L3 payment template. **Not** gstd-bridge prod until upstream ships. See `MAG_v5_XRPL.md`.

---

## 6. One-pagers

| # | File |
|---|------|
| 9 | `09-gstd-v5-pipe.md` |
| 10 | `10-vast-training-v5.md` |
| 11 | `11-xrpl-v5-pipe.md` |
| 12 | `12-v5-pipe-umbrella.md` |

---

## 7. Backlog IDs

| ID | Title |
|----|-------|
| v5-GSTD | GSTD forest seat |
| v5-VAST | Vast.ai training pipeline |
| v5-XRPL | XRPL via Mag tools |

All in `MAG_v3_BACKLOG.md` §6.

---

*v5 = optional power on the same harness. Local janitor stays default.*
