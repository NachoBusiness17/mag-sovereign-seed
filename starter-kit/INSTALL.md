# INSTALL - the ladder, in order, with the why

Written the way a friend explains it: what you're installing, why it
exists, how to verify it, and the gotcha that will bite you. Everything
launches HEADLESS (no windows popping at you; everything runs in the
background and files receipts). Nothing here ever kills your machine's
background work when interrupted - interrupts steer, they never kill.

## Step 0 - a daily driver (pick ONE, this is your cockpit)

You need one CLI agent you open every day. Any of:
- a coding-agent CLI (the kind that reads files and runs commands with
  you), or
- VS Code with an agent extension, or
- a headless agent runtime if you live in a terminal.

The kit is harness-agnostic: whatever you pick becomes the hands. Verify:
you can open it, point it at this folder, and it can read README.md.

## Step 1 - a free Gmail account (free compute, with real numbers)

Make a dedicated Gmail. It is the key to the free tier of every major AI
provider. Date-stamped reality (verified 2026-10-04; re-verify before you
lean on them - free tiers move):

- OpenRouter: 50 requests/day free; add $10 credit once and the free tier
  lifts to 1,000 requests/day (the credit is not consumed by :free models)
- Groq: ~200K tokens/day across its free model shelf
- Gemini: free tier exists at login, and **prompts on the free tier may be
  used to train the provider's models - keep private lanes off it and on
  your local model**

The kit's lanes are built to ride free tiers first (the ladder law:
dogfood cheap before spend).

## Step 2 - Docker (why you want it)

Docker gives every organ its own box: the lanes, the scheduler, the
memory services, each in a container that cannot stomp your system, that
restarts when it crashes, and that ships to any other machine unchanged.
Without Docker, one bad dependency wrecks the cockpit; with it, you
`docker compose up` and the whole system stands headless. Install:
docker.com/products/docker-desktop (Windows/Mac) or your package
manager (Linux). Verify: `docker run hello-world`.

## Step 3 - a local model (why, and which)

WHY: a local model is yours - no rate limit, no subscription, no data
leaving the machine, runs offline, and powers the unattended night lanes
without burning API credits. It is the sovereignty layer.

WHICH (pick by your VRAM):
- 8GB VRAM: a 7-8B instruct model (q4 quant) - drafts, summaries, lanes
- 16GB VRAM: a 20-27B (q4) - writes working code at reading speed
- CPU only / phone: a 2-4B - the janitor tier, still useful for lanes

Install Ollama (the easiest local runtime):
- Windows: `winget install Ollama.Ollama` in an admin PowerShell
- Mac: `brew install ollama` - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
Then pull your model by size class (see ollama.com/library) and verify:
`ollama run <model> "Write a haiku"` - if it answers, your GPU is doing AI.
`ollama ps` should show 100% GPU (100% CPU means update your graphics
driver).

GOTCHA (the one that bites everyone): default context is 4096 tokens -
too small for real work. Make a Modelfile:
```
FROM <your-model>
PARAMETER num_ctx 32768
```
then `ollama create mine-32k -f Modelfile` and use `mine-32k` by name.

## Step 4 - your env keys, done correctly

Every provider key you collect (from the free Gmail signups) goes in ONE
file: `.env` in the kit root, one `NAME=value` per line. Rules:
- `.env` is gitignored from birth. NEVER commit it, never paste a key
  into a chat or a script.
- The kit reads keys from `.env` only; no key is ever hardcoded.
- Template shipped as `.env.example` (names, no values) - copy to `.env`
  and fill in. If a key leaks, rotate it at the provider, same day.

## Step 5 - murmur (the voice room)

Murmur is the server of Mumble, a free, open-source voice-chat system.
It is the kit's PARTY LINE: a persistent voice room your machines and
people can join - agents that speak status, you that talk while doing
other things, everything headless. Why it belongs here: problems get
solved faster in a group, and a room that is always open is the cheapest
coordination organ there is.

Set up (Docker, one command - the OFFICIAL image; the server was renamed
Murmur -> mumble-server, pushed 2026-09-23, ~3.7M pulls):
```
docker run -d --name murmur --restart on-failure \
  -p 64738:64738 -p 64738:64738/udp \
  -v murmur-data:/data mumblevoip/mumble-server
```
Install any Mumble client (mumble.info) on your daily driver, connect to
localhost, and you are in the room. Verify: two clients connect and hear
each other. The whole thing: containers keep it alive headless, the
party line keeps the swarm human.

## Step 6 - the loading interview (computer-use mode)

If your daily driver has computer use, load the kit INTO the agent and
let it run this install itself: hand it this file, answer its questions,
watch it explain what it will install and why at each step. Then ask it
THE two questions: "what skills do you have and why do you exist?" The
kit's answer lives in README.md and SUBSYSTEMS.md - the agent you just
built should be able to give it in your own words.

## The interrupt law (read this one twice)

Interrupting a running lane STEERS it - it never kills your machine's
background work. Lanes checkpoint per leg and resume; nothing nukes
processes it did not start. If a lane wedges, the master watcher repairs
the ask or escalates to you. Your box is yours; the kit is a guest.
