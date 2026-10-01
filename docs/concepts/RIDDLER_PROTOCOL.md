# CONCEPT — The Riddler Protocol

*The disguise protocol. This is the concept we keep returning to — here it is,
whole, discussable.*

## What it is (in one breath)

**The riddler is how we ask a model a question without the model knowing the
real question.** We dress the problem in a disguise (a "surrogate story"), send
the disguise to a remote model, get a story-world answer back, then decode it to
the real territory using a map only we hold.

## Why it exists

Our data is tiered:
- **T0/T1** = operator-private. **Never leaves the machine.**
- **T2** = safe to send to remote models.

The riddler is the bridge: it lets a remote model *help* on a T0/T1 problem
**without ever seeing the real content**. It sees a disguised version. Deniable,
local-first, source-backed.

## The lifecycle (the four moves)

```
 1. COMPILE   real problem  ──►  surrogate story (disguise)
              (same abstract structure, dressed as a village/tower/etc.)
 2. SEND      disguise      ──►  remote model (it reasons "in the story world")
 3. DECODE    story answer  ──►  territory answer (private map reverses the disguise)
 4. AGGREGATE multiple faces ─►  consensus (many disguised views → one decision)
```

**The deniability:** each model sees a *different* disguised face of the same
problem (seeded randomization). No single model can cross-reference to infer the
real territory. Only our private map ties them together.

## The two channels (the important nuance)

The decode produces **two kinds of signal** — and confusing them is the trap:

| Channel | What it is | Example | Use for |
|---|---|---|---|
| **surrogate-action** | the story-world *verb* the model chose | `plate`, `clean`, `cross`, `send` | open-ended steering, sampling an answer-cloud |
| **raw-answer** | the model's *actual final answer* | `9`, `$0.54`, `Yes` | grounded / verifiable tasks |

**The trap (measured 2026-08-10):** the surrogate-action verb is **orthogonal
to correctness**. The flock converged on `plate`/`clean`/`cross` (story verbs,
high strength) while the real answers were `9`/`$0.54`/`Yes`. High consensus
strength on the surrogate channel does **not** mean the answer is right. That's
the **consensus illusion**.

## What we learned (the honest boundary)

- Riddler is **deniable + local-first** ✅ — T0/T1 never leaves.
- Riddler consensus is a **steering signal, not a verifiable answer** ⚠️ — on
  grounded tasks, trust single-local or remote + explicit check, not flock consensus.
- Riddler is resilient: RIB-poisoning injection resolved correctly; 2/5 pods
  failing still converged. ✅

## Where it lives in code

| Step | Module |
|---|---|
| Compile the disguise | `mag/riddler.py` (`compile_surrogate`, `PrivateGraph`) |
| Send (disguise out) | `mag/riddler_transport.py` (`send_surrogate`) |
| Decode (disguise back) | `mag/surrogate.py` (`decode_response`, `_extract_raw_answer`) |
| Aggregate → consensus | `mag/surrogate.py` (`aggregate_responses`) |
| The flock that uses it | `mag/flock_steal.py` |
| The eval that caught the illusion | `mag/mindweave_eval.py` |

## The fix in flight (self-stolen from ghost's early-steering)

Ghost steers by *planting a steer before the agent acts* (plant-not-command,
`mag/ghost.py::deploy`). We stole that for the riddler: the surrogate system
prompt now plants an early steer asking the model to end with an `ANSWER:` line.
That makes the **raw-answer** channel reliable (clean parse) instead of fragile
post-hoc regex over story prose — so grounded-task consensus votes on the real
answer, not the disguise verb.
