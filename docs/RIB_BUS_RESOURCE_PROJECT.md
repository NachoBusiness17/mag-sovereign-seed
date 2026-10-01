# RIB-Bus Resource Project — the instruction layer routed through the VRAM-anchored verkle bus

> Operator (2026-08-11): "all of our rib files are basically instructions for flocks on how to act
> intelligently from frontier models down to these dumb workers ... wire everything through memories
> so we can speed this up and align more succinctly with our own stuff" + "route almost everything
> through [the bus] ... do research around it so we can exploit it."
> Schema: rib_bus_resource_project.v1 · Deterministic + $0 (this doc is a file-tool artifact; the
> frontier/LLM validation is queued separately through ghost's exec surface).

---

## 1. The architecture (what we built)

The central idea: **RIBs are the instruction layer** — frontier-produced invariants (Roshomon-core
convergent truth, attractor-tool memlang chords, mined frontier steer) compressed down to cheap
worker instructions. The cheap workers then "act as autonomous robots" doing what the frontier
asked, on our compute.

That instruction layer is now routed through **the bus** (mag/verkle_bus — a Redis Pub/Sub ↔ Verkle
knot bridge, now anchored by GPU/VRAM telemetry via mag/gpu_k8s), and **through memory** (the
source of truth aligned with our doctrine).

```
 frontier produces RIBs (invariants)
        │
        ▼
 mag/rib_renderer.dispatch() ──► mag/rib_bus.publish_rib()
        │                            │ fold → verkle knot (content-addressed, replayable)
        │                            │ publish → mag:rib (real-time sync)
        │                            │ store → memory/rib_bus/<domain>.json  (SOURCE OF TRUTH)
        ▼                            ▼
   k8s render farm (cheap workers)   all agents sync via the bus
        ▲                            ▲
        └────── mag/rib_bus.inject_for() ◄──── workers AUTO-MOUNT the domain's RIB instruction set
                                             (base frontier steer + mounted domain RIBs)
```

Key module: **mag/rib_bus.py** (schema `rib_bus.v1`, deterministic + $0).
- `publish_rib(invariant, domain)` — fold as verkle knot + publish `mag:rib` + append to the
  per-domain memory store.
- `mount(domain)` — auto-load the bus-grown instruction set from memory.
- `inject_for(slice, domain)` — drop-in for `frontier_steer.inject()`: workers auto-carry the
  frontier instruction layer **aligned with our memory**, not a static hardcoded block.

Wired: `stateless_research.launch()` uses `inject_for`; `rib_renderer.dispatch()` publishes RIBs to
the bus before enqueueing; `mag:rib` channel added to `verkle_bus`.

The VRAM/GPU anchor: `mag/gpu_k8s.py` reads GPU telemetry from the k8s node and folds it as a
verkle knot + publishes to the bus — so the bus has a **hardware-truth anchor** (real VRAM state)
that any seat/mem-tool reads, not just derived state.

## 2. Curated external resources / mechanisms (grounded)

**Grounding honesty:** the external web research call for this pass was interrupted by network
failure, so anything below that we have NOT directly read is explicitly marked **SPECULATION — not
yet verified**. We do not fabricate claims we couldn't read. What IS grounded is marked as such.

**Grounded (verified in our own repo / verified field-steal this session):**
- **Verkle event bus + flywheel** (ours): `mag/verkle_bus.py`, `mag/verkle_knot.py`, and the
  verkle-bus research project (`memory/steal/VERKLE_BUS_RESEARCH_PROJECT_*`, `mag/window_bus.py`):
  bounded window → mine invariant → accept → self-contained verkle knot (content hash = address,
  CAS) → parent root ties back → all agents sync via `mag:verkle`. Grounded: validated, folded.
- **GPU-in-k8s → verkle** (ours): `mag/gpu_k8s.py` — cluster resource the host can't see becomes a
  content-addressed knot. Grounded: built 2026-08-11.
- **Shader-bus** (ours): `mag/shader_bus.py` — a shader (pure function) as a register + LSB bus in
  one image. Grounded: validated.
- **Blackboard / multi-agent orchestrator clones** (verified external field-steal this session, from
  `mine/raw/steal_protocol`): agentswarm (conductor + verifier + `evidenceOverlap` independence),
  microsoft/conductor (deterministic `when`-routing + OutputValidator), marikarx/subagent-router
  (risk-gated escalation + budget hard-stop), togethercomputer/moa (layered proposer/aggregator),
  whiteducksoftware/flock (typed blackboard + fan-out), arvarik/bmas (control-unit rounds + decider).
  Grounded: read + adapted into gap_swarm_experiment.

**Related patterns worth researching next — SPECULATION, not yet verified (do NOT cite as fact):**
- **KV-cache sharing across agents** ("KV cache is all you need", LMSYS) — GPU KV-cache as a shared,
  reusable state across requests/agents. Likely the strongest "GPU/VRAM-as-bus" mechanism to steal.
  *Marked speculation until read.*
- **GPU-memory / compute-in-memory as a shared bus** — using VRAM-resident structures (attention
  state, prompt cache, tensors) as the coordination layer. *Speculation until read.*
- **Merkle / verkle Patricia tries as memory buses** (Ethereum history, stateless clients) — the
  content-addressed structure we already emulate with `verkle_knot`. *Speculation until read.*
- **Memory-mapped / unified CPU–GPU memory** — a single address space as the bus. *Speculation.*

**Next action for grounding these:** re-run the external web/github research (was interrupted) and
route the findings through the frontier (already queued: `rib-bus-frontier-push-1` in
`memory/copilot/inbox.jsonl` → `memory/runs/rib_bus/frontier_synthesis.md`).

## 3. Concrete next wiring upgrades — "route almost everything through the bus"

Ranked by value/effort (deterministic, $0-first):
1. **Fold worker OUTPUTS back to the bus** — cheap workers currently auto-mount instructions from
   memory but don't fold their results back. Add a fold-on-complete so each render result becomes a
   knot + publish, closing the loop (frontier → bus → worker → bus → frontier).
2. **VRAM as the anchor clock/state** — extend `gpu_k8s` so VRAM/GPU state is published on every
   sense/cycle, not just on demand; agents read it as a live hardware-truth signal on the bus.
3. **Publish every RIB fold by default** — make `publish_rib` the default path in `rib_renderer`
   (already done) and add a cadence fold so the instruction layer never goes stale in memory.
4. **Auto-mount on worker spawn** — already done for `stateless_research`; extend to `swarm_worker`
   and `surrogate` so ALL cheap workers carry the domain RIB set by default.
5. **Bus-aware dedupe** — use the verkle content hash as the dedupe key for RIB instruction sets
   across domains (dedupe identical invariants globally, not per-domain).
6. **Frontier→worker fidelity loop** — after the frontier push lands, fold its refinements back as
   new RIBs on the bus so the swarm re-renders the improved instruction layer (the flywheel).

## Provenance
- This is OUR synthesis of grounded material (our own built modules + a verified external
  field-steal). Anything not directly verified is labeled SPECULATION. NOT a frontier-model claim.
- Deterministic + $0; the LLM/frontier validation is queued separately (honest provenance will be
  labeled on the frontier artifact when it lands).
