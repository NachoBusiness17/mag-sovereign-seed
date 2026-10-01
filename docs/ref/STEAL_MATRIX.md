# STEAL MATRIX — mispriced hardware, right-sized tasks (2026-08-28)

Operator thesis: hunt "weird systems we can exploit with our unusual systems —
broken otherwise, but cheap and awesome for the right-sized tasks." Price is
per GPU-hour; VALUE is per right-sized task. Rank tok/s-per-dollar for the
TASK, never $/hr alone. Every row graduates from folklore to receipt the first
time a boot measures it (desk-probe at READY).

| Hardware the market calls broken | Why it's mispriced | Our exploit | Task class |
|---|---|---|---|
| RAM-rich + VRAM-poor (e.g. 188GB RAM + 3090, $0.30/hr) | RAM "wasted" on a GPU box | llama.cpp expert-offload `-ot ".ffn_.*_exps.=CPU"` runs 120GB MoE brains | BRAIN — proven tonight (receipt) |
| Old arch (V100 16GB) at $0.05–0.11 | No tensor hype, "too small" | fp16 inference of 7–8B quants is fine; cheapest $/blade seen | Fan-out blades |
| 3060 12GB at $0.05 | Gamers want 24GB | qwen3:8b needs ~5–6GB — full-GPU fit, 2x margin | Blades (2 of 3 dark so far — class suspicion logged) |
| Interruptible / preemptible (−50–80%) | Jobs die mid-run | Idempotent rib batches: steering batteries, eval burns, 100-way fan-out — death is free, requeue is cheap | Stateless burns only |
| High-core CPU-only boxes ($0.02–0.05) | "No GPU" | 0.6b/1.7b models, embeddings, n-gram tables (the wave-mechanism NVMe play), transcription | Warm/witness work |
| Storage-rich GPU-weak (1TB+ disk) | Disk doesn't sell | THE SHELF: stage weights once; volume clone targets; hub bypass | Stage-2 volume host |
| 2× small GPUs (2×V100 etc.) | Can't pool VRAM for training | llama.cpp split-mode = 2× VRAM for mid models | Mid-brain tier |
| Same-datacenter-as-volume hosts | Locality invisible in search | Clone volume in minutes vs hours re-pull | Any boot after stage-2 |

## Hunting laws

1. **Steal-score, not price**: `expected_tok_s(task, gpu_class) / dph` ranks
   offers; V4.1 wires this into blade_buyer once measurements exist.
2. **Measure at READY**: every first boot of a class runs the desk-probe —
   folklore becomes receipt or the class dies honestly.
3. **Exploit asymmetry**: our unusual systems (expert-offload, idempotent
   ribs, riddler-locality, n-gram tables) are exactly what mispriced boxes
   are good at. The market's "broken" is our "right-sized."
4. **Class suspicion**: when a whole class keeps failing (2/3 dark 3060s),
   log it in the wedge ledger and demote the class — the box isn't the issue,
   the neighborhood is.
