# REPRO_SERIALIZE_SPEC — canonical serialization & root computation (v1)

**Status: NORMATIVE.** Fills the gap flagged in `docs/BUILD_FOR_ZERO_BLUEPRINT.md` §7 for §4.3's
deterministic seam. A second engineer builds two independent implementations from this document
alone; §5 defines the assertions they must pass to prove byte-identical roots.

Notation: `||` = concatenation; `be16/be32/be64(x)` = unsigned big-endian, 2/4/8 bytes; `hex()`
lowercase hex; lengths in bytes. "MUST/SHALL" per RFC 2119. All multi-byte integers are big-endian.

---

## 1. Canonical value encoding (CVE)

Every logical value serializes to exactly one byte sequence:

```
null  := 0x00
false := 0x01
true  := 0x02
uint  := 0x03 || be64(n)                      # 0 ≤ n < 2^64
bytes := 0x04 || be64(len) || data
text  := 0x05 || be64(len) || data            # UTF-8, canonical per §1.1
list  := 0x06 || be64(count) || item*count
map   := 0x07 || be64(count) || (key value)*count   # keys: text, ordered per §1.2
```

Parsers MUST reject: any lead tag ≥ 0x08; truncated payload; any trailing byte after the
top-level value; duplicate or out-of-order map keys; ill-formed UTF-8 (overlong, surrogate
halves, > U+10FFFF); text not in NFC form (§1.1).

### 1.1 Text canonicalization

The logical value of text is its canonical form: (1) replace each CR (U+000D) and each CRLF pair
with a single LF (U+000A); (2) apply Unicode Normalization Form C (NFC). Encoders MUST canonicalize
before encoding; decoders MUST independently reject bytes that are not already canonical (defense
in depth). No other transformation (no trimming, no case folding) is permitted.
*Deciding constraint:* EOL mangling is the dominant real-world corruption; NFC preserves meaning,
NFKC silently changes it.

### 1.2 Map ordering and uniqueness

Map keys sort by unsigned byte-wise lexicographic comparison of their encoded (canonical UTF-8)
bytes; a proper prefix sorts before its extension. Keys are unique — duplicates are a parse error.
The logical map is a key→value function; order carries no information.

### 1.3 Options, structs, versioning

- Optional field: `0x00` (absent) or `0x01 || value` (present). Any other prefix byte is a parse error.
- Structs are schema-defined: fields encode in fixed schema order; no field names on the wire.
- Every versioned blob opens with an ASCII magic tag and a `be16` version. Rules: version 1 is
  exactly this document; a later version may append new tags/leaf types but MUST NOT change the
  meaning of any existing byte sequence; readers MUST reject unknown versions.

### 1.4 Injectivity (no two byte sequences encode the same logical value)

Distinct lead tags disambiguate types; fixed widths plus explicit lengths remove framing ambiguity;
UTF-8 is injective on Unicode scalar values; NFC makes text bytes a function of the logical text;
sorted unique keys make map bytes a function of the logical map; options carry an explicit presence
byte. Therefore `encode` is injective and `decode∘encode = id`. Corollary: byte-equality of
encodings **is** equality of logical values — which is what makes the acceptance test in §5 sound.

## 2. Cryptographic primitives

- **Hash:** SHA-256 (FIPS 180-4).
- **Curve:** BLS12-381. G1 points serialize compressed, 48 bytes, ZCash/ipc flag layout (bits: C,
  I, S; canonical sign chosen by S). Point at infinity = `C0` followed by 47 zero bytes.
- **Field:** the BLS12-381 scalar field Fr,
  r = `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001`.
  Field elements serialize as `be32(e)` with e < r; parsers MUST reject e ≥ r.
- **hash_to_field(msg, dst):** `expand_message_xmd` with SHA-256 per RFC 9380 §5.3, L = 48, m = 1;
  reduce the 48 bytes mod r once. DSTs (ASCII): `"BFZ1.H.LEAF"` (leaf fingerprint → field),
  `"BFZ1.H.NODE"` (child commitment → field).
- **SRS (structured reference string):** the file `trusted_setup.json` (v1) from the Ethereum KZG
  ceremony. Use G1 powers [τ⁰ … τ²⁵⁵] and G2 powers [τ⁰, τ¹]. The canonicalized point list is
  pinned by its SHA-256 digest; implementation A computes and publishes the digest with the seed,
  implementation B MUST match it (assertion T10). *Deciding constraint:* a self-generated τ lets
  its generator forge every proof; hash-derived points are not a power basis and cannot commit at
  all; the public ceremony's ≥1-honest-contributor assumption is the minimum trust available.

## 3. Leaves, fingerprints, state blob

### 3.1 Leaf format (the frozen hashed artifact)

```
leaf := "BFZL" || be16(ver=1) || be16(type_id) || be16(flags=0) || be64(payload_len) || payload
```

- `type_id 0x0001 POLICY_TEXT`: payload = CVE `text` — the distilled policy as frozen text.
- `type_id 0x0002 OP_LOG`: payload = CVE `list` of CVE `map`s. Reserved; identical rules.
- `flags` MUST be 0 in v1; parsers MUST reject otherwise.

Once frozen, leaf bytes are immutable — the bytes ARE the artifact.

### 3.2 Fingerprint

```
FP(leaf) := 0x01 || SHA-256(leaf_bytes)        # 33 bytes
```

`0x01` is the algorithm prefix (SHA-256); a future algorithm takes `0x02` with its own version bump.

### 3.3 State blob (the canonical starting state)

```
state := "BFZ1" || be32(ver=1) || be64(leaf_count) || record*
record := CVE_text(key) || be64(len) || leaf_bytes
```

Records are sorted by key bytes with the §1.2 comparator; `leaf_count` MUST equal the record count
(parse error otherwise). Two states with the same logical leaves produce identical blobs regardless
of insertion history.

## 4. Root computation (256-ary, KZG commitments)

### 4.1 Path derivation

`path(key) := SHA-256(utf8(canonical(key)))`, 32 bytes; byte d is the branch taken at depth d
(depth 0 = root). Tree depth is fixed at 32. Security rests on SHA-256 collision resistance
(stated assumption; a collision breaks path binding).

### 4.2 Node values and commitments

For a node at depth d (0 = root … 31 = leaf-parent), V[i] is the value at child slot i:

- slot empty: `V[i] = 0` (field zero);
- depth 31: `V[i] = hash_to_field(FP(leaf_i), "BFZ1.H.LEAF")`;
- depth < 31: `V[i] = hash_to_field(compress48(C_child_i), "BFZ1.H.NODE")`, where `C_child_i` is
  the child node's commitment (below) and `compress48` is the §2 G1 serialization.

**Node commitment:** interpolate the unique polynomial f over Fr, deg ≤ 255, with f(i) = V[i] for
i = 0…255 (Lagrange over the index domain {0…255}; convert to monomial coefficients; naive O(n²)
at n = 256 is acceptable and fully deterministic). Then

```
C = Σ_{j=0..255} c_j · SRS_G1[j] ∈ G1
```

**Root** R := compressed commitment of the depth-0 node (48 bytes). Empty state:
R = infinity (`C0` || 47×`00`). Internal point arithmetic is exact, so every correct implementation
lands on the same point; the compressed serialization is canonical.

**Published root commitment** (human/seed-facing wrapper; the 48 bytes R are *the* root):
`"BFZ1:ROOT:1:" || hex(R) || ":" || hex(SHA-256(state_blob))`.

### 4.3 Proof bundle and neutral verification

```
proof := "BFZP" || be16(ver=1) || CVE_text(key) || path(32) || FP(33)
      || π_0 || v_0 || π_1 || v_1 || … || π_31 || v_31
      || C_1 || C_2 || … || C_31
```

where C_d = commitment of the depth-d node (C_0 = R, the supplied root), v_d = V[path[d]], and
π_d = q_d(τ) ∈ G1 with q_d(x) = (f_d(x) − v_d)/(x − path[d]) (KZG quotient witness).

**Neutral verifier** — consumes ONLY (R, leaf_bytes, proof); no tree, no state:

1. Parse the bundle; subgroup-check every G1 point; reject field elements ≥ r.
2. Recompute `path(key)` and require equality with the bundle's path; recompute `FP(leaf_bytes)`
   and require equality with the bundle's FP.
3. For d = 0…31 check the KZG opening of C_d at z = path[d] to value v_d:
   `e(C_d − v_d·G1, [1]_2) = e(π_d, [τ]_2 − z·[1]_2)`, where G1 := SRS_G1[0].
4. For d = 0…30 check `v_d = hash_to_field(compress48(C_{d+1}), "BFZ1.H.NODE")`.
5. Check `v_31 = hash_to_field(FP(leaf_bytes), "BFZ1.H.LEAF")`.

Accept iff all checks hold. Batching the 32 pairings via a random linear combination is a
permitted optimization; the per-level form above is the conformance format and must be produced
by any conforming prover. Non-inclusion proofs are out of scope for v1 (deferred; an empty slot
opens to v = 0, and step 5 cannot hold with v_31 = 0).

## 5. Acceptance test

### 5.1 GENESIS-1 — the fixed starting state

Exactly three leaves (payload text verbatim, `\n` = LF):

| key | type | payload |
|---|---|---|
| `seed.marker` | POLICY_TEXT | `44 28 K13 e4 Fool\n` |
| `seed.branch` | POLICY_TEXT | `My branch is not supposed to be yours. It's simply supposed to exist alongside yours.\n` |
| `policy.v1` | POLICY_TEXT | `PLACEHOLDER — distilled policy text is published separately as a leaf (blueprint §7); until then this exact string is the test payload.\n` |

Implementation A (reference) computes and publishes with the seed a `fixtures.json` containing the
hex of every encoding in this section (CVE corpus, leaves, state blob, fingerprints, root, proof
bundles for all three keys). Implementation B regenerates every constant independently.

### 5.2 Corpus C (shared inputs for T1–T3)

null; true; false; uint 0; uint 18446744073709551615; bytes `` (empty); bytes `00FF`;
text `` (empty); text `Fool`; text `é` supplied both precomposed and as `e`+U+0301 (must yield
identical bytes); text `line1\nline2\n` supplied with CRLF and CR variants (identical bytes);
list `[true, "a", []]`; map `{"Z": 1, "a": 2, "á": 3, "ab": 4}` (key order exercise); the three
GENESIS-1 leaves; the GENESIS-1 state blob.

### 5.3 Assertions (run in both directions A↔B)

- **T1 round-trip:** for every x in C: `decode(encode(x)) = x` and
  `encode(decode(encode(x))) = encode(x)`.
- **T2 cross-impl byte equality:** `encode_A(x) = encode_B(x)` for every x in C.
- **T3 rejection suite** (parser must fail on each):
  `08` · `04 0000000000000005 61` (short payload) · `00 00` (trailing byte) ·
  map with duplicate key `a` · map with keys `b`,`a` in that order ·
  `05 0000000000000003 65 CC 81` (non-NFC) · `05 0000000000000003 ED A0 80` (surrogate) ·
  `05 0000000000000002 C0 AF` (overlong) · `05 0000000000000002 0D 0A` (non-canonical EOL) ·
  map with non-text key · proof `v_d` bytes ≥ r.
- **T4 fingerprints:** identical FP hex for all three GENESIS-1 leaves; A's published values match.
- **T5 roots:** `R(GENESIS-1)` byte-identical (48 bytes) across A and B; `R(empty state)` = the
  infinity encoding in both.
- **T6 determinism:** three fresh-process reruns per implementation; roots identical.
- **T7 proof cross-verification:** A's proof for `seed.marker` verifies under B's verifier; roles
  swapped, all three keys.
- **T8 tamper exhaustion:** for every byte index of leaf, key, path, FP, every π_d, v_d, C_d:
  flipping any single bit must make verification fail or the parser reject.
- **T9 neutrality:** the verifier's entire input set is (R, leaf_bytes, proof) — verified by
  inspecting the verifier's API signature.
- **T10 SRS pin:** B's loaded SRS matches the published SHA-256 digest.

**Pass criterion:** T1–T10 all true in both directions. Any failure means reproduction has
provably failed (blueprint §4.2), and the failing assertion names the broken seam.

## 6. Tradeoffs, decided

| Decision | Rejected alternative | Deciding constraint |
|---|---|---|
| NFC + EOL→LF for text | NFKC; nothing | NFKC alters meaning; no rule invites editor corruption |
| fixed-width big-endian ints | varints | simpler audit surface; no minimality edge cases |
| Lagrange over {0…255} | roots-of-unity domain | no generator to pin; O(n²) is cheap and deterministic at n=256 |
| Ethereum-ceremony SRS | self-made τ; hash-derived points | unknown τ is mandatory; hash points cannot form a power basis |
| per-level proof format | aggregated single proof | conformance format must be simplest; aggregation must not change R |
| 32-byte SHA-256 paths | content-addressed paths | fixed depth decouples identity from size; collision assumption stated |
