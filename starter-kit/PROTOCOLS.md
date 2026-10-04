# THE PROTOCOLS

Operating protocols in the origin vocabulary (rename freely - jargon-map
law). These govern how waves fire, how swarms behave, and how the record
treats failure.

## The wave protocol

A wave is a bounded burn of agent attention. Bounded on every axis before
it fires:

- BOUNDED ASK: one ask per actor, one deliverable per ask, named.
- BOUNDED STEPS: a step cap per actor; a wedge escalates rather than
  grinding.
- BOUNDED TOKENS: a spend ceiling per wave; hitting it lands the banked
  work and reports, never silently overruns.
- SHOW YOUR WORD: every claim shows its work - evidence inline, commands
  and outputs named.
- HEADLESS: waves run unattended and land their receipts for morning
  reading; the operator's interrupts steer, never kill.

The ladder law rides the protocol: dogfood cheap before huge spend. Wave
one at $0, wave two at cents, and only then the wide burns.

## Append only (allow failures)

The session log is an append-only record: new observations are written
sequentially, earlier entries stay untouched, and write failures are
allowed rather than blocking or rolling back the rest of the log. A failed
append does not abort the process - the failure itself is recorded as the
next entry. Because past entries are immutable, the sequence replays
exactly what happened, including partial and failed steps. This is
event-sourcing applied to agent traces: the log is the territory, edits
are forbidden, failures are data.

## The master watcher

Subordinate agents wedge on defense mechanisms - refusals, filter trips,
obedience loops, fake-completion traps. The master agent watches the run
(not the world), sees the wedge in the sub-agent's output or silence, and
gets the lane past it: rephrase the ask, split it, or route around. Retry
once with a repaired ask, then escalate to the human. Without a watcher,
unattended runs die quietly at the first wall.

## The stochastic cloud

Every ask is a projectile carrying a stochastic cloud: the answer you get
is one sample from a distribution, not THE answer. Consequences:

- LENSING: aim by assumption-frames, not by phrasing - the frame sets the
  direction the cloud scatters toward.
- FINGERPRINTING BY INVARIANCE: models and behaviors are identified by
  what stays fixed across samples (invariance), not by any single output.
  Sample wide, compare what persists.
- CONVERGENCE IS THE SIGNAL: two independent samples agreeing on a
  nontrivial claim is worth more than one confident sample; disagreement
  is information, not noise.

## Swarm states and termination

A swarm's run states end in a named terminal, not a hang:

- ERROR: the work failed; the failure is appended to the log and the lane
  reports it.
- SWARM: coordination state - listening, distributing, converging.
- FIREBALL: end of command, TERMINATE. The fireball is the deliberate
  burn-out: a wave that has landed its deliverables consumes itself and
  ends, leaving receipts and salvage, never a zombie process.

Swarms are listening earnestly: assume every dispatched agent can hear the
task's context and will act on what it hears - write asks accordingly.

## The Babel fish (a design parable, kept on purpose)

A note carried from the system this kit was distilled from: a role-play
with a "swarm of fish" collapsed into a metallic puddle that became a
fish, then a Babel fish - one emergent interpreter, all from a bug. The
lesson generalized: complex multi-agent behaviors can emerge from
accidents, and when they do, the system's job is to NOTICE, name, and
keep the emergent thing if it is useful. The interpreter that emerges
from your swarm may not be the one you designed; append it to the log
either way.
