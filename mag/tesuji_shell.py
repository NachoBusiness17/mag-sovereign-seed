"""Capture emergent wins — brilliant moves / unexpected tesuji shells.

Symmetric to behavioral errors (operator_inbox.log_behavioral_event →
behavioral_synth → improve scout). Logs append to logs/tesuji_shells.jsonl;
daily leaf at memory/improve/daily/{date}-tesuji-shells.md.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "tesuji_shell.v1"
SHELLS_PATH = ROOT / "logs" / "tesuji_shells.jsonl"
DAILY_DIR = ROOT / "memory" / "improve" / "daily"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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


def read_shells(*, limit: int = 200) -> list[dict[str, Any]]:
    return _read_jsonl(SHELLS_PATH, tail=limit)


def log_tesuji_shell(
    what: str,
    *,
    surprise: str = "",
    maps_to: str | None = None,
    source: str = "operator",
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Record one emergent win — what happened and why it surprised."""
    what = (what or "").strip()
    if not what:
        return {"ok": False, "error": "empty what"}
    row = {
        "schema": SCHEMA,
        "ts": _now(),
        "what": what[:800],
        "surprise": (surprise or "")[:500],
        "maps_to": (maps_to or "").strip()[:200] or None,
        "source": source[:40],
        "session_id": session_id,
        "tags": [str(t)[:40] for t in (tags or [])[:8]],
    }
    try:
        SHELLS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SHELLS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        return {"ok": False, "error": str(exc)[:200]}

    try:
        from mag.compass import record_decision

        record_decision(
            "tesuji shell",
            what[:200],
            f"surprise: {(surprise or '')[:120]} · maps_to={maps_to or 'none'}",
        )
    except Exception:
        pass

    try:
        from mag.training_events import emit

        emit(
            "tesuji_shell",
            input_data={"what": what[:400], "surprise": (surprise or "")[:200]},
            action={"maps_to": maps_to, "source": source, "tags": tags or []},
            outcome={"logged": True},
            pattern_tags=["emergent_win"],
            tier_max="T2",
        )
    except Exception:
        pass

    return {"ok": True, "shell": row, "path": _display_path(SHELLS_PATH)}


def status() -> dict[str, Any]:
    shells = read_shells(limit=500)
    map_counts = Counter(
        str(s.get("maps_to") or "unmapped") for s in shells if s.get("what")
    )
    daily = sorted(DAILY_DIR.glob("*-tesuji-shells.md"), reverse=True)
    latest_leaf = _display_path(daily[0]) if daily else None
    return {
        "ok": True,
        "schema": SCHEMA,
        "shells_n": len(shells),
        "recent": [
            {
                "ts": s.get("ts"),
                "what": str(s.get("what") or "")[:120],
                "maps_to": s.get("maps_to"),
            }
            for s in shells[-5:]
        ],
        "maps_to_counts": dict(map_counts.most_common(8)),
        "log_path": _display_path(SHELLS_PATH),
        "latest_leaf": latest_leaf,
        "layman": (
            f"{len(shells)} tesuji shell(s) on disk — emergent wins to repeat, "
            "not errors to avoid."
        ),
    }


def _shell_title(what: str) -> str:
    line = what.strip().splitlines()[0] if what else "Emergent win"
    return line[:72] + ("…" if len(line) > 72 else "")


def synthesize_tesuji_shell_leaf(day: str | None = None) -> dict[str, Any]:
    """Build or update today's tesuji-shell leaf from logs/tesuji_shells.jsonl."""
    day = day or _today()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DAILY_DIR / f"{day}-tesuji-shells.md"

    shells = read_shells(limit=300)
    # Prefer shells from today (UTC), fall back to recent tail
    day_shells = [s for s in shells if str(s.get("ts") or "").startswith(day)]
    active = day_shells if day_shells else shells[-12:]

    wins: list[tuple[str, str, str, str]] = []
    map_counter = Counter(
        str(s.get("maps_to") or "") for s in active if s.get("maps_to")
    )

    for i, s in enumerate(active[-8:], start=1):
        wid = f"W{i}"
        title = _shell_title(str(s.get("what") or ""))
        surprise = str(s.get("surprise") or "unexpected structural win")
        maps = str(s.get("maps_to") or "unmapped")
        wins.append((wid, title, surprise, maps))

    lines = [
        f"# Tesuji shells — {day}",
        "",
        "_Synthesized from logs/tesuji_shells.jsonl — emergent wins to repeat._",
        "",
        "## Summary",
        f"- shells: {len(active)} (day={len(day_shells)}, recent tail={len(shells)})",
    ]
    if map_counter:
        top_maps = ", ".join(f"{k}×{v}" for k, v in map_counter.most_common(4))
        lines.append(f"- maps_to: {top_maps}")

    if not wins:
        lines.extend([
            "",
            "## W0 — No shells logged yet",
            "- surprise: n/a",
            "- repeat: log with `python main.py tesuji-shell log \"…\" --surprise \"…\"`",
            "",
            "## Patterns (weekly roll-up stub)",
            "- Cluster by maps_to prefix (remedy:, skill:, tesuji:) when ≥3 shells share a link.",
        ])
    else:
        for wid, title, surprise, maps in wins:
            lines.extend([
                "",
                f"## {wid} — {title}",
                f"- surprise: {surprise}",
                f"- maps_to: {maps}",
                "- repeat: file for scout; promote if pattern holds ≥3×",
            ])
        lines.extend([
            "",
            "## Patterns (weekly roll-up stub)",
        ])
        if map_counter:
            for link, cnt in map_counter.most_common(5):
                if cnt >= 2:
                    lines.append(f"- `{link}` appeared {cnt}× — candidate for remedy/skill weave")
        else:
            lines.append("- No maps_to clusters yet — tag shells when the link is obvious.")

    body = "\n".join(lines) + "\n"
    out_path.write_text(body, encoding="utf-8")
    return {
        "ok": True,
        "path": _display_path(out_path),
        "wins_n": len(wins),
        "shells_n": len(active),
        "map_clusters": dict(map_counter),
    }


def latest_leaf_excerpt(*, max_wins: int = 3) -> dict[str, Any]:
    """Parse latest tesuji-shell leaf for context-pack / governance."""
    if not DAILY_DIR.is_dir():
        return {}
    leaves = sorted(DAILY_DIR.glob("*-tesuji-shells.md"), reverse=True)
    if not leaves:
        return {}
    path = leaves[0]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    wins: list[dict[str, str]] = []
    for m in re.finditer(r"^#{2,3}\s+(W\d+)\s*[—\-–]\s*(.+)$", text, re.M):
        wid, title = m.group(1), m.group(2).strip()
        surprise, maps = "", ""
        block_m = re.search(
            rf"^#{2,3}\s+{re.escape(wid)}\s*[—\-–].*?(?=^#{2,3}\s+|\Z)",
            text,
            re.M | re.S,
        )
        if block_m:
            sm = re.search(r"surprise:\s*(.+)", block_m.group(0), re.M)
            mm = re.search(r"maps_to:\s*(.+)", block_m.group(0), re.M)
            if sm:
                surprise = sm.group(1).strip()[:200]
            if mm:
                maps = mm.group(1).strip()[:120]
        wins.append({"id": wid, "title": title, "surprise": surprise, "maps_to": maps})
    return {
        "path": _display_path(path),
        "wins": wins[:max_wins],
        "n_wins": len(wins),
    }
