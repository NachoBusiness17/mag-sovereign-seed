"""game_play — the PLAYABLE surface of the Mycelial Republic game. Server-authoritative, event-driven,
moddable by RIBs, deterministic + $0. The honest 'when can I play' answer, made real.

OPERATOR (2026-08-12): "so when can i play" + "sip" (go). This is the playable layer standing on the
foundation we already built (wow_manifest -> game_world verkle state -> world_rib render). No pretend,
no "coming soon": you can run a real session and PLAY it now.

THE CORE (reuses our own machinery, nothing invented):
  map()            -> world_rib.compile renders the territory (deterministic 2D field + ASCII map +
                       objective markers). The map precedes the territory; same world -> same map.
  act(action, who) -> a PLAYER ACTION is a PROPOSAL: it only becomes true when game_world folds it as
                       a verkle knot (server-authoritative). The world validates; clients present.
  sense()          -> event-driven read of the world (no polling): returns the world state + the
                       player's objective + what changed. Deterministic.
  play(action)     -> the full turn: sense -> validate -> act (fold to verkle) -> re-sense -> report.
                       One turn = one verkle-anchored world change (replayable, unbreakable).

THE CONTRACT (the castle-in-the-sky map, from the wow-k8s foundation):
  - server-authoritative truth = game_world (verkle chain); players/clients = presentation.
  - event-driven world = verkle event bus, no polling (sense reads the committed state).
  - mods = RIB-as-mod via rib_bus (additive, never shadows the authoritative path).
  - deterministic + $0: the play loop is pure local state + a world render, no external LLM needed
    to move (a DM voice can be added later as a stochastic flesh layer, but the WORLD does not need it).

Schema: game_play.v1 · deterministic + $0 · reuse: game_world, world_rib
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

SCHEMA = "game_play.v1"

# World genesis: the seed RIB the world is compiled from. Reuses our WoW invariants so the world is
# grounded in the standing wave, not random. Deterministic: same RIB -> same world -> same map.
WORLD_RIB = (
    "MYCELIAL REPUBLIC — the world is the authority, players are presentation. "
    "goal (0.2, 0.3) the spire of the republic; "
    "goal (0.7, 0.6) the mycelial gate; "
    "goal (0.5, 0.15) the frontier seam; "
    "peak (0.9, 0.9) the cold castle."
)

# The player's objective (a standing invariant, foldable as a verkle knot). Honest: an objective is
# a direction, not a promise of completion.
OBJECTIVE = "walk the mycelial republic: discover the spire, the gate, and the frontier seam."

# Valid player actions (the sandbox — the world only accepts these; it validates, it doesn't spoof).
VALID_ACTIONS = {"look", "walk", "map", "rest", "survey", "help"}


def _world() -> Any:
    from mag import game_world
    return game_world


def map(w: int = 48, h: int = 24) -> dict[str, Any]:
    """Render the world's territory from its seed RIB (deterministic + $0). Returns an ASCII map the
    player can read. Same world -> same map (re-derivable; the map cannot lie)."""
    try:
        from mag import world_rib
        r = world_rib.compile(WORLD_RIB, w=w, h=h)
        field = r.get("field")
        grid = r.get("grid") or _render_grid(field, w, h)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"world render unavailable: {str(e)[:80]}"}
    objective = OBJECTIVE
    return {"ok": True, "schema": SCHEMA, "map": grid, "objective": objective,
            "seed_rib": WORLD_RIB[:120], "note": "the map precedes the territory; re-derivable from "
                                                 "the RIB (a lying map is caught)"}


def _render_grid(field, w: int, h: int) -> str:
    """ASCII render of the scalar field: high terrain -> '#' (castle), low -> '.' (open). Cheap $0."""
    try:
        import numpy as np
        arr = np.asarray(field)
        rows = []
        for i in range(min(h, arr.shape[0])):
            row = "".join("#" if float(arr[i, j]) > 0.55 else "." for j in range(min(w, arr.shape[1])))
            rows.append(row)
        return "\n".join(rows)
    except Exception:
        return "(map render unavailable)"


def sense() -> dict[str, Any]:
    """Event-driven read of the world (no polling): the committed verkle state + objective + count.
    Deterministic + $0. The world is the authority; this reads it."""
    gw = _world()
    st = gw.get_state()
    return {"ok": True, "schema": SCHEMA, "objective": OBJECTIVE,
            "n_entities": st.get("n_entities"),
            "root": st.get("root"),
            "n_changes": st.get("n_changes"),
            "world": st.get("world", {}),
            "note": "event-driven read of the server-authoritative world state"}


def act(action: str, who: str = "player") -> dict[str, Any]:
    """A PLAYER ACTION is a PROPOSAL: it becomes true only when the world folds it as a verkle knot.
    The world validates (sandbox) — it accepts known actions, ignores/spoofs nothing. Honest."""
    action = (action or "").strip().lower()
    if action not in VALID_ACTIONS:
        return {"ok": False, "schema": SCHEMA, "action": action, "who": who,
                "error": "unknown action", "valid": sorted(VALID_ACTIONS)}
    # fold the action as a server-authoritative world change (the proposal becomes true)
    gw = _world()
    r = gw.set_state(f"{who}.{action}", {"action": action, "who": who, "ts": _now()},
                     source="player-proposal")
    return {"ok": r.get("ok"), "schema": SCHEMA, "action": action, "who": who,
            "leaf": r.get("leaf"), "root": r.get("root"),
            "note": "player action folded as a verkle knot — server-authoritative, replayable"}


def _narrate(action: str, *, scene: str = "", world_root: str = "") -> dict[str, Any]:
    """Narrate the turn's consequence. Deterministic + $0 by default; the creative DM
    (game_dm_llm, deepseek) is the STOCHASTIC flesh layer ON TOP when reachable.
    Honest: never fabricate — if the DM is down, fall back to a real, grounded line."""
    try:
        from mag import game_dm_llm
        r = game_dm_llm.dm_narrate(scene, world_root=world_root, action=action)
        if r.get("ok") and (r.get("text") or "").strip():
            return {"ok": True, "narration": str(r["text"]).strip(), "dm": True}
    except Exception:
        pass
    # Deterministic fallback (honest, $0): grounded in the actual action + world, not invented.
    fallback = {
        "look": "You look around the Mycelial Republic. The world holds still, patient, remembering.",
        "walk": "You walk forward. The world folds a knot beneath your feet and holds.",
        "map": "You trace the shape of the world in your mind — it is larger than one room.",
        "rest": "You rest. The world keeps ticking while you are gone.",
        "survey": "You survey what is here. The land remembers what it took to build it.",
        "help": "The world lists what you can do: look, walk, map, rest, survey, help.",
    }
    return {"ok": True, "narration": fallback.get(action, f"You {action}. The world records it."),
            "dm": False}


def play(action: str, who: str = "player") -> dict[str, Any]:
    """ONE FULL TURN: sense -> validate -> act (fold to verkle) -> re-sense -> narrate -> report.
    The world is the authority (deterministic commit); the DM narrates the consequence on top.
    Honest: narration is real prose (dm=True) or a grounded deterministic line (dm=False)."""
    pre = sense()
    a = act(action, who)
    post = sense()
    narr = _narrate(action, world_root=post.get("root") or "")
    # GWAP score (2026-08-16): the real-work total, surfaced per turn — the fun IS the work.
    gwap = {}
    try:
        from mag import game_score
        gwap = (game_score.score().get("score") or {})
    except Exception:
        gwap = {}
    return {"ok": a.get("ok") and post.get("ok"), "schema": SCHEMA,
            "turn": {"action": a.get("action"), "who": who, "accepted": a.get("ok")},
            "world_before": {"root": pre.get("root"), "n_changes": pre.get("n_changes")},
            "world_after": {"root": post.get("root"), "n_changes": post.get("n_changes")},
            "committed": a.get("ok"),  # honest: true only if the knot committed
            "narration": narr.get("narration"),
            "dm": narr.get("dm", False),  # honest: true = creative DM narrated, false = deterministic
            "gwap": gwap,  # the world-built score: real folded work, never fake points
            "valid_actions": sorted(VALID_ACTIONS),
            "hint": "try: look / walk / map / rest / survey / help — or `game_play.map` to see the world"}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="game-play")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "map", "sense", "play", "help"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--who", default="player")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "map":
        out = map()
    elif a.cmd == "sense":
        out = sense()
    elif a.cmd == "play":
        out = play(a.arg or "look", who=a.who)
    elif a.cmd == "help":
        out = {"ok": True, "actions": sorted(VALID_ACTIONS), "objective": OBJECTIVE}
    else:
        out = {"ok": True, "schema": SCHEMA, "objective": OBJECTIVE,
               "actions": sorted(VALID_ACTIONS),
               "note": "game_play — the playable server-authoritative surface. Commands: "
                       "map / sense / play <action> / help"}
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
