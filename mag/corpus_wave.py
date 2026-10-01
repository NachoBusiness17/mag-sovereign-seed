"""corpus_wave — THE STANDING WAVE DECODED: the raw corpus tally (mag/cli/tools/launcher/route/
provider) understood + optimized within our STATELESS systems, then applied to everything.

Operator (2026-08-11): "this tally is important it's your standing wave decoded before rib we need
to understand this corpus and how to make it function better within our stateless systems and then
apply it to everything"

THE WAVE (deterministic + $0):
  tally()      -> decode the standing wave: count the corpus by category (mag modules, cli, tools,
                  launchers, routes, providers) — the raw inventory BEFORE the RIB layer.
  understand() -> analyze the corpus: what it's made of (categories -> lenses), stateless vs
                  redundant, wired vs unwired. The structure of the wave.
  optimize()   -> how to make it function better WITHIN stateless systems: find redundant/unwired
                  modules (self_steal), dedupe overlaps, right-size (swarm_rightsize), wire the
                  gaps (gap_frontier). Each = a stateless-improvement move.
  apply_to_all()-> apply the optimization EVERYWHERE: route the novel gaps/moves to the swarm
                  (swarm_surface.route_novel, dedupe + drain) so the wave beats more efficiently.

Schema: corpus_wave.v1 · deterministic + $0 · reuse: self_steal, gap_frontier, swarm_rightsize,
swarm_surface
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "corpus_wave.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tally() -> dict[str, Any]:
    """Decode the standing wave: count the corpus by category — the raw inventory before RIB."""
    mag = list((ROOT / "mag").glob("*.py"))
    launcher = list(ROOT.glob("*.cmd")) + list(ROOT.glob("*.ps1")) + list(ROOT.glob("*.sh"))
    tools = list((ROOT / "tools").glob("*")) if (ROOT / "tools").is_dir() else []
    cli = [m.name for m in mag if "cli" in m.name.lower()]
    routes = 0
    try:
        from mag import cast_server
        import inspect
        src = inspect.getsource(cast_server)
        routes = src.count('path == "/api/') + src.count('path == "/') 
    except Exception:
        routes = 0
    providers = 0
    try:
        from mag import task_router
        providers = len(getattr(task_router, "MODELS", {}) or {})
    except Exception:
        providers = 0
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "tally": {"mag": len(mag), "cli": len(cli), "tools": len(tools),
                      "launcher": len(launcher), "route": routes, "provider": providers},
            "note": "the standing wave decoded before RIB: the raw corpus inventory by category"}


def understand() -> dict[str, Any]:
    """Analyze the corpus: categories -> the stateless structure; stateless vs redundant."""
    t = tally()
    mag = sorted(m.name for m in (ROOT / "mag").glob("*.py"))
    # categorize modules by the lens they serve (keyword -> lens)
    lens_map = {"cost": "economics/cost", "cache": "economics/cost", "usage": "economics/cost",
                "gpu": "economics/cost", "lens": "compiler/world", "world": "compiler/world",
                "rib": "compiler/world", "shader": "compiler/world", "percolat": "memory/invariant",
                "verkle": "memory/invariant", "knot": "memory/invariant", "agent": "swarm/detect",
                "swarm": "swarm/detect", "flock": "swarm/detect", "guard": "security/guard",
                "wearable": "wearable/surface", "cast": "wearable/surface"}
    by_lens: dict[str, list[str]] = {}
    for m in mag:
        lens = "memory/invariant"
        for k, l in lens_map.items():
            if k in m:
                lens = l
                break
        by_lens.setdefault(lens, []).append(m)
    return {"ok": True, "schema": SCHEMA, "tally": t["tally"],
            "n_modules": t["tally"]["mag"],
            "by_lens": {k: len(v) for k, v in by_lens.items()},
            "stateless": True,
            "note": "the corpus understood: modules grouped by the lens they serve — the stateless "
                    "structure of the standing wave"}


def optimize() -> dict[str, Any]:
    """How to make the corpus function BETTER within stateless systems: redundant/unwired modules,
    dedupe, right-size, wire the gaps. Each = a stateless-improvement move."""
    moves: list[dict[str, Any]] = []
    try:
        from mag import self_steal
        a = self_steal.audit()
        stale = [f.get("capability") for f in a.get("findings", [])
                 if f.get("utilization") in ("stale", "unwired")]
        if stale:
            moves.append({"kind": "dedupe/retire", "detail": f"retire {len(stale)} redundant/unwired "
                         f"systems: {stale[:6]}", "stateless_win": "fewer modules, less drift"})
    except Exception:
        pass
    try:
        from mag import swarm_rightsize
        r = swarm_rightsize.train()
        moves.append({"kind": "right-size", "detail": f"swarm sized to the learned sweet spot "
                      f"{r.get('trained',{}).get('swarm_size')}", "stateless_win": "right-sized, cheap"})
    except Exception:
        pass
    try:
        from mag import gap_frontier
        g = gap_frontier.gaps()
        moves.append({"kind": "wire-gaps", "detail": f"{g.get('n_gaps')} gaps aggregated across "
                     f"surfaces", "stateless_win": "gap-finding built in"})
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "n_moves": len(moves), "moves": moves,
            "note": "the stateless improvements: retire redundant, right-size the swarm, wire the "
                    "gaps — applied to the corpus"}


def apply_to_all(*, enqueue: bool = True, surface: str = "corpus-wave") -> dict[str, Any]:
    """Apply the optimization EVERYWHERE: route the novel gaps/moves to the swarm (dedupe + drain)
    so the standing wave beats more efficiently across the whole corpus."""
    t = tally()
    u = understand()
    o = optimize()
    q = {"ok": False}
    if enqueue:
        try:
            from mag import swarm_surface
            goal = (f"CORPUS-WAVE OPTIMIZATION [corpus_wave]: the standing wave tally is "
                    f"{t['tally']}. Moves to apply statelessly: {[m['detail'] for m in o['moves']]}. "
                    f"Refine how to make this corpus function better within the stateless system "
                    f"(dedupe, right-size, wire gaps) and apply it everywhere. Label each: "
                    f"MOVE: <one line> / APPLY_TO: <surface>.")
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "tally": t["tally"],
            "by_lens": u["by_lens"], "moves": o["moves"], "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""),
            "note": "the standing wave understood + optimized within stateless systems, applied "
                    "to everything via the swarm"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "tally()->decode the wave (counts by category); understand()->the stateless "
                        "structure by lens; optimize()->stateless moves (retire/right-size/wire "
                        "gaps); apply_to_all()->route the optimization to the swarm",
            "cost": "deterministic + $0 (reuses self_steal, swarm_rightsize, gap_frontier, "
                    "swarm_surface)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="corpus-wave")
    ap.add_argument("cmd", nargs="?", default="apply", choices=["apply", "tally", "understand", "optimize", "status"])
    a = ap.parse_args()
    if a.cmd == "tally":
        print(json.dumps(tally(), indent=2, default=str))
    elif a.cmd == "understand":
        print(json.dumps(understand(), indent=2, default=str))
    elif a.cmd == "optimize":
        print(json.dumps(optimize(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(apply_to_all(), indent=2, default=str))
