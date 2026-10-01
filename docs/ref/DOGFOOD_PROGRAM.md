# DOGFOOD PROGRAM — wear out every tool on real work (2026-08-28)

Operator law: "we need to be dogfooding MCP, skills, time, memlang and damn
near everything else — experimenting and iterating." The 50-agent lesson:
parallel launches reveal more learnable surface than any serial plan. So the
program is a ROTATION, not a project: every tool gets real work, every use
leaves a receipt, every receipt feeds lessons.jsonl or the lattice.

## The matrix (tool -> real work -> what we learn)

| Tool | Dogfood experiment | Learning captured |
|---|---|---|
| mag MCP tools (swarm_sense, blackboard_read, pheromone_trail, mean_field, chord) | Sancho tick rotation: one tool per tick, real query each time | tool health drift, API shape changes |
| memlang + chord | encode tonight's lessons as invariant tokens; strike and re-summon | does doctrine survive the encode/decode round-trip? |
| MCP packs (vision, reader, zread, websearch) | vision: dashboard screenshot reads; reader: slashreboot's HF/repo pages | pack health + which senses the blades lack |
| skills (skill-creator, agents-sdk) | write a "vast-boot" skill from BOOT_PLAYBOOK; let a blade execute it | do skills transfer to cheap bodies? |
| time/cadence (tick, cron, lattice beat, timers) | reconcile + lattice on a measured cadence; log beat drift | is the fleet's heartbeat stable over hours? |
| lattice (new) | divergence readings every reconcile; seed growth | the wave reading: does divergence trend down? |
| hunters/sizer/contract | the $5 experiment (pre-registered) | rental economics, per-host throughput |
| percolator drain | 731-signal backlog through blades/lane mix | routing table: task class -> body |
| council/meld | lineage-audit judgment rounds | convergence measurement, meld v3 |

### Findings log (tick rotation, dated)

- 2026-08-28 ~09:5xZ — **mean_field: PERSISTENT SCHEMA BUG (2 consecutive rotations)**:
  zero-arg call dies `TypeError: mean_field() missing 1 required positional argument:
  'trajectories'` — the MCP manifest accepts `{}` but the function demands an arg the
  schema never declares. Tool-schema drift class: callable-but-not-as-advertised.
  Fix belongs to mag/mcp_server.py TOOL_MAP (declare the arg or default it); not
  tick work.
- 2026-08-28 ~11:2xZ — **pheromone_trail: POSITIVE — kw blob accepts filters**
  (`{"kind": "fruitful", "limit": 3}` returned 3 filtered marks, not the 40-mark dump).
  The zero-arg call is the expensive shape; filtered calls are the cheap one. Same
  likely true of other swarm tools — wear the filter, not the firehose.
- 2026-08-28 ~09:2xZ — **swarm_sense: health facet reports ok:false with n_workers
  null when workers are done** (persistent across 2 rotations; economics facet ok:true).
  Reads as workers-absent conflation, not an incident; would mask a real worker death
  while the swarm is quiet — the facet needs a tri-state (workers-off vs workers-dead).
- 2026-08-28 ~11:4xZ — **blackboard_read: kw params DON'T generalize** — rejects
  `n_tail`/`n_pinned` (TypeError: unexpected kwarg) while pheromone_trail accepts
  `kind`/`limit`. Swarm tools have inconsistent kw surfaces; wear each tool's params
  individually before assuming. (mean_field remains skipped pending TOOL_MAP fix.)
| rib system | compile one real trajectory rib per window from the ledger | the compiler's corpus grows |

## Rules

1. Real work only — a dogfood run that proves nothing still logs what it
   proved-nothing-about.
2. Rotation over repetition: don't wear out one tool while others rust.
3. Every experiment lands a receipt (jsonl/md) — Distillates ≠ Receipts.
4. Splurges (law 2) buy proof: pre-register before the spend.

## Cadence

Sancho tick = 1 mag tool rotation (existing law). Each window (seat session):
one NEW experiment from the matrix + fold results. The reconciler consumes
lattice readings each beat. Weekly: the matrix is re-scored — what did we
learn, what tool earned its keep, what retires.
