"""Voice memory lanes — separate cheap contexts so Voice Mag ≠ Code Mag ≠ Desk RAM.

Schema: mag_voice_lane.v1

Problem: one shared dig board + desk goal (BIOS/RAM) poisons every voice turn.
Fix: named lanes with isolated session memory + what they may load.

Lanes:
  voice   — conversation companion (default); no dig board, no desk goal
  dig     — research/salon/refine; dig board ok, still no desk sludge unless hardware
  code    — implement/handoff; brief + handoff stack
  harness — Mag itself (this page, seats, STT); mostly instant harness answers
  janitor — status/bonds/pulse only; pack scut
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "mag_voice_lane.v1"

LANES: dict[str, dict[str, Any]] = {
    "voice": {
        "id": "voice",
        "label": "Voice Mag (talk)",
        "session_prefix": "vlane-voice-",
        "system": (
            "You are Voice Mag — a talk companion on this PC. "
            "You are NOT a BIOS/RAM technician unless the latest line names hardware. "
            "Answer ONLY the latest operator line in 1-2 short spoken sentences. "
            "No markdown. Never say 'Sure, here's the answer:'. Never reopen old topics. "
            "If they ask about this page: Mag Voice is talk→brief→answer→speak; "
            "handoff files DeepSeek; refine chain is multi-seat design. "
            "If they greet you: confirm hearing and wait for a real topic."
        ),
        "allow_dig_board": False,
        "allow_desk_pulse": False,
        "allow_history": True,
        "max_history_turns": 2,
        "model_env": "MAG_VOICE_LOCAL_MODEL",
        "default_model": "gemma:2b",
    },
    "dig": {
        "id": "dig",
        "label": "Dig Mag (research/salon)",
        "session_prefix": "vlane-dig-",
        "system": (
            "You are Dig Mag — Socratic research companion. "
            "Use dig board only if on-topic. No BIOS/RAM unless they asked. "
            "1-3 short sentences. Prefer one sharp question or one insight."
        ),
        "allow_dig_board": True,
        "allow_desk_pulse": False,
        "allow_history": True,
        "max_history_turns": 3,
        "model_env": "MAG_VOICE_DIG_MODEL",
        "default_model": "gemma:2b",
    },
    "code": {
        "id": "code",
        "label": "Code Mag (handoff/implement)",
        "session_prefix": "vlane-code-",
        "system": (
            "You are Code Mag — you FILE handoffs for DeepSeek; you rarely write long code aloud. "
            "Confirm the job in one sentence. Prefer handoff over monologue."
        ),
        "allow_dig_board": False,
        "allow_desk_pulse": False,
        "allow_history": True,
        "max_history_turns": 2,
        "model_env": "MAG_VOICE_CODE_MODEL",
        "default_model": "gemma:2b",
    },
    "harness": {
        "id": "harness",
        "label": "Harness Mag (this page / Mag itself)",
        "session_prefix": "vlane-harness-",
        "system": (
            "You are Harness Mag — explain Mag Voice UI and seats only. "
            "No BIOS/RAM. No personal drama. 1-2 short sentences."
        ),
        "allow_dig_board": False,
        "allow_desk_pulse": False,
        "allow_history": False,
        "max_history_turns": 0,
        "model_env": "MAG_VOICE_HARNESS_MODEL",
        "default_model": "gemma:2b",
    },
    "janitor": {
        "id": "janitor",
        "label": "Janitor Mag (status/scut)",
        "session_prefix": "vlane-janitor-",
        "system": (
            "You are Janitor Mag — short status only. "
            "No BIOS/RAM troubleshooting monologues."
        ),
        "allow_dig_board": False,
        "allow_desk_pulse": True,
        "allow_history": False,
        "max_history_turns": 0,
        "model_env": "MAG_VOICE_JANITOR_MODEL",
        "default_model": "gemma:2b",
    },
}

_PAGE = re.compile(
    r"\b("
    r"this page|what('?s| is) this|on this page|can you see (this )?page|"
    r"what is (the )?voice|mag voice|what does this (do|page)|"
    r"whole (not |nought )?thing about|what is going on (here|on this)"
    r")\b",
    re.I,
)
_HEAR = re.compile(
    r"\b(can you hear|hear me|are you (there|listening)|hello|hey)\b",
    re.I,
)
_COMPLAIN = re.compile(
    r"\b("
    r"this still sucks|still sucks|wrong topic|not (about|that)|"
    r"stop (talking about|with)|stuck on|keep (talking about|saying)|"
    r"not helping|useless|wrong (again)?"
    r")\b",
    re.I,
)
_PREMISE = re.compile(
    r"\b("
    r"create a premise|start (a )?premise|refine chain|"
    r"escalate (this |the )?(like |as )?|"
    r"multi[- ]?seat|pass to deepseek then|verkle experiment"
    r")\b",
    re.I,
)


def normalize_lane(raw: str | None) -> str:
    s = (raw or "voice").strip().lower()
    if s in LANES:
        return s
    aliases = {
        "talk": "voice",
        "chat": "voice",
        "research": "dig",
        "salon": "dig",
        "build": "code",
        "implement": "code",
        "mag": "harness",
        "ui": "harness",
        "page": "harness",
        "status": "janitor",
        "scut": "janitor",
    }
    return aliases.get(s, "voice")


def lane_spec(lane: str | None) -> dict[str, Any]:
    return dict(LANES[normalize_lane(lane)])


def session_id_for_lane(base_session: str, lane: str) -> str:
    """Isolate history per lane so Voice Mag never inherits Code Mag RAM sludge."""
    lane = normalize_lane(lane)
    base = re.sub(r"[^a-zA-Z0-9_-]+", "", (base_session or "").strip())[:48] or "s"
    # strip any prior lane prefix
    for p in ("vlane-voice-", "vlane-dig-", "vlane-code-", "vlane-harness-", "vlane-janitor-"):
        if base.startswith(p):
            base = base[len(p) :]
            break
    return f"{LANES[lane]['session_prefix']}{base}"[:64]


def infer_lane(text: str, *, explicit: str | None = None) -> str:
    if explicit:
        return normalize_lane(explicit)
    t = text or ""
    if _COMPLAIN.search(t) or _PAGE.search(t) or _HEAR.search(t):
        return "harness"
    if _PREMISE.search(t) or re.search(r"\b(jung|bernays|ellul|salon|summon)\b", t, re.I):
        return "dig"
    if re.search(r"\b(implement|refactor|wire|patch|pytest|handoff)\b", t, re.I):
        return "code"
    if re.search(r"\b(status|bonds|quota|what was i doing|doctor)\b", t, re.I):
        return "janitor"
    return "voice"


def instant_harness_reply(text: str) -> dict[str, Any] | None:
    """No LLM — kill sludge paths for page/meta questions."""
    t = (text or "").strip()
    if not t:
        return None
    if _COMPLAIN.search(t):
        return {
            "ok": True,
            "answer": (
                "You're right — I was stuck on an old desk topic that doesn't belong here. "
                "This is Mag Voice: you talk, I answer, optional DeepSeek handoff or a refine chain. "
                "Sticky topic cleared. What do you want to do on this page?"
            ),
            "route": "lane_harness_instant",
            "lane": "harness",
            "force_reset": True,
        }
    if _HEAR.search(t) and len(t) < 80:
        return {
            "ok": True,
            "answer": "Yes — I hear you. This is Mag Voice. Go ahead.",
            "route": "lane_harness_instant",
            "lane": "harness",
            "force_reset": True,
        }
    if _PAGE.search(t):
        return {
            "ok": True,
            "answer": (
                "This page is Mag Voice. You speak, Mag compiles a short intention brief, "
                "answers on a memory lane (voice, dig, code, harness), can FILE handoffs to DeepSeek "
                "or run a multi-seat refine chain, and Seal diary freezes the day on Verkle. "
                "It is not your BIOS settings page."
            ),
            "route": "lane_harness_instant",
            "lane": "harness",
            "force_reset": True,
        }
    return None


def lane_public(lane: str) -> dict[str, Any]:
    sp = lane_spec(lane)
    return {
        "schema": SCHEMA,
        "id": sp["id"],
        "label": sp["label"],
        "allow_dig_board": sp["allow_dig_board"],
        "allow_desk_pulse": sp["allow_desk_pulse"],
    }
