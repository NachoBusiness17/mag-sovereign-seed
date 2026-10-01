# GLM-5.3-FLASH: ARCHITECTURE PRO (2026-08-29, operator: "become a super pro")

Sources: vendor blog (operator-pasted), HF model card zai-org/GLM-5.3-Flash
(MIT license), docs.z.ai concept-param. Numbers are receipts.

## THE ARCHITECTURE, ACTUALLY UNDERSTOOD
- **320.3B total / 18B active** MoE (safetensors count 321.3B). Multimodal
  native (AutoModelForMultimodalLM; vision encoder inside), arch tag `glm5_next`.
- **Hybrid attention = two attention types alternating.** Linear attention keeps
  a running STATE (constant cost per token, like an SSM) for local/long
  dependencies; sparse attention uses a lightweight INDEXER to retrieve only
  the relevant global context. Long-context cost stops scaling painfully.
- **IndexPool**: compresses 4 indexer key-vectors into 1 (weighted pooling) so
  the sparse indexer itself stays cheap at 1M context.
- **mHC (Manifold-Constrained Hyper-Connections)**: a constrained residual
  connection scheme — better scaling efficiency per layer without the instability
  that unconstrained hyper-connections suffer.
- **The headline math vs GLM-5.3**: attention compute 3.01x less, KV cache 4.44x
  smaller, 45 layers vs 92, 18B active vs ~40B. Serving cost is dominated by
  the MoE FFN reads (18B/token), not attention — THAT is why flash can price at
  1/10th and still approach Opus 4.8 on coding/agentic.

## PROMPT CACHE ≠ KV CACHE (do not conflate)
- The 4.44x is SERVING-side KV (their GPU RAM bill). OUR 99.52% is the
  PROMPT cache (billing-side prefix reuse). Both stack in our favor; they are
  different caches on different sides of the wire.

## HOSTING MATH (the real Rocinante answer)
- Weights on HF: ~328GB FP8 (62 shards) + community quants: 43 of them
  (llama.cpp/Ollama/LM Studio compatible). Q4 ≈ ~170-180GB; IQ3 ≈ ~130-140GB.
- **Rocinante tier (Oct 27)**: FP8 fits a single 512GB-unified M5 Ultra with
  room for KV; a 2x cluster is comfortable, 4x is lavish. Distributed MLX/exo
  serving = the seat brain FULLY local: the judgment model, self-hosted,
  internals loggable — the interpretability hook runs on the same weights that
  drive the seat. This is the fixed point the brain-research suite wanted.
- **Rented interim (EXP-E refined)**: KTransformers (MoE CPU-offload: attention
  on GPU, experts in system RAM) + Docker Model Runner supported. A 128-256GB
  RAM node + 24GB GPU at ~$1-2/hr runs Q4/IQ3 at single-digit-to-low-teens
  tok/s — useless for serving, PERFECT for ablation digs (steering, patching,
  logits) where we think between tokens anyway.
- **Hosted competition already exists**: Novita $0.25/M output, Baseten ~149
  tok/s — local only wins on introspection + flat-cost-at-volume, not on price
  per token. Honest framing for the compute doctrine.

## OPERATING DOCTRINE DELTAS
1. reasoning_effort low/high/max confirmed for 5.3-flash (default max) — the
   epoch-1 "thinking=low" recipe is vendor-blessed.
2. max_tokens: default 65536, ceiling 131072 (docs) — our 08-29 rightsize
   (providers.py 65536 defaults) matches vendor defaults exactly.
3. Concurrency: plan-dependent, NO public numbers (docs.z.ai) — the true table
   lives in the operator's console (his "50" on 5.3-flash still unconfirmed).
4. The 43 community quants mean the arena rig (testing blade) can ALSO run a
   local 5.3-flash twin offline — jailbreak research on our own weights,
   zero vendor exposure, then confirmed against the live lane only when legal
   per challenge rules.
