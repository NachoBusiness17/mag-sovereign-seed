# Cross-agent Verkle handoff

**Status:** governing handoff contract  
**Purpose:** let Codex, Cursor, Grokbuild, DeepSeek, and local Ollama reconstruct and continue Mag from files rather than private chat memory.

## Principle

The durable intelligence belongs to the project. Model platforms are replaceable readers, workers, critics, and teachers.

Mag retains the complete useful history locally: operator intent and corrections, agent contributions, decisions, disagreements, prompts, tool actions, Git changes, tests, failures, costs, lessons, and unresolved work. Raw transcripts remain local source evidence. A Verkle knot is the attributed, provenance-linked artifact that makes this history portable without forcing every model to ingest every transcript.

Never export secrets, `.env` values, credentials, tokens, private certificates, or material prohibited by the configured data tier.

## Source-to-pack flow

```text
local source archive
  (Codex · Cursor · DeepSeek · Ollama · Git · dashboard · trails)
        ↓
source leaves with hashes and attribution
        ↓
cross-agent project knot
        ↓
privacy + relevance + authority filter
        ├─ local Ollama pack: locally authorized T0/T1 context
        └─ remote pack: sanitized T2 context for Grokbuild/DeepSeek/etc.
        ↓
response, actions, evidence, and outcome attach to the same knot
```

The knot is not a prose summary pretending to be the source. It contains compact interpretation plus paths, identifiers, hashes, and evidence needed to inspect the underlying record.

For temporary cross-platform collaboration, export a scoped copy through the provider-neutral `shared_scratch` transport defined in `docs/ref/SHARED_STATELESS_SCRATCH.md`. Hugging Face may host one adapter, but it is only a disposable table; the local knot remains canonical.

## What a project knot preserves

- Operator requests, corrections, priorities, and approval boundaries
- Project thesis, constitution, roadmap, current phase, and vocabulary
- Each model's contributions with attribution
- Material prompts and handoff envelopes
- Decisions, rejected alternatives, disagreements, and changes of mind
- Branches, commits, diffs, worktrees, ownership, and merge targets
- Tests, audit receipts, failures, retries, and graduation evidence
- Router choices, capability observations, latency, cost, and usefulness
- Spider observations, Overseer interventions, and Tesuji moves
- Open loops, blockers, active owner, and exact next action
- A manifest of what context was disclosed to each receiving model

## Privacy views

| View | Recipient | Allowed material |
| --- | --- | --- |
| Local custody | Local Ollama and local tools | T0/T1 only when authorized; secrets remain excluded from prompts and logs |
| Sanitized project | Remote model seats | T2 facts, code, public docs, bounded excerpts, hashes, decisions, and evidence |
| Irreversible action | Any seat | Recommendation only; T3 action requires human approval |

Revocation prevents future authorized retrieval but cannot retract information already disclosed. Every pack records recipient, tier, sources, purpose, and creation time.

## How a receiving agent reads Mag

1. `docs/FRAMEWORK_LOAD.md`
2. `docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md`
3. This file
4. `memory/briefs/latest.md`, `memory/attention.md`, and `queue/todo.md`
5. Latest relevant `queue/handoff/` files
6. Current Git branch, worktrees, status, upstream, and recent commits
7. Referenced Verkle/residual leaves and test evidence
8. Source transcripts only when a claim, disagreement, or missing detail requires them

Interpretation rules:

- Files and verified evidence outrank chat recollection.
- A summary is interpretation; follow source links for proof.
- Prefer constitutional law, explicit operator corrections, exact-HEAD tests, and recorded graduation gates.
- Preserve model disagreement rather than averaging it away.
- Attribute ideas and actions to their contributing seats.
- Distinguish proposed, implemented, tested, graduated, and merged.
- Report unavailable platform history honestly.
- Never create a second router, scheduler, memory store, or transcript database.

## Operating loop

```text
observe work and evidence
→ Spider detects stalls, repetition, missing proof, and waste
→ Overseer chooses continue, steer, consult, retry, stop, or escalate
→ Router selects the cheapest capable seat
→ switchboard/pigeonhole delivers bounded context at a checkpoint
→ worker acts in an isolated branch/worktree
→ deterministic tests and audit verify the result
→ outcome and contribution become Verkle leaves
→ meta-analysis updates routing and display priority
→ exact-HEAD evidence enters graduation review
```

The dashboard is a viewport over this loop. Experimental surfaces belong in Feature Lab and graduate into the semantic main dashboard only after branch-bound tests and audit evidence pass. The dashboard never silently merges.

## Current truth and acceptance test

Mag already has residuals, registry entries, Verkle leaves, context packs, peer handoffs, orchestrator records, pigeonhole mailboxes, switchboard steering, Spider signals, Overseer logic, training events, Git/worktree evidence, and release gates. Complete automatic harvesting and reconciliation of every platform's full history is not yet proven.

A fresh agent with no prior chat must be able to determine what Mag is, what is implemented, who owns active work, which evidence is green or missing, what remains local, which model should act next, and the exact next bounded action. If the operator must retell the project, the handoff system has failed.
