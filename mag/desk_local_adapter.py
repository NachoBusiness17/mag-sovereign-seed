"""Adapt Local (L0) desk output to protocol — extract moves, block heading-only stalls."""
from __future__ import annotations

import json
import re
from typing import Any

# Full move line: 4... exd4, 5. O-O, 1. e4
_MOVE_LINE = re.compile(
    r"(\d+\.\.\.\s*(?:O-O-O|O-O|[NBRQK]?[a-h]?x?[a-h][1-8](?:=[NBRQ])?[+#]?)"
    r"|\d+\.\s*(?:O-O-O|O-O|[NBRQK]?[a-h]?x?[a-h][1-8](?:=[NBRQ])?[+#]?))",
    re.I,
)
_BACKTICK = re.compile(r"`([^`]+)`")
_LOCAL_HEADER = re.compile(r"^###\s+Local\s*[·\-][^\n]*\n?", re.I | re.M)
_PLAYS_WRAPPER = re.compile(r"^(?:Black|White)\s+plays\s+", re.I)


def extract_move_line(text: str) -> str:
    """Best-effort chess move line from noisy Local output."""
    t = (text or "").strip()
    if not t:
        return ""
    m = _BACKTICK.search(t)
    if m:
        t = m.group(1).strip()
    t = _LOCAL_HEADER.sub("", t).strip()
    t = _PLAYS_WRAPPER.sub("", t).strip()
    hit = _MOVE_LINE.search(t)
    if hit:
        return hit.group(1).strip()
    for pat in (
        r"\b(O-O-O|O-O|[NBRQK]?[a-h]?x?[a-h][1-8](?:=[NBRQ])?[+#]?)\b",
        r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b",
    ):
        m = re.search(pat, t, re.I)
        if m:
            return m.group(1)
    return ""


def canvas_fingerprint(edit: str) -> str:
    return re.sub(r"\s+", " ", (edit or "").strip().lower())[:240]


def canvas_quality(edit: str) -> str:
    """move | heading_only | empty | prose"""
    raw = (edit or "").strip()
    if not raw:
        return "empty"
    body = _LOCAL_HEADER.sub("", raw).strip()
    if not body:
        return "heading_only"
    if _PLAYS_WRAPPER.match(body) and not extract_move_line(body):
        return "heading_only"
    if extract_move_line(raw):
        return "move"
    if re.match(r"^###\s+Local\s*[·\-]\s*(title|orchestrator)\s*$", raw, re.I | re.M):
        return "heading_only"
    return "prose"


def format_local_canvas(move_line: str) -> str:
    line = (move_line or "").strip()
    if not line:
        return ""
    return f"### Local · move\n{line}\n"


def normalize_local_canvas_edit(
    canvas_edit: str,
    *,
    reply: str = "",
    operator_note: str = "",
) -> tuple[str, dict[str, Any]]:
    """Rewrite Local canvas edit into minimal move block; mine reply/operator for payload."""
    before = canvas_quality(canvas_edit)
    meta: dict[str, Any] = {
        "normalized": False,
        "stall_break": False,
        "quality_before": before,
        "quality_after": before,
        "extracted_from": None,
    }

    line = extract_move_line(canvas_edit)
    src = "canvas"
    if not line:
        line = extract_move_line(reply)
        src = "reply" if line else src
    if not line:
        line = extract_move_line(operator_note)
        src = "operator_note" if line else src

    if line:
        normalized = format_local_canvas(line)
        meta["normalized"] = normalized.strip() != (canvas_edit or "").strip()
        meta["stall_break"] = before == "heading_only" and meta["normalized"]
        meta["quality_after"] = "move"
        meta["extracted_from"] = src
        meta["move_line"] = line
        return normalized, meta

    meta["quality_after"] = before
    return canvas_edit, meta


def local_heading_stall_detected(
    log_lines: list[str],
    *,
    threshold: int = 3,
    tail: int = 12,
) -> bool:
    """True when Local repeats the same heading-only canvas edit."""
    import json

    fps: list[str] = []
    for line in log_lines[-tail:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") != "local":
            continue
        edit = str(o.get("canvas_edit") or "")
        if canvas_quality(edit) != "heading_only":
            continue
        fps.append(canvas_fingerprint(edit))
    if len(fps) < threshold:
        return False
    return len(set(fps[-threshold:])) == 1


_PROMISE_ECHO = re.compile(
    r"^(?:Understood|Sure|OK|Okay|I will|I'll|I am going to|Got it)\b",
    re.I,
)


def echo_without_commit_detected(
    log_lines: list[str],
    *,
    threshold: int = 3,
    tail: int = 16,
) -> dict[str, Any]:
    """Local promised a canvas edit in Reply but wake was blocked — echo-without-commit."""
    streak = 0
    last_move = ""
    last_reply = ""
    for line in log_lines[-tail:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") != "local":
            continue
        reply = str(o.get("reply") or "").strip()
        adapter = o.get("local_adapter") or {}
        wake_blocked = bool(o.get("wake_blocked"))
        quality = adapter.get("quality_after") or ""
        promised = bool(_PROMISE_ECHO.match(reply)) or "commit" in reply.lower()
        if wake_blocked or (promised and quality != "move"):
            streak += 1
            last_reply = reply
            last_move = str(adapter.get("move_line") or extract_move_line(reply) or "")
        elif quality == "move" and not wake_blocked:
            streak = 0
    return {
        "detected": streak >= threshold,
        "streak": streak,
        "threshold": threshold,
        "last_move": last_move,
        "last_reply_preview": last_reply[:200],
    }
