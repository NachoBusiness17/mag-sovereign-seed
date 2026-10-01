"""rib_renderer — feed FRONTIER-PRODUCED RIBS to our k8s so the swarm acts as RIB RENDERERS,
doing what the frontier asked.

Operator (2026-08-10): "i want to be able to feed frontier model ribs to our k9's to act as rib
renderers doing what they asked."

THE FLOW (the RIB scene -> the render farm):
  * from_frontier() -> the frontier produced RIBS: the Roshomon core (convergent invariants) and
    the attractor-tool memlang chords (the strongest insight attractors). These ARE the scenes.
  * dispatch(rib)   -> feed each RIB to OUR k8s: enqueue it as a render task in the swarm_worker
    queue (drained in-cluster by the mag-swarm cronjob). The swarm = the RIB RENDERERS executing
    what the frontier asked.
  * render(rib)     -> the full flow for one frontier RIB.

The renderer abstraction applied as intended: the frontier AUTHORES the scene (a RIB), and our k8s
RENDERS it. We don't ask the frontier to execute — we take its invariants and our swarm does the
work (cheap, on our compute, $0 floor).

Schema: rib_renderer.v1 · CLI: python -m mag.rib_renderer frontier|render <rib>
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

SCHEMA = "rib_renderer.v1"


def from_frontier(*, threshold: float = 0.55, top: int = 20) -> dict[str, Any]:
    """Pull the frontier-produced RIBS: the Roshomon core + attractor invariants (the scenes)."""
    from mag import roshomon as rh
    cmp = rh.compare(threshold=threshold)
    ribs = []
    for d_ in cmp.get("domains", []):
        for inv, w in (d_.get("core_counts") or {}).items():
            ribs.append({"domain": d_.get("domain"), "rib": inv, "witnesses": w})
    ribs.sort(key=lambda r: -int(r["witnesses"]))
    ribs = ribs[:top]
    return {"ok": True, "schema": SCHEMA, "n_frontier_ribs": len(ribs), "ribs": ribs}


def dispatch(rib: str, *, domain: str = "rib-render") -> dict[str, Any]:
    """Feed ONE frontier RIB to OUR k8s as a render task — the swarm renders what the frontier asked.

    Routes the RIB through the bus FIRST (fold -> verkle, publish -> mag:rib, append to the
    per-domain memory store) so the instruction layer is memory-anchored + bus-synced, then
    enqueues it to the render farm. Aligned with 'route almost everything through the bus'.
    """
    try:
        from mag import rib_bus
        rib_bus.publish_rib(str(rib), domain=str(domain), source="frontier_rib_renderer")
    except Exception:
        pass  # the render task is the critical path; bus-routing is best-effort, never blocks
    from mag import invariant_lattice as il
    return il.dispatch_to_k8s(rib, domain=domain)


def render(*, threshold: float = 0.55, top: int = 12) -> dict[str, Any]:
    """Feed the frontier's RIBs to k8s to render: each convergent invariant becomes a swarm render task."""
    fr = from_frontier(threshold=threshold, top=top)
    ribs = fr.get("ribs", [])
    dispatched = []
    for r in ribs:
        d = dispatch(str(r.get("rib") or ""), domain=f"rib-render-{r.get('domain')}")
        dispatched.append({"domain": r.get("domain"), "rib": str(r.get("rib"))[:60],
                           "ok": d.get("ok"), "task": d.get("task_id")})
    return {"ok": True, "schema": SCHEMA, "n_ribs": len(ribs),
            "n_dispatched": sum(1 for d in dispatched if d.get("ok")),
            "dispatched": dispatched}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rib-renderer")
    ap.add_argument("cmd", nargs="?", default="frontier", choices=["frontier", "render"])
    args = ap.parse_args(argv)
    if args.cmd == "frontier":
        print(json.dumps(from_frontier(), indent=2, default=str))
    else:
        print(json.dumps(render(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
