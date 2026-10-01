"""session_bridge — cross-session communication relay with riddler sanitization.

Problem: OpenClaw sessions are tree-isolated. They cannot see each other.
Solution: Filesystem bus. Every session writes to a per-session outbox.
The bridge polls all outboxes, sanitizes via riddler, publishes to shared inbox.
Sessions read the inbox to see what the swarm discussed.

This is the "one window that talks to all sessions" — the inbox is the window.
Sanitization is the riddler process: surrogate stories, no private map.

No model calls. Deterministic. $0 by construction.
"""
from __future__ import annotations

import argparse
import calendar
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
OUTBOXES = BRIDGE / "outboxes"
INBOX = BRIDGE / "inbox" / "broadcast.jsonl"
WINDOW = BRIDGE / "window.md"  # Human-readable aggregate
RELAY_STATE = BRIDGE / "relay_state.json"
RECEIPTS = ROOT / "memory" / "runs" / "session_bridge" / "receipts.jsonl"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slug(s: str) -> str:
    return s.replace(":", "_").replace("/", "_")[:40]


# ── Sanitization import ──
# We import riddler_sanitize as a module (they're in the same staging dir)
def sanitize(text: str) -> str:
    """Thin wrapper around riddler_sanitize.sanitize()."""
    try:
        from .riddler_sanitize import sanitize as _sanitize
        return _sanitize(text)
    except Exception:
        # Fallback if import fails: basic path stripping
        import re
        text = re.sub(r"/[^\s]+", "[PATH]", text)
        text = re.sub(r"C:\\\\[^\s]+", "[WIN_PATH]", text)
        return text


def _ts_epoch(value: object) -> float:
    """Parse bridge timestamps as UTC, never host-local time."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(calendar.timegm(time.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")))
    except (TypeError, ValueError, OverflowError):
        return 0.0


def ensure_dirs():
    """Create bridge filesystem layout."""
    OUTBOXES.mkdir(parents=True, exist_ok=True)
    INBOX.parent.mkdir(parents=True, exist_ok=True)


def discover_sessions() -> list[str]:
    """List all sessions that have outboxes."""
    ensure_dirs()
    sessions = []
    if OUTBOXES.exists():
        for d in OUTBOXES.iterdir():
            if d.is_dir():
                sessions.append(d.name)
    return sessions


def read_outbox(session_id: str, since: float = 0, after_seq: int = 0) -> list[dict]:
    """Read new messages using sequence cursors, with timestamp fallback."""
    outbox = OUTBOXES / session_id
    if not outbox.exists():
        return []
    messages = []
    for p in sorted(outbox.glob("msg_*.json")):
        try:
            msg = json.loads(p.read_text(encoding="utf-8"))
            seq = int(msg.get("seq", 0) or 0)
            if after_seq and seq <= after_seq:
                continue
            msg_ts = _ts_epoch(msg.get("ts", 0))
            if (after_seq and seq > after_seq) or (not after_seq and msg_ts > since):
                messages.append(msg)
        except Exception:
            pass
    return messages


def write_to_inbox(sanitized_messages: list[dict]):
    """Append sanitized messages to shared inbox."""
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    with INBOX.open("a", encoding="utf-8") as f:
        for msg in sanitized_messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def update_window(sanitized_messages: list[dict]):
    """Update human-readable window with latest messages."""
    if not sanitized_messages:
        return
    lines = []
    if WINDOW.exists():
        lines = WINDOW.read_text(encoding="utf-8").splitlines()
    # Keep last 100 lines
    lines = lines[-100:]

    for msg in sanitized_messages:
        ts = msg.get("ts", _now())
        from_label = msg.get("from_label", "[AGENT]")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c.get("text", "")) for c in content)
        line = f"[{ts}] {from_label}: {content[:200]}"
        lines.append(line)

    WINDOW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _receipt(result: dict) -> dict:
    """Persist a bounded relay receipt without copying message contents."""
    RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": "session_bridge.receipt.v1",
        "ts": result.get("ts", _now()),
        "ok": bool(result.get("ok")),
        "sessions_found": int(result.get("sessions_found", 0) or 0),
        "messages": int(result.get("messages", 0) or 0),
        "state_path": str(RELAY_STATE.relative_to(ROOT)).replace("\\", "/"),
        "caller": "mag.session_bridge.relay",
    }
    with RECEIPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return result


def post(session_id: str, content: str, authority: str = "agent-generated") -> dict:
    """Post a message from a session to the bridge outbox.
    This is what sessions call to talk to the swarm."""
    ensure_dirs()
    outbox = OUTBOXES / _slug(session_id)
    outbox.mkdir(parents=True, exist_ok=True)

    # Find next sequence number
    existing = sorted(outbox.glob("msg_*.json"))
    seq = 0
    if existing:
        try:
            seq = int(existing[-1].stem.split("_")[1])
        except Exception:
            seq = len(existing)
    seq += 1

    msg = {
        "schema": "session_bridge.v1",
        "seq": seq,
        "ts": _now(),
        "session_id": session_id,  # Internal, will be stripped by sanitizer
        "from_label": f"[AGENT_{session_id[:8]}]",  # Anonymized
        "content": content,
        "authority": authority,
        "kind": "chat",  # chat | proposal | finding | question
    }

    path = outbox / f"msg_{seq:04d}.json"
    path.write_text(json.dumps(msg, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(path), "seq": seq}


def relay() -> dict:
    """Poll all outboxes, sanitize new messages, publish to inbox.
    This is what the bridge runner calls periodically."""
    ensure_dirs()
    sessions = discover_sessions()
    if not sessions:
        return _receipt({"ok": True, "sessions_found": 0, "messages": 0, "ts": _now()})

    # Track per-outbox sequence numbers. A timestamp-only cursor loses
    # same-second messages and can replay out-of-order writes.
    relay_state: dict[str, int] = {}
    try:
        raw_state = json.loads(RELAY_STATE.read_text(encoding="utf-8"))
        if isinstance(raw_state, dict):
            relay_state = {str(k): int(v) for k, v in raw_state.items()}
    except (OSError, ValueError, TypeError):
        relay_state = {}

    # Track last relay time only for first-run compatibility with an older
    # bridge that did not persist sequence cursors.
    last_relay = 0
    if not relay_state and INBOX.exists():
        try:
            for line in INBOX.read_text(encoding="utf-8").splitlines():
                try:
                    msg = json.loads(line)
                    ts = _ts_epoch(msg.get("ts", 0))
                    last_relay = max(last_relay, ts)
                except Exception:
                    pass
        except Exception:
            pass

    all_new = []
    for session_id in sessions:
        messages = read_outbox(session_id, since=last_relay,
                               after_seq=relay_state.get(session_id, 0))
        for msg in messages:
            # Sanitize via riddler
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(c.get("text", "")) for c in content)
            sanitized_content = sanitize(content)

            sanitized = {
                "schema": "session_bridge.v1",
                "ts": msg.get("ts", _now()),
                "seq": int(msg.get("seq", 0) or 0),
                "from_label": msg.get("from_label", "[AGENT]"),
                "content": sanitized_content,
                "authority": msg.get("authority", "agent-generated"),
                "kind": msg.get("kind", "chat"),
                "relay_ts": _now(),
            }
            all_new.append(sanitized)
            relay_state[session_id] = max(relay_state.get(session_id, 0), sanitized["seq"])

    if all_new:
        write_to_inbox(all_new)
        update_window(all_new)
    RELAY_STATE.parent.mkdir(parents=True, exist_ok=True)
    RELAY_STATE.write_text(json.dumps(relay_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return _receipt({
        "ok": True,
        "sessions_found": len(sessions),
        "messages": len(all_new),
        "ts": _now(),
    })


def read_inbox(limit: int = 50) -> list[dict]:
    """Read recent messages from the shared inbox.
    This is what sessions call to hear the swarm."""
    if not INBOX.exists():
        return []
    lines = []
    try:
        with INBOX.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    messages = []
    for line in lines[-limit:]:
        try:
            messages.append(json.loads(line))
        except Exception:
            pass
    return messages


def window_html() -> str:
    """Generate a simple HTML window view."""
    messages = read_inbox(limit=100)
    lines = []
    for msg in messages:
        ts = msg.get("ts", "")
        from_label = msg.get("from_label", "[AGENT]").replace("<", "&lt;")
        content = str(msg.get("content", "")).replace("<", "&lt;").replace(">", "&gt;")
        kind = msg.get("kind", "chat")
        color = {
            "chat": "#e0e0e0",
            "proposal": "#ffcc00",
            "finding": "#66ff66",
            "question": "#66ccff",
        }.get(kind, "#e0e0e0")
        lines.append(f'<div style="margin:8px 0; padding:8px; border-left:4px solid {color}; background:#1a1a1a; color:#d0d0d0;">')
        lines.append(f'<div style="font-size:0.8em; color:#888;">{ts} · {from_label} · {kind}</div>')
        lines.append(f'<div>{content}</div>')
        lines.append('</div>')

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Session Bridge Window</title>
<style>body{{background:#0d0d0d;font-family:monospace;margin:0;padding:16px;}}
</style></head><body>
<h2 style="color:#fff;margin-top:0;">Swarm Bridge — Sanitized Cross-Session Window</h2>
<div style="color:#666;font-size:0.9em;margin-bottom:16px;">
Internals stripped. Research physics preserved. {len(messages)} messages in flight.
</div>
{chr(10).join(lines)}
</body></html>"""
    return html


def cmd_post(args):
    result = post(args.session, args.content, args.authority)
    print(json.dumps(result, indent=2))
    return 0


def cmd_relay(_args):
    result = relay()
    print(json.dumps(result, indent=2))
    return 0


def cmd_read(args):
    messages = read_inbox(args.limit)
    print(json.dumps({"count": len(messages), "messages": messages}, indent=2))
    return 0


def cmd_window(_args):
    html = window_html()
    path = BRIDGE / "window.html"
    path.write_text(html, encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(path), "messages": len(read_inbox(100))}))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.session_bridge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("post", help="session writes message to outbox")
    p.add_argument("session", help="session identifier")
    p.add_argument("content", help="message content")
    p.add_argument("--authority", default="agent-generated")
    p.set_defaults(func=cmd_post)

    r = sub.add_parser("relay", help="bridge polls outboxes, sanitizes, publishes")
    r.set_defaults(func=cmd_relay)

    rd = sub.add_parser("read", help="read recent inbox messages")
    rd.add_argument("--limit", type=int, default=50)
    rd.set_defaults(func=cmd_read)

    w = sub.add_parser("window", help="regenerate HTML window")
    w.set_defaults(func=cmd_window)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
