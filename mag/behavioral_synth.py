"""Synthesize behavioral leaves from events + decisions + sessions.

Writes memory/improve/daily/{YYYY-MM-DD}-behavioral.md so scout/governance
can surface recurring seat-error themes (the decision-tree layer).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

EVENTS_PATH = ROOT / "logs" / "behavioral_events.jsonl"
DECISIONS_PATH = ROOT / "memory" / "decisions_log.jsonl"
DAILY_DIR = ROOT / "memory" / "improve" / "daily"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-tail:]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except json.JSONDecodeError:
            continue
    return out


def synthesize_behavioral_leaf(day: str | None = None) -> dict[str, Any]:
    """Build or update today's behavioral leaf from disk artifacts."""
    day = day or _today()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DAILY_DIR / f"{day}-behavioral.md"

    events = _read_jsonl(EVENTS_PATH)
    decisions = _read_jsonl(DECISIONS_PATH)
    kind_counts = Counter(str(e.get("kind") or "event") for e in events)
    tool_counts = Counter(str(e.get("tool") or "") for e in events if e.get("tool"))

    themes: list[tuple[str, str, str]] = []

    if kind_counts.get("collapse", 0):
        top_tool = tool_counts.most_common(1)
        tool_s = top_tool[0][0] if top_tool else "unknown"
        themes.append((
            "T1",
            "Tool collapse loops",
            f"{kind_counts['collapse']} collapse events; top tool: {tool_s}. "
            "Escalate to smarter seat instead of 5x identical calls.",
        ))

    if kind_counts.get("degenerate", 0):
        themes.append((
            "T2",
            "Degenerate model output",
            f"{kind_counts['degenerate']} degenerate responses. "
            "disable_thinking on DeepSeek; escalate after 2 retries.",
        ))

    if kind_counts.get("operator_behavior", 0):
        themes.append((
            "T0b",
            "Operator thrash / phase catch",
            f"{kind_counts['operator_behavior']} operator_behavior events. "
            "Architecture notes under memory/improve/behavior/ — return to Play Ladder R0; "
            "do not open a new front to fix thrash.",
        ))

    if kind_counts.get("tool_fail", 0):
        themes.append((
            "T3",
            "Tool failures",
            f"{kind_counts['tool_fail']} tool_fail events. Read error, change approach.",
        ))

    # Operator complaints in case law
    complaints = 0
    for d in decisions:
        blob = f"{d.get('context', '')} {d.get('steer_input', '')} {d.get('outcome', '')}".lower()
        if any(k in blob for k in ("loop", "collapse", "degenerate", "empty", "doesn't work", "chugging")):
            complaints += 1
    if complaints:
        themes.append((
            "T4",
            "Operator-reported seat friction",
            f"{complaints} case-law entries mention loops/failures. Prefer escalation over retry.",
        ))

    try:
        from mag.decision_framework import session_loop_patterns

        hot = session_loop_patterns(limit=15)
        if hot and hot[0].get("count", 0) >= 5:
            themes.append((
                "T5",
                "Hot tools across sessions",
                f"Frequent: {hot[0].get('tool')} ({hot[0].get('count')} calls). "
                "Consider different tool or smarter seat.",
            ))
    except Exception:
        pass

    if not themes:
        themes.append((
            "T0",
            "No high-signal errors today",
            "Keep behavioral_events logging enabled; loops will surface here.",
        ))

    lines = [
        f"# Behavioral leaf — {day}",
        "",
        "_Synthesized from behavioral_events, decisions_log, agent_sessions._",
        "",
        "## Summary",
        f"- events: {sum(kind_counts.values())} · kinds: {dict(kind_counts)}",
        "",
    ]
    for tid, title, avoid in themes:
        lines.append(f"## {tid} — {title}")
        lines.append(f"- root: mined from disk")
        lines.append(f"- avoid: {avoid}")
        lines.append("")

    body = "\n".join(lines)
    out_path.write_text(body, encoding="utf-8")
    try:
        rel = str(out_path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(out_path)
    return {
        "ok": True,
        "path": rel,
        "themes_n": len(themes),
        "event_kinds": dict(kind_counts),
    }
