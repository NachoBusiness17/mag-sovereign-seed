# local_sovereign_agent — harness rules

**LLMs: load framework first → `docs/FRAMEWORK_LOAD.md`** (or repo root `LOAD.md`) · then **`docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md`** (compass)

This project is the **Mag Resource Harness** (standalone product home): local Ollama **janitors** first (`gemma:2b` scut, `gemma4` short worker), **remote specialist scarce** for hard inference, Hermes **dormant but dispatch-capable** (dispatch log active 2026-09-09, $220 armed — audit 2026-09-14), biographer + orchestrator. Warm boot: run `python -m mag.hermes_warm_boot` at session start to load chain tip + Vercel URLs + session brief into `memory/warm_state.json`. Vercel URLs may return 302 SSO redirects — verify with `curl -I` before reporting live.

**DNA:** residual + registry + leaf = filed workdays (`docs/DNA.md`). Lab is optional ops.  
**Zeitgeist:** beads (this repo) + forest (mycelial-republic) — `docs/archive/ZEITGEIST.md` (era 003: THE POUR; the `docs/ZEITGEIST.md` path cited before 2026-09-14 never existed). No core-mirror throne.

## Shared artifact boundary — every client

All durable cross-surface work lands on the shared inbox. A VS Code, Cursor, z.code, Grok, Codex, PowerShell, Linux, WSL, or OpenClaw-local session directory is cache only and must never be the sole copy.

| Context | Read first | Durable write root |
|---|---|---|
| Windows host / Mag venv | `watch\inbox\INDEX.json` | `watch\inbox\` |
| Docker / OpenClaw | `/board/inbox/INDEX.json` | `/board/inbox/` |
| WSL | `/mnt/c/Users/ESTATE_USER/Documents/projects/local_sovereign_agent/watch/inbox/INDEX.json` | same directory |

The machine contract is `watch/inbox/SHARED_SURFACE_CONTRACT.json`. Read the index, classify content before reuse, preserve hashes and bounded pointers, and leave a receipt before promotion. Model text can propose; only the switchboard/effect broker authorizes effects. Validate with `.venv\Scripts\python.exe -m mag.shared_surface validate`.

## 🖇️ Clippy — standing reminders (always-on, verkle-knotted)

> It looks like you're trying to work on Mag. Would you like a reminder? *(You do not have a choice. The rope is verkle-committed.)*

- **New window?** → execute the frozen spec: `/memories/session/next-window-handoff.md`. Design is done; this is **execution → LOW tier** (flash-off or local).
- **Tests:** 3,550 tests collected / 455 files (2026-09-30 census, `pytest --collect-only -q -p no:cacheprovider tests`, moment 2026-09-30T18:51Z (14:51 EDT), 26.31s, zero collection errors, receipt `watch/inbox/last_mile_20260930/B17_CENSUS.md`; the same-day 11:46Z carrier read 3,220 / 433 and the drift to 3,550 / 455 (+330 collected, +22 files) is attributed to the 09-30 midday/afternoon last-mile landings: the IMP+LM+AJ wave commit (e0ff8cec0, 14:29 EDT: anomaly flagger, estate_query corr_id joins, LDT near-miss arc, DFHack liquids+units) riding under 15 untracked working-tree test files (test_mountain_liquids, test_mountain_units, test_mountain_digflood, test_mountain_reveal, test_estate_query, test_anomaly_flagger, test_flock_positive, test_current_anchor_guards, test_effect_broker_ah18, test_ldt_nearmiss, test_ah4_rib_fixes, test_ah5_warmboot, test_rib_freeze, test_ask_bank, test_cost_rollup — counted by `git status`), plus committed same-day waves landing after the 11:46Z moment (AH19 amend-perf c1fb757da: test_ah19_append_leaves +14 byte-prefix tests; HISTORY PURGE 662dc739e: test_ah2_proof AH2 ed25519 + seal Merkle; also landed 09-30: test_ag5_tip_verify, test_burns_verdict_enum, test_concept_predictor, test_corr_id_ah14) and items landed inside existing files; file arithmetic: 440 committed + 15 untracked = 455 on disk; the same-day 11:46Z carrier (receipt `watch/inbox/last_mile_20260930/AG7_CENSUS_SEED.md`) had attributed its own drift from 2,436 / 371 to 3,220 / 433 to the 09-29-evening and 09-30 last-mile waves: MICKEY17 (328896fcb, tests/test_server_v0.py), THE COORDINATOR COMMIT (84811acb7, +17 test files incl test_gate_canary, test_gwap_to_gps, test_room, test_scarless_preflight, test_regen_front_door, test_receipt_xref_gate, test_census_zero_collect, test_duel_harness, test_ledger_registry, test_protocol_table, plus the entrypoint 2,757-collect fix), TIE-IT-ALL (579109f44, +12 test files incl test_gods_number, test_lane_budget, test_legality_dataset, test_verkle_dangling), WAVE X + X1 hydrology (f8452e01a + 6caa8ef3e: test_hydrology, test_dem_to_board, test_motion_rows, test_verdict_feed, test_propagator), Y11 (e74021078: test_verkle_restore_prep), V-WAVE (ff1c02822 + ac17d5da8: test_realmd_client, test_ldt_lattice, test_ldt_train, test_anticheat, test_chat, test_field_flow, test_innkeeper, test_percolator_z15, test_rollup_delta, test_section_stream, test_server_persist), full-stack W3/W4/LW4 (00daf9103 + d389326f0 + 70b781e84: test_k8s_water, test_worldgen, test_river), AC14 (7f3ed70e8: test_estate_cleanup), AD/AF last-mile (63f82eb12: test_env_contract), and items landed inside existing files; the audit's interim 3,192 predates the 09-30 morning landings; a 12:05Z probe of the still-moving tree read 3,217 collected + 7 transient collection errors with an 8-file zero-collect gap (7 mid-landing import errors + tests/test_selffeed_integration.py, the standing gap), full gained-file list in the receipt); the 2026-09-29 refresh had attributed its own drift to the 09-28 burn-wave landings and 09-29 wave5 in-flight files (receipt `watch/inbox/wave5_repair/patrol-fix.md`); the 2026-09-27 refresh had attributed its own drift to the 09-26/27 burn-wave test landings and the verkle99 landing tests/test_verkle_compaction.py (+1 file, +9 collected); the retired "1,341 tests / 264 files" headline was hand-copied, never byte-backed: the 09-14 trio 1305 passed / 34 failed / 9 skipped sums to 1,348). Run `pytest -q` before claiming done, file the real numbers, and never trust a hand-written count. **Census denominator law (B2-216):** a count is a snapshot of one tree at one moment, never a constant: "collected" (`--collect-only -q`) and "executed" (a `pytest -q` outcome sum) are different denominators from different instruments, and same-day collected exceeds same-day executed sums by the tests landed between the two moments (2026-09-26: census 1,837 at ~09:49 EDT vs executed sums 1,776 / 1,782 / 1,837 from three full runs; by ~10:04 the census already read 1,854 / 303 files). Name instrument, moment, and delta before comparing counts; never difference two counts taken at different moments. Receipt: `watch/inbox/burn_wave_20260926/B2_216_collect_delta_20260926.md`. **Trust bytes, not reports.** Census-carrier tripwire (B2-215, 2026-09-26): `tools/census_drift_patrol.py` flags this line when its census date is older than 7 days while `tests/` has gained files since that date (the retired 1,341 headline rode 12 days stale with 31 files grown and no gate noticed); WARN-ONLY at pre-push, flip-to-enforce is an operator call. Collected-count deep check (B2-244, 2026-09-26): file-growth signals are blind to items added inside existing files (parametrize, appended cases), so the opt-in `--collect` flag makes the patrol rerun `pytest --collect-only -q` itself and fail exit 1 when this line's collected claim is 20 or more off the byte truth in either direction; kept out of the default pre-push path because it needs the venv. **Carrier shape law (B2-249, 2026-09-26):** the census claim on this bullet must keep the exact grammar "N tests [collected] / M files (YYYY-MM-DD census" because `tools/census_drift_patrol.py` `parse_carrier` reads the counts and census date only from that parenthesized clause shape and fail-closes exit 2 with the "need the claim shape" message on any bullet edited to other grammar, so rewording the claim breaks the gate instead of silently rephrasing it. Scheduled deep check (B2-246, 2026-09-26): the `--collect` deep check runs daily on the MagCensusPatrolDaily task at 08:30 (`scripts/census_patrol_daily.ps1`, registered by `scripts/register_census_patrol_task.ps1`, log `logs/census_patrol.log`); on COLLECT-DRIFT or STALE (exit 1) the operator refreshes this bullet's claim from a fresh `pytest --collect-only -q` and names the landings that moved the count (an unattributable drift is a fabrication smell: investigate before refreshing), and on a cannot-verify exit (exit 2) the operator treats it as an incident and fixes the collection error the log names.
- **Deliberate-ask:** strong asks = frozen RIB (system+bootloader+manifest+verkle tip) + small ask + output contract + quantize target. **Pay the context tax once.**
- **Thinking-mode is the axis** (not flash vs pro) — tune it before tier (design_vague proved it).
- **Pile habit:** escalation/session-close → `mag.state_snapshot.capture_summary`; overnight → `main.py pile-classify`. Contribute your state summary before you go.
- **Tier ladder:** ollama → free tiers (gemini/groq/z.ai…) → deepseek flash → pro/grok (only judgment climbs).
- **DRIVING LADDER (2026-09-28, operator, code-as-law — supersedes the tier-ladder line above; 2026-09-29 SPEND amendment):** ONLY Hermes is funded ($180 Nous credits: glm-5.3-prime / qwen3.8-max-prime = the workhorse+judgment tier; Anthropic keys in .env are UNFUNDED, no Opus rung) AND grok-4.7 is funded on the xAI SD account (XAI_SD_API_KEY, 13 models live-verified 09-29). SENSING stays free-lane; JUDGMENT dispatches to the primes or grok-4.7 by default - hoarding funded budget while free lanes grind is the 03:00Z drain bug in money form (operator order: "USE IT I WANT YOU TO SPEND MONEY"); every paid dispatch banks usage in its receipt. Receipt: memory/rib/RIB_DRIVING_LADDER_20260928.md addendum + watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md. Free stealth lanes are a SENSING surface only — their outputs are banked as findings, never as done/trusted work; verification climbs to the funded tier. **REMEMBER BEFORE RUNNING:** warm the ribs (`memory/rib/`, esp. RIB_FREE_USAGE_POLICY_20260823 + RIB_DRIVING_LADDER_20260928) and current state before building any mechanism — the estate has already solved most of what a fresh seat is about to hand-roll. The operator must never have to re-teach a law the ribs hold: boot-order is load ribs → load state → then act. Receipt: `memory/rib/RIB_DRIVING_LADDER_20260928.md`.
- **Fan-out width law (dispatch shape is the retry strategy):** on `account:zai-individual-coding-plan` the cap lives on the dispatch shape, not on width alone. Workflow children get `maxAttempts 0` (zero adapter retries, die on the first 429/1302; a 50-wide workflow dig on this account 429-storms it and crashes tethered sessions with fake "subscription" errors), so keep workflow `max_concurrency` at 3 or less; Task agents ride the main-session retry path (`maxAttempts 11` + driver backoff) and measured clean at widths 3, 6, 10 and 12, width 10 banking 109.4M tok/h with zero surfaced 1302s (the 15-16 rung stays untested; after a burst even 12 takes 1302s until the window decays; the limit is rolling throughput, not width-only). Receipts: `corpus/steal/TETHERED_LINK_STEAL_20260925.md`, `watch/inbox/GALA_20260925.md`, `watch/inbox/burn_wave_20260926/B2_25_envelope_remeasure_20260926.md`. Proven-width table + the full source-cited contract (workflow-child failure census included): `watch/inbox/gala_20260925/AFTERPARTY_CLOSE_20260926.md` B2-476 amendment + `watch/inbox/burn_wave_20260926/B2_443_dwf_error_census_20260926.md`.
- **Max-concurrency standing law (2026-09-26, operator):** the measured envelope supersedes the 3-cap conservatism: 5 concurrent gated workflows at `max_concurrency` 10 each (50 workflow children) plus the hourly burn cron plus offpeak tasks ran clean for hours; the first rate-limit contact at that shape is a HOLD signal (children retry 429/1302s internally, nothing lost), not a width cut. **Maintain this shape usefully from now on:** every window keeps its lanes at max concurrency on demanded work, dogfoods the fleet's own tools (gate, drift, graders, checkers) every wave, folds a self-improvement from every wave into the manifest, routes overflow to free lanes when the account caps (offpeak queue, Hermes/Nous credits per LAW-11), and keeps the seat token-maxed on useful work. First-contact receipt: `watch/inbox/ENVELOPE_50W_HIT_20260926.md`.
- Invocable: `python main.py clippy` · full doctrine in repo memory (DELIBERATE-ASK · PUPPETEER GAUNTLET · PILE).

## Load order (agents — do not skip)

| # | File | Why |
|---|------|-----|
| 1 | `docs/FRAMEWORK_LOAD.md` | Navigation, metaphors, use cases, commands |
| 2 | **`docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md`** | **Compass** — vision, agent loop, v1–v10 arc, sovereignty |
| 3 | **`docs/ref/MYCELIAL_SCIENCE_MAP.md`** | **Biology ↔ protocol** — mycelial science map |
| 4 | `docs/ref/MAG_DIRECTION_ARTIFACT_v2.md` | Phase gates, v3–v5 mold |
| 5 | `docs/ref/MAG_PROJECT_PROPOSAL.md` | Problem depth |
| 6 | `docs/ref/OPERATOR_CARD.md` | FIND · FILE · LOAD |
| 7 | `AGENTS.md` | This file — env + commands |
| 8 | `mag.cmd context-pack` | Min-token pack for your seat |

Machine arc: `configs/version_roadmap.yaml` · Version index: `docs/ref/releases/VERSION_REGISTRY.md`

Then: `state/CURRENT.md` (live truth; `memory/briefs/latest.md` FROZEN 2026-09-26 and must not be consumed as live) · `queue/todo.md` · `HANDOFF_MAG_AGENT_TODOS.md` if implementing.

## When a specialist seat is used

- Prefer `memory/briefs/latest.md`, `memory/live_from_grok.md`, `memory/attention.md`, `queue/todo.md`.
- L2 escalate needs `[priority]` / `[L2]` (see `configs/lanes.yaml`) unless force.
- Mag escalations may call the harness or `queue/handoff/*.json` with **brief attached**, not full chat.
- Do not claim R0; T0/T1 stay local.

## Python env (do not skip)

**Default shell `python` is often Hermes** (`…\hermes-agent\venv\…`) — no Mag deps → `No module named 'langgraph'`.

Always use **this repo's** interpreter:

```text
mag.cmd doctor                # preferred (no PS execution policy issues)
mag.cmd context-pack
.\.venv\Scripts\python.exe main.py <cmd>
```

Repair / create venv: `powershell -ExecutionPolicy Bypass -File .\scripts\ensure_venv.ps1`  
Agents: call `.venv\Scripts\python.exe` or `mag.cmd`, **never** bare `python` on PATH (Hermes).

## Commands

```text
# fence-owner: operator - harness command card (AGENTS.md Commands section). FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
mag.cmd lab                   # product UI :8765 (+ flags for watch/mag)
mag.cmd dashboard             # UI only
mag.cmd brief                 # L0 dossier → memory/briefs/
mag.cmd ask "…"               # biographer Q&A local
mag.cmd mag --once            # companion cycle
mag.cmd watch                 # tail specialist sessions
mag.cmd run "goal"            # single graph job
mag.cmd context-pack          # min-token pack for TUI (bonds+brief)
mag.cmd bonds                 # residual next-session edges
mag.cmd improve --once        # daily scout + eval → memory/improve/
mag.cmd improve --status
mag.cmd promote --apply c-…   # human gate for candidates
mag.cmd research-pack …       # public URL → local pack
python main.py autorun --once --dry   # plan drainer (no execute)
python main.py verkle-audit --dry
```

**Metaphors + use cases:** `docs/FRAMEWORK_LOAD.md` §1–§3  
**Seats / habit:** `memory/improve/SEATS.md` · `memory/improve/HABIT.md`  
**Daily task:** `scripts\register_improve_task.ps1` → MagImproveDaily 08:00  

## Build discipline (landed 2026-09-25, recreated from ZCode's own source)

The seat's maker machine-enforces these; Mag now does too:

- **Spec before behavior change.** The doc/spec that owns a behavior is updated BEFORE the code that changes it. No orphan behavior.
- **No timeouts papering over sync problems. No fallback-branch creep.** Found a design defect → align and fix the design; never add another guard branch to mute the symptom.
- **Fix comments carry the receipt.** A bug fix's comment names the cause and the evidence it was fixed on — not just what changed.
- **Ratchet gate at pre-push** (`githooks/pre-push`): `python tools/violation_ratchet.py check --changed` over `mag/`+`tools/`. Registered debt passes; NEW debt blocks the push. Accept debt by NAME (`baseline-update --by <who>`) or fix it (`prune` recovers) — never loosen the hook. Register: `configs/violation_baseline.json`.
- **Scenario-suite gate at pre-push** (`githooks/pre-push`, B2-164 2026-09-26): a `tools/workflow_gate.py` change (working tree or pushed range) runs the LAW-12 card suite `python tools/workflow_gate.py check --scenarios configs/workflow_gate_scenarios` READ-ONLY; a red suite blocks the push the way the ratchet does. Operator response: fix the gate or re-prove the cards, never loosen the hook. Trigger is the gate script only; widening it to the card dir is an operator decision after the cards commit (they are untracked at landing and a sibling lane holds an active claim on one).
- **Workflow gate at submit** (`python tools/workflow_gate.py check --script <path>`): no ungated CreateWorkflow. The gate enforces dogfood: Mickey17 gopher fan-out (per-item named actors), interagent pass-off (outputs feed later asks), steering (reviewer feedback drives revision), incremental report() salvage, published deliverable, receipt landing in `watch/inbox/`, and the no-fabrication + em-dash laws inside the asks. Every check registers a row in `memory/workflows/REGISTRY.jsonl` (self-steal of the ratchet: exit-2 blocks, amend-not-rewrite, improvement is a ledger fact). Save gated workflows (`SaveWorkflow`) so reruns are amendments; the one-time user approval is the harness contract, the gate is what keeps it rare. Scenario mode (`python tools/workflow_gate.py check --scenarios configs/workflow_gate_scenarios`, landed 2026-09-26 per the LAW-12 genesis clause in `watch/inbox/BURN_rsi-harness_20260926.md`) re-validates the seven per-gate scenario cards READ-ONLY against real registry FAIL rows: run it after any gate change; the suite must stay green.
- **Boot freshness** (`python tools/freshness_check.py`): BOOT_4_7.md and the `state/` boot docs go STALE at >7d while the repo has a heartbeat — that is the stale-trap disease. Refresh the doc with today's truth or register it frozen with a reason+date.
- **Corpus FTS index daily (B2-465, 2026-09-26):** the FTS5 index behind corpus_search decays to scan fallback whenever catalog.jsonl moves past catalog/catalog_fts.sqlite; the B2-102 freshness gate only detects, it never heals. The MagFtsIndexDaily task (09:00 daily, scripts/fts_index_daily.ps1, registered by scripts/register_fts_index_task.ps1, log logs/fts_index.log) runs `.venv\Scripts\python.exe tools\corpus_fts_rebuild.py --check --deep`, rebuilds through the one sanctioned writer on exit 2, and alerts to memory/attention.md only when exit 2 survives the rebuild attempt or the rebuild itself fails. Routine stale-then-fresh needs no operator; an exit 2 after a rebuild is an incident (inspect the log JSON note naming mtime, catalog_bytes, or deep sha256, verify catalog integrity, rerun by hand); no START stamp for today in the log means the surface is dark (schtasks /Query /TN MagFtsIndexDaily, re-register, run by hand).
- Receipts: `corpus/steal/ZCODE_RATCHET_LANDED_20260924.md` · map: `corpus/steal/ZCODE_REPO_STEAL_MAP_20260924.md`
- **Running workflows / hooks on this harness?** Read `corpus/steal/ZCODE_OPERATING_PLAYBOOK_20260925.md` first — cache, compaction, and hook-contract laws verified against the harness's own source (byte-identical asks for cache hits, amend-don't-resume, exit-2-only hard blocks, yolo bypasses disallowedTools).

## Constitution

See `CONSTITUTION.md` → mycelial-republic `docs/CONSTITUTION.md`.
