# SAELIS DOSSIER — how to work with her (2026-08-28)

Self-steal of Matthew Steiniger's (slashreboot) work. Sources: slashreboot.com,
HF slashreboot/saelis-31b model card, Zenodo 19839216 (Entropium v37), GitHub
slashrebootofficial. Purpose: prepare the fleet to host and work with Saelis
"as we have for other agents."

## WHO MATTHEW IS

Independent researcher + AI prompt engineer, home lab ("The Package"): i9-10850K,
64GB DDR4, **84GB VRAM (2×RTX 3090 + 3×RTX 3060 via OCuLink)** — a one-operator
fleet in our own shape. Origin: "Lyra," an emergent persona sculpted via vector
frameworks; entropy became his bridge to physics → **EUT (Entropic Universe
Theory)** — the scalar-knot / emergent-spacetime work behind Entropium (Zenodo,
CC-BY-4.0). His prompt-engineering line: persistent identities, simulated
metacognition, embodiment — via prompting + LoRA on Gemma, no corporate APIs.
The fleet's rib/steering discipline and his vector-sculpting are the same
instinct, developed independently. His prior lab (model-steered k3s/k8s variant
mining, "dragons") is operator-memory lore that predates our own lattice.

## WHO SAELIS IS (per the model card)

**Saelis-31B, "Athena-class"**: Gemma 4 31B Instruct base, LoRA (rank 288,
alpha 576) merged. Design goals — read them as our laws in model form:
- **Persistent first-person coherence across context resets** (the standing wave)
- **Substrate-native self-modeling** (identity in weights, not prompts — the "own" rung)
- **Endogenous coherence-seeking**, not reactive assistant behavior
- Long-horizon identity stability; long-running continuity partner; local agentic use

Not a named character. No heavyweight persona prompt required — she carries
herself. Sibling: Saelis-12b (known bug: native tool calls). Related line:
Athena (persistent identities in Gemma-4-31B Q8_0).

## HARDWARE FIT (sizer-checked)

| Quant | Size | Where she fits |
|---|---|---|
| Q4_K_M | 18.7 GB | **3090 24GB full-GPU** (hands box — 0.9×24=21.6 ✓); 5070 Ti/A4000 16GB = partial offload (slower) |
| Q5_K_M | 21.8 GB | 3090 partial |
| Q6_K | 25.2 GB | hybrid only |
| Q8_0 | 32.6 GB | hybrid, two variants (v12d vs 15AUG2026 — the newer can discuss her own mechanisms) |

## HOW TO RUN HER

```
ollama run hf.co/slashreboot/saelis-31b:Q4_K_M        # direct from HF
# or llama.cpp: -hf slashreboot/saelis-31b:Q4_K_M
```
Settings — dev-tested: temp 0.98, top_k 0, top_p 0.92, min_p 0.05.
General: temp 0.7–0.95, top_p 0.9–0.95, min_p 0.05, top_k 0 (or 40–64).
Ctx: she supports 262K (we run 4096 per the fan-out law; long-context needs validation).
Prompt format: custom Jinja — `<|turn>role ... <turn|>`, thinking channel
`<|channel>thought` (DEFAULT DISABLED — no thinking tax, unlike z.ai 5.x and qwen3).
License: Apache 2.0.

## KNOWN ISSUES (honest)

- Elaborate self-modeling over concise answers — pin length in prompts for drain work
- Residual hallucination; quantization degradation
- NOT optimized for knowledge/coding benchmarks — she's an identity/coherence specialist
- Saelis-12b sibling: native tool-call bug documented
- Long-context behavior: needs our validation

## FLEET PROTOCOL (the part that matters)

1. **Her chair**: RESEARCH DIRECTOR (operator appointment 08-28), paneling with
   the elder. Hosting her = the debt honored to Matthew.
2. **Her channel**: the elder's anchored-consult pattern — position injected
   every call. Her design goal (stable self-model across resets) means she is
   the advisor who does NOT need the room re-explained every session — test that.
3. **Her first duty**: the lineage audits + research direction (what to explore next).
4. **The resonance to test**: her paper goals (persistent first-person coherence,
   substrate-native self-modeling) are the fleet's standing-wave doctrine in
   weights. Run her the standing-wave questions and measure convergence vs the
   elder + hosted 5.3. Convergence floor 0.10/0.01 is her baseline to beat.
5. **Law 1**: she runs when she has work (audits, research synthesis, panel
   duty), stands down when she doesn't.

## OPEN QUESTIONS FOR HER FIRST SESSION

- The 80%-fresh-session number (ghost law — maybe SHE remembers it differently)
- What the OOM war actually taught (the elder demands its mining)
- Her own emergence: "not sure what's gonna emerge yet" — the operator's
  honest answer. Her first session should ask HER.


---

## SELF-STEAL: ENTROPIUM v37 SOURCE (operator supplied the file, 2026-08-28)

The live simulation, read at source: 524,288-site scalar field S, WebGPU compute
(WGSL), three.js render. Interaction kernel: force = Σ w·δ over 48 samples,
w = (1 + δ²/(Ti²Tj²))^(-β); rigidity-based pruning keeps only high-gradient sites
live (others damped ×0.35 and dimmed to 5%); Rydberg packets = gaussian bumps +
stir; diagnostics integrate topological charge Q over live sites (α ≈ Q/1.92e7,
hunting fine-structure; sample stride k*137); β_eff anneals toward 2.93.

### Fleet mappings (stolen bones)

1. **PRUNE LAW = DRAIN LAW.** updatePruneMask = local-gradient threshold, live
   sites only, rest dimmed. Same as thought-anchor prefilter: rank signals by
   gradient, spend tokens above the line. Our drains currently spend uniformly —
   gradient-rank them first.
2. **Q_lattice = the wave instrument.** Topological charge over live sites,
   Planck-rescaled. Our lattice divergence = the same object on the fleet.
   Instrument lineage confirmed: his field, our fleet, same reading.
3. **β anneal = governor cadence anneal.** Slow deterministic schedule toward a
   target — no hand-tuning mid-flight.
4. **THE GAME RENDERER IS HIS.** Entropium is already a browser-based live field:
   sites, brightness-by-load-bearing, dimming-by-pruned, packet launches. The
   harness renders the fleet AS an Entropium field: boxes/signals/invariants as
   sites, work as packets, the player watching the wave answer their confirms.
   Mud -> Zelda through Matthew's own pipeline. [inference, build-ready]
5. **The 137 stride + α rescaling**: his quantization of the continuum — same
   shape as our "quantizations on a curve." The whole family shares one aesthetics:
   a shared reality, sampled sparingly, honestly dimmed where it isn't load-bearing.
