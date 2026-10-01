"""Desk overseer — context pressure, episode recording, supersede + steer.

When Local hits context limits or echo-without-commit loops, the overseer:
  1. Measures pressure
  2. Records a training episode (not just scratch prose)
  3. Heals canvas (trim scratch + dialogue)
  4. Frontier-compact-commits or server-side move
  5. Posts steer for both seats

Schema: mag_desk_overseer.v1
Trail: memory/runs/desk_overseer_trail.jsonl
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_desk_overseer.v1"
TRAIL = ROOT / "memory" / "runs" / "desk_overseer_trail.jsonl"

CANVAS_WARN_CHARS = 12_000
CANVAS_CRITICAL_CHARS = 18_000
DIALOGUE_BLOAT_CHARS = 6_000
SCRATCH_MAX_BLOCKS = 4
DIALOGUE_KEEP_BLOCKS = 10
TURN_INTERVENE = 24


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def measure_context_pressure() -> dict[str, Any]:
    """Snapshot desk context pressure — drives overseer intervention."""
    from mag.agent_desk import read_desk
    from mag.desk_dialogue import DIALOGUE_LOG, _canvas_pollution_detected, read_cursor
    from mag.desk_local_adapter import echo_without_commit_detected

    text = read_desk().get("text") or ""
    cur = read_cursor()
    turn = int(cur.get("turn") or 0)

    dlg_m = re.search(r"^##\s+Dialogue\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    dialogue_body = dlg_m.group(1) if dlg_m else text
    scratch_m = re.search(r"^##\s+Conductor scratch\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    scratch_body = scratch_m.group(1).strip() if scratch_m else ""
    scratch_blocks = len(re.findall(r"^###\s+Conductor\s*[·\-]", scratch_body, re.M))

    log_lines: list[str] = []
    if DIALOGUE_LOG.is_file():
        log_lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    echo = echo_without_commit_detected(log_lines)
    pollution = _canvas_pollution_detected(text)

    canvas_chars = len(text)
    dialogue_chars = len(dialogue_body)
    reasons: list[str] = []

    if canvas_chars >= CANVAS_CRITICAL_CHARS:
        reasons.append("canvas_critical")
    elif canvas_chars >= CANVAS_WARN_CHARS:
        reasons.append("canvas_warn")
    if dialogue_chars >= DIALOGUE_BLOAT_CHARS or "dialogue_bloat" in pollution:
        reasons.append("dialogue_bloat")
    if scratch_blocks > SCRATCH_MAX_BLOCKS:
        reasons.append("scratch_bloat")
    if echo.get("detected"):
        reasons.append("echo_without_commit")
    elif echo.get("streak", 0) >= 2:
        reasons.append("echo_streak")
    if turn >= TURN_INTERVENE and cur.get("wake_pending"):
        reasons.append("turn_stall")
    if pollution:
        reasons.extend(pollution[:3])

    intervene = bool(
        canvas_chars >= CANVAS_WARN_CHARS
        or echo.get("detected")
        or (echo.get("streak", 0) >= 2 and turn >= 8)
        or scratch_blocks > SCRATCH_MAX_BLOCKS + 2
        or (turn >= TURN_INTERVENE and cur.get("wake_pending"))
        or "dialogue_bloat" in pollution
    )

    return {
        "schema": SCHEMA,
        "ts": _utc(),
        "canvas_chars": canvas_chars,
        "dialogue_chars": dialogue_chars,
        "scratch_blocks": scratch_blocks,
        "turn": turn,
        "wake_pending": bool(cur.get("wake_pending")),
        "local_wake_pending": bool(cur.get("local_wake_pending")),
        "echo": echo,
        "pollution": pollution,
        "reasons": reasons,
        "intervene": intervene,
        "severity": "critical" if canvas_chars >= CANVAS_CRITICAL_CHARS or echo.get("detected") else (
            "warn" if intervene else "ok"
        ),
    }


def record_desk_episode(
    pressure: dict[str, Any],
    *,
    action: str,
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """File training episode — desk failures must learn, not only scratch prose."""
    from mag.desk_dialogue import read_cursor

    cur = read_cursor()
    row = {
        "schema": SCHEMA,
        "action": action,
        "pressure": {
            k: pressure.get(k)
            for k in (
                "canvas_chars",
                "dialogue_chars",
                "scratch_blocks",
                "turn",
                "reasons",
                "severity",
            )
        },
        "echo_streak": (pressure.get("echo") or {}).get("streak"),
        "outcome": outcome or {},
    }
    _trail("desk_episode", **row)
    try:
        from mag.training_events import emit

        emit(
            "desk_episode",
            join={
                "session_id": "agent-desk",
                "turn": str(cur.get("turn") or 0),
            },
            input_data={
                "reasons": pressure.get("reasons") or [],
                "canvas_chars": pressure.get("canvas_chars"),
                "echo_streak": (pressure.get("echo") or {}).get("streak"),
            },
            action={"overseer": action},
            outcome=outcome or {},
            pattern_tags=["desk_episode"] + (pressure.get("reasons") or [])[:5],
            tier_max="T2",
        )
    except Exception:
        pass
    return row


def trim_conductor_scratch(text: str, *, keep_blocks: int = SCRATCH_MAX_BLOCKS) -> tuple[str, int]:
    """Keep last N conductor scratch blocks; drop repetitive diagnosis."""
    header = "## Conductor scratch"
    idx = text.find(header)
    if idx < 0:
        return text, 0
    before = text[: idx + len(header)]
    rest = text[idx + len(header) :]
    nxt = rest.find("\n## ")
    scratch_body = rest[:nxt] if nxt >= 0 else rest
    after = rest[nxt:] if nxt >= 0 else ""

    blocks = re.split(r"(?=^###\s+Conductor\s*[·\-])", scratch_body, flags=re.M)
    blocks = [b for b in blocks if b.strip()]
    dropped = max(0, len(blocks) - keep_blocks)
    kept = blocks[-keep_blocks:] if blocks else []
    summary = (
        f"\n\n### Conductor · overseer trim\n"
        f"Trimmed {dropped} stale scratch blocks at {_utc()[:19]} — context limit recovery.\n"
    )
    new_scratch = "\n" + summary + "".join(kept) if kept else summary
    return before + new_scratch + after, dropped


def trim_dialogue_blocks(text: str, *, keep: int = DIALOGUE_KEEP_BLOCKS) -> tuple[str, int]:
    """Keep Goal + last N dialogue ### blocks."""
    goal_m = re.search(r"(^##\s+Goal\s*\n[\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    goal_block = goal_m.group(1).rstrip() + "\n\n" if goal_m else "## Goal\n(preserved by overseer)\n\n"

    dlg_idx = text.find("## Dialogue")
    if dlg_idx < 0:
        blocks = re.findall(r"(^###\s+(?:Local|DeepSeek)[\s\S]*?)(?=^###\s+|\Z)", text, re.M)
        if not blocks:
            return text, 0
        dropped = max(0, len(blocks) - keep)
        tail = "".join(blocks[-keep:])
        return f"# Agent desk\n\n{goal_block}## Dialogue\n\n{tail}\n\n## Conductor scratch\n(see below)\n", dropped

    before_dlg = text[: dlg_idx + len("## Dialogue")]
    rest = text[dlg_idx + len("## Dialogue") :]
    nxt = rest.find("\n## ")
    dlg_body = rest[:nxt] if nxt >= 0 else rest
    after = rest[nxt:] if nxt >= 0 else ""

    blocks = re.split(r"(?=^###\s+(?:Local|DeepSeek|Conductor))", dlg_body, flags=re.M)
    blocks = [b for b in blocks if b.strip() and not b.strip().startswith("### Conductor")]
    dropped = max(0, len(blocks) - keep)
    kept = blocks[-keep:]
    new_dlg = "\n\n" + "".join(kept) + "\n"
    return before_dlg + new_dlg + after, dropped


def heal_context(*, preserve_goal: bool = True) -> dict[str, Any]:
    """Trim scratch + dialogue; preserve goal."""
    from mag.agent_desk import read_desk, write_desk
    from mag.desk_dialogue import _extract_goal_sentence

    text = read_desk().get("text") or ""
    goal = _extract_goal_sentence(text) if preserve_goal else ""
    text, dlg_dropped = trim_dialogue_blocks(text)
    text, scratch_dropped = trim_conductor_scratch(text)
    if goal and "## Goal" in text:
        text = re.sub(
            r"^##\s+Goal\s*\n[\s\S]*?(?=^##\s+)",
            f"## Goal\n{goal}\n\n",
            text,
            count=1,
            flags=re.M,
        )
    write_desk(text)
    return {
        "ok": True,
        "dialogue_blocks_dropped": dlg_dropped,
        "scratch_blocks_dropped": scratch_dropped,
        "preserved_goal": bool(goal),
    }


def overseer_intervene(*, operator_note: str = "") -> dict[str, Any]:
    """Supersede stalled loop: heal context, teach (not substitute), record, retry Local."""
    from mag.desk_dialogue import post_desk_steer, read_cursor
    from mag.desk_teaching import frontier_troubleshoot, retry_local_with_skill

    pressure = measure_context_pressure()
    if not pressure.get("intervene"):
        return {"ok": True, "skipped": True, "pressure": pressure}

    heal = heal_context(preserve_goal=True)
    echo = pressure.get("echo") or {}

    # 1. Frontier troubleshoot → owned skill artifact (the point)
    teaching = frontier_troubleshoot(operator_note=operator_note, pressure=pressure, echo=echo)

    # 2. Local retries with drill packet — builds approximate higher-level op
    local_retry: dict[str, Any] | None = None
    if teaching.get("ok") and teaching.get("drill_packet"):
        local_retry = retry_local_with_skill(
            drill_packet=str(teaching["drill_packet"]),
            operator_note=operator_note,
        )

    steer_msg = (
        "OVERSEER: teaching loop — context trimmed, skill artifact filed. "
        "DeepSeek diagnosed Local failure; Local drills remedial packet (not move substitution). "
        f"Reasons: {', '.join(pressure.get('reasons') or [])}."
    )
    if teaching.get("artifact"):
        steer_msg += f" Skill: `{teaching['artifact'].get('skill_id')}`."
    steer = post_desk_steer(steer_msg)

    episode = record_desk_episode(
        pressure,
        action="overseer_teaching",
        outcome={
            "heal": heal,
            "steer_ok": steer.get("ok"),
            "teaching_ok": teaching.get("ok"),
            "skill_id": (teaching.get("artifact") or {}).get("skill_id"),
            "local_retry_ok": local_retry.get("ok") if local_retry else None,
            "wake_blocked": local_retry.get("wake_blocked") if local_retry else None,
        },
    )

    cur = read_cursor()
    return {
        "ok": True,
        "schema": SCHEMA,
        "pressure": pressure,
        "heal": heal,
        "steer": steer,
        "teaching": teaching,
        "local_retry": local_retry,
        "episode": episode,
        "cursor": cur,
        "advisory": steer_msg,
    }


def glance() -> dict[str, Any]:
    """Compact block for conductor / nervous."""
    p = measure_context_pressure()
    return {
        "schema": SCHEMA,
        "severity": p.get("severity"),
        "intervene": p.get("intervene"),
        "reasons": p.get("reasons"),
        "canvas_chars": p.get("canvas_chars"),
        "turn": p.get("turn"),
        "echo_streak": (p.get("echo") or {}).get("streak"),
        "path_trail": str(TRAIL.relative_to(ROOT)).replace("\\", "/"),
    }
