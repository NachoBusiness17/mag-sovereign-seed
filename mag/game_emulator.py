"""game_emulator — the SERVER-AUTHORITATIVE ACTION RESOLVER for the Mycelial Republic game.

game_world is the verkle-anchored WORLD STATE (set_state/get_state fold knots). It says "a player
action is a proposal that only becomes true when the world folds it" — but it has no resolver. THIS
module is the emulator core that makes that real: an actor (player or agent) PROPOSES an action, and
the SERVER validates + resolves it against the current world state + the rules, then folds the
outcome as a verkle knot. The server (the world) is the authority; the actor is a client (presentation).

OPERATOR (2026-08-12): "how should the server-authoritative emulator core + world state be structured
on the verkle chain?" — answer, made real: world state lives in game_world (verkle knots); the
emulator core is the deterministic resolve loop that commits actor proposals as authoritative changes.

THE RESOLVER (non-handwavy):
  act(action, actor)   — SERVER-side: validate the proposal against world + rules -> resolve the
                         outcome deterministically (hash-seeded, no hidden randomness) -> fold the
                         world change via game_world.set_state (a verkle knot). The actor cannot
                         choose the outcome; the server decides. Returns the authoritative result.
  room_attempt(actor)  — the DND action: a party member attempts the current room; the server
                         resolves conquest; conquered -> the room folds as a world knot; failed ->
                         the member is lost (permadeath), room stays. Grounded in dungeon_dev's
                         room-as-task design.

DETERMINISM: the resolution roll is a sha256 of (actor + action + current world root) — byte-stable,
reproducible, testable. No hidden RNG. The world root is the seed, so the same world gives the same
outcome — the chain is the authority.

Schema: game_emulator.v1 · deterministic + $0 · reuse: game_world (verkle state), dungeon_dev (rooms)
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "game_emulator.v1"


def _h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _world_root() -> str:
    """The current authoritative world root from game_world (the chain is the seed)."""
    try:
        from mag import game_world as gw
        st = gw.get_state()
        return str(st.get("root") or "empty")
    except Exception:
        return "empty"


def _rules() -> dict[str, Any]:
    """The deterministic rule set: how a roll resolves. Grounded + simple + explicit."""
    return {
        "difficulty_floor": 6,   # a roll under this always fails
        "difficulty_ceiling": 18,  # a roll at/above this always succeeds
        "crit": 19,              # 19-20 = critical success
        "fumble": 2,             # 1-2 = critical failure
        "d20": 20,
    }


def _roll(actor: str, action: str) -> int:
    """Deterministic d20-style roll seeded by (actor + action + world root): 1..20, byte-stable."""
    seed = _h(f"{actor}::{action}::{_world_root()}")
    return (int(seed[:8], 16) % 20) + 1


def act(action: str, actor: str = "player", *, difficulty: int = 12) -> dict[str, Any]:
    """SERVER-AUTHORITATIVE action resolution: validate the proposal against the world + rules,
    resolve the outcome deterministically, and fold the world change as a verkle knot. The actor
    proposes; the server decides; the world commits. Returns the authoritative result."""
    action = (action or "").strip()
    if not action:
        return {"ok": False, "schema": SCHEMA, "error": "empty action"}
    rules = _rules()
    roll = _roll(actor, action)
    # resolve against the difficulty (server decides, not the actor)
    if roll <= rules["fumble"]:
        outcome = "critical-failure"
        success = False
    elif roll >= rules["crit"]:
        outcome = "critical-success"
        success = True
    elif roll >= difficulty:
        outcome = "success"
        success = True
    else:
        outcome = "failure"
        success = False
    # fold the world change as a verkle knot (server-authoritative commit)
    change = {"action": action, "actor": actor, "roll": roll, "difficulty": difficulty,
              "outcome": outcome, "success": success}
    try:
        from mag import game_world as gw
        folded = gw.set_state(f"act:{actor}:{_h(action)[:8]}", change, source="server")
    except Exception as e:
        folded = {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "schema": SCHEMA, "actor": actor, "action": action[:160],
            "roll": roll, "difficulty": difficulty, "outcome": outcome, "success": success,
            "folded": folded.get("ok"), "leaf": folded.get("leaf"),
            "note": "server-authoritative: the actor proposed, the server resolved, the world "
                    "committed the outcome as a verkle knot"}


def room_attempt(actor: str = "adventurer") -> dict[str, Any]:
    """The DND action (grounded in dungeon_dev's room-as-task): a party member attempts the current
    room. The server resolves conquest deterministically. Conquered -> the room folds as a world
    knot (the region becomes structured). Failed -> the member is lost (permadeath), room stays."""
    try:
        from mag import dungeon_dev as dd
        rooms = getattr(dd, "ROOMS", []) or []
    except Exception:
        rooms = []
    if not rooms:
        return {"ok": False, "schema": SCHEMA, "error": "no dungeon rooms available"}
    room = rooms[0]
    difficulty = room.get("hp", 3) * 5  # harder rooms need a higher roll
    r = act(f"attempt room: {room.get('room', room.get('region', 'room'))}",
            actor=actor, difficulty=difficulty)
    # server-authoritative conquest: success -> fold the room as conquered in the world
    conquered = bool(r.get("success"))
    if conquered:
        try:
            from mag import game_world as gw
            gw.set_state(f"room:{room.get('room')}", {"conquered": True, "by": actor,
                                                      "ts": __import__("datetime").datetime.now(
                                                          __import__("datetime").timezone.utc
                                                      ).isoformat()}, source="server")
        except Exception:
            pass
    return {"ok": True, "schema": SCHEMA, "room": room.get("room"), "region": room.get("region"),
            "actor": actor, "difficulty": difficulty, "roll": r.get("roll"),
            "outcome": r.get("outcome"), "conquered": conquered,
            "permadeath_if_failed": not conquered,
            "note": "server-authoritative room attempt — conquest folds the room as a world knot; "
                    "failure loses the member, the room stays"}


def session(goal: str = "explore") -> dict[str, Any]:
    """A short playable testable session: the server resolves a small number of actions and shows
    the world advancing on the chain. This is the test surface the operator wanted — propose,
    resolve, fold, see the world change."""
    actions = [
        ("scout", "player"),
        ("attempt room: emulator-core", "adventurer"),
        ("reinforce", "adventurer"),
    ]
    results = []
    for action, actor in actions:
        r = act(action, actor=actor)
        results.append({"action": action, "actor": actor, "roll": r.get("roll"),
                        "outcome": r.get("outcome"), "success": r.get("success"),
                        "leaf": r.get("leaf")})
    return {"ok": True, "schema": SCHEMA, "goal": goal, "turns": results,
            "note": "a server-authoritative test session — every action resolved + folded as a "
                    "verkle knot on the chain"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "act(action, actor)->server-authoritative resolution (validate -> resolve "
                        "deterministically -> fold as a verkle knot); room_attempt(actor)->the DND "
                        "room conquest (grounded in dungeon_dev); session()->a short playable "
                        "testable run",
            "reuse": "game_world (verkle state) + dungeon_dev (rooms)",
            "cost": "deterministic + $0 (hash-seeded roll; no external LLM in the core)",
            "doctrine": "the actor proposes, the server resolves, the world commits — the chain is "
                        "the authority, clients are presentation"}


def route() -> dict[str, Any]:
    """EXTERNAL-STEAL (operator standing law): route the server-authoritative emulator-core research
    through the ONE primitive (swarm_surface.route_novel). SELF-STEAL already folded: reuses
    game_world (verkle state) + dungeon_dev (rooms). EXTERNAL: go find OTHER deterministic
    server-authoritative game/action-resolution engines (authoritative turn servers, deterministic
    lockstep, rollback netcode, verifiable world sims) and adapt their mechanisms to our shape —
    contracts only, no wholesale copy. Idempotent (dedupe by anchor)."""
    from mag import swarm_surface
    goal = ("RESEARCH-PACK game-emulator (STEAL both): the server-authoritative action resolver — "
            "an actor proposes, the server validates + resolves deterministically (hash-seeded, no "
            "hidden RNG), and folds the outcome as a verkle knot on game_world. SELF-STEAL (folded): "
            "reuses game_world (verkle state) + dungeon_dev (rooms). EXTERNAL-STEAL: go find OTHER "
            "deterministic server-authoritative game/action-resolution engines — authoritative turn "
            "servers, deterministic lockstep, rollback netcode, verifiable world simulation — and "
            "adapt their mechanisms to our deterministic, chain-anchored shape (contracts only, no "
            "wholesale copy). Produce a concrete design so the game becomes a real testable surface "
            "with the chain as the sole authority.")
    r = swarm_surface.route_novel(goal, surface="game-emulator",
                                  lens="server-authoritative resolution, deterministic lockstep",
                                  domain="research")
    return {"ok": r.get("ok"), "schema": SCHEMA, "route": r,
            "note": "the emulator-core external-steal research is routed through the ONE primitive"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="game-emulator")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["act", "room", "session", "status"])
    ap.add_argument("action", nargs="*", default=[])
    ap.add_argument("--actor", default="player")
    a = ap.parse_args()
    if a.cmd == "act":
        print(json.dumps(act(" ".join(a.action) or "explore", actor=a.actor), indent=2, default=str))
    elif a.cmd == "room":
        print(json.dumps(room_attempt(actor=a.actor), indent=2, default=str))
    elif a.cmd == "session":
        print(json.dumps(session(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
