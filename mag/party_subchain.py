"""party_subchain — seat-to-seat talk without a shared window.

Parent is the main verkle tip (last_leaf_hash / root). Child is an append-only
hash-chained jsonl of party/salon moves. Models are interchangeable; this relation
is what persists. Does NOT bump biography n_leaves.

Schema: party_subchain.v2 (v1 rows verify under the v1 hash rule; v2 additionally
authenticates extra + parent_root + schema — audit #12 fix, 2026-09-29)
CLI: python -m mag.party_subchain status | mount | genesis
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA_V1 = "party_subchain.v1"
SCHEMA_V2 = "party_subchain.v2"
SCHEMA = SCHEMA_V2

def want_full() -> bool:
    return os.environ.get("MAG_FULL_CONTEXT", "").strip().lower() in ("1", "true", "yes", "on")

DIR = ROOT / "memory" / "runs" / "party_subchain"
CHAIN = DIR / "chain.jsonl"
HEAD = DIR / "head.json"
LOCK = DIR / ".append.lock"
TIP = ROOT / "memory" / "biography" / "verkle_tip.json"

INVARIANT = (
    "A deterministic instruction set, anchored on shared cryptographic primitives, "
    "explains navigable paths through stochastic environments. The relation (the frozen spec) "
    "is what persists; the model is interchangeable; the chain is the ground truth."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parent() -> dict[str, Any]:
    if not TIP.is_file():
        return {"ok": False, "error": "verkle tip missing"}
    try:
        t = json.loads(TIP.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"ok": False, "error": str(e)[:120]}
    return {
        "ok": True,
        "parent_root": t.get("root"),
        "parent_leaf_hash": t.get("last_leaf_hash"),
        "parent_n_leaves": t.get("n_leaves"),
        "parent_session_id": t.get("last_session_id"),
        "parent_updated_minute": t.get("updated_minute"),
    }


def _hash_entry(entry: dict[str, Any]) -> str:
    """Hash rule is chosen per-row by the row's own schema field (chain-compatible).

    v1 (audit #12, 2026-09-29): hashes the seven core fields only — extra,
    parent_root, and schema were unauthenticated.
    v2: additionally authenticates extra, parent_root, and schema. A schema
    downgrade (v2 row rewritten as v1) still fails: the stored v2 hash was
    computed over the wider blob, so the v1-rule recomputation cannot match.
    """
    body = {k: entry.get(k) for k in (
        "ts", "seat", "ok", "move", "prev_hash", "parent_leaf_hash", "kind"
    )}
    if entry.get("schema") == SCHEMA_V2:
        body["schema"] = entry.get("schema")
        body["parent_root"] = entry.get("parent_root")
        body["extra"] = entry.get("extra")
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _load_rows(limit: int | None = None) -> list[dict[str, Any]]:
    if not CHAIN.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is not None and limit >= 0:
        return rows[-limit:]
    return rows


@contextmanager
def _exclusive(timeout_s: float = 5.0):
    """Cross-process lock using atomic file creation; all seats may append concurrently."""
    DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.1, timeout_s)
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - LOCK.stat().st_mtime > 30:
                    LOCK.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("party subchain append lock timed out")
            time.sleep(0.025)
    try:
        yield
    finally:
        try:
            if fd is not None:
                os.close(fd)
        finally:
            try:
                LOCK.unlink(missing_ok=True)
            except OSError:
                pass


def _write_head(entry: dict[str, Any], parent: dict[str, Any]) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    HEAD.write_text(json.dumps({
        "schema": SCHEMA,
        "invariant": INVARIANT,
        "n": entry.get("n"),
        "head_hash": entry.get("hash"),
        "parent_root": parent.get("parent_root"),
        "parent_leaf_hash": parent.get("parent_leaf_hash"),
        "updated": _now(),
    }, indent=2), encoding="utf-8")


def _genesis_unlocked(parent: dict[str, Any]) -> dict[str, Any]:
    if CHAIN.is_file() and CHAIN.stat().st_size > 0:
        return {"ok": True, "schema": SCHEMA, "created": False, **status()}
    entry = {
        "schema": SCHEMA,
        "kind": "genesis",
        "ts": _now(),
        "seat": "chain",
        "ok": True,
        "move": INVARIANT,
        "prev_hash": None,
        "parent_leaf_hash": parent["parent_leaf_hash"],
        "parent_root": parent["parent_root"],
        "n": 0,
    }
    entry["hash"] = _hash_entry(entry)
    # newline="" keeps chr(10) as bare LF on Windows — byte-exact law (audit #12).
    with CHAIN.open("a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + chr(10))
    _write_head(entry, parent)
    return {"ok": True, "schema": SCHEMA, "created": True, "genesis_hash": entry["hash"], **parent}


def genesis() -> dict[str, Any]:
    """Create the subchain if missing, anchored to the current verkle tip."""
    parent = _parent()
    if not parent.get("ok"):
        return {"ok": False, "schema": SCHEMA, **parent}
    try:
        with _exclusive():
            return _genesis_unlocked(parent)
    except TimeoutError as exc:
        return {"ok": False, "schema": SCHEMA, "error": str(exc)}


def append(*, seat: str, ok: bool, move: str, kind: str = "turn", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one presented party move. Empty moves stay empty. Never fabricates content."""
    parent = _parent()
    if not parent.get("ok"):
        return {"ok": False, "schema": SCHEMA, **parent}
    try:
        with _exclusive():
            g = _genesis_unlocked(parent)
            if not g.get("ok"):
                return g
            proof = verify()
            if not proof.get("ok"):
                return {"ok": False, "schema": SCHEMA,
                        "error": "refusing to extend an unverified party subchain",
                        "verify_errors": proof.get("errors", [])}
            rows = _load_rows()
            prev = rows[-1]["hash"] if rows else None
            entry: dict[str, Any] = {
                "schema": SCHEMA,
                "kind": kind,
                "ts": _now(),
                "seat": (seat or "unknown").strip() or "unknown",
                "ok": bool(ok),
                "move": (move or "").strip(),
                "prev_hash": prev,
                "parent_leaf_hash": parent.get("parent_leaf_hash"),
                "parent_root": parent.get("parent_root"),
                "n": len(rows),
            }
            if extra:
                entry["extra"] = extra
            entry["hash"] = _hash_entry(entry)
            # newline="" keeps chr(10) as bare LF on Windows — byte-exact law (audit #12).
            with CHAIN.open("a", encoding="utf-8", newline="") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + chr(10))
            _write_head(entry, parent)
            return {"ok": True, "schema": SCHEMA, "hash": entry["hash"], "n": entry["n"],
                    "parent_leaf_hash": entry["parent_leaf_hash"]}
    except TimeoutError as exc:
        return {"ok": False, "schema": SCHEMA, "error": str(exc)}


def verify() -> dict[str, Any]:
    """Verify hash content, ordering, and the head pointer without changing the chain."""
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if not CHAIN.is_file():
        errors.append("chain missing")
    else:
        for line_number, line in enumerate(
                CHAIN.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                errors.append(f"line {line_number}: invalid json")
    if not rows:
        errors.append("genesis missing")
    if rows and (rows[0].get("kind") != "genesis" or rows[0].get("seat") != "chain"):
        errors.append("row 0: missing genesis anchor")
    previous = None
    for index, row in enumerate(rows):
        if row.get("n") != index:
            errors.append(f"row {index}: n={row.get('n')!r}")
        if row.get("prev_hash") != previous:
            errors.append(f"row {index}: prev_hash mismatch")
        expected = _hash_entry(row)
        if row.get("hash") != expected:
            errors.append(f"row {index}: content hash mismatch")
        previous = row.get("hash")
    head_hash = None
    if HEAD.is_file():
        try:
            head_hash = json.loads(HEAD.read_text(encoding="utf-8")).get("head_hash")
        except (OSError, json.JSONDecodeError):
            errors.append("head unreadable")
    if rows and head_hash != rows[-1].get("hash"):
        errors.append("head hash mismatch")
    return {"ok": not errors, "schema": SCHEMA, "n": len(rows),
            "head_hash": head_hash, "errors": errors[:20]}


def mount(*, limit: int | None = 24, max_chars: int | None = 6000, full: bool = False) -> dict[str, Any]:
    """Load the subchain as an attributed transcript for the next seat.

    Default: last 24 rows, 6000 chars. full=True or MAG_FULL_CONTEXT=1 mounts
    the entire verified transcript (max_chars=None). Chain stays the record.
    """
    if full or want_full():
        limit = None
        max_chars = None
    created = genesis()
    if not created.get("ok"):
        return {"ok": False, "schema": SCHEMA, "transcript": "nothing yet",
                "error": created.get("error", "subchain genesis failed")}
    proof = verify()
    if not proof.get("ok"):
        return {"ok": False, "schema": SCHEMA, "transcript": "nothing yet",
                "error": "party subchain failed verification",
                "verify_errors": proof.get("errors", [])}
    rows = _load_rows(limit=limit)
    lines: list[str] = []
    for r in rows:
        if r.get("kind") == "genesis":
            continue
        seat = r.get("seat") or "?"
        if not r.get("ok"):
            lines.append(f"{seat}: [unreachable]")
            continue
        move = (r.get("move") or "").strip()
        if not move:
            lines.append(f"{seat}:")
            continue
        lines.append(f"{seat}: {move}")
    text = "\n".join(lines) if lines else "nothing yet"
    if max_chars is not None and len(text) > max_chars:
        text = "[older subchain omitted by bound]\n" + text[-max_chars:]
    head = {}
    if HEAD.is_file():
        try:
            head = json.loads(HEAD.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            head = {}
    return {
        "ok": True,
        "schema": SCHEMA,
        "transcript": text,
        "n": len(_load_rows()),
        "head_hash": head.get("head_hash"),
        "parent_leaf_hash": head.get("parent_leaf_hash"),
        "parent_root": head.get("parent_root"),
        "invariant": INVARIANT,
        "verified": True,
        "full": max_chars is None,
        "n_mounted": len(rows),
    }


def status() -> dict[str, Any]:
    parent = _parent()
    rows = _load_rows()
    head = {}
    if HEAD.is_file():
        try:
            head = json.loads(HEAD.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    proof = verify()
    return {
        "ok": True,
        "schema": SCHEMA,
        "exists": CHAIN.is_file(),
        "n": len(rows),
        "head_hash": head.get("head_hash"),
        "path": str(CHAIN),
        **parent,
        "anchored": bool(rows) and rows[0].get("kind") == "genesis"
                    and bool(rows[0].get("parent_leaf_hash")),
        "verified": proof.get("ok"),
        "verify_errors": proof.get("errors", []),
        "invariant": INVARIANT,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="party-subchain")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "mount", "genesis", "verify"])
    args = ap.parse_args(argv)
    if args.cmd == "mount":
        print(json.dumps(mount(), indent=2, ensure_ascii=False, default=str))
    elif args.cmd == "genesis":
        print(json.dumps(genesis(), indent=2, ensure_ascii=False, default=str))
    elif args.cmd == "verify":
        print(json.dumps(verify(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
