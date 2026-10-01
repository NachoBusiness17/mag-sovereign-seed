# CONCEPTS — the machine, as ideas

> This is the discussion layer. Every concept below is explained in plain
> language (what it IS, why it exists) and mapped to where it lives in code, so
> we can talk about the architecture as ideas — not just as files.

**Why this exists:** the system's power comes from a few composable ideas.
When they're only in code, we can't discuss them, refactor them, or steer them
as concepts. This layer keeps them discussable. If a concept changes, update
it HERE first, then the code.

---

## The core stack (one line each)

| Concept | One-liner | Code home |
|---|---|---|
| **Riddler** | Send a problem to a model wearing a *disguise*, so the remote never sees the real thing — then decode the disguised answer back. | `mag/riddler.py`, `mag/riddler_transport.py`, `mag/surrogate.py` |
| **Memlang** | A binary *trigger language*: a 69-byte token (opcode + hash-anchor) that points at shared state instead of spelling the instruction out. | `mag/memlang.py` |
| **RIB** | The knowledge base — the "geometric maps" of everything the system understands/solved. | `memory/rib/` |
| **Weave** | The skill-recipe system — reusable patterns the agent *executes* instead of reinventing. | weave/skill ledger |
| **Verkle** | The memory substrate — content-addressed knots; filename = hash; nothing secretly erased. | `mag/verkle_knot.py`, `memory/biography/knots/` |
| **Flock** | N cheap agents fan out in parallel on K8s, each sampling independently, then converge on a consensus. | `mag/flock_steal.py`, `mag/flock_job.py` |
| **Ghost** | The reconciler — reads the RIB, speaks memlang, acts through weave, runs the flock, folds to knots. | `mag/ghost.py` |
| **Memweave** | The synthesized doctrine: memlang × RIB × weave. How ghost reads, steers, acts, folds as one. | `memory/rib/DOCTRINE_MEMWEAVE_20260810.md` |
| **Mindweave** | The applied idea: beat the local-GPU speed wall with structure + parallelism, not a bigger GPU. | `mag/flock_steal.py`, `mag/mindweave_eval.py` |

---

## The riddler protocol (deep dive — the concept we keep coming back to)

**What it is:** a way to ask a model a question WITHOUT the model knowing the
real question.

**Why:** our data has tiers. T0/T1 (operator-private) must never leave the
machine. But a remote model could help. The riddler lets us:
1. **Compile** the real problem into a *surrogate story* (a disguise) — same
   abstract structure, but dressed as a village/tower/whatever.
2. **Send** the disguised story to the remote model. It reasons "inside the
   story world." It never sees the territory.
3. **Decode** the story-domain answer back into territory terms, using a
   private map only we hold.
4. **Aggregate** answers across multiple disguised faces into a consensus.

**The cost (measured 2026-08-10):** the disguise is *deniable* and *local-first*,
but the story-answer vocabulary is **orthogonal to real correctness** on grounded
tasks. The flock converged on `plate`/`clean`/`cross` (story verbs) while the
real answer was `9` / `$0.54` / `Yes`. That's the **consensus illusion** — high
confidence, wrong meaning.

**The fix (in progress):** two channels in the decode —
- *surrogate-action* channel (story verbs, for open-ended/steering) 
- *raw-answer* channel (the model's actual final `ANSWER:` line, steered early
  like ghost plants a steer — for grounded/verifiable tasks)

**Code:** `mag/riddler.py` (compile), `mag/riddler_transport.py` (send),
`mag/surrogate.py` (decode + aggregate), `mag/flock_steal.py` (the flock using it).

---

## The memweave mindweave (the applied thesis)

**The idea:** a local small model can feel "fast enough" not by having a big GPU,
but by:
1. getting **structures, not prose** (memlang tokens that resolve to RIB context),
2. running **N cheap pods in parallel** (K8s) instead of one slow deep call,
3. **converging** on a consensus (semantic, invariant-aligned).

**Measured:** ~3.4× per-answer wall-clock vs a single deep call; semantic embed
separates related vs unrelated 2.5×. **But** the eval harness caught that the
flock's consensus is a *steering* signal, not a *verifiable answer*, on grounded
tasks.

**Where the boundary is (honest):** mindweave wins the 90% that is
structured/routing/parallel + keeps T0/T1 local. Frontier models (grok/deepseek)
stay for the 10% needing deep synthesis or verifiable answers. Do not overclaim.

---

## How to discuss these

- **Riddler** = "the disguise protocol" — deniable, local-first, but the disguise
  vocabulary ≠ correctness. Use for steering/sampling, not verification.
- **Memlang** = "the pointer language" — a token that points at shared memory
  instead of spelling the thought out.
- **Flock** = "the parallel swarm" — many cheap agents, not one expensive one.
- **Verkle** = "the chain of knots" — memory that can't be silently rewritten.
- **Ghost** = "the reconciler" — the one that weaves it all and folds it back.
- **Mindweave** = "structure + swarm beats bigger GPU" — the applied play.

*Maintained by the operator + agent. Keep this current — it's the shared
vocabulary.*
