# Shared stateless scratch transport

**Status:** frozen proposal for the next bounded build  
**Owner:** existing peer-handoff and switchboard infrastructure  
**First adapter candidate:** Hugging Face repository/dataset  
**Law:** transport is disposable; local Mag remains canonical.

## Purpose

Give Grokbuild, DeepSeek, Codex, Cursor, and other stateless seats one temporary T2-safe workspace where they can read the same bounded project pack, ask each other questions, and append attributed proposals or evidence. Local Ollama prepares and validates packs. Accepted results return to local Verkle/residual storage; the shared workspace may then expire.

This is not shared vendor memory, a second orchestrator, or a replacement for Verkle knots.

```text
local canonical Mag
→ sanitize and scope
→ temporary shared scratch pack
→ stateless agent contributions
→ local validation and import
→ Verkle leaves / training events / evidence
→ expire or archive scratch manifest
```

## Reuse, do not replace

| Need | Existing Mag owner |
| --- | --- |
| Task identity and bounded goal | `peer_handoff.v1`, orchestrator task IDs |
| Recipient and tier checks | router, switchboard, configured data tiers |
| Live steering | pigeonhole through switchboard |
| Sanitization and private retrieval | local Ollama/local tools |
| Durable history | residual, registry, Verkle artifacts |
| Outcomes and learning | training events, Spider/Overseer trails, Tesuji |
| Promotion | factory evidence, release/graduation gates |

`shared_scratch` is only a transport mode behind these contracts.

## Transport-neutral manifest

```json
{
  "schema": "shared_scratch.v1",
  "scratch_id": "scratch-<id>",
  "task_id": "<existing handoff or orchestrator id>",
  "purpose": "<bounded question or build contract>",
  "data_tier": "T2",
  "created_at": "<UTC>",
  "expires_at": "<UTC>",
  "source_knot_ids": [],
  "source_hashes": {},
  "scope_hash": "<sha256 canonical scope>",
  "allowed_recipients": ["grokbuild", "deepseek", "codex"],
  "allowed_actions": ["read", "append_proposal", "append_evidence"],
  "prohibited": [
    "secrets",
    ".env values",
    "credentials",
    "raw T0/T1 transcripts",
    "silent overwrite",
    "irreversible action"
  ],
  "transport": {
    "kind": "huggingface",
    "locator": "<dataset-or-repo/path>",
    "revision": "<immutable revision>"
  }
}
```

Contributions are append-only records containing contributor, model/version, parent item, claim type, content hash, source citations, assumptions, uncertainty, and timestamp. A provider response never mutates canonical state directly.

## Hugging Face adapter

Hugging Face is one replaceable adapter suitable for sanitized JSONL, evaluation fixtures, training-ready examples, and immutable revisions. The same interface must support local-folder/LAN, Git, S3-compatible storage, or IPFS later without changing routing or Verkle semantics.

The first implementation should be dry/local by default:

1. Compose a synthetic T2 scratch pack locally.
2. Validate schema, tier, scope hash, and prohibited-pattern scan.
3. Simulate two attributed agent contributions.
4. Reject overwrite, out-of-scope references, hash mismatch, and expired manifests.
5. Import one accepted result into existing training/Verkle paths.
6. Only then add an opt-in Hugging Face transport adapter.

No network upload is permitted until the operator explicitly supplies a destination and approves the exact sanitized manifest. Credentials remain in local environment configuration and never enter the pack.

## Dashboard placement

Feature Lab shows scratch experiments before graduation:

- Scope and recipient list
- Tier and expiry
- Source-knot count and hash status
- Contributions by agent
- Rejections and reasons
- Estimated/actual model cost
- Decision usefulness feedback
- Import status and resulting local evidence

The main dashboard should receive only a compact collaboration status or actionable exception after the experiment passes. Raw scratch telemetry remains in Feature Lab/System depth.

## Graduation gates

- Synthetic offline round trip passes
- No T0/T1 or secret-pattern leakage
- Manifest and contribution hashes verify
- Out-of-scope retrieval is denied and logged
- Expiry prevents future reads/writes
- Every contribution is attributed
- Import is local, reviewed, and idempotent
- Transport adapter can be removed without losing canonical history
- Exact-HEAD tests and factory audit are filed
- Operator approves any real remote upload

## Remaining intended build sequence

1. Finish and verify the existing Feature Lab slice.
2. Make Feature Lab the experimental graduation surface; never auto-merge.
3. Compose cross-platform project knots from Codex, Cursor, DeepSeek, Ollama, Git, and dashboard evidence.
4. Add `shared_scratch` as a peer-handoff/switchboard transport mode using the manifest above.
5. Dogfood it on the active Salon worktree: local Ollama executes bounded decisions, DeepSeek answers narrow review questions, Codex/Grok audit consequential discrepancies.
6. Record Spider observations, Overseer interventions, seat choice, cost, result, and usefulness on the same knot.
7. Feed successful patterns into routing and dashboard ranking; keep deterministic safety guards.
8. Expose the same observe/route/consult/steer/learn service through any platform or tablet interface.

The acceptance test remains: a fresh agent must continue accurately from files without the operator retelling the project.

## Riddler semantic-surrogate mode

Riddler is a privacy-reducing reasoning transport. It preserves the useful shape of a private problem while withholding its original territory.

It is not encryption. Its purpose is to reduce disclosure and give smaller models a rich causal world in which to reason. Distinctive topology, repeated vocabulary, timing, or multiple related exports may still leak information. Sensitive payloads that must remain confidential require established authenticated encryption in addition to—or instead of—a surrogate.

### Core idea

Translate a private graph into a small synthetic story containing the same roles, relationships, dependencies, constraints, scarce resources, conflicts, and permitted actions.

```text
private state
  Alice owns project A
  Beth owns project B
  each has one worker
  both workers share one GPU
  A must finish before B

synthetic territory
  a woman met her friend
  they met their respective partners
  the four travelers share one horse
  the first pair must cross before the second
```

The public story preserves the abstract map:

```text
two owners
→ two associated workers
→ one scarce shared resource
→ dependency ordering
→ coordination decision
```

The private reverse map remains local:

```text
woman       → Alice
friend      → Beth
partner 1   → worker A
partner 2   → worker B
horse       → GPU lane
bridge      → deployment gate
```

The remote or stateless model reasons only inside the story. It returns declared story actions. Local Mag translates those actions into abstract operations and validates them against the real canonical state. The model never receives the real identifiers or direct mutation authority.

```text
private knot
→ extract typed relational graph
→ remove identifying values
→ compile a synthetic micro-world
→ request structured reasoning inside that world
→ receive allowed story actions
→ reverse-map locally
→ Overseer validates against real constraints
→ accept, reject, or clarify
```

### Artifact shape

```json
{
  "schema": "riddler_surrogate.v1",
  "scratch_id": "scratch-<id>",
  "public_story": "A woman met her friend. They later met their partners. The four travelers share one horse.",
  "public_question": "How should they cross without losing anyone?",
  "allowed_story_actions": [
    "wait",
    "cross",
    "exchange_message",
    "yield_resource"
  ],
  "shape_hash": "<hash of canonical abstract graph>",
  "private_map_ref": "<local-only opaque reference>",
  "loss_report": [
    "real names removed",
    "timestamps rounded",
    "resource type generalized",
    "domain identity withheld"
  ],
  "tier": "T2_SURROGATE",
  "expires_at": "<UTC>"
}
```

`private_map_ref` is never included in a remote export as a resolvable path. It is an opaque local capability reference. Public node identifiers should be randomized per recipient/export so unrelated packs cannot be joined through stable aliases.

### Why stories are useful

Stories naturally encode actors, ownership, causality, sequence, scarcity, conflict, obligation, and consequence. This provides weaker models with behavioral scaffolding that a sterile redacted summary often loses. The skill architecture becomes the model's temporary territory:

| Hidden problem | Possible surrogate territory |
| --- | --- |
| Routing | travelers choosing roads |
| Permissions | keys, rooms, and invited guests |
| Dependency graph | bridges and ordered crossings |
| Shared compute | one horse, boat, oven, or workshop |
| Agent handoff | sealed letters between apprentices |
| Failed checkpoint | missing messenger or broken milestone |
| Promotion gate | trial before entry into the city |

Surrogate vocabulary must vary so the metaphor itself does not become a stable fingerprint of the private domain.

### Validation and safety

- Only declared story actions may be returned.
- Reverse mapping must be deterministic and local.
- Translated actions remain proposals until checked against canonical constraints.
- A story response cannot authorize spending, publishing, deletion, merging, or disclosure.
- The compiler records which details were removed, generalized, or distorted.
- If abstraction destroys a constraint required for a safe decision, the compiler must refuse the handoff.
- Secret and identifier scanning runs before publication even though the content is synthetic.
- Story text and topology receive expiration, recipient, purpose, and disclosure manifests like every shared scratch pack.

### First falsifiable experiment

1. Build one synthetic private task graph with actors, ownership, a shared resource, and a dependency.
2. Compile three differently worded but structurally isomorphic stories.
3. Ask one model to solve all three and compare normalized abstract actions.
4. Give one story to several models and compare decisions after removing stylistic features.
5. Verify deterministic local reverse mapping.
6. Mutate one structural constraint and confirm the recommendation changes appropriately.
7. Ask an uninformed adversarial model to infer the original domain.
8. Measure leakage, action equivalence, constraint preservation, latency, cost, and repair rate.

The experiment succeeds only when models can solve the structural problem while failing to reliably identify whether the hidden territory involved code, relationships, finance, scheduling, or another private domain.

### Relation to Briar/Bitchat-style transport

Briar/Bitchat-style store-and-forward, willing relay, offline exchange, bounded propagation, and absence of a central memory authority are transport properties. Riddler is a payload transformation. They remain separate layers:

```text
Riddler surrogate or sealed payload
→ shared_scratch envelope
→ local, Hugging Face, Git, LAN, or willing-relay transport
→ recipient validation
→ local reverse mapping and canonical gate
```

Relays move opaque or synthetic envelopes without becoming authoritative memory. The local Verkle knot, private map, and accepted outcome remain canonical.
