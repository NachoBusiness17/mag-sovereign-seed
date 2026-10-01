# Decision layers

Three channels — do not merge them in code or UI.

```
┌─────────────────────────────────────────────────────────────┐
│  INTERFERENCE (operator)                                     │
│  Breadcrumbs · operator_inbox · deferred at checkpoint       │
│  Emergency steer · !steer / !pause · mid-round               │
└───────────────────────────┬─────────────────────────────────┘
                            │ feeds hints, does not route alone
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  DECISION FRAMEWORK (mag/decision_framework.py)              │
│  Mirror compass · case law · behavioral leaves · session mine  │
│  → surface_tips() · decide() · escalate_on_loop()            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ROUTER (mag/router.py)                                      │
│  depth → seat → provider · honest executable flag              │
└─────────────────────────────────────────────────────────────┘
```

## Breadcrumbs = interference only

Operator drops a note while the seat works. **Not** a routing decision — absorbed at checkpoint (`operator_inbox`). Use for steering intent; framework + router still pick the seat.

## Framework = your embedded decision tree

Built from disk, not chat:

| Source | Feeds |
|--------|--------|
| `mag/compass.py` | Constitution, blueprint, case law, mandate |
| `memory/decisions_log.jsonl` | Precedent from steers + outcomes |
| `logs/behavioral_events.jsonl` | collapse, degenerate, tool_fail |
| `memory/improve/daily/*-behavioral.md` | Synthesized themes (`behavioral_synth`) |
| `memory/agent_sessions/*.json` | Hot tool patterns across sessions |

**CLI:** `python main.py decide "implement X"`  
**API:** `POST /api/v1/decide` `{ "goal": "…" }`

## Loop → smarter seat (not more tokens)

When a janitor seat repeats tools or degenerates:

1. Log `behavioral_events`
2. `escalate_on_loop()` — ollama → deepseek → overmind → Grok pack
3. Queue orchestrator job; **stop** local burn

Wired in `mag/agent_cli.py` collapse detector + degenerate retries.

## Daily behavioral leaf

`mag improve --once` (scout) runs `synthesize_behavioral_leaf()` →  
`memory/improve/daily/{date}-behavioral.md`

Governance + context-pack inject themes when `inject_behavioral_pack` is on.
