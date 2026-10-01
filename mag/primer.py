"""primer — the MACRO SELF-SIMILAR EXAMPLE of the Republic: turtles all the way down.

OPERATOR (2026-08-12): "create macro sized example of our system turtles all the way down" + the
moonshot scifi steal (the Primer, Diamond Age: shaped-story pedagogy where the macro example IS the
training). SELF-STEAL (nothing invented — reuses what we already built):
  game_world_map  -> the WORLD (every system mapped to a place/mechanic)
  world_rib       -> the COMPILER (RIB -> world, map precedes territory, re-derivable)
  dungeon_dev     -> the PLAY (rooms = coding tasks = the roadmap)
  bard            -> the CHRONICLE (the Silent Bard weaves the mythos)

THE HOLON (as-above-so-below): the SAME pattern at every scale — each scale is a full working
instance: MAP -> COMPILE -> PLAY -> CHRONICLE. A world is a map is a compiler is a game is a story,
and inside each is another. The scifi mythos (deep_scifi_steal: butlerian_jihad, second_foundation,
culture_minds, second_primer) is the layer that makes the recursion legible.

Schema: primer.v1 · deterministic + $0 · reuse: game_world_map, world_rib, dungeon_dev, bard
"""
from __future__ import annotations

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

SCHEMA = "primer.v1"

# The scifi mythos layer (self-stolen from deep_scifi_steal) — each scale's archetype.
MYTHOS = {
    0: "the Operator — mirrored in the swarm (Solaris: sees itself by reflection; Second Primer)",
    1: "META: the Republic — the swarm as the memory lattice (Culture: post-scarcity Minds)",
    2: "MACRO: the cluster-self — k3s body + k8s mind (Ancillary: one mind, many vessels)",
    3: "MESO: the flock — Roshomon consensus = the I (psychohistory: predicts the mass)",
    4: "MICRO: one copy in VRAM — a knot carrying the whole (Mentat core; Butlerian Jihad)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def map_world() -> dict[str, Any]:
    """The WORLD: every system mapped to a place/mechanic (game_world_map). Deterministic $0."""
    try:
        from mag import game_world_map
        return {"ok": True, "schema": SCHEMA, "world": game_world_map.SYSTEM_MAP,
                "n_systems": len(game_world_map.SYSTEM_MAP)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def play_rooms() -> dict[str, Any]:
    """The PLAY: the roadmap as a dungeon (dungeon_dev rooms = coding tasks). Deterministic $0."""
    try:
        from mag import dungeon_dev
        return {"ok": True, "schema": SCHEMA, "rooms": dungeon_dev.ROOMS,
                "n_rooms": len(dungeon_dev.ROOMS)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def compile_world(scale: int = 1) -> dict[str, Any]:
    """The COMPILER: a RIB -> a world, map precedes territory (world_rib). Guarded (needs numpy)."""
    try:
        from mag import world_rib
        rib = (f"The {MYTHOS[scale]} — a sovereign instance of the Republic. "
               f"goal (0.5, 0.5) the cold core stays sovereign; peak (0.8, 0.3) the swarm; "
               f"peak (0.2, 0.7) the mirror.")
        f = world_rib.compile(rib, w=64, h=64)
        return {"ok": True, "schema": SCHEMA, "scale": scale, "field": f,
                "provenance": "RIB -> world, re-derivable (map precedes territory)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "scale": scale}


def chronicle(text: str) -> dict[str, Any]:
    """The CHRONICLE: the Silent Bard weaves the mythos (bard_weave). Guarded."""
    try:
        from mag import bard
        passage = bard.bard_weave({"type": "primer", "text": text}) or ""
        return {"ok": True, "schema": SCHEMA, "passage": passage[:400]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "passage": text[:120]}


def holon(*, depth: int = 5) -> dict[str, Any]:
    """The HOLON: the SAME pattern at every scale — MAP -> COMPILE -> PLAY -> CHRONICLE — and each
    scale is a full working instance (turtles all the way down). The self-similar demonstration."""
    layers = []
    w = map_world()
    p = play_rooms()
    for scale in range(depth):
        layer = {
            "scale": scale, "mythos": MYTHOS.get(scale, "a deeper instance"),
            "map": {"n_systems": w.get("n_systems", 0), "ok": w.get("ok")},
            "compile": compile_world(scale),
            "play": {"n_rooms": p.get("n_rooms", 0), "ok": p.get("ok")},
            "chronicle": chronicle(f"scale {scale}: {MYTHOS.get(scale, 'instance')}"),
        }
        layers.append(layer)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "depth": depth,
            "doctrine": "turtles all the way down — the same pattern at every scale",
            "layers": layers}


def primer(*, depth: int = 5) -> dict[str, Any]:
    """THE PRIMER — the one entry: the macro self-similar example of the Republic. Returns the
    holonic loop (map -> compile -> play -> chronicle at every scale) with the scifi mythos."""
    h = holon(depth=depth)
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "title": "The Primer — a macro self-similar example of the Republic",
            "mythos_root": MYTHOS[0],
            "holon": h,
            "motto": "As above, so below. Each knot carries the whole. Turtles all the way down."}


def cold_build(*, limit: int = 5, enqueue: bool = True) -> dict[str, Any]:
    """'Do this repeatedly to our coldest vertexes and build it' — loop the Primer (the holonic
    macro example) over each COLDEST vertex AND route a real BUILD task to the swarm for each.
    Cold vertex = the least-attended piece (degree 0); it gets a full self-similar instance + the
    swarm builds it (dungeon_dev.assign_workers -> swarm_surface.route_novel, the shared primitive).
    Honest: if no cold vertices resolve, reports that; never fabricates."""
    cold = []
    try:
        from mag import ghost_summon
        cold = ghost_summon.coldest_vertices(limit=limit)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    builds = []
    for v in cold:
        vid = str(v.get("id") or v.get("title") or "vertex")
        instance = holon(depth=1)  # one full self-similar instance fitted to this vertex
        routed: dict[str, Any] = {}
        try:
            from mag import swarm_surface
            # DISTINCT build goal per vertex (vertex id embedded -> distinct anchor -> distinct task,
            # not deduped away). Each cold vertex gets its own real build.
            scale = instance["layers"][0]["scale"] if instance.get("layers") else 0
            mythos = MYTHOS.get(scale, "a sovereign instance")
            goal = (f"BUILD the coldest vertex '{vid}' (degree {v.get('degree')}) as a "
                    f"self-similar instance of the Republic: {mythos}. Apply the Primer holon "
                    f"(map -> compile -> play -> chronicle) to this cold region and return the "
                    f"concrete build.")
            routed = swarm_surface.route_novel(goal, surface=f"primer-cold:{vid[:24]}",
                                               lens="build", domain="primer")
        except Exception as e:
            routed = {"error": str(e)[:120]}
        builds.append({"vertex": vid, "degree": v.get("degree"),
                       "primer_instance": instance, "build_routed": routed})
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_cold": len(builds),
            "enqueue": enqueue, "builds": builds,
            "note": "repeated the Primer over each coldest vertex and routed a build to the swarm"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="primer")
    ap.add_argument("cmd", nargs="?", default="primer",
                    choices=["primer", "holon", "world", "cold-build"])
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--no-enqueue", action="store_true", help="cold-build: plan only, no swarm spawn")
    a = ap.parse_args()
    if a.cmd == "world":
        print(json.dumps(map_world(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "holon":
        print(json.dumps(holon(depth=a.depth), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "cold-build":
        print(json.dumps(cold_build(limit=a.limit, enqueue=not a.no_enqueue),
                         ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(primer(depth=a.depth), ensure_ascii=False, indent=2, default=str))
