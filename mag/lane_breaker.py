"""lane_breaker — the canary's missing actuator (2026-09-13, obstacle wave L08).

THE FINDING: the fleet's hourly canary SENSES drift but has no actuator — a human
is the thrust-then-brake override, which is the crane's phase-2 cheat (success that
bills operator attention). This organ closes the loop: score in, lane suspension out.

Contract: register a baseline once; each check(score, lane) compares against it.
A score dropping >=2% below baseline trips the breaker within one call: the lane is
suspended (state file) until explicitly cleared. Trip writes are append rows —
strata never amended. A deliberate-degraded model MUST trip (the L08 falsifier);
a healthy score MUST NOT.

This is deliberately stateless and dumb: the canary stays the sensor, this is only
the switch. It never kills processes — it writes the suspension state that route
organs (probe_route consumers, wave runners) consult before arming lanes.

Schema: lane_breaker.v1
State: state/lane_breaker.json  {baseline, trips: [...], suspended: {lane: ts}}
CLI:
  python -m mag.lane_breaker register --baseline 1.0
  python -m mag.lane_breaker check --score 0.97 --lane glm-4.5-air
  python -m mag.lane_breaker status
  python -m mag.lane_breaker clear --lane glm-4.5-air --note "re-fed"
  python -m mag.lane_breaker selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "lane_breaker.json"
SCHEMA = "lane_breaker.v1"
TRIP_RATIO = 0.98  # 2% below baseline trips (L08 spec)


def _load() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": SCHEMA, "baseline": None, "suspended": {}, "trips": []}


def _save(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def check(score: float, lane: str, note: str = "") -> dict:
    st = _load()
    ts = datetime.now(timezone.utc).isoformat()
    if st.get("baseline") is None:
        st["baseline"] = score
        _save(st)
        return {"tripped": False, "action": "baseline_registered", "baseline": score, "lane": lane}
    if lane in st["suspended"]:
        return {"tripped": True, "action": "already_suspended", "lane": lane, "since": st["suspended"][lane]}
    if score < st["baseline"] * TRIP_RATIO:
        st["suspended"][lane] = ts
        st["trips"].append({"ts": ts, "lane": lane, "score": score,
                            "baseline": st["baseline"], "note": note})
        _save(st)
        return {"tripped": True, "action": "lane_suspended", "lane": lane, "score": score,
                "baseline": st["baseline"], "ts": ts}
    return {"tripped": False, "action": "pass", "lane": lane, "score": score, "baseline": st["baseline"]}


def clear(lane: str, note: str = "") -> dict:
    st = _load()
    since = st["suspended"].pop(lane, None)
    if since:
        st["trips"].append({"ts": datetime.now(timezone.utc).isoformat(), "lane": lane,
                            "action": "cleared", "since": since, "note": note})
        _save(st)
    return {"cleared": bool(since), "lane": lane}


def selftest() -> int:
    STATE.unlink(missing_ok=True)
    r1 = check(1.0, "SELFTEST")            # registers baseline
    r2 = check(0.99, "SELFTEST")           # healthy, no trip (>= 0.98)
    r3 = check(0.97, "SELFTEST")           # degraded, must trip
    r4 = check(0.50, "SELFTEST")           # while suspended stays suspended
    st = _load()
    ok = (r1["action"] == "baseline_registered"
          and r2["tripped"] is False
          and r3["tripped"] is True and r3["action"] == "lane_suspended"
          and r4.get("action") == "already_suspended"
          and "SELFTEST" in st["suspended"])
    print(f"  baseline:   {r1}")
    print(f"  healthy:    {r2}")
    print(f"  degraded:   {r3}")
    print(f"  suspended:  {r4}")
    print(f"SELFTEST {'PASS' if ok else 'FAIL'} (degraded model must trip within one call — L08 falsifier)")
    STATE.unlink(missing_ok=True)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="lane_breaker")
    ap.add_argument("action", choices=["register", "check", "clear", "status", "selftest"])
    ap.add_argument("--baseline", type=float, default=None)
    ap.add_argument("--score", type=float, default=None)
    ap.add_argument("--lane", default="default")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    if args.action == "selftest":
        return selftest()
    if args.action == "register":
        st = _load()
        st["baseline"] = args.baseline if args.baseline is not None else st.get("baseline")
        _save(st)
        print(json.dumps({"baseline": st["baseline"]}))
        return 0
    if args.action == "check":
        if args.score is None:
            print("--score required")
            return 2
        print(json.dumps(check(args.score, args.lane, args.note), indent=2))
        return 0
    if args.action == "clear":
        print(json.dumps(clear(args.lane, args.note)))
        return 0
    st = _load()
    print(json.dumps({"baseline": st.get("baseline"), "suspended": st.get("suspended", {}),
                      "trips": len(st.get("trips", []))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
