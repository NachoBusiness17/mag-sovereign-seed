"""Intention compiler — cheap prep before smart seats fire.

Schema: intention_brief.v1
Tesuji: docs/ref/tesuji/intention-fidelity-routing-2026-08-07.md

Law:
  - Compile with disk + rules (+ optional local later). No frontier in compile.
  - Smart seats answer the brief, not sticky dig/desk sludge.
  - Mode A (default): local speaks; scout fills dig for next turn.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

SCHEMA = "intention_brief.v1"

_SLUDGE = re.compile(
    r"\b("
    r"sam|smart access|resizable\s*bar|bios|vram|motherboard|"
    r"ram settings|memory settings|sam settings"
    r")\b",
    re.I,
)
_GREET = re.compile(
    r"\b("
    r"hey|hello|hi\b|can you hear|hear me|good morning|good night|thanks|thank you"
    r")\b",
    re.I,
)
_ESCALATE = re.compile(
    r"\b("
    r"escalate|smarter model|smarter seat|use deepseek|call deepseek|"
    r"deep\s*seek|fidelity mode|use a smarter|not helping|wrong topic"
    r")\b",
    re.I,
)
# Blocking smart answer vs FILE handoff (non-blocking)
_HANDOFF = re.compile(
    r"\b("
    r"hand\s*off|handoff|file (that |this |it )?(for|to)|"
    r"pass (that |this |it )?to deepseek|queue (that |this |it )?|"
    r"implement that|build that|background (that|this)"
    r")\b",
    re.I,
)
_IMPLEMENT = re.compile(
    r"\b(implement|refactor|multi[- ]?file|write code|wire up|pytest)\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_sludge(text: str) -> bool:
    return bool(_SLUDGE.search(text or ""))


def _soft_stt(text: str) -> str:
    """Keep self-contained — avoid import cycle with voice_turn."""
    t = (text or "").strip()
    t = re.sub(r"\bb[eé]arnaise\b", "Bernays", t, flags=re.I)
    t = re.sub(r"\bburn\s*ays\b", "Bernays", t, flags=re.I)
    return t


def _topic_reset_signal(text: str, history: list[dict[str, Any]]) -> bool:
    if _has_sludge(text):
        return False
    if re.search(
        r"\b("
        r"hear me|hello|hi\b|hey\b|never ?mind|different topic|new topic|"
        r"talk about|about life|bernays|propaganda|forget (sam|ram|bios)|"
        r"stop (talking about|with)|not (about|that)|wrong topic"
        r")\b",
        text or "",
        re.I,
    ):
        return True
    asst = [str(t.get("text") or "") for t in (history or []) if t.get("role") == "assistant"][-4:]
    if not asst:
        return False
    hits = sum(1 for a in asst if _has_sludge(a))
    return hits >= max(1, len(asst) // 2)


def _verkle_tip_line() -> str:
    try:
        import json
        from config import ROOT

        tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
        if not tip_path.is_file():
            return ""
        tip = json.loads(tip_path.read_text(encoding="utf-8"))
        leaf = tip.get("n_leaves") or tip.get("n") or "?"
        root = str(tip.get("tip") or tip.get("root") or "")[:16]
        return f"leaves={leaf} tip={root}…"
    except Exception:
        return ""


def _goal_line(text: str, *, depth: str) -> str:
    t = (text or "").strip()
    if not t:
        return "(empty)"
    if _GREET.search(t) and len(t) < 48:
        return "Acknowledge hearing; invite next topic (no hardware drama)"
    if depth == "conversation":
        # Prefer operator phrasing as the goal
        return t[:220]
    if depth == "scut":
        return t[:180]
    return t[:220]


def _constraints(text: str, *, topic_reset: bool, depth: str) -> list[str]:
    cs = [
        "Answer ONLY the latest operator intention / goal line",
        "Do not invent troubleshooting drama",
        "1-3 short spoken sentences if voice; no markdown walls",
    ]
    if topic_reset or not _has_sludge(text):
        cs.append("Prior RAM/SAM/BIOS/desk hardware topics are void unless named now")
    if depth == "conversation":
        cs.append("Engage named people/ideas in the first sentence when present")
    if depth in ("simple_code", "heavy_code"):
        cs.append("Stay technical; defer multi-file factory if too large for voice")
    return cs


def compile_intention(
    text: str,
    *,
    session_id: str = "",
    channel: str = "voice",
    history: list[dict[str, Any]] | None = None,
    fidelity: bool = False,
    seat_force: str = "",
) -> dict[str, Any]:
    """Cheap compile — no frontier calls."""
    raw = (text or "").strip()
    fixed = _soft_stt(raw)
    history = history or []

    topic_reset = _topic_reset_signal(fixed, history)

    escalate = bool(_ESCALATE.search(fixed) or fidelity)
    handoff = bool(_HANDOFF.search(fixed))
    depth_info: dict[str, Any] = {}
    try:
        from mag.router import classify_depth

        depth_info = classify_depth(fixed)
    except Exception:
        depth_info = {"depth": "scut", "seat": "local", "ok": False}

    depth = str(depth_info.get("depth") or "scut")
    # Greet-only short → scut even if classifier drifts
    if _GREET.search(fixed) and len(fixed) < 40 and depth not in ("heavy_code", "plan"):
        depth = "scut"
        depth_info = {**depth_info, "depth": "scut", "seat": "local"}

    # Implement-class work on voice → prefer handoff (non-blocking) over mic DeepSeek
    if not handoff and channel in ("voice", "dashboard-voice", "") and _IMPLEMENT.search(fixed):
        if depth in ("heavy_code", "simple_code") or len(fixed) > 50:
            handoff = True

    seat_recommend = "local"
    if handoff and not escalate:
        seat_recommend = "handoff"  # FILE DeepSeek; voice stays local
    elif escalate or str(seat_force).lower() in ("deepseek", "remote", "frontier"):
        seat_recommend = "deepseek"
    elif depth in ("heavy_code", "plan", "overview"):
        if channel in ("voice", "dashboard-voice", ""):
            # Voice default: handoff stack, not block mic
            seat_recommend = "handoff"
            handoff = True
        else:
            seat_recommend = str(depth_info.get("seat") or "deepseek")
            if seat_recommend == "grok_tui":
                seat_recommend = "deepseek"
    elif depth in ("conversation", "scut", "simple_code"):
        seat_recommend = "local"  # Mode A: local + scout

    why_bits = []
    if handoff:
        why_bits.append("handoff_non_blocking")
    if escalate:
        why_bits.append("operator escalate/fidelity")
    why_bits.append(f"depth={depth}")
    if topic_reset:
        why_bits.append("topic_reset")
    if seat_recommend == "local" and depth == "conversation":
        why_bits.append("mode_A local+scout")
    why = "; ".join(why_bits)

    context_refs: list[str] = []
    tip = _verkle_tip_line()
    if tip:
        context_refs.append("memory/biography/verkle_tip.json")
    # Dig board only as ref when on-topic hardware or non-sludge
    if _has_sludge(fixed) or (depth == "conversation" and not topic_reset):
        context_refs.append("memory/working/voice_dig_board.md")

    goal = _goal_line(fixed, depth=depth)
    constraints = _constraints(fixed, topic_reset=topic_reset, depth=depth)

    brief = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "channel": channel or "voice",
        "session_id": (session_id or "")[:64],
        "stt_raw": raw if raw != fixed else None,
        "stt_fixed": fixed,
        "goal": goal,
        "constraints": constraints,
        "depth": depth,
        "seat_recommend": seat_recommend,
        "why": why,
        "topic_reset": topic_reset,
        "escalate": escalate,
        "handoff": handoff,
        "fidelity": bool(fidelity),
        "context_refs": context_refs,
        "verkle_tip": tip or None,
        "depth_class": {
            "depth": depth,
            "seat": depth_info.get("seat"),
            "token_hint": depth_info.get("token_hint"),
        },
        "mode": "A" if not handoff else "handoff",
        "steal": {
            "origin": "swarm economics + planner→generator shape",
            "leaf": "docs/ref/tesuji/intention-fidelity-routing-2026-08-07.md",
        },
    }
    return brief


def render_brief_for_model(brief: dict[str, Any], *, spoken: bool = True) -> str:
    """User payload for answer seats — sharp, small."""
    goal = str(brief.get("goal") or brief.get("stt_fixed") or "")
    constraints = brief.get("constraints") or []
    parts = [
        "## Intention brief (compiled — answer this)",
        f"**Goal:** {goal}",
        f"**Depth:** {brief.get('depth')} · **Seat plan:** {brief.get('seat_recommend')} · **Why:** {brief.get('why')}",
    ]
    if brief.get("topic_reset"):
        parts.append("**Topic reset:** prior hardware monologue is void.")
    if constraints:
        parts.append("**Constraints:**")
        for c in constraints[:6]:
            parts.append(f"- {c}")
    if brief.get("verkle_tip"):
        parts.append(f"**Verkle tip (spine, not topic):** {brief['verkle_tip']}")
    if spoken:
        parts.append(
            "Reply for voice: short, concrete, name the goal subject in the first sentence when it is a person or idea."
        )
    # Include fixed transcript for grounding
    fixed = brief.get("stt_fixed") or ""
    if fixed and fixed != goal:
        parts.append(f"## Operator words\n{fixed}")
    else:
        parts.append(f"## Operator words\n{fixed or goal}")
    return "\n".join(parts)


def brief_public(brief: dict[str, Any]) -> dict[str, Any]:
    """Slim dict for API / canvas."""
    return {
        "schema": SCHEMA,
        "goal": brief.get("goal"),
        "depth": brief.get("depth"),
        "seat_recommend": brief.get("seat_recommend"),
        "why": brief.get("why"),
        "topic_reset": brief.get("topic_reset"),
        "escalate": brief.get("escalate"),
        "handoff": brief.get("handoff"),
        "mode": brief.get("mode"),
        "stt_fixed": brief.get("stt_fixed"),
        "verkle_tip": brief.get("verkle_tip"),
        "constraints": (brief.get("constraints") or [])[:4],
    }
