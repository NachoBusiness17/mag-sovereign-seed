# START HERE — the training session

Someone asked: "will you be putting a training session together for your system?"
This is it. You hold the seed; this page drops you in. Pick the door that matches
the time and the computer you actually have.

## The one-paragraph version

A person built an AI agent that lives on one machine, keeps its own memory in a
tamper-evident diary, writes receipts for its work, grades its own claims
(Supported / Disputed / Unproven), and runs mostly on free compute. This package
is the shareable part of that system: its rulebook, its organs, its manual, and
two of its stories. You can read it, talk to it, or grow it.

## Door 0 — ten minutes, install nothing

Read, in this order:

1. `THE_SYSTEMS.md` (here) — what the parts are and why each one exists, in
   normal words.
2. `story/48h_synth/STORY.md` — the system's own account of its busiest two days.
3. `story/RAINBOW_ROAD_RACTOR_20260929/FINAL_PIECE.md` — it fact-checks a friend's
   poster about the Norse rainbow bridge, tells you which of thirteen claims
   survived (twelve did, one did not), and then tells the story anyway.

That is the whole personality. Everything else is plumbing.

## Door 1 — drop us into any chat AI you already have

You do not need to install anything to talk to this. Open whatever chat AI you
already use (free tiers are fine), attach or paste these files, and send this:

```
You are holding the seed package of a working AI agent system.
Read these three files, then answer my questions about how it works:
1. THE_SYSTEMS.md
2. boot/CONSTITUTION.md
3. boot/LOAD.md
Answer in plain language. If the files do not answer something, say so
instead of guessing.
```

Why the last line matters: that is the system's own first law, tri-state honesty.
An AI that says "not in the record" instead of inventing an answer is doing the
thing this whole package is about.

## Door 2 — get free compute (the actual guide)

The system runs on nearly-free compute by design. `FREE_COMPUTE.md` (here) is the
guide: local models on your own machine, then free API keys from five providers,
then the no-account lanes. Ten minutes of sign-ups gets you more AI than any one
paid subscription, if you follow its one law: the pool matters more than any
single model, and you audit a lane before you trust it.

## Door 3 — an evening: grow it

For a technically-minded friend. After unzipping, from inside the folder:

```powershell
# the 30-second version: prove the skeleton is alive first
pip install -r requirements.txt
python mag\smoke.py
# -> ~18 organs tri-stated, a receipt hash, the first law.
#    no keys, no network, no .env. Then read mag\MANIFEST.md for the map.

# the full evening: the whole system
python -m venv .venv
.venv\Scripts\Activate
pip install -r boot\requirements.txt
# create a file named .env and put YOUR OWN free keys in it (FREE_COMPUTE.md)
docker compose -f boot\docker-compose.yml up -d --build
# dashboard appears at http://127.0.0.1:8765/
```

Expect to read more than you type. It is a garden, not an app.

## Common mistakes (each one was made live, then written down)

- **Skipping the audit.** Before installing anything, check what already exists.
  "Command not found" means not on the PATH, not that it is missing. Audit first,
  install second. This rule exists because someone once spent an evening
  reinstalling five tools that were already installed.
- **The silent truncation trap.** Local models often default to short memory
  (8K tokens) while agent tools ask for long memory (64K). There is no error
  message; the model just quietly forgets most of a long document. If answers
  seem to ignore your files, that is this trap. Set the context length
  explicitly on both sides.
- **Trusting a free lane forever.** Free catalogs change without notice (one
  provider's free list went from four models to three mid-week). The habit that
  survives it: check the live model list before each work session.
- **Putting keys anywhere except a .env file.** One file, never shared, never
  zipped, never pasted. This package was machine-scanned to keep secrets out;
  keep your copy equally clean.

## What it costs (honest numbers from the live system)

Free lanes carried the bulk of roughly 190 million tokens of the system's work
(its own audit flags that headline number as unverified, which is exactly the
house style). The paid frontier bill on a heavy day was $2.39. The default
answer to "can we afford it?" is a free lane. That is not a slogan; it is how
the thing actually runs.

## If you get stuck

`boot/README_ESTATE.md` and `docs/PLAIN_SYSTEM_FOR_HUMANS.md` are the long
manuals. `PROVENANCE.md` says exactly what is in this package and what was kept
home. Nothing here phones home, and no one can unplug your copy but you.
