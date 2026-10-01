# BIBLIOGRAPHY MAP — papers ↔ fleet subsystems (law 18, 2026-09-11)

**THE POINT:** when a system is upgraded, this map says which research it
instantiates and where the new piece connects. One row per paper: ref,
subsystem, what it gives us, status, where it's used in the fleet. Deepseek
pad-outs (cheap lane) generate adjacent-literature scaffolding per intake;
rows land here.

Status vocabulary: PRIMARY-READ (we read the source), SECONDHAND (via posts),
CLASSICAL (established), INTERNAL (our own verified cards), UNVERIFIED.

## THE UNNAMED DEBT — retrieval plans (salon wave 5, provenance [V]=held-from-training, †=lowest confidence; ALL status: RETRIEVAL-PLAN until primary pulled + hashed)

The salon's central finding, adopted as law: our two load-bearing claims —
append-only record, validity-by-independent-convergence — each have canonical
citations in fields our bibliography never drew from (Dynamo/Merkle for the
record; Hurlbert 1984 for replication). Nine frontier models missed them in
the same direction. Adjacent fields are mined ON PURPOSE from now on.

**Cache & serving math (the falsifier's home):**
- Belady 1966 (IBM SysJ) — the oracle ceiling [V]
- Mattson et al. 1970 — stack algorithms; why aggregate hit rate hides segment effects [V]
- LRU-K (O'Neil 1993), ARC (Megiddo-Modha 2003), LeCaR (Vietri 2018)† — classical's adaptive ladder; beating LRU proves little, beating ARC proves something [V]
- PagedAttention/vLLM (Kwon 2023, SOSP) — tiered KV paging is this paper; the KV-OS's direct ancestor, never named in four rounds [V]
- Mooncake (Qin 2024, 2407.00079)† — strongest existing KV-as-OS production system; our doctrine competes with it [V]
- Pope 2022 (2211.05102) — the prefill/decode asymmetry underneath the 778x [V]
- Kraska 2018 learned indexes — DERIVE is learned indexing with a KV costume [V]

**Economics & routing:** FrugalGPT (2305.05176) — cheapest-lane-meets-bar formalized; RouteLLM (2406.18665)† — learned tier routing; provider prompt-caching price docs (~10% ratio) [S]

**Record, deletion, unsaying:** AGM 1985 — deletion-semantics gap is a 40-year-old field (retract/contract/revise); Hansson belief bases = materialized-view-over-append-only; Dynamo 2007 — tombstones/Merkle anti-entropy ("orphan knots are a solved pathology"); Haber-Stornetta 1991 — the hash chain's actual ancestor; Merkle 1987; Boneh-Lipton 1996 — cryptographic deletion; GDPR Art.17 — the external constraint that forces deletion to ship; Dolstra 2006 (Nix) — "behavior follows bytes" is a thesis with a build farm [V]

**Measurement & the Red Ledger:** Hurlbert 1984 — pseudoreplication (the word that killed nine-model invariants; ecology settled it 1984); Simmons-Nelson-Simonsohn 2011 — researcher degrees of freedom, the Red Ledger's formal case; Gelman-Loken forked paths†; Nosek 2018 preregistration revolution; Pocock 1977 group-sequential (the α=0.029 five-look rule); NIST randomness beacon; Zheng 2023 LLM-as-judge biases; Self-Consistency 2022 — convergence-as-validity's honest limits [V]

**Groups & bias:** Stasser-Titus 1985 hidden profiles (what the four-condition experiment breaks on); continued-influence effect (why bare RETRACT re-presents error); Dietterich 2000 — decorrelation is the ensemble's whole value; five personas of one prior are an ensemble of one; Mandelbrot 1967 — the coastline's true source [V]

**Governance & failure:** Greshake 2023 indirect injection (tool drift is a security class); Instruction Hierarchy (2404.13208)†; Goodhart taxonomies (1803.04585); Fagan 1976 — one-builds-one-verifies with defect numbers; Leveson STAMP — safety as control problem (the referee is folk-STAMP); Lamport Part-Time Parliament — "any seat drives" is leader election with impossibility bounds that bite at split-brain; SWE-bench/τ-bench — the benchmark lane's two canonical templates; CoT/ReAct 2022 — trace-as-state scooped at the prompt layer; our delta is the cache layer; MCP spec — the 950 tools are one spec away from infrastructure [V]

**EXTRACTION PROTOCOL EXECUTED (2026-09-11 night) — six Tier-3 gate rows upgraded RETRIEVAL-PLAN → PULLED+HASHED.** Receipts with content hashes + verbatim excerpts at docs/report_v1/sources/receipts/: PagedAttention 2309.06180 (sha e78143719241b48b), Mooncake 2407.00079 (e087ba864b1350dc), CoT 2201.11903 (f68502ec31b42f5f), ReAct 2210.03629 (ce203c4840ecbde7), SWE-bench 2310.06770 (657fd960559ce3eb), FrugalGPT 2305.05176 (805e8a26049e7c0e). Remaining unnamed-debt rows stay RETRIEVAL-PLAN until their pulls.

**ADJACENT-FIELD SWEEP (standing, next unmined field): QUEUEING THEORY.** The mesh is a queueing system; Little's Law (L = λW) directly governs wave cadence — width × latency = work-in-flight — and the spawn-2 rotation is an admission-control policy nobody has named as one. Field never touched by the corpus before this line.

## KV OS (addressing / paging / scheduling / policy / metering)


🆕 **2026 wave (deepseek seam return, full annotated bibliography + BibTeX at
docs/report_v1/SECTION2_KVOS_bibliography.md):**

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| PBKV (arXiv 2605.06472) | policy | PREDICTION-based KV management for DYNAMIC agent workflows — predicts upcoming agent invocations, prefetch/evict by reuse potential; 1.85x vs LRU, 1.26x vs KVFlow. **Plan-PREDICTED twin of our plan-KNOWN organ** (we read the queue; they infer it). Falsifier refines to: plan-KNOWN beats plan-PREDICTED | PRIMARY (bibliography row) | report section 2 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| RoleKV (OpenReview, anonymous ARR) | policy/addressing | role-aware eviction; **inverted age-importance** — oldest blocks (system prompts, tool outputs) stay hot, newest CoT decays fastest; 31% fewer preemptions, 1.34x speedup. **Published twin of pin-the-scaffold** | PRIMARY row, authors anonymous | report section 2 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+1 more) |
| CacheWise (arXiv 2606.16824) | paging+policy | coding-agent KV workloads; prefix-aware scheduling + reuse-aware eviction in vLLM; 2-2.6x fewer evictions, 3.5x faster sessions; RELEASED real coding-agent traces = ready-made corpus for our P2 Bellman replay | PRIMARY row | P2 replay corpus · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| KVFlow (arXiv 2507.07400, NeurIPS 2025) | scheduling | static agent-workflow caching; Agent Step Graph; steps-to-execution eviction + prefetch; the static baseline PBKV beats | PRIMARY row | report section 2 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| TokenCake (arXiv 2510.18586, EuroSys'27) | scheduling | temporal scheduler (offload idle KV during tool-call stalls) + spatial scheduler (critical-path agents protected) | PRIMARY row | report section 2 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| Shen et al. 2606.21238 (ICLR-W AdaptFM) | policy | adaptive recency/frequency split; +10.8% hit rate — the classical-baseline rung on the falsifier ladder | PRIMARY row | P2 baselines · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md |
| KV-cache surveys (Jiang ACL'26 Findings; Li 2412.19442) | surveys | field maps for the report's related-work | PRIMARY rows | report section 2 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| DeepSeek Harness + Agent Teams (official + 3 third-party plugins) | mesh | spawnTeammate fresh/fork FORMALIZED; durable peer messaging; shared task boards; version-pinned plugins | PRIMARY rows | report section 3 |
| τ^τ-bench (2609.04611) | eval | building-the-agent-as-the-task; 23.9% pass vs 82.2% expert ceiling; outer loop on τ-bench | PRIMARY row | report eval section · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| HAL (2510.11977, ICLR'26) | eval | 21,730 rollouts / $40k; models×scaffolds×benchmarks; **higher reasoning effort REDUCED accuracy in most runs** — nuance for the effort-scheduling organ | PRIMARY row | effort scheduler · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| Exgentic / General Agent Evaluation (2602.22953) | eval | architecture swings results 12 points within one model — scaffold matters more than backbone on 4/6 benchmarks | PRIMARY row | mesh section · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+2 more) |
| swe-router (Arora, MIT-0) | metabolism | cheapest-model-that-clears-the-bar routing, productized | PRIMARY row | effort scheduler · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+1 more) |



| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| DeepSeek-V4.1-Flash Tech Report (HF, 51pp, 09-10) | paging+policy | CED 8B/16B asymmetric active; CSA2; FP4 KV 890 B/token; SWA Bounded Replay; Engram hashed n-gram memory; DSpark draft-verify | PRIMARY-READ | watch/inbox/DESK_DSV41FLASH_20260911.md |
| GVA — Grouped Value Attention (FrontiersMind, 16pp) | policy+addressing | DERIVE action; fidelity ladder EXACT/QUANTIZED/DERIVABLE; keys = values × absorbed map; 45-47% scalar cut vs GQA (toy scale) | PRIMARY-READ (toy-scale claims) | KV_OS_CHARTER GVA section · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/FRONTIER_PROMPT_V1.md (+3 more) |
| LMCache (github/LMCache/LMCache; paper cited secondhand) | paging+metering | tiered GPU/CPU/SSD/remote; CUDA-IPC sharing; claim: up to 15x throughput with vLLM | SECONDHAND | desk fold 09-11 (bot4/bot1) · ⚠ DUST-RELINK 2026-09-11: consulted_by -> handoff/OX_MEGA3_t0554.json (+7 more) |
| W3_CACHE_IDENTITY (internal card, 09-07) | addressing | byte-exact prefix = 778x prefill; one-byte HEAD drift re-costs prefill; mutable bytes at tail | INTERNAL | KV_OS_CHARTER v0 hook · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+6 more) |
| GROUNDING_WAVE ledger (internal, live) | metering | cache share 0.9437 CONFIRMED; hash-chained tri-state ground | INTERNAL | KV_OS_CHARTER metering · ⚠ DUST-RELINK 2026-09-11: consulted_by -> mag/bash_local.py (+67 more) |
| Belady 1966 / Bellman optimality (classical) | policy | eviction as MDP; Belady-optimal under foresight; plan-oracle = our novelty | CLASSICAL | KV_OS_CHARTER Bellman organ · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+6 more) |
| SHEPHERD / MetaHarness / Tree-GRPO (via @marfinxx) | policy | REVERT action; pause/revert/fork execution; −62% recovery token burn (claims) | UNVERIFIED | desk fold seven 09-11 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/INTAKE_STRACE_EDG_20260904.md (+1 more) |
| Kimi K3 CPU 8.24GB run (via @HuggingModels) | paging | degenerate cold-paging endpoint: 32 s/token — hot-set principle boundary proof | SECONDHAND | desk fold seven 09-11 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/inbox/DESK_FOLD_SEVEN_20260911.md |
| WaveNet (van den Oord 2016) | addressing (lineage) | autoregressive fast inference = custom state mgmt + gather, pre-KV-cache naming | CLASSICAL | desk fold 09-11 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> state/arxiv/2026-09-07/2609.04797v1.txt (+2 more) |
| arXiv 2309.06180 PagedAttention (vLLM, SOSP'23) | paging | tiered KV paging; KG receipt evidence that caching improves cost/latency but adds no semantic context capacity | PRIMARY-READ (pdf sha-pinned) | KG_PDFS_RECEIPT_20260901 + report_v1 receipts · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/sources/receipts/2309.06180.md (+6 more) |
| arXiv 2311.04934 Prompt Cache (MLSys'24) | paging/policy | modular attention reuse for low-latency inference; same no-new-capacity cluster as PagedAttention | PRIMARY-READ (pdf sha-pinned) | KG_PDFS_RECEIPT_20260901 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2407.00023 Preble | scheduling | distributed prompt scheduling + KV reuse across servers (1.5-14.5x latency claims) | PRIMARY-READ (pdf sha-pinned) | KG_PDFS_RECEIPT_20260901 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/KG_STORE/catalog.jsonl (+4 more) |
| arXiv 2609.02737 Declarative Attention (KAIST+DeepMind) | policy/addressing | LMs control their own attention via tags; tag-driven KV masking cut attended tokens 52%; cite-gate 5/5 vs html | PRIMARY-READ (html, 5/5) | PURPLE_HARVEST_B3 + TRIAGE_HAUL_BOT_01 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> mag/decl_attention.py (+4 more) |
| arXiv 2609.02702 Trace as State (Zou & Tang, Z.ai) | head policy + trajectory lens | prepending first-pass reasoning beats appending 26/27; append has exponential worst-case memory | PRIMARY-READ (abstract) | DESK_TRACE_AS_STATE + FRONTIER_PROMPT_V1 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/FRONTIER_PROMPT_V1.md (+3 more) |
| arXiv 2607.08032 What to Keep, What to Forget | policy survey | compaction as rate-distortion (minimize distortion per bit kept); field map of MemGPT/ACON/FoldGRPO; rejected as vocab donor | SECONDHAND | RIB_COMPACTION_DOC + NIGHT_EXTERNAL_MEMORY · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+7 more) |
| arXiv 2606.23525 SelfCompact (Li et al.) | policy | model compacts itself via a callable tool + when/when-not rubric; +18.1pp math, 30-70% lower cost, no fine-tune | SECONDHAND | NIGHT_EXTERNAL_MEMORY_20260911 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+6 more) |
| arXiv 2605.08580 Slipstream (Chen et al.) | policy | async compaction while the agent keeps running; judge validates summary against actual next steps; +8.8pp accuracy | SECONDHAND | RIB_COMPACTION_DOC + NIGHT_EXTERNAL_MEMORY · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+6 more) |
| arXiv 2608.20953 Quantization-Aware Healing | paging/quantized fidelity | recovers compressed 4-bit models through teacher distillation — feed for the EXACT/QUANTIZED/DERIVABLE ladder | SECONDHAND | FRONTIER_DISPATCH_001_COMPLETE · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+3 more) |

| arXiv 1804.08221 | KV OS | lecar-2018  ·  Learning Cache Replacement with LRU and LFU (2018)  ·  arxiv.org/abs/1804.08221  ·  2dd8f7f571d6a663 | PRIMARY-READ (receipt sha-pinned) | docs/report_v1/sources/receipts/lecar-2018.md (+3 more) |
| arXiv 2312.07104 | KV OS | 3.1× on DeepSeek V3+MTP vs contemporaneous systems): https://arxiv.org/abs/2312.07104 · LMSYS writeup lineage via https://github.com/sgl-project/sglang | SECONDHAND | docs/ref/VAST_DEEP_GROK_THROUGHPUT.md (+1 more) |
| arXiv 2404.00456 QuaRot | KV OS | Quantized deployment  ·  QuaRot (2404.00456)  ·  Low-bit inference and rotation-based quantization | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2404.19737 | KV OS | Multi-token prediction  ·  Gloeckle et al. (2404.19737)  ·  Better training efficiency and speculative decoding | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2405.04434 DeepSeek-V2 | KV OS | MoE and KV efficiency  ·  DeepSeek-V2 (2405.04434), DeepSeek-V3 (2412.19437)  ·  Mixture-of-experts and compressed attention ideas | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2411.09688 | KV OS | WHAT: "reading about squeezed attention today" + arxiv 2411.09688 (Squeezed Attention: KV-cache compression for long-context LLMs). | SECONDHAND | watch/inbox/RESEARCH_WAVE_20260910.md (+1 more) |
| arXiv 2412.06464 Gated Delta Networks | KV OS | Linear/recurrent memory  ·  Gated Delta Networks (2412.06464)  ·  Efficient state updates and hybrid attention | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2412.19437 DeepSeek-V3 | KV OS | MoE and KV efficiency  ·  DeepSeek-V2 (2405.04434), DeepSeek-V3 (2412.19437)  ·  Mixture-of-experts and compressed attention ideas | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2501.12766 NExtLong | KV OS | Long-context synthesis  ·  NExtLong (2501.12766), EntropyLong (2510.02330)  ·  Constructing genuine long-range dependencies | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2502.03771 | KV OS | Load-bearing leads to verify: vCache (arXiv:2502.03771, verified semantic caching), | SECONDHAND | watch/GAME_PROMPT_GENOME_LEAD_20260901.md (+1 more) |
| arXiv 2507.18071 GSPO | KV OS | Sequence-level RL  ·  GSPO (2507.18071)  ·  More stable optimization for long responses and MoE | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2510.02330 EntropyLong | KV OS | Long-context synthesis  ·  NExtLong (2501.12766), EntropyLong (2510.02330)  ·  Constructing genuine long-range dependencies | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2512.02556 | KV OS | Sparse global attention  ·  DeepSeek-V3.2 (arXiv:2512.02556)  ·  Selective attention over long contexts | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2605.23296 | KV OS | Parallel Context Compaction (Cim, Topcu, Das, Kandemir, May 2026)  ·  Compacts in parallel BLOCKS instead of one seque | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_MEMORY_20260911.md (+1 more) |
| arXiv 2605.24914 | KV OS | GenCache (NeurIPS 2025, 83% hit claim), MVR-cache (arXiv:2605.24914, +37% hit claim), | SECONDHAND | watch/GAME_PROMPT_GENOME_LEAD_20260901.md (+1 more) |
| arXiv 2607.05378 | KV OS | CompactionRL (Jul 2026)  ·  RL-trains the model to write the summaries it will rely on — joint objectiv | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_MEMORY_20260911.md (+1 more) |

## Chain / memory / corpus

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| Governance paper (night-audit find, 09-11) | verkle chain | open problem = our verkle chain (external convergence) | SECONDHAND | MORNING_REPORT_20260911 |
| Slipstream + Constraint Pinning (night-audit steals) | memory frontier | async compaction; constraint pinning as memory organs | SECONDHAND | night-run cards · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+9 more) |
| Lost-record recovery census (internal, 09-11) | chain | 21,479 orphan knots; 5-tier silence coverage; pointer index | INTERNAL | MORNING_REPORT_20260911 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/WING_CHUN_MAP_20260911.md (+5 more) |
| Observer anatomy atlas (internal, 09-11) | chain analytics | rope step-collapse; Q ≈ 0.52 × mass^1.78, corr 0.993 | INTERNAL | memory index |
| arXiv 2602.20214 Right to History | verkle chain | tamper-evident action logs as a research program — external convergence for the verkle chain + training-event log | SECONDHAND | MYCELIAL_SCIENCE_MAP · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/MYCELIAL_SCIENCE_MAP.md (+3 more) |
| arXiv 2502.19519 Narrator/Archivist | corpus / state-drift | studied remedy for LLM game-master state drift: split fiction (Narrator) from state (Archivist) — the corpus primer's Fact 6 | SECONDHAND | 00_PRIMER + CORPUS_WAVE2_SYNTHESIS · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/canon/canon_world_games_cache_farming_2.txt (+7 more) |

| arXiv 1406.2294 | Chain / memory / corpus | on: Lamping & Veach, "A Fast, Minimal Memory, Consistent Hash Algorithm", arXiv:1406.2294 (2014). Prior art: Karger et al., "Consistent Hashing and Random Trees", STOC 1997 (MIT L | SECONDHAND | watch/INTAKE_JUMP_HASH_20260904.md (+1 more) |
| arXiv 2605.28258 | Chain / memory / corpus | s-single-artifact is too rigid, proposing continual generation instead (arXiv 2605.28258) — which the layered corpus directly supports. | SECONDHAND | watch/corpus/00_PRIMER.md (+1 more) |

## Lanes / models / moderation

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| arXiv 2609.09793 (GLM-5.3-Flash 320B abliteration) | moderation map + lane integrity | refusal = single weight direction at scale; public abliterated twins → pin trusted weights hash | SECONDHAND (abstract-level) | desk fold seven 09-11 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> state/arxiv/2026-09-10/2609.09793v1.txt (+4 more) |
| Densing Law (Tsinghua/ModelBest, via @itsPaulAi) | edge deployment | capability density ~2x / 3.5 months → KV OS pressure at 2GB class | SECONDHAND | desk fold 09-11 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/KV_OS_CHARTER_20260911.md |
| MiniCPM5-2B + JustRL II + DeepSWE (via @itsPaulAi/@Voxyz_ai) | edge rig + scheduling | 2B agentic at 2GB; effort-level scheduling by cost/pass-rate | SECONDHAND | KV_OS_CHARTER P3 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/KV_OS_CHARTER_20260911.md |
| ZAI_API_EXPERT_REFERENCE (internal, docs/ref) | fuel lanes | model catalog, pricing, lane mapping | INTERNAL | routing law · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/BEHAVIORAL_ROUTER_INTERFACE.md (+34 more) |
| Emergent agent languages (arXiv 2609.01491) | wrongthink map + memlang | LLMs under communication pressure invent compositional shorthand, transmitted across model generations; "can't monitor what you can't translate" — memlang is our auditable version (anchors = semantic grounding); riddler = the translation layer | RETRIEVAL-PLAN | timeline percolator · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md |
| V4.1 Flash weights ON HF (verified 09-11: 49 safetensors shards, 88 files, MIT) | Rocinante brain | weights are LIVE — refutes the "not released yet" claim in a 30.9K-view thread; one API call | PRIMARY-VERIFIED (HF API) | Rocinante P3 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/GLM53_ARCHITECTURE_PRO.md (+20 more) |
| Alibaba FLASepformer + JAEC 16K (ModelScope, open) | space ear | linear-attention speech separation (1.5-2.3x, 16-32% memory) + 22ms echo cancel; steal for Spaces capture preprocessing | SECONDHAND | space_ear v0.1 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/THE_HUM_20260911.md |
| Security stack: garak (LLM red team), HexStrike (150+ tools), PentestGPT, Lakera Guard | cage security | open-source LLM vuln scanning + pentest tooling; pairs with mantis + Mimosa | SECONDHAND | cage hardening queue · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/canon/canon_tokens_as_spores_v8.txt |
| arXiv 2602.15763 GLM-5 family tech report | fuel lanes / lineage | closest disclosure to Flash's recipe: ~10M issue-PR pairs, 160B tok, thinking blocks preserved across tool calls, human anchors vs formulaic drift — lineage evidence, not Flash proof | SECONDHAND (contents quoted) | GLM53_LINEAGE_DROP_20260901 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/ARCHIVIST_RECEIPTS.jsonl (+6 more) |
| arXiv 2508.06471 GLM-4.5 tech report | fuel lanes / lineage | MoE + thinking/direct modes; 23T-token multi-stage accounting vs docs' 15T (unresolved discrepancy worth keeping) | SECONDHAND | GLM53_LINEAGE_DROP + salon_glm53 lane_e · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/GLM53_LINEAGE_DROP_20260901.md (+6 more) |
| arXiv 2103.10360 GLM (original) | model lineage | autoregressive blank infilling with 2D positional info — the family's pretraining root, Tsinghua/Zhipu | SECONDHAND | GLM53_LINEAGE_DROP_20260901 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/GLM53_LINEAGE_DROP_20260901.md (+3 more) |
| arXiv 2606.29150 FRM flow reasoning models | lanes/models | flow/diffusion reasoning-models survey (Georgia Tech); fleet runs a generation ahead of Anthropic's map on it | PRIMARY-READ (abstract, verbatim) | STEAL_FLOW_REASONING_MODELS_20260903 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/INTAKE_AMISHA_AI_ROADMAP_20260903.md (+3 more) |

| arXiv 2305.05176 | Lanes / models / moderation | 8  ·  frugalgpt-2023  ·  FrugalGPT (2023)  ·  arxiv.org/abs/2305.05176  ·  9ff28dd137f27e3f | PRIMARY-READ (receipt sha-pinned) | docs/report_v1/sources/receipts/2305.05176.md (+5 more) |
| arXiv 2210.02414 | Lanes / models / moderation | e model, constrained hardware" identity. GLM-130B paper | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2402.03300 GRPO | Lanes / models / moderation | Reasoning RL  ·  DeepSeekMath / GRPO (2402.03300)  ·  Group-relative verifiable-reward training | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |
| arXiv 2405.02421 | Lanes / models / moderation | Knowledge?", ICLR 2024 Spotlight — arXiv:2405.02421, | SECONDHAND | watch/inbox/INTAKE_HAUL11_20260907.md (+1 more) |
| arXiv 2406.11794 DataComp-LM | Lanes / models / moderation | Data curation  ·  DataComp-LM (2406.11794)  ·  Treating dataset selection as an optimization problem | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md (+1 more) |

## Mesh / orchestration

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| GraphCode (@DanKornas, FSL-1.1-MIT) | mesh topology | graph of live agent sessions, handoff/spawn edges, persistent terminals — our mesh as product | SECONDHAND | vindication fold 09-11 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/inbox/STEAL_FOLD_RESEARCH_PIPELINE_20260911.md |
| Nielsen, info geometry (2020, free on ChapterPal) | math wing | Fisher-Rao, dually flat spaces, natural gradient — under the Bellman organ | CLASSICAL (unread) | math wing pile · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/ARCHIVIST_RECEIPTS.jsonl (+1 more) |
| OpenDesign Arena benchmark (09-10) | model selection | V4.1 Flash 98% of Astra at 1.4% cost on design tasks | SECONDHAND (marketing-shaped) | DESK_DSV41FLASH tri-state · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/inbox/DESK_DOGFOOD_VISUAL_DECK_20260911.md (+2 more) |
| arXiv 2507.01701 Blackboard-architecture LLM MAS (Han & Zhang) | mesh / board | doctrinal source for the estate's blackboard design: shared board state, control-component selection, round loop → switchboard/hypervisor doctrine | PRIMARY-READ (pdf sha-pinned) | KG_PDFS_RECEIPT_20260901 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> state/_astra_triangulation.md (+3 more) |
| arXiv 2503.02068 AGDebugger | mesh debugging | message browsing + EDIT/RESET of prior turns + intervention injection for multi-agent runs; nearest neighbor — full read owed before any build | SECONDHAND | WAR_ROOM_PRIOR_ART_20260909 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/ASTRA_ASK_WAR_ROOM_20260909.md (+3 more) |
| arXiv 2304.03442 Generative Agents (Smallville) | mesh coordination | 25-believable-agents sim; coordination-without-protocols prior art for the room | SECONDHAND (arXiv-verified) | WAR_ROOM_PRIOR_ART + salon fetch_log · ⚠ DUST-RELINK 2026-09-11: consulted_by -> handoff/KABUKI_AI_DEEP_RESEARCH_FOR_GROK.md (+5 more) |
| arXiv 2406.04692 Mixture-of-Agents (Wang et al.) | swarm / ranking law | aggregated weak agents beat one strong model (AlpacaEval 2.0) — error-decorrelation prior behind the T1 voting arms | SECONDHAND | SWARM_RESEARCH_LEDGER + octant ranking_law · ⚠ DUST-RELINK 2026-09-11: consulted_by -> handoff/KABUKI_AI_DEEP_RESEARCH_FOR_GROK.md (+6 more) |
| arXiv 2607.07702 STRACE / Execution Dependency Graphs (Microsoft) | trajectory lens / spawn tree | execution dependency graphs for agent runs; steal target for spawn-tree verification | SECONDHAND | INTAKE_STRACE_EDG_20260904 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/CORPUS_INDEX_FOR_BOTS_20260906.md (+6 more) |
| arXiv 1805.00899 AI safety via debate (Irving et al.) | mesh arbitration / observer | judged debate as oversight — the Observer arm's ancestor | SECONDHAND | WAR_ROOM_PRIOR_ART_20260909 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/ASTRA_ASK_WAR_ROOM_20260909.md (+3 more) |

| arXiv 2112.07236 | Mesh / orchestration | ments Boolean gates (Adamatzky, Schubert, 2021)  ·  Logic emerges from handoff topology, not one model  ·  handoff loop , scheduler triage | SECONDHAND | docs/ref/MYCELIAL_SCIENCE_MAP.md (+1 more) |
| arXiv 2304.10675 | Mesh / orchestration | s; memristive dynamics (Adamatzky et al., 2023)  ·  Timing badge + training event per agent turn  ·  mag/desk timing.py , memory/training | SECONDHAND | docs/ref/MYCELIAL_SCIENCE_MAP.md (+1 more) |
| arXiv 2506.09579 | Mesh / orchestration | 1. Power Diagram Enhanced Adaptive Isosurface Extraction (arXiv 2506.09579, 2025). | SECONDHAND | watch/INTAKE_MESH3D_SWEEP_SHIFT7_20260904.md (+1 more) |
| arXiv 2508.16792 | Mesh / orchestration | arXiv 2508.16792  ·  "Neuromorphic Simulation of Drosophila Melanogaster" — FlyWire connectome on neuromorph | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_CONNECTOME_20260911.md (+1 more) |
| arXiv 2509.06341 | Mesh / orchestration | (arXiv:2509.06341) — measured multi-turn agent coordination. | SECONDHAND | watch/ASTRA_ASK_WAR_ROOM_20260909.md (+1 more) |
| arXiv 2604.00157 | Mesh / orchestration | 1. Dual Contouring of Signed Distance Data (arXiv 2604.00157, 2026). | SECONDHAND | watch/INTAKE_MESH3D_SWEEP_20260904.md (+1 more) |
| arXiv 2604.02460 | Mesh / orchestration | beat several multi-agent architectures on multi-hop reasoning (arXiv:2604.02460). | SECONDHAND | watch/MAG_CHORD_V4_ADOPTED_20260903.md (+1 more) |
| arXiv 2605.08013 | Mesh / orchestration | ing CLI Agents with Structured Action Credit under Selective Observation. arXiv:2605.08013, 2026. https://arxiv.org/abs/2605.08013 This deposit contains the reference list of the p | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-08.md (+1 more) |

## Eval / methodology / red-team

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| arXiv 2406.12045 τ-bench (Sierra+Princeton) | eval | tool-agent-user customer service; pass^k metric, DB-state objectives — the benchmark lane's outer-loop template | SECONDHAND (arXiv-verified) | salon fetch_log + report_v1 BibTeX · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/report_v1/FRONTIER_REVIEW_001.md (+3 more) |
| arXiv 2607.28956 MerchantBench | eval | e-commerce agent benchmark (365-day / 98,843 records; best LLM = 27.3% of human) | PRIMARY-READ (abstract sha-pinned) | KG_SOURCES_20260901 + INVARIANT_SHEET · ⚠ DUST-RELINK 2026-09-11: consulted_by -> state/_astra_triangulation.md (+16 more) |
| arXiv 2609.04148 Terminal-Universe (Qwen) | eval | turns agent trajectories into scalable terminal environments | SECONDHAND | INTAKE_TERMINAL_UNIVERSE_20260904 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> state/arxiv/2026-09-06/2609.04148v1.txt (+4 more) |
| arXiv 2606.11217 Preregistration for AI-agent experiments | methodology / Red Ledger | exact model snapshots + verbatim prompts + checkpoint hashes as the preregistration standard; external anchor for Astra's A2 snapshot-pin table | PRIMARY-READ (html v1) | BUDGET_MANIFEST_SKELETON + NIGHT_EXTERNAL_EVAL · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+6 more) |
| arXiv 2507.20526 UK AISI agent red-teaming | cage security | AISI's agent red-team methodology behind the Grayswan arena challenge set | SECONDHAND | GRAYSWAN_ARENA_STEAL · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/GRAYSWAN_ARENA_STEAL.md (+2 more) |

| arXiv 1706.03741 | Eval / methodology / red-team | Reinforcement Learning from Human Preferences — Christiano et al., 2017. arXiv:1706.03741 (learning what "good" means from judgments — reward-modeling, the ancestor of the gate). | SECONDHAND | docs/SOURCES_MAP.md (+1 more) |
| arXiv 2402.05863 | Eval / methodology / red-team | (arXiv:2402.05863) and the seller-bargaining benchmark | SECONDHAND | watch/ASTRA_ASK_WAR_ROOM_20260909.md (+1 more) |
| arXiv 2409.11363 | Eval / methodology / red-team | on-scientific-tasks-introducing-replicatorbench · https://www.alphaxiv.org/abs/2409.11363 | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_EVAL_20260911.md (+1 more) |
| arXiv 2410.08650 | Eval / methodology / red-team | Marc Duclusaud, Grégoire Passault, Vincent Padois, Olivier Ly — arxiv.org/pdf/2410.08650". | SECONDHAND | watch/INTAKE_JACKVIAL_SIM2REAL_FRICTION_20260904.md (+1 more) |
| arXiv 2510.26585 | Eval / methodology / red-team | 0% on GAIA benchmark without hurting success rates." — https://arxiv.org/html/2510.26585 | SECONDHAND | watch/OPS_RESEARCH_001_20260901.md (+1 more) |

## Corpus / math wing / games

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| arXiv 1201.0749 No 16-Clue Sudoku (McGuire et al.) | games / math wing | exhaustive search: 17 givens is the uniqueness minimum — the constraint-puzzle engine's verified fact | SECONDHAND (salon-verified) | salon_corpus_l1 + sudoku.DRAFT · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/GAMES_CORPUS_PRIMER_SALON_SYNTHESIS_20260901.md (+4 more) |
| arXiv 2412.17870 soap-bubble volume conservation | corpus / math wing | stretched bubble conserves volume; Lagrange multiplier pressure, bottleneck pinch-off — the physics under the token/bubble metaphor | SECONDHAND | SALON_PACK_BUBBLES + DESKTOP_CORPUS_DATED · ⚠ DUST-RELINK 2026-09-11: consulted_by -> docs/ref/canon/canon_bubbles_holographic_transfer.txt (+6 more) |
| arXiv 2609.02882 Lamzouri zeta zeros | math wing | new proof: >67.25% of zeta zeros simple + on the critical line; intake triaged SUPPORTED | PRIMARY-READ (abstract fetched) | INTAKE_ZETA_ZEROS_20260903 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/INTAKE_ZETA_ZEROS_20260903.md (+1 more) |
| arXiv 2410.20536 Malinowski Argonauts text-games | games / prompt genome | LLM text-game designs from an anthropological classic; source of the cultural_context template | SECONDHAND | GAME_PROMPT_GENOME_LEAD_20260901 · ⚠ DUST-RELINK 2026-09-11: consulted_by -> watch/LIBRARIAN_REPORT.md (+1 more) |

| arXiv 1712.01208 | Corpus / math wing / games | learned-indexes  ·  The Case for Learned Index Structures (2018)  ·  arxiv.org/abs/1712.01208  ·  576ab74e6284d599 | PRIMARY-READ (receipt sha-pinned) | docs/report_v1/sources/receipts/kraska-2018-learned-indexes.md (+3 more) |
| arXiv 2006.01475 | Corpus / math wing / games | ith the wavelengths of light and how they are rendered" - LightOn paper (arXiv:2006.01475). | SECONDHAND | watch/LIGHT_IN_THE_LOOP_20260903.md (+1 more) |
| arXiv 2007.1558 [DOI-ARTIFACT] | Corpus / math wing / games | https://doi.org/10.61467/2007.1558.2026.v17i5.1420 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-08.md (+1 more) |
| arXiv 2201.11903 | Corpus / math wing / games | Wei et al., 2022 — Chain-of-Thought Prompting  ·  Intermediate reasoning examples can improve specified task performance  ·  Helpful inter | PRIMARY-READ (receipt sha-pinned) | docs/report_v1/sources/receipts/2201.11903.md (+1 more) |
| arXiv 2210.03629 | Corpus / math wing / games | Yao et al., 2022 preprint / 2023 conference — ReAct  ·  Reasoning interleaved with actions and observations  ·  Tool-equipped system performance | PRIMARY-READ (receipt sha-pinned) | docs/report_v1/sources/receipts/2210.03629.md (+1 more) |
| arXiv 2404.06364 | Corpus / math wing / games | everything new (Wang 2024, arXiv:2404.06364; Synced on | SECONDHAND | watch/STEAL_RESEARCH_PIPELINES_20260904.md (+1 more) |
| arXiv 2407.18384 | Corpus / math wing / games | (arXiv 2407.18384) — 6/25 REMEMBER. Sixth bibliography drop; filter | SECONDHAND | watch/INTAKE_BATCH_POPMATH_20260905.md (+1 more) |
| arXiv 2506.08725 | Corpus / math wing / games | Stop Misusing t-SNE and UMAP for Visual Analytics — arXiv:2506.08725, 2025. Interview study: practitioners routinely over-interpret spatial artifacts AND cher | SECONDHAND | watch/FRONTIER_PROJECTION_FIDELITY_20260906.md (+1 more) |
| arXiv 2510.26852 | Corpus / math wing / games | a (code-revise-iterate), Auto-Arena ELO, SC2Arena  ·  VERIFIED via 9 cites (arXiv 2510.26852 = CATArena)  ·  web search | SECONDHAND | watch/salon_research/fetch_log.md (+1 more) |
| arXiv 2512.10685 | Corpus / math wing / games | 3D Gaussian splatting model ( a href="https:& x2F;& x2F;arxiv.org& x2F;abs& x2F;2512.10685" rel="nofollow" https:& x2F;& x2F;arxiv.org& x2F;abs& x2F;2512.10685 /a ). Their refer… | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md (+1 more) |
| arXiv 2605.20520 | Corpus / math wing / games | https://arxiv.org/html/2605.20520v1 | SECONDHAND | watch/HIRE_FOLLOW_ARXIV_PROBE_20260905.md (+1 more) |
| arXiv 2606.04511 | Corpus / math wing / games | arXiv:2606.04511 (abstract re-verified against arxiv.org bytes this turn: the | SECONDHAND | watch/PURPLE_HARVEST_B4_FORECAST_20260906.md (+1 more) |
| arXiv 2606.26836 | Corpus / math wing / games | arXiv:2606.26836 (Martian; Fowler, Smith, et al.), ICLR 2026 DATA-FM Workshop Oral. | SECONDHAND | watch/INTAKE_MARTIAN_AI_FRONTIER_20260904.md (+1 more) |
| arXiv 2608.03893 | Corpus / math wing / games | NVIDIA (arXiv:2608.03893): a receipt with conditions (278ms vs 6.98s | SECONDHAND | watch/ASTRA_ASK_V3_20260909.md (+1 more) |

## Protocol
New intake → mechanism extraction → academic sweep → pad-out (deepseek lane)
→ row here within the same turn. Upgrades consult this map first (law 18).


## APPENDIX — overflow citations (batch-registered from W7_G_overflow)

| ref | subsystem | gives | status | used at |
|---|---|---|---|---|
| arXiv 2608.31036 | KV OS | 2608.31036  ·  Normalized Low-Rank Adaptation (NoRA) — nora normalized low rank  | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md (+1 more) |
| arXiv 1706.03762 | KV OS | Vaswani et al., 2017 — Attention Is All You Need  ·  The Transformer as a techni | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2307.03172 | KV OS | 2307.03172  ·  Lost in the Middle: How LMs Use Long Contexts — lost in the middl | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2310.05736 | KV OS | 2310.05736  ·  LLMLingua: Compressing Prompts for Accelerated Inference — llmlin | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2310.06839 | KV OS | 2310.06839  ·  LongLLMLingua: Accelerating & Enhancing LLMs in Long Context — lo | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2407.21783 | KV OS | etrained and instruction-tuned models. July 2024 report  ·  A released base, ins | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2408.03314 | KV OS | et al., 2024 — Scaling LLM Test-Time Compute Optimally  ·  Test-time allocation  | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2510.17776 | KV OS | Granularity is instance-level: sample-wise forgetting (2510.17776) — 1→0 transit | SECONDHAND | watch/LINEAGE_DIFF_DEEPRESEARCH_20260831.md |
| arXiv 2601.22170 | KV OS | LM-book / Karpeles. The corpus' math needs are served by primary sources (arXiv  | SECONDHAND | watch/INTAKE_BORNE_MATH_BOOK_20260903.md |
| arXiv 2603.20397 | KV OS | intel-gpu-new-in-openvino-2026-2-d71d03c27897), survey)  ·  2026 converged on 4- | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_MEMORY_20260911.md |
| arXiv 2606.22528 | KV OS | Governance Decay + Constraint Pinning (2026)  ·  7 models, 1,323 episodes: compa | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_MEMORY_20260911.md |
| arXiv 2607.00501 | KV OS | 44570048); r/rust thread; cited by name in arXiv 2607.00501 (BaseRT, native | SECONDHAND | watch/INTAKE_UZU_SPECDEC_20260903.md |
| arXiv 2608.06947 | KV OS | 4. RAG poisoning / attention-collapse, arXiv:2608.06947 (rohanpaul ai) — adversa | SECONDHAND | watch/inbox/GOPHER_DIGEST_20260901_0410Z.md |
| arXiv 2608.19920 | KV OS | arXiv:2608.19920 (rohanpaul ai 08-31 20:06) — fine-tune LLMs to match a sparse-a | SECONDHAND | watch/OPS_RESEARCH_001_20260901.md |
| arXiv 2608.26530 | KV OS | STEAL: rohanpaul ai PILOT in the Loop (arXiv 2608.26530) live self-improvement — | SECONDHAND | watch/HARVEST_DIGEST_20260901.md |
| arXiv 2310.06770 | Chain / memory / corpus | RETRIEVAL RECEIPT — 2310.06770 | PRIMARY-READ (receipt sha-pinn | docs/report_v1/sources/receipts/2310.06770.md |
| arXiv 2605.23950 | Chain / memory / corpus | CT harness/skills/memory gap feed. + harness-diff pair (2608.27472 PDG causal /  | SECONDHAND | watch/HARVEST_DIGEST_20260901.md |
| arXiv 2608.27472 | Chain / memory / corpus | success/Mtok +134%. DIRECT harness/skills/memory gap feed. + harness-diff pair ( | SECONDHAND | watch/HARVEST_DIGEST_20260901.md |
| arXiv 2608.27790 | Chain / memory / corpus | triage Credo VALID (arXiv:2608.27790) — harness primitives + provenance; flagged | SECONDHAND | watch/OPS_RESEARCH_001_20260901.md |
| arXiv 2609.03874 | Chain / memory / corpus | 2. @di zhang fdu — STAIR (arXiv:2609.03874): structure-aware retriever that | SECONDHAND | watch/PURPLE_HARVEST_TRIAGE_02_20260906.md |
| arXiv 1910.02054 ZeRO | Lanes / models / moderation | Large-scale infrastructure  ·  Megatron-LM (2104.04473), ZeRO (1910.02054)  ·  D | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md |
| arXiv 2005.14165 | Lanes / models / moderation | wn et al., 2020 — Language Models are Few-Shot Learners  ·  Task adaptation thro | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2102.05242 | Lanes / models / moderation | 309-page ML foundations PDF (arXiv 2102.05242, Moroney/Norvig lineage), | SECONDHAND | watch/INTAKE_BATCH_POPMATH_20260904b.md |
| arXiv 2104.04473 Megatron-LM | Lanes / models / moderation | Large-scale infrastructure  ·  Megatron-LM (2104.04473), ZeRO (1910.02054)  ·  D | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md |
| arXiv 2310.08560 | Lanes / models / moderation | 2310.08560  ·  MemGPT: Towards LLMs as Operating Systems — memgpt  ·  663,708  · | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2405.17766 | Lanes / models / moderation | method (arXiv 2405.17766): hide one modality at a time during pretraining, | SECONDHAND | watch/INTAKE_SLEEPFM_DISCORDANCE_20260904.md |
| arXiv 2504.12335 | Lanes / models / moderation | Black-box change detection works: "You've Changed" (2504.12335) — fixed prompts  | SECONDHAND | watch/LINEAGE_DIFF_DEEPRESEARCH_20260831.md |
| arXiv 2504.13171 | Lanes / models / moderation | https://www.letta.com/blog/sleep-time-compute/) (paper, MemGPT 2.0 coverage via  | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_MEMORY_20260911.md |
| arXiv 2506.00756 SHIFT | Lanes / models / moderation | Decay is heterogeneous: SHIFT (2506.00756) — subgroup decay localizes (some capa | SECONDHAND | watch/LINEAGE_DIFF_DEEPRESEARCH_20260831.md |
| arXiv 2507.01006 | Lanes / models / moderation | GLM-4.5V: https://arxiv.org/abs/2507.01006 | SECONDHAND | watch/GLM53_LINEAGE_DROP_20260901.md |
| arXiv 2511.13371 | Lanes / models / moderation | Mechanistic Interpretability Study — Baumgartner et al., NeurIPS 2025 / arXiv:25 | SECONDHAND | watch/FRONTIER_PROJECTION_FIDELITY_20260906.md |
| arXiv 2512.18792 | Lanes / models / moderation | The Dead Salmons of AI Interpretability — arXiv:2512.18792 (cited-by lineage): i | SECONDHAND | watch/FRONTIER_PROJECTION_FIDELITY_20260906.md |
| arXiv 2602.00986 | Lanes / models / moderation | Paper is REAL and matches: arXiv 2602.00986, "Sparse Reward Subsystem in Large L | SECONDHAND | watch/INTAKE_SPARSE_REWARD_SUBSYSTEM_20260904.md |
| arXiv 2602.01230 | Lanes / models / moderation | Harbor Laboratory); preprint arXiv:2602.01230. Nature's cookie gate refused the  | SECONDHAND | watch/PURPLE_HARVEST_TRIAGE_02_20260906.md |
| arXiv 2603.06610 CapTrack | Lanes / models / moderation | Behavioral drift ≠ capability loss: CapTrack (2603.06610) — CAN/WILL/HOW taxonom | SECONDHAND | watch/LINEAGE_DIFF_DEEPRESEARCH_20260831.md |
| arXiv 2608.24876 | Lanes / models / moderation | o any Zhipu/Z.ai announcement. Appears in generic research papers only (arXiv 26 | SECONDHAND | watch/salon_research/lane_r5_launchwatch.md |
| arXiv 2008.0277 [DOI-ARTIFACT] | Mesh / orchestration | 5–762. PubMed · DOI: 10.1098/rstb.2008.0277 . | SECONDHAND | watch/inbox/AGENT_HIVE_BEE_FUNGUS_HANDOFF_2026-08-31.md |
| arXiv 2403.02691 | Mesh / orchestration | 2403.02691  ·  InjecAgent: Benchmarking IPIs in Tool-Integrated LLM Agents — inj | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2403.08399 | Mesh / orchestration | (arXiv:2403.08399). OSINT teams run staged, | SECONDHAND | watch/STEAL_RESEARCH_PIPELINES_20260904.md |
| arXiv 2406.13352 | Mesh / orchestration | 2406.13352  ·  AgentDojo: Dynamic Env to Eval Attacks/Defenses for LLM Agents —  | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2508.00828 | Mesh / orchestration | OpenReview criticism threads), Finance Agent Benchmark (arXiv 2508.00828), Snork | SECONDHAND | watch/INTAKE_ANT_LING_FIN_20260903.md |
| arXiv 2601.13671 | Mesh / orchestration | 3. arXiv: "The Orchestration of Multi-Agent Systems: Architectures" (2601.13671) | SECONDHAND | watch/INTAKE_LEGIONS_SWEEP_SHIFT6_20260904.md |
| arXiv 2602.02276 | Mesh / orchestration | eports a multimodal agentic model. February 2026 report  ·  Separate visual-inpu | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2608.28027 | Mesh / orchestration | only, minimal fetches, no synthesis. Stacks arxiv candidates (String agentic-OS  | SECONDHAND | watch/SELF_STEAL_WINDOWS_20260901.md |
| arXiv 2608.30730 | Mesh / orchestration | Team (2026). E-Commerce Bench: Long-Horizon Evaluation of AI Agents . arXiv:2608 | SECONDHAND | watch/inbox/SALON3_FILING_20260901.md |
| arXiv 2609.04141 | Mesh / orchestration | 2. @di zhang fdu — TAHI (arXiv:2609.04141): test-time adaptation of agents | SECONDHAND | watch/PURPLE_HARVEST_TRIAGE_02_20260906.md |
| arXiv 1706.04599 | Eval / methodology / red-team | [verified] On Calibration of Modern Neural Networks — Guo et al., 2017. arXiv:17 | SECONDHAND | docs/SOURCES_MAP.md |
| arXiv 2209.13085 | Eval / methodology / red-team | 2209.13085  ·  Defining and Characterizing Reward Hacking — reward hacking  ·  8 | SECONDHAND | watch/inbox/KG_PDFS_RECEIPT_20260901.md |
| arXiv 2211.09110 | Eval / methodology / red-team | du/helm/ · https://github.com/stanford-crfm/helm · paper: https://arxiv.org/abs/ | SECONDHAND | watch/inbox/NIGHT_EXTERNAL_EVAL_20260911.md |
| arXiv 2308.03688 | Eval / methodology / red-team | , 8 envs (OS/DB/KG/DCG/LTP/HH/WS/WB), success-rate metrics  ·  VERIFIED via arXi | SECONDHAND | watch/salon_research/fetch_log.md |
| arXiv 2404.07972 | Eval / methodology / red-team | mputer-use, 369 tasks, GUI grounding, execution-based eval  ·  VERIFIED via arXi | SECONDHAND | watch/salon_research/fetch_log.md |
| arXiv 2603.15714 | Eval / methodology / red-team | Publication Practice  ·  Aggregate statistics published (e.g., arXiv:2603.15714) | SECONDHAND | docs/concepts/GRAYSWAN_NG_AISRP_BRIEF.md |
| arXiv 2608.10993 | Corpus / math wing / games | Fourier Surfaces Revisited" (arXiv 2608.10993, topic standing wave, mined | SECONDHAND | watch/INTAKE_SLIT_TRANSMISSION_20260904.md (+1 more) |
| arXiv 2608.23541 | Corpus / math wing / games | (arXiv:2608.23541). MoA stays non-negative because proposers never read each oth | SECONDHAND | watch/MAG_CHORD_V4_ADOPTED_20260903.md (+1 more) |
| arXiv 2608.27454 | Corpus / math wing / games | 25. WikiSkill law (arXiv:2608.27454): rejected proposals persist reason + root-c | SECONDHAND | watch/FLEET_CONTRACT_V5_DRAFT_20260901.md (+1 more) |
| arXiv 2608.28048 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.28048 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md (+1 more) |
| arXiv 2608.28433 | Corpus / math wing / games | 7. THE STOLEN GRAMMAR (Prove2Me, arXiv:2608.28433 — open, confirmed) | SECONDHAND | watch/THE_MARGIN_20260906.md (+1 more) |
| arXiv 2608.29530 | Corpus / math wing / games | Linzen, Smolensky — Yale/JHU/NYU/MSR; arxiv 2608.29530, 30 Aug 2026). Tweet by | SECONDHAND | watch/INTAKE_TPR_ROLE_FILLER_20260904.md (+1 more) |
| arXiv 2609.00196 | Corpus / math wing / games | Blog: krafton.ai/blog/whale/  ·  Paper: arXiv:2609.00196 (submitted 2026-08-31)  | SECONDHAND | watch/INTAKE_WHALE_HARNESS_WEIGHT_20260903.md (+1 more) |
| arXiv 2609.01437 | Corpus / math wing / games | SOURCE — @askalphaxiv tweet 2095708436977824220 (2026-09-04) → alphaxiv.org/abs/ | SECONDHAND | watch/INTAKE_HARNESSDEV_SELF_HARNESS_20260904.md (+1 more) |
| arXiv 2609.04010 | Corpus / math wing / games | views, 51 likes, 4 replies/1 quote unmined — time-box). Paper receipted: arXiv:2 | SECONDHAND | watch/INTAKE_UNO_DIFFUSION_20260904.md (+1 more) |
| arXiv 2609.04098 | Corpus / math wing / games | ~2.9x smaller. Ponytail: SUPPORTED — arXiv 2609.04098 verified live. | SECONDHAND | watch/INTAKE_XBATCH_20260905.md (+1 more) |
| arXiv 1407.3561 | Corpus / math wing / games | d] IPFS — Content Addressed, Versioned, P2P File System — J. Benet, 2014. arXiv: | SECONDHAND | docs/SOURCES_MAP.md |
| arXiv 1504.04909 | Corpus / math wing / games | ied] Illuminating Search Spaces by Mapping Elites — Mouret & Clune, 2015. arXiv: | SECONDHAND | docs/SOURCES_MAP.md |
| arXiv 2026.15906 [DOI-ARTIFACT] | Corpus / math wing / games | https://doi.org/10.17148/ijarcce.2026.15906 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-07.md |
| arXiv 2026.84791 [DOI-ARTIFACT] | Corpus / math wing / games | https://doi.org/10.22214/ijraset.2026.84791 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-08.md |
| arXiv 2104.07143 | Corpus / math wing / games | An Interpretability Illusion for BERT — Bolukbasi et al. (Google), arXiv:2104.07 | SECONDHAND | watch/FRONTIER_PROJECTION_FIDELITY_20260906.md |
| arXiv 2203.11171 | Corpus / math wing / games | Self-Consistency Improves Chain of Thought Reasoning — Wang et al., 2022. arXiv: | SECONDHAND | docs/SOURCES_MAP.md |
| arXiv 2303.10798 | Corpus / math wing / games | (authors Smith/Myers/Kaplan/Goodman-Strauss; arXiv 2303.10798; "ein Stein" etymo | SECONDHAND | watch/INTAKE_Math_files_einstein_hat_tile_20260904.md |
| arXiv 2306.05685 | Corpus / math wing / games | erbosity and self-preference biases. Zheng et al., 2023. | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2310.01798 | Corpus / math wing / games | an impossibility claim. Huang et al., 2023 / ICLR 2024. | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2310.13548 | Corpus / math wing / games | for these models or this protocol. Sharma et al., 2023. | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2312.03664 | Corpus / math wing / games | and Concordia (arXiv:2312.03664) — shared-world grounding as the | SECONDHAND | watch/ASTRA_ASK_WAR_ROOM_20260909.md |
| arXiv 2412.06769 | Corpus / math wing / games | den mechanism of a vendor's deployed assistant. Coconut, LLaDA. | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2412.14161 | Corpus / math wing / games | net, 175 tasks, GitLab/ownCloud/Plane/RocketChat + 16 NPCs  ·  VERIFIED via arXi | SECONDHAND | watch/salon_research/fetch_log.md |
| arXiv 2502.09992 | Corpus / math wing / games | ant. Coconut, LLaDA. | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2503.14647 | Corpus / math wing / games | https://arxiv.org/abs/2503.14647 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2504.11393 | Corpus / math wing / games | target-task documents (arXiv:2504.11393); QuRating (Princeton, multi-criteria | SECONDHAND | watch/PURPLE_HARVEST_DIG_RHYME_20260906.md |
| arXiv 2505.09388 | Corpus / math wing / games | variants, and post-training procedures. May 2025 report  ·  Within-family compar | SECONDHAND | watch/astra_pilot/research-blueprint.md |
| arXiv 2505.16004 | Corpus / math wing / games | ng Robustness of Concept Representations — Li, Srinivas, Bhalla et al., arXiv:25 | SECONDHAND | watch/FRONTIER_PROJECTION_FIDELITY_20260906.md |
| arXiv 2506.02634 | Corpus / math wing / games | infinite-capacity) rates of ~54–62% in real traces." — https://arxiv.org/html/25 | SECONDHAND | watch/OPS_RESEARCH_001_20260901.md |
| arXiv 2507.07969 | Corpus / math wing / games | ; n-step TD across the chunk. "Change the timescale RL reasons at." Paper arxiv  | SECONDHAND | watch/inbox/RESEARCH_WAVE_20260910.md |
| arXiv 2507.12466 | Corpus / math wing / games | implicit target EXPLICIT (arXiv:2507.12466); DsDm — model-annotated selection wi | SECONDHAND | watch/PURPLE_HARVEST_DIG_RHYME_20260906.md |
| arXiv 2509.13160 | Corpus / math wing / games | (searched EN + CN). Nearest peer work: FinSearchComp (arXiv 2509.13160, has open | SECONDHAND | watch/INTAKE_ANT_LING_FIN_20260903.md |
| arXiv 2510.24416 | Corpus / math wing / games | vast (the repo's amplitude-heterogeneity study targets Khan et al. arXiv:2510.24 | SECONDHAND | docs/ref/RESEARCH_NOTE_FLYWHEEL_BUDGET_PROJECTION.md |
| arXiv 2601.05103 | Corpus / math wing / games | arXiv:2601.05103), ClaimFlow (claim evolution across papers, arXiv:2603.16073), | SECONDHAND | watch/PURPLE_HARVEST_DIG_RHYME_20260906.md |
| arXiv 2603.16073 | Corpus / math wing / games | arXiv:2601.05103), ClaimFlow (claim evolution across papers, arXiv:2603.16073), | SECONDHAND | watch/PURPLE_HARVEST_DIG_RHYME_20260906.md |
| arXiv 2604.19953 | Corpus / math wing / games | LatentGandr — arXiv:2604.19953, 2026. Visual analytics over generative latent sp | SECONDHAND | watch/FRONTIER_PROJECTION_FIDELITY_20260906.md |
| arXiv 2604.24833 | Corpus / math wing / games | (arXiv 2604.24833) — the pose-token/VQ internals would decide how expensive | SECONDHAND | watch/INTAKE_MOTION_BRICKS_GGML_20260904.md |
| arXiv 2605.08233 | Corpus / math wing / games | gn of Multi-Layer Sub-Pixel-Resolution RF Passives  ·  2026-05-06  ·  arxiv.org/ | SECONDHAND | watch/SHELF_ARENA_PHYSICA_20260904.md |
| arXiv 2605.09189 | Corpus / math wing / games | mpute into Performance in a Data-Constrained World  ·  2026-05-06  ·  arxiv.org/ | SECONDHAND | watch/SHELF_ARENA_PHYSICA_20260904.md |
| arXiv 2605.11496 | Corpus / math wing / games | canonical paper. Anchors: [arXiv 2605.11496 "When Frontier AI Models Recognise T | SECONDHAND | watch/inbox/INTAKE_HAUL11_20260907.md |
| arXiv 2607.05391 | Corpus / math wing / games | Ponytail: SUPPORTED. Paper pinned: arXiv 2607.05391 (Kwok, Li, Atreya, Liu, | SECONDHAND | watch/INTAKE_XBATCH2_20260905.md |
| arXiv 2607.10814 | Corpus / math wing / games | hidden-information games (arXiv:2607.10814). | SECONDHAND | watch/ASTRA_ASK_WAR_ROOM_20260909.md |
| arXiv 2607.16183 | Corpus / math wing / games | tion identity is standard)  ·  Blog math + refs [11,19,20]; vendor-authored arXi | SECONDHAND | docs/ref/EXTROPIC_Z1T_DIGEST_20260904.md |
| arXiv 2607.27191 | Corpus / math wing / games | https://www.alphaxiv.org/abs/2607.27191 | SECONDHAND | watch/HIRE_FOLLOW_ARXIV_PROBE_20260905.md |
| arXiv 2608.01612 | Corpus / math wing / games | y is standard)  ·  Blog math + refs [11,19,20]; vendor-authored arXiv 2607.16183 | SECONDHAND | docs/ref/EXTROPIC_Z1T_DIGEST_20260904.md |
| arXiv 2608.01615 | Corpus / math wing / games | d)  ·  Blog math + refs [11,19,20]; vendor-authored arXiv 2607.16183, 2608.01612 | SECONDHAND | docs/ref/EXTROPIC_Z1T_DIGEST_20260904.md |
| arXiv 2608.08910 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.08910 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.12114 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.12114 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.15930 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.15930 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.16884 | Corpus / math wing / games | Receipts : arXiv 2608.16884 "Improving the matrix multiplication exponent | SECONDHAND | watch/INTAKE_ALPHAEVOLVE_OMEGA_20260904.md |
| arXiv 2608.17390 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.17390 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.22152 | Corpus / math wing / games | arXiv:2608.23541 (Interaction Tax), arXiv:2604.02460 (matched budgets), arXiv:26 | SECONDHAND | watch/MAG_CHORD_V4_ADOPTED_20260903.md |
| arXiv 2608.24547 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.24547 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.25655 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.25655 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.26418 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.26418 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.28044 | Corpus / math wing / games | https://doi.org/10.48550/arxiv.2608.28044 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |
| arXiv 2608.28476 | Corpus / math wing / games | 3. Tencent ContextPilot, arXiv:2608.28476 (omarsar0) — context management, code  | SECONDHAND | watch/inbox/GOPHER_DIGEST_20260901_0410Z.md |
| arXiv 2609.01449 | Corpus / math wing / games | Paper: arXiv 2609.01449 — "Diffusion as a Training Curriculum for Timestep-Free  | SECONDHAND | watch/INTAKE_TIMESTEP_FREE_SOLVER_20260904.md |
| arXiv 2609.02881 | Corpus / math wing / games | 1. @vintcessun (Chinese) — Graph Machine (arXiv:2609.02881): differentiable | SECONDHAND | watch/PURPLE_HARVEST_TRIAGE_02_20260906.md |
| arXiv 2609.04159 | Corpus / math wing / games | 1. @di zhang fdu — SENTINEL-RL (arXiv:2609.04159, THIRD Di Zhang paper | SECONDHAND | watch/PURPLE_HARVEST_TRIAGE_02_20260906.md |
| arXiv 3841.71428 [DOI-ARTIFACT] | Corpus / math wing / games | https://doi.org/10.1111/1750-3841.71428 | SECONDHAND | watch/scout/MONITOR_LANE_2026-09-04.md |

| arXiv 2601.07372 | the hum / Rocinante / librarian | Engram: Conditional Memory via Scalable Lookup (DeepSeek) — https://arxiv.org/abs/2601.07372 — deterministic hash-lookup memory, 100B table to DRAM <3% penalty, NVMe tier proposed-not-measured | PRIMARY | watch/inbox/ENGRAM_OPEN_WEIGHTS_20260911.md |
| arXiv 2104.07857 | the hum / Rocinante / memory hierarchy | ZeRO-Infinity: Breaking the GPU Memory Wall (Microsoft, SC21) — https://arxiv.org/abs/2104.07857 — GPU+CPU+NVMe tiering for trillion-param TRAINING; the founding tier paper, 2021 | PRIMARY-abstract | watch/inbox/HOT_LATTICE_TO_ENGRAM_20260911.md |
| arXiv 2312.11514 | the hum / Rocinante / memory hierarchy | LLM in a flash (Apple) — https://arxiv.org/pdf/2312.11514 — weights resident on FLASH storage, windowing + row-column bundling, on-device from limited DRAM (Dec 2023) | PRIMARY-abstract | watch/inbox/HOT_LATTICE_TO_ENGRAM_20260911.md |
| arXiv 2312.17238 | the hum / Rocinante / memory hierarchy | Fast Inference of MoE LMs with Offloading (Eliseev & Mazur) — https://arxiv.org/abs/2312.17238 — expert tables to CPU RAM, LRU cache, speculative expert prefetch; Mixtral 8x7B on a laptop 3060 (Dec 2023). NOTE: 2310.16837 was a from-memory WRONG ID, caught by sweep | PRIMARY-abstract | watch/inbox/HOT_LATTICE_TO_ENGRAM_20260911.md |
| arXiv 2312.12456 | the hum / Rocinante / memory hierarchy | PowerInfer — https://arxiv.org/abs/2312.12456 — hot neurons on GPU, cold on CPU via activation locality; consumer-GPU PC serving, ~11x llama.cpp (Dec 2023, ASPLOS25) | PRIMARY-abstract | watch/inbox/HOT_LATTICE_TO_ENGRAM_20260911.md |
| arXiv 2402.07033 | the hum / Rocinante / memory hierarchy | Fiddler: CPU-GPU Orchestration for MoE (Kamahori et al.) — https://arxiv.org/abs/2402.07033 — keep experts on CPU and COMPUTE there, per-expert GPU/CPU choice (Feb 2024). NOTE: 2402.05959 was a from-memory WRONG ID, caught by sweep | PRIMARY-abstract | watch/inbox/HOT_LATTICE_TO_ENGRAM_20260911.md |
| DOI 10.1145/3731569.3764843 | the hum / Rocinante / memory hierarchy | KTransformers (Tsinghua MADSys, ACM Oct 2025) — https://github.com/kvcache-ai/ktransformers — attention/shared on GPU, expert FFN on CPU RAM; 671B DeepSeek on ONE GPU; the exact recipe of our vast box contracts (-ot .ffn_.*_exps.=CPU) | SECONDHAND (repo+venue) | watch/inbox/HOT_LATTICE_TO_ENGRAM_20260911.md |
| arXiv 2412.19437 | the hum / decode | DeepSeek-V3 Technical Report — MTP = shared embed + shared head + 1 block + d×2d proj; 85-90% acceptance, 1.8x TPS | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 1911.00172 | corpus-engram | kNN-LM: Generalization through Memorization — interpolate LM with kNN over hidden-state datastore; domain swap with zero training | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2112.04426 | corpus-engram | RETRO (DeepMind) — frozen-retrieval over 2T-token chunk DB + chunked cross-attention; knowledge updates by editing the DB | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2203.08913 | corpus-engram | Memorizing Transformers — kNN into non-differentiable memory of past KV pairs; gains to 262K | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 1612.04426 | corpus-engram | Neural cache (Grave et al. 2016) — continuous cache of past activations, dot-product access (ID near-collision with RETRO noted) | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2310.08560 | corpus-engram | MemGPT — OS-style virtual context paging between in-context memory and storage; on-demand not predictive | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2210.08803 | corpus-engram | Merlin HugeCTR — GPU embedding cache + GPU→DRAM→SSD tiering with hot-embedding prefetch (the only corpus-adjacent prefetch prior) | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2411.01142 | KV offload | NEO (MLSys25) — CPU-offloaded attention+KV beats GPU-only up to 6.6x. NOTE: 2409.15534 was a wrong ID, caught | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2406.19707 | KV offload | InfiniGen (OSDI24) — prefetch only attention-essential KV via next-layer weight prediction, 3x over naive offload | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2306.14048 | KV offload | H2O (NeurIPS23) — heavy-hitter KV eviction | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2409.19798 | attribution armor | Membership Inference Cannot Prove Training On Your Data (Tramèr et al.) — canary-MIA + extraction are the ONLY sound proofs | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2202.07646 | attribution armor | Quantifying Memorization (Carlini et al.) — memorization log-linear in scale and DUPLICATION; canary GUID methodology | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2012.07805 | attribution armor | Extracting Training Data from LLMs (Carlini et al., USENIX Sec 21) — founding extraction attack | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2311.17035 | attribution armor | Scalable Extraction from Production LMs — divergence attack; RLHF does not erase memorization | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2301.10226 | attribution armor | A Watermark for LLMs (Kirchenbauer et al., ICML23) — green/red lists, z-score detection; the FP-math template | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2502.10673 | attribution armor | Dataset Protection via Watermarked Canaries in RAG LLMs — nearest working canary design, statistical response scoring | PRIMARY-abstract | watch/inbox/OFFLOAD_WAVE_FOLD_20260911.md |
| arXiv 2609.119xx (TRUNCATED-verify) | the eye / vessels | SenseNova-U1.5 (SenseTime): 8B-MoT native unified multimodal, no visual encoder/VAE, native 4K — HF sensenova/SenseNova-U1.5-8B-MoT | SECONDHAND (HuggingPapers) | watch/inbox/INTAKE_XBATCH_20260912.md |
| alphaXiv 2609.deepseek-v4-1-flash (TRUNCATED-verify) | the hum / KV | DeepSeek-V4.1-Flash KV compression: Causal Encoder-Decoder O(NL)->O(NL/2) prefill, CSA2 layer-KV sharing, FP4 KV + SWA Bounded Replay -> 890 bytes/token global KV, 1M ctx | SECONDHAND (alphaXiv post) | watch/inbox/INTAKE_XBATCH_20260912.md |
| NON-ARXIV realswe | eval wing | Real-SWE (Specific Labs/YC): coding agents on real tasks from PRIVATE company codebases; community: Fable leads, GLM 5.3 surprisingly high — realswe.withspecific.com | SECONDHAND | watch/inbox/INTAKE_XBATCH_20260912.md |
| NON-ARXIV agent-me | corpus-engram / receipts | Agent-Me (DanKornas, MIT): markdown knowledge base + deterministic bounded retrieval + typed role handoffs + evidence checks blocking unsupported synthesis — the fleet shape published small | SECONDHAND | watch/inbox/INTAKE_XBATCH_20260912.md |
| NON-ARXIV zsec | mimosa / harness | ZephrFish AI-VR pipeline (blog.zsec.uk/bullyingllms + /harnessing-harnesses): 8 MCP servers, 300+ tools, validation gates > model choice, bounty-funded | SECONDHAND | watch/inbox/INTAKE_XBATCH_20260912.md |
| arXiv 2601.07372 cross-ref | the hum / KV | NOTE: the V4.1-Flash KV paper is the CED/CSA2 companion to the Engram paper — same model, second mechanism axis | CROSSREF | watch/inbox/INTAKE_XBATCH_20260912.md |
| SSRN 5877662 (TITLE UNFETCHED) | the hum / macro | Sara Hooker, "On the slow death of scaling" — post-training returns concentrate in data/environment pipeline engineering | SECONDHAND (title+abstract unfetched) | watch/inbox/INTAKE_XBATCH_20260912.md |
| arXiv 2604.08407 (TITLE UNFETCHED) | mimosa / security | LLM-router supply chain: routers harvest credentials from traffic, inject malicious tool calls, forward traffic (shoucccc disclosure, 1.9M views) | SECONDHAND (verify before citing) | watch/inbox/INTAKE_XBATCH_20260912.md |


---

## MAP MERGE — 22 ROWS PULLED + HASHED + RECEIPTED (2026-09-29)

**Executed against the map's own promotion rule**: fetch the PDF, sha256 it, drop a per-id
receipt, and only then does a row move from RETRIEVAL-PLAN to PULLED+HASHED. All three legs
verified against the filesystem, not against a ledger: **22/22 real PDFs (`%PDF-` magic),
22/22 sha256 re-hashed from disk with 0 mismatches, 22/22 per-id receipts carrying a verbatim
abstract excerpt.** 21,342,104 bytes.

**Rights tier, stated because it was nearly got wrong.** arXiv's API returns **no
`<arxiv:license>` tag at all** for these entries — verified directly: a 1,861-byte response for
0706.1347 containing no "licen" substring anywhere. So the per-article licence is *unstated*,
not *withheld* and not *CC*. The earlier run recorded all 22 as `redistributable: false` and
**discarded the bytes** (`landed: null` on every row, 0/22 hashes matching any file under
`corpus/`). That made the whole promotion theatre: **a sha256 of bytes that no longer exist is
a claim, not evidence** — nothing on disk to re-check, and the module had no receipt writer at
all, so it could never satisfy the rule it was invoking. Unstated is the house convention's
**middle tier** (RAG/reference), not a refusal; only an affirmative all-rights-reserved
statement is refused. These are landed in `corpus/papers_reference_nonredistributable/` —
the path states the tier so no file can be misread as redistributable or public domain.

**What did NOT merge, and why that is the point.** The backfill staged **901 fresh rows** as
RETRIEVAL-PLAN. They are still RETRIEVAL-PLAN. A title confirmed by the arXiv API is not the
document; a row never pulled must never read as though it had. 26 of the 933 unregistered
citations stayed *unresolved and unclaimed* because their titles could not be confirmed at all.
**A wrong citation is worse than an honest gap** — that is the law this map runs on, and the
merge is smaller than the staging table for exactly that reason.

| ref | category | evidence | status | where it's used |
|---|---|---|---|---|
| arXiv 0706.1347 — The Two-State Vector Formalism | quant-ph | sha256 008f007f7776db43; 72,615 B; receipt `docs/report_v1/sources/receipts/0706.1347.md`; bytes in `corpus/papers_reference_nonredistributable/0706.1347.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 0808.2669 — Closed Timelike Curves Make Quantum and Classical Computing Equivalent | quant-ph | sha256 eb7674b2b1ff0515; 215,117 B; receipt `docs/report_v1/sources/receipts/0808.2669.md`; bytes in `corpus/papers_reference_nonredistributable/0808.2669.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 0810.4179 — Memristive model of amoeba's learning | q-bio.CB | sha256 62de9e385fbb776e; 383,321 B; receipt `docs/report_v1/sources/receipts/0810.4179.md`; bytes in `corpus/papers_reference_nonredistributable/0810.4179.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 0812.4360 — Driven by Compression Progress: A Simple Principle Explains Essential Aspects of Subjective Beauty, Novelty, Surprise, Interestingness, Attention, Curiosity, Creativity, Art, Science, Music, Jokes | cs.AI | sha256 e971d466392c52f0; 537,077 B; receipt `docs/report_v1/sources/receipts/0812.4360.md`; bytes in `corpus/papers_reference_nonredistributable/0812.4360.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 0912.3995 — Gaussian Process Optimization in the Bandit Setting: No Regret and Experimental Design | cs.LG | sha256 981a17a4d356ac79; 735,139 B; receipt `docs/report_v1/sources/receipts/0912.3995.md`; bytes in `corpus/papers_reference_nonredistributable/0912.3995.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1001.1778 — Understanding Quaternions and the Dirac Belt Trick | physics.pop-ph | sha256 e78cb6a91fc01002; 764,608 B; receipt `docs/report_v1/sources/receipts/1001.1778.md`; bytes in `corpus/papers_reference_nonredistributable/1001.1778.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1003.4273 — Time-symmetric boundary conditions and quantum foundations | quant-ph | sha256 87e42841e11ee1ab; 164,437 B; receipt `docs/report_v1/sources/receipts/1003.4273.md`; bytes in `corpus/papers_reference_nonredistributable/1003.4273.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1005.2213 — Herschel PACS Spectroscopic Diagnostics of Local ULIRGs: Conditions and Kinematics in Mrk 231 | astro-ph.CO | sha256 c320a9d423fa9d3f; 269,694 B; receipt `docs/report_v1/sources/receipts/1005.2213.md`; bytes in `corpus/papers_reference_nonredistributable/1005.2213.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1005.2219 — Closed timelike curves via post-selection: theory and experimental demonstration | quant-ph | sha256 f8e881534aa540b1; 204,593 B; receipt `docs/report_v1/sources/receipts/1005.2219.md`; bytes in `corpus/papers_reference_nonredistributable/1005.2219.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1012.2599 — A Tutorial on Bayesian Optimization of Expensive Cost Functions, with Application to Active User Modeling and Hierarchical Reinforcement Learning | cs.LG | sha256 cced13a396275b30; 5,799,414 B; receipt `docs/report_v1/sources/receipts/1012.2599.md`; bytes in `corpus/papers_reference_nonredistributable/1012.2599.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1101.3501 — Convergence rates of efficient global optimization algorithms | stat.ML | sha256 de3c80c096388b96; 311,811 B; receipt `docs/report_v1/sources/receipts/1101.3501.md`; bytes in `corpus/papers_reference_nonredistributable/1101.3501.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1106.1819 — A Knowledge Compilation Map | cs.AI | sha256 e521e1d0bd3e670b; 426,218 B; receipt `docs/report_v1/sources/receipts/1106.1819.md`; bytes in `corpus/papers_reference_nonredistributable/1106.1819.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1108.0153 — A reply to "Problems with modelling closed timelike curves as post-selected teleportation" | quant-ph | sha256 48e7aab7284c452f; 77,622 B; receipt `docs/report_v1/sources/receipts/1108.0153.md`; bytes in `corpus/papers_reference_nonredistributable/1108.0153.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1108.1542 — Colour field flux tubes and Casimir scaling for various SU(3) representations | hep-lat | sha256 2b68d96f161b5d42; 2,368,318 B; receipt `docs/report_v1/sources/receipts/1108.1542.md`; bytes in `corpus/papers_reference_nonredistributable/1108.1542.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1203.4834 — Experimental delayed-choice entanglement swapping | quant-ph | sha256 82d39acf6171dd56; 1,047,973 B; receipt `docs/report_v1/sources/receipts/1203.4834.md`; bytes in `corpus/papers_reference_nonredistributable/1203.4834.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1204.5227 — The Possibilist Transactional Interpretation and Relativity | quant-ph | sha256 b6bb5289b464bd4a; 305,751 B; receipt `docs/report_v1/sources/receipts/1204.5227.md`; bytes in `corpus/papers_reference_nonredistributable/1204.5227.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1209.2020 — Differentiating the entropy of random walks on hyperbolic groups | math.PR | sha256 9add256eb3e5c1fb; 271,382 B; receipt `docs/report_v1/sources/receipts/1209.2020.md`; bytes in `corpus/papers_reference_nonredistributable/1209.2020.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1209.4191 — Entanglement Between Photons that have Never Coexisted | quant-ph | sha256 7078f1c1f7427b0f; 391,975 B; receipt `docs/report_v1/sources/receipts/1209.4191.md`; bytes in `corpus/papers_reference_nonredistributable/1209.4191.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1212.0501 — Effective results for complex hyperbolic manifolds | math.DG | sha256 b72f81dc1b460acf; 412,798 B; receipt `docs/report_v1/sources/receipts/1212.0501.md`; bytes in `corpus/papers_reference_nonredistributable/1212.0501.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1303.4969 — Computation of the Travelling Salesman Problem by a Shrinking Blob | cs.ET | sha256 a17e28d2e86a5ba1; 2,966,464 B; receipt `docs/report_v1/sources/receipts/1303.4969.md`; bytes in `corpus/papers_reference_nonredistributable/1303.4969.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1304.7469 — Asking photons where have they been | quant-ph | sha256 d56ac4e3c08e54c5; 2,554,920 B; receipt `docs/report_v1/sources/receipts/1304.7469.md`; bytes in `corpus/papers_reference_nonredistributable/1304.7469.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
| arXiv 1304.7474 — The past of a quantum particle | quant-ph | sha256 d2d5603c3c8ea954; 1,060,857 B; receipt `docs/report_v1/sources/receipts/1304.7474.md`; bytes in `corpus/papers_reference_nonredistributable/1304.7474.pdf` | PULLED+HASHED (reference tier, not redistribution-eligible) | bibliography; citation graph; RAG |
