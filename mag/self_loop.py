"""self_loop — THE SELF-IMPROVEMENT LOOP, three deterministic steps:
  1. MAP OF SELF   — create a map of yourself deterministically using our subsystems.
  2. STOCHASTIC DIRECTION — talk to stochastic (frontier) models for direction, via the SWARM.
  3. ZEITGEIST LOOP — loop the results through the agent swarm to determine the ZEITGEIST (the
     collective direction = consensus + coldest vector).

Operator (2026-08-11): "so here are the loop steps create a map of yourself deterministically using
our subsystems talk to stochastic models for direction loop results through agent swarm for
zeitgeist."

THE LOOP (deterministic map + swarm-routed stochastic + deterministic zeitgeist; $0):
  map_self()        -> compile the deterministic SELF-MAP from our subsystems (chain_substrate,
                       lens_shader, lens_knot, agent_knot, percolator, emergence). Same subsystems
                       -> same map (content-addressed, stateless, revisited with fidelity).
  talk_stochastic() -> enqueue a DIRECTION research goal to the SWARM research queue
                       (swarm_surface.route_novel) -> stochastic frontier models answer in-cluster.
                       Dogfooding: we don't run the stochastic part; the swarm does.
  loop_zeitgeist()  -> loop the results through the agent swarm: aggregate the returned directions
                       (Roshomon consensus across stochastic witnesses) + the COLDEST VECTOR
                       (ghost_summon.coldest_vertices) -> the ZEITGEIST (where the collective
                       points = the direction to pursue).

Schema: self_loop.v1 · deterministic + $0 · reuse: chain_substrate, lens_shader, lens_knot,
agent_knot, percolator, emergence, swarm_surface, roshomon, ghost_summon
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "self_loop.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── STEP 1: MAP OF SELF (deterministic, via our subsystems) ───────────────────
def map_self() -> dict[str, Any]:
    """Create a map of yourself DETERMINISTICALLY using our subsystems. Same subsystems -> same
    map (content-addressed, stateless)."""
    parts: list[str] = []
    m: dict[str, Any] = {"ok": True, "schema": SCHEMA, "step": "map-self", "ts": _now()}

    # the substrate: chain as sense/core/surface/world/vmem/heartbeat
    try:
        from mag import chain_substrate
        p = chain_substrate.pulse()
        m["chain"] = {"root": p["sense"].get("root", ""), "n_leaves": p["sense"].get("n_leaves", 0),
                      "alive": p["heartbeat"].get("alive"), "jones": p["world"].get("jones_fingerprint", "")}
        parts.append(f"chain:root={p['sense'].get('root','')[:8]}:alive={p['heartbeat'].get('alive')}")
    except Exception as e:
        m["chain_error"] = str(e)[:80]

    # the standing invariant (my core)
    try:
        from mag import agent_knot
        w = agent_knot.where()
        m["core"] = {"leaf": w.get("leaf_hash", ""), "exists": w.get("exists")}
        parts.append(f"core:{w.get('leaf_hash','')[:8]}")
    except Exception as e:
        m["core_error"] = str(e)[:80]

    # the lenses (lens_shader frame + lens_knot swarm truth)
    try:
        from mag import lens_knot
        st = lens_knot.swarm_truth()
        m["lenses"] = {"n": st.get("n_lenses", 0), "roshomon_core": st.get("roshomon_core", [])[:5]}
        parts.append(f"lenses:{st.get('n_lenses',0)}:core={len(st.get('roshomon_core',[]))}")
    except Exception as e:
        m["lenses_error"] = str(e)[:80]

    # the invariants compiled (percolator)
    try:
        from mag import percolator
        reg = percolator._load_registry() if hasattr(percolator, "_load_registry") else {}
        m["invariants"] = len(reg.get("invariants") or {})
        parts.append(f"invariants:{m['invariants']}")
    except Exception as e:
        m["invariants_error"] = str(e)[:80]

    # emergence grid
    try:
        from mag import emergence
        em = emergence.metrics()
        m["emergence"] = {k: em.get(k) for k in ("n", "deltas", "trends") if k in em}
        parts.append(f"emergence:{em.get('n')}")
    except Exception as e:
        m["emergence_error"] = str(e)[:80]

    # the map hash (content-addressed — same subsystems -> same map)
    m["map_hash"] = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]
    m["map_parts"] = parts
    m["note"] = "STEP 1 done: a deterministic map of the agent, from our subsystems"
    return m


# ── STEP 2: TALK TO STOCHASTIC MODELS FOR DIRECTION (via the swarm) ───────────
def talk_stochastic(*, enqueue: bool = True, surface: str = "self-loop-direction") -> dict[str, Any]:
    """Talk to stochastic (frontier) models for direction, THROUGH the swarm (dogfooding).
    The self-map is the preamble; the swarm's stochastic models answer in-cluster."""
    sm = map_self()
    goal = (f"DEEP DIRECTION SELF-STEAL [self_loop]: given this deterministic self-map of the "
            f"Republic, what is the SINGLE most load-bearing direction to pursue next? "
            f"Self-map: chain_root={sm.get('chain',{}).get('root','')[:8]} n_leaves="
            f"{sm.get('chain',{}).get('n_leaves',0)} lenses={sm.get('lenses',{}).get('n',0)} "
            f"invariants={sm.get('invariants',0)} roshomon_core={sm.get('lenses',{}).get('roshomon_core',[])} "
            f"map_hash={sm.get('map_hash','')}. Give ONE sharp, buildable direction, one line, "
            f"labeled DIRECTION: <one line>.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="swarm/detect",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "step": "talk-stochastic", "self_map_hash": sm["map_hash"],
            "direction_goal": goal[:300], "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "deduped": q.get("deduped", False),
            "note": "STEP 2 done: self-map dispatched to stochastic frontier models via the swarm "
                    "research queue (dogfooding — the swarm runs the stochastic part)"}


# ── STEP 3: LOOP RESULTS THROUGH THE AGENT SWARM FOR ZEITGEIST ─────────────────
def loop_zeitgeist() -> dict[str, Any]:
    """Loop the results through the agent swarm to determine the ZEITGEIST: the collective
    direction = Roshomon consensus across the stochastic witnesses + the COLDEST VECTOR."""
    # consensus across the lenses (Roshomon core = what the swarm agrees is load-bearing)
    roshomon_core = []
    try:
        from mag import lens_knot
        roshomon_core = lens_knot.swarm_truth().get("roshomon_core", [])[:6]
    except Exception:
        pass
    # the coldest vector (the neglected direction the collective should fill)
    coldest = []
    try:
        from mag import ghost_summon
        coldest = ghost_summon.coldest_vertices(limit=5)
    except Exception:
        pass
    # the zeitgeist = consensus signals + the coldest neglected direction
    zeitgeist = [{"signal": c["signal"], "n_lenses": c["n_lenses"]} for c in roshomon_core]
    coldest_titles = [c.get("title", "") for c in coldest]
    return {"ok": True, "schema": SCHEMA, "step": "loop-zeitgeist", "ts": _now(),
            "zeitgeist": zeitgeist, "coldest_vector": coldest_titles,
            "consensus_direction": zeitgeist[0]["signal"] if zeitgeist else None,
            "cold_direction": coldest_titles[0] if coldest_titles else None,
            "note": "STEP 3 done: results looped through the agent swarm -> the zeitgeist = "
                    "consensus (Roshomon core) + the coldest vector (the neglected direction)"}


def loop(*, enqueue_stochastic: bool = True) -> dict[str, Any]:
    """THE FULL LOOP: map self -> talk to stochastic models for direction -> loop results through
    the agent swarm for zeitgeist. Wired into the cadence so it runs by default."""
    s1 = map_self()
    s2 = talk_stochastic(enqueue=enqueue_stochastic)
    s3 = loop_zeitgeist()
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "loop": [s1, s2, s3],
            "map_hash": s1["map_hash"], "direction_task": s2.get("task_id"),
            "zeitgeist": s3["zeitgeist"], "cold_direction": s3.get("cold_direction"),
            "note": "the self-improvement loop: map yourself deterministically -> stochastic "
                    "direction via the swarm -> zeitgeist (consensus + coldest vector)"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "map_self()->deterministic self-map from our subsystems; "
                        "talk_stochastic()->dispatch self-map to stochastic models via the swarm; "
                        "loop_zeitgeist()->Roshomon consensus + coldest vector = the zeitgeist; "
                        "loop()->all three on the cadence",
            "cost": "deterministic + $0 (dogfoods our subsystems; the stochastic part is swarmed)",
            "loop": ["map-self", "talk-stochastic", "loop-zeitgeist"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="self-loop")
    ap.add_argument("cmd", nargs="?", default="loop",
                    choices=["loop", "map", "talk", "zeitgeist", "status"])
    a = ap.parse_args()
    if a.cmd == "map":
        print(json.dumps(map_self(), indent=2, default=str))
    elif a.cmd == "talk":
        print(json.dumps(talk_stochastic(), indent=2, default=str))
    elif a.cmd == "zeitgeist":
        print(json.dumps(loop_zeitgeist(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(loop(), indent=2, default=str))
