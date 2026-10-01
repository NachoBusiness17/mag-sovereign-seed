"""Curveballs — freestyle player intent → joke fail or world graph rewrite.

Steals: Henry Stickmin (fail = content, keep progress) · KoL (zone tables, NC vs combat) ·
weighted encounter tables · graph rewrite (add room + edge only).

Schema: mag_game_curveball.v1
Law: never blank balk; every curveball pays a joke or FILEs a room.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Any

SCHEMA = "mag_game_curveball.v1"
MAX_GEN_ROOMS = 5

# Phrase → preferred exit key if present on current room
_FUZZY_EXIT: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(woods?|forest|trees?|timber|copse|thicket|off (the )?trail)\b", re.I), "south"),
    (re.compile(r"\b(keep|gate|castle|fort|north(ward)?)\b", re.I), "north"),
    (re.compile(r"\b(farm|field|east|crops)\b", re.I), "east"),
    (re.compile(r"\b(road|path back|south(ward)?)\b", re.I), "south"),
    (re.compile(r"\b(cave|below|down|cellar|under)\b", re.I), "down"),
    (re.compile(r"\b(deeper|further in)\b", re.I), "deeper"),
    (re.compile(r"\b(back|return|retreat path)\b", re.I), "back"),
]

_COLOR = re.compile(
    r"\b("
    r"take a dump|take a shit|poop|pee|piss|urinate|nap here|sit down|"
    r"flirt|kiss (the )?rock|dance|sing|yell|scream|do nothing|"
    r"pick (my )?nose|scratch|fart|meditate|pray to|worship"
    r")\b",
    re.I,
)
_REJECT = re.compile(
    r"\b(god mode|noclip|infinite hp|kill all|win the game|sudo|cheat)\b",
    re.I,
)
_OFFMAP = re.compile(
    r"\b("
    r"run (off|away|into)|head (into|for|off)|leave (the )?(road|path|trail)|"
    r"wander|explore|go off|make (for|toward)|bolt|flee (to|into|toward)|"
    r"move off|dash (into|to)|hide in"
    r")\b",
    re.I,
)

# Stickmin-style fails (always stay in room unless effect says otherwise)
_COLOR_TABLE: list[dict[str, Any]] = [
    {
        "w": 25,
        "id": "privy_bush",
        "text": "You duck behind a bush for a heroic bathroom break. A raven judges you. Dignity: optional. Progress: intact.",
    },
    {
        "w": 20,
        "id": "rock_flirt",
        "text": "You monologue at a rock. The rock remains emotionally unavailable. Somewhere, a bard takes notes.",
    },
    {
        "w": 15,
        "id": "power_nap",
        "text": "You power-nap for four minutes. Dream: the keep files a noise complaint. You wake stickier, not wiser.",
    },
    {
        "w": 15,
        "id": "yell_void",
        "text": "You yell your plan into the void. The void replies with wind. Nearby wildlife unfollows you.",
    },
    {
        "w": 15,
        "id": "dance_trail",
        "text": "You invent a victory dance early. A squirrel drops a nut in pity. No HP lost. Reputation among rodents: mixed.",
    },
    {
        "w": 10,
        "id": "meditate",
        "text": "You meditate on the meaning of quests. Insight: maybe just walk north. Body still here. Mind slightly smug.",
    },
]

_DIVERT_TABLE: list[dict[str, Any]] = [
    {
        "w": 30,
        "id": "bandit_shove",
        "text": "Bandits pop from the scrub: 'Trail tax — or back on the road, hero.' They herd you like a confused sheep. Destination unchanged; dignity not.",
        "effect": "stay",
    },
    {
        "w": 25,
        "id": "wolf_stare",
        "text": "Wolves shadow your off-path hustle, too polite to eat you, too hungry to let you improvise geography. You rethink the trail.",
        "effect": "stay",
    },
    {
        "w": 20,
        "id": "merchant_yell",
        "text": "A merchant on a mule hollers: 'That way's bandits and bad Yelp! Keep to the ruts!' You are peer-pressured by capitalism.",
        "effect": "stay",
    },
    {
        "w": 15,
        "id": "signpost",
        "text": "A crooked sign appears mid-ditch: 'NO SHORTCUTS — BY ORDER OF NARRATIVE.' You respect the font.",
        "effect": "stay",
    },
    {
        "w": 10,
        "id": "ambush_fight",
        "text": "Your clever detour walks straight into an ambush. Surprise: the story had budget for one fight.",
        "effect": "encounter",
        "encounter": {
            "id": "trail_bandit",
            "name": "Trail Bandit",
            "hp": 8,
            "hp_max": 8,
            "ac": 13,
            "attack_bonus": 3,
            "damage": "1d6+1",
        },
    },
]

_WOODS_SPURS: list[dict[str, Any]] = [
    {
        "name": "Brushy Copse",
        "desc": "Tangled saplings, a deer path, and the feeling something watches from one tree over.",
        "hooks": ["Broken arrow in the mud.", "Far off: keep smoke."],
        "encounter_chance": 0.35,
        "encounter": {
            "id": "brush_bandit",
            "name": "Brush Bandit",
            "hp": 7,
            "hp_max": 7,
            "ac": 12,
            "attack_bonus": 3,
            "damage": "1d6",
        },
    },
    {
        "name": "Mossy Ditch",
        "desc": "A damp ditch parallel to the road — shortcut energy, ankle-break reality.",
        "hooks": ["Someone camped here last week.", "Boot prints head back to the ruts."],
        "encounter_chance": 0.2,
        "encounter": None,
    },
    {
        "name": "Raven Clearing",
        "desc": "A circle of trees where ravens argue. One drops a bent copper coin at your feet.",
        "hooks": ["The coin is warm.", "Keep chimney smoke still wrong."],
        "encounter_chance": 0.15,
        "encounter": None,
    },
]


def _pick(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"text": "The world shrugs.", "id": "shrug"}
    total = sum(int(r.get("w") or 1) for r in rows)
    x = random.randint(1, max(1, total))
    acc = 0
    for r in rows:
        acc += int(r.get("w") or 1)
        if x <= acc:
            return r
    return rows[-1]


def _slug_phrase(text: str) -> str:
    h = hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:6]
    return h


def fuzzy_exit_for_phrase(text: str, exits: dict[str, str]) -> str | None:
    """Map natural language to an existing exit key if possible."""
    exits = exits or {}
    if not exits:
        return None
    t = text or ""
    # direct mention of exit name
    for k in exits:
        if re.search(rf"\b{re.escape(k)}\b", t, re.I):
            return k
    for pat, preferred in _FUZZY_EXIT:
        if pat.search(t):
            if preferred in exits:
                return preferred
            # any exit that sounds woodsy/keep etc.
            for k, dest in exits.items():
                if preferred == "south" and ("wood" in dest or k in ("south", "east")):
                    return k
                if preferred == "north" and ("keep" in dest or "gate" in dest or k == "north"):
                    return k
            # fallback first available matching compass
            if preferred in exits:
                return preferred
    return None


def classify_curveball(text: str) -> str:
    t = text or ""
    if _REJECT.search(t):
        return "reject_soft"
    # Dialogue / IC questions are not Stickmin fails — caller should prefer talk/look
    if re.search(
        r"\b(why|what|who|how come|tell me|ask |talk |speak |hello|hey |"
        r"polishing|barkeep|mug)\b",
        t,
        re.I,
    ):
        return "inworld_talk"
    if _COLOR.search(t):
        return "color"
    if _OFFMAP.search(t) or _FUZZY_EXIT[0][0].search(t):
        return "offmap"
    # short wander-ish
    if re.search(r"\b(explore|wander|detour|shortcut|side path)\b", t, re.I):
        return "offmap"
    # explicit comedy divert only
    if re.search(r"\b(surprise me|do something stupid|curveball|stickmin)\b", t, re.I):
        return "color"
    return "inworld_talk"  # residual is IC speech, not Stickmin


def resolve_curveball(campaign_id: str, text: str) -> dict[str, Any]:
    """Apply curveball to campaign. Returns apply_action-compatible result."""
    from mag.game_campaign import (
        _room,
        list_legal_actions,
        load_campaign,
        save_campaign,
        scene_context,
        _utc,
    )

    camp = load_campaign(campaign_id)
    if not camp or camp.get("status") != "active":
        return {"ok": False, "error": "no active campaign", "schema": SCHEMA}

    phrase = (text or "").strip()
    snap = camp.get("module_snapshot") or {}
    rooms = dict(snap.get("rooms") or {})
    room = _room(camp)
    exits = dict(room.get("exits") or {})
    rid = str(camp.get("room_id") or "")
    st = dict(camp.get("storyteller") or {})
    st.setdefault("gen_rooms", 0)
    st.setdefault("threat_budget", 2)
    st.setdefault("curveball_fails", [])
    events: list[str] = []
    pl = camp.get("player") or {}

    # 1) Fuzzy legal exit — Stickmin "correct" path when map already has it
    fe = fuzzy_exit_for_phrase(phrase, exits)
    if fe and fe in exits:
        from mag.game_campaign import apply_action

        out = apply_action(campaign_id, {"type": "move", "direction": fe})
        if out.get("ok"):
            out["schema"] = SCHEMA
            out["curveball"] = {"kind": "fuzzy_exit", "direction": fe, "steal": "map_match"}
            # prepend acknowledgment
            ev = list(out.get("events") or [])
            ev.insert(0, f"(You mean {fe} — the map already had that idea.)")
            out["events"] = ev
            out["narrate"] = " ".join(ev)
            return out

    kind = classify_curveball(phrase)
    tables = (snap.get("event_tables") or {})

    # Dialogue should not become privy_bush — bounce to talk action
    if kind == "inworld_talk":
        from mag.game_campaign import apply_action

        out = apply_action(campaign_id, {"type": "talk", "raw": phrase[:240]})
        if out.get("ok"):
            out["schema"] = SCHEMA
            out["curveball"] = {"kind": "inworld_talk", "steal": "stay_in_room"}
            return out

    # 2) Soft reject (god mode)
    if kind == "reject_soft":
        events.append(
            "The universe stamps REJECTED on your cheat request. "
            "A tiny clerk-elf cites policy §1: no god mode on Tuesdays (it's always Tuesday)."
        )
        return _finish(camp, events, st, phrase, "reject_soft", tables)

    # 3) Color / Stickmin fail
    if kind == "color":
        rows = list(tables.get("curveball_color") or _COLOR_TABLE)
        row = _pick(rows)
        events.append(str(row.get("text") or "You do a bit. The world endures."))
        fails = list(st.get("curveball_fails") or [])
        fails.append(str(row.get("id") or "color"))
        st["curveball_fails"] = fails[-40:]
        if row.get("lose") and row["lose"] in (pl.get("inventory") or []):
            pl["inventory"] = [i for i in pl["inventory"] if i != row["lose"]]
            events.append(f"(Lost {row['lose']}.)")
            camp["player"] = pl
        return _finish(camp, events, st, phrase, "color", tables, fail_id=str(row.get("id")))

    # 4) Offmap — KoL zone roll: divert / guard / generate
    budget = int(st.get("threat_budget") or 0)
    gen_n = int(st.get("gen_rooms") or 0)
    roll = random.randint(1, 6)
    # bias divert if threat budget high or gen capped
    if gen_n >= MAX_GEN_ROOMS:
        roll = min(roll, 4)
    if budget >= 2 and roll == 6:
        roll = random.choice([2, 3, 5, 6])

    if roll <= 2:
        # pure Stickmin divert joke
        rows = list(tables.get("curveball_divert") or _DIVERT_TABLE)
        row = _pick(rows)
        events.append(str(row.get("text") or "Something herds you back."))
        return _finish(camp, events, st, phrase, "divert_fail", tables, fail_id=str(row.get("id")))

    if roll <= 4:
        rows = list(tables.get("curveball_divert") or _DIVERT_TABLE)
        # prefer combat row if any
        combat_rows = [r for r in rows if r.get("effect") == "encounter"]
        row = _pick(combat_rows or rows)
        events.append(str(row.get("text") or "Trouble finds your detour."))
        if row.get("effect") == "encounter" and row.get("encounter"):
            camp["encounter"] = dict(row["encounter"])
            events.append(f"{row['encounter'].get('name')} blocks the clever idea!")
            if budget > 0:
                st["threat_budget"] = budget - 1
        return _finish(camp, events, st, phrase, "trail_guard", tables, fail_id=str(row.get("id")))

    if roll == 5:
        # branch existing theme room if any woods-like
        for dest_id, rmeta in rooms.items():
            name = str((rmeta or {}).get("name") or dest_id).lower()
            if any(k in name or k in dest_id for k in ("wood", "forest", "trail", "copse")):
                dir_key = "woods"
                if rid in rooms:
                    ex = dict(rooms[rid].get("exits") or {})
                    ex[dir_key] = dest_id
                    rooms[rid]["exits"] = ex
                camp["module_snapshot"] = {**snap, "rooms": rooms}
                camp["room_id"] = dest_id
                camp["encounter"] = None
                enc = (rooms.get(dest_id) or {}).get("encounter")
                if enc:
                    camp["encounter"] = dict(enc)
                events.append(
                    f"You cut through to {(rooms.get(dest_id) or {}).get('name')}. "
                    f"The map shrugs and adds a footpath labeled '{dir_key}'."
                )
                from mag.game_campaign import _narrate_room

                save_campaign(camp)
                events.append(_narrate_room(camp))
                return _finish(camp, events, st, phrase, "branch_existing", tables)

    # roll 6 or fallthrough: generate_branch
    if gen_n >= MAX_GEN_ROOMS:
        rows = list(tables.get("curveball_divert") or _DIVERT_TABLE)
        row = _pick(rows)
        events.append("The map is full of your improvisations. " + str(row.get("text") or ""))
        return _finish(camp, events, st, phrase, "divert_cap", tables)

    spur = random.choice(_WOODS_SPURS)
    new_id = f"gen_{_slug_phrase(phrase)}_{_slug_phrase(rid)}"
    if new_id in rooms:
        new_id = f"gen_{_slug_phrase(phrase + new_id)}"
    dir_key = "woods" if "wood" in phrase.lower() or "forest" in phrase.lower() or "tree" in phrase.lower() else "side"
    new_room = {
        "id": new_id,
        "name": spur["name"],
        "desc": spur["desc"],
        "exits": {"back": rid},
        "hooks": list(spur.get("hooks") or []),
        "generated": True,
        "from_phrase": phrase[:120],
        "steal": "kol_zone+graph_rewrite",
    }
    if spur.get("encounter") and random.random() < float(spur.get("encounter_chance") or 0):
        new_room["encounter"] = dict(spur["encounter"])
    rooms[new_id] = new_room
    if rid in rooms:
        ex = dict(rooms[rid].get("exits") or {})
        ex[dir_key] = new_id
        rooms[rid]["exits"] = ex
    camp["module_snapshot"] = {**snap, "rooms": rooms}
    camp["room_id"] = new_id
    camp["encounter"] = dict(new_room["encounter"]) if new_room.get("encounter") else None
    st["gen_rooms"] = gen_n + 1
    events.append(
        f"The world grows a new footpath ({dir_key}). You enter {spur['name']}. "
        f"(Generated branch — disk truth, not chat vapor.)"
    )
    if camp.get("encounter"):
        events.append(f"{camp['encounter'].get('name')} was already here. Awkward.")
    from mag.game_campaign import _narrate_room

    camp["storyteller"] = st
    save_campaign(camp)
    events.append(_narrate_room(camp))
    return _finish(camp, events, st, phrase, "generate_branch", tables, new_room=new_id)


def _finish(
    camp: dict[str, Any],
    events: list[str],
    st: dict[str, Any],
    phrase: str,
    kind: str,
    tables: dict[str, Any],
    *,
    fail_id: str = "",
    new_room: str = "",
) -> dict[str, Any]:
    from mag.game_campaign import list_legal_actions, save_campaign, scene_context, _utc

    camp["storyteller"] = st
    camp["log"] = list(camp.get("log") or []) + [
        {"ts": _utc(), "type": "curveball", "kind": kind, "text": e, "phrase": phrase[:80]}
        for e in events
    ]
    save_campaign(camp)
    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={"campaign_id": str(camp.get("campaign_id")), "kind": kind},
            input_data={"phrase": phrase[:200]},
            action={"curveball": kind, "fail_id": fail_id, "new_room": new_room},
            outcome={"events_n": len(events), "room": camp.get("room_id")},
            pattern_tags=["game", "curveball", kind, "stickmin_kol"],
            tier_max="T2",
        )
    except Exception:
        pass
    return {
        "ok": True,
        "schema": SCHEMA,
        "campaign_id": camp.get("campaign_id"),
        "events": events,
        "narrate": " ".join(events),
        "legal": list_legal_actions(camp),
        "scene_context": scene_context(camp),
        "status": camp.get("status"),
        "player": camp.get("player"),
        "curveball": {"kind": kind, "fail_id": fail_id, "new_room": new_room, "phrase": phrase[:120]},
    }
