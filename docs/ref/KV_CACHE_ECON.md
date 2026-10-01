# KV CACHE ECON — the layer under our lane economics (2026-09-07)

Operator: "kv cache we should be learning as much as we can... We need to understand."
Trigger: @akshay_pachaar's PagedAttention explainer. This is the seat's understanding pass —
what the KV layer IS, and why our measured numbers (F-W2's 778×, refeed_guard's 94%) look
the way they do from underneath. Mechanics tri-state: PagedAttention/prefix-cache behavior
SUPPORTED (public, well-documented serving-layer design since vLLM 2023); the z.ai-specific
internals UNPROVEN (we observe pricing/behavior, not their code).

## 1. What the KV cache actually is

Every token you've already processed has two vectors per layer — a **key** and a **value**.
Generating token N+1 means the new token's query attends over ALL previous tokens'
keys/values. Recomputing those for the whole prefix every step would be O(n²) work, so
serving engines keep them in GPU memory: the **KV cache**. It is the model's short-term
body — the computed residue of your exact context.

Consequences that matter to us:
- The KV cache is why a warmed prefix feels different from a cold one at the SERVING layer
  even before any provider cache discount: the attention work is pre-paid.
- Cache size scales with (layers × heads × context × bytes). Long context is expensive to
  KEEP, not just to fill. That's why providers price cached-input tokens cheaper and why
  eviction policy is an economics variable, not an implementation detail.

## 2. PagedAttention — KV memory as an operating system (the tweet's core, expanded)

Naive serving reserves ONE CONTIGUOUS slab per request sized for max_tokens (e.g. 4,096
slots on arrival). If the request stops at 40 tokens, the rest of the slab sits reserved
and never written — internal fragmentation. At scale, most GPU KV memory is dead air.

**PagedAttention (vLLM) borrows virtual memory from operating systems:**
- KV space is chopped into fixed-size **blocks** (like memory pages, e.g. 16 tokens each).
- A per-request **block table** maps logical token positions → physical blocks, scattered
  anywhere in GPU memory (like page tables mapping virtual→physical).
- Attention kernels read through the block table, so non-contiguity costs nothing.
- **Copy-on-write / shared prefixes**: two requests sharing a system prompt point at the
  SAME physical blocks until one diverges — then only the diverging tail is copied.
  Refcounted, exactly like fork() pages.

Results as-reported: ~near-zero waste vs 60-80%+ waste in contiguous reservation, and
much higher concurrency per GPU (more requests resident = more throughput).

## 3. Prefix caching — the provider's version of our warmed state

On top of paging, serving stacks keep a **prefix cache across requests**: if your prompt
shares a long identical prefix with a recent request (same system prompt, same tool
schemas, same conversation head), the engine reuses the computed KV blocks instead of
prefilling again. That's what provider UIs call "cache hit".

This is the substrate truth under our measured receipts:
- **F-W2 (cache identity, 778×/797×):** our warmed-cold replay timing gap IS the prefill
  skip. The 778× is not a vendor trick — it's the arithmetic of not re-running attention
  prefill over ~megabytes of sealed prefix. The vendor prices this as cheaper cached
  tokens; physically it's fewer FLOPs and no recomputation.
- **refeed_guard (94% refeed):** our batches are almost entirely prefix reuse — from the
  serving layer's view we are a shared-prefix workload with copy-on-write tails. The
  PagedAttention shared-prefix mechanism is exactly why our fan-out pattern is cheap:
  N workers sharing the fleet preamble are ONE prefix in physical memory until they diverge.
- **Worldline seed:** the seed's "warmed state" slab is a request to the provider's prefix
  cache to resurrect context. Vendor-native (the 94.3% spawn cache-hit the operator
  screenshotted on the Mickey-17 respawn) = the same mechanism, managed for us.

## 4. The operator's coinage: known-value cache

"Known value cache" — reading it as doctrine, not a typo: the KV cache is the layer where
what the model KNOWS about this conversation has a physical address and a price. Every
invariant we've been building maps onto it:
- trajectory tape = the record of how the cache got warm;
- refeed economics = the price of keeping it warm;
- continuity (W2) = whether the warm blocks are still OURS after a break;
- the 2.7% meta-context = the part of the prefix that steers all the rest (smallest
  slab, highest leverage per byte).

## 5. Literature (operator's feed, 09-07)

- **earendil.com/posts/prompt-caching/ — "Prompt Caching In Agents"** (via @xiaomovps,
  who calls it the best article for understanding why agents are designed the way they
  are): prompt cache, PREFIX STABILITY, cache hits — the exact mechanics §3 describes
  from our receipts. Prefix stability = our FLEET_PREAMBLE discipline formalized: the
  preamble is byte-stable so the shared prefix stays cacheable; any per-dispatch jitter
  in the head breaks the hit for everyone downstream. Read + verify against our meter.

## 6. Doors (not built, named)

- **KV-ECON meter**: extend cache_identity to log per-call cached-token pricing vs cold
  pricing — our own lane-level PagedAttention telemetry.
- **Shared-prefix fan-out probe**: measure whether 5-wide batches with identical preambles
  show hit-rate compounding on the provider meter (F-W2 at width 5).
- **Eviction watching**: the promo window's "94.3% at spawn" is eviction-policy evidence;
  track it daily across the Sep 3-20 window as a substrate-behavior series.
