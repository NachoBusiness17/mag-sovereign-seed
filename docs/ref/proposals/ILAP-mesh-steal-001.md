# ILAP proposal — mesh forest steal (completed run)

**Commitment:** ilap-mesh-steal-001  
**Version arc:** v5 mesh forest (research)  
**Status:** **aimed** — wire only, no BUILD  
**Parent:** `docs/ref/MAG_ILAP_PROTOCOL.md`

---

## One line

Steal mesh/offline transport **contracts** from local Bitchat/Bridgefy/Briar clones; prove Mag router already covers scut; **wire** conductor/pigeonhole — do not ship mesh SDK.

---

## Scout results (system-run 2026-08-05)

| Step | Tool | Outcome |
|------|------|---------|
| Pull | `pull_mesh_comm_repos.sh` | 10 repos · `mine/raw/mesh_comm/_pull_manifest.json` |
| Steal | field-steal bitchat | 21 files · seat_routing×4 · memory_context×9 |
| Steal | field-steal bridgefy | SDK docs scanned |
| Steal | field-steal briar | 16 files |
| Pack | research-pack WHITEPAPER | `memory/research_packs/20260805T125145Z_*` |
| Scout | improve --once | candidates ranked · field_brief updated |
| Spores | FEATURE_COMPOSE | `docs/ref/spores/mesh/*.md` (3 cards) |

---

## Overlap decision

| Finding | Mag module | Decision |
|---------|------------|----------|
| Dual transport router | conductor + seat_playbook (draft) | **wire** |
| P2P/Mesh/Broadcast | pigeonhole + switchboard | **wire** docs/enum |
| Sync without server | beads/zeitgeist | **already** — document |
| BLE mesh SDK | — | **defer** v5+ after G4 |

**P3 verdict: WIRE ONLY — no implementation BUILD.**

---

## Routing matrix (filled)

| # | Goal | Expected | Actual | Match |
|---|------|----------|--------|-------|
| 1 | `doctor health status` | local/janitor | local ollama | ✓ |
| 2 | `mesh offline relay steer` | local/route | local ollama execute | ✓ |
| 3 | routing_smoke suite | 9/9 PASS | 9/9 PASS | ✓ |

---

## Training events

Emitted via `mesh_comm_ilap_run.sh`: `research_dive`, `ilap_cycle` → `memory/training/events.jsonl`

---

## Next (system — not operator)

- v4: `steward-mesh-digest` job (auto weekly)  
- v5: transport probe + preflight chip  
- Re-run: `./scripts/mesh_comm_ilap_run.sh`
