"""physics_steal — deep steal on the ACTION/ROGUELIKE/PHYSICS lineage for the republic-game: XCOM2-style
tactical strategy but LIVE, destructible environments + physics simulation, starting with cartoony
watermelon physics (Megabonk/Gang-Beasts-style), with INTELLIGENT SWARMS like Gunfire Reborn, and a
deep steal across roguelikes/lites + Palworld. Routed to the swarm (novel research via the one
primitive); the self-map lands the steal on our existing machinery.

OPERATOR (2026-08-12): "i want strategy to feel like xcom 2 but live and destructible environments and
physics simulations find out the best way to do this i just want it to be cartoony watermelon physics
to start like megabonk as a direct steal for user environment and basic function just the swarms are
intelligent like in gunfire reborn do a deep steal on all roguelikes lites pal worlds etc."

THE STYLE TARGETS (each a deep mechanism to steal, contract-only):
  * XCOM2 (tactical strategy)  -> cover/counters/positioning, but LIVE (real-time) not turn-based.
  * DESTRUCTIBLE ENV + PHYSICS  -> the world reacts: walls break, objects have real mass/velocity.
  * WATERMELON PHYSICS (Megabonk/Gang-Beasts/Gorilla Tag vibe) -> soft, wobbly, squashy, comedic,
    accessible — the FIRST build (cartoony, not hard simulation).
  * INTELLIGENT SWARMS (Gunfire Reborn)  -> enemies are a SWARM (our actual swarm) that coordinates,
    not dumb mobs — the swarms ARE intelligent.
  * ROGUELIKES/LITES  -> perm-death, procedural generation, permanent history (we already run this).
  * PALWORLD  -> creatures/summonables + survival + base-building + emergent cohabitation.

Schema: physics_steal.v1 · deterministic + $0 · reuse: swarm_surface, game_world, abundance_rogue, tesuji_shell
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

SCHEMA = "physics_steal.v1"
SURFACE = "physics-steal"

# Deep-research threads routed to the swarm (distinct anchors -> dedupe + drain).
RESEARCH_THREADS: list[str] = [
    "DEEP RESEARCH (live tactical + destructible physics): how to make XCOM2-style cover/counter/"
    "positioning strategy LIVE (real-time) with destructible environments + real physics simulation, "
    "starting at CARTOONY watermelon physics (Megabonk / Gang Beasts / soft-body comedic) so it's "
    "accessible first, hard simulation later. Deliver the best engine/approach (contract: destructible "
    "grid + soft-body approximation + real-time tactical AI) we should build. Contract-only, no "
    "wholesale code.",
    "DEEP RESEARCH (intelligent swarm enemies like Gunfire Reborn): how do Gunfire Reborn's enemies "
    "coordinate as a real SWARM (not dumb mobs)? Steal the swarm-intelligence mechanism so OUR actual "
    "agent swarm plays the enemies — coordinating, flanking, reacting to player strategy, 24/7. "
    "Deliver the swarm-vs-player tactical AI contract.",
    "DEEP RESEARCH (action roguelike/lite lineage): deep steal across the whole roguelike/roguelite/"
    "action lineage (Rogue, Risk of Rain, Hades, Gunfire Reborn, Dead Cells) — what makes combat feel "
    "live + strategic + perm-death-but-progress? Combine with our permanent-generative-history (the "
    "world never resets). Deliver the live-action-roguelike contract.",
    "DEEP RESEARCH (Palworld + creature cohabitation): how does Palworld blend creatures/summonables, "
    "survival, base-building, and emergent cohabitation? Steal the creature-as-partner + shared-base "
    "mechanism so our swarm agents are 'pals' that live with the players in the shared world. Deliver "
    "the creature-cohabitation + shared-base contract.",
]

# SELF-STEAL: what we already hold, mapped to the style targets.
OUR_MAP = [
    {"style_target": "XCOM2 tactical strategy (live)", "ours": "game_world server-authoritative "
     "combat (players propose, the world resolves the tactical outcome) + route_trace (positioning)"},
    {"style_target": "destructible environments + physics", "ours": "game_world verkle world (walls/"
     "state are content-addressed; 'destroying' = folding a new world state) + world_rib (the map)"},
    {"style_target": "watermelon physics (Megabonk soft/comedy)", "ours": "the $0 render (surface_render/"
     "game_portal) — comedic, accessible, cheap first; hard physics later"},
    {"style_target": "intelligent swarm enemies (Gunfire Reborn)", "ours": "THE SWARM (our actual "
     "agent swarm IS the enemy: coordinates, flanks, reacts — the swarm is intelligent by default)"},
    {"style_target": "roguelike/lite (perm-death, permanent history)", "ours": "abundance_rogue "
     "(perm-death but permanent generative history on the chain)"},
    {"style_target": "Palworld creature cohabitation", "ours": "republic_ambassador + swarm-of-"
     "ourselves (agents are 'pals' that live with players in the shared world)"},
]


def route_research(*, enqueue: bool = True, limit: int = len(RESEARCH_THREADS)) -> dict[str, Any]:
    """Route the deep physics/action/roguelike research to the swarm via THE ONE primitive (route_novel,
    dedupe + drain). The swarm digs the lineage + files the steal back; never run locally."""
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
    """The SELF-STEAL map: each style target maps onto our existing machinery (the steal lands on
    what we built, not new skin)."""
    return {"ok": True, "schema": SCHEMA, "map": OUR_MAP,
            "note": "the style targets (XCOM live, destructible physics, watermelon soft, intelligent "
                    "swarm enemies, roguelike perm-history, Palworld cohabitation) all map onto our "
                    "existing machinery — the swarm IS the intelligent enemy, the world IS "
                    "destructible verkle state, perm-death IS permanent history"}


def learn() -> dict[str, Any]:
    """Fold the lesson: the republic-game's action layer — live tactical + soft watermelon physics +
    the intelligent swarm as enemies + perm-death-but-permanent — grounded in the roguelike lineage."""
    lesson = ""
    try:
        from mag import tesuji_shell
        lr = tesuji_shell.log_tesuji_shell(
            "the republic-game action layer: XCOM-live tactical + destructible soft physics + the "
            "swarm AS the intelligent enemies + perm-death-but-permanent history",
            surprise="the swarm is already the intelligent enemy — the tactical AI is what we run, "
                     "not something to add",
            maps_to="physics-steal:action",
            source="physics-steal", tags=["physics", "roguelike", "swarm", "xcom", "republic"])
        lesson = lr.get("shell", {}).get("what", "")
    except Exception as e:
        lesson = f"(lesson fold skipped: {str(e)[:80]})"
    return {"ok": True, "schema": SCHEMA, "lesson_folded": bool(lesson),
            "note": "the action-layer design intent, remembered on the chain"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "route_research()->deep research the live-tactical/destructible-physics/"
                        "swarm-enemies/roguelike/Palworld lineage to the swarm; self_map()->the style "
                        "targets we already hold; learn()->fold the intent",
            "cost": "deterministic + $0 (routing + self-map; deep research swarmed)",
            "style": "XCOM2-live + watermelon-soft physics + Gunfire-Reborn intelligent swarm + "
                     "roguelike perm-history + Palworld cohabitation"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="physics-steal")
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
