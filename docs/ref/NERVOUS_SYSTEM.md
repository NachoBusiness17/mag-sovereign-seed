# Nervous system — agent ops subsystem

**Commitment:** `nervous-system-module-001`  
**Module:** `mag/nervous_system.py`  
**Face:** `memory/nervous_system.md` · `.json`

## Job

At-a-glance **containment** for agent operation: is the body alive, what tips do we hold, which seats have keys — **without inventing status from chat**.

Not DNA. Not a second constitution. Viewport + harness edge.

## Commands

```text
python main.py nervous          # human glance
python main.py nervous --json   # full schema
python main.py context-pack     # L0a = pack_excerpt() from this module
mag.cmd doctor                  # first grab — venv read, no spawn
docker compose restart mag      # if dash/heartbeat dead AND docker works
python main.py lab              # LAST RESORT host supervisor — not default
```

## Key statuses (presence only — never print values)

| status | Meaning |
|--------|---------|
| `ok` | in `.env` and process |
| `env-only` | in `.env`; Mag python usually loads it |
| `process-only` | shell has it; may not be in `.env` |
| `missing` | neither |

## Law

Trust glance + doctor JSON, not model memory.  
Probe before claim: `provider-chat --provider X`.
