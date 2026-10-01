# MAG platform-agnostic operating protocol

Every operator instruction enters the same `mag_intent.v1` envelope. The persistent personal interface is the project-aware router and learner. Codex, dashboard, tablet, CLI, Cursor, Grok, API, and automation are ingress surfaces—not separate workflows.

```text
intent from any surface
  -> personal router recalls projects, interactions, failures, wins, prompts, and skills
  -> it classifies the task and tests available model speed/capability
  -> smallest model that passes the task eval becomes the working seat
  -> frontier dungeon master is summoned when novelty, risk, or failure demands it
  -> dungeon master returns a plan, skill, eval, prompt pattern, or remedy
  -> Local/DeepSeek executes the bounded work
  -> evidence lands; result, cost, speed, and lesson return to memory
```

## Invariants

1. The source surface may affect presentation and authentication, never routing law.
2. Unfrozen build work is deferred on every surface.
3. T0/T1 never leave the machine.
4. The personal router is the continuing architect because it owns longitudinal context.
5. Frontier models are dungeon masters: temporary advisers and skill authors, not the permanent interface.
6. DeepSeek receives bounded BUILD contracts and relevant Verkle evidence, not an ambiguous full conversation.
7. Local handles deterministic, repetitive, and maintenance work first, after capability/speed evaluation.
8. Completion requires a terminal outcome plus evidence on disk.
9. Failures route back through the conductor; repeated failure summons a smarter dungeon master rather than repeating blindly.

## Model right-sizing loop

For each task class Mag keeps evaluated observations: model, hardware, prompt/skill, time-to-first-token, total duration, correctness, retries, cost, and resulting artifact. It starts with the smallest plausible local seat, promotes upward only when the eval fails or risk demands it, and periodically probes whether a smaller/faster model can now inherit the skill.

The frontier deliverable is not merely an answer. It is reusable teaching material: a bounded skill, eval case, prompt pattern, failure remedy, or routing rule that can be tested by the personal router and promoted after repeated success.

## Adapter requirement

Every new UI, chat integration, voice entry, scheduled job, or external tool must produce `mag_intent.v1` through `mag.operating_protocol.build_envelope`. Direct provider calls are legacy exceptions and should be migrated or explicitly labeled.
