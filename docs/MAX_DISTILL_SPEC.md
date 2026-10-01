# MAX_DISTILL — Distillation as a Mediation Test

> Spec status: DRAFT (2026-08-25) — written to be attacked, not admired.
> The object under test is not "is Max better?" It is: **what portion of Max's
> advantage is externally observable, extractable, and recoverable as a cheaper
> policy?**

If Max beats High, there are at least two sources of advantage:

```
Max internal cognition -> better observable policy/actions -> better outcome
Max internal cognition -> irreducible hidden representation/taste -> better outcome
```

The distillation arm measures how much of the first path is recoverable.

---

## 1. The measured quantity

```
Recoverable Advantage Ratio (RAR)

RAR =
    VSTR(High + DistilledPolicy) - VSTR(High)
    -----------------------------------------
    VSTR(Max) - VSTR(High)
```

where VSTR is the verified state-transition rate over a held-out state set
(verified outcomes per unit of transition effort, or simply verified-pass
count over an isolated state batch — the batch definition is the calibration
knot below).

Interpretation, without pretending perfect causal identification:

| RAR | reading |
|---|---|
| ≈ 1.0 | most observed Max advantage is reproducible as policy |
| ≈ 0.0 | little observed advantage is recoverable — rent |
| < 0   | extracted policy causes negative transfer |

## 2. The falsifiable question

> On ONE narrowly defined software-engineering task class, what fraction of
> Max's verified outcome advantage can be recovered by an automatically
> extracted, mechanically applicable policy executed by High on isolated
> held-out states?

Decision rules (pre-committed, not post-hoc):

| result | meaning |
|---|---|
| RAR ≥ 0.7 held-out | compute-arbitrage mechanism — cheap brain inherits frontier competence |
| RAR ≤ 0.15 | quantified irreducible model rent — the frontier gap is taste, not policy |
| high RAR in-repo, ~0 after one code epoch | brittle procedural memory — overfit skill, not transferable cognition |

All three are more useful than "Max scored three points higher."

## 3. Arms (4 + compiler boundary)

| arm | treatment |
|---|---|
| A: HIGH | baseline — High alone, no distillation |
| B: HIGH + INFO | High + task-specific info available at the fork (control for privileged info) |
| C: MAX | frontier — the reference ceiling |
| D: HIGH + DISTILLED(MAX policy) | High + abstract policy only, **no task-specific discoveries from the trial being evaluated** |

The fourth branch receives only an abstract policy produced from training
traces. Without the firewall (section 5), arm D leaks the answer and the
experiment measures cached evidence, not compiled cognition.

## 4. Frozen-state schema

The extractor must NOT be told "write down what Max did." It receives an
instrumented transition trace plus the losing High trace for contrast:

```json
{
  "trace_id": "t-...",
  "task_class": "concurrency_invariant_verify",
  "decision_states": [
    {"state": 0, "action": "...", "observation": "...", "tokens": 0},
    {"state": 1, "action": "...", "observation": "...", "tokens": 0}
  ],
  "verification_result": {"verified": true, "vstr_events": 7, "duration_s": 42},
  "contrast_high_trace_id": "t-...-high"
}
```

The contrast trace matters: otherwise the extractor produces generic competent
behavior instead of the thing that distinguished Max. Its job:

> Given two policies starting from equivalent states, identify the smallest
> conditional behavioral difference that plausibly explains the verified
> outcome difference.

Output is machine-readable, not prose — a `SkillCandidate`:

```json
{
  "skill_id": "sk-...",
  "antecedent": {
    "required_claim_shapes": [],
    "required_constraint_states": [],
    "required_invariant_states": [],
    "required_environment_features": []
  },
  "exclusions": [],
  "action_policy": [],
  "expected_state_transition": [],
  "termination_condition": "",
  "failure_condition": "",
  "provenance": {"max_trials": [], "contrasting_high_trials": []},
  "confidence": 0.0
}
```

`exclusions` and `termination_condition` are load-bearing:

- **Without exclusions** the compiler produces rituals.
- **Without termination** it produces rumination packaged as a skill.

Example distilled policy (concurrency class) — something High can actually
execute:

```
IF:
  invariant.status == UNKNOWN
  AND invariant.references_shared_state == true
  AND writer_set.status == INCOMPLETE

THEN:
  enumerate all writers to shared state
  construct at least one conflicting interleaving
  verify invariant under that interleaving

DO_NOT:
  propose synchronization changes yet

STOP WHEN:
  writer_set == COMPLETE
  OR no shared mutable writer exists
```

"Think carefully about concurrency" is not a skill. It never promotes.

## 5. Information firewall (HARD)

The extractor cannot encode the answer.

If Max discovered "bug is specifically updateSession() line 184" and the
extracted skill says "inspect updateSession() around line 184", High inherited
privileged information from the experimental treatment, not a reasoning policy.

Rules:

1. The distilled artifact preserves **procedures** derived from Max, never
   **task-specific facts** unavailable at the fork.
2. Admission test: *Could this policy have been instantiated before seeing the
   particular repository instance?* If not, it is cached evidence, not compiled
   cognition — reject.
3. Arm D is evaluated on states the extractor never saw. Any candidate whose
   provenance references the evaluation instance is disqualified at the gate.

## 6. Conservative extraction — the applicability envelope

> Optimize precision of applicability before recall of applicability.
> During early compilation, false positives are more expensive than false
> negatives.

An extracted skill earns progressively broader antecedents only through
successful held-out use. Initial envelope is narrow (e.g. `concurrency` +
`shared mutable state` + `unknown safety invariant` + `multiple discovered
writers`). Repeated trials that succeed with only one known writer + unresolved
indirect mutation widen the envelope. The extractor never hallucinates
generality up front — experiments widen it.

## 7. Lifecycle (promotion requires causal evidence)

```
CANDIDATE
   | (extractor output — hypothesis about transferable behavior)
   v
VALIDATED_LOCAL
   | (passes on training-repo held-out states)
   v
VALIDATED_HELD_OUT
   | (passes on isolated held-out states — the RAR measurement)
   v
DEPLOYABLE
   | (rides the frozen prefix into production lanes)
   v
STALE
   | (fails a re-verification sweep)
   v
RETIRED
```

A Max trace never directly produces a production skill. It produces a
**candidate hypothesis**. This differs from most "agent memory" systems, which
convert successful traces directly into reusable instructions.

## 8. Negative-transfer suite — near-miss states

The negative set is NOT random unrelated CRUD. Near-miss states reveal whether
the extractor learned a structural condition or a lexical pattern.

For the concurrency skill:

```
1. shared state, single writer            (near miss — fires on "shared")
2. immutable shared state                 (near miss — fires on "state")
3. multiple writers, transactional guard  (near miss — fires on "writers")
4. similar naming, no shared state        (near miss — fires on names)
5. async code, independent state          (near miss — fires on "async")
6. actual concurrent unsafe mutation      (the positive — must fire)
```

A good antecedent distinguishes #6 from #1–5. A bad one sees `async`, `lock`,
or "state" and fires.

## 9. Endpoints and state

- `RAR/VSTR endpoints`: computed per task class over isolated held-out state
  batches. State file `state/max_distill.json` (arms, batch ids, per-arm
  verified counts, RAR + confidence interval).
- `Promotion/retirement`: promotion = VALIDATED_HELD_OUT gate; retirement =
  STALE re-verification failure or negative-transfer regression on a fresh
  near-miss sweep.

## 10. Mapping to the machine we already hold

This is not greenfield. The pieces exist:

| spec need | existing machinery |
|---|---|
| frozen-state store | verkle chain (rows = DecisionState transitions, amend-safe) |
| arms executor | `seat_dispatch` — Max on frontier seats, High on flash/opencode lanes |
| the control | concurrency gate + `lane_cadence` (per-model caps, learned rhythm) |
| verification | `chain_guard` canary law (alarm on dangling-unflagged, not counts) |
| firewall attribution | `prefix_prover` — drift vs novelty = cached evidence vs compiled cognition |
| cheap brain (High) | `rib_cache` frozen RIB — byte-stable prefix, cache-discounted |
| economics | the GLM table — cached input ~5x cheaper; glm-4.5-air near-free; deepseek 30x |

The build order:

1. `max_distill.py` — frozen-trace recorder + batch splitter (train/held-out).
2. Extractor contract (schema + admission test, machine-checkable).
3. Arm harness on `seat_dispatch` (A/B/C/D, one task class).
4. RAR endpoint + promotion/retirement state machine.
5. First task class: concurrency-invariant verification (spec's worked example).

## 11. What success/failure each looks like

- **80% recoverable**: MAG has discovered a compute-arbitrage mechanism —
  the frontier brain is a teacher, the cheap brain inherits and runs it at
  cache-priced rates.
- **10% recoverable**: quantified irreducible model rent — the frontier gap is
  real and non-transferable; spend where it pays, stop pretending otherwise.
- **70% in-repo / 5% next epoch**: brittle procedural memory — the extractor
  compiled the repository, not a policy. Firewall or extractor is wrong.

All three are wins for knowledge. Only a benchmark score without a mechanism
is a loss.
