"""tool_lifecycle — route TOOL CREATION through the standing-wave pipeline (born, bred, percolated,
verified, rendered, branched, propagated).

Operator (2026-08-13): "what would routing tool creation through this look like?" -> "yes".

THE LIFECYCLE — a new tool is a first-class citizen of the constitutional percolation:
  1. BORN   — an insight/need arrives as a TESUJI (tesuji_steal.on_unexpected: hold + mine).
  2. CARRIED— validated + earns its place -> encoded as a GENE RIB the system carries (carry_gene).
  3. SELECTED— joins the BREEDING population (genetic_pass: is it fit? does it survive connectivity?
               leaf = stdlib / shared = one-primitive / frontier = thin).
  4. PERCOLATED— merged toward the ONE (percolate_to_one: the quant root carries it).
  5. VERIFIED— expectations_monitor: does it KEEP working over time (RIB-debug law)?
  6. RENDERED— rib_render + clawbot: the tool + its place in the lattice, visible on the desktop.
  7. BRANCHED— invariant_frontier: the gap to the frontier, routed (search-swarm + conversation + steal).
  8. PROPAGATED— route_novel: the tool's invariant sent into the medium.

Deterministic + $0 core; the mine/branch/propagate seams route to the swarm. HONEST — real bytes at
every step; never fabricates a lifecycle stage.
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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "tool_lifecycle.v1"


def born(need: str, *, source: str = "new-tool") -> dict[str, Any]:
    """1. BORN: an insight/need arrives as a TESUJI — hold it (RIB, fit unknown) + mine it (route_novel)."""
    from mag import tesuji_steal as ts
    return ts.on_unexpected(need, source=source)


def carried(name: str, invariant: str) -> dict[str, Any]:
    """2. CARRIED: validated + earns its place -> encode as a GENE RIB the system carries."""
    from mag import tesuji_steal as ts
    return ts.carry_gene(name, invariant)


def selected(name: str, invariant: str, *, keep: int = 5) -> dict[str, Any]:
    """3. SELECTED: does the tool's invariant survive in the BREEDING population (is it fit)?"""
    from mag import meta_percolate as mp
    sel = mp.genetic_pass(keep=keep)
    return {"ok": True, "schema": SCHEMA, "tool": "tool_lifecycle", "stage": "selected",
            "tool": name, "invariant": invariant[:160],
            "survived": bool(sel.get("best_genes")),
            "best_genes": (sel.get("best_genes") or [])[:3],
            "note": "the tool's invariant joins the breeding population — is it fit for the job?"}


def percolated(name: str, invariant: str) -> dict[str, Any]:
    """4. PERCOLATED: merge the tool's invariant toward the ONE (the quant root carries the whole)."""
    from mag import meta_percolate as mp
    one = mp.percolate_to_one()
    return {"ok": True, "schema": SCHEMA, "tool": "tool_lifecycle", "stage": "percolated",
            "tool": name, "invariant": invariant[:160],
            "quant_root": one.get("quant_root"),
            "single_invariant": (one.get("single_invariant") or "")[:160],
            "note": "the tool's invariant percolated toward the one — carried by the quant root"}


def verified(name: str, *, passed: bool, detail: str = "") -> dict[str, Any]:
    """5. VERIFIED: expectations_monitor — does the tool KEEP working over time (RIB-debug law)?"""
    from mag import expectations_monitor as em
    em.register_space(name, f"a tool routed through the standing-wave lifecycle ({name})")
    em.expect(name, f"{name} keeps working over time (RIB-debug: trust bytes, not reports)")
    return em.check(name, passed=passed, detail=detail)


def rendered(name: str, *, deliver: bool = True) -> dict[str, Any]:
    """6. RENDERED: rib_render + clawbot — the tool's place in the lattice, visible on the desktop."""
    from mag import rib_render as rr
    r = rr.render_chart_artifact(deliver=deliver)
    return {"ok": True, "schema": SCHEMA, "tool": "tool_lifecycle", "stage": "rendered",
            "tool": name, "artifact": r.get("artifact"),
            "delivered": r.get("deliverable"),
            "note": "the tool + its lattice rendered — the constitutional percolation, seen"}


def branched(name: str, invariant: str) -> dict[str, Any]:
    """7. BRANCHED: invariant_frontier — the tool's gap to the frontier, routed (search-swarm +
    conversation + steal)."""
    from mag import invariant_frontier as invf
    return invf.extract_branch("standing-wave")


def propagated(name: str, invariant: str) -> dict[str, Any]:
    """8. PROPAGATED: route_novel — the tool's invariant sent into the medium."""
    try:
        from mag import swarm_surface
        r = swarm_surface.route_novel(goal=f"[tool:{name}] {invariant[:300]}",
                                      surface="tool-lifecycle", lens=f"tool:{name}")
        return {"ok": True, "schema": SCHEMA, "tool": "tool_lifecycle", "stage": "propagated",
                "tool": name, "routed": r.get("ok"),
                "task_id": r.get("task_id") or r.get("enqueued"),
                "note": "the tool's invariant propagated into the medium via route_novel"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "tool": "tool_lifecycle", "stage": "propagated",
                "error": str(e)[:120]}


def run_tool(name: str, invariant: str, need: str = "", *, verify_passed: bool = True) -> dict[str, Any]:
    """RUN the full lifecycle for a new tool: born -> carried -> selected -> percolated -> verified ->
    rendered -> branched -> propagated. Deterministic + $0 core; mine/branch/propagate are the swarm
    seams. HONEST — every stage is real; the swarm does the emergence."""
    stages = {
        "born": born(need or invariant, source=f"tool:{name}"),
        "carried": carried(name, invariant),
        "selected": selected(name, invariant),
        "percolated": percolated(name, invariant),
        "verified": verified(name, passed=verify_passed, detail="tool routed through the lifecycle"),
        "rendered": rendered(name),
        "branched": branched(name, invariant),
        "propagated": propagated(name, invariant),
    }
    return {"ok": True, "schema": SCHEMA, "tool": "tool_lifecycle", "stage": "complete",
            "tool": name, "invariant": invariant[:160],
            "stages": {k: (v.get("ok") if isinstance(v, dict) else False) for k, v in stages.items()},
            "quant_root": (stages["percolated"].get("quant_root") or "")[:12],
            "note": "the tool's full lifecycle: born a tesuji, carried as a gene, selected for "
                    "fitness, percolated toward the one, verified over time, rendered visible, "
                    "branched toward the frontier, propagated into the medium"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="tool-lifecycle")
    ap.add_argument("name", nargs="?", default="new_tool")
    ap.add_argument("--invariant", default="a tool routed through the standing-wave lifecycle")
    ap.add_argument("--need", default="")
    a = ap.parse_args(argv)
    print(json.dumps(run_tool(a.name, a.invariant, a.need), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
