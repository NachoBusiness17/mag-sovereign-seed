# Bittensor Subnet Study for a Data-Scoring / Verifier Lane
**Work Order:** `WO_BITTENSOR_SUBNET_STUDY_20261016` · **Date:** `2026-10-17` · **Seat:** `Bob` (Antigravity Primary)

## Executive Verdict (TL;DR)
- **Validator Registration / Stake:** **NO-GO** (`$0` doctrine violation — requires significant staked `TAO` weight to hold a validator permit and emit non-trivial dividends under Yuma Consensus).
- **Miner / Open-Source Verifier Kit (`RART` + `lane_hoeffding.py` + `rope_scorer.py`):** **CONDITIONAL GO (Phase 2)** — only after GSTD `SettlementMasterV3` settles its first live task on TON. Wrapping our existing three-axis reliability scorer (`label agreement` + `RART semantic reason agreement` + `rope_scorer` strand survival) as a standalone open-source validator module costs ~150 lines of Python (`$0` capital) and positions the fleet as the **instrument supplier** rather than a capital-staked player.

---

## 1. How Validator Scoring & Emissions Flow Works in Practice (`SN13` Reference Shape)
*Tri-state: **Supported** (public Bittensor / Macrocosmos SN13 documentation & Yuma Consensus specification).*

- **The Loop (Miner ↔ Validator ↔ Yuma Consensus):**
  1. **Miners** continuously scrape, index, or generate domain artifacts (in **SN13 Data Universe** by Macrocosmos: X/Reddit/web social streams stored in local SQLite/Parquet indices and committed via HuggingFace/content hashes).
  2. **Validators** issue randomized spot-check challenges to miners:
     - **Freshness score:** Timestamp recency of indexed rows (exponential decay curve — identical in math to our `SMELL_PHEROMONE_STEERING` reader-side decay).
     - **Uniqueness / Anti-duplication score:** Penalizes miners serving overlapping or copied buckets.
     - **Credibility / Spot-check verification:** Validators independently fetch a random sample (`k` rows) from the source platform or re-run the verification check; if a miner's sample fails authenticity, its credibility multiplier drops multiplicatively toward `0`.
  3. **Weight Vector Submission:** Every tempo (~360 blocks, ~72 minutes), each validator submits a weight vector $W_i = \langle w_{i,1}, \dots, w_{i,n} \rangle$ over all miners in the subnet to the Subtensor chain.
  4. **Yuma Consensus (Clipping Against Collusion):** Subtensor computes the stake-weighted median across validators. Any validator whose weights deviate above the consensus clip threshold ($\kappa = 0.5$ stake-majority) has its outlier weights clipped and loses validator trust/dividends.
  5. **Emissions Split (Dynamic TAO / `dTAO` post-2025/2026 upgrade):** Subnet alpha emissions split **41% to miners (incentive)**, **41% to validators + stakers (dividends)**, and **18% to subnet owner**, scaled by the subnet's alpha pool price/liquidity relative to root `TAO`.

---

## 2. Stake & Registration Cost Today (Miner vs. Validator)
*Tri-state: **Supported** on mechanism; **Fuzzy** on exact intraday `TAO` spot price (no live market ticker queried per $0 offline discipline).*

| Role | Entry Cost / Burn | Ongoing Capital Requirement | Immunity / Deregistration Risk |
| :--- | :--- | :--- | :--- |
| **Miner (`UID` slot)** | Dynamic registration burn (`0.05 – 1.0 TAO` typical on active subnets, recycled/burned depending on subnet demand) | `0 TAO` staked required; needs 24/7 reachable IP/port (`axon`) + storage/compute | **High:** Brief immunity period (~few hours to 1 day); lowest-scoring UID at the end of immunity is deregistered when a new miner registers. |
| **Validator (with Permit)** | Registration burn + **Top-64 Stake Floor** (often `1,000+ TAO` via self-stake or delegated alpha stake to hold a Validator Permit) | Must maintain top-64 stake weight + run continuous evaluation requests (`dendrite`) | **Capital-gated:** Without top-64 stake weight, a node cannot submit consensus weights or earn validator dividends. |

**Key Takeaway:** Running a **validator** directly violates the fleet's `$0` capital law unless backed by external delegated stake. Running a **miner** requires a small registration burn (non-zero `TAO`) and exposes that burn to immediate loss if the miner's host (`Bob` or `t90`) drops offline or gets out-scored after the immunity window.

---

## 3. Engineering Cost to Wrap `Band` / `RART` / `Hoeffding` / `Rope` as a Subnet Scorer
*Tri-state: **Supported** (measured directly against our local organs on `Bob`).*

Our existing verification stack on `Bob` already computes the exact multi-axis vector a reasoning/audit subnet validator needs:
1. **Axis 1 — Label Agreement (`work_orders.json` / cross-band fold):** Multi-substrate consensus across uncorrelated model families.
2. **Axis 2 — Semantic Reason Agreement (`WO-RART-METAJUDGE`):** Verifies *why* two verifiers reached a verdict (catches lucky guesses and keyword-only overlap).
3. **Axis 3 — Strand Survival (`rope_scorer.py`):** Measures whether a model preserves conflicting evidence (`PRESERVE` vs `ERASE` pair) without sycophantic collapse.
4. **Statistical Gate (`lane_hoeffding.py`):** Computes the Hoeffding confidence bound ($\epsilon = \sqrt{\ln(2/\delta)/(2n)}$) so weights are only sealed once sample size $n$ crosses tolerance.

**Wrapper Effort (~1–2 afternoons, ~150 LOC Python):**
- A single adapter module (`bittensor_rart_validator.py`) mapping `forward(synapse)` → `[rope_scorer, rart_metajudge, lane_hoeffding]` → `self.scores` weight vector.
- However, per the **Fox Clause** (`RED_QUEEN_CONTACT_RACTOR_20261017.md`), shipping this as an **open-source scoring library** that existing Bittensor subnet owners/validators can import is strictly superior to paying `TAO` registration burns ourselves.

---

## 4. Revenue Realism vs. GSTD Rails
*Tri-state: **Supported**.*

| Dimension | Bittensor Subnets (`TAO` / `dTAO`) | GSTD Rails (`TON` Jetton + `SettlementMaster`) |
| :--- | :--- | :--- |
| **Upfront Capital** | Requires `TAO` for UID registration burn + `1,000+ TAO` stake for validator permit | Testnet live at `$0`; Mainnet V3 redeploy + pause script costs `< $1` (`~0.2 TON`) |
| **Hardware Fit** | Commodity miners get crushed by GPU farms on compute subnets; only niche scraping/scoring subnets fit CPU/free-tier | Purpose-built for heterogeneous bodies (`desktop` + `Bob` + `t90` + `pixel-11-pro`) + MCP torrent mesh |
| **Sovereignty / Custody** | Deregistration wipes your UID if your residential connection blinks | We hold the `SettlementMasterV3` hardening patch (`fix/settlement-hardening`, `e395828`) and the 3-body mesh |
| ** Cryptographic Proof** | Yuma Consensus = stake-weighted subjective agreement among validators | `SettlementMasterV3` + `TAILS_LEDGER_SPEC` = deterministic SHA-256 quorum over `taskId + workerAddr + resultHash + computeUnits + bonusAmount` |

---

## 5. Final Recommendation & Falsifier
- **Decision:** **NO-GO** on spending capital or `TAO` to register a Bittensor validator or miner right now. **KEEP ON SHELF** as an export target for our scoring organs (`RART` + `rope_scorer.py` + `lane_hoeffding.py`).
- **Falsifier:** If a Bittensor reasoning/verification subnet offers a `$0` faucet/grant registration path OR an external validator delegates stake to run our `RART + Hoeffding` scoring adapter at zero capital risk to the operator, reopen this order and wire the 150-line adapter.
