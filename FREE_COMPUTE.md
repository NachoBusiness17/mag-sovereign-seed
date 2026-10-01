# FREE COMPUTE — how to get real AI power for $0 (2026-10 edition)

The live system this seed came from runs on free compute by design, not as a
hobby trick but as its founding economics: the answer to "can we afford it?" is
a free lane. This guide is that doctrine, written for someone starting from
zero. Every provider named here was used by the live system; the numbers below
come from its own receipts.

## The three laws (the durable part; providers come and go)

1. **The pool beats the model.** No single free provider is reliable forever.
   Five free accounts at five providers is more compute, more uptime, and more
   model variety than one paid subscription. The live system keeps about a
   dozen free endpoints alive and routes around whichever one is limping.
2. **Audit a lane before you trust it.** Before each work session, fetch the
   provider's live model list (one web request). Free catalogs change with no
   notice: during one week of watching, one provider's free list went from four
   models to three. The system survived because it re-checked instead of
   trusting yesterday's list.
3. **Keys live in one file, and that file never travels.** Make a plain text
   file named `.env` in the project folder, one `NAME=key` per line, and never
   zip it, paste it, or screenshot it. Every provider below gives keys for free;
   a leaked key is the only way this hobby costs real money.

## Level 1 — your own machine (no account, private, forever free)

**Ollama** (ollama.com) runs open models locally on Windows, Mac, or Linux.

- Install it, then in a terminal: `ollama pull qwen3:1.7b` (or `gemma3:1b` for
  very modest computers), then `ollama run qwen3:1.7b` and just talk to it.
- Small models run on ordinary laptops with no graphics card. Bigger models
  (`:7b` and up) want a machine with a good GPU or lots of RAM.
- The trap (verified the hard way): Ollama often defaults to a short memory
  (8K tokens) while agent tools ask for long (64K), and it fails silently; the
  model just ignores most of a long document. If local answers seem to skip
  your files, set the context length explicitly.

Level 1 is private (nothing leaves your machine) and cannot be taken away.
It is small. Levels 2 and 3 are where free compute gets big.

## Level 2 — free API keys (ten minutes of sign-ups)

Each of these gives a free tier with a free key. Sign up, create a key, put it
in your `.env`, and point any OpenAI-compatible tool at it.

| Provider | What you get free | The gotcha |
|---|---|---|
| **OpenRouter** (openrouter.ai) | One key, hundreds of models; filter the catalog to `:free` tags (the live system's last audit counted 460 models total, with a rotating free subset) | Free models are rate-limited per day; rotate between several rather than hammering one |
| **Groq** (groq.com) | Extremely fast open models | Free tier has per-day caps; a second free account doubles the ceiling (the live system runs two, both legal free accounts) |
| **Google AI Studio** (aistudio.google.com) | Gemini models, generous free tier, fast | Region and rate limits vary; get the key from the "Get API key" button |
| **Mistral** (console.mistral.ai) | Solid small models, free tier | Some models need a phone-verified account |
| **Cohere** (dashboard.cohere.com) | Trial key with free usage | Trial means trial; fine for learning, not for a daemon |
| **NVIDIA build** (build.nvidia.com) | A very large catalog of open models via free API credits | Credits need periodic renewal; check remaining credits before long jobs |

## Level 3 — the no-account lanes (what the live system actually watches)

- **LLM7** (api.llm7.io): a keyless endpoint; you can call it with no account at
  all. Its free model set is small and CHANGES (audit it first: GET
  `https://api.llm7.io/v1/models` with no key, read the JSON). Treat as
  best-effort, never load-bearing.
- **Provider model catalogs as free intel**: `https://openrouter.ai/api/v1/models`
  and `https://api.featherless.ai/v1/models` answer with no key and no account.
  The second lists tens of thousands of community models for recon.

## What free compute actually looks like (receipted numbers)

- The live system's inventory: **12 alive free endpoints, roughly 50 to 100
  distinct usable model lanes at $0**, about 35 in daily rotation.
- Its own verdict, quoted: "The free-tier rate ceilings are the constraint, not
  the model quality. gpt-oss-120b on Groq answers in 1-3 seconds, faster than
  most paid APIs. The wealth isn't one big model, it's the diversity of the pool."
- Total spend on the heavy frontier day this seed was cut: **$2.39**, by choice,
  for twelve verdicts that needed the biggest models. Everything else rode free.

## The honest closing

Rate limits and free catalogs shift monthly, so treat the provider list as a
snapshot and the three laws as the asset. If a lane dies, audit, rotate, and
keep moving. That habit, not any single website, is what "free compute" means.
