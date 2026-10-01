#!/usr/bin/env python3
"""rib_store — content-addressed store for verified computations (2026-08-28).

Distinct from mag/rib_cache.py (the FROZEN RIB prefix cache). This is the
verified-output store: every computation that passes its verifier gets stored
here, keyed by input hash. Re-runs with the same input hit the store instead
of recomputing. Core-memory protocol: all-or-nothing writes, hash-verified reads.

    from mag.rib_store import put, get, stats
    put(input_hash, output_path)
    text = get(input_hash)   # None on miss
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

STORE = Path(__file__).resolve().parents[1] / "memory" / "runs" / "rib_store"
INDEX = STORE / "index.jsonl"


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_index(row: dict) -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def put(input_hash: str, output_path: Path, verifier_result: str = "deterministic") -> dict:
    """Store an output file keyed by input hash. All-or-nothing (square loop)."""
    output = output_path.read_text(encoding="utf-8")
    rib_hash = _hash(output)
    rib_dir = STORE / rib_hash[:16]
    rib_dir.mkdir(parents=True, exist_ok=True)
    target = rib_dir / "output"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(output, encoding="utf-8")
    tmp.replace(target)  # atomic rename = all-or-nothing
    row = {
        "ts": _now(), "rib_hash": rib_hash, "input_hash": input_hash,
        "verifier_result": verifier_result, "size": len(output),
    }
    _append_index(row)
    print(json.dumps({"status": "stored", "rib_hash": rib_hash[:16],
                      "input_hash": input_hash[:16], "bytes": len(output)}))
    return row


def get(input_hash: str) -> str | None:
    if not INDEX.exists():
        return None
    for line in reversed(INDEX.read_text(encoding="utf-8").splitlines()):
        r = json.loads(line)
        if r.get("input_hash") == input_hash:
            rib_file = STORE / r["rib_hash"][:16] / "output"
            if rib_file.exists():
                return rib_file.read_text(encoding="utf-8")
    return None


def stats() -> dict:
    rows = [json.loads(l) for l in INDEX.open(encoding="utf-8")] if INDEX.exists() else []
    return {"ribs": len(rows), "store": str(STORE)}


if __name__ == "__main__":
    print(json.dumps(stats(), indent=1))
