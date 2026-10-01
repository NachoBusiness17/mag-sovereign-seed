"""verified_clock — THE ONE CLOCK, grounded in the verkle chain (2026-08-24).

Operator: "we need a verified clock everywhere self steal and think about it and how it ties
into our heartbeat/verkles/subsystems we built in the past that are orphaned."

SELF-STEAL finding: every module defines its own private `_now()` (dozens of copies, no single
clock), and time lives scattered across orphaned subsystems:
  - seat_availability (per-seat heartbeat cool/heat ledger)
  - fleet_heartbeat / loop_health (liveness with ts)
  - offpeak (the Beijing pricing clock)
  - the verkle chain (committed ts on every leaf = the GROUND-TRUTH temporal record)
None of them read a single authoritative clock.

This module IS that clock:
  now_iso() / ts()   -> the authoritative UTC now (read once, used everywhere).
  age(ts)            -> seconds since a timestamp (heartbeat age, cadence age, liveness).
  verify()           -> CROSS-CHECK system time against the verkle chain's latest committed ts
                        (drift). If drift is small, the clock is TRUSTED; if large, flag it —
                        "don't trust unanchored time claims" (the grounding rule, made literal).
  anchor()           -> commit the clock's own leaf to the verkle chain (deduped) so the clock
                        itself is on the ground-truth record.
  status()           -> the full readout: utc, local, peak/off-peak, chain ts, drift, trusted.

Ties in: offpeak (pricing from the same clock), seat_availability (heartbeat age),
work_loop/team_knot (anchored reality), cadence (last-fired age). One clock everywhere.

Schema: verified_clock.v1 · deterministic + $0 · reuse: verkle_knot (ground-truth ts), offpeak
CLI: python -m mag.verified_clock now | verify | anchor | status
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "verified_clock.v1"
# drift above this = distrust unanchored time claims (the chain says otherwise)
DRIFT_LIMIT_S = int((__import__("os").environ.get("MAG_CLOCK_DRIFT_LIMIT_S", "300")) or "300")
SESSION_ID = "verified-clock"


def now_utc() -> datetime:
    """The authoritative now, read once from the system clock (UTC)."""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def ts() -> str:
    return now_iso()


def age(ts_iso: str | None) -> float:
    """Seconds since a timestamp (heartbeat age, cadence age, liveness). None/parse-fail -> -1."""
    if not ts_iso:
        return -1.0
    try:
        t = datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (now_utc() - t).total_seconds()
    except Exception:  # noqa: BLE001
        return -1.0


def chain_ts() -> str | None:
    """The verkle chain's latest committed timestamp (the ground-truth temporal record)."""
    try:
        from mag import verkle_knot
        p = verkle_knot.prove_latest()
        # prove_latest gives the merkle path, not a ts — read the chain tail via chain_query
        from mag import chain_query
        q = chain_query.chain_query_endpoint("tail", n=1)
        knots = q.get("knots") or []
        if knots:
            return str(knots[0].get("ts") or "")
    except Exception:  # noqa: BLE001
        pass
    return None


def verify() -> dict[str, Any]:
    """Cross-check system time against the chain's committed ts. Small drift = trusted clock."""
    cts = chain_ts()
    drift = None
    if cts:
        drift = round(age(cts), 1)
    trusted = drift is not None and abs(drift) <= DRIFT_LIMIT_S
    return {"ok": True, "schema": SCHEMA, "sys_ts": now_iso(), "chain_ts": cts,
            "drift_s": drift, "trusted": trusted, "drift_limit_s": DRIFT_LIMIT_S,
            "note": ("clock trusted (matches the chain)" if trusted else
                     "clock drift vs chain — do not trust unanchored time claims")}


def anchor() -> dict[str, Any]:
    """Commit the clock's own leaf to the verkle chain (deduped by leaf hash) so the clock is
    on the ground-truth record — 'verified' means on the chain."""
    try:
        from mag import verkle_knot
        k = verkle_knot.append_verkle_knot({
            "session_id": SESSION_ID,
            "theme": "verified-clock",
            "summary": f"[verified-clock] {now_iso()}",
        })
        return {"ok": True, "schema": SCHEMA, "leaf": k.get("leaf_hash"),
                "root": k.get("verkle_root") or k.get("root"), "note": "clock anchored to the chain"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160]}


def status() -> dict[str, Any]:
    """The full clock readout — one verified source everywhere."""
    v = verify()
    out = {"ok": True, "schema": SCHEMA, "utc_now": now_iso(),
           "local_now": datetime.now().astimezone().isoformat(), **v}
    try:
        from mag.offpeak import pricing
        p = pricing()
        out["peak"] = {"is_peak": p.get("is_peak"), "multiplier": p.get("multiplier"),
                       "bj_now": p.get("bj_now"),
                       "local_peak_windows": p.get("local_peak_windows")}
    except Exception:  # noqa: BLE001
        pass
    out["contract"] = "one verified clock everywhere: offpeak, heartbeat age, cadence age, liveness"
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="verified_clock", description="the one clock, verkle-verified")
    p.add_argument("cmd", nargs="?", default="status", choices=["now", "verify", "anchor", "status"])
    a = p.parse_args(argv)
    if a.cmd == "now":
        print(json.dumps({"schema": SCHEMA, "utc_now": now_iso(),
                          "local_now": datetime.now().astimezone().isoformat()}, indent=2))
    elif a.cmd == "verify":
        print(json.dumps(verify(), indent=2))
    elif a.cmd == "anchor":
        print(json.dumps(anchor(), indent=2))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
