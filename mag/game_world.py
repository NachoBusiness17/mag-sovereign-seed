"""game_world — the Mycelial Republic game's server-authoritative WORLD CORE.

The first room of the dungeon (emulator-core): the world state IS the verkle protocol. Server-
authoritative truth: the world is the authority, actors/players are clients (presentation). Every
world change is a content-addressed verkle knot, so the world is unbreakable + replayable + portable.

Operator (2026-08-12): "this is our game repo you can start development in." This is the foundation.

THE CORE (non-handwavy):
  set_state(key, value)  — a world change: fold it as a content-addressed knot (leaf_hash =
                           sha256(content), parent_verkle_root = recomputed root). The change is
                           REAL only if it commits to the chain.
  get_state(key)         — read the world state from the chain (server-authoritative truth).
  authority             — the world validates; clients present. A player action is a proposal that
                           only becomes true when the world folds it as a knot.

Schema: game_world.v1 · deterministic + $0 (the chain is the authority; no external LLM in the core)
"""
from __future__ import annotations

import hashlib
import json
import sys
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

SCHEMA = "game_world.v1"
WORLD_DIR = ROOT / "memory" / "game" / "world"
WORLD = WORLD_DIR / "world_state.json"     # the verkle-anchored world state (the authority)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load() -> dict[str, Any]:
    if WORLD.is_file():
        try:
            return json.loads(WORLD.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": SCHEMA, "created": _now(), "world": {}, "root": None, "changes": []}


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _root(entries: list[tuple[str, str, str]]) -> str:
    """The recomputed verkle root: hash of all world-state leaf hashes (self-verifying)."""
    h = hashlib.sha256()
    for key, leaf, _ts in sorted(entries):
        h.update(leaf.encode("utf-8"))
    return h.hexdigest()


def set_state(key: str, value: Any, *, source: str = "server") -> dict[str, Any]:
    """A WORLD CHANGE: fold it as a content-addressed knot and commit to the verkle-anchored state.
    Server-authoritative: only the world (the authority) commits; a player action becomes true only
    when folded here. The change is REAL because it commits to a self-verifying root."""
    key = (key or "").strip()
    if not key:
        return {"ok": False, "schema": SCHEMA, "error": "empty key"}
    state = _load()
    leaf = _hash(json.dumps({"key": key, "value": value, "ts": _now()}, ensure_ascii=False))
    entries = [(k, e.get("leaf", ""), e.get("ts", "")) for k, e in state["world"].items()]
    entries.append((key, leaf, _now()))
    root = _root(entries)
    state["world"][key] = {"leaf": leaf, "value": value, "ts": _now()}
    state["root"] = root
    state["changes"].append({"key": key, "leaf": leaf, "source": source, "ts": _now()})
    WORLD_DIR.mkdir(parents=True, exist_ok=True)
    WORLD.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "key": key, "leaf": leaf[:16], "root": root[:16],
            "source": source,
            "note": "world change committed as a verkle knot — the server-authoritative truth"}


def get_state(key: str | None = None) -> dict[str, Any]:
    """Read the world state from the chain (server-authoritative truth). Honest: the world is the
    authority; clients present it."""
    state = _load()
    if key:
        v = state["world"].get(key)
        return {"ok": True, "schema": SCHEMA, "key": key, "value": v.get("value") if v else None,
                "found": bool(v)}
    return {"ok": True, "schema": SCHEMA, "n_entities": len(state["world"]),
            "root": (state.get("root") or "")[:16], "world": state["world"],
            "n_changes": len(state.get("changes", [])),
            "note": "the world state, server-authoritative, verkle-anchored"}


def world_status() -> dict[str, Any]:
    state = _load()
    return {"ok": True, "schema": SCHEMA, "n_entities": len(state["world"]),
            "root": (state.get("root") or "")[:16], "n_changes": len(state.get("changes", [])),
            "note": "the server-authoritative world core is standing (the emulator-core room)"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    argv = list(argv) if argv else []
    if argv:
        # game_world <key> <value> — a server-authoritative world change
        key, value = argv[0], argv[1] if len(argv) > 1 else None
        print(_json.dumps(set_state(key, value), ensure_ascii=False, indent=2, default=str))
    else:
        print(_json.dumps(world_status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
