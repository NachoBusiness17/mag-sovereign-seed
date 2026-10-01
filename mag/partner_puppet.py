"""partner_puppet — the partner (AdventureNLearn/AOS) puppeteers the local agent
via invariants + shared history.

The embassy vision: the partner does NOT paste raw prompts. They send a compact INVARIANT —
a memlang token (or verkle anchor / Riddler surrogate) — that points into SHARED HISTORY.
The local agent RESOLVES it against the shared registry/verkle chain (reconstructing intent
from shared state, NOT from token bytes), then TRIGGERS the local action. Puppeteering via
invariants + shared history: trust the anchor, not the text.

Layers composed (steal: this is the "self-aware coordinator steers cheap agents via a shared
map to execute hidden intent" tesuji, made an external surface):
  memlang   -> resolve token against shared registry (the trigger language)
  verkle    -> the tamper-evident shared history the anchor points into
  riddler   -> deniable surrogate decode (partner sends a fantasy face, local decodes)

Schema: partner_puppet.v1
CLI: python -m mag.partner_puppet puppet <token_hex> [--execute] | status
REST: POST /api/v1/partner/puppet {token, execute} · GET /api/v1/partner/puppet
"""
from __future__ import annotations

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

SCHEMA = "partner_puppet.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def puppet(token_hex: str, *, execute: bool = False) -> dict[str, Any]:
    """Partner sends a memlang token -> resolve against shared history -> optionally trigger
    the local agent action (puppeteer via invariant). Dead-knot safe: never fires a down executor."""
    try:
        from mag import memlang
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"memlang unavailable: {e}"[:160]}
    r = memlang.resolve(token_hex)
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": r.get("error", "unresolved token"),
                "detail": "partner sent an anchor the local map cannot resolve — no shared history for it"}
    if not execute:
        return {"ok": True, "schema": SCHEMA, "action": r.get("action"), "intent": r,
                "executed": False,
                "note": "resolved against shared history; pass execute=true to fire the local agent action"}
    t = memlang.trigger(token_hex, execute=True)
    return {"ok": bool(t.get("ok")), "schema": SCHEMA, "action": t.get("action"),
            "intent": t.get("intent"), "executed": bool(t.get("executed")),
            "dead_knot": bool(t.get("dead_knot")), "result": t.get("result"),
            "error": t.get("error"), "note": t.get("note")}


def from_anchor(anchor_hex: str, *, execute: bool = False) -> dict[str, Any]:
    """Puppet by verkle anchor (an invariant from shared history) — find the token that anchors it."""
    try:
        from mag import memlang
        reg = memlang._registry()  # shared registry: anchor_hex -> {token_hex, ...}
    except Exception:
        reg = {}
    for token_hex, entry in (reg or {}).items():
        if str(entry.get("anchor_hex", "")).lower() == str(anchor_hex).lower():
            return puppet(token_hex, execute=execute)
    return {"ok": False, "schema": SCHEMA, "error": "anchor not found in shared registry",
            "anchor_hex": anchor_hex}


def surrogate(scratch_id: str) -> dict[str, Any]:
    """Decode a Riddler deniable surrogate (partner sent a fantasy face) into the private intent."""
    try:
        from mag import ghost_whisper
        return ghost_whisper.decode(scratch_id)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160]}


def status() -> dict[str, Any]:
    """The partner surface — liveness ONLY. The partner sees the contract, never internals.
    (Steal 2026-08-09: redact module paths / registry / vocab — that IS the architecture dump.)"""
    live = False
    try:
        from mag import memlang  # noqa: F401  (surface importable = alive)
        live = True
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "partner": {"name": "adventurn-learn", "mode": "invariant-and-shared-history"},
            "liveness": live}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
        return 0
    if argv and argv[0] == "puppet" and len(argv) >= 2:
        execute = "--execute" in argv
        print(json.dumps(puppet(argv[1], execute=execute), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
