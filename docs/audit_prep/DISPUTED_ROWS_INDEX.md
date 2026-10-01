# DISPUTED ROWS INDEX — audit reference

Cross-reference of pre-emptive answer claims (disputed rows with consequences).

| ID | Claim | Status | Evidence Path | Current State |
|---|---|---|---|---|
| DR-01 | Sep-6 chain-stop: tip root mismatch (`a57b50f312470e42` vs `8bd588968c0bbfaf`) froze chain at index 7376 | **SUPPORTED (healed)** | `memory/biography/verkle_chain.jsonl` (7,924 rows, zero parent breaks, tip root matches) | Repaired 2026-09-13 via `repair_tip_if_consistent()`; backup `verkle_tip.json.bak-poison-20260913T022403Z` |
| DR-02 | Recount: 21,479 orphan knots vs 7,359 chained (28,838 total) | DISPUTED | `dashboard/static/index_data/orphan_ledger.json` (generated 2026-09-09T16:18Z); `memory/vault/astra_v2_companions/failure-ledger-recount.json` | 24,854 = `distinct_raw_row_hashes` for `run_shell:c73866f2f1b5` signature (706 sessions), NOT chain leaf count. Chain has 7,924 leaves. No discrepancy. |
| DR-03 | Twelve-ledger consolidation: ONE typed loom ledger replaces twelve proposed siblings | **DISPUTED (metaphor, not migration)** | `watch/GROUNDING_WAVE.jsonl` row 2026-09-12T15:30:58Z (rope-and-loom metaphor); cited `dist_audit/.../packs/p80_loom3_20260912.json` does NOT exist in repo | No migration executed; "twelve ledgers" never existed as separate ledgers |

## Falsifier
- DR-01: Run `python -c "from mag.verkle_knot import _verify_chain_consistent as v; print(v())"` — returns `(True, 'chain consistent')` after repair
- DR-02: Count `memory/biography/knots/*.json` files, compare to `verkle_chain.jsonl` rows
- DR-03: Find executed migration from GROUNDING_WAVE.jsonl to typed loom ledger

## Tri-state Source
All three rows are recorded in `watch/CLAIMS_REGISTER.md` (C-09 references DR-01). The grounding_wave.md ledger enforces tri-state discipline with auto-demotion rules.
