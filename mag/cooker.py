"""cooker — fire the free-compute burn right after each provider's reset, by default
(2026-09-24, operator: "we know how long we have until resets, we have their apis ...
lets make this cook by default").

Law: a pool that refills while we sleep is a pool we paid attention to and wasted.
The cooker knows each reset window, fires the mapped burn once per window, and logs
every fire. It NEVER auto-rearms credentials (operator-hand law) and NEVER spends
outside the free/metered lanes the estate already wired.

CLI:
  python mag/cooker.py status        # next resets, countdowns, last fires
  python mag/cooker.py fire --due    # fire every reset whose window hasn't been fired
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "fuel" / "cooker_ledger.jsonl"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _py() -> str:
    return sys.executable


# Reset windows of record. window_start(now) returns the UTC instant the current
# window opened; a burn fires once per window (deduped via the ledger).
RESETS: list[dict] = [
    {"name": "openrouter_free_daily", "kind": "daily_utc", "hour": 0,
     "cmd": [_py(), "tools/stealth_sweep.py"],
     "why": "free/:stealth wall refreshes — score it before anyone else does"},
    {"name": "free_daily_burst", "kind": "daily_utc", "hour": 0,
     "cmd": [_py(), "tools/task_wall.py", "--budget-minutes", "15"],
     "why": "groq/openrouter daily quotas refill — 15-min real-chore burst"},
    {"name": "lite_weekly", "kind": "weekly_utc", "weekday": 5, "hour": 2, "minute": 19,
     "cmd": ["METER_ONLY"],  # rearm is operator-hand; cooker reads the meter and reports
     "why": "z_ai Lite weekly pool ~02:19Z — read meter, report, never auto-rearm"},
]


def window_start(r: dict, now: datetime) -> datetime:
    """UTC instant the current window for this reset opened."""
    if r["kind"] == "daily_utc":
        start = now.replace(hour=r["hour"], minute=0, second=0, microsecond=0)
        return start if now >= start else start.replace(day=start.day - 1)
    if r["kind"] == "weekly_utc":
        # weekday: 0=Mon ... 5=Sat, 6=Sun (Python convention)
        start = now.replace(hour=r["hour"], minute=r.get("minute", 0), second=0, microsecond=0)
        days_back = (now.weekday() - r["weekday"]) % 7
        if days_back == 0 and now < start:
            days_back = 7
        return start.replace(day=start.day) if days_back == 0 else _minus_days(start, days_back)
    raise ValueError(r["kind"])


def _minus_days(dt: datetime, n: int) -> datetime:
    import datetime as _dt
    return dt - _dt.timedelta(days=n)


def next_reset(r: dict, now: datetime) -> datetime:
    if r["kind"] == "daily_utc":
        cand = now.replace(hour=r["hour"], minute=0, second=0, microsecond=0)
        return cand if now < cand else _minus_days(cand, -1)
    if r["kind"] == "weekly_utc":
        start = now.replace(hour=r["hour"], minute=r.get("minute", 0), second=0, microsecond=0)
        days_ahead = (r["weekday"] - now.weekday()) % 7
        if days_ahead == 0 and now >= start:
            days_ahead = 7
        return start if days_ahead == 0 else _minus_days(start, -days_ahead)
    raise ValueError(r["kind"])


def _fired_windows() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
                out.add((row.get("name", ""), row.get("window_start", "")))
            except Exception:
                pass
    return out


def _log(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def status() -> str:
    now = datetime.now(timezone.utc)
    fired = _fired_windows()
    lines = [f"COOKER STATUS — {now.isoformat(timespec='seconds')} (UTC)", ""]
    for r in RESETS:
        nxt = next_reset(r, now)
        ws = window_start(r, now)
        due = (r["name"], ws.isoformat(timespec="seconds")) not in fired
        delta = nxt - now
        hrs, rem = divmod(int(delta.total_seconds()), 3600)
        lines.append(f"{r['name']}: next reset {nxt.isoformat(timespec='seconds')} "
                     f"(in {hrs}h{rem//60:02d}m) — {'DUE NOW' if due else 'fired this window'}")
        lines.append(f"  burn: {' '.join(map(str, r['cmd']))[:90]} — {r['why']}")
    return "\n".join(lines)


def fire_due() -> int:
    now = datetime.now(timezone.utc)
    fired = _fired_windows()
    exits = 0
    for r in RESETS:
        ws = window_start(r, now)
        key = (r["name"], ws.isoformat(timespec="seconds"))
        if key in fired:
            continue
        cmd = r["cmd"]
        if cmd == ["METER_ONLY"]:
            try:
                sys.path.insert(0, str(ROOT))
                from mag.lite_guard import provider_quota
                q = provider_quota(force=True)
                _log({"name": r["name"], "window_start": key[1], "kind": "meter_read",
                      "quota": q})
                print(f"{r['name']}: meter read logged: {json.dumps(q)[:120]}")
            except Exception as e:  # noqa: BLE001
                _log({"name": r["name"], "window_start": key[1], "kind": "meter_read",
                      "error": str(e)[:200]})
                print(f"{r['name']}: meter read FAILED: {e}")
            continue
        print(f"{r['name']}: firing — {' '.join(map(str, cmd))[:100]}")
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                  timeout=1500, encoding="utf-8", errors="replace")
            tail = (proc.stdout or "")[-400:].replace("\n", " | ")
            _log({"name": r["name"], "window_start": key[1], "kind": "burn",
                  "exit": proc.returncode, "stdout_tail": tail,
                  "stderr_tail": (proc.stderr or "")[-200:]})
            exits |= 0 if proc.returncode == 0 else 1
            print(f"{r['name']}: exit {proc.returncode} — {tail[:160]}")
        except Exception as e:  # noqa: BLE001
            _log({"name": r["name"], "window_start": key[1], "kind": "burn",
                  "error": f"{type(e).__name__}: {str(e)[:200]}"})
            exits |= 1
            print(f"{r['name']}: FIRE FAILED: {e}")
    return exits


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--due" in args:
        sys.exit(fire_due())
    print(status())
