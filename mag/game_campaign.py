"""Campaign engine — state/legal actions first; LLM narrates after.

Schema: mag_game_campaign.v1
Law: engine owns truth; character ask + save check; traits fire tables (CK-lite).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
import hashlib
from typing import Any
from uuid import uuid4

from config import ROOT
from mag.water_computer import seed_graph as _seed_graph

SCHEMA = "mag_game_campaign.v1"
CAMP_DIR = ROOT / "memory" / "working" / "game_campaigns"
MODULES_DIR = ROOT / "memory" / "game_modules"
CHAR_DIR = ROOT / "memory" / "working" / "game_characters"

_ARCHETYPES = {
    "fighter": {"hp": 12, "hp_max": 12, "ac": 14, "attack_bonus": 4, "damage": "1d8+2"},
    "rogue": {"hp": 10, "hp_max": 10, "ac": 13, "attack_bonus": 5, "damage": "1d6+3"},
    "wizard": {"hp": 8, "hp_max": 8, "ac": 12, "attack_bonus": 3, "damage": "1d10"},
    "cleric": {"hp": 10, "hp_max": 10, "ac": 14, "attack_bonus": 3, "damage": "1d6+1"},
}
_TRAITS = ["greedy", "brave", "craven", "curious", "hotheaded", "cautious", "kind", "cynical"]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cid() -> str:
    return "gc-" + uuid4().hex[:10]


def list_modules() -> list[dict[str, Any]]:
    out = []
    if not MODULES_DIR.is_dir():
        return out
    for p in MODULES_DIR.glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            out.append(
                {
                    "module_id": m.get("module_id") or p.stem,
                    "title": m.get("title"),
                    "aliases": m.get("aliases") or [],
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                }
            )
        except Exception:
            continue
    return out


# MODULE HANDLERS (wired 2026-09-27, the dead-seam burn-down): module_id ->
# python module exposing handle(camp, action, *, atype, raw). Explicit
# registry, no import magic over untrusted json. Add a module here only
# when it carries verb semantics the generic Inform rules must not answer.
_MODULE_HANDLERS = {
    "water_computer": "mag.water_computer",
    "water_graph": "mag.water_computer",
}


def _module_handler(module_id: str):
    mod_name = _MODULE_HANDLERS.get((module_id or "").strip().lower())
    if not mod_name:
        return None
    try:
        import importlib

        mod = importlib.import_module(mod_name)
    except Exception:
        return None
    h = getattr(mod, "handle", None)
    return h if callable(h) else None


def resolve_module(name: str) -> dict[str, Any] | None:
    q = (name or "classic").strip().lower()
    # First pass: exact module_id match wins (avoids alias substring collisions).
    for p in MODULES_DIR.glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        mid = str(m.get("module_id") or "").lower()
        if q == mid:
            return m
    # Second pass: alias exact, alias substring, then title.
    for p in MODULES_DIR.glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        aliases = [str(a).lower() for a in (m.get("aliases") or [])]
        title = str(m.get("title") or "").lower()
        if q in aliases or any(q in a or a in q for a in aliases) or q in title:
            return m
    classic = MODULES_DIR / "dnd_classic_stub.v1.json"
    if classic.is_file():
        return json.loads(classic.read_text(encoding="utf-8"))
    return None


def _path(campaign_id: str) -> Path:
    return CAMP_DIR / f"{campaign_id}.json"


def load_campaign(campaign_id: str) -> dict[str, Any] | None:
    p = _path(campaign_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_campaign(camp: dict[str, Any]) -> Path:
    CAMP_DIR.mkdir(parents=True, exist_ok=True)
    camp["updated"] = _utc()
    p = _path(str(camp["campaign_id"]))
    p.write_text(json.dumps(camp, indent=2, default=str), encoding="utf-8")
    return p


def latest_for_session(session_id: str) -> dict[str, Any] | None:
    if not CAMP_DIR.is_dir() or not session_id:
        return None
    best, best_ts = None, ""
    for p in CAMP_DIR.glob("gc-*.json"):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(c.get("voice_session_id") or "") != session_id:
            continue
        if c.get("status") not in ("active", "awaiting_character", "paused"):
            continue
        ts = str(c.get("updated") or c.get("ts") or "")
        if ts >= best_ts:
            best_ts, best = ts, c
    return best


def latest_any() -> dict[str, Any] | None:
    """Most recently updated live campaign, session-agnostic. Desk mounts this, not a void."""
    if not CAMP_DIR.is_dir():
        return None
    best, best_ts = None, ""
    for pth in CAMP_DIR.glob("gc-*.json"):
        try:
            c = json.loads(pth.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("status") not in ("active", "awaiting_character", "paused"):
            continue
        ts = str(c.get("updated") or c.get("ts") or "")
        try:
            mtime = str(pth.stat().st_mtime)
        except OSError:
            mtime = ""
        key = ts or mtime
        if key >= str(best_ts):
            best_ts, best = key, c
    return best


def parse_character(text: str) -> dict[str, Any] | None:
    """Parse 'I'm Ash a greedy fighter' or 'random classic'."""
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower()
    if re.search(r"\b(random|classic character|surprise me)\b", low):
        arch = random.choice(list(_ARCHETYPES.keys()))
        traits = random.sample(_TRAITS, 2)
        name = random.choice(["Ash", "Brynn", "Corin", "Dax", "Elra", "Fenn"])
        base = dict(_ARCHETYPES[arch])
        return {
            "name": name,
            "archetype": arch,
            **base,
            "traits": traits,
            "inventory": ["torch", "rations"],
        }
    # name patterns
    name = None
    m = re.search(
        r"\b(?:i(?:'m| am)|call me|name(?:'s| is)|play as)\s+([A-Za-z][A-Za-z'-]{1,20})",
        t,
        re.I,
    )
    if m:
        name = m.group(1)
    # Tavern Brawler (5e feat kit) — preferred for brawl dogfood
    # Do not treat leading word "tavern" as character name.
    if re.search(r"\btavern\s*brawler\b", low):
        from mag.game_brawl import tavern_brawler_sheet

        bad_names = {
            "tavern",
            "brawler",
            "the",
            "a",
            "an",
            "with",
            "fighter",
            "adventurer",
        }
        nm = name if name and name.lower() not in bad_names else "Ash"
        # "I'm Brynn a tavern brawler"
        m_nm = re.search(
            r"\b(?:i(?:'m| am)|call me|name(?:'s| is)|play as)\s+([A-Za-z][A-Za-z'-]{1,20})",
            t,
            re.I,
        )
        if m_nm and m_nm.group(1).lower() not in bad_names:
            nm = m_nm.group(1)
        traits_tb = [tr for tr in _TRAITS if tr in low] or ["hotheaded", "brave"]
        sheet = tavern_brawler_sheet(nm, traits=traits_tb[:3])
        # pick up gear words into inventory
        inv = list(sheet.get("inventory") or [])
        if re.search(r"\b(axe|hatchet)\b", low) and "axe" not in inv:
            inv.append("axe")
        if re.search(r"\b(mug|ale|tankard)\b", low) and "mug" not in inv:
            inv.append("mug of ale")
        sheet["inventory"] = inv
        return {k: v for k, v in sheet.items() if k not in ("id", "is_player", "faction", "ai")}
    if not name:
        m2 = re.match(r"^([A-Za-z][A-Za-z'-]{1,20})\b", t)
        if m2 and m2.group(1).lower() not in (
            "the",
            "go",
            "i",
            "a",
            "an",
            "tavern",
            "play",
        ):
            name = m2.group(1)

    arch = "fighter"
    for a in _ARCHETYPES:
        if a in low:
            arch = a
            break
    if "rogue" in low or "thief" in low:
        arch = "rogue"
    if "mage" in low or "wizard" in low:
        arch = "wizard"
    if "cleric" in low or "priest" in low:
        arch = "cleric"
    traits = [tr for tr in _TRAITS if tr in low]
    if not traits:
        traits = ["brave"]
    if not name and not re.search(r"\b(fighter|rogue|wizard|cleric|greedy|brave|tavern)\b", low):
        return None
    if not name:
        name = "Adventurer"
    base = dict(_ARCHETYPES[arch])
    return {
        "name": name[:40],
        "archetype": arch,
        **base,
        "traits": traits[:3],
        "inventory": ["torch", "rations"],
    }


def begin_play(
    *,
    module_id: str = "classic",
    voice_session_id: str = "",
    force_new: bool = False,
) -> dict[str, Any]:
    """Save check → resume or await character / start."""
    if not force_new and voice_session_id:
        existing = latest_for_session(voice_session_id)
        if existing and existing.get("status") in ("active", "paused"):
            if existing.get("status") == "paused":
                existing["status"] = "active"
                save_campaign(existing)
            return {
                "ok": True,
                "resumed": True,
                "campaign": existing,
                "speak": (
                    f"Resuming {existing.get('module_title')}: "
                    f"{(existing.get('player') or {}).get('name')} "
                    f"in {_room(existing).get('name')}. "
                    f"HP {(existing.get('player') or {}).get('hp')}/"
                    f"{(existing.get('player') or {}).get('hp_max')}. "
                    f"Say an action: go north, attack, look, help…"
                ),
                "legal": list_legal_actions(existing),
                "scene_context": scene_context(existing),
            }
        if existing and existing.get("status") == "awaiting_character":
            starter = ((existing.get("module_snapshot") or {}).get("player_start") or {})
            if starter.get("name"):
                seated = set_character(str(existing.get("campaign_id")), dict(starter))
                camp2 = load_campaign(str(existing.get("campaign_id"))) or existing
                return {
                    "ok": True,
                    "resumed": False,
                    "need_character": False,
                    "campaign_id": camp2.get("campaign_id"),
                    "campaign": camp2,
                    "speak": seated.get("speak") or (
                        f"Starting {camp2.get('module_title')}. "
                        f"You are {starter.get('name')} the {starter.get('archetype')}."
                    ),
                    "legal": list_legal_actions(camp2),
                    "scene_context": scene_context(camp2),
                }
            return {
                "ok": True,
                "need_character": True,
                "campaign_id": existing.get("campaign_id"),
                "speak": (
                    "Campaign ready. Who are you? "
                    "Say e.g. I'm Ash a greedy fighter — or random classic."
                ),
            }

    mod = resolve_module(module_id)
    if not mod:
        return {"ok": False, "error": "no module", "modules": list_modules()}

    cid = _cid()
    camp = {
        "schema": SCHEMA,
        "campaign_id": cid,
        "ts": _utc(),
        "voice_session_id": voice_session_id or "",
        "module_id": mod.get("module_id"),
        "module_title": mod.get("title"),
        "status": "awaiting_character",
        "room_id": mod.get("start_room"),
        "player": None,
        "encounter": None,
        "flags": [],
        "storyteller": {"threat_budget": 2, "days_since_crisis": 0},
        "log": [{"ts": _utc(), "type": "init", "text": f"Module {mod.get('title')} loaded"}],
        "module_snapshot": {
            "rooms": mod.get("rooms") or {},
            "event_tables": mod.get("event_tables") or {},
            "license_note": mod.get("license_note"),
            "player_start": mod.get("player_start") or {},
        },
    }
    # Auto-seed graph mode when the module spec carries a graph_spec dict
    # (e.g. water_graph.v1.json) — routes the campaign through WaterGraph.
    _gs = mod.get("graph_spec")
    if _gs is not None:
        try:
            _seed_graph(camp, _gs)
        except Exception:  # noqa: BLE001
            pass
    save_campaign(camp)
    starter = mod.get("player_start") or {}
    if starter.get("name"):
        seated = set_character(cid, dict(starter))
        camp2 = load_campaign(cid) or camp
        return {
            "ok": True,
            "resumed": False,
            "need_character": False,
            "campaign_id": cid,
            "campaign": camp2,
            "speak": seated.get("speak") or (
                f"Starting {mod.get('title')}. "
                f"You are {starter.get('name')} the {starter.get('archetype')} "
                f"in {_room(camp2).get('name')}."
            ),
            "legal": list_legal_actions(camp2),
            "scene_context": scene_context(camp2),
        }
    return {
        "ok": True,
        "resumed": False,
        "need_character": True,
        "campaign_id": cid,
        "campaign": camp,
        "speak": (
            f"Starting {mod.get('title')}. Who are you playing? "
            "Name and class/vibe — or say random classic."
        ),
    }


def set_character(campaign_id: str, player: dict[str, Any]) -> dict[str, Any]:
    camp = load_campaign(campaign_id)
    if not camp:
        return {"ok": False, "error": "missing campaign"}
    camp["player"] = player
    camp["status"] = "active"
    start = camp.get("room_id")
    rooms = (camp.get("module_snapshot") or {}).get("rooms") or {}
    room = rooms.get(start) or {}
    enc = room.get("encounter")
    if enc:
        camp["encounter"] = dict(enc)
    camp["log"] = list(camp.get("log") or []) + [
        {
            "ts": _utc(),
            "type": "character",
            "text": f"{player.get('name')} the {player.get('archetype')} "
            f"({', '.join(player.get('traits') or [])}) enters the road.",
        }
    ]
    # persist character sheet
    try:
        CHAR_DIR.mkdir(parents=True, exist_ok=True)
        cp = CHAR_DIR / f"{re.sub(r'[^a-z0-9]+', '-', str(player.get('name') or 'x').lower())}.json"
        cp.write_text(
            json.dumps({"player": player, "campaign_id": campaign_id, "ts": _utc()}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    save_campaign(camp)
    sc = scene_context(camp)
    speak = f"Playing {player.get('name')} the {player.get('archetype')}. " + _narrate_room(camp)
    try:
        from mag.game_passage import narrate_passage, room_meta_from_camp

        pas = narrate_passage(
            sc,
            room_meta=room_meta_from_camp(camp),
            full=True,
            use_llm=True,
            last_action="arrive",
        )
        if pas.get("text"):
            speak = f"Playing {player.get('name')} the {player.get('archetype')}.\n\n" + str(
                pas["text"]
            )
    except Exception:
        pass
    return {
        "ok": True,
        "campaign": camp,
        "speak": speak,
        "legal": list_legal_actions(camp),
        "scene_context": sc,
    }


def _room(camp: dict[str, Any]) -> dict[str, Any]:
    rid = camp.get("room_id")
    return (camp.get("module_snapshot") or {}).get("rooms", {}).get(rid) or {}




def _rashomon_voice(who: str) -> str:
    """FILE voice from the tavern bar-fight seed. Engine_truth stays the ledger."""
    from config import ROOT as _R
    path = _R / "memory" / "narrative_corpus" / "rashomon" / "tavern_bar_fight_party.v1.md"
    if not path.is_file():
        return ""
    body = path.read_text(encoding="utf-8", errors="replace")
    key = "## Perspective: " + who
    if key not in body:
        return ""
    rest = body.split(key, 1)[1]
    rest = rest.split("\n", 1)[1] if "\n" in rest else rest
    chunk = rest.split("## Perspective:", 1)[0].strip()
    return " ".join(chunk.split())[:360]


def _donjon_sense(camp: dict[str, Any]) -> str:
    """Donjon constraint: one sensory atom, hashed to the room, no new geography."""
    try:
        from mag.narrative_engine import SENSORY_TABLES
    except Exception:
        return ""
    room = _room(camp)
    tags = [str(x).lower() for x in (room.get("tags") or [])]
    if "tavern" in tags or "hub" in tags or room.get("area_tag") == "hub":
        return ""
    rid = str(camp.get("room_id") or room.get("id") or "room")
    kind = "sight"
    rows = list(SENSORY_TABLES.get(kind) or SENSORY_TABLES.get("sight") or [])
    if not rows:
        return ""
    i = int(hashlib.sha256(("donjon:" + rid + ":" + kind).encode()).hexdigest()[:8], 16) % len(rows)
    return str(rows[i])



def _adjacent_memory(keys: list[str]) -> list[str]:
    """Single recall surface: verkle_lance.trace. Themes only — session_ids are theater."""
    lines: list[str] = []
    try:
        from mag.verkle_lance import trace
    except Exception:
        return lines
    for key in keys:
        try:
            r = trace(str(key), limit=4)
        except Exception:
            continue
        if not r.get("found"):
            continue
        for m in r.get("matches") or []:
            theme = str(m.get("theme") or "")
            low = theme.lower()
            if not theme or "steal_pack" in low or "rib_bus_" in low:
                continue
            if theme not in lines:
                lines.append(theme)
            if len(lines) >= 6:
                return lines
    return lines


def _rib_babel_speech() -> str:
    """Plain speech from memory/rib_bus/babelfish-turtles.json. No hashes, no filenames."""
    path = ROOT / "memory" / "rib_bus" / "babelfish-turtles.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    for rec in (data.get("ribs") or {}).values():
        inv = str(rec.get("invariant") or "").strip()
        if not inv:
            continue
        body = inv.split(":", 1)[-1].strip() if ":" in inv[:90] else inv
        body = re.sub(r"\([^)]*self_loop[^)]*\)", "", body)
        body = re.sub(r"\bfish_ear\b", "fish", body)
        body = re.sub(r"\s+\.", ".", body)
        return " ".join(body.split())
    return ""


def _player_signal(text: str, *, source: str) -> str:
    """percolator.partition: SIGNAL vs THEATER vs NOISE. steal_pack / rib_bus_ never narrate."""
    raw = (text or "").strip()
    if not raw:
        return ""
    kept: list[str] = []
    try:
        from mag.percolator import partition
        part = partition(raw, source=source)
        for row in part.get("signal") or []:
            sent = str(row.get("sentence") or "").strip()
            low = sent.lower()
            if not sent or "steal_pack" in low or "rib_bus_" in low:
                continue
            kept.append(sent)
    except Exception:
        kept = []
    if not kept:
        kept = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", raw)
            if s.strip() and "steal_pack" not in s.lower() and "rib_bus_" not in s.lower()
        ]
    return " ".join(kept).strip()



def _trial_from_lance(goal: str) -> str:
    """ghost_memlance.select: the quest is naming the grounded tool. Two strokes, then wait."""
    try:
        from mag.ghost_memlance import select
        picked = select(goal, k=6)
    except Exception:
        return ""
    strokes: list[str] = []
    for s in picked.get("selected") or []:
        if not s.get("verified"):
            continue
        raw = str(s.get("excerpt") or "")
        # drop markdown chrome; keep operator bytes
        keep: list[str] = []
        for ln in raw.splitlines():
            t = ln.strip()
            if not t or t.startswith("#") or t.startswith("**Schema") or t.startswith("**Scope"):
                continue
            t = re.sub(r"^\*\*[^*]+\*\*:\s*", "", t)
            t = t.strip("\"'")
            if t:
                keep.append(t)
        body = " ".join(keep)
        body = _player_signal(body, source="memlance") or body
        body = " ".join(body.split())
        if len(body) < 24:
            continue
        # first sentence only — Positronick: two strokes
        sent = re.split(r"(?<=[.!?])\s+", body)[0].strip()
        if sent and sent not in strokes:
            strokes.append(sent.rstrip(".") + ".")
        if len(strokes) >= 2:
            break
    if not strokes:
        return ""
    return " ".join(strokes) + " What do you do?"



def _named_hearth(camp: dict[str, Any]) -> bool:
    """Evennia characters≠things: Calcifer is DefaultCharacter only at Mira's lantern hearth."""
    room = _room(camp)
    rid = str(camp.get("room_id") or room.get("id") or room.get("name") or "").lower()
    rname = str(room.get("name") or "").lower()
    return ("lantern" in rid) or ("tavern" in rid) or ("mira" in rname)

def _talk_calcifer(camp: dict[str, Any]) -> str:
    """Hearth: persona_recall trickster + RIB invariant. No session_id dump."""
    if not _named_hearth(camp):
        return ""
    room = _room(camp)
    blob = " ".join([
        str(room.get("name") or ""),
        str(room.get("desc") or ""),
        " ".join(str(h) for h in (room.get("hooks") or [])),
    ]).lower()
    if not any(w in blob for w in ("fire", "hearth", "flame", "damp", "calcifer")):
        return ""
    beat = _trial_from_lance("calcifer named hearth fingerprint liquid familiar babel")
    if beat:
        return beat
    line = "You already named this fire. The next name is the tool you do not have. What do you do?"
    return _player_signal(line, source="calcifer") or line


def _look_at(camp: dict[str, Any], noun: str) -> str:
    """Examine one thing in the room. Bytes already on the lantern, not a new throne."""
    room = _room(camp)
    n = (noun or "").strip().lower()
    desc = str(room.get("desc") or "")
    hooks = [str(h) for h in (room.get("hooks") or [])]
    if n in ("fire", "hearth", "flame", "calcifer", "torch"):
        # Evennia get_display_things: inventory/keep torch is a Thing, not the named Character
        if n == "torch" and not _named_hearth(camp):
            hit = next((h for h in hooks if "torch" in h.lower()), "")
            return hit or "A torch. Just a torch. It is not the fire you named."
        if n == "torch" and _named_hearth(camp):
            return "A torch in hand. The named fire is the hearth, not this stick."
        if _named_hearth(camp):
            return "The fire argues with the damp. It is the only honest heat in the room. You named it Calcifer."
        return "No named fire here. A torch is a torch."
    if n in ("mug", "tankard", "glass"):
        return "The same mug. Mira polishes it like a debt she can finish."
    if "stranger" in n:
        hit = next((h for h in hooks if "stranger" in h.lower()), "")
        return hit or "A stranger maps wet rings on the table and will not look up."
    if n in ("barkeep", "mira", "bartender"):
        hit = next((h for h in hooks if "barkeep" in h.lower()), "")
        return hit or "The barkeep polishes the same mug."
    if n in ("door", "road"):
        return "Door to the road. The weather is on the other side of it."
    if n in ("stairs", "rooms"):
        return "Stairs up to rooms. The boards remember wet wool."
    if n in ("cart", "wagon", "tracks"):
        hit = next((h for h in hooks if "cart" in h.lower() or "track" in h.lower()), "")
        return hit or "Mixed tracks. An overturned cart. Blood, no bodies."
    if n in ("gate", "gates", "gatehouse"):
        return desc or "Iron-bound gates. The keep is the building that appeared."
    if n in ("raven", "ravens"):
        return "Raven calls. They already know the chimney is wrong."
    if n in ("chimney", "keep", "smoke", "weather"):
        hit = next((h for h in hooks if "chimney" in h.lower() or h.lower().startswith("rumor")), "")
        if hit.lower().startswith("rumor"):
            hit = hit.split(":", 1)[-1].strip()
        return hit or "The keep chimney. Wrong smoke for this weather."
    if n in ("chair", "table", "tables", "rings"):
        return "Sticky tables. Wet rings. Someone has been mapping them and will not look up."
    if n in ("torch", "rations", "coins"):
        return "You are carrying that."
    if n in ("merchant", "captive", "prisoner"):
        hit = next((h for h in hooks if any(w in h.lower() for w in ("merchant", "captive", "prisoner"))), "")
        body = hit.split(":", 1)[-1].strip() if hit else ""
        return body or "A captive merchant, still bound. The keep's business did not end at the gate."
    if n in ("crate", "chest", "seal", "box"):
        hit = next((h for h in hooks if any(w in h.lower() for w in ("crate", "seal", "chest", "box"))), "")
        body = hit.split(":", 1)[-1].strip() if hit else ""
        opened = any(str(f).startswith("temple:") or str(f).startswith("shared:") or str(f).startswith("slain:") for f in (camp.get("flags") or []))
        if not opened:
            beat = _trial_from_lance(
                "puzzle box temple primer play_rooms dungeon_dev rooms are the roadmap missing tool"
            )
            return beat or "The box is closed because the tool is unnamed. What do you do?"
        return body or _trial_from_lance("dungeon_dev conquer share the knot") or "The box is open. The ward has a name."
    if n:
        try:
            from mag.verkle_lance import trace
            trace(n, limit=2)
        except Exception:
            pass
        for h in hooks:
            if n in h.lower():
                return h
        if n in desc.lower():
            for sent in re.split(r"(?<=[.!?])\s+", desc):
                if n in sent.lower():
                    return sent
            # Noun is scenery mentioned in desc but no focused sentence — still one beat,
            # not a second Look of the whole room (Inform "nothing special" class).
            return "Nothing special about the " + noun + "."
    # Evennia caller.search no-match: short refuse then return (no room.desc dump).
    # Inform parser error (E): "You can't see any such thing." — one beat, not Look glue.
    return ("Nothing called " + (noun or "that") + " here.").strip()


def _hook_body(s: str) -> str:
    t = str(s or "").strip()
    if not t:
        return ""
    if t.lower().startswith(("rumor", "quest", "hook")) and ":" in t[:28]:
        t = t.split(":", 1)[-1].strip()
    elif ":" in t[:28]:
        head, rest = t.split(":", 1)
        if head.strip().replace(" ", "").isalpha() and len(head.strip()) < 24:
            t = rest.strip()
    return t


def _lookables(room: dict[str, Any]) -> list[str]:
    blob = " ".join([
        str(room.get("name") or ""),
        str(room.get("desc") or ""),
        " ".join(str(h) for h in (room.get("hooks") or [])),
        " ".join(str(x) for x in (room.get("loot") or [])),
    ]).lower()
    nouns = (
        "crate", "seal", "merchant", "captive", "torch", "fire",
        "cart", "gate", "mug", "stranger", "chest", "tracks",
    )
    out: list[str] = []
    for n in nouns:
        if n in blob and n not in out:
            out.append(n)
    return out[:6]


def _takeables(camp: dict[str, Any]) -> list[str]:
    room = _room(camp)
    inv = [str(x).lower() for x in ((camp.get("player") or {}).get("inventory") or [])]
    loot = [str(x) for x in (room.get("loot") or [])]
    out: list[str] = []
    for x in loot:
        if x and x.lower() not in inv and x.lower() not in [o.lower() for o in out]:
            out.append(x)
    blob = " ".join([str(room.get("desc") or ""), " ".join(str(h) for h in (room.get("hooks") or []))]).lower()
    if "crate" in blob and "crate" not in inv and "crate" not in [o.lower() for o in out]:
        out.append("crate")
    return out[:4]


def story_so_far(camp: dict[str, Any]) -> str:
    """Legend of the run. Start near the end. The sim already happened."""
    if not camp:
        return ""
    pl = camp.get("player") or {}
    who = str(pl.get("name") or "You")
    room = _room(camp)
    here = str(room.get("name") or camp.get("room_id") or "somewhere")
    rid = str(camp.get("room_id") or "")
    flags = [str(x) for x in (camp.get("flags") or []) if x]
    log = list(camp.get("log") or [])
    blob = " ".join(
        [rid, here, " ".join(flags)]
        + [str(e.get("text") or "") for e in log[-80:]]
        + [str(e.get("type") or "") for e in log[-80:]]
    ).lower()
    color = str((camp.get("storyteller") or {}).get("color") or "").strip()

    # Vonnegut: start at the end of what already happened.
    now = []
    if "claw" in rid or "claw" in here.lower() or "hall" in here.lower():
        if "goblin" in blob:
            now.append("The goblin band is already down. That is not the story.")
        now.append("The keep is a temple. The crate is a puzzle box. The story is who comes out when you open it.")
    elif "keep" in rid or "gate" in rid:
        now.append("The keep is the building that appeared. The chimney still lies about the weather.")
    elif "lantern" in rid or "tavern" in here.lower():
        now.append("The lantern is still a hub. The road north is the call.")
    else:
        now.append(f"Now: {here}.")

    path = []
    if any(w in blob for w in ("lantern", "tavern", "mira")):
        path.append("the Guttered Lantern")
    if any(w in blob for w in ("road", "cart", "tracks")):
        path.append("the road with the overturned cart")
    if any(w in blob for w in ("keep_gate", "gatehouse", "courtyard")):
        path.append("the keep gate")
    if any(w in blob for w in ("cellar", "cave", "fork")):
        path.append("the caves")
    if any(w in blob for w in ("claw", "hall")):
        path.append("the claw-marked hall")
    walked = ""
    if path:
        walked = f"{who} walked {', then '.join(path)}. "

    calc = ""
    # Thing≠Character: carried/keep torch does not mint Calcifer into the saga
    if "calcifer" in blob or ("lantern" in blob and any(w in blob for w in ("fire", "hearth", "mira"))):
        calc = "The fire came with them — Calcifer, same flame as the lantern, still arguing with the damp. "

    want = ""
    if "merchant" in blob or "captive" in blob:
        want = "The merchant wants a name spoken and a rope cut. The crate wants to go up. "
    if "chimney" in blob or "wrong smoke" in blob:
        want += "The keep still wants its lie believed. "

    legend = (walked + " ".join(now) + " " + calc + want).strip()
    if color and color.lower() not in legend.lower():
        legend = legend + " " + color[:280]
    return " ".join(legend.split())


def _craft_narrate(camp: dict[str, Any], events: list[str]) -> str:
    """Author corpus through Mag DM voice. Engine bytes stay truth. No new throne."""
    room = _room(camp)
    pl = camp.get("player") or {}
    try:
        from mag.corpus_query import inspire_for_scene
        from mag.game_dm_voice import _narrator_from_pack
        pack = (inspire_for_scene(
            story=" ".join(str(e) for e in (events or [])[-5:]),
            room=str(room.get("name") or room.get("id") or ""),
            flags=list(camp.get("flags") or [])[-8:],
            events_tail=list(events or [])[-5:],
        ) or {}).get("pack") or {}
        line = _narrator_from_pack(
            pack,
            status=str(camp.get("status") or "active"),
            player_name=str(pl.get("name") or "Adventurer"),
            absurd=False,
            your_turn=True,
            events=list(events or []),
        )
        return " ".join(str(line or "").split())[:420]
    except Exception:
        return ""


def _llm_room_beat(camp: dict[str, Any]) -> str:
    """Creative DM beat via game_dm_llm (emergent, Memento-flavored). Returns text or None on
    failure so the deterministic narration is the safe fallback."""
    try:
        from mag import game_dm_llm
        room = _room(camp)
        scene = f"{room.get('name')}. {room.get('desc')}".strip()
        root = str((camp.get("world_root") or ""))[:16]
        res = game_dm_llm.dm_narrate(scene, world_root=root, action="look", history=camp.get("log") or [])
        if res.get("ok") and res.get("text"):
            return str(res["text"]).strip()
    except Exception:
        pass
    return ""


def _narrate_room(camp: dict[str, Any]) -> str:
    """This beat. Objects first. People want. Soft craft echo. No census."""
    # Creative DM (MAG_CAMPAIGN_LLM, default ON): emergent LLM narration via game_dm_llm,
    # deterministic fallback if it fails. Set MAG_CAMPAIGN_LLM=0 for the pure $0 engine.
    if os.environ.get("MAG_CAMPAIGN_LLM", "1") not in ("0", "false", "no"):
        beat = _llm_room_beat(camp)
        if beat:
            return beat
    room = _room(camp)
    name = str(room.get("name") or "?")
    desc = str(room.get("desc") or "").strip()
    paras: list[str] = []
    lead = desc if desc and desc.lower().startswith(name.lower()) else (
        f"{name}. {desc}" if desc else f"{name}."
    )
    paras.append(lead if lead[-1:] in ".!?" else lead + ".")

    people = people_in_room(camp)
    hooks = [str(h).strip() for h in (room.get("hooks") or []) if str(h).strip()]
    rumor = ""
    used = set()
    for h in hooks:
        low = h.lower()
        if low.startswith("quest"):
            continue
        if low.startswith("rumor"):
            rumor = _hook_body(h)
            continue
        body = _hook_body(h)
        if not body:
            continue
        for ppl in people:
            if ppl.lower() in h.lower():
                used.add(ppl.lower())
        words = body.replace(".", "").split()
        # Inform: skip when_closed labels; weave verbs only
        if len(words) <= 6 and not any(
            w.lower() in ("is", "are", "has", "holds", "wants", "lies", "sits", "burns", "waits")
            for w in words
        ):
            continue
        if body[-1] not in ".!?":
            body += "."
        paras.append(body)
        for p in people:
            if p.lower() in h.lower():
                used.add(p.lower())

    leftover = [p for p in people if p.lower() not in used]
    if leftover:
        if len(leftover) == 1:
            paras.append(f"{leftover[0]} is here, and wants something.")
        else:
            paras.append(", ".join(leftover[:-1]) + f", and {leftover[-1]} are here.")

    if rumor and rumor.lower() not in " ".join(paras).lower():
        paras.append(rumor if rumor[-1:] in ".!?" else rumor + ".")

    enc = camp.get("encounter")
    if enc and int(enc.get("hp") or 0) > 0:
        paras.append(
            f"{enc.get('name')} still holds the floor. They want you gone more than they want to talk."
        )
    elif enc and int(enc.get("hp") or 0) <= 0:
        nm = str(enc.get("name") or "the fight")
        if nm.lower() not in " ".join(paras).lower():
            paras.append(f"{nm} is down. The stone has not cooled.")

    sense = _donjon_sense(camp)
    if sense and sense.lower() not in " ".join(paras).lower():
        paras.append(sense if sense[-1:] in ".!?" else sense + ".")

    try:
        from mag.chasm_state import recall
        mem = recall(str(camp.get("campaign_id") or ""), str(camp.get("room_id") or ""), limit=2)
        for m in mem or []:
            line = " ".join(str(m).split())
            low = line.lower()
            if not line:
                continue
            if low.startswith("this place remembers") or "`idle`" in low:
                continue
            if re.search(r"\d{4}-\d{2}-\d{2}T", line):
                continue
            if "`" in line:
                continue
            if any(line[:40] in p for p in paras):
                continue
            paras.append(line[:160] if line[-1:] in ".!?" else line[:160] + ".")
            break
    except Exception:
        pass

    exits = room.get("exits") or {}
    if isinstance(exits, dict) and exits:
        rooms = (camp.get("module_snapshot") or {}).get("rooms") or {}
        named = []
        for d, dest_id in exits.items():
            dest = rooms.get(str(dest_id) or "") or {}
            dname = str(dest.get("name") or dest_id or d)
            named.append(f"{d} toward {dname}")
        if named:
            paras.append("Ways out: " + "; ".join(named) + ".")
    return " ".join(p.strip() for p in paras if p and p.strip())



def scene_context(camp: dict[str, Any]) -> dict[str, Any]:
    """TinyStories-regime input for narrator — no dig/desk sludge."""
    room = _room(camp)
    pl = camp.get("player") or {}
    return {
        "room_name": room.get("name"),
        "room_desc": room.get("desc"),
        "hook": (room.get("hooks") or [None])[0],
        "hooks": list(room.get("hooks") or []),
        "exits": list((room.get("exits") or {}).keys()),
        "encounter": camp.get("encounter"),
        "player": {
            "name": pl.get("name"),
            "archetype": pl.get("archetype"),
            "hp": pl.get("hp"),
            "hp_max": pl.get("hp_max"),
            "traits": pl.get("traits"),
        },
        "flags": (camp.get("flags") or [])[-8:],
        "log_tail": [e.get("text") for e in (camp.get("log") or [])[-3:]],
        "legal": list_legal_actions(camp),
    }


def _examine_verbs(camp: dict[str, Any]) -> str:
    """Command/verb reference for the current room — the grounded 'how do I play' answer."""
    room = _room(camp)
    lookables = _lookables(room)
    takeables = _takeables(camp)
    people = people_in_room(camp)
    exits = list((room.get("exits") or {}).keys())
    L = ["— COMMANDS · verbs you can use right now —"]
    if lookables:
        L.append("  look <object>    : study  " + ", ".join(str(x) for x in lookables))
    if people:
        L.append("  talk <person>    : speak  " + ", ".join(people))
    if takeables:
        L.append("  take <item>      : take   " + ", ".join(str(x) for x in takeables))
    if exits:
        L.append("  move <direction> : go     " + ", ".join(exits))
    L.append("  use <object>     : interact with a feature (torch / crate / box / seal)")
    L.append("  examine          : this reference · examine <object> : study one thing closer")
    L.append("  try <verb> <obj> : attempt a complex action — the dice decide, the world reacts")
    L.append("  look / rest / rumor / drink / work")
    return "\n".join(L)


def _verbs_for_object(camp: dict[str, Any], noun: str) -> str:
    """Suggest verbs that work on one examined object (the 'try' hook)."""
    return (f"On the {noun}, you could: examine <it>, use {noun}, or try <verb> {noun}. "
            f"Look close first — the right verb may be hiding in its description.")


def _try_action(
    camp: dict[str, Any], pl: dict[str, Any], action: dict[str, Any], *, raw: str = ""
) -> str:
    """Complex interaction: roll the dice, decide success/fail, narrate the consequence
    (via the creative DM), and subtly hint a good next move to finish the task."""
    from mag.game_dice import roll_dice

    text = (raw or str(action.get("raw") or action.get("text") or "")).strip()
    rest = re.sub(r"^(try|try to|attempt|attempt to)\s+", "", text, flags=re.I).strip()
    words = rest.split()
    verb = words[0].lower() if words else "force"
    target = " ".join(words[1:]).strip() or str(action.get("target") or "the door")
    room = _room(camp)
    bonus = int(pl.get("attack_bonus") or 2)
    roll = int(roll_dice("1d20", seed=None).get("total") or 1) + bonus
    dc = 12
    ok = roll >= dc
    try:
        from mag import game_dm_llm
        scene = f"{room.get('name')}. {room.get('desc')}".strip()
        prompt = (f"The player attempts to {verb} the {target}. "
                  f"Roll {roll} vs difficulty {dc} — {'SUCCESS' if ok else 'FAILURE'}. "
                  f"Narrate the consequence, then subtly hint a good next move to finish the task.")
        res = game_dm_llm.dm_narrate(scene, action=prompt)
        if res.get("ok") and res.get("text"):
            return str(res["text"]).strip()
    except Exception:
        pass
    if ok:
        camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + [f"handled:{target.lower()[:20]}"]))
        return (f"You {verb} the {target} — it gives ({roll} vs {dc}). A knot unties in the world. "
                f"Look or examine to see what changed; something here may be finishable now.")
    return (f"You try to {verb} the {target}, but it resists ({roll} vs {dc}). It keeps its secret. "
            f"Examine it again — there is likely a tool or a word you have not tried yet.")


def list_legal_actions(camp: dict[str, Any]) -> list[dict[str, Any]]:
    room = _room(camp)
    acts: list[dict[str, Any]] = []
    enc = camp.get("encounter")
    if enc and int(enc.get("hp") or 0) > 0:
        acts.append({"type": "attack"})
        acts.append({"type": "flee"})
    for name in people_in_room(camp):
        acts.append({"type": "talk", "target": name})
    for noun in _lookables(room):
        acts.append({"type": "look", "target": noun})
    for item in _takeables(camp):
        acts.append({"type": "take", "item": item})
    for direction in room.get("exits") or {}:
        acts.append({"type": "move", "direction": direction})
    acts.append({"type": "work"})
    acts.append({"type": "look"})
    acts.append({"type": "rest"})
    tags = [str(t).lower() for t in (room.get("tags") or [])]
    if "tavern" in tags or "hub" in tags or room.get("area_tag") == "hub":
        acts.extend([{"type": "rumor"}, {"type": "drink"}])
    if room.get("area_tag") in ("road", "woods") or "road" in str(room.get("id") or ""):
        acts.append({"type": "seek_fight"})
    acts.append({"type": "examine"})  # command/verb reference (how to play, grounded)
    acts.append({"type": "try"})      # complex interaction: roll -> consequence -> hint
    return acts



def people_in_room(camp: dict[str, Any]) -> list[str]:
    """Names you can talk to. Same bytes wave._room_who already paints."""
    room = _room(camp)
    names: list[str] = []
    enc = camp.get("encounter")
    if isinstance(enc, dict) and enc.get("name") and int(enc.get("hp") or 0) > 0:
        names.append(str(enc.get("name")))
    for h in room.get("hooks") or []:
        s = str(h).strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith("rumor") or low.startswith("quest"):
            continue
        name = ""
        if low.startswith("barkeep"):
            name = "barkeep"
        elif "stranger" in low:
            name = "stranger"
        elif "merchant" in low or "captive" in low:
            name = "merchant"
        elif "goblin" in low:
            name = "goblin"
        elif ":" in s[:28]:
            name = s.split(":", 1)[0].strip()
            if name.lower() in ("rumor", "quest", "hook"):
                continue
        if not name:
            continue
        if any(x.lower() == name.lower() for x in names):
            continue
        names.append(name)
    blob = " ".join([
        str(room.get("name") or ""),
        str(room.get("desc") or ""),
        " ".join(str(x) for x in (room.get("tags") or [])),
        " ".join(str(h) for h in (room.get("hooks") or [])),
    ]).lower()
    # characters≠things: Calcifer only on named hearth (not every torch)
    if _named_hearth(camp) and any(w in blob for w in ("fire", "hearth", "flame", "calcifer")):
        if "calcifer" not in [n.lower() for n in names]:
            names.append("Calcifer")
    return names


def _talk_target(raw: str, people: list[str], explicit: str = "") -> str:
    if (explicit or "").strip():
        e = explicit.strip()
        for p in people:
            if p.lower() == e.lower() or e.lower() in p.lower() or p.lower() in e.lower():
                return p
        return e
    blob = (raw or "").strip().lower()
    for p in people:
        if p.lower() in blob:
            return p
    aliases = (("mira", "barkeep"), ("bartender", "barkeep"))
    for a, canon in aliases:
        if re.search(rf"\\b{a}\\b", blob):
            for p in people:
                if p.lower() == canon:
                    return p
            return canon
    m = re.search(
        r"\\b(?:talk|speak|say|ask)\\s+(?:to\\s+|with\\s+)?(?:the\\s+)?([a-z][\\w'-]*)",
        blob,
    )
    if m:
        cand = m.group(1)
        if cand not in ("to", "the", "a", "an", "me", "you"):
            return cand
    return ""


def _hook_for_person(room: dict[str, Any], name: str) -> str:
    for h in room.get("hooks") or []:
        if name.lower() in str(h).lower():
            return str(h).strip()
    return ""


def _talk_events(camp: dict[str, Any], pl: dict[str, Any], action: dict[str, Any]) -> list[str]:
    """Address the person in the room. Hooks are their lines. No rumor dump."""
    raw = str(action.get("raw") or "").strip()
    room = _room(camp)
    people = people_in_room(camp)
    you = str(pl.get("name") or "").strip()
    target = _talk_target(raw, people, str(action.get("target") or ""))
    events: list[str] = []
    low_raw = raw.lower().strip()
    commandish = (
        low_raw in ("talk", "speak", "say", "ask")
        or low_raw.startswith(("talk to ", "speak to ", "say to ", "ask ", "talk with ", "speak with "))
        or bool(re.search(r"\b(wink|nod|wave)\s+at\b", low_raw))
    )
    # Evennia CmdSay: empty args → "Say what?" and return (no room lecture).
    # at_pre_say returning empty also aborts with no msg_contents.
    # Bare say/speak must not auto-pick the only person and dump their hook.
    if low_raw in ("say", "speak") and not str(action.get("target") or "").strip():
        events.append("Say what?")
        return events
    if raw and not commandish:
        events.append(f'You say: "{raw[:180]}"')
    elif not raw:
        events.append("Say what?")
        return events
    if target and you and target.lower() == you.lower():
        events.append("That's you.")
        if people:
            events.append("Here: " + ", ".join(people) + ".")
        return events
    if not target:
        names = {x.lower() for x in people}
        if "barkeep" in names and any(
            w in low_raw for w in ("polish", "mug", "tankard", "glass", "why", "mira")
        ):
            target = "barkeep"
        elif "stranger" in names and any(
            w in low_raw for w in ("hunt", "mark", "bad guy", "failed", "party", "adventur")
        ):
            target = "stranger"
        elif "barkeep" in names and any(
            w in low_raw for w in ("howdy", "hello", "hey", "hiya", "greetings")
        ):
            target = "barkeep"
        elif len(people) == 1:
            target = people[0]
        elif people:
            events.append("Talk to whom? " + ", ".join(people) + ".")
            return events
        else:
            # Evennia talking_npc CmdTalk sits ON the NPC, not the room
            # (contrib/tutorials/talking_npc). Empty people = no talk cmdset.
            # Operator law: empty-room hi is "No one answers", never a hearth lecture.
            events.append("No one answers.")
            return events
    here = any(
        p.lower() == target.lower() or target.lower() in p.lower() for p in people
    )
    if people and not here:
        events.append("No " + target + " here. Here: " + ", ".join(people) + ".")
        return events
    tlow = target.lower()
    if "calcifer" in tlow or tlow in ("fire", "hearth", "flame"):
        beat = _talk_calcifer(camp)
        events.append(beat or ("The fire pops. You named it Calcifer." if _named_hearth(camp) else "No named fire here. A torch is a torch."))
        return events
    if tlow == "torch":
        events.append("A torch. Just a torch. It does not answer as Calcifer.")
        return events
    if "merchant" in tlow or "captive" in tlow:
        beat = _trial_from_lance(
            "right sized tools flock memlance identify the tool we needed for the intended goal"
        )
        events.append(beat or "The merchant waits. The box is a question. What do you do?")
        return events
    if tlow in ("barkeep", "mira") or "barkeep" in tlow:
        if any(w in raw.lower() for w in ("polish", "mug", "tankard", "glass", "why")):
            events.append(
                "Mira the barkeep does not look up. "
                "'Because if I stop, I start counting chairs I do not own and debts I do. "
                "Mug is honest work. Keep smoke is not my department.'"
            )
            return events
        hook = _hook_for_person(room, "barkeep") or _hook_for_person(room, target)
        if hook:
            events.append(hook)
            return events
        events.append(
            "The barkeep polishes. The fire argues with the damp. "
            "No one answers cleanly — but the room heard you."
        )
        return events
    if tlow == "stranger" or "stranger" in tlow:
        if any(w in raw.lower() for w in ("hunt", "mark", "bad guy", "failed", "party", "adventur")):
            events.append(
                "A regular snorts. 'Party came back empty-handed. "
                "Heat like that finds a stranger's stool real quick.'"
            )
            camp["flags"] = list(
                dict.fromkeys(list(camp.get("flags") or []) + ["failed_hunt_rumor"])
            )
            return events
        voice = _rashomon_voice("stranger")
        if voice:
            events.append("The stranger does not look up. " + voice)
            return events
        hook = _hook_for_person(room, "stranger")
        if hook:
            events.append(hook)
            return events
    hook = _hook_for_person(room, target)
    if hook:
        events.append(hook)
        return events
    events.append(target + " does not answer cleanly. The room heard you.")
    return events


def _pick_weighted(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    total = sum(int(r.get("w") or 1) for r in rows)
    x = random.randint(1, max(1, total))
    acc = 0
    for r in rows:
        acc += int(r.get("w") or 1)
        if x <= acc:
            return r
    return rows[-1]


def _fire_rest_events(camp: dict[str, Any]) -> list[str]:
    """CK/Rim-lite: tables + traits produce comedy."""
    events: list[str] = []
    tables = (camp.get("module_snapshot") or {}).get("event_tables") or {}
    pl = camp.get("player") or {}
    traits = [str(t).lower() for t in (pl.get("traits") or [])]
    st = camp.get("storyteller") or {}
    st["days_since_crisis"] = int(st.get("days_since_crisis") or 0) + 1

    row = _pick_weighted(list(tables.get("rest_safe") or []))
    if row:
        events.append(str(row.get("text") or ""))
        if row.get("lose") and row["lose"] in (pl.get("inventory") or []):
            pl["inventory"] = [i for i in pl.get("inventory") or [] if i != row["lose"]]
            events.append(f"(Lost {row['lose']}.)")
        if row.get("id") == "omen" and "craven" in traits:
            events.append("Your craven streak whispers: turn back.")
        if row.get("id") == "thief" and "greedy" in traits:
            events.append("As a greedy soul, the missing ration stings extra.")

    # merchant debt comedy if flag pending
    if "freed_merchant_opportunity" in (camp.get("flags") or []) and "greedy" in traits:
        row2 = _pick_weighted(list(tables.get("greedy_merchant") or []))
        if row2:
            events.append(str(row2.get("text") or ""))
            if row2.get("flag"):
                camp["flags"] = list(camp.get("flags") or []) + [str(row2["flag"])]
            camp["flags"] = [f for f in camp["flags"] if f != "freed_merchant_opportunity"]

    # storyteller crisis if budget and long calm
    budget = int(st.get("threat_budget") or 0)
    if budget > 0 and int(st.get("days_since_crisis") or 0) >= 2 and random.random() < 0.35:
        events.append("Distant horns — the keep's troubles don't sleep when you do.")
        st["days_since_crisis"] = 0
        st["threat_budget"] = budget - 1

    camp["storyteller"] = st
    camp["player"] = pl
    return [e for e in events if e]


def _act_events(camp: dict[str, Any], action: dict[str, Any]) -> list[str]:
    """cast/summon/call: collide verb with room bytes + lance.trace. FILE speech, never empty."""
    raw = str(action.get("raw") or "").strip()
    verb = str(action.get("verb") or "").strip().lower()
    target = str(action.get("target") or "").strip().lower()
    blob = (raw + " " + verb + " " + target).lower()
    room = _room(camp)
    desc = str(room.get("desc") or "")
    hooks = [str(h) for h in (room.get("hooks") or [])]
    room_blob = " ".join(
        [str(room.get("name") or ""), desc, " ".join(hooks)]
    ).lower()
    try:
        from mag.fish_ear import decompile
        decompile(raw or (verb + " " + target))
    except Exception:
        pass
    found: dict[str, bool] = {}
    try:
        from mag.verkle_lance import trace
        for k in ("fireball", "familiar", "babel", "calcifer", "percolat"):
            try:
                found[k] = bool((trace(k, limit=3) or {}).get("found"))
            except Exception:
                found[k] = False
    except Exception:
        pass
    parts: list[str] = []
    if "fireball" in blob or (verb == "cast" and "familiar" not in blob):
        if _named_hearth(camp) and any(w in room_blob for w in ("fire", "hearth", "flame")):
            parts.append(
                "The hearth pops — Calcifer, the fire you named. It answers the cast."
            )
        elif any(w in room_blob for w in ("torch", "fire", "flame", "hearth")):
            parts.append("The torch pops. Just a torch.")
        dice_h = next((h for h in hooks if "dice" in h.lower()), "")
        if dice_h:
            parts.append(dice_h)
        if "gate" in room_blob and desc:
            parts.append(desc.split(".")[0].strip().rstrip(".") + ".")
        if not found.get("fireball"):
            parts.append("The chain has no fireball knot. The room still moves.")
    if "familiar" in blob or verb in ("summon", "call"):
        if found.get("babel") or found.get("familiar"):
            rib = _rib_babel_speech()
            origin_what = ""
            try:
                from mag.fish_ear import originate
                origin_what = str(((originate() or {}).get("origin") or {}).get("what") or "")
            except Exception:
                pass
            parts.append(
                "The liquid familiar answers as translation in a body of work — "
                "the babel fish, not a pet on the floor."
            )
            if rib:
                parts.append(rib)
            elif origin_what:
                parts.append(origin_what)
            camp["flags"] = list(
                dict.fromkeys(list(camp.get("flags") or []) + ["liquid_familiar"])
            )
        else:
            if any(w in room_blob for w in ("torch", "fire", "flame")):
                parts.append("The torch pops. No familiar stands on the floor.")
            elif hooks:
                parts.append(hooks[0])
    if not parts:
        try:
            from mag.swarm_emerge import detect
            detect()
        except Exception:
            pass
        # Evennia SystemNoMatch: self.msg("Huh?") — one refuse, never return_appearance.
        # Inform Check/Instead fail: stop the action; do not Look the room.
        v = (verb or "verb").strip() or "verb"
        parts.append("Nothing answers that " + v + ".")
    speech = _player_signal(" ".join(p for p in parts if p), source="keep_gate_act")
    if not speech:
        speech = " ".join(p for p in parts if p) or "Nothing answers that verb."
    return [speech]


def apply_action(campaign_id: str, action: dict[str, Any] | None) -> dict[str, Any]:
    from mag.game_dice import roll_dice

    camp = load_campaign(campaign_id)
    if not camp:
        return {"ok": False, "error": "missing campaign"}
    if camp.get("status") == "awaiting_character":
        return {"ok": False, "error": "need character first", "need_character": True}
    if camp.get("status") != "active":
        return {"ok": False, "error": f"campaign {camp.get('status')}"}

    action = action or {}
    atype = str(action.get("type") or "").lower().strip()
    raw = str(action.get("raw") or action.get("text") or "").strip()
    legal = list_legal_actions(camp)
    events: list[str] = []
    pl = camp.get("player") or {}

    # MODULE VERB DISPATCH (wired 2026-09-27, the dead-seam burn-down):
    # mag/water_computer.py::handle() existed since the module landed with
    # ZERO callers — the engine answered module verbs ("open valve", "pour
    # bucket") with generic Inform rules and the water tests failed on a
    # seam that was never connected (tests/test_water_computer.py 5 red
    # since landing; audit LANE4D flagged the module). A module handler
    # that claims the verb returns BEFORE the generic rules; persistence
    # rides the same save_campaign every other action path uses.
    _mod_handler = _module_handler(str(camp.get("module_id") or ""))
    if _mod_handler is not None:
        try:
            _r = _mod_handler(camp, action, atype=atype, raw=raw)
        except Exception as e:  # a broken module must not brick the engine
            events.append(f"(the mechanism jams: {type(e).__name__})")
        else:
            if _r.get("handled"):
                save_campaign(camp)
                out = dict(_r)
                out.setdefault("ok", True)
                out.setdefault("campaign_id", campaign_id)
                return out

    if atype in ("look", "status"):
        noun = str(action.get("item") or action.get("target") or "").strip()
        if noun:
            events.append(_look_at(camp, noun))
        else:
            events.append(_narrate_room(camp))
    elif atype == "use":
        room = _room(camp)
        tags = [str(x).lower() for x in (room.get("tags") or [])]
        if "tavern" in tags or "hub" in tags:
            events.append(
                "The torch dips toward a sticky chair. Mira does not look up. "
                "'Hearth only. You want a fire, take the road north toward the keep.'"
            )
            camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + ["hearth_only"]))
        else:
            events.append("Nothing here takes the torch kindly.")
    elif atype == "take":
        noun = str(action.get("item") or "").strip().lower()
        room = _room(camp)
        blob = " ".join([
            str(room.get("name") or ""),
            str(room.get("desc") or ""),
            " ".join(str(h) for h in (room.get("hooks") or [])),
            " ".join(str(x) for x in (room.get("loot") or [])),
        ]).lower()
        loot = list(room.get("loot") or [])
        inv = list(pl.get("inventory") or [])
        # Evennia CmdGet: empty args → "Get what?" and return (no room dump).
        # Mag verb is take; bare take/get/grab/pick up must not invent a Look.
        if not noun:
            events.append("Take what?")
        elif any(noun in str(i).lower() for i in inv):
            events.append(f"Already carrying {noun}.")
        elif any(noun in str(x).lower() for x in loot) or (noun and noun in blob):
            item = next((x for x in loot if noun in str(x).lower()), noun.replace(" ", "_"))
            if item not in inv:
                inv.append(item)
                pl["inventory"] = inv
            events.append(f"You take the {noun}.")
            if any(w in noun for w in ("crate", "seal", "chest", "bounty")):
                events.extend(_work_events(camp, action))
            events.append("Carrying: " + ", ".join(inv) + ".")
        else:
            # Evennia caller.search no-match: short refuse then return (no Look dump).
            # Inform "You can't see any such thing" — one beat, not room.desc glued on.
            events.append(f"No {noun} here.")
    elif atype == "drop":
        # Evennia CmdDrop (general.py): empty → "Drop what?"; inventory miss →
        # nofound_string "You aren't carrying {args}." — short refuse, never Look/talk.
        noun = str(action.get("item") or "").strip().lower()
        inv = list(pl.get("inventory") or [])
        if not noun:
            events.append("Drop what?")
        else:
            # Prefer exact inventory name, then substring (same spirit as take).
            match = next((i for i in inv if str(i).lower() == noun), None)
            if match is None:
                match = next((i for i in inv if noun in str(i).lower()), None)
            if match is None:
                events.append(f"You aren't carrying {noun}.")
            else:
                pl["inventory"] = [i for i in inv if i != match]
                events.append(f"You drop the {match}.")
    elif atype == "give":
        # Evennia CmdGive (general.py): need inv obj + to/target.
        # empty/rhs miss → usage; inv miss → You aren't carrying X; no target → short refuse.
        # Never fall through to talk / return_appearance.
        noun = str(action.get("item") or "").strip().lower()
        whom = str(action.get("target") or "").strip()
        inv = list(pl.get("inventory") or [])
        if not noun or not whom:
            events.append("Give what to whom?")
        else:
            match = next((i for i in inv if str(i).lower() == noun), None)
            if match is None:
                match = next((i for i in inv if noun in str(i).lower()), None)
            if match is None:
                events.append(f"You aren't carrying {noun}.")
            else:
                people = people_in_room(camp)
                you = str(pl.get("name") or "").strip()
                target = _talk_target(whom, people, whom)
                in_room = any(
                    target.lower() == p.lower()
                    or whom.lower() == p.lower()
                    or whom.lower() in p.lower()
                    or p.lower() in whom.lower()
                    for p in people
                )
                if you and target and target.lower() == you.lower():
                    events.append(f"You keep the {match} to yourself.")
                elif not target or not in_room:
                    # Evennia caller.search miss on rhs — short refuse, no room dump.
                    events.append(f"No one here called {whom}.")
                else:
                    display = next(
                        (p for p in people if p.lower() == target.lower() or whom.lower() in p.lower() or p.lower() in whom.lower()),
                        target,
                    )
                    pl["inventory"] = [i for i in inv if i != match]
                    events.append(f"You give the {match} to {display}.")
    elif atype == "whisper":
        # Evennia CmdWhisper: empty lhs/rhs → Usage then return; search miss quiet;
        # success → at_say(whisper=True). Short refuse; never talk/room.desc dump.
        whom = str(action.get("target") or "").strip()
        # Evennia rhs only — never treat the command token / bare raw as speech.
        speech = str(action.get("message") or "").strip()
        if not whom or not speech:
            events.append("Usage: whisper <character> = <message>")
        else:
            people = people_in_room(camp)
            target = _talk_target(whom, people, whom)
            in_room = any(
                target.lower() == p.lower()
                or whom.lower() == p.lower()
                or whom.lower() in p.lower()
                or p.lower() in whom.lower()
                for p in people
            ) if people else False
            if not target or not in_room:
                events.append(f"No one here called {whom}.")
            else:
                display = next(
                    (
                        p
                        for p in people
                        if p.lower() == target.lower()
                        or whom.lower() in p.lower()
                        or p.lower() in whom.lower()
                    ),
                    target,
                )
                events.append(f'You whisper to {display}: "{speech[:180]}"')
    elif atype == "pose":
        # Evennia CmdPose (general.py): empty → "What do you want to do?"; else
        # f"{caller.name}{args}" with leading space unless args[0] in "',:".
        # Short refuse; never talk/room.desc dump.
        raw_pose = str(action.get("pose") if action.get("pose") is not None else action.get("message") or "")
        pose_text = raw_pose.strip()
        if not pose_text:
            events.append("What do you want to do?")
        else:
            name = str(pl.get("name") or "Adventurer").strip() or "Adventurer"
            if raw_pose[:1] in ("'", ",", ":"):
                args = raw_pose
            else:
                args = " " + pose_text
            events.append(f"{name}{args}"[:220])
    elif atype == "wait":
        # Inform Standard Rules / DM4 Wait: "Time passes." Short beat; never talk dump.
        events.append("Time passes.")
    elif atype == "wear":
        # Inform Wear: 1 can't wear / 2 not holding / 3 already wearing / 4 put on.
        # Mag has no wearable flag yet — short refuse; bare → Wear what?
        noun = str(action.get("item") or "").strip().lower()
        inv = list(pl.get("inventory") or [])
        if not noun:
            events.append("Wear what?")
        elif any(noun in str(i).lower() for i in inv):
            # carried but not wearable in Mag wardrobe yet
            events.append("You can't wear that!")
        else:
            events.append("You're not holding that!")
    elif atype == "remove":
        # Inform Disrobe: 1 not wearing / 2 take off. Mag: short refuse.
        noun = str(action.get("item") or "").strip().lower()
        if not noun:
            events.append("Remove what?")
        else:
            events.append("You're not wearing that!")
    elif atype == "read":
        # Inform DM4 Consult / §16 reading matter: bare needs noun;
        # default "You discover nothing of interest in <x1>."
        # Never dump room.desc / return_appearance; never talk belt.
        noun = str(action.get("item") or "").strip().lower()
        if not noun:
            events.append("Read what?")
        else:
            room = _room(camp)
            blob = " ".join([
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(str(h) for h in (room.get("hooks") or [])),
                " ".join(str(x) for x in (room.get("loot") or [])),
            ]).lower()
            inv = list(pl.get("inventory") or [])
            in_scope = (noun in blob) or any(noun in str(i).lower() for i in inv)
            if not in_scope:
                events.append(f"Nothing called {noun} here.")
            else:
                # Mag has no readable text attr yet — Consult default, one beat.
                events.append(f"You discover nothing of interest in the {noun}.")
    elif atype in ("unlock", "lock"):
        # Inform DM4 Unlock/Lock message 1: not something you can unlock/lock.
        # Bare → Unlock/Lock what?; Mag has no lockable flag yet — short refuse.
        # Never talk dump; never move (fixes lock-the-gate → north).
        noun = str(action.get("item") or "").strip().lower()
        locking = atype == "lock"
        if not noun:
            events.append("Lock what?" if locking else "Unlock what?")
        else:
            room = _room(camp)
            blob = " ".join([
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(str(h) for h in (room.get("hooks") or [])),
                " ".join(str(x) for x in (room.get("loot") or [])),
                " ".join(str(k) for k in (room.get("exits") or {})),
            ]).lower()
            in_scope = bool(noun and noun in blob) or any(
                noun in str(i).lower() for i in (pl.get("inventory") or [])
            )
            if not in_scope and noun not in ("door", "gate", "crate", "chest", "box", "seal", "lock"):
                events.append(f"Nothing called {noun} here.")
            else:
                if locking:
                    events.append("That doesn't seem to be something you can lock.")
                else:
                    events.append("That doesn't seem to be something you can unlock.")

    elif atype == "listen":
        # Inform WI §7.7 / Standard Rules: bare listen = listen to location.
        # Default report: "You hear nothing unexpected." Art of Noise room miss:
        # "Nothing of note." Short ambient beat from room hooks/people only —
        # never talk belt, never full room.desc / return_appearance.
        room = _room(camp)
        target = str(action.get("target") or action.get("item") or "").strip().lower()
        hooks = [str(h) for h in (room.get("hooks") or []) if str(h).strip()]
        blob = " ".join(
            [
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(hooks),
            ]
        ).lower()
        people = people_in_room(camp)
        if target:
            # listen to <noun>: match hook/person/named hearth; else Inform default.
            hit = ""
            if target in ("fire", "hearth", "flame", "calcifer") and _named_hearth(camp):
                hit = "The named fire argues with the damp. A soft pop, then quiet."
            elif any(target in str(p).lower() for p in people):
                whom = next(p for p in people if target in str(p).lower())
                hit = f"You catch a murmur near {whom}."
            else:
                for h in hooks:
                    if target and target in h.lower():
                        hit = f"You hear something near the {target}."
                        break
            events.append(hit or "You hear nothing unexpected.")
        else:
            # bare listen → location ambient, not Look.
            strokes = []
            if _named_hearth(camp) or any(w in blob for w in ("fire", "hearth", "flame")):
                strokes.append("The hearth ticks once against the damp.")
            if people:
                strokes.append("Soft voices braid at the edge of hearing.")
            elif any(w in blob for w in ("wind", "road", "woods", "keep", "stone", "gate")):
                strokes.append("Stone and air hold their own quiet.")
            if strokes:
                events.append(" ".join(strokes)[:220])
            else:
                events.append("You hear nothing unexpected.")
    elif atype in ("smell", "taste", "touch"):
        # Inform DM4 §A4 Smell / Taste / Touch — short sensory floors; never talk belt / room.desc.
        #  Smell: "You smell nothing unexpected."
        #  Taste: "You taste nothing unexpected."
        #  Touch1 animate: "Keep your hands to yourself!"; Touch2: "You feel nothing unexpected."
        room = _room(camp)
        target = str(action.get("target") or action.get("item") or "").strip().lower()
        hooks = [str(h) for h in (room.get("hooks") or []) if str(h).strip()]
        blob = " ".join(
            [
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(hooks),
            ]
        ).lower()
        people = people_in_room(camp)
        sense = atype
        if sense == "smell":
            default = "You smell nothing unexpected."
            if target:
                if target in ("fire", "hearth", "flame", "calcifer") and _named_hearth(camp):
                    events.append("Woodsmoke and named fire. A sharp sweet pop.")
                elif any(target in str(p).lower() for p in people):
                    events.append(default)
                elif any(target in h.lower() for h in hooks):
                    events.append(f"You catch a faint scent near the {target}.")
                else:
                    events.append(default)
            else:
                # Calcifer/hearth scent only on named lantern hearth — keep torch ≠ woodsmoke.
                if _named_hearth(camp) and any(w in blob for w in ("fire", "hearth", "flame", "calcifer")):
                    events.append("Woodsmoke hangs low. The hearth answers first.")
                else:
                    events.append(default)
        elif sense == "taste":
            events.append("You taste nothing unexpected.")
        else:  # touch
            if target and any(target in str(p).lower() for p in people):
                events.append("Keep your hands to yourself!")
            elif target in ("fire", "hearth", "flame", "calcifer") and _named_hearth(camp):
                events.append("Heat warns your fingers back. The named fire does not want a hand.")
            else:
                events.append("You feel nothing unexpected.")

    elif atype == "lmode":
        # Inform DM4 §A4 LMode1/2/3 — Mag has no look-mode organ yet; speak only + flag.
        # Never room.desc; never invent Calcifer on keep_gate.
        mode = str(action.get("mode") or "brief").strip().lower()
        if mode not in ("brief", "verbose", "superbrief"):
            mode = "brief"
        camp["look_mode"] = mode
        if mode == "verbose":
            events.append(
                "The game is now in its verbose mode, which always gives "
                "long descriptions of locations (even if you've been there before)."
            )
        elif mode == "superbrief":
            events.append(
                "The game is now in its superbrief mode, which always gives "
                "short descriptions of locations (even if you haven't been there before)."
            )
        else:
            events.append(
                "The game is now in its normal brief printing mode, which gives "
                "long descriptions of places never before visited and short descriptions otherwise."
            )
    elif atype == "objects":
        # Inform DM4 §A4 Objects1/2 — no handled-history organ; hang on inventory if present.
        inv = list(((camp.get("player") or {}).get("inventory") or []))
        if not inv:
            events.append("Objects you have handled: None.")
        else:
            lines = ["Objects you have handled:"]
            for item in inv[:16]:
                lines.append(f"  {item}")
            if len(inv) > 16:
                lines.append("(considering the first sixteen objects only)")
            events.append("\n".join(lines))
    elif atype == "places":
        # Inform DM4 §A4 Places — no visited organ yet; current room name only.
        room = _room(camp)
        rname = str((room or {}).get("name") or camp.get("room_id") or "").strip()
        if not rname:
            events.append("You have visited: nowhere interesting.")
        else:
            events.append(f"You have visited: {rname}.")

    elif atype == "pronouns":
        # Inform DM4 §A4 Pronouns1-4. Mag has no it/him/her/them antecedent organ yet.
        # Floor Pronouns4 only; never room.desc; never invent Calcifer on keep_gate.
        events.append("At the moment, no pronouns are known to the game.")
    elif atype == "notify":
        # Inform DM4 §A4 NotifyOn / NotifyOff. Hang score_notify flag; speak only.
        mode = str(action.get("mode") or "on").strip().lower()
        if mode == "off":
            camp["score_notify"] = False
            events.append("Score notification off.")
        else:
            camp["score_notify"] = True
            events.append("Score notification on.")
    elif atype == "verify":
        # Inform DM4 §A4 Verify1 — Mag has no gamefile CRC organ; always intact.
        events.append("The game file has verified as intact.")
    elif atype == "version":
        # Inform Version banner — Mag release line, not a room dump.
        events.append("Mag play-as-work table. The Verkle chain is the only save.")
    elif atype == "script":
        # Inform DM4 §A4 ScriptOn / ScriptOff. No Z-machine transcript stream —
        # hang camp["transcript"] flag; short floors only; never room.desc; never invent Calcifer.
        mode = str(action.get("mode") or "on").strip().lower()
        on = bool(camp.get("transcript"))
        if mode == "off":
            if not on:
                events.append("Transcripting is already off.")
            else:
                camp["transcript"] = False
                events.append("End of transcript.")
        else:
            if on:
                events.append("Transcripting is already on.")
            else:
                camp["transcript"] = True
                events.append("Start of a transcript of Mag play-as-work table.")
    elif atype == "recording":
        # Inform I6 CommandsOn/Off (PunyInform verblib). No Z-machine @output_stream 4 —
        # hang camp["recording"] flag; short floors only; never room.desc; never invent Calcifer.
        mode = str(action.get("mode") or "on").strip().lower()
        on = bool(camp.get("recording"))
        if mode == "off":
            camp["recording"] = False
            events.append("[Command recording off.]")
        else:
            camp["recording"] = True
            events.append("[Command recording on.]")
    elif atype == "replay":
        # Inform I6 CommandsRead. Mag has no @input_stream / command-file organ — soft floor only.
        # Never invent a replay file; never dump room.desc; never invent Calcifer on keep_gate.
        events.append("[Replaying commands.]")
    elif atype == "amusing":
        # Inform DM4 Amusing entry point / AMUSING_PROVIDED end-menu. Mid-story refuse.
        # Classic library stub: "You must finish the story first." Mag: no victory organ yet.
        # Never dump room.desc; never invent Calcifer on keep_gate; never open end-menu.
        events.append("You must finish the story first.")
    elif atype == "pushdir":

        # Inform DM4 §A4 PushDir1/2/3. Mag has no AllowPushDir organ — refuse only.
        # Never move the player; never dump room.desc; never invent Calcifer on keep_gate.
        code = int(action.get("code") or 1)
        if code == 2:
            events.append("That's not a direction.")
        elif code == 3:
            events.append("Not that way you can't.")
        else:
            events.append("Is that the best you can think of?")

    elif atype == "quit":
        # Inform DM4 §A4 Quit2. Soft confirm only — never kill /wave; never room.desc; never invent Calcifer.
        events.append("Are you sure you want to quit?")
    elif atype == "restart":
        # Inform DM4 §A4 Restart1. Soft confirm only — never wipe campaign; never invent Calcifer.
        events.append("Are you sure you want to restart?")
    elif atype == "restore":
        # Inform DM4 §A4 Restore1. Mag ironman / no restore organ — fail short.
        events.append("Restore failed.")
    elif atype == "save":
        # Inform DM4 §A4 Save2 "Ok." Mag: Verkle chain is the only save (no Z-machine file dialog).
        events.append("Ok. The Verkle chain is the only save.")
    elif atype == "undo":
        # Inform DM4 Miscellany 6. Mag ironman provides no undo organ.
        events.append("[Your interpreter does not provide undo. Sorry!]")
    elif atype == "oops":
        # Inform DM4 Miscellany 14/16. Mag has no oops-correction organ — short refuse only.
        mode = str(action.get("mode") or "bare").strip().lower()
        if mode == "multi":
            events.append('"Oops" can only correct a single word.')
        else:
            events.append("Sorry, that can't be corrected.")

    elif atype == "score":
        # Inform DM4 §A4 Score: "You have so far scored ‹score› out of a possible MAX_SCORE, in ‹turns› turn/turns"
        # Mag has no MAX_SCORE organ — floor 0/0. Prefer camp day / turns / storyteller fast_turns.
        # Short beat only; never room.desc; never invent Calcifer on keep_gate.
        st = camp.get("storyteller") if isinstance(camp.get("storyteller"), dict) else {}
        n = 0
        if camp.get("day") is not None:
            try:
                n = int(camp.get("day") or 0)
            except (TypeError, ValueError):
                n = 0
        elif camp.get("turns") is not None:
            try:
                n = int(camp.get("turns") or 0)
            except (TypeError, ValueError):
                n = 0
        else:
            try:
                n = int(st.get("fast_turns") or 0)
            except (TypeError, ValueError):
                n = 0
            if n <= 0:
                try:
                    n = int(st.get("days_since_crisis") or 0)
                except (TypeError, ValueError):
                    n = 0
        turn_word = "turn" if n == 1 else "turns"
        events.append(f"You have so far scored 0 out of a possible 0, in {n} {turn_word}.")
    elif atype in ("push", "pull", "turn"):
        # Inform DM4 §A4 Push / Pull / Turn — Mag has no scenery-push organ yet.
        #  Pull1 fixed-in-place unused (no scenery model); Pull2 unable; Pull3 nothing obvious; Pull4 courteous.
        #  Push and Turn use the same floors (DM4: Turn: see Pull). Bare → What do you want to …?
        target = str(action.get("target") or action.get("item") or "").strip().lower()
        if atype == "push":
            verb = "push"
        elif atype == "pull":
            verb = "pull"
        else:
            verb = "turn"
        if not target:
            events.append(f"What do you want to {verb}?")
        elif target in ("fire", "hearth", "flame", "calcifer", "torch") and _named_hearth(camp):
            # Named fire isn't furniture — Pull2 / Push2 / Turn2.
            events.append("You are unable to.")
        else:
            people = people_in_room(camp)
            person_keys = (
                "mira", "merchant", "goblin", "captive", "cartographer",
                "stranger", "barkeep", "bartender",
            )
            is_person = False
            for p in people:
                pl = str(p).lower()
                if pl in ("calcifer", "fire", "hearth", "flame", "torch"):
                    continue
                if target == pl or target in pl or pl in target:
                    is_person = True
                    break
            if not is_person:
                for k in person_keys:
                    if target == k or target.startswith(k + " ") or target.endswith(" " + k):
                        is_person = True
                        break
            if is_person:
                events.append("That would be less than courteous.")
            else:
                # Fixed-in-place / no push organ — Pull3 / Turn3 default.
                events.append("Nothing obvious happens.")

    elif atype == "knock":
        # Inform 7 Handbook knocking-on Report/Check. Mag: no door-open organ yet.
        # Bare → What do you want to knock on?
        # self → Your head makes a hollow sound.
        # person → That wouldn't be polite.
        # else → You tap gently on <noun>, but nothing happens.
        # Never dump room.desc; never invent Calcifer on keep_gate; never steal Attack.
        target = str(action.get("target") or "").strip().lower()
        if not target:
            events.append("What do you want to knock on?")
        elif target in ("me", "myself", "self", "my head", "head"):
            events.append("Your head makes a hollow sound.")
        else:
            people = people_in_room(camp)
            person_keys = (
                "mira", "merchant", "goblin", "captive", "cartographer",
                "stranger", "barkeep", "bartender",
            )
            is_person = False
            for p in people:
                pl = str(p).lower()
                if pl in ("calcifer", "fire", "hearth", "flame", "torch"):
                    continue
                if target == pl or target in pl or pl in target:
                    is_person = True
                    break
            if not is_person:
                for k in person_keys:
                    if target == k or target.startswith(k + " ") or target.endswith(" " + k):
                        is_person = True
                        break
            if is_person:
                events.append("That wouldn't be polite.")
            else:
                noun = target
                if not noun.startswith(("the ", "a ", "an ")):
                    noun = f"the {noun}"
                events.append(f"You tap gently on {noun}, but nothing happens.")

    elif atype == "jump":
        # Inform DM4 §A4 Jump / JumpOver. Short beat; never room.desc; never invent Calcifer.
        target = str(action.get("target") or "").strip()
        if action.get("over") and target:
            events.append("You would achieve nothing by this.")
        else:
            events.append("You jump on the spot, fruitlessly.")
    elif atype == "sing":
        # Inform DM4 §A4 Sing
        events.append("Your singing is abominable.")
    elif atype == "think":
        # Inform DM4 §A4 Think
        events.append("What a good idea.")
    elif atype == "kiss":
        # Inform DM4 §A4 Kiss — same floor with or without target; never talk dump.
        events.append("Keep your mind on the game.")
    elif atype == "swim":
        # Inform DM4 §A4 Swim ("swim"/"dive")
        events.append("There's not enough water to swim in.")
    elif atype == "dig":
        # Inform DM4 §A4 Dig
        events.append("Digging would achieve nothing here.")
    elif atype == "cut":
        # Inform DM4 §A4 Cut — bare or with target; never room.desc; never invent Calcifer.
        if not str(action.get("target") or "").strip():
            events.append("Cut what?")
        else:
            events.append("Cutting that up would achieve little.")
    elif atype == "wake":
        # Inform DM4 §A4 Wake / WakeOther
        events.append("The dreadful truth is, this is not a dream.")
    elif atype == "sleep":
        # Inform DM4 §A4 Sleep — soft floor for nap/doze/yawn ONLY.
        # Mag rest|heal|camp|sleep stays the rest organ (HP heal). Never dump room.desc;
        # never invent Calcifer on keep_gate; never steal rest.
        events.append("You aren't feeling especially drowsy.")
    elif atype == "swing":
        # Inform DM4 §A4 Swing — Grammar.h: Verb 'swing' * noun / * 'on' noun → Swing.
        # Floor: There's nothing sensible to swing here.
        # Mag attack organ keeps bare swing / swing at / combat synonyms.
        # Never dump room.desc; never invent Calcifer on keep_gate.
        events.append("There's nothing sensible to swing here.")
    elif atype == "burn":
        # Inform DM4 §A4 Burn + Miscellany 49.
        # Bare burn → incomplete prompt. Burn+noun → "This dangerous act would achieve little."
        # Mag use/fire keeps: set fire / on fire / light the / torch the / set the X on fire.
        # Never dump room.desc; never invent Calcifer on keep_gate; never steal use/light/torch.
        target = str(action.get("target") or "").strip()
        if target:
            events.append("This dangerous act would achieve little.")
        else:
            events.append("What do you want to burn?")
    elif atype == "pray":
        # Inform DM4 §A4 Pray
        events.append("Nothing practical results from your prayer.")
    elif atype == "rub":
        # Inform DM4 §A4 Rub — short floor; never talk dump; never room.desc.
        events.append("You achieve nothing by this.")
    elif atype == "squeeze":
        # Inform DM4 §A4 Squeeze — Squeeze2 default (inanimate); never talk dump.
        events.append("You achieve nothing by this.")
    elif atype == "wave":
        # Inform DM4 §A4 WaveHands / Wave. Bare wave = hands; with target = wave object.
        # Do not invent hold-check organ — short WaveHands/Wave floors only.
        target = str(action.get("target") or "").strip()
        if target:
            events.append(f"You look ridiculous waving {target}.")
        else:
            events.append("You wave, feeling foolish.")
    elif atype == "climb":
        # Inform DM4 §A4 Climb — miss verb floor; do not steal enter/gate→move.
        events.append("I don't think much is to be achieved by that.")
    elif atype == "extinguish":
        # Inform Extinguish / SwitchOff soft (put out / douse / blow out).
        # No lit-device organ yet — short refuse only.
        # Never dump room.desc; never invent Calcifer quench on keep_gate.
        target = str(action.get("target") or "").strip()
        if target:
            events.append("You can't extinguish that.")
        else:
            events.append("What do you want to extinguish?")
    elif atype == "blow":
        # Inform DM4 §A4 Blow — bare asks noun; with target short refuse. Never talk dump.
        if not str(action.get("target") or "").strip():
            events.append("Blow what?")
        else:
            events.append("You can't usefully blow that.")
    elif atype == "buy":
        # Inform DM4 §A4 Buy. "buy a drink" already drink earlier in parse.
        events.append("Nothing is on sale.")
    elif atype == "tie":
        # Inform DM4 §A4 Tie — bare or with target; never dump Look prose.
        if not str(action.get("target") or "").strip():
            events.append("Tie what?")
        else:
            events.append("You would achieve nothing by this.")
    elif atype == "untie":
        # Inform community Untie soft (no stock I7 Untie). Field block refuse.
        # Never dump room.desc; never invent rope-cut / Calcifer; never talk belt.
        if not str(action.get("target") or "").strip():
            events.append("What do you want to untie?")
        else:
            events.append("There's nothing to be achieved by that.")
    elif atype == "sorry":
        # Inform DM4 §A4 Sorry
        events.append("Oh, don't apologise.")
    elif atype == "look_under":
        # Inform DM4 §A4 LookUnder — miss under-look; never mistype as look(item=under…).
        events.append("You find nothing of interest.")
    elif atype == "yes":
        # Inform DM4 §A4 Yes — Soft Yes; rhetorical only; never talk dump.
        events.append("That was a rhetorical question.")
    elif atype == "no":
        # Inform DM4 §A4 No — same floor as Yes.
        events.append("That was a rhetorical question.")
    elif atype == "set":
        # Inform DM4 §A4 Set / SetTo — miss dial; never invent switch organ.
        target = str(action.get("target") or "").strip()
        if action.get("set_to"):
            events.append("No, you can't set that to anything.")
        elif not target:
            events.append("Set what?")
        else:
            events.append("No, you can't set that.")
    elif atype == "switch":
        # Inform DM4 §A4 SwitchOn/SwitchOff — miss switchables; short refuse.
        events.append("That's not something you can switch.")
    elif atype == "throw_at":
        # Inform DM4 §A4 ThrowAt — miss throw; do NOT steal attack/slay or "throw workers".
        target = str(action.get("target") or "").strip()
        if not target:
            events.append("Throw what?")
        else:
            events.append("Futile.")

    elif atype == "mild":
        events.append("Quite.")
    elif atype == "strong":
        events.append("Real adventurers do not use such language.")
    elif atype == "fill":
        events.append("But there's no water here to carry.")
    elif atype == "empty":
        target = str(action.get("target") or "").strip()
        if not target:
            events.append("Empty what?")
        else:
            events.append("That can't contain things.")
    elif atype == "pour":
        # Inform EmptyT cousin (stock Grammar.h has no Pour verb). Mag miss floors only.
        # Do NOT invent liquid/container organ; drink phrases stay drink organ.
        target = str(action.get("target") or "").strip()
        into = str(action.get("into") or "").strip()
        if not target and not into:
            events.append("What do you want to pour?")
        else:
            # DM4 EmptyT4 / EmptyT1 miss — no liquid organ yet
            events.append("That would scarcely empty anything.")
    elif atype == "show":
        item = str(action.get("item") or "").strip()
        target = str(action.get("target") or "").strip()
        if not item and not target:
            events.append("Show what?")
        elif item and not target:
            events.append("Show it to whom?")
        else:
            # miss holding organ: short Show2
            inv = [str(i).lower() for i in (pl.get("inventory") or [])]
            held = any(item.lower() in i or i in item.lower() for i in inv) if item else False
            if item and not held:
                events.append("You aren't holding that.")
            else:
                events.append("They are unimpressed.")

    elif atype == "search":
        # Inform DM4 §A4 Search 2/4/5/6. Mag has no container organ yet — short floors,
        # never _narrate_room. Container open/closed reads the same crate_open flag
        # the open/close organ already writes; no new state.
        noun = str(action.get("target") or action.get("item") or "").strip().lower()
        if not noun:
            events.append("Search what?")
        else:
            room = _room(camp)
            blob = " ".join([
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(str(h) for h in (room.get("hooks") or [])),
                " ".join(str(x) for x in (room.get("loot") or [])),
                " ".join(str(k) for k in (room.get("exits") or {})),
            ]).lower()
            in_inv = any(noun in str(i).lower() for i in (pl.get("inventory") or []))
            in_room = bool(noun and noun in blob) or in_inv
            containers = ("crate", "chest", "seal", "box", "sack", "pack", "barrel")
            supporters = ("table", "bar", "counter", "shelf", "bench", "slab")
            is_container = any(w in noun or noun in w for w in containers) and (
                in_room or any(w in blob for w in containers)
            )
            is_supporter = any(w in noun or noun in w for w in supporters) and in_room
            flags = list(camp.get("flags") or [])
            opened = any(
                str(f) == "crate_open"
                or str(f).startswith(("temple:", "shared:", "door_open:"))
                for f in flags
            )
            if not in_room and not is_container:
                events.append(f"Nothing called {noun} here.")
            elif is_container and not opened:
                events.append(f"You can't see inside, since the {noun} is closed.")
            elif is_container:
                events.append(f"The {noun} is empty.")
            elif is_supporter:
                events.append(f"There is nothing on the {noun}.")
            else:
                events.append("You find nothing of interest.")
    elif atype == "vague_go":
        # Inform DM4 §A4 VagueGo. The exits themselves stay the move organ's job.
        events.append("You'll have to say which compass direction to go in.")
    elif atype == "answer":
        # Inform DM4 §A4 Answer. A named person still routes to the talk organ upstream.
        events.append("There is no reply.")
    elif atype == "follow":
        # Inform follow.inf FollowSub soft: bare → whom; noun present → "No need!".
        # No follow_direction / MoveNPC organ yet. Never talk belt; never room.desc.
        target = str(action.get("target") or "").strip()
        mode = str(action.get("mode") or "").strip().lower()
        if mode == "whom" or not target:
            events.append("Whom do you want to follow?")
        else:
            events.append("No need!")
    elif atype == "ask":
        # Inform Miscellany 48 incomplete Ask (creature token missing).
        # Named-person Ask stays talk organ upstream. Never room.desc; never invent Calcifer.
        events.append("Whom do you want to ask?")
    elif atype == "tell":
        # Inform DM4 §A4 Tell1/Tell2. Named-person Tell stays talk organ upstream.
        target = str(action.get("target") or "").strip()
        if not target:
            events.append("You talk to yourself a while.")
        else:
            events.append("This provokes no reaction.")
    elif atype == "order":
        # Inform DM4 §A4 Order. Drink "order a …" never reaches here.
        target = str(action.get("target") or "").strip()
        if not target:
            events.append("Order whom?")
        else:
            name = target.split()[0].capitalize()
            events.append(f"{name} has better things to do.")
    elif atype == "exit":
        # Inform DM4 §A4 Exit1 / GetOff — Mag has no enter-furniture organ yet.
        ex_tgt = str(action.get("target") or "").strip().lower()
        if ex_tgt:
            events.append(f"But you aren't on the {ex_tgt} at the moment.")
        else:
            events.append("But you aren't in anything at the moment.")
    elif atype == "eat":
        # Inform DM4 §A4 Eat1 — no edible organ yet; never room.desc.
        item = str(action.get("item") or "").strip()
        if not item:
            events.append("Eat what?")
        else:
            events.append("That's plainly inedible.")
    elif atype == "enter":
        # Inform DM4 §A4 Enter2/3 — no furniture organ yet; never _narrate_room.
        noun = str(action.get("target") or action.get("item") or "").strip().lower()
        if not noun:
            events.append("Enter what?")
        else:
            room = _room(camp)
            blob = " ".join([
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(str(h) for h in (room.get("hooks") or [])),
                " ".join(str(x) for x in (room.get("loot") or [])),
            ]).lower()
            flags = list(camp.get("flags") or [])
            opened = any(
                str(f) == "crate_open"
                or str(f).startswith(("temple:", "shared:", "door_open:"))
                for f in flags
            )
            containers = ("crate", "chest", "seal", "box", "sack", "barrel")
            is_container = any(w in noun or noun in w for w in containers)
            if is_container and not opened:
                events.append(f"You can't get into the closed {noun}.")
            else:
                events.append("That's not something you can enter.")
    elif atype == "sit":
        # Inform Sit is Enter. Mag: no furniture organ — short refuse, never room.desc.
        noun = str(action.get("target") or "").strip().lower()
        mode = str(action.get("mode") or "").strip().lower()
        if not noun:
            events.append("Lie on what?" if mode == "lie" else "Sit on what?")
        else:
            events.append("That's not something you can sit on.")
    elif atype == "stand":
        # Inform: already standing when not on a supporter.
        events.append("You are already standing.")

    elif atype == "home":
        # Evennia CmdHome (general.py): key=home; locks perm(home)|Builder; arg_regex r"$".
        # no home → "You have no home!"; already there → "You are already home!";
        # else → "There's no place like home ..." + move_to(..., move_type="teleport").
        # Mag home = lantern/tavern hub (no caller.home attr). Short refuse; never talk dump.
        rooms = (camp.get("module_snapshot") or {}).get("rooms") or {}
        home_id = None
        for rid, room in rooms.items():
            rid_l = str(rid).lower()
            tags = [str(x).lower() for x in ((room or {}).get("tags") or [])]
            rname = str((room or {}).get("name") or "").lower()
            area = str((room or {}).get("area_tag") or "").lower()
            if (
                "lantern" in rid_l
                or "tavern" in rid_l
                or "tavern" in tags
                or "hub" in tags
                or area == "hub"
                or ("mira" in rname and any(w in rname for w in ("hearth", "tavern", "lantern", "inn")))
            ):
                home_id = rid
                break
        if home_id is None:
            start = (
                camp.get("start_room")
                or (camp.get("module_snapshot") or {}).get("start_room")
            )
            if start and str(start) in rooms:
                home_id = start
            elif start:
                home_id = start
        if not home_id:
            events.append("You have no home!")
        elif str(camp.get("room_id") or "") == str(home_id):
            events.append("You are already home!")
        else:
            camp["room_id"] = home_id
            camp["encounter"] = None
            room = _room(camp)
            for fl in room.get("flags_on_enter") or []:
                camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + [fl]))
            events.append("There's no place like home ...")
            name = str(room.get("name") or "home")
            hook = str((room.get("hooks") or [""])[0] or "")
            land = f"You are home: {name}."
            if hook:
                land = land + " " + hook
            events.append(land[:220])
    elif atype in ("open", "close"):
        # Evennia CmdOpenCloseDoor: empty → usage return; not-door short refuse;
        # already open/closed; You open/close X. Inform: "That's not something you can open."
        # Never fall through to talk / return_appearance.
        noun = str(action.get("item") or "").strip().lower()
        closing = atype == "close"
        if not noun:
            events.append("Close what?" if closing else "Open what?")
        else:
            room = _room(camp)
            blob = " ".join([
                str(room.get("name") or ""),
                str(room.get("desc") or ""),
                " ".join(str(h) for h in (room.get("hooks") or [])),
                " ".join(str(x) for x in (room.get("loot") or [])),
                " ".join(str(k) for k in (room.get("exits") or {})),
            ]).lower()
            people = people_in_room(camp)
            in_people = any(
                noun == p.lower() or noun in p.lower() or p.lower() in noun
                for p in people
            )
            in_inv = any(noun in str(i).lower() for i in (pl.get("inventory") or []))
            in_room = bool(noun and noun in blob) or in_inv
            containers = ("crate", "chest", "seal", "box")
            doors = ("door", "gate", "doorway", "hatch")
            is_container = any(w in noun or noun in w for w in containers) and (
                in_room or any(w in blob for w in containers)
            )
            is_door = any(w in noun or noun in w for w in doors) and (
                in_room or any(w in blob for w in doors) or bool(room.get("exits"))
            )
            flags = list(camp.get("flags") or [])
            opened = any(
                str(f).startswith("temple:")
                or str(f).startswith("shared:")
                or str(f).startswith("slain:")
                or str(f).startswith("crate_open")
                or str(f).startswith("door_open:")
                for f in flags
            )
            if in_people and not is_container and not is_door:
                events.append("This is not a door.")
            elif not in_room and not is_container and not is_door:
                events.append(f"Nothing called {noun} here.")
            elif not is_container and not is_door:
                events.append("That's not something you can open." if not closing else "That's not something you can close.")
            elif is_container:
                label = next((w for w in containers if w in noun or noun in w), "crate")
                if closing:
                    if "crate_open" in flags:
                        camp["flags"] = [f for f in flags if f != "crate_open"]
                        events.append(f"You close the {label}.")
                    else:
                        events.append(f"The {label} is already closed.")
                else:
                    if opened or "crate_open" in flags:
                        events.append(f"The {label} is already open.")
                    else:
                        events.append(f"You open the {label}.")
                        camp["flags"] = list(dict.fromkeys(flags + ["crate_open"]))
                        events.extend(_work_events(camp, action))
            else:
                rid = str(camp.get("room_id") or "here")
                flag = f"door_open:{rid}"
                label = next((w for w in doors if w in noun or noun in w), "door")
                if closing:
                    if flag in flags:
                        camp["flags"] = [f for f in flags if f != flag]
                        events.append(f"You close the {label}.")
                    else:
                        events.append(f"The {label} is already closed.")
                else:
                    if flag in flags:
                        events.append(f"The {label} is already open.")
                    else:
                        camp["flags"] = list(dict.fromkeys(flags + [flag]))
                        events.append(f"You open the {label}.")
    elif atype == "talk":
        # Address the named person. Their hook is the line. HP lives on the bar.
        events.extend(_talk_events(camp, pl, action))
    elif atype == "rumor":
        tables = (camp.get("module_snapshot") or {}).get("event_tables") or {}
        rows = list(tables.get("tavern_rumor") or [])
        if not rows:
            events.append("No one is talking. The fire pops once, unhelpfully.")
        else:
            row = _pick_weighted(rows) or {}
            events.append(str(row.get("text") or "A rumor dissolves before it lands."))
            if row.get("flag"):
                camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + [str(row["flag"])]))
    elif atype == "drink":
        tables = (camp.get("module_snapshot") or {}).get("event_tables") or {}
        rows = list(tables.get("tavern_drink") or [])
        row = _pick_weighted(rows) if rows else {}
        events.append(str((row or {}).get("text") or "You drink. It is a liquid."))
        # tiny heal in hub
        pl["hp"] = min(int(pl.get("hp_max") or 10), int(pl.get("hp") or 0) + 1)
        events.append(f"HP {pl['hp']}/{pl.get('hp_max')}.")
    elif atype == "seek_fight":
        tables = (camp.get("module_snapshot") or {}).get("event_tables") or {}
        room = _room(camp)
        tag = str(room.get("area_tag") or "road")
        key = "random_woods" if tag == "woods" else "random_road"
        if tag == "hub":
            events.append(
                "The barkeep clears their throat: 'Not in the Lantern.' "
                "Take the road if you want a fair fight."
            )
        else:
            rows = list(tables.get(key) or tables.get("random_road") or [])
            row = _pick_weighted(rows) if rows else {}
            events.append(str((row or {}).get("text") or "Nothing answers your bloodlust."))
            enc = (row or {}).get("encounter")
            if enc:
                camp["encounter"] = dict(enc)
    elif atype == "examine":
        # examine (no target) -> the command/verb reference; examine <object> -> study it
        noun = str(action.get("item") or action.get("target") or "").strip()
        if noun:
            events.append(_look_at(camp, noun))
            events.append(_verbs_for_object(camp, noun))
        else:
            events.append(_examine_verbs(camp))
    elif atype == "try" or (raw and re.match(r"^(try|attempt)", raw, re.I)):
        events.append(_try_action(camp, pl, action, raw=raw))
    elif atype == "freeze":
        try:
            from mag.game_freeze import freeze_campaign

            fr = freeze_campaign(str(campaign_id))
            if fr.get("ok"):
                events.append(fr.get("speak") or f"Frozen `{fr.get('freeze_id')}`.")
            else:
                events.append(str(fr.get("error") or "freeze failed"))
        except Exception as exc:
            events.append(f"Freeze failed: {exc}"[:200])
    elif atype == "help":
        tips = ", ".join(
            a.get("type", "")
            + (f" {a['direction']}" if a.get("direction") else "")
            for a in legal[:10]
        )
        # Socratic: try freeze L0/L1 help if available
        try:
            from mag.game_freeze import freeze_campaign, format_socratic_help, load_freeze

            st = camp.get("storyteller") or {}
            fid = st.get("freeze_id")
            frz = load_freeze(str(fid)) if fid else None
            if not frz:
                fr = freeze_campaign(str(campaign_id))
                frz = fr.get("freeze") if fr.get("ok") else None
            if frz:
                events.append(format_socratic_help(frz))
            else:
                events.append(f"You can: {tips}. Or say inventory, rest, freeze state.")
        except Exception:
            events.append(f"You can: {tips}. Or say inventory, rest, freeze state.")
    elif atype == "inventory":
        inv = pl.get("inventory") or []
        events.append(
            f"{pl.get('name') or 'You'} carries: {', '.join(inv) if inv else 'nothing much'}."
        )
        events.append(f"HP {pl.get('hp')}/{pl.get('hp_max')}.")
    elif atype == "move":
        direction = str(action.get("direction") or "").lower()
        exits = _room(camp).get("exits") or {}
        if direction not in exits:
            # fuzzy
            for k in exits:
                if k.startswith(direction) or direction in k:
                    direction = k
                    break
        if direction not in exits:
            # Evennia CmdExitError (Howto-Default-Exit-Errors): "You cannot move {key}."
            # Short refuse as narrate/events — never ok:False empty speak → room floor dump.
            d = (direction or "that way").strip() or "that way"
            events.append(f"You cannot move {d}.")
        else:
            if camp.get("encounter") and int((camp["encounter"] or {}).get("hp") or 0) > 0:
                dmg = roll_dice("1d4")
                pl["hp"] = max(0, int(pl.get("hp") or 0) - int(dmg["total"]))
                events.append(f"Leaving under fire — take {dmg['total']}! HP {pl['hp']}.")
                if pl["hp"] <= 0:
                    camp["status"] = "defeated"
                    camp["player"] = pl
                    events.append("You fall. Say start classic for a new run.")
                    save_campaign(camp)
                    return {"ok": True, "events": events, "narrate": " ".join(events), "status": "defeated"}
            camp["room_id"] = exits[direction]
            camp["encounter"] = None
            room = _room(camp)
            for fl in room.get("flags_on_enter") or []:
                camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + [fl]))
            enc = room.get("encounter")
            if enc:
                camp["encounter"] = dict(enc)
                events.append(f"You enter {room.get('name')}. {enc.get('name')}!")
            else:
                # game_entry.walk shape (stone 2), geography from the module not BUILDINGS.
                hook = str((room.get("hooks") or [""])[0] or "")
                name = str(room.get("name") or "somewhere")
                low_n = name.lower()
                if any(w in low_n for w in ("cave", "hall", "fork", "cellar", "tunnel", "pit", "road")):
                    line = "You walk " + direction + " into " + name + "."
                else:
                    line = "You walk " + direction + " and a building appears: " + name + "."
                if hook:
                    line = line + " " + hook
                events.append(line)
            # loot
            for item in room.get("loot") or []:
                inv = list(pl.get("inventory") or [])
                if item not in inv:
                    inv.append(item)
                    pl["inventory"] = inv
                    events.append(f"You pick up {item}.")
            events.append(_narrate_room(camp))
    elif atype == "attack":
        enc = camp.get("encounter")
        if not enc or int(enc.get("hp") or 0) <= 0:
            return {"ok": False, "error": "nothing to attack", "legal": legal}
        traits = [str(t).lower() for t in (pl.get("traits") or [])]
        bonus = int(pl.get("attack_bonus") or 0)
        if "hotheaded" in traits:
            bonus += 1
        if "craven" in traits:
            events.append("Fear nags — you strike anyway.")
        hit = roll_dice(f"1d20+{bonus}")
        ac = int(enc.get("ac") or 10)
        if hit["total"] >= ac:
            dmg = roll_dice(str(pl.get("damage") or "1d6"))
            enc["hp"] = max(0, int(enc.get("hp") or 0) - int(dmg["total"]))
            events.append(
                f"Hit ({hit['total']} vs AC {ac}) for {dmg['total']}. "
                f"{enc.get('name')} HP {enc['hp']}/{enc.get('hp_max')}."
            )
            if enc["hp"] <= 0:
                events.append(f"{enc.get('name')} drops!")
                droom = str(enc.get("dungeon_room") or "")
                if droom:
                    try:
                        from mag import dungeon_dev
                        dungeon_dev.conquer(droom, knot=f"slain:{enc.get('name')}", publish=True)
                        events.append(
                            "The ward folds. The temple keeps that room for everyone, not a throne."
                        )
                    except Exception:
                        events.append("The beast is down. The knot did not fold. File it again.")
                for fl in _room(camp).get("flags_on_clear") or []:
                    camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + [fl]))
                camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + ([f"slain:{droom}"] if droom else [])))
                camp["encounter"] = None
                if "greedy" in traits and "freed_merchant_opportunity" in (camp.get("flags") or []):
                    events.append("The captive merchant eyes your purse already…")
        else:
            events.append(f"Miss ({hit['total']} vs AC {ac}).")
        enc = camp.get("encounter")
        if enc and int(enc.get("hp") or 0) > 0:
            fhit = roll_dice(f"1d20+{int(enc.get('attack_bonus') or 0)}")
            if fhit["total"] >= int(pl.get("ac") or 10):
                fdmg = roll_dice(str(enc.get("damage") or "1d6"))
                pl["hp"] = max(0, int(pl.get("hp") or 0) - int(fdmg["total"]))
                events.append(f"{enc.get('name')} hits for {fdmg['total']}! HP {pl['hp']}.")
                if pl["hp"] <= 0:
                    camp["status"] = "defeated"
                    events.append("You fall.")
            else:
                events.append(f"{enc.get('name')} misses.")
    elif atype == "flee":
        exits = list((_room(camp).get("exits") or {}).keys())
        if not exits:
            return {"ok": False, "error": "nowhere to flee"}
        return apply_action(campaign_id, {"type": "move", "direction": exits[0]})
    elif atype == "rest":
        if camp.get("encounter") and int((camp["encounter"] or {}).get("hp") or 0) > 0:
            return {"ok": False, "error": "can't rest in combat", "legal": legal}
        pl["hp"] = int(pl.get("hp_max") or 10)
        events.append(f"You rest. HP {pl['hp']}.")
        events.extend(_fire_rest_events(camp))
    elif atype == "act":
        events.extend(_act_events(camp, action))
    elif atype in ("work", "share", "file"):
        events.extend(_work_events(camp, action))
    elif atype == "put":
        # Inform DM4 §A4 Insert (1–9) / PutOn (1–8). Mag has no container organ yet —
        # short refuse floors only; never talk belt / room.desc dump.
        #  Insert1: need holding before put into
        #  Insert2: can't contain things
        #  Insert5: can't put inside itself
        #  PutOn1: need holding before put on top
        #  PutOn3: putting on X would achieve nothing
        noun = str(action.get("item") or "").strip().lower()
        target = str(action.get("target") or "").strip().lower()
        mode = str(action.get("mode") or "into").strip().lower()
        if mode not in ("into", "onto"):
            mode = "into"
        inv = list(pl.get("inventory") or [])
        if not noun:
            events.append("Put what?")
        elif not target:
            events.append(
                "What do you want to put that in?"
                if mode == "into"
                else "What do you want to put that on?"
            )
        elif noun == target or noun in target or target in noun:
            events.append("You can't put something inside itself.")
        else:
            match = next((i for i in inv if str(i).lower() == noun), None)
            if match is None:
                match = next((i for i in inv if noun in str(i).lower()), None)
            if match is None:
                if mode == "onto":
                    events.append(
                        f"You need to be holding {noun} before you can put it on top of something else."
                    )
                else:
                    events.append(
                        f"You need to be holding {noun} before you can put it into something else."
                    )
            else:
                # No Mag container/supporter model yet — Inform Insert2 / PutOn3.
                if mode == "onto":
                    events.append(f"Putting things on {target} would achieve nothing.")
                else:
                    events.append("That can't contain things.")
    elif atype == "again":
        # Inform DM4 Miscellany 20/21 — never talk dump.
        # 21: no prior command → "You can hardly repeat that."
        # 20: misuse (NPC, again / again <junk>) → short coach, not re-dispatch.
        if action.get("misuse"):
            events.append(
                'To repeat a command like "look", just say "again", not "look, again".'
            )
        else:
            last = camp.get("last_speech")
            if not isinstance(last, dict) or not str(last.get("type") or "").strip():
                events.append("You can hardly repeat that.")
            else:
                # Re-dispatch prior speech action (flee-style recursion). Do not nest again.
                replay = dict(last)
                replay.pop("raw", None)
                if str(replay.get("type") or "").lower() == "again":
                    events.append("You can hardly repeat that.")
                else:
                    return apply_action(campaign_id, replay)
    else:
        return {"ok": False, "error": f"illegal action {atype}", "legal": legal}

    camp["player"] = pl
    # Inform AGAIN buffer: remember last speech action (not again itself).
    if atype and atype != "again":
        remembered = {"type": atype}
        for k in ("item", "target", "direction", "pose", "message", "verb", "mode"):
            if action.get(k) is not None and str(action.get(k)).strip() != "":
                remembered[k] = action.get(k)
        camp["last_speech"] = remembered
    color = _craft_narrate(camp, events)
    # color lives on storyteller for the passage, not in the spoken beat
    camp["log"] = list(camp.get("log") or []) + [
        {"ts": _utc(), "type": atype, "text": e} for e in events
    ]
    save_campaign(camp)

    # session stats for DM dogfood / Fast-Slow metrics
    st = dict(camp.get("storyteller") or {})
    st["turn_n"] = int(st.get("turn_n") or 0) + 1
    st["fast_turns"] = int(st.get("fast_turns") or 0) + 1  # engine apply = fast path
    if color:
        st["color"] = color
        st["slow_turns"] = int(st.get("slow_turns") or 0) + 1
        st["ds_called"] = False
        st["craft"] = True
    st["saga"] = story_so_far({**camp, "storyteller": st})
    camp["storyteller"] = st
    save_campaign(camp)

    # Foundation: play is a world change. Castle (table) proposes; world core commits.
    try:
        from mag import game_world, game_world_render
        rid = str(camp.get("room_id") or "")
        pln = str((pl.get("name") or "adventurer")).lower().replace(" ", "-") or "adventurer"
        game_world.set_state(
            "table.campaign",
            {
                "campaign_id": campaign_id,
                "room_id": rid,
                "status": camp.get("status"),
                "turn": st.get("turn_n"),
                "action": atype,
            },
            source="table",
        )
        room = _room(camp)
        game_world.set_state(
            f"table.room.{rid or 'void'}",
            {
                "name": room.get("name"),
                "desc": (room.get("desc") or "")[:240],
                "hooks": list(room.get("hooks") or [])[:6],
            },
            source="table",
        )
        if atype == "move":
            game_world_render.walk(
                player=pln,
                direction=str(action.get("direction") or "forward"),
                region="guttered-lantern",
            )
    except Exception:
        pass

    try:
        from mag.chasm_state import persist as _chasm_persist
        _chasm_persist(camp, events=events, action=atype)
    except Exception:
        pass

    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={
                "campaign_id": campaign_id,
                "module_id": str(camp.get("module_id") or ""),
                "world_family": "tabletop-dnd",
                "voice_session_id": str(camp.get("voice_session_id") or ""),
            },
            input_data={"action": atype, "direction": action.get("direction") or ""},
            action={
                "room": camp.get("room_id"),
                "fast_path": True,
                "ds_called": False,
            },
            outcome={
                "status": camp.get("status"),
                "events_n": len(events),
                "turn_n": st.get("turn_n"),
                "has_encounter": bool(
                    camp.get("encounter") and int((camp.get("encounter") or {}).get("hp") or 0) > 0
                ),
            },
            pattern_tags=["game", "tabletop-dnd", atype, "fast_path", "dogfood_dm"],
            tier_max="T2",
            exportable=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "campaign_id": campaign_id,
        "events": events,
        "narrate": " ".join(events).strip(),
        "legal": list_legal_actions(camp),
        "scene_context": scene_context(camp),
        "status": camp.get("status"),
        "player": camp.get("player"),
        "fast_path": True,
        "ds_called": False,
        "metrics": {
            "turn_n": st.get("turn_n"),
            "fast_turns": st.get("fast_turns"),
            "slow_turns": st.get("slow_turns") or 0,
        },
    }



# dungeon_dev rooms wearing MUD armor. Play slays them. Conquer folds the knot.
_TEMPLE_BEASTS = {
    "emulator-core": {
        "name": "Temple Guardian",
        "kind": "construct",
        "want": "the engine room stays sealed",
        "ac": 14,
        "attack_bonus": 3,
        "damage": "1d6",
    },
    "rib-as-mod": {
        "name": "Puzzle-Box Ward",
        "kind": "puzzle",
        "want": "the lid stays shut",
        "ac": 12,
        "attack_bonus": 2,
        "damage": "1d4",
    },
    "warm-prefix": {
        "name": "Troll Army",
        "kind": "horde",
        "want": "to eat the treasury and the warming",
        "ac": 11,
        "attack_bonus": 2,
        "damage": "1d6",
    },
    "vram-lattice": {
        "name": "Necromancer",
        "kind": "undead",
        "want": "the memlands as a private grave",
        "ac": 13,
        "attack_bonus": 4,
        "damage": "1d8",
    },
    "arrival-compiler": {
        "name": "Lich of Arrival",
        "kind": "undead",
        "want": "to write its own RIB and never die",
        "ac": 15,
        "attack_bonus": 4,
        "damage": "1d8",
    },
    "hologram-visor": {
        "name": "Dragon of the Eye",
        "kind": "dragon",
        "want": "the hologram as a hoard, not a well",
        "ac": 16,
        "attack_bonus": 5,
        "damage": "1d10",
    },
}


def _beast_for_room(room_id: str, hp: int = 3) -> dict[str, Any]:
    spec = dict(_TEMPLE_BEASTS.get(str(room_id) or "") or {
        "name": "Temple Warden",
        "kind": "ward",
        "want": "the inner door stays shut",
        "ac": 12,
        "attack_bonus": 2,
        "damage": "1d6",
    })
    h = max(1, int(hp or 3))
    spec.update({
        "hp": h,
        "hp_max": h,
        "dungeon_room": str(room_id or ""),
        "temple": True,
    })
    return spec


def _work_events(camp: dict[str, Any], action: dict[str, Any] | None = None) -> list[str]:
    """Puzzle box / temple. Opening a ward spawns a beast. Share throws one worker. Slay conquers."""
    events: list[str] = []
    try:
        from mag import dungeon_dev
        st = dungeon_dev.dungeon_state() or {}
        ip = list(st.get("in_progress") or [])
        room = ip[0] if ip else None
        spec = next((r for r in dungeon_dev.ROOMS if r.get("room") == room), None) if room else None
        if not room:
            gen = dungeon_dev.generate_room() or {}
            room = gen.get("room")
            if not room:
                events.append("The temple is mapped. The puzzle box is empty. Share what you already carry.")
                return events
            spec = next((r for r in dungeon_dev.ROOMS if r.get("room") == room), None)
        hp = int((spec or {}).get("hp") or 3)
        beast = _beast_for_room(str(room), hp=hp)
        enc = camp.get("encounter")
        live = isinstance(enc, dict) and int(enc.get("hp") or 0) > 0
        if live and not enc.get("temple"):
            events.append(
                f"{enc.get('name')} still holds the floor. The puzzle box can wait."
            )
            return events
        if not live:
            camp["encounter"] = beast
            events.append(
                f"The crate is a puzzle box. The keep is a temple. "
                f"A ward opens: the {beast['name']} wants {beast.get('want')}."
            )
        else:
            events.append(f"The {enc.get('name')} is still the ward. Hit it. Share it. Slay it.")
            beast = dict(enc)
            room = str(enc.get("dungeon_room") or room)
        asg = dungeon_dev.assign_workers(str(room), n=1, enqueue=True) or {}
        if asg.get("ok"):
            events.append(
                "A worker takes the blow with you. If the beast drops, the knot is for everyone."
            )
        else:
            events.append("The temple filed the blow. The swarm did not pick up the sword.")
        camp["flags"] = list(dict.fromkeys(list(camp.get("flags") or []) + [f"temple:{room}"]))
        try:
            from mag.party_subchain import append as _ps
            _ps(seat="table", ok=True, move=f"slay {beast.get('name')} / {room}", kind="play_as_work")
        except Exception:
            try:
                from mag.steer import emit as _steer
                _steer("play-as-work", "table", f"slay {room}", steer_back=False)
            except Exception:
                pass
    except Exception as e:
        events.append("The puzzle box jams. " + str(e)[:140])
    return events


def parse_player_speech(text: str) -> dict[str, Any] | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    # single-letter exits (voice-friendly)
    if t in ("n", "north"):
        return {"type": "move", "direction": "north"}
    if t in ("s", "south"):
        return {"type": "move", "direction": "south"}
    if t in ("e", "east"):
        return {"type": "move", "direction": "east"}
    if t in ("w", "west"):
        return {"type": "move", "direction": "west"}
    if t in ("u", "up"):
        return {"type": "move", "direction": "up"}
    if t in ("d", "down"):
        return {"type": "move", "direction": "down"}
    if re.search(r"\b(share|bounty|file work|file the take|throw workers|assign workers|open the (box|temple|ward))\b", t) or t in ("share", "work", "file", "bounty"):
        return {"type": "work", "raw": (text or "").strip()[:240]}
    if re.search(r"\b(slay|kill|fight|stab|hit)\b", t) or t in ("attack", "strike"):
        return {"type": "attack"}
    if re.search(r"\b(freeze state|freeze game|game freeze|dump state|save freeze)\b", t):
        return {"type": "freeze"}
    # Water-computer physics verbs (dead-seam burn-down 2026-09-27): bare
    # boil/steam/melt and freeze-the-WATER phrases parsed to None, the test
    # harness fell back to a harmless look, and the module never saw the
    # verb ("freeze state" above is the engine save, not the element). The
    # type carries the verb; the module's handle() blob-match does the rest.
    if re.fullmatch(r"(boil|steam|melt)", t):
        return {"type": "boil", "raw": (text or "").strip()[:240]}
    if re.fullmatch(r"(freeze|ice|cool( down)?)", t) or re.search(r"\bfreeze (the )?(water|it)\b", t):
        return {"type": "freeze_water", "raw": (text or "").strip()[:240]}
    if re.search(r"\b(help|what can i do|options|commands|legal)\b", t):
        return {"type": "help"}
    # Evennia CmdInventory (general.py): key=inventory aliases=["inv","i"] arg_regex=r"$".
    # Bare "i" was None → table_turn long-IC talk belt. Exact token only (no extra args).
    if t == "i" or re.search(r"\b(inventory|inv|what do i (have|carry)|gear|pack)\b", t):
        return {"type": "inventory"}
    if re.search(
        r"\b(rumor|rumours|rumors|gossip|news|what('s| is) the (word|news)|ask (the )?barkeep)\b",
        t,
    ):
        return {"type": "rumor"}
    if re.search(r"\b(drink|ale|beer|broth|buy a drink|order a)\b", t):
        return {"type": "drink"}
    if re.search(
        r"\b(leave (the )?(tavern|inn|bar)|go (outside|out)|hit the road|leave for the road)\b",
        t,
    ):
        return {"type": "move", "direction": "out"}
    # Inform DM4 Miscellany 20/21 / parser AGAIN (g):
    # Bare again|g with no prior command → "You can hardly repeat that."
    # Misuse like "look, again" / trailing junk → Miscellany 20 short refuse.
    # Never fall through to talk belt. Do not eat gather/gaining/go/get/give.
    if re.match(r"^(again|g)(\b|$)", t) and not t.startswith(
        ("gather", "gaining", "against", "ago", "agency", "agenda", "go ", "get ", "give ", "gaze")
    ):
        # exact bare g/again only; "g east" / "again look" = misuse (not go)
        if re.match(r"^(again|g)$", t):
            return {"type": "again", "raw": (text or "").strip()[:240]}
        if re.match(r"^(again|g)\s+\S", t):
            return {"type": "again", "misuse": True, "raw": (text or "").strip()[:240]}
        # "g," or odd trailing — still again, short refuse path
        if re.match(r"^(again|g)\b", t):
            return {"type": "again", "misuse": True, "raw": (text or "").strip()[:240]}

    # Inform Standard Rules Wait / Wear / Disrobe (DM4 §A4):
    # Wait → "Time passes."; Wear bare → need noun; miss/not wearable → short refuse.
    # Evennia clothing contrib: wear/remove never fall through to say.
    # Bare wait/wear/remove were None → table_turn long-IC talk belt.
    # Handle take off / put on BEFORE take/drop so "take off cloak" is not take(item=off cloak).
    if re.match(r"^(wait|z)(\b|$)", t) and not t.startswith(
        ("waiting", "waiter", "waitress", "waits", "waited", "zulu", "zoom")
    ):
        return {"type": "wait", "raw": (text or "").strip()[:240]}
    if re.match(r"^(wear|don)(\b|$)", t) or re.match(r"^put\s+on(\b|$)", t):
        m = re.match(
            r"^(?:wear|don|put\s+on)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "") or "").strip()[:80]
        if item in ("the", "a", "an", "on"):
            item = ""
        return {"type": "wear", "item": item, "raw": (text or "").strip()[:240]}
    if re.match(r"^(remove|doff)(\b|$)", t) or re.match(r"^take\s+off(\b|$)", t):
        # do not eat "remove from <place>" as wardrobe; still short refuse not talk
        if re.search(r"\bremove\s+from\b", t):
            pass  # fall through — not clothing remove
        else:
            m = re.match(
                r"^(?:remove|doff|take\s+off)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            item = ((m.group(1) if m else "") or "").strip()[:80]
            if item in ("the", "a", "an", "off"):
                item = ""
            return {"type": "remove", "item": item, "raw": (text or "").strip()[:240]}
    if re.search(r"\b(drop|put\s+down|discard)\b", t):
        # Evennia CmdDrop: bare drop → "Drop what?"; miss → "You aren't carrying X."
        # Must not fall through to talk (table_turn long-IC belt).
        m = re.search(r"\b(?:drop|put\s+down|discard)\s+(?:the |a |an )?(.+)$", t)
        item = ((m.group(1) if m else "").strip()[:80])
        if item in ("down", "the", "a", "an"):
            item = ""
        return {"type": "drop", "item": item}
    # Inform Extinguish soft (SwitchOff / put out / douse / blow out) — BEFORE put
    # so "put out torch" never Insert-belts with item="out torch".
    # Field: Understand "extinguish/douse/put out [something]" / "put [something] out"
    # / "blow out [something]" (dualtransform.ni / I7 switching off). Soft floors only.
    # Do NOT steal: Burn/use/fire/"light the"/Calcifer quench; real put X in/on Y; bare blow.
    if re.match(r"^(extinguish|douse)(\b|$)", t) and not t.startswith(
        ("extinguished", "extinguishing", "extinguisher", "doused", "dousing", "douses")
    ):
        m = re.match(
            r"^(?:extinguish|douse)\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+with\s+.+)?$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "with", "out"):
            target = ""
        return {"type": "extinguish", "target": target, "raw": (text or "").strip()[:240]}
    # put out / put X out — must precede Insert/PutOn put organ
    if re.match(r"^put\s+out\b", t) or re.match(
        r"^put\s+(?:the\s+|a\s+|an\s+)?.+\sout$", t
    ):
        if re.match(r"^put\s+out$", t):
            return {"type": "extinguish", "target": "", "raw": (text or "").strip()[:240]}
        m1 = re.match(r"^put\s+out\s+(?:the\s+|a\s+|an\s+)?(.+)$", t)
        if m1:
            target = (m1.group(1) or "").strip()[:80]
            if target in ("the", "a", "an"):
                target = ""
            return {"type": "extinguish", "target": target, "raw": (text or "").strip()[:240]}
        m2 = re.match(r"^put\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+out$", t)
        if m2:
            target = (m2.group(1) or "").strip()[:80]
            if target in ("the", "a", "an", "out"):
                target = ""
            return {"type": "extinguish", "target": target, "raw": (text or "").strip()[:240]}
    # blow out X / blow X out — extinguish soft before Blow organ eats "out …" as target
    if re.match(r"^blow\s+out\b", t) or re.match(
        r"^blow\s+(?:the\s+|a\s+|an\s+)?.+\sout$", t
    ):
        if re.match(r"^blow\s+out$", t):
            return {"type": "extinguish", "target": "", "raw": (text or "").strip()[:240]}
        m1 = re.match(r"^blow\s+out\s+(?:the\s+|a\s+|an\s+)?(.+)$", t)
        if m1:
            target = (m1.group(1) or "").strip()[:80]
            if target in ("the", "a", "an"):
                target = ""
            return {"type": "extinguish", "target": target, "raw": (text or "").strip()[:240]}
        m2 = re.match(r"^blow\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+out$", t)
        if m2:
            target = (m2.group(1) or "").strip()[:80]
            if target in ("the", "a", "an", "out"):
                target = ""
            return {"type": "extinguish", "target": target, "raw": (text or "").strip()[:240]}

    # Inform DM4 §A4 Insert / PutOn — put/insert/place never talk-belt.
    # Grammar (Evennia/Inform verb index):
    #   put on X / put X on → Wear (handled above)
    #   put down X → Drop (handled above)
    #   put|insert|place X in|into|inside Y → Insert
    #   put|place X on|onto Y → PutOn
    # Bare put/insert/place → Put what?
    # Do not eat putter/putting alone; "put on" already returned as wear.
    if re.match(r"^(put|insert|place)(\b|$)", t) and not t.startswith(
        ("putter", "putting", "putrid", "putty", "inserted", "placing", "placement")
    ):
        # Insert: put|insert|place <item> in|into|inside <container>
        m_ins = re.match(
            r"^(?:put|insert|place)\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+"
            r"(?:in|into|inside)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m_ins:
            item = (m_ins.group(1) or "").strip()[:80]
            container = (m_ins.group(2) or "").strip()[:80]
            if item in ("the", "a", "an", "in", "into", "inside"):
                item = ""
            if container in ("the", "a", "an"):
                container = ""
            return {
                "type": "put",
                "mode": "into",
                "item": item,
                "target": container,
                "raw": (text or "").strip()[:240],
            }
        # PutOn: put|place <item> on|onto <supporter> (not "put on <wearable>")
        m_on = re.match(
            r"^(?:put|place)\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+"
            r"(?:on|onto)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m_on:
            item = (m_on.group(1) or "").strip()[:80]
            target = (m_on.group(2) or "").strip()[:80]
            if item in ("the", "a", "an", "on", "onto"):
                item = ""
            if target in ("the", "a", "an"):
                target = ""
            return {
                "type": "put",
                "mode": "onto",
                "item": item,
                "target": target,
                "raw": (text or "").strip()[:240],
            }
        # insert <item> (missing into) or bare put/insert/place
        m_bare_ins = re.match(
            r"^insert\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m_bare_ins:
            item = (m_bare_ins.group(1) or "").strip()[:80]
            if item in ("the", "a", "an", "into", "in"):
                item = ""
            return {
                "type": "put",
                "mode": "into",
                "item": item,
                "target": "",
                "raw": (text or "").strip()[:240],
            }
        # bare put / place / insert
        if re.match(r"^(put|insert|place)$", t):
            return {
                "type": "put",
                "mode": "into",
                "item": "",
                "target": "",
                "raw": (text or "").strip()[:240],
            }
        # put <something> with no in/on → still put, short refuse (not talk)
        m_partial = re.match(
            r"^(?:put|place)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m_partial:
            item = (m_partial.group(1) or "").strip()[:80]
            if item in ("the", "a", "an", "on", "down"):
                item = ""
            return {
                "type": "put",
                "mode": "into",
                "item": item,
                "target": "",
                "raw": (text or "").strip()[:240],
            }

    # Inform Grammar Transfer (Grammar.h) + verblibm TransferSub:
    #   Verb 'transfer' * noun 'to' noun -> Transfer;
    #   TransferSub → AttemptToTake then PutOn / Drop / Insert.
    # Mag has no separate Transfer organ — hang on existing put (Insert/PutOn floors).
    # Bare transfer was None → table_turn long-IC talk belt.
    # Do NOT invent containers/supporters; do NOT steal transformer/transferred alone;
    # Burn stays use; compass move stays move; Knock hangs just below.
    if re.match(r"^transfer(\b|$)", t) and not t.startswith(
        (
            "transferring", "transferred", "transfers", "transferable",
            "transformer", "transform", "transfusion", "transgress",
        )
    ):
        m_to = re.match(
            r"^transfer\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+to\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m_to:
            item = (m_to.group(1) or "").strip()[:80]
            target = (m_to.group(2) or "").strip()[:80]
            if item in ("the", "a", "an", "to"):
                item = ""
            if target in ("the", "a", "an"):
                target = ""
            return {
                "type": "put",
                "mode": "into",
                "item": item,
                "target": target,
                "raw": (text or "").strip()[:240],
            }
        if re.match(r"^transfer$", t):
            return {
                "type": "put",
                "mode": "into",
                "item": "",
                "target": "",
                "raw": (text or "").strip()[:240],
            }
        m_partial = re.match(
            r"^transfer\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m_partial:
            item = (m_partial.group(1) or "").strip()[:80]
            if item in ("the", "a", "an", "to"):
                item = ""
            return {
                "type": "put",
                "mode": "into",
                "item": item,
                "target": "",
                "raw": (text or "").strip()[:240],
            }


    # Inform 7 Handbook knocking-on (I7 custom — not DM4 §A4 Grammar.h).
    # Stock I7 maps bare "knock"→Attack; Mag refuses that belt and hangs soft floors.
    # Understand "knock on [something]" / "tap on [something]" / "rap on|at …".
    # Bare → What do you want to knock on?; Report → You tap gently… nothing happens.
    # Check: self → hollow sound; person → wouldn't be polite.
    # Do NOT steal: attack|hit|fight|kill|swing (attack organ); Burn (use/fire);
    # knockoff/knockout/knocking alone as IC; compass move; enter/gate→move.
    # Never invent Calcifer on keep_gate; never dump room.desc.
    if re.match(r"^(knock|tap|rap)(\b|$)", t) and not t.startswith(
        (
            "knocking", "knocked", "knocks", "knockoff", "knockout", "knockdown",
            "knockabout", "tapping", "tapped", "taps", "taproot", "tapas", "tapestry",
            "rapping", "rapped", "raps", "rapid", "raptor", "rapport", "rapture",
        )
    ):
        # tap alone without on/at stays None (too ambiguous vs tap dance / tap water)
        if re.match(r"^tap$", t):
            pass
        else:
            m = re.match(
                r"^(?:knock|tap|rap)(?:\s+(?:on|at|upon))?\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            if re.match(r"^(?:knock|rap)(?:\s+(?:on|at|upon))?$", t):
                target = ""
            else:
                target = ((m.group(1) if m else "") or "").strip()[:80]
                if target in ("the", "a", "an", "on", "at", "upon", "hard", "gently", "politely", "twice", "thrice"):
                    target = ""
            if m or re.match(r"^(?:knock|rap)(?:\s+(?:on|at|upon))?$", t):
                return {
                    "type": "knock",
                    "target": target,
                    "raw": (text or "").strip()[:240],
                }

    # Inform DM4 §A4 Exit1 + Leave (Grammar.h) — before take/get/climb/talk.
    # Verb 'exit' 'out' 'outside' → Exit; Verb 'leave': bare→VagueGo, noun→Exit,
    # noun=ADirection→Go (move). Mag has no enter-furniture organ yet.
    # Do NOT steal: bare out / leave the tavern|inn|bar / go out (move organ earlier);
    # leave north (move); enter/gate move; Calcifer invent; room.desc dump.
    if t in ("outside", "outside now") or (
        re.match(r"^outside\b", t) and not t.startswith(("outsider", "outsides"))
    ):
        return {"type": "exit", "target": "", "raw": (text or "").strip()[:240]}
    m_leave = re.match(r"^(leave)\b(.*)$", t)
    if m_leave and not t.startswith(
        ("leaving", "leaved", "leaver", "leaves", "leaf", "leaflet", "league")
    ):
        rest = (m_leave.group(2) or "").strip()
        m_ent = re.match(
            r"^(?:into|in|inside|through)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            rest,
        )
        if m_ent:
            ent_tgt = (m_ent.group(1) or "").strip()[:80]
            if ent_tgt in ("the", "a", "an", "into", "in", "inside", "through"):
                ent_tgt = ""
            return {
                "type": "enter",
                "target": ent_tgt,
                "raw": (text or "").strip()[:240],
            }
        if not rest:
            return {"type": "vague_go", "raw": (text or "").strip()[:240]}
        noun = re.sub(r"^(?:the\s+|a\s+|an\s+)", "", rest).strip()[:80]
        _dirs = {
            "n", "s", "e", "w", "u", "d", "north", "south", "east", "west",
            "up", "down", "in", "out", "northeast", "northwest", "southeast",
            "southwest", "ne", "nw", "se", "sw",
        }
        if noun in _dirs or rest in _dirs:
            return {"type": "move", "direction": noun if noun in _dirs else rest}
        if noun in ("the", "a", "an"):
            noun = ""
        if not noun:
            return {"type": "vague_go", "raw": (text or "").strip()[:240]}
        return {
            "type": "exit",
            "target": noun,
            "raw": (text or "").strip()[:240],
        }
    if t in ("exit", "get out", "get off", "climb out", "climb off") or re.match(
        r"^(exit|get\s+out(?:\s+of)?|get\s+off(?:\s+of)?|climb\s+(?:out(?:\s+of)?|off))(\b|$)",
        t,
    ):
        if not t.startswith(("exiting", "exited", "exits", "getting", "climbing")):
            m_ex = re.match(
                r"^(?:exit|get\s+out(?:\s+of)?|get\s+off(?:\s+of)?|"
                r"climb\s+(?:out(?:\s+of)?|off))\s+"
                r"(?:of\s+|from\s+)?(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            ex_tgt = ((m_ex.group(1) if m_ex else "") or "").strip()[:80]
            if ex_tgt in ("the", "a", "an", "of", "from", "out", "off"):
                ex_tgt = ""
            return {
                "type": "exit",
                "target": ex_tgt,
                "raw": (text or "").strip()[:240],
            }

    # Inform DM4 §A4 Enter + Sit/Stand + GetOff residual — never dump room.desc / talk belt.
    # Enter: 1 already in  2 "That's not something you can enter."  3 closed  4 freestanding  5 get onto
    # Sit is Enter. Stand when not on a supporter: "You are already standing."
    # GetOff: "But you aren't on <x1> at the moment." (exit with target, above)
    # Mag has no enter-furniture organ yet → Enter2 / Enter3 / Sit on what? / already standing.
    # Do NOT steal: enter/gate/keep/door/tavern/inn/hall/lantern → later gate heuristic (move north).
    # Do NOT steal Ask (talk) or Burn (use/fire). climb in stays climb. leave tavern/go out/bare out stay move.
    _keep_enter = (
        "gate", "keep", "door", "tavern", "inn", "hall", "lantern",
        "road", "courtyard", "cellar", "cave", "fork", "camp", "town",
        "north", "south", "east", "west",
    )

    def _keep_scale(noun: str) -> bool:
        n = (noun or "").strip().lower()
        if not n:
            return False
        bits = re.split(r"[\s'-]+", n)
        return any(b in _keep_enter for b in bits if b)

    # sit / sit down / sit on|in|at|upon X — before compass so "sit down" never walks down
    if re.match(r"^(sit)(\b|$)", t) and not t.startswith(
        ("sitting", "sitter", "sits", "site", "situat", "sitcom")
    ):
        m_sit = re.match(
            r"^sit(?:\s+down)?(?:\s+(?:on|in|at|upon)\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
            t,
        )
        sit_tgt = ((m_sit.group(1) if m_sit else "") or "").strip()[:80]
        if sit_tgt in ("the", "a", "an", "on", "in", "at", "upon", "down"):
            sit_tgt = ""
        return {
            "type": "sit",
            "target": sit_tgt,
            "raw": (text or "").strip()[:240],
        }

    # stand / stand up — before compass so "stand up" never walks up
    if re.match(r"^(stand)(\b|$)", t) and not t.startswith(
        ("standing", "standard", "stands", "standpoint", "standby", "standstill")
    ):
        if re.match(r"^stand\s+(?:on|in|upon)\s+", t):
            m_st = re.match(
                r"^stand\s+(?:on|in|upon)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            st_tgt = ((m_st.group(1) if m_st else "") or "").strip()[:80]
            if st_tgt in ("the", "a", "an", "on", "in", "upon"):
                st_tgt = ""
            return {
                "type": "sit",
                "target": st_tgt,
                "raw": (text or "").strip()[:240],
            }
        return {"type": "stand", "raw": (text or "").strip()[:240]}

    # get up is Stand, not take
    if t in ("get up", "get up now") or re.match(r"^get\s+up$", t):
        return {"type": "stand", "raw": (text or "").strip()[:240]}

    # lie / lie down / lie on X — not "lie to" (talk) / lieutenant
    if re.match(r"^(lie)(\b|$)", t) and not t.startswith(
        ("lieutenant", "lies", "lied", "lien", "lier")
    ):
        if re.match(r"^lie\s+to\b", t):
            pass  # talk organ later
        else:
            m_lie = re.match(
                r"^lie(?:\s+down)?(?:\s+(?:on|in|upon)\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
                t,
            )
            lie_tgt = ((m_lie.group(1) if m_lie else "") or "").strip()[:80]
            if lie_tgt in ("the", "a", "an", "on", "in", "upon", "down"):
                lie_tgt = ""
            return {
                "type": "sit",
                "target": lie_tgt,
                "mode": "lie",
                "raw": (text or "").strip()[:240],
            }

    # enter <furniture> — bare enter / enter gate|keep|door stay later gate heuristic
    if re.match(r"^(enter)(\b|$)", t) and not t.startswith(
        ("entering", "entered", "enters", "enterprise", "entertain", "entire")
    ):
        if t in ("enter", "enter in"):
            pass  # GoIn → gate heuristic (move north)
        else:
            m_en = re.match(r"^enter\s+(?:the\s+|a\s+|an\s+)?(.+)$", t)
            en_tgt = ((m_en.group(1) if m_en else "") or "").strip()[:80]
            if en_tgt in ("the", "a", "an"):
                en_tgt = ""
            if en_tgt and not _keep_scale(en_tgt):
                return {
                    "type": "enter",
                    "target": en_tgt,
                    "raw": (text or "").strip()[:240],
                }
            # keep-scale: fall through to gate heuristic

    # get in/into/on/onto — before take so "get in the crate" is not take
    # get out/off already returned as exit. get on with → enter refuse (not take).
    if re.match(r"^get\s+(in|into|on|onto)\b", t) and not t.startswith("getting"):
        if re.match(r"^get\s+on\s+with\b", t):
            return {
                "type": "enter",
                "target": "",
                "raw": (text or "").strip()[:240],
            }
        m_gi = re.match(
            r"^get\s+(?:in(?:to)?|on(?:to)?)(?:\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
            t,
        )
        gi_tgt = ((m_gi.group(1) if m_gi else "") or "").strip()[:80]
        if gi_tgt in ("the", "a", "an", "in", "into", "on", "onto"):
            gi_tgt = ""
        if gi_tgt and _keep_scale(gi_tgt):
            return {"type": "move", "direction": "north"}
        return {
            "type": "enter",
            "target": gi_tgt,
            "raw": (text or "").strip()[:240],
        }

    # go into <furniture> — go in / go inside stay later (inside→north; go in handled below)
    if re.match(r"^go\s+into\b", t) and not t.startswith("going"):
        m_go = re.match(
            r"^go\s+into\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        go_tgt = ((m_go.group(1) if m_go else "") or "").strip()[:80]
        if go_tgt in ("the", "a", "an"):
            go_tgt = ""
        if go_tgt and _keep_scale(go_tgt):
            return {"type": "move", "direction": "north"}
        return {
            "type": "enter",
            "target": go_tgt,
            "raw": (text or "").strip()[:240],
        }
    if t in ("go in", "go inside"):
        return {"type": "move", "direction": "north"}

    # Inform DM4 Sleep idiom before take: "take a nap" must not become take item=nap.
    # Also snooze / have a nap|doze — soft Sleep floor; rest|sleep|camp|heal stay rest later.
    if re.match(
        r"^(?:take\s+(?:a\s+|an\s+)?nap|have\s+(?:a\s+|an\s+)?(?:nap|doze|snooze)|snooze)(\b|$)",
        t,
    ) and not t.startswith(("taken", "taking", "takes", "having", "snoozing", "snoozed", "snoozes")):
        return {"type": "sleep", "raw": (text or "").strip()[:240]}

    if re.search(r"\b(take|grab|get|pick\s+up|pick)\b", t):
        # Evennia CmdGet: pick up is one verb; bare "pick up" has no noun (not item=up).
        m = re.search(r"\b(?:pick\s+up|take|grab|get|pick)\s+(?:the |a |an )?(.+)$", t)
        item = ((m.group(1) if m else "").strip()[:80])
        if item in ("up", "the", "a", "an"):
            item = ""
        return {"type": "take", "item": item}
    if re.search(r"\b(give|hand)\b", t):
        # Evennia CmdGive: give <inv> to <target> — bare/miss never fall through to talk.
        # Usage floor when rhs missing; inventory miss → You aren't carrying X.
        m = re.search(
            r"\b(?:give|hand)\s+(?:the |a |an )?(.+?)\s+(?:to|=)\s+(?:the\s+)?(.+)$",
            t,
        )
        if m:
            item = (m.group(1) or "").strip()[:80]
            target = (m.group(2) or "").strip()[:80]
            return {"type": "give", "item": item, "target": target}
        m2 = re.search(r"\b(?:give|hand)\s+(?:the |a |an )?(.+)$", t)
        item = ((m2.group(1) if m2 else "").strip()[:80])
        if item in ("the", "a", "an", "to"):
            item = ""
        return {"type": "give", "item": item, "target": ""}
    if re.search(r"\b(open|close|shut|cover|uncover|unwrap)\b", t):
        # Evennia CmdOpenCloseDoor (simpledoor): empty args → usage then return.
        # Bare "open" used to be work (talk/work dump). Crate/door open is in-world.
        # "open the box|temple|ward" stays work (matched above).
        # Inform Grammar.h: Verb 'close' 'shut' 'cover' → Close (* up noun);
        # Verb 'open' 'unwrap' 'uncover' 'undo' → Open. Hang cover/uncover/unwrap
        # on existing open/close organ only — no new type, no Calcifer invent.
        closing = bool(re.search(r"\b(close|shut|cover)\b", t))
        if re.search(r"\b(uncover|unwrap)\b", t):
            closing = False
        m = re.search(
            r"\b(?:open|close|shut|cover|uncover|unwrap)\s+(?:up\s+)?(?:the |a |an )?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "").strip()[:80])
        if item in ("the", "a", "an", "up"):
            item = ""
        return {"type": "close" if closing else "open", "item": item}
    if re.search(r"\b(wink|nod|wave)\s+at\b", t):
        # Inform [someone] / Evennia caller.search: social verbs are local-scope.
        # Bare "wink at" must not teleport to Calcifer; empty target lets _talk_events
        # ask "Talk to whom?" or floor "No one answers." Explicit "wink at calcifer" still works.
        m = re.search(r"\b(?:wink|nod|wave)\s+at\s+(?:the\s+)?(.+)$", t)
        who = ((m.group(1) if m else "").strip()[:80])
        return {"type": "talk", "raw": (text or "").strip()[:240], "target": who}
    if re.search(r"\bwhisper\b", t):
        # Evennia CmdWhisper (general.py): key=whisper; empty lhs/rhs →
        # "Usage: whisper <character> = <message>" then return. Bare whisper was
        # None → table_turn long-IC talk belt. Never invent NPC chatter for miss.
        # Accept Evennia "=" form plus voice-friendly "whisper to NAME MSG".
        m = re.search(
            r"\bwhisper\s+(?:to\s+)?(?:the\s+)?(.+?)\s*=\s*(.+)$",
            t,
        )
        if m:
            target = (m.group(1) or "").strip()[:80]
            message = (m.group(2) or "").strip()[:240]
            if target in ("the", "a", "an", "to"):
                target = ""
            return {"type": "whisper", "target": target, "message": message, "raw": (text or "").strip()[:240]}
        m2 = re.search(
            r"\bwhisper\s+(?:to\s+)?(?:the\s+)?([a-z][\w'-]*)(?:\s+(.+))?$",
            t,
        )
        if m2:
            target = (m2.group(1) or "").strip()[:80]
            message = (m2.group(2) or "").strip()[:240]
            if target in ("the", "a", "an", "to", "at"):
                target = ""
                message = ""
            return {"type": "whisper", "target": target, "message": message, "raw": (text or "").strip()[:240]}
        return {"type": "whisper", "target": "", "message": "", "raw": (text or "").strip()[:240]}
    # Evennia CmdPose (general.py): key=pose aliases=[":","emote"] arg_regex=None.
    # Bare pose/emote was None → table_turn long-IC talk belt. Never invent NPC chatter.
    # Colon alias only at line start (:waves); pose's form keeps apostrophe glued to name.
    if t.startswith(":") or re.match(r"^(pose|emote)(?:\s|$|'s\b)", t):
        raw_in = (text or "").strip()
        if raw_in.startswith(":"):
            pose_body = raw_in[1:]
        else:
            mpose = re.match(r"^(?:pose|emote)('s)?\s*(.*)$", raw_in, re.I)
            if not mpose:
                pose_body = ""
            else:
                apost = mpose.group(1) or ""
                rest = (mpose.group(2) or "").strip()
                if apost:
                    # Evennia pose's X → args="'s X" (no space before apostrophe)
                    pose_body = apost + ((" " + rest) if rest else "")
                else:
                    pose_body = rest
        return {"type": "pose", "pose": pose_body, "raw": raw_in[:240]}
    # Inform DM4 §A4 Smell / Taste / Touch. Bare smell/taste/touch were None →
    # table_turn long-IC talk belt. Short sensory floors only; never room.desc.
    # Mag voice: sniff≈smell, feel≈touch. Do not eat smelling/tasting/touching/feeling alone.
    if re.match(r"^(smell|sniff|taste|touch|feel)(\b|$)", t) and not t.startswith(
        ("smelling", "smelly", "tasting", "tasty", "touching", "feeling", "feels", "felt")
    ):
        m = re.match(
            r"^(?:smell|sniff|taste|touch|feel)(?:\s+(?:the\s+|a\s+|an\s+|at\s+))?(.+)?$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "at", "carefully", "closely", "hard", "gently"):
            target = ""
        if t.startswith(("smell", "sniff")):
            sense = "smell"
        elif t.startswith("taste"):
            sense = "taste"
        else:
            sense = "touch"
        return {"type": sense, "target": target, "raw": (text or "").strip()[:240]}

    # Inform DM4 §A4 Pronouns + NotifyOn/Off + Verify; Inform Version (banner).
    # Bare pronouns|nouns|notify|verify|version were None → table_turn long-IC talk belt.
    # Mag: no pronoun-antecedent organ yet → Pronouns4 only. Notify hangs score_notify flag.
    # Verify always intact (no gamefile CRC organ). Version is Mag banner, not room.desc.
    # Do NOT steal: notification/notified/pronoun/noun singular/verifying/verified/versions;
    # consult stays read; score stays score; brief stays lmode.
    if re.match(r"^(pronouns|nouns)$", t):
        return {"type": "pronouns", "raw": (text or "").strip()[:240]}
    if re.match(r"^notify(\s+on)?$", t):
        return {"type": "notify", "mode": "on", "raw": (text or "").strip()[:240]}
    if t == "notify off":
        return {"type": "notify", "mode": "off", "raw": (text or "").strip()[:240]}
    if re.match(r"^(verify|verif)$", t):
        return {"type": "verify", "raw": (text or "").strip()[:240]}
    if t == "version":
        return {"type": "version", "raw": (text or "").strip()[:240]}

    # Inform DM4 §A4 / I6 PG §A.3.3 ScriptOn/Off + noscript/unscript aliases.
    # Bare script|transcript|script on|script off|noscript|unscript were None → table_turn long-IC talk belt.
    # Mag: no Z-machine transcript stream — hang camp["transcript"] flag + short floors only.
    # Do NOT steal: scripting/scripts/scripture/typescript; bare "commands" stays help; version/score stay.
    if re.match(r"^(script|transcript)(\s+on)?$", t):
        return {"type": "script", "mode": "on", "raw": (text or "").strip()[:240]}
    if re.match(r"^(script|transcript)\s+off$", t) or re.match(r"^(noscript|unscript)$", t):
        return {"type": "script", "mode": "off", "raw": (text or "").strip()[:240]}

    # Inform I6 PG §A.3.3 Recording / Replay (CommandsOn/Off/Read).
    # Bare recording|recording on|recording off|replay were None → table_turn long-IC talk belt.
    # Mag: no Z-machine command-file / input_stream organ — hang camp["recording"] flag; soft floors only.
    # Do NOT steal: record/recorded/recordings/replaying/replayed; bare "commands" (help organ above).
    # Never invent Calcifer on keep_gate; never dump room.desc; never open a file dialog.
    if re.match(r"^recording(\s+on)?$", t):
        return {"type": "recording", "mode": "on", "raw": (text or "").strip()[:240]}
    if re.match(r"^recording\s+off$", t):
        return {"type": "recording", "mode": "off", "raw": (text or "").strip()[:240]}
    if re.match(r"^replay$", t):
        return {"type": "replay", "raw": (text or "").strip()[:240]}

    # Inform DM4 / verblib AMUSING_PROVIDED end-menu stub (Amusing entry point).
    # Bare "amusing" was None → table_turn long-IC talk belt.
    # Mag has no deadflag=2 victory organ — soft refuse only; never room.desc; never invent Calcifer.
    # Do NOT steal: amuse/amused/amusingly; "amusing mira"; Burn (use/fire).
    # Ask soft floors: bare / ask about only (see ask block near Answer).
    if re.match(r"^amusing$", t):
        return {"type": "amusing", "raw": (text or "").strip()[:240]}

    # Inform DM4 §A4 Quit/Restart/Restore/Save + Miscellany Undo/Oops.
    # Bare quit|restart|restore|save|undo|oops were None → table_turn long-IC talk belt.
    # Mag: Verkle is the only save (ironman). Soft floors only — never wipe camp, never kill /wave,
    # never invent Z-machine file dialog, never invent Calcifer on keep_gate.
    # Do NOT steal: die (attack synonym), bare q (ambiguous), save freeze (freeze organ above),
    # undo NOUN (Inform open synonym), bare o, quitting/restarted/restoring/saved/undone/oopsie.
    if re.match(r"^quit$", t):
        return {"type": "quit", "raw": (text or "").strip()[:240]}
    if re.match(r"^restart$", t):
        return {"type": "restart", "raw": (text or "").strip()[:240]}
    if re.match(r"^restore$", t):
        return {"type": "restore", "raw": (text or "").strip()[:240]}
    if re.match(r"^save$", t):
        return {"type": "save", "raw": (text or "").strip()[:240]}
    if re.match(r"^undo$", t):
        return {"type": "undo", "raw": (text or "").strip()[:240]}
    if re.match(r"^oops$", t):
        return {"type": "oops", "mode": "bare", "raw": (text or "").strip()[:240]}
    if re.match(r"^oops\s+\S+$", t):
        return {"type": "oops", "mode": "word", "raw": (text or "").strip()[:240]}
    if re.match(r"^oops\s+\S+\s+\S+", t):
        return {"type": "oops", "mode": "multi", "raw": (text or "").strip()[:240]}

    # Inform DM4 §A4 LMode1/2/3 + Objects + Places — bare brief|verbose|superbrief|objects|places
    # were None → table_turn long-IC talk belt. Short Inform floors only; never room.desc.
    # Mag: no look-mode / visited / handled organs yet — speak + optional look_mode flag / inv hang.
    # Do NOT steal: short|long|normal (ambiguous); object/place singular; briefcase; scoreboard.
    # sleep|rest|heal|camp stay rest. nap/doze/yawn → Sleep soft above. Score/Push/Pull below.
    if re.match(r"^(brief|verbose|superbrief)$", t):
        return {"type": "lmode", "mode": t, "raw": (text or "").strip()[:240]}
    if re.match(r"^(objects|places)$", t):
        return {"type": t, "raw": (text or "").strip()[:240]}
    if re.match(r"^objects\s+i\s+have\s+handled$", t) or t == "objects handled":
        return {"type": "objects", "raw": (text or "").strip()[:240]}
    if re.match(r"^places\s+i\s+have\s+visited$", t) or t == "places visited":
        return {"type": "places", "raw": (text or "").strip()[:240]}

    # Inform DM4 §A4 Score / Push / Pull (Turn shares Pull floors; parse block just below).
    # Bare score|push|pull were None → table_turn long-IC talk belt. Short Inform floors only.
    # Mag has no MAX_SCORE organ yet — scored 0 / possible 0. Do not break enter/gate→move.
    # Exact word boundaries: scoreboard/scores/scoring/pushes/pushing/pulling alone stay None.
    if re.match(r"^(score|fullscore|full\s+score)$", t):
        return {"type": "score", "raw": (text or "").strip()[:240]}
    if re.match(r"^(push|pull)(\b|$)", t) and not t.startswith(
        ("pushing", "pushes", "pushed", "pushy", "pulling", "pulls", "pulled", "pulley", "pullout")
    ):
        m = re.match(
            r"^(?:push|pull)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "hard", "gently", "carefully", "aside", "away"):
            target = ""
        verb = "push" if t.startswith("push") else "pull"
        # Inform Grammar: push|move|shift|clear|press noun 'to' noun → Transfer (not Push).
        # Mag only routes push (not pull) noun-to-noun onto put; Pull stays Pull.
        # Direction seconds stay PushDir below. Never invent a container organ.
        if verb == "push" and target:
            m_xfer = re.match(
                r"^(.+?)\s+to\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                target,
            )
            if m_xfer:
                x_item = (m_xfer.group(1) or "").strip()[:80]
                x_dest = (m_xfer.group(2) or "").strip()[:80]
                _xfer_dirs = (
                    "north", "south", "east", "west",
                    "northeast", "northwest", "southeast", "southwest",
                    "n", "s", "e", "w", "ne", "nw", "se", "sw",
                    "up", "down", "in", "out",
                )
                if x_dest and x_dest not in _xfer_dirs and x_item not in ("the", "a", "an"):
                    return {
                        "type": "put",
                        "mode": "into",
                        "item": x_item,
                        "target": x_dest,
                        "raw": (text or "").strip()[:240],
                    }
        # Inform DM4 §A4 PushDir — push|pull NOUN DIR / DIR alone.
        # Mag has no AllowPushDir scenery organ → short floors; never room.desc; never move.
        # Do NOT steal bare n/s/e/w (already move). Swing stays attack.
        _dirs = (
            "north", "south", "east", "west",
            "northeast", "northwest", "southeast", "southwest",
            "n", "s", "e", "w", "ne", "nw", "se", "sw",
            "up", "down", "in", "out",
        )
        if target:
            parts = target.split()
            last = parts[-1]
            # strip trailing "to the DIR" / "to DIR"
            if last in _dirs:
                noun_parts = parts[:-1]
                while noun_parts and noun_parts[-1] in ("to", "the", "a", "an"):
                    noun_parts = noun_parts[:-1]
                noun = " ".join(noun_parts).strip()
                if not noun:
                    # push north — direction alone is not a pushable
                    return {
                        "type": "pushdir",
                        "code": 2,
                        "direction": last,
                        "target": "",
                        "raw": (text or "").strip()[:240],
                    }
                if last in ("up", "down"):
                    return {
                        "type": "pushdir",
                        "code": 3,
                        "direction": last,
                        "target": noun[:80],
                        "raw": (text or "").strip()[:240],
                    }
                return {
                    "type": "pushdir",
                    "code": 1,
                    "direction": last,
                    "target": noun[:80],
                    "raw": (text or "").strip()[:240],
                }
        return {"type": verb, "target": target, "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Turn (see Pull) + English synonyms rotate/twist/screw/unscrew.
    # Bare turn was None → table_turn long-IC talk belt. Shares Push/Pull floors.
    # turn on|off / turn X on|off → SwitchOn/Off (existing switch organ); never invent dial.
    # Do NOT steal: turning/turned/turns/turner/turnip/tournament; Burn (use/fire);
    # push/pull stay their organs; set fire stays use.
    if re.match(r"^(turn|rotate|twist|screw|unscrew)(\b|$)", t) and not t.startswith(
        (
            "turning", "turned", "turns", "turner", "turnip", "turnout", "turnover",
            "turnpike", "turntable", "tournament", "tornado",
            "rotating", "rotated", "rotates", "rotary", "rotation",
            "twisting", "twisted", "twists", "twister",
            "screwing", "screwed", "screws", "screwdriver", "screwball",
            "unscrewing", "unscrewed", "unscrews",
        )
    ):
        # SwitchOn/Off grammar rides on turn (Inform English library).
        if re.match(r"^turn\s+(on|off)(\b|$)", t):
            m = re.match(
                r"^turn\s+(?:on|off)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            target = ((m.group(1) if m else "") or "").strip()[:80]
            if target in ("the", "a", "an", "on", "off"):
                target = ""
            return {"type": "switch", "target": target, "raw": (text or "").strip()[:240]}
        if re.match(r"^turn\s+(?:the\s+|a\s+|an\s+)?.+\s+(on|off)$", t):
            m = re.match(
                r"^turn\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+(?:on|off)$",
                t,
            )
            target = ((m.group(1) if m else "") or "").strip()[:80]
            if target in ("the", "a", "an", "on", "off"):
                target = ""
            return {"type": "switch", "target": target, "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^(?:turn|rotate|twist|screw|unscrew)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "around", "aside", "away", "hard", "gently", "carefully"):
            target = ""
        # strip leading "around " residue
        if target.startswith("around "):
            target = target[7:].strip()[:80]
        return {"type": "turn", "target": target, "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Sleep — Grammar.h Verb 'sleep' 'nap' 'doze' → Sleep.
    # Mag rest organ owns rest|heal|camp|sleep (HP heal). Hang ONLY nap/doze/yawn soft floors
    # so bare nap/doze never belt to long-IC talk. Do NOT steal sleep/rest/camp/heal.
    # Do not eat napping/napped/naps/napkin, dozing/dozed/dozes, yawning/yawned/yawns alone as IC.
    # Never invent Calcifer on keep_gate; never dump room.desc.
    if re.match(r"^(nap|doze|yawn)(\b|$)", t) and not t.startswith(
        (
            "napping", "napped", "naps", "napkin", "napoleon", "naphtha",
            "dozing", "dozed", "dozes", "dozen", "dozy",
            "yawning", "yawned", "yawns", "yawner",
        )
    ):
        return {
            "type": "sleep",
            "raw": (text or "").strip()[:240],
        }

    # Inform DM4 §A4 Jump / JumpOver / Sing / Think / Kiss.
    # Bare jump|sing|think|kiss were None → table_turn long-IC talk belt.
    # sleep|rest|heal|camp stay rest organ below — do not steal Sleep verb word itself.
    # Do not eat jumper/jumping alone, singer/singing alone, thinker alone, kissing alone as IC.
    if re.match(r"^(jump)(\b|$)", t) and not t.startswith(
        ("jumper", "jumping", "jumped", "jumpsuit", "jumpstart")
    ):
        m = re.match(
            r"^jump\s+(?:over\s+)?(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "over", "up", "down", "around"):
            target = ""
        # "jump over X" or "jump X" → JumpOver floor when target present
        over = bool(re.match(r"^jump\s+over\b", t)) or bool(target)
        return {
            "type": "jump",
            "over": over and bool(target),
            "target": target,
            "raw": (text or "").strip()[:240],
        }
    if re.match(r"^(sing)(\b|$)", t) and not t.startswith(
        ("singer", "singing", "single", "singular", "singapore")
    ):
        return {"type": "sing", "raw": (text or "").strip()[:240]}
    if re.match(r"^(think)(\b|$)", t) and not t.startswith(
        ("thinker", "thinking", "thinks", "thought")
    ):
        # bare think only; "think about X" still think (short floor)
        return {"type": "think", "raw": (text or "").strip()[:240]}
    if re.match(r"^(kiss)(\b|$)", t) and not t.startswith(
        ("kisser", "kissing", "kisses", "kissed")
    ):
        m = re.match(
            r"^kiss\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an"):
            target = ""
        return {"type": "kiss", "target": target, "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Swim/Dig/Cut/Wake/Pray — miss verbs were None → table_turn talk belt.
    # Do NOT steal Burn here: burn|set fire already maps to use/fire earlier.
    # Do NOT eat swimming/digger/cutter/waking/prayer alone as IC.
    if re.match(r"^(swim|dive)(\b|$)", t) and not t.startswith(
        ("swimmer", "swimming", "swims", "diver", "diving", "dives", "dividend", "diverse")
    ):
        return {"type": "swim", "raw": (text or "").strip()[:240]}
    if re.match(r"^(dig)(\b|$)", t) and not t.startswith(
        ("digger", "digging", "digits", "digital", "digest", "dignity")
    ):
        m = re.match(
            r"^dig\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "with", "up", "down"):
            target = ""
        # strip trailing "with X"
        target = re.sub(r"\s+with\s+.+$", "", target).strip()[:80]
        return {"type": "dig", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(cut|chop|slice|prune)(\b|$)", t) and not t.startswith(
        ("cutter", "cutting", "cuts", "cute", "cutoff", "chopper", "chopping", "slicer", "slicing", "pruner", "pruning")
    ):
        m = re.match(
            r"^(?:cut|chop|slice|prune)\s+(?:the\s+|a\s+|an\s+|up\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "up", "down", "with"):
            target = ""
        target = re.sub(r"\s+with\s+.+$", "", target).strip()[:80]
        return {"type": "cut", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(wake)(\b|$)", t) and not t.startswith(
        ("waker", "waking", "wakes", "wakeful", "wakeup")
    ):
        # wake / wake up / wake X → Wake floor (not rest); WakeOther same short refusal
        return {"type": "wake", "raw": (text or "").strip()[:240]}
    if re.match(r"^(pray)(\b|$)", t) and not t.startswith(
        ("prayer", "praying", "prays", "prayed")
    ):
        return {"type": "pray", "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Swing — Grammar.h Verb 'swing' * noun → Swing * 'on' noun → Swing.
    # Floor: There's nothing sensible to swing here.
    # Weakest link: swing on rope / swing the rope hit attack catchall → combat belt.
    # Steal ONLY object/on|from forms. Keep bare swing / swing at X as attack synonym.
    # Do NOT steal: attack|hit|fight|strike|kill|stab|slash; Burn (use/fire).
    # Never invent Calcifer on keep_gate; never dump room.desc.
    if re.match(r"^(swing)(\b|$)", t) and not t.startswith(
        (
            "swinging", "swung", "swings", "swingset", "swinger", "swinging",
        )
    ):
        # bare swing → fall through to attack catchall
        if re.match(r"^swing$", t):
            pass
        # swing at X → attack (combat aim)
        elif re.match(r"^swing\s+at\b", t):
            pass
        # swing sword at goblin → attack
        elif re.search(r"\bat\b", t):
            pass
        else:
            m_on = re.match(
                r"^swing\s+(?:on|from)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            m_noun = re.match(
                r"^swing\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            if m_on:
                target = (m_on.group(1) or "").strip()[:80]
            elif m_noun:
                target = (m_noun.group(1) or "").strip()[:80]
            else:
                target = ""
            if target in ("the", "a", "an", "on", "from", "at", "hard", "gently", "wildly"):
                target = ""
            # strip trailing "with X" residue
            target = re.sub(r"\s+with\s+.+$", "", target).strip()[:80]
            if m_on or m_noun:
                return {
                    "type": "swing",
                    "target": target,
                    "raw": (text or "").strip()[:240],
                }

    # Inform DM4 §A4 Rub/Squeeze/WaveHands/Climb — miss verbs were None → table_turn talk belt.
    # Swing object/on|from stolen above; bare swing / swing at stay attack synonym below.
    # Do NOT steal "wave at" (social→talk earlier).
    # Do NOT break enter/gate→move. Do NOT eat rubber/squeezer/waving/climber alone.
    if re.match(r"^(rub)(\b|$)", t) and not t.startswith(
        ("rubber", "rubbing", "rubs", "rubbish", "rubble")
    ):
        m = re.match(
            r"^rub\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an"):
            target = ""
        return {"type": "rub", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(squeeze)(\b|$)", t) and not t.startswith(
        ("squeezer", "squeezing", "squeezes", "squeezed")
    ):
        m = re.match(
            r"^squeeze\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an"):
            target = ""
        return {"type": "squeeze", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(wave)(\b|$)", t) and not t.startswith(
        ("waver", "waving", "waves", "wavelength", "waveform")
    ):
        # "wave at X" already returned talk earlier; bare wave / wave <obj>
        m = re.match(
            r"^wave\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "around", "hello", "goodbye", "bye"):
            target = ""
        # strip "at ..." if somehow reached here
        if target.startswith("at "):
            target = target[3:].strip()[:80]
        return {"type": "wave", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(climb)(\b|$)", t) and not t.startswith(
        ("climber", "climbing", "climbs", "climbed", "climate", "climax")
    ):
        m = re.match(
            r"^climb\s+(?:(?:up|down|over|on|onto)\s+)?(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "up", "down", "over", "on", "onto"):
            target = ""
        return {"type": "climb", "target": target, "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Blow/Buy/Tie/Sorry/LookUnder — miss verbs were None (or look-under→look)
    # → table_turn talk belt / wrong look. Do NOT steal Burn (use/fire). Do NOT eat
    # buyer/buying alone as buy when "buy a drink" already drink. Do NOT break search→look.
    if re.match(r"^(blow)(\b|$)", t) and not t.startswith(
        ("blower", "blowing", "blows", "blown", "blowout", "blowup")
    ):
        m = re.match(
            r"^blow\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "on", "out", "up"):
            target = ""
        return {"type": "blow", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(buy|purchase)(\b|$)", t) and not t.startswith(
        ("buyer", "buying", "buys", "bought", "buyout")
    ):
        # "buy a drink" already returned drink earlier; remaining buy → shop floor.
        m = re.match(
            r"^(?:buy|purchase)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an"):
            target = ""
        return {"type": "buy", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(tie|fasten)(\b|$)", t) and not t.startswith(
        ("tier", "tied", "ties", "tying", "tiebreaker", "fastener", "fastening", "fastens")
    ):
        m = re.match(
            r"^(?:tie|fasten)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "up", "down", "to", "onto"):
            target = ""
        # strip "to X" residual for short floor
        target = re.sub(r"\s+to\s+.+$", "", target).strip()[:80]
        return {"type": "tie", "target": target, "raw": (text or "").strip()[:240]}
    # Inform community Untie soft (I7 has no built-in Untie; stock says
    # "That's not a verb I recognise." Field: Untying / Untying it from —
    # https://intfiction.org/t/built-in-verb-for-opposite-of-tie-attach/42145
    # Understand "untie/unfasten [something]" / "untie [something] from [something]".
    # Check block: "There's nothing to be achieved by that."
    # Mag: bare → What do you want to untie?; noun → field refuse.
    # Hang BEFORE talk catch-all so "untie mira" is not belted by mira keyword.
    # Do NOT steal: cut/rope free organ; tie/fasten; Calcifer invent; room.desc.
    if re.match(r"^(untie|unfasten)(\b|$)", t) and not t.startswith(
        (
            "untied", "untying", "unties", "untieable",
            "unfastened", "unfastening", "unfastens",
        )
    ):
        m = re.match(
            r"^(?:untie|unfasten)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "from", "off", "up"):
            target = ""
        # strip "from X" residual (Untying it from) for short floor
        target = re.sub(r"\s+from\s+.+$", "", target).strip()[:80]
        return {"type": "untie", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(sorry|apologize|apologise)(\b|$)", t) and not t.startswith(
        ("sorrow", "sorryness")
    ):
        return {"type": "sorry", "raw": (text or "").strip()[:240]}
    # LookUnder before later look/look-up paths so "look under X" is not look(item=under X).
    if re.match(r"^look\s+(under|underneath|beneath)(\b|$)", t):
        m = re.match(
            r"^look\s+(?:under|underneath|beneath)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "here", "there"):
            target = ""
        return {"type": "look_under", "target": target, "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Soft Yes/No + Set/SetTo + Switch + ThrowAt — miss verbs were None
    # → table_turn talk belt. Do NOT steal "n" (north), "throw workers" (work), attack/slay.
    # Do NOT invent switch organ. Bare y only (n already move north).
    if t in ("yes", "y", "yeah", "yep") or re.match(r"^(yes)(\b|$)", t):
        if t.startswith(("yesterday", "yester", "yeast", "yellow")):
            pass
        else:
            return {"type": "yes", "raw": (text or "").strip()[:240]}
    if t in ("no", "nope", "nah") or (
        re.match(r"^(no)(\b|$)", t)
        and not t.startswith(
            (
                "north",
                "note",
                "notch",
                "none",
                "nothing",
                "nobody",
                "nowhere",
                "now",
                "noble",
                "noise",
                "nod",
            )
        )
    ):
        # bare no / nope; "no thanks" still rhetorical Soft No
        return {"type": "no", "raw": (text or "").strip()[:240]}
    if re.match(r"^(set)(\b|$)", t) and not t.startswith(
        ("settle", "setting", "sets", "setup", "settee", "setter")
    ):
        # set fire / set X on fire stays use (parsed later); do not steal burn.
        if not (
            re.search(r"\b(fire|alight|ablaze)\b", t) or " on fire" in t
        ):
            m = re.match(
                r"^set\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+to\s+(.+))?$",
                t,
            )
            target = ((m.group(1) if m else "") or "").strip()[:80]
            set_to = ((m.group(2) if m else "") or "").strip()[:80]
            if target in ("the", "a", "an", "to"):
                target = ""
            out = {"type": "set", "target": target, "raw": (text or "").strip()[:240]}
            if set_to:
                out["set_to"] = set_to
            return out
    if re.match(r"^(switch)(\b|$)", t) and not t.startswith(
        ("switched", "switching", "switches", "switcher")
    ):
        if t in ("switch", "switch on", "switch off"):
            return {"type": "switch", "target": "", "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^switch\s+(?:(?:on|off)\s+)?(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "on", "off"):
            target = ""
        target = re.sub(r"\s+(on|off)$", "", target).strip()[:80]
        return {"type": "switch", "target": target, "raw": (text or "").strip()[:240]}
    if re.match(r"^(throw)(\b|$)", t) and not t.startswith(
        ("thrown", "throws", "throwing", "throwback")
    ):
        # "throw workers" already work earlier; remaining throw → ThrowAt floor
        if re.search(r"\bworkers?\b", t):
            pass
        else:
            m = re.match(
                r"^throw\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+at\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
                t,
            )
            if m:
                obj = (m.group(1) or "").strip()[:80]
                at = (m.group(2) or "").strip()[:80]
                if obj in ("the", "a", "an", "at"):
                    obj = ""
                if obj.startswith("at "):
                    at = obj[3:].strip()[:80]
                    obj = ""
                target = at or obj
            else:
                target = ""
            return {"type": "throw_at", "target": target, "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Mild / Strong — miss swear floors; bare (or trailing punct) only.
    # Longer IC speech with a mid-line swear stays None → talk. Do not invent Mild organ.
    m_mild = re.match(r"^(damn|darn|heck|bloody)\b(.*)$", t)
    if m_mild and re.fullmatch(r"[\s!?.]*", m_mild.group(2) or ""):
        return {"type": "mild", "raw": (text or "").strip()[:240]}
    m_strong = re.match(r"^(fuck|shit|asshole|bastard|bitch)\b(.*)$", t)
    if m_strong and re.fullmatch(r"[\s!?.]*", m_strong.group(2) or ""):
        return {"type": "strong", "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Fill — miss fillables; no water organ yet.
    if re.match(r"^(fill)(\b|$)", t) and not t.startswith(
        ("filling", "filled", "filler", "fillet")
    ):
        if t == "fill":
            return {"type": "fill", "target": "", "with_what": "", "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^fill\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+with\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        with_what = ((m.group(2) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "with"):
            target = ""
        if with_what in ("the", "a", "an"):
            with_what = ""
        return {
            "type": "fill",
            "target": target,
            "with_what": with_what,
            "raw": (text or "").strip()[:240],
        }
    # Inform DM4 §A4 EmptyT — miss empties; no container organ yet.
    # Do not steal empty-handed / emptying / emptied / emptiness.
    if re.match(r"^(empty)(\b|$)", t) and not t.startswith(
        ("emptying", "emptied", "emptiness", "empty-handed", "emptyhanded", "empty-")
    ):
        if t in ("empty", "empty out"):
            return {"type": "empty", "target": "", "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^empty\s+(?:out\s+)?(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "out"):
            target = ""
        return {"type": "empty", "target": target, "raw": (text or "").strip()[:240]}
    # Inform EmptyT cousin — Mag soft Pour (stock Grammar.h has no Pour verb).
    # Empty: noun / out noun / noun out / noun to|into|on|onto noun → EmptyT.
    # Hang before talk catch-all so "pour mira" never talk-belts.
    # Do NOT steal: pouring/poured/pours; drink phrases (drink organ earlier:
    # "pour yourself a drink" / "pour a drink"); fill/empty organs; Calcifer invent.
    if re.match(r"^(pour)(\b|$)", t) and not t.startswith(
        ("pouring", "poured", "pours", "pourable")
    ):
        # leave long IC with drink keywords to earlier drink path (already returned)
        if t in ("pour", "pour out"):
            return {"type": "pour", "target": "", "into": "", "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^pour\s+(?:out\s+)?(?:the\s+|a\s+|an\s+)?(.+?)"
            r"(?:\s+(?:into|in|on|onto|to)\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        into = ((m.group(2) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "out", "into", "in", "on", "onto", "to"):
            target = ""
        if into in ("the", "a", "an"):
            into = ""
        # "pour out the jug" → target jug
        if target.startswith("out "):
            target = target[4:].strip()[:80]
        return {
            "type": "pour",
            "target": target,
            "into": into,
            "raw": (text or "").strip()[:240],
        }
    # Inform DM4 §A4 Show — miss show; do NOT steal share (work) or examine/look.
    if re.match(r"^(show|display|present)(\b|$)", t) and not t.startswith(
        (
            "showing",
            "showed",
            "shower",
            "shown",
            "displaying",
            "displayed",
            "presents",
            "presented",
            "presenting",
            "presentation",
        )
    ):
        if t in ("show", "display", "present"):
            return {"type": "show", "item": "", "target": "", "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^(?:show|display|present)\s+(?:the\s+|a\s+|an\s+)?(.+?)\s+to\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        if m:
            item = (m.group(1) or "").strip()[:80]
            target = (m.group(2) or "").strip()[:80]
            if item in ("the", "a", "an", "to"):
                item = ""
            if target in ("the", "a", "an"):
                target = ""
            return {
                "type": "show",
                "item": item,
                "target": target,
                "raw": (text or "").strip()[:240],
            }
        m = re.match(
            r"^(?:show|display|present)\s+(?:the\s+)?(\S+)\s+(?:the\s+|a\s+|an\s+)(.+)$",
            t,
        )
        if m:
            # show Y the X → item=X, target=Y
            target = (m.group(1) or "").strip()[:80]
            item = (m.group(2) or "").strip()[:80]
            if target in ("the", "a", "an"):
                target = ""
            if item in ("the", "a", "an"):
                item = ""
            return {
                "type": "show",
                "item": item,
                "target": target,
                "raw": (text or "").strip()[:240],
            }
        m = re.match(
            r"^(?:show|display|present)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "") or "").strip()[:80]
        if item in ("the", "a", "an", "to"):
            item = ""
        return {"type": "show", "item": item, "target": "", "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Search (2/4/5/6) + VagueGo + Answer — never dump room.desc.
    #   Search2 "There is nothing on <x1>."  Search4 "You find nothing of interest."
    #   Search5 "You can't see inside, since <x1> is/are closed."  Search6 "<x1> is/are empty."
    #   VagueGo "You'll have to say which compass direction to go in."
    #   Answer  "There is no reply."
    # Before the look branch on purpose: bare "search" matched \b(...|search|...)\b there and
    # returned {look} with no item -> _narrate_room dump. "look in|inside|into X" returned
    # {look, item:"in the crate"}. Both are the room-dump bug, not a Search.
    # Do NOT eat: research/searching/searched/rummaging, "look up" (read/consult),
    # "look under" (look_under), "go north"/"go out" (move), "answer <person>" (talk organ).
    if (
        re.match(r"^(search|rummage)(\b|$)", t)
        and not t.startswith(
            ("searching", "searched", "searcher", "searches", "rummaging", "rummaged")
        )
    ) or re.match(r"^look\s+(in|inside|into|through)(\b|$)", t):
        m = re.match(
            r"^(?:search|rummage|look\s+(?:in|inside|into|through))"
            r"(?:\s+(?:in|inside|into|through|for))?"
            r"(?:\s+(?:the|a|an))?\s*(.+)?$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        target = re.sub(r"^(?:the|a|an)\s+", "", target).strip()[:80]
        if target in (
            "the", "a", "an", "in", "inside", "into", "through", "for",
            "around", "here", "room", "everything",
        ):
            target = ""
        return {"type": "search", "target": target, "raw": (text or "").strip()[:240]}
    # VagueGo: exact bare motion tokens only. "go north" / "go out" / "go to the keep"
    # already reach the direction / leave / gate organs later and stay untouched.
    if t in (
        "go", "go on", "walk", "walk on", "head", "head on", "move", "move on",
        "travel", "proceed", "onward", "onwards", "forward", "keep going", "keep walking",
    ):
        return {"type": "vague_go", "raw": (text or "").strip()[:240]}
    # Answer: bare, or answering a non-person (yes/no/nothing/quoted line). A named
    # person keeps falling through to the talk organ ("answer mira" -> talk).
    m_ans = re.match(r"^(answer|reply|respond)\b(.*)$", t)
    if m_ans and not t.startswith(
        (
            "answered", "answering", "answers", "replied", "replying", "replies",
            "responded", "responding", "responds", "response", "responsible",
        )
    ):
        rest = (m_ans.group(2) or "").strip()
        rest = re.sub(r"^(?:to|with)\s+", "", rest).strip()
        bare = rest.strip("\"'“”.,!?").strip()
        if (
            not rest
            or rest.startswith(("\"", "'", "“"))
            or bare in (
                "yes", "y", "yeah", "yep", "no", "nope", "nah", "nothing",
                "anything", "something", "honestly", "truthfully", "it",
                "him", "her", "them", "the question",
            )
        ):
            return {"type": "answer", "raw": (text or "").strip()[:240]}
        # else: a named topic/person — leave it to the talk organ below.
    # Inform follow.inf (IF Archive) / Grammar-adjacent Follow soft floors.
    # Verb "follow" "chase" "pursue" "trail" → Follow; bare → Miscellany 48 whom;
    # noun in location → "No need!" (FollowSub). Mag has no follow_direction organ yet.
    # Do NOT steal: talk/ask mira; follower/following/followed/follows; Calcifer invent; room.desc.
    # Hang BEFORE talk catch-all so "follow mira" is not belted by mira keyword.
    m_follow = re.match(r"^(follow|chase|pursue|trail)\b(.*)$", t)
    if m_follow and not t.startswith(
        ("follower", "following", "followed", "follows", "chaseable", "pursued", "pursuit", "trailer", "trailing")
    ):
        rest = (m_follow.group(2) or "").strip()
        if rest.startswith("after "):
            rest = rest[6:].strip()
        elif rest == "after":
            rest = ""
        m_tgt = re.match(r"^(?:the\s+|a\s+|an\s+)?(.+)$", rest) if rest else None
        target = ((m_tgt.group(1) if m_tgt else "") or "").strip()[:80]
        if target in ("the", "a", "an", "after"):
            target = ""
        if not target:
            return {"type": "follow", "mode": "whom", "raw": (text or "").strip()[:240]}
        return {"type": "follow", "target": target, "raw": (text or "").strip()[:240]}
    # Inform Miscellany 48 / Ask soft floors — bare ask / ask about TOPIC were None
    # (or belt via talk) when no creature. Named-person Ask stays talk.
    # Do NOT steal: ask mira / ask the stranger (talk); ask the barkeep (rumor earlier);
    # ask for help (help earlier); ask for the key (leave talk); Burn (use/fire).
    # Never invent Calcifer on keep_gate; never dump room.desc.
    m_ask = re.match(r"^ask\b(.*)$", t)
    if m_ask and not t.startswith(
        ("asked", "asking", "asks", "askance", "askew", "askari")
    ):
        rest = (m_ask.group(1) or "").strip()
        if rest.startswith("for "):
            pass  # ask for help/key — help/talk organs
        elif (not rest) or rest.startswith("about"):
            return {"type": "ask", "mode": "whom", "raw": (text or "").strip()[:240]}
        # else: ask [the] NAME … → talk/rumor organs below
    # Inform DM4 §A4 Tell + Order + Exit + Eat — never dump room.desc / talk belt.
    #   Tell1 "You talk to yourself a while."  Tell2 "This provokes no reaction."
    #   Order "<x1> has/have better things to do."
    #   Exit1 "But you aren't in anything at the moment."
    #   Eat1 "That's/They're plainly inedible."
    # Ask soft floors hang above (bare / ask about only). Do NOT steal Burn (use/fire).
    # Do NOT break: "order a drink" (drink organ earlier), "tell me"/"tell mira" (talk),
    # "leave the tavern"/"go out" (move), enter/gate move.
    if re.match(r"^(tell)(\b|$)", t) and not t.startswith(
        ("telling", "teller", "tells", "telly", "telegram", "telephone", "teleport")
    ):
        # "tell me …" stays talk (Ask-ish). Named person → talk organ.
        if re.match(r"^tell\s+me\b", t):
            pass  # fall through to talk
        elif re.match(r"^tell\s+(?:the\s+)?[a-z][\w'-]*(?:\s+about\b.*)?$", t) and not re.match(
            r"^tell\s+about\b", t
        ):
            # tell <person> [about …] → talk organ below
            pass
        else:
            # bare tell / tell about <topic> / tell <scenery>
            m = re.match(r"^tell\s+(?:about\s+)?(?:the\s+|a\s+|an\s+)?(.+)$", t)
            target = ((m.group(1) if m else "") or "").strip()[:80]
            if target in ("the", "a", "an", "about"):
                target = ""
            return {"type": "tell", "target": target, "raw": (text or "").strip()[:240]}
    # Order: bare or "order <npc> [to …]". Drink already caught "order a …".
    if re.match(r"^(order)(\b|$)", t) and not t.startswith(
        ("ordering", "ordered", "orders", "orderly", "ordinal", "ordinary")
    ):
        if re.search(r"\border\s+a\b", t):
            pass  # drink path already returned, or fall through
        elif t == "order":
            return {"type": "order", "target": "", "raw": (text or "").strip()[:240]}
        else:
            m = re.match(
                r"^order\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+to\s+.+)?$",
                t,
            )
            target = ((m.group(1) if m else "") or "").strip()[:80]
            target = re.sub(r"^(?:the|a|an)\s+", "", target).strip()[:80]
            if target in ("the", "a", "an", "to"):
                target = ""
            return {
                "type": "order",
                "target": target,
                "raw": (text or "").strip()[:240],
            }
    # Eat — no edible organ yet; Eat1 for any noun; bare → Eat what?
    if re.match(r"^(eat|consume|devour|nibble|munch)(\b|$)", t) and not t.startswith(
        (
            "eating", "eaten", "eater", "eats", "eaves", "each",
            "consuming", "consumed", "devouring", "devoured",
            "nibbling", "nibbled", "munching", "munched",
        )
    ):
        if t in ("eat", "consume", "devour", "nibble", "munch"):
            return {"type": "eat", "item": "", "raw": (text or "").strip()[:240]}
        m = re.match(
            r"^(?:eat|consume|devour|nibble|munch)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "") or "").strip()[:80]
        if item in ("the", "a", "an"):
            item = ""
        return {"type": "eat", "item": item, "raw": (text or "").strip()[:240]}
    # Inform Standard Rules / WI §7.7: bare "listen" = listening to the location.
    # Default report: "You hear nothing unexpected." Bare listen was None →
    # table_turn long-IC talk belt. Never dump room.desc. Mag voice: hear / eavesdrop.
    # Accept "listen/hear/eavesdrop [to|at|for] <noun>" so "hear the gate" never
    # falls through to move (gate→north). Do not eat listener/listening alone.
    if re.match(r"^(listen|hear|eavesdrop)(\b|$)", t) and not t.startswith(
        ("listener", "listening", "hearsay", "hearing aid")
    ):
        m = re.match(
            r"^(?:listen|hear|eavesdrop)(?:\s+(?:to|at|for))?\s*(?:the\s+|a\s+|an\s+)?(.+)?$",
            t,
        )
        target = ((m.group(1) if m else "") or "").strip()[:80]
        if target in ("the", "a", "an", "to", "at", "for", "carefully", "closely", "hard"):
            # adverbs alone = bare room listen
            target = ""
        return {"type": "listen", "target": target, "raw": (text or "").strip()[:240]}
    # Evennia CmdHome (general.py): key=home; arg_regex=r"$".
    # Bare "home" was None → table_turn long-IC talk belt. Exact token only (no homesick).
    # Mag voice: go/head home (still not homeward/homework).
    if t == "home" or t in ("go home", "head home"):
        return {"type": "home", "raw": (text or "").strip()[:240]}
    if t in ("talk", "speak", "say"):
        return {"type": "talk", "raw": (text or "").strip()[:240]}
    if re.search(r"\b(howdy|hiya|greetings)\b", t):
        return {"type": "talk", "raw": (text or "").strip()[:240]}
    # Inform DM4 §A4 Burn — Grammar.h Verb 'burn' * noun / * noun 'with' noun → Burn.
    # Bare burn → Miscellany 49 incomplete. Burn+noun → completed Burn soft refuse.
    # Mag use/fire keeps: set fire / on fire / light the / torch the / set the X on fire.
    # Do NOT steal: use organ; light/torch idioms; Calcifer invent; room.desc dump.
    if re.match(r"^burn$", t):
        return {"type": "burn", "raw": (text or "").strip()[:240]}
    m_burn = re.match(
        r"^burn\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+with\s+(?:the\s+|a\s+|an\s+)?(.+))?$",
        t,
    )
    if m_burn:
        target = (m_burn.group(1) or "").strip()[:80]
        with_item = ((m_burn.group(2) or "") or "").strip()[:80]
        if target in ("the", "a", "an", "with"):
            target = ""
        if target:
            out = {"type": "burn", "target": target, "raw": (text or "").strip()[:240]}
            if with_item and with_item not in ("the", "a", "an"):
                out["with"] = with_item
            return out
    if re.search(r"\b(set fire|on fire|light the|torch the|set the .+ on fire)\b", t):
        return {"type": "use", "raw": (text or "").strip()[:240], "item": "fire"}
    # Inform Consult ("look up …"): must run BEFORE look/l/ls so "look up X" is not look(item=up X).
    if re.match(r"^look\s+up(\b|$)", t):
        m = re.match(
            r"^look\s+up\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "") or "").strip()[:80]
        if item in ("the", "a", "an", "up"):
            item = ""
        if " in " in item:
            item = item.split(" in ", 1)[0].strip()[:80]
        return {"type": "read", "item": item, "raw": (text or "").strip()[:240]}

    # Evennia CmdLook (general.py): key=look aliases=["l","ls"] arg_regex=r"\s|$".
    # Bare "l"/"ls" was None → table_turn long-IC talk belt. look/examine already apply.
    # Do not eat "look"/"listen"/"leave" — only exact l/ls or l/ls + space (arg_regex).
    m_l = re.match(r"^(l|ls)(?:\s+(?:at |the |a |an )?(.+))?$", t)
    if m_l:
        item = (m_l.group(2) or "").strip()[:80]
        if item and item not in ("around", "here", "room"):
            return {"type": "look", "item": item}
        return {"type": "look"}
    # Inform Grammar.h Verb 'examine' 'x//' 'watch' 'describe' 'check'
    # https://inform-fiction.org/source/library/Grammar/Grammar_3_4.html
    # Mag already maps examine/describe→look; bare x / x NOUN / watch|check were None
    # (and "x mira" wrongly hit talk). Hang on look organ only.
    # Do NOT steal: talk organ; use/fire; Calcifer invent; room.desc dump.
    m_x = re.match(r"^x(?:\s+(?:at |the |a |an )?(.+))?$", t)
    if m_x:
        item = (m_x.group(1) or "").strip()[:80]
        if item and item not in ("around", "here", "room"):
            return {"type": "look", "item": item}
        return {"type": "look"}
    m_watch_check = re.match(r"^(?:watch|check)(?:\s+(?:at |the |a |an )?(.+))?$", t)
    if m_watch_check:
        item = (m_watch_check.group(1) or "").strip()[:80]
        if item and item not in ("around", "here", "room"):
            return {"type": "look", "item": item}
        return {"type": "look"}
    if re.search(r"\b(look|where am i|describe|status|what do i see|examine|search|peer)\b", t):
        m = re.search(r"\b(?:look|examine|inspect|peer|describe|watch|check)\s+(?:at |the |a |an )?(.+)$", t)
        item = (m.group(1).strip()[:80] if m else "")
        if item and item not in ("around", "here", "room"):
            return {"type": "look", "item": item}
        return {"type": "look"}
    # In-world talk / ask NPC (must not fall through to curveball bathroom fails)
    if re.search(
        r"\b("
        r"why (are|is|do|does)|what (are|is|do|does)|who (are|is)|"
        r"how (are|is|do|does|come)|tell me|ask |talk to|speak to|say to|"
        r"polishing|barkeep|mira|hey |hello|howdy|hiya|good (eve|day|night)|"
        r"what('s| is) (that|this|the)"
        r")\b",
        t,
    ):
        out = {"type": "talk", "raw": (text or "").strip()[:240]}
        m = re.search(
            r"\b(?:talk|speak|say|ask)\s+(?:to\s+|with\s+)?(?:the\s+)?([a-z][\w'-]*)",
            t,
        )
        if m:
            cand = m.group(1)
            if cand not in ("to", "the", "a", "an", "me", "you"):
                out["target"] = cand
        return out
    if re.search(r"\b(rest|heal|camp|sleep)\b", t):
        return {"type": "rest"}
    if re.search(r"\b(attack|hit|fight|strike|kill|swing|stab|slash)\b", t):
        return {"type": "attack"}
    if re.search(r"\b(flee|run away|retreat)\b", t) and not re.search(r"\brun into\b", t):
        return {"type": "flee"}
    for d in (
        "north",
        "south",
        "east",
        "west",
        "up",
        "down",
        "left",
        "right",
        "deeper",
        "back",
        "out",
        "tavern",
    ):
        if re.search(rf"\b(go |move |head |walk |run )?(to )?{d}\b", t) or t.strip() == d:
            return {"type": "move", "direction": d}
    # Inform DM4 §A4 Consult / Lock / Unlock — never talk dump.
    # Consult: "You discover nothing of interest in <x1>."
    # Lock 1 / Unlock 1: "That doesn't seem to be something you can lock/unlock."
    # Bare read|unlock|lock were None → table_turn long-IC talk belt.
    # "lock the gate" was misparsed as move north (gate→keep heuristic). Handle BEFORE enter/gate.
    if re.match(r"^(read|consult)(\b|$)", t) or re.match(r"^look\s+up(\b|$)", t):
        if t.startswith(("ready", "reader", "readily", "readiness", "reading room")):
            pass  # fall through — not the read verb
        else:
            m = re.match(
                r"^(?:read|consult|look\s+up)\s+(?:the\s+|a\s+|an\s+)?(.+)$",
                t,
            )
            item = ((m.group(1) if m else "") or "").strip()[:80]
            if item in ("the", "a", "an", "up"):
                item = ""
            # "look up X in Y" — keep topic noun only (before " in ")
            if " in " in item:
                item = item.split(" in ", 1)[0].strip()[:80]
            return {"type": "read", "item": item, "raw": (text or "").strip()[:240]}
    if re.match(r"^unlock(\b|$)", t):
        m = re.match(
            r"^unlock\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "") or "").strip()[:80]
        if item in ("the", "a", "an", "with"):
            item = ""
        # drop trailing " with <key>" for short refuse path
        if " with " in item:
            item = item.split(" with ", 1)[0].strip()[:80]
        return {"type": "unlock", "item": item, "raw": (text or "").strip()[:240]}
    if re.match(r"^lock(\b|$)", t) and not t.startswith(
        ("locker", "locket", "locking", "locked out", "locksmith")
    ):
        m = re.match(
            r"^lock\s+(?:the\s+|a\s+|an\s+)?(.+)$",
            t,
        )
        item = ((m.group(1) if m else "") or "").strip()[:80]
        if item in ("the", "a", "an", "with", "up"):
            item = ""
        if " with " in item:
            item = item.split(" with ", 1)[0].strip()[:80]
        return {"type": "lock", "item": item, "raw": (text or "").strip()[:240]}

    if re.search(r"\b(enter|gate|to the keep|inside|through the (gate|door))\b", t):
        return {"type": "move", "direction": "north"}
    if re.search(r"\b(fight (a |some )?|go (fight|hunt)|find (a )?monster|random fight)\b", t):
        return {"type": "seek_fight"}
    m_act = re.search(r"\b(cast|summon|call)\s+(?:the\s+|a\s+|an\s+)?(.+)$", t)
    if m_act:
        return {
            "type": "act",
            "raw": (text or "").strip()[:240],
            "verb": m_act.group(1),
            "target": (m_act.group(2) or "").strip()[:80],
        }
    return None


# ── REPRINT (2026-09-29, W3D — ledger return 11/24 improvement) ──────────────
# Death as interagent hand-off: on status==defeated, fold the death as a
# verkle knot (rib_bus.publish_rib — the same fold idiom dungeon_dev.conquer
# uses), harvest salvage (honest temple:/slain:/door_open: flags + inventory
# kept; cheat:/nuke: dropped; the rest folded into the knot, never silently
# lost), re-seat the named actor from CHAR_DIR with hp restored and
# reprint_n+1, then pass the salvage off to the module handler if one is
# registered (_MODULE_HANDLERS — the water remembers). Receipts ride the two
# live patterns: party_subchain.append (game_campaign.py:2957 idiom) +
# training_events.emit (game_campaign.py:2790 idiom).

_SALVAGE_KEEP_PREFIXES = ("temple:", "slain:", "door_open:")
_SALVAGE_DROP_PREFIXES = ("cheat:", "nuke:")
_SALVAGE_DROP_EXACT = ("cheat", "scorched")  # water_computer.cheated/scorched semantics


def _salvage_split(flags: list[str] | None) -> tuple[list[str], list[str], list[str]]:
    """Split flags into (kept, dropped, folded). Kept carry to the clone;
    dropped are cheats; folded are honest but module-scoped — recorded in
    the knot, not carried."""
    kept: list[str] = []
    dropped: list[str] = []
    folded: list[str] = []
    for f in flags or []:
        s = str(f)
        low = s.lower()
        if low.startswith(_SALVAGE_DROP_PREFIXES) or low in _SALVAGE_DROP_EXACT:
            dropped.append(s)
        elif low.startswith(_SALVAGE_KEEP_PREFIXES):
            kept.append(s)
        else:
            folded.append(s)
    return kept, dropped, folded


def _char_sheet_path(name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "x").lower())
    return CHAR_DIR / f"{slug}.json"


def reprint(dead_campaign_id: str) -> dict[str, Any]:
    """Reprint a defeated campaign: harvest the corpse, seat the next clone.

    Only status==defeated reprints. Live, sealed or already-reprinted
    campaigns are refused — reprint is a death rite, not a save-scum.
    """
    old = load_campaign(dead_campaign_id)
    if not old:
        return {"ok": False, "error": f"missing campaign {dead_campaign_id}"}
    status = str(old.get("status") or "")
    if status != "defeated":
        return {
            "ok": False,
            "error": f"refused: campaign {dead_campaign_id} is {status or 'statusless'}, not defeated",
            "status": status,
            "refused": True,
        }

    # 1. Salvage harvest — what the corpse carries is the hand-off cargo.
    kept, dropped, folded = _salvage_split(list(old.get("flags") or []))
    dead_player = dict(old.get("player") or {})
    name = str(dead_player.get("name") or "")
    salvage_inventory = [
        str(i) for i in (dead_player.get("inventory") or [])
    ]

    # 2. Re-seat the named actor from CHAR_DIR (sheet persisted by
    #    set_character); the sheet is the actor's source of truth, the
    #    corpse only if no sheet survived.
    sheet: dict[str, Any] = {}
    sp = _char_sheet_path(name or "x")
    if name and sp.is_file():
        try:
            sheet = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            sheet = {}
    player = dict(sheet.get("player") or dead_player)
    player["name"] = name or str(player.get("name") or "Adventurer")
    player["inventory"] = salvage_inventory or list(player.get("inventory") or [])
    hp_max = int(player.get("hp_max") or 10)
    player["hp"] = hp_max
    n = int(old.get("reprint_n") or 0) + 1

    # 3. The clone: same module/world, honest flags only, encounter cleared.
    new: dict[str, Any] = {
        "schema": SCHEMA,
        "campaign_id": _cid(),
        "ts": _utc(),
        "voice_session_id": str(old.get("voice_session_id") or ""),
        "module_id": old.get("module_id"),
        "module_title": old.get("module_title"),
        "status": "active",
        "room_id": old.get("room_id"),
        "player": player,
        "encounter": None,
        "flags": list(dict.fromkeys(kept)),
        "reprint_n": n,
        "reprint_of": dead_campaign_id,
        "storyteller": {"threat_budget": 2, "days_since_crisis": 0},
        "log": [
            {
                "ts": _utc(),
                "type": "reprint",
                "text": (
                    f"{player['name']} falls in {old.get('room_id')} and is reprinted "
                    f"(reprint_n {n}, from campaign {dead_campaign_id}). "
                    f"Salvage kept: {', '.join(kept) or 'nothing'}; "
                    f"cheats dropped: {', '.join(dropped) or 'none'}."
                ),
            }
        ],
        "module_snapshot": old.get("module_snapshot") or {},
    }

    # 4. Per-module pass-off (the water remembers): a registered handler may
    #    fold salvage into module state. Unknown atypes return handled:False.
    pass_off: dict[str, Any] = {"handled": False}
    handler = _module_handler(str(old.get("module_id") or ""))
    if handler:
        try:
            pass_off = handler(
                new,
                {"type": "reprint", "salvage": {"flags": kept, "inventory": salvage_inventory}},
                atype="reprint",
                raw=f"reprint {dead_campaign_id}",
            ) or {"handled": False}
            ev = [str(e) for e in (pass_off.get("events") or [])]
            if ev:
                new["log"].append({"ts": _utc(), "type": "reprint", "text": " ".join(ev)})
        except Exception as e:  # noqa: BLE001 — pass-off must never kill the reprint
            pass_off = {"handled": False, "error": str(e)[:140]}

    # 5. Fold the death as a verkle knot (dungeon_dev.conquer idiom).
    knot: dict[str, Any] = {}
    try:
        from mag import rib_bus

        knot = rib_bus.publish_rib(
            f"[DEATH FILED] campaign {dead_campaign_id}: {player['name']} falls at "
            f"'{old.get('room_id')}'. Salvage kept {kept}; cheat dropped {dropped}; "
            f"folded-not-carried {folded}. Clone {new['campaign_id']} seated at reprint_n {n}.",
            domain="game_reprint",
            source="game_campaign.reprint",
            target_rank="T1",
        )
    except Exception as e:  # noqa: BLE001
        knot = {"ok": False, "error": str(e)[:140]}

    # 6. File the corpse, seat the clone, advance the character sheet.
    old["status"] = "reprinted"
    old["reprinted_to"] = new["campaign_id"]
    old["log"] = list(old.get("log") or []) + [
        {
            "ts": _utc(),
            "type": "reprint",
            "text": f"Death filed as a knot. Clone {new['campaign_id']} carries the salvage (reprint_n {n}).",
        }
    ]
    save_campaign(old)
    save_campaign(new)
    try:
        CHAR_DIR.mkdir(parents=True, exist_ok=True)
        sp.write_text(
            json.dumps(
                {
                    "player": player,
                    "campaign_id": new["campaign_id"],
                    "reprint_n": n,
                    "ts": _utc(),
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    # 7. Receipt rows — the two live patterns (party_subchain + training_events).
    try:
        from mag.party_subchain import append as _ps

        _ps(
            seat="table",
            ok=True,
            move=f"reprint {dead_campaign_id} -> {new['campaign_id']} (n={n})",
            kind="reprint",
            extra={"kept_flags": kept, "dropped_flags": dropped},
        )
    except Exception:
        try:
            from mag.steer import emit as _steer

            _steer("game", "table", f"reprint {dead_campaign_id}", steer_back=False)
        except Exception:
            pass
    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={
                "campaign_id": str(new["campaign_id"]),
                "kind": "reprint",
                "from_campaign": dead_campaign_id,
            },
            input_data={"reprint": dead_campaign_id, "actor": player["name"]},
            action={"reprint": True, "campaign_id": dead_campaign_id},
            outcome={
                "reprint_n": n,
                "kept_flags": len(kept),
                "dropped_flags": len(dropped),
                "folded_flags": len(folded),
            },
            pattern_tags=["game", "reprint", "death_salvage", "verkle_knot"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass

    speak = (
        f"{player['name']} falls — and is reprinted. Clone {new['campaign_id']} "
        f"(reprint {n}) stands at HP {player['hp']}/{hp_max}. "
        f"Salvage kept: {', '.join(kept) or 'nothing'}; cheats dropped: {', '.join(dropped) or 'none'}. "
        f"The death is filed as a knot; the next clone inherits the map."
    )
    return {
        "ok": True,
        "campaign_id": new["campaign_id"],
        "reprint_n": n,
        "reprint_of": dead_campaign_id,
        "kept_flags": kept,
        "dropped_flags": dropped,
        "folded_flags": folded,
        "inventory": player["inventory"],
        "knot": knot,
        "pass_off": pass_off,
        "campaign": new,
        "speak": speak,
        "narrate": speak,
    }


def _cli(argv: list[str] | None = None) -> int:
    """CLI verb: python -m mag.game_campaign reprint <campaign_id>"""
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = (argv[0].strip().lower() if argv else "")
    if verb == "reprint" and len(argv) >= 2:
        out = reprint(argv[1])
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    print("usage: python -m mag.game_campaign reprint <campaign_id>")
    return 2


def seal_session(
    *,
    session_id: str = "",
    campaign_id: str = "",
    tldr: str = "",
) -> dict[str, Any]:
    """DM post-game notes — FILE session card for train/exploit review."""
    camp = load_campaign(campaign_id) if campaign_id else None
    if not camp and session_id:
        camp = latest_for_session(session_id)
    if not camp:
        return {"ok": False, "error": "no campaign to seal"}
    st = camp.get("storyteller") or {}
    turn_n = int(st.get("turn_n") or len(camp.get("log") or []))
    fast_n = int(st.get("fast_turns") or turn_n)
    slow_n = int(st.get("slow_turns") or 0)
    card = {
        "schema": "mag_game_session_seal.v1",
        "ts": _utc(),
        "campaign_id": camp.get("campaign_id"),
        "voice_session_id": camp.get("voice_session_id") or session_id,
        "module_id": camp.get("module_id"),
        "module_title": camp.get("module_title"),
        "room_id": camp.get("room_id"),
        "status": camp.get("status"),
        "player": camp.get("player"),
        "flags": camp.get("flags"),
        "metrics": {
            "turn_n": turn_n,
            "fast_turns": fast_n,
            "slow_turns": slow_n,
            "local_only_pct": round(100.0 * fast_n / max(1, fast_n + slow_n), 1),
        },
        "log_tail": (camp.get("log") or [])[-12:],
        "tldr": (tldr or "")[:500]
        or f"Sealed at {camp.get('room_id')} after ~{turn_n} turns.",
        "dogfood_dm": True,
        "transfer_checklist": [
            "default_local_engine",
            "pack_then_guest",
            "confirm_before_write",
            "file_outcomes",
            "hub_return",
        ],
    }
    out_dir = ROOT / "memory" / "working" / "game_sessions"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"seal_{camp.get('campaign_id')}_{_utc()[:19].replace(':', '')}.json"
    path = out_dir / fname
    path.write_text(json.dumps(card, indent=2, default=str), encoding="utf-8")
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={"campaign_id": str(camp.get("campaign_id")), "kind": "seal"},
            action={"seal": True, "path": rel},
            outcome=card["metrics"],
            pattern_tags=["game", "seal", "dogfood_dm", "dm_transfer"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass
    speak = (
        f"Session sealed ({rel}). "
        f"Turns {turn_n}; fast {fast_n}; slow/guest {slow_n}; "
        f"local-only ~{card['metrics']['local_only_pct']}%. "
        f"DM drill: name which Mag seat fired. See docs/ref/DM_MAG_TRANSFER.md"
    )
    return {"ok": True, "path": rel, "card": card, "speak": speak, "narrate": speak}


def handle_game(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or "status").strip().lower()
    sid = str(body.get("session_id") or "")
    if action in ("modules", "list_modules"):
        return {"ok": True, "modules": list_modules()}
    if action in ("seal", "seal_session", "end_session"):
        return seal_session(
            session_id=sid,
            campaign_id=str(body.get("campaign_id") or ""),
            tldr=str(body.get("tldr") or body.get("text") or ""),
        )
    if action in ("start", "new", "classic", "play"):
        return begin_play(
            module_id=str(body.get("module") or body.get("module_id") or "classic"),
            voice_session_id=sid,
            force_new=bool(body.get("force_new") or action == "new"),
        )
    if action in ("character", "set_character"):
        cid = str(body.get("campaign_id") or "")
        if not cid:
            c = latest_for_session(sid)
            cid = str((c or {}).get("campaign_id") or "")
        player = body.get("player") if isinstance(body.get("player"), dict) else parse_character(
            str(body.get("text") or "")
        )
        if not player:
            return {"ok": False, "error": "could not parse character", "need_character": True}
        return set_character(cid, player)
    if action in ("state", "status"):
        c = load_campaign(str(body.get("campaign_id") or "")) or latest_for_session(sid)
        if not c:
            return {"ok": False, "error": "no campaign"}
        return {
            "ok": True,
            "campaign_id": c.get("campaign_id"),
            "status": c.get("status"),
            "scene_context": scene_context(c) if c.get("player") else None,
            "speak": _narrate_room(c) if c.get("player") else "Need character.",
            "legal": list_legal_actions(c) if c.get("player") else [],
        }
    if action in ("act", "apply", "do"):
        c = load_campaign(str(body.get("campaign_id") or "")) or latest_for_session(sid)
        if not c:
            return {"ok": False, "error": "no campaign"}
        act = body.get("move") or body.get("act")
        if isinstance(act, str):
            act = parse_player_speech(act) or {"type": act}
        if not act and body.get("text"):
            act = parse_player_speech(str(body.get("text")))
        return apply_action(str(c["campaign_id"]), act if isinstance(act, dict) else {})
    return {"ok": False, "error": f"unknown action {action}"}


if __name__ == "__main__":
    raise SystemExit(_cli())
