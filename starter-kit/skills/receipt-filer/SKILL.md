---
name: receipt-filer
version: 0.1.0
description: >
  File the receipt before claiming done: what was done, the evidence
  (commands + outputs + paths), what is owed. Trigger: end of any task.
---

# Receipt Filer

The claim comes after the evidence, never before.

## Run

```bash
mkdir -p inbox && date -u +%Y-%m-%dT%H:%MZ
# then write inbox/<date>-<slug>.md with the shape below
```

## The receipt shape

```markdown
# <what was done> - <date>

## What was done
- <imperative bullets>

## Evidence
- <command> -> <its real output, pasted or path:line>

## Owed
- <what this work discovered but did not do>
```

## Gates

- Every claim in the receipt has a neighbor in Evidence (a command, a
  path:line, or a fetched URL). No naked claims.
- Owed is never empty silence: write "none found" if nothing is owed.
- Append-only: a wrong receipt gets a follow-up receipt, not an edit.
- Filing happens BEFORE anyone says "done" - including you.

## If the task has no evidence

Then the task is not done. Do the task, or file a receipt that says what
blocked it, with the blocker's output as evidence.
