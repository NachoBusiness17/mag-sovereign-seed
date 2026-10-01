"""Multi-combatant tavern brawl — watch auto NPCs, pause YOUR TURN, absurd room react.

Schema: mag_game_brawl.v1
Law: engine owns initiative/HP/hit; DS only colors; Mag holds roster state.
5e-lite Tavern Brawler (PHB-shaped): improvised/unarmed 1d4, proficient;
  after hit with those, may bonus-action grapple.
Story open: failed_hunt heat — party lost the mark; words → chairs.
Craft rails: soft fiction frame only (never name authors in player output).
"""
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from config import ROOT
from mag.game_dice import roll_dice
from server.protocol import encode
from server.room import DEFAULT_EXPIRE, DEFAULT_MAXSIZE, Member, Room

SCHEMA = "mag_game_brawl.v1"
BRAWL_DIR = ROOT / "memory" / "working" / "brawls"

# --- L1 sheets (commoners + party). All level 1. ---

_ROSTER_TEMPLATE: list[dict[str, Any]] = [
    {
        "id": "barkeep_mira",
        "name": "Mira the Barkeep",
        "role": "commoner",
        "level": 1,
        "hp": 8,
        "hp_max": 8,
        "ac": 11,
        "attack_bonus": 2,
        "damage": "1d4",
        "str_mod": 1,
        "dex_mod": 0,
        "skills": {"insight": 2, "athletics": 1},
        "traits": ["territorial", "tired"],
        "faction": "house",
        "improvised": "mug",
        "ai": "defend_bar",
    },
    {
        "id": "stable_hand",
        "name": "Pip the Stable Hand",
        "role": "commoner",
        "level": 1,
        "hp": 4,
        "hp_max": 4,
        "ac": 10,
        "attack_bonus": 2,
        "damage": "1d4",
        "str_mod": 0,
        "dex_mod": 1,
        "skills": {"animal_handling": 1, "acrobatics": 1},
        "traits": ["skittish"],
        "faction": "house",
        "improvised": "stool leg",
        "ai": "flail_or_flee",
    },
    {
        "id": "farmhand_odette",
        "name": "Odette Farmhand",
        "role": "commoner",
        "level": 1,
        "hp": 6,
        "hp_max": 6,
        "ac": 10,
        "attack_bonus": 2,
        "damage": "1d4+1",
        "str_mod": 1,
        "dex_mod": 0,
        "skills": {"athletics": 2},
        "traits": ["hotheaded"],
        "faction": "crowd",
        "improvised": "chair",
        "ai": "swing_nearest",
    },
    {
        "id": "merchant_gil",
        "name": "Gil the Merchant",
        "role": "commoner",
        "level": 1,
        "hp": 4,
        "hp_max": 4,
        "ac": 10,
        "attack_bonus": 1,
        "damage": "1d4",
        "str_mod": -1,
        "dex_mod": 0,
        "skills": {"persuasion": 2, "deception": 1},
        "traits": ["greedy", "cowardly"],
        "faction": "crowd",
        "improvised": "coin pouch",
        "ai": "hide_or_snipe",
    },
    {
        "id": "drinker_bo",
        "name": "Bo the Regular",
        "role": "commoner",
        "level": 1,
        "hp": 5,
        "hp_max": 5,
        "ac": 10,
        "attack_bonus": 1,
        "damage": "1d4",
        "str_mod": 1,
        "dex_mod": 0,
        "skills": {"athletics": 1},
        "traits": ["drunk", "loyal"],
        "faction": "crowd",
        "improvised": "tankard",
        "ai": "swing_nearest",
    },
    {
        "id": "corner_stranger",
        "name": "Corner Stranger",
        "role": "commoner",
        "level": 1,
        "hp": 8,
        "hp_max": 8,
        "ac": 12,
        "attack_bonus": 2,
        "damage": "1d4",
        "str_mod": 1,
        "dex_mod": 1,
        "skills": {"perception": 2, "stealth": 1},
        "traits": ["watchful"],
        "faction": "crowd",
        "improvised": "platter",
        "ai": "swing_nearest",
    },
    # Adventuring party — failed the hunt; heat spills here
    {
        "id": "party_vex",
        "name": "Vex (party fighter)",
        "role": "adventurer",
        "level": 1,
        "hp": 12,
        "hp_max": 12,
        "ac": 14,
        "attack_bonus": 4,
        "damage": "1d8+2",
        "str_mod": 2,
        "dex_mod": 1,
        "skills": {"athletics": 4, "intimidation": 2},
        "traits": ["hotheaded", "proud"],
        "faction": "party",
        "improvised": "broken bottle",
        "ai": "party_aggressor",
        "archetype": "fighter",
    },
    {
        "id": "party_sable",
        "name": "Sable (party rogue)",
        "role": "adventurer",
        "level": 1,
        "hp": 10,
        "hp_max": 10,
        "ac": 13,
        "attack_bonus": 5,
        "damage": "1d6+3",
        "str_mod": 0,
        "dex_mod": 3,
        "skills": {"stealth": 5, "sleight_of_hand": 5, "perception": 3},
        "traits": ["cynical", "quick"],
        "faction": "party",
        "improvised": "thrown plate",
        "ai": "party_flanker",
        "archetype": "rogue",
    },
    {
        "id": "party_quill",
        "name": "Quill (party wizard)",
        "role": "adventurer",
        "level": 1,
        "hp": 8,
        "hp_max": 8,
        "ac": 11,
        "attack_bonus": 3,
        "damage": "1d6",
        "str_mod": -1,
        "dex_mod": 2,
        "skills": {"arcana": 4, "history": 2},
        "traits": ["curious", "fragile"],
        "faction": "party",
        "improvised": "candle snuffer",
        "ai": "party_caster",
        "archetype": "wizard",
    },
    {
        "id": "party_bram",
        "name": "Bram (party cleric)",
        "role": "adventurer",
        "level": 1,
        "hp": 10,
        "hp_max": 10,
        "ac": 14,
        "attack_bonus": 3,
        "damage": "1d6+1",
        "str_mod": 1,
        "dex_mod": 0,
        "skills": {"medicine": 3, "religion": 3},
        "traits": ["kind", "stubborn"],
        "faction": "party",
        "improvised": "holy symbol as club",
        "ai": "party_support",
        "archetype": "cleric",
    },
]

_ABSURD_REACT = {
    "shock": [
        "{name} freezes mid-swing, jaw open.",
        "{name} drops their {weapon} with a clatter.",
        "{name} makes a sound no language claims.",
    ],
    "laugh": [
        "{name} barks a laugh that turns into a cough.",
        "{name} wheezes: 'Did they just—?'",
        "{name} nearly falls off their chair laughing.",
    ],
    "rage": [
        "{name} goes red: 'THAT'S IT.'",
        "{name} decides you are the real problem.",
        "{name} prioritizes you with ugly sincerity.",
    ],
    "join": [
        "{name} shrugs and joins the bit.",
        "{name} weaponizes the same absurdity.",
        "{name} copies you badly and somehow worse.",
    ],
    "flee": [
        "{name} bolts for the door.",
        "{name} hides under a table muttering prayers.",
        "{name} exits the narrative at speed.",
    ],
    "story": [
        "{name} will tell this story wrong for years.",
        "{name} files it under 'why we don't hunt with strangers.'",
        "{name} feels the ordinary night crack open.",
    ],
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bid() -> str:
    return "br-" + uuid4().hex[:10]


def _path(brawl_id: str) -> Path:
    BRAWL_DIR.mkdir(parents=True, exist_ok=True)
    return BRAWL_DIR / f"{brawl_id}.json"


def load_brawl(brawl_id: str) -> dict[str, Any] | None:
    p = _path(brawl_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_brawl(brawl: dict[str, Any]) -> Path:
    p = _path(str(brawl["brawl_id"]))
    brawl["updated"] = _utc()
    p.write_text(json.dumps(brawl, indent=2, default=str), encoding="utf-8")
    return p


def latest_brawl_for_session(session_id: str) -> dict[str, Any] | None:
    if not BRAWL_DIR.is_dir() or not session_id:
        return None
    best, best_ts = None, ""
    for p in BRAWL_DIR.glob("br-*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(b.get("session_id") or "") != session_id:
            continue
        if b.get("status") not in ("active", "awaiting_player", "auto_running"):
            continue
        ts = str(b.get("updated") or b.get("ts") or "")
        if ts >= best_ts:
            best_ts, best = ts, b
    return best


def tavern_brawler_sheet(name: str = "Ash", *, traits: list[str] | None = None) -> dict[str, Any]:
    """PC L1 with Tavern Brawler feat (5e-lite).

    Feat: proficient improvised; unarmed/improv 1d4; after hit → bonus grapple.
    """
    return {
        "id": "pc",
        "name": name[:40],
        "role": "player",
        "level": 1,
        "is_player": True,
        "archetype": "tavern_brawler",
        "feat": "tavern_brawler",
        "feat_note": (
            "Tavern Brawler (5e-lite): proficient improvised; unarmed/improv 1d4; "
            "after hit with those, bonus-action grapple."
        ),
        "hp": 12,
        "hp_max": 12,
        "ac": 12,
        "attack_bonus": 4,
        "damage": "1d4+2",
        "unarmed_damage": "1d4+2",
        "improvised_damage": "1d4+2",
        "str_mod": 2,
        "dex_mod": 1,
        "con_mod": 2,
        "skills": {"athletics": 4, "intimidation": 2, "perception": 1},
        "traits": traits or ["brawler", "hotheaded"],
        "inventory": ["mug", "stool leg", "few coins"],
        "faction": "player",
        "improvised": "whatever is nearest",
        "proficient_improvised": True,
        "can_bonus_grapple_on_improv_hit": True,
    }


def apply_tavern_brawler_to_player(player: dict[str, Any]) -> dict[str, Any]:
    """Overlay Tavern Brawler onto an existing campaign player sheet."""
    pl = dict(player or {})
    pl["feat"] = "tavern_brawler"
    pl["archetype"] = pl.get("archetype") or "tavern_brawler"
    pl["feat_note"] = (
        "Tavern Brawler (5e-lite): proficient improvised; unarmed/improv 1d4; "
        "after hit with those, bonus-action grapple."
    )
    pl["level"] = 1
    pl["proficient_improvised"] = True
    pl["can_bonus_grapple_on_improv_hit"] = True
    pl["unarmed_damage"] = "1d4+2"
    pl["improvised_damage"] = "1d4+2"
    pl["damage"] = pl.get("damage") or "1d4+2"
    if int(pl.get("ac") or 0) > 14:
        pass
    elif int(pl.get("ac") or 0) < 12:
        pl["ac"] = 12
    traits = list(pl.get("traits") or [])
    low = [str(t).lower() for t in traits]
    if "brawler" not in low:
        traits.append("brawler")
    if "hotheaded" not in low:
        traits.append("hotheaded")
    pl["traits"] = traits[:4]
    inv = list(pl.get("inventory") or [])
    for item in ("mug", "stool leg"):
        if item not in inv:
            inv.append(item)
    pl["inventory"] = inv
    return pl


def _clone_roster() -> list[dict[str, Any]]:
    out = []
    for row in _ROSTER_TEMPLATE:
        c = dict(row)
        c["skills"] = dict(row.get("skills") or {})
        c["traits"] = list(row.get("traits") or [])
        c["alive"] = True
        c["grappled_by"] = None
        c["grappling"] = None
        c["status_effects"] = []
        out.append(c)
    return out


def _roll_initiative(combatants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for c in combatants:
        dex = int(c.get("dex_mod") or 0)
        r = roll_dice(f"1d20+{dex}")
        init = int(r["total"])
        scored.append((init, str(c.get("name") or ""), c, r))
    scored.sort(key=lambda x: (-x[0], x[1]))
    order = []
    for init, _name, c, r in scored:
        entry = dict(c)
        entry["initiative"] = init
        entry["init_faces"] = r.get("faces")
        order.append(entry)
    return order


def _alive(combatants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in combatants if int(c.get("hp") or 0) > 0 and c.get("alive", True)]


def _find(combatants: list[dict[str, Any]], cid: str) -> dict[str, Any] | None:
    for c in combatants:
        if c.get("id") == cid:
            return c
    return None


def _targets_for(actor: dict[str, Any], combatants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alive = [c for c in _alive(combatants) if c.get("id") != actor.get("id")]
    if not alive:
        return []
    af = str(actor.get("faction") or "")
    if af == "player" or actor.get("is_player"):
        party = [c for c in alive if c.get("faction") == "party"]
        return party or alive
    if af == "party":
        foes = [
            c
            for c in alive
            if c.get("faction") in ("player", "crowd") or c.get("is_player")
        ]
        return foes or alive
    if af == "house":
        return alive
    party = [c for c in alive if c.get("faction") == "party"]
    return party or alive


def _pick_target(actor: dict[str, Any], combatants: list[dict[str, Any]]) -> dict[str, Any] | None:
    opts = _targets_for(actor, combatants)
    if not opts:
        return None
    opts = sorted(opts, key=lambda c: (int(c.get("hp") or 99), str(c.get("name") or "")))
    ai = str(actor.get("ai") or "")
    if ai == "party_flanker" and len(opts) > 1:
        return opts[min(1, len(opts) - 1)]
    if ai in ("hide_or_snipe", "flail_or_flee") and int(actor.get("hp") or 0) <= 2:
        return None
    return opts[0]


def _attack(
    attacker: dict[str, Any],
    defender: dict[str, Any],
    *,
    style: str = "weapon",
) -> dict[str, Any]:
    bonus = int(attacker.get("attack_bonus") or 0)
    if style in ("improvised", "unarmed"):
        if not attacker.get("proficient_improvised") and style == "improvised":
            bonus = max(0, bonus - 2)
        dmg_note = str(
            attacker.get("improvised_damage")
            or attacker.get("unarmed_damage")
            or attacker.get("damage")
            or "1d4"
        )
        weapon = str(attacker.get("improvised") or "improvised object")
        if style == "unarmed":
            weapon = "unarmed"
            dmg_note = str(attacker.get("unarmed_damage") or dmg_note)
    elif style == "cantrip":
        dmg_note = "1d8"
        weapon = "frost cantrip"
        bonus = int(attacker.get("attack_bonus") or 3)
    else:
        dmg_note = str(attacker.get("damage") or "1d4")
        weapon = "weapon"

    hit_roll = roll_dice(f"1d20+{bonus}")
    ac = int(defender.get("ac") or 10)
    total = int(hit_roll["total"])
    if total < ac:
        return {
            "hit": False,
            "attacker": attacker.get("name"),
            "defender": defender.get("name"),
            "roll": total,
            "ac": ac,
            "style": style,
            "weapon": weapon,
            "event": (
                f"{attacker.get('name')} swings ({style}/{weapon}) — "
                f"miss ({total} vs AC {ac})."
            ),
        }

    dmg = roll_dice(dmg_note)
    dmg_total = int(dmg["total"])
    defender["hp"] = max(0, int(defender.get("hp") or 0) - dmg_total)
    dropped = defender["hp"] <= 0
    if dropped:
        defender["alive"] = False
    ev = (
        f"{attacker.get('name')} hits {defender.get('name')} with {weapon} "
        f"({total} vs AC {ac}) for {dmg_total}. "
        f"HP {defender['hp']}/{defender.get('hp_max')}."
    )
    if dropped:
        ev += f" {defender.get('name')} drops!"
    return {
        "hit": True,
        "attacker": attacker.get("name"),
        "defender": defender.get("name"),
        "defender_id": defender.get("id"),
        "roll": total,
        "ac": ac,
        "damage": dmg_total,
        "style": style,
        "weapon": weapon,
        "dropped": dropped,
        "event": ev,
    }


def _try_grapple(attacker: dict[str, Any], defender: dict[str, Any]) -> dict[str, Any]:
    a_ath = int((attacker.get("skills") or {}).get("athletics") or attacker.get("str_mod") or 0)
    d_ath = int((defender.get("skills") or {}).get("athletics") or defender.get("str_mod") or 0)
    d_acr = int((defender.get("skills") or {}).get("acrobatics") or defender.get("dex_mod") or 0)
    d_def = max(d_ath, d_acr)
    ar = roll_dice(f"1d20+{a_ath}")
    dr = roll_dice(f"1d20+{d_def}")
    ok = int(ar["total"]) >= int(dr["total"])
    if ok:
        attacker["grappling"] = defender.get("id")
        defender["grappled_by"] = attacker.get("id")
        se = list(defender.get("status_effects") or [])
        if "grappled" not in se:
            se.append("grappled")
        defender["status_effects"] = se
        return {
            "ok": True,
            "event": (
                f"{attacker.get('name')} grapples {defender.get('name')} "
                f"({ar['total']} vs {dr['total']})!"
            ),
        }
    return {
        "ok": False,
        "event": (
            f"{attacker.get('name')} fails to grapple {defender.get('name')} "
            f"({ar['total']} vs {dr['total']})."
        ),
    }


def is_absurd(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.match(
        r"^\s*(attack|hit|strike|flee|grapple|grab|improvise|punch|kick|"
        r"unarmed|look|help|status|end turn)\b",
        t,
        re.I,
    ) and len(t) < 40:
        return False
    if re.search(
        r"\b("
        r"dance|sing|serenade|kiss|hug|propose|marry|strip|moon|juggle|"
        r"chicken|cluck|quack|meow|bark|yodel|cartwheel|handstand|"
        r"monologue|soliloquy|recite|poem|sonnet|insult|"
        r"throw (the )?(pie|soup|stew|ale|broth)|"
        r"improv(ise)? a |do something (crazy|wild|stupid|absurd)|"
        r"table dance|conga|limbo|polka|breakdance|"
        r"summon|polymorph|turn into|pretend (to be|i'?m)|"
        r"challenge to (a )?(duel of|dance|staring)|"
        r"flash|mooning|pants|trousers|"
        r"steal the show|make a scene|ridiculous|absurd|bit\b|"
        r"flip (the )?table|cut the (rope|lamp)"
        r")\b",
        t,
        re.I,
    ):
        return True
    if len(t) > 60 and not re.search(r"\b(attack|hit|strike|grapple|stab|slash)\b", t, re.I):
        return True
    return False


def _classify_absurd_flavor(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\b(kiss|hug|propose|marry|love|serenade)\b", t):
        return "shock"
    if re.search(r"\b(dance|sing|juggle|yodel|cartwheel|polka|conga)\b", t):
        return "laugh"
    if re.search(r"\b(insult|moon|strip|pants|spit|slap)\b", t):
        return "rage"
    if re.search(r"\b(join|everyone|together|conga|chorus)\b", t):
        return "join"
    if re.search(r"\b(chicken|flee|hide|run away while)\b", t):
        return "flee"
    return "story"


def room_react_to_absurd(
    combatants: list[dict[str, Any]],
    *,
    player_text: str,
    player_name: str,
) -> list[str]:
    flavor = _classify_absurd_flavor(player_text)
    lines = [
        f"*** ABSURD BEAT *** {player_name}: \"{(player_text or '')[:120]}\"",
        "The room answers as one organism — then splinters.",
    ]
    pool = list(_ABSURD_REACT.get(flavor) or _ABSURD_REACT["story"])
    story_pool = list(_ABSURD_REACT["story"])
    for c in _alive(combatants):
        if c.get("is_player"):
            continue
        tmpl = random.choice(pool if random.random() < 0.7 else story_pool)
        weapon = str(c.get("improvised") or "mug")
        lines.append(tmpl.format(name=c.get("name"), weapon=weapon))
        if flavor == "rage" and random.random() < 0.4:
            se = list(c.get("status_effects") or [])
            if "focused_on_pc" not in se:
                se.append("focused_on_pc")
            c["status_effects"] = se
        if flavor == "flee" and c.get("role") == "commoner" and random.random() < 0.35:
            c["hp"] = 0
            c["alive"] = False
            lines.append(f"  → {c.get('name')} is gone from the fight.")
        if flavor == "laugh" and random.random() < 0.25:
            se = list(c.get("status_effects") or [])
            if "laughing" not in se:
                se.append("laughing")
            c["status_effects"] = se
        if flavor == "join" and c.get("role") == "commoner" and random.random() < 0.2:
            c["faction"] = "player"
            lines.append(f"  → {c.get('name')} sides with you (for now).")
    rails = [
        "Something in the threshold shifts: the night stops being ordinary.",
        "A private wound in the room (the failed hunt) just got public.",
        "The brawl is no longer about the mark — it is about who they are when the story turns.",
    ]
    lines.append(random.choice(rails))
    return lines


def _npc_turn(actor: dict[str, Any], combatants: list[dict[str, Any]]) -> list[str]:
    events: list[str] = []
    if int(actor.get("hp") or 0) <= 0:
        return events
    if "grappled" in (actor.get("status_effects") or []):
        br = roll_dice("1d20")
        if int(br["total"]) >= 12:
            actor["status_effects"] = [
                s for s in (actor.get("status_effects") or []) if s != "grappled"
            ]
            actor["grappled_by"] = None
            events.append(f"{actor.get('name')} breaks free of the grapple.")
        else:
            events.append(f"{actor.get('name')} struggles in the grapple.")
            return events

    ai = str(actor.get("ai") or "swing_nearest")
    if ai in ("hide_or_snipe", "flail_or_flee") and int(actor.get("hp") or 0) <= 2:
        actor["hp"] = 0
        actor["alive"] = False
        events.append(f"{actor.get('name')} bolts / hides — out of the brawl.")
        return events

    target = _pick_target(actor, combatants)
    if not target:
        events.append(f"{actor.get('name')} finds no target and ducks.")
        return events

    if "focused_on_pc" in (actor.get("status_effects") or []):
        pc = next((c for c in combatants if c.get("is_player")), None)
        if pc and int(pc.get("hp") or 0) > 0:
            target = pc

    style = "weapon"
    if actor.get("role") == "commoner":
        style = "improvised"
    elif ai == "party_caster" and actor.get("archetype") == "wizard":
        style = "cantrip"
    elif ai == "party_flanker" and roll_dice("1d2")["total"] == 1:
        style = "improvised"

    if "laughing" in (actor.get("status_effects") or []):
        actor["attack_bonus"] = int(actor.get("attack_bonus") or 0) - 2
        res = _attack(actor, target, style=style)
        actor["attack_bonus"] = int(actor.get("attack_bonus") or 0) + 2
        actor["status_effects"] = [
            s for s in (actor.get("status_effects") or []) if s != "laughing"
        ]
    else:
        res = _attack(actor, target, style=style)
    events.append(str(res["event"]))

    if ai == "party_support" and not res.get("hit"):
        allies = [
            c
            for c in _alive(combatants)
            if c.get("faction") == actor.get("faction") and c.get("id") != actor.get("id")
        ]
        hurt = [c for c in allies if int(c.get("hp") or 0) < int(c.get("hp_max") or 1)]
        if hurt:
            a = sorted(hurt, key=lambda x: int(x.get("hp") or 0))[0]
            heal = roll_dice("1d4")
            a["hp"] = min(int(a.get("hp_max") or 1), int(a.get("hp") or 0) + int(heal["total"]))
            events.append(
                f"{actor.get('name')} patches {a.get('name')} (+{heal['total']} HP → {a['hp']})."
            )
    return events


def _advance_until_player(
    brawl: dict[str, Any],
    *,
    max_steps: int = 24,
) -> list[str]:
    events: list[str] = []
    combatants: list[dict[str, Any]] = list(brawl.get("combatants") or [])
    order: list[str] = list(brawl.get("initiative_order") or [])
    idx = int(brawl.get("turn_index") or 0)
    steps = 0

    while steps < max_steps:
        alive_ids = {c.get("id") for c in _alive(combatants)}
        if "pc" not in alive_ids:
            brawl["status"] = "defeat"
            events.append("You drop. The tavern brawl continues without its stranger.")
            break

        party_alive = [c for c in _alive(combatants) if c.get("faction") == "party"]
        hostiles = [
            c
            for c in _alive(combatants)
            if c.get("faction") in ("party", "crowd") and not c.get("is_player")
        ]
        if not party_alive and len(_alive(combatants)) <= 4:
            brawl["status"] = "complete"
            events.append(
                "The adventuring party is down or gone. "
                "Heat drains. Mira starts counting broken chairs."
            )
            break
        if not hostiles:
            brawl["status"] = "complete"
            events.append("No one left standing against you. Brawl over.")
            break

        if not order:
            break
        idx = idx % len(order)
        cid = order[idx]
        actor = _find(combatants, cid)
        if not actor or int(actor.get("hp") or 0) <= 0 or not actor.get("alive", True):
            idx = (idx + 1) % len(order)
            brawl["turn_index"] = idx
            steps += 1
            continue

        if actor.get("is_player") or actor.get("id") == "pc":
            brawl["status"] = "awaiting_player"
            brawl["turn_index"] = idx
            brawl["current_actor"] = "pc"
            events.append("— YOUR TURN —")
            events.append(
                f"{actor.get('name')} the Tavern Brawler: "
                f"HP {actor.get('hp')}/{actor.get('hp_max')} · "
                f"AC {actor.get('ac')} · feat ready "
                f"(improvise / punch / grapple after hit / freestyle absurd)."
            )
            # Auto freeze for multi-seat handoff (Socratic pack)
            try:
                from mag.game_freeze import freeze_campaign

                fr = freeze_campaign(
                    str(brawl.get("campaign_id") or ""),
                    brawl=brawl,
                )
                if fr.get("ok"):
                    brawl["freeze_id"] = fr.get("freeze_id")
                    events.append(
                        f"(State frozen: `{fr.get('freeze_id')}` — say freeze state / help.)"
                    )
            except Exception:
                pass
            break

        events.append(f"— {actor.get('name')} (init {actor.get('initiative')}) —")
        events.extend(_npc_turn(actor, combatants))
        idx = (idx + 1) % len(order)
        brawl["turn_index"] = idx
        if idx == 0:
            brawl["round"] = int(brawl.get("round") or 1) + 1
        steps += 1

    brawl["combatants"] = combatants
    return events


def _roster_summary(combatants: list[dict[str, Any]]) -> str:
    lines = []
    for c in combatants:
        flag = "PC" if c.get("is_player") else str(c.get("faction") or "?")
        st = "DOWN" if int(c.get("hp") or 0) <= 0 else f"HP {c.get('hp')}/{c.get('hp_max')}"
        lines.append(
            f"  [{c.get('initiative')}] {c.get('name')} ({flag} L{c.get('level')}) "
            f"AC {c.get('ac')} {st}"
        )
    return "\n".join(lines)


def _ds_color_batch(pack: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You color a D&D tavern brawl for Mag Table. Engine already fixed dice/HP. "
        "Output ONLY JSON: "
        '{"color":"3-6 vivid in-world sentences","pressure":"one line heat",'
        '"motif":"optional one-word story motif (threshold|shadow|failed_hunt|comedy)"}. '
        "Soft craft only — no lectures. No OOC. No new rooms. Never change HP."
    )
    user = json.dumps(pack, indent=2, default=str)[:3200]
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            system,
            user,
            tier="T2",
            max_tokens=320,
            temperature=0.6,
        )
        if res.get("ok"):
            raw = str(res.get("text") or res.get("content") or "")
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                o = json.loads(m.group(0))
                if isinstance(o, dict) and o.get("color"):
                    o["source"] = "deepseek"
                    o["model"] = res.get("model")
                    return o
    except Exception as exc:
        return {
            "color": " ".join(pack.get("events") or ["Chairs fly."])[:500],
            "pressure": "The failed hunt still burns.",
            "motif": "failed_hunt",
            "source": "fallback",
            "error": str(exc)[:120],
        }
    return {
        "color": " ".join(pack.get("events") or ["The brawl thickens."])[:500],
        "pressure": "Someone will remember this wrong.",
        "motif": "threshold",
        "source": "fallback",
    }


def start_tavern_brawl(
    *,
    session_id: str,
    campaign_id: str = "",
    channel: str = "table",
    player_name: str = "",
    use_ds: bool = True,
) -> dict[str, Any]:
    """Force tavern hub, L1 roster, Tavern Brawler PC, initiative, auto to YOUR TURN."""
    from mag.game_campaign import (
        begin_play,
        latest_for_session,
        load_campaign,
        save_campaign,
        scene_context,
        set_character,
    )

    camp = load_campaign(campaign_id) if campaign_id else latest_for_session(session_id)
    if not camp:
        # bootstrap classic if nothing exists
        boot = begin_play(
            module_id="classic",
            voice_session_id=session_id,
            force_new=True,
        )
        if not boot.get("ok"):
            return {"ok": False, "error": "could not start campaign for brawl"}
        camp = load_campaign(str(boot.get("campaign_id"))) or boot.get("campaign")
        if not camp:
            return {"ok": False, "error": "campaign missing after begin_play"}

    pl = camp.get("player")
    if not pl:
        name = (player_name or "Ash").strip() or "Ash"
        pl = tavern_brawler_sheet(name, traits=["brawler", "hotheaded"])
        out_c = set_character(str(camp["campaign_id"]), pl)
        if not out_c.get("ok"):
            return {"ok": False, "error": out_c.get("error") or "set_character failed"}
        camp = load_campaign(str(camp["campaign_id"])) or camp
        pl = camp.get("player") or pl
    else:
        pl = apply_tavern_brawler_to_player(pl)
        camp["player"] = pl

    camp["room_id"] = "tavern_lantern"
    camp["encounter"] = None
    camp["status"] = "active"
    flags = list(camp.get("flags") or [])
    for f in ("failed_hunt", "tavern_brawl", "heat_party"):
        if f not in flags:
            flags.append(f)
    camp["flags"] = flags

    pc = tavern_brawler_sheet(str(pl.get("name") or "Ash"), traits=list(pl.get("traits") or []))
    pc["hp"] = int(pl.get("hp") or pc["hp"])
    pc["hp_max"] = int(pl.get("hp_max") or pc["hp_max"])
    pc["ac"] = int(pl.get("ac") or pc["ac"])
    pc["attack_bonus"] = int(pl.get("attack_bonus") or pc["attack_bonus"])
    pc["is_player"] = True
    pc["id"] = "pc"

    combatants = [pc] + _clone_roster()
    combatants = _roll_initiative(combatants)
    initiative_order = [c["id"] for c in combatants]

    bid = _bid()
    story_open = [
        "FAILED HUNT.",
        "The party came back without the mark — empty hands, full blame.",
        "Vex slams a fist: the stranger at the bar (you) becomes convenient weather.",
        "Words → elbows → chairs. Mira swears in three languages.",
        "You are a Tavern Brawler for this fight: improvised weapons, d4 unarmed, "
        "grapple after you land an improv hit.",
        "Watch the room. When it is your turn, give your line.",
    ]

    brawl: dict[str, Any] = {
        "schema": SCHEMA,
        "brawl_id": bid,
        "ts": _utc(),
        "updated": _utc(),
        "session_id": session_id,
        "campaign_id": camp.get("campaign_id"),
        "status": "auto_running",
        "room_id": "tavern_lantern",
        "story": "failed_hunt",
        "round": 1,
        "turn_index": 0,
        "combatants": combatants,
        "initiative_order": initiative_order,
        "history": [],
        "metrics": {
            "npc_turns": 0,
            "player_turns": 0,
            "absurd_n": 0,
            "ds_rounds": 0,
            "text_n": 0,
            "speech_n": 0,
        },
    }

    open_events = list(story_open)
    open_events.append("INITIATIVE:")
    open_events.append(_roster_summary(combatants))
    auto_events = _advance_until_player(brawl)
    open_events.extend(auto_events)
    brawl["metrics"]["npc_turns"] = sum(
        1 for e in auto_events if e.startswith("— ") and "YOUR TURN" not in e
    )

    # Corpus inspiration (craft fuel) + optional DS color + multi-POV
    from mag.corpus_query import inspire_for_scene
    from mag.game_brawl_perspectives import perspectives_for_brawl_card
    from mag.game_dm_voice import format_brawl_card

    insp = inspire_for_scene(
        story="failed_hunt",
        room="The Guttered Lantern tavern",
        flags=list(camp.get("flags") or []),
        events_tail=open_events[-6:],
        limit=4,
    )
    insp_pack = (insp.get("pack") or {}) if insp.get("ok") else {}

    color: dict[str, Any] = {"source": "none"}
    if use_ds:
        color = _ds_color_batch(
            {
                "phase": "open",
                "story": "failed_hunt",
                "room": "The Guttered Lantern",
                "events": open_events[-12:],
                "inspiration_tags": (insp_pack.get("tags") or [])[:8],
                "inspiration_echo": (insp_pack.get("quotes") or [None])[0],
                "roster": [
                    {"name": c.get("name"), "hp": c.get("hp"), "faction": c.get("faction")}
                    for c in combatants
                ],
            }
        )
        if color.get("source") == "deepseek":
            brawl["metrics"]["ds_rounds"] = 1

    room = {}
    try:
        rooms = (camp.get("module_snapshot") or {}).get("rooms") or {}
        room = rooms.get("tavern_lantern") or {}
    except Exception:
        room = {}

    combatants_now = list(brawl.get("combatants") or combatants)
    persp_md, persp_rows = perspectives_for_brawl_card(
        combatants_now,
        events=open_events,
        flags=list(camp.get("flags") or []),
        max_voices=6,
    )

    card = format_brawl_card(
        events=open_events,
        status=str(brawl.get("status") or "awaiting_player"),
        player_name=str(pl.get("name") or "Ash"),
        room_name=str(room.get("name") or "The Guttered Lantern"),
        room_area=str(room.get("area") or "Village edge under the keep's shadow"),
        room_env=str(room.get("environment") or ""),
        round_n=int(brawl.get("round") or 1),
        absurd=False,
        open_story=True,
        brawl_id=bid,
        roster_summary=_roster_summary(combatants_now),
        inspiration_pack=insp_pack,
        color_line=str(color.get("color") or ""),
        pressure=str(color.get("pressure") or ""),
        perspectives_md=persp_md,
    )

    brawl["history"].append(
        {
            "ts": _utc(),
            "role": "open",
            "events": open_events,
            "color": color,
            "inspiration": {"tags": insp_pack.get("tags"), "quotes": insp_pack.get("quotes")},
            "perspectives": persp_rows,
            "card": {"speak": card.get("speak"), "passage": card.get("passage")},
        }
    )
    save_brawl(brawl)

    st = dict(camp.get("storyteller") or {})
    st["brawl_id"] = bid
    st["battle_cycle_id"] = None
    if color.get("source") == "deepseek":
        st["slow_turns"] = int(st.get("slow_turns") or 0) + 1
    camp["storyteller"] = st
    camp["player"] = pl
    camp["log"] = list(camp.get("log") or []) + [
        {
            "ts": _utc(),
            "type": "brawl_start",
            "text": f"Tavern brawl {bid}: failed_hunt heat. Tavern Brawler {pl.get('name')}.",
        }
    ]
    save_campaign(camp)

    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={"brawl_id": bid, "campaign_id": str(camp.get("campaign_id"))},
            action={
                "kind": "tavern_brawl_start",
                "story": "failed_hunt",
                "ds": color.get("source"),
                "corpus": True,
            },
            outcome={
                "combatants": len(combatants),
                "status": brawl.get("status"),
                "feat": "tavern_brawler",
            },
            pattern_tags=[
                "game",
                "tavern_brawl",
                "dogfood_dm",
                "multi_combat",
                "failed_hunt",
                "corpus_query",
            ],
            tier_max="T2",
            exportable=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "brawl_id": bid,
        "campaign_id": camp.get("campaign_id"),
        "speak": card.get("speak"),
        "speak_text": card.get("speak"),
        "narrate": card.get("narrate"),
        "answer": card.get("answer"),
        "passage": card.get("passage"),
        "color": color,
        "inspiration": insp_pack,
        "status": brawl.get("status"),
        "legal": _brawl_legal(),
        "scene_context": scene_context(camp),
        "roster": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "initiative": c.get("initiative"),
                "hp": c.get("hp"),
                "hp_max": c.get("hp_max"),
                "ac": c.get("ac"),
                "faction": c.get("faction"),
                "level": c.get("level"),
            }
            for c in combatants
        ],
        "fast_path": color.get("source") != "deepseek",
        "ds_called": color.get("source") == "deepseek",
        "route": "tavern_brawl_open",
        "perspectives": persp_rows,
    }


def _brawl_legal() -> list[dict[str, Any]]:
    return [
        {"type": "attack", "note": "weapon strike (name target optional)"},
        {"type": "improvise", "note": "chair/mug/leg — Tavern Brawler d4"},
        {"type": "unarmed", "note": "punch/kick — d4 + grapple option"},
        {"type": "grapple", "note": "bonus after improv/unarmed hit, or alone"},
        {"type": "absurd", "note": "freestyle bit — whole room reacts"},
        {"type": "flee", "note": "try the door"},
        {"type": "look", "note": "roster + HP"},
        {"type": "help"},
    ]


def parse_brawl_action(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    low = t.lower()
    if not t:
        return {"type": "help"}
    if re.search(r"\b(help|what can i|options|leads)\b", low):
        return {"type": "help"}
    if re.search(r"\b(look|status|roster|who.?s up|initiative)\b", low):
        return {"type": "look"}
    if re.search(r"\b(flee|run away|bolt|exit|door)\b", low):
        return {"type": "flee"}
    if re.search(r"\b(grapple|grab|wrestle|hold)\b", low) and not re.search(
        r"\b(punch|kick|improvise|chair|attack)\b", low
    ):
        return {"type": "grapple", "target": _parse_target_name(low), "raw": t}
    if re.search(r"\b(punch|kick|unarmed|fist|headbutt)\b", low):
        return {
            "type": "unarmed",
            "target": _parse_target_name(low),
            "grapple": bool(re.search(r"\b(and )?(grapple|grab)\b", low)),
            "raw": t,
        }
    if re.search(
        r"\b(improvise|chair|mug|stool|bottle|tankard|plate|throw (a |the )?(chair|mug))\b",
        low,
    ):
        return {
            "type": "improvise",
            "target": _parse_target_name(low),
            "grapple": bool(re.search(r"\b(and )?(grapple|grab)\b", low)),
            "raw": t,
        }
    if re.search(r"\b(attack|hit|strike|stab|slash|swing at)\b", low):
        return {"type": "attack", "target": _parse_target_name(low), "raw": t}
    if is_absurd(t):
        return {"type": "absurd", "raw": t}
    if len(t) > 48:
        return {"type": "absurd", "raw": t}
    return {"type": "attack", "target": _parse_target_name(low), "raw": t}


def _parse_target_name(low: str) -> str | None:
    names = [
        "vex",
        "sable",
        "quill",
        "bram",
        "mira",
        "pip",
        "odette",
        "gil",
        "bo",
        "stranger",
        "barkeep",
        "fighter",
        "rogue",
        "wizard",
        "cleric",
        "merchant",
        "farmhand",
        "stable",
        "regular",
    ]
    for n in names:
        if re.search(rf"\b{n}\b", low):
            return n
    m = re.search(r"\b(?:at|on|toward|towards)\s+([a-z][a-z'-]{1,20})\b", low)
    if m:
        return m.group(1)
    return None


def _resolve_target(
    combatants: list[dict[str, Any]],
    hint: str | None,
    actor: dict[str, Any],
) -> dict[str, Any] | None:
    alive = [c for c in _alive(combatants) if c.get("id") != actor.get("id")]
    if not alive:
        return None
    if not hint:
        for pref in ("party_vex", "party_sable", "party_quill", "party_bram"):
            t = _find(alive, pref)
            if t:
                return t
        party = [c for c in alive if c.get("faction") == "party"]
        return (party or alive)[0]
    h = hint.lower()
    for c in alive:
        nm = str(c.get("name") or "").lower()
        cid = str(c.get("id") or "").lower()
        arch = str(c.get("archetype") or "").lower()
        if h in nm or h in cid or (h and h == arch):
            return c
        if h == "barkeep" and "mira" in nm:
            return c
        if h == "stranger" and "stranger" in nm:
            return c
        if h == "fighter" and arch == "fighter":
            return c
        if h == "rogue" and arch == "rogue":
            return c
        if h == "wizard" and arch == "wizard":
            return c
        if h == "cleric" and arch == "cleric":
            return c
    return alive[0]


def player_brawl_turn(
    text: str,
    *,
    session_id: str,
    channel: str = "table",
    use_ds: bool = True,
) -> dict[str, Any]:
    """Player line on YOUR TURN → resolve → auto NPCs → next pause or end."""
    from mag.game_battle_cycle import detect_input_signals
    from mag.game_campaign import (
        latest_for_session,
        load_campaign,
        save_campaign,
        scene_context,
    )

    signals = detect_input_signals(text, channel=channel)
    camp = latest_for_session(session_id)
    if not camp:
        return {"ok": False, "error": "no campaign", "signals": signals}

    st = dict(camp.get("storyteller") or {})
    brawl_id = str(st.get("brawl_id") or "")
    brawl = load_brawl(brawl_id) if brawl_id else latest_brawl_for_session(session_id)
    if not brawl or brawl.get("status") not in ("awaiting_player", "active", "auto_running"):
        return {
            "ok": False,
            "error": "no active brawl — say start tavern brawl",
            "signals": signals,
        }

    metrics = dict(brawl.get("metrics") or {})
    if signals["modality"] == "speech":
        metrics["speech_n"] = int(metrics.get("speech_n") or 0) + 1
    else:
        metrics["text_n"] = int(metrics.get("text_n") or 0) + 1

    if signals.get("ooc") and re.search(r"\b(pause|quit|seal)\b", text or "", re.I):
        brawl["status"] = "paused"
        brawl["metrics"] = metrics
        save_brawl(brawl)
        return {
            "ok": True,
            "route": "tavern_brawl_pause",
            "speak": "Brawl paused (OOC). Say start tavern brawl to reopen heat.",
            "signals": signals,
            "brawl_id": brawl.get("brawl_id"),
        }

    if brawl.get("status") == "auto_running":
        extra = _advance_until_player(brawl)
        save_brawl(brawl)
        return {
            "ok": True,
            "route": "tavern_brawl_auto",
            "speak": "\n".join(extra) or "Watching…",
            "status": brawl.get("status"),
            "brawl_id": brawl.get("brawl_id"),
        }

    combatants: list[dict[str, Any]] = list(brawl.get("combatants") or [])
    pc = _find(combatants, "pc")
    if not pc or int(pc.get("hp") or 0) <= 0:
        brawl["status"] = "defeat"
        save_brawl(brawl)
        return {
            "ok": True,
            "route": "tavern_brawl_end",
            "speak": "You are already down. Brawl over for you. Seal session or classic one.",
            "status": "defeat",
        }

    act = parse_brawl_action(text)
    events: list[str] = [f"[YOUR LINE · {signals['modality']}] {(text or '')[:200]}"]
    absurd_lines: list[str] = []

    if act["type"] == "help":
        events.append(
            "Brawl actions: attack [name] · improvise / chair · punch · grapple · "
            "flee · look · or say anything absurd (room reacts)."
        )
        brawl["metrics"] = metrics
        save_brawl(brawl)
        return {
            "ok": True,
            "route": "tavern_brawl_help",
            "speak": "\n".join(events),
            "legal": _brawl_legal(),
            "status": "awaiting_player",
            "brawl_id": brawl.get("brawl_id"),
            "signals": signals,
        }

    if act["type"] == "look":
        events.append("ROSTER:")
        events.append(_roster_summary(combatants))
        brawl["metrics"] = metrics
        save_brawl(brawl)
        return {
            "ok": True,
            "route": "tavern_brawl_look",
            "speak": "\n".join(events),
            "status": "awaiting_player",
            "brawl_id": brawl.get("brawl_id"),
            "signals": signals,
            "scene_context": scene_context(camp),
        }

    if act["type"] == "absurd":
        metrics["absurd_n"] = int(metrics.get("absurd_n") or 0) + 1
        absurd_lines = room_react_to_absurd(
            combatants,
            player_text=str(act.get("raw") or text),
            player_name=str(pc.get("name") or "You"),
        )
        events.extend(absurd_lines)
        flags = list(camp.get("flags") or [])
        if "absurd_brawl_beat" not in flags:
            flags.append("absurd_brawl_beat")
        camp["flags"] = flags
    elif act["type"] == "flee":
        dex = int(pc.get("dex_mod") or 0)
        r = roll_dice(f"1d20+{dex}")
        if int(r["total"]) >= 12:
            brawl["status"] = "fled"
            events.append(f"You dive for the door ({r['total']}) — free of the brawl.")
            events.append("Cold air. Behind you: Mira's inventory of broken furniture.")
            metrics["player_turns"] = int(metrics.get("player_turns") or 0) + 1
            brawl["metrics"] = metrics
            brawl["history"].append(
                {
                    "ts": _utc(),
                    "role": "player",
                    "text": text[:300],
                    "events": events,
                    "act": act,
                }
            )
            save_brawl(brawl)
            st["brawl_id"] = brawl.get("brawl_id")
            camp["storyteller"] = st
            save_campaign(camp)
            return {
                "ok": True,
                "route": "tavern_brawl_end",
                "speak": "\n".join(events),
                "status": "fled",
                "brawl_id": brawl.get("brawl_id"),
                "signals": signals,
            }
        events.append(f"The door is a rumor ({r['total']}). Bodies block you.")
    else:
        style = {
            "attack": "weapon",
            "improvise": "improvised",
            "unarmed": "unarmed",
            "grapple": "grapple",
        }.get(act["type"], "weapon")
        target = _resolve_target(combatants, act.get("target"), pc)
        if not target:
            events.append("No one left to hit.")
        elif style == "grapple":
            g = _try_grapple(pc, target)
            events.append(g["event"])
        else:
            res = _attack(pc, target, style=style)
            events.append(res["event"])
            want_g = bool(act.get("grapple"))
            if (
                res.get("hit")
                and style in ("improvised", "unarmed")
                and want_g
                and pc.get("can_bonus_grapple_on_improv_hit")
            ):
                g = _try_grapple(pc, target)
                events.append("Bonus (Tavern Brawler): " + g["event"])
            elif (
                res.get("hit")
                and style in ("improvised", "unarmed")
                and pc.get("can_bonus_grapple_on_improv_hit")
            ):
                events.append(
                    "(Tavern Brawler: you could bonus-grapple — say 'and grapple' next hit.)"
                )

    metrics["player_turns"] = int(metrics.get("player_turns") or 0) + 1

    order = list(brawl.get("initiative_order") or [])
    idx = int(brawl.get("turn_index") or 0)
    if order and order[idx % len(order)] == "pc":
        brawl["turn_index"] = (idx + 1) % len(order)
    elif "pc" in order:
        brawl["turn_index"] = (order.index("pc") + 1) % len(order)

    brawl["combatants"] = combatants
    brawl["status"] = "auto_running"

    pl = dict(camp.get("player") or {})
    pl["hp"] = int(pc.get("hp") or pl.get("hp") or 0)
    camp["player"] = pl

    auto_events = _advance_until_player(brawl)
    events.extend(auto_events)
    metrics["npc_turns"] = int(metrics.get("npc_turns") or 0) + sum(
        1 for e in auto_events if e.startswith("— ") and "YOUR TURN" not in e
    )

    from mag.corpus_query import inspire_for_scene
    from mag.game_brawl_perspectives import perspectives_for_brawl_card
    from mag.game_dm_voice import format_brawl_card

    insp = inspire_for_scene(
        story="failed_hunt",
        room="The Guttered Lantern tavern",
        flags=list(camp.get("flags") or []),
        absurd=act["type"] == "absurd",
        events_tail=events[-8:],
        limit=4,
    )
    insp_pack = (insp.get("pack") or {}) if insp.get("ok") else {}

    color: dict[str, Any] = {"source": "none"}
    if use_ds and (act["type"] == "absurd" or metrics["player_turns"] % 2 == 0):
        color = _ds_color_batch(
            {
                "phase": "round",
                "story": "failed_hunt",
                "player_text": (text or "")[:200],
                "absurd": act["type"] == "absurd",
                "events": events[-16:],
                "player_hp": pc.get("hp"),
                "inspiration_tags": (insp_pack.get("tags") or [])[:8],
                "inspiration_echo": (insp_pack.get("quotes") or [None])[0],
            }
        )
        if color.get("source") == "deepseek":
            metrics["ds_rounds"] = int(metrics.get("ds_rounds") or 0) + 1
            st["slow_turns"] = int(st.get("slow_turns") or 0) + 1

    room = {}
    try:
        rooms = (camp.get("module_snapshot") or {}).get("rooms") or {}
        room = rooms.get(str(camp.get("room_id") or "tavern_lantern")) or {}
    except Exception:
        room = {}

    # Multi-agent Rashomon: each living fighter speaks from their head (templates = $0)
    combatants = list(brawl.get("combatants") or combatants)
    persp_md, persp_rows = perspectives_for_brawl_card(
        combatants,
        events=events,
        flags=list(camp.get("flags") or []),
        max_voices=6,
    )

    card = format_brawl_card(
        events=events,
        status=str(brawl.get("status") or "awaiting_player"),
        player_name=str(pc.get("name") or "Ash"),
        room_name=str(room.get("name") or "The Guttered Lantern"),
        room_area=str(room.get("area") or "Village edge under the keep's shadow"),
        room_env=str(room.get("environment") or ""),
        round_n=int(brawl.get("round") or 1),
        absurd=act["type"] == "absurd",
        open_story=False,
        brawl_id=str(brawl.get("brawl_id") or ""),
        roster_summary=_roster_summary(combatants),
        inspiration_pack=insp_pack,
        color_line=str(color.get("color") or ""),
        pressure=str(color.get("pressure") or ""),
        perspectives_md=persp_md,
    )

    brawl["metrics"] = metrics
    brawl["history"].append(
        {
            "ts": _utc(),
            "role": "player",
            "text": (text or "")[:400],
            "act": act,
            "signals": signals,
            "events": events,
            "color": color,
            "absurd": absurd_lines[:3] if absurd_lines else None,
            "inspiration": {"tags": insp_pack.get("tags"), "quotes": insp_pack.get("quotes")},
            "perspectives": persp_rows,
            "card": {"speak": card.get("speak"), "passage": card.get("passage")},
        }
    )
    save_brawl(brawl)

    st["brawl_id"] = brawl.get("brawl_id")
    st["fast_turns"] = int(st.get("fast_turns") or 0) + 1
    camp["storyteller"] = st
    camp["log"] = list(camp.get("log") or []) + [
        {"ts": _utc(), "type": "brawl_turn", "text": events[0][:200]}
    ]
    save_campaign(camp)

    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={
                "brawl_id": str(brawl.get("brawl_id")),
                "campaign_id": str(camp.get("campaign_id")),
                "round": str(brawl.get("round")),
            },
            input_data={
                "text": (text or "")[:200],
                "modality": signals["modality"],
                "absurd": act["type"] == "absurd",
            },
            action={
                "engine": act,
                "ds": color.get("source"),
                "feat": "tavern_brawler",
                "corpus": True,
            },
            outcome={
                "status": brawl.get("status"),
                "player_hp": pc.get("hp"),
                "alive": len(_alive(combatants)),
            },
            pattern_tags=[
                "game",
                "tavern_brawl",
                "dogfood_dm",
                signals["modality"],
                "absurd" if act["type"] == "absurd" else "combat",
                "corpus_query",
            ],
            tier_max="T2",
            exportable=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "route": (
            "tavern_brawl_end"
            if brawl.get("status") in ("complete", "defeat", "fled")
            else "tavern_brawl_round"
        ),
        "brawl_id": brawl.get("brawl_id"),
        "campaign_id": camp.get("campaign_id"),
        "speak": card.get("speak"),
        "speak_text": card.get("speak"),
        "narrate": card.get("narrate"),
        "answer": card.get("answer"),
        "passage": card.get("passage"),
        "events": events,
        "color": color,
        "inspiration": insp_pack,
        "signals": signals,
        "metrics": metrics,
        "legal": _brawl_legal(),
        "scene_context": scene_context(camp),
        "status": brawl.get("status"),
        "fast_path": color.get("source") != "deepseek",
        "ds_called": color.get("source") == "deepseek",
        "absurd": bool(absurd_lines),
        "perspectives": persp_rows,
    }


def wants_brawl_start(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"start tavern brawl|tavern brawl|begin brawl|start brawl|"
            r"bar fight|tavern fight|failed hunt brawl|"
            r"i('m| am) a tavern brawler|play tavern brawler"
            r")\b",
            text or "",
            re.I,
        )
    )


# ---------------------------------------------------------------------------
# Room transport — the tavern as spectator fan-out (Y3 verdict, Z6 2026-09-29)
#
# One Room per brawl_id (player seat + spectators). The ENGINE keeps
# authority — initiative/HP/hit never move in here; the room moves bytes
# only (server/room.py's own law). handle_brawl_voice is the inbound-frame
# handler: room.touch per inbound frame, the engine runs, publish()
# broadcasts the advance/react lines to every seat, and a brawl sitting
# awaiting_player sweeps its silent spectators. Receipt:
# watch/inbox/hydrology/Z6_BRAWL_ROOM.md
# ---------------------------------------------------------------------------

_BRAWL_ROOMS: dict[str, Room] = {}


def brawl_room(
    brawl_id: str,
    *,
    create: bool = False,
    maxsize: int = DEFAULT_MAXSIZE,
    expire: float = DEFAULT_EXPIRE,
) -> Room | None:
    """The Room for one brawl_id. One per brawl, lazily created on first seat."""
    room = _BRAWL_ROOMS.get(brawl_id)
    if room is None and create:
        room = Room(maxsize=maxsize, expire=expire)
        _BRAWL_ROOMS[brawl_id] = room
    return room


def join_brawl_room(
    brawl_id: str,
    *,
    send: Callable[[bytes], Awaitable[None]],
    close_fn: Callable[[], None] | None = None,
    meta: dict[str, Any] | None = None,
    mid: str | None = None,
) -> Member:
    """Take a seat in the brawl's room (player or spectator).

    Must run inside a live event loop: Room.join spawns the writer task
    that drains this seat's bounded inbox.
    """
    room = brawl_room(brawl_id, create=True)
    return room.join(send=send, close_fn=close_fn, meta=meta, mid=mid)


async def close_brawl_room(brawl_id: str) -> bool:
    """Brawl over / transport shutdown: drop every seat, reap writer tasks."""
    room = _BRAWL_ROOMS.pop(brawl_id, None)
    if room is None:
        return False
    await room.close()
    return True


def _touch_brawl_member(brawl_id: str, member_id: str | None) -> None:
    """Any inbound frame refreshes presence — the room's own law."""
    if not member_id:
        return
    room = _BRAWL_ROOMS.get(brawl_id)
    if room is not None:
        room.touch(member_id)


def _brawl_room_publish(brawl_id: str, lines: list[str], *, status: str = "") -> int:
    """Encode-once fan-out of the advance/react lines. No seats → 0."""
    room = _BRAWL_ROOMS.get(brawl_id)
    if room is None or not lines:
        return 0
    frame = encode(
        {"op": "brawl", "brawl_id": brawl_id, "status": status, "lines": list(lines)}
    )
    return room.publish(frame)


def _room_wire_result(result: dict[str, Any]) -> None:
    """Post-engine room wiring for one handled frame: publish the result's
    advance/react lines, then — on awaiting_player — sweep silent seats."""
    if not result or not result.get("ok"):
        return
    bid = str(result.get("brawl_id") or "")
    if not bid:
        return
    lines = [str(e) for e in (result.get("events") or []) if str(e).strip()]
    if not lines:
        lines = [ln for ln in str(result.get("speak") or "").splitlines() if ln.strip()]
    _brawl_room_publish(bid, lines, status=str(result.get("status") or ""))
    if str(result.get("status") or "") == "awaiting_player":
        room = _BRAWL_ROOMS.get(bid)
        if room is not None:
            room.sweep()


def handle_brawl_voice(
    text: str,
    *,
    session_id: str,
    channel: str = "table",
    campaign: dict[str, Any] | None = None,
    use_ds: bool = True,
    member_id: str | None = None,
) -> dict[str, Any] | None:
    """Voice/table entry. None = not brawl path.

    This is the brawl's inbound-frame handler (Y3): every call touches the
    sender's seat (room.touch), the engine runs with full authority, the
    advance/react lines are published to the brawl's Room, and an
    awaiting_player result sweeps silent spectators. member_id is the
    sender's seat in the brawl's room, when the caller is a room transport.
    """
    camp = campaign
    if camp is None:
        from mag.game_campaign import latest_for_session

        camp = latest_for_session(session_id)

    if wants_brawl_start(text):
        result = start_tavern_brawl(
            session_id=session_id,
            campaign_id=str((camp or {}).get("campaign_id") or ""),
            channel=channel,
            use_ds=use_ds,
        )
        _room_wire_result(result)
        return result

    if not camp or camp.get("status") != "active":
        return None

    st = camp.get("storyteller") or {}
    brawl_id = st.get("brawl_id")
    brawl = load_brawl(str(brawl_id)) if brawl_id else latest_brawl_for_session(session_id)
    if brawl and brawl.get("status") in ("awaiting_player", "active", "auto_running"):
        _touch_brawl_member(str(brawl.get("brawl_id") or ""), member_id)
        result = player_brawl_turn(
            text, session_id=session_id, channel=channel, use_ds=use_ds
        )
        _room_wire_result(result)
        return result
    return None
