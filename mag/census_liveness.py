"""census_liveness -- darkness tripwire for MagCensusPatrolDaily (B2-314).

The patrol (scripts/census_patrol_daily.ps1, daily 08:30, Logon Mode
Interactive only) runs the deep census check but its own darkness is silent:
machine-off, logout, or task deregistration reopens the B2-246 falsifier (a
week where no scheduled surface runs the deep check) with zero signal. The
ps1's own operator paragraph names the condition ("No START stamp for today
in this log: the surface is dark") but nothing ATTENDED read it. This module
is that reader: the last bracketed START stamp in logs/census_patrol.log
older than 26 hours (daily cadence + slack) is reported as darkness on an
attended surface (mag.cmd context-pack), never inferred from mtimes
(mtime is not tamper evidence, B2-237) and never self-repairing.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "census_patrol.log"
MAX_AGE_HOURS = 26.0  # daily 08:30 cadence + 2.5h slack before naming darkness

_START_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] START")


def patrol_status(log_path: Path | None = None, now: datetime | None = None,
                  max_age_hours: float = MAX_AGE_HOURS) -> dict:
    """Read the last bracketed START stamp and judge liveness. Returns
    {dark, last_start, age_hours, line}. Never raises on log problems: an
    unreadable or stamp-less log is darkness with a named reason (falsify by
    bytes, not by crash)."""
    log_path = Path(log_path) if log_path else LOG
    now = now or datetime.now()
    last_start: str | None = None
    if log_path.is_file():
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for ln in text.splitlines():
            m = _START_RE.match(ln.strip())
            if m:
                last_start = m.group(1)
    if last_start is None:
        return {"dark": True, "last_start": None, "age_hours": None,
                "line": ("census patrol dark: no START stamp found in "
                         f"{log_path.name} (never ran, log deleted, or "
                         "task deregistered)")}
    try:
        stamp = datetime.strptime(last_start, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return {"dark": True, "last_start": last_start, "age_hours": None,
                "line": f"census patrol dark: unparseable START stamp {last_start!r}"}
    age_hours = (now - stamp).total_seconds() / 3600.0
    if age_hours > max_age_hours:
        return {"dark": True, "last_start": last_start,
                "age_hours": round(age_hours, 2),
                "line": (f"census patrol dark since {last_start} "
                         f"({age_hours:.1f}h > {max_age_hours:g}h; check "
                         "schtasks /Query /TN MagCensusPatrolDaily)")}
    return {"dark": False, "last_start": last_start,
            "age_hours": round(age_hours, 2),
            "line": (f"census patrol live: last START {last_start} "
                     f"({age_hours:.1f}h ago)")}


def report(out=print, log_path: Path | None = None,
           now: datetime | None = None) -> str:
    """The attended-surface hook: print and return the one-line status."""
    line = patrol_status(log_path=log_path, now=now)["line"]
    out(line)
    return line
