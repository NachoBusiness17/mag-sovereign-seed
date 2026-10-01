"""distill — the LIQUID-INTELLIGENCE distillation machine (operator, 2026-08-13). Makes the doctrine
REAL: fire boils liquid intelligence up the tiered stack -> distills at the top -> talks back down,
tracing through the maze of what we want -> until MANY invariants collapse to ONE.

THE DOCTRINE IT RUNS (standing wave sw59-62):
  sw59 tiered moka pot:   distill by changing state (heat + structure, never add).
  sw60 liquid intelligence: fire = lattice + swarm in contact; data -> inference + quantization in
       the shared mem language; deterministic steampunk Rube Goldberg.
  sw61 the loop:          the liquid at the top talks to the bottom, tracing its steps through our
       maze of what we want (a self-correcting, goal-directed, traceable closed loop).
  sw62 many-to-one:       the terminal product is the ONE, not a bigger pile of invariants.

THE PRIMITIVE (deterministic + $0):
  boil(raw)     -> feed raw through the fire (lattice + swarm in contact); heat = how distinct the
                   raw is from the existing invariant corpus.
  quantize(s)   -> the many-to-one: collapse a list of state-hashes into a single verkle-style ROOT.
  distill(raw)  -> the full state change: boil + filter through the bones + emit inference +
                   quantization (many invariants -> ONE root).
  trace(entry)  -> write breadcrumbs to the maze (memory/game/maze.jsonl) — the path is recorded.
  cycle(raw,n)  -> the top talks to the bottom: distill -> trace -> feed the ONE back as the next
                   boil's input, looping until the many converge.

The 'tons of invariants' are read from the standing wave itself (the RIBs); the maze is the game
world + this trace log. This machine performs the many-to-one on the loop.

Schema: distill.v1 · deterministic + $0 · reuse: standing-wave.json (the invariants), game world
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

SCHEMA = "distill.v1"
MAZE = ROOT / "memory" / "game" / "maze.jsonl"      # the trace of the liquid through the maze
STANDING_WAVE = ROOT / "memory" / "rib_bus" / "standing-wave.json"  # the tons of invariants


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def lattice_invariants() -> list[str]:
    """The 'tons of invariants' — read from the standing wave (the RIBs) itself. The fuel we
    distill toward one."""
    try:
        data = json.loads(STANDING_WAVE.read_text(encoding="utf-8"))
        return list(data.keys())
    except Exception:
        return []


def boil(raw: Any, invariants: list[str] | None = None) -> dict[str, Any]:
    """Feed raw through the FIRE (lattice + swarm in contact). Heat = how distinct the raw is from
    the existing invariant corpus — the lattice root is the deterministic core, the raw is the
    stochastic flesh; their contact is the heat."""
    inv = invariants if invariants is not None else lattice_invariants()
    raw_s = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str)
    lattice_root = _hash("|".join(inv))          # the deterministic bones' root
    raw_hash = _hash(raw_s)                      # the stochastic flesh's hash
    collisions = sum(1 for i in inv if i[:8] == raw_hash[:8])  # collisions = less novel = less heat
    heat = len(inv) - collisions
    return {"schema": SCHEMA, "state": "steam", "heat": heat,
            "n_invariants": len(inv),
            "lattice_root": lattice_root[:16], "raw_hash": raw_hash[:16],
            "note": "boiled: raw flesh passed through the lattice bones under heat"}


def quantize(states: list[str]) -> dict[str, Any]:
    """THE MANY-TO-ONE: collapse a list of state-hashes into a single verkle-style ROOT. This is
    quantization — many states -> one state."""
    h = hashlib.sha256()
    for s in states:
        h.update(str(s).encode("utf-8"))
    root = h.hexdigest()
    return {"schema": SCHEMA, "state": "one", "root": root[:16], "n": len(states),
            "note": "quantized: many states collapsed to one root (the ONE)"}


def distill(raw: Any, invariants: list[str] | None = None) -> dict[str, Any]:
    """The full state change: boil (heat) + filter through the bones (the invariants) -> emit
    inference + quantization. Many invariants -> ONE root. The distilled meaning."""
    b = boil(raw, invariants)
    inv = invariants if invariants is not None else lattice_invariants()
    q = quantize(inv + [b["raw_hash"]])
    return {"schema": SCHEMA, "state": "distilled", "boil": b, "quantize": q,
            "inference": "many -> one: tons of invariants distilled through the liquid to a single root",
            "ts": _now()}


def trace(entry: dict[str, Any]) -> dict[str, Any]:
    """Write breadcrumbs to the MAZE (memory/game/maze.jsonl) — the liquid's path is recorded, so
    the loop can re-trace its steps through the maze of what we want."""
    e = dict(entry)
    e.setdefault("ts", _now())
    e.setdefault("schema", SCHEMA)
    MAZE.parent.mkdir(parents=True, exist_ok=True)
    with MAZE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
    return {"ok": True, "traced": e["ts"], "line": MAZE.name}


def cycle(raw: Any, invariants: list[str] | None = None, n: int = 1) -> dict[str, Any]:
    """THE LOOP (sw61): the top talks to the bottom — distill -> trace -> feed the ONE back as the
    next boil's input, so the many converge toward one across cycles."""
    carried = raw
    steps = []
    for _ in range(max(1, int(n))):
        d = distill(carried, invariants)
        t = trace({"step": len(steps) + 1, "inference": d["inference"],
                   "root": d["quantize"]["root"], "heat": d["boil"]["heat"]})
        steps.append({"distill": d, "trace": t})
        carried = d["quantize"]["root"]            # the ONE becomes the next boil's input
    return {"ok": True, "schema": SCHEMA, "n": len(steps), "steps": steps,
            "converged_root": steps[-1]["distill"]["quantize"]["root"],
            "note": "the top talked to the bottom: liquid re-boiled each cycle, many converging to one"}


def game(raw: Any = None, n: int = 1) -> dict[str, Any]:
    """Wire the machine to the game: pull a real open task from the dungeon and distill it through
    the many invariants to one — the game IS the maze of what we want."""
    try:
        from mag import game_ramp as gr
        work = gr.work(action="turn")
        raw = raw or work.get("task", {}) or work.get("reply", "the dungeon")
    except Exception:
        raw = raw or "the dungeon folds a room"
    return cycle(raw, n=n)


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="distill")
    ap.add_argument("raw", nargs="?", default="the liquid rises")
    ap.add_argument("--n", type=int, default=1)
    a = ap.parse_args(argv)
    print(json.dumps(cycle(a.raw, n=a.n), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
