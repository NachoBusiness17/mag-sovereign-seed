"""work_loop — the standing bank-or-halt loop. Work ONLY when the chain/queue has a task;
bank the result; halt at 0% CPU when empty. Built ONCE, wired standing (2026-08-24).

Frontier consensus (lane_salon, 2026-08-24): "the loop only runs when a concrete task exists
in the verkle chain, and it must bank a result or halt. No task = sleep at 0% CPU. No
speculative spin." That's the fix for the night that "banked nothing and spun CPU."

SELF-STEAL (recombine what we already proved — nothing invented):
  * sense()  -> game_play.sense pattern: event-driven read of the work state (no polling).
  * bank     -> ox_resident banking (OX_RESIDENT_*.json artifacts) + verkle fold.
  * queue    -> orchestrator (enqueue/drain/list_queue) — the real source of work.
  * halt     -> the NEW guard: empty + nothing running = halt (no governor spin).

The standing seam: any session/cadence calls work_loop.run_once() instead of fire-all-lanes.
REST: POST /api/v1/work/once (run a tick), GET /api/v1/work/status. CLI: python -m mag.work_loop.

Schema: work_loop.v1 · deterministic + $0 coordinator · reuse: orchestrator, governor, ox_resident
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "work_loop.v1"

# Discovery burn size: a BOUNDED batch (NOT the thousand-ask megaburn) — just enough new
# reasoning to refill the cold-vertex backlog each discovery pass. Small by design.
DISCOVERY_BATCH = 8


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _orchestrator() -> Any:
    from mag import orchestrator
    return orchestrator


def _cold_pending() -> dict[str, Any]:
    """The COLDEST-VERTEX demand (the operator's default action): discovered high-yield cells +
    not-yet-banked novel cores, minus already-done/retry-capped ones. This is REAL discovered
    work — not speculative spin. Reuses ox_resident.target_cells/done/attempts."""
    try:
        from mag import ox_resident
        cells = ox_resident.target_cells() or []
        drilled = ox_resident.drilled_cores()
        pending = [c for c in cells if c["core"] not in drilled]
        return {"ok": True, "cells": len(cells), "pending": len(pending),
                "note": "coldest-vertex demand — discovered high-yield work to drill + bank"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120], "cells": -1, "pending": -1}


def sense() -> dict[str, Any]:
    """Event-driven read of the WORK state (no polling, no LLM): queued tasks, running tasks,
    and the COLDEST-VERTEX demand (the default action's backlog). The source of work is the
    queue/chain + the discovered cold vertices — this reads both."""
    orch = _orchestrator()
    queued = running = 0
    try:
        q = orch.list_queue()
        queued = sum(1 for row in q if str(row.get("status") or "") == "queued")
        running = sum(1 for row in q if str(row.get("status") or "") in ("running", "dispatched"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": f"sense: {str(e)[:120]}"}
    cold = _cold_pending()
    return {"ok": True, "schema": SCHEMA, "queued": queued, "running": running,
            "cold_cells": cold.get("cells"), "cold_pending": cold.get("pending"),
            "has_work": bool(queued or running or (cold.get("pending") or 0) > 0),
            "ts": _now(), "note": "work = queued tasks + running + coldest-vertex backlog; empty = halt"}


def _scan_cold() -> dict[str, Any]:
    """Deterministic re-scan of the cold-vertex backlog (novelty index + novel CORES)."""
    try:
        from mag import ox_resident
        cells = ox_resident.target_cells() or []
        drilled = ox_resident.drilled_cores()
        pending = [c for c in cells if c["core"] not in drilled]
        return {"ok": True, "cells": len(cells), "pending": len(pending),
                "detail": f"re-scanned {len(cells)} cells — {len(pending)} new cold vertices"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:160], "cells": -1, "pending": -1}


def _ceiling_gate() -> dict[str, Any]:
    """CEILING-AT-POLL (GSTD steal #3, 2026-08-24): before the loop claims ANY work, check the
    machine's headroom. At/above the CPU ceiling -> REFUSE work (honest throttle — the loop must
    never burn the box to improve it; the queue/cold vertices wait for the next tick). Under the
    ceiling -> return the drill width the machine can actually carry (cadence_learn
    throttled_workers, which tapers parallelism as CPU climbs). Deterministic + $0."""
    try:
        from mag import cadence_learn
        h = cadence_learn.headroom()
        if h.get("throttle"):
            return {"ok": True, "schema": SCHEMA, "action": "throttled",
                    "gate": "ceiling", "throttled": True,
                    "cpu_pct": h.get("cpu_pct"), "ceiling": h.get("ceiling"),
                    "headroom_pct": h.get("headroom_pct"),
                    "detail": f"CPU at/above ceiling ({h.get('cpu_pct')} >= "
                              f"{h.get('ceiling')}) — refused work; box stays usable",
                    "note": "ceiling-at-poll: the machine protects itself before claiming work"}
        width = int(cadence_learn.throttled_workers() or 0)
        return {"ok": True, "schema": SCHEMA, "gate": "ceiling", "throttled": False,
                "cpu_pct": h.get("cpu_pct"), "ceiling": h.get("ceiling"),
                "headroom_pct": h.get("headroom_pct"), "drill_width": width or None,
                "note": "under the ceiling — machine can carry the drill"}
    except Exception as e:  # noqa: BLE001 — the gate must never BREAK the loop; it DENIES instead
        # SPEC (2026-09-25, t52): FAIL CLOSED. The old except returned throttled=False
        # ("assume safe (no throttle)") so an errored headroom check let the loop claim
        # work with the ceiling unknown. An errored gate now honors the deny (throttled,
        # run_once refuses work this tick) and names the error in ceiling_gate_error.
        return {"ok": False, "schema": SCHEMA, "gate": "ceiling", "throttled": True,
                "cpu_pct": None, "ceiling": None, "drill_width": None,
                "ceiling_gate_error": str(e)[:150],
                "detail": "ceiling gate errored; failing CLOSED (work refused): " + str(e)[:110],
                "note": "ceiling gate unavailable; deny honored, no work claimed this tick"}


def _discover() -> dict[str, Any]:
    """DISCOVERY (the refill half — the skeleton's last bone): when the cold-vertex backlog
    runs dry, generate NEW work with a BOUNDED discovery burn (ox_megaburn3.run(batch=N) —
    a small batch of CORES x scopes x contexts, NOT the thousand-ask burn). The new reasoning
    banks and feeds the novelty index -> next scan sees new cold vertices -> the drill consumes
    them. Only halt when even the generator has nothing left."""
    s = _scan_cold()
    if s.get("ok") and (s.get("pending") or 0) > 0:
        return {**s, "note": "discovery = re-scan of novelty index + CORES (no burn needed)"}
    try:
        from mag import ox_megaburn3
        r = ox_megaburn3.run(batch=DISCOVERY_BATCH)
        fired = int(r.get("fired_this_run") or 0)
        ok_n = int(r.get("ok_count") or 0)
        # after the burn, re-scan — new novel cells should be in the index
        s2 = _scan_cold()
        return {"ok": True, "action": "discovered", "fired": fired, "ok": ok_n,
                "cells": (s2 or {}).get("cells"), "pending": (s2 or {}).get("pending"),
                "detail": f"discovery burn fired {fired} asks ({ok_n} ok) — "
                          f"re-scan sees {(s2 or {}).get('pending', 0)} new cold vertices",
                "note": "bounded discovery burn refills the backlog (small, not the thousand-ask burn)"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:160], "cells": -1, "pending": -1,
                "note": "discovery unavailable — the loop halts honestly rather than spinning"}


def _learn(banked_any: bool) -> dict[str, Any]:
    """LEARN (2026-08-24, the seam): map what the loop banked into the percolator so it becomes
    standing knowledge — novel->explore, consolidated->invariant, noise->noise, and the drilled
    distill -> invariant. Without this the loop banks files but never learns (the deep-steal gap
    between ox artifacts and the percolator). Deterministic + $0, deduped."""
    try:
        from mag import ox_percolate
        s = ox_percolate.sync()
        if banked_any:
            d = ox_percolate.distill()
            return {"ok": True, "action": "learned", "mapped": s.get("percolated", 0),
                    "distilled": d.get("percolated", 0),
                    "invariants": s.get("invariants_total") or d.get("invariants_total") or 0,
                    "detail": "mapped banked artifacts + drilled distill into the percolator"}
        return {"ok": True, "action": "learned", "mapped": s.get("percolated", 0),
                "invariants": s.get("invariants_total", 0),
                "detail": "mapped new artifacts into the percolator"}
    except Exception as e:  # noqa: BLE001 — learning must never break the loop
        return {"ok": False, "action": "learn_error", "error": str(e)[:160]}


def _anchor(action: str, s: dict[str, Any]) -> None:
    """Anchor the tick to the VERKLE CHAIN (the operator: 'use the verkles'): one committed
    work-loop leaf, deduped — the chain is the ground truth of the loop's state, so any
    session reads the same committed state instead of its own in-process claim."""
    try:
        from mag import verkle_knot
        verkle_knot.append_verkle_knot({
            "session_id": "work-loop",
            "theme": "work-loop",
            "summary": f"[work-loop] action={action} queued={s.get('queued', 0)} "
                       f"running={s.get('running', 0)} cold_pending={s.get('cold_pending', 0)}",
        })
    except Exception as _va:  # noqa: BLE001 — anchoring must never break the loop
        # LOOP-DEATH GUARD (2026-09-25, t19 except-pass sweep): a silently dead anchor
        # voids the "every tick anchored to the verkle chain" custody claim while the
        # loop keeps claiming banked work. Non-fatal, but visible.
        print(f"[work-loop] VERKLE-ANCHOR LOOP DEATH GUARD: append_verkle_knot exited: {_va}", flush=True)


def run_once(*, drill: int | None = None) -> dict[str, Any]:
    """ONE bank-or-halt tick, with the COLDEST VERTEX as the DEFAULT ACTION (2026-08-24):
      0. CEILING-AT-POLL (GSTD #3): refuse work if the machine is at/above the CPU ceiling.
      1. queued/running tasks -> drain (bank results).
      2. else -> DRILL THE COLDEST VERTEX (ox_resident.run): real discovered high-yield work,
         bounded (done-set + RETRY_CAP), banks each result. This is the default when idle.
      3. drill exhausted -> DISCOVER (deterministic re-scan: novelty index + novel CORES)
         refills the backlog; next tick drills the new vertices.
      4. nothing new -> HALT at 0% CPU (no speculative governor spin).
    Every tick is anchored to the verkle chain (shared ground truth, no in-process claims)."""
    g = _ceiling_gate()
    if g.get("throttled"):
        return g  # the box is already hot — refuse work, sleep, protect the machine
    s = sense()
    if not s.get("ok"):
        return s
    orch = _orchestrator()
    if s.get("queued") or s.get("running"):
        try:
            r = orch.drain_parallel()
            out = {"ok": True, "schema": SCHEMA, "action": "drained", "ts": _now(),
                   "queued": s["queued"], "running": s["running"],
                   "drain": (r or {}).get("action"), "detail": (r or {}).get("detail", "")[:160],
                   "note": "drained real queued work — results banked by the orchestrator/ox"}
            _anchor("drained", s)
            return out
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "schema": SCHEMA, "action": "drain_error",
                    "error": str(e)[:160], "ts": _now()}
    # DEFAULT ACTION: drill the coldest vertex (bounded, banked, real discovered work)
    if (s.get("cold_pending") or 0) > 0:
        try:
            from mag import ox_resident
            width = int(drill or g.get("drill_width") or ox_resident.CONCURRENCY)
            r = ox_resident.run(drill=width)
            asks = int(r.get("asks") or 0)
            if asks > 0:
                # fold the real round into cadence_learn so the worker cap adapts from data
                try:
                    from mag import cadence_learn
                    cadence_learn.learn({"workers": asks,
                                         "ok": int(r.get("new_ok") or 0) > 0,
                                         "cpu_pct": g.get("cpu_pct")})
                except Exception:  # noqa: BLE001 — learning must never break the drill
                    pass
                learn = _learn(banked_any=int(r.get("new_ok") or 0) > 0)
                out = {"ok": True, "schema": SCHEMA, "action": "drilled", "ts": _now(),
                       "fired": r.get("fired"), "new_ok": r.get("new_ok"),
                       "cold_pending": s.get("cold_pending"),
                       "learn": learn,
                       "detail": f"drilled {r.get('fired')} coldest-vertex asks, "
                                 f"{r.get('new_ok')} banked (ox_resident)",
                       "note": "default action = coldest-vertex drill (discovered work, banked)"}
                _anchor("drilled", s)
                return out
            # run() found nothing pending (race) -> discovery below
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "schema": SCHEMA, "action": "drill_error",
                    "error": str(e)[:160], "ts": _now()}
    # DISCOVERY: refill the backlog when it's exhausted (bounded burn, then re-scan)
    d = _discover()
    if d.get("ok") and ((d.get("pending") or 0) > 0 or (d.get("fired") or 0) > 0):
        learn = _learn(banked_any=int(d.get("fired") or 0) > 0)
        out = {"ok": True, "schema": SCHEMA, "action": "discovered", "ts": _now(),
               "cold_pending": d.get("pending"), "fired": d.get("fired"),
               "learn": learn,
               "detail": d.get("detail", ""),
               "note": "discovery refilled the backlog — next tick drills the new cold vertices"}
        _anchor("discovered", s)
        return out
    # FUEL (2026-08-24): the real work sources -> the free lanes. When queue + cold are empty,
    # feed the percolator's explore queue (291 novel signals) through the free-lane channel and
    # fold the answers back. This is "use the seats instead of looking at them."
    # SPEC (2026-09-25, t43): the fuel swallow below discarded the captured error and fell
    # through to the halt branch, which then filed a FALSE halt note ("nothing real left to
    # do") even when the halt was caused by the fuel channel crashing. Fix: trace the crash
    # (ghost.py LOOP-DEATH GUARD pattern) and record fuel_error so the halt note tells the
    # truth about why this tick stopped.
    fuel_error: str | None = None
    try:
        from mag import fuel_feed
        fr = fuel_feed.run(batch=1)
        if int(fr.get("fired") or 0) > 0:
            out = {"ok": True, "schema": SCHEMA, "action": "fed", "ts": _now(),
                   "fuel": fr.get("results", []),
                   "detail": fr.get("detail", ""),
                   "note": "fed explore-queue signals through the free lanes — real work flowing"}
            _anchor("fed", s)
            return out
    except Exception as e:  # noqa: BLE001
        # LOOP-DEATH GUARD (2026-09-25, t43): a silently dead fuel channel made the halt
        # below claim "nothing real left to do" while real work may sit behind the crash.
        # Non-fatal, but visible and truth-carrying. Evidence: t19 next_steal census;
        # tests/test_loop_death_guards.py::work_fuel proves the honest halt note.
        fuel_error = str(e)[:160]
        print(f"[work-loop] FUEL LOOP DEATH GUARD: fuel_feed.run exited: {e}", flush=True)
    out = {"ok": True, "schema": SCHEMA, "action": "halt", "ts": _now(),
           "queued": 0, "running": 0, "cold_pending": s.get("cold_pending"),
           "detail": "queue empty + all cold vertices banked + no new discovery — halted at 0% CPU",
           "note": "nothing real left to do; sleep, don't spin"}
    if fuel_error:
        # the note must tell the truth: this halt is NOT a verified "nothing left" halt
        out["fuel_error"] = fuel_error
        out["detail"] += f"; FUEL CHANNEL ERRORED: {fuel_error}"
        out["note"] = ("halt reached with the fuel channel dead; "
                       "NOT a verified 'nothing left to do' halt; fix fuel before trusting it")
    _anchor("halt", s)
    return out


def status() -> dict[str, Any]:
    """The loop's standing status — where the work loop is, and what it would do."""
    s = sense()
    return {"ok": True, "schema": SCHEMA, "ts": _now(), **{k: v for k, v in s.items() if k != "ok"},
            "contract": "work_loop.run_once() = bank-or-halt: run only on real tasks, halt at 0% CPU",
            "built": "2026-08-24 — standing surface, do NOT rebuild (see work_loop docstring)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="work_loop", description="standing bank-or-halt work loop")
    p.add_argument("cmd", nargs="?", default="status", choices=["status", "sense", "once"])
    a = p.parse_args(argv)
    if a.cmd == "sense":
        print(json.dumps(sense(), indent=2))
    elif a.cmd == "once":
        print(json.dumps(run_once(), indent=2))
    else:
        print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
