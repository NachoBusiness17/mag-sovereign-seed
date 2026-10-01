# One-pager: Seat intelligence (no test farm)

**Commitment:** `mag-seat-intelligence-001`

## Goal

Pick **which model/seat** for each task using **public priors + your ledger** — not running full eval yourself.

## Stack

```text
seat_playbook.yaml (priors, tips, cites)
  → seat_score(task, seat) at route time
  → posterior from cost_ledger (optional, grows over time)
```

## You record

- **Capabilities:** context, tool use, sweet spots, avoid list  
- **Tips:** per seat (DeepSeek, Grok, Cursor, Ollama, **cloud agent**)  
- **Public prior:** cited URL or community_hearsay — honest confidence  
- **Your posterior:** median USD/leaf, seat_efficient rate (when n≥5)  

## Public data sources (already in Mag)

improve scout URLs · AGENTIC_LANDSCAPE · STEAL_AUTOPILOT · cost_rates · vendor docs

**Steward:** `steward-seats` weekly → draft playbook diffs → promote

## Inference (no pytest required)

Score = prior fit + avoid penalty + context fit + economics + budget + posterior

## Not

Mandatory A/B · LMSYS clone · auto-promote scout · chat-as-truth

## Files

`docs/ref/MAG_SEAT_INTELLIGENCE.md` · `configs/seat_playbook.yaml`

## Build

I1 playbook → I2 seat_score.py → I3 route hint → I4 steward-seats → I5 ledger merge
