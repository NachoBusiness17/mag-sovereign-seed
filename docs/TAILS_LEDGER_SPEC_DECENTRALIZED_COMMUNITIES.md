# Tails Ledger Specification for Decentralized Communities
v1.0 · 2026-10-17 · open artifact: run it unchanged or fork it in public

No author, no operator desk. A community runs its own ledger or it has none.

## Preamble
A constitution names the lines a community won't cross. A tails ledger proves whether anyone crossed them to do real work.

Belief, rank, and loyalty are cheap to fake; work leaves a tail that a stranger can re-run. This specification defines an append-only, chain-agnostic work ledger small enough to live in a single JSONL file, a Git repository, or an on-chain settlement contract.

---

## I. Object Clause (Work Only)
The ledger records **completed, verifiable work entries** and nothing else.
- **Admissible:** artifacts, code, audits, datasets, translations, physical deliverables with independent receipts, and scored verifications.
- **Inadmissible:** belief attestations, status titles, membership rolls, vows, vibes, or prophecies. If an entry cannot fail a verification check, it is not a ledger row.

## II. Row Schema (Append-Only, Hash-Chained)
Every row is a single newline-delimited JSON object (`tails.jsonl`). Nothing is edited or deleted; a correction or reversal is a new row whose `corrects` field points to the earlier `row_hash`.

```json
{
  "seq": 1,
  "ts": "2026-10-17T00:00:00Z",
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "author": "id_or_pubkey_of_worker",
  "scorer": "id_or_pubkey_of_verifier_1,id_or_pubkey_of_verifier_2",
  "payer": "id_or_pubkey_of_settler_or_bounty_pool",
  "what": "Short description of the deliverable and its content hash",
  "artifact_sha256": "64_hex_char_sha256_of_deliverable_bytes",
  "how_to_verify": "Deterministic command or procedure any stranger can run to reproduce the check",
  "expected_falsifier": "The specific observation that would mark this work invalid or refuted",
  "witness_reasons": [
    "witness_1: independent mechanism/reason why the artifact passes the check",
    "witness_2: independent mechanism/reason why the artifact passes the check"
  ],
  "settlement_ref": "tx_hash_or_receipt_uri_or_unsettled",
  "corrects": null,
  "row_hash": "sha256(seq|ts|prev_hash|author|scorer|payer|artifact_sha256|how_to_verify|expected_falsifier|settlement_ref)"
}
```

---

## III. The Eight Structural Clauses

1. **Separation of Powers (No One-Address Crown)**
   For any row to count as settled, `author` (who did the work), `scorer` (who verified it), and `payer` (who released the bounty or settlement) **must be distinct keys/actors**. Self-scored or self-paid rows are drafts, never tails.
2. **Anti-Mimicry & Two-Witness Replay**
   Every `how_to_verify` procedure must be independently re-executable from the artifact bytes. A valid tail requires **at least two independent witnesses** (`scorer` keys on different machines, substrates, or operators) whose replay certificates match the artifact hash.
3. **Reason Clause (Score the Why, Not Just the Pass)**
   Adopters and witnesses must state a **falsifiable reason** (`expected_falsifier` + `witness_reasons`) explaining *why* the artifact works or passes. Two witnesses rubber-stamping `"PASS"` without a specific mechanism fail semantic agreement and do not seal a row.
4. **Object Clause Enforcement**
   Any row lacking `artifact_sha256`, `how_to_verify`, or `expected_falsifier` is rejected at write time by the ledger verifier.
5. **Tempo Split (Fast Coordinates, Slow Amends)**
   - **Fast layer** (chat, boards, ephemeral queues): routes tasks and coordinates drafts at any speed.
   - **Slow layer** (this ledger + the constitution): appends verified tails and amends rules after a mandatory public waiting window.
   - **Invariant:** The fast layer never amends the slow layer. Urgency is never an exemption.
6. **Authorless Diffusion (Ship the Instrument, Never Run Their Hall)**
   This specification carries no central authority, backdoor, or mandatory relay. Any community instantiates its own `tails.jsonl` and holds its own keys. Whoever writes the tool never arbitrates another community's rows.
7. **First-Tail Ceremony (Unhamed Row One)**
   Row `seq: 1` of a live ledger must be a **real third-party work deliverable**, verified by two witnesses and settled (however small the amount) within days of opening the ledger — never a founder pre-mine, genesis tribute, or manifesto declaration.
8. **Parameterized Flip Condition (Belief-Fed → Work-Fed)**
   A community transitions from *belief-fed* to *work-fed* on the timestamp of its **first paid, two-witness-verified third-party tail**.
   - **Sunset parameter:** If `30 days` elapse from ledger publication with zero settled third-party tails, the ledger automatically marks itself `DORMANT / STORY-ONLY` until a real row lands.

---

## IV. Anchoring Options (Pick One or Layer Gradually)

1. **Tier 0 — Plain Git + JSONL (`$0`, Day 1):**
   Keep `tails.jsonl` in a public Git repository with a 30-line Python/Node pre-commit hash-chain + schema check. Every clone is a full mirror.
2. **Tier 1 — Content-Addressed Mesh / MCP Sync (`$0`, Peer-to-Peer):**
   Pin `tails.jsonl` and artifact hashes across peer nodes so every participant verifies `row_hash` and `artifact_sha256` before accepting an update.
3. **Tier 2 — On-Chain Settlement Rails (TON Jetton / Bittensor Subnet / L2):**
   Anchor periodic `row_hash` roots on-chain and wire `settlement_ref` to an atomic payout contract (where the quorum digest signs `taskId + workerAddr + artifact_sha256 + payoutAmount` before releasing funds).

---

## V. Reference Verifier Rule (20-Line Contract — Hardened via Multi-Body Band Audit 2026-10-17)
A ledger file is valid if and only if for every row $i \ge 1$:
1. $\text{row}_i.\text{prev\_hash} = \text{row}_{i-1}.\text{row\_hash}$ (with $\text{row}_1.\text{prev\_hash} = 0^{64}$).
2. $\text{row}_i.\text{row\_hash}$ matches the recomputed SHA-256 of its canonical fields (including validator/witness key fingerprints when Tier 2+ anchored).
3. **Pairwise Separation of Powers:** $|\{\text{author}, \text{scorer}, \text{payer}\}| = 3$ (strictly prevents `scorer == payer` proxy collapse) and $\text{author} \notin \text{expected\_falsifier}$ (prevents self-referential falsifiers).
4. **Non-Boilerplate Witness Quorum:** $|\text{set}(\text{witness\_reasons})| \ge 2$ (distinct non-empty justifications) and $\text{expected\_falsifier} \neq \emptyset$.
5. **Sliding-Window Reciprocal Collusion Guard ($W = 16$ rows):** No `(author, scorer)` pair may invert roles (`row_j.author == row_i.scorer` and `row_j.scorer == row_i.author`) within a 16-row window without an independent third-party scorer intervening:
```python
def verify_row_spirit(row, window_rows):
    roles = {row["author"], row["scorer"], row["payer"]}
    if len(roles) < 3 or row["author"] in str(row.get("expected_falsifier", "")):
        return False, "ROLE_COLLAPSE_OR_SELF_FALSIFIER"
    reasons = {r.strip() for r in row.get("witness_reasons", []) if r and r.strip()}
    if len(reasons) < 2:
        return False, "DUPLICATE_OR_MISSING_WITNESS_REASONS"
    if any(w["author"] == row["scorer"] and w["scorer"] == row["author"] for w in window_rows[-16:]):
        return False, "RECIPROCAL_SCORER_SWAP_IN_WINDOW"
    return True, "OK"
```
