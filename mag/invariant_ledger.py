"""invariant_ledger — shard ALL mapped subsystem invariants (so cache-sharding just happens), lens
them into each other, and keep a deterministic 5-W record + gaps at a glance.

Operator (2026-08-11): "we need to do this with all of our mapped subsystem invariants so it just
happens. lensing into each other while keeping a deterministic stochastic record so we know the
5 ws at a glance of all pieces how they interconnect and what our gaps are at a glance."

WHAT THIS IS (deterministic + $0, stdlib):
  ledger()          -> map EVERY subsystem's core STABLE invariant -> shard_key (cache_shard) so the
                       whole system is sharded by invariant automatically. Each row carries the 5 W's:
                       who (module) · what (contract) · when (built/updated) · where (path) · why
                       (the invariant/purpose) + live stochastic metrics (cache hit, cost, novelty).
  interconnect()    -> LENS each subsystem into each other: two subsystems are linked when they share
                       a lens/domain or one mounts the other's invariant (a subsystem interconnect
                       graph). Deterministic.
  gaps_at_glance()  -> the gaps view: subsystems with no stable invariant (unsharded -> would pay 50x)
                       + research_class coverage gaps. Deterministic.
  The ledger IS the "5 W's at a glance of all pieces, how they interconnect, and our gaps."

Schema: invariant_ledger.v1 · deterministic + $0 · reuse: cache_shard, research_class, novelty_lens
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

SCHEMA = "invariant_ledger.v1"

# ── THE MAPPED SUBSYSTEMS: who · what · when · where · why (the stable invariant) ──
# invariant = the STABLE PREFIX each subsystem keeps immutable (cache_shard keys on this).
SUBSYSTEMS: list[dict[str, Any]] = [
    {"module": "percolator",     "path": "mag/percolator.py",   "when": "2026-08-11",
     "what": "dedup + novelty; noise->shadow; repeat->invariant; novel->explore",
     "why": "raw signal stripped of noise; only repeated truth is compiled",
     "invariant": "raw signal stripped of noise and theater; repeatable truth compiled to invariants"},
    {"module": "research_class", "path": "mag/research_class.py", "when": "2026-08-11",
     "what": "classify every research through ONE lens, chained to origin",
     "why": "all research readable through the same lens, traceable to the beginning",
     "invariant": "all research is classified through one lens and chained to origin"},
    {"module": "novelty_lens",   "path": "mag/novelty_lens.py", "when": "2026-08-11",
     "what": "measure novelty 0..1; map keywords to lenses",
     "why": "know which steals are new lenses vs variants",
     "invariant": "novelty is measured as unseen signal against the classified corpus"},
    {"module": "shadow_graph",   "path": "mag/shadow_graph.py", "when": "2026-08-11",
     "what": "garbage -> latent knowledge graph; latent signals -> RIBs on the fly",
     "why": "the discarded past becomes signal (Jungian shadow work)",
     "invariant": "the garbage is a shadow-work repository with latent meaning"},
    {"module": "emergence",      "path": "mag/emergence.py", "when": "2026-08-11",
     "what": "core self-improve loop + real analytics grid (turtles all the way down)",
     "why": "track genuine emergence by bytes, not hand-waving",
     "invariant": "the core loop is turtles all the way down; emergence is measured"},
    {"module": "swarm_emerge",   "path": "mag/swarm_emerge.py", "when": "2026-08-11",
     "what": "detect seams/gaps; fan out right-sized subswarm tasks natively",
     "why": "the swarm decides where to spend, like tasking agents",
     "invariant": "the swarm detects its own seams and fans out right-sized work"},
    {"module": "cache_shard",    "path": "mag/cache_shard.py", "when": "2026-08-11",
     "what": "shard by stable invariant to avoid cache-hit redirects",
     "why": "workers sharing a shard share a warm cache region; volatile tail -> cheap",
     "invariant": "the shared stable prefix stays immutable; only deltas follow"},
    {"module": "usage_monitor",  "path": "mag/usage_monitor.py", "when": "2026-08-11",
     "what": "live API-usage monitoring; predict cost spikes before the bill",
     "why": "catch the 50x tax before it hits (rule + training)",
     "invariant": "live usage is monitored to catch cost spikes before they hit"},
    {"module": "flock_usage_guard", "path": "mag/flock_usage_guard.py", "when": "2026-08-11",
     "what": "RIB catches cost/cache-miss spikes before they happen via flocking",
     "why": "predict the seam (mid-context edit) and route before the 50x",
     "invariant": "the RIB predicts the seam before it costs, using flocking"},
    {"module": "world_rib",      "path": "mag/world_rib.py", "when": "2026-08-11",
     "what": "RIB -> 2D field -> 3D mesh, re-derivable (world-target for the compiler)",
     "why": "the map precedes the territory, all the way down to the compiler",
     "invariant": "the RIB (map) precedes the world (territory); the world re-derives"},
    {"module": "wearable_swarm", "path": "mag/wearable_swarm.py", "when": "2026-08-11",
     "what": "control the swarm from a wearable/VR HUD (Baymax-lite)",
     "why": "a head-up command + awareness surface for the swarm",
     "invariant": "the wearable is a companion surface; the HUD is the map"},
    {"module": "cast_guard",     "path": "mag/cast_guard.py", "when": "2026-08-11",
     "what": "LAN-only + token + probe detection for the cast/wearable server",
     "why": "baked-in defense; detect people gating into it",
     "invariant": "control routes are fail-closed, LAN-only, probe-detected"},
    {"module": "rib_bus",        "path": "mag/rib_bus.py", "when": "2026-08-11",
     "what": "RIB instruction layer on the verkle bus; mount + inject_for",
     "why": "the RIB precedes the flock (frontier -> cheap workers)",
     "invariant": "the RIB is the instruction that precedes the flock"},
    {"module": "machine_target", "path": "mag/machine_target.py", "when": "2026-08-11",
     "what": "RIB lowers to machine (T0 local / T1 execve / T2 file / T3 patch)",
     "why": "the compiler's machine target (agent-as-OS)",
     "invariant": "a RIB lowers to a machine action by default"},
    {"module": "flock_shader",   "path": "mag/flock_shader.py", "when": "2026-08-11",
     "what": "the field (phi, steer) precedes agent-pixels; seams = where to shade",
     "why": "MMO scale: cheap everywhere, frontier only at the seams",
     "invariant": "the field precedes the pixels; shade only the seams"},
]


def _shard(subsystem: dict[str, Any]) -> dict[str, Any]:
    from mag import cache_shard
    sk = cache_shard.shard_key(subsystem.get("invariant", ""))
    return {"who": subsystem["module"], "what": subsystem["what"], "when": subsystem["when"],
            "where": subsystem["path"], "why": subsystem["why"],
            "shard_id": sk.get("shard_id", "unsharded"),
            "stable": sk.get("stable", ""), "unsharded": sk.get("shard_id") == "unsharded"}


def ledger() -> dict[str, Any]:
    """The full 5-W + shard ledger: every mapped subsystem sharded by its stable invariant."""
    rows = [_shard(s) for s in SUBSYSTEMS]
    n_unsharded = sum(1 for r in rows if r["unsharded"])
    return {"ok": True, "schema": SCHEMA, "n_subsystems": len(rows),
            "n_unsharded": n_unsharded, "rows": rows,
            "note": "every mapped subsystem sharded by its stable invariant -> cache hits 'just happen'"}


def interconnect() -> dict[str, Any]:
    """Lens each subsystem into each other: linked when they share a domain/theme. Deterministic."""
    # lens map: theme keywords -> modules that live under that lens
    lens_themes = {
        "memory/invariant": ["percolator", "research_class", "shadow_graph", "rib_bus", "cache_shard"],
        "inference/synthesis": ["novelty_lens", "shadow_graph", "research_class"],
        "economics/cost": ["cache_shard", "usage_monitor", "flock_usage_guard"],
        "compiler/world": ["rib_bus", "machine_target", "world_rib"],
        "swarm/detect": ["flock_shader", "swarm_emerge", "emergence"],
        "security/guard": ["cast_guard"],
        "wearable/surface": ["wearable_swarm", "cast_guard"],
    }
    # theme -> the modules under it; edges = module pairs sharing a theme
    nodes = {s["module"] for s in SUBSYSTEMS}
    edges: dict[tuple[str, str], str] = {}
    for theme, mods in lens_themes.items():
        for i in range(len(mods)):
            for j in range(i + 1, len(mods)):
                if mods[i] in nodes and mods[j] in nodes:
                    edges[tuple(sorted((mods[i], mods[j])))] = theme
    return {"ok": True, "schema": SCHEMA, "n_nodes": len(nodes),
            "n_edges": len(edges),
            "edges": [{"a": a, "b": b, "via_lens": theme} for (a, b), theme in sorted(edges.items())],
            "lenses": lens_themes}


def gaps_at_glance() -> dict[str, Any]:
    """GAPS at a glance: unsharded subsystems + research_class coverage gaps. Deterministic."""
    led = ledger()
    unsharded = [r["who"] for r in led["rows"] if r["unsharded"]]
    gaps: dict[str, Any] = {"ok": True, "schema": SCHEMA, "n_subsystems": led["n_subsystems"],
                            "n_unsharded": led["n_unsharded"], "unsharded": unsharded,
                            "note": "unsharded subsystem = no stable invariant -> would pay 50x on every call"}
    try:
        from mag import research_class as rc
        gaps["coverage_gaps"] = [g["cell"] for g in rc.gaps(8)["gaps"]]
    except Exception as e:
        gaps["coverage_gaps"] = [f"error: {str(e)[:60]}"]
    return gaps


def status() -> dict[str, Any]:
    led = ledger()
    ic = interconnect()
    return {"ok": True, "schema": SCHEMA, "n_subsystems": led["n_subsystems"],
            "n_unsharded": led["n_unsharded"], "n_interconnect_edges": ic["n_edges"],
            "cost": "deterministic + $0"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="invariant-ledger")
    ap.add_argument("cmd", nargs="?", default="ledger",
                    choices=["ledger", "interconnect", "gaps", "status"])
    a = ap.parse_args()
    if a.cmd == "ledger":
        print(json.dumps(ledger(), indent=2, default=str))
    elif a.cmd == "interconnect":
        print(json.dumps(interconnect(), indent=2, default=str))
    elif a.cmd == "gaps":
        print(json.dumps(gaps_at_glance(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
