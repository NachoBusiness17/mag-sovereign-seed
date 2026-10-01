"""cleanup_steal — DEEP STEAL of the cleanup vs plugins vs orphans decision: how best to balance
what we RETIRE (cleanup), what we BUILD as VS Code plugins, and what novel orphans we SHADE.

Operator (2026-08-11): "cleanup vs plugins and orphans deep steal."

GROUNDED (self-stolen from real surfaces):
  CLEANUP  — retired/redundant systems (memory/repo/retired-redundant-systems.md): mycelium,
             republic_os, comms_trail, scrum = 2026-08-09 experimental builds, RETIRED. The live
             core is the stateless ghost+queue/drainer+RIB+verkle+rightsize+orphan_sense core.
  PLUGINS  — the VS Code extension surfaces (extensions/mag-dashboard: Flock/World/Emerge views);
             what NEW plugin surfaces to build (e.g. a Loop view, a Lens view, a Billing view).
  ORPHANS  — the NOVEL ORPHANS (orphan_sense) the swarm should shade next.

THE FLOW (deterministic map + swarm-routed deep analysis; $0 for the map):
  map()   -> the deterministic 3-surface map (cleanup candidates / plugin surfaces / orphan count).
  steal() -> route ONE deep steal goal to the SWARM (swarm_surface.route_novel) so a frontier
             model produces the cleanup-vs-plugins-vs-orphans strategy in-cluster (dogfooding).

Schema: cleanup_steal.v1 · deterministic + $0 map · swarm-routed deep analysis
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "cleanup_steal.v1"

# The retired/redundant systems (the CLEANUP surface), from the operator's correction.
RETIRED = ["mag/mycelium.py", "mag/republic_os.py", "mag/comms_trail.py", "mag/scrum.py"]
# The VS Code plugin surfaces we have + candidates to build (the PLUGINS surface).
PLUGIN_VIEWS = ["magFlock (flock)", "magWorld (world_rib)", "magEmerge (loop/lens/billing)"]
PLUGIN_CANDIDATES = ["loop-heartbeat view", "lens-map view", "billing/cost view",
                     "chain-substrate view", "novel-orphans view"]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def map_() -> dict[str, Any]:
    """The deterministic 3-surface map: cleanup candidates / plugin surfaces / orphan count."""
    cleanup = []
    for r in RETIRED:
        cleanup.append({"module": r, "retired": True,
                        "exists": (ROOT / r).is_file()})
    # orphan count from the live surface (orphan_sense)
    orphans = {"n": 0, "surfaces": []}
    try:
        from mag import orphan_sense
        o = orphan_sense.novel_orphans(enqueue=False)
        orphans = {"n": o.get("n_novel_orphans", 0),
                   "surfaces": list(o.get("by_surface", {}).keys())}
    except Exception as e:
        orphans = {"n": 0, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "cleanup": cleanup, "n_cleanup": len(cleanup),
            "plugins": {"existing": PLUGIN_VIEWS, "candidates": PLUGIN_CANDIDATES,
                        "n_existing": len(PLUGIN_VIEWS)},
            "orphans": orphans,
            "note": "the 3-surface map: what to cleanup (retired), what to build as plugins, how "
                    "many novel orphans to shade"}


def steal(*, enqueue: bool = True, surface: str = "cleanup-steal") -> dict[str, Any]:
    """Route the DEEP STEAL to the swarm: cleanup vs plugins vs orphans strategy."""
    m = map_()
    goal = (f"DEEP STEAL [cleanup vs plugins vs orphans]: we are balancing three surfaces. "
            f"CLEANUP (retired/redundant, to retire): {', '.join(RETIRED)}. "
            f"PLUGINS (VS Code extension views): existing {', '.join(PLUGIN_VIEWS)}; candidates "
            f"{', '.join(PLUGIN_CANDIDATES)}. "
            f"ORPHANS (novel orphans to shade): {m['orphans']['n']} across "
            f"{', '.join(m['orphans'].get('surfaces',[]))}. "
            f"Produce the sharpest strategy: (1) what to CLEANUP/retire first (highest debt, "
            f"lowest live value), (2) which PLUGIN to build next that surfaces the most live "
            f"signal (loop/lens/billing/chain/orphans), (3) which orphans to shade first. "
            f"Label each: CLEANUP: <module> / PLUGIN: <view> / ORPHAN: <surface>.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="compiler/world",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "step": "steal", "goal": goal[:300],
            "enqueued": q.get("ok", False), "task_id": q.get("task_id", ""),
            "deduped": q.get("deduped", False),
            "note": "deep cleanup-vs-plugins-vs-orphans steal routed to the swarm research queue"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "map_()->the 3-surface decision map (cleanup/plugins/orphans); "
                        "steal()->route the deep steal to the swarm",
            "cost": "deterministic + $0 map (deep analysis swarmed)",
            "n_retired": len(RETIRED), "n_plugin_candidates": len(PLUGIN_CANDIDATES)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="cleanup-steal")
    ap.add_argument("cmd", nargs="?", default="steal", choices=["steal", "map", "status"])
    a = ap.parse_args()
    if a.cmd == "map":
        print(json.dumps(map_(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(steal(), indent=2, default=str))
