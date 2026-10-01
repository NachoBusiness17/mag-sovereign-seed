"""Seats registry — inbound clients + outbound providers for the Body tab.

Layman labels + file-backed proof. Mag does not invent online status from chat.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

AGENT_SESS = ROOT / "memory" / "agent_sessions"
ATTENTION = ROOT / "memory" / "attention.md"
BONDS = ROOT / "memory" / "bonds_active.md"
WATCH = ROOT / "watch"
USAGE = ROOT / "logs" / "usage.jsonl"


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s.replace(" ", "T") if "T" not in s[:20] else s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _age_label(ts: datetime | None) -> str:
    if ts is None:
        return "never seen"
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    sec = max(0, int((now - ts).total_seconds()))
    if sec < 60:
        return f"{sec}s ago"
    if sec < 3600:
        return f"{sec // 60}m ago"
    if sec < 86400:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"


def _mtime_ts(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _tail_jsonl(path: Path, n: int = 30) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-n:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _attention_sessions(limit: int = 8) -> list[dict[str, Any]]:
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
        seat = (m_seat.group(1) if m_seat else "").strip() or "unknown"
        out.append({"session_id": sid, "seat": seat, "block": block[:400]})
        if len(out) >= limit:
            break
    return out


def _agent_seat_activity() -> dict[str, dict[str, Any]]:
    """Latest activity per inbound seat from agent_sessions/."""
    by_seat: dict[str, dict[str, Any]] = {}
    if not AGENT_SESS.is_dir():
        return by_seat
    for path in AGENT_SESS.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        stem = path.stem
        provider = str(data.get("provider") or "").lower()
        source = str(data.get("source") or "").lower()
        if stem.startswith("cursor") or provider == "cursor" or source == "cursor":
            seat_id = "cursor"
        elif stem in ("deepseek", "dashboard") or provider == "deepseek":
            seat_id = "dashboard"
        elif stem == "cli":
            seat_id = "mag_cli"
        elif stem.startswith("orc-"):
            seat_id = "orchestrator"
        else:
            seat_id = f"agent:{stem}"
        ts = _parse_ts(data.get("updated_at")) or _mtime_ts(path)
        prev = by_seat.get(seat_id)
        if prev and prev.get("_ts") and ts and ts <= prev["_ts"]:
            continue
        msgs = data.get("messages") or []
        preview = ""
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "user":
                preview = str(m.get("content") or "")[:120]
                break
        by_seat[seat_id] = {
            "_ts": ts,
            "last_at": ts.isoformat() if ts else None,
            "age": _age_label(ts),
            "session_id": data.get("session_id") or stem,
            "preview": preview,
            "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "provider": provider or source or stem,
        }
    return by_seat


def _feed_last(source: str, path: Path) -> dict[str, Any] | None:
    rows = _tail_jsonl(path, 5)
    if not rows:
        return None
    last = rows[-1]
    ts = _parse_ts(last.get("ts")) or _mtime_ts(path)
    return {
        "last_at": ts.isoformat() if ts else None,
        "age": _age_label(ts),
        "preview": str(last.get("prompt_preview") or last.get("response_preview") or "")[:120],
        "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "event": last.get("hook_event"),
    }


def _outbound_seats() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from models.providers import status_table
        from models.quota import all_budgets

        st = status_table()
        budgets = {b.get("provider"): b for b in (all_budgets().get("providers") or [])}
        for row in st.get("providers") or []:
            pid = row.get("id") or "?"
            b = budgets.get(pid) or {}
            live = bool(row.get("configured"))
            local = bool(row.get("free_local"))
            if local:
                layman = f"Local models on your PC ({row.get('default_model') or 'ollama'})"
            else:
                layman = f"Mag can call {row.get('name') or pid} when you dispatch or agent runs"
            pct = None
            max_c = b.get("max_calls")
            used_c = int(b.get("used_calls") or 0)
            if max_c:
                pct = round(100.0 * used_c / max_c, 1)
            rows.append({
                "id": pid,
                "direction": "outbound",
                "label": row.get("name") or pid,
                "layman": layman,
                "live": live,
                "local": local,
                "model": row.get("default_model"),
                "pct_used": pct,
                "key_env": row.get("key_env"),
                "source_path": "configs/providers.yaml",
                "mag_knows": "Key present + Mag-tracked budget from logs/quota_state.json",
                "mag_does_not_know": "Vendor subscription UI % (Grok TUI, ChatGPT web plan)",
            })
    except Exception as e:
        rows.append({
            "id": "_error",
            "direction": "outbound",
            "label": "providers",
            "layman": f"Could not load provider table: {str(e)[:80]}",
            "live": False,
            "source_path": "configs/providers.yaml",
        })
    rows.sort(key=lambda r: (0 if r.get("live") else 1, r.get("id") or ""))
    return rows


def _inbound_seats() -> list[dict[str, Any]]:
    activity = _agent_seat_activity()
    cursor_feed = _feed_last("cursor", WATCH / "cursor_feed.jsonl")
    grok_feed = _feed_last("grok", WATCH / "grok_feed.jsonl")
    att = _attention_sessions(3)
    bonds_mtime = _mtime_ts(BONDS)

    def _merge(seat_id: str, label: str, layman: str, **extra: Any) -> dict[str, Any]:
        act = activity.get(seat_id) or {}
        return {
            "id": seat_id,
            "direction": "inbound",
            "label": label,
            "layman": layman,
            "live": bool(act.get("last_at") or extra.get("feed")),
            "last_at": act.get("last_at") or (extra.get("feed") or {}).get("last_at"),
            "age": act.get("age") or (extra.get("feed") or {}).get("age") or "never seen",
            "session_id": act.get("session_id"),
            "preview": act.get("preview") or (extra.get("feed") or {}).get("preview"),
            "source_path": act.get("source_path") or (extra.get("feed") or {}).get("source_path"),
            "mag_knows": extra.get("mag_knows", "Filed sessions + agent_sessions JSON on disk"),
            "mag_does_not_know": extra.get(
                "mag_does_not_know",
                "IDE subscription usage — only what Mag filed as sessions",
            ),
        }

    seats = [
        _merge(
            "cursor",
            "Cursor IDE",
            "IDE assistant talks to Mag over :8765 REST (context-pack + agent turns)",
            feed=cursor_feed,
            mag_knows="cursor_bridge.py hits /api/v1/agent; sessions file as mag-agent-cursor-*",
            mag_does_not_know="Cursor billing, model picker, or chat outside Mag bridge",
        ),
        _merge(
            "dashboard",
            "Dashboard Chat",
            "Browser chat on this page — DeepSeek + tools or local Ollama",
            mag_knows="POST /api/v1/agent from dashboard; memory/agent_sessions/deepseek.json",
        ),
        _merge(
            "mag_cli",
            "Mag CLI",
            "Terminal agent: mag.cmd agent --provider deepseek",
            mag_knows="memory/agent_sessions/cli.json + briefs",
        ),
        _merge(
            "grok_tui",
            "Grok TUI (L2)",
            "Scarce judgment seat — Grok harness, not API providers.yaml",
            feed=grok_feed,
            mag_knows="watch/grok_feed.jsonl hooks + grok escalation count in logs/usage.jsonl",
            mag_does_not_know="Grok TUI plan % — check x.com / Grok UI",
        ),
    ]

    if att:
        latest = att[0]
        for s in seats:
            if s["id"] == "cursor" and "cursor" in latest.get("session_id", ""):
                s["last_filed"] = latest["session_id"]
                s["live"] = True
            if bonds_mtime and (s.get("last_at") is None or _parse_ts(s.get("last_at"))):
                bt = _parse_ts(s.get("last_at"))
                if bt is None or bonds_mtime > bt:
                    s["bonds_updated"] = bonds_mtime.isoformat()
                    s["age"] = _age_label(bonds_mtime)

    return seats


def build_workers_summary(*, recent_hours: float = 48.0) -> dict[str, Any]:
    """Orchestrator sub-agents: running + recent only — not historical soak corpses."""
    from mag.orchestrator import TASK_DIR, TERMINAL

    now = datetime.now(timezone.utc)
    running: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    archived_n = 0
    if TASK_DIR.is_dir():
        for p in TASK_DIR.glob("*.json"):
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            st = t.get("status") or "?"
            if st not in TERMINAL:
                running.append(_worker_row(t))
                continue
            created = _parse_ts(t.get("created_at") or t.get("ended_at"))
            if created and (now - created).total_seconds() <= recent_hours * 3600:
                recent.append(_worker_row(t))
            else:
                archived_n += 1
    recent.sort(key=lambda r: r.get("created") or "", reverse=True)
    recent = recent[:12]
    return {
        "running": running,
        "recent": recent,
        "archived_hidden": archived_n,
        "recent_hours": recent_hours,
        "source_path": "memory/runs/orchestrator/tasks/*.json",
        "layman": (
            f"{len(running)} worker(s) running now · "
            f"{len(recent)} finished in last {int(recent_hours)}h · "
            f"{archived_n} older hidden"
        ),
    }


def _worker_row(t: dict[str, Any]) -> dict[str, Any]:
    goal = t.get("goal") or ""
    if not goal:
        cmd = t.get("cmd") or []
        try:
            i = cmd.index("--query")
            goal = cmd[i + 1] if i + 1 < len(cmd) else ""
        except ValueError:
            goal = ""
    sid = t.get("session_id") or t.get("bio_session_id")
    return {
        "task_id": t.get("task_id"),
        "status": t.get("status"),
        "goal": str(goal)[:100],
        "tag": t.get("tag"),
        "provider": t.get("provider"),
        "created": t.get("created_at"),
        "session_id": sid,
        "bead_hint": f"memory/briefs/mag-agent-{sid}.md" if sid else None,
    }


def build_seats_registry() -> dict[str, Any]:
    """Full Body tab payload: inbound + outbound seats + workers."""
    inbound = _inbound_seats()
    outbound = _outbound_seats()
    workers = build_workers_summary()
    n_live_out = sum(1 for s in outbound if s.get("live"))
    n_active_in = sum(1 for s in inbound if s.get("live") or s.get("age", "never") != "never seen")

    headline_parts = []
    if n_live_out:
        headline_parts.append(f"{n_live_out} API route(s) live")
    else:
        headline_parts.append("no remote API keys")
    if workers["running"]:
        headline_parts.append(f"{len(workers['running'])} worker running")
    cursor = next((s for s in inbound if s["id"] == "cursor"), None)
    if cursor and cursor.get("age") != "never seen":
        headline_parts.append(f"Cursor {cursor['age']}")

    return {
        "ok": True,
        "schema": "mag_seats.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "headline": " · ".join(headline_parts) or "Seats registry",
        "inbound": inbound,
        "outbound": outbound,
        "workers": workers,
        "counts": {
            "inbound": len(inbound),
            "outbound_live": n_live_out,
            "outbound_total": len(outbound),
            "inbound_active": n_active_in,
            "workers_running": len(workers["running"]),
        },
        "honesty": {
            "layman": "Seats = who talks to Mag (inbound) and who Mag calls (outbound). Files on disk are proof.",
            "mag_knows": "agent_sessions/, watch/*_feed.jsonl, orchestrator tasks, providers.yaml keys",
            "mag_does_not_know": "External IDE billing, Grok TUI plan %, ChatGPT subscription %",
        },
        "sources": [
            "memory/agent_sessions/",
            "watch/cursor_feed.jsonl",
            "watch/grok_feed.jsonl",
            "memory/attention.md",
            "configs/providers.yaml",
            "memory/runs/orchestrator/tasks/",
        ],
    }
