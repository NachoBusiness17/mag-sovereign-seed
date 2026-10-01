# TOKEN RENDER MANAGER — REBUILD SPEC (2026-08-27)

Operator's ask: "deep research, self-steal external practices, help me rebuild."
This is the rebuild design for the token render-farm: fan-out N cheap concurrent calls,
verify K-of-N, route by live $-per-verified-task. Two independent analyst passes ran
(deepseek-research + groq/gpt-oss-120b, both in memory/research_packs/20260827_*); their
DISAGREEMENTS are tri-stated below rather than averaged (roshomon law).

---

## WHAT THE EXTERNAL WORLD DOES (tri-state)

### 1. Batch APIs — cheap, slow, cache-compatible
- OpenAI Batch: 50% off, 24h window [Supported - public docs]. Cache stacks → ~75% off cached input.
- Anthropic Batches: 50% off, cache_control works inside batch (0.1x reads stack).
- **Steal**: batch is for PRE-COMPUTE only (synthetic evals, digest backfill) — never the
  interactive path. Our swarm queue is already batch-shaped; we just never priced it as such.
- Witness conflict: groq witness claimed 10-15% discounts — DISPUTED vs deepseek's 50%
  (public docs favor 50%; treat 50% as working number).

### 2. Prompt-cache discipline — our FROZEN_RIB doctrine is confirmed best practice
- Byte-frozen system prompt + static tool schemas + dynamic-tail-only = the reported recipe
  everywhere; hit rates 90-99%. We run 96-99% (measured, on our ledger).
- Anthropic mechanics [Supported]: writes cost 1.25x, reads 0.1x, 5-min sliding TTL →
  batch your fan-out INSIDE 5-minute windows or you re-pay writes.
- DeepSeek disk cache: automatic, LRU, no TTL; docs say keep first ~1024 tokens stable.
- **What we add that nobody documents**: per-model cache health tracked in OUR ledger with
  prefix_prover drift attribution. External world infers hits from bills; we measure them.

### 3. Cascades / routers — real savings, known signals
- FrugalGPT: up to 98% savings at 95% quality [Supported - paper], needs a trained rejector.
- RouteLLM: ~85% savings, embedding-similarity router, +50ms latency.
- Signal set used industry-wide: difficulty estimate, confidence/logprobs, task type,
  latency budget, cost budget.
- **Steal**: route on $-per-VERIFIED-task (our ledger oracle), not capability guesses.
  Nobody in the public material uses their own usage ledger as the price oracle — that's
  our [ONLY-US] edge.

### 4. Fan-out with K-of-N verification — production-proven shape
- Industry scale: 5-10 parallel calls/task, majority vote or programmatic verify;
  Together/Anthropic/OpenAI internal evals all use this shape [Supported].
- Cost math worth internalizing: 3 cheap calls + escalation on 10% = ~0.4x the price of
  one expensive call, same quality floor.
- What breaks (both witnesses agree): vote deadlocks on genuinely ambiguous tasks;
  rate-limit amplification (fan-out multiplies request count N times against ONE lane —
  the exact z.ai pool-saturation we lived tonight).

### 5. Concurrency craft — the 429 taxonomy (directly validates tonight)
- Pool saturation vs key cap detection via response headers (`retry-after` length,
  `x-ratelimit-remaining`) [Supported pattern]; adaptive buckets reduce 429s 80-90%;
  full jitter mandatory; circuit breaker at ~5% error rate for 30s.
- **Tonight's live confirmation**: z.ai glm-4.7-flash global pool saturation looked
  identical across six keys — header-based key-cap logic would have MISERRED it; only
  cross-key probing identified pool saturation. Steal the header heuristics AND keep our
  cross-key probe as the arbitration layer.

---

## THE REBUILD — five components, everything rides existing bone

### R1. models/fanout_router.py (~200 lines, NEW)
- Input: job spec {goal, fanout_n, k_of_n, max_cost_usd, tier}.
- Reads logs/provider_usage.jsonl → live table of {lane, model}: $/task, cache-hit %,
  error rate, p50 latency (7-day window). Chooses the cheapest lane meeting the health
  floor (error <5%, hit >80%). Re-probes on dispatch failure (the dead-by-probe rule).
- Escalation ladder per FrugalGPT hybrid: flash lanes → groq → deepseek-chat → frontier.
  Escalate only when K-of-N fails after verification.

### R2. Job spec v1 (extend swarm_worker.enqueue_task)
- Fields added: fanout {n, k, strategy=majority|verifier}, verify spec (schema/regex/
  judge-lane), deadline. Backward compatible — old specs still drain unchanged.

### R3. Verification pass (mag/work_register tri-state, already built)
- Programmatic first (schema/regex — free), then judge-lane second (groq gpt-oss-120b),
  K-of-N quorum last. Every shard returns its claim; the compositor writes the merged
  verdict + spend back to the ledger → closes the pricing loop (ledger = price oracle).

### R4. Concurrency governor (extend models/providers.py)
- Per-lane adaptive bucket with full jitter; header-based pool-vs-key classification;
  circuit breaker (5% errors/60s → lane parked 30s); nightly saturation map written to
  state/ (epoch-window input). The 1305 storm becomes remembered weather, not surprise.
- **BUDGET-PROJECTION UPGRADE (2026-08-27, research note
  `docs/ref/RESEARCH_NOTE_FLYWHEEL_BUDGET_PROJECTION.md`):** model every
  lane/seat/box as a node with a per-node coupling budget ($/hr, tok/hr,
  concurrent calls) and make each allocation step an exact projection onto the
  budget polytope (symmetric-Frobenius projection, KKT-exact dual root-finder).
  Consequence: allocation provably descends a Lyapunov function — no oscillation,
  no thrash, and the "orphaned buyer loops spawned five boxes" failure class
  (2026-08-27, $0.53/hr silent bleed) becomes structurally impossible. Same math
  governs the vast buyer (one-instance cap + spend rails are polytope constraints).
  Start with exact projection over lane budgets; add oscillators never — the shape
  is the steal, not the domain.

### R5. Pricing surface (dashboard tile + hourly knot note)
- Live $/1K verified tasks by lane from the ledger; today's spend; projected EOD. The
  operator reads prices like a wallboard, not an audit.

---

## BUILD ORDER (each lands independently useful)
1. R4 governor (stops the bleeding; feeds R1 data) — smallest, first.
2. R2 job fields + R3 verification wiring on existing queue (fan-out usable by hand).
3. R1 router reading the ledger (automates choice).
4. R5 wallboard (visibility).

## WHAT THIS FEEDS
- Epoch 2: High arms ride R4's healthy lanes automatically.
- The method post: "we sharded a render job across 40 dumb models and paid pennies;
  here is the router that made it boring" — receipt-first arc continues.
- Rocinante: this router IS the conductor layer's request broker; moving it to the
  Studios later is a config change, not a rewrite.

*Research receipts: memory/research_packs/20260827_fanout_router_state_of_art.md (+witness).* 
