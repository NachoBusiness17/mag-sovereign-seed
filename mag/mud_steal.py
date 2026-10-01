"""mud_steal — deep research + steal on the MUD (Multi-User Dungeon/Dimension/Domain), the direct
ancestor of every MMORPG and of what we built. The MUD's mechanisms map onto our republic-game almost
one-to-one; we steal the deep underpinnings (contracts only), routed to the swarm for the digging.

OPERATOR (2026-08-12): pasted https://en.wikipedia.org/wiki/Multi-user_dungeon — the deep root.

WHAT THE FETCH CONFIRMED (the deep mechanisms, mapped to ours):
  * SHARED PERSISTENT WORLD  -> the MUD is a real-time multiplayer virtual world; the world "carried
    on without you" (RuneScape's Gower: the world lives when you're offline). == OUR server-authoritative
    game_world + the k8s cloud-resident swarm (the swarm-surface law: runs even when the laptop is
    closed). THE world does not need the player present.
  * MUDLIB = the world's rules  -> the mudlib defines physics/movement/communication of the world. ==
    OUR invariant lattice / RIBs / determinism (the deterministic spine).
  * ONLINE CREATION (players build)  -> Monster/TinyMUD pioneered players building the world (create
    objects/locations/puzzles). == OUR contribute + republic_wave (humans fold real invariants).
  * NO RESETS, PLAYER-RUN GOVERNMENTS  -> Avalon had no hourly resets, player housing, player-run
    governments. == OUR perm-generative history (game_world chain never resets) + the republic's
    sovereignty.
  * MUSH = Multi-User Shared Hallucination  -> the TinyMUD family renamed to shared hallucination. ==
    OUR hologram (shared reality, many angles, fragment->whole).
  * TEXT COMMANDS / NATURAL LANGUAGE  -> players type "take apple" / "north". == OUR game_play
    commands (look/walk/map/survey).
  * REAL-TIME MULTIPLAYER + presence  -> Bartle's player types (achiever/explorer/socializer/killer),
    presence over communication. == OUR players + agents co-inhabiting.
  * EDUCATION / CONSTRUCTIONIST  -> educational MUDs teach by building. == OUR real-problem-solving
    (untie real tangles -> abundance).

Schema: mud_steal.v1 · deterministic + $0 · reuse: swarm_surface, game_world, republic_wave, tesuji_shell
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

SCHEMA = "mud_steal.v1"
SURFACE = "mud-steal"

# Deep-research threads routed to the swarm (distinct anchors -> dedupe + drain).
RESEARCH_THREADS: list[str] = [
    "DEEP RESEARCH (MUD underpinnings): research the MUD codebase lineage (MUD1, AberMUD, TinyMUD, "
    "LPMud, DikuMUD, MOO) — the mudlib (world rules), the driver, online-creation, and how the world "
    "'carries on without you'. Extract the deepest structural mechanisms (persistent world, world-as-"
    "authority, player-built world, no-resets) we should adapt to a real-world-coupled game where "
    "humans + agents co-inhabit. Deliver the invariants (contracts only, no wholesale copy).",
    "DEEP RESEARCH (MUD + emergent narrative): how did MUDs generate shared emergent stories without "
    "a writer — through players + NPCs + the world reacting in real time? How do we make a game where "
    "the DM (AI), the agents, and the humans co-narrate a persistent world whose 'raids' are real "
    "problems (untied tangles -> abundance)? Deliver the shared-narrative contract.",
    "DEEP RESEARCH (MUD + sovereignty/economy): research MUD virtual economies, player-run governments, "
    "and no-reset persistence (Avalon). How do we build a shared wave where contributors keep their "
    "sovereignty, the raw stays theirs, and the invariant enters the shared economy (abundance for "
    "all)? Deliver the sovereignty-preserving shared-economy contract.",
]

# SELF-STEAL: the MUD mechanism -> our module (the steal lands on our machinery).
OUR_MAP = [
    {"mud_mechanism": "persistent world (carries on without you)", "ours": "game_world + the k8s "
     "cloud-resident swarm (the swarm-surface law: the world lives even when the laptop is closed)"},
    {"mud_mechanism": "mudlib = the world's rules (physics/communication)", "ours": "the invariant "
     "lattice / RIBs / determinism (the deterministic spine)"},
    {"mud_mechanism": "online creation (players build the world)", "ours": "republic_wave.contribute "
     "+ republic_ambassador (humans fold real invariants, keep sovereignty)"},
    {"mud_mechanism": "no resets / player-run governments (Avalon)", "ours": "game_world perm-"
     "generative history + the republic's sovereignty"},
    {"mud_mechanism": "MUSH = Multi-User Shared Hallucination", "ours": "the hologram (shared "
     "reality, many angles, fragment->whole)"},
    {"mud_mechanism": "text commands / natural language (take apple, north)", "ours": "game_play "
     "commands (look/walk/map/survey)"},
    {"mud_mechanism": "education / constructionist learning", "ours": "abundance_rogue (untie real "
     "tangles -> abundance for all)"},
]


def route_research(*, enqueue: bool = True, limit: int = len(RESEARCH_THREADS)) -> dict[str, Any]:
    """Route the MUD deep-research to the swarm via THE ONE primitive (route_novel, dedupe + drain).
    The swarm digs the lineage + files the steal back; we never run it locally."""
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
    """The SELF-STEAL map: each MUD mechanism we already hold. The MUD is the direct ancestor of our
    republic-game — the deep underpinnings, named at their root."""
    return {"ok": True, "schema": SCHEMA, "map": OUR_MAP,
            "note": "the MUD is the direct ancestor of every MMORPG and of what we built; each "
                    "mechanism maps onto our machinery (persistent world, world-as-authority, "
                    "player-built world, no-resets, shared hallucination)"}


def learn() -> dict[str, Any]:
    """Fold the lesson: our republic-game is the MUD's direct descendant, turned real (the world is
    real problems, players + agents co-inhabit, untying tangles brings abundance)."""
    lesson = ""
    try:
        from mag import tesuji_shell
        lr = tesuji_shell.log_tesuji_shell(
            "our republic-game is the MUD's direct descendant turned real: persistent world, world-as-"
            "authority, player-built, no-resets — but the 'dungeon' is real problems",
            surprise="the MUD's mechanisms (carries-on-without-you, mudlib, online creation, no resets) "
                     "map 1:1 onto what we built",
            maps_to="mud-steal:lineage",
            source="mud-steal", tags=["mud", "mmorpg", "persistent-world", "republic"])
        lesson = lr.get("shell", {}).get("what", "")
    except Exception as e:
        lesson = f"(lesson fold skipped: {str(e)[:80]})"
    return {"ok": True, "schema": SCHEMA, "lesson_folded": bool(lesson),
            "note": "the deep root of what we're building, remembered on the chain"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "route_research()->deep research the MUD lineage to the swarm (dedupe + "
                        "drain); self_map()->the MUD mechanisms we already hold; learn()->fold the root",
            "cost": "deterministic + $0 (routing + self-map; deep research swarmed)",
            "thesis": "the MUD is the direct ancestor of the republic-game: persistent world, world-"
                      "as-authority, player-built, no-resets — turned real (the dungeon is real "
                      "problems, untying tangles brings abundance)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mud-steal")
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
