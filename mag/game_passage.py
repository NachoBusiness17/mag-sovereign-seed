"""Adventure passage cards — IF turn envelope for quick beautiful prose.

Schema: mag_game_passage.v1
Layers: Interior · Area · Environment · Narrator · Soft leads
Craft rails (never literal on player): Jung-light, Campbell-light, Le Guin-clean,
fiction-only attention framing. Engine owns facts.
"""
from __future__ import annotations

import os
import re
from typing import Any

SCHEMA = "mag_game_passage.v1"

SYSTEM = """You write Mag adventure passages for voice and table.
Output ONLY these sections with those headings:
## Interior
## Area
## Environment
## Narrator
## Soft leads

Rules:
- Short, vivid, concrete (Le Guin-clean: cut ornament, no sermon).
- One subtle mythic pressure (threshold, shadow, mentor-glint, trickster) — NEVER name theories or Jung/Campbell.
- Frame stakes and attention honestly from STATE — never invent HP, rooms, exits, or loot not listed.
- Soft leads: at most 3 invitations, not a prison menu.
- No markdown bold spam. No BIOS/RAM. No deserts unless STATE says so.
"""


def state_from_scene(
    scene: dict[str, Any] | None,
    *,
    events: list[str] | None = None,
    last_action: str = "",
    room_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sc = scene or {}
    rm = room_meta or {}
    return {
        "room_name": sc.get("room_name") or rm.get("name"),
        "room_desc": sc.get("room_desc") or rm.get("desc"),
        "area": rm.get("area") or sc.get("area") or "",
        "environment": rm.get("environment") or sc.get("environment") or "",
        "hook": sc.get("hook") or (rm.get("hooks") or [None])[0],
        "exits": sc.get("exits") or list((rm.get("exits") or {}).keys()),
        "encounter": sc.get("encounter"),
        "player": sc.get("player"),
        "flags": sc.get("flags"),
        "events": (events or [])[:6],
        "last_action": (last_action or "")[:200],
        "area_tag": rm.get("area_tag") or "road",
    }


def template_passage(state: dict[str, Any], *, full: bool = True) -> str:
    """Offline-beautiful fallback — no LLM required."""
    name = state.get("room_name") or "Somewhere"
    desc = state.get("room_desc") or "The air holds still."
    area = state.get("area") or "The known map."
    env = state.get("environment") or "The day continues."
    hook = state.get("hook") or ""
    exits = state.get("exits") or []
    pl = state.get("player") or {}
    enc = state.get("encounter") or {}
    events = state.get("events") or []

    interior = desc
    if full and hook:
        interior = f"{desc} {hook}"
    if events and not full:
        interior = " ".join(str(e) for e in events[:3])

    narrator = "The place waits to see what you are."
    if enc and int(enc.get("hp") or 0) > 0:
        narrator = f"{enc.get('name')} is a living problem in the room."
    elif pl.get("traits"):
        t0 = (pl.get("traits") or ["curious"])[0]
        narrator = f"Something in you — {t0} — answers the room."

    leads = []
    if exits:
        leads.append("go " + str(exits[0]))
    if any(x in ("out", "north", "road") for x in exits) or "tavern" in str(name).lower():
        leads.append("ask for a rumor")
        leads.append("leave for the road")
    if not leads:
        leads = ["look", "help"]

    parts = [
        f"## Interior\n{interior}",
        f"## Area\n{area}",
        f"## Environment\n{env}",
        f"## Narrator\n{narrator}",
        "## Soft leads\n- " + "\n- ".join(leads[:3]),
    ]
    if pl.get("name") and full:
        parts.append(
            f"\n({pl.get('name')}: HP {pl.get('hp')}/{pl.get('hp_max')})"
        )
    return "\n\n".join(parts).strip()


def format_spoken(passage: str) -> str:
    """Flatten sections for TTS / chat bubbles."""
    t = passage or ""
    t = re.sub(r"^##\s+", "", t, flags=re.M)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:900]


def narrate_passage(
    scene: dict[str, Any] | None,
    *,
    events: list[str] | None = None,
    last_action: str = "",
    room_meta: dict[str, Any] | None = None,
    full: bool = True,
    use_llm: bool = True,
) -> dict[str, Any]:
    state = state_from_scene(
        scene, events=events, last_action=last_action, room_meta=room_meta
    )
    # Mechanical / stickmin already complete
    joined = " ".join(events or []).lower()
    if any(x in joined for x in ("you can:", "carries:", "dignity:", "guest offers")):
        text = " ".join(events or [])
        return {"ok": True, "schema": SCHEMA, "text": text[:900], "source": "events", "passage": text}

    fallback = template_passage(state, full=full)
    if not use_llm or (os.environ.get("MAG_GAME_PASSAGE_LLM") or "1").strip() in (
        "0",
        "false",
        "off",
    ):
        return {
            "ok": True,
            "schema": SCHEMA,
            "text": format_spoken(fallback),
            "passage": fallback,
            "source": "template",
            "state": state,
        }

    try:
        from models.providers import chat_provider

        # FAST ROUTE BY DEFAULT (2026-08-15): the deterministic template above is 0ms/$0 and is
        # the "known route." When a live brain IS wanted, route to DeepSeek (fast remote) — NOT the
        # slow local GPU (ollama gemma:2b took ~56s and fell back to template anyway). Tier T2 so
        # remote is allowed (T0/T1 fail closed for non-local providers). Override via env.
        provider = (os.environ.get("MAG_GAME_NARRATE_PROVIDER") or "deepseek").strip()
        model = (os.environ.get("MAG_GAME_NARRATE_MODEL") or "deepseek-v4-flash").strip()
        tier = (os.environ.get("MAG_GAME_NARRATE_TIER") or "T2").strip()
        user = (
            f"STATE:\n{state}\n\n"
            f"Write the passage card. full={full}. "
            "If events exist, weave them into Interior/Narrator without inventing new places."
        )
        res = chat_provider(
            provider,
            SYSTEM,
            user,
            model=model,
            tier=tier,
            max_tokens=280 if full else 160,
            temperature=0.45,
        )
        if res.get("ok"):
            raw = str(res.get("text") or res.get("content") or "").strip()
            if raw and "## Interior" in raw:
                # invent ban
                if re.search(r"\b(bios|ram|lane depth|desert sands)\b", raw, re.I):
                    raw = fallback
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "text": format_spoken(raw),
                    "passage": raw,
                    "source": "local_llm",
                    "model": model,
                    "state": state,
                }
    except Exception:
        pass
    return {
        "ok": True,
        "schema": SCHEMA,
        "text": format_spoken(fallback),
        "passage": fallback,
        "source": "template",
        "state": state,
    }


def room_meta_from_camp(camp: dict[str, Any] | None) -> dict[str, Any]:
    if not camp:
        return {}
    rid = camp.get("room_id")
    rooms = (camp.get("module_snapshot") or {}).get("rooms") or {}
    return dict(rooms.get(rid) or {})
