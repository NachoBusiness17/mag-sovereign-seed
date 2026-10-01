# Vast.ai market economics — deep research for internal compute-economy (gstd)

**Date:** 2026-08-27  
**Status:** RESEARCH COMPLETE · public sources + this repo’s live probes  
**Job:** How Vast.ai prices, bids, reserves, meters storage/bandwidth, scores hosts, credits accounts, and bans workloads — filed as the **external cost oracle** for Mag’s internal proof-of-cost receipt units (house name **gstd**).  
**Not:** affiliation with public `gstdcoin` (see `FOREIGN_GSTD_DEEPDIVE_20260827.md`). House gstd here = receipt units minted from real spend.

**Companions (do not duplicate):**  
- Workhorse API/ops: `docs/ref/VAST_API_EXPERT_REFERENCE.md`  
- v5 train pipe: `docs/ref/MAG_v5_VAST_TRAINING.md`  
- Live watch: `state/vast/market_watch.jsonl`

**Honesty rule:** Official docs first. Third-party snapshots dated. Conflicts marked. Preemption *frequency* is **not published** by Vast — derived from mechanics + occupancy, not a fake MTTI.

---

## 0. One-line for gstd

Vast is a **host-set three-meter marketplace** (GPU $/hr + storage $/GB/hr + bandwidth $/TB), not a list-price cloud. A gstd receipt must mint from **itemized charges** (`dph_total` + storage seconds + bytes), never from a GPU headline alone. Interruptible is a **bid floor + auction**, not AWS Spot. Reserved is **prepaid locked to one machine**. Reliability2 is a **host uptime score**, not an SLA.

---

## 1. How prices form

### 1.1 Marketplace, not a rate card

Vast’s own pricing page: *“Prices are set by the market, not by Vast.”* Supply/demand across **40+ data centers**, **68+ GPU types**, billed **per second**.  
URLs: https://vast.ai/pricing · https://docs.vast.ai/guides/instances/pricing.md · https://docs.vast.ai/guides/pricing.md

Hosts create **offers** (`list machine` / GUI). Parameters locked into a **rental contract** at accept time: GPU price, internet, storage, reserved-discount factor, interruptible **min bid**, `min_gpu` slice, offer end date. Changing the offer later does **not** rewrite existing contracts.  
URL: https://docs.vast.ai/host/hosting-overview.md

API fields (this repo, live): `dph_base` = GPU-only; **`dph_total` = real all-in GPU+allowances**; `storage_cost`; `inet_up_cost` / `inet_down_cost`; `min_bid`; `reliability2`; `geolocation`; `datacenter`; `dlperf`.  
Law: **sort/filter on `dph_total`**, not `dph_base`. See `VAST_API_EXPERT_REFERENCE.md`.

### 1.2 Who sets which lever

| Lever | Who sets | What it does |
|---|---|---|
| On-demand $/GPU/hr (`price_gpu`) | Host | Ceiling / high-priority rate |
| Interruptible min bid (`price_min_bid`) | Host | **Floor**, not the expected price |
| Reserved max discount (`credit_discount_max`) | Host (0 = opt out) | Caps prepaid discount curve |
| Storage `$/GB` (`price_disk`) | Host | Listed as $/GB/month on CLI `-z` |
| Bandwidth `$/GB` up/down (`price_inetu` / `price_inetd`) | Host | Charged per byte both ways |
| Duration / offer end date | Host | Becomes contract rental end date |
| Bid `$/hr` | **Client** | Interruptible only; API min **0.001**, max **32** |
| Search ranking | Vast algo | Verification, duration, disk, DLPerf, reliability, **plus randomness** |

List-machine API: https://docs.vast.ai/api-reference/machines/list-machine.md  
Change-bid API: https://docs.vast.ai/api-reference/instances/change-bid.md (`price` minimum 0.001, maximum 32)

Host economics guide: occupancy × price, not price alone. Customers filter first on **verification, duration, disk** — a cheap unverified short-duration box is invisible to the default search.  
URL: https://docs.vast.ai/host/optimization-guide.md

Search default: `verified=true`, `rentable=true`. CLI search “Auto Sort” mixes rank factors **and randomness**. There are **10,000+ listings**; a specific machine is often unfindable in the GUI.  
URL: https://docs.vast.ai/host/hosting-overview.md (FAQ “Why can’t I see my machine”)

### 1.3 Variance by GPU / datacenter / time

Prices are a **distribution**, not a number.

**This house’s live probe (credit $48.50, reliability2 ≥ 0.97, ≥24 GB VRAM), 2026-08-27 15:54–16:29Z** — `state/vast/market_watch.jsonl`:

| GPU | Observed `dph_total` $/hr | Notes |
|---|---|---|
| Tesla V100 | 0.029 – 0.216 | Bargain floor in our watcher is $0.12 |
| RTX 3080 | 0.029 | Cheap consumer |
| RTX 4070 Super Ti | 0.069 | |
| RTX 3090 | 0.082 – 0.162 | Our bargain bell: < $0.20 |
| RTX 4090 | 0.121 – 0.241 | Our bargain bell: < $0.45 |
| RTX 5080 | 0.135 | |
| RTX 5090 | 0.353 | |
| RTX PRO 6000 S (Utah, US) | 1.002 | rel 0.991 |

**Third-party marketplace snapshots (dated):**

| GPU (1× on-demand) | Snapshot | Source |
|---|---|---|
| RTX 3090 | ~$0.07/hr start (24 Aug 2026) | https://www.aichatdaily.com/tools/vast-ai |
| RTX 3090 | $0.058–$0.149/hr min–median (14 Jul 2026 API) | https://www.usagepricing.com/blueprint/vast-ai |
| RTX 4090 | $0.136–$0.349/hr (14 Jul 2026) | same |
| RTX 4090 cheapest in-stock | **$0.13/hr** Norway (27 Aug 2026 13:16 UTC); 6-month floor $0.11–$0.60 | https://gpufinder.dev/gpu/rtx-4090 |
| RTX 4090 (this house) | $0.121/hr at 16:23Z 27 Aug 2026 | `market_watch.jsonl` |
| RTX 5090 | $0.227–$0.407/hr (14 Jul 2026) | usagepricing |
| A100 80GB | $0.401–$0.934/hr (14 Jul 2026) | usagepricing |
| A100 SXM4 | ~$0.60/hr start (24 Aug 2026) | aichatdaily |
| H100 | $1.045–$2.747/hr (14 Jul 2026) | usagepricing |
| H100 SXM cheapest public | $1.34/hr unverified Moldova, rel ~0.95; verified from ~$1.74 (24 Aug 2026) | aichatdaily |
| H100 cheapest in-stock | **$1.33/hr** Mexico (27 Aug 2026); interruptible row from **$0.01** | https://gpufinder.dev/gpu/h100 |
| H200 | $1.936–$3.816/hr (14 Jul 2026) | usagepricing |
| B200 | $6.752–$6.877/hr (14 Jul 2026) / ~$4.63 start (24 Aug 2026) | usagepricing / aichatdaily |
| Platform range (1×) | $0.02 – $10.56/hr; 52 GPU models, 2385 configs, 811 available | https://gpufinder.dev/providers/vast (27 Aug 2026) |

Host-side published bands (Vast marketing, 18 May 2026): consumer RTX 5090 host-earn **$0.30–$0.60**/GPU-hr; 4×5090 @ 80% util **$700–$1,400/mo**; H100/H200 **$2.15–$4.00+**/GPU-hr. *“Live GPU prices are typically about **25% above what hosts earn**.”*  
URL: https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai

That 25% markup is consistent with the **75/25 revenue split** in the official FAQ (see §6). Treat marketing calculator yields as **upper bound**; Trustpilot hosts report earnings “an order of magnitude lower” than the calculator.

Geographic / verification spread is first-class: same GPU, Moldova unverified vs US/EU verified can 2× the hourly. Datacenter / Secure Cloud filters pull a different (higher) cohort. Consumer cards in Eastern Europe/India/Saudi listings dominate the **floor**; datacenter US/EU dominate the **median used by serious renters**.

Time variance: consumer 4090/3090 floors moved **down** Jun→Jul 2026 while B200/B300 **up** (usagepricing). GPU Finder 4090 1× floor near 6-month **low** ($0.11) on 27 Aug 2026. 8× H100 floor **up 449% vs prior month** in that same snapshot — high-end is not a smooth curve.

Market stats (host-key only): `vastai metrics gpu` / `gpu-trends` / `gpu-locations` — https://docs.vast.ai/host/market-metrics.md · dashboard https://cloud.vast.ai/host/market/

### 1.4 Three rental types (priority ladder)

Current docs: **three** types. (Stale console FAQ still says “two” — ignore.)

| Type | Priority | Price | Preempted by |
|---|---|---|---|
| On-demand | High | Host-set fixed | Never (until contract end) |
| Reserved | High (same as OD) | Prepaid discounted | Never |
| Interruptible | Low | Client bid ≥ `min_bid` | Any OD/reserved on those GPUs, or a **higher bid** |

Official savings claims: interruptible **often 50%+** (pricing page) / **50–80%** (rental-types FAQ). Reserved **up to 50%**.  
URLs: https://docs.vast.ai/guides/instances/choosing/instance-types.md · https://docs.vast.ai/guides/reference/faq/rental-types.md

You **cannot** convert interruptible ↔ on-demand. On-demand → reserved is the only conversion.  
https://docs.vast.ai/guides/instances/choosing/instance-types.md

---

## 2. Interruptible / bid mechanics (deep)

### 2.1 What the bid actually is

Two-sided:

**Host** sets `min_bid` / `price_min_bid` — a **floor**. Bids below are rejected. Official host advice: set floor at **cost of power under load**, *not* near the hoped-for rental. Idle GPUs earn $0; bidding is supposed to fill the gap.  
https://docs.vast.ai/host/optimization-guide.md  
API: `PUT /api/v0/machines/{machine_id}/minbid` body `{"price": 0.5}` — https://docs.vast.ai/api-reference/machines/set-min-bid.md  
CLI: `vastai set min-bid <id> --price <price>`

**Client** sets a bid on create (`price` field) and can retune:  
`vastai change bid <id> [--price PRICE]`  
If PRICE omitted, “a **winning bid price** is used as the default.”  
https://docs.vast.ai/cli/reference/change-bid.md  
REST: `PUT /api/v0/instances/bid_price/{id}` body `{"client_id":"me","price":0.17}` — min 0.001, max 32.  
https://docs.vast.ai/api-reference/instances/change-bid.md

Alternate/legacy path in some CLI docs: `PUT /api/v0/instances/{id}/change_bid/`. Probe before automating (this house’s API law).

Host can also create an **idle/default job** (`set defjob`) at a price — historically *this was* the min-bid mechanism (“If you don’t want a true mining idle job, use ubuntu + bash”).  
https://docs.vast.ai/cli/reference/set-defjob.md · https://console.vast.ai/faq/ (Hosting → “How do I set prices?”)

Priority rules (official):

1. On-demand / reserved **always** beat interruptible, regardless of bid.  
2. Among interruptible, **highest bid wins**.  
3. Loser is **stopped** (processes killed). Data on disk is preserved; instance is not functional.  
4. Auto-resume when priority returns — **“instance may wait long to resume.”**

https://docs.vast.ai/guides/instances/choosing/instance-types.md · https://docs.vast.ai/guides/reference/faq/rental-types.md

vs AWS Spot / GCE preemptible (official FAQ): Vast uses **direct bidding** (you name the price); AWS uses market pricing; **no 24-hour cap** (unlike GCE); can run indefinitely if not outbid.

Notifications: **Instance outbid**, resumed, maintenance scheduled, offline.  
https://docs.vast.ai/guides/reference/notifications.md

### 2.2 Preemption frequency — what is actually known

**Vast publishes no MTTI, no preemption rate, no “typical hours between outbids.”** Anyone quoting a universal “interruptible lasts N hours” is inventing it.

Mechanics imply frequency is **endogenous**:

| Driver | Effect on interruptible |
|---|---|
| Host occupancy of **on-demand** | Every new OD rental on those GPUs **kills** interruptibles immediately |
| Bid vs other interruptibles | First-price-ish highest-bid wins (docs do not specify second-price clearing of *payment*; usagepricing calls it second-price — **unconfirmed by Vast**) |
| Bid vs `min_bid` | Below floor = never scheduled |
| Bid near OD price | Behaves almost like OD but still loses to true OD |
| Popular GPU, verified, long duration | High OD demand → interruptibles are **gap-fillers**, preempted often |
| Unpopular GPU / off-hours / unverified | Can run “indefinitely” (official claim) |

GPU Finder (27 Aug 2026) observed:

- RTX 4090 interruptible floor **$0.05/hr** vs OD floor **$0.13** (~60% off)  
- H100 interruptible advertised from **$0.01/hr** vs OD **$2.67** on some rows (99% off) — treat $0.01 as a **host floor**, not a clearing price you will actually hold  

https://gpufinder.dev/gpu/rtx-4090 · https://gpufinder.dev/gpu/h100 · https://gpufinder.dev/providers/vast

aichatdaily (24 Aug 2026): sampled host `min_bid` typically **~2/3 of on-demand**. That conflicts with Vast’s host advice (“floor = power cost”). Real hosts often mis-set the floor high.

MiningBoard (27 Aug 2026, third-party, host-oriented): interruptible clears at **30–60% of on-demand**; RTX 4090 clearing **~$0.121/h** (matches this house’s 16:23Z print).  
https://miningboard.com/guides/vast-ai-bid-pricing

**gstd implication:** do **not** mint a “cheap hour” receipt from `min_bid`. Mint from **actual billed seconds** after the fact. Checkpoint tax (lost work + re-download bandwidth) is part of true cost.

### 2.3 Bid strategies (renter)

Official: checkpoint to disk **and** cloud; expect kill; paused instance may sit a long time.

Practical (synthesized from mechanics, not a Vast SOP):

| Strategy | Bid | When |
|---|---|---|
| Floor-sit | `min_bid` | Stateless burns, scrapes, eval loops. High preempt risk. |
| Discount band | ~50–70% of that machine’s OD | Batch train with frequent checkpoints |
| Almost-OD | just under OD | Want cheap until someone pays full freight |
| Win-default | `change bid` with no price | Lets Vast pick a currently-winning price |
| Scheduled retune | `change bid --schedule HOURLY/DAILY/WEEKLY` | Follow diurnal occupancy |

**Wrong for gstd uptime receipts** (already filed in `VAST_API_EXPERT_REFERENCE.md`): interruptible. Right for **stateless burns**.

On-demand vs interruptible cannot be flipped in place — destroy and recreate.

### 2.4 Bid strategies (host)

Official optimization guide:

- Min bid ≈ **electricity under load**  
- Do not treat min bid as a second on-demand price  
- If nobody bids, run your **own defjob** on idle silicon  
- Mix `min_gpu` across a fleet (1/2/4/8) to avoid fragmentation; ~2× search volume for 8× vs 1× (their claim)

MiningBoard (not official): OD at 25th percentile of cohort; interruptible at 50% of OD; wait 48–72h while reliability is provisional.

---

## 3. Reserved / commitment discounts

### 3.1 Mechanism

Convert **existing on-demand** → reserved by prepaying. Credits **lock to that instance / host**. **Cannot migrate.** Discount scales with how many months the prepay covers.

UI: 1 / 3 / 6 month terms, green discount badge.  
CLI: `vastai prepay instance ID AMOUNT`  
Example from docs: `$50` on instance 24973511 → **0.546 months**, discount **3.5%**.  
https://docs.vast.ai/guides/instances/choosing/reserved-instances.md

REST: `PUT /api/v0/instances/prepay/{id}` `{"amount":500}` → `{timescale, discount_rate}` with **`discount_rate` 0.0–0.4** and text *“Maximum discount is typically **40%**.”*  
https://docs.vast.ai/api-reference/instances/prepay-instance.md

**Conflict (keep both):** marketing + instance-types docs say **up to 50%**. Prepay API says **typically 40%**. CLI comment: default discount func **0.2 for 1 month, 0.3 for 3 months**. Worked refund example is **20%** for 1 month.

Worked official example:

| | |
|---|---|
| On-demand | $1/hr → **$720/month** |
| Reserved 1 month | **$576/month** (−20%) |
| Cancel immediately | refund $576 |
| Cancel after 15 days | remaining $288 → refund **~$212** after discount clawback + **5% fee** |
| Cancel at end | $0 |

Early cancel: claw back discount already received **plus 5%**.  
If the machine is **deverified / fails SLA**, **full remaining balance withdrawable without penalty**.

**Trap:** every additional credit mid-term **recalculates** the discount. Adding 2 weeks of credit with 2 weeks left can **worsen** the rate.

**Trap:** **stopping** a reserved instance **releases the GPU** — another renter can take it. Reserved is a **prepaid discount on a contract**, not a parked reservation of idle silicon.

Host side: `credit_discount_max` / “Reserved Discount Pricing Factor” — host-set maximum; **0 = opt out**. Discount **scales with duration**, not a flat coupon.  
https://docs.vast.ai/host/hosting-overview.md

gstd: reserved hours are **cheaper per second** but **illiquid**. Receipt should tag `rental=reserved`, `host_id`, `instance_id`, `discount_rate`, `locked=true`.

---

## 4. Bandwidth and storage economics

### 4.1 Three meters (official)

https://docs.vast.ai/guides/reference/billing.md

1. **GPU** — `$/hr`, per second in **active/connected** state. Not charged while **offline**. Not charged during **“Loading”**.  
2. **Storage** — `$/GB/hr`, every second the instance **exists and is online** (running, stopped, inactive, loading). **Stop does not stop storage.** Destroy is the only off switch. Volumes billed separately while they exist. Stopped instances **may have a higher storage rate** than running (docs).  
3. **Bandwidth** — `$/TB` (host sets `$/GB` in list-machine), **every byte in and out**, any state.

Headline `$/hr` **does not include** realized bandwidth. Vast FAQ: people get “charged more per hour than expected” because of upload/download. Hover the price for the Internet: line.

Units in this house’s API notes:

- `storage_cost` ≈ **$/GB/month**  
- `inet_*_cost` ≈ **$/GB** (convert ×1000 ≈ $/TB)

CLI list volume: price in **$/GB/Month**.

### 4.2 Typical numbers (ranges, not list prices)

Official: **no platform-wide $/GB**. Host-set, “vary considerably.”

| Item | Typical / sampled | Convert | Source |
|---|---|---|---|
| Storage cluster | **~$0.20 / GB / month** (24 Aug 2026 sample); range “few cents to over a dollar” | $0.20/GB/mo ≈ **$0.000274/GB/hr** ≈ **$6.6/TB/mo** | https://www.aichatdaily.com/tools/vast-ai |
| Storage (this house prior) | **~$0.10 / GB / mo** typical | 100 GB model ≈ **$0.014/day** while instance exists | `VAST_API_EXPERT_REFERENCE.md` |
| Storage worked example | 1 TB disk 24/7 ≈ **$30/mo** | implies **$0.03/GB/mo** in *that* example (inconsistent with $0.20 cluster — example is illustrative) | https://www.usagepricing.com/blueprint/vast-ai |
| Bandwidth typical | **~$2.60 / TB** both ways (24 Aug 2026 sample); “order of magnitude higher on some hosts” | $0.0026/GB | aichatdaily |
| Bandwidth this house | **~$1–5 / TB** common on offers we read | | `VAST_API_EXPERT_REFERENCE.md` |
| Bandwidth horror | Trustpilot **$2.50 / 100 GB** = **$25/TB** for a 20-minute session | | https://costbench.com/software/ai-gpu-cloud/vast-ai/ citing Trustpilot |
| Bandwidth filter UI | Search sliders **$0–$100 / TB** upload and download | | cloud.vast.ai create filters |
| Disk default | **10 GB min** (storage types) / older API default **8 GB** | always billed | https://docs.vast.ai/guides/instances/storage/types.md |
| Volume default listing | half of machine disk at **same disk price** as GPU offers | | hosting-overview |

**GPU Finder labels Vast egress “Free.” That is wrong for Vast’s own billing.** Official docs charge per byte. GPU Finder is aggregating a catalog field, not Vast invoices. Do not use it as a gstd input.

Host advice: if unmetered uplink, **price bandwidth at 0** as a ranking weapon; if metered, price it to stop one client saturating the NIC. Excess disk → price near amortized cost; tight disk → **price storage high** so stopped instances don’t starve GPUs.

### 4.3 gstd storage/bandwidth recipe

For a 70B pull (~140 GB) on a $5/TB host: **$0.70** one-way. On a $25/TB host: **$3.50**. Checkpoint egress every hour on a chatty job can exceed GPU on cheap 3090s.

Always read per-offer `storage_cost` and `inet_*_cost` before minting a planned receipt. After the job, mint from **Charges tab** (GPU + reserved disk + upload + download), not from `dph_total` × hours.

---

## 5. Reliability engineering — reliability2, deverification, disputes, gaming

### 5.1 Two different scores (do not conflate)

| Signal | What it is | Affects search | Official independence |
|---|---|---|---|
| **reliability2** | 0..1 historical uptime / start-success estimate | Default auto-rank; clients filter (this house: ≥0.97) | **Independent of verification** |
| **Verified** | Automated badge | Default search **hides unverified** | Independent of reliability2 |
| **Secure Cloud / datacenter** | Partner certification path | Separate filter | ISO 27001 etc. for DC status |

Host FAQ (verbatim): *“Your machine's reliability does **not** directly affect your verification standing. Verification is independent of reliability.”*  
https://docs.vast.ai/host/hosting-overview.md

### 5.2 How reliability2 moves

Official fragments (no closed-form formula published):

- Disconnects, outages, errors feed a **future-reliability estimate** shown on cards and used in auto-rank. https://console.vast.ai/faq/  
- Reliability drops if the machine **loses connection** or a **client instance will not start**.  
- **Punishes restarts hard** (host video lore + FAQ). A 3–5 min flicker loop drove a host from healthy → **45%** then crawled back toward 60%. https://www.youtube.com/watch?v=54eBzwYglyw  
- **Earnings-weighted:** “machines with less earnings get penalized less from offline time.” High-earning boxes are punished more per minute of downtime.  
- First week is **provisional** (third-party host guides; 48–72h utilization lag).  
- Verification eligibility wants **≥90%** reliability plus CUDA ≥12, ports, bandwidth vs VRAM, 7 GB GPU RAM, passing self-test. Favored uptime for verification: **≥99.99% (up to 99.9999%+)**.  
  https://docs.vast.ai/host/verification-stages.md · https://docs.vast.ai/host/understanding-verification.md

Client-side: `reliability2: None` **breaks naive sorts** (this house, live). Filter nulls first.

Practical client cutoffs (not official): serious rentals often want **≥0.95–0.99**. Aura/NEOXIS host writeup: below **~95%** “effectively invisible.” https://auradigitalglobal.com/blog/vast-ai-verification-gpu-server/

### 5.3 Verification / deverification

States: Unverified → Verified → (Deverified) → Unverified → …

Fully **automated**, proprietary, **supply-and-demand weighted**. High-end (B200/H200/H100/A100, 8×4090/5090, RTX PRO 6000) prioritized. Mining rigs **may never verify**. Random auto-verify ~weekly for the rest; DC/high-end may get manual tests.  
https://docs.vast.ai/host/hosting-overview.md · https://docs.vast.ai/host/understanding-verification.md

Deverify triggers (official): hosting software error → **temporary** unverified; red indicator on Machines tab; common causes = network/ports/bandwidth, storage/PCIe, nvidia-smi/NVML, container launch loops, **detected abuse/policy violations**, **reducing GPU/RAM after create**. Most errors clear **1–2 hours** after fix; sometimes needs a human.  
https://docs.vast.ai/host/verification-stages.md

Reducing hardware after listing **triggers Deverified**. Upgrades allowed, slow to reflect.

EPYC+NCCL: Vast will test distributed PyTorch; fail → possible deverification. https://cloud.vast.ai/host/setup/

### 5.4 How hosts game (and what actually works)

**Allowed / encouraged by docs:**

- Don’t take the box offline; use `schedule maint` (notifies clients) instead of hard reboot.  
- Unlist to stop *new* contracts; honor existing until latest rental end date. Breaking a DC contract = “serious penalty” (amount unpublished).  
- Keep CUDA/drivers latest; pass self-test; open **≥3 ports/GPU (100 recommended)**; symmetric bandwidth **~2.6 Mbps per GiB VRAM**, floor 100 Mbps, ceiling 500 Mbps for verify.  
- Price interruptible at power-cost so occupancy (and therefore the earnings-weighted reliability prior) stays healthy.  
- New hosts: list slightly **below** market to get first rentals and build the score (Vast blog).

**Gray / observed:**

- **Unverified + high reliability2 + rock-bottom $/hr** still shows if the renter disables the verified filter — that’s how $1.34 Moldova H100s exist.  
- **Same physical host, many offer IDs** (this house: dedupe `host_id`+`mobo_name`). Relisting can reset *perception* without resetting machine_id if they don’t delete `/var/lib/vastai_kaalia/machine_id`.  
- Recreate machine by deleting `machine_id` (official way to remove a GPU — unlist, 0 rentals, then recreate). Can be used to **shed a ruined score** — not documented as allowed gaming, but the mechanism exists.  
- Earnings-weight: a little-used box can sit offline with **less** score damage than a hot box — incentive to **park** weak machines rather than repair.  
- Silent **clock-down / 22% perf cut** on a prepaid month (Trustpilot, Aug 2026) — renter paid $231; host degraded the GPU. Reliability2 does **not** measure TFLOPS over time; DLPerf is a snapshot.  
- Support posture (Trustpilot, Travis, 13 Aug 2026): reliability is **not an entitlement**; offline with a client on the box = denied reversal; threat of deverification.

**Does not work:** asking Vast to “please verify.” Randomized. Messaging the renter is **not supported**.

### 5.5 Disputes

ToS (11 Nov 2025): disputes **between users** — Company is **under no obligation to become involved**. You release Vast from claims arising from user-user disputes. Arbitration vs Vast (JAMS, LA); **1-year** claim limit; liability cap = amount paid in **prior 3 months**.  
https://vast.ai/terms

Renter **reports**: `GET /api/v0/machines/{id}/reports` / `vastai reports <machine_id>` — problem, message, created_at. Hosts get **“Machine reported by renter”** notifications.  
https://docs.vast.ai/api-reference/machines/show-reports.md · https://docs.vast.ai/host/notifications.md

Reserved SLA hook: deverification → **full prepaid remainder back, no penalty**. That is the closest thing to a **credit remedy**. Community OD: **no public uptime SLA**. Secure Cloud is a filtered partner subset (SOC 2 Type 2 at company level per aichatdaily; BAAs on that tier).

Spent credits: **no refunds**. Unspent card credits: chat, usually yes. Crypto credits: **no**.

---

## 6. Account economics — how credits appear and how accounts earn

### 6.1 Client (renter) balance

- **Prepaid credits required.** Min deposit **$5**. https://docs.vast.ai/guides/get-started/quickstart.md  
- Card via **Stripe**; crypto via **BitPay** and **Crypto.com**. PayPal: not for *buying* credits (hosts *can* get paid via PayPal).  
- Legacy FAQ: after email **and** card verify, “you will receive a **small amount of free test credit**.” Newer quickstart does **not** repeat the free-credit sentence — treat as **maybe, small, not a strategy**.  
- Autobilling: threshold ≈ daily/weekly spend; email alert at **~75%** of threshold.  
- Zero credit → instances **stopped**, GPU released, **storage still bills**. Negative-balance **grace** sized to **average daily spend** (established accounts). No card on file → data **scheduled for deletion**. Card on file → auto-charge.  
- This house: money lives in **`credit`**, not `balance`. User 170099 held **credit ~$48.50**, `balance` $0 (2026-08-27). Spend-rate-limit on new accounts (`spend_rate_limit` error).  
- Transfer credits to another user (email, **irreversible**) or a team. https://docs.vast.ai/guides/reference/billing.md · `vastai transfer credit`  
- Invoice export from Charges (GPU / disk / up / down).

Startup program: **$2,500** free GPU credits by application + 24/7 priority support. (Page also says “up to 2,500 free compute **hours**” — wording conflict; treat as **dollar credits** unless the offer letter says hours.)  
https://vast.ai/article/vast-ai-startup-program · https://vast.ai/startup

### 6.2 Referral credits (earn without hosting)

https://docs.vast.ai/guides/reference/referral-program.md

- **3% of referred user’s lifetime spend**, forever. $1,000 spend → **$30**.  
- Cash out **75%** via Stripe Connect / PayPal / Wise; rest stays as Vast credit.  
- **Cannot refer yourself** or connected accounts.  
- Payouts require a **dedicated account that has never rented or hosted**. If the account *has* rented/hosted: cannot cash out until **referral earnings > lifetime instance spend**. Example: $300 referrals vs $855 spend → locked.  
- Public **template referral links** also pay (template performance chart on Earnings).  
- Large collabs: support@vast.ai.

Earnings page is mostly **referral** accounting even for hosts. https://docs.vast.ai/host/earning.md

### 6.3 Host earnings (separate account — mandatory)

Official: **client and host must be different accounts.** Same account “will quickly run into issues.”  
https://docs.vast.ai/host/hosting-overview.md · https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai

**Revenue split (authoritative FAQ):** *“Hosts receive **75%** of the revenue earned from successful jobs, with **25%** kept by Vast.ai.”*  
https://console.vast.ai/faq/  (Hosting → revenue/fee structure)

Matching blog: live GPU prices **~25% above what hosts earn**.

**Conflicts to ignore or footnote:** hosting calculator marketing (“Keep What You List”, “No minimum threshold to cash out”) vs docs **$20 min invoice**. Third-party MiningBoard **85/15** is **not** in Vast docs as of this research.

Payouts: Wise / PayPal / Stripe. **No** direct ACH/SWIFT/wire despite an older FAQ mentioning US ACH via Stripe — current host-payout doc says **no direct bank transfer**. Min **$20**. Invoices **Fridays**; pay the **following Friday**; first payout **~2 weeks**. **No crypto payouts** (FAQ).  
https://docs.vast.ai/host/payment.md

Host can also:

- Run **defjob** / idle jobs on own GPUs when OD empty (earn *as if* a low-priority renter of yourself — historically also set the bid floor).  
- Earn **storage** and **bandwidth** line items (same 75% unless contradicted — calculator FAQ “Does storage revenue go through the platform fee?” exists as a question; **answer not captured in the public HTML fetch**; do not assume storage is fee-free).  
- Earn **referrals** on top.  
- **Vast Finance**: revenue-based lending / equipment / sale-leaseback against host history. Example pitch: 6 months of **$15k/mo** → finance **$250k** of H100s. https://vast.ai/hosting/finance

### 6.4 Ways an account earns credit (checklist)

| Path | Who | Liquid? |
|---|---|---|
| Stripe/crypto top-up | Client | Spendable credits |
| Small test credit after verify | Client | Maybe, small |
| Startup program $2,500 | Approved startups | Credits |
| 3% referral of others’ spend | Referrer | 75% cashable only on clean account |
| Template referral | Template owner | Same as referral |
| Host 75% of GPU/storage/bandwidth | Host account | Payout ≥$20 weekly Fri cycle |
| Host defjob | Host | Occupies own GPU; not “free money” |
| Reserved refund / deverified clawback | Client | Back to credit |
| Credit transfer in | Any | Irreversible |
| Vulnerability bounty | Discretionary, not guaranteed | https://vast.ai/vulnerability-disclosure-policy |

**Not a path:** cashing host invoices into the **client** account on the same login — they made you split accounts. Trustpilot: host with unpaid earnings had to **top up a separate client account** to rent.

---

## 7. Risks

### 7.1 Host churn / vanishing machines

- Contract has a **Max Duration / lifetime**. At expiry the instance **stops**. Host *may* extend. Expired instances **may be deleted 48 hours after expiration**; cannot restart while expired.  
  https://docs.vast.ai/guides/instances/choosing/instance-types.md  
- Host **unlist** stops new rentals; **does not** kill live contracts. Host must stay up until the **latest** rental end date across contracts.  
- Unplanned: `schedule maint` — you get a notice; checkpoint. No host→client chat channel.  
- Machine **offline** → reliability hit + renter instance offline notification. Data *should* remain until destroy/expiry, but a vanished residential host is a **disk you do not own**.  
- API poll trap (official OpenAPI quirks): if `actual_status` is `exited` / `unknown` / `offline` it **will never** become `running` — destroy and retry.  
- Stop then start: GPUs may be **reassigned**; restart stuck in **scheduling** until conflict ends.  
- Zero credit + no card → **deletion**. Stopped disks keep billing through the grace window.  
- GPU Finder 4090 **in-stock week score 37%** on Vast (21–27 Aug 2026) — cheap cards **disappear from the book** even when the platform is up.

**gstd rule:** interruptible disk is **assumed loss** (`MAG_v5_VAST_TRAINING.md`). Weights and receipts come **home**; Vast is capacity, not identity.

### 7.2 Banned / restricted workloads

**Crypto mining — payment-method ban (ToS § Prohibited Activities 22, version date 10 Nov 2025):**

> If you purchase credits … **using a credit card**, you may not engage in any cryptocurrency mining, including but not limited to Bitcoin mining, Ethereum mining, or any other form of digital currency mining. … using Company or Provider resources to solve complex mathematical problems or algorithms associated with the generation or transaction of cryptocurrencies.

https://vast.ai/terms

Read tightly: the mining prohibition is **explicitly gated on card-purchased credits** (chargeback/fraud control). It is **not** a clean “mining allowed if you pay crypto.” Other clauses still bite: violate law, undue burden, malware, export. Hosts historically ran **mining idle jobs** as the defjob; that is the **host’s** GPU, not a card-funded renter job.

**Bittensor** has an **official Vast example** (open ports, `btcli`, GPU miner). That is **not** SHA mining; it is a listed use case. https://console.vast.ai/faq/ (Examples → Bittensor)

**Uncensored / abliterated LLM inference:**

- **No ToS clause bans local weights, Oobabooga, vLLM, TGI, llama.cpp, or “uncensored” models.**  
- Vast **documents** Oobabooga, vLLM, TGI, Ollama+WebUI, GGUF as first-party guides. https://docs.vast.ai/oobabooga-llm-webui.md · https://docs.vast.ai/vllm-llm-inference-and-serving.md  
- Content clause (ToS 21): do not *post/transmit/store* content that is **unlawful, racist, hateful, abusive, libelous, obscene, or discriminatory**. Inference of an uncensored model is not named. Hosts are independent contractors; Vast disclaims provider acts.  
- Separate bans: **train/improve a competing product** (ToS 17); **service bureau** (ToS 10); scrape the Website (ToS 7, 18).  
- Export: no Cuba/Iran/NK/Syria/Crimea-etc.; no military end-use in China/Russia without licenses. Vast may suspend immediately.

**Practical gstd posture (already in VAST_API_EXPERT_REFERENCE):** the box is untrusted silicon. Run **.env-less**. T0/T1 never land on Vast. Uncensored weights are a **tenant choice**, not a Vast feature — still bound by law + ToS 21 if you *serve* banned content.

Other hard limits: Linux Docker (mostly Ubuntu), **no Windows**; default isolation = unprivileged containers. Sensitive work → **Secure Cloud** filter, encrypt before upload, no creds on disk.

### 7.3 Other economic risks

| Risk | Why it hits gstd |
|---|---|
| Bandwidth surprise | Receipt undercounted if minted from $/hr |
| Stopped storage bleed | Silent drain; destroy-or-it-bills |
| Reserved lock + 5% early-exit | Illiquid credit |
| Host 75% vs renter $ | Internal “we hosted it” accounting is not 1:1 with renter invoice |
| Spend-rate-limit new accounts | Can’t dump $48 on day one |
| No involvement in renter-host disputes | Don’t rely on chargebacks as a control |
| Calculator vs realized host income | Don’t plan Rocinante ROI off the marketing calculator |

---

## 8. Mapping onto house gstd (proof-of-cost receipt units)

Internal gstd is **not** a token, not gstdcoin, not a host payout. It is a **receipt** that a job consumed scarce compute at a **demonstrable dollar cost**.

**Mint from Vast Charges rows, one receipt per destroyed instance (or per billing interval):**

```
gstd_units = f( gpu_usd + storage_usd + inet_up_usd + inet_down_usd )
meta = {
  instance_id, host_id, offer_id, gpu_name, geolocation,
  rental: on_demand | interruptible | reserved,
  reliability2, verified, dph_total, min_bid, bid,
  discount_rate, storage_gb, inet_up_gb, inet_down_gb,
  preempted: bool, duration_s,
  source: "vast.charges", invoice_id
}
```

**Do not mint from:**

- `min_bid` or GPU Finder “spot $0.01”  
- `dph_base`  
- Marketing “50% off” before prepay settles  
- GPU Finder “egress free”

**Tiering (compute ladder already filed):**

| Work | Vast type | gstd quality |
|---|---|---|
| Uptime / rehearsal / serving | On-demand, reliability2 ≥ 0.97, verified | High — receipt ≈ wall-clock × dph_total + meters |
| Stateless burn / sweep | Interruptible @ min_bid | Medium — add estimated preempt waste |
| Multi-day train | Reserved only after pause-test | High if job finishes on **same** host |
| T0/T1 / DNA | **Never Vast** | Do not mint |

Live rails already: never launch if credit < $10; hard destroy at $45 of $50; one live instance; destroy — not stop — after use (`VAST_API_EXPERT_REFERENCE.md`).

---

## 9. Source index (URLs)

**Official**

- https://vast.ai/pricing  
- https://vast.ai/terms  (v 2025-11-10)  
- https://docs.vast.ai/llms.txt  
- https://docs.vast.ai/guides/instances/pricing.md  
- https://docs.vast.ai/guides/pricing.md  
- https://docs.vast.ai/guides/instances/choosing/instance-types.md  
- https://docs.vast.ai/guides/instances/choosing/reserved-instances.md  
- https://docs.vast.ai/guides/reference/faq/rental-types.md  
- https://docs.vast.ai/guides/reference/billing.md  
- https://docs.vast.ai/guides/reference/faq/billing.md  
- https://docs.vast.ai/guides/reference/referral-program.md  
- https://docs.vast.ai/guides/get-started/quickstart.md  
- https://docs.vast.ai/guides/instances/storage/types.md  
- https://docs.vast.ai/guides/reference/notifications.md  
- https://docs.vast.ai/host/hosting-overview.md  
- https://docs.vast.ai/host/optimization-guide.md  
- https://docs.vast.ai/host/understanding-verification.md  
- https://docs.vast.ai/host/verification-stages.md  
- https://docs.vast.ai/host/payment.md  
- https://docs.vast.ai/host/earning.md  
- https://docs.vast.ai/host/market-metrics.md  
- https://docs.vast.ai/host/notifications.md  
- https://docs.vast.ai/api-reference/machines/list-machine.md  
- https://docs.vast.ai/api-reference/machines/set-min-bid.md  
- https://docs.vast.ai/api-reference/instances/change-bid.md  
- https://docs.vast.ai/api-reference/instances/prepay-instance.md  
- https://docs.vast.ai/api-reference/machines/show-reports.md  
- https://docs.vast.ai/cli/reference/change-bid.md  
- https://docs.vast.ai/cli/reference/set-defjob.md  
- https://console.vast.ai/faq/  
- https://cloud.vast.ai/create/  
- https://cloud.vast.ai/host/setup/  
- https://cloud.vast.ai/host/market/  
- https://vast.ai/hosting/calculator  
- https://vast.ai/hosting/finance  
- https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai  
- https://vast.ai/article/vast-ai-startup-program  
- https://vast.ai/vulnerability-disclosure-policy  
- https://docs.vast.ai/oobabooga-llm-webui.md  

**Dated third-party snapshots**

- https://www.usagepricing.com/blueprint/vast-ai  (API capture 2026-07-14)  
- https://www.aichatdaily.com/tools/vast-ai  (24 Aug 2026 listing sample)  
- https://gpufinder.dev/providers/vast · /gpu/rtx-4090 · /gpu/h100  (27 Aug 2026 13:16 UTC)  
- https://miningboard.com/guides/vast-ai-bid-pricing  (host lore, 27 Aug 2026)  
- https://www.trustpilot.com/review/vast.ai  
- https://costbench.com/software/ai-gpu-cloud/vast-ai/  

**This repo**

- `docs/ref/VAST_API_EXPERT_REFERENCE.md`  
- `state/vast/market_watch.jsonl` (2026-08-27 15:54–16:29Z)  
- `docs/ref/MAG_v5_VAST_TRAINING.md`  

---

## 10. Open / unproven (do not pretend)

- Closed-form **reliability2** equation (earnings weight exists; coefficients unpublished).  
- Interruptible **clearing rule** (highest bid runs; whether you *pay* your bid or second price is **not** in Vast docs; usagepricing’s “second-price” is unverified).  
- **Preemption MTTI** — unpublished.  
- Whether **storage/bandwidth** take the same 75/25 host cut.  
- Current existence/size of **signup test credit** (old FAQ yes, new quickstart silent).  
- Host calculator vs realized occupancy (Trustpilot: calculator can be 10× optimistic).  
- Mining on **crypto-paid** renter credits — ToS 22 is card-specific; do not treat that as a green light.  
- `PUT /asks/{id}/` vs legacy `PUT /instances/?id=` — new path still untested by this house.

---

*End. Chat is heat; this file is the oracle map. Next empirical step: dump one live `GET /api/v0/bundles/` offer’s `storage_cost` + `inet_*_cost` percentiles into `state/vast/` so gstd planned-receipts stop using ~$0.10/GB/mo folklore.*
