"""Burn gate — promo-hours + quota governor for lane dispatch (2026-09-07).

Born from the 09-07 audit: 73/73 tape seals landed at 04:00-07:59 PT — the ENTIRE
day's 7-wide build wave fired outside the z.ai promo window (08:00-18:00
America/Los_Angeles, Sep 3-20 2026) because the box runs EDT and "morning" felt
like working hours. Every token hit the paid weekly pool. This organ makes the
hours check executable so dispatch is gated, not remembered.

Law: bulk lanes (builders, salons, wide fan-out, backfills) fire only inside the
promo window and only above the quota floor. Judgment (the seat's own replies,
verification, operator comms) is NEVER gated by the clock — premium tokens touch
judgment only, that side of the law is unchanged.

Usage:
  python -m mag.burn_gate check [--quota-pct 4] [--floor 10] [--force]
Exit 0 = GO · 3 = DEFER (outside window) · 4 = DEFER (quota floor).

TZ honesty: PDT = UTC-7 holds through the whole promo window (DST ends Nov 1);
hardcoded offset, no tzdata dependency on Windows. Fix the constant on Nov 2.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys

PROMO_START = _dt.date(2026, 9, 3)
PROMO_END = _dt.date(2026, 9, 20)
PT_OFFSET = _dt.timedelta(hours=-7)  # PDT through 2026-11-01
WINDOW_OPEN, WINDOW_CLOSE = 8, 18  # PT hours, inclusive-open


def now_pt() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc) + PT_OFFSET


def in_window(ts: _dt.datetime | None = None) -> bool:
    ts = ts or now_pt()
    if not (PROMO_START <= ts.date() <= PROMO_END):
        return False
    return WINDOW_OPEN <= ts.hour < WINDOW_CLOSE


def check(quota_pct: float, floor: float, force: bool = False) -> int:
    ts = now_pt()
    window = in_window(ts)
    headroom = quota_pct >= floor
    print(f"burn_gate: now={ts.isoformat()} PT | promo window "
          f"{PROMO_START}..{PROMO_END} {WINDOW_OPEN:02d}:00-{WINDOW_CLOSE:02d}:00 PT")
    print(f"burn_gate: in_window={window} | quota={quota_pct:.0f}% floor={floor:.0f}% "
          f"headroom={headroom}")
    if force:
        print("burn_gate: GO (forced — operator override, on record)")
        return 0
    if not window:
        print("burn_gate: DEFER — outside promo hours; bulk lanes queue, "
              "judgment lanes unaffected")
        return 3
    if not headroom:
        print("burn_gate: DEFER — quota below floor; judgment only until refill")
        return 4
    print("burn_gate: GO — inside window, above floor")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="burn_gate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("--quota-pct", type=float, default=100.0)
    ck.add_argument("--floor", type=float, default=10.0)
    ck.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.cmd == "check":
        return check(args.quota_pct, args.floor, args.force)
    return 2


if __name__ == "__main__":
    sys.exit(main())
