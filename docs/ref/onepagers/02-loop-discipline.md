# One-pager: Loop discipline

**Commitment:** `mag-loop-discipline-001`

## Problem

“100+ Mag steps” is usually **harness ticks**, not one smart agent.

| Signal | Meaning |
|--------|---------|
| Same goal replanned 1000+× | Plan theater — drainer replans, queue never drains |
| N× `[verkle] summarize-session` | Verkle fan-out — batch `backfill-sessions --all` instead |
| 100 tool rounds, no leaf | Agent churn — collapse/FKB; outcome gate missing |

## Rules

1. **One outcome per leaf** — knot · test green · PR/spec · terminal queue state  
2. **Batch cold path** — verkle integrity = batch, not queue drip  
3. **Dedupe goals** — same normalized goal refused at enqueue  
4. **Slim autorun trail** — plan fingerprint, not full routes every 5s  
5. **Check pause** — `MAG_OPERATOR_ACTIVE` / drainer pause before blaming model  

## Detectors

| Kind | Counters |
|------|----------|
| plan_theater | replan ↑, drain_delta = 0 |
| verkle_fanout | summarize_count > 1 per session |
| agent_churn | tool rounds ↑, no terminal / knot |

**CLI:** `python main.py loop-audit` · **Patterns:** `configs/training_patterns.yaml`

## Safe auto tier

| Auto | Draft | Human |
|------|-------|-------|
| dedupe refuse, pause fill, slim trail | batch verkle goal, FKB remedy | clear queue, promote config |

## Eval (frozen)

Autorun 2000× replan no drain · 5 orphans → 1 batch · 100 rounds no file · duplicate enqueue refused

## Full spec

`docs/ref/MAG_LOOP_DISCIPLINE.md`
