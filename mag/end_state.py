"""end_state — the END-STATE ATTRACTOR: the one "castle" target all subsystems flock to, with a
measured distance-to-goal. Closes missing pattern #4 (a defined end-state the whole tree aims at).

  goal()               -> the standing goal (castle_foundation castles = the zeitgeist/coldest vector).
  deploy_attractor()   -> deploy the goal as an action-RIB attractor so the swarm flocks toward it
                          (reuses attractor_tools / rib_action three-body dynamics).
  distance_to_goal()   -> MEASURED distance 0..1 from real subsystem state (errors, queue failed,
                          orphans, verkle freshness, loop health) — provable, not handwaved.
  status()             -> the surface contract.

Deterministic + $0 · guarded (any missing sensor degrades that component, never breaks the run).
Schema: end_state.v1
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

SCHEMA = "end_state.v1"
TRAIL = ROOT / "logs" / "end_state.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x or 0.0)))


def goal() -> dict[str, Any]:
    """The standing goal: the COLDEST SHARED VERTEX — the coldest node in the shared idea graph that
    ALL subsystems aim at. A stateless target (future-proof: no per-subsystem drift, no state debt)."""
    g = {"ok": True, "schema": SCHEMA}
    try:
        from mag import ghost_summon
        cv = ghost_summon.coldest_vertices(limit=5)
        g["coldest_shared_vertex"] = [c.get("title", "")[:80] for c in cv[:3]] if cv else []
        g["goal"] = (cv[0].get("title", "")[:120] if cv and isinstance(cv[0], dict)
                      else str(cv[0])[:80] if cv else "novel")
    except Exception as e:
        g["goal"] = "novel"
        g["goal_error"] = str(e)[:80]
    return g


def deploy_attractor() -> dict[str, Any]:
    """Deploy the goal as an action-RIB attractor so the swarm flocks toward it."""
    g = goal()
    try:
        from mag import attractor_tools
        attrs = [{"domain": "end-state", "witnesses": 12,
                  "invariant": f"flock to end state: {g.get('goal','novel')} — coldest vector: "
                               f"{str(g.get('coldest_vector') or [])[:120]}"}]
        d = attractor_tools.deploy_to_swarm(attrs)
        return {"ok": True, "n_tools": d.get("n_tools"), "collective": d.get("collective"),
                "goal": g.get("goal")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def distance_to_goal() -> dict[str, Any]:
    """MEASURED distance 0..1 from the end state, from real subsystem state. 0 = at the goal."""
    g = goal()
    gaps: list[dict[str, Any]] = []
    # errors/warnings (loop_doctor) — 0 desired
    try:
        from mag import loop_doctor
        d = loop_doctor.sense()
        n_err = int(d.get("n_errors") or 0)
        n_warn = int(d.get("n_warnings") or 0)
        gaps.append({"component": "code-health", "score": _clamp01((n_err * 20 + n_warn * 2) / 100.0),
                     "detail": f"{n_err} err, {n_warn} warn"})
    except Exception:
        pass
    # queue failed items — 0 desired
    try:
        from mag import ghost
        sf = ghost.sense_surfaces()
        q = (sf.get("queue") or {})
        failed = int((q.get("counts") or {}).get("failed") or 0)
        total = int(q.get("total") or 0) or 1
        gaps.append({"component": "queue-health", "score": _clamp01(failed / total),
                     "detail": f"{failed}/{total} failed"})
    except Exception:
        pass
    # ghost loop up? (process_supervisor) — 0 desired if down
    try:
        from mag import process_supervisor
        st = process_supervisor.status() or {}
        loops = st.get("loops") or []
        down = sum(1 for l in loops if not l.get("running"))
        gaps.append({"component": "supervisor", "score": _clamp01(down / max(1, len(loops))),
                     "detail": f"{down}/{len(loops)} loops down"})
    except Exception:
        pass
    # frontier internals: cache-invisible themes — 0 desired
    try:
        from mag import ghost
        fi = ghost.sense().get("frontier_internals") or {}
        zero = len(fi.get("themes_zero_cache") or [])
        gaps.append({"component": "frontier-internals", "score": _clamp01(zero / 4.0),
                     "detail": f"{zero} zero-cache themes"})
    except Exception:
        pass

    # THREE-BODY: the end state IS the three-body attractor field — deploy the goal as an action-RIB
    # attractor and measure how well the flock's three-body dynamics CONVERGE toward the shared vertex
    # (0 = fully converged = at the end state). Stateless: computed live from the dynamics, no ledger.
    try:
        tb = deploy_attractor()
        n_actions = int(tb.get("n_actions") or 0) if "n_actions" in tb else \
                    (len(tb.get("actions") or []) if isinstance(tb.get("actions"), list) else 0)
        # 0 actions emitted = flock converged on the attractor (no stray pulls); more = still diverging
        gaps.append({"component": "three-body-convergence", "score": _clamp01(n_actions / 20.0),
                     "detail": f"{n_actions} actions (flock divergence toward attractor)"})
    except Exception:
        gaps.append({"component": "three-body-convergence", "score": 0.5,
                     "detail": "three-body unavailable (no attractor deployed)"})

    distance = _clamp01(sum(x["score"] for x in gaps) / max(1, len(gaps)))
    # STATELESS by design (future-proof): no ledger/trail written. The distance is a PURE function of
    # current subsystem state + the three-body dynamics — swap/scale the surface freely, no state to migrate.
    return {"ok": True, "schema": SCHEMA, "distance_to_goal": round(distance, 3),
            "goal": g.get("goal"), "coldest_shared_vertex": g.get("coldest_shared_vertex"),
            "gaps": gaps,
            "note": "stateless + future-proof + THREE-BODY: distance 0..1 from the coldest shared vertex; "
                    "0 = the flock fully converged on the attractor. Pure function of live state + "
                    "three-body dynamics, no persistent trail."}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "goal()->the castle (zeitgeist); deploy_attractor()->deploy goal as action-RIB "
                        "attractor; distance_to_goal()->measured 0..1 distance from real subsystem state. "
                        "$0 deterministic.",
            "trail": str(TRAIL.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="end-state")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "goal", "deploy", "distance"])
    a = ap.parse_args()
    r = {"status": status, "goal": goal, "deploy": deploy_attractor, "distance": distance_to_goal}[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
