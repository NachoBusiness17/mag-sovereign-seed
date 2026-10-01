# VAST.AI API EXPERT REFERENCE — the workhorse's manual (v0, 2026-08-27)

Companion to `docs/ref/ZAI_API_EXPERT_REFERENCE.md` (the brain's manual). Division
of labor per operator: **vast = the workhorse** (cheap dedicated silicon for local
models, swarm hands, burns), **z.ai = the brain/orchestra layer** (judgment, cache-
mined frontier API). Read this before any vast automation. Sources: official docs
(docs.vast.ai, fetched 2026-08-27) + our own live API probes (state/vast/).

## Auth
- `Authorization: Bearer $VAST_API_KEY` on every call. Key in `.env` as
  `VASTAI_API_KEY`. Account: nachobusinesscorp@gmail.com, user id 170099.
- **Money lives in `credit`, not `balance`.** `GET /users/current/` returns both:
  `balance` = cash (we hold $0), `credit` = prepaid (we hold ~$48.50). Spend math
  MUST read `credit`. Zero funds → instances auto-stop, GPUs released; without a
  card on file, data is scheduled for deletion. `total_spend` is negative-of-credit
  style (weird, trust credit).

## Two API generations live side by side (both work as of 2026-08-27)
- **Legacy (what our scripts use):** `GET /api/v0/bundles/?q=<URL-encoded JSON>`,
  `PUT /api/v0/instances/?id={offer_id}`.
- **Current docs:** `POST /api/v0/bundles` with filters in the JSON BODY (each
  value an operator object), create via `PUT /api/v0/asks/{offer_id}/`.
- Lesson (self-steal + live): docs rotate; **probe before trusting any endpoint
  shape**. Our working receipts: GET-bundles-with-q, PUT-instances-with-id,
  DELETE `/api/v0/instances/{id}/`, GET `/api/v0/instances/`.

## Search (find offers = "bundles")
```
GET /api/v0/bundles/?q={"num_gpus":{"eq":1},"gpu_name":{"in":["RTX 3090","RTX 4090"]},
     "gpu_ram":{"gte":24000},"cpu_ram":{"gte":100000},"disk_space":{"gte":150},
     "rentable":{"eq":true}}
```
- Operators: `eq, neq, gt, lt, gte, lte, in, notin`. The q-as-DSL-string form
  (CLI syntax) returns 400 "q must be valid JSON" — always JSON.
- Defaults: `verified eq:true`, `rentable eq:true`, `rented eq:false`.
- Sort client-side: `reliability2: None` values break naive sorts (learned live).
- **Unit trap: `gpu_ram` is MB in REST** (24576 = 24GB) but GB in the CLI.
- Useful filters: `reliability2, inet_down/up (Mbps), inet_down_cost/up_cost
  ($/GB), storage_cost ($/GB/mo), disk_bw, gpu_mem_bw, compute_cap (×100),
  cuda_max_good, pci_gen, pcie_bw, min_bid (interruptible floor), geolocation,
  dlperf_per_dphtotal (value score), direct_port_count, static_ip, datacenter,
  host_id, mobo_name` (same physical host often relists under several ids —
  dedupe by host_id+mobo when bargain-hunting).

## Offer fields that matter (response `offers[]`)
- `dph_base` GPU-only rate; **`dph_total` = the real number** (GPU + storage +
  bandwidth allowances baked in); `dph_total_adj`/`discounted_dph_total` for
  reserved/credit discounts. `min_bid` = floor for interruptible bids.
- `reliability2` = historical uptime 0..1. CLIENT-SIDE filter (None breaks sorts).
- `duration` = how long continuously rented (seconds) — proxy for "stable host".
- `storage_cost` — the hidden fee, $/GB/MO, billed **while the instance exists,
  running OR stopped**. ~$0.10/GB/mo typical ⇒ 100GB model ≈ $0.014/day.
  Stop-vs-destroy rule (ours): stopped >24h with no next-use plan = destroy.
- `inet_up_cost / inet_down_cost` $/GB — egress is the usual surprise bill;
  a 100GB model pull matters (see internet_down_cost_per_tb ~$1-5/TB).
- Interruptible ("bid") instances: 50-80% cheaper, preemptible by higher bids.
  Our take: WRONG for the rehearsal (receipts need uptime) but right for
  stateless burns — bid at min_bid, expect preemption, save 50%+.

## Create / lifecycle
```
PUT /api/v0/instances/?id={offer_id}      body (all optional except image):
  {"image": "ollama/ollama:latest",       # required (or template_hash_id)
   "env": {"OLLAMA_HOST":"0.0.0.0:11434", "-p 8000:8000":"1"},
   "onstart_cmd": "apt-get update && ...", # runs after vast entrypoint init
   "disk": 40,                            # GB, default 8 (storage billed!)
   "label": "sancho-rehearsal",
   "runtype": "ssh_direct"|"ssh_proxy"|"jupyter_direct"|"args",
   "target_state": "running"|"stopped",
   "price": <bid $/hr>,                   # interruptible only
   "vm": false, "image_login": "-u user -p token", "cancel_unavail": true}
→ response: `new_contract` (new docs) / `new_instance_id` (legacy).
GET  /api/v0/instances/            # list (instances[].id, actual_status, public_ip, ports)
GET  /api/v0/instances/{id}/       # detail incl. ssh_url/port after boot
PUT  /api/v0/instances/{id}/       # {"state":"stopped"|"running"|"reboot"} or {"label":...}
DELETE /api/v0/instances/{id}/     # DESTROY — the only thing that stops storage billing
```
- Errors: 400 invalid json body; 404 "Invalid user key" (also returned by wrong
  path shapes — distinguish auth vs endpoint by testing GET /users/current/).
- Boot takes minutes; poll `actual_status` until `running`, then read ssh port.
- Billing is **per second** of runtime.

## Buying discipline (our rails, live in state/vast/launch_vast.py)
1. Never launch if credit < $10; hard destroy at $45 spend ($50 allocated).
2. One live instance max (duplicate boxes = duplicate bleed).
3. `actual_status` polling before SSH; never leave a GPU idling (destroy after use).
4. Watch-only until 24h feed (2026-08-27 order): `watch/vast_bargain_loop.py`
   `BUY_ARMED` flag + `state/vast/market_watch.jsonl` is the price memory.

## DOCTRINE — why this box (operator's frame, 2026-08-27)
- **Compute ladder:** free API tiers → cheap rental (vast) → Rocinante (owned,
  Oct 27). Vast is the rehearsal that makes Rocinante's runbook already-written.
- **Brain/workhorse split:** z.ai stays brain/orchestra (judgment, cache-mined
  frontier, MCP senses); vast runs the HANDS — local Qwen-class models, GPU
  burns, k3s/rib_k8s playground. Judgment stays API-priced; bulk moves to
  per-second silicon.
- **Gatekeeping bypass, the honest version:** hosted models have behavior
  guardrails; locally hosted "abliterated"/uncensored weights don't. Our use is
  our own swarm's work (riddler-protocol encoded — surrogate stories, seeded
  per-model faces, plaintext never leaves the box). The box runs the models as
  REAL-TIME SKILLS the swarm can consult via the riddler pipeline — no
  provider, no log, no gatekeeper between ask and answer.
- **Isolation law stands:** the box ships .env-LESS; local model needs zero keys;
  one groq key = whole secret surface; memory syncs as riddler-encoded maps on
  an encrypted volume. "A .env-less box is a box that can't leak anything that matters."

## Open / unproven
- Exact per-GB storage and per-TB bandwidth rates: host-specific, read them from
  each offer (`storage_cost`, `inet_*_cost`) — never assume.
## CLUSTERS + MULTI-NODE (operator lead 2026-08-28 06:30Z, researched 10:5xZ by zcode-tick)

- **The Clusters PRODUCT is sales-gated, not API**: vast.ai/products/clusters offers
  "dedicated GPU/CPU configurations" via contact-sales + guided setup — no public
  pricing, no API endpoint. Self-service cluster contracting: Unproven (likely absent).
- **`cluster_id` exists ONLY in the search-offers RESPONSE** (null in docs example),
  never as a request filter — the cluster concept is embryonic in the public API.
- **The self-service multi-node path TODAY** (all Supported, in docs):
  (a) same-host colocation — `rented:eq true` + group by `machine_id` ("useful for
  finding offers on machines you're already renting"); intra-host interconnect is
  queryable via `bw_nvlink` (GB/s); `gpu_frac` < 1 signals shared-host offers.
  (b) overlay networks — docs.vast.ai/multi-node-training-using-torch-nccl: instances
  on DIFFERENT MACHINES on the same physical LAN share a private virtual network.
  This is the documented sharding substrate (the economist's WAN objection dies at
  same-LAN granularity).
- **Same-LAN DISCOVERY gap**: no request parameter finds "machines on the same LAN";
  only same-host (machine_id). Workaround hypothesis: infer from datacenter fields in
  offers — Unproven, one probe away.
- k3s-lab revival path: one multi-GPU host via machine_id grouping (best RTT) or
  overlay-netted same-LAN instances (needs the discovery workaround). Covenant-gated
  until top-up: balance $39.31 vs $39 floor.

- `PUT /asks/{offer_id}/` RESOLVED 2026-08-28 (zcode-tick, live docs read): it is NOT
  legacy — it is the ONLY documented ask-acceptance endpoint (docs.vast.ai
  api-reference/instances/create-instance). The public docs sitemap (llms.txt) has
  ZERO CPU-tier pages: no CPU-specific contracting path exists in the docs. The
  08-28 CPU-blocking no_such_ask (7+ candidates) is therefore most likely STALE
  SEARCH INDEX / phantom asks (error text is "Instance type … not available" = 404
  availability failure; CPU at $0.011-0.014/hr rents in seconds), not an API-generation
  gap. $0 discriminator: contract a GPU ask via the same code path in the same minute —
  GPU accepts + CPU 404s = phantom asks; both 404 = path broken. Contract mechanics
  the rails should honor: success returns `new_contract` (the instance id — not `id`);
  `cancel_unavail: true` turns start-failure into a 410 auto-destroy; 401/403/429 also
  documented on this endpoint; SSH key must be registered before any `vm: true` create.
- Reserved-conversion economics (up to 50%) unexplored — relevant AFTER the
  pause-test verdict, if the box wins.

## PORTFOLIO ECONOMICS (the operator's correction, 2026-08-27 ~17:3xZ)

Per-lane $/M-token math was the wrong frame. The fleet buys WORK, not tokens.
Cost = ∫ over all tasks of min-price available lane, with swap latency as friction.
The stack, in allocation order (governor = fuel_feed evolved):

1. FREE TIERS (floor): flash pools, groq, grok, cerebras — $0 marginal, rate-limited.
   Absorbs the judgment floor and overflow-light. Never the grind (they choke).
2. ALWAYS-ON BOXES (base load): 1-2 cheap instances ($60-180/mo total) eating the
   24/7 grind — drains, scribes, burns, k3s playground. Flat rate, fed to saturation,
   shared-prefix served (SGLang). This is where the per-second meter is cheapest.
3. BURST BOXES (spikes): fan-out surges spin EXTRA instances per-second. A 100-way
   kabuki for 2 hours on 4 burst boxes ≈ $1. Spin, burn, destroy (storage law).
   Elastic ceiling: capacity stops being a quota and becomes an hourly decision.
4. MODEL SWAP at need: same box, different weights per workload class — vision model
   for eye-batches, 30B-A3B for grind, big MoE for the heavy lane. Weights staged on
   disk (storage fee ~$0.014/day/100GB) make swaps minutes, not downloads.
5. HOSTED PAID (last resort): judgment class only, cache-primed, when 1-4 are
   dry or the task is genuinely frontier.

Why this beats every pure play: free tiers alone choke at swarm volume; pure vast
bleeds on idle + can't do frontier; pure hardware is dead capex between burns.
The blend's marginal cost curve is the ENVELOPE of all four — always the minimum.

Subsystem mapping (already built, just needs to be wired as ONE allocator):
fuel_feed lane rotation → portfolio allocator · zcode tick → demand forecast ·
OpenClaw/MCP :8765 → the router front door · market_watch.jsonl → box price feed ·
provider_usage ledger → gstd proof-of-cost receipts · mag-worker drains → the load.

GSTD tie: the treasury allocates finite units across this portfolio; every second
on a box arrives with its price attached (native receipt); hosted calls carry ours.
Two witnesses, one ledger — gstd units get their exchange rate from exactly this.
