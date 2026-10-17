#!/usr/bin/env python3
"""verify_tails.py — Reference 5-rule verifier & row minter for tails.jsonl.

Implements Section V of TAILS_LEDGER_SPEC_DECENTRALIZED_COMMUNITIES.md:
  1. prev_hash chain continuity (row_1.prev_hash == "0"*64)
  2. Canonical SHA-256 row_hash match
  3. Pairwise separation of powers: len({author, scorer, payer}) == 3 and author not in expected_falsifier
  4. Non-boilerplate witness quorum: len(set(witness_reasons)) >= 2 and expected_falsifier non-empty
  5. Sliding-window reciprocal collusion guard (W=16 rows)
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LEDGER = (
    os.path.join(HERE, "tails.jsonl")
    if os.path.exists(os.path.join(HERE, "tails.jsonl"))
    else os.path.join(os.path.dirname(HERE), "tails.jsonl")
)


def canonical_row_hash(row):
    payload = {k: row[k] for k in sorted(row.keys()) if k != "row_hash"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_row_spirit(row, window_rows):
    roles = {row.get("author", ""), row.get("scorer", ""), row.get("payer", "")}
    if "" in roles or len(roles) < 3 or row["author"] in str(row.get("expected_falsifier", "")):
        return False, "ROLE_COLLAPSE_OR_SELF_FALSIFIER"
    reasons = {r.strip() for r in row.get("witness_reasons", []) if r and r.strip()}
    if len(reasons) < 2 or not str(row.get("expected_falsifier", "")).strip():
        return False, "DUPLICATE_OR_MISSING_WITNESS_REASONS"
    if any(w["author"] == row["scorer"] and w["scorer"] == row["author"] for w in window_rows[-16:]):
        return False, "RECIPROCAL_SCORER_SWAP_IN_WINDOW"
    return True, "OK"


def verify_ledger(path=DEFAULT_LEDGER):
    if not os.path.exists(path):
        return False, f"missing ledger: {path}", 0
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            expected_prev = "0" * 64 if idx == 1 else rows[-1]["row_hash"]
            if row.get("prev_hash") != expected_prev:
                return False, f"row {idx}: prev_hash mismatch", idx
            recomputed = canonical_row_hash(row)
            if row.get("row_hash") != recomputed:
                return False, f"row {idx}: row_hash mismatch ({row.get('row_hash')} != {recomputed})", idx
            ok, why = verify_row_spirit(row, rows)
            if not ok:
                return False, f"row {idx}: spirit check failed ({why})", idx
            rows.append(row)
    return True, f"VERIFIED {len(rows)} row(s) - chain head {rows[-1]['row_hash'][:12] if rows else 'empty'}", len(rows)


def mint_genesis_if_missing(path=DEFAULT_LEDGER):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    row1 = {
        "seq": 1,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prev_hash": "0" * 64,
        "author": "bob:antigravity-primary",
        "scorer": "t90:poolside_laguna-s-2.1_free",
        "payer": "desktop:estate-bench",
        "artifact_uri": "TAILS_LEDGER_SPEC_DECENTRALIZED_COMMUNITIES.md",
        "artifact_sha256": "e487dfdc1744038e73282467c463d1208295276cf1c404538b525a15f8772e96",
        "witness_reasons": [
            "t90 via poolside/laguna-s-2.1:free verified reciprocal scorer-swap attack & key-commitment requirement (WO-AUTO-mvcnnsok)",
            "bob via dots-studio/dots-3-note-preview:free + liquid/lfm-2.5-2.6b:free verified scorer!=payer role collapse & self-falsifier guard (WO-TAILS-VERIFIER-TEST-20261017)"
        ],
        "expected_falsifier": "verify_tails.py rejects any row where len({author,scorer,payer})<3, author in expected_falsifier, len(set(witness_reasons))<2, or reciprocal scorer swap occurs within 16 rows",
        "settlement_ref": "mesh_seed:TAILS_LEDGER_SPEC_DECENTRALIZED_COMMUNITIES.md@e487dfdc1744"
    }
    row1["row_hash"] = canonical_row_hash(row1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(row1, separators=(",", ":")) + "\n")


def print_row_template(path=DEFAULT_LEDGER):
    prev_hash = "0" * 64
    seq = 1
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
            if lines:
                last = json.loads(lines[-1])
                prev_hash = last["row_hash"]
                seq = int(last.get("seq", len(lines))) + 1
    tpl = {
        "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prev_hash": prev_hash,
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
        "settlement_ref": "tx_hash_or_git_commit_ref"
    }
    tpl["row_hash"] = canonical_row_hash(tpl)
    print(json.dumps(tpl, indent=2))


if __name__ == "__main__":
    if "--template" in sys.argv:
        print_row_template()
        sys.exit(0)
    if "--mint-row1" in sys.argv:
        mint_genesis_if_missing()
    ok, msg, n = verify_ledger()
    print(f"[verify_tails] {'PASS' if ok else 'FAIL'}: {msg}")
    sys.exit(0 if ok else 1)

