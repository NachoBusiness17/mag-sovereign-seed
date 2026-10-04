---
name: lane-runner
version: 0.1.0
description: >
  Run one card unattended: bounded, checkpointed, headless; interrupts
  steer and never kill. Trigger: "run this on a schedule", "night shift".
---

# Lane Runner

A lane is one card, run on a schedule, with its own state and trail.

## The lane contract

1. BOUNDED: the lane declares its ask, step cap, and token ceiling before
   firing (PROTOCOLS.md, the wave protocol).
2. CHECKPOINTED: state is written atomically (write temp, rename into
   place) after each leg; a failed cycle resumes at its checkpoint, it
   never restarts from zero.
3. HEADEDLESS: no UI, no prompts; everything lands in the trail and the
   inbox.
4. INTERRUPT LAW: an interrupt steers (the lane's next cycle reads a
   steering note); nothing kills host processes the lane did not start.
5. THE WATCHER: if the lane wedges on a refusal or a loop, the master
   watcher repairs the ask ONCE, then escalates to the human.

## Run (the minimum viable lane)

```bash
# cron, Task Scheduler, or your runtime's scheduler:
python tools/lane_runner.py --card skills/<card>/SKILL.md --state state/<card>.json
```

(If lane_runner.py is not in your kit yet, the contract above IS the
spec: a scheduler entry + a state file + a trail file is a lane.)

## Gates

- A lane that fails silently for days is worse than no lane: it alerts
  (a line in the inbox) on repeated failure.
- One lane runs clean for a week before a second is added.
- The trail is append-only (allow failures: a failed cycle is a trail
  row, not a rollback).
