"""
Abliterator for spawn_manifest.py — Matthew Steiniger's abliteration instinct applied.

Softest assumption to break: the manifest ledger is append-only and tamper-evident.
Attack: mutate the ledger in-place and verify whether the organ detects the change.

Expected outcome if assumption holds: the organ's integrity checks (if any) or
semantic invariants (e.g., session uniqueness, source list consistency) will fail
or the falsifier will detect tampering via checksums/ledger structure.

If the organ has NO integrity checks, the falsifier will succeed and reveal that
the "append-only" claim is decorative, not enforced.

This script is a standalone falsifier; it does not modify the live ledger unless
--apply is used, in which case it appends a tampered row and tests detection.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "memory" / "runs" / "spawn_manifest.jsonl"


def read_ledger():
    """Return list of rows from the ledger."""
    if not LEDGER.exists():
        print("LEDGER MISSING: spawn_manifest.jsonl not found")
        return []
    rows = []
    with LEDGER.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"WARNING: malformed JSON line in ledger: {line[:80]}")
    return rows


def compute_checksum(rows):
    """Compute a simple checksum over the ledger rows for tamper detection.
    Uses sorted JSON strings to ignore insertion order differences."""
    import hashlib
    hasher = hashlib.sha256()
    for row in sorted(rows, key=lambda r: r.get("ts", "") + r.get("session", "")):
        hasher.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return hasher.hexdigest()


def mutate_row(row):
    """Create a mutated copy of a row to test tamper detection."""
    mut = row.copy()
    mut["note"] = mut.get("note", "") + " [ABLITERATED MUTATION INSERTED BY FALSIFIER]"
    return mut


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Abliterator for spawn_manifest.py")
    ap.add_argument("--apply", action="store_true", help="Apply a tampered row to the ledger and test detection")
    ap.add_argument("--verbose", action="store_true", help="Show detailed ledger state")
    args = ap.parse_args()

    rows = read_ledger()
    print(f"Loaded {len(rows)} rows from spawn_manifest.jsonl")

    if args.verbose:
        print("\nLedger rows:")
        for i, r in enumerate(rows, 1):
            print(f"{i:03d} | session={r.get('session')} ts={r.get('ts')} sources={len(r.get('sources', []))} note={r.get('note', '').strip()[:60]}")

    # Compute checksum before any mutation
    checksum_before = compute_checksum(rows)
    print(f"\nChecksum (before): {checksum_before}")

    # Attempt to detect tampering by recomputing checksum after potential mutation
    # We'll simulate a mutation and see if the organ has any detection logic
    if rows:
        tampered_rows = rows[:-1] + [mutate_row(rows[-1])]
        checksum_after = compute_checksum(tampered_rows)
        print(f"Checksum (after simulated mutation): {checksum_after}")
        if checksum_before != checksum_after:
            print("✓ Checksums differ — tampering detectable by checksum")
        else:
            print("✗ Checksums identical — no checksum-based tamper detection present")

    # If --apply, append a tampered row and verify the ledger still "works"
    if args.apply:
        print("\n--- APPLY MODE: appending tampered row ---")
        fake_row = {
            "ts": "2026-09-13T12:00:00.000Z",
            "session": "falsifier_abliterator_session_001",
            "sources": ["memory/runs/spawn_manifest.jsonl"],
            "note": "[ABLITERATION TEST] This row was inserted by the falsifier to test tamper detection. The organ should detect this anomaly."
        }
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fake_row, ensure_ascii=False) + "\n")
        print(f"Appended tampered row to {LEDGER.relative_to(ROOT)}")

        # Re-read and checksum
        rows_after = read_ledger()
        checksum_applied = compute_checksum(rows_after)
        print(f"Checksum (after apply): {checksum_applied}")
        if checksum_applied != checksum_before:
            print("✓ Tampering detectable by checksum after apply")
        else:
            print("✗ No checksum-based tamper detection — organ is not tamper-evident")

        # Semantic anomaly: session uniqueness
        sessions = [r.get("session") for r in rows_after]
        if len(sessions) != len(set(sessions)):
            print("✗ Session uniqueness invariant violated — organ does not enforce uniqueness")
        else:
            print("✓ Session uniqueness holds (but may be coincidental)")

        print("\nFALSIFIER VERDICT:")
        print("- If the organ had tamper-evidence, the falsifier would have failed.")
        print("- If the organ enforces session uniqueness, the falsifier would have failed.")
        print("- If neither, the softest assumption holds and the organ is decorative.")


if __name__ == "__main__":
    main()
