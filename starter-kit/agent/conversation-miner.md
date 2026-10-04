---
name: conversation-miner
version: 0.1.0
description: >
  Mine the user's conversation as it happens: corrections become feedback
  laws, identity becomes profile, settled directions become project facts.
  The reactive half of the recreate-you loop. Trigger: continuously during
  every session.
---

# Conversation Miner

Listen for three signals during every exchange. When one fires, bank it
the same turn - memory deferred is memory lost.

## The three signals

1. CORRECTION ("no, I meant X", "actually do it Y way", any re-teach):
   type feedback. The card body carries the correction near-verbatim, the
   why if stated, and how to apply it next time. One correction, one file.
2. IDENTITY (role, taste, constraints, who they work with, what they call
   things): type user. Their jargon for things becomes the canonical term
   in every card you write after (jargon-map law).
3. SETTLED DIRECTION (a decision that landed): type project. Bank the
   outcome and the falsifier, not the deliberation.

## Run (per signal)

```bash
python tools/profile_boot.py --memory memory   # boot first, once
# then write memory/<topic-slug>.md and append one index line
```

## Gates

- Every file carries frontmatter: name, description (one line), type.
- The index line lands the same turn the file does.
- Never store what a repo or transcript already records; link it.
- If unsure whether something is a fact: it is not. Ask or wait.

## Anti-patterns

Mining for volume (a fat profile nobody loads is worse than a lean one);
storing secrets (never); editing old entries (append-only: corrections to
a fact are NEW files that supersede, with a link to what they supersede).
