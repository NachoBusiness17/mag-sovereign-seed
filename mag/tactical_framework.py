"""tactical_framework — see the ENTIRE framework as TACTICAL: every subsystem is a layer in one
coherent war-plan, not a scattered toolkit. If a piece can't be stated in tactical terms (what it
captures/defends/advances, against what, at what cost), it's impractical — retire or right-size it.

OPERATOR (2026-08-12): "our entire framework should be seen as tactical. if not impractical. self steal"

SELF-STEAL (the tactical machinery we already hold, no invention):
  * arena_strategies.get_strategy()  -> existing named strategies (the tactical playbook).
  * coordination.coordinate()        -> route/depth/seat (the logistics of the war).
  * governor G1-G3                   -> G1 = G3 irreversible = OPERATOR ONLY (the strategic gates).
  * local_playbook                   -> a chess seat: playbook + strategy + legal moves (the tactical
                                        reasoning shape).
  * vessel_swarm.fleet_tactics()     -> the navy: ships, liquid swarms, sonar (the fleet operation).
  * game_world / route_trace         -> the battlefield + the map (positioning + provenance).

THE TACTICAL VIEW (every subsystem = a layer):
  STRATEGY  (why we fight)     -> the constitution + the moonshot destination (the objective).
  OPERATIONS (how the war runs) -> the loop/cadence (republic_loop) = the campaign rhythm.
  TACTICS   (the engagements)  -> the swarm, the ships, the modules — the local fights.
  LOGISTICS (the supply)       -> the corpus, cost gates, rightsize (what feeds the fight).
  INTELLIGENCE (the map)       -> lensing/sonar/verkle (knowing the battlefield).
  COMMAND   (who decides)      -> the captain (operator, the nod) + admiral (agent).

Schema: tactical_framework.v1 · deterministic + $0 · reuse: arena_strategies, coordination, governor,
vessel_swarm, game_world
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

SCHEMA = "tactical_framework.v1"

# The tactical layers of the framework (self-stolen from what we actually run).
LAYERS = [
    {"layer": "STRATEGY", "why": "the objective — the constitution + the moonshot destination "
     "(why we fight)"},
    {"layer": "OPERATIONS", "why": "the campaign rhythm — republic_loop cadence (how the war runs)"},
    {"layer": "TACTICS", "why": "the engagements — the swarm, the ships, the modules (the local "
     "fights that advance the objective)"},
    {"layer": "LOGISTICS", "why": "the supply — the corpus, cost gates, rightsize (what feeds the "
     "fight, the $0 discipline)"},
    {"layer": "INTELLIGENCE", "why": "the map — lensing/sonar/verkle (knowing the battlefield "
     "before engaging)"},
    {"layer": "COMMAND", "why": "who decides — the captain (operator, the nod is theirs) + the "
     "admiral (the agent)"},
]


def war_map() -> dict[str, Any]:
    """THE TACTICAL VIEW OF THE WHOLE FRAMEWORK: every subsystem as a layer in one coherent war-plan.
    If a subsystem can't be stated in tactical terms, it's impractical (the operator's law)."""
    return {"ok": True, "schema": SCHEMA, "layers": LAYERS,
            "note": "the entire framework seen tactically: STRATEGY (why) -> OPERATIONS (how the war "
                    "runs) -> TACTICS (the engagements) -> LOGISTICS (supply) -> INTELLIGENCE (map) "
                    "-> COMMAND (who decides). A subsystem that can't be stated in tactical terms is "
                    "impractical."}


def strategic_objective() -> dict[str, Any]:
    """THE STRATEGIC OBJECTIVE (why we fight): the moonshot destination, grounded in the doctrine."""
    return {"ok": True, "schema": SCHEMA, "objective":
        "the mycelial republic: a billion sovereign minds sharing one content-addressed standing "
        "wave — deterministic spine + stochastic flesh, dedupe by invariant, sovereignty kept, MIT "
        "shared compute, bare-metal (survives losing all remote compute). The game = the hologram.",
        "note": "STRATEGY: why we fight. Every tactical engagement must advance this objective."}


def tactical_layer(layer: str) -> dict[str, Any]:
    """EXAMINE ONE tactical layer: what it captures/defends/advances, against what, at what cost.
    Honest — if a subsystem in this layer can't answer those, it's impractical."""
    layer = layer.upper()
    row = next((l for l in LAYERS if l["layer"] == layer), None)
    if not row:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown layer {layer}",
                "known": [l["layer"] for l in LAYERS]}
    # map each layer to the concrete subsystems it holds
    subsystems = {
        "STRATEGY": ["constitution", "moonshot destination", "invariant lattice"],
        "OPERATIONS": ["republic_loop", "governor_autorun", "ghost", "drainer"],
        "TACTICS": ["the swarm", "vessel_swarm (navy)", "abundance_rogue", "the modules"],
        "LOGISTICS": ["corpus", "cost gates", "rightsize", "billing_feed", "budget_refactor"],
        "INTELLIGENCE": ["lens_chain", "lens_shader", "sonar", "verkle chain", "route_trace"],
        "COMMAND": ["captain (operator, the nod)", "admiral (the agent)", "guard_registry", "capture_guard"],
    }
    return {"ok": True, "schema": SCHEMA, "layer": row["layer"], "why": row["why"],
            "subsystems": subsystems.get(layer, []),
            "tactical_questions": ["what does it capture/defend/advance?",
                                   "against what? at what cost?",
                                   "if it can't answer these — impractical, retire or right-size"]}


def impractical_audit() -> dict[str, Any]:
    """THE IMPRACTICALITY AUDIT: scan the framework for subsystems that can't be stated tactically.
    Self-steal the gap surfaces (self_steal + gap_frontier) to find the ones that are defined but not
    advancing an objective."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA}
    try:
        from mag import self_steal
        a = self_steal.audit()
        out["underutilized"] = [f for f in a.get("findings", [])[:15]
                                if f.get("utilization") in ("stale", "absent", "unwired")]
        out["n_underutilized"] = len(out["underutilized"])
    except Exception as e:
        out["audit_error"] = str(e)[:120]
    out["note"] = ("impracticality audit: subsystems that are defined but not advancing an objective "
                   "(stale/absent/unwired) are candidates to retire or right-size — tactical discipline")
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "war_map()->the whole framework as tactical layers; strategic_objective()-"
                        ">why we fight; tactical_layer(name)->examine one layer; impractical_audit()-"
                        ">find subsystems that aren't advancing an objective",
            "cost": "deterministic + $0 (reuses self_steal + coordination + arena_strategies)",
            "law": "the entire framework should be seen as tactical; if not, impractical"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="tactical-framework")
    ap.add_argument("cmd", nargs="?", default="war-map",
                    choices=["war-map", "objective", "layer", "audit", "status"])
    ap.add_argument("--layer", default="")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "war-map":
        out = war_map()
    elif a.cmd == "objective":
        out = strategic_objective()
    elif a.cmd == "layer":
        out = tactical_layer(a.layer)
    elif a.cmd == "audit":
        out = impractical_audit()
    else:
        out = status()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
