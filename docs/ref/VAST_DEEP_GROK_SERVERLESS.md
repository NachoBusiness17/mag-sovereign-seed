# Vast.ai — serverless, volumes, reserved, host, templates

**Commitment:** `vast-deep-grok-serverless-001`  
**As-of:** 2026-08-27  
**Status:** Research brief from official docs (fetched 2026-08-27). Not a live probe. Marketplace rates float.  
**Job:** Exact platform capabilities for a GPU-swarm project: (1) serverless inference, (2) volumes, (3) reserved, (4) hosting your GPU, (5) template marketplace.  
**Companion:** instance REST/CLI workhorse = `docs/ref/VAST_API_EXPERT_REFERENCE.md`. Train pipe = `docs/ref/MAG_v5_VAST_TRAINING.md`.

**Index of truth:** https://docs.vast.ai/llms.txt

---

## 0. Swarm-shaped one-liner

Vast is a **marketplace of other people's GPUs**, billed **per second**, with **no serverless surcharge**. Serverless is an autoscaler that **rents ordinary marketplace instances** and routes inference at them. Volumes are **local to one physical machine**. Reserved is **prepaid discount on one instance, locked to that host**. Hosting is a **separate account**. Templates are **docker-run wrappers**; public ones earn **3% lifetime referral of spend**, not a template royalty.

If the swarm needs **shared disk across many boxes**, Vast volumes will not do it. Use S3/HF/cloud-copy, or clone volumes, or keep weights on your disk.

---

## 1. Serverless endpoints

**Product page:** https://vast.ai/products/serverless  
**Docs hub:** https://docs.vast.ai/guides/serverless/  
**Console:** https://cloud.vast.ai/serverless/  
**Pricing:** https://docs.vast.ai/guides/serverless/pricing  
**Architecture:** https://docs.vast.ai/guides/serverless/architecture  
**Quickstart:** https://docs.vast.ai/guides/serverless/quickstart  
**Scaling knobs:** https://docs.vast.ai/guides/serverless/serverless-parameters  
**Setup:** https://docs.vast.ai/guides/serverless/setting-up-endpoints  
**Managing scale:** https://docs.vast.ai/guides/serverless/managing-scale  
**Worker states:** https://docs.vast.ai/guides/serverless/worker-states  
**OpenAI proxy:** https://docs.vast.ai/guides/serverless/openai-compatible-api  
**vLLM template:** https://docs.vast.ai/guides/serverless/vllm  
**SDK:** https://docs.vast.ai/guides/serverless/sdk-overview  
**PyWorker:** https://docs.vast.ai/guides/serverless/creating-new-pyworkers  
**Sessions (pin worker):** https://docs.vast.ai/guides/serverless/sessions  
**Route API:** https://docs.vast.ai/api-reference/serverless/route  
**Create endpoint API:** https://docs.vast.ai/api-reference/serverless/create-endpoint  
**Marketing article:** https://vast.ai/article/vast-ai-serverless-automated-gpu-scaling

### 1.1 What it actually is

Not a separate GPU SKU. The engine **recruits marketplace GPU instances** as workers, scales them on measured **load** (you define the units), and **drops the worst price-performance GPU first** when demand falls. Claim: same $/hr as non-serverless instances, **no serverless surcharge**.

Stack:

| Layer | Role |
|-------|------|
| **Endpoint** | Named router. Scaling hyperparameters live here. One per use-case × environment. |
| **Workergroup** | Template + marketplace search filters + GPU RAM hint. Multiple groups per endpoint (mixed GPU / canary model). |
| **Worker** | One rented GPU instance running a **PyWorker** (aiohttp proxy) in front of vLLM/TGI/Comfy/your server. |
| **Serverless engine** | Recruits / activates / releases workers; routes by queue time + cost-perf. |
| **SDK** | `pip install vastai` — auth, route, retry, sessions. Env: `VAST_API_KEY`. |

Default templates: **vLLM** (LLM), **ComfyUI** (images), plus TGI. Workload types in quickstart: LLM Inference, Image Generation, Text Generation, Other.

### 1.2 Pricing — per-second, no extra tier

Same three components as instances: **GPU compute ($/hr → per second)**, **storage ($/GB/hr while the worker exists)**, **bandwidth ($/TB in and out)**.

Worker billing by state ([pricing](https://docs.vast.ai/guides/serverless/pricing)):

| State | Meaning | GPU compute | Storage | Bandwidth |
|-------|---------|-------------|---------|-----------|
| **Ready** | Active, serving | Billed | Billed | Billed |
| **Loading** | Model downloading / loading | Billed | Billed | Billed |
| **Creating** | Offer accepted, recruiting | **Not billed** | Billed | Billed |
| **Inactive** | Cold / stopped, model already loaded | **Not billed** | Billed | Billed |
| Destroying / Error / Pending | teardown / fail / pre-create | Not billed | — | — |

UI aliases: Starting bills as Ready; Stopping bills as Inactive; Updating bills as Ready. Full table: https://docs.vast.ai/guides/serverless/worker-states

Endpoint billing:

| Endpoint state | Engine | Billing |
|----------------|--------|---------|
| **Active** | recruiting/releasing | workers billed by their states |
| **Suspended** | engine off; workers stay | billed at state-at-suspend; creating/loading **finish to Ready and keep billing** |
| **Stopped** | all workers inactive | all billed as Inactive (storage+bandwidth only) |
| **Destroyed** | workers gone | **all billing stops** |

**Idle tax:** cold workers still pay **storage**. Scale-to-zero is the only way to stop storage. Destroy the endpoint to stop everything.

Credits: min deposit **$5**. Balance → $0 stops instances; no card on file → data scheduled for deletion. Autobill on card. https://docs.vast.ai/guides/reference/billing · https://docs.vast.ai/guides/get-started/quickstart

### 1.3 Cold starts (the real numbers)

Official wait times:

| Event | Official figure | Source |
|-------|-----------------|--------|
| First deploy / new worker (boot + pull + load + health) | **3–5 minutes** (Qwen3-8B ~8 GB). Larger models longer. | [Quickstart](https://docs.vast.ai/guides/serverless/quickstart), [Setting up](https://docs.vast.ai/guides/serverless/setting-up-endpoints) |
| Cold worker → Ready (model already loaded, instance stopped) | **~seconds**. DeepWiki (secondary) quotes **~30 s vs ~5 min** for cold provision. Official: “spin up in seconds” / “don't need to download the model or benchmark.” | [Products](https://vast.ai/products/serverless), [Serverless parameters](https://docs.vast.ai/documentation/serverless/serverless-parameters) |
| First request after idle | Longer — worker activates from Inactive | Quickstart troubleshooting |
| Benchmark after `on_load` | Worker is **not Ready until benchmark finishes**. Failed bench → Error → restart. | [PyWorker](https://docs.vast.ai/guides/serverless/creating-new-pyworkers) |

**Reserve pool = Inactive workers with model loaded.** They still cost **storage**, not GPU.

Scale-to-zero ([managing scale](https://docs.vast.ai/guides/serverless/managing-scale)):

- Zero **active** workers: `min_load = 0` + positive `inactivity_timeout`. Keep `cold_workers` / `min_workers` for fast wake.
- Zero **total** workers: `min_load = 0`, `cold_workers = 0`, positive `inactivity_timeout`. Cheapest; pays the 3–5 min boot on next request.
- Never scale to zero: `inactivity_timeout = -1`.
- `inactivity_timeout = 0` disables inactivity gating (pure autoscaler).

### 1.4 OpenAI-compatible API shape

**Two paths.** Do not mix them.

#### A. Proxy (drop-in OpenAI SDK)

https://docs.vast.ai/guides/serverless/openai-compatible-api

```
Base URL:  https://openai.vast.ai/<ENDPOINT_NAME>
Auth:      Authorization: Bearer <VAST_API_KEY>
```

Supported:

| Route | Notes |
|-------|--------|
| `/v1/chat/completions` | multi-turn |
| `/v1/completions` | single prompt |

Streaming: `"stream": true` (SSE). Tool calling: models that support it; **`parallel_tool_calls` not supported**. `model` field is **required by the SDK and ignored** — served model is `MODEL_NAME` on the worker.

**Not supported through the proxy:** vision/`image_url`, `/v1/audio`, `/v1/images`, `/v1/embeddings`, `/v1/moderations`. Ignored params: `user`, `suffix`, `image_url.detail`. Extra vLLM field: `kv_transfer_params`.

Python:

```python
from openai import OpenAI
client = OpenAI(
    api_key="<YOUR_VAST_API_KEY>",
    base_url="https://openai.vast.ai/<ENDPOINT_NAME>",
)
r = client.chat.completions.create(
    model="",  # ignored
    messages=[{"role": "user", "content": "…"}],
    max_tokens=256,
    temperature=0.7,
)
```

cURL: `https://openai.vast.ai/<ENDPOINT_NAME>/v1/chat/completions`

#### B. Native SDK / route (what the proxy wraps)

1. `POST https://run.vast.ai/route` with `{ "endpoint": "<name>", "cost": <workload float> }`  
   → `{ url, cost, reqnum, signature, endpoint }`
2. POST the worker URL with envelope:

```json
{
  "auth_data": {
    "url": "http://WORKER_IP:PORT",
    "endpoint": "vLLM-Qwen3-8B",
    "cost": 242,
    "reqnum": 12345,
    "signature": "…"
  },
  "payload": { "model": "Qwen/Qwen3-8B", "prompt": "…", "max_tokens": 128 }
}
```

SDK hides this:

```python
from vastai import Serverless
async with Serverless() as client:  # VAST_API_KEY
    ep = await client.get_endpoint(name="vLLM-Qwen3-8B")
    result = await ep.request("/v1/completions", payload, cost=MAX_TOKENS)
    text = result["response"]["choices"][0]["text"]
```

vLLM native payload fields ([vLLM doc](https://docs.vast.ai/guides/serverless/vllm)): `model`, `prompt` or `messages`, `max_tokens` (default 256), `temperature` (0.7), `top_k` (20), `top_p` (0.4), `stream`, `tools`, `tool_choice`. Workload for scaling ≈ `max_tokens` (they say this, not prompt length, is what hits perf).

Worker HTTP: main server `WORKER_PORT` default **3000**; internal session-end `WORKER_PORT+1`. Session timeout on a single HTTP request: **600 s** — longer jobs need sessions + poll.

### 1.5 Scaling knobs

GUI defaults ([setting up](https://docs.vast.ai/guides/serverless/setting-up-endpoints) + [parameters](https://docs.vast.ai/guides/serverless/serverless-parameters)):

| Param | Default (GUI) | What it does |
|-------|---------------|--------------|
| `endpoint_name` | auto | router name; also the OpenAI base-URL path |
| `min_workers` | **5** | floor on **total** workers with model loaded (Ready + Inactive) |
| `max_workers` | **16** | hard cap on total workers |
| `min_load` | **1** | floor on **active** capacity in load-units. `1` ≈ keep ≥1 Ready. `0` allows zero active. |
| `target_util` | **0.9** | active_capacity = anticipated_load / util. 0.9 → 11.1% spare; 0.8 → 25%; 0.5 → 100% |
| `cold_mult` | **3** | inactive capacity = active_load × cold_mult. Example: load 100, cold_mult 2 → 100 inactive |
| `min_cold_load` | **0** | absolute total-capacity floor independent of `cold_mult` |
| `max_queue_time` | **30 s** | per-worker “full” threshold; excess goes to global hold queue |
| `target_queue_time` | **10 s** | endpoint-wide scale-up trigger |
| `inactivity_timeout` | unset | seconds idle before scale-to-zero is allowed |
| `cold_workers` | (API default **5**) | named cold pool; see API vs GUI below |

**Load math:** each worker has a **perf** from the post-load benchmark (load-units / second). A 100-perf worker finishes a 100-load request in 1 s; 200-perf in 0.5 s. Set `min_load ≈ measured_perf × minimum_parallel_requests`.

**API create endpoint** `POST https://console.vast.ai/api/v0/endptjobs` ([spec](https://docs.vast.ai/api-reference/serverless/create-endpoint)) uses **different defaults** than the GUI. Do not assume they match:

| Field | API default | GUI default |
|-------|-------------|-------------|
| `min_load` | 10 | 1 |
| `target_util` | 0.9 | 0.9 |
| `cold_mult` | 2.5 | 3 |
| `cold_workers` | 5 | (via min_workers / advanced) |
| `max_workers` | 20 | 16 |

CLI: `vastai create endpoint --endpoint_name … --cold_mult 2.0 --min_load 100 --target_util 0.9 --max_workers 20 --cold_workers 5`

Workergroup knobs ([workergroup parameters](https://docs.vast.ai/guides/serverless/workergroup-parameters)):

| Param | Default | Role |
|-------|---------|------|
| `gpu_ram` | 24 GB | bandwidth estimate + filter hint |
| `search_params` | none | marketplace query (verified, gpu_name, region, …) |
| `template_hash` / `template_id` | none | docker+env+onstart |
| `launch_args` | none | extra create-instance flags |

Tuning recipes ([managing scale](https://docs.vast.ai/guides/serverless/managing-scale)):

- Bursty: raise `min_workers` and `max_workers`.
- Idle cheap: drop `min_load` toward 0; keep cold pool if latency matters.
- First day: apply test load; **scale to 2× expected workers and back down, three times**, so the engine learns GPU class cost-perf. Example: https://github.com/vast-ai/vast-sdk/blob/main/examples/client/vllm_load_example.py

**Sessions** (swarm-relevant): pin N requests to one worker (KV-cache, LoRA, Comfy checkpoint). `endpoint.session(cost=…, lifetime=60)`. Default `max_sessions=10` per worker. Open session **counts as load** so the engine will not scale that worker away. Abandoned sessions hold a GPU until `lifetime` expires. https://docs.vast.ai/guides/serverless/sessions

Custom worker: public git repo with `worker.py` + `requirements.txt`; set `PYWORKER_REPO`. PyWorker source: https://github.com/vast-ai/pyworker

---

## 2. Volumes / persistence

**Volumes:** https://docs.vast.ai/guides/instances/storage/volumes  
**Types:** https://docs.vast.ai/guides/instances/storage/types  
**Storage UI:** https://cloud.vast.ai/storage/  
**Data movement:** https://docs.vast.ai/guides/instances/storage/data-movement  
**Cloud sync:** https://docs.vast.ai/guides/instances/storage/cloud-sync  
**Scheduled backups:** https://docs.vast.ai/guides/instances/storage/cloud-backups  
**Clone CLI:** https://docs.vast.ai/cli/reference/clone-volume  
**Search volumes:** https://docs.vast.ai/cli/reference/search-volumes  
**Host list volumes:** https://docs.vast.ai/cli/reference/list-volumes  
**Billing:** https://docs.vast.ai/guides/reference/billing

### 2.1 Two storage kinds (not AWS EBS)

| Kind | Lives | Survives destroy? | Reattach? | Resize? | Billed when |
|------|-------|-------------------|-----------|---------|-------------|
| **Container disk** | inside the Docker instance | **No** | No | **No** (fixed at create; min **10 GB**) | every second the instance **exists and the machine is online**, **including stopped** |
| **Volume** | local disk on **that physical machine** | **Yes** | Yes, **same machine only** | **No** | every second the volume exists and the machine is online |

Official: **“We currently provide local volumes only.”** Cannot attach to another host. Docker instances only — **not VMs**.

GUI mount: `/data`. CLI: `vastai create instance <offer> --env '-v V.<id>:/mnt'`.

Must **destroy the instance** before deleting the volume.

Machine offline → **not billed** (same as instances). Comes back → charges resume.

### 2.2 Pricing (host-set; no global SKU)

- Host CLI default when **listing** volume space: **`$0.1 / GB / month`**, default offer size **15 GB**, default expiry **3 months**.  
  `vastai list volume <machine_id> -s <GB> -p <$/GB/mo>`
- Client-side: hover Rent on Search. Offer field in our live API notes: `storage_cost` ≈ **$/GB/month** (`VAST_API_EXPERT_REFERENCE.md`: typical ~$0.10/GB/mo → 100 GB ≈ $0.014/day).
- Conversion: **$0.10/GB-month ≈ $0.000139/GB-hour**.
- Stopped instances **may be charged a higher storage rate** than running (official types page).
- Volume billed **independently** of the GPU instance.
- Bandwidth: **$/TB** in and out, host-set, **any instance state**. Same-machine / same-LAN copy: **no transit charge**.

**There is no published “volume snapshot” product.** Closest tools:

| Want | Mechanism | Command / URL |
|------|-----------|----------------|
| Copy volume → another machine | **clone volume** (new contract on dest offer, one-shot copy, **no ongoing sync**) | `vastai clone volume <src_id> <dest_offer_id> [-s GB] [-d no-compress]` |
| Copy paths volume ↔ volume / instance | `vastai copy` | `vastai copy V.<id>:/data/ V.<id2>:/data/` · `V.` ↔ `C.<instance>` |
| Off-machine backup | Cloud Sync (S3, GDrive, Backblaze, Dropbox, HF) | https://docs.vast.ai/guides/instances/storage/cloud-sync |
| Schedule | HOURLY / DAILY / WEEKLY rclone jobs | https://docs.vast.ai/guides/instances/storage/cloud-backups |
| Local laptop | **not supported** for volume↔local via `vastai copy`; use scp on a running instance | — |

Clone: dest offer must be ≥ source size; `-s` can **increase** size if dest has room.

CLI create: `vastai search volumes` then `vastai create volume <offer_id> -s <GB> -n <name>` (alnum+underscore, max 64).

**Network volumes:** older/third-party writeups (DeepWiki) describe network disks at host-set $/GB/hr. **Current official volumes page does not.** Treat network-volume as **unverified / not current product** until Vast publishes it again.

### 2.3 Swarm implication

A volume is a **sticky host**. Re-rent **that machine** (`Rent instance using this volume` filters Search to the same host). A serverless workergroup that hops GPUs across the marketplace **will not see the volume**. Put shared weights in HuggingFace / S3, or bake them into the image, or pin the workergroup `search_params` to `machine_id=` / `host_id=`.

---

## 3. Reserved instances — real discount mechanics

**Docs:** https://docs.vast.ai/guides/instances/choosing/reserved-instances  
**Types:** https://docs.vast.ai/guides/instances/choosing/instance-types  
**Instance pricing:** https://docs.vast.ai/guides/instances/pricing  
**Host-side factor:** https://docs.vast.ai/host/hosting-overview  
**2023 explainer (still the worked math):** https://vast.ai/article/reserved-instance-discounts  
**CLI:** `vastai prepay instance <ID> <AMOUNT>` — https://docs.vast.ai/cli/reference/prepay-instance  
**REST:** `PUT https://console.vast.ai/api/v0/instances/prepay/{id}` body `{"amount": 500}` — https://docs.vast.ai/api-reference/instances/prepay-instance  
**Marketing:** https://vast.ai/pricing — “Up to 50% Off · 1, 3, or 6 month terms”

### 3.1 What it is (not AWS RI)

1. Rent **on-demand**.
2. **Prepay credits onto that instance**.
3. Hourly rate drops as a **function of how many months of balance you just funded**.
4. Credits are **locked to that instance / that host**. **Cannot migrate.**

Not a separate SKU you buy off Search. GUI: green **discount badge** on the instance card → pick 1 / 3 / 6 months → system computes deposit. Search filter **Reserved** + duration shows a **Reserved cost** breakdown on hover before you rent.

### 3.2 The discount function (the real numbers)

**Default schedule** (host can change the **max**; this is Vast’s documented default):

| Prepaid coverage | Default discount | Worked example at $1/hr on-demand |
|------------------|------------------|-----------------------------------|
| 1 month | **20%** (`0.2`) | $720 → **$576** |
| 3 months | **30%** (`0.3`) | — |
| 6 months | **40%** (`0.4`) | — |

Sources: reserved-instances docs (same $576 vs $720 example), 2023 article, CLI text “default discount func of 0.2 for 1 month, 0.3 for 3 months”.

**Cap conflict (do not paper over):**

| Source | Stated max |
|--------|------------|
| Marketing + reserved-instances intro | **up to 50%** |
| Prepay API schema | `discount_rate` **0.0–0.4**, “typically **40%**” |
| Host “Reserved Discount Pricing Factor” | **host-set maximum**; host can set **0** to opt out. Discount **scales with duration**, not a flat %. |

Treat **40% at 6 months as the default ceiling**; 50% only if **that host’s factor** allows it. Always hover Rent on the Reserved filter.

CLI example from docs (small top-up is a **bad** idea — see below):

```
vastai prepay instance 24973511 50
prepaid for 0.546 months of instance 24973511 applying $50.0 credits for a discount of 3.5%
```

**Every top-up recalculates the rate from the new remaining coverage.** Adding 2 weeks of credit onto a 3-month reserve with 2 weeks left **can collapse the discount**. Do not nibble.

### 3.3 Refunds / cancel / stop

Cancel (destroy) prepaid instance:

- Claw back the **discount already consumed**
- Plus a **5% fee**
- Remainder of unused deposit returned to credits (Billing → Invoices)

Worked example (official):

| When | Refund |
|------|--------|
| On-demand $1/hr = $720/mo; reserved 1 mo = $576 | |
| Cancel **immediately** | **$576** |
| Cancel **after 15 days** (remaining $288) | **~$212** after clawback + 5% |
| Cancel at term end | **$0** |

Machine **deverified** / SLA fail → **full balance withdrawable, no penalty**.

**Stop ≠ keep the GPU.** Official: stopping a reserved instance **releases the GPU**; another user may rent it. You still hold prepaid credits on **that instance id**, but you are not sitting on the silicon while stopped. This is the opposite of “I reserved a box in the corner.”

Interruptible is a **different** product (bid, 50–80% cheaper, preemptible). You **cannot** convert on-demand ↔ interruptible; you **can** convert on-demand → reserved anytime.

### 3.4 Swarm implication

Reserved is for a **known host you will keep hitting** (train box, sticky volume machine). It is a **bad** fit for serverless workers that the engine will create and destroy. Prepay on a worker the autoscaler kills = credits stuck.

---

## 4. Host side — run your own GPU

**Setup (canonical):** https://cloud.vast.ai/host/setup/  
**Overview:** https://docs.vast.ai/host/hosting-overview  
**Agreement:** https://cloud.vast.ai/host/agreement  
**Verification:** https://docs.vast.ai/host/understanding-verification  
**Verification stages:** https://docs.vast.ai/host/verification-stages  
**Self-test:** https://docs.vast.ai/host/how-to-self-test  
**Earnings UI:** https://docs.vast.ai/host/earning  
**Optimize listings:** https://docs.vast.ai/host/optimization-guide  
**Payouts:** https://docs.vast.ai/host/payment  
**Taxes:** https://docs.vast.ai/host/guide-to-taxes  
**Market stats (host login):** https://cloud.vast.ai/host/market/  
**Calculator:** https://vast.ai/hosting/calculator  
**Earnings article (May 18, 2026):** https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai  
**Uninstall:** https://s3.amazonaws.com/vast.ai/uninstall  
**Host Discord:** https://discord.gg/hSuEbSQ4X8  
**Datacenter status:** https://docs.vast.ai/host/datacenter-status

### 4.1 Account / legal

- **Host account must be separate from client (renter) account.** Same account for both is unsupported.
- Convert via setup guide → hosting agreement. Then Machines appears in nav.
- Vast **does not support getting your machine working**. Host-only Discord for peer help.
- You commit to advertised specs until each rental contract’s **rental end date**. Unlisting stops **new** contracts; **existing contracts keep original price and end date**.
- No host→client messaging channel.

### 4.2 Hardware / software requirements

**Minimum to list** ([verification stages](https://docs.vast.ai/host/verification-stages) + setup table):

| Item | Minimum |
|------|---------|
| OS | Ubuntu **18.04+** (setup recommends **22.04/24.04 Server**) |
| GPU | NVIDIA **10-series (Pascal)+**, all GPUs **same model**. AMD: MI25+ Instinct, Radeon VII / Pro VII, RX 7900 GRE/XT/XTX, Pro W7900/W7800; other 6000+ RX/Pro W may work but not standard-filter searchable |
| CPU | ≥ **1 physical core (2 threads) per GPU**, **AVX** required |
| RAM | ≥ **4 GB system RAM per GPU** (verified machines: more — “a 5090 needs more than a 3060”) |
| Disk | **Fast SSD, ≥ 128 GB per GPU** |
| PCIe | ≥ **1× lane per 2.5 TFLOPS** |
| Network | **≥ 10 Mbps** up and down per machine |
| Ports | **≥ 3 open ports per GPU** (100 recommended), **continuous TCP+UDP range** e.g. `16384-32768` |
| Dedication | machine **should not do other work while rented** |

**Extra to be eligible for verification** (not a guarantee):

- CUDA **≥ 12.0**
- Reliability **≥ 90%**
- Download **and** upload scale with total VRAM: **~2.6 Mbps per GiB**, **floor 100 Mbps, ceiling 500 Mbps**
- GPU RAM **≥ 7 GB**
- Pass **self-test**

Verification is **automated, supply/demand weighted**. Fast track: **$10k+** datacenter (H100/A100 80GB “a day or so”; 8×4090 / 4×A6000 “under a week”). Mining-class consumer may **never** verify. Unverified still lists but **default Search hides it**. Manual tests only for datacenters / high-end. Datacenter badge: min server count + **ISO 27001** (etc.) — https://docs.vast.ai/host/datacenter-status · `contact@vast.ai`

Reliability **≠** verification. Offline time hurts reliability (penalized less on low-earning machines).

### 4.3 What you earn (official numbers vs marketing)

You set:

- on-demand **$/GPU-hour**
- interruptible **min bid** (set near **power cost under load**, not hoped-for price)
- disk **$/GB/month** (default listing **$0.1**)
- bandwidth **$/TB**
- reserved **max discount factor** (0 = opt out)
- `min_gpu` slicing (powers of 2)
- offer **end date** (unset = open-ended — don’t)

**Vast does not publish a host take-rate % in docs.** Two official-adjacent statements:

1. Calculator: “**Keep What You List.** Customer-facing prices may also reflect marketplace operations and support.” https://vast.ai/hosting/calculator
2. Earnings article: “**Live GPU prices are typically about 25% above what hosts earn.**” https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai

That 25% gap is the closest official “platform cut / markup” figure. Third-party sites claiming “host keeps 85% / 15% fee” are **not Vast docs** — do not treat as law.

Vast’s own host-earnings snapshot (**May 18, 2026**, marketing, not a contract):

| Hardware | Stated host earn |
|----------|------------------|
| RTX 5090 consumer | **$0.30–$0.60 / GPU-hour** |
| 4×5090 at **80% util** | **$700–$1,400 / month** |
| H100 / H200 datacenter | **$2.15–$4.00+ / GPU-hour** |

Client-side marketplace ranges (third-party scrape **2026-07-14**, UsagePricing, **not list prices**): RTX 3090 $0.058–$0.149/hr, 4090 $0.136–$0.349, 5090 $0.227–$0.407, A100 80GB $0.401–$0.934, H100 $1.045–$2.747, H200 $1.936–$3.816, B200 $6.752–$6.877. Live UI: https://vast.ai/pricing

Interruptible fills idle gaps at lower $/hr; on-demand always preempts interruptible. Storage revenue: hosts list disk separately; calculator FAQ “does storage go through the platform fee?” is JS-only — **not retrieved here**.

### 4.4 Credit payouts (docs vs calculator marketing)

**Docs win.** https://docs.vast.ai/host/payment

| Rule | Number |
|------|--------|
| Methods | **Wise, PayPal, Stripe** only. **No** ACH / SWIFT / wire. |
| Minimum invoice | **$20 USD**. Below that rolls forward. |
| Invoice generation | **Fridays**, if payout method connected **and** ≥ $20 |
| First payout | **up to 2 weeks**: Week1 accrue → Friday invoice **Pending** → next Friday submit to provider → provider delay |
| “Paid” | means Vast **submitted** to Wise/PayPal/Stripe, **not** that money landed |
| Customize invoice | Settings → Invoice Information |
| Download | Earnings → Payout History (CSV / PDF) |

Calculator copy says “No minimum threshold to cash out” — **contradicts payment docs**. Use **$20 + weekly Friday**.

Referral cash-out is a **different** pile: 3% of referred clients’ lifetime spend; **75% of those credits** cashable; **must be a dedicated account that has never rented or hosted**, else you cannot cash out until referral earnings **exceed lifetime instance spend**. https://docs.vast.ai/guides/reference/referral-program

Host testing your own box: separate **client** account + card, or CLI `vastai search offers 'machine_id=ID verified=any'` then `create instance` (self-rent is how you validate SSH/Jupyter).

Maintenance: wait for all contracts to end, or `vastai schedule maint`. Breaking a live contract is an SLA event.

---

## 5. Templates marketplace

**Browse:** https://cloud.vast.ai/templates/  
**Intro:** https://docs.vast.ai/guides/templates/introduction  
**Create:** https://docs.vast.ai/guides/templates/creating-templates  
**Settings (incl. public flag):** https://docs.vast.ai/guides/templates/template-settings  
**Manage / share:** https://docs.vast.ai/guides/templates/managing-templates  
**Advanced (provisioning, portal, custom images):** https://docs.vast.ai/guides/templates/advanced-setup  
**CLI create:** https://docs.vast.ai/cli/reference/create-template  
**REST:** `POST https://console.vast.ai/api/v0/template` — https://docs.vast.ai/api-reference/templates/create-template  
**Base images:** https://github.com/vast-ai/base-image/  
**Referral via templates:** https://docs.vast.ai/guides/reference/referral-program

### 5.1 What a template is

A wrapper around `docker run`: image, ports, env, launch mode, on-start, disk hint, extra Search filters, optional volume UI hint. Used by GUI Search, CLI, API, and **serverless workergroups** (`template_hash` / `template_id`).

Launch modes:

| Mode | Entrypoint | Use |
|------|------------|-----|
| Jupyter + SSH | Vast **replaces** image entrypoint | default interactive |
| SSH only | same | no Jupyter |
| `docker ENTRYPOINT` / `args` | **your** entrypoint | serverless / services. Pass `args_str`. |

On-start script: Jupyter/SSH modes only (start the services the overwritten entrypoint would have). REST `onstart` cap: **4048 chars** (gzip+base64 if longer).

Recommended templates sit on `vastai/base-image` / `vastai/pytorch` (CUDA, Caddy TLS, Instance Portal, `PROVISIONING_SCRIPT`). Cached on many hosts → faster cold boot.

### 5.2 Publishing (there is no separate “storefront SKU”)

1. Create in GUI (`+ New` or fork a recommended template) or:

```bash
vastai create template --name "mag-swarm-vllm" \
  --image "vllm/vllm-openai" \
  --env "-p 8000:8000 -e MODEL_NAME=Qwen/Qwen3-8B" \
  --onstart-cmd '…' \
  --search_params "gpu_ram>=23 num_gpus=1 inet_down>128 disk_space>=64" \
  --disk_space 32 --public
```

REST required: `name`, `image`. `private: true` hides from search. CLI `--public` makes it searchable.

2. **Template Visibility = public** → appears in template search. Private still works via **shared URL**.
3. **Never put secrets in a public template.** Account-level env vars (e.g. `HF_TOKEN`) inject at runtime. https://cloud.vast.ai/account/

Share menu (three dots on card):

| Link | Points at | Contains |
|------|-----------|----------|
| **Referral link** | **latest** template with that **name** | referral ID + creator ID + name |
| **Template link** | **this save’s hash** | referral ID + `hash_id` |

Every save gets a **new `hash_id`**. Serverless workergroups should pin `template_hash` if you need reproducibility.

Earnings: **not a per-launch bounty**. Public template + referral link → **3% of that new client’s lifetime spend** as credits; **75% cashable** on a clean referral account. Template Performance chart lives on the Earnings page. Big deals: `support@vast.ai`.

Serverless-specific: template must run a PyWorker. Set `PYWORKER_REPO` to a **public** git repo with `worker.py`. Prebuilt: vLLM, TGI, ComfyUI, ComfyUI Wan 2.2, ComfyUI ACE Step. Docs under https://docs.vast.ai/guides/serverless/

---

## 6. GPU-swarm mapping (this repo)

| Swarm need | Vast primitive | Trap |
|------------|----------------|------|
| Burst inference, OpenAI SDK | Serverless + `https://openai.vast.ai/<name>` | Cold = 3–5 min unless Inactive pool (you pay storage) |
| Sticky KV / LoRA / conversation | **Sessions** | abandoned session holds a GPU |
| Cheap batch train | Interruptible bid | preemption; checkpoint |
| Multi-week train on one box | On-demand → **prepay reserved** | credits locked; **stop releases the GPU** |
| Weights that outlive a worker | **Volume on one host** or S3/HF | volume **does not follow** serverless recruitment |
| Snapshot | **clone volume** / cloud copy | not COW snapshots |
| Own silicon on the market | **separate host account** | $20 min payout, Friday invoices, 2-week first pay |
| Ship a Mag image to strangers | **public template + referral link** | 3% spend, not a royalty |
| Same $/hr as dedicated | Serverless (no surcharge) | Loading **is** billed for GPU |

Existing Mag rails: `VASTAI_API_KEY` / `VAST_API_KEY`, `mag/vast_launcher.py`, `docs/ref/VAST_API_EXPERT_REFERENCE.md`. Serverless would be a **new** surface (`VAST_OPENAI_BASE_URL=https://openai.vast.ai/<endpoint>` already named in `mag/nervous_system.py`).

---

## 7. Contradictions to keep on the table

| Topic | A | B | Use |
|-------|---|---|-----|
| Reserved max | Marketing “up to 50%” | API “typically 40%”, `discount_rate` 0–0.4 | Hover that host’s Reserved breakdown |
| Host payout floor | Payment docs **$20** + Friday | Calculator “no minimum” | **Docs** |
| Serverless GUI vs API defaults | GUI min_workers 5 / max 16 / min_load 1 / cold_mult 3 | API min_load 10 / max_workers 20 / cold_mult 2.5 / cold_workers 5 | Read back `vastai show endpoints` after create |
| Network volumes | DeepWiki / old notes | Current volumes doc: **local only** | Local only |
| Host take rate | Article: client prices **~25% above host earn** | No % in payment docs | Do not invent 15% |

---

## 8. Source list (fetched 2026-08-27)

### Serverless
- https://docs.vast.ai/guides/serverless/pricing
- https://docs.vast.ai/guides/serverless/openai-compatible-api
- https://docs.vast.ai/guides/serverless/setting-up-endpoints
- https://docs.vast.ai/guides/serverless/serverless-parameters
- https://docs.vast.ai/guides/serverless/quickstart
- https://docs.vast.ai/guides/serverless/architecture
- https://docs.vast.ai/guides/serverless/worker-states
- https://docs.vast.ai/guides/serverless/managing-scale
- https://docs.vast.ai/guides/serverless/workergroup-parameters
- https://docs.vast.ai/guides/serverless/vllm
- https://docs.vast.ai/guides/serverless/sdk-overview
- https://docs.vast.ai/guides/serverless/creating-new-pyworkers
- https://docs.vast.ai/guides/serverless/sessions
- https://docs.vast.ai/api-reference/serverless/route
- https://docs.vast.ai/api-reference/serverless/create-endpoint
- https://vast.ai/products/serverless
- https://vast.ai/article/vast-ai-serverless-automated-gpu-scaling
- https://vast.ai/article/deploy-llm-inference-using-vast-ai-serverless

### Storage
- https://docs.vast.ai/guides/instances/storage/volumes
- https://docs.vast.ai/guides/instances/storage/types
- https://docs.vast.ai/guides/instances/storage/data-movement
- https://docs.vast.ai/guides/instances/storage/cloud-sync
- https://docs.vast.ai/guides/instances/storage/cloud-backups
- https://docs.vast.ai/cli/reference/clone-volume
- https://docs.vast.ai/cli/reference/search-volumes
- https://docs.vast.ai/cli/reference/list-volumes

### Reserved / billing / live prices
- https://docs.vast.ai/guides/instances/choosing/reserved-instances
- https://docs.vast.ai/guides/instances/choosing/instance-types
- https://docs.vast.ai/guides/instances/pricing
- https://docs.vast.ai/guides/reference/billing
- https://docs.vast.ai/api-reference/instances/prepay-instance
- https://vast.ai/article/reserved-instance-discounts
- https://vast.ai/pricing

### Host
- https://docs.vast.ai/host/hosting-overview
- https://docs.vast.ai/host/payment
- https://docs.vast.ai/host/earning
- https://docs.vast.ai/host/verification-stages
- https://docs.vast.ai/host/understanding-verification
- https://docs.vast.ai/host/optimization-guide
- https://cloud.vast.ai/host/setup/
- https://vast.ai/hosting/calculator
- https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai

### Templates
- https://docs.vast.ai/guides/templates/creating-templates
- https://docs.vast.ai/guides/templates/managing-templates
- https://docs.vast.ai/guides/templates/template-settings
- https://docs.vast.ai/guides/templates/introduction
- https://docs.vast.ai/cli/reference/create-template
- https://docs.vast.ai/api-reference/templates/create-template
- https://docs.vast.ai/guides/reference/referral-program
- https://cloud.vast.ai/templates/

### Index
- https://docs.vast.ai/llms.txt
