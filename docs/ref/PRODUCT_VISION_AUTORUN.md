# Product vision - the autorun decision framework (2026-08-03)

**The point, stated once:** the product is not a dataset, not a mirror, not a chat app.
It is a **decision framework that autoruns the agent - including its coding** - so the
agent acts as your **proxy** and builds the whole thing itself.

**Who it is for:** people who want to own their digital footprint (nothing leaves the
machine; data tiers T0-T3 are law, not preference) and have an agent be their proxy -
OpenClaw-like, but for footprint owners instead of convenience renters.

**One line:** *A decision framework that autoruns your agent and its coding - your agent
is your proxy, your footprint stays yours.*

## Architecture (the loop, first version)
1. **Decide** - Governor scores candidate work from real sources: queue, agent_state next
   moves, dig leaves, boot manifest. value / (1 + cost); blocked skips.
2. **Execute** - run the task: code edits, docs, pytest. No human in the loop.
3. **Verify** - prove it: exit codes, tests, dry-run correctness.
4. **Record** - append the cycle to the trail; the trail IS the audit.
5. **Loop** - repeat until no unblocked work or an operator gate fires.

**Gates (the only reasons to pause):**
- G1 law (constitution, data tiers, residual DNA) - never violate, never route around
- G2 secrets (.env, tokens, credentials) - never read, never echo
- G3 irreversible (archive drops, deletes, publishes) - operator only

Everything else autoruns. That is the product.

**Full v2 plan:** `docs/ref/MAG_v2_PLAN.md` — phases, acceptance criteria, merge path (#8–#10).

## Where the seed mirror sits
The X archive / mirror_train rows are ONE aspect: one household's soil - the demo that
proves the loop on real data. They are not the product, and they never block the framework
from running. When the loop finds no unblocked work, it says so and waits - it does not
fabricate.
