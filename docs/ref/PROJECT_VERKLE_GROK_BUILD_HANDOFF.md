# Project Verkle — Grok Build handoff

## Vision

Build a sovereign alternative to conventional AI memory and identity systems: a user-owned Verkle leaf recording durable preferences, provenance, relationships, and model-specific behavior.

The system should eventually support persistent user-controlled memory; separation of user and model preferences; local/frontier collaboration; synthetic salons; auditable branching, replay, comparison, and synthesis; narrative simulation; selectively rentable sovereign mirrors; and a playful PSO MAG-like interface. Historical figures are explicitly synthetic interpretations, never authentic reconstructions.

## Current build

Worktree: `C:\Users\foste\Documents\projects\worktrees\salon-arena-mvp`  
Branch: `codex/salon-arena-mvp`

Important files:

- `mag/salon_arena.py`
- `mag/salon_renderer.py`
- `mag/agent_arena.py`
- `configs/salon/lenses.yaml`
- `tests/test_salon_arena.py`
- `tests/test_salon_renderer.py`

Inspect branch and dirty state before modification. Do not silently merge or edit this worktree concurrently with its owning agent.

## Implemented observations

Slice 1 established deterministic canonical state, hash-chained events, legal-action validation, branching/replay, three conflicting lenses, and bounded salon actions.

Slice 2 established local Ollama decisions with `gemma4-desk:latest`, strict structured output, schema/actor/branch/state-hash validation, one constrained repair attempt, non-mutating rejection records, execution provenance, and explicit rejection of remote seats for this slice.

Focused result reported by the owning task: 15 tests passed; four unrelated chess tests skipped because optional `python-chess` was unavailable.

Live Ollama evidence reported model digest `8b8796e7d24b31599bf928c5e98ee9edf8085c00762b97922952aadcdb7a4a27` at 100% GPU. Nine decisions were accepted through round three and replay matched canonical state. Turn ten produced duplicate policy IDs twice; both attempts were recorded and the run stopped without inventing a replacement. This is a valid partial smoke test, not a completed behavioral experiment.

Calibration lessons—template anchoring toward `pass`, reasoning consuming the JSON allowance, action-vocabulary mismatch, and an exact-turn-limit bug—are instrumentation effects, not model preferences.

## Assignment

Audit the implementation and experimental design, then implement the smallest defensible next slice. Decide explicit failure semantics after two rejected decisions; prevent meaningless repeated proposals without action steering; preserve separation among user preference, model behavior, lens effects, interface effects, facts, simulation, and synthesis; and define the minimum dogfood console and measurements required before claiming model differentiation.

## Recommended next slice

Build an experiment console that can start named seats/models/lenses; display canonical state and append-only events; separate accepted and rejected attempts; show model/GPU provenance; replay or fork accepted events; compare actions and rationales; label observation source; and export a compact report.

Keep the deterministic engine authoritative. Models propose actions but never mutate state. Defer voice, historical salons, marketplaces, and elaborate world simulation until provenance, replay, branching, and preference separation are reliable.

## Working rules

- Local-first and user-owned
- No secret remote fallback
- Never call an incomplete or rejected run successful
- Never silently change a rejected action's meaning
- Preserve provenance hashes without unnecessarily retaining private raw prompts
- Keep model identity separate from lens
- Counterbalance prompt order and presentation
- Treat interface effects as experimental variables
- Test every transition and failure mode
- Report observations, not aspirations

## Required return

1. Design audit
2. Exact next slice
3. Chosen failure semantics and rationale
4. Files changed
5. Test and local-GPU evidence
6. Remaining limitations and next falsifiable experiment

Read first: `docs/CROSS_AGENT_VERKLE_HANDOFF.md` and `docs/ref/SHARED_STATELESS_SCRATCH.md`.
