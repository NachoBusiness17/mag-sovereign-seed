"""Agent desk — shared canvas + cross-lane peer context for multi-seat Chat.

Local Ask can read the shared canvas and a read-only excerpt of the remote
agent lane (DeepSeek tools) without merging sessions on disk.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

DESK_PATH = ROOT / "memory" / "working" / "agent_desk.md"
SCHEMA = "agent_desk.v1"

LOCAL_SESSION = "desk-local"
REMOTE_SESSION = "desk-deepseek"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_path(path: Path) -> str:
    """Render real or test/alternate-root paths without assuming containment."""
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_desk() -> dict[str, Any]:
    text = ""
    if DESK_PATH.is_file():
        text = DESK_PATH.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "schema": SCHEMA,
        "path": _display_path(DESK_PATH),
        "text": text,
        "updated": _now() if text else None,
        "local_session": LOCAL_SESSION,
        "remote_session": REMOTE_SESSION,
    }


def write_desk(text: str) -> dict[str, Any]:
    DESK_PATH.parent.mkdir(parents=True, exist_ok=True)
    DESK_PATH.write_text(text or "", encoding="utf-8")
    return read_desk()


def set_desk_section(section: str, body: str) -> dict[str, Any]:
    """Replace ## Section body until the next ## heading."""
    section = (section or "").strip().lstrip("#").strip()
    body = (body or "").strip()
    if not section:
        return read_desk()
    text = (read_desk().get("text") or "").strip()
    if not text:
        text = DESK_TEMPLATE.strip()
    header = f"## {section}"
    if header not in text:
        text = text.rstrip() + f"\n\n{header}\n{body}\n"
        return write_desk(text)
    idx = text.find(header)
    rest = text[idx + len(header) :]
    nxt = rest.find("\n## ")
    if nxt >= 0:
        text = text[: idx + len(header)] + "\n" + body + "\n" + text[idx + len(header) + nxt :]
    else:
        text = text[: idx + len(header)] + "\n" + body + "\n"
    return write_desk(text)


def set_desk_goal(goal: str) -> dict[str, Any]:
    return set_desk_section("Goal", (goal or "").strip())


def commit_operator_intent(*, goal: str = "", note: str = "", author: str = "operator") -> dict[str, Any]:
    """Canvas-first routing — persist operator intent before any seat wakes."""
    out: dict[str, Any] = {"ok": True, "committed": []}
    g = (goal or "").strip()
    n = (note or "").strip()
    if g:
        set_desk_goal(g)
        out["committed"].append("goal")
    if n:
        append_desk_section("Operator notes", n, author=author)
        out["committed"].append("operator_note")
    out.update(read_desk())
    return out


def _read_agent_messages(session_id: str, last_n: int = 12) -> list[dict[str, Any]]:
    from mag.chat_source import agent_session_path

    path = agent_session_path(session_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    msgs = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(msgs, list):
        return []
    out: list[dict[str, Any]] = []
    for m in msgs[-last_n:]:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(x.get("text") or x) for x in content if isinstance(x, dict)
            )
        text = str(content or m.get("text") or "").strip()
        if text:
            out.append({"role": role, "text": text[:2000]})
    return out


def peer_lane_excerpt(session_id: str, *, last_n: int = 10) -> str:
    """Read-only transcript excerpt for cross-lane Ask context."""
    msgs = _read_agent_messages(session_id, last_n=last_n)
    if not msgs:
        return ""
    lines = [f"[{m['role']}] {m['text']}" for m in msgs]
    return "\n\n".join(lines)


def desk_snapshot(*, peer_last_n: int = 10) -> dict[str, Any]:
    desk = read_desk()
    peer = peer_lane_excerpt(REMOTE_SESSION, last_n=peer_last_n)
    return {
        **desk,
        "peer_session": REMOTE_SESSION,
        "peer_excerpt": peer,
        "peer_chars": len(peer),
    }


DESK_TEMPLATE = """# Agent desk

Shared surface — Local and DeepSeek take turns on ## Dialogue. **No tools here.** Execute in Shell/Workers.

Operator manual: `docs/agent_desk_operator_manual.md`

## Goal
(one clear sentence — what success looks like)

## Dialogue
(turn-based — `### Local ·` and `### DeepSeek ·` blocks only)

## Meta
(DeepSeek Meta-A ↔ Meta-B strategy — does not wake Local)

## Conductor scratch
(Conductor-maintained running summary — handoff state for both seats)

## Operator notes
(your binding decisions — agents propose, you decide)

## Open questions
(optional — park unresolved items)
"""


def ensure_desk_template() -> dict[str, Any]:
    desk = read_desk()
    if not (desk.get("text") or "").strip():
        return write_desk(DESK_TEMPLATE)
    return desk


def append_desk_section(
    section: str,
    body: str,
    *,
    author: str = "operator",
) -> dict[str, Any]:
    """Append under ## Dialogue with ### Speaker · title (never orphan lane sections)."""
    section = (section or "Notes").strip().lstrip("#").strip()
    body = (body or "").strip()
    if not body:
        return read_desk()

    sec_lower = section.lower()
    if sec_lower in ("local (orchestrator)", "local", "local orchestrator"):
        block = f"### Local · {author or 'operator pin'}\n{body}"
        return append_desk_raw(block)
    if sec_lower in ("remote (deepseek)", "remote", "deepseek"):
        block = f"### DeepSeek · {author or 'operator pin'}\n{body}"
        return append_desk_raw(block)
    if sec_lower in ("dialogue", "notes"):
        block = f"### Operator · {author or 'note'}\n{body}"
        return append_desk_raw(block)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n\n### {author} · {stamp}\n{body}\n"
    text = (read_desk().get("text") or "").strip()
    if not text:
        text = DESK_TEMPLATE.strip()

    header = f"## {section}"
    idx = text.find(header)
    if idx >= 0:
        rest = text[idx + len(header) :]
        nxt = rest.find("\n## ")
        if nxt >= 0:
            insert_at = idx + len(header) + nxt
            text = text[:insert_at] + block + text[insert_at:]
        else:
            text = text.rstrip() + block
    else:
        text = text.rstrip() + f"\n\n{header}{block}"

    return write_desk(text)


def append_desk_raw(block: str) -> dict[str, Any]:
    """Append pre-formatted markdown (dialogue turns with their own headers)."""
    block = (block or "").strip()
    if not block:
        return read_desk()
    text = (read_desk().get("text") or "").strip()
    text = text.rstrip() + "\n\n" + block + "\n"
    return write_desk(text)


def append_desk_meta_raw(block: str) -> dict[str, Any]:
    """Append under ## Meta (strategy lane — separate from main Dialogue)."""
    block = (block or "").strip()
    if not block:
        return read_desk()
    text = (read_desk().get("text") or "").strip()
    if not text:
        text = DESK_TEMPLATE.strip()
    header = "## Meta"
    if header not in text:
        anchor = "## Operator notes"
        if anchor in text:
            text = text.replace(anchor, f"{header}\n\n{anchor}", 1)
        else:
            text = text.rstrip() + f"\n\n{header}\n"
    idx = text.find(header)
    rest = text[idx + len(header) :]
    nxt = rest.find("\n## ")
    if nxt >= 0:
        insert_at = idx + len(header) + nxt
        text = text[:insert_at].rstrip() + "\n\n" + block + "\n" + text[insert_at:]
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    return write_desk(text)
