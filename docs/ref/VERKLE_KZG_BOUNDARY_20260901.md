# Verkle/KZG Boundary — What We Have, What It Means

Status: shared explanatory note · 2026-09-01

## The clean distinction

Mag's live `verkle_knot` organ is a content-addressed, append-only SHA-256
Merkle ledger. It has leaves, prefix roots, sibling-path membership proofs, a
tip, a lock, and repair tooling. It is useful and currently passing its chain
and proof gates.

It is **not** yet a KZG Verkle tree. The name describes the intended role and
upgrade path; it does not prove that polynomial commitments exist in the
runtime.

The executable facts are in `mag/verkle_knot.py`: leaf hashing uses
`SHA256("leaf:" || canonical_json)`, internal hashing uses
`SHA256("node:" || left || ":" || right)`, and an odd node is duplicated. The
proof is an index plus sibling hashes. There is no finite-field polynomial,
elliptic-curve point, SRS, or pairing check in that path.

## KZG in one page

KZG (Kate–Zaverucha–Goldberg) commits to a polynomial without publishing all
of its coefficients.

Given a polynomial

```text
p(X) = c0 + c1 X + ... + cd X^d
```

the setup publishes curve points `[τ^0]G1, [τ^1]G1, ...` for a hidden setup
value `τ`. The commitment is:

```text
C = [p(τ)]G1 = c0[τ^0]G1 + c1[τ^1]G1 + ... + cd[τ^d]G1
```

To prove that `p(z) = y`, the prover forms:

```text
q(X) = (p(X) - y) / (X - z)
π = [q(τ)]G1
```

The verifier checks one pairing relation:

```text
e(C - [y]G1, G2) = e(π, [τ]G2 - [z]G2)
```

The point is not that the verifier knows the whole polynomial. It knows a
small commitment and checks a local opening against that commitment. That is
why KZG can make a wide Verkle node practical: 256 child slots are encoded as
values of one degree-255 polynomial, and a path proves one selected slot per
level.

## Mapping to our system

| Our organ | Current meaning | Genuine KZG/Verkle counterpart |
|---|---|---|
| `verkle_chain.jsonl` | ordered session-leaf history | canonical state/version history |
| `verkle_tip.json` | current SHA-256 root pointer | published root commitment |
| `*.knot.json` | leaf payload and its SHA-256 fingerprint | immutable leaf bytes / field value |
| sibling path | binary Merkle membership proof | 32 wide-node KZG openings plus child-link hashes |
| `topic_evolution.json` | derived view | derived index, never root authority |
| Q-state / RIB / game stores | separate memory lineages | separate namespaces bridged by explicit hashes |
| `by-session_*.json` | convenience pointer, currently truncated | must become collision-free content index |

## What defragmentation means here

Defragmentation is not flattening every memory into one giant chain. It is
making the seams explicit:

1. Freeze the current root as `legacy_sha256_merkle.v1`.
2. Preserve source bytes and backups; build a derived index containing path,
   schema, content hash, lineage, chain index, and root membership.
3. Replace truncated session pointers with full-session or hash-addressed keys.
4. Keep Q-state, RIB/trajectory, game/world, and biography as distinct
   lineages with bridge receipts.
5. Add `verkle_kzg.v1` beside the legacy root, with canonical bytes, pinned
   BLS12-381 parameters, a public SRS digest, cross-implementation fixtures,
   and neutral verification.
6. Publish dual-root receipts only after the KZG implementation verifies the
   same frozen leaves; never silently reinterpret an old SHA root as a KZG root.

The immediate recovery rule is therefore: repair missing leaf files only when
session, filename, and leaf hash agree exactly; preserve alternate amended
variants as candidates, not replacements.

## Primary references

- Kate, Zaverucha, Goldberg, *Constant-Size Commitments to Polynomials and
  Their Applications*, ASIACRYPT 2010: [IACR paper PDF](https://www.iacr.org/archive/asiacrypt2010/6477178/6477178.pdf).
- Kate, Zaverucha, Goldberg, extended *Polynomial Commitments* report:
  [CACR 2010-10 PDF](https://cacr.uwaterloo.ca/techreports/2010/cacr2010-10.pdf).
- Hash-to-field and `expand_message_xmd`: [RFC 9380](https://www.rfc-editor.org/rfc/rfc9380.html).
- Verkle overview and vector-commitment motivation: [Ethereum Verkle trees](https://ethereum.org/roadmap/verkle-trees/).
- 256-way Verkle structure: [Ethereum Foundation structure note](https://blog.ethereum.org/2021/12/02/verkle-tree-structure).
- Reproducible local construction: `docs/REPRO_SERIALIZE_SPEC.md`.

The operational conclusion is simple: our current SHA ledger is a sound
recovery substrate. KZG is a future cryptographic layer with stricter math,
setup, serialization, and test obligations—not a label we should backfill onto
the existing implementation.
