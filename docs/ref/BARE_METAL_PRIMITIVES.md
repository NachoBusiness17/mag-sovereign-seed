# BARE METAL PRIMITIVES — the common language layer (2026-08-28)

Source: History of Computing Hardware (structural invariants extracted).
Thesis: the models don't need to KNOW the history — the MCP layer serves the
history's surviving INVARIANTS as operations. Any model, 1.7B to 5.3, drives
the same primitives. The fundamentals become the tool schema; that's the
common language between all our models, without them knowing.

## THE INVARIANTS THAT SURVIVED EVERY ERA → MCP OPS

| Invariant (200 years old) | Fleet embodiment | MCP primitive op |
|---|---|---|
| Symbolic representation: quantity by physical state | the event.v1 stream, the ledgers | `state.write` / `state.read` |
| Finite ops composed into procedures | the MCP tool set itself | (the tool set IS this) |
| Store/mill separation (Babbage's words) | ledgers (store) vs governor (mill) | `store.append` / `mill.run` |
| Conditional branching + loops (Babbage) | cadence loop, covenant branches | `flow.branch` / `flow.loop` |
| Stored program: instructions as data (deepest invariant) | **THE RIBS** — ribs are stored programs | `rib.compile` / `rib.execute` |
| Addressing + sequencing | event seq + prev_hash chain | `stream.address` |
| Shannon's bridge: logic ↔ circuits | hooks: laws ↔ tool calls | `gate.check` |
| Reliability as first-class constraint | wedge ledger, the bell | `ledger.audit` |
| Generality costs speed | the steal matrix | `route.cheapest_capable` |
| I/O abstraction: the human boundary | the salon, the receipt cards | `surface.render` |

## THE VALIDATION (from the history itself)

- "Each generation replaces a slower physical substrate for the previous
  one's logic primitive" = the elder's re-summoning law, stated by hardware.
- "Digital won because analog can't be reliably repeated" = receipts over
  distillates, stated by 1850.
- "Generality costs speed" = the steal matrix, stated by Turing.
- "Instructions as data" = the ribs, the stored-program concept applied to
  fleet doctrine — the deepest single invariant, and the fleet's ribs
  implement it natively.

## THE COMMON LANGUAGE DESIGN

Every model drives the same ~10 primitive ops over MCP. The ops embody the
invariants. A 1.7B blade and the 5.3 brain speak identically at this layer —
the intelligence difference lives in HOW they compose the primitives, not in
WHICH primitives exist. Composition quality is the intelligence; the language
is common.

The history's lesson for the schema: primitives stay FEW (Babbage's failure
was richness; Zuse's win was binary simplicity), DETERMINISTIC (digital beat
analog on repeatability), and COMPOSABLE (stored program = composition beats
rewiring). Any op that fails those three tests doesn't enter the language.
