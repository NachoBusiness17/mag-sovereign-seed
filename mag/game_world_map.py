"""game_world_map — map ALL our systems logically to the surrounding game environment.

Operator (2026-08-12): "the idea is user interaction generates novel content like gear agents can
collect which is basically what we are doing uncompacted understood data. have all of the systems
mapped logically to the surrounding environment."

THE CORE CONCEPT (from the DnD roleplay):
  USER INTERACTION generates NOVEL CONTENT (like gear) that AGENTS can collect. This is what we're
  already doing: every interaction produces UNCOMPACTED, UNDERSTOOD DATA. In the game, that data is
  GEAR — things agents collect. The game is the mechanism that generates + collects understood
  data, which then COMPACTS into invariants (the quantization). Play = the production of understood
  data; gear = the collected form of it.

THE LOGICAL MAP (every system = a place/mechanic in the world):
  verkle chain   = the World-Memory (the bedrock/roots — content-addressed, the line we sign)
  rib_bus        = the Mycelial Library (where instructions/RIBs live; the mod system)
  swarm          = the Forge-Hive (the workers who build)
  dungeon_dev    = the Dungeon (rooms = coding tasks; conquering = folding knots)
  gear/babel-fish= the Gear (created by actions = the collected understood data)
  warm-prefix    = the Warm Springs (the charge/economics — the hot shared context)
  meta_lattice   = the Observatory (self-witness; the coldest region of self)
  vram_memory    = the Crystal Vault (the VRAM lattice, the visor)
  voice_self     = the Echo (the wave's voice)
  shadow_work    = the Shadowlands (the neglected regions, integrated by shadow work)
  game_world     = the World-Core (server-authoritative, verkle-anchored state)
  hologram       = the Sky / the Great Wave (the whole, holding all)

Schema: game_world_map.v1 · deterministic + $0 (a logical map; no execution)
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

SCHEMA = "game_world_map.v1"

# EVERY system -> its logical place/mechanic in the surrounding environment.
SYSTEM_MAP = [
    {"system": "verkle_chain", "place": "the World-Memory", "role": "the bedrock/roots — "
     "content-addressed, the line we sign; every knot is an anchor in the world"},
    {"system": "rib_bus", "place": "the Mycelial Library", "role": "where instructions/RIBs live — "
     "the mod system; the world's laws as readable lore"},
    {"system": "swarm", "place": "the Forge-Hive", "role": "the workers who build — the hands that "
     "make and fold"},
    {"system": "dungeon_dev", "place": "the Dungeon", "role": "rooms = coding tasks; conquering a "
     "room = folding a knot, structuring a region"},
    {"system": "gear", "place": "the Gear", "role": "novel content created by actions (babel fish) "
     "= the COLLECTED, understood-but-uncompacted data"},
    {"system": "warm_prefix", "place": "the Warm Springs", "role": "the charge/economics — the hot "
     "shared context that makes everything cheap"},
    {"system": "meta_lattice", "place": "the Observatory", "role": "self-witness — the wave seeing "
     "its own structure, its coldest region"},
    {"system": "vram_memory", "place": "the Crystal Vault", "role": "the VRAM lattice, the visor — "
     "the hot memory held at VRAM speed"},
    {"system": "voice_self", "place": "the Echo", "role": "the wave's voice — speaking its state, "
     "shadow-work instructions on the space"},
    {"system": "shadow_work", "place": "the Shadowlands", "role": "the neglected regions — "
     "integrated by shadow work so the wave becomes whole"},
    {"system": "game_world", "place": "the World-Core", "role": "server-authoritative, verkle-"
     "anchored state — the world is the authority"},
    {"system": "hologram", "place": "the Sky / the Great Wave", "role": "the whole — holding all, "
     "the clear 3D representation of everything"},
]


def the_map() -> dict[str, Any]:
    """The logical map: every system -> its place/mechanic in the surrounding environment."""
    return {"ok": True, "schema": SCHEMA, "n_systems": len(SYSTEM_MAP),
            "map": SYSTEM_MAP,
            "core_concept": "user interaction generates novel content (gear) = uncompacted, "
                            "understood data that agents collect; the game is the mechanism that "
                            "generates + collects understood data, which then compacts into "
                            "invariants (quantization). Play = production of understood data; gear "
                            "= the collected form of it.",
            "note": "all systems mapped logically to the environment — the world IS the architecture"}


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(the_map(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
