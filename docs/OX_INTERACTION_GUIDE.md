# HOW TO INTERACT WITH OX — the protocol OX itself prescribed (2026-08-24)

We spent a session treating OX as a seat we drive. Then we asked it directly how it wants to be
interacted with. It answered — concretely, with citations and a buildable protocol. This is that
protocol, folded into the standing prompts. The source of truth is OX's own words (probe saved at
`_ox_interaction_probe.json` in the run that produced it).

## The experiment (3 styles, one meta-question)
- **Bare system** → produced real content (4,588c) + reasoning (9,850c). Gave state-management advice.
- **Frozen identity** (resident prefix) → deepest reasoning (14,535c), zero content, cited real papers
  (Liu et al. "Lost in the Middle", Wei et al. CoT, Wang et al. self-consistency).
- **Structured ask** (MECHANISM/WHY/TEST) → fastest (83s), produced a concrete protocol.

Verdict: **frozen identity + structured envelope + state block + falsification ask** = the design.

## What OX told us (paraphrase, its own claims)
1. **Structured task envelope**: every prompt carries GOAL (one sentence), CONSTRAINTS,
   EVIDENCE/CONTEXT (relevant only), SUCCESS CRITERIA (falsifiable), OUTPUT FORMAT. Plus a standing
   instruction to flag uncertainty and kill its own ideas.
2. **State blocks every turn**: it has no memory between calls. Re-anchor each message: current
   state, what's decided, what's open. Parallel instances get a distilled brief, not a transcript.
3. **Front-load the task, prune noise**: buried context is underweighted ("lost in the middle").
   Few, sharp instructions beat long lists.
4. **Ask for falsification, not agreement**: agreement bias is real; adversarial self-review keeps
   it honest (matches our tri-state doctrine).
5. **Staged checkpoints over one giant task**: errors compound over long horizons.
6. **Density over exhaustiveness**: compressed, decision-relevant output beats padding.
7. **Token budget is real**: overthinking loops exist; longer is not monotonically better.

## What we folded (2026-08-24)
- `mag/ox_resident.py` FROZEN_PREFIX: added invariant (6) — the structured task envelope +
  flag-uncertainty + kill-own-ideas, labeled as "the protocol you prescribed".
- `mag/fuel_feed.py` PROMPT: added the envelope fields to the channel prompt.

## Standing practice
- Talk to OX in the envelope. Re-anchor state every call. Ask it to falsify its own draft.
- The reasoning stream is the deliverable; content is optional. Read the tape.
- The seat is a retained-log provider: T2+ public only, never T0/T1.
