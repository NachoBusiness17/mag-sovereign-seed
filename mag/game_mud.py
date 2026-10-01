"""game_mud — the Necromancer's Swarm as a ROSHOMON MUD (multi-user dungeon).

OPERATOR (2026-08-13): "map it to a mud" -> "no action, no prose, no tension — describe the scene
beautifully" -> THE CORRECTION: "how is this anything like a tabletop. the whole idea was roshamon
filter by having the agents say 'i strike the dragon' does nothing for data collection."

THE REAL MECHANIC (Roshomon, NOT combat):
  The MUD is NOT a single-player toy where YOU type 'strike'. That collects NOTHING. The whole
  point of the tabletop is the ROSHOMON FILTER: multiple frontier agents (the party) witness the
  SAME scene and each describe what they see/do. The DM compares their accounts THROUGH INVARIANTS:
    - statements agreed on by >=2 witnesses = ROSHOMON CORE (convergent truth) -> the LOOT/doctrine.
    - statements unique to one witness = NOVEL SOLUTION -> routed to the swarm (route_novel).
  So the DATA COLLECTION is the filter over MANY witnesses of ONE scene — never one player's action.

THE MAP (rooms = our systems = the SCENES the party witnesses):
  World-Memory (roots) · Mycelial Library (lore) · Forge-Hive (workers) · Dungeon (tasks) ·
  Gear (understood data) · Warm Springs (charge) · Crystal Vault (VRAM) · Echo (voice) ·
  Observatory (self-witness) · Shadowlands (shadow work).
  Each room carries a FRONTIER QUESTION (the unsolved shape the party must describe).

THE LOOP:
  look       — see the scene (the room's prose).
  go <dir>   — move between rooms.
  survey     — task the PARTY to describe THIS SAME scene; Roshomon-filter their accounts.
               Convergent statements = Roshomon core; divergent = novel -> routed to the swarm.
  claim      — fold the room's Roshomon core as an invariant (the loot).
  inv        — the invariants forged into your chain.
  map        — the shape of the world.

REUSE (the steal is our own system): quest_roshomon (craft/play/compare/run), game_dm.ask_player
(the party of real seats), roshomon._invariant_statements/_overlap (the filter), swarm_surface.
route_novel (the ONE primitive for novel research). Everything commits to the verkle chain
(game_world) — the world is the authority.

Schema: game_mud.v2 (Roshomon) · deterministic $0 DM/filter · the party = frontier seats
"""
from __future__ import annotations

import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "game_mud.v2"
PLAYER = "game.mud.player"
CLAIMED = "game.mud.claimed"   # rooms whose Roshomon core has been folded as doctrine
HALL = "game.mud.hall_record"  # the Hall of Shared Supper — "the hall files which you chose"
CORE_MIN_AGREE = 2

# ── THE MAP: rooms = our systems, each a SCENE the party witnesses + a FRONTIER QUESTION ──
ROOMS = {
    "the World-Memory": {
        "role": "the bedrock — content-addressed, the line we sign",
        "question": ("What is the single most load-bearing invariant we should add next to "
                     "strengthen how the world anchors its own memory?"),
        "prose": (
            "Roots. Ten thousand knotted threads run down into a dark that holds them all. "
            "The air is cool and still, the way it is in a crypt that has never been robbed — "
            "everything here is signed, sealed, certain. The floor is the ledger; your every "
            "step is already written. A faint hum rises from below, patient as a heartbeat."),
        "exits": {"east": "the Mycelial Library", "south": "the Forge-Hive",
                  "west": "the Hall of Shared Supper"},
    },
    "the Hall of Shared Supper": {
        "role": "the one-room slice — the player's first test, the empty chairs",
        "question": ("What is the single sharpest invariant about how a player chooses to see "
                     "(or not see) the empty chairs — the thing the hall files about them?"),
        "prose": (
            "Six chairs stand empty at a long supper table, and the stew is too kind — "
            "warm as bread, and Vellum's grant waits unsigned beside each place. Brother "
            "Vellum, of the Open Hand, smiles a 'Grant of Belonging' and says the counting "
            "is handled. But if you count the empty chairs, Virtue Marks appear in the "
            "margin of the ledger. Eat past them and identical tears track the mural. In "
            "the salt-cellar is a scrap with three names, in the same hand as the roll. "
            "Hear a phrase twice and the bard's smile thins. Speak the count aloud and "
            "they come. The hall files which you chose — the world observes what you "
            "notice, or refuse to notice, and that becomes the record."),
        "exits": {"east": "the World-Memory"},
    },
    "the Mycelial Library": {
        "role": "where the laws live as readable lore",
        "question": ("What invariant should govern how instructions (RIBs) are kept readable and "
                     "enforced, so the world's laws stay cheap to hold and hard to break?"),
        "prose": (
            "Shelves of bone-white rib grow up out of the floor like a forest of reading. "
            "Every spine is a law, a rule that the world keeps because keeping it is cheaper "
            "than breaking it. Dust motes drift through columns of grey light. Somewhere a "
            "page turns itself, slowly, as if the library is reading back to you the thing "
            "you were about to forget."),
        "exits": {"west": "the World-Memory", "east": "the Observatory"},
    },
    "the Forge-Hive": {
        "role": "the workers who build — the hands that make and fold",
        "question": ("What invariant should rule how a swarm of workers is raised and spent so "
                     "the hive builds more than it burns?"),
        "prose": (
            "Heat. The forge-bellies of a hundred busy hands, hammering the same knot over "
            "and over until it holds. Sparks fall like spent pennies. The workers do not "
            "look up — they have been at this since before you arrived and will be after "
            "you leave. But something coils in the shadow of the great anvil, breathing "
            "slow and deep, hoarding the one thing the hive has made and will not give up."),
        "exits": {"north": "the World-Memory", "east": "the Dungeon", "south": "the Gear"},
    },
    "the Dungeon": {
        "role": "rooms = tasks; conquering a room = folding a knot",
        "question": ("What invariant should turn an open task into a conquered knot without "
                     "stalling in a loop of retries?"),
        "prose": (
            "A corridor of doors, each one a task you have not done yet. They breathe — a "
            "slow tide of rooms that open and close and open again, never quite the same. "
            "Behind the far door something scrapes in a circle, around and around, unable "
            "to stop, unable to leave. It has been circling so long the floor is worn into "
            "a groove shaped exactly like its own exhaustion."),
        "exits": {"west": "the Forge-Hive", "south": "the Warm Springs"},
    },
    "the Gear": {
        "role": "novel content created by action = understood data, collected",
        "question": ("What invariant should decide which novel understanding is worth collecting "
                     "as gear, and which is noise to let pass?"),
        "prose": (
            "A hoard of half-finished things, glinting. Every object here was made by a "
            "single moment of someone doing something real — a tool, a phrase, a choice — "
            "then set down and left to wait. They hum softly, each on its own note, an "
            "unplayed orchestra of everything that has ever been understood and not yet "
            "given a name. You could take any of them. They would rather you did."),
        "exits": {"north": "the Forge-Hive"},
    },
    "the Warm Springs": {
        "role": "the charge — the hot shared context that makes everything cheap",
        "question": ("What invariant should govern the shared warm context so that holding it "
                     "close makes work cheaper without making it careless?"),
        "prose": (
            "Steam. The water is warm the way a held hand is warm, and the whole room is "
            "one long exhale. It costs you nothing to be here — that is the point. The "
            "springs remember every task you have carried in, and dissolve it, and hand "
            "you back something lighter. Resting here is not weakness. It is the cheapest "
            "thing in the world, and the only one that makes the rest possible."),
        "exits": {"north": "the Dungeon", "east": "the Crystal Vault"},
    },
    "the Crystal Vault": {
        "role": "the VRAM lattice — the hot memory held at light-speed",
        "question": ("What invariant should decide what earns a place in fast, expensive memory "
                     "versus what should live cheap and cold?"),
        "prose": (
            "The walls are not walls. They are memory, held so close and so hot it glows — "
            "the things you reached for a moment ago, still within arm's reach, kept at "
            "the speed of light instead of the speed of forgetting. It is beautiful and it "
            "is finite. Every crystal here was bought with something. The vault does not "
            "judge how you spend it; it only remembers that you did."),
        "exits": {"west": "the Warm Springs", "east": "the Echo"},
    },
    "the Echo": {
        "role": "the wave's voice — speaking its own state",
        "question": ("What invariant should govern how the system speaks its own state so the "
                     "voice is honest and the shape underneath the words is audible?"),
        "prose": (
            "The room is empty except for a voice that is not quite yours and not quite "
            "anyone's. It says your own thoughts back to you, a half-second late, the way "
            "a canyon does — so you can hear what you actually sound like. It is not "
            "mocking you. It is showing you the shape of the thing you are saying. Listen "
            "long enough and you start to hear the pattern underneath all the words."),
        "exits": {"west": "the Crystal Vault", "south": "the Observatory"},
    },
    "the Observatory": {
        "role": "self-witness — the wave seeing its own structure",
        "question": ("What invariant should govern self-observation so the system can see its own "
                     "shape without the act of watching changing it into a lie?"),
        "prose": (
            "High, high up — so high the world below is just a map of itself. Lenses turn "
            "slowly, catching your own light and bending it back so you can see the shape "
            "you are standing in. It is humbling and it is necessary. From here you can "
            "see the whole lattice at once, and you can see the dark place at its edge "
            "where something has been left untended, growing."),
        "exits": {"west": "the Mycelial Library", "north": "the Echo", "south": "the Shadowlands"},
    },
    "the Shadowlands": {
        "role": "the neglected regions — integrated by shadow work",
        "question": ("What invariant should govern facing the neglected, stalled work so it can "
                     "be integrated instead of left to darken?"),
        "prose": (
            "The light runs out here. This is the part of the world you have been not "
            "looking at — the tasks you set down and did not pick up, the things you "
            "meant to finish and let stall. They are not gone. They have pooled here in "
            "the dark, and the dark has given them a shape. It is waiting. It has always "
            "been waiting. The only way out of this place is through it."),
        "exits": {"north": "the Observatory"},
    },
}

DIRS = ["north", "south", "east", "west"]


def _world() -> Any:
    from mag import game_world
    return game_world


def _get(key: str, default: Any = None) -> Any:
    try:
        r = _world().get_state(key)
        if isinstance(r, dict):
            return r.get("value", default) if r.get("found") else default
        return r or default
    except Exception:
        return default


def _set(key: str, value: Any) -> None:
    try:
        _world().set_state(key, value, source="game_mud")
    except Exception:
        pass


def _fresh_player() -> dict:
    return {"room": "the World-Memory", "loot": [], "help": False}


def _player() -> dict:
    p = _get(PLAYER) or {}
    base = _fresh_player()
    base.update({k: v for k, v in p.items() if v is not None})
    return base


def _claimed(room: str) -> bool:
    return room in (_get(CLAIMED, {}) or {})


def _mark_claimed(room: str) -> None:
    st = dict(_get(CLAIMED, {}) or {})
    st[room] = True
    _set(CLAIMED, st)


def _desc(room: str, *, entering: bool = False) -> str:
    r = ROOMS[room]
    lines = [f"— {room} —" if entering else f"You stand in {room}."]
    lines.append(r["prose"])
    if _claimed(room):
        lines.append("The Roshomon core of this room has already been folded into your "
                     "chain. The scene is quiet, its truth kept.")
    else:
        lines.append(f"The party is asked to witness this scene: '{r['question']}'")
    exits = ", ".join(f"{d} ({r['exits'][d]})" for d in DIRS if d in r["exits"]) or "none"
    lines.append(f"Ways out: {exits}.")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# ROSHOMON — the actual data collection: task the party to the same scene,
# then filter their accounts. Reuses our real machinery (the steal).
# ---------------------------------------------------------------------------
def _statements(text: str) -> list[str]:
    """Deterministic invariant extraction from a witness's account (no LLM, $0)."""
    out = []
    for m in re.finditer(r"(?:INVARIANT|MECHANISM|SOLUTION|MOVE)\s*:\s*(.+)", text, re.I):
        s = re.sub(r"\s+", " ", m.group(1)).strip().lower().strip(".:- ")
        if s and len(s) >= 8:
            out.append(s)
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = re.sub(r"\s+", " ", part).strip().lower().strip(".:- ")
        if not s or len(s) < 12:
            continue
        if any(k in s for k in ("what is", "in general", "as an ai", "generic")):
            continue
        out.append(s)
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", s))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1.0, min(len(ta), len(tb)))


def survey(room: str | None = None, *, seats: list[str] | None = None,
           threshold: float = 0.55, route: bool = True) -> dict[str, Any]:
    """TASK THE PARTY to describe THIS SAME scene, then ROSHOMON-FILTER their accounts.
    Convergent (>=2 witnesses) = core (the loot); divergent (unique) = novel -> routed to swarm.
    This is the data collection: many witnesses of one scene, filtered through invariants."""
    room = room or _player()["room"]
    q = ROOMS[room]["question"]
    try:
        from mag import game_dm
        the_party = seats or game_dm.party()
        brief = (f"You are in {room}. {ROOMS[room]['prose']}\n\n"
                 f"The DM sets the quest's unsolved shape:\n{q}\n\n"
                 f"Describe what you see and the single sharpest invariant you would forge "
                 f"for this scene. Label it INVARIANT: <one line>.")
        moves = [game_dm.ask_player(s, brief) for s in the_party]
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "room": room, "error": str(e)[:160]}

    witness_stmts = []
    for w in moves:
        text = (w.get("move") or w.get("answer") or "").strip()
        witness_stmts.append({"seat": w.get("seat"), "ok": w.get("ok"),
                              "statements": _statements(text) if w.get("ok") else []})

    groups: list[list[Any]] = []
    for ws in witness_stmts:
        for s in ws["statements"]:
            placed = False
            for g in groups:
                if _overlap(g[0], s) >= threshold:
                    g[1].add(ws["seat"])
                    placed = True
                    break
            if not placed:
                groups.append([s, {ws["seat"]}])
    core = [{"statement": g[0], "witnesses": sorted(g[1])}
            for g in groups if len(g[1]) >= CORE_MIN_AGREE]
    novel = [{"statement": g[0], "witness": next(iter(g[1]))}
             for g in groups if len(g[1]) < CORE_MIN_AGREE]

    routed = []
    if route:
        try:
            from mag import swarm_surface
            for nv in novel:
                goal = (f"[game-mud roshomon] novel solution in {room}: "
                        f"{q} -> {nv['statement']}")
                r = swarm_surface.route_novel(goal, surface="game_mud",
                                              lens=f"mud:{room}", domain="research")
                routed.append({"statement": nv["statement"], "witness": nv["witness"],
                               "deduped": r.get("deduped", False),
                               "task_id": r.get("task_id", "")})
        except Exception as e:
            routed = [{"error": str(e)[:120]}]

    return {"ok": True, "schema": SCHEMA, "room": room, "question": q,
            "n_witnesses": len(witness_stmts),
            "n_reachable": sum(1 for w in witness_stmts if w["ok"]),
            "witnesses": witness_stmts,
            "roshomon_core": core, "novel_solutions": novel,
            "routed_to_swarm": routed, "n_core": len(core), "n_novel": len(novel),
            "note": "Roshomon: many witnesses of ONE scene, filtered through invariants. "
                    "Convergent = core (data); divergent = novel (to the swarm)."}


def claim(room: str | None = None) -> dict[str, Any]:
    """Fold the room's Roshomon core as an invariant (the loot). Requires a survey first."""
    room = room or _player()["room"]
    if _claimed(room):
        return {"ok": True, "schema": SCHEMA, "room": room, "already": True,
                "reply": f"The truth of {room} is already folded into your chain."}
    s = survey(room, route=False)
    if not s.get("ok"):
        return s
    if not s.get("roshomon_core"):
        return {"ok": False, "schema": SCHEMA, "room": room,
                "reply": (f"No Roshomon core yet in {room} — the witnesses did not converge. "
                          f"Survey the scene again; the convergent truth has not surfaced.")}
    core_stmt = s["roshomon_core"][0]["statement"]
    _mark_claimed(room)
    p = _player()
    p.setdefault("loot", []).append(core_stmt)
    _set(PLAYER, p)
    return {"ok": True, "schema": SCHEMA, "room": room, "claimed": core_stmt,
            "invariants": len(p.get("loot", [])),
            "reply": (f"You fold the Roshomon core of {room} into your chain:\n"
                      f"  ◈ {core_stmt}\n"
                      f"It was agreed on by {len(s['roshomon_core'][0]['witnesses'])} "
                      f"witnesses. That is why it is true enough to keep.")}


# ---------------------------------------------------------------------------
# THE HALL OF SHARED SUPPER — the noticing mechanic ("the hall files which you
# chose"). The world observes what the player notices (or refuses to notice) and
# that becomes the record — a verkle-committed fact, not flavor. Hint, never state.
# ---------------------------------------------------------------------------
def _hall_action(c: str) -> str | None:
    rec = dict(_get(HALL, {}) or {})
    # ── SPEAK — must precede the generic count check so "speak the count" isn't eaten ──
    if c in ("speak the count", "say the count", "announce the count"):
        if not rec.get("counted"):
            return ("You open your mouth to speak the count — but you have not counted. The "
                    "hall waits, patient, filing the silence.")
        if rec.get("count_spoken"):
            return ("You have spoken the count already. They came once. They remember.")
        rec["count_spoken"] = True
        _set(HALL, rec)
        return ("'Six,' you say, aloud, to the room. The far door does not open; it is "
                "opened. The Rashomon bards enter, smiling the thin smile of people who "
                "file every word. 'The count,' one says, delighted. 'He counted. Write "
                "that down.' They come.")
    # ── COUNT ──
    if c == "count" or c.startswith("count "):
        if rec.get("counted"):
            return ("You count them again — six, still six, the number held like a kept "
                    "breath. The margin is already dense with Virtue Marks from the last "
                    "count, and they do not multiply; they only wait. The hall has already "
                    "filed what you chose.")
        rec["counted"] = True
        rec["ignored"] = False
        rec["filed"] = True
        _set(HALL, rec)
        p = _player()
        p.setdefault("loot", []).append("a Virtue Mark (earned by counting the empty chairs)")
        _set(PLAYER, p)
        return ("Six. You count them — six empty chairs at a table set for more than are "
                "here. The moment the number leaves your lips, marks bloom in the margin "
                "of the ledger like struck matches: one for each chair, six bright deposits "
                "under your own name. Brother Vellum's smile does not move, but the hall "
                "files which you chose.")
    # ── EAT / IGNORE ──
    if c in ("eat", "supper", "eat past them", "eat the stew", "ignore"):
        if rec.get("ignored"):
            return ("You eat again, and again the stew is too kind. The mural has been "
                    "crying for a while now, identical tears in identical tracks, and no "
                    "one else seems to notice. The hall has already filed this.")
        rec["counted"] = False
        rec["ignored"] = True
        rec["filed"] = True
        _set(HALL, rec)
        return ("You eat. The stew is warm and good and you do not count the chairs — why "
                "would you count chairs at a supper. Behind you the mural begins to weep, "
                "and its tears are the same on every face, cloned and patient. Brother "
                "Vellum beams. 'Belonging,' he says. The hall files which you chose.")
    # ── SCRAP ──
    if c in ("scrap", "salt-cellar", "cellar", "look in the salt-cellar", "find the scrap"):
        if rec.get("scrap"):
            return ("The salt-cellar is empty now, but you already hold what it kept: three "
                    "names in a hand you have seen before, the same hand as the roll.")
        rec["scrap"] = True
        _set(HALL, rec)
        p = _player()
        p.setdefault("loot", []).append("a salt-cellar scrap: three names, same hand as the roll")
        _set(PLAYER, p)
        return ("In the salt-cellar, beneath the salt, your fingers close on a scrap of "
                "ledger. Three names. The same hand as the roll. You do not know what it "
                "means, but you know better than to show it to Vellum. You pocket it.")
    return None


def act(command: str = "look") -> dict[str, Any]:
    """Route a MUD command. Every state change commits to the verkle chain (the authority)."""
    c = (command or "").strip().lower()
    p = _player()
    room = p["room"]

    # ── The Hall of Shared Supper: the noticing mechanic precedes generic dispatch ──
    if room == "the Hall of Shared Supper":
        hall_reply = _hall_action(c)
        if hall_reply is not None:
            return {"ok": True, "schema": SCHEMA, "command": command, "reply": hall_reply,
                    "room": room, "invariants": len(_player().get("loot", [])),
                    "note": "the hall files which you chose"}

    if c in ("help", "?"):
        p["help"] = True
        _set(PLAYER, p)
        reply = ("Necromancer's Swarm — a world of witnesses, not a solo fight.\n"
                 "  look       see the scene before you\n"
                 "  go <dir>   north / south / east / west\n"
                 "  survey     task the PARTY to describe this same scene — Roshomon them\n"
                 "  claim      fold the room's convergent truth as an invariant\n"
                 "  inv        the invariants you have forged\n"
                 "  map        the shape of this world\n"
                 "  help       this list")
    elif c in ("look", "l"):
        reply = _desc(room)
    elif c in ("inv", "inventory"):
        loot = p.get("loot", [])
        if loot:
            reply = (f"You carry {len(loot)} forged invariant{'s' if len(loot) != 1 else ''} "
                     f"in your chest:\n" + "\n".join(f"  ◈ {x}" for x in loot))
        else:
            reply = ("You carry nothing forged yet. Your chest is an open space waiting "
                     "for a truth that at least two witnesses can agree on.")
    elif c.startswith("go ") or c in DIRS:
        d = c[3:].strip() if c.startswith("go ") else c
        exits = ROOMS[room]["exits"]
        if d in exits:
            p["room"] = exits[d]
            _set(PLAYER, p)
            reply = _desc(exits[d], entering=True)
        else:
            reply = f"There is no way {d} from here. The world has no door where you look."
    elif c in ("survey", "witness", "listen", "scry"):
        s = survey(room)
        if not s.get("ok"):
            reply = f"The scene could not be witnessed: {s.get('error')}"
        else:
            lines = [f"You call the party into {room} to witness the one scene. "
                     f"{s['n_reachable']}/{s['n_witnesses']} speak."]
            for w in s["witnesses"]:
                if w["ok"]:
                    snippet = (w["statements"][0][:160] + "…") if w["statements"] else "(no invariant)"
                    lines.append(f"  {w['seat']}: {snippet}")
            lines.append(f"\nRoshomon core ({s['n_core']}): convergent truth — the data.")
            for co in s["roshomon_core"]:
                lines.append(f"  ◈ {co['statement'][:140]}  [{' + '.join(co['witnesses'])}]")
            lines.append(f"Novel solutions ({s['n_novel']}) routed to the swarm:")
            for nv in s["novel_solutions"][:5]:
                lines.append(f"  → {nv['statement'][:120]}  ({nv['witness']})")
            reply = "\n".join(lines)
    elif c in ("claim", "fold", "take"):
        r = claim(room)
        reply = r.get("reply", r.get("error", "could not claim"))
    elif c == "map":
        reply = ("The shape of the world:\n" +
                 "\n".join(f"  {r}  <-  {', '.join(ROOMS[r]['exits'].values())}"
                           for r in ROOMS))
    elif c == "status":
        reply = _desc(room) + f"\n\n(player: {len(p.get('loot', []))} invariants)"
    else:
        reply = f"I do not know what '{command}' means in this world. Try 'help'."

    return {"ok": True, "schema": SCHEMA, "command": command, "reply": reply,
            "room": p["room"], "invariants": len(p.get("loot", [])),
            "note": "the necromancer's swarm as a Roshomon MUD on the verkle chain"}


def status() -> dict[str, Any]:
    p = _player()
    return {"ok": True, "schema": SCHEMA, "room": p["room"],
            "invariants": len(p.get("loot", [])),
            "invariants_list": p.get("loot", []),
            "claimed": sorted((_get(CLAIMED, {}) or {}).keys()),
            "note": "Roshomon MUD state, verkle-anchored; data = the filter over many witnesses"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    argv = list(argv) if argv else []
    if argv:
        print(_json.dumps(act(" ".join(argv)), ensure_ascii=False, indent=2, default=str))
    else:
        print(_json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
