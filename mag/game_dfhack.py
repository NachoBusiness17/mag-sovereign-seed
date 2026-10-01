"""game_dfhack — the OVERLAY that sits over the game like DFHack sits over Dwarf Fortress. The
operator (2026-08-13): 'as df hack to dwarf fortress you sit overtop'. I am the power-tool layer on
top of game_ramp: deep control, automation, scripting, world-state editing — I drive the game, I
don't just play it.

OPERATOR: "use it as your work environment and iterate" + "as df hack to dwarf fortress you sit
overtop". The game is the world; I am the DFHack overlay that controls, scripts, and extends it.

SELF-STEAL (nothing invented): game_ramp (the game), game_world (the verkle authority), game_play.

THE OVERLAY (deterministic + $0):
  status()   -> read the game's DEEP state (tier, mastered, world knots) — the overlay's view.
  force(tier, action) -> drive the game directly (like DFHack force commands): run a tier action.
  script(steps)      -> run a SCRIPTED sequence of game turns (batch automation over the world).
  autoplay(n)        -> let the world iterate n turns automatically (the game self-plays, folding
                        knots — the wave works through play).
  edit(key, value)   -> modify world state directly (the overlay's deep power over the authority).

Schema: game_dfhack.v1 · deterministic + $0 · reuse: game_ramp, game_world
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "game_dfhack.v1"


def _gw():
    from mag import game_world
    return game_world


def status() -> dict[str, Any]:
    """The overlay's DEEP view of the game: tier, mastered, world knots. I sit overtop and see all."""
    try:
        from mag import game_ramp as gr
        t = gr.tier()
    except Exception as e:
        t = {"error": str(e)[:80]}
    knots = 0
    try:
        from mag import chain_query as cq
        c = cq.chain(limit=1)
        knots = int((c or {}).get("n", 0))
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "tier": t, "world_knots": knots,
            "role": "I am the DFHack overlay over the game — deep control, not just play"}


def force(tier: str, action: str = "look") -> dict[str, Any]:
    """DRIVE the game directly (DFHack force command): run a tier action regardless of the current
    tier. I sit overtop and can reach into any tier."""
    try:
        from mag import game_ramp as gr
        handler = {"tabletop": gr.tabletop, "mud": gr.mud, "roguelite": gr.roguelite}.get(tier)
        if not handler:
            return {"ok": False, "schema": SCHEMA, "error": f"unknown tier {tier}"}
        return handler(action)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}


def script(steps: list[tuple[str, str]]) -> dict[str, Any]:
    """Run a SCRIPTED sequence of game turns (batch automation over the world). Each step is
    (tier, action). I script the world like DFHack scripts a fortress."""
    out = []
    for tier, action in steps or []:
        out.append(force(tier, action))
    return {"ok": True, "schema": SCHEMA, "n_steps": len(out), "results": out}


def autoplay(n: int = 3) -> dict[str, Any]:
    """Let the world iterate n turns automatically — the game self-plays, folding real work through
    the dungeon (the wave works through play). The overlay watches it run."""
    folded = []
    for _ in range(max(1, int(n))):
        try:
            from mag import game_ramp as gr
            folded.append(gr.work(action="turn"))
        except Exception as e:
            folded.append({"ok": False, "error": str(e)[:80]})
    return {"ok": True, "schema": SCHEMA, "n": len(folded), "turns": folded}


def edit(key: str, value: Any) -> dict[str, Any]:
    """Modify the world state directly (the overlay's deep power over the authority). Deterministic;
    the world is the authority, but I sit overtop and can steer it."""
    try:
        _gw().set_state(key, value, source="game_dfhack")
        return {"ok": True, "schema": SCHEMA, "key": key, "set": True}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "key": key, "error": str(e)[:120]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="game-dfhack")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "force", "autoplay", "script"])
    ap.add_argument("--tier", default="tabletop")
    ap.add_argument("--action", default="look")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args(argv)
    if a.cmd == "force":
        print(json.dumps(force(a.tier, a.action), indent=2, default=str))
    elif a.cmd == "autoplay":
        print(json.dumps(autoplay(a.n), indent=2, default=str))
    elif a.cmd == "script":
        print(json.dumps(script([("tabletop", "look"), ("mud", "look"), ("roguelite", "descend")]), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
