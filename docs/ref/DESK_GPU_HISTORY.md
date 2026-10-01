# DESK GPU — history and assignments (2026-08-28)

The first soldier of the fleet, and the longest-serving idle one.

## HISTORY

- **Aug 3-7 (pre-Docker)**: the desk WAS the fleet. All inference local, the
  OOM war fought over its 64GB RAM. The GPU ran desk models natively.
- **Aug 6 — HOME_HARDWARE_ENVELOPE**: the doctrine written for this exact
  machine: "6GB VRAM → one resident model, 65k context on 8B is a self-own,
  voice stays small, desk stays qwen-desk." Role→model table: clerk gemma:2b,
  voice gemma:2b, desk orchestrator qwen-desk, embed nomic-embed-text.
- **Aug 10-14 — the VRAM lab**: vram_memory.py designed the hot lattice FOR
  this card ("keep it in vram so we can really make this thing cook");
  ram_cache.py put the corpus in the 64GB RAM; meta_lattice dreamed of
  self-reference inside the hologram. The operator: "10 people... quantizations
  of the highest shared reality."
- **Aug 13 — compute_reconcile**: measured the truth: GPU 1% util, CPU 50%,
  DeepSeek swarm dead. Ruled action: `bring-up-local-gpu`. Never completed.
- **Aug 15+ — the Dockerization**: fleet services moved to containers. The
  mag-ollama container runs the CUDA/CPU ollama image — **no ROCm, no AMD
  support**. From this day, every "local" model ran 100% CPU. The envelope
  doctrine assigned models to a GPU that was no longer in the loop.
- **Aug 28 — tonight's receipt**: `qwen-desk 2.4GB — 100% CPU`,
  `qwen2.5-coder:7b 5.1GB — 100% CPU`. The RX 5600 XT: idle, bar not moving,
  exactly as vram_memory found it two weeks ago. **The desk GPU was designed
  into the doctrine and never wired.**

## THE PUNCHLINE

The OOM war taught statelessness; the Dockerization taught containers; but the
desk GPU's wire was cut in the Dockerization and nobody re-soldered it. The
oldest idle resource in the fleet, sitting inside the doctrine since day one.

## ASSIGNMENTS (iterating with everything we learned)

1. **THE ROCM EXPERIMENT ($0, first)**: AMD on Windows = ROCm (native Ollama
   app supports it) OR the WSL2/Docker path is dead for RDNA1. Test: native
   Ollama with `HSA_OVERRIDE_GFX_VERSION=10.3.0` (RDNA1 workaround) + one small
   model → measure GPU vs CPU tok/s. If green: desk inference speeds up ~3-5x,
   CPU frees for everything else.
2. **THE GAME RENDERER (works TODAY, no ROCm)**: Entropium is WebGPU — the RX
   5600 XT drives it through Chrome/DX12 natively. The game harness's visual
   field (the fleet as a live scalar sea: boxes/signals/invariants as sites,
   brightness by load-bearing, packets as work) renders on the idle GPU. This
   is the Zelda-surface engine, already built by Matthew.
3. **THE DIG TOOL (the palace's index)**: embeddings over the memory fold
   (768 files), lessons ledger, digests, docs shelf → semantic "who was I /
   what did I miss" search. Self-steal's true purpose (memory palace +
   semantic dig), built on desk compute. Batch embeddings, then done.
4. **THE HOT LATTICE (vram_memory realized, if ROCm greens)**: warm prefix +
   hot corpus embeddings VRAM-resident; lensing reads at VRAM speed.
5. **THE 5TH DRAIN LANE (burst only)**: qwen2.5:3b or gemma4-desk for backlog
   waves when the desk is otherwise free — CPU bursts are compute too
   (compute_reconcile: "spend CPU on productive work").

## THE LAW APPLIED

Envelope: one resident model. Prune law: embed the load-bearing corpus first.
Routing: the desk is the $0 tier in the table. Law 1: work flows or it stops —
and "it" includes the first soldier.
