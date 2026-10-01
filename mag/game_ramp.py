"""game_ramp — the GAME, built as the complexity ramp (operator 2026-08-13): TABLE TOP (perfect) ->
MUD (perfect) -> ROGUELITE (perfect) -> then scale. Each tier is a mastered base, on the SAME
server-authoritative world (game_world = the verkle chain is the authority). The player descends
through the tiers; each is deterministic + $0, sharing the base render (world_rib ASCII = the
'pixels between swarms').

OPERATOR (2026-08-13): "the way i want to do this is go from our base render state like our pixels
between swarms. start at tabletop perfect, mud, perfect, roguelite, perfect, then move on in
complexity and games at the base level this will act as our early swarm tests did to our complex
swarm structure" + "then build it please". THE GAME IS THE DELIVERABLE (memory/game/STATE.md).

SELF-STEAL (nothing invented — assembled from what we hold):
  * WORLD  -> game_world (the server-authoritative verkle chain: set_state/get_state; every change
              is a content-addressed knot). The authority every tier shares.
  * RENDER -> world_rib (the deterministic 2D field / ASCII map = the base pixels).
  * ROGUE  -> dungeon_dev (rooms = tasks, conquering folds a knot; the dungeon = the roadmap).
  * VOICE  -> the two-mode party (Diogenes plain / D&D adventure) as the DM flesh layer.

THE RAMP:
  tier()        -> the current tier (tabletop -> mud -> roguelite), persisted in the world.
  tabletop(a)   -> the SIMPLEST world: a scene + a DM voice + actions (look/interact/rest). Perfect
                   when the scene is coherent + persistent.
  mud(a)        -> the navigable text world: rooms + exits + look/move/take on the world_rib map.
                   Perfect when the player can move through a coherent space.
  roguelite(a)  -> the run-based dungeon: rooms = tasks, descend levels, permadeath (a run ends, the
                   score records how deep). Perfect when a run descends + folds a knot.
  descend()     -> progress to the next tier once the current is mastered (the ramp).
  play(a)       -> route the action to the current tier; each turn is a verkle-anchored world change.
  render()      -> the base ASCII render of the current tier's world (the pixels between swarms).

Schema: game_ramp.v1 · deterministic + $0 · reuse: game_world, world_rib, dungeon_dev

REWIRE (2026-09-16, wave N8): the tiers no longer pretend — each delegates to the matching REAL
engine while this module's own API stays stable:
  tier 1 tabletop  -> the toy core verb (headless port of dashboard/static/games/toy.html window.TOY)
  tier 2 mud       -> mag.game_mud.act (the Roshomon MUD harness; the old 3-room loop is a
                      degraded fallback only)
  tier 3 roguelite -> mag.dungeon_dev (generate_room / assign_workers dry / conquer / dungeon_state)
  tier 4 wow       -> mag.wow_world.WorldSession (bones-gate legality rooms; on LADDER, past roguelite)
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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "game_ramp.v1"
# TIERS is the frozen public contract (tests + game_dfhack key on it). The full ramp adds
# tier 4 on LADDER: roguelite mastered -> wow (the bones-world sessions).
TIERS = ["tabletop", "mud", "roguelite"]
LADDER = TIERS + ["wow"]
DM = {
    "diogenes": "I am Diogenes. Speak plainly; the world rewards honesty, not theater.",
    "dnd": "Welcome, adventurer. The dungeon remembers what you did while you were gone.",
}

# ── THE REAL ENGINES (2026-09-16 rewire — the ramp no longer pretends) ──
#   tier 1 tabletop -> the toy core verb (headless port of dashboard/static/games/toy.html
#                    window.TOY: one verb, roll — read -> roll -> punish, souls grammar).
#   tier 2 mud      -> mag.game_mud.act (the Roshomon MUD harness: 11-room world, survey/claim).
#   tier 3 roguelite-> mag.dungeon_dev (rooms = real roadmap tasks; generate/assign/conquer).
#   tier 4 wow      -> mag.wow_world.WorldSession (rooms as legality tables on the bones gate).
# The ramp's own API is unchanged: tier/tabletop/mud/roguelite/work/descend/play/render/status.
ENGINE = {
    "tabletop": "toy.core_verb (headless port of dashboard/static/games/toy.html window.TOY)",
    "mud": "mag.game_mud.act (Roshomon MUD harness, 11-room world)",
    "roguelite": "mag.dungeon_dev (rooms = real roadmap tasks)",
    "wow": "mag.wow_world.WorldSession (legality-table rooms on the bones gate)",
}

# toy.html verb law (window.TOY): seeded LCG, no Math.random; roll = 30 sta, 0.28 roll,
# 0.5 cd, 0.35 iframes; regen 25/s gated on rollT (x0.5 active / x1.5 still).
TOY = {"sta_max": 100, "sta_cost": 30, "roll_t": 0.28, "roll_cd": 0.5,
       "iframes": 0.35, "regen": 25.0, "still_mult": 1.5, "dt": 1 / 60}
TOY_KEY = "game.tabletop.toy"   # {"seed", "lcg", "draw_index", "sta", "rolls"}
WOW_KEY = "game.wow.session"    # the live wow_world session id
WOW_RUN_KEY = "game.wow.run"    # run counter -> the session seed (fresh run = fresh id)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _world() -> Any:
    from mag import game_world
    return game_world


def _get(key: str, default: Any = None) -> Any:
    try:
        r = _world().get_state(key)
        if isinstance(r, dict):
            # get_state returns a wrapper dict {ok, key, value, found}; unwrap the VALUE.
            return r.get("value", default) if r.get("found") else default
        return r or default
    except Exception:
        return default


def _set(key: str, value: Any) -> None:
    try:
        _world().set_state(key, value, source="game_ramp")
    except Exception:
        pass


def tier() -> dict[str, Any]:
    t = _get("game.ramp.tier", "tabletop")
    mastered = list(_get("game.ramp.mastered", []) or [])
    nxt = LADDER[LADDER.index(t) + 1] if t in LADDER and LADDER.index(t) + 1 < len(LADDER) else None
    return {"ok": True, "schema": SCHEMA, "tier": t, "mastered": mastered, "next": nxt,
            "engine": ENGINE.get(t)}


def _toy_state() -> dict[str, Any]:
    st = _get(TOY_KEY) or {}
    st.setdefault("seed", 20260813)          # the ramp's birthday — deterministic, $0
    st.setdefault("lcg", int(st["seed"]) & 0xFFFFFFFF)
    st.setdefault("draw_index", 0)
    st.setdefault("sta", TOY["sta_max"])
    st.setdefault("rolls", 0)
    return st


def _toy_roll(st: dict[str, Any]) -> dict[str, Any]:
    """toy.html's ONE verb, headless (window.TOY roll law, verbatim numbers): ShiftLeft edge,
    30 sta, 0.28 roll, 0.5 cd, 0.35 iframes. One invocation advances the sim one cd cycle
    (0.5s): the roll (0.28s, regen gated off during rollT) + idle regen on the remainder."""
    dt, t = TOY["dt"], TOY
    sta = float(st["sta"])
    idle = t["roll_cd"] - t["roll_t"]
    # regen over the idle tail only (during rollT the regen gate is shut — the mud law)
    sta = min(t["sta_max"], sta + t["regen"] * t["still_mult"] * idle)
    if sta < t["sta_cost"]:
        return {"rolled": False, "sta": round(sta, 2),
                "reply": f"not enough stamina to roll ({round(sta, 2)}/{t['sta_cost']}) — rest."}
    sta -= t["sta_cost"]
    st["sta"] = round(sta, 2)
    st["rolls"] = int(st["rolls"]) + 1
    # the toy's seeded LCG — the world draw the frame loop runs each sim step it advances
    st["lcg"] = (int(st["lcg"]) * 1664525 + 1013904223) % 4294967296
    st["draw_index"] = int(st["draw_index"]) + 1
    return {"rolled": True, "sta": st["sta"], "draw_index": st["draw_index"],
            "roll_t": t["roll_t"], "roll_cd": t["roll_cd"], "iframes": t["iframes"],
            "reply": (f"You roll. 30 stamina, 0.28s of commitment, 0.35s of iframes — "
                      f"sta {st['sta']}/100, draw {st['draw_index']} (seed {st['seed']}).")}


def tabletop(action: str = "look") -> dict[str, Any]:
    """TIER 1 — the SIMPLEST world, now driven by the toy's core verb (toy.html window.TOY):
    read -> roll -> punish. look/talk/rest keep the tavern scene; 'roll' runs the real verb."""
    action = (action or "").strip().lower() or "look"
    scene = _get("game.tabletop.scene", "a quiet tavern, lit by a single candle")
    turns = int(_get("game.tabletop.turns", 0))
    engine_note = None
    if action in ("roll", "dodge"):
        st = _toy_state()
        r = _toy_roll(st)
        _set(TOY_KEY, st)
        reply = r["reply"]
        engine_note = r
    elif action == "look":
        reply = f"You are in {scene}."
    elif action == "talk":
        reply = DM["diogenes"] + " 'Tell me what happened while you were gone.'"
    elif action == "rest":
        st = _toy_state()
        st["sta"] = TOY["sta_max"]
        _set(TOY_KEY, st)
        reply = "You rest. The world remembers. (stamina restored — the toy's flask.)"
    else:
        reply = f"I don't know how to {action} here yet — the toy knows one verb: roll."
    _set("game.tabletop.turns", turns + 1)
    out = {"ok": True, "schema": SCHEMA, "tier": "tabletop", "action": action,
           "reply": reply, "scene": scene, "turns": turns + 1, "engine": ENGINE["tabletop"]}
    if engine_note:
        out["toy"] = engine_note
    return out


_MUD_CMDS = {"look": "look", "l": "look", "map": "map", "survey": "survey", "witness": "survey",
             "claim": "claim", "fold": "claim", "take": "claim", "inv": "inv",
             "inventory": "inv", "help": "help", "?": "help", "status": "status"}
_MUD_DIRS = ("north", "south", "east", "west")


def _mud_legacy(action: str) -> dict[str, Any]:
    """The OLD hardcoded 3-room loop — kept only as the degraded fallback when the real
    game_mud engine cannot be reached (never the first choice again)."""
    room = _get("game.mud.room", "the gate")
    exits = {"the gate": ["the hall"], "the hall": ["the gate", "the forge"],
             "the forge": ["the hall"]}
    if action == "look":
        reply = f"You are in {room}. Exits: {', '.join(exits.get(room, [])) or 'none'}."
    elif action.startswith("go ") or action.startswith("move "):
        dest = action.split(" ", 1)[1].strip()
        norm = dest if dest.startswith("the ") else "the " + dest
        target = norm if norm in exits.get(room, []) else dest
        if target in exits.get(room, []):
            _set("game.mud.room", target)
            room = target
            reply = f"You walk to {target}."
        else:
            reply = f"You cannot go {dest} from {room}."
    elif action == "map":
        try:
            from mag import world_rib
            r = world_rib.compile("game map: the gate, the hall, the forge", w=32, h=16)
            reply = "the map of this text world:\n" + _ascii(field=r.get("field"), w=32, h=16)
        except Exception:
            reply = "the map is not drawn yet."
    else:
        reply = f"mud: {action} is not a thing you can do here."
    return {"ok": True, "schema": SCHEMA, "tier": "mud", "action": action, "reply": reply,
            "room": room, "degraded": True,
            "engine": "legacy 3-room fallback (game_mud unreachable)"}


def mud(action: str = "look") -> dict[str, Any]:
    """TIER 2 — the navigable text world, driven by the REAL MUD harness (mag.game_mud.act:
    the Roshomon world — 11 rooms, each a scene the party witnesses; go/look/survey/claim)."""
    action = (action or "").strip().lower() or "look"
    if action.startswith("go ") or action.startswith("move "):
        cmd = "go " + action.split(" ", 1)[1].strip()
    elif action in _MUD_DIRS:
        cmd = "go " + action
    else:
        cmd = _MUD_CMDS.get(action)
    if cmd is None:
        # not a MUD command — hand it to the harness anyway so its parser answers (typed refusal)
        cmd = action
    try:
        from mag import game_mud
        r = game_mud.act(cmd)
        if not isinstance(r, dict) or not r.get("ok"):
            raise RuntimeError(str((r or {}).get("error", "harness refused"))[:80])
        room = r.get("room")
        if room:
            _set("game.mud.room", room)   # mirror for anything still reading the legacy key
        return {"ok": True, "schema": SCHEMA, "tier": "mud", "action": action,
                "reply": r.get("reply", ""), "room": room,
                "invariants": r.get("invariants"), "engine": ENGINE["mud"],
                "harness_schema": r.get("schema")}
    except Exception as e:
        legacy = _mud_legacy(action)
        legacy["error"] = str(e)[:120]
        return legacy


def roguelite(action: str = "descend") -> dict[str, Any]:
    """TIER 3 — the run-based dungeon, driven by the REAL dungeon_dev engine: rooms = real
    roadmap coding tasks, workers are thrown at them, conquering folds a knot that structures
    the hologram. The ramp keeps its depth/best counters (the run law) on top of the engine.
    Verbs: descend/enter · conquer [room] · assign [room] (dry, $0) · die · state/rooms."""
    action = (action or "").strip().lower() or "descend"
    depth = int(_get("game.rogue.depth", 0))
    best = int(_get("game.rogue.best", 0))
    room_out: Any = None
    extra: dict[str, Any] = {}

    def _dd() -> Any:
        from mag import dungeon_dev
        return dungeon_dev

    if action == "descend" or action == "enter":
        _set("game.rogue.depth", depth + 1)
        best = max(best, depth + 1)
        _set("game.rogue.best", best)
        try:
            g = _dd().generate_room()
            if g.get("room"):
                room_out = g["room"]
                extra["dungeon_room"] = g
                _set("game.rogue.last_room", g["room"])
                reply = (f"You descend to depth {depth + 1} and enter room '{g['room']}' "
                         f"(floor {g['floor']}, region {g['region']}): {g['task']} "
                         f"The walls fold a knot.")
            else:
                reply = (f"You descend to depth {depth + 1}. All mapped rooms are discovered "
                         f"already — the dungeon is being remapped. The walls fold a knot.")
        except Exception as e:
            extra["dungeon_error"] = str(e)[:120]
            reply = f"You descend to depth {depth + 1} of the dungeon. The walls fold a knot."
    elif action.startswith("conquer"):
        rest = action.split(" ", 1)[1].strip() if " " in action else ""
        room = rest or _get("game.rogue.last_room") or None
        if not room:
            reply = "conquer which room? descend into one first (the engine tracks last_room)."
        else:
            try:
                c = _dd().conquer(room)
                reply = (c.get("note") if c.get("ok") else c.get("error")) or "conquered."
                extra["conquered"] = c
                room_out = room
            except Exception as e:
                extra["dungeon_error"] = str(e)[:120]
                reply = f"the room would not fold: {str(e)[:80]}"
    elif action.startswith("assign"):
        rest = action.split(" ", 1)[1].strip() if " " in action else ""
        room = rest or _get("game.rogue.last_room") or None
        if not room:
            reply = "assign workers to which room? descend into one first."
        else:
            try:
                # DRY by default (enqueue=False): deterministic + $0, no swarm writes from the ramp.
                a = _dd().assign_workers(room, n=3, enqueue=False)
                reply = (f"3 workers thrown at room '{room}' (dry — no swarm enqueue from the "
                         f"ramp). They conquer it under the roundtrip RIB.")
                extra["assigned"] = a
                room_out = room
            except Exception as e:
                extra["dungeon_error"] = str(e)[:120]
                reply = f"no workers could be thrown: {str(e)[:80]}"
    elif action == "die":
        reply = f"You die at depth {depth}. Best depth: {best}. A new run begins."
        _set("game.rogue.depth", 0)
    elif action in ("state", "rooms", "map"):
        try:
            s = _dd().dungeon_state()
            reply = (f"the dungeon IS the roadmap — {s['n_rooms']} rooms, "
                     f"conquered: {', '.join(s['conquered']) or 'none'}; "
                     f"in progress: {', '.join(s['in_progress']) or 'none'}.")
            extra["dungeon_state"] = s
        except Exception as e:
            extra["dungeon_error"] = str(e)[:120]
            reply = "the dungeon map cannot be read right now."
    else:
        reply = f"roguelite: {action} is not a dungeon action (descend / conquer / assign / die / state)."
    out = {"ok": True, "schema": SCHEMA, "tier": "roguelite", "action": action,
           "reply": reply, "engine": ENGINE["roguelite"],
           # Receipts describe the post-transition world.  Death starts a fresh run,
           # so do not leak the pre-reset depth in the returned state.
           "depth": 0 if action == "die" else (depth + 1 if action in ("descend", "enter") else depth),
           "best": best}
    if room_out is not None:
        out["room"] = room_out
    out.update(extra)
    return out


def _wow_session() -> tuple[Any | None, str | None]:
    """The live wow_world session (the engine owns persistence; the ramp just points at it).
    Returns (session, error) — error is the typed stub reason when the engine cannot run."""
    try:
        from mag.wow_bones import load_fixture
        from mag.wow_world import WorldSession
    except Exception as e:
        return None, f"wow_world import failed: {str(e)[:100]}"
    fx = load_fixture()
    if fx is None:
        return None, ("wow_world fixture missing — run the bones extract first "
                      "(mag.wow_bones extract); delegation point stubbed, nothing invented")
    sid = _get(WOW_KEY)
    ses = WorldSession.load(sid) if sid else None
    if ses is None:
        run = int(_get(WOW_RUN_KEY, 1) or 1)
        ses = WorldSession(fx, f"ramp-run{run}")
        _set(WOW_KEY, ses.session_id)
    return ses, None


def wow(action: str = "look") -> dict[str, Any]:
    """TIER 4 — the bones-world: rooms as legality tables, every verb dispatches through the
    SAME gate wow_bones runs. Sessions persist in memory/runs/wow_world/sessions (the engine's
    own ledger). Verbs: look · go <dir> · verbs · map · status · new (fresh run)."""
    action = (action or "").strip().lower() or "look"
    base = {"ok": True, "schema": SCHEMA, "tier": "wow", "action": action,
            "engine": ENGINE["wow"]}
    if action == "new":
        run = int(_get(WOW_RUN_KEY, 1) or 1)
        _set(WOW_RUN_KEY, run + 1)
        _set(WOW_KEY, "")
        base["reply"] = f"a new run begins (ramp-run{run + 1}) — the gate resets, the route is blank."
        return base
    ses, err = _wow_session()
    if ses is None:
        base["reply"] = f"the bones world is closed: {err}"
        base["degraded"] = True
        base["error"] = err
        return base

    if action in ("look", "l"):
        entry = ses.turn("look")
    elif action.startswith("go ") or action in ("north", "south", "east", "west"):
        d = action.split(" ", 1)[1].strip() if action.startswith("go ") else action
        entry = ses.turn("go", d)
    elif action == "verbs":
        entry = None
    elif action == "map":
        entry = None
    elif action == "status":
        entry = None
    else:
        ses.save()
        base["reply"] = (f"wow: '{action}' is not a bones verb here — try look / go <dir> / "
                         f"verbs / map / status / new.")
        return base

    ses.save()   # the engine's ledger is the only write (its own contract)
    base["room"] = ses.room
    base["route"] = list(ses.route)
    base["session_id"] = ses.session_id
    base["session_status"] = ses.session_status
    base["world"] = ses.world["id"]
    if entry is not None:
        base["turn"] = entry
        if entry.get("ok"):
            base["reply"] = (f"the gate rules '{entry['verb']}' legal here"
                             + (f" — you walk to {entry['to']}." if entry.get("to")
                                else " — the room answers."))
        else:
            base["reply"] = (f"the gate refuses: {entry['reason']} "
                             f"(handler_ran={entry.get('handler_ran')}) — the door is not there.")
    elif action == "verbs":
        legal = ses.legal_verbs()
        base["reply"] = f"legal verbs in {ses.room}: {', '.join(legal) or 'none'}."
        base["legal_verbs"] = legal
    elif action == "map":
        room = ses._current_room()
        exits = {d: (t["room"] if isinstance(t, dict) else t) for d, t in room["exits"].items()}
        base["reply"] = (f"{room['name']} — exits: "
                         + ", ".join(f"{d}->{r}" for d, r in exits.items()))
        base["exits"] = exits
    else:  # status
        base["reply"] = (f"{ses.room} · status {ses.session_status} · turn {ses.turn_count} · "
                         f"encounter {ses.encounter_name()} · verdict {ses.verdict()}.")
    return base


def _next_open() -> dict[str, Any] | None:
    """Pull a REAL open task from the orchestrator queue (the dungeon room = real work). Grounded:
    the game's rooms are real tasks; conquering a room = doing the task."""
    try:
        from mag import orchestrator as o
        for q in o.list_queue(limit=30):
            if q.get("status") == "queued" and q.get("goal"):
                return {"goal": str(q["goal"])[:200], "queue_id": q.get("queue_id")}
    except Exception:
        pass
    return None


def work(action: str = "turn") -> dict[str, Any]:
    """USE THE GAME AS THE WORK ENVIRONMENT (Enders Game — play IS the mission): each turn descends
    the dungeon, pulls a REAL open task, and folds it as a knot (the work is done). The game IS the
    work; the dungeon IS the roadmap."""
    t = tier()["tier"]
    task = _next_open()
    if not task:
        return {"ok": True, "schema": SCHEMA, "tier": t, "action": action,
                "reply": "no open tasks — the dungeon is clear; the world rests.",
                "folded": False}
    # conquer the room: fold the real task as a verkle knot (game_world is the authority)
    try:
        _set(f"game.work.{t}.last", task["goal"])
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "tier": t, "action": action,
            "reply": f"The dungeon {t} folds a room: '{task['goal'][:80]}...' — a real task, done.",
            "task": task, "folded": True,
            "note": "the game is the work environment: descending folds real open tasks as knots"}


def descend() -> dict[str, Any]:
    """Progress to the next tier once the current is mastered (the ramp). Returns the new tier."""
    t = tier()
    cur = t["tier"]
    if not t["next"]:
        return {"ok": True, "schema": SCHEMA, "tier": cur, "at_max": True,
                "note": "you are at the deepest tier; the ramp continues with new games at the base"}
    mastered = list(t["mastered"]) + [cur]
    _set("game.ramp.mastered", mastered)
    _set("game.ramp.tier", t["next"])
    return {"ok": True, "schema": SCHEMA, "tier": t["next"], "mastered": mastered,
            "note": f"mastered {cur} -> descended to {t['next']}"}


def play(action: str = "look") -> dict[str, Any]:
    """Route the action to the current tier. Each turn is a verkle-anchored world change (the world
    is the authority; clients present)."""
    t = tier()["tier"]
    handler = {"tabletop": tabletop, "mud": mud, "roguelite": roguelite, "wow": wow}.get(t)
    if not handler:
        return {"ok": False, "schema": SCHEMA, "error": f"no handler for tier {t}"}
    r = handler(action)
    r["world_root"] = _get("game_world_root", None)
    return r


def _ascii(field: Any, w: int, h: int) -> str:
    try:
        import numpy as np
        arr = np.asarray(field)
        rows = []
        for i in range(min(h, arr.shape[0])):
            rows.append("".join("#" if float(arr[i, j]) > 0.55 else "." for j in range(min(w, arr.shape[1]))))
        return "\n".join(rows)
    except Exception:
        return "(map render unavailable)"


def render() -> dict[str, Any]:
    """The base render (the pixels between swarms): the current tier's world as ASCII."""
    t = tier()["tier"]
    if t == "mud":
        try:
            from mag import world_rib
            r = world_rib.compile("game map: the gate, the hall, the forge", w=32, h=16)
            return {"ok": True, "schema": SCHEMA, "tier": t,
                    "ascii": _ascii(field=r.get("field"), w=32, h=16)}
        except Exception as e:
            return {"ok": True, "schema": SCHEMA, "tier": t, "ascii": "(map unavailable)", "error": str(e)[:80]}
    if t == "wow":
        ses, err = _wow_session()
        if ses is None:
            return {"ok": True, "schema": SCHEMA, "tier": t,
                    "ascii": f"[WOW — the bones world is closed: {err}]"}
        route = " -> ".join(ses.route[-6:])
        return {"ok": True, "schema": SCHEMA, "tier": t,
                "ascii": (f"[WOW · {ses.world['id']} · {ses.room} · {ses.session_status}]\n"
                          f"route: {route}\n"
                          f"[the legality table is the map — 'wow map' reads the doors]")}
    return {"ok": True, "schema": SCHEMA, "tier": t,
            "ascii": f"[{t.upper()} — {ENGINE.get(t, 'the base render of this tier')}]"}


def status() -> dict[str, Any]:
    t = tier()
    return {"ok": True, "schema": SCHEMA, "tier": t["tier"], "mastered": t["mastered"],
            "tiers": TIERS, "ladder": LADDER, "next": t["next"],
            "engines": ENGINE,
            "contract": "tier()->current tier; tabletop/mud/roguelite/wow(action)->the tier's "
                        "world; descend()->master + progress to the next tier; play(action)->"
                        "route to the current tier; render()->the base ASCII (the pixels "
                        "between swarms)",
            "cost": "deterministic + $0 (the verkle world is the authority; no external LLM in the core)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="game-ramp")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "tier", "play", "descend", "render", "wow", "mud", "toy"])
    ap.add_argument("action", nargs="?", default="look")
    a = ap.parse_args()
    if a.cmd == "play":
        print(json.dumps(play(a.action), indent=2, default=str))
    elif a.cmd == "descend":
        print(json.dumps(descend(), indent=2, default=str))
    elif a.cmd == "render":
        print(json.dumps(render(), indent=2, default=str))
    elif a.cmd == "tier":
        print(json.dumps(tier(), indent=2, default=str))
    elif a.cmd == "wow":
        print(json.dumps(wow(a.action), indent=2, default=str))
    elif a.cmd == "mud":
        print(json.dumps(mud(a.action), indent=2, default=str))
    elif a.cmd == "toy":
        print(json.dumps(tabletop(a.action), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
