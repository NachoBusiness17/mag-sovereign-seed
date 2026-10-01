# Mag — Seat intelligence registry (planning draft)

**Status:** Planning — educated inference without mandatory self-test  
**As-of:** 2026-08-05  
**Commitment:** `mag-seat-intelligence-001`  
**Parents:** `SEATS.md` · `seat_economics_map` (v4) · `MAG_STEAL_AUTOPILOT.md` · `configs/cost_rates.yaml`

**Read when:** you want **which model for which task** from **public priors + your ledger**, not running a full eval farm.

---

## North star

> **Other people's data sets the prior. Your ledger sets the posterior. Routing scores seats — you don't A/B every task by hand.**

You are **not** trying to reproduce LMSYS on your laptop. You are building a **playbook + scorer**:

1. **Ingest** public signals (pricing, context windows, community tips, vendor docs, improve scout URLs).  
2. **Store** structured **seat cards** (capabilities, sweet spots, anti-patterns, tips).  
3. **Score** each `(task, seat)` at route time with **prior + optional local evidence**.  
4. **Update** posterior when `cost_ledger` / outcomes file — no extra test harness required.

---

## Three layers

```text
┌─────────────────────────────────────────────────────────┐
│  L0  PUBLIC PRIORS     configs/seat_playbook.yaml       │
│      + improve scout field briefs (cited URLs)          │
├─────────────────────────────────────────────────────────┤
│  L1  INFERENCE         mag/seat_score.py (v4)           │
│      task_estimate + seat_score → route.v2 hint         │
├─────────────────────────────────────────────────────────┤
│  L2  YOUR POSTERIOR    memory/improve/seat_economics_map │
│      cost_ledger.jsonl · optional thumbs on outcomes    │
└─────────────────────────────────────────────────────────┘
```

| Layer | Source | Updates |
|-------|--------|---------|
| Prior | Web, papers, blogs, pricing pages | improve scout + manual promote |
| Inference | Rules + weights in playbook | promote gate |
| Posterior | Your usage + leaves | automatic weekly rollup |

---

## Seat card schema (`seat_card.v1`)

One card per **seat** (not just model id) — e.g. `deepseek_api`, `cursor_cloud`, `grok_tui`, `ollama_gemma4`, `cursor_composer` (this agent).

```yaml
id: deepseek_api
class: engine          # engine | ide | local | human
provider: deepseek
billing: per_token     # per_token | subscription | fixed_per_run | free_local

capabilities:
  context_tokens: 1000000
  tool_use: strong
  multi_file: good
  planning: medium
  local_repo: via_mag_agent

sweet_spots:           # task types — from PUBLIC data + your notes
  - hard_code
  - build
  - long_context_impl

avoid_for:
  - scut
  - plan_without_spec
  - secrets_t0

tips:                  # operator + community distilled
  - "Freeze BUILD on disk first — else replan tax"
  - "Use mag agent --provider deepseek, not raw chat"
  - "One goal per orchestrator queue row"

public_prior:          # educated guess — cite, don't pretend you benchmarked
  sources:
    - url: https://api-docs.deepseek.com/...
      note: context window claim
    - url: https://...
      note: community: strong on code, weak on prose plans
  confidence: community_hearsay | vendor_doc | benchmark_table
  last_reviewed: 2026-08-05

economics_prior_usd:   # from cost_rates.yaml
  input_per_m: 0.28
  output_per_m: 0.42

posterior:             # filled by seat_economics_map rollup
  n_local_samples: 0
  median_usd_per_leaf: null
  seat_efficient_rate: null
```

**Cursor / Composer / cloud agent** get cards too — `billing: subscription + fixed_per_run`, tips about RUN discipline, hooks, queue mode.

---

## Task → seat inference (no mandatory test)

At route time, score each eligible seat:

```text
score(seat, task) =
    w1 * prior_fit(task.type, seat.sweet_spots)
  + w2 * prior_avoid_penalty(task, seat.avoid_for)
  + w3 * context_fit(task.context_need, seat.context_tokens)
  + w4 * economics(task.price_band, seat.economics_prior)
  + w5 * posterior(seat, task.type)   # 0 until ledger has n≥5
  + w6 * budget_ok(seat.provider)
```

**Output:** ranked list + `route_hint` string for pack — not a single oracle.

**task.type** from existing `classify_depth` + conductor `phase` + tags (`[build]`, `[steward]`, `[priority]`).

No pytest required. Optional: if you **did** run tests, bump posterior weight.

---

## Where public data comes from (already in Mag)

| Source | What it feeds |
|--------|----------------|
| `configs/improve.yaml` rotation Thu | openrouter, deepseek, xai URLs |
| `AGENTIC_LANDSCAPE_2026.md` | contract steals + gap notes |
| `MAG_STEAL_AUTOPILOT.md` | who to rob |
| `MODEL_TESUJI.md` / FEATURE_COMPOSE | model signal cards |
| Vendor pricing pages | `cost_rates.yaml` |
| Reddit/HN/GitHub scout | tips → improve candidates → playbook |
| Cursor blog (swarm economics) | seat economics priors |

**Steward job `steward-seats` (new):** weekly clerk pass — 3 URLs → diff against playbook → **draft** card updates (promote gate).

---

## Record of "all of them"

```text
configs/seat_playbook.yaml          # priors + tips (promote-gated)
memory/improve/seat_cards/        # optional one md per seat for long form
memory/improve/seat_economics_map.json   # your posterior
memory/actors/engines/              # per-engine facts + amends (tips as facts)
logs/provider_usage.jsonl         # raw actuals
```

**Office / pack bond (target):**

```text
## Seat pick (inference)
task: build · 45k ctx · recommend deepseek_api (0.82) · avoid grok (plan without [priority])
tip: freeze BUILD first — see seat_card deepseek_api
```

---

## Including VS Code Copilot + DeepSeek V4 BYOK

Card id: `vscode_copilot_deepseek`  
Runbook: `docs/ref/VSCODE_COPILOT_DEEPSEEK.md`  
Extension: `Vizards.deepseek-v4-for-copilot` — DeepSeek in Copilot Chat model picker (same API models as Mag `deepseek`). Interactive IDE only; headless drain stays `deepseek_api`.

---

## Including "you" (Cursor cloud / Composer)

Card id: `cursor_cloud_agent` (or `cursor_composer`)

| Field | Value |
|-------|--------|
| sweet_spots | multi_file, PR integration, audit diff, frozen RUN execution |
| avoid_for | improve 24/7 drain, scut, re-planning without spec |
| tips | one RUN one branch; read onepagers; mag_kill during debug; never bare python |
| billing | subscription + ~$0.50/run marginal (operator guess) |
| public_prior | Cursor agent-swarm economics blog; multi-file strength (vendor/community) |

Actor memory `engines/cursor/` stores **your** learned tips with `source.ref`.

---

## What you don't have to do

- Run full eval suite per model per task  
- Trust chat claims ("I'm best at code")  
- Auto-promote playbook changes from scout  

## What you do

- Keep playbook **small and cited**  
- Let ledger **slowly** override priors when n_samples enough  
- Promote card changes when steward drafts look right  
- Use `cost-sim` + `seat_score` before expensive waves  

---

## Build order

| # | Deliverable |
|---|-------------|
| I1 | `configs/seat_playbook.yaml` — 6–8 cards (ollama, deepseek, grok, cursor_ide, cursor_cloud, hermes_parked) |
| I2 | `mag/seat_score.py` — prior-only scorer (no ledger yet) |
| I3 | Wire hint into `route.v2` as `seat_recommendation` |
| I4 | `steward-seats` improve job — scout → draft card diffs |
| I5 | Posterior merge from `cost_ledger` when E2 ships |
| I6 | Office seat picker one-liner |

---

## Eval (lightweight — not a test farm)

1. Given `task.type=scut`, top seat is ollama — always  
2. Given `[priority]` plan, grok recommended but `executable: false`  
3. Given build + 400k ctx need, deepseek beats grok on score  
4. Posterior with n=0 → prior only; routing still deterministic  
5. Card tip appears in pack when seat within 0.1 of winner  

---

*Planning only — playbook edits = promote gate. Link from seat economics § in MAG_V4_CONDUCTOR_LOOP_DRAFT.md.*
