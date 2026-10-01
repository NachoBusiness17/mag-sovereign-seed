"""Memory-mapping & obfuscation layer — map to the user, obfuscate through the system.

The idea: real entities (operator, projects, people, places) map to opaque tokens
via a LOCAL key table. Data at rest stores ONLY tokens, so raw files / models /
logs are not directly readable. The real meaning is resolvable ONLY at "your
surface" — the framework/operator interface — where the mapping key lives.

  - register(entity, kind)   -> opaque token; the only place real->token is stored
  - encode(text)             -> replace known real entities with tokens (at-rest form)
  - decode(text)             -> tokens -> real entities (operator surface only)
  - surface(text, mode)      -> "operator" = decoded; "world" = encoded (for models)
  - anchor()                 -> append_verkle_knot over the encoded store (leak/tamper audit)
  - assert_cage()            -> confirm the store holds NO real entities (the guard)

Key table lives in memory/mapping/ (gitignored). Never commit it, never send it
to a model. Salt keeps tokens stable across runs but unguessable without the key.

This is the "soul map": the data is encrypted-by-mapping at rest; only the surface
can read it back. Nothing here is about evading surveillance — it's the operator's
own data, protected from casual reading and from leaking to models as raw PII.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAPPING_DIR = ROOT / "memory" / "mapping"
KEY_PATH = MAPPING_DIR / "key.json"       # real -> token (SENSITIVE, gitignored)
SALT_PATH = MAPPING_DIR / "salt"          # local salt (gitignored)
STORE_PATH = MAPPING_DIR / "store.jsonl"  # at-rest encoded rows (tokens only)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _salt() -> str:
    if SALT_PATH.is_file():
        s = SALT_PATH.read_text(encoding="utf-8").strip()
        if s:
            return s
    s = secrets.token_hex(16)
    SALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SALT_PATH.write_text(s, encoding="utf-8")
    return s


def _token(entity: str, kind: str) -> str:
    """Stable opaque token. Not readable; reversible only via the key table."""
    digest = hashlib.sha256(f"{_salt()}::{kind}::{entity}".encode("utf-8")).hexdigest()
    prefix = kind[:1].lower()
    return f"{prefix}-{digest[:12]}"


def _load_key() -> dict[str, dict[str, str]]:
    return _load_json(KEY_PATH, {})  # {kind: {real: token}}


def _save_key(key: dict[str, dict[str, str]]) -> None:
    _save_json(KEY_PATH, key)


def register(entity: str, *, kind: str = "user") -> dict[str, Any]:
    """Map a real entity to an opaque token. idempotent (stable per entity)."""
    entity = (entity or "").strip()
    if not entity:
        return {"ok": False, "error": "empty entity"}
    key = _load_key()
    bucket = key.setdefault(kind, {})
    if entity in bucket:
        return {"ok": True, "token": bucket[entity], "existing": True}
    tok = _token(entity, kind)
    bucket[entity] = tok
    _save_key(key)
    _log_store("register", {"kind": kind, "token": tok, "entity_hash": hashlib.sha256(entity.encode()).hexdigest()[:8]})
    return {"ok": True, "token": tok, "existing": False}


def _all_entities() -> list[tuple[str, str]]:
    """[(real, token)] across all kinds, longest-real-first for safe replace."""
    key = _load_key()
    items = [(real, tok) for bucket in key.values() for real, tok in bucket.items()]
    items.sort(key=lambda x: len(x[0]), reverse=True)
    return items


def encode(text: str) -> str:
    """Replace known real entities with tokens -> at-rest / world-safe form."""
    if not text:
        return text
    for real, tok in _all_entities():
        if real in text:
            text = re.sub(re.escape(real), tok, text)
    return text


def decode(text: str) -> str:
    """tokens -> real entities (operator surface only)."""
    if not text:
        return text
    key = _load_key()
    for bucket in key.values():
        for real, tok in bucket.items():
            text = re.sub(re.escape(tok), real, text)
    return text


def surface(text: str, *, mode: str = "operator") -> str:
    """'operator' -> decode (real names). 'world' -> encode (tokens for models)."""
    if mode == "operator":
        return decode(text)
    return encode(text)


def _log_store(kind: str, payload: dict[str, Any]) -> None:
    row = {"ts": _now(), "kind": kind, **payload}
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with STORE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def anchor() -> dict[str, Any]:
    """Verkle-knot the encoded store -> a tamper/leak audit tip."""
    from mag.verkle_knot import append_verkle_knot

    # The knot commits a hash of the encoded store + key fingerprint, NOT the key.
    store_digest = hashlib.sha256()
    if STORE_PATH.is_file():
        for line in STORE_PATH.read_text(encoding="utf-8").splitlines():
            store_digest.update(line.encode("utf-8"))
    committed = append_verkle_knot(
        kind="memory_map",
        payload={
            "store_sha256": store_digest.hexdigest()[:16],
            "mapping_kinds": sorted(_load_key().keys()),
            "salt_fp": hashlib.sha256(_salt().encode()).hexdigest()[:8],
        },
    )
    return {"ok": True, "anchor": committed, "tip": getattr(committed, "get", lambda k: None)("tip")}


def assert_cage() -> dict[str, Any]:
    """Guard: confirm the at-rest store holds NO real entities (only tokens)."""
    leaked: list[str] = []
    store_text = ""
    if STORE_PATH.is_file():
        store_text = STORE_PATH.read_text(encoding="utf-8", errors="replace")
    for real, _tok in _all_entities():
        if real and real in store_text:
            leaked.append(real)
    return {
        "ok": len(leaked) == 0,
        "leaked_real_entities": leaked,
        "mapped": len(_all_entities()),
        "store_rows": len([l for l in store_text.splitlines() if l.strip()]),
    }


def status() -> dict[str, Any]:
    key = _load_key()
    return {
        "ok": True,
        "schema": "memory_map.v1",
        "mapped": {kind: len(bucket) for kind, bucket in key.items()},
        "key_path": str(KEY_PATH),
        "store_path": str(STORE_PATH),
        "cage": assert_cage(),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd == "register":
        entity = argv[1] if len(argv) > 1 else ""
        kind = argv[2] if len(argv) > 2 else "user"
        print(json.dumps(register(entity, kind=kind), indent=2, ensure_ascii=False))
    elif cmd == "anchor":
        print(json.dumps(anchor(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "cage":
        print(json.dumps(assert_cage(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
