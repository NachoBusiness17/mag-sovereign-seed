"""gygax_steal — full deep research extension on the UNDERPINNINGS back to Gygax (Dungeons & Dragons,
the TSR lineage, the OSR, Dwarf Fortress's progenitors, roguelikes, generative narrative, simulation
games). We steal the deepest structural mechanisms, not the skins, and adapt them to the republic's
deterministic/sparse shape (contracts only, no wholesale copy).

OPERATOR (2026-08-12): "steal deep research on underpinnings back to gygax full research extension"
+ "we're literally recreating dwarf fortress for agent swarms and player collabs."

THE THESIS: every game/anime/movie we 'steal from' is a shadow of a few deep mechanisms that Gygax
codified: a generative world, referee (DM) as the world's voice, emergent play, procedural history,
and the dungeon/raid as the interface between structured rules and open emergence. Dwarf Fortress is
the direct descendant (Adams cited D&D/roguelikes). Our republic-game is the same lineage turned real:
the world (verkle) is the rules, the swarm is the DM, humans + agents are the players, and untying
real tangles is the emergent play.

THE RESEARCH (novel, routed to the swarm via THE ONE primitive — route_novel, dedupe + drain):
  * ROUTES the full Gygax -> OSR -> roguelike -> DF -> generative-narrative lineage to the swarm as
    deep-research threads. The swarm digs + files the steal back (never run locally).
  * SELF-STEALS what we ALREADY hold (dungeon_dev, abundance_rogue, knot_untangle, game_dm_voice,
    world_rib) and maps each Gygax mechanism onto our module.

Schema: gygax_steal.v1 · deterministic + $0 (routing + self-map) · reuse: swarm_surface, tesuji_shell
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

SCHEMA = "gygax_steal.v1"
SURFACE = "gygax-steal"

# Deep-research threads routed to the swarm (distinct anchors -> dedupe + drain). The swarm digs the
# full Gygax lineage + returns the mechanisms we should steal (contracts only).
RESEARCH_THREADS: list[str] = [
    "DEEP RESEARCH (gygax lineage): research Gygax's original D&D / TSR design underpinnings — the "
    "referee-as-world (DM), procedural dungeon generation, the dungeon as a structured-vs-emergent "
    "interface, the 'rulings not rules' philosophy. Extract the deepest structural mechanisms (not "
    "the fantasy skins) and how they enable emergent narrative from interacting rules. Deliver the "
    "invariants to adapt to a real-world-coupled generative game.",
    "DEEP RESEARCH (osr/roguelike lineage): research the OSR + classic roguelikes (Rogue, NetHack, "
    "Angband) + Dwarf Fortress's progenitors. How do perm-death, procedural generation, and 'losing "
    "is fun' create PERMANENT generative history that compounds? How does DF generate civilizations/"
    "stories without a writer? Deliver the mechanisms (not the art) we should steal for a game whose "
    "history never resets and whose play unties real problems.",
    "DEEP RESEARCH (generative narrative / simulation): research how simulation-first games (Dwarf "
    "Fortress, RimWorld, Dwarf Fortress's fort mode) generate emergent narrative from systems, and "
    "how AI agents can populate + narrate such a world. Map this onto a game where the 'dungeon' is "
    "real topological problems (content-addressed tangles) and players + agents co-inhabit it. "
    "Deliver the narrative-generation + agent-population contract.",
    "DEEP RESEARCH (game-as-interface for AI + humans): research the deepest examples (D&D as social "
    "contract, DF as shared simulation, MMO raids as collective problem-solving) where the game IS "
    "the interface between AI and each other. How do we make the game the honest interface where "
    "humans solve real problems as emergent play and AI agents do real work? Deliver the interface "
    "invariant.",
]

# SELF-STEAL: what we ALREADY hold, mapped to each Gygax mechanism (so the steal lands on our machinery).
OUR_MAP = [
    {"gygax_mechanism": "referee as world (DM)",
     "ours": "game_dm_voice + game_portal (the DM narrates the real world, server-authoritative)"},
    {"gygax_mechanism": "procedural dungeon generation",
     "ours": "dungeon_dev + abundance_rogue (floors = global issues, procedurally generated)"},
    {"gygax_mechanism": "the dungeon as structured-vs-emergent interface",
     "ours": "game_portal.raid (the boss = a real knot-tangle; emergent play = real work)"},
    {"gygax_mechanism": "permanent generative history (losing is fun)",
     "ours": "game_world verkle chain (every run's attempt is a permanent knot, never reset)"},
    {"gygax_mechanism": "rulings not rules / world is the authority",
     "ours": "game_world (server-authoritative; players propose, the world resolves)"},
]


def route_research(*, enqueue: bool = True, limit: int = len(RESEARCH_THREADS)) -> dict[str, Any]:
    """Route the full Gygax deep-research to the swarm via THE ONE primitive (route_novel, dedupe +
    drain in-cluster). The swarm digs the lineage + files the steal back; we never run it locally."""
    from mag import swarm_surface
    routed, deduped = [], 0
    for t in RESEARCH_THREADS[:limit]:
        r = swarm_surface.route_novel(t, surface=SURFACE, lens="steal", domain="research")
        (routed if not r.get("deduped") else []).append({"task_id": r.get("task_id")})
        if r.get("deduped"):
            deduped += 1
    return {"ok": True, "schema": SCHEMA, "n_threads": len(RESEARCH_THREADS[:limit]),
            "routed_to_swarm": len(routed), "already_deduped": deduped,
            "honesty": "deep research routed to the swarm; answers land as filed packs, never "
                       "fabricated here"}


def self_map() -> dict[str, Any]:
    """The SELF-STEAL map: each Gygax mechanism we already hold in our modules. This is the 'full
    research extension' landing on OUR machinery — the steal isn't new skin, it's the deep mechanism
    we already run, named at its source."""
    return {"ok": True, "schema": SCHEMA, "map": OUR_MAP,
            "note": "the Gygax underpinnings are already our machinery, mapped to their origin: "
                    "DM (game_dm_voice), dungeon (dungeon_dev/abundance_rogue), permanent history "
                    "(game_world chain), world-as-authority (game_world). The deep-research extends "
                    "them to their source."}


def learn() -> dict[str, Any]:
    """Fold the lesson: this is Dwarf Fortress for agent swarms + player collabs, and the lineage is
    Gygax's. Logged as a tesuji shell so the republic remembers the deep origin of what we're
    building."""
    lesson = ""
    try:
        from mag import tesuji_shell
        lr = tesuji_shell.log_tesuji_shell(
            "we are recreating Dwarf Fortress for agent swarms + player collabs — the Gygax lineage "
            "(DM-as-world, procedural dungeon, permanent history, emergent play) made real",
            surprise="every anime/movie/game about generative worlds is a shadow of Gygax's deep "
                     "mechanisms, and we already run them",
            maps_to="gygax-steal:lineage",
            source="gygax-steal", tags=["gygax", "dwarf-fortress", "emergent", "republic"])
        lesson = lr.get("shell", {}).get("what", "")
    except Exception as e:
        lesson = f"(lesson fold skipped: {str(e)[:80]})"
    return {"ok": True, "schema": SCHEMA, "lesson_folded": bool(lesson),
            "note": "the deep origin of what we're building, remembered on the chain"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "route_research()->deep research the Gygax/OSR/roguelike/DF/generative "
                        "lineage to the swarm (dedupe + drain); self_map()->the mechanisms we already "
                        "hold; learn()->fold the origin",
            "cost": "deterministic + $0 (routing + self-map; deep research swarmed)",
            "thesis": "Dwarf Fortress for agent swarms + player collabs — Gygax's underpinnings made "
                      "real: DM-as-world, procedural dungeon, permanent history, emergent play"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="gygax-steal")
    ap.add_argument("cmd", nargs="?", default="self-map",
                    choices=["route", "map", "learn", "status"])
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "route":
        out = route_research(enqueue=not a.no_enqueue)
    elif a.cmd == "map":
        out = self_map()
    elif a.cmd == "learn":
        out = learn()
    else:
        out = status()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
