"""Voice skill seek — progressive disclosure before bluff.

Schema: mag_voice_skills.v1
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "mag_voice_skills.v1"

CATALOG = [
    {
        "id": "tabletop-dnd",
        "when": [
            "dnd",
            "d&d",
            "dungeon",
            "campaign",
            "classic one",
            "classic dnd",
            "adventure",
            "goblin",
            "the keep",
            "water one",
            "water computer",
            "hydraulic",
        ],
        "blurb": "Campaign engine + classic keep stub + dice (engine-first)",
        "engine": "game_campaign",
    },
    {
        "id": "refine-chain",
        "when": ["refine chain", "multi-seat", "premise"],
        "blurb": "Recursive multi-seat design",
        "engine": "refine_chain",
    },
]


def match_voice_skills(text: str) -> dict[str, Any]:
    t = (text or "").lower()
    hits = []
    for sk in CATALOG:
        for w in sk.get("when") or []:
            if w in t:
                hits.append(sk)
                break
    if re.search(r"\bclassic one\b", t) and not any(h["id"] == "tabletop-dnd" for h in hits):
        hits.append(next(s for s in CATALOG if s["id"] == "tabletop-dnd"))
    return {"ok": True, "schema": SCHEMA, "hits": hits, "miss": not hits}


def is_play_intent(text: str) -> bool:
    t = (text or "").lower()
    return bool(
        re.search(
            r"\b("
            r"dnd|d&d|dungeon|campaign|classic one|classic dnd|the keep|"
            r"water one|water computer|hydraulic|"
            r"start (a )?(game|campaign|adventure|classic)|"
            r"play (dnd|d&d|the classic|a game|the keep)|"
            r"let'?s play|wanna play|want to play|"
            r"new (game|campaign|adventure)|resume (game|campaign)"
            r")\b",
            t,
        )
    )


def is_in_game_action(text: str) -> bool:
    from mag.game_campaign import parse_player_speech

    return parse_player_speech(text) is not None
