"""Orchestrator memory packets — slow/fast bandwidth adaptation for desk seats."""
from __future__ import annotations

import json
import re
from typing import Any

from config import ROOT


def _board_tail_from_canvas(text: str, *, max_lines: int = 6) -> str:
    """Extract recent move lines from ## Dialogue."""
    dlg_m = re.search(r"^##\s+Dialogue\s*$([\s\S]*?)(?=^##\s+|\Z)", text or "", re.M)
    if not dlg_m:
        return ""
    lines: list[str] = []
    for raw in dlg_m.group(1).splitlines():
        s = raw.strip()
        if not s or s.startswith("###"):
            continue
        if re.search(r"\d+\.\.?\.?|\b(O-O|Nf3|e4|exd4)\b", s, re.I):
            lines.append(s[:120])
    return " ".join(lines[-max_lines:])[:400]


def _local_failure_profile(log_lines: list[str]) -> dict[str, Any]:
    from mag.desk_local_adapter import canvas_fingerprint, canvas_quality, local_heading_stall_detected

    heading_stall = local_heading_stall_detected(log_lines)
    last_edits: list[str] = []
    for line in log_lines[-10:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") != "local":
            continue
        edit = str(o.get("canvas_edit") or "")
        if edit:
            last_edits.append(canvas_fingerprint(edit))
    repeat = len(last_edits) >= 2 and len(set(last_edits[-3:])) == 1
    last_quality = "unknown"
    for line in reversed(log_lines[-6:]):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") != "local":
            continue
        last_quality = canvas_quality(str(o.get("canvas_edit") or ""))
        break
    return {
        "heading_stall": heading_stall,
        "repeat_edit": repeat,
        "last_quality": last_quality,
    }


def build_local_memory_packet(
    *,
    fidelity: dict[str, Any],
    operator_note: str = "",
    glance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Low-bandwidth memory for slow Local seat — orchestrator acts as external memory."""
    from mag.desk_dialogue import DIALOGUE_LOG, _extract_goal_sentence
    from mag.agent_desk import read_desk
    from mag.desk_local_adapter import extract_move_line

    text = read_desk().get("text") or ""
    goal = _extract_goal_sentence(text) or ""
    board = _board_tail_from_canvas(text)
    last_remote = (fidelity.get("last_peer_message") or "").strip()
    required_line = extract_move_line(last_remote) or extract_move_line(operator_note)

    log_lines: list[str] = []
    if DIALOGUE_LOG.is_file():
        log_lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    failures = _local_failure_profile(log_lines) if log_lines else {"heading_stall": False, "repeat_edit": False}

    if failures.get("heading_stall") or failures.get("repeat_edit"):
        mode = "recovery"
    elif required_line:
        mode = "minimal"
    elif not board:
        mode = "bootstrap"
    else:
        mode = "continue"

    bullets: list[str] = []
    if goal:
        bullets.append(f"Goal: {goal[:160]}")
    elif operator_note.strip():
        bullets.append(f"Operator: {operator_note.strip()[:160]}")
    if board:
        bullets.append(f"Board so far: {board}")
    if last_remote:
        distilled = last_remote[:280].replace("\n", " ")
        bullets.append(f"DeepSeek last said: {distilled}")
    if required_line:
        bullets.append(f"Your canvas edit body (one line only): `{required_line}`")
    elif mode == "bootstrap":
        bullets.append("Your canvas edit body: one opening move line (e.g. `1. e4`)")
    if failures.get("heading_stall"):
        bullets.append("Recovery: you kept posting headings — NO ### in canvas edit, one bare line only")

    cur = (glance or {}).get("cursor") or {}
    return {
        "seat": "local",
        "bandwidth": "low",
        "mode": mode,
        "memory_bullets": bullets,
        "required_canvas_line": required_line,
        "board_tail": board,
        "goal": goal,
        "failures": failures,
        "turn": cur.get("turn"),
    }


def build_remote_memory_packet(
    *,
    fidelity: dict[str, Any],
    operator_note: str = "",
) -> dict[str, Any]:
    """High-bandwidth context for fast DeepSeek seat."""
    from mag.desk_local_adapter import extract_move_line

    last_local = (fidelity.get("last_peer_message") or "").strip()
    local_move = extract_move_line(last_local)
    return {
        "seat": "remote",
        "bandwidth": "high",
        "mode": "structure",
        "last_local_message": last_local[:2000],
        "local_canvas_move": local_move,
        "operator_note": (operator_note or "")[:800],
        "recent_dialogue": fidelity.get("recent_dialogue") or [],
        "arena": fidelity.get("arena"),
    }


def compose_local_wake_payload(
    *,
    memory: dict[str, Any],
    wake_note: str = "",
    operator_note: str = "",
) -> str:
    """Orchestrator → Local: minimal memory packet, not full canvas dump."""
    blocks = [
        "## Orchestrator memory",
        "You are **Local** (slow · low bandwidth). The orchestrator holds context for you.",
        "",
        *([f"- {b}" for b in memory.get("memory_bullets") or []] or ["- Respond on canvas"]),
    ]
    if wake_note.strip():
        blocks.extend(["", "## Conductor instruction", wake_note.strip()[:600]])
    if operator_note.strip() and operator_note.strip() not in wake_note:
        blocks.extend(["", "## Operator intent", operator_note.strip()[:400]])
    req = memory.get("required_canvas_line")
    blocks.extend(
        [
            "",
            "## Your one job",
            f"Reply: one short sentence. Canvas edit body: exactly `{req}` — nothing else."
            if req
            else "Reply: one short sentence. Canvas edit body: one move line only — no headers.",
            "",
            "## Do not",
            "- No ### Local headers in canvas edit (server wraps for you)",
            "- No descriptions, no 'Black plays', no asking operator to log",
            "",
            "## Protocol",
            "Canvas edit wakes DeepSeek. One bare line in ### Canvas edit section.",
        ]
    )
    tail = memory.get("board_tail")
    if tail:
        blocks.extend(["", "## Board reference", tail[:500]])
    return "\n".join(blocks)


def compose_remote_wake_payload(
    *,
    memory: dict[str, Any],
    wake_note: str = "",
    fidelity: dict[str, Any],
    operator_note: str = "",
) -> str:
    """Orchestrator → DeepSeek: high-fidelity structural wake."""
    blocks = [
        "## Conductor wake — you are **remote** (fast · high bandwidth)",
        "Local (slow) edited the board — respond with structure.",
    ]
    if operator_note.strip():
        blocks.append(f"\n## Operator intent\n{operator_note.strip()[:800]}")
    if wake_note.strip():
        blocks.append(f"\n## Conductor instruction\n{wake_note.strip()[:1200]}")
    last_local = memory.get("last_local_message")
    if last_local:
        blocks.append(f"\n## Last Local message\n{last_local}")
    move = memory.get("local_canvas_move")
    if move:
        blocks.append(f"\n## Local board move extracted\n`{move}`")
    recent = memory.get("recent_dialogue") or []
    if recent:
        tail = "\n".join(
            f"- {r.get('speaker')}: {(r.get('reply_preview') or r.get('canvas_preview') or '')[:200]}"
            for r in recent[-4:]
        )
        blocks.append(f"\n## Recent handoff\n{tail}")
    arena = memory.get("arena")
    if arena:
        blocks.append(f"\n## Active arena\n{json.dumps(arena)}")
    blocks.append(
        "\n## Protocol\nAlways ### Reply then ### Canvas edit. "
        "End Reply with one explicit bare line for Local's next canvas edit. "
        "Name Local's L0 limit when it truncates or echoes headers."
    )
    return "\n".join(blocks)
