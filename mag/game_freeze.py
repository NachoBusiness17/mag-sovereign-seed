"""Game freeze packs — high-fidelity state any seat can LOAD (Socratic / AI-Doom).

Schema: mag_game_freeze.v1
Law: engine truth only; props/fire are real state; Slow never invents them.
Layers: L0 micro · L1 play · L2 full freeze for multi-seat handoff.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import ROOT

SCHEMA = "mag_game_freeze.v1"
FREEZE_DIR = ROOT / "memory" / "working" / "game_freezes"

# Default tavern props (material + fire — engine-owned)
DEFAULT_TAVERN_PROPS: list[dict[str, Any]] = [
    {
        "id": "prop_mug_iron",
        "name": "iron mug",
        "material": "iron",
        "flammable": False,
        "hp": 6,
        "hp_max": 6,
        "on_fire": False,
        "as_weapon": "1d4",
        "notes": "Mira's honest work",
    },
    {
        "id": "prop_chair_willow",
        "name": "willow chair",
        "material": "willow",
        "flammable": True,
        "hp": 4,
        "hp_max": 4,
        "on_fire": False,
        "as_weapon": "1d4",
        "notes": "breaks, burns, or flies",
    },
    {
        "id": "prop_table_oak",
        "name": "oak table",
        "material": "oak",
        "flammable": True,
        "hp": 12,
        "hp_max": 12,
        "on_fire": False,
        "as_weapon": None,
        "notes": "sticky; hard to flip alone",
    },
    {
        "id": "prop_lamp",
        "name": "hanging lamp",
        "material": "brass+oil",
        "flammable": True,
        "hp": 3,
        "hp_max": 3,
        "on_fire": True,
        "as_weapon": None,
        "notes": "already alight; can spill",
    },
    {
        "id": "prop_stool_pine",
        "name": "pine stool",
        "material": "pine",
        "flammable": True,
        "hp": 3,
        "hp_max": 3,
        "on_fire": False,
        "as_weapon": "1d4",
        "notes": "stable-hand favorite",
    },
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fid() -> str:
    return "gf-" + uuid4().hex[:10]


def _path(freeze_id: str) -> Path:
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    return FREEZE_DIR / f"{freeze_id}.json"


def load_freeze(freeze_id: str) -> dict[str, Any] | None:
    p = _path(freeze_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_freeze(freeze: dict[str, Any]) -> Path:
    p = _path(str(freeze["freeze_id"]))
    freeze["updated"] = _utc()
    p.write_text(json.dumps(freeze, indent=2, default=str), encoding="utf-8")
    # tip pointer
    tip = FREEZE_DIR / "LATEST.json"
    tip.write_text(
        json.dumps(
            {
                "freeze_id": freeze["freeze_id"],
                "campaign_id": freeze.get("campaign_id"),
                "brawl_id": freeze.get("brawl_id"),
                "ts": freeze.get("updated") or freeze.get("ts"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return p


def latest_freeze() -> dict[str, Any] | None:
    tip = FREEZE_DIR / "LATEST.json"
    if not tip.is_file():
        return None
    try:
        meta = json.loads(tip.read_text(encoding="utf-8"))
        return load_freeze(str(meta.get("freeze_id") or ""))
    except Exception:
        return None


def ensure_room_props(camp: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach default tavern props to campaign storyteller if missing."""
    st = dict(camp.get("storyteller") or {})
    props = st.get("room_props")
    if not props:
        rid = str(camp.get("room_id") or "")
        if rid in ("tavern_lantern", "tavern_loft") or "tavern" in rid:
            props = [dict(p) for p in DEFAULT_TAVERN_PROPS]
            st["room_props"] = props
            camp["storyteller"] = st
        else:
            props = []
    return list(props or [])


def build_freeze(
    camp: dict[str, Any],
    *,
    brawl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build freeze pack from campaign + optional live brawl."""
    from mag.game_campaign import list_legal_actions, scene_context

    props = ensure_room_props(camp)
    sc = scene_context(camp)
    pl = camp.get("player") or {}
    legal = list_legal_actions(camp)

    roster: list[dict[str, Any]] = []
    turn: dict[str, Any] = {}
    brawl_id = None
    if brawl:
        brawl_id = brawl.get("brawl_id")
        for c in brawl.get("combatants") or []:
            roster.append(
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "level": c.get("level"),
                    "archetype": c.get("archetype") or c.get("role"),
                    "feat": c.get("feat"),
                    "hp": c.get("hp"),
                    "hp_max": c.get("hp_max"),
                    "ac": c.get("ac"),
                    "faction": c.get("faction"),
                    "traits": c.get("traits"),
                    "inventory": c.get("inventory"),
                    "status_effects": c.get("status_effects"),
                    "initiative": c.get("initiative"),
                    "alive": int(c.get("hp") or 0) > 0,
                    "is_player": bool(c.get("is_player")),
                }
            )
        turn = {
            "round": brawl.get("round"),
            "initiative_order": brawl.get("initiative_order"),
            "turn_index": brawl.get("turn_index"),
            "status": brawl.get("status"),
            "current": brawl.get("current_actor") or "pc",
            "awaiting_player": brawl.get("status") == "awaiting_player",
        }
        # props may be on brawl
        if brawl.get("room_props"):
            props = list(brawl["room_props"])
    else:
        if pl:
            roster.append(
                {
                    "id": "pc",
                    "name": pl.get("name"),
                    "archetype": pl.get("archetype"),
                    "feat": pl.get("feat"),
                    "hp": pl.get("hp"),
                    "hp_max": pl.get("hp_max"),
                    "ac": pl.get("ac"),
                    "faction": "player",
                    "traits": pl.get("traits"),
                    "inventory": pl.get("inventory"),
                    "is_player": True,
                    "alive": int(pl.get("hp") or 0) > 0,
                }
            )
        turn = {"status": camp.get("status"), "awaiting_player": False}

    legal_types = []
    for a in legal:
        t = a.get("type", "")
        if a.get("direction"):
            t = f"{t}:{a['direction']}"
        legal_types.append(t)
    if brawl and brawl.get("status") == "awaiting_player":
        legal_types = [
            "attack",
            "improvise",
            "unarmed",
            "grapple",
            "absurd",
            "talk",
            "flee",
            "look",
            "help",
            "ignite_prop",
            "throw_prop",
        ]

    freeze = {
        "schema": SCHEMA,
        "freeze_id": _fid(),
        "ts": _utc(),
        "campaign_id": camp.get("campaign_id"),
        "brawl_id": brawl_id,
        "module_id": camp.get("module_id"),
        "rules": {
            "system": "5e-srd-lite",
            "legal_actions": legal_types,
            "feat_notes": (pl.get("feat_note") or "") if pl else "",
            "engine_owns": ["hp", "ac", "props", "on_fire", "initiative", "rooms"],
            "slow_may": ["color", "perspective", "talk_flavor"],
            "slow_must_not": ["invent_hp", "invent_rooms", "invent_fire", "invent_kills"],
        },
        "room": {
            "id": camp.get("room_id"),
            "name": sc.get("room_name"),
            "desc": sc.get("room_desc"),
            "exits": sc.get("exits"),
            "hook": sc.get("hook"),
            "props": props,
        },
        "roster": roster,
        "turn": turn,
        "flags": list(camp.get("flags") or [])[-16:],
        "events_tail": [e.get("text") for e in (camp.get("log") or [])[-8:] if e.get("text")],
        "misconceptions": [
            {
                "false_claim": "Narrator can light a chair without engine prop state",
                "correction": "Set prop.on_fire only via engine intent ignite_prop",
            },
            {
                "false_claim": "POV monologue can kill someone",
                "correction": "Only dice events change HP; perspectives are color",
            },
        ],
        "obligations": [
            "narrate uses events_from_engine and freeze.props only",
            "no invent HP or rooms not in freeze",
            "intent must map to rules.legal_actions when possible",
        ],
        "world_roles": [
            "rules_clerk",
            "scene_painter",
            "player",
            "chronicler",
            "module_author",
        ],
        "player": {
            "name": pl.get("name"),
            "hp": pl.get("hp"),
            "hp_max": pl.get("hp_max"),
            "archetype": pl.get("archetype"),
            "feat": pl.get("feat"),
        },
    }
    if brawl and brawl.get("history"):
        last = brawl["history"][-1]
        freeze["events_tail"] = list(last.get("events") or freeze["events_tail"])[-12:]
        if last.get("perspectives"):
            freeze["perspectives_tail"] = last["perspectives"]
    return freeze


def slice_layer(freeze: dict[str, Any], layer: str = "L1") -> dict[str, Any] | str:
    """Socratic progressive disclosure."""
    layer = (layer or "L1").upper()
    if layer == "L0":
        props = freeze.get("room", {}).get("props") or []
        burning = [p["name"] for p in props if p.get("on_fire")]
        turn = freeze.get("turn") or {}
        pl = freeze.get("player") or {}
        leads = (freeze.get("rules") or {}).get("legal_actions") or []
        return {
            "layer": "L0",
            "room": (freeze.get("room") or {}).get("name"),
            "you": f"{pl.get('name')} HP {pl.get('hp')}/{pl.get('hp_max')}",
            "turn": "YOUR TURN" if turn.get("awaiting_player") else turn.get("status"),
            "burning": burning,
            "leads": leads[:4],
        }
    if layer == "L1":
        return {
            "layer": "L1",
            "room": freeze.get("room"),
            "roster": [
                {
                    "name": r.get("name"),
                    "hp": r.get("hp"),
                    "hp_max": r.get("hp_max"),
                    "faction": r.get("faction"),
                    "alive": r.get("alive"),
                }
                for r in (freeze.get("roster") or [])
            ],
            "turn": freeze.get("turn"),
            "legal": (freeze.get("rules") or {}).get("legal_actions"),
            "flags": freeze.get("flags"),
            "events_tail": (freeze.get("events_tail") or [])[-5:],
        }
    # L2 full
    return freeze


def format_socratic_help(freeze: dict[str, Any]) -> str:
    """Roguelike ? style: rules → state → options."""
    l0 = slice_layer(freeze, "L0")
    assert isinstance(l0, dict)
    props = freeze.get("room", {}).get("props") or []
    prop_lines = []
    for p in props:
        fire = " [ON FIRE]" if p.get("on_fire") else ""
        prop_lines.append(
            f"  - {p.get('name')} ({p.get('material')}) HP {p.get('hp')}/{p.get('hp_max')}{fire}"
        )
    rules = freeze.get("rules") or {}
    lines = [
        "## Rules (engine)",
        f"System: {rules.get('system')}. Engine owns: {', '.join(rules.get('engine_owns') or [])}.",
        f"Slow must not: {', '.join(rules.get('slow_must_not') or [])}.",
        "",
        "## State (L0)",
        f"Room: {l0.get('room')}. {l0.get('you')}. Turn: {l0.get('turn')}.",
        f"Burning: {', '.join(l0.get('burning') or []) or 'nothing'}.",
        "",
        "## Props",
        *(prop_lines or ["  (none)"]),
        "",
        "## Legal / leads",
        "- " + "\n- ".join(str(x) for x in (l0.get("leads") or ["look", "help"])[:8]),
        "",
        f"Freeze id: `{freeze.get('freeze_id')}` (LOAD for multi-seat handoff).",
    ]
    return "\n".join(lines)


def freeze_campaign(
    campaign_id: str,
    *,
    brawl_id: str = "",
    brawl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build + save freeze; pin on campaign storyteller."""
    from mag.game_campaign import load_campaign, save_campaign
    from mag.game_brawl import load_brawl

    camp = load_campaign(campaign_id)
    if not camp:
        return {"ok": False, "error": "no campaign"}
    st = dict(camp.get("storyteller") or {})
    bid = brawl_id or (brawl or {}).get("brawl_id") or st.get("brawl_id")
    if brawl is None and bid:
        brawl = load_brawl(str(bid))
    ensure_room_props(camp)
    if brawl and not brawl.get("room_props"):
        brawl["room_props"] = list((camp.get("storyteller") or {}).get("room_props") or [])
    freeze = build_freeze(camp, brawl=brawl)
    save_freeze(freeze)
    st["freeze_id"] = freeze["freeze_id"]
    camp["storyteller"] = st
    save_campaign(camp)
    if brawl:
        brawl["freeze_id"] = freeze["freeze_id"]
        if not brawl.get("room_props"):
            brawl["room_props"] = freeze["room"]["props"]
        from mag.game_brawl import save_brawl

        save_brawl(brawl)
    return {
        "ok": True,
        "schema": SCHEMA,
        "freeze_id": freeze["freeze_id"],
        "path": str(_path(freeze["freeze_id"]).relative_to(ROOT)).replace("\\", "/"),
        "speak": format_socratic_help(freeze),
        "L0": slice_layer(freeze, "L0"),
        "freeze": freeze,
    }


def agent_prompt_block(freeze: dict[str, Any], *, role: str = "scene_painter") -> str:
    """High-fidelity handoff text for another model/skill."""
    l1 = slice_layer(freeze, "L1")
    return (
        f"LOAD freeze `{freeze.get('freeze_id')}` schema {SCHEMA}.\n"
        f"You are world_role={role}.\n"
        f"may: color and intent from legal list. "
        f"must_not: invent HP, rooms, fire, or kills.\n\n"
        f"STATE_L1:\n{json.dumps(l1, indent=2, default=str)[:2400]}\n\n"
        f"Reply with intent JSON "
        f'{{"type":"attack|talk|improvise|absurd|ignite_prop|throw_prop|look",'
        f'"target":"...","raw":"..."}} or one short IC line.'
    )
