"""gap_frontier — REFINE the frontier loop to find gaps: aggregate the gaps across every surface,
route the refined gap-analysis to the swarm (frontier models find the sharpest gaps + how to close
them), and loop the results. The standing-wave synthesis, refined for gap-finding.

Operator (2026-08-11): "refine and fronteir loop to find gaps".

SELF-STOLEN gap surfaces (real):
  research_class.gaps()     -> one-lens classification coverage gaps (the underexplored lens cells).
  self_loop.loop_zeitgeist()-> the coldest vector (the neglected direction the swarm should fill).
  orphan_sense.novel_orphans()-> the novel orphans (neglected novel work).
  agentic_test_steal.map_ours()-> where our surfaces have no test = capability gaps.
  budget_refactor.plan()   -> the cost-waste gaps (miss bursts to kill).

THE REFINED LOOP (deterministic + $0 aggregation, swarm-routed frontier gap analysis):
  gaps()  -> aggregate ALL gaps across surfaces into one gap map (grounded, deduped by signature).
  refine()-> route the gap map to the SWARM (swarm_surface.route_novel): a frontier model refines
             the gaps into the sharpest ones + the single highest-leverage gap to close next.
  loop()  -> gaps -> refine via swarm -> read back -> the loop finds and closes gaps by default.

Schema: gap_frontier.v1 · deterministic + $0 aggregation · swarm-routed frontier refinement
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "gap_frontier.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def gaps() -> dict[str, Any]:
    """Aggregate ALL gaps across every surface into one grounded gap map."""
    agg: dict[str, Any] = {"ok": True, "schema": SCHEMA, "ts": _now(), "gaps": []}

    # research_class coverage gaps (underexplored lens cells)
    try:
        from mag import research_class
        g = research_class.gaps(8)
        for cell in g.get("gaps", [])[:8]:
            agg["gaps"].append({"surface": "lens-coverage", "kind": "lens-gap",
                                "id": str(cell.get("lens") or cell.get("cell") or cell)[:80],
                                "text": str(cell)[:160]})
    except Exception as e:
        agg["gaps"].append({"surface": "lens-coverage", "error": str(e)[:80]})

    # self_loop coldest vector (the neglected direction)
    try:
        from mag import self_loop
        z = self_loop.loop_zeitgeist()
        for c in z.get("coldest_vector", [])[:5]:
            agg["gaps"].append({"surface": "zeitgeist", "kind": "cold-vector",
                                "id": str(c)[:80], "text": str(c)[:160]})
    except Exception as e:
        agg["gaps"].append({"surface": "zeitgeist", "error": str(e)[:80]})

    # novel orphans (neglected novel work)
    try:
        from mag import orphan_sense
        o = orphan_sense.novel_orphans(enqueue=False)
        agg["n_orphan_gaps"] = o.get("n_novel_orphans", 0)
        for f in o.get("novel_orphans", [])[:5]:
            if f.get("novel"):
                agg["gaps"].append({"surface": "orphans", "kind": "novel-orphan",
                                    "id": str(f.get("id"))[:80], "text": str(f.get("text"))[:160]})
    except Exception as e:
        agg["gaps"].append({"surface": "orphans", "error": str(e)[:80]})

    # agentic-test capability gaps (surfaces with no test)
    try:
        from mag import agentic_test_steal
        m = agentic_test_steal.map_ours()
        for r in m.get("map", [])[:4]:
            agg["gaps"].append({"surface": "testing", "kind": "capability-gap",
                                "id": r.get("framework", ""), "text": r.get("our_surface", "")[:160]})
    except Exception as e:
        agg["gaps"].append({"surface": "testing", "error": str(e)[:80]})

    # cost-waste gap (the miss burst to kill)
    try:
        from mag import budget_refactor
        w = budget_refactor.waste()
        agg["gaps"].append({"surface": "economics", "kind": "cost-waste",
                            "id": "cache-miss", "text": f"recover ${w.get('recoverable_usd')} of miss waste"})
    except Exception as e:
        agg["gaps"].append({"surface": "economics", "error": str(e)[:80]})

    # dedupe by (surface,id)
    seen, dedup = set(), []
    for g in agg["gaps"]:
        k = (g.get("surface", ""), str(g.get("id", "")))
        if k in seen:
            continue
        seen.add(k); dedup.append(g)
    agg["gaps"] = dedup
    agg["n_gaps"] = len(dedup)
    agg["note"] = "ALL gaps aggregated across lens-coverage/zeitgeist/orphans/testing/economics"
    return agg


def refine(*, enqueue: bool = True, surface: str = "gap-frontier") -> dict[str, Any]:
    """Route the gap map to the SWARM: a frontier model refines the gaps into the sharpest ones +
    the single highest-leverage gap to close next. The refined gap-finding of the loop."""
    g = gaps()
    gap_txt = "; ".join(f"{x.get('surface')}:{x.get('id','')}" for x in g["gaps"][:15])
    goal = (f"REFINE FRONTIER LOOP GAPS: here are ALL the gaps aggregated from the Republic's "
            f"surfaces: {gap_txt}. n_gaps={g['n_gaps']}. "
            f"Refine them: (1) collapse into the sharpest distinct gaps (dedupe overlap), "
            f"(2) rank by leverage (which gap, closed, unblocks the most others), "
            f"(3) name the SINGLE highest-leverage gap to close next + the one buildable step to "
            f"close it. Label each: GAP: <sharp gap> / LEVERAGE: <1-10> / CLOSE_NEXT: <one step>.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="compiler/world",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_gaps": g["n_gaps"],
            "gap_map": g["gaps"][:15], "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "deduped": q.get("deduped", False),
            "note": "gap map routed to the swarm for frontier refinement (the loop finds + closes "
                    "gaps by default)"}


def loop(*, enqueue: bool = True) -> dict[str, Any]:
    """The refined frontier gap-loop: aggregate gaps -> refine via swarm -> the sharpest gap next."""
    g = gaps()
    r = refine(enqueue=enqueue)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_gaps": g["n_gaps"],
            "gap_map": g["gaps"][:15], "refined_task": r.get("task_id"),
            "enqueued": r.get("enqueued"),
            "note": "frontier loop refined for gap-finding: all gaps aggregated, frontier refines "
                    "them, the highest-leverage gap gets closed next"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "gaps()->aggregate ALL gaps across lens-coverage/zeitgeist/orphans/testing/"
                        "economics; refine()->route the gap map to the swarm for frontier refinement; "
                        "loop()->gaps -> refine -> close the sharpest gap next",
            "cost": "deterministic + $0 aggregation (frontier refinement swarmed)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="gap-frontier")
    ap.add_argument("cmd", nargs="?", default="loop", choices=["loop", "gaps", "refine", "status"])
    a = ap.parse_args()
    if a.cmd == "gaps":
        print(json.dumps(gaps(), indent=2, default=str))
    elif a.cmd == "refine":
        print(json.dumps(refine(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(loop(), indent=2, default=str))
