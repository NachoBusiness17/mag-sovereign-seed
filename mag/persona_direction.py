"""persona_direction — deep self-steal of the north-star (the intent-gated persistent world /
persona-recall dream), lensed via the swarm, generating potential DIRECTIONS from different map
combinations, each measured against the ZEITGEIST'S COLDEST VECTOR.

Operator (2026-08-11): "how does this map to our subsystems in a self steal deeply lensed via our
swarm using different maps and combinations to create potential directions and have them measured
against the zeitgeist's coldest vector."

THE METHOD (deterministic + $0, reuses real primitives):
  1. SELF-STEAL the north-star through our OWN subsystems: for each swarm lens (lens_shader) x each
     relevant subsystem (self_steal capabilities + new modules), fold the north-star seed
     (persona-recall / intent-gated world) into a concrete DIRECTION candidate.
  2. LENS via DIFFERENT MAPS + COMBINATIONS: each candidate gets a jones_lens VECTOR (its
     coordinate in the multi-level map) + a Jones topology fingerprint, so different map
     combinations become distinct, measurable directions.
  3. MEASURE against the ZEITGEIST'S COLDEST VECTOR: score each candidate by its affinity to the
     coldest idea-graph vertices (ghost_summon.coldest_vertices = least-attended, oldest, fewest
     connections). A candidate that points INTO cold territory (high cosine affinity to a cold
     vertex) is the underexplored direction worth pursuing — that's the emergence.

Schema: persona_direction.v1 · deterministic + $0 · reuse: lens_shader, self_steal, jones_lens,
ghost_summon
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

SCHEMA = "persona_direction.v1"
NORTHSTAR = ("intent-gated persistent world: deterministic world-as-program; render only what you "
             "steer toward; persistent fidelity on revisit; agents with memory who recount what "
             "happened while you were gone (persona-recall)")

# ── The map COMBINATIONS: north-star x lens x subsystem ─────────────────────────
# Each lens (from lens_shader) x a subsystem it could realize the north-star through = a DIRECTION.
COMBOS: list[dict[str, Any]] = [
    {"lens": "memory/invariant", "subsystem": "percolator", "direction":
     "compile the operator's persona-recall memories into invariants (deterministic, dedup by hash)"},
    {"lens": "memory/invariant", "subsystem": "research_class", "direction":
     "classify each north-star capability into the origin-chained registry with vertical pointers"},
    {"lens": "memory/invariant", "subsystem": "shadow_graph", "direction":
     "mine the latent knowledge graph for underexplored world-regions (the wallpaper) to reveal"},
    {"lens": "economics/cost", "subsystem": "cache_shard", "direction":
     "shard the persistent world's invariants so revisit is a warm cache hit, not a rebuild"},
    {"lens": "economics/cost", "subsystem": "usage_monitor", "direction":
     "watch live usage so the world only shades expensive seams when budget allows"},
    {"lens": "compiler/world", "subsystem": "world_rib", "direction":
     "compile the world-as-program: gray field -> rendered building appears where you steer"},
    {"lens": "compiler/world", "subsystem": "jones_lens", "direction":
     "give each world-region a topology fingerprint so revisits map to the same lens"},
    {"lens": "compiler/world", "subsystem": "rib_bus", "direction":
     "the shared field (texture) every agent-pixel reads = the rib bus the world renders from"},
    {"lens": "swarm/detect", "subsystem": "flock_shader", "direction":
     "agents as pixels; the world renders cheap everywhere, shades the seams (intent = iMouse)"},
    {"lens": "swarm/detect", "subsystem": "swarm_emerge", "direction":
     "native swarm surfacing: detect which world-region/persona is hot and fan out to it"},
    {"lens": "swarm/detect", "subsystem": "emergence", "direction":
     "measure BEFORE/AFTER deltas as the world reveals more area each pass"},
    {"lens": "steal-lens", "subsystem": "steal_lens", "direction":
     "every external steal auto-lenses into a world-region (novelty=color, lens=shader, shard=bank)"},
    {"lens": "steal-lens", "subsystem": "novelty_lens", "direction":
     "score how novel each revealed region is vs the persistent corpus"},
    {"lens": "security/guard", "subsystem": "cast_guard", "direction":
     "LAN-only world entry: detect people gating into the persistent environment as a baked-in defense"},
    {"lens": "wearable/surface", "subsystem": "wearable_swarm", "direction":
     "the wearable HUD = walking the world: intent steers which building renders"},
    {"lens": "compiler/world", "subsystem": "persona_recall", "direction":
     "THE GAP: agents with memory who recount what happened in their world-region while you were gone"},
]


def _hash01(s: str) -> float:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16) % 10_000 / 10_000.0


def _coldest() -> list[dict[str, Any]]:
    """The zeitgeist's coldest vector = ghost_summon.coldest_vertices() (real primitive)."""
    try:
        from mag import ghost_summon
        return ghost_summon.coldest_vertices(limit=8) or []
    except Exception:
        return []


def _vec(text: str) -> list[float]:
    """Deterministic vector coordinate via jones_lens.vector (the multi-level map position)."""
    try:
        from mag import jones_lens
        return jones_lens.vector(text)["vector"]
    except Exception:
        return []


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(x * x for x in b) ** 0.5 or 1.0
    return dot / (na * nb)


def _cold_affinity(cand_vec: list[float], cold: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure the candidate vector against the zeitgeist's coldest vectors: the max cosine
    affinity to any cold vertex = how deep into underexplored territory this direction points."""
    best = {"title": "", "affinity": 0.0}
    for cv in cold:
        aff = _cos(cand_vec, _vec((cv.get("title") or "") + " " + (cv.get("body") or "")))
        if aff > best["affinity"]:
            best = {"title": cv.get("title", ""), "id": cv.get("id"),
                    "degree": cv.get("degree"), "affinity": round(aff, 4)}
    # cold score: affinity to cold territory = emergence potential; coldest vertex = neglected
    score = round(best["affinity"] * 100, 1)
    return {**best, "cold_score": score}


def self_steal_map() -> dict[str, Any]:
    """Lens the north-star through every subsystem x lens combination -> direction candidates."""
    cold = _coldest()
    candidates = []
    for c in COMBOS:
        text = NORTHSTAR + " " + c["lens"] + " " + c["subsystem"] + " " + c["direction"]
        vec = _vec(text)
        aff = _cold_affinity(vec, cold)
        try:
            from mag import jones_lens
            j = jones_lens.jones(text)
            fp = j["jones_fingerprint"]
        except Exception:
            fp = ""
        candidates.append({**c, "vector": vec[:8], "jones": fp, **aff})
    candidates.sort(key=lambda x: -x["cold_score"])
    return {"ok": True, "schema": SCHEMA, "n_candidates": len(candidates),
            "n_cold_vertices": len(cold), "coldest_vertices": cold[:5],
            "candidates": candidates}


def measure() -> dict[str, Any]:
    """Ranked directions measured against the zeitgeist's coldest vector. The cold-score tells us
    which potential directions fill underexplored territory (the highest-leverage emergence)."""
    m = self_steal_map()
    ranked = m["candidates"]
    return {"ok": True, "schema": SCHEMA,
            "northstar": NORTHSTAR[:80] + "...",
            "top_direction": ranked[0] if ranked else None,
            "ranked": ranked,
            "interpretation": ("directions with HIGH cold_score point INTO neglected (coldest) "
                               "territory = underexplored = best emergence candidates; LOW = already "
                               "well-explored (warm core)"),
            "note": "map precedes territory: each candidate is a vector; coldest vector = the "
                    "neglected region it should fill"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "self_steal_map()->lens north-star x subsystem x lens; "
                        "measure()->ranked directions scored vs ghost_summon coldest_vertices",
            "cost": "deterministic + $0 (reuses lens_shader, self_steal, jones_lens, ghost_summon)",
            "n_combinations": len(COMBOS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="persona-direction")
    ap.add_argument("cmd", nargs="?", default="measure",
                    choices=["measure", "map", "status"])
    a = ap.parse_args()
    if a.cmd == "map":
        print(json.dumps(self_steal_map(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(measure(), indent=2, default=str))
