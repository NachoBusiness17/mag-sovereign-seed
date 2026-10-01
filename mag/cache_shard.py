"""cache_shard — swarms auto-shard by INVARIANT to avoid cache-hit redirects (the 50x tax).

Operator (2026-08-11): "how can our swarms automatically shard with the correct invariants via our
ghost tools to avoid cache hit redirects on the fly."

THE MECHANISM (deterministic + $0, stdlib):
  DeepSeek caches by PREFIX. A cache-hit redirect = the 50x miss when a worker's prefix changes
  mid-stream. We avoid it by SHARDING BY INVARIANT, not by task:
    shard_key(invariant)      -> content-hash of the STABLE invariant prefix. Workers with the same
                                 invariant hash land in the SAME shard -> SHARED cache region -> the
                                 expensive prefix is paid once and HIT by every worker in the shard.
    route(invariant, task)    -> assign a task to the shard holding that invariant prefix
                                 (prefix affinity). Stable invariant -> stable shard -> warm cache.
    volatile_redirect(...)    -> if a task would need to EDIT the shared prefix (a mid-context
                                 mutation), it is REDIRECTED to cheap/free (never pays 50x).
  This is the "map precedes territory" move applied to token economics: the invariant (map) fixes
  the cache region (territory) so the swarm renders the deltas for ~free.

Schema: cache_shard.v1 · deterministic + $0 · reuse: invariant.py (stable prefix contract)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "cache_shard.v1"
STABLE_END = "<<<STABLE-INVARIANT-END>>>"  # invariant.py's stable-prefix delimiter


def _stable_prefix(invariant: str) -> str:
    """Extract the STABLE prefix (before the delimiter) — the shared cache region."""
    if STABLE_END in invariant:
        return invariant.split(STABLE_END, 1)[0].strip()
    return (invariant or "").strip()


def shard_key(invariant: str, *, bits: int = 12) -> dict[str, Any]:
    """The shard key = content-hash of the STABLE invariant prefix. Same invariant -> same shard.
    Workers sharing a shard share a cache region -> the expensive prefix is paid once, hit by all."""
    stable = _stable_prefix(invariant)
    if not stable:
        return {"ok": True, "schema": SCHEMA, "stable": "", "shard_id": "unsharded",
                "note": "no stable prefix -> not shardable (would pay full miss)"}
    h = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    shard = h[:bits]
    return {"ok": True, "schema": SCHEMA, "stable": stable[:200], "stable_hash": h,
            "shard_id": shard, "note": "workers in this shard share a warm cache region"}


def route(invariant: str, task: str, *, worker_count: int = 1) -> dict[str, Any]:
    """Assign a task to the shard holding its invariant (prefix affinity). Deterministic."""
    sk = shard_key(invariant)
    if sk.get("shard_id") == "unsharded":
        return {"ok": True, "schema": SCHEMA, "route": "unsharded", "note": "pay full miss",
                "shard": sk["shard_id"]}
    # worker slot within the shard = hash(task) % worker_count (spread deltas, keep prefix shared)
    slot = int(hashlib.sha256((task or "").encode("utf-8")).hexdigest()[:6], 16) % max(1, worker_count)
    return {"ok": True, "schema": SCHEMA, "route": "shard_hit", "shard": sk["shard_id"],
            "worker_slot": slot, "stable_prefix": sk["stable"],
            "note": f"assigned to shard {sk['shard_id']} slot {slot}; shared prefix stays HIT"}


def volatile_redirect(task: str, *, would_edit_prefix: bool = False) -> dict[str, Any]:
    """If a task would EDIT the shared prefix (a mid-context mutation), redirect it to cheap/free
    so the 50x is never paid on the re-derived region. Deterministic."""
    if would_edit_prefix:
        return {"ok": True, "schema": SCHEMA, "redirect": True, "target": "cheap/free",
                "reason": "would_edit_shared_prefix (50x)", "note": "route volatile tail to ollama/grok_free"}
    return {"ok": True, "schema": SCHEMA, "redirect": False, "target": "shard_hit",
            "reason": "append-only delta preserves the shared prefix"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "shard_key(invariant)->shard by stable prefix hash; "
                        "route(invariant, task)->assign to warm shard; "
                        "volatile_redirect(task)->route mid-prefix edits to cheap/free",
            "cost": "deterministic + $0", "stable_delimiter": STABLE_END}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="cache-shard")
    ap.add_argument("invariant", nargs="*", default=[])
    ap.add_argument("--task", default="", help="route: the task text")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), indent=2))
        raise SystemExit(0)
    inv = " ".join(a.invariant) or "the map precedes the territory; the RIB precedes the flock"
    print(json.dumps(shard_key(inv), indent=2, default=str))
    if a.task:
        print(json.dumps(route(inv, a.task), indent=2, default=str))
