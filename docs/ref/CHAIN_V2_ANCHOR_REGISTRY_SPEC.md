# Chain-v2 anchor registry — the per-tree v2→v1 citation ledger (spec v0)

Companion to `memory/runs/grok_burn/design_chain_v2_mmr.md` (the MMR build spec).
That spec defines HOW a v2 knot cites a v1 leaf (MEM1 `prove` token carrying the
32-byte v1 `leaf_hash`). This spec defines WHERE citations are claimed, tracked,
and falsified: the last unsolved piece before the first legal v2 write.

## Why a registry exists at all

Operator law of repairs (2026-08-27, CONVO): **testimony, not resurrection.**
v1 stays frozen byte-zero. Every repair is a typed fact in v2 — either a healed
row (surrogate re-derivable from floor tapes) or an irrecoverable gap (honestly
committed as such). Each claim must be *falsifiable by re-derivation with
map+tape*. That means three parties must agree at any time:

1. the v2 leaf (carries the MEM1 anchor + surrogate commitment),
2. the v1 chain row it testifies about (frozen, read-only),
3. the **registry** — the claim window where seats reserve the right to testify.

Without (3) two seats could append competing repairs for the same v1 row
(equivocation), or an unfalsifiable repair could slip in unclaimed. The registry
is the coordination surface, not a source of truth — the chain and the tapes are.

## Artifact

`memory/biography/anchor_registry.jsonl` — append-only, one claim per line.

```json
{"schema": "anchor_registry.v1",
 "ts": "2026-08-27T15:3xZ",
 "v1_leaf_hash": "<64hex — the elder row being testified about>",
 "v1_window": {"start_ts": "...", "end_ts": "...", "source": "<tape class>"},
 "claim": "repair" | "gap",
 "claimed_by": "<seat_id from mag/seats.py>",
 "derive_spec": "<path to rib/recipe that regenerates the surrogate>",
 "tapes_sha256": "<sha256 of the tape slice the derivation reads>",
 "status": "claimed" | "committed" | "refuted",
 "v2_leaf_hash": null | "<64hex once the v2 knot lands>",
 "proof_sha256": null | "<sha256 of surrogate -> re-derives v1 leaf hash or witness fields>"}
```

## Invariants (each is checkable by a dumb verifier)

1. **Append-only.** No row is ever edited; status advances by appending a new
   row with the same `v1_leaf_hash` + a later `ts` (claim → committed/refuted).
   The registry has no tip to rewrite; integrity = tail-append under `verkle_lock`.
2. **One live claim per v1 row.** For any `v1_leaf_hash`, at most one row may be
   in `status: claimed` at a time. A second claim for a row with a live claim is
   refused (equivocation gate — same rule as seat signing).
3. **Claim-before-compile.** A v2 leaf carrying a MEM1 anchor into v1 is invalid
   unless a `claimed` row exists that predates the leaf's `ts`. This is the check
   `mmr` verification runs.
4. **Committed ⇒ proof attached.** Transition `claimed → committed` requires
   `v2_leaf_hash` + `proof_sha256` non-null. Re-derivation recipe lives at
   `derive_spec` and must run deterministically ($0, local).
5. **Refuted ⇒ gap typed.** Transition `claimed → refuted` appends with a
   `refuted_by` note and, per the law of repairs, the seat then files a
   `claim: "gap"` row (irrecoverable) — the gap becomes a committed typed fact
   rather than silence.
6. **Gap rows are permanent.** A `gap` committed row never transitions. Healing
   found later = a NEW `repair` claim citing the gap row (the room learns, the
   wall is never amended).
7. **Per-tree scoping.** `v1_window.source` + `claim` kind name the tree
   (`session`, `digest`, `genesis_cite`). Cross-tree claims are refused — an
   anchor cites its own tree only (the bridge stays honest about direction:
   v2→v1 only, never v1→v2).

## Workflow (the loop)

```
sweep (C) -> classifies flagged v1 rows: derivable? from which tape?
  -> for derivable:   seat APPENDS claim:"repair" row (status claimed)
  -> for not:         seat APPENDS claim:"gap" row (committed immediately,
                      operator_sig optional at registry level, required on leaf)
compile -> riddler.repair.v1 compiler reads ONLY claimed rows, regenerates
  surrogates, writes v2 leaves with MEM1 anchors
verify -> dumb verifier: for each committed row, run derive_spec, hash the
  surrogate, compare to proof_sha256; mismatch => row auto-refuted + alarm
```

## Acceptance commands (for whoever builds — rib-ready)

```
python -m mag.anchor_registry claim --v1 <leaf_hash> --claim repair --derive-spec <path> --tapes <sha>
python -m mag.anchor_registry commit --v1 <leaf_hash> --v2 <leaf_hash> --proof <sha>
python -m mag.anchor_registry verify          # re-derive every committed row
python -m mag.anchor_registry audit           # invariant 2/3/7 violations
```

Module: `mag/anchor_registry.py` (~150 lines: jsonl append under `verkle_lock`,
the four verbs, invariant checks pure/deterministic). Then the MMR spec's
"who signs" section governs leaf-side; registry stays seat-level, append-cheap.

## What this unblocks

First legal v2 write: the compiler can run against sweep output the moment
invariant 3 is checkable. The room-that-remembers bridge (v2 anchors into v1's
walls) uses the SAME registry in reverse citation direction? No — it does not.
Bridge = memlang anchors INTO v1 is still a separate build (v1 is frozen; any
bridge writes are v2-side citations, which is exactly this registry). The freeze
decision remains the operator's, made deliberately.
