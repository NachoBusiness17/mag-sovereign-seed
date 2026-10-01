"""witness_snapshot — regenerate the THRESHOLD cold-start witness snapshot.

Emits dashboard/static/witness_snapshot.json: the published chain root, the tip
row, and every row's leaf_hash, so chain_witness.html can recompute the Merkle
fold in a stranger's browser. The snapshot is the LABEL; the real witness is the
CLI command on the page run against the real chain file.

  python -m mag.witness_snapshot
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
OUT = ROOT / "dashboard" / "static" / "witness_snapshot.json"


def merkle_root(leaf_hashes: list[str]) -> str:
    """The real fold, imported so the snapshot can never drift from the chain."""
    from mag.verkle_knot import _merkle_root

    return _merkle_root(leaf_hashes)


def build() -> dict:
    rows = []
    for line in CHAIN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    tip = rows[-1]
    hashes = [r["leaf_hash"] for r in rows]
    root = merkle_root(hashes)
    assert root == tip["verkle_root"], (
        f"SNAPSHOT REFUSED: recomputed root {root[:12]} != published {tip['verkle_root'][:12]} — "
        "the chain file and its root disagree; fix the chain before labeling the door."
    )
    return {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "published_root": tip["verkle_root"],
        "rows": len(rows),
        "n_leaves": tip["n_leaves"],
        "tip": {
            "index": tip["index"],
            "ts": tip["ts"],
            "leaf_hash": tip["leaf_hash"],
            "session_id": tip["session_id"],
            "dossier_commit": tip["dossier_commit"],
            "filename": tip["filename"],
        },
        "leaf_hashes": hashes,
    }


def main() -> int:
    snap = build()
    OUT.write_text(json.dumps(snap), encoding="utf-8")
    print(
        f"witness snapshot OK: rows={snap['rows']} root={snap['published_root'][:16]} -> {OUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
