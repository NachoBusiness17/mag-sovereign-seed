"""Constrained narrator — TinyStories regime: paint engine truth only.

Schema: mag_game_narrate.v1
"""
from __future__ import annotations

import os
import re
from typing import Any

SCHEMA = "mag_game_narrate.v1"


def narrate_scene(
    scene_context: dict[str, Any] | None,
    *,
    events: list[str] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """2–4 spoken sentences. Never invent entities not in context."""
    ctx = scene_context or {}
    events = events or []
    # Deterministic paint first (always works offline)
    bits = []
    if events:
        bits.append(" ".join(events[:4]))
    else:
        if ctx.get("room_name"):
            bits.append(f"You stand in {ctx['room_name']}.")
        if ctx.get("room_desc"):
            bits.append(str(ctx["room_desc"]))
        if ctx.get("hook"):
            bits.append(str(ctx["hook"]))
        enc = ctx.get("encounter") or {}
        if enc and int(enc.get("hp") or 0) > 0:
            bits.append(f"{enc.get('name')} watches you, still a threat.")
        pl = ctx.get("player") or {}
        if pl.get("name"):
            bits.append(f"{pl.get('name')} has HP {pl.get('hp')}/{pl.get('hp_max')}.")
    plain = " ".join(bits).strip()
    if not plain:
        plain = "The world holds its breath. What do you do?"

    # Mechanical lines stay template (help/inventory/HP) — small models invent deserts
    joined_ev = " ".join(events or []).lower()
    if any(x in joined_ev for x in ("you can:", "carries:", "try:")):
        return {"ok": True, "schema": SCHEMA, "text": plain[:500], "source": "template"}

    if not use_llm or (os.environ.get("MAG_GAME_NARRATE_LLM") or "1").strip() in (
        "0",
        "false",
        "off",
    ):
        return {"ok": True, "schema": SCHEMA, "text": plain[:500], "source": "template"}

    try:
        from models.providers import chat_provider

        # FAST ROUTE (2026-08-15): DeepSeek by default, NOT the slow local GPU (ollama gemma:2b).
        # Tier T2 so remote is allowed (T0/T1 fail closed for non-local). Override via env.
        provider = (os.environ.get("MAG_GAME_NARRATE_PROVIDER") or "deepseek").strip()
        model = (os.environ.get("MAG_GAME_NARRATE_MODEL") or "deepseek-v4-flash").strip()
        tier = (os.environ.get("MAG_GAME_NARRATE_TIER") or "T2").strip()
        user = (
            "Rewrite as 2 short spoken adventure sentences for voice TTS. "
            "Use ONLY these facts — invent nothing new (no new monsters, rooms, deserts, or treasure).\n\n"
            f"FACTS:\n{plain}\n\n"
            f"TRAITS: {(ctx.get('player') or {}).get('traits')}\n"
            f"EXITS: {ctx.get('exits')}\n"
            "If you cannot stay faithful, repeat the FACTS almost verbatim."
        )
        res = chat_provider(
            provider,
            "You are a tight RPG narrator. No markdown. No RAM/BIOS/settings. Facts only. Two short sentences.",
            user,
            model=model,
            tier=tier,
            max_tokens=80,
            temperature=0.25,
        )
        if res.get("ok"):
            text = str(res.get("text") or res.get("content") or "").strip()
            # Reject freestyle if none of the key fact tokens appear
            anchors = [
                w
                for w in re.findall(r"[A-Za-z]{4,}", plain)
                if w.lower()
                not in (
                    "you",
                    "stand",
                    "have",
                    "with",
                    "from",
                    "that",
                    "this",
                    "still",
                    "traits",
                )
            ][:8]
            ok_anchor = not anchors or any(a.lower() in text.lower() for a in anchors)
            invent_ban = bool(
                re.search(
                    r"\b(desert|bios|ram|lane depth|optimal|settings|cpu)\b",
                    text,
                    re.I,
                )
            )
            if text and len(text) > 20 and ok_anchor and not invent_ban:
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "text": text[:500],
                    "source": "local_llm",
                    "model": model,
                }
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "text": plain[:500], "source": "template"}
