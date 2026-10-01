# One-pager: Seat economics

**Commitment:** `mag-seat-economics-001`

## Goal

Internal map of **real cost per platform** and **value per outcome** — forecast before spend, reconcile after.

## Loop

```text
route.task_estimate → spawn → provider_usage.jsonl → queue terminal + leaf → cost_ledger → seat_economics_map (weekly)
```

## task_estimate.v1 (on route.v2)

- `depth`, `phase`, `context_need_tokens`, `output_tokens_est`  
- `price_band_usd` (from `configs/cost_rates.yaml`)  
- `confidence: heuristic` — not ML on day one  

## cost_ledger.v1 (at terminal)

Join: `queue_id`, `task_id`, `session_id`  
Fields: estimate vs actual tokens/USD, `leaf_kind`, `waste_kind`, `seat_efficient` label  

## Platform map (posterior)

Weekly rollup: median USD per build/scut, estimate error, waste rate when misrouted  

**Prior** = operator edits `cost_rates.yaml` · **Posterior** = ledger medians · **Hints** = promote-gated

## Routing for value

| Job | Prefer |
|-----|--------|
| scut | Ollama ($0) |
| build | DeepSeek if window fits |
| plan | Grok TUI + `[priority]` only |
| audit | Cursor when fixed cost amortizes |

**Value** = outcome / all-in USD — not cheapest tokens alone.

## Exists today

`record_usage`, `provider_usage.jsonl`, `cost_simulator` — **gap:** no estimate↔actual join

## Full spec

`MAG_V4_CONDUCTOR_LOOP_DRAFT.md` § Seat economics map
