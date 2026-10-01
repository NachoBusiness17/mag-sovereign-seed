"""Unified seat activity feed — Grok hooks, Cursor hooks, agent sessions, orchestrator."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

WATCH = ROOT / "watch"
AGENT_SESS = ROOT / "memory" / "agent_sessions"
ORCH_LOG = ROOT / "logs" / "orchestrator"


def _clip(s: str | None, n: int = 220) -> str:
    t = (s or "").replace("\r", " ").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1].strip() + "…"


def _tail_jsonl(path: Path, n: int = 25) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _agent_entries(limit: int = 12) -> list[dict[str, Any]]:
    if not AGENT_SESS.is_dir():
        return []
    files = sorted(AGENT_SESS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    entries: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        msgs = data.get("messages") or []
        preview = ""
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "user":
                preview = _clip(str(m.get("content") or ""))
                break
        if not preview and msgs:
            preview = _clip(str((msgs[-1] or {}).get("content") or ""))
        seat = path.stem
        provider = str(data.get("provider") or "agent")
        src = "deepseek" if provider == "deepseek" else "agent"
        if seat.startswith("cursor-"):
            src = "cursor"
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        entries.append(
            {
                "source": src,
                "seat": seat,
                "ts": data.get("updated_at") or mtime,
                "event": "session",
                "preview": preview or f"({len(msgs)} messages)",
                "session_id": data.get("session_id") or seat,
                "provider": provider,
            }
        )
    return entries


def _orch_entries(limit: int = 8) -> list[dict[str, Any]]:
    if not ORCH_LOG.is_dir():
        return []
    logs = sorted(ORCH_LOG.glob("*.out.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    entries: list[dict[str, Any]] = []
    for path in logs[:limit]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        preview = _clip(lines[-1] if lines else "")
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        entries.append(
            {
                "source": "orchestrator",
                "seat": path.stem,
                "ts": mtime,
                "event": "log",
                "preview": preview,
                "session_id": path.stem,
            }
        )
    return entries


def unified_seat_feed(*, limit: int = 40) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []

    for rec in _tail_jsonl(WATCH / "grok_feed.jsonl", 20):
        entries.append(
            {
                "source": "grok",
                "seat": "grok_tui",
                "ts": rec.get("ts"),
                "event": rec.get("hook_event"),
                "preview": _clip(rec.get("prompt_preview") or rec.get("tool_input_preview")),
                "session_id": rec.get("session_id"),
                "tool": rec.get("tool_name"),
            }
        )

    for rec in _tail_jsonl(WATCH / "cursor_feed.jsonl", 20):
        entries.append(
            {
                "source": "cursor",
                "seat": "cursor",
                "ts": rec.get("ts"),
                "event": rec.get("hook_event"),
                "preview": _clip(rec.get("prompt_preview") or rec.get("response_preview")),
                "session_id": rec.get("session_id"),
                "model": rec.get("model"),
            }
        )

    entries.extend(_agent_entries(12))
    entries.extend(_orch_entries(8))

    entries.sort(key=lambda e: str(e.get("ts") or ""), reverse=True)
    trimmed = entries[: max(1, min(limit, 80))]

    counts: dict[str, int] = {}
    for e in entries:
        src = str(e.get("source") or "unknown")
        counts[src] = counts.get(src, 0) + 1

    live = ROOT / "memory" / "live_from_grok.md"
    live_cursor = ROOT / "memory" / "live_from_cursor.md"
    return {
        "ok": True,
        "schema": "seat_feed.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "entries": trimmed,
        "counts": counts,
        "paths": {
            "grok_feed": str(WATCH / "grok_feed.jsonl"),
            "cursor_feed": str(WATCH / "cursor_feed.jsonl"),
            "live_grok": str(live) if live.is_file() else None,
            "live_cursor": str(live_cursor) if live_cursor.is_file() else None,
        },
    }
