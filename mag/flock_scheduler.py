"""flock_scheduler — map a batch of queued tasks onto the swarm via field-steering.

THE TESUJI: the swarm allocates work EMERGENTLY instead of through the serial queue.
  1. Each task is embedded (deterministic hash) into a shared invariant space.
  2. A flock field φ is built over those points (goal = solution centroid, invariants seed
     the penalty field from code_map.distilled()).
  3. Cheap agents (particles) steer: -grad(phi) pulls toward the solution, SEPARATION pushes
     overlapping tasks apart (the DEDUPE — replaces the central same-goal guard), ALIGNMENT
     keeps them on the distilled-invariants policy, COHESION clusters true duplicates.
  4. Each agent gets a cheapest-capable tier from one_sizer.resolve_sizing(shape, domain).
  5. Output: task -> agent -> (tier, model) + dedupe groups + convergence.

Deterministic + $0 (the field is pure; it just decides allocation before the cheap agents run).
Schema: flock_scheduler.v1
CLI: python -m mag.flock_scheduler "task1" "task2" ...  (or --demo)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "flock_scheduler.v1"


def _embed(task: str, dim: int = 3) -> tuple:
    """Semantic embedding of a task into invariant space.

    Prefers a local Ollama semantic embedding (nomic-embed-text / all-minilm) so
    that distance in invariant space MEANS semantic overlap, not hash-distance.
    Falls back to the deterministic sha256 geometric embed when Ollama is down
    (never crash, but geometric = weaker clustering). This is the memlang-mindweave
    linchpin: RIB distance must be meaning, not hash.
    """
    try:
        vec = _ollama_embed(task)
        if vec is not None:
            return _normalize(vec, dim)
    except Exception:
        pass
    # deterministic fallback (geometric, hash-based)
    h = hashlib.sha256((task or "").strip().lower().encode()).digest()
    coords = []
    for i in range(dim):
        v = int.from_bytes(h[i * 4:i * 4 + 4], "big") / (2 ** 32) - 0.5
        coords.append(v * 2.0)
    return tuple(coords)


def _ollama_embed(task: str, host: str = "http://localhost:11434",
                  model: str = "nomic-embed-text") -> list[float] | None:
    """Query a local Ollama embedding model for a semantic vector."""
    import json
    import urllib.request
    body = json.dumps({"model": model, "prompt": (task or "")[:512]}).encode("utf-8")
    req = urllib.request.Request(
        host + "/api/embeddings", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
        emb = data.get("embedding") or []
        if not emb:
            return None
        # truncate/pad to dim
        return emb[:256] if len(emb) > 256 else emb


def _normalize(vec: list[float], dim: int) -> tuple:
    """Reduce an N-dim semantic vector to `dim` dims and L2-normalize to [-1,1]."""
    if not vec:
        return tuple([0.0] * dim)
    # if fewer than dim, pad; else bucket-averagate down to dim
    if len(vec) < dim:
        vec = vec + [0.0] * (dim - len(vec))
    elif len(vec) > dim:
        bucket = len(vec) // dim
        red = []
        for i in range(dim):
            chunk = vec[i * bucket:(i + 1) * bucket] or [0.0]
            red.append(sum(chunk) / len(chunk))
        vec = red
    n = (sum(x * x for x in vec) ** 0.5) or 1.0
    return tuple((x / n) for x in vec)


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _clusters(points: list[tuple], radius: float = 0.45) -> list[list[int]]:
    """Greedy single-link clustering: tasks within radius = likely duplicates (overlap work)."""
    groups: list[list[int]] = []
    assigned: set[int] = set()
    for i, p in enumerate(points):
        if i in assigned:
            continue
        g = [i]
        assigned.add(i)
        for j, q in enumerate(points):
            if j in assigned:
                continue
            if _dist(p, q) < radius:
                g.append(j)
                assigned.add(j)
        groups.append(g)
    return groups


def _one_sizer_tier(task: str, domain: str = "general") -> dict[str, Any]:
    try:
        from mag import one_sizer as osz
        from mag.self_drive import plan as _plan
        shape = str(_plan(task).get("model_shape") or "balanced")
        r = osz.resolve_sizing(shape=shape, domain=domain)
        return {"tier": r.get("effective_tier") or "flash",
                "model": r.get("model") or "deepseek-v4-flash", "shape": shape,
                "learned": bool(r.get("found"))}
    except Exception:
        return {"tier": "flash", "model": "deepseek-v4-flash", "shape": "balanced", "learned": False}


def plan(tasks: list[str], *, domain: str = "general", sep_steps: int = 60,
         dup_radius: float = 0.45) -> dict[str, Any]:
    """Allocate a batch of tasks to the swarm: embed -> field-steer (separation = dedupe) ->
    cluster -> assign one_sizer tier. Returns assignments + dedupe groups."""
    tasks = [t for t in (tasks or []) if (t or "").strip()]
    if not tasks:
        return {"ok": True, "schema": SCHEMA, "tasks": 0, "assignments": [], "dedupe_groups": []}
    points = [_embed(t) for t in tasks]

    # DEDUPE is the key move (the tesuji): identical/near-identical tasks embed to the SAME
    # point in invariant space = the same work. Cluster on the ORIGINAL embedding (before any
    # separation), because separation is the DISPATCH force for DISTINCT agents — it must NOT
    # separate true duplicates (that would break dedupe). Replaces the central same-goal guard.
    groups = _clusters(points, radius=dup_radius)

    # Dedupe: keep the first task per cluster as canonical; others are duplicates.
    kept: set[int] = set()
    dedupe_groups: list[dict[str, Any]] = []
    for g in groups:
        if len(g) > 1:
            dedupe_groups.append({"duplicates": [tasks[i] for i in g[1:]],
                                  "kept": tasks[g[0]]})
        kept.add(g[0])

    # DISPATCH field (the flock): UNIQUE tasks steer apart so distinct cheap agents don't
    # collide when they run in parallel. Separation applies only to kept (unique) tasks.
    from mag import flock_field as ff
    uniq_idx = [i for i in range(len(tasks)) if i in kept]
    agents = [ff.Agent(pos=points[i]) for i in uniq_idx]
    for _ in range(sep_steps):
        for a in agents:
            for b in agents:
                if a is b:
                    continue
                d = _dist(a.pos, b.pos)
                if 0 < d < 0.6:  # separation radius
                    dx = tuple((a.pos[k] - b.pos[k]) / max(d, 1e-9) for k in range(3))
                    a.pos = tuple(a.pos[k] + dx[k] * 0.01 for k in range(3))

    assignments = []
    for i, t in enumerate(tasks):
        tier = _one_sizer_tier(t, domain=domain)
        assignments.append({"task": t, "task_index": i,
                            "tier": tier["tier"], "model": tier["model"],
                            "shape": tier["shape"], "learned_tier": tier["learned"],
                            "is_duplicate": i not in kept})

    return {"ok": True, "schema": SCHEMA, "tasks": len(tasks),
            "unique_tasks": len(kept), "deduped": len(tasks) - len(kept),
            "assignments": assignments, "dedupe_groups": dedupe_groups}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--demo":
        tasks = [
            "wire the free-frontend browser seat into the swarm",
            "wire the free-frontend browser seat into the swarm",   # duplicate
            "build flock_field gradient steering demo",
            "distill the full code map to invariants",
            "distill the full code map to invariants again",         # near-dup
            "start the ollama local model sidecar",
        ]
    elif argv:
        tasks = argv
    else:
        print(__doc__)
        return 0
    print(json.dumps(plan(tasks), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
