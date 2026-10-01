"""vertical_meter — the Sep-20 wall meter for the trajectory spine (W4, $0 read-only).

Reads memory/runs/trajectory/steps.jsonl (the sealed TrajectoryStep tape, ALL producers:
bash-local, salon, every seat) and reports pace against the vertical: 100 sealed
steps/day by 2026-09-20 (card falsifier: <100/day on 09-19 = the wall is missed).

  python -m mag.vertical_meter          # human verdict
  python -m mag.vertical_meter --json   # machine verdict
  python -m mag.vertical_meter --tape PATH [--today YYYY-MM-DD]   # test/what-if

Meter itself never writes. Read-only on the tape.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
WALL = date(2026, 9, 20)
TARGET = 100.0  # sealed steps / day


def _rows(tape: Path) -> list[dict[str, Any]]:
    if not tape.is_file():
        return []
    out = []
    for ln in tape.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _day(ts: Any) -> date | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc).date()
    except (TypeError, ValueError):
        return None


def measure(tape: Path = TAPE, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    days = [d for d in (_day(r.get("ts")) for r in _rows(tape)) if d]
    rows_today = sum(1 for d in days if d == today)
    week = {today - timedelta(days=i) for i in range(7)}
    last7 = sum(1 for d in days if d in week)
    avg7 = round(last7 / 7.0, 1)
    days_left = (WALL - today).days  # 0 on wall day, negative after
    required_total = int(TARGET * days_left) if days_left > 0 else 0
    projected_total = int(avg7 * days_left) if days_left > 0 else 0
    gap = round(TARGET - avg7, 1)
    if days_left < 0:
        verdict = "WALL PASSED"
    elif avg7 >= TARGET:
        verdict = "ON PACE"
    else:
        verdict = "SHORTFALL " + str(gap)
    return {
        "tape": str(tape), "total_rows": len(days), "rows_today": rows_today,
        "rows_last_7d": last7, "avg_per_day_7d": avg7,
        "wall": WALL.isoformat(), "days_remaining": days_left,
        "target_per_day": TARGET,
        "required_rows_remaining": required_total,       # 100/day x days left
        "projected_rows_at_pace": projected_total,       # avg7 x days left
        "verdict": verdict,
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    argv = sys.argv[1:]
    tape, today = TAPE, None
    if "--tape" in argv:
        i = argv.index("--tape")
        tape = Path(argv[i + 1])
    if "--today" in argv:
        i = argv.index("--today")
        today = date.fromisoformat(argv[i + 1])
    m = measure(tape, today)
    if "--json" in argv:
        print(json.dumps(m, indent=1))
        return
    print("=== VERTICAL METER — %g sealed steps/day by %s ===" % (TARGET, m["wall"]))
    print("tape: %s (%d sealed rows total)" % (m["tape"], m["total_rows"]))
    print("rows today (%s): %d" % (today.isoformat() if today
                                   else datetime.now(timezone.utc).date().isoformat(),
                                   m["rows_today"]))
    print("last 7 days: %d rows (avg %g/day)" % (m["rows_last_7d"],
                                                 m["avg_per_day_7d"]))
    print("days to wall: %d" % m["days_remaining"])
    print("required: %g/day flat = %d rows over %d days"
          % (TARGET, m["required_rows_remaining"], max(m["days_remaining"], 0)))
    print("projection at current pace: %g/day = %d rows over %d days"
          % (m["avg_per_day_7d"], m["projected_rows_at_pace"], max(m["days_remaining"], 0)))
    print("VERDICT: " + m["verdict"])


if __name__ == "__main__":
    main()
