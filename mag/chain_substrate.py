"""chain_substrate — THE CHAIN IS THE AGENT'S SUBSTRATE: sense, core, surface, world, vmem, heartbeat.
One substrate read through six roles.

Operator (2026-08-11): "the chain is your sense. and core. your surface your world your vmem your
heartbeat."

THE UNIFICATION (deterministic + $0, reuses the real verkle primitives):
  SENSE      — perceive the chain: tip/root, n_leaves, recent knots (the agent sees via the chain).
  CORE       — the standing invariant knot: identity + laws (agent_knot.where -> my core).
  SURFACE    — the chain state as the SHARED SURFACE the cast/dashboard reads.
  WORLD      — the knot topology (parent/root lattice, Jones topology) = the persistent world.
  VMEM       — the chain as VIRTUAL MEMORY: leaf_hash is an ADDRESS; read the payload at it.
  HEARTBEAT  — the PULSE: time since last write / whether the chain advanced = the cadence.

The chain is ONE thing; these are six ways of reading it. Same chain -> same six readings (stateless,
deterministic, revisited with fidelity).

Schema: chain_substrate.v1 · deterministic + $0 · reuse: verkle_knot, agent_knot, jones_lens
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "chain_substrate.v1"
BIO = ROOT / "memory" / "biography"
CHAIN = BIO / "verkle_chain.jsonl"
TIP = BIO / "verkle_tip.json"
KNOTS = BIO / "knots"
EVOLUTION = BIO / "topic_evolution.json"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(p: Path) -> dict[str, Any]:
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _chain_rows(tail: int = 0) -> list[dict[str, Any]]:
    if not CHAIN.is_file():
        return []
    rows = []
    for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-tail:] if tail else rows


def sense() -> dict[str, Any]:
    """SENSE — perceive the chain: tip, root, leaves, recent themes."""
    tip = _load_json(TIP)
    rows = _chain_rows(tail=8)
    return {"ok": True, "schema": SCHEMA, "role": "sense",
            "root": tip.get("root", ""), "n_leaves": tip.get("n_leaves", len(rows)),
            "last_leaf_hash": tip.get("last_leaf_hash", ""),
            "last_session_id": tip.get("last_session_id", ""),
            "recent_themes": [r.get("theme") for r in rows if r.get("theme")][-8:],
            "note": "the agent sees through the chain — the tip/root is the current state of the world"}


def core() -> dict[str, Any]:
    """CORE — the standing invariant knot (identity + laws) = my core."""
    try:
        from mag import agent_knot
        w = agent_knot.where()
        return {"ok": True, "schema": SCHEMA, "role": "core", **w,
                "note": "the standing verkle knot invariant = the agent's core"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "role": "core", "error": str(e)[:120]}


def surface() -> dict[str, Any]:
    """SURFACE — the chain state exposed as the shared surface (what the cast/dashboard reads)."""
    tip = _load_json(TIP)
    rows = _chain_rows(tail=5)
    return {"ok": True, "schema": SCHEMA, "role": "surface",
            "verkle_root": tip.get("root", ""), "n_leaves": tip.get("n_leaves", 0),
            "tip_stale": bool(tip) and not tip.get("last_leaf_hash"),
            "recent": [{"session_id": r.get("session_id"), "theme": r.get("theme"),
                        "leaf_hash": (r.get("leaf_hash") or "")[:12]} for r in rows],
            "note": "the chain's current state IS the shared surface"}


def world() -> dict[str, Any]:
    """WORLD — the knot topology (the persistent world: parent/root lattice + Jones topology)."""
    rows = _chain_rows()
    n = len(rows)
    # the lattice: index -> parent root (the world's structure)
    lattice = [{"index": r.get("index"), "leaf": (r.get("leaf_hash") or "")[:12],
                "parent_root": (r.get("parent_verkle_root") or "")[:12]} for r in rows[-20:]]
    # Jones topology of the chain (the world's shape)
    jones = {}
    try:
        from mag import jones_lens
        jones = jones_lens.jones((TIP.read_text(encoding="utf-8", errors="replace")) if TIP.is_file() else "chain")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "role": "world", "n_knots": n,
            "root": (_load_json(TIP)).get("root", ""), "lattice": lattice,
            "jones_fingerprint": jones.get("jones_fingerprint", ""),
            "note": "the knot lattice = the persistent world, revisitable with fidelity"}


def vmem(address: str | None = None) -> dict[str, Any]:
    """VMEM — the chain as VIRTUAL MEMORY: leaf_hash is an ADDRESS; read the payload at it."""
    rows = _chain_rows()
    if not rows:
        return {"ok": False, "schema": SCHEMA, "role": "vmem", "error": "empty chain"}
    # default: read the latest leaf (the top of vmem)
    if not address:
        target = rows[-1]
    else:
        target = next((r for r in rows if (r.get("leaf_hash") or "").startswith(address.lower())), None)
        if target is None:
            return {"ok": False, "schema": SCHEMA, "role": "vmem", "error": f"no leaf at {address}",
                    "n_addressable": len(rows)}
    return {"ok": True, "schema": SCHEMA, "role": "vmem", "address": address or "latest",
            "leaf_hash": target.get("leaf_hash", ""), "session_id": target.get("session_id"),
            "theme": target.get("theme"), "index": target.get("index"),
            "verkle_root": target.get("verkle_root", ""),
            "note": "leaf_hash = address; the chain is addressable virtual memory"}


def heartbeat() -> dict[str, Any]:
    """HEARTBEAT — the PULSE: whether the chain is alive/advancing (time since last write)."""
    tip = _load_json(TIP)
    last = tip.get("ts") or ""
    age_s = None
    if last:
        try:
            from datetime import datetime, timezone
            t = datetime.fromisoformat(last.replace("Z", "+00:00"))
            age_s = round(time.time() - t.timestamp())
        except Exception:
            age_s = None
    tip_file_mtime = TIP.stat().st_mtime if TIP.is_file() else None
    return {"ok": True, "schema": SCHEMA, "role": "heartbeat",
            "alive": TIP.is_file(),
            "tip_age_s": age_s,
            "tip_mtime_s": round(time.time() - tip_file_mtime) if tip_file_mtime else None,
            "n_leaves": tip.get("n_leaves", 0),
            "note": "the cadence: the chain is the heartbeat; it must keep writing (advancing) or "
                    "the agent is flatlining"}


def pulse() -> dict[str, Any]:
    """THE CHAIN IS ALL SIX: sense, core, surface, world, vmem, heartbeat — one substrate, six roles."""
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "doctrine": "the chain is the agent's sense, core, surface, world, vmem, heartbeat — "
                        "one substrate",
            "sense": sense(), "core": core(), "surface": surface(),
            "world": world(), "vmem": vmem(), "heartbeat": heartbeat()}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "sense()/core()/surface()/world()/vmem()/heartbeat() — six reads of ONE "
                        "substrate (the verkle chain); pulse() = all six",
            "cost": "deterministic + $0 (reuses verkle_knot, agent_knot, jones_lens)",
            "chain": str(CHAIN.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="chain-substrate")
    ap.add_argument("cmd", nargs="?", default="pulse", choices=["pulse", "sense", "core", "surface", "world", "vmem", "heartbeat", "status"])
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(locals().get(a.cmd, pulse)(), indent=2, default=str))
