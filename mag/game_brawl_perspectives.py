"""Multi-POV monologues for tavern brawl — Rashomon seats, engine-bound.

Schema: mag_brawl_perspectives.v1
Law: templates (cheap) first; optional Slow rewrite never invents HP/kills/rooms.
DF flavor is aesthetic source material, not live sim.
"""
from __future__ import annotations

import random
import re
from typing import Any

SCHEMA = "mag_brawl_perspectives.v1"

# Voice banks keyed by combatant id / archetype / faction
_VOICES: dict[str, list[str]] = {
    "party_vex": [
        "I only stopped the stranger from making us look soft. The mark got away — someone here is why.",
        "Window, loft, keep smoke — I don't care. Fists now. Blame later.",
        "If the wizard throws more light, I'm throwing the wizard.",
        "We lost the hunt. I'm not losing the bar too.",
    ],
    "party_sable": [
        "I was upstairs. Window was latched. Fighter needs a villain. Convenient weather: you.",
        "Three different windows in three mouths. I need fewer witnesses.",
        "Cynical? Accurate. Hotheaded steel is the real problem.",
        "Slip, throw, leave. Pride is a tax I don't pay.",
    ],
    "party_quill": [
        "I de-escalated with illumination. Mass answers with mass. Porous security at the keep is the metaphor.",
        "The unlatched window is a thesis. This brawl is a footnote written in ale.",
        "Fragile? No — correctly budgeted. Let the fighter be the wall.",
        "I paid for the mug. Probably. Statistics favor my version.",
    ],
    "party_bram": [
        "Kindness is not softness. Someone is bleeding pride and I still have a patch kit.",
        "Stubborn enough to stand between chairs and skulls.",
        "The failed hunt is a wound. This fight is the bandage torn off too soon.",
        "Out of my way — or under my care. Your choice, stranger.",
    ],
    "barkeep_mira": [
        "Keep politics does not pour ale. Next time: outside. I count chairs, not windows.",
        "They broke a mug. They scare regulars. I swear in three languages and mean all of them.",
        "House rules: no blood on the hearth if you can help it. You cannot help it.",
        "When this ends, someone owes inventory.",
    ],
    "corner_stranger": [
        "I saw the light first. Then the shove. Then three windows. Broth first.",
        "I still don't know if the keep smokes black. I know the floor is sticky.",
        "Watching is a profession. Joining is a tax.",
        "Your absurdity is data. I file it under 'evening ruined productively.'",
    ],
    "stable_hand": [
        "I work horses, not fists. If I swing, it's because the bar is safer than the door.",
        "Skittish is smart. Staying is debt.",
    ],
    "farmhand_odette": [
        "Chair is a tool. You are a problem. Math is simple.",
        "Hotheaded? Field work teaches that weather doesn't wait.",
    ],
    "merchant_gil": [
        "Greedy and alive beats brave and billed. I hide, then invoice.",
        "Coin pouch as sling — metaphor and threat.",
    ],
    "drinker_bo": [
        "Loyal to the mug, the regulars, and the story I'll misremember tomorrow.",
        "Drunk is a stance. Tankard is a thesis.",
    ],
    "pc": [
        # player speaks themselves — rare template if needed
        "My line is mine. The room will answer.",
    ],
    "crowd": [
        "This was supposed to be broth and rumor.",
        "I will tell this wrong for years.",
        "Someone else's hunt. Our furniture.",
    ],
    "default": [
        "Noise, heat, and a story that will not agree with itself by morning.",
        "I swing because the room decided I must.",
    ],
}

# DF-flavored material words (aesthetic only — original phrasing)
_DF_MATERIAL = [
    "oak mug",
    "stoneware cup",
    "iron tankard",
    "spilled plump-helmet stew",
    "sticky table-blood of spilled ale",
    "chair-leg of willow",
    "boot-print of mud shaped like keep-stone",
]


def _voice_key(combatant: dict[str, Any]) -> str:
    cid = str(combatant.get("id") or "")
    if cid in _VOICES:
        return cid
    arch = str(combatant.get("archetype") or "").lower()
    if arch == "fighter":
        return "party_vex"
    if arch == "rogue":
        return "party_sable"
    if arch == "wizard":
        return "party_quill"
    if arch == "cleric":
        return "party_bram"
    if combatant.get("role") == "commoner":
        return "crowd"
    if combatant.get("is_player"):
        return "pc"
    return "default"


def _filter_invent(text: str, events: list[str]) -> str:
    """Refuse lines that invent kills/rooms not in engine events."""
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    # invent bans
    if re.search(r"\b(i kill|kills you|you die|dead on the floor|body count)\b", low):
        return ""
    if re.search(r"\b(desert|bios|ram|lane depth)\b", low):
        return ""
    # if claim drop/kill, require events mention drop
    if re.search(r"\b(drops?|down for good|finished them)\b", low):
        joined = " ".join(events or []).lower()
        if "drops" not in joined and "down" not in joined:
            return ""
    return t[:320]


def perspective_line(
    combatant: dict[str, Any],
    *,
    events: list[str] | None = None,
    flags: list[str] | None = None,
    spotlight_note: str = "",
) -> dict[str, Any]:
    """One in-character line. Template source; never invents engine state."""
    events = list(events or [])
    flags = list(flags or [])
    key = _voice_key(combatant)
    bank = list(_VOICES.get(key) or _VOICES["default"])
    # failed_hunt pressure for party
    if "failed_hunt" in flags and combatant.get("faction") == "party":
        bank = [
            "Empty hands. Full blame. The mark is gone and the stranger is convenient.",
            *bank,
        ]
    line = random.choice(bank)
    if spotlight_note and random.random() < 0.45:
        line = f"{line} ({spotlight_note[:80]})"
    # light DF material color
    if random.random() < 0.25 and combatant.get("role") == "commoner":
        mat = random.choice(_DF_MATERIAL)
        line = f"{line} The {mat} remembers this better than I will."
    line = _filter_invent(line, events) or random.choice(_VOICES["default"])
    return {
        "schema": SCHEMA,
        "unit_id": combatant.get("id"),
        "name": combatant.get("name"),
        "faction": combatant.get("faction"),
        "text": line,
        "source": "template",
        "voice_key": key,
    }


def collect_round_perspectives(
    combatants: list[dict[str, Any]],
    *,
    events: list[str] | None = None,
    flags: list[str] | None = None,
    max_voices: int = 6,
    include_player: bool = False,
    spotlight_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Living non-player voices this beat (Rashomon cast)."""
    events = list(events or [])
    living = [
        c
        for c in combatants
        if int(c.get("hp") or 0) > 0 and c.get("alive", True)
    ]
    out: list[dict[str, Any]] = []
    spotlight = set(spotlight_ids or [])
    # prioritize party + house + anyone focused on pc
    ordered = sorted(
        living,
        key=lambda c: (
            0 if c.get("id") in spotlight else 1,
            0 if c.get("faction") == "party" else 1,
            0 if c.get("faction") == "house" else 1,
            str(c.get("name") or ""),
        ),
    )
    for c in ordered:
        if c.get("is_player") and not include_player:
            continue
        if len(out) >= max_voices:
            break
        note = ""
        if "focused_on_pc" in (c.get("status_effects") or []):
            note = "eyes on the stranger"
        if any("ABSURD" in str(e) for e in events[-8:]):
            note = note or "still processing the bit"
        out.append(
            perspective_line(c, events=events, flags=flags, spotlight_note=note)
        )
    return out


def format_perspectives_section(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    lines = ["## Perspectives"]
    for r in rows:
        name = r.get("name") or r.get("unit_id") or "?"
        lines.append(f"**{name}:** {r.get('text')}")
    return "\n\n".join(lines)


def perspectives_for_brawl_card(
    combatants: list[dict[str, Any]],
    *,
    events: list[str] | None = None,
    flags: list[str] | None = None,
    max_voices: int = 6,
) -> tuple[str, list[dict[str, Any]]]:
    rows = collect_round_perspectives(
        combatants,
        events=events,
        flags=flags,
        max_voices=max_voices,
    )
    return format_perspectives_section(rows), rows
