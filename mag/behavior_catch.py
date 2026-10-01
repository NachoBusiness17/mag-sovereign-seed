"""Operator behavioral catch — thrash/sprint/anxiety as architecture + train soil.

Schema: mag_behavior_catch.v1
Law:
  - Operator-owned T1 local by default (not population surveillance)
  - Catch → name once → FILE note → emit event → return to active phase
  - Not a lecture; not a new product front
  - Proves portable personal behavioral OS ≠ Palantir panopticon
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_behavior_catch.v1"
NOTE_DIR = ROOT / "memory" / "improve" / "behavior"
INDEX_PATH = NOTE_DIR / "index.jsonl"
BEHAVIORAL_EVENTS = ROOT / "logs" / "behavioral_events.jsonl"

# Consent: MAG_BEHAVIOR_LOG=0 disables FILE+emit (except force=True)
def _logging_enabled() -> bool:
    v = (os.environ.get("MAG_BEHAVIOR_LOG") or "1").strip().lower()
    return v not in ("0", "false", "off", "no")


KNOWN_PATTERNS: dict[str, str] = {
    "thrash_multi_front": "Open many fronts then rebuild the middle (sprint / catchup)",
    "sprint_before_measure": "Ship features before Play Ladder / scoreboard",
    "irreversibility_anxiety": "Fear of long-run damage without sandbox rails",
    "grok_sink": "Scarce seat used for scut",
    "chat_as_memory": "Chat treated as DNA instead of FILE",
    "map_echo": "Framework recitation instead of one job",
    "phase_hop": "Abandon active phase without exit criteria",
    "feature_as_improve": "New module instead of measuring play quality",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def log_catch(
    pattern: str,
    *,
    note: str = "",
    session_id: str = "",
    phase_was: str = "",
    phase_return: str = "play_ladder_R0",
    fear: str = "",
    opened: list[str] | None = None,
    abandoned: list[str] | None = None,
    play_ladder_impact: str = "",
    force: bool = False,
    tier_max: str = "T1",
) -> dict[str, Any]:
    """FILE architecture note + training event. Silent-safe."""
    if not force and not _logging_enabled():
        return {"ok": True, "skipped": True, "reason": "MAG_BEHAVIOR_LOG off"}

    pattern = (pattern or "thrash_multi_front").strip().lower()
    pattern = re.sub(r"[^a-z0-9_]+", "_", pattern)[:64] or "thrash_multi_front"
    label = KNOWN_PATTERNS.get(pattern, pattern)
    ts = _utc()
    day = _day()
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    slug = f"{pattern}_{day}_{ts[11:19].replace(':', '')}"
    path = NOTE_DIR / f"{slug}.md"
    body = "\n".join(
        [
            f"# Behavior catch — {pattern}",
            "",
            f"**Schema:** {SCHEMA}  ",
            f"**ts:** {ts}  ",
            f"**label:** {label}  ",
            f"**session:** {session_id or '—'}  ",
            f"**tier:** {tier_max} (operator-owned; not export psych dump)",
            "",
            "## Architecture note",
            "",
            note.strip() or "_No free text — pattern only._",
            "",
            "## Context",
            "",
            f"- **phase_was:** {phase_was or '—'}",
            f"- **phase_return:** {phase_return or '—'}",
            f"- **fear (if spoken):** {fear or '—'}",
            f"- **opened:** {', '.join(opened or []) or '—'}",
            f"- **abandoned / parked:** {', '.join(abandoned or []) or '—'}",
            f"- **play_ladder_impact:** {play_ladder_impact or '—'}",
            "",
            "## Law",
            "",
            "- Name once; do not lecture.",
            "- Do not open a new front to 'fix the thrash.'",
            "- Return to single Play Ladder phase.",
            "- Portable personal train soil — not institutional surveillance.",
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")
    rel = str(path.relative_to(ROOT)).replace("\\", "/")

    row = {
        "schema": SCHEMA,
        "ts": ts,
        "pattern": pattern,
        "label": label,
        "path": rel,
        "session_id": session_id or "",
        "phase_return": phase_return,
        "tier_max": tier_max,
    }
    with INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")

    # behavioral_events for daily synth
    try:
        BEHAVIORAL_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with BEHAVIORAL_EVENTS.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": ts,
                        "kind": "operator_behavior",
                        "pattern": pattern,
                        "tool": "behavior_catch",
                        "path": rel,
                        "session_id": session_id or "",
                    },
                    default=str,
                )
                + "\n"
            )
    except OSError:
        pass

    # training_events (republic export path; T1 default not exportable)
    try:
        from mag.training_events import emit

        emit(
            "operator_behavior",
            join={"session_id": session_id or "", "pattern": pattern},
            input_data={
                "phase_was": phase_was[:200],
                "opened": (opened or [])[:12],
            },
            action={"kind": "behavior_catch", "path": rel},
            outcome={
                "phase_return": phase_return,
                "fear": (fear or "")[:120],
                "play_ladder_impact": (play_ladder_impact or "")[:200],
            },
            pattern_tags=["operator_behavior", pattern, "architecture_note"],
            tier_max=tier_max if tier_max in ("T0", "T1", "T2") else "T1",
            exportable=False,  # psych/train soil stays local unless scrubbed later
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "pattern": pattern,
        "path": rel,
        "phase_return": phase_return,
        "speak": f"Logged {pattern} → {rel}. Return: {phase_return}.",
    }


def try_voice_or_text_catch(text: str, *, session_id: str = "") -> dict[str, Any] | None:
    """If operator language matches thrash/catchup, log and return speak."""
    t = text or ""
    if not re.search(
        r"\b("
        r"thrash|catch[\s-]?up|catchup|sprinting ahead|too many fronts|"
        r"all over the place|get it together|log (this )?behavior|"
        r"playing catch[\s-]?up|multi[\s-]?front"
        r")\b",
        t,
        re.I,
    ):
        return None
    pattern = "thrash_multi_front"
    if re.search(r"fuck something up|afraid to|what if i break", t, re.I):
        pattern = "irreversibility_anxiety"
    elif re.search(r"measure|scoreboard|benchmark first", t, re.I):
        pattern = "sprint_before_measure"
    out = log_catch(
        pattern,
        note=t[:800],
        session_id=session_id,
        phase_return="play_ladder_R0",
        play_ladder_impact="operator named thrash; return to chat+D&D measure",
    )
    out["route"] = "behavior_catch"
    out["speak_text"] = out.get("speak")
    out["answer"] = out.get("speak")
    return out


def seed_play_ladder_thrash_episode() -> dict[str, Any]:
    """One-shot seed from Play Ladder + thrash conversation (idempotent-ish)."""
    marker = NOTE_DIR / "SEED_play_ladder_thrash.md"
    if marker.is_file():
        return {"ok": True, "already": True, "path": str(marker.relative_to(ROOT)).replace("\\", "/")}
    NOTE_DIR.mkdir(parents=True, exist_ok=True)
    note = (
        "Operator pattern: sprint many Mag fronts (skills ecosystem, checkin, "
        "Bernays packs, chess, riddler) then play catchup. Wanted clarity: chat agent "
        "→ D&D as only improvement measure → map same form to coding later → "
        "indefinite play without fear of irreversible damage. "
        "Also: thrash catches are architecture + behavioral train soil "
        "(personal portable OS vs Palantir-shaped surveillance)."
    )
    r = log_catch(
        "thrash_multi_front",
        note=note,
        session_id="seed-play-ladder",
        phase_was="multi_front_skill_ecosystem",
        phase_return="play_ladder_R0",
        fear="indefinite agent run corrupts or breaks real systems",
        opened=[
            "mag-checkin",
            "mag-arena",
            "skill ecosystem map",
            "local_usable",
            "game theory map",
        ],
        abandoned=["park until R1: Bernays corpus, riddle X, speak-as-me, skill marketplaces"],
        play_ladder_impact="Defined R0–R5; active phase R0 chat plays D&D",
        force=True,
    )
    marker.write_text(
        f"# Seed marker\n\nCatch path: {r.get('path')}\n\nPlay Ladder is the scoreboard.\n",
        encoding="utf-8",
    )
    return r
