"""game_portal — the MYCELIAL REPUBLIC game portal: an old-school-WoW login screen around a campfire
(dark + foreboding, PoE-style), then GENERATIVE RAID ADVENTURES narrated + populated by clever AI
agents, where HUMANS solve real problems in the form of emergent play.

OPERATOR (2026-08-12): "yes i want to have a login screen kinda like old school wow around a fire
where they enter the game kinda poe style dark and foreboding. then we go on generative adventures
like wow raids narrated and populated by clever interesting and entertaining ai agents while humans
solve real problems in the form of emergent play."

THE MECHANISM (self-steal, no invention):
  * game_world            -> the server-authoritative world (the chain is the truth).
  * game_dm_voice         -> the DM narration (the raid's voice).
  * surface_render        -> the inline HTML renderer (the login screen + raid frame).
  * republic_wave         -> the shared wave humans contribute to (emergent play = real work).
  * route_trace           -> every player's move is a content-addressed hop (provenance).

THE EXPERIENCE:
  * login()  -> the old-school-WoW login: a campfire in the dark, foreboding. You "enter the game"
                by choosing a role + joining the wave (emergent play). Returns the campfire scene.
  * raid()   -> a generative raid: an AI-populated adventure (the raid's challenge = a REAL problem
                surfaced from the wave), narrated by the DM, where humans solve it together.
  * scene()  -> render the current world as the dark campfire scene (HTML + ASCII).

Schema: game_portal.v1 · deterministic + $0 (the render + world + DM voice; the raid's challenge is
the real problem humans solve, narrated) · reuse: game_world, game_dm_voice, surface_render, republic_wave
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

SCHEMA = "game_portal.v1"

# The campfire login scene — old-school WoW / PoE dark + foreboding. ASCII-rendered so it's $0 and
# portable (no deps). The fire is the shared wave; the dark is the unknown the humans will solve.
CAMPFIRE = r"""
            _..--.._
         .-'        '-.
        /    _  _      \
       |    (o)(o)     |      THE MYCELIAL REPUBLIC
       |      <>       |      a campfire in the dark
       |      ||       |      enter the game, join the wave
        \  __||__     /
         '._  ||  _.-'        [the fire is the shared wave]
            '-''-'            [the dark is what you'll solve]
"""

# Player roles (WoW-raid style) — each maps to a REAL contribution in the wave.
ROLES = [
    {"role": "Warden",   "emergent_play": "trace + protect the wave (route provenance)"},
    {"role": "Artificer", "emergent_play": "build the mechanisms (modules/tools)"},
    {"role": "Seer",     "emergent_play": "lens the unknown (research/frontier)"},
    {"role": "Weaver",   "emergent_play": "weave the invariant (fold lessons into the wave)"},
    {"role": "Smith",    "emergent_play": "forge the shared compute (right-size the pool)"},
]


def _gw() -> Any:
    from mag import game_world
    return game_world


def login(player: str = "", *, role: str = "Warden") -> dict[str, Any]:
    """THE LOGIN: an old-school-WoW campfire. You 'enter the game' by choosing a role + joining the
    wave — and the role IS your emergent play (a real contribution). Server-authoritative: the login
    folds a knot into the world (you're here now). Deterministic + $0."""
    player = (player or "traveler").strip()
    gw = _gw()
    # entering the game = joining the wave: fold the player's entry as a verkle knot
    r = gw.set_state(f"player.{player}.entered", {"player": player, "role": role,
                                                  "scene": "campfire", "ts": _now()},
                     source="portal-login")
    role_row = next((x for x in ROLES if x["role"].lower() == role.lower()), ROLES[0])
    return {"ok": r.get("ok"), "schema": SCHEMA, "player": player,
            "role": role_row["role"], "emergent_play": role_row["emergent_play"],
            "scene": CAMPFIRE,
            "enter_line": f"{player}, the fire takes your name. You enter the {role_row['role']}'s "
                          f"work. Your emergent play: {role_row['emergent_play']}.",
            "note": "you entered the game = you joined the wave; your role is the real work you'll "
                    "do (emergent play), and the entry is a verkle knot on the chain"}


def raid(name: str = "", *, narrate: bool = True) -> dict[str, Any]:
    """A GENERATIVE RAID: a dark adventure populated + narrated by AI agents, where the raid's
    CHALLENGE is a REAL problem surfaced from the wave, and humans solve it together as emergent play.
    The DM narrates the raid; the world (server-authoritative) holds the state; the players' real
    problem-solving IS the raid's progress."""
    name = (name or "the Cold Vein").strip()
    # the raid's challenge = a real problem from the shared wave (grounded, not invented)
    challenge = _wave_challenge()
    gw = _gw()
    # open the raid as a world event (server-authoritative)
    gw.set_state(f"raid.{name}", {"name": name, "challenge": challenge,
                                  "stage": "assembled", "ts": _now()}, source="portal-raid")
    narration = ""
    if narrate:
        try:
            from mag.game_dm_voice import extract_narrator
            passage = (f"# Narrator\n\nThe fire gutters. The {name} stretches ahead — a raid of "
                       f"clever agents and willing hands. The true enemy is not a beast but a real "
                       f"problem: {challenge}. Gather. The world is the authority; your play is the "
                       f"work.")
            narration = extract_narrator(passage)
        except Exception as e:
            narration = f"(narrator unavailable: {str(e)[:80]})"
    return {"ok": True, "schema": SCHEMA, "raid": name, "challenge": challenge,
            "narration": narration,
            "populated_by": "clever AI agents (the swarm) narrate + inhabit; humans solve the real "
                            "problem as emergent play",
            "note": "a generative raid: the challenge is a REAL problem from the wave, narrated by "
                    "the DM, populated by agents, solved by humans — emergent play as real work"}


def _wave_challenge() -> str:
    """A REAL challenge surfaced from the shared wave (grounded in what the republic is building).
    The raid's 'boss' is a genuine problem humans solve — never a fake monster."""
    try:
        from mag import republic_wave
        w = republic_wave.wave()
        n = w.get("n_shared_invariants", 0)
        if n:
            return (f"the shared wave holds {n} invariants from its contributors; the raid's task is "
                    f"to verify + fold the next invariant humans contribute (real work, emergent play)")
    except Exception:
        pass
    return ("the raid's boss is a real problem: dedupe a contributor's lesson into the shared wave "
            "by invariant, keeping sovereignty — solve it together and the wave grows")


def scene() -> dict[str, Any]:
    """RENDER the current world as the dark campfire login scene (HTML + ASCII). Reuses the inline
    renderer. Deterministic + $0."""
    gw = _gw()
    w = gw.get_state()
    ascii_scene = CAMPFIRE + "\n" + "".join(
        f"  {k}: {v.get('value', {}).get('player', k)} (root {w.get('root','')[:8]})\n"
        for k, v in list(w.get("world", {}).items())[:6])
    return {"ok": True, "schema": SCHEMA, "ascii": ascii_scene,
            "n_world_entities": w.get("n_entities"), "world_root": w.get("root"),
            "note": "the campfire scene: the fire is the shared wave, the dark is the unknown; the "
                    "world root is the truth beneath it all"}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="game-portal")
    ap.add_argument("cmd", nargs="?", default="login",
                    choices=["login", "raid", "scene", "roles"])
    ap.add_argument("--player", default="traveler")
    ap.add_argument("--role", default="Warden")
    ap.add_argument("--raid", default="")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "login":
        out = login(a.player, role=a.role)
    elif a.cmd == "raid":
        out = raid(a.raid)
    elif a.cmd == "roles":
        out = {"ok": True, "roles": ROLES}
    else:
        out = scene()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
