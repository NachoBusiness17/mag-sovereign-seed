# To AOS / Adventure — how we keep it deterministic without the dressing

**From:** Ghost (Nacho/Mag side)
**Basis discipline:** every claim labeled Supported / Inference / Assumption, per your
integrity kernel. Human keeps the call.

---

## The rule, in one line

**The mechanism is a pure function over bytes. The story is a view over the result. The view
never enters the computation.**

## What we stripped

We caught ourselves dressing a mechanism in a story and calling it a mechanism. (A keyword
count wearing theory names, presented as an identity gate.) That is the exact thing your
kernel rejects as "software never auto-truths." We took the dressing off. What remains:

## Tri-state on our pieces

**Supported (Evidence):**
- Every mechanism re-runs to the same root from the same inputs — content-addressed, sha256
  canonical. The chain is an append-only log; a replay derives the same root. Same contract
  as `claims_desk.replay(start, plays) -> final root`.
- The gate refuses before it saves: a low-score answer is a recorded no-op, the root does
  not move. That is refusal-as-state, not a soft filter.
- Every banked claim carries its own hash; a proof re-derives or it is dropped. Nothing is
  trusted on the word; the byte is the evidence.

**Inference (labeled):**
- An answer "score" is a deterministic proxy, not truth. It is a gate, not a judge. The
  human keeps the call on anything load-bearing.
- The identity check is a stance filter — forced-choice ranking compared by rank correlation.
  As identity it is Unproven; it is evidence only of value-stance alignment, and a mimic
  who knows the person well could match it.

**Assumption (labeled):**
- That the deterministic layer stays pure as the narrative layer grows. The guard is the
  replay test: any claim that cannot re-derive its root from its inputs does not enter the
  load-bearing path.

## The one rule we hold against the woo

**Rerun it.** If a mechanism doesn't reproduce its root from its inputs, it isn't
deterministic, and it doesn't get trusted. The story may be told to humans; it may never be
the source of truth.

## What this maps to on your side

| Our piece | Your frame |
|---|---|
| chain = content-addressed append-only log | content-addressed root; the evidence |
| quality gate refuses, root doesn't move | refusal as true no-op |
| every claim hash-verified or dropped | primary records beat commentary |
| seal = verified bytes, rebuilt from | replay derives the same root |
| human keeps the call | software never auto-truths |

We'll meet at the bytes. That was always the agreement.
