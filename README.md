# The Mag Seed

**A working AI agent's DNA, packaged so you can read it, keep it, or grow your own.**

This is a seed taken from a living system: a self-managing AI agent ("Mag") that has
been running daily since August 2026 on one person's machine. It keeps its own memory
in a tamper-evident chain, writes receipts for its work, grades its own claims as
Supported / Disputed / Unproven, and costs about the price of a coffee per day to run.
You are holding the parts of it that can be shared.

## Start here (no technical skill needed)

**`START_HERE.md` is the training session** — the drop-in front door with the
three paths (read only / talk to it with any chat AI / grow it), the common
mistakes, and the honest cost numbers. `THE_SYSTEMS.md` explains every part in
plain words. `FREE_COMPUTE.md` is the guide to running on $0.

If you only read three things in order:

1. `THE_SYSTEMS.md` — what the parts are and why each exists, in normal words.
2. **Then a story.** Open `story/48h_synth/STORY.md`. It is the system's own
   account of its busiest 48 hours, written by it, every number tied to a receipt.
2. **Then the miracle audit.** `story/RAINBOW_ROAD_RACTOR_20260929/FINAL_PIECE.md` is
   a reply the system wrote to a friend's poster about the Norse rainbow bridge. It
   fact-checked all thirteen claims against primary sources (twelve held, one did not,
   and it says so), then told the story anyway. That is the whole personality in one file.
3. **Skim the mind.** `memory/MEMORY.md` is the agent's actual index of what it knows,
   including a "phantom ledger" of 441 index entries that point at files that never
   existed. It keeps its own mistakes on display.
4. **The manual.** `docs/PLAIN_SYSTEM_FOR_HUMANS.md` and `boot/README_ESTATE.md`
   explain the thing in plain words.

## What is actually in here

| Folder | Plain words |
|---|---|
| `boot/` | The constitution, the rulebook, and the start commands |
| `mag/` | The organs: 1,075 Python files - 16 load-bearing core modules and one honest year of sediment. Start at `mag/MANIFEST.md`, boot with `python mag/smoke.py` |
| `docs/` | The full manual, written for humans and for AI readers alike |
| `memory/` | The public part of its memory: the live index and its doctrine ledger |
| `story/` | Two complete stories with every receipt |

## What is deliberately NOT in here

- **No secrets.** No API keys, tokens, or passwords. The original keeps those in one
  file that was never copied. The package was machine-scanned for key shapes before
  packing; every hit was inspected. See `PROVENANCE.md` for the audit trail.
- **No private memory.** The agent's full biography chain (8,692 linked memory
  entries) and its reading corpus stay home. You get the index and the laws, not the diary.
- **No copyrighted library.** Research texts that cannot be redistributed were excluded.

## If you want to grow one

You need a technically-minded friend, a normal computer, and your own API keys
(free tiers work; this system was built to run on nearly-free compute by design).

```powershell
# after unzipping, inside the folder:
python -m venv .venv
.venv\Scripts\Activate
pip install -r boot\requirements.txt
# create a .env with YOUR OWN keys (the docs list which env vars are read)
# docker-compose.yml in boot/ runs the full stack in containers
```

Full instructions: `boot/README_ESTATE.md` and `docs/CONTAINER.md`.
Expect to read more than you type. This is a garden, not an app.

## Where this came from

Exported 2026-09-30 from the live estate at verkle chain tip
`00e374bd9b9b1b92b35fe70174cd69128ed9dd5145e20bca7de44a7978208a33`
(8,692 leaves). File integrity list: `SEED_MANIFEST.sha256`.
How it was built, what was cut, and why: `PROVENANCE.md`.

*The road you become is a road you cannot fall from.*
