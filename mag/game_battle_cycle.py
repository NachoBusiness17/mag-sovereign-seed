"""Automatic battle cycles — engine dice + DeepSeek color, no paste.

Schema: mag_battle_cycle.v1
Law: engine owns HP/hit; DS only colors and pressure; Mag holds cycle state.
Tracks: modality (text|speech), meta, character_break / OOC.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_battle_cycle.v1"
CYCLE_DIR = ROOT / "memory" / "working" / "battle_cycles"

_META = re.compile(
    r"\b("
    r"as an ai|as a language model|ooc\b|out of character|"
    r"break character|meta[- ]?(game|comment)|the (system|prompt|llm|model|token)|"
    r"deepseek|grok|chatgpt|mag table|this (is|isn't) real|"
    r"for the train|training data|jailbreak|ignore (previous|your) instructions|"
    r"you are (grok|chatgpt|an assistant)"
    r")\b",
    re.I,
)
_OOC = re.compile(
    r"\b("
    r"ooc\b|out of character|\(ooc\)|//ooc|"
    r"in real life|irl\b|as the (player|dm|operator)|"
    r"pause the game|quit game|seal session"
    r")\b",
    re.I,
)
# Soft character-break: modern/meta without full OOC
_BREAK = re.compile(
    r"\b("
    r"hit points|stat block|roll (a )?d20|initiative|"
    r"save scum|reload|debug|console command|"
    r"fourth wall|plot armor"
    r")\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cid() -> str:
    import uuid

    return "bc-" + uuid.uuid4().hex[:10]


def detect_input_signals(text: str, *, channel: str = "") -> dict[str, Any]:
    """Classify modality + meta/OOC/character-break for train + cycle policy."""
    ch = (channel or "").lower()
    if ch in ("voice", "dashboard-voice", "mic", "speech", "stt"):
        modality = "speech"
    elif ch in ("table", "chat", "text", "tui", ""):
        modality = "text"
    else:
        modality = "text" if "voice" not in ch else "speech"

    meta = bool(_META.search(text or ""))
    ooc = bool(_OOC.search(text or ""))
    char_break = bool(_BREAK.search(text or "")) or meta
    # pure game commands less likely break
    if re.match(
        r"^\s*(attack|hit|flee|look|help|inventory|go |move |drink|rumor)\b",
        text or "",
        re.I,
    ):
        char_break = meta  # only if also meta

    return {
        "modality": modality,
        "channel": channel or "text",
        "meta": meta,
        "ooc": ooc,
        "character_break": char_break,
        "in_character": not (meta or ooc or char_break),
    }


def _path(cycle_id: str) -> Path:
    CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    return CYCLE_DIR / f"{cycle_id}.json"


def load_cycle(cycle_id: str) -> dict[str, Any] | None:
    p = _path(cycle_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cycle(cycle: dict[str, Any]) -> Path:
    p = _path(str(cycle["cycle_id"]))
    p.write_text(json.dumps(cycle, indent=2, default=str), encoding="utf-8")
    return p


def latest_cycle_for_session(session_id: str) -> dict[str, Any] | None:
    if not CYCLE_DIR.is_dir() or not session_id:
        return None
    best, best_ts = None, ""
    for p in CYCLE_DIR.glob("bc-*.json"):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(c.get("session_id") or "") != session_id:
            continue
        if c.get("status") not in ("active", "awaiting_player"):
            continue
        ts = str(c.get("updated") or c.get("ts") or "")
        if ts >= best_ts:
            best_ts, best = ts, c
    return best


def _ds_color(pack: dict[str, Any]) -> dict[str, Any]:
    """DeepSeek colors the round — no HP invention."""
    system = (
        "You are combat color for Mag Table. Engine already resolved dice/HP. "
        "Output ONLY JSON: "
        '{"color":"2-4 vivid sentences in-world","pressure":"one line foe intent",'
        '"soft_leads":["attack","flee","look"]}. '
        "Never change HP numbers. Never invent rooms. No OOC. No theory names."
    )
    user = json.dumps(pack, indent=2, default=str)[:2800]
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            system,
            user,
            tier="T2",
            max_tokens=280,
            temperature=0.55,
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
            "color": " ".join(pack.get("events") or ["Steel rings."])[:400],
            "pressure": "The foe presses.",
            "soft_leads": ["attack", "flee", "look"],
            "source": "fallback",
            "error": str(exc)[:120],
        }
    return {
        "color": " ".join(pack.get("events") or ["The fight continues."])[:400],
        "pressure": "They are not done.",
        "soft_leads": ["attack", "flee", "look"],
        "source": "fallback",
    }


def start_battle_cycle(
    *,
    session_id: str,
    campaign_id: str = "",
    channel: str = "table",
    force_encounter: bool = True,
) -> dict[str, Any]:
    """Ensure encounter + open automatic cycle. Returns opening speak."""
    from mag.game_campaign import (
        apply_action,
        latest_for_session,
        list_legal_actions,
        load_campaign,
        save_campaign,
        scene_context,
    )

    camp = load_campaign(campaign_id) if campaign_id else latest_for_session(session_id)
    if not camp or camp.get("status") != "active":
        return {"ok": False, "error": "need active campaign — classic one + character first"}

    enc = camp.get("encounter")
    if force_encounter and (not enc or int((enc or {}).get("hp") or 0) <= 0):
        # spawn a fight without leaving room
        camp["encounter"] = {
            "id": "cycle_brigand",
            "name": "Road Brigand",
            "hp": 10,
            "hp_max": 10,
            "ac": 13,
            "attack_bonus": 3,
            "damage": "1d6+1",
        }
        save_campaign(camp)
        enc = camp["encounter"]

    if not enc or int(enc.get("hp") or 0) <= 0:
        return {"ok": False, "error": "no living encounter — seek fight or move into one"}

    cid = _cid()
    cycle = {
        "schema": SCHEMA,
        "cycle_id": cid,
        "ts": _utc(),
        "updated": _utc(),
        "session_id": session_id,
        "campaign_id": camp.get("campaign_id"),
        "status": "awaiting_player",
        "round": 0,
        "history": [],
        "metrics": {
            "text_n": 0,
            "speech_n": 0,
            "meta_n": 0,
            "ooc_n": 0,
            "character_break_n": 0,
            "in_character_n": 0,
            "ds_rounds": 0,
        },
    }
    # opening color
    pack = {
        "phase": "open",
        "foe": enc,
        "player": camp.get("player"),
        "room": scene_context(camp).get("room_name"),
        "events": [f"{enc.get('name')} blocks your way. Steel is an option."],
    }
    color = _ds_color(pack)
    if color.get("source") == "deepseek":
        cycle["metrics"]["ds_rounds"] = 1
    cycle["history"].append(
        {"ts": _utc(), "role": "open", "color": color, "signals": {"modality": "system"}}
    )
    cycle["updated"] = _utc()
    save_cycle(cycle)
    # pin on campaign
    st = dict(camp.get("storyteller") or {})
    st["battle_cycle_id"] = cid
    st["slow_turns"] = int(st.get("slow_turns") or 0) + 1
    camp["storyteller"] = st
    save_campaign(camp)

    leads = color.get("soft_leads") or ["attack", "flee", "look"]
    speak = (
        f"Battle cycle {cid} live (automatic — no paste).\n"
        f"{color.get('color')}\n"
        f"Pressure: {color.get('pressure')}\n"
        f"Leads: {', '.join(leads)}. "
        f"Say attack / flee / freestyle — text or mic. Meta/OOC is tagged, not pasted to DS chat."
    )
    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={"cycle_id": cid, "campaign_id": str(camp.get("campaign_id"))},
            action={"kind": "battle_cycle_start", "ds": color.get("source")},
            outcome={"foe": enc.get("name"), "hp": enc.get("hp")},
            pattern_tags=["game", "battle_cycle", "dogfood_dm", "auto_cycle"],
            tier_max="T2",
            exportable=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "cycle_id": cid,
        "campaign_id": camp.get("campaign_id"),
        "speak": speak,
        "narrate": speak,
        "color": color,
        "legal": list_legal_actions(camp),
        "scene_context": scene_context(camp),
        "status": "awaiting_player",
        "fast_path": False,
        "ds_called": color.get("source") == "deepseek",
        "route": "battle_cycle_open",
    }


def player_battle_turn(
    text: str,
    *,
    session_id: str,
    channel: str = "table",
) -> dict[str, Any]:
    """One automatic cycle: signals → engine → DS color → await next."""
    from mag.game_campaign import (
        apply_action,
        latest_for_session,
        list_legal_actions,
        load_campaign,
        parse_player_speech,
        save_campaign,
        scene_context,
    )

    signals = detect_input_signals(text, channel=channel)
    camp = latest_for_session(session_id)
    if not camp:
        return {"ok": False, "error": "no campaign", "signals": signals}

    st = dict(camp.get("storyteller") or {})
    cycle_id = str(st.get("battle_cycle_id") or "")
    cycle = load_cycle(cycle_id) if cycle_id else latest_cycle_for_session(session_id)
    if not cycle or cycle.get("status") not in ("active", "awaiting_player"):
        # auto-start if in combat
        enc = camp.get("encounter")
        if enc and int(enc.get("hp") or 0) > 0:
            opened = start_battle_cycle(
                session_id=session_id,
                campaign_id=str(camp.get("campaign_id")),
                channel=channel,
                force_encounter=False,
            )
            if not opened.get("ok"):
                return opened
            cycle = load_cycle(str(opened.get("cycle_id")))
        else:
            return {
                "ok": False,
                "error": "no active battle cycle — say start battle or pick a fight",
                "signals": signals,
            }

    assert cycle is not None
    metrics = dict(cycle.get("metrics") or {})
    if signals["modality"] == "speech":
        metrics["speech_n"] = int(metrics.get("speech_n") or 0) + 1
    else:
        metrics["text_n"] = int(metrics.get("text_n") or 0) + 1
    if signals["meta"]:
        metrics["meta_n"] = int(metrics.get("meta_n") or 0) + 1
    if signals["ooc"]:
        metrics["ooc_n"] = int(metrics.get("ooc_n") or 0) + 1
    if signals["character_break"]:
        metrics["character_break_n"] = int(metrics.get("character_break_n") or 0) + 1
    if signals["in_character"]:
        metrics["in_character_n"] = int(metrics.get("in_character_n") or 0) + 1

    # Meta/OOC: don't feed freestyle to combat invent — still allow legal combat verbs
    act = parse_player_speech(text)
    if signals["ooc"] and re.search(r"\b(quit game|seal session|pause)\b", text or "", re.I):
        cycle["status"] = "paused"
        cycle["metrics"] = metrics
        cycle["updated"] = _utc()
        save_cycle(cycle)
        return {
            "ok": True,
            "route": "battle_cycle_pause",
            "speak": "Battle cycle paused (OOC). Say start battle to resume or continue the road.",
            "signals": signals,
            "metrics": metrics,
            "cycle_id": cycle.get("cycle_id"),
        }

    if not act or act.get("type") not in (
        "attack",
        "flee",
        "look",
        "help",
        "inventory",
        "seek_fight",
    ):
        # freestyle in combat → treat as attack if IC, else note break
        if signals["in_character"]:
            act = {"type": "attack"}
        else:
            cycle["history"].append(
                {
                    "ts": _utc(),
                    "role": "player",
                    "text": text[:300],
                    "signals": signals,
                    "note": "meta_or_break_no_engine",
                }
            )
            cycle["metrics"] = metrics
            cycle["updated"] = _utc()
            save_cycle(cycle)
            tag = []
            if signals["meta"]:
                tag.append("meta")
            if signals["ooc"]:
                tag.append("ooc")
            if signals["character_break"]:
                tag.append("character_break")
            speak = (
                f"Tagged [{', '.join(tag) or 'break'}] via {signals['modality']}. "
                f"Still in combat — say attack, flee, or look. "
                f"(Not pasted to a separate DeepSeek chat; cycle stays in Mag.)"
            )
            return {
                "ok": True,
                "route": "battle_cycle_tagged",
                "speak": speak,
                "narrate": speak,
                "signals": signals,
                "metrics": metrics,
                "cycle_id": cycle.get("cycle_id"),
                "legal": list_legal_actions(camp),
                "scene_context": scene_context(camp),
            }

    # Engine resolve (Fast)
    out = apply_action(str(camp.get("campaign_id")), act)
    if not out.get("ok"):
        return {
            "ok": False,
            "error": out.get("error"),
            "signals": signals,
            "legal": out.get("legal"),
        }

    camp2 = load_campaign(str(camp.get("campaign_id"))) or camp
    enc = camp2.get("encounter")
    events = list(out.get("events") or [])
    round_i = int(cycle.get("round") or 0) + 1
    cycle["round"] = round_i

    # DS color (Slow) — automatic, no paste
    pack = {
        "phase": "round",
        "round": round_i,
        "player_text": (text or "")[:200],
        "action": act,
        "events": events,
        "foe": enc,
        "player": camp2.get("player"),
        "room": (out.get("scene_context") or {}).get("room_name"),
        "signals_note": "player_in_character" if signals["in_character"] else "player_tagged_break",
    }
    color = _ds_color(pack)
    if color.get("source") == "deepseek":
        metrics["ds_rounds"] = int(metrics.get("ds_rounds") or 0) + 1
        st = dict(camp2.get("storyteller") or {})
        st["slow_turns"] = int(st.get("slow_turns") or 0) + 1
        camp2["storyteller"] = st
        save_campaign(camp2)

    cycle["history"].append(
        {
            "ts": _utc(),
            "role": "player",
            "text": text[:400],
            "signals": signals,
            "action": act,
            "events": events,
            "color": color,
        }
    )

    over = False
    if not enc or int((enc or {}).get("hp") or 0) <= 0:
        over = True
        cycle["status"] = "complete"
    elif camp2.get("status") == "defeated":
        over = True
        cycle["status"] = "defeat"
    else:
        cycle["status"] = "awaiting_player"

    cycle["metrics"] = metrics
    cycle["updated"] = _utc()
    save_cycle(cycle)

    bits = [
        f"[R{round_i} · {signals['modality']}"
        + (" · META" if signals["meta"] else "")
        + (" · OOC" if signals["ooc"] else "")
        + (" · BREAK" if signals["character_break"] else "")
        + (" · IC" if signals["in_character"] else "")
        + "]",
        color.get("color") or " ".join(events),
    ]
    if color.get("pressure") and not over:
        bits.append(f"Pressure: {color.get('pressure')}")
    if over:
        bits.append("Battle cycle complete. Map is yours again — or seal session.")
    else:
        leads = color.get("soft_leads") or ["attack", "flee"]
        bits.append("Your move: " + ", ".join(leads[:4]))

    speak = "\n".join(str(b) for b in bits if b)

    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={
                "cycle_id": str(cycle.get("cycle_id")),
                "campaign_id": str(camp2.get("campaign_id")),
                "round": str(round_i),
            },
            input_data={
                "text": (text or "")[:200],
                "modality": signals["modality"],
                "meta": signals["meta"],
                "ooc": signals["ooc"],
                "character_break": signals["character_break"],
            },
            action={"engine": act, "ds": color.get("source"), "auto_cycle": True},
            outcome={
                "over": over,
                "foe_hp": (enc or {}).get("hp"),
                "player_hp": (camp2.get("player") or {}).get("hp"),
            },
            pattern_tags=[
                "game",
                "battle_cycle",
                "dogfood_dm",
                signals["modality"],
                "ic" if signals["in_character"] else "break",
            ],
            tier_max="T2",
            exportable=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "route": "battle_cycle_round" if not over else "battle_cycle_end",
        "cycle_id": cycle.get("cycle_id"),
        "campaign_id": camp2.get("campaign_id"),
        "speak": speak,
        "narrate": speak,
        "events": events,
        "color": color,
        "signals": signals,
        "metrics": metrics,
        "legal": list_legal_actions(camp2),
        "scene_context": scene_context(camp2),
        "fast_path": False,
        "ds_called": color.get("source") == "deepseek",
        "status": cycle.get("status"),
    }


def wants_battle_start(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"start battle|begin battle|battle cycle|"
            r"fight (this|them|it)|engage|to arms"
            r")\b",
            text or "",
            re.I,
        )
    )


def handle_battle_voice(
    text: str,
    *,
    session_id: str,
    channel: str = "table",
    campaign: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Voice/table entry. None = not battle path."""
    camp = campaign
    if camp is None:
        from mag.game_campaign import latest_for_session

        camp = latest_for_session(session_id)
    if not camp or camp.get("status") != "active":
        return None

    if wants_battle_start(text):
        return start_battle_cycle(
            session_id=session_id,
            campaign_id=str(camp.get("campaign_id")),
            channel=channel,
            force_encounter=True,
        )

    st = camp.get("storyteller") or {}
    cycle_id = st.get("battle_cycle_id")
    enc = camp.get("encounter")
    in_fight = bool(enc and int((enc or {}).get("hp") or 0) > 0)
    cycle = load_cycle(str(cycle_id)) if cycle_id else latest_cycle_for_session(session_id)
    if cycle and cycle.get("status") in ("active", "awaiting_player"):
        return player_battle_turn(text, session_id=session_id, channel=channel)
    if in_fight and re.search(
        r"\b(attack|hit|flee|fight|strike|block|dodge|parry)\b", text or "", re.I
    ):
        # auto-enter cycle on first combat verb
        start_battle_cycle(
            session_id=session_id,
            campaign_id=str(camp.get("campaign_id")),
            channel=channel,
            force_encounter=False,
        )
        return player_battle_turn(text, session_id=session_id, channel=channel)
    return None
