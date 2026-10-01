# Mag - front door (a regenerated clone)

**What this file is:** `docs/FRAMEWORK_LOAD.md`, the estate's front door. It is
**never hand-edited**: `tools/regen_front_door.py` renders it from live truth
(stable prose below + auto sections above). The front door dies and is reborn
every cycle, so a cold seat can never load a self-story that no longer exists
(Mickey17 W3, return 12: the old hand-written door narrated the August estate
while the live chain had moved on).

**Point any model here:** `docs/FRAMEWORK_LOAD.md` · **Short pointer at repo
root:** `LOAD.md`

<!--REGEN:ERA-->
<!--REGEN:GATES-->
<!--REGEN:AGENT_STATE-->
<!--REGEN:LAYOUT-->

## What this repo is (stable)

Mag is the **Mag Resource Harness**: a local-first records office for one
operator and a fleet of model seats. Residual on disk is truth; chat is heat.
Local Ollama janitors do the scut, funded frontier specialists are scarce and
climbed to only for judgment, and the operator is the owner, not a user.
Fidelity lives in files + chain (see `docs/DNA.md`), never in a process that
must stay awake.

Sovereignty law: T0/T1 material never leaves the machine. All durable
cross-surface work lands on the shared inbox (`watch/inbox/INDEX.json`), and
model text can propose while only the switchboard / effect broker authorizes
effects.

## The office metaphor (stable)

| Mag piece | Metaphor | Layman use |
|-----------|----------|------------|
| Office dashboard (`:8765`) | Front window of the building | "Is everything OK? What happened yesterday?" |
| Bead / residual | Filed workday folder | "What did I actually do that day?" |
| Pack | Briefing envelope for a visitor | "Here is what matters, not my whole life" |
| Queue / todo | In-tray on the desk | "Do this next" |
| Router / switchboard | Receptionist | Sends work to the right room (cheap local vs scarce specialist) |
| Janitor seats | Janitor | Sorts mail, summaries, routing; always on, cheap |
| Specialist seats | Skilled contractor | Called in only when the janitor cannot |
| Orchestrator | Shift supervisor | Spawns workers; one crash does not kill the building |
| Improve loop | Suggestion box + review | Scouts ideas; the operator approves changes (promote) |
| Verkle / tip | Seal on the filing chain | "The chain of records is intact" |
| Constitution / tiers | Building code | What must never leave the building (T0/T1) |

**You are not the building. You are the owner.** Models are visitors with a
pack, not roommates with memory. Live seat truth (who is funded, who is
dormant) rides the agent-state tip above and `AGENTS.md`, never this table.

## Load order (stable)

| # | File | Why |
|---|------|-----|
| 1 | `docs/FRAMEWORK_LOAD.md` | This door (you are here) |
| 2 | `docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md` | Compass: vision, agent loop, v1-v10 arc, sovereignty |
| 3 | `docs/ref/MYCELIAL_SCIENCE_MAP.md` | Biology to protocol: mycelial science map |
| 4 | `docs/ref/MAG_DIRECTION_ARTIFACT_v2.md` | Phase gates, v3 entry, v4-v5 mold |
| 5 | `docs/ref/MAG_PROJECT_PROPOSAL.md` | Problem depth |
| 6 | `docs/ref/OPERATOR_CARD.md` | FIND · FILE · LOAD daily doors |
| 7 | `AGENTS.md` | Python env law + commands (do not skip) |
| 8 | `mag.cmd context-pack` | Min-token pack for your seat |

Then: `state/CURRENT.md` (live truth) · `queue/todo.md` ·
`HANDOFF_MAG_AGENT_TODOS.md` if implementing. `memory/briefs/latest.md` is
FROZEN 2026-09-26 and must not be consumed as live.

## Three doors (stable)

```text
FIND  ->  get real material (posts, exports, files - as presented)
FILE  ->  write durable record on disk (bead, trail, dig leaf)
LOAD  ->  hand AI a small pack (context-pack), not chat history
```

## FILE block (end every session)

```text
FILE for Mag residual:
- What turned (3 bullets)
- Open loops
- Paths touched
- One next move
- Commitment slug
```

Chat dies. Files persist.

## What NOT to do (stable)

| Don't | Do instead |
|-------|------------|
| Treat chat as memory | FILE to residual / trail |
| Load the whole repo into context | `context-pack` only |
| Use bare `python` on PATH (often Hermes venv) | `.venv\Scripts\python.exe` or `mag.cmd` |
| Send T0/T1 to remote APIs | Local only |
| Hand-edit this door | Edit the template, rerun the tool |
| Trust a label over bytes | gates.jsonl / LATEST.md / chain tip win |

## How this door is born (regeneration contract)

- `docs/templates/FRONT_DOOR_TEMPLATE.md` (this template) holds every stable
  section plus the four `<!--REGEN:SECTION-->` placeholder lines.
- `tools/regen_front_door.py` parses the zeitgeist era line
  (`docs/archive/ZEITGEIST.md`), the release-gate rows
  (`memory/improve/releases/gates.jsonl`; final row per gate wins), the
  agent-state tip (`memory/agent_state/LATEST.md`), and the root `ls`, then
  writes this file with LF endings.
- **Determinism law:** no wall clock, no dict iteration order. Each auto
  section's `generated_at` is keyed to the newest mtime of its own truth
  sources, so reruns over an unchanged tree are byte-identical; `--at` pins
  all stamps for receipts.
- **Em-dash law:** a U+2014 anywhere in the render fails the run (exit 2)
  naming the line. Parsed truth is never silently laundered.
- Rerun at every wave close:
  `.venv\Scripts\python.exe tools/regen_front_door.py` (`--check` for a
  fresh/stale exit, `--stdout` to preview, `--at ISO` to pin stamps).

*End front door - the clone replaces the corpse; do not edit me by hand.*
