> **Deprecation banner:** cursor lane lapsed 2026-08-27 — current seats are Codex, Grok x2, DeepSeek. See `docs/ref/ZAI_API_EXPERT_REFERENCE.md` for current lanes.

# Behavioral Router Interface

**Status:** Desk migration contract · 2026-08-06

## Product job

Desk is the operator surface for the whole Mag program. The operator supplies an outcome once. Mag turns it into a durable contract, chooses the cheapest capable seat, executes reversible work, verifies artifacts, escalates only when needed, and returns decisions or exceptions—not a stream of permission requests.

The earlier three-lane Desk was a calibration rig for proving Local → DeepSeek handoffs. Its controls remain useful as instrumentation, but they are no longer the primary interaction.

## Default operator surface

1. **Direction** — one outcome, optional constraints, optional definition of done.
2. **Route goal** — commits direction, enables continuity, and advances until done, blocked, or gated.
3. **Working contract** — editable disk-backed state shared across seats and tools.
4. **Activity** — Local, DeepSeek, Codex, Grok x2, workers, and tools report concise deltas.
5. **Exception inbox** — only genuine decisions, unavailable credentials, irreversible actions, spending, publishing, or unresolved ambiguity.

Everything else belongs under **Lab & maintenance** or **System details**.

## Behavioral routing contract

```text
operator direction
  → decision framework: intent, precedent, behavioral lessons, risk
  → router: depth, seat, provider, cost, executable capability
  → worker: act through tools and files
  → verifier: tests, diff, evidence, budget
  → continue automatically when reversible and in scope
  → escalate capability when stuck; do not merely spend more tokens
  → ask operator only at an exception boundary
  → file outcome, behavioral episode, and continuity leaf
```

## Approval law

The operator approves the goal and its declared boundary, not each implementation step.

May continue automatically:

- reading, searching, planning, and diagnostics;
- scoped edits inside the chosen workspace;
- tests, formatting, local builds, and reversible retries;
- switching between approved local/remote coding seats within privacy and budget policy;
- filing trails, reports, diffs, and behavioral events.

Must stop for the operator:

- secrets or credentials not already authorized;
- deletion, destructive reset, irreversible migration, or data loss risk;
- publishing, sending messages, spending money, merging/releasing, or external commitments;
- changing constitution, promotion policy, or autonomy boundary;
- ambiguity where plausible choices materially change the requested outcome.

Host applications such as Codex, Windows, and browsers may enforce their own security prompts. Mag cannot safely impersonate the operator for those prompts. The integration target is persistent, narrowly scoped permissions and agent-owned sandbox execution—not universal “always approve” on the host.

## Active contract shape

The working file should remain small:

```markdown
# Goal

# Constraints

# Definition of done

# Current route

# Evidence

# Exceptions
```

Calibration dialogue and lane transcripts should be archived as evidence, not accumulate in the active contract. Agents report only state-changing deltas into the contract.

## Migration sequence

1. Simplify the surface without deleting prototype instrumentation. **Done.**
2. Archive the existing calibration transcript and seed the compact active contract. Requires an explicit migration action because the current file may contain operator-owned notes.
3. Connect Route goal to the program decision framework and executable background coordinator, not only the dialogue conductor. **Done for routed seat launch; factory-specific lifecycle remains a later specialization.**
4. Introduce an exception queue with risk reason, requested authority, proposed action, reversibility, and evidence.
5. Add route visualization: current seat, why it was chosen, cost, capability, next checkpoint, and fallback.
6. Learn from operator interventions so repeated safe approvals become scoped policy while irreversible boundaries remain fixed.
