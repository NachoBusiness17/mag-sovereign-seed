# TRAJECTORY→RIB COMPILER — spec v0 (2026-08-28)

Three-witness deep-steal: memory/research_packs/20260827_traj_rib/ (A: grok
academic, B: grok practitioner, C: codex/OpenAI — independent families).
Status: SPEC, build gated on operator GO. Tri-state throughout.

## The confirmed gap

Witness C, independently: "I did not find a paper or product that fully
compiles a trajectory into a portable artifact with explicit acceptance
commands as first-class data." Rationale distillation stops at prose
(Distilling Step-by-Step, STaR, Orca); process reward models stop at scores
(PRM, ThinkPRM); trace vendors stop at dashboards (LangSmith/Arize).
**The executable contract is the [ONLY-US] edge.** [Supported — negative
result across surveyed field; strict impossibility Unproven.]

## Architecture (LLVM shape, per witness B)

```
frontends          →  IR            →  pass pipeline        →  backend
ghost tapes          canonical        canonicalize            rib v1 format
session tapes        trace graph      pair tool-results       (invariants /
agent traces         (spans +         redact secrets           one task /
hosted seat logs     artifacts)       slice to task            forbidden /
                                      verify-at-bytes          acceptance cmds)
```

## The steal map (bones → components)

1. **Front-end / compile pass** — thought-anchor extraction (Bogdan 2025,
   counterfactual resampling: "this sentence changes the answer
   distribution"). Cheap prefilter: TokenSkip/step-entropy; causal keep-set:
   anchors. Emit the sentence/action DAG as the rib's spine. [A#1]
   Unproven: whether agent traces (tools/files/seats) split planning-vs-
   compute the way math CoT does — first experiment.
2. **Execution split** — PAL/Program-of-Thoughts: the model decomposes, the
   RUNTIME executes. Our acceptance commands ARE the runtime. [A#2]
3. **Portability proof** — Self-Discover + Buffer of Thoughts: task-
   intrinsic structure transfers across model families with NO weight
   updates; BoT's meta-buffer = the rib library on FILE. [A#3]
4. **Metric gate** — DSPy `compile(teacher, student, metric)` + Bachmann
   potential + STaR outcome gate: **only verifier-passing traces compile**;
   a candidate rib must RAISE cheap-model success on held-out rollouts or
   it is not a rib. Mag's own accept commands are the oracle (the thing
   contest-math PRMs had to fake with gold answers). [A#4, B#2]
   The steering suite IS this oracle, already built.
5. **Rib format hardening** — Agent Skills SKILL.md shape: progressive
   disclosure, bundled scripts the small model INVOKES not narrates,
   allowed-tools as legal moves. Guardrail/evaluator as first-class IR
   types: forbidden = enforced rails (match→refuse), one Task with named
   artifacts + terminal status. [B#3, B#4, B#5]
6. **Library** — Trace2Skill: consolidate success AND failure trajectories;
   failures become standing refusals. Architecture-steal only; effect sizes
   Unproven (WIP paper). [A#5]

## What we refuse (explicit)

- Latent/thought-vector transfer (Coconut, CCoT, iCoT) — "un-files the path."
- SFT of student weights — not portable, not a file, no local trainer.
- Replay = call-the-model-again. Replay = run the accept commands, no LLM.
- Steering vectors as default channel — model-locked; the rib is decoder-
  agnostic.
- More prose into AGENTS.md — industry measured a cost/quality hit
  (witness B) the same night our battery measured the same tax on an 8B
  (−0.10 paired). Two independent measurements, one conclusion: prefixes
  are not programs.

## Build order (gated)

1. **Compile pass prototype**: thought-anchor extraction over ghost tapes
   (free lane bulk) → rib candidates for ONE deterministic task.
2. **Gate**: steering suite as pot-oracle — candidate rib must raise
   deepseek-chat / qwen3:8b pass rate on held-out tasks. Pre-register n
   and thresholds before first run (epoch-1 lesson).
3. **Library**: rib buffer on FILE, failures → standing refusals.
4. **Cross-family transfer test**: rib compiled from a GLM/z.ai trajectory,
   executed by deepseek + qwen bodies. Convergence floor (0.10 within /
   0.01 cross) is the baseline the rib must beat.

## Existing machinery (shelves)

- MAX_DISTILL = epoch-1 embryo (teacher trajectory → distilled arm D).
- RIB_TRAJECTORY_20260827 = hand-compiled prototype, dumb body executed it.
- steering_suite = the metric gate, verified.
- council + meld_claims = convergence instrumentation, floor measured.
