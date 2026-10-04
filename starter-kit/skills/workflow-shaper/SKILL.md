---
name: workflow-shaper
version: 0.1.0
description: >
  Cut a question wider than one seat into the five workflow shapes:
  fan-out, confirm, synthesize, cold-read, revise. Trigger: "go wide on
  this", any multi-agent need.
---

# Workflow Shaper

Five shapes cover almost every wide question. Compose them; do not
invent a sixth until these five have failed you.

## The five shapes

1. FAN-OUT: one NAMED actor per item (never one actor for all items;
   never N actors sharing one name). Each actor gets the item, the laws
   (no em-dashes, never fabricate, cite evidence), and a typed result
   contract.
2. CONFIRM: a fresh context re-reads each load-bearing finding's
   evidence and returns confirmed/unconfirmed. The finder never confirms
   itself. Findings that fail stay, labelled.
3. SYNTHESIZE: chapters from the lane results - every claim traceable to
   a lane's evidence; disagreements named, not smoothed.
4. COLD-READ: a context that saw nothing but the draft reports what is
   unclear, unsupported, and missing. Ask what would break it, never
   whether it is good.
5. REVISE: the critique drives exactly one revision round; then ship
   with the residue named.

## The salvage law

Report each item the moment it lands. A run that dies on item twelve
still delivers eleven items' work - if and only if items were reported
as they landed.

## Run

Write the shapes as a script in whatever workflow harness you hold (or
as five sequential prompts in five fresh chats - the shapes, not the
tooling, are the method). Name actors per item; bound every ask; keep
actor names stable across revisions so re-runs reuse finished work.
