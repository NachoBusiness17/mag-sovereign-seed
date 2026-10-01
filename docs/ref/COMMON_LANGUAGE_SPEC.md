# COMMON LANGUAGE SPEC v1 — the fused constitution (2026-08-28)

All four chairs delivered (PRIMITIVES_{grok,codex,deepseek,zai}.md). This is
the fused spec: the corrected minimal op set, its governance, and the schema
laws. Supersedes the ~10-op table in BARE_METAL_PRIMITIVES.md.

## THE MODEL-FACING ISA — THREE SYSCALLS (identical for 1.7B and 200B)

| Op | Args | Returns | Failures |
|---|---|---|---|
| `store.read` | addr: seq \| content-hash \| {kind, from_seq, limit} | {events[], next_seq, head_hash} | NOT_FOUND, GAP, DENIED |
| `intent.append` | kind (closed enum), body, idempotency_key, cause_id, expected_head | OK{seq,hash} or DUPLICATE{seq,hash} | INVALID_ARGS, CONFLICT, COVENANT, DENIED |
| `rib.exec` | rib_id (content-hash), args (that rib's schema) | {status, receipt_hash, result} | UNKNOWN_RIB, REFUSED, FAILED, TIMEOUT |

Unix survived on read/write/exec. Raft mutates with one op. The fleet's
model-facing surface is three. Everything else composes from these or was
never a primitive.

## GOVERNOR-ONLY (never exposed to models)

- `commit` — sole mutator of state; content-hash; O_EXCL; **the gate lives here**
- `rib.compile` — verifier-passing tapes only
- `route` — the steal matrix; blades never see it
- `fold` — verify(): recompute content + covenant fold

## SURFACE-ONLY

- `render` — idempotent projection over the canonical snapshot; cache keyed by
  (offset, hash); **zero model calls, forever** (zai: "cat is mud").

## THE SCHEMA LAWS (codex, ergonomics for weak drivers)

1 required object, 1–3 scalar fields, 0 optional fields unless they buy real
safety. Split ops rather than make them expressive — a weak model succeeds on
two small ops and fails on one large expressive one.

## GOVERNANCE (elder, ratified by grok's one-writer derivation)

- Primitives are **constitutional amendments**: governor proposes (a repeated
  pattern across ≥3 surfaces, incomposable from existing ops), elder ratifies.
  No committee. Languages that grew by committee died; by dictator survived.
- **TMR for load-bearing ops**: mill-class executes on three seats, governor
  commits the majority. Hallucination cannot corrupt the stream alone.
- **Write-ahead journaling**: every state.write appends raw to event.v1 before
  interpretation; corruption replays from the last clean beat.
- **The bell as circuit breaker**: 3 mill failures in one beat → read-only
  mode. Sacrifice the beat to save the fleet.

## ECONOMICS (zai)

- Right-sized: three ops carry the traffic; the rest of the brochure was
  workflow engines larping as primitives.
- Versioning: breaking an op after N models depend on it costs N× migration —
  hence the closed enum, the content-hash addresses, and the elder's veto.
- Buy-vs-build: existing MCP tool standards may implement ops internally, but
  the THREE-SYSCALL SURFACE is fleet-owned and never delegated.

## PRESERVED DISPUTES (testable)

- Whether TMR everywhere is affordable at blade prices, or only for
  mill-class ops (zai: cost center; elder: correctness floor). [open]
- The exact similarity threshold for the self-steal gate's semantic layer
  (codex: 80% default; grok: derive from AST, not strings). [open]

## THE LAW

Three syscalls. Four mill ops. One window. Everything else composes —
or was never a primitive. Files over slogans. The language is a floor only
if ring-0 stays off the floor.
