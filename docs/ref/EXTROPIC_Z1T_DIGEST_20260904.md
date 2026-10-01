# EXTROPIC Z1T DIGEST — blog deep-read (2026-09-04, zcode card-worker)

Source: https://extropic.ai/writing/z1t/ (fetched full HTML, text extracted).
Companion to watch/INTAKE_EXTROPIC_Z1T_20260904.md; feeds
docs/ref/NNUE_SIDECAR_BRIEF_20260904.md (hardware-rhyme section).
Authors: Verdon, Neagoe, Lockwood, Morton (Extropic). Dated 2026-09-04.
The tweet's "140x" is one cell of a table whose honest headline is a RANGE
(14x–139x depending on assumed H100 utilization) — the digest below is the
technical read.

## What the hardware actually does (vendor description, mechanism-level)
- Z1 = sub-threshold CMOS chip of "probabilistic bits" (pbits): binary
  stochastic units whose bias is set by 16 tunable couplings each. The chip
  samples a programmable Ising model via chromatic Gibbs sampling at 50 MHz,
  in-memory. Topology: 8 cores x 33,696 pbits = 269,568 pbits, 2,135,904
  hardwired edges, <1 W claimed.
- Continuous numbers are encoded as dy4p "p-Int4" bundles (4 weighted pbit
  streams, levels 1/4..1/32); the VALUE is the empirical mean of N samples,
  so precision is tunable at runtime (k <= 0.5*log2(N) - log2(sigma) bits
  effective) — noise buys fractional bits by spending more samples.
- The compute primitive is a "tanh-linear unit": E[v|h] = tanh(b + sum J h),
  i.e. a sparse matrix-vector product FUSED with tanh, executed by physics.
  RMSNorm is replaced by Dynamic Tanh (DyT, Zhu et al. 2025); attention is
  replaced by gated convolutional attention (GCA, AFT lineage) — O(TD) local
  ops, no softmax-QK, no dense matmul. Everything that Z1 cannot do (embedding,
  residuals, transcendentals, the vocabulary logit readout) runs on an FPGA
  co-processor on the same board. Disaggregated decode: FPGA orchestration +
  Z1 sampling.

## What the model class is
Z1T = 4-block, D=512, T=1024, ~11.55M body params (excluding vocab readout),
4-bit weights, k=4 sparse projections, GCA attention, DyT norms — a
transformer-like decoder deliberately mutated away from dense-matmul shapes to
be a subgraph of Z1's fixed degree-16 connectivity. Trained on OpenWebText
with GPT-2 BPE. OPEN artifacts: open weights (one larger run) on Hugging Face
+ open training recipe on GitHub. Scaling experiments sweep connectivity c on
a standard GPT-2 decoder too.

## The scaling-law claim (stated honestly by the vendor)
Sparse models are LESS compute-efficient: matching GPT-2-small loss takes
~9.5e19 FLOPs, "about an order of magnitude more FLOPs" than dense. The claim
is that Z1 ops are ~3 orders of magnitude more energy-efficient per op than
GPU ops, so 10x FLOP penalty x 1000x op-energy win => ~2 orders (100x)
energy win end-to-end. It is an ENERGY-vs-LOSS trade curve with connectivity
as a new axis, not a claim that sparsity beats dense at equal compute. The
vendor says this themselves: "dense models are more efficient per FLOP."

## The energy numbers — what is measured vs assumed
CRITICAL: the Z1 side of every number is a PROJECTION, not a measurement.
Blog's own words: "the following projections are based on theoretical chip
energy consumption of Z1 based on our best estimates, anchored to reality
from our experiments with similar pbits in X0."
- Z1T: 294.52 nJ/token = 8.74 nJ Z1 sampling (1.3e-14 J/sample, projected)
  + 285.78 nJ FPGA work (0.2 pJ/matmul-op, 3.0 pJ/scalar-op, 1.5 W static).
  >95% of the energy is the FPGA, not the exotic hardware.
- H100 reference: 40.9 uJ/token at 10% MFU, 8.17 uJ at 50%, 4.09 uJ at 100%
  (fp16, batch-1 decode of the dense-equivalent 11.55M model, measured
  2026-08-12). Ratios: ~139x / ~28x / ~14x. Z1-layers-only: ~4,680x.
- EXCLUDED from the ratio: the dense vocabulary logit readout (including it:
  ~136.4 uJ/token on FPGA — which would ERASE most of the win), and
  FPGA<->Z1 data movement. Chip count for model-parallel placement not modeled.
- Latency: 58.8 us/token (~17k tok/s claimed serial) vs H100 eager 702 us /
  torch.compile 102 us. Honest caveat given: at this tiny model size the H100
  is at 0.006% MFU and batching "would make H100s substantially more
  efficient"; prefill stays on GPU.

## Claims table (tri-state)
| Claim | State | Evidence |
|---|---|---|
| Z1 is a real pbit/Ising chip, Gibbs-sampling, 50 MHz, <1 W | Vendor-claimed (mechanism credible, silicon receipt thin) | Blog + refs [1-3]; X0 experiments cited, no third-party silicon benchmark |
| tanh-linear unit computes tanh(Wx+b) via sampling, tunable precision | Supported-by-paper lineage (math is sound; Ising/Boltzmann expectation identity is standard) | Blog math + refs [11,19,20]; vendor-authored arXiv 2607.16183, 2608.01612, 2608.01615 |
| Z1T model trains and follows a scaling law paralleling dense transformers | Vendor-claimed (plausible; loss-vs-FLOPs plot with GPT-2 anchors shown; open weights + recipe let third parties check) | Fig. 1; HF weights + GitHub recipe |
| Sparse Z1T needs ~10x more FLOPs than dense at equal loss | Vendor-claimed, and stated AGAINST their own interest — highest-credibility claim in the piece | Fig. 1 dashed fit |
| Z1 sampling costs 1.3e-14 J/sample | Unproven (projection from X0, anchored, but not measured on shipping silicon) | Blog "theoretical chip energy ... best estimates" |
| "140x energy efficiency vs GPUs" | Unproven as a headline (it is the 10%-MFU cell; 14x at 100% MFU; excludes logit readout which alone is ~136 uJ on FPGA; assumes dense H100 baseline of an 11.5M model at batch 1) | Blog Fig. 7 table — the fine print contradicts the tweet |
| FPGA-free design could reach ~1000x vs GPU | Unproven (future-chip projection) | Blog outlook section |

## Availability
Open weights (one larger Z1T run, Hugging Face) + open training recipe
(GitHub) + the earlier blueprint papers on arXiv. No devkit; Z1 chips not
for sale to us. Rocinante fit: zero hardware; value is conceptual.

## The Stockfish-split read (why the fleet cares)
This is EXACTLY the NNUE sidecar brief's hardware rhyme, from the vendor side:
the analog/probabilistic substrate takes the EVAL-LIKE kernels (sparse
projections, tanh-linear "activations" = leaf scoring) while everything that
needs exactness (residuals, embedding, vocabulary readout, prefill) stays
digital on the FPGA/GPU. Search analog: none — but the split is the same
shape as Stockfish: cheap noisy leaf eval, digital tree around it.
The brief's calibration law maps directly: Z1T's pbit values are ESTIMATES
with variance falling as 1/N samples — the blog's own precision bound
(k <= 0.5 log2 N - log2 sigma) IS a leaf-variance budget. "Calm leaf or
poisoned cutoff" becomes a sampling-rate question: at 32 parallel samples per
tan h-linear (their latency budget), what is the tail variance of an eval
score, and would an alpha-beta cutoff built on it be safe? That is the
falsifiable engineering question this digest hands to the accumulator work.
Also steals cleanly into MAX_DISTILL: efficiency-via-structure (sparsity +
probability, not scale), with the vendor's own admission that structure buys
energy, not FLOPs.

## What would falsify the 140x claim
1. Measure a real Z1 (or the X0 successor) sampling energy above 1.3e-14
   J/sample by ~2 orders — the whole win collapses to the FPGA side.
2. Include the vocabulary readout (136.4 uJ/token on their own FPGA estimate)
   in the ratio: end-to-end it is ~2.9x vs the 10%-MFU H100, roughly parity
   at 50% MFU. The 140x number exists only because the readout is excluded.
3. Count chip count / inter-chip data movement for model-parallel placement
   (explicitly not modeled).
4. Third-party H100 baseline at realistic batch/MFU: a batched H100 runs this
   11.5M model far below 4-40 uJ/token.
5. Reproduce the scaling curve from the open weights and find the sparse
   FLOP penalty is worse than 10x (their own numbers say the win is
   1000x-per-op MINUS 10x-FLOP-penalty; every multiple on the penalty divides
   the headline).

## Verdict
Real research, unusually honest fine print, marketing headline cherry-picks
the best cell of its own table. Watch-lane item: open weights make the
scaling claim checkable; the energy claim stays Unproven until independent
silicon numbers exist. No fleet action beyond the conceptual steal.
