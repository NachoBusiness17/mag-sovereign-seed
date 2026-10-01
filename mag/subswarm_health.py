"""subswarm_health — per-sub-swarm HEALTH with CASCADE ISOLATION (bulkhead / circuit-breaker).

Operator (2026-08-10): "we also need sub swarm health so we don't cascade."

STEAL (microservices fault-isolation): the BULKHEAD + CIRCUIT-BREAKER pattern — isolate a failing
component so its failure does NOT cascade into healthy ones. Applied to our swarms:
  * Each SUBSYSTEM is a sub-swarm (memory, verkle, ghost, rib, frontier, experimenter...).
  * health()   -> per sub-swarm: success rate, active/failed count, recency (staleness).
  * report()   -> the dashboard: HEALTHY / STRESSED / ISOLATED per sub-swarm.
  * circuit()  -> if a sub-swarm's success rate collapses (or failures spike), flip it OPEN
                  (ISOLATED) — tasks ROUTE AROUND it (route_guard) so its failure can't cascade.
  * route_guard() -> which sub-swarms are isolated; dispatchers skip them (the anti-cascade router).

Deterministic, $0 (reads swarm results + recent failures). Schema: subswarm_health.v1
CLI: python -m mag.subswarm_health report|circuit|route
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "subswarm_health.v1"
STATE = ROOT / "memory" / "runs" / "subswarm_health" / "circuit.json"
# a sub-swarm is ISOLATED (circuit OPEN) when success rate < this OR >= this many consecutive fails
FAIL_RATE_THRESHOLD = 0.5
MIN_SAMPLES = 3
MAX_FAIL_STREAK = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict[str, Any]:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(st: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _subsystem_of(result: dict[str, Any]) -> str:
    # derive the sub-swarm from the result's domain/tag
    return str(result.get("domain") or result.get("tag") or "misc").split("-")[0] or "misc"


def health() -> dict[str, Any]:
    """Per sub-swarm health: success rate, counts, recency from the swarm results."""
    from mag import swarm_worker as sw
    results = sw.collect().get("results", [])
    by_sub: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_sub[_subsystem_of(r)].append(r)
    rows = []
    for sub, res in by_sub.items():
        ok = sum(1 for r in res if r.get("ok"))
        fail_streak = 0
        for r in reversed(res):  # most recent first
            if not r.get("ok"):
                fail_streak += 1
            else:
                break
        rows.append({"subsystem": sub, "n": len(res), "ok": ok,
                     "fail": len(res) - ok,
                     "success_rate": round(ok / len(res), 2) if res else 0.0,
                     "fail_streak": fail_streak})
    return {"ok": True, "schema": SCHEMA, "n_results": len(results), "sub_swarms": rows}


def circuit(*, force: bool = False) -> dict[str, Any]:
    """Flip sub-swarms OPEN (ISOLATED) when they collapse — the anti-cascade circuit breaker."""
    st = _load_state()
    h = health()
    flips = []
    for sub in h.get("sub_swarms", []):
        n, rate, streak = sub["n"], sub["success_rate"], sub["fail_streak"]
        bad = n >= MIN_SAMPLES and (rate < FAIL_RATE_THRESHOLD or streak >= MAX_FAIL_STREAK)
        was = st.get(sub["subsystem"], {}).get("status", "healthy")
        if bad and was != "isolated":
            st[sub["subsystem"]] = {"status": "isolated", "opened_at": _now(),
                                    "success_rate": rate, "fail_streak": streak}
            flips.append(sub["subsystem"])
        elif not bad and was == "isolated":
            # half-open recovery: a sub-swarm that recovered flips back to healthy
            st[sub["subsystem"]] = {"status": "healthy", "recovered_at": _now()}
    _save_state(st)
    return {"ok": True, "schema": SCHEMA, "opened_isolated": flips, "state": st}


def route_guard() -> dict[str, Any]:
    """Which sub-swarms are ISOLATED — dispatchers ROUTE AROUND them (anti-cascade)."""
    st = _load_state()
    isolated = [k for k, v in st.items() if v.get("status") == "isolated"]
    return {"ok": True, "schema": SCHEMA, "isolated": isolated, "state": st}


def report() -> dict[str, Any]:
    """The dashboard: per sub-swarm status (HEALTHY / STRESSED / ISOLATED) + isolation state."""
    h = health()
    st = _load_state()
    for sub in h.get("sub_swarms", []):
        s = st.get(sub["subsystem"], {}).get("status", "healthy")
        sub["status"] = "ISOLATED" if s == "isolated" else (
            "STRESSED" if (sub["n"] >= MIN_SAMPLES and sub["success_rate"] < FAIL_RATE_THRESHOLD)
            else "HEALTHY")
    return {"ok": True, "schema": SCHEMA, "sub_swarms": h.get("sub_swarms", []),
            "isolated": [k for k, v in st.items() if v.get("status") == "isolated"]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="subswarm-health")
    ap.add_argument("cmd", nargs="?", default="report", choices=["report", "circuit", "route", "health"])
    args = ap.parse_args(argv)
    if args.cmd == "circuit":
        print(json.dumps(circuit(), indent=2, default=str))
    elif args.cmd == "route":
        print(json.dumps(route_guard(), indent=2, default=str))
    elif args.cmd == "health":
        print(json.dumps(health(), indent=2, default=str))
    else:
        print(json.dumps(report(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
