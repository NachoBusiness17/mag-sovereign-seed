# One-pager: Local steward & actor memory

**Commitment:** `mag-local-steward-001`

## Local steward

**Seat:** Ollama janitor · **Shape:** queued `[steward]` jobs, not open REPL · **Cap:** ~2/day via autorun/improve

| Job | Output |
|-----|--------|
| steward-prompts | prompt catalog jsonl |
| steward-bugs | improve candidates from FKB/pytest |
| steward-patterns | daily patterns md from trails/events |
| steward-verkle | chain walk + synth slice |
| steward-engines | draft actor facts from Grok/Cursor feeds |
| steward-train-prep | redacted T2 export |

## Verkle read (local only)

Full: tip, chain, knots, residuals, lattice. Remote seats: **thin bond** in pack only.

## Actor memory (xAI-like, on your disk)

```text
memory/actors/persons/{id}/  profile + facts.jsonl + amends.jsonl
memory/actors/engines/{grok,cursor,deepseek}/  + sessions_index → pointers
```

- **Fact** = one line + `source.ref` — not chat dump  
- **Person facts** → draft until L3 promote  
- **Edit/delete** → `amends.jsonl` audit trail  

**Law:** Prompt is never memory (`memory_verkle_map.md`). Chat = warm; facts = cold.

## Pack bond (L0)

Active actor facts only — no full amends trail to remote.

## Build order

S1 actor schema → S2 steward enqueue → S3 verkle read API → S4 engine digest → S5 Office Actors tab

## Full spec

`docs/ref/MAG_LOCAL_STEWARD.md`
