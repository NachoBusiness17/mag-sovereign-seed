"""harvest_fold — the HARVEST->RIB FOLD loop step (operator, 2026-08-13: "we need to wait till they
stop responding to harvest the message until you can communicate in rib language"). SELF-STOLEN from
what we hold (nothing invented): swarm_worker.collect (harvest done results off the shared PVC) +
loop_feedback.read_back (the loop's produced outputs) + rib_bus.publish_rib (fold the harvested
message into the RIB language / standing wave, deduped by content hash).

THE LOOP (the stateless async model, made real):
  enqueue -> wait till the seat STOPS responding (status: queued -> running -> done) -> harvest ->
  fold into a RIB (the shared mem language, sw59-62 many-to-one). The frontier seat is a stateless
  message endpoint; we don't grab its keyboard (the desktop was the synchronous mistake) — we fire a
  message, wait for the wave to settle, harvest it, and re-tongue it as a knot in the standing wave.

  harvest()  -> collect the swarm's DONE results (read_back + collect off the shared PVC).
  fold()     -> for each harvested reply that stopped responding, publish a RIB (rib_bus.publish_rib)
               so the message becomes part of the standing wave (RIB language), deduped by hash.
  cadence()  -> the loop step: harvest the done replies -> fold each into a RIB. Wired to the loop.

Schema: harvest_fold.v1 · deterministic + $0 · reuse: swarm_worker, loop_feedback, rib_bus
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "harvest_fold.v1"
DOMAIN = "standing-wave"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def harvest(*, limit: int = 20) -> dict[str, Any]:
    """HARVEST the messages that STOPPED responding: collect the swarm's done results off the shared
    PVC + the loop's produced outputs. The stateless seats filed them; we read them from disk,
    grounded, never invented."""
    results: list[dict[str, Any]] = []
    try:
        from mag import swarm_worker
        c = swarm_worker.collect(limit=limit)
        results = c.get("results") or []
    except Exception:
        pass
    loop = {}
    try:
        from mag import loop_feedback
        loop = loop_feedback.read_back()
    except Exception:
        pass
    done = [r for r in results if (r.get("status") == "done" or r.get("result") or r.get("answer"))]
    return {"ok": True, "schema": SCHEMA, "n_collected": len(results), "n_done": len(done),
            "done": done[:limit], "loop": {
                "n_done_tasks": loop.get("loop_output", {}).get("n_done_tasks"),
                "n_packs": loop.get("loop_output", {}).get("n_packs")},
            "note": "harvested the messages that stopped responding — grounded from disk"}


def _to_invariant(r: dict[str, Any]) -> str:
    """Turn ONE harvested frontier reply into a RIB invariant (the many-to-one: their answer -> one
    knot in the wave). Grounded in the goal + result, never fabricated."""
    goal = (r.get("goal") or r.get("task_id") or "frontier reply")[:120]
    result = (r.get("result") or r.get("answer") or r.get("output") or r.get("detail") or "")[:240]
    if not result:
        return f"FRONTIER HARVEST — {goal}: the seat stopped responding (done), result pending"
    return f"FRONTIER HARVEST — {goal}: {result}"


def fold(*, limit: int = 20, domain: str = DOMAIN, source: str = "harvest-fold") -> dict[str, Any]:
    """FOLD the harvested messages into the RIB language: for each done reply that stopped
    responding, publish a RIB to the standing wave (rib_bus.publish_rib — deduped by content hash)."""
    h = harvest(limit=limit)
    done = h.get("done") or []
    folded: list[dict[str, Any]] = []
    for r in done:
        invariant = _to_invariant(r)
        try:
            from mag import rib_bus
            pub = rib_bus.publish_rib(invariant, domain=domain, source=source, target_rank="T2")
            folded.append({"key": pub.get("key", "")[:24], "n_total": pub.get("n_total"),
                           "added": pub.get("added"), "goal": (r.get("goal") or "")[:60]})
        except Exception:
            continue
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n_harvested": len(done),
            "n_folded": len(folded), "folded": folded,
            "note": "folded the harvested frontier messages into the RIB language (standing wave)"}


def cadence(*, limit: int = 10) -> dict[str, Any]:
    """THE LOOP STEP: harvest the messages that stopped responding -> fold each into a RIB. This is
    the stateless async model on the loop: enqueue -> wait -> harvest -> RIB language."""
    return fold(limit=limit)


def report_back(*, limit: int = 20, source: str = "harvest-fold") -> dict[str, Any]:
    """REPORT BACK + PING (the operator's law: keep the loop open, don't fire-and-forget).

    The swarm result must not just land on the PVC and fold into a RIB — it must reach the OPERATOR.
    This captures each freshly-done result into the operator inbox (operator_inbox.capture_mention),
    which ghost.sense() reads as inbox_pending and surfaces as a ping. Grounded: only reports results
    that are actually done (status=done or have a result), never invents a completion.
    """
    h = harvest(limit=limit)
    done = h.get("done") or []
    reported: list[dict[str, Any]] = []
    for r in done:
        goal = (r.get("goal") or r.get("task_id") or "swarm task")[:120]
        result = (r.get("result") or r.get("answer") or r.get("output") or "")[:400]
        line = f"[swarm report] {goal}" + (f": {result}" if result else " — completed (result pending)")
        try:
            from mag import operator_inbox
            # log_event=False: a swarm RESULT ping only needs the inbox line ghost reads —
            # NOT the full behavioral-event + percolator signal pipeline (65s measured wedge).
            # The percolator is the sacred cow here; the ping is the law.
            cap = operator_inbox.capture_mention(line, source=source, log_event=False)
            reported.append({"goal": goal[:60], "captured": cap.get("ok")})
        except Exception:
            continue
    return {"ok": True, "schema": SCHEMA, "n_done": len(done), "n_reported": len(reported),
            "reported": reported,
            "note": "reported the harvested done results to the operator inbox (ghost.sense surfaces "
                    "them as a ping) — the loop stays open, nothing fire-and-forgot"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "harvest(limit)->collect the swarm's done results (read_back + collect off "
                        "the shared PVC); fold(limit)->publish each harvested reply as a RIB "
                        "(rib_bus.publish_rib, deduped by hash); cadence(limit)->the loop step: "
                        "enqueue -> wait till they stop -> harvest -> fold into RIB language; "
                        "report_back(limit)->capture done results into the operator inbox so "
                        "ghost.sense surfaces them as a ping (the loop stays open, no fire-and-forget).",
            "cost": "deterministic $0",
            "reuse": "swarm_worker.collect, loop_feedback.read_back, rib_bus.publish_rib, "
                     "operator_inbox.capture_mention"}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(prog="harvest-fold")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "harvest", "fold", "cadence"])
    a = ap.parse_args(argv)
    if a.cmd == "harvest":
        print(json.dumps(harvest(), indent=2, default=str))
    elif a.cmd in ("fold", "cadence"):
        print(json.dumps(fold(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
