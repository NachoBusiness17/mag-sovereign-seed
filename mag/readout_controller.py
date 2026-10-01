"""readout_controller — the RESERVOIR READOUT CONTROL LOOP: read the liquid, curate the readout,
inject it back to STEER the liquid. The mechanism that makes the swarm (liquid) cook controllably.

Operator (2026-08-10): "build it" — the highest-leverage mechanism from the deep-research synthesis
(reservoir computing / liquid state machines). Our swarm IS the liquid (fixed, non-linear,
high-dimensional); our invariants are the readout. The missing piece is the CONTROL LOOP that
closes it: the readout doesn't just observe the liquid — it injects back as attractors to steer it.

The loop (each iteration):
  read()    -> pull the swarm's raw output (liquid state) -> extract the Roshomon core (convergent
               invariants = the readout signal).
  curate()  -> rank by witness count, fold as attractor-tools (the trained readout layer).
  inject()  -> inject the curated invariants as ACTION-ATTRACTORS into the action-RIB
               (rib_action.influence) so the liquid is STEERED toward them next round.
  control_loop() -> repeat: the reservoir self-organizes toward its own convergent readout.

This directly answers the LSM criticism ("no control over the liquid") and the frontier-help ask
("make the readout control the liquid better"): the readout BECOMES the steering field.

Deterministic, $0 (all local analysis + field dynamics). Schema: readout_controller.v1
CLI: python -m mag.readout_controller read|curate|inject|loop
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "readout_controller.v1"
OUT_DIR = ROOT / "memory" / "runs" / "readout_controller"


def read(*, threshold: float = 0.55, top: int = 20) -> dict[str, Any]:
    """READ the liquid: pull the swarm's raw results and extract the Roshomon core (the readout
    signal — the invariants that converged across the swarm's witnesses)."""
    from mag import roshomon as rh
    cmp = rh.compare(threshold=threshold)
    rows = []
    for d_ in cmp.get("domains", []):
        for inv, w in (d_.get("core_counts") or {}).items():
            rows.append({"domain": d_.get("domain"), "invariant": inv, "witnesses": w})
    rows.sort(key=lambda r: (-int(r["witnesses"]), str(r["domain"])))
    rows = rows[:top]
    return {"ok": True, "schema": SCHEMA, "n_readout": len(rows), "readout": rows}


def curate(*, threshold: float = 0.55, top: int = 20) -> dict[str, Any]:
    """CURATE the readout: fold the convergent invariants as attractor-tools (the trained readout
    layer) + memlang chords. This is where the liquid's output becomes durable, steerable doctrine."""
    from mag import attractor_tools as at
    a = at.run(threshold=threshold)
    return {"ok": True, "schema": SCHEMA, "attractors": a.get("attractors"),
            "swarm_tools": a.get("swarm_tools"), "folded": a.get("folded"),
            "batch": a.get("batch")}


def inject(*, threshold: float = 0.55, top: int = 12) -> dict[str, Any]:
    """INJECT the readout back into the liquid: turn the curated invariants into ACTION-ATTRACTORS
    in the action-RIB (rib_action.influence). The reservoir is STEERED toward its own convergent
    readout next round — the closed control loop."""
    from mag import rib_action as ra
    rd = read(threshold=threshold, top=top)
    attractors = rd.get("readout", [])
    if not attractors:
        return {"ok": False, "schema": SCHEMA, "error": "no readout to inject"}
    spec = [{"id": f"ro_{i}", "action": str(a.get("invariant") or "")[:180],
             "radius": 0.3, "weight": max(1.0, int(a.get("witnesses") or 1))}
            for i, a in enumerate(attractors)]
    rib = ra.declare(spec)
    # a short three-body pass: the liquid settles toward the injected attractors
    agents = ra.spawn_agents(rib, n=len(spec), seed=3)
    run = ra.run_three_body(rib, agents=agents, steps=40, seed=3)
    return {"ok": True, "schema": SCHEMA, "n_injected": len(spec),
            "collective": run.get("goal"),
            "actions": run.get("actions"),
            "note": "readout injected as action-attractors; the liquid settles toward them"}


def control_loop(*, iterations: int = 3, threshold: float = 0.55) -> dict[str, Any]:
    """The full control loop: read -> curate -> inject, repeated. Each iteration the liquid's own
    convergent readout is injected back, so the reservoir self-organizes toward its invariants."""
    out = {"schema": SCHEMA, "iterations": []}
    for i in range(1, iterations + 1):
        rd = read(threshold=threshold)
        cu = curate(threshold=threshold)
        ij = inject(threshold=threshold)
        out["iterations"].append({"iter": i, "readout_n": rd.get("n_readout"),
                                  "folded": cu.get("folded"), "injected_n": ij.get("n_injected"),
                                  "collective": str(ij.get("collective"))[:60]})
        print(f"[readout_controller] iter {i}: read={rd.get('n_readout')} fold={cu.get('folded')} "
              f"inject={ij.get('n_injected')}", flush=True)
    out["ok"] = True
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="readout-controller")
    ap.add_argument("cmd", nargs="?", default="loop",
                    choices=["read", "curate", "inject", "loop"])
    ap.add_argument("--threshold", type=float, default=0.55)
    args = ap.parse_args(argv)
    if args.cmd == "read":
        print(json.dumps(read(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "curate":
        print(json.dumps(curate(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "inject":
        print(json.dumps(inject(threshold=args.threshold), indent=2, default=str))
    else:
        print(json.dumps(control_loop(threshold=args.threshold), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
