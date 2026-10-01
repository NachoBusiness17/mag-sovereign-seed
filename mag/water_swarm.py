"""water_swarm — instruct the swarms to BE WATER: flow and form around the invariants BEFORE we
detect them. The stochastic water pre-shapes around the deterministic lattice (the invariants),
adapting to their probable form before they're confirmed.

OPERATOR (2026-08-12): "now we can instruct our swarms to be our water flowing and forming around
invariants before we can detect them." The quant versions of all our tools (tool_quant) give us the
INVARIANT LATTICE; the swarm is the WATER that flows around it. The map (invariants) precedes the
territory; the water forms to the map's probable shape before the territory is detected.

THE MECHANISM (self-steal):
  invariant_lattice() -> the deterministic bones: tool_quant roots + rib_bus RIBs + coldest vertices.
  water_doctrine()    -> the STEERING that tells the swarm "be water: flow, adapt, form around these
                         invariants before you detect them" (via steer_engine — the unified steering).
  flow(enqueue)       -> instruct the swarm: route research goals that PRE-ADAPT around each
                         invariant (the probable lattice), so the water is already formed to the
                         shape before it's confirmed. Deterministic + $0 (dry); enqueue -> swarm.

Schema: water_swarm.v1 · deterministic + $0 (lattice/doctrine); flow routes to the swarm
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "water_swarm.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def invariant_lattice(*, limit: int = 8) -> list[dict[str, Any]]:
    """The DETERMINISTIC lattice the water forms around: tool_quant roots + rib_bus RIBs +
    coldest vertices. Grounded, never fabricated."""
    lattice: list[dict[str, Any]] = []
    try:
        from mag import tool_quant
        tools = tool_quant.scan_tools()
        for t in tools[:limit]:
            q = tool_quant.quant_tool(t["name"], t["path"])
            if q.get("ok"):
                lattice.append({"kind": "tool-quant", "id": t["name"],
                                "root": q["quant"]["root"][:16]})
    except Exception:
        pass
    try:
        from mag import rib_bus
        st = rib_bus.status()
        for dom, info in list(st.get("domains", {}).items())[:limit]:
            lattice.append({"kind": "rib-domain", "id": dom, "n": info.get("n_ribs", 0)})
    except Exception:
        pass
    return lattice


def water_doctrine() -> str:
    """The 'water' steering block: flow, adapt, form around the invariants before detection.
    Self-steal: compiled through steer_engine (the unified steering) so it's consistent + telemetry-fed."""
    try:
        from mag import steer_engine
        c = steer_engine.compile_steer("water")
        base = "\n".join(f"- {s}" for s in c["steer"][:6])
    except Exception:
        base = "- flow, adapt, form around the invariants before you detect them (water finds the lattice's shape)"
    return (f"WATER DOCTRINE (be water):\n"
            f"{base}\n"
            f"- FLOW: adapt to the probable invariant shape BEFORE it is confirmed (map precedes territory).\n"
            f"- FORM: pre-shape your output around the lattice (the deterministic bones), not around a confirmed outcome.\n"
            f"- TURTLE: each form you take is itself an invariant — turtles all the way down.\n")


def flow(*, enqueue: bool = True, limit: int = 6) -> dict[str, Any]:
    """Instruct the swarms to be water: route research goals that FLOW and FORM around each
    invariant in the lattice BEFORE detection. The water is pre-shaped to the probable invariants."""
    lattice = invariant_lattice(limit=limit)
    doctrine = water_doctrine()
    routed = []
    for inv in lattice:
        goal = (f"{doctrine}\nTARGET-INVARIANT: {inv.get('kind')} '{inv.get('id')}' "
                f"(root={inv.get('root', inv.get('n', ''))}). BE WATER: flow and form around this "
                f"invariant BEFORE it is fully detected — pre-adapt your output to its probable "
                f"shape (map precedes territory), then return the form you took.")
        if enqueue:
            from mag import swarm_surface
            r = swarm_surface.route_novel(goal, surface=f"water:{inv.get('id','x')[:24]}",
                                          lens="water/form", domain="water")
            routed.append({"invariant": inv.get("id"), "kind": inv.get("kind"),
                           "routed": r.get("ok"), "task_id": r.get("task_id", ""),
                           "deduped": r.get("deduped")})
        else:
            routed.append({"invariant": inv.get("id"), "kind": inv.get("kind"),
                           "routed": True, "dry": True})
    return {"ok": True, "schema": SCHEMA, "n_invariants": len(lattice), "n_routed": len(routed),
            "enqueue": enqueue, "doctrine": doctrine[:120],
            "routed": routed,
            "note": "the swarm is water: it flows and forms around the invariants before detection"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "invariant_lattice()->deterministic bones; water_doctrine()->the 'be water' "
                        "steering; flow()->instruct the swarm to pre-form around the invariants "
                        "before detection",
            "cost": "deterministic + $0 (lattice/doctrine); flow enqueues to the swarm"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="water-swarm")
    ap.add_argument("cmd", nargs="?", default="flow", choices=["flow", "lattice", "status"])
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args()
    if a.cmd == "lattice":
        print(json.dumps(invariant_lattice(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(flow(enqueue=not a.no_enqueue), ensure_ascii=False, indent=2, default=str))
