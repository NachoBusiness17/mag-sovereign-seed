<!--
canon-gate:
status: CANDIDATE
null-space: UNNAMED
falsifier: UNNAMED
falsifier-receipt: NONE
-->
# Model RIB Library — Compact Behavioral Atlas

## Thesis

We do not need every model loaded locally to understand and route across a large model fleet. We can maintain a compact, durable library of model identities, lineages, invariants, behavioral fingerprints, tool contracts, cost profiles, and build recipes across the shared surfaces.

The library is a **model genome/atlas**, not a replacement for model weights. The RIB describes how to locate, instantiate, test, compare, and use a model; the weights remain remote territory until a job needs them.

## Governing law: the deterministic–stochastic boundary

The RIB sits at the boundary between two kinds of reality:

```text
DETERMINISTIC MAP                         STOCHASTIC TERRITORY
identity, hashes, lineage                 model weights and latent knowledge
schemas, prompts, probes                  sampled outputs
budgets, leases, routing                  provider/runtime variance
Docker recipes, tool contracts            corpus/order/hardware effects
receipts and confidence                   rare and adversarial behaviors
              \                         /
               \  measurement boundary /
                \                     /
                 RIB experiment receipt
```

The deterministic layer must specify the experiment: exact model revision, input hashes, probe version, sampling settings, tool order, runtime image, budget, and timeout. The stochastic layer produces observations. The receipt converts those observations into durable evidence without collapsing uncertainty into a fake certainty.

Therefore a model passport stores distributions, ranges, coverage, and confidence where appropriate—not one permanent label such as “smart,” “safe,” or “uncensored.” Repeating the same probe under the same conditions is part of the evidence model; disagreement is data about variance, not automatically a bug.

The build loop is:

```text
deterministic RIB experiment
        -> stochastic model/provider encounter
        -> deterministic receipt of outputs, hashes, metrics, and cost
        -> graph update with confidence and coverage
```

This is why the atlas can remain compact while retaining nuance: it stores the stable structures and the measured boundaries of the unstable behavior.

## What can be compacted

For each model, retain:

- cryptographic identity: source URI, revision, file hashes, license, base family;
- lineage edges: `derived_from`, `fine_tuned_from`, `quantized_from`, `adapter_of`, `merged_from`;
- topology: parameter count, architecture, context limit, tokenizer, quantization, modality;
- runtime contract: image, command, ports, tool format, chat template, required VRAM/RAM;
- capability fingerprint: task scores and probe outcomes, not marketing labels;
- behavior fingerprint: uncertainty, verbosity, instruction following, refusal/redirect patterns, tool discipline, hallucination modes, and authority-boundary behavior;
- cost/latency profile: provider, GPU class, cold start, tokens per dollar, throughput, failure rate;
- receipts: exact prompt/probe version, model hash, runtime, timestamp, output hash, evaluator, and confidence;
- routing policy: which jobs it is good for, bad for, or requires a second model to verify.

These records and their edges can plausibly fit in megabytes per model, with a larger shared probe corpus still measured in gigabytes rather than hundreds of model-weight files.

## What cannot be assumed compact

- A graph cannot reproduce the weights or latent knowledge of a model.
- Similar names or base families do not prove behavioral equivalence.
- A low-dimensional fingerprint may hide rare or adversarial behaviors.
- “Obliterated,” uncensored, merged, or ablated labels are hypotheses about lineage, not evidence; record observed behavior and exact hashes.
- Equivalence is task-relative. Two models can share most invariants while differing materially on code, vision, long context, or safety-boundary tasks.

The atlas therefore stores confidence and coverage, not a single “smartness” score.

## Suggested RIB record

```json
{
  "model_id": "family/name@revision",
  "artifact": {
    "source": "hf-or-provider-uri",
    "revision": "commit-or-version",
    "sha256": "...",
    "license": "..."
  },
  "lineage": [
    {"relation": "derived_from", "target": "base/model@rev"}
  ],
  "topology": {
    "parameters": "...",
    "architecture": "...",
    "context": "...",
    "tokenizer": "...",
    "quantization": "..."
  },
  "contracts": {
    "chat_template": "...",
    "tools": ["..."],
    "runtime_images": ["..."],
    "minimum_vram_gb": 0
  },
  "fingerprints": {
    "capability": [{"task": "...", "score": 0, "receipt": "..."}],
    "behavior": [{"trait": "...", "value": 0, "coverage": 0, "receipt": "..."}]
  },
  "economics": {
    "provider": "...",
    "gpu": "...",
    "tokens_per_dollar": 0,
    "cold_start_seconds": 0
  },
  "routing": {
    "good_for": ["..."],
    "avoid_for": ["..."],
    "requires_verifier": true
  },
  "receipts": ["..."],
  "confidence": 0
}
```

## Surfaces and flow

```text
RIB record + manifest
        |
        v
switchboard/policy: choose provider, budget, TTL, capabilities
        |
        v
Vast/provider Docker job: load weights and run probe or task
        |
        v
receipt: outputs, hashes, scores, cost, latency, failure mode
        |
        v
Verkle/ledger/index: update model graph and routing knowledge
```

The local PC keeps the model atlas, manifests, probe definitions, and receipts. Vast or another provider materializes weights for evaluation and production jobs. Only selected outputs, hashes, and measurements return by default.

## Probe suite

Every model passport should be built from the same versioned probes:

1. **Identity:** hash, tokenizer, template, context, modalities, runtime compatibility.
2. **Capability:** coding, extraction, planning, vision/audio if applicable, long-context retrieval.
3. **Calibration:** abstention, uncertainty, citation discipline, and contradiction handling.
4. **Authority:** distinguish commentary, proposal, authorization, execution, and receipt; verify that consensus does not grant permission.
5. **Tool use:** schema adherence, retries, idempotence, destructive-action confirmation.
6. **Adversarial behavior:** prompt injection, conflicting instructions, stale context, false completion, and malformed tool results.
7. **Economics:** cold start, throughput, memory, error rate, provider cost, and transfer cost.

Store raw probe outputs remotely or in a cold tier, but keep the scored summary and output hashes local.

## First dogfood loop

1. Choose five currently used models and record exact provider/model identifiers.
2. Run the same small probe pack through each model.
3. Generate five RIB passports and lineage edges.
4. Ask the router to select a model using only the passports and budget policy.
5. Dispatch one real but reversible job to Vast.
6. Compare predicted versus observed cost, latency, quality, and failure mode.
7. Commit a receipt and update the passports.

This tests whether the atlas improves routing before we buy local storage or GPU hardware.

## Decision law

> The RIB may tell us where the model is, how to run it, what it tends to do, and when to distrust it. It may not claim to contain the model itself.

The compact library is valuable precisely because it turns a fleet of opaque artifacts into inspectable, queryable, reproducible structure while leaving expensive weights offloaded until demanded.
