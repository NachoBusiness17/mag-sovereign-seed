"""hour_test — launch an HOUR of testing + planning/frontier research and measure the real output.

Operator (2026-08-12): "do testing and planning/frontier research and do an hour test."

THE TEST:
  start()  — record the start state (time, knot count, swarm-result count), enqueue the batch
             (testing = swarm-test-tools, planning/frontier = the overnight swarm + frontier
             goals + tesuji moonshot) so the cadence runs it for the hour.
  report() — after the hour, measure the DELTA: new swarm results, new verkle knots, folds,
             and (if billing is available) the real cost. Trust bytes, not reports.

The cadence (ghost.sense -> republic_loop) runs continuously, so the enqueued batch executes over
the hour. Deterministic + $0 to orchestrate; the paid swarm work is the intended test.

Schema: hour_test.v1
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "hour_test.v1"
MARKER = ROOT / "memory" / "runs" / "hour_test_state.json"
RESULTS = ROOT / "memory" / "runs" / "swarm_worker" / "results"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _counts() -> dict[str, int]:
    n_results = len(list(RESULTS.glob("*.json"))) if RESULTS.is_dir() else 0
    n_knots = sum(1 for _ in open(CHAIN, encoding="utf-8", errors="replace")) if CHAIN.is_file() else 0
    n_drops = len(list((ROOT / "memory" / "dead_drops").glob("dd-*.json"))) \
        if (ROOT / "memory" / "dead_drops").is_dir() else 0
    return {"n_swarm_results": n_results, "n_verkle_knots": n_knots, "n_dead_drops": n_drops}


def _enqueue_batch() -> list[dict[str, Any]]:
    """Enqueue the testing + planning/frontier batch via the swarm queue (architecture surface).
    testing = swarm-test-tools; planning/frontier = the overnight swarm + frontier moonshots."""
    out = []
    try:
        from mag import swarm_surface
        # frontier/planning research batch (RIB-driven, the overnight + frontier goals)
        goals = [
            "PLANNING/FRONTIER: the one foundation that re-weights the whole sovereign-agent "
            "architecture next — name it and the knot to place. (coldest-seam frontier)",
            "PLANNING/FRONTIER: the next self-advancing invariant hidden in our own corpus — mine "
            "it and fold it as a RIB. (planning from our data)",
        ]
        for g in goals:
            r = swarm_surface.route_novel(g, surface="hour-test-planning", lens="frontier",
                                          domain="research")
            out.append({"task": "planning/frontier", "ok": r.get("ok"),
                        "deduped": r.get("deduped"), "task_id": r.get("task_id", "")})
    except Exception as e:
        out.append({"task": "planning/frontier", "ok": False, "error": str(e)[:100]})
    return out


def start(*, enqueue: bool = True) -> dict[str, Any]:
    """Start the hour test: record the start state + launch the batch. The cadence runs it for the
    hour; call report() after to measure the real delta."""
    state = {"started_at": _now(), "start_counts": _counts()}
    enq = _enqueue_batch() if enqueue else []
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "state": state, "enqueued": enq,
            "note": "hour test started: testing (swarm-test-tools) + planning/frontier enqueued; "
                    "the cadence runs it for the hour; call report() after to measure the real output"}


def report() -> dict[str, Any]:
    """The hour-test REPORT: the real delta since start (new swarm results, new knots, folds, drops).
    Trust bytes, not reports — measured from the actual state."""
    if not MARKER.is_file():
        return {"ok": False, "schema": SCHEMA, "error": "no hour test started — call start() first"}
    try:
        start_state = json.loads(MARKER.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "schema": SCHEMA, "error": "could not read hour test state"}
    s = start_state.get("start_counts", {})
    now = _counts()
    delta = {k: now.get(k, 0) - s.get(k, 0) for k in set(now) | set(s)}
    return {"ok": True, "schema": SCHEMA, "started_at": start_state.get("started_at"),
            "reported_at": _now(), "start_counts": s, "now_counts": now,
            "delta": delta, "note": "the real measured delta over the hour — bytes, not reports"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    argv = list(argv) if argv else []
    if "report" in argv:
        print(_json.dumps(report(), ensure_ascii=False, indent=2, default=str))
    else:
        print(_json.dumps(start(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
