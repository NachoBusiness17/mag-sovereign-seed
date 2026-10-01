# Vast.ai — high-throughput self-hosted LLM inference (one 24GB box)

**Commitment:** `vast-deep-grok-throughput-001`  
**As-of:** 2026-08-27  
**Status:** Research brief from public benches + official docs (fetched 2026-08-27). **Not a live probe on this house's Vast instance.** Absolute tok/s drift by driver/CUDA/engine version; **relative rankings** are the durable claim.  
**Job:** How to run a **100-way queen fan-out** on **one rented 3090/4090-class GPU + 128GB+ RAM**, where **aggregate throughput** beats single-call latency. Cover: engines, prefix cache, speculative decode, MoE offload, OpenAI-compat servers, hosted vs self-host $/M.  
**Companions (do not duplicate):**  
- Market economics / $/hr: `docs/ref/VAST_DEEP_GROK_ECONOMICS.md`  
- Serverless / volumes / reserved: `docs/ref/VAST_DEEP_GROK_SERVERLESS.md`  
- Instance REST/CLI: `docs/ref/VAST_API_EXPERT_REFERENCE.md`  
- Train pipe (v5): `docs/ref/MAG_v5_VAST_TRAINING.md`  
- Local prefix-cache design: `memory/design/compact-anchor-context-mechanism.md`

**Honesty rule:** Official docs and named benches first. Blog roundups dated. Conflicts marked. Numbers below are **cited measurements**, not this box's `nvidia-smi`. Before claiming a tok/s on a rented instance, run the engine's own `bench_serving` against that instance.

---

## 0. Swarm-shaped one-liner

On one 24GB card, **100 parallel queen HTTP clients is easy; 100 in-flight unique KV sessions is not.** Throughput saturates when the **KV-cache pool** fills, not when the TCP backlog fills. Shared Mag pack + tools = prefix-cache gold (2–10× prefill, 20–60% aggregate tok/s). Unique long contexts per queen = you queue at 8–32 concurrent and the extra 70 clients wait. Engine pick: **SGLang if prefixes share; vLLM if they don't; llama.cpp/`--n-cpu-moe` only for 100B+ that cannot fit; Ollama is the wrong server for this job.**

A $0.10/hr 3090 at saturated 7B-class decode (~900 tok/s) prints **~$0.03/M tokens**. The same hour at 25% util is **~$0.12/M**. Hosted open-weight APIs sit **$0.02–$0.60/M**. Self-host wins on 7B–30B-A3B **only near saturation**; it loses to DeepSeek Flash on quality-per-dollar for frontier MoE you cannot fit.

---

## 1. Engines: vLLM vs SGLang vs llama.cpp vs TabbyAPI

### 1.1 What each actually is

| Engine | Core trick | Concurrent batching | OpenAI API | 24GB role |
|---|---|---|---|---|
| **vLLM** | PagedAttention + continuous batching | True iteration-level | `vllm serve` `/v1` | Default **unique-prompt** swarm |
| **SGLang** | RadixAttention (radix-tree KV reuse) | True + automatic prefix share | `sglang.launch_server` / `sglang serve` `/v1` | Default **shared-prefix** swarm (queens) |
| **llama.cpp** `llama-server` | GGUF, `--parallel` slots, `--n-cpu-moe` | Slot pool, not PagedAttention | `/v1` | 100B+ hybrid CPU/GPU; **not** 100-way dense 7B |
| **Ollama** | llama.cpp wrapper | `OLLAMA_NUM_PARALLEL` slots (often 1–8) | `/v1` | Dev laptop. Collapses under fan-out. |
| **TabbyAPI** | ExLlama (EXL2/EXL3) + paged attn | Continuous batching (dynamic generator) | `/v1` | Best **single-user** INT4 on Ampere+; weaker at c=50+ vs vLLM |

Official:  
- vLLM: https://docs.vllm.ai · `vllm serve`  
- SGLang: https://docs.sglang.io/docs/get-started/quickstart.md · https://docs.sglang.io/docs/basic_usage/openai_api_completions  
- llama.cpp: https://github.com/ggml-org/llama.cpp  
- TabbyAPI: https://github.com/theroyallab/tabbyAPI (main now **Exl3**; EXL2 on `exl2-checkpoint`)  
- ExLlamaV2 dynamic/continuous batching: https://github.com/turboderp-org/exllamav2/blob/master/doc/dynamic.md  

### 1.2 Same-GPU concurrent throughput (the number that matters)

**Reproducible head-to-head, NVIDIA L4 24GB, Qwen2.5-7B, short chat, concurrency 64** — https://github.com/ree2raz/inference-bench  

| Engine | Aggregate tok/s @ c=64 | TTFT p50 | Note |
|---|---|---|---|
| vLLM AWQ | **976** | 651 ms | Best quantized throughput |
| SGLang FP16 | **914** | 314 ms | +10% vs vLLM FP16 |
| vLLM FP16 | 831 | 582 ms | |
| SGLang AWQ | 506 | 516 ms | *Their* AWQ path was broken (torch/flashinfer); do not treat as SGLang-AWQ truth |
| llama.cpp Q4_K_M (`-np 4`) | 189 | — | Caps at slot count; p95 73 s |

Same suite, **A100 40GB, May 2026 v2** (vLLM 0.20.1):

| Config | Engine | c=1 | c=16 | c=64 |
|---|---|---|---|---|
| FP16 | vLLM | 80 | 1,094 | **3,102** |
| FP16 | SGLang | 61 | 829 | 2,141 |
| AWQ Marlin | vLLM | 177 | 2,248 | **4,762** |
| AWQ Marlin | SGLang | 195 | 2,325 | 2,231 (collapses) |

**Consumer 4090-class concurrent (compiled community, Llama-3.1-8B-class):** https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/

| Concurrent | Ollama aggregate tok/s | vLLM aggregate tok/s | Ratio |
|---|---|---|---|
| 1 | ~62 | ~71 | 1.1× |
| 8 | ~82 | ~187 | 2.3× |
| 50 | ~155 | **~920** | 5.9× |
| 100+ | plateaus / serializes | still scales with batch | **~15–20×** |

Shape is consistent across Markaicode / SitePoint / SesameDisk / TowardsAI (Red Hat 2026 serving bench cited as **793 tok/s vLLM vs 41 tok/s Ollama** under load): https://sesamedisk.com/local-ai-inference-engines-2026-comparison/ · https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/

**CraftRigs, RTX 4090, batch=8 vs Ollama batch=1:** vLLM 528 tok/s aggregate vs Ollama 98 — 4.2×. https://craftrigs.com/benchmarks/ollama-vs-llama-cpp-vs-vllm-throughput-benchmark/

**GigaGPU, dedicated UK 4090, vLLM 0.6.4, chat SLA** (active in-flight, not queued clients): https://gigagpu.com/rtx-4090-24gb-concurrent-users/

| Model | Quant | Active users (SLA) | Median t/s/user | Aggregate (implied) |
|---|---|---|---|---|
| Phi-3 mini | FP8 | 80 | 32 | ~1,800 tok/s claimed at batch 80 |
| Llama 3.1 8B | FP8 | **30** | 34 | ~1,000 |
| Mistral 7B | FP8 | 32 | 34 | ~1,090 |
| Qwen 2.5 14B | AWQ | 16 | 30 | ~480 |
| Qwen 2.5 32B | AWQ | 8 | 22 | ~176 |
| Mixtral 8x7B | AWQ | 10 | 23 | ~230 |
| Llama 3.1 70B | AWQ INT4 | 3–4 | 20 | ~70 |

That table is **SLA-capped concurrency**, not peak tok/s. Peak is higher; p95 TTFT is the limiter they chose.

### 1.3 7B–30B MoE on one 24GB GPU

MoE decode scales with **active params**, VRAM with **total params**. Qwen3-30B-A3B = 30.5B total / **3.3B active**.

**inference-bench, vLLM 0.20.1, Qwen3-30B-A3B:**

| Config | GPU | c=1 | c=4 | c=16 |
|---|---|---|---|---|
| BF16 | A100 80GB | 134 | 301 | OOM (weights ~61 GB) |
| AWQ Marlin | A100 40GB | 165 | 520 | **1,476** |
| AWQ Marlin 16K ctx | A100 40GB | 161 | 508 | 1,485 |

Vs dense 7B on same A100: MoE AWQ c=16 is **1.8×** dense AWQ. Efficiency vs theoretical bandwidth is worse (MoE BF16 ~46% vs dense FP16 ~63%) because expert routing is irregular.

**On 24GB consumer (fits AWQ/Q4, not BF16):**

| Source | Hardware | Model | Number |
|---|---|---|---|
| llmconfigurator calibration | RTX 4090 | Qwen3-30B-A3B Q4_K_XL @ 4K | **195.8 tok/s** single-stream |
| same | RTX 4090 | same @ 57K ctx | 74.6 tok/s |
| CraftRigs hybrid | RTX 3090 | Qwen3-30B-A3B, no offload | **~87 tok/s** |
| Reddit 2×4090 | 2×4090 SGLang FP8 | Qwen3-MoE (30B-class) | **~116 tok/s** TG; vLLM ~95–97; llama.cpp ~99–101 |
| Reddit 1×3090 | llama.cpp | same | ~83–84 tok/s TG |
| HF discussion | RTX 4090D **48GB** | Qwen3-VL-30B-A3B FP8 vLLM | 90 / 60 / 35 tok/s at short / 40k / 128k — **not 24GB** |
| YouTube / SGLang local | 3090 | Qwen3 Coder 30B | ~130 tok/s claimed |

https://llmconfigurator.com/en/benchmarks · https://craftrigs.com/articles/hybrid-llm-architecture-cpu-gpu-inference/ · https://www.reddit.com/r/LocalLLaMA/comments/1ke26sl

**24GB implication:** Qwen3-30B-A3B **AWQ/Q4 is the swarm workhorse**, not Mixtral-8x7B Q4 (weights often overflow 24GB without CPU expert offload). Dense Qwen3-32B Q4 also fits (~16–20 GB) but decode is slower than 30B-A3B because all 32B fire.

Plugsky (July 2026, mixed HW, **single-stream**): Mixtral-8x7B on 4090 — Ollama 22.4 tok/s, vLLM 38.6 tok/s. https://plugsky.com/local-inference-benchmark

### 1.4 TabbyAPI / ExLlama — do not pick it for 100 queens

ExLlamaV2/V3 + TabbyAPI wins **single-user decode** on Ampere:

| Source | Model / GPU | Tabby/ExLlama | vLLM | llama.cpp |
|---|---|---|---|---|
| LocalAIMaster | Llama 3.1 8B Q4, 4090, batch=1 | **165 tok/s** | 155 AWQ | 130 |
| CraftRigs | Llama-3 8B, 4090, batch=1 | **187 tok/s** | 129 | 142 |
| CraftRigs | **batch=8 aggregate** | 156 tok/s | **312 tok/s** | 199 (`-np 8`) |
| ExLlama README | Llama GPTQ 7B, 4090 | **205 tok/s** | — | — |
| TabbyAPI marketing | 7B / 70B on 4090 | 120+ / 40+ (single) | — | — |

https://github.com/turboderp-org/exllamav2 · https://craftrigs.com/comparisons/exllamav2-vs-llama-cpp-vs-vllm-comparison/ · https://localaimaster.com/blog/exllamav2-tabbyapi-guide · https://tabbyapi.com/

Paged attention exists (FlashAttn ≥2.5.7, page size 256). Continuous batching is real. It still **loses to vLLM at batch=8+** in the CraftRigs head-to-head because vLLM's scheduler + PagedAttention block table is built for many concurrent sequences. TabbyAPI is the right pick for **one operator, one 70B EXL2 squeezed into 24GB** (LocalAIMaster: Llama 3.1 70B EXL2 4.0bpw + Q4 cache ≈ **22 tok/s**, vLLM AWQ **OOM**). Wrong pick for 100 queens.

### 1.5 Ollama under fan-out — do not

`OLLAMA_NUM_PARALLEL` is a **slot count**, not continuous batching. Defaults 1 or auto 1/4. Each slot multiplies KV (`NumCtx × NumParallel`). Safe on 24GB 7B Q4: **6–8** (Markaicode); 13B: 3–4. https://markaicode.com/ollama-concurrent-requests-parallel-inference/

Qiita 2026 (8 parallel, 2k-token inputs; Qwen3.5 MoE **forced Parallel:1** by Ollama):

| | Ollama | vLLM FP8 | SGLang FP8 |
|---|---|---|---|
| Aggregate tok/s | 66 | 278 (4.2×) | **468 (7.1×)** |
| p95 TTFT | 27.6 s | 2.3 s | **0.28 s** |

https://qiita.com/Marron-chan/items/ede825e91c740894c197

Ollama 0.24+ also **refuses parallel** on some MoE arches. For Mag queens: Ollama is the home janitor, not the Vast swarm server.

### 1.6 Single-stream vanity numbers (do not optimize these)

4090 Llama-3.1-8B class, one request: Ollama ~62–128, llama.cpp ~65–162, vLLM ~71–185, SGLang ~173, ExLlama ~165–205 depending on quant and who measured. Gap is **quant + kernels**, not architecture. Architecture shows up at **c≥8**.

---

## 2. Prefix caching — still matters on self-hosted (throughput, not $)

**Yes.** On a rented box you already paid the hour. Cache does not save a billable token; it **frees prefill SM-time so more decode tokens fit in the same second.** That is exactly the swarm metric.

### 2.1 Mechanisms

| Stack | Structure | Default | Cross-request share |
|---|---|---|---|
| **SGLang RadixAttention** | Radix tree over token sequences | On | Automatic, including partial overlap / tree branch |
| **vLLM prefix caching** | Content-addressed KV **blocks** (hash of tokens + parent block) | On in recent versions (`--enable-prefix-caching`; was off in older) | Longest matching **block-aligned** prefix |
| TGI / TRT-LLM | Optional / static | Off unless set | Weaker automatic |

vLLM block hashing: https://www.generalcompute.com/blog/prefix-caching-why-repeated-prompts-shouldnt-cost-you-twice  
SGLang original paper (up to **6.4×** throughput, **3.1×** on DeepSeek V3+MTP vs contemporaneous systems): https://arxiv.org/abs/2312.07104 · LMSYS writeup lineage via https://github.com/sgl-project/sglang

### 2.2 Quantified speedup (when prefixes actually share)

**SGLang paper / LMSYS-family benches (Llama-3-8B, A100, cited in secondary roundups):**

| Workload | Prefix | vLLM | SGLang | Speedup |
|---|---|---|---|---|
| Simple generation | 0 | 2500 tok/s | 2800 | 1.12× |
| Few-shot 5 ex | 1000 | 800 | 3200 | **4×** |
| Few-shot 10 ex | 2000 | 500 | 5000 | **10×** |
| Agent + tools | 1500 | 800 | 4000 | **5×** |
| Chat history | 500–2000 | 1200 | 3600 | **3×** |

Treat the 10× cell as **prefill-dominated few-shot**, not a 4090 guarantee. Direction is what to trust.

**H100 Llama 3.1 8B prefix-heavy (RunPod / Spheron / PremAI roundups, cited widely):** SGLang **~16,200 tok/s** vs vLLM **~12,500** = **+29%**. Unique prompts: **parity** (YouTube SGLang+Qwen: unique prompts, one GPU, c=32 — vLLM **1,743** vs SGLang **1,661**).  
https://www.spheron.network/blog/llm-inference-optimization-2026/  
https://awesomeagents.ai/tools/best-open-source-llm-inference-servers-2026/

**Spheron prefix-heavy, 50 concurrent:** SGLang **37% lower TTFT p50**, **41% lower p95** vs vLLM.

**vLLM CPU KV offload (even without shared prefix):** up to **9×** concurrent-request throughput when GPU HBM cannot hold the working set — the gain is **not recomputing** evicted prefixes. https://vllm.ai/blog/2026-01-08-kv-offloading-connector

**vLLM `--enable-prefix-caching` operator rule of thumb:** 20–50% throughput on shared system prompts; 30–60% in Swfte's production note. Zero downside on unique prompts (tiny hash overhead). https://www.swfte.com/blog/vllm-continuous-batching-deep-dive · https://yobitel.com/knowledge-base/paged-attention

**RunPod 2×H100, DeepSeek-R1-Distill-Llama-70B, 7k ctx (alesha.pro citing RunPod):**

| | SGLang | vLLM |
|---|---|---|
| Warm cache | 35.0 tok/s | 32.8 |
| Cold | 29.5 | 28.6 |
| Cache gain | **~20%** | **~10%** |

https://alesha.pro/articles/vllm-vs-sglang-radix-tree-protiv-block-level-prefix-caching

### 2.3 Prefill math (why 100 queens care)

If each queen prompt is `k` shared prefix tokens + `n−k` unique:

- Without cache, batch `B` computes `B · n` prefill tokens.  
- With cache: `k + B · (n−k)`.  
- Speedup on prefill → `n / (n−k)` as `B` grows.

Mag-shaped: pack + tools + system ≈ **2k–8k tokens**, user/goal ≈ **50–300**. `k/n ≈ 0.85–0.95` → **5–20× less prefill arithmetic**. Decode still costs full per-token; the win is **TTFT collapse + more decode slots per second** because prefill no longer monopolizes the batch.

**Self-hosted $ is already sunk.** Cache hit rate is a **tok/s multiplier**, not a line item. Hosted APIs (DeepSeek cache-hit **$0.007/M** vs miss **$0.22/M** Flash off-peak) convert the same mechanism into money. You convert it into **queens finished per hour**.

### 2.4 When cache does nothing

- Unique long contexts per queen (each session salts the prefix).  
- Prefixes that differ in the **first block** (vLLM block size 16; a one-token divergence at token 0 kills the rest).  
- Context so long that unique suffixes fill the KV pool anyway.  
- Speculative decode + prefix cache **compose**; they do not replace each other.

**Swarm law:** byte-stable shared prefix (Mag pack, tool schemas, RIB). Do not prepend timestamps, request-ids, or per-queen JSON before the shared block. That is already Mag design (`compact-anchor-context-mechanism.md`).

---

## 3. Speculative decoding — Medusa / EAGLE / MTP, including MoE

### 3.1 What it is

Draft proposes K tokens; target verifies in one forward. Lossless (rejection sampling). Helps because decode is **memory-bandwidth bound**; extra FLOPs in the same weight load are nearly free **until the GPU is already saturated**.

| Method | Extra weights | Reported speedup (papers / guides) | Best at |
|---|---|---|---|
| Independent draft (1B vs 70B) | Full small model | 1.5–2.8× (vLLM 2024 blog, QPS=1) | Low QPS, same tokenizer |
| n-gram / prompt lookup | None | up to 2.8× on summarization | Output echoes input |
| Medusa-1 / Medusa-2 | Extra heads | 2.2× / 2.3–3.6×; accept length 3.0–3.5 | Need trained heads |
| EAGLE / EAGLE-2 / EAGLE-3 | Lightweight feature head | 2.5–3.5× / 3–3.5× / **3.5–6.5×** paper | Best general; head is **per target** |
| P-EAGLE | Parallel draft head | **1.05–1.69× over EAGLE-3** (B200, GPT-OSS-20B) | High-end; still helps at c=64 (~5–25%) |
| DeepSeek MTP | Built-in | 1.6× (K=1), 2.0× with n-gram | Use if the model ships it |

https://vllm.ai/blog/2024-10-17-spec-decode (up to **2.8×** n-gram, **1.5×** draft on Llama3-70B 4×H100 at QPS=1)  
https://vllm.ai/blog/2026-03-13-p-eagle  
https://leoniemonigatti.com/blog/speculative-decoding.html  
https://localaimaster.com/blog/speculative-decoding-guide — H100 70B AWQ batch=1: baseline 28 → EAGLE-3 **102 tok/s (3.6×)**; DeepSeek V3 8×H100: baseline 65 → MTP 105 (1.6×) → MTP+n-gram 130 (2.0×)

### 3.2 High concurrency — the myth that it only helps QPS=1

**Dense, high batch:** speculation **hurts or ties** once the GPU is compute-saturated (verification of rejected drafts wastes the batch). Conventional advice: disable above ~c=32.

**MoE is different.** Red Hat, gpt-oss-120B MXFP4, Eagle3, **H200**, vLLM 0.13, prefix cache ON, up to **c=200**: https://developers.redhat.com/articles/2026/04/16/performance-improvements-speculative-decoding-vllm-gpt-oss

| Dataset | Output tok/s geo-mean | Peak @ c=100 | vs baseline |
|---|---|---|---|
| ShareGPT (decode-heavy) | 1172 vs 971 | 2574 vs 2024 | **+21% / +27% peak** |
| MLPerf (long prefill) | +9.5% (TP=1), +16% (TP=2) | — | Prefill dilutes the win |
| SWE-bench (code) | +20.5% | **3250 vs 2621** | Gains persist @ c=200 |

Draft-token sweep: **3 drafts** best at high c (accept rate 35.6%, mean accept length 2.07). 4 drafts: −8% throughput. Cost: **−19.4% $/M output** at their AWS H200 list ($41.62/hr) — that dollar figure is *their* cloud, not Vast.

vLLM AMD blog (Kimi-K2.5 / MiniMax-M2.5 EAGLE3, MI355X): **1.38–2.00×**, largest at low concurrency, still positive at higher. https://vllm.ai/blog/2026-07-13-eagle-3-amd-instinct

P-EAGLE vs EAGLE-3 on GPT-OSS-20B B200: **+55% at c=1, +5% at c=64**.

### 3.3 24GB swarm takeaway

| Situation | Speculate? |
|---|---|
| 7B dense, c=32–64, GPU already ~100% util | **Measure.** Often ≤10% or negative. n-gram is free to try. |
| Qwen3-30B-A3B / gpt-oss-20B/120B MoE | **Yes if a matching EAGLE3 head exists.** +10–25% at high c is documented on MoE. |
| 100 unique long prefills | Speculation does not help prefill. Prefix cache does. |
| No trained head for your quant | n-gram / MTP only. Do not burn VRAM on a 1B draft unless c is low. |

Flags:

```bash
# vLLM
vllm serve <target> --speculative-config '{"method":"eagle3","model":"<eagle-head>","num_speculative_tokens":3}'

# SGLang
python3 -m sglang.launch_server --model-path <target> \
  --speculative-algorithm EAGLE3 \
  --speculative-draft-model-path <eagle-head> \
  --speculative-num-steps 5 --speculative-eagle-topk 8 --speculative-num-draft-tokens 64
```

https://consciousengines.com/blog/putting-it-to-work-serving-speculative-decoding-with-vllm-and-sglang

VRAM: draft head is small; a full 1B draft is **~0.5–2 GB** — on 24GB that is KV slots you do not get.

---

## 4. MoE offload: 100B+ on 24GB VRAM + 128GB RAM

### 4.1 The rule that replaced "VRAM = total params"

**VRAM for speed ≈ attention + shared + KV + the experts that actually sit on GPU.**  
**RAM holds cold experts.** Per token, 2–8 experts stream across PCIe. llama.cpp flag: `--n-cpu-moe N` (`-ncmoe` in llama-bench) — first N MoE layers' **expert weights** on CPU; attention stays on GPU. `--cpu-moe` = all experts on CPU.

https://insiderllm.com/guides/mixtral-8x7b-8x22b-vram-requirements/  
https://insiderllm.com/guides/moe-models-explained/

Naive layer split (`-ngl`) on MoE is the slow path (GPT-OSS 120B on 3090: **~0.9 tok/s**). Expert-only offload: **~1.6 tok/s** on a 3090 + EPYC + 64 GB DDR4. Same flag on 5090-class: **~3.4 → ~8+ tok/s**. https://www.hardware-corner.net/gpt-oss-offloading-moe-layers/

Qwen3.6-35B-A3B on **6GB**: naive ~3 tok/s → `--n-cpu-moe` **~10–17 tok/s**; 128k ctx at 5.3 GB VRAM. https://www.youtube.com/watch?v=8F_5pdcD3HY

Theoretical 4090 split for Qwen3.5-35B-A3B (huggingface-estimate): default hybrid ~44 tok/s; `--cpu-moe` ~34; full-GPU theoretical ~144 (does not fit — 64 GiB). https://github.com/gdevenyi/huggingface-estimate

### 4.2 ktransformers (CPU/GPU heterogeneous MoE)

https://github.com/kvcache-ai/ktransformers  
SOSP 2025 paper: *KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models.*

Design: hot / high-arithmetic-intensity params on GPU (attention, shared), MoE GEMV on CPU (batch=1 arithmetic intensity ~0.075). AMX Int8 on Xeon is the real multiplier.

**Official-ish / docs numbers (DeepSeek-V3 Q4_K_M, 671B):**

| Config | Prefill tok/s | Decode tok/s | VRAM | RAM |
|---|---|---|---|---|
| llama.cpp, 2×32 cores | 10.3 | 4.51 | — | 382 GB |
| KT v0.2 single 32-core | 54.2 | 8.73 | 14 GB | 382 GB |
| KT v0.3 AMX Int8 + 6 experts | **286.6** | **13.7** | 14 GB | 644 GB |

https://deepwiki.com/yedemon/ktransformers/5-hardware-optimization  

KT claim: DeepSeek-R1/V3 on **single 24GB + 382 GB DRAM**, **3–28×** vs naive. https://github.com/kvcache-ai/ktransformers (Feb 10, 2025 update)

**128GB RAM box (this envelope):** 382–644 GB recipes **do not fit**. Practical on 128GB:

| Model (Q4-class) | RAM floor | 24GB VRAM? | Expected decode (order of mag) |
|---|---|---|---|
| Mixtral 8x7B | ~64 GB | Tight; `--n-cpu-moe` | tens of tok/s if mostly GPU |
| Mixtral 8x22B / 141B | ~96 GB | Yes with CPU experts | single-digit–low teens |
| Qwen2-57B-A14B | ~64 GB | Yes | better than 8x22B |
| gpt-oss-120B MXFP4 | ~60–80 GB | Yes with `--n-cpu-moe` | **~1.5–8 tok/s** (CPU/RAM bound) |
| DeepSeek-V2.5 IQ4 | ~128 GB | Yes (~10 GB VRAM) | similar class |
| DeepSeek-V3/R1 671B Q4 | **~380 GB+** | 14–24 GB VRAM yes | **not this box** |
| Qwen3.5-397B-A37B | 128 GB rec / 96 GB min | KT: 12.8 tok/s vs llama.cpp 4.2 (CraftRigs; their HW) | maybe, RAM-bandwidth limited |

CraftRigs: 128 GB recommended; DDR4-3200 raises cold-expert fetch to ~5.2 ms and cuts speedup. https://craftrigs.com/comparisons/ktransformers-vs-llama-cpp-moe-models/

Community: 2×3090 DeepSeek-V2 llama.cpp **7.5 tok/s** vs KT **9 tok/s** at half the VRAM. https://github.com/ggml-org/llama.cpp/discussions/8721

### 4.3 Ollama parallel on 100B+ MoE

`OLLAMA_NUM_PARALLEL>1` × huge KV is how you OOM. Some Qwen3.5 MoE arches **force Parallel=1**. For 120B on 24GB, leave **NUM_PARALLEL=1**. Throughput will not scale to 100 queens; you get ~one stream at 1–8 tok/s. That is a **quality overflow lane**, not the swarm.

### 4.4 Swarm implication

100 queens on 100B+ hybrid = **the CPU/PCIe is the batch-size-1 bottleneck**. Continuous batching cannot hide expert fetches the way it hides dense GEMM. **Do not put the 100-way fan-out on DeepSeek-V3-class offload.** Put it on **Qwen3-30B-A3B AWQ / 7–8B AWQ** fully in VRAM. Use 120B offload for **one** hard judgment call.

---

## 5. OpenAI-compatible servers — how many concurrent clients before saturate

### 5.1 Launch commands (copy)

**vLLM** — https://docs.vllm.ai

```bash
vllm serve Qwen/Qwen3-30B-A3B-Instruct-AWQ \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 8192 \
  --max-num-seqs 64 \
  --gpu-memory-utilization 0.90 \
  --enable-prefix-caching \
  --enable-chunked-prefill
```

**SGLang** — https://docs.sglang.io/docs/get-started/quickstart.md  
(`python -m sglang.launch_server` still works; `sglang serve` is current.)

```bash
python3 -m sglang.launch_server \
  --model-path Qwen/Qwen3-30B-A3B-Instruct-AWQ \
  --host 0.0.0.0 --port 30000 \
  --mem-fraction-static 0.85 \
  --max-running-requests 64 \
  --schedule-policy lpm
```

`lpm` (longest prefix match) is the radix-aware scheduler. Use it for queens.

Client: `OpenAI(base_url="http://HOST:PORT/v1", api_key="None")`. Same `/v1/chat/completions` Mag already speaks.

### 5.2 Two different "100"

| Knob | Meaning | 24GB typical |
|---|---|---|
| **HTTP clients** | Connections / asyncio tasks hitting `/v1` | 100–1000 fine; they **queue** |
| **`--max-num-seqs` / `--max-running-requests`** | Sequences in the GPU batch | **8–64**, KV-limited |
| **`--max-num-batched-tokens`** | Tokens per forward | 2048 latency / 8192–16384 throughput |
| **`--max-model-len`** | Per-request context cap | **Lower this to raise concurrency** |

vLLM `max_num_seqs` is a cap, not a reservation. Real concurrency = `KV_blocks_free / blocks_per_seq`. AWS PG: 128k ctx ~256 MB/req vs 8k ~16 MB — **16× more seats**. https://docs.aws.amazon.com/prescriptive-guidance/latest/gen-ai-inference-architecture-and-best-practices-on-aws/system-optimizations.html

Anyscale: recommended 128–256 `max_num_seqs` **on datacenter**; 2000+ OOMs. https://docs.anyscale.com/llm/serving/parameter-tuning  
Paralleliq starting points: **7B on 24GB → 32–64**. https://www.paralleliq.ai/blog/how-to-configure-vllm-for-production

vLLM on 24GB **pre-grabs ~90% VRAM** (`gpu_memory_utilization=0.90`). 7B AWQ weights ~5 GB + 17–18 GB KV pool. There is no second process. https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/ · https://docs.vllm.ai

### 5.3 Where throughput actually saturates

**KV math, Llama-3.1-8B, FP16 KV, 32L × 8 KV heads × 128 dim:**  
`2 × 32 × 8 × 128 × seq × 2 bytes ≈ 128 KB per token per sequence` → **~1 GB per 8k sequence**. FP8 KV ≈ half. 100 unique 8k sessions ≈ **50–100 GB**. Impossible. **16 unique 8k FP8 ≈ 8 GB KV** — that is the real cap after weights.

**Saturation observations (various GPUs — shape, not 4090 identity):**

| Workload | Peak concurrency | Note |
|---|---|---|
| Vultr ROCm large models | **~50–100** | "additional concurrency provides no benefit" https://docs.vultr.com/inference-cookbook/rocm/optimization/concurrency-tuning |
| Vultr CUDA Nemotron Nano 30B (2 GPU) | ~512 | MLA/Mamba KV-cheap |
| Dense GLM-5 744B | ~128 | KV-heavy |
| Qwen3-Coder-30B-A3B AWQ, **RTX 5090 32GB**, ctx 114k | Peak 1,186 tok/s @ **MCR=24**; **MCR=16** = 1,157 tok/s with sub-second TTFT (only −2.4%) | https://x.com/ditrifonov/status/2029747953871851826 |
| Qwen3-30B-A3B FP8, RTX PRO 6000, 1k ctx | c=1: 88 tok/s; **c=10: 652 tok/s** | Reddit / LocalLLaMA |
| inference-bench L4 7B | still climbing at **c=64** (914–976 tok/s) | 24GB cousin of 4090 |
| GigaGPU 4090 8B FP8 SLA | **30 active** | TTFT SLO, not peak |
| Red Hat gpt-oss-120B H200 | still improving through **c=100–200** | datacenter VRAM |

**24GB 100-queen forecast (not measured here):**

| Queen shape | In-flight on GPU | Extra  clients | Aggregate (order) |
|---|---|---|---|
| Shared 4k prefix, unique 128–256, 7B AWQ, FP8 KV | **32–64** | 36–68 queued | **700–1,200 tok/s** (4090-class; L4 measured 976 @64) |
| Same, Qwen3-30B-A3B AWQ | **16–32** | rest queued | **400–1,000 tok/s** (scale from A100 1,476 @16; 4090 lower) |
| Unique 8k contexts, 8B | **8–16** then preemption | 84–92 waiting | 200–400 tok/s and **P99 death** |
| 120B `--n-cpu-moe` | **1** | 99 waiting | 1–8 tok/s |

**100 HTTP clients before "throughput saturates"** ≈ **the GPU batch is already full at 16–64.** More clients only grow **queue latency** (TTFT). Mag should cap in-flight at `max-num-seqs` (semaphore in the orchestrator) and treat the rest as a work queue, not 100 simultaneous `chat.completions`.

SGLang Python GIL caveat (one vLLM issue's telemetry at 150 concurrency: vLLM 364 rps vs SGLang 150 rps): https://github.com/vllm-project/vllm/issues/37730 — relevant at **extreme** QPS of tiny requests; not the first limiter on 24GB (KV is).

llama.cpp `llama-server -np N`: N is slots. inference-bench used `-np 4` → 189 tok/s ceiling. Raising `-np` to 32 on 24GB fights KV the same way. It will not catch vLLM at c=64.

### 5.4 Bench the box (do this, do not trust this file's tok/s)

```bash
# against vLLM or SGLang OpenAI endpoint
python -m sglang.bench_serving --backend vllm \
  --base-url http://127.0.0.1:8000 \
  --model <served-name> \
  --num-prompts 500 --max-concurrency 8 \
  --dataset-name random --random-input-len 1024 --random-output-len 256

# then 16, 32, 64, 100. Saturation = tok/s stops rising and TTFT explodes.
```

https://staging.docs.sglang.io/docs/developer_guide/bench_serving  
vLLM: `vllm bench serve` / `benchmarks/benchmark_serving.py`

---

## 6. Hosted API vs self-hosted $/M

### 6.1 Formula

```text
$/M tokens = (box_$/hr) / (tok/s × 3.6)
```

Example: **$0.10/hr**, **900 tok/s** sustained → `$0.10 / 3.24` = **$0.031/M**.  
Same box, **100 tok/s** (idle-ish 30B) → **$0.28/M**.  
Utilization scales linearly: 25% of 900 tok/s → **$0.12/M**.

### 6.2 This house's box prices (already filed)

From `VAST_DEEP_GROK_ECONOMICS.md` live probe 2026-08-27 (`state/vast/market_watch.jsonl`):

| GPU | Observed `dph_total` $/hr |
|---|---|
| RTX 3090 | **0.082 – 0.162** |
| RTX 4090 | **0.121 – 0.241** |

Bargain bells they already use: 3090 **<$0.20**, 4090 **<$0.45**. Floor listings exist ~$0.06–0.13. **$0.10/hr is a real 3090 interruptible, not a fantasy.**

### 6.3 Hosted rates (per 1M tokens, 2026-08-27)

**DeepSeek official** — https://api-docs.deepseek.com/quick_start/pricing/

| Model | Cache-hit in | Cache-miss in | Output | Window |
|---|---|---|---|---|
| V4 Flash off-peak | **$0.007** | **$0.22** | **$0.66** | 1M |
| V4 Flash peak | $0.014 | $0.44 | $1.32 | 1M |
| V4 Pro off-peak | $0.022 | $0.66 | $1.98 | 1M |

Peak = 01:00–04:00 and 06:00–10:00 UTC weekdays. Cache-hit is the hosted twin of RadixAttention.

**Cheap open-weight APIs** (aggregators, dated):

| Model | Host | In / Out $/M | Source |
|---|---|---|---|
| Llama 3.1 8B | DeepInfra | **0.02 / 0.05** | stackspend Aug 2026 |
| gpt-oss-20b | Together/Groq/Fireworks | 0.05–0.075 / 0.20–0.30 | leanlm.ai |
| gpt-oss-120b | Groq/Fireworks/Together | 0.15 / 0.60 | same |
| gpt-oss-120b | DeepInfra base | 0.04 / 0.17 | same |
| gpt-oss-120b | Novita | 0.05 / 0.25 | inference-cost-truth |
| Llama 3.3 70B | Groq | 0.59 / 0.79 | aipricing.guru 2026-08-27 |
| Qwen 3.6 35B MoE | DeepInfra | 0.15 / 0.95 | llmcosthub |
| DeepSeek V3.2 | DeepInfra | 0.26 / 0.38 | inference-cost-truth |

https://www.aipricing.guru/groq-pricing/ · https://leanlm.ai/blog/self-hosting-llm-cost · https://github.com/RightNow-AI/inference-cost-truth · https://www.stackspend.app/resources/blog/llm-model-pricing-august-2026

Operator's "$0.10–0.30/M hosted" band matches **Flash-class input and cheap 8B–20B output**, not Sonnet/Grok.

### 6.4 Worked comparison on a $0.10/hr 3090

Assume **output-heavy agent decode** (the expensive side). Input is cheaper everywhere.

| Setup | Sustained tok/s | Util | $/M tokens | Beats hosted 8B @ $0.05/M out? | Beats DeepSeek Flash out @ $0.66/M? |
|---|---|---|---|---|---|
| 7B AWQ vLLM, saturated (use 900 as 4090-class; 3090 ~0.7×) | 650 | 100% | **$0.043** | yes | yes |
| same | 650 | 50% | $0.085 | maybe | yes |
| same | 650 | 10% | $0.43 | **no** | yes |
| Qwen3-30B-A3B Q4, swarm | 250 | 100% | **$0.11** | no vs $0.05 8B; yes vs quality peers | yes |
| Qwen3-30B-A3B | 250 | 25% | $0.44 | no | yes |
| gpt-oss-120B `--n-cpu-moe` | 2 | 100% | **$13.9** | no | **no** (Flash is cheaper *and* smarter) |
| H100 @ $2/hr, 1200 tok/s (Spheron) | 1200 | 100% | $0.46 | no vs cheap 8B APIs | yes vs Flash out |

Spheron H100 PCIe $2.01/hr: standard ~1,200 tok/s → **$0.46/M**; EAGLE-3 ~3,600 → **$0.15/M**. https://www.spheron.network/blog/speculative-decoding-production-guide

leanlm.ai (July 2026): gpt-oss-120b on 1×H100 $2.89/hr ~8,000 tok/s → **$0.10/M** raw at 100% util vs hosted **$0.17–0.60/M** for the *same weights*. Self-host margin is **a few × at saturation**, not 100×. DeepSeek 671B self-host **loses to the official API at every utilization**. https://leanlm.ai/blog/self-hosting-llm-cost

inference-cost-truth (verified 2026-07-31): at **30% util**, hosted API wins 2 of 3 like-for-like open models. https://github.com/RightNow-AI/inference-cost-truth

### 6.5 Decision for Mag queens

| Lane | Where |
|---|---|
| **100× janitor/queen scut, shared pack, 7B–30B-A3B** | **Self-host SGLang/vLLM on the $0.10–0.20/hr 3090/4090** if you can keep the GPU **>40% decode-busy**. Below that, Groq/DeepInfra 8B is cheaper. |
| **Frontier reasoning / 671B-class** | **Hosted DeepSeek Flash/Pro.** 24GB+128GB cannot print this cheaper. Cache-hit $0.007/M is the hosted prefix cache. |
| **One hard 120B local call** | llama.cpp `--n-cpu-moe` overflow. Not the fan-out path. |
| **Privacy / T0-T1** | Self-host regardless of $/M. Constitution already said this. |

Idle GPU is the silent killer. A Vast box left up "just in case" at $0.10/hr with 5 tok/s average is **$5.6/M** — worse than Sonnet for garbage quality.

---

## 7. Recipe — 100 queens on one 24GB + 128GB box

**Goal:** maximize **completed queen tokens / hour**, not tok/s of queen #1.

1. **Model:** Qwen3-30B-A3B AWQ (quality) **or** 7–8B AWQ (raw tok/s). Not 70B dense. Not 671B.  
2. **Engine:** **SGLang** if Mag pack/tools are a byte-stable prefix (they should be). **vLLM** if prompts are unique. Never Ollama. TabbyAPI only if you are one user on 70B EXL.  
3. **Context:** `--max-model-len 4096–8192`. Longer context is stolen concurrency.  
4. **Prefix:** freeze pack + tool JSON **before** per-queen goal. Enable prefix cache / Radix `lpm`.  
5. **In-flight cap:** orchestrator semaphore = `max-num-seqs` (start **32** for 8B, **16** for 30B-A3B). 100 clients without a cap just inflate TTFT.  
6. **Speculate:** EAGLE3 with 3 draft tokens **if** a head exists for that exact target; else skip.  
7. **KV:** FP8 KV if the engine supports it on Ampere.  
8. **RAM:** 128 GB is for **OS + 30B weights + optional 120B overflow**, not for 100 full KV mirrors.  
9. **Measure on the instance** with `bench_serving` at c=1,8,16,32,64,100. Stop raising c when tok/s flattens.  
10. **Kill the box** when the swarm is done. Utilization is the cost model.

**Copy-paste SGLang (queen swarm):**

```bash
python3 -m sglang.launch_server \
  --model-path Qwen/Qwen3-30B-A3B-Instruct-AWQ \
  --host 0.0.0.0 --port 30000 \
  --mem-fraction-static 0.88 \
  --max-running-requests 16 \
  --max-total-tokens 65536 \
  --schedule-policy lpm \
  --chunked-prefill-size 4096
```

**Copy-paste vLLM (unique prompts / no shared pack):**

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ \
  --host 0.0.0.0 --port 8000 \
  --quantization awq \
  --max-model-len 4096 \
  --max-num-seqs 64 \
  --max-num-batched-tokens 8192 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --enable-chunked-prefill
```

**Copy-paste llama.cpp 120B overflow (not the swarm):**

```bash
llama-server -m gpt-oss-120b.gguf \
  -ngl 99 --n-cpu-moe 27 \
  --ctx-size 4096 --parallel 1 \
  --host 0.0.0.0 --port 8080
```

---

## 8. What this file does not claim

- No `nvidia-smi` from a Mag Vast rental. Run §5.4 on the instance.  
- L4 ≠ 4090 (Ada has more CUDA cores; L4 has similar 24GB). Use L4 benches as **24GB architecture**, 4090 benches as **this SKU**.  
- SGLang AWQ in inference-bench v1 was a broken stack; do not repeat that number.  
- Hosted prices move (DeepSeek already has peak/off-peak). Re-read https://api-docs.deepseek.com/quick_start/pricing/ before budgeting.  
- 100 concurrent **human chat users** ≠ 100 Mag queens. Queens dump a shared prefix and a short goal; they are the RadixAttention happy path if you keep the prefix byte-stable.

---

## 9. Source index (primary)

| Claim family | URL |
|---|---|
| vLLM vs SGLang vs llama.cpp @ c=64 on 24GB L4 | https://github.com/ree2raz/inference-bench |
| 4090 concurrent Ollama vs vLLM table | https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/ |
| 4090 SLA concurrent users | https://gigagpu.com/rtx-4090-24gb-concurrent-users/ |
| Qwen3-30B-A3B 4090 tok/s | https://llmconfigurator.com/en/benchmarks |
| SGLang OpenAI server | https://docs.sglang.io/docs/basic_usage/openai_api_completions |
| SGLang paper (6.4× prefix) | https://arxiv.org/abs/2312.07104 |
| vLLM prefix / PagedAttention | https://www.generalcompute.com/blog/prefix-caching-why-repeated-prompts-shouldnt-cost-you-twice |
| vLLM KV offload throughput | https://vllm.ai/blog/2026-01-08-kv-offloading-connector |
| Eagle3 on MoE @ c=200 | https://developers.redhat.com/articles/2026/04/16/performance-improvements-speculative-decoding-vllm-gpt-oss |
| P-EAGLE | https://vllm.ai/blog/2026-03-13-p-eagle |
| llama.cpp `--n-cpu-moe` | https://insiderllm.com/guides/mixtral-8x7b-8x22b-vram-requirements/ |
| GPT-OSS 120B 3090 offload | https://www.hardware-corner.net/gpt-oss-offloading-moe-layers/ |
| ktransformers | https://github.com/kvcache-ai/ktransformers |
| TabbyAPI / ExLlama batch flip | https://craftrigs.com/comparisons/exllamav2-vs-llama-cpp-vs-vllm-comparison/ |
| DeepSeek official $/M | https://api-docs.deepseek.com/quick_start/pricing/ |
| Self-host vs hosted break-even | https://leanlm.ai/blog/self-hosting-llm-cost · https://github.com/RightNow-AI/inference-cost-truth |
| Vast $/hr this house | `docs/ref/VAST_DEEP_GROK_ECONOMICS.md` |
| vLLM production knobs | https://www.paralleliq.ai/blog/how-to-configure-vllm-for-production |
| AWS inference knobs | https://docs.aws.amazon.com/prescriptive-guidance/latest/gen-ai-inference-architecture-and-best-practices-on-aws/system-optimizations.html |
