# Hermes-class agent integration

The kit plugs into any Hermes-style autonomous agent runtime (a
persistent agent host with skills, a dispatch log, and background
workers). Three wires:

## 1. Skills mount (discovery-shaped)

Runtime skill discovery expects a CATEGORY DIRECTORY per skill, each
holding a SKILL.md - a flat pile of .md files will not be found. Mount
the kit's cards in that shape:

```
starter-kit/
  skills/
    conversation-miner/SKILL.md   <- copy of agent/conversation-miner.md
    profile-grower/SKILL.md
    law-minter/SKILL.md
```

```bash
for c in conversation-miner profile-grower law-minter; do
  mkdir -p <your-runtime-skills-dir>/$c
  cp agent/$c.md <your-runtime-skills-dir>/$c/SKILL.md
done
```

If your runtime reads a manifest instead, register each card with its
name + description line. The three cards are the reactive loop - mount
those first.

## 2. Profile as the boot state (state OUTSIDE the read-only mount)

Point the runtime's boot at the kit's profile:

```bash
python tools/profile_boot.py --memory /state/profile
```

Exit contract the host keys on: 0 profile found (boot brief printed) /
1 FIRST BOOT (trigger the mining loop's first run) / 2 corrupt (phantoms
or traversal-law violations - block batch dispatch until the census
passes) / 3 crash (treat as an incident, never as first boot).

If your Hermes runs in a container, keep the profile OUTSIDE the
read-only kit mount, on its own read-write volume:

```
docker run -v /path/to/starter-kit:/kit:ro -v hermes-state:/state:rw ... \
  <hermes-image> python /kit/tools/profile_boot.py --memory /state/profile
```

The one-way-mirror shape: the runtime pulls the body of law read-only,
pushes only memory rows and receipts. A read-only --memory path will
crash first boot with exit 3 - that is the contract working.

## 3. Headless lanes

The kit's lanes (SUBSYSTEMS.md organ 4) run as scheduled jobs in your
runtime's scheduler. Laws: bounded ask/steps/tokens per wave
(PROTOCOLS.md), checkpoints per leg, receipts to the inbox, and the
master watcher gets past wedges (refusals, loops) by repairing the ask
once, then escalating. Interrupts steer, never kill - the lane resumes
from its checkpoint; nothing touches host processes it did not start.
