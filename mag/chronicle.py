"""Chronicle payload — file-backed events with layman labels (no fake AI commentary)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

CHRONICLE = ROOT / "memory" / "running_commentary.md"
ATTENTION = ROOT / "memory" / "attention.md"
BONDS = ROOT / "memory" / "bonds_active.md"


def _attention_events(limit: int = 10) -> list[dict[str, Any]]:
    if not ATTENTION.is_file():
        return []
    text = ATTENTION.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n---+\n", text)
    out: list[dict[str, Any]] = []
    for block in blocks:
        m_sess = re.search(r"session:\s*`([^`]+)`", block)
        m_seat = re.search(r"seat:\s*`([^`]+)`", block)
        if not m_sess:
            continue
        sid = m_sess.group(1).strip()
        seat = (m_seat.group(1) if m_seat else "unknown").strip()
        if "cursor" in sid.lower() or seat == "cursor":
            layman = "Cursor filed a work session to Mag disk"
        elif seat == "mag_agent":
            layman = "Mag agent turn filed a session bead"
        elif seat == "grok_tui" or seat == "grok":
            layman = "Grok TUI run closed and filed"
        else:
            layman = f"Session filed from seat {seat}"
        out.append({
            "kind": "filed_session",
            "session_id": sid,
            "seat": seat,
            "layman": layman,
            "proof": "memory/attention.md",
            "technical": f"session `{sid}` seat `{seat}`",
        })
        if len(out) >= limit:
            break
    return out


def build_chronicle_payload() -> dict[str, Any]:
    """Structured chronicle for API + markdown file from synthesis_agent."""
    from mag.seat_feed import unified_seat_feed
    from mag.seats import build_workers_summary

    events: list[dict[str, Any]] = []
    events.extend(_attention_events(8))

    feed = unified_seat_feed(limit=15)
    for e in feed.get("entries") or []:
        src = e.get("source") or "?"
        if src == "cursor":
            layman = "Cursor bridge activity"
        elif src == "grok":
            layman = "Grok hook fired"
        elif src == "orchestrator":
            layman = "Sub-agent worker log line"
        else:
            layman = f"{src} activity"
        events.append({
            "kind": "feed",
            "source": src,
            "ts": e.get("ts"),
            "layman": layman,
            "preview": (e.get("preview") or "")[:160],
            "proof": feed.get("paths", {}).get(f"{src}_feed") or "memory/agent_sessions/",
            "technical": f"{src} · {e.get('event') or 'event'}",
        })

    workers = build_workers_summary(recent_hours=24.0)
    for w in workers.get("running") or []:
        events.append({
            "kind": "worker",
            "status": "running",
            "task_id": w.get("task_id"),
            "layman": f"Worker running: {(w.get('goal') or '')[:60]}",
            "proof": "memory/runs/orchestrator/tasks/",
            "technical": w.get("task_id"),
        })

    content = ""
    updated = None
    if CHRONICLE.is_file():
        try:
            content = CHRONICLE.read_text(encoding="utf-8")
            updated = datetime.fromtimestamp(
                CHRONICLE.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")
        except OSError:
            content = "Chronicle unreadable"
    else:
        content = (
            "Waiting for synthesis_agent.py — run `python synthesis_agent.py` "
            "or start Mag lab."
        )

    bonds_line = None
    if BONDS.is_file():
        m = re.search(r"Ingested `([^`]+)`", BONDS.read_text(encoding="utf-8", errors="replace")[:500])
        if m:
            bonds_line = m.group(1)

    return {
        "ok": True,
        "schema": "mag_chronicle.v2",
        "content": content,
        "updated": updated,
        "events": events[:20],
        "bonds_updated": bonds_line,
        "workers_layman": workers.get("layman"),
        "sources": [
            "memory/attention.md",
            "memory/running_commentary.md",
            "watch/cursor_feed.jsonl",
            "watch/grok_feed.jsonl",
            "memory/agent_sessions/",
            "memory/runs/orchestrator/tasks/",
        ],
        "honesty": {
            "layman": "Each line cites a file Mag read — not model invention.",
            "interpretation": "Commentary block in markdown is template text unless labeled otherwise.",
        },
    }
