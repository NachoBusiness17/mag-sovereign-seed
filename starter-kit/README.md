# THE STARTER KIT - a behavioral agent system that grows into your own

A complete, self-describing setup package: load it into ANY system that can
run Python and talk to an LLM (a coding agent, a chat assistant, a headless
box, your phone). It contains the method, the organs, the workflows, and
the laws - and none of anyone's private data. What you build from it is
yours, in your jargon.

What it becomes: a truly reactive behavioral agent that mines your
conversations and posts data into its own memory, recreating the
assistant-you-rely-on over time - your laws, your vocabulary, your decided
things. It reaches for a user profile at boot; if none exists it makes one
and starts empty. That is the designed first run.

## Quickstart (any system)

```bash
git clone https://github.com/NachoBusiness17/mag-sovereign-seed starter-kit && cd starter-kit
python tools/kit_doctor.py          # environment check + what to fetch
python tools/profile_boot.py        # first boot prints FIRST BOOT and exits 1 - that is the designed start
# then read tutorial/TUTORIAL.md and do lesson 1 today
```

No pip installs. The kit is stdlib-only Python plus markdown. The doctor
names anything missing and where to get it free (git, a GitHub account,
optionally a local model runtime for offline lanes).

## What's inside

| path | what |
|---|---|
| BOOT.md | the clean boot: the first hour, step by step |
| LAWS.md | the method laws that survived - each with its why |
| PROTOCOLS.md | wave protocol, append-only-allow-failures, the master watcher, the stochastic cloud, swarm states |
| SUBSYSTEMS.md | the 11-organ catalog: what each does, how to grow it, how to jargon-map it |
| tutorial/ | tutorial mode: a guided first day, hands-on lessons |
| agent/ | the mining-loop skill cards (conversation-miner, profile-grower, law-minter) |
| skills/ | transferable method cards (steal-ready, rename freely) |
| workflows/ | multi-agent workflow shapes (fan-out, confirm, ractor lens swarms) |
| setup/ | install helpers per platform |
| integrations/ | plugs for Hermes-class agents and Android |

## The one-sentence theory

Laws are bred from failures, organs are selected by evidence, inheritance
is commits, memory is the chain - and the assistant a user experiences is
the grown profile, not the base model.

## License & spirit

Open source rules: take it, tear it apart, mash it with other shit, make
it yours. Rename everything into your own vocabulary - the laws survive
translation, the labels do not need to. If it made something cool for you,
that is the whole point.

## Pushing it onward

This kit is itself a git repo - fork it, strip what you do not use, commit
your genome into it, and send it forward. (If you cloned the canonical
repo: fork on your host, add your fork as a remote, push there; the
canonical repo stays read-only for you.) It is a starter kit designed to
be sent back in time.
