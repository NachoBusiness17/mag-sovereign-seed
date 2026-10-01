"""TV-safe display payload — read-only ambient viewport for Roku / wall clients.

Poll `GET /api/v1/display` from a thin receiver channel (BrightScript, tablet browser).
Not the full dashboard — structured text only, no secrets.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_display.v1"
TRUST_PATH = ROOT / "memory" / "working" / "agent_desk_trust_status.json"
CURSOR_PATH = ROOT / "memory" / "working" / "agent_desk_cursor.json"
DESK_PATH = ROOT / "memory" / "working" / "agent_desk.md"
CHRONICLE = ROOT / "memory" / "running_commentary.md"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _desk_goal(text: str) -> str:
    m = re.search(r"^##\s+Goal\s*\n+(.+?)(?:\n##|\Z)", text or "", re.M | re.S)
    if not m:
        return ""
    line = m.group(1).strip().splitlines()[0].strip()
    return line[:240]


def _desk_dialogue_tail(text: str, *, lines: int = 4) -> list[str]:
    if "## Dialogue" not in (text or ""):
        return []
    _, _, tail = text.partition("## Dialogue")
    out: list[str] = []
    for raw in tail.splitlines():
        s = raw.strip()
        if not s or s.startswith("<!--"):
            continue
        if s.startswith("###"):
            out.append(s.lstrip("#").strip()[:160])
        elif out:
            out[-1] = (out[-1] + " " + s)[:160]
        if len(out) >= lines:
            break
    return out


def build_display_payload(*, event_limit: int = 8, fast: bool = False) -> dict[str, Any]:
    """Compose a TV-safe JSON slice: pulse, body, desk, trust.

    ``fast`` is for the ambient cast receiver: it must render while a provider,
    Docker host, or Ollama endpoint is down, so it never performs remote health
    probes on the HTTP request thread.
    """
    from mag.chronicle import build_chronicle_payload

    if fast:
        # The full chronicle walks worker/task history. Ambient and brain
        # observers only need the durable headline; keep that path bounded.
        chronicle = {"content": "", "updated": None, "events": [], "workers_layman": ""}
        try:
            if CHRONICLE.is_file():
                chronicle["content"] = CHRONICLE.read_text(
                    encoding="utf-8", errors="replace"
                )[:12000]
                chronicle["updated"] = datetime.fromtimestamp(
                    CHRONICLE.stat().st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC")
        except OSError:
            chronicle["content"] = "Chronicle unreadable"
    else:
        chronicle = build_chronicle_payload()
    if fast:
        nervous = {"body": {"dashboard_8765": False, "ollama_11434": False,
                             "integral_ok": False}}
    else:
        from mag.nervous_system import build_glance
        nervous = build_glance(write=False)
    body = nervous.get("body") or {}
    desk_trust = nervous.get("desk_trust") or _read_json(TRUST_PATH)
    cursor = _read_json(CURSOR_PATH)
    desk_text = DESK_PATH.read_text(encoding="utf-8", errors="replace") if DESK_PATH.is_file() else ""

    events: list[str] = []
    for e in chronicle.get("events") or []:
        if not isinstance(e, dict):
            continue
        layman = str(e.get("layman") or e.get("preview") or "").strip()
        if layman:
            events.append(layman[:200])
        if len(events) >= event_limit:
            break

    pulse = (chronicle.get("content") or "").strip().splitlines()
    headline = ""
    for line in pulse:
        s = line.strip().lstrip("#").strip()
        if s and not s.startswith("_") and s != "---":
            headline = s[:200]
            break
    if not headline:
        headline = str(chronicle.get("workers_layman") or "Mag pulse — waiting for activity")

    dash_up = bool(body.get("dashboard_8765"))
    ollama_up = bool(body.get("ollama_11434"))
    status_line = (
        f"Dashboard {'UP' if dash_up else 'DOWN'}"
        f" · Ollama {'UP' if ollama_up else 'DOWN'}"
    )
    if desk_trust:
        status_line += (
            f" · trust tier {desk_trust.get('tier', '?')}"
            f" · ui {desk_trust.get('ui_smoke_score', '?')}"
        )

    holder = str(cursor.get("holder") or "operator")
    remote_asleep = cursor.get("remote_asleep")
    cursor_line = holder
    if remote_asleep is True:
        cursor_line += " · DeepSeek asleep"

    try:
        from mag.local_pulse import build_local_pulse

        local_pulse = build_local_pulse()
    except Exception as exc:
        local_pulse = {"ok": False, "state": "offline", "error": str(exc)[:120]}

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "headline": headline,
        "status": status_line,
        "events": events,
        "desk": {
            "goal": _desk_goal(desk_text),
            "dialogue_tail": _desk_dialogue_tail(desk_text),
            "cursor": cursor_line,
        },
        "trust": desk_trust or None,
        "local_pulse": {
            "state": local_pulse.get("state"),
            "thinking": bool(local_pulse.get("thinking")),
            "headline": local_pulse.get("headline"),
            "cpu_system_pct": (local_pulse.get("cpu") or {}).get("system_pct"),
        },
        "body": {
            "dashboard_up": dash_up,
            "ollama_up": ollama_up,
            "integral_ok": bool(nervous.get("integral_ok")),
        },
        "chronicle_updated": chronicle.get("updated"),
        "poll_seconds": 15,
        "note": "Read-only ambient viewport. Bind LAN or Tailscale; do not expose publicly.",
    }
