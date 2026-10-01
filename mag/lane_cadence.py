"""lane_cadence — learn the right rhythm for the free lanes (2026-08-25).

Operator: "okay so we need to figure out the right cadence for it" (the free lanes).

cadence_learn holds the CPU ceiling. THIS holds the LANE rhythm: the free pools open and
close (z_ai 1305 overload, nvidia quota-exhausted, groq slow patches), so the question is
WHEN to hit a lane, HOW LONG to back off after a failure, WHEN to fall through to the next
free body, and WHEN the paid brake is allowed to breathe.

Learned from REAL data: fuel_feed's lane profile (ok-rates + failure kinds) and a new
cadence ledger of time-stamped lane outcomes. Policy is data-driven, deterministic, $0:
- retry_after(lane)  — exponential backoff, longer for overload (1305) than for transient.
- best_hours(lane)   — the calm hours per lane from the ledger (schedule heavy work there).
- demote_after()     — losing-streak threshold (matches fuel_feed rotation).
- brake_after()      — the free-rotation failure count before the paid brake may fire.
- learn(round)       — fold one round's outcomes into the ledger.

Schema: lane_cadence.v1
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "memory" / "runs" / "cadence_learn" / "lane_rounds.jsonl"
DEFAULT_RETRY = 5          # base seconds before retrying a lane
OVERLOAD_RETRY = 25        # backoff when the failure is a pool overload (1305/429-overload)
MAX_RETRY = 120            # cap on backoff
DEMOTE_STREAK = 3          # consecutive failures before a lane is pushed to the back
BRAKE_FREE_FAILS = 3       # full-rotation free failures before the paid brake may fire
COOLDOWN_GATE_ERROR: str | None = None  # t84: the fail-closed pacing gates name their cause
BRAKE_GATE_ERROR: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _profile() -> dict[str, dict[str, Any]]:
    try:
        from mag import fuel_feed as f
        return {k: v for k, v in (f.profile().get("lanes") or {}).items()}
    except Exception:  # noqa: BLE001
        return {}


def _ledger_rows() -> list[dict[str, Any]]:
    """Read the time-stamped lane outcomes from fuel_feed's PROFILE (already recorded on every
    attempt — ts + ok + error per row). No separate ledger needed for the cadence to learn."""
    try:
        from mag import fuel_feed as f
        p = Path(f.PROFILE)
    except Exception:  # noqa: BLE001
        return []
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:  # noqa: BLE001
            pass
    return rows


def _is_overload(err: str) -> bool:
    e = (err or "").lower()
    return "1305" in e or "overloaded" in e or "rate limit" in e or "429" in e


def retry_after(lane: str, error: str = "") -> int:
    """Backoff before retrying a lane. Overload failures get a longer breather (the pool needs
    time to open); transient failures retry sooner. Capped."""
    base = OVERLOAD_RETRY if _is_overload(error) else DEFAULT_RETRY
    # stretch with consecutive recent failures from the ledger (up to the cap)
    rows = _ledger_rows()[-10:]
    streak = 0
    for r in reversed(rows):
        if r.get("lane") != lane:
            break
        if not r.get("ok"):
            streak += 1
        else:
            break
    mult = min(2 ** streak, 8)
    return min(base * mult, MAX_RETRY)


def best_hours(lane: str, n: int = 3) -> list[int]:
    """The calmest UTC hours for a lane from time-stamped outcomes (schedule heavy work there)."""
    rows = _ledger_rows()
    by_hour: dict[int, list[bool]] = defaultdict(list)
    for r in rows:
        if r.get("lane") != lane:
            continue
        try:
            ts = r.get("ts") or ""
            hour = int(ts[11:13])
        except Exception:  # noqa: BLE001
            continue
        by_hour[hour].append(bool(r.get("ok")))
    if not by_hour:
        return []
    scored = [(hour, sum(1 for o in oks if o) / len(oks), len(oks))
              for hour, oks in by_hour.items() if len(oks) >= 2]
    scored.sort(key=lambda x: (-x[1], -x[2]))
    return [h for h, _, _ in scored[:n]]


def demote_after() -> int:
    return DEMOTE_STREAK


def cooldown(lane: str) -> int:
    """Seconds remaining before this lane should be retried (0 = ready). Based on its LAST
    failure's time + retry_after (overload = longer). The drain/router can probe cooled lanes
    LAST instead of hammering them — the cadence, USED."""
    global COOLDOWN_GATE_ERROR
    COOLDOWN_GATE_ERROR = None  # a clean read clears the named error
    rows = _ledger_rows()
    for r in reversed(rows):
        if r.get("lane") != lane:
            continue
        if r.get("ok"):
            return 0  # last attempt succeeded -> ready
        try:
            ts = datetime.fromisoformat((r.get("ts") or "").replace("Z", "+00:00"))
        except Exception as _te:  # noqa: BLE001 - an unverifiable lane state must not read as ready
            # GATE FAIL-CLOSED (2026-09-25, t84): the old 'except Exception: return 0' read
            # a FAILED row with an unparseable ts as READY (pacing GO). Call sites confirm
            # the safe direction is the cooled/slower path: queue_gate.preflight denies
            # dispatch while cd>0 (mag/queue_gate.py:206), fuel_feed._lane_order probes
            # cooled lanes last (mag/fuel_feed.py:201), pick_free_glm (below) rides the
            # calmer clerk pool while cd>0. Honor the slower path: a full-cap breather,
            # cause named in COOLDOWN_GATE_ERROR. Self-heals: the next attempt appends a
            # fresh parseable row that becomes this lane's last row.
            # SPEC: tests/test_loop_death_guards.py, t84 SPEC line 3.
            COOLDOWN_GATE_ERROR = f"FAIL-CLOSED: cooldown() ts parse exited: {_te}"
            return MAX_RETRY
        elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
        wait = retry_after(lane, str(r.get("error") or ""))
        return max(0, int(wait - elapsed))
    return 0


GLM_FLASH_FREE = "glm-4.7-flash"      # official Z.ai: free in/cached/out
GLM_FLASH_CLERK = "glm-4.5-flash"     # free, cap 2, calmer pool
GLM_FLASHX_PAID = "glm-4.7-flashx"    # $0.07 — never the free mill


def pick_free_glm(lane: str = "z_ai3") -> str:
    """Cadence for free 4.7-flash cache mining (operator 2026-08-28).

    Ride glm-4.7-flash when the funded API lane is calm (cooldown 0, last
    error not 1305). Drop to glm-4.5-flash while the global 4.7-flash pool
    is congested. Never glm-4.7-flashx. Never a coding-plan key — those
    hang on raw /paas/v4.

    Uses lane_cadence.cooldown + last error from the fuel_feed profile.
    """
    if cooldown(lane) > 0:
        return GLM_FLASH_CLERK
    rows = _ledger_rows()
    for r in reversed(rows):
        if r.get("lane") != lane:
            continue
        if r.get("ok"):
            return GLM_FLASH_FREE
        if _is_overload(str(r.get("error") or "")):
            return GLM_FLASH_CLERK
        return GLM_FLASH_CLERK
    return GLM_FLASH_FREE


def brake_after() -> int:
    """Free-rotation failures (within a 10-min window) before the paid brake may fire."""
    global BRAKE_GATE_ERROR
    BRAKE_GATE_ERROR = None  # a clean pass clears the named error
    rows = _ledger_rows()
    now = datetime.now(timezone.utc)
    recent = 0
    for r in rows[-20:]:
        try:
            ts = datetime.fromisoformat((r.get("ts") or "").replace("Z", "+00:00"))
        except Exception as _te:  # noqa: BLE001 - an unverifiable row must not read as no-failure
            # GATE FAIL-CLOSED (2026-09-25, t84): the old 'except Exception: continue' let
            # an unparseable ts row read as NOT a failure, undercounting recent free fails
            # and delaying the paid brake (the pacing GO: the free rotation keeps pounding
            # unpaced). No production callers today (repo grep: status() + the dist_audit
            # copy); the contract is this docstring: the return is the count of free fails
            # still needed before the brake may fire, so the deny direction is COUNT the
            # unverifiable row. Cause named in BRAKE_GATE_ERROR.
            # SPEC: tests/test_loop_death_guards.py, t84 SPEC line 4.
            recent += 1
            BRAKE_GATE_ERROR = f"FAIL-CLOSED: brake_after() ts parse exited: {_te}"
            continue
        if (now - ts).total_seconds() > 600:
            break
        if not r.get("ok"):
            recent += 1
    return max(0, BRAKE_FREE_FAILS - recent)  # if many free fails recently, brake is ALLOWED


def status() -> dict[str, Any]:
    """The learned cadence, grounded in the profile + ledger."""
    profile = _profile()
    rows = _ledger_rows()
    lanes = {}
    for lid, tele in profile.items():
        fails = tele.get("errors") or []
        err0 = str(fails[0])[:80] if fails else ""
        lanes[lid] = {
            "ok_rate": round(int(tele.get("ok", 0)) / max(int(tele.get("calls", 0)), 1), 3),
            "calls": int(tele.get("calls", 0)),
            "retry_after_s": retry_after(lid, err0),
            "best_utc_hours": best_hours(lid),
            "overload_hint": _is_overload(err0),
        }
    return {
        "ok": True, "schema": "lane_cadence.v1",
        "demote_after": demote_after(),
        "brake_allowed_after_free_fails": BRAKE_FREE_FAILS,
        "ledger_rows": len(rows),
        "cooldown_gate_error": COOLDOWN_GATE_ERROR,
        "brake_gate_error": BRAKE_GATE_ERROR,
        "lanes": lanes,
        "note": "retry_after stretches on consecutive failures (overload = longer breather); "
                "best_utc_hours are calm windows from real outcomes; brake fires only after "
                "free lanes fail a full rotation.",
    }


def learn(lane: str, ok: bool, error: str = "", *, persist: bool = True) -> dict[str, Any]:
    """Fold one lane outcome into the cadence ledger."""
    rec = {"ts": _now(), "lane": lane, "ok": ok, "error": error[:200]}
    if persist:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": "lane_cadence.v1", "recorded": rec}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="lane-cadence")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "learn", "retry"])
    ap.add_argument("--lane", default="z_ai")
    ap.add_argument("--ok", type=int, default=0)
    ap.add_argument("--error", default="")
    a = ap.parse_args()
    if a.cmd == "learn":
        print(json.dumps(learn(a.lane, bool(a.ok), a.error), indent=2))
    elif a.cmd == "retry":
        print(json.dumps({"lane": a.lane, "retry_after_s": retry_after(a.lane, a.error)}, indent=2))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
