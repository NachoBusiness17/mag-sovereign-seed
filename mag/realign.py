"""Operator realignment surface: what needs you, what moved, what was ignored.

Return 13 of the Mickey17 wave (2026-09-29) found 186 verbs behind a
6-command door and the operator's own kill switch off the card.  This module
is the plain-language door: it reads a last-visit stamp, diffs the estate
state files and the inbox event log SINCE that stamp, and renders three
sections in operator language with receipts linked by filename.

Convention (created here): the stamp lives at state/last_operator_visit.json
and is updated AFTER a render, only when the operator says --mark-visited.
A plain `python main.py realign` never moves the stamp, so two looks at the
same window show the same diff.

Schema: last_operator_visit.v1
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "last_operator_visit.v1"

MOVED_CAP = 20
NEEDS_CAP = 10
OLD_DAYS = 7

_TS_LINE = re.compile(r"^- ts:\s*(\S+)", re.MULTILINE)
_HEADER_DATE = re.compile(r"^###.*\((\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})?\)?\s*$", re.MULTILINE)
_TAG_LINE = re.compile(r"^- ((?:\[[^\]]+\])+\s*)(.*)$")
_VERDICT_LINE = re.compile(r"^- verdict:\s*(.*)$")
_CURRENT_FIELD = re.compile(r"^- \*\*(status|updated):\*\*\s*(.+)$", re.MULTILINE)


@dataclass
class Paths:
    root: Path

    @property
    def stamp(self) -> Path:
        return self.root / "state" / "last_operator_visit.json"

    @property
    def current(self) -> Path:
        return self.root / "state" / "CURRENT.md"

    @property
    def operator_state(self) -> Path:
        return self.root / "state" / "operator_mode.json"

    @property
    def attention(self) -> Path:
        return self.root / "memory" / "attention.md"

    @property
    def events(self) -> Path:
        return self.root / "watch" / "inbox" / "index_events.jsonl"

    @property
    def queue_index(self) -> Path:
        return self.root / "queue" / "queue_index.jsonl"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------- stamp


def read_stamp(root: Path = ROOT) -> dict[str, Any]:
    """Return {'last_visit': datetime|None, 'raw': dict|None}. Missing file = cold start."""
    raw: dict[str, Any] | None = None
    try:
        raw = json.loads(Paths(root).stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None
    last = _parse_ts((raw or {}).get("last_visit")) if raw else None
    return {"last_visit": last, "raw": raw}


def mark_visited(root: Path = ROOT, now: datetime | None = None, counts: dict[str, int] | None = None) -> dict[str, Any]:
    """Write the visit stamp atomically. Called AFTER a render, never before."""
    paths = Paths(root)
    previous = read_stamp(root)["last_visit"]
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "last_visit": _iso(now or _now()),
        "previous_visit": _iso(previous) if previous else None,
        "rendered": counts or {},
    }
    paths.stamp.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="last_operator_visit_", suffix=".tmp", dir=str(paths.stamp.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
        os.replace(tmp_name, paths.stamp)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return record


# ---------------------------------------------------------------- parsers


def parse_current(root: Path = ROOT) -> dict[str, Any]:
    text = _read_text(Paths(root).current)
    fields = dict(_CURRENT_FIELD.findall(text))
    goal = ""
    match = re.search(r"^## Goal\s*$\n+(.*)$", text, re.MULTILINE)
    if match:
        goal = match.group(1).strip()
    return {
        "updated": _parse_ts(fields.get("updated")),
        "status": fields.get("status", "").strip(),
        "goal": goal,
    }


def parse_attention(root: Path = ROOT) -> list[dict[str, Any]]:
    """Extract alert lines from memory/attention.md with their block timestamps.

    The file mixes quiet session notices with real alerts; only bracket-tagged
    lines ([priority], [probe-alarm], ...) and patrol verdict lines count as
    alerts.  Repeats of the same text (the probe flood) collapse into one
    entry with a count.
    """
    text = _read_text(Paths(root).attention)
    alerts: list[dict[str, Any]] = []
    for block in re.split(r"(?m)^---\s*$", text):
        ts = None
        ts_match = _TS_LINE.search(block)
        if ts_match:
            ts = _parse_ts(ts_match.group(1))
        else:
            header = _HEADER_DATE.search(block)
            if header:
                stamp = header.group(1) + ("T" + (header.group(2) or "00:00:00"))
                ts = _parse_ts(stamp)
        for line in block.splitlines():
            tagged = _TAG_LINE.match(line.strip())
            if tagged:
                body = tagged.group(2).strip()
                # Drop the trailing pointer (path) so flood copies dedup.
                body = body.split(" -> ")[0].strip()
                if body:
                    alerts.append({"ts": ts, "text": body})
                continue
            verdict = _VERDICT_LINE.match(line.strip())
            if verdict and ts:
                alerts.append({"ts": ts, "text": verdict.group(1).strip()})
    merged: dict[str, dict[str, Any]] = {}
    for alert in alerts:
        key = re.sub(r"\s+", " ", alert["text"]).strip().lower()
        slot = merged.get(key)
        if slot is None:
            merged[key] = {**alert, "count": 1}
        else:
            slot["count"] += 1
            if (alert["ts"] or _now()) > (slot["ts"] or _now()):
                slot["ts"] = alert["ts"]
    return sorted(merged.values(), key=lambda a: a["ts"] or _now(), reverse=True)


def parse_queue_needs(root: Path = ROOT) -> list[dict[str, Any]]:
    """Queue rows parked because only the operator may decide them."""
    rows: list[dict[str, Any]] = []
    for line in _read_text(Paths(root).queue_index).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if str(row.get("status", "")).lower() == "closed":
            continue
        verdict = str(row.get("roam_verdict") or "")
        status = str(row.get("status") or "")
        if "needs-operator" not in verdict and "needs-operator" not in status:
            continue
        why = verdict.split("needs-operator:", 1)[-1] if "needs-operator:" in verdict else verdict
        why = re.split(r"[;.]", why)[0].strip()
        rows.append(
            {
                "id": row.get("id", "?"),
                "title": str(row.get("title", "")).strip(),
                "ts": _parse_ts(row.get("ts")),
                "why": why,
            }
        )
    return sorted(rows, key=lambda r: r["ts"] or _now())


def parse_events(root: Path = ROOT) -> list[dict[str, Any]]:
    """Inbox registration events (the append-only log is the source of truth)."""
    events: list[dict[str, Any]] = []
    for line in _read_text(Paths(root).events).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if str(event.get("op", "")).lower() != "register":
            continue
        events.append(
            {
                "ts": _parse_ts(event.get("ts")),
                "file": str(event.get("file", "")),
                "purpose": str(event.get("purpose", "")),
            }
        )
    return events


def read_operator_mode(root: Path = ROOT) -> dict[str, Any]:
    """Minimal read of the operator switch (same file mag.operator_mode owns)."""
    try:
        data = json.loads(Paths(root).operator_state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"mode": "running", "reason": "", "changed_at": None}
    return {
        "mode": str(data.get("mode", "running")),
        "reason": str(data.get("reason", "")),
        "changed_at": _parse_ts(data.get("changed_at")),
    }


# ---------------------------------------------------------------- collect + render


def collect(root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    since = read_stamp(root)["last_visit"]
    old_cutoff = now - timedelta(days=OLD_DAYS)

    alerts = [a for a in parse_attention(root) if since is None or not a["ts"] or a["ts"] > since]
    needs_rows = parse_queue_needs(root)
    mode = read_operator_mode(root)

    registrations = parse_events(root)
    if since is None:
        # Cold start: there is no last visit, so "moved" means the recent
        # window (last OLD_DAYS days); anything older folds into IGNORED.
        moved_events = [e for e in registrations if not e["ts"] or e["ts"] >= old_cutoff]
    else:
        moved_events = [e for e in registrations if e["ts"] and e["ts"] > since]
    moved_events.sort(key=lambda e: e["ts"] or now, reverse=True)

    current = parse_current(root)
    current_moved = bool(since is None or (current["updated"] and current["updated"] > since))

    ignored = sum(1 for e in registrations if e["ts"] and e["ts"] < old_cutoff)
    ignored += sum(1 for a in parse_attention(root) if a["ts"] and a["ts"] < old_cutoff)

    return {
        "now": now,
        "since": since,
        "cold_start": since is None,
        "operator_mode": mode,
        "alerts": alerts,
        "queue_needs": needs_rows,
        "moved_events": moved_events,
        "current": current,
        "current_moved": current_moved,
        "ignored_count": ignored,
    }


def _fmt_day(ts: datetime | None) -> str:
    return ts.strftime("%m-%d %H:%M") if ts else "unknown time"


def render(state: dict[str, Any]) -> str:
    since = state["since"]
    mode = state["operator_mode"]
    lines: list[str] = []

    if state["cold_start"]:
        lines.append("REALIGN - first visit, so everything counts as new")
    else:
        lines.append(f"REALIGN - what changed since your last visit ({_fmt_day(since)} UTC)")
    lines.append(f"looked at: {_fmt_day(state['now'])} UTC · operator switch: {mode['mode']}")
    lines.append("")

    needs: list[str] = []
    if mode["mode"] == "paused":
        reason = mode["reason"] or "no reason given"
        needs.append(f"YOU PAUSED the autonomous work ({reason}); say `python main.py operator-mode resume` to let it run again")
    for alert in state["alerts"][:NEEDS_CAP]:
        count = f" (seen {alert['count']} times)" if alert["count"] > 1 else ""
        needs.append(f"attention {_fmt_day(alert['ts'])}: {alert['text']}{count}")
    for row in state["queue_needs"]:
        why = f" - {row['why']}" if row["why"] else ""
        needs.append(f"queue {row['id']} waiting since {_fmt_day(row['ts'])}: {row['title']}{why}")
    extra = len(state["alerts"]) - NEEDS_CAP
    if extra > 0:
        needs.append(f"...plus {extra} more attention alerts not shown")

    lines.append("NEEDS YOU")
    if needs:
        lines.extend(f"- {item}" for item in needs)
    else:
        lines.append("- (nothing needs you right now)")

    lines.append("")
    lines.append("MOVED")
    moved: list[str] = []
    if state["current_moved"]:
        current = state["current"]
        bits = [b for b in (current["status"], current["goal"]) if b]
        moved.append(f"state/CURRENT.md - current work: {' · '.join(bits) if bits else 'changed'}")
    for event in state["moved_events"][:MOVED_CAP]:
        purpose = f" - {event['purpose']}" if event["purpose"] else ""
        moved.append(f"{_fmt_day(event['ts'])} · watch/inbox/{event['file']}{purpose}")
    hidden = len(state["moved_events"]) - MOVED_CAP
    if hidden > 0:
        moved.append(f"...plus {hidden} more registrations not shown")
    if moved:
        lines.extend(f"- {item}" for item in moved)
    else:
        lines.append("- (nothing moved)")

    lines.append("")
    lines.append("IGNORED")
    ignored = state["ignored_count"]
    if ignored:
        lines.append(f"- {ignored} items older than {OLD_DAYS} days, counted but not shown")
    else:
        lines.append("- (nothing old enough to ignore)")

    if not needs and not moved:
        lines.append("")
        lines.append("Bottom line: nothing moved and nothing needs you.")

    lines.append("")
    lines.append("mark this visit (so next time shows only the new stuff): python main.py realign --mark-visited")
    return "\n".join(lines)


def main(mark_visited: bool = False, root: Path = ROOT, out: Callable[[str], None] = print) -> int:
    state = collect(root=root)
    out(render(state))
    if mark_visited:
        record = mark_visited(
            root=root,
            counts={
                "needs": len(state["alerts"]) + len(state["queue_needs"]),
                "moved": len(state["moved_events"]),
                "ignored": state["ignored_count"],
            },
        )
        out("")
        out(f"visit stamped: {record['last_visit']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
