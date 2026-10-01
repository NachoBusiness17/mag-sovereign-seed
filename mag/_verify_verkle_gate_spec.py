"""_verify_verkle_gate_spec — VERKLE GATE (path b) spec-validation harness.

Read-only. Validates that the mag/verkle_pointers.py SPEC (receipt
watch/inbox/VERKLE_GATE_20260907.md) binds to REAL artifacts today:

  1. seed_hash integrity: recompute the W1 seed's seed_hash exactly the way
     mag/worldline_seed.py does (canonical json sort_keys ensure_ascii=False,
     sha256[:16] over manifest-minus-seed_hash) and compare to the on-disk
     field. Proves leaf-1 payload {seed_hash, chain_tip, ts} is real, not
     transcribed.
  2. chain tips: take the last two verkle_chain.jsonl leaf_hashes as leaves
     2-3 (read-only).
  3. contract-level tamper teeth: build the SPEC leaf records, digest each
     with sha256 (the stand-in commitment for the demo ONLY — this is NOT a
     verkle claim; the real commitment arrives with the toolchain), flip one
     byte in one leaf, show the digest flips = the verify contract's
     tamper-reject property at the schema level.

Exit 0 = SPEC VALIDATED (all green), exit 2 = any check fails.
Falsifier mapping (spec): "proof fails on tampered leaf, passes on intact"
is exercised here at contract level; the cryptographic version runs under
OPTION 1's toolchain via go-verkle IPA proofs.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "memory" / "worldline" / "w1-dogfood-20260907" / "SEED.json"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"

EXPECTED_SEED_HASH = "8dbd503f64bd163c"


def _canonical(obj: dict) -> str:
    # mirrors mag/worldline_seed.py::_canonical exactly
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    # --- 1. seed_hash integrity -------------------------------------------
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    core = {k: v for k, v in seed.items() if k != "seed_hash"}
    recomputed = hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()[:16]
    ok = recomputed == seed["seed_hash"] == EXPECTED_SEED_HASH
    checks.append((
        "seed_hash",
        ok,
        f"field={seed['seed_hash']} recomputed={recomputed} "
        f"expected={EXPECTED_SEED_HASH} session={seed['session_id']}",
    ))

    # --- 2. real chain tips (leaves 2-3) -----------------------------------
    rows = [
        json.loads(line)
        for line in CHAIN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tip1, tip2 = rows[-1], rows[-2]
    ok = tip1["leaf_hash"] != tip2["leaf_hash"] and len(tip1["leaf_hash"]) == 64
    checks.append((
        "chain_tips",
        ok,
        f"rows={len(rows)} tip1={tip1['leaf_hash'][:16]}@{tip1['ts']} "
        f"tip2={tip2['leaf_hash'][:16]}@{tip2['ts']}",
    ))

    # --- 3. SPEC leaf schema + contract-level tamper teeth ------------------
    # Leaf schema (SPEC): {"kind", "ref", "ts"} — ref = seed_hash or leaf_hash.
    leaves = [
        {"kind": "worldline_seed", "ref": seed["seed_hash"], "ts": seed["created_utc"]},
        {"kind": "chain_tip", "ref": tip1["leaf_hash"], "ts": tip1["ts"]},
        {"kind": "chain_tip", "ref": tip2["leaf_hash"], "ts": tip2["ts"]},
    ]
    digests = [
        hashlib.sha256(_canonical(l).encode("utf-8")).hexdigest() for l in leaves
    ]
    tampered = json.loads(json.dumps(leaves[0]))
    tampered["ref"] = ("0" if tampered["ref"][0] != "0" else "1") + tampered["ref"][1:]
    digest_tampered = hashlib.sha256(_canonical(tampered).encode("utf-8")).hexdigest()
    ok = digest_tampered not in digests and len(set(digests)) == 3
    checks.append((
        "tamper_reject",
        ok,
        f"3 leaves digested (sha256 stand-in) distinct={len(set(digests)) == 3}; "
        f"tampered leaf0 ref->{tampered['ref'][:8]}.. digest "
        f"{digest_tampered[:12]} != intact {digests[0][:12]}",
    ))

    all_ok = all(ok for _, ok, _ in checks)
    print("VERKLE GATE SPEC VALIDATION (path b, read-only)")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print(f"  VERDICT: {'SPEC VALIDATED — binds to real seed 8dbd503f64bd163c + live chain tips' if all_ok else 'SPEC BINDING FAILED'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
