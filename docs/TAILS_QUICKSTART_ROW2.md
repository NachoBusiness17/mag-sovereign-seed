# TAILS LEDGER QUICKSTART — Minting & Verifying Row 2 (External Communities)

*Companion to [`TAILS_LEDGER_SPEC_DECENTRALIZED_COMMUNITIES.md`](TAILS_LEDGER_SPEC_DECENTRALIZED_COMMUNITIES.md). Zero dependencies (Python 3.10+ stdlib only).*

---

## 1. Verify the Existing Ledger (Row 1 Genesis)

From the root of the repository:

```bash
python mag/verify_tails.py
```

Expected output:

```text
[verify_tails] PASS: VERIFIED 1 row(s) - chain head 7681b91ea93d
```

---

## 2. Generate a Pre-Linked Row 2 Template

Run `verify_tails.py --template` to print a ready-to-edit JSON template with `seq: 2` and `prev_hash` automatically bound to the current chain head (`7681b91ea93da06345320a3729e18cefd320080d72790ff44266ed810dcd74ec`):

```bash
python mag/verify_tails.py --template
```

Output (`15` lines):

```json
{
  "seq": 2,
  "ts": "2026-10-17T18:46:55+00:00",
  "prev_hash": "7681b91ea93da06345320a3729e18cefd320080d72790ff44266ed810dcd74ec",
  "author": "community-a:builder-handle",
  "scorer": "community-b:independent-validator",
  "payer": "community-c:treasury-or-sponsor",
  "artifact_uri": "path/or/url/to/reproducible-artifact",
  "artifact_sha256": "REPLACE_WITH_64_HEX_SHA256_OF_ARTIFACT",
  "witness_reasons": [
    "scorer witness 1: independent replay command exited 0 and matched artifact_sha256",
    "scorer witness 2: falsifier boundary tested on negative fixture and rejected as expected"
  ],
  "expected_falsifier": "replay command exits non-zero or output sha256 diverges if artifact is tampered",
  "settlement_ref": "tx_hash_or_git_commit_ref",
  "row_hash": "917a7469387319a03681b3f108ff88b8266dad61fc56ab0a68088941c84f3258"
}
```

---

## 3. Five Rules Enforced by `verify_tails.py`

Every appended line in `tails.jsonl` must satisfy:

1. **Chain Continuity (`prev_hash`):** Row $N$'s `prev_hash` equals Row $N-1$'s `row_hash` (Row 1 is `"0" * 64`).
2. **Canonical Digest (`row_hash`):** `row_hash` equals the SHA-256 hex digest of `json.dumps(row_without_row_hash, sort_keys=True, separators=(",", ":"))`.
3. **Pairwise Separation of Powers:** `len({author, scorer, payer}) == 3`, and `author` never appears in `expected_falsifier` (an author cannot write a self-controlled falsifier).
4. **Two-Witness Anti-Mimicry Quorum:** `witness_reasons` contains at least **2 distinct** non-empty verification statements (`len(set(witness_reasons)) >= 2`), and `expected_falsifier` is non-empty.
5. **16-Row Reciprocal Collusion Guard:** Within a sliding window of $W=16$ rows, if entity $A$ scored entity $B$ (`w["author"] == row["scorer"] and w["scorer"] == row["author"]`), $B$ cannot score $A$.

---

## 4. Recompute `row_hash` & Append Row 2

After filling in your fields in `row2.json`, compute the canonical `row_hash` and append a single compact JSONL line to `tails.jsonl`:

```bash
python -c '
import json
from mag.verify_tails import canonical_row_hash
row = json.load(open("row2.json", encoding="utf-8"))
row["row_hash"] = canonical_row_hash(row)
with open("tails.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(row, separators=(",", ":")) + "\n")
'
python mag/verify_tails.py
```
