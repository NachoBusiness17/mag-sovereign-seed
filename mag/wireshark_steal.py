"""wireshark_steal — FULL RESEARCH steal from Wireshark-class and other deep systems, routed to the
swarm for the swarm to do the actual digging. Also grounds the VISION the operator described: 10
people fighting a dragon, doing REAL work, interpreting backend unraveling + emergence as the game
state narrator for everyone — under a local MIT license so everyone's compute is shared to the whole,
right-sized for rendering.

OPERATOR (2026-08-12): "what other tools can we steal from? wire shark and other systems like this
full research. we used brarchat and openclaw we're really not even touching them. what would it look
like to have 10 people fighting a dragon doing actual work interpreting the backend unraveling and
emergence as the game state narrator for all involved. maybe in a local mit license so all their
compute is shared to the whole like our pc is to then right size rendering for the game."

TWO HALVES (both $0, deterministic, reuse):
  A) ROUTE THE FULL RESEARCH — novel research (Wireshark-class packet/instrumentation tools, Briar/
     OpenClaw deep reuse) routes via THE ONE primitive (swarm_surface.route_novel) so the swarm digs
     and files the steal back. We never research it locally; the swarm does.
  B) GROUND THE VISION — self-steal what we ALREADY have so the 10-player-dragon vision is built on
     our own machinery, not invented: render farm (flock_shader k8s render farm), shared compute
     (horse/boat/oven workshop pattern), rightsize (swarm_rightsize), MIT (mag-sovereign-kit/LICENSE),
     server-authoritative world (game_world), route provenance (route_trace). The vision assembles
     these; the swarm researches the missing mechanism.

Schema: wireshark_steal.v1 · deterministic + $0 · reuse: swarm_surface, game_world, route_trace
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

SCHEMA = "wireshark_steal.v1"
SURFACE = "wireshark-steal"

# Novel research threads routed to the swarm (distinct anchors -> dedupe + drain). The swarm digs
# each and files the steal back; we never run it locally.
RESEARCH_THREADS: list[str] = [
    "RESEARCH STEAL (wireshark-class): how does Wireshark instrument/observe a live packet stream "
    "(capture filters, dissectors, taps, real-time protocol tree) and how can we steal+adapt that "
    "deterministic observation shape to instrument OUR routes/queues/session-logs as a live, "
    "debuggable stream? Contract-only, no wholesale copy. Deliver the mechanism to adapt.",
    "RESEARCH STEAL (briar deep): we cloned Briar but barely touch it. Deep-dive the Briar "
    "delay-tolerant serverless P2P rendezvous + offline-first sync contract and map it onto our "
    "mesh_comm seats + swarm_control dead-drop so the swarm's offline/mesh layer actually runs.",
    "RESEARCH STEAL (openclaw deep): we reference OpenClaw but barely touch it. Map OpenClaw's "
    "native/plugin module + memory-promote + long-run-personal-agent shape onto our seats so we "
    "actually use it (improve promote + residual), not just cite it.",
    "RESEARCH STEAL (MIT shared compute render farm): design a LOCAL MIT-licensed shared-compute "
    "layer where N peers each contribute compute (like our PC does to the whole) and right-size "
    "rendering across them — so 10+ players' machines jointly render the game world, licensed MIT "
    "so the shared pool belongs to everyone. Deliver the rightsizing + licensing mechanism.",
    "RESEARCH STEAL (game-as-narrator of real backend work): 10 people fight a dragon, but the "
    "'dragon' IS the backend unraveling + emergence — each player does REAL work (debugging, "
    "tracing, building) and the game state NARRATES that real backend activity to all players "
    "simultaneously (server-authoritative world = the shared state). Deliver the mapping: real "
    "backend event -> game-state narration for everyone.",
]

# The vision assembled from what we ALREADY have (grounded, not invented). Each maps to a module.
VISION_MAP = [
    {"name": "render farm", "module": "mag/flock_shader.py + invariant_lattice.py",
     "note": "shade only the seams through the k8s swarm render farm — right-size rendering, pennies"},
    {"name": "shared compute", "module": "mag/renderman.py (distributed bucket) + swarm_rightsize",
     "note": "the render-farm = distributed agent processing; right-size the whole pool"},
    {"name": "MIT license", "module": "mag-sovereign-kit/LICENSE + mycelial-republic spore",
     "note": "MIT-open shared pool — every node's compute belongs to the whole"},
    {"name": "server-authoritative world", "module": "mag/game_world.py",
     "note": "world = the authority; 10 players propose, the world resolves (the shared truth)"},
    {"name": "route provenance", "module": "mag/route_trace.py",
     "note": "every player's move is a content-addressed hop; 'where did they go from' is a trace"},
    {"name": "game-as-narrator", "module": "mag/game_dm_voice.py + game_live.py",
     "note": "the DM narrates the real live republic activity into the world for all players"},
]


def route_research(*, enqueue: bool = True, limit: int = len(RESEARCH_THREADS)) -> dict[str, Any]:
    """Route the FULL RESEARCH threads to the swarm via THE ONE primitive (dedupe by anchor + drain
    in-cluster). The swarm digs; we never run the research locally. $0."""
    from mag import swarm_surface
    routed, deduped = [], 0
    for t in RESEARCH_THREADS[:limit]:
        r = swarm_surface.route_novel(t, surface=SURFACE, lens="steal", domain="research")
        (routed if not r.get("deduped") else []).append({"task_id": r.get("task_id")})
        if r.get("deduped"):
            deduped += 1
    return {"ok": True, "schema": SCHEMA, "n_threads": len(RESEARCH_THREADS[:limit]),
            "routed_to_swarm": len(routed), "already_deduped": deduped,
            "contract": "novel research routed to the swarm (route_novel, dedupe + drain); the swarm "
                        "files the steals back, never run locally", "honesty": True}


def vision() -> dict[str, Any]:
    """The 10-player-dragon vision, GROUNDED in what we already have (self-steal, not invented).
    Each piece maps to a real module; the swarm researches the missing mechanism."""
    return {"ok": True, "schema": SCHEMA, "vision": {
        "scene": "10 people fight a dragon; the dragon IS the backend unraveling + emergence",
        "mechanism": "each player does REAL work (trace/debug/build); the server-authoritative world "
                     "(game_world) + route_trace record it; the DM (game_dm_voice) narrates the real "
                     "backend activity as game state to ALL players simultaneously",
        "shared_compute": "MIT license (mag-sovereign-kit/LICENSE) so every node's compute belongs to "
                          "the whole, like our PC's does; render farm (flock_shader) + swarm_rightsize "
                          "right-size rendering across the shared pool",
        "existing_pieces": VISION_MAP,
    }, "note": "the vision assembles our own machinery (render farm, shared compute, MIT, world, "
               "trace, DM); the swarm researches the missing mechanisms via route_research()"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "route_research()->full research (wireshark-class/briar/openclaw/MIT-shared-"
                        "compute/game-narrator) routed to the swarm for digging; vision()->the "
                        "10-player-dragon vision grounded in our existing modules",
            "cost": "deterministic + $0 (reuses swarm_surface; vision is self-steal)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="wireshark-steal")
    ap.add_argument("cmd", nargs="?", default="vision",
                    choices=["route", "vision", "status"])
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "route":
        out = route_research(enqueue=not a.no_enqueue)
    elif a.cmd == "status":
        out = status()
    else:
        out = vision()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
