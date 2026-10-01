"""Salon advise loop — local parse · frontier guest · clarify · confirm · output.

Schema: mag_game_salon.v1
Law: frontier advises only; engine applies only after confirm.
     Pack + scene, never full chat novel.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_game_salon.v1"
PENDING_DIR = ROOT / "memory" / "working" / "salon_pending"

_ASK = re.compile(
    r"\b("
    r"what should i (do|say)|what do i do|advise me|ask (the )?(guest|advisor|salon)|"
    r"guest opinion|salon|counsel|what now\?|options\?"
    r")\b",
    re.I,
)
_SURPRISE = re.compile(r"\b(surprise me|just pick|you choose|auto)\b", re.I)
_CONFIRM = re.compile(
    r"\b("
    r"take (?P<id>[a-dA-D1-4])|"
    r"option (?P<id2>[a-dA-D1-4])|"
    r"pick (?P<id3>[a-dA-D1-4])|"
    r"go with (?P<id4>[a-dA-D1-4])|"
    r"confirm (?P<id5>[a-dA-D1-4])|"
    r"(?P<id6>[a-dA-D])\b|"
    r"ignore (the )?guest|never ?mind|just paint|no advice"
    r")\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid() -> str:
    return "sa-" + uuid.uuid4().hex[:10]


def wants_advice(text: str) -> bool:
    return bool(_ASK.search(text or ""))


def wants_surprise(text: str) -> bool:
    return bool(_SURPRISE.search(text or ""))


def parse_confirm(text: str) -> dict[str, Any] | None:
    t = text or ""
    if re.search(r"\b(ignore (the )?guest|never ?mind|just paint|no advice)\b", t, re.I):
        return {"kind": "reject"}
    m = _CONFIRM.search(t)
    if not m:
        # bare "a" / "1" / "option a"
        m2 = re.match(r"^\s*([a-dA-D1-4])\s*$", t)
        if m2:
            return {"kind": "pick", "option_id": _norm_opt(m2.group(1))}
        return None
    if re.search(r"ignore|never|just paint|no advice", t, re.I):
        return {"kind": "reject"}
    for g in ("id", "id2", "id3", "id4", "id5", "id6"):
        if m.groupdict().get(g):
            return {"kind": "pick", "option_id": _norm_opt(m.group(g))}
    return None


def _norm_opt(s: str) -> str:
    s = (s or "a").strip().lower()
    if s.isdigit():
        return chr(ord("a") + int(s) - 1) if s in "1234" else "a"
    return s[:1] if s else "a"


def _pending_path(session_id: str) -> Path:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "", session_id or "anon")[:48] or "anon"
    return PENDING_DIR / f"{safe}.json"


def load_pending(session_id: str) -> dict[str, Any] | None:
    p = _pending_path(session_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_pending(session_id: str, card: dict[str, Any]) -> Path:
    p = _pending_path(session_id)
    p.write_text(json.dumps(card, indent=2, default=str), encoding="utf-8")
    return p


def clear_pending(session_id: str) -> None:
    p = _pending_path(session_id)
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            pass


def build_intention_card(
    *,
    campaign: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    from mag.game_campaign import list_legal_actions, scene_context

    sc = scene_context(campaign) if campaign.get("player") else {}
    legal = list_legal_actions(campaign) if campaign.get("player") else []
    return {
        "schema": "mag_salon_intention.v1",
        "act": "ask_advice",
        "player_text": (text or "")[:400],
        "scene": {
            "room": sc.get("room_name"),
            "desc": (sc.get("room_desc") or "")[:200],
            "hook": sc.get("hook"),
            "exits": sc.get("exits"),
            "encounter": sc.get("encounter"),
            "player": sc.get("player"),
            "flags": sc.get("flags"),
        },
        "legal": legal[:12],
        "needs_frontier": True,
        "non_goals": [
            "Do not invent rooms, exits, HP, or loot as facts",
            "Do not claim engine state changed until chair confirms",
            "Options must map to legal moves or curveball classes when possible",
        ],
    }


def _parse_advice_json(raw: str) -> dict[str, Any] | None:
    t = (raw or "").strip()
    if not t:
        return None
    # fenced json
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    else:
        start, end = t.find("{"), t.rfind("}")
        if start >= 0 and end > start:
            t = t[start : end + 1]
    try:
        o = json.loads(t)
        return o if isinstance(o, dict) else None
    except json.JSONDecodeError:
        return None


def _fallback_advice(intention: dict[str, Any]) -> dict[str, Any]:
    legal = intention.get("legal") or []
    opts = []
    labels = "abcd"
    for i, a in enumerate(legal[:4]):
        lab = labels[i]
        tip = a.get("type", "")
        if a.get("direction"):
            tip += f" {a['direction']}"
        opts.append(
            {
                "id": lab,
                "label": f"Do: {tip}",
                "engine_hint": json.dumps(a),
            }
        )
    if not opts:
        opts = [
            {"id": "a", "label": "Look around", "engine_hint": '{"type":"look"}'},
            {"id": "b", "label": "Ask for help list", "engine_hint": '{"type":"help"}'},
        ]
    return {
        "options": opts,
        "recommend": opts[0]["id"],
        "clarify_questions": [],
        "flavor": "The guest shrugs (offline): stick to the map.",
        "source": "fallback_local",
    }


def ask_frontier_advice(intention: dict[str, Any]) -> dict[str, Any]:
    """Guest of honor: DeepSeek or soft-skip to local fallback."""
    system = (
        "You are the Guest of Honor at a Mag salon table. "
        "Advise only. The engine owns truth. "
        "Reply with ONLY a JSON object: "
        '{"options":[{"id":"a","label":"...","engine_hint":"{\\"type\\":\\"look\\"}"}],'
        '"recommend":"a","clarify_questions":[],"flavor":"one witty line"} '
        "engine_hint must be JSON for move/look/attack/rest/help/inventory or "
        '{"type":"curveball_note","text":"..."}. Max 4 options. No markdown novel.'
    )
    user = (
        "## Intention + scene (pack only)\n"
        + json.dumps(intention, indent=2, default=str)[:3500]
        + "\n\nPropose options grounded in legal actions when possible."
    )
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            system,
            user,
            tier="T2",
            max_tokens=500,
            temperature=0.4,
        )
        if res.get("ok"):
            parsed = _parse_advice_json(str(res.get("text") or res.get("content") or ""))
            if parsed and parsed.get("options"):
                parsed["source"] = "deepseek"
                parsed["model"] = res.get("model")
                return parsed
    except Exception:
        pass
    # try ollama as weaker guest
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "ollama",
            system,
            user,
            model="gemma:2b",
            tier="T1",
            max_tokens=300,
            temperature=0.3,
        )
        if res.get("ok"):
            parsed = _parse_advice_json(str(res.get("text") or res.get("content") or ""))
            if parsed and parsed.get("options"):
                parsed["source"] = "ollama"
                return parsed
    except Exception:
        pass
    return _fallback_advice(intention)


def speak_advice_card(advice: dict[str, Any], *, clarify: bool = True) -> str:
    bits = []
    flavor = str(advice.get("flavor") or "").strip()
    if flavor:
        bits.append(flavor)
    bits.append("Guest offers:")
    for o in advice.get("options") or []:
        bits.append(f"{o.get('id')}) {o.get('label')}")
    rec = advice.get("recommend")
    if rec:
        bits.append(f"Recommends: {rec}.")
    qs = advice.get("clarify_questions") or []
    if clarify and qs:
        bits.append("Clarify: " + str(qs[0])[:160])
    bits.append("Say take A, or ignore guest.")
    return " ".join(bits)


def start_advice(
    *,
    campaign_id: str,
    session_id: str,
    text: str,
    auto_surprise: bool = False,
) -> dict[str, Any]:
    from mag.game_campaign import load_campaign

    camp = load_campaign(campaign_id)
    if not camp or camp.get("status") != "active":
        return {"ok": False, "error": "need active campaign", "schema": SCHEMA}

    intention = build_intention_card(campaign=camp, text=text)
    advice = ask_frontier_advice(intention)
    aid = _pid()
    pending = {
        "schema": SCHEMA,
        "advice_id": aid,
        "ts": _utc(),
        "session_id": session_id,
        "campaign_id": campaign_id,
        "intention": intention,
        "advice": advice,
        "status": "awaiting_confirm",
        "auto_surprise": auto_surprise,
    }
    save_pending(session_id, pending)

    # mark slow path on campaign
    try:
        from mag.game_campaign import load_campaign, save_campaign

        camp = load_campaign(campaign_id)
        if camp:
            st = dict(camp.get("storyteller") or {})
            st["slow_turns"] = int(st.get("slow_turns") or 0) + 1
            camp["storyteller"] = st
            save_campaign(camp)
    except Exception:
        pass
    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={"campaign_id": campaign_id, "kind": "salon_advice"},
            input_data={"text": (text or "")[:200]},
            action={
                "fast_path": False,
                "ds_called": advice.get("source") == "deepseek",
                "advice_source": advice.get("source"),
                "n_options": len(advice.get("options") or []),
            },
            outcome={"advice_id": aid},
            pattern_tags=["game", "salon", "slow_path", "dogfood_dm"],
            tier_max="T2",
            exportable=False,
        )
    except Exception:
        pass

    if auto_surprise or wants_surprise(text):
        return confirm_advice(
            session_id=session_id,
            option_id=str(advice.get("recommend") or "a"),
            surprise=True,
        )

    speak = speak_advice_card(advice)
    return {
        "ok": True,
        "schema": SCHEMA,
        "route": "salon_advice",
        "advice_id": aid,
        "pending": True,
        "advice": advice,
        "speak": speak,
        "narrate": speak,
        "events": [speak],
        "campaign_id": campaign_id,
        "fast_path": False,
        "ds_called": advice.get("source") == "deepseek",
    }


def confirm_advice(
    *,
    session_id: str,
    option_id: str = "",
    reject: bool = False,
    surprise: bool = False,
) -> dict[str, Any]:
    from mag.game_campaign import apply_action, load_campaign, scene_context, list_legal_actions
    from mag.game_curveball import resolve_curveball
    from mag.game_narrate import narrate_scene

    pending = load_pending(session_id)
    if not pending:
        return {"ok": False, "error": "no pending advice", "schema": SCHEMA}

    if reject:
        clear_pending(session_id)
        speak = "Guest dismissed. The road remains. Try a move, or ask again later."
        return {
            "ok": True,
            "schema": SCHEMA,
            "route": "salon_reject",
            "speak": speak,
            "narrate": speak,
            "events": [speak],
            "campaign_id": pending.get("campaign_id"),
        }

    advice = pending.get("advice") or {}
    opts = {str(o.get("id")).lower(): o for o in (advice.get("options") or [])}
    oid = (option_id or advice.get("recommend") or "a").lower()
    chosen = opts.get(oid) or opts.get("a") or (list(opts.values())[0] if opts else None)
    if not chosen:
        clear_pending(session_id)
        return {"ok": False, "error": "no option", "schema": SCHEMA}

    cid = str(pending.get("campaign_id") or "")
    hint_raw = str(chosen.get("engine_hint") or "").strip()
    action: dict[str, Any] | None = None
    try:
        action = json.loads(hint_raw) if hint_raw.startswith("{") else None
    except json.JSONDecodeError:
        action = None

    events: list[str] = []
    if surprise:
        events.append(f"(Surprise — guest's pick {oid}.)")
    events.append(f"Chair confirms: {chosen.get('label')}")

    out: dict[str, Any]
    if action and action.get("type") == "curveball_note":
        out = resolve_curveball(cid, str(action.get("text") or chosen.get("label") or ""))
    elif action and action.get("type"):
        out = apply_action(cid, action)
    else:
        # treat label as curveball phrase
        out = resolve_curveball(cid, str(chosen.get("label") or "look around"))

    clear_pending(session_id)

    if not out.get("ok"):
        # fallback look
        out = apply_action(cid, {"type": "look"})
        events.append(str(out.get("error") or "Applied look instead."))

    ev = events + list(out.get("events") or [])
    narr = narrate_scene(out.get("scene_context"), events=ev, use_llm=True)
    speak = str(narr.get("text") or out.get("narrate") or " ".join(ev))

    try:
        from mag.training_events import emit

        emit(
            "game_turn",
            join={"campaign_id": cid, "salon": pending.get("advice_id", "")},
            action={"confirm": oid, "surprise": surprise},
            outcome={"ok": True, "source": (advice.get("source") or "")},
            pattern_tags=["game", "salon", "confirm"],
            tier_max="T2",
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "route": "salon_confirm",
        "speak": speak,
        "narrate": speak,
        "events": ev,
        "legal": out.get("legal") or list_legal_actions(load_campaign(cid) or {}),
        "scene_context": out.get("scene_context") or scene_context(load_campaign(cid) or {}),
        "campaign_id": cid,
        "confirmed_option": oid,
    }


def handle_salon_voice(
    text: str,
    *,
    session_id: str,
    campaign_id: str,
) -> dict[str, Any] | None:
    """Voice entry: pending confirm, or start advice. None = not salon."""
    pending = load_pending(session_id)
    conf = parse_confirm(text)
    if pending and conf:
        if conf.get("kind") == "reject":
            return confirm_advice(session_id=session_id, reject=True)
        return confirm_advice(
            session_id=session_id,
            option_id=str(conf.get("option_id") or "a"),
        )
    if pending and not conf:
        # re-speak options if they babble
        advice = pending.get("advice") or {}
        speak = "Still waiting on the chair. " + speak_advice_card(advice)
        return {
            "ok": True,
            "schema": SCHEMA,
            "route": "salon_await_confirm",
            "speak": speak,
            "narrate": speak,
            "pending": True,
            "campaign_id": campaign_id,
        }
    if wants_advice(text) or wants_surprise(text):
        return start_advice(
            campaign_id=campaign_id,
            session_id=session_id,
            text=text,
            auto_surprise=wants_surprise(text),
        )
    return None
