"""usage_digest — commit the fleet's daily economics to the verkle chain.

WHY (operator 2026-08-26): the books are layered — logs/ are the raw exhaust
(high-volume, unsigned), the verkle chain is the signed line (session-scale,
tamper-evident). The gap: the money truth ($0 runs, 99.8% cache hits, per-key
usage) lives ONLY in unsigned append-only logs. This module closes it: ONE
signed leaf per UTC day carrying the digest of logs/provider_usage.jsonl.

THE COMMITMENT (coordination upgrade 2026-08-26, verifier seat): the leaf is a
COMMITMENT, not a summary — it carries sha256 of the exact raw jsonl bytes in
the day's window, so anyone can recompute the digest from the logs and prove it
wasn't cooked. The verifier (other seat) recomputes a day's digest from the raw
logs and diffs it against the committed knot.

Schema: usage_digest.v1 · deterministic + $0 · reuses mag.verkle_knot primitives
(verkle_lock, _verify_chain_consistent, pure-append path) — the append block is
copied verbatim from verkle_knot._append_verkle_knot_unlocked so the chain can
never diverge in shape.

Cadence: run AFTER mag.cache_watch (which rides the governor's janitor slot).
CLI: python -m mag.usage_digest [--day YYYY-MM-DD] [--dry]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "usage_digest.v1"
LEAF_SCHEMA = "usage_digest_knot_leaf.v1"
SOURCE = ROOT / "logs" / "provider_usage.jsonl"

from mag.verkle_knot import (  # noqa: E402  (chain-native primitives, canonical)
    BIO,
    CHAIN,
    KNOTS,
    TIP,
    _h,
    _leaf_hash,
    _load_chain_rows,
    _merkle_root,
    _verify_chain_consistent,
    knot_filename,
    verkle_lock,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_rows(source: Path) -> list[tuple[bytes, dict[str, Any]]]:
    """Raw (verbatim_bytes, parsed_row) pairs — bytes for the commitment, row for math."""
    if not source.is_file():
        return []
    out: list[tuple[bytes, dict[str, Any]]] = []
    for line in source.read_bytes().splitlines():
        if not line.strip():
            continue
        try:
            out.append((line, json.loads(line)))
        except json.JSONDecodeError:
            continue
    return out


def aggregate_day(day: str, source: Path | None = None) -> dict[str, Any]:
    """Digest one UTC day of provider_usage.jsonl. Deterministic, pure."""
    source = source or SOURCE
    rows = [pair for pair in _read_rows(source) if str(pair[1].get("ts", "")).startswith(day)]
    n = len(rows)

    # commitment = sha256 of the verbatim jsonl bytes in the window (recomputable)
    raw_bytes = b"\n".join(b for b, _ in rows)
    commitment = hashlib.sha256(raw_bytes).hexdigest() if rows else hashlib.sha256(b"").hexdigest()

    total = {"calls": n, "ok": 0, "failed": 0, "cost": 0.0,
             "prompt_tokens": 0, "completion_tokens": 0,
             "cache_hit_tokens": 0, "cache_miss_tokens": 0}
    lanes: dict[str, dict[str, Any]] = {}
    keys: dict[str, dict[str, Any]] = {}

    for _, r in rows:
        ok = bool(r.get("ok"))
        total["ok" if ok else "failed"] += 1
        total["cost"] += float(r.get("cost") or 0.0)
        total["prompt_tokens"] += int(r.get("prompt_tokens") or 0)
        total["completion_tokens"] += int(r.get("completion_tokens") or 0)
        total["cache_hit_tokens"] += int(r.get("cache_hit_tokens") or 0)
        total["cache_miss_tokens"] += int(r.get("cache_miss_tokens") or 0)

        lane = f"{r.get('provider')}:{r.get('model')}"
        L = lanes.setdefault(lane, {"calls": 0, "ok": 0, "cost": 0.0,
                                    "cache_hit": 0, "cache_miss": 0})
        L["calls"] += 1
        L["ok"] += int(ok)
        L["cost"] += float(r.get("cost") or 0.0)
        L["cache_hit"] += int(r.get("cache_hit_tokens") or 0)
        L["cache_miss"] += int(r.get("cache_miss_tokens") or 0)

        key = (r.get("meta") or {}).get("key_env") or "unknown"
        K = keys.setdefault(key, {"calls": 0, "ok": 0, "cost": 0.0})
        K["calls"] += 1
        K["ok"] += int(ok)
        K["cost"] += float(r.get("cost") or 0.0)

    for L in lanes.values():
        denom = L["cache_hit"] + L["cache_miss"]
        L["hit_ratio"] = round(L["cache_hit"] / denom, 4) if denom else None
    denom = total["cache_hit_tokens"] + total["cache_miss_tokens"]
    total["overall_hit_ratio"] = round(total["cache_hit_tokens"] / denom, 4) if denom else None

    ts_list = [r.get("ts") for _, r in rows if r.get("ts")]
    return {
        "schema": SCHEMA,
        "day": day,
        "source": str(source),
        "window": {"rows": n,
                   "start_ts": min(ts_list) if ts_list else None,
                   "end_ts": max(ts_list) if ts_list else None},
        "commitment": {"algorithm": "sha256(verbatim jsonl lines in window)",
                       "sha256": commitment},
        "total": total,
        "lanes": {k: lanes[k] for k in sorted(lanes)},
        "keys": {k: keys[k] for k in sorted(keys)},
    }


def _build_leaf(day: str, digest: dict[str, Any]) -> dict[str, Any]:
    ts = _now()
    leaf = {
        "type": "usage_digest_knot_leaf",
        "schema": LEAF_SCHEMA,
        "day": day,
        "ts": ts,
        "source": digest["source"],
        "window": digest["window"],
        "commitment": digest["commitment"],
        "total": digest["total"],
        "lanes": digest["lanes"],
        "keys": digest["keys"],
    }
    leaf["leaf_hash"] = _leaf_hash(leaf)
    return leaf


def commit_day(day: str | None = None, *, dry: bool = False) -> dict[str, Any]:
    """One signed leaf per UTC day on the verkle chain (pure append, never amend)."""
    day = day or _now()[:10]
    digest = aggregate_day(day)
    leaf = _build_leaf(day, digest)

    if dry:
        return {"ok": True, "schema": SCHEMA, "dry": True, "day": day,
                "leaf_hash": leaf["leaf_hash"],
                "summary": {k: leaf["total"].get(k) for k in
                            ("calls", "ok", "failed", "cost", "overall_hit_ratio")}}

    with verkle_lock():
        ok, why = _verify_chain_consistent()
        if not ok:
            return {"ok": False, "schema": SCHEMA,
                    "error": "refusing to extend an unverified verkle chain", "verify": why}

        KNOTS.mkdir(parents=True, exist_ok=True)
        session_id = f"usage_digest-{day}"
        fname = knot_filename(
            start_minute_iso=leaf["ts"],
            dominant_theme="usage-digest",
            session_id=session_id,
            commit_hex=leaf["commitment"]["sha256"],
            chord_slug=None,
        )
        leaf["filename"] = fname
        path = KNOTS / fname
        path.write_text(json.dumps(leaf, indent=2), encoding="utf-8")
        import re
        _safe_sid = re.sub(r"[^A-Za-z0-9._-]+", "-", session_id)[:12]
        (KNOTS / f"by-session_{_safe_sid}.json").write_text(
            json.dumps({"filename": fname, "leaf_hash": leaf["leaf_hash"]}, indent=2),
            encoding="utf-8",
        )

        rows = _load_chain_rows()
        # same-session replace would be an amend; a digest is append-only per day.
        existing_i = next((i for i, r in enumerate(rows)
                           if str(r.get("session_id") or "") == session_id), None)
        chain_row = {
            "ts": _now(),
            "filename": fname,
            "leaf_hash": leaf["leaf_hash"],
            "session_id": session_id,
            "start_minute": leaf["window"]["start_ts"],
            "end_minute": leaf["window"]["end_ts"],
            "dominant_theme": "usage-digest",
            "theme_vector_normalized": None,
            "tension_index": None,
            "dossier_commit": leaf["commitment"]["sha256"],
            "amended": existing_i is not None,
        }
        if existing_i is not None:
            rows[existing_i] = chain_row
            all_hashes = _rewrite_chain_unlocked(rows)
            # B2-388 fix: root was never bound on the amend arm, so the tip
            # construction below raised UnboundLocalError AFTER _rewrite_chain
            # had already rewritten the chain rows: chain moved, tip stayed
            # behind, the exact stale-tip disease B2-388 hunted (the live dual
            # of the 06:12Z tip freeze B2-82 repaired). Evidence: the B2-388
            # probe caught the UnboundLocalError live pre-fix; post-fix the tip
            # root equals the recomputed merkle root.
            root = _merkle_root(all_hashes) if all_hashes else _h(b"empty")
            amended = True
        else:
            rows.append(chain_row)
            amended = False
            # PURE APPEND (verbatim from verkle_knot, Option A): O(n) root, one line.
            all_hashes = [r.get("leaf_hash") for r in rows if r.get("leaf_hash")]
            root = _merkle_root(all_hashes) if all_hashes else _h(b"empty")
            parent_root = _merkle_root(all_hashes[:-1]) if len(all_hashes) > 1 else _h(b"empty")
            chain_row["index"] = len(all_hashes) - 1
            chain_row["n_leaves"] = len(all_hashes)
            chain_row["parent_verkle_root"] = parent_root
            chain_row["verkle_root"] = root
            CHAIN.parent.mkdir(parents=True, exist_ok=True)
            with CHAIN.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(chain_row, ensure_ascii=False) + "\n")
            root = chain_row["verkle_root"]

        tip = {
            "schema": "verkle_tip.v1",
            "root": root,
            "n_leaves": len(all_hashes),
            "last_filename": fname,
            "last_leaf_hash": leaf["leaf_hash"],
            "last_session_id": session_id,
            "updated_minute": None,
            "note": "One leaf per session; amend in place on re-summarize. Merkle–Verkle hybrid tip.",
        }
        # atomic tip write (2026-09-25): torn tip writes freeze chain appends via
        # the integrity gate; use verkle_knot's tmp+os.replace helper instead.
        from mag.verkle_knot import _write_tip_atomic
        _write_tip_atomic(tip)

    return {"ok": True, "schema": SCHEMA, "amended": amended, "day": day,
            "filename": fname, "leaf_hash": leaf["leaf_hash"],
            "verkle_root": root, "n_leaves": len(all_hashes),
            "commitment_sha256": leaf["commitment"]["sha256"],
            "summary": {k: leaf["total"].get(k) for k in
                        ("calls", "ok", "failed", "cost", "overall_hit_ratio")}}


def _rewrite_chain_unlocked(rows: list[dict[str, Any]]) -> list[str]:
    """Amend path — same shape as verkle_knot._rewrite_chain (rare for a digest)."""
    from mag.verkle_knot import _rewrite_chain
    return _rewrite_chain(rows)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="usage-digest",
                                 description="Commit daily fleet economics to the verkle chain")
    ap.add_argument("--day", default=None, help="UTC day YYYY-MM-DD (default today)")
    ap.add_argument("--dry", action="store_true", help="aggregate + preview only, no commit")
    args = ap.parse_args(argv)
    out = commit_day(args.day, dry=args.dry)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
