# THE MACHINE — what's working, in plain language (2026-08-17)

You don't need to keep this in your head. Read this file. It's the truth, grounded.

## The whole idea (one sentence)
Two grok seats do real work; a free local DeepSeek coordinates them; our system steers everything
with contracts and gently corrects when they drift. Everything the seats produce folds into
training data and the game.

## What's actually working RIGHT NOW
- **Two grok seats** (nacho + sd) — both authenticated, both drive in parallel, both answer
  on-contract. `grok` picks the seat in PowerShell.
- **Steering works** — thin seat-card + contract + watch + gently correct. Proven repeatedly:
  seats answer directly, on-scene, first try. No more "grok goes dumb."
- **Local DeepSeek bus** — running free on Ollama (VRAM). Steers the same way as grok. This is
  the free coordinating glue.
- **Training loop** — every accepted seat output folds into `training_rows.jsonl` + steer feedback.
  The steer protocol learns and improves each round.
- **Game** — seats produce real Mirror Sea content (rooms, mechanics, world details) that folds
  into the game.

## How to run it (the only command you need)
```
python memory/runs/experiment_loop.py 3
```
That drives both seats for 3 rounds, folds everything, learns. Repeat with a bigger number to do more.

## How to check usage (stop guessing)
- Seat status: `grok --seats`
- Training rows: `memory/pile/training_rows.jsonl` (it's growing)
- The premium usage meter is on the **SD/fostertron** grok.com account, not nacho.

## The honest limits (so you don't get surprised)
- Local DeepSeek is only **1.5b** (fits 6GB VRAM) — good for coordinating/scut, NOT frontier work.
- Grok seats are the frontier brain. Local bus is the cheap glue.
- "0% usage" on a dashboard usually = checking the wrong account, not nothing happening.

## What's NOT done yet (so you know)
- The loop runs when you run it, or on the governor cadence — not yet fully autonomous end-to-end.
- dsh-on-Ollama is a real capability now, but the full DeepSeek Harness isn't installed — we use
  our own `agent_cli.py` as the harness instead.

## Standing facts (the ones you kept re-teaching me)
- Two seats = two accounts = nacho + sd. SD = fostertron = the premium/funded one.
- Thin context good, full context makes grok dumb.
- Never claim usage/spend without the ledger bytes.
