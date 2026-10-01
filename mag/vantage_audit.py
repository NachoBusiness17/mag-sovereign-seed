"""vantage_audit — the HIGHER-VANTAGE audit: deep frontier research + gap analysis of where we are,
where we're going, what it takes to get there, and an audit of ALL surfaces/subsystems/tools from
that higher vantage — then ITERATE. Built on our own audit machinery (reuse, not invention).

OPERATOR (2026-08-12): "deep frontier research and gap analysis of where we are where we are going
and what it will take to get there and an audit of all surfaces subsystems and tools from that higher
vantage and then iterate."

THE STACK (self-steal our own audit surfaces, no invention):
  * gap_frontier.gaps()   -> aggregate ALL gaps across lens-coverage/zeitgeist/orphans/testing/
                             economics (the existing all-surface gap map).
  * gap_analysis.gap_analysis() -> cadence/module/enforcement gaps (defined-but-not-running).
  * self_steal.audit()    -> every internal capability's utilization (not wired / stale / absent).
  * corpus_wave.tally()   -> the standing wave decoded: how many mag modules/tools/surfaces.
  * swarm_surface.route_novel() -> route DEEP FRONTIER RESEARCH to the swarm (dedupe + drain).

THE HIGHER-VANTAGE SYNTHESIS (deterministic + $0 aggregation, swarm-routed frontier):
  surfaces()   -> audit EVERY surface/subsystem/tool: count + per-surface utilization (grounded).
  synthesis()  -> where we ARE (the standing inventory) / where we're GOING (the moonshot) /
                  WHAT IT TAKES (the gaps + the frontier research) — one higher-vantage picture.
  frontier()   -> route the deep frontier research (where we're going + what it takes) to the swarm.
  iterate()    -> the loop: audit -> synthesize -> frontier -> read back -> close the sharpest gap.

Schema: vantage_audit.v1 · deterministic + $0 aggregation · swarm-routed frontier
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

SCHEMA = "vantage_audit.v1"
SURFACE = "vantage-audit"

# The moonshot destination (grounded in what we've built) — where we're going.
DESTINATION = (
    "the mycelial republic: a billion sovereign minds sharing ONE content-addressed standing wave — "
    "deterministic spine + stochastic flesh, dedupe by invariant, sovereignty preserved, MIT shared "
    "compute, bare-metal (survives losing all remote compute). The game = the hologram."
)

# Deep frontier research threads (what it takes to get there) routed to the swarm.
FRONTIER_THREADS: list[str] = [
    "FRONTIER RESEARCH (vantage): from the higher vantage, what is the SINGLE highest-leverage "
    "mechanism we must build to reach a billion-person content-addressed standing wave (dedupe by "
    "invariant, sovereignty kept, MIT shared compute)? Name the load-bearing next stone + the "
    "riskiest assumption to test first. Be concrete and buildable.",
    "FRONTIER RESEARCH (vantage): our wave is a standing wave (spine out + flesh in superpose). What "
    "is the deepest lesson from Tesla's wave mechanics + fluid mechanics that we should encode as the "
    "next invariant — the mechanism that makes the republic's oscillation compound rather than "
    "dissipate? Deliver the invariant to add.",
    "FRONTIER RESEARCH (vantage): a billion machines each rendering a QUANTIZATION of one shared "
    "reality. What is the right right-sizing curve (fidelity vs VRAM/compute) and the hologram "
    "reconstruction contract so every machine reconstructs the whole from any fragment, cheaply? "
    "Deliver the curve + contract.",
    "FRONTIER RESEARCH (vantage): what tools (wireshark-class instrumentation, briar mesh, openclaw, "
    "distributed render farms) are the highest-leverage to actually USE next, and what is the first "
    "real integration that would prove the republic works at 10 people? Deliver the integration plan.",
]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def surfaces() -> dict[str, Any]:
    """AUDIT EVERY surface/subsystem/tool from the higher vantage: count + per-surface utilization,
    grounded from our own audit machinery (corpus_wave tally + self_steal audit + gap maps)."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA}
    # 1) the standing-wave inventory (how many mag modules/tools/surfaces)
    try:
        from mag import corpus_wave
        tally = corpus_wave.tally()
        out["inventory"] = {"n_modules": tally.get("n_modules"),
                            "n_tools": tally.get("n_tools"),
                            "n_surfaces": tally.get("n_surfaces"),
                            "categories": tally.get("categories")}
    except Exception as e:
        out["inventory_error"] = str(e)[:120]
    # 2) every internal capability's utilization (self_steal)
    try:
        from mag import self_steal
        a = self_steal.audit()
        out["capabilities"] = {"n_capabilities": a.get("n_capabilities"),
                               "n_findings": a.get("n_findings"),
                               "findings": a.get("findings", [])[:20]}
    except Exception as e:
        out["capabilities_error"] = str(e)[:120]
    # 3) the all-surface gap map (gap_frontier)
    try:
        from mag import gap_frontier
        g = gap_frontier.gaps()
        out["gaps"] = {"n_gaps": g.get("n_gaps"), "gap_map": g.get("gaps", [])[:15]}
    except Exception as e:
        out["gaps_error"] = str(e)[:120]
    # 4) cadence/module/enforcement gaps (gap_analysis)
    try:
        from mag import gap_analysis
        ga = gap_analysis.gap_analysis()
        out["analysis_gaps"] = {"n_gaps": ga.get("n_gaps"),
                                "cadence": len(ga.get("cadence_gaps", [])),
                                "modules": len(ga.get("module_gaps", [])),
                                "enforcement": len(ga.get("enforcement_gaps", []))}
    except Exception as e:
        out["analysis_error"] = str(e)[:120]
    return out


def synthesis() -> dict[str, Any]:
    """THE HIGHER-VANTAGE PICTURE: where we ARE / where we're GOING / WHAT IT TAKES — one coherent
    synthesis from the audited surfaces + the destination. Deterministic + $0."""
    s = surfaces()
    return {"ok": True, "schema": SCHEMA,
            "where_we_are": s.get("inventory", {}) ,
            "utilization": s.get("capabilities", {}),
            "gaps": s.get("gaps", {}),
            "analysis_gaps": s.get("analysis_gaps", {}),
            "where_we_are_going": DESTINATION,
            "what_it_takes": "close the gaps (frontier-routed), build the load-bearing stone "
                             "(the swarm names it), and prove it at 10 people (the first real "
                             "integration) — then scale the standing wave",
            "note": "the higher-vantage audit: every surface counted + utilization measured + gaps "
                    "aggregated, against the moonshot destination"}


def frontier(*, enqueue: bool = True, limit: int = len(FRONTIER_THREADS)) -> dict[str, Any]:
    """Route the DEEP FRONTIER RESEARCH (where we're going + what it takes) to the swarm via THE ONE
    primitive (route_novel). The swarm returns the load-bearing next stone + the first integration."""
    from mag import swarm_surface
    routed, deduped = [], 0
    for t in FRONTIER_THREADS[:limit]:
        r = swarm_surface.route_novel(t, surface=SURFACE, lens="frontier", domain="research")
        (routed if not r.get("deduped") else []).append({"task_id": r.get("task_id")})
        if r.get("deduped"):
            deduped += 1
    return {"ok": True, "schema": SCHEMA, "n_threads": len(FRONTIER_THREADS[:limit]),
            "routed_to_swarm": len(routed), "already_deduped": deduped,
            "honesty": "frontier research routed to the swarm; answers land as filed packs, never "
                       "fabricated here"}


def iterate(*, enqueue: bool = True) -> dict[str, Any]:
    """THE LOOP: audit every surface -> synthesize the higher vantage -> route deep frontier research
    -> the swarm returns what it takes to get there -> close the sharpest gap next. This is the
    iterate-on-the-audit contract."""
    s = surfaces()
    syn = synthesis()
    f = frontier(enqueue=enqueue)
    return {"ok": True, "schema": SCHEMA, "audit": s, "synthesis": syn,
            "frontier": f,
            "note": "iterate: audit -> synthesize -> frontier-research -> close the sharpest gap; "
                    "the loop runs by default (idempotent via anchor dedupe)"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "surfaces()->audit every surface/subsystem/tool (inventory + utilization + "
                        "gaps); synthesis()->where we are/go/need; frontier()->route deep research to "
                        "the swarm; iterate()->the loop",
            "cost": "deterministic + $0 aggregation (frontier research swarmed)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="vantage-audit")
    ap.add_argument("cmd", nargs="?", default="iterate",
                    choices=["surfaces", "synthesis", "frontier", "iterate", "status"])
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "surfaces":
        out = surfaces()
    elif a.cmd == "synthesis":
        out = synthesis()
    elif a.cmd == "frontier":
        out = frontier(enqueue=not a.no_enqueue)
    elif a.cmd == "status":
        out = status()
    else:
        out = iterate(enqueue=not a.no_enqueue)
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
