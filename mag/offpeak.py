"""offpeak — DeepSeek time-of-day pricing window (peak vs off-peak), deterministic + $0.

Operator (2026-08-24): DeepSeek peak hours (weekdays Beijing time 09:00-12:00 and
14:00-18:00) are DOUBLE the off-peak price; weekends are off-peak all day. So heavy
rounds should auto-schedule for off-peak hours — the price is literally half.

This module answers, from the wall clock only (no network, no state):
  is_peak(dt)        — is this instant priced at peak (2x)?
  pricing()          — {is_peak, multiplier, bj_now, next_offpeak_utc, ...}
  defer_if_peak()    — for a cadence tick: {defer: bool, action, reason, next_offpeak_utc}

Rules (from the pricing table, 2026-08-24):
  - Weekday (Mon-Fri) Beijing time 09:00-12:00 and 14:00-18:00  -> PEAK (2x).
  - Weekends (Sat/Sun) Beijing time all day                     -> OFF-PEAK (1x).
  - Everything else (nights, weekday lunch gap, after 18:00)    -> OFF-PEAK (1x).
  - Beijing = UTC+8 (no DST).

Deterministic: same instant -> same answer. $0: pure datetime math.
Schema: offpeak.v1
CLI: python -m mag.offpeak now | pricing | next
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA = "offpeak.v1"
BJ = timezone(timedelta(hours=8))  # Beijing = UTC+8, no DST
PEAK_MULT = 2.0
OFFPEAK_MULT = 1.0


def _bj_from(dt: datetime | None) -> datetime:
    """Convert an aware/naive datetime to Beijing time (naive -> assume UTC)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BJ)


def is_peak(dt: datetime | None = None) -> bool:
    """True when this instant is at DeepSeek PEAK pricing (weekday BJ 09-12 / 14-18)."""
    bj = _bj_from(dt)
    if bj.weekday() >= 5:  # Sat/Sun — off-peak all day
        return False
    hm = bj.hour * 60 + bj.minute
    return (9 * 60 <= hm < 12 * 60) or (14 * 60 <= hm < 18 * 60)


def multiplier(dt: datetime | None = None) -> float:
    """The DeepSeek price multiplier right now (2.0 peak, 1.0 off-peak)."""
    return PEAK_MULT if is_peak(dt) else OFFPEAK_MULT


def _next_offpeak_utc(dt: datetime | None = None) -> str:
    """UTC ISO timestamp of when the next off-peak window starts (from this instant)."""
    bj = _bj_from(dt)
    if not is_peak(bj):
        return bj.astimezone(timezone.utc).isoformat()
    # find the next boundary in Beijing time
    cur = bj.replace(second=0, microsecond=0)
    boundaries = []
    for d in range(0, 3):  # look ahead up to 3 days
        day = cur + timedelta(days=d)
        for h in (12, 18):  # end of 09-12, end of 14-18
            b = day.replace(hour=h, minute=0)
            if b > bj:
                boundaries.append(b)
        # weekend: whole day off-peak from Sat 00:00
        if day.weekday() in (5, 6):
            b = day.replace(hour=0, minute=0)
            if b > bj:
                boundaries.append(b)
        else:
            # next weekday morning off-peak starts 00:00 too, but first off-peak after
            # peak today is 18:00 — already covered. Also Fri 18:00 -> Sat 00:00 off-peak.
            pass
    if boundaries:
        nxt = min(boundaries)
        return nxt.astimezone(timezone.utc).isoformat()
    return bj.astimezone(timezone.utc).isoformat()


def _local_peak_windows() -> dict[str, str]:
    """The Beijing peak windows converted to the MACHINE's local timezone (so the operator on
    US Eastern sees '2:00 AM - 6:00 AM' without converting). Computed from the fixed Beijing
    boundaries; DST-correct because Beijing has no DST. Saturday/Sunday: no peak at all."""
    try:
        import zoneinfo
        local = datetime.now().astimezone().tzinfo  # machine local tz
    except Exception:  # noqa: BLE001
        return {"note": "local tz unavailable"}
    out = {}
    for label, start_h, end_h in (("morning_peak", 9, 12), ("afternoon_peak", 14, 18)):
        try:
            base = datetime.now(timezone.utc).date()
            s = datetime(base.year, base.month, base.day, start_h, tzinfo=BJ)
            e = datetime(base.year, base.month, base.day, end_h, tzinfo=BJ)
            out[label] = f"{s.astimezone().strftime('%H:%M')} - {e.astimezone().strftime('%H:%M')} local"
        except Exception:  # noqa: BLE001
            pass
    out["weekends"] = "no peak (off-peak all day)"
    return out


def pricing(dt: datetime | None = None) -> dict[str, Any]:
    """The full pricing window readout for the current instant, in BOTH Beijing and local time."""
    bj = _bj_from(dt)
    peak = is_peak(bj)
    return {"ok": True, "schema": SCHEMA, "is_peak": peak,
            "multiplier": PEAK_MULT if peak else OFFPEAK_MULT,
            "bj_now": bj.isoformat(), "bj_weekday": bj.strftime("%A"),
            "local_now": datetime.now().astimezone().isoformat(),
            "local_peak_windows": _local_peak_windows(),
            "next_offpeak_utc": _next_offpeak_utc(bj),
            "note": "peak = 2x (weekday BJ 09-12/14-18); off-peak = 1x; weekends off-peak all day"}


def defer_if_peak(dt: datetime | None = None, *, allow_peak: bool | None = None) -> dict[str, Any]:
    """For a cadence tick: should heavy NEW work defer because it's peak-priced?
    allow_peak=None -> honor MAG_ALLOW_PEAK env ('1'/'true' forces on); True forces on."""
    if allow_peak is None:
        try:
            import os
            allow_peak = os.environ.get("MAG_ALLOW_PEAK", "").strip().lower() in ("1", "true", "yes")
        except Exception:  # noqa: BLE001
            allow_peak = False
    peak = is_peak(dt)
    if allow_peak or not peak:
        return {"ok": True, "defer": False, "action": "run", "is_peak": peak,
                "multiplier": PEAK_MULT if peak else OFFPEAK_MULT,
                "note": "off-peak or peak allowed — run the work"}
    return {"ok": True, "defer": True, "action": "deferred_peak", "is_peak": True,
            "multiplier": PEAK_MULT,
            "next_offpeak_utc": _next_offpeak_utc(dt),
            "note": "peak pricing (2x) — defer heavy NEW work to off-peak (MAG_ALLOW_PEAK=1 overrides)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="offpeak", description="DeepSeek peak/off-peak pricing window")
    p.add_argument("cmd", nargs="?", default="pricing", choices=["now", "pricing", "next", "defer"])
    a = p.parse_args(argv)
    import json
    if a.cmd == "now":
        print(json.dumps({"bj_now": _bj_from(None).isoformat(), "is_peak": is_peak(),
                          "multiplier": multiplier()}, indent=2))
    elif a.cmd == "next":
        print(json.dumps({"next_offpeak_utc": _next_offpeak_utc(None)}, indent=2))
    elif a.cmd == "defer":
        print(json.dumps(defer_if_peak(), indent=2))
    else:
        print(json.dumps(pricing(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
