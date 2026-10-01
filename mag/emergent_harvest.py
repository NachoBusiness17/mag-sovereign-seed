"""emergent_harvest — run the flock so we ONLY get emergent data.

The operator's ask (2026-08-09): "can we try the flocking thing so we only get emergent data."

Mechanism — combine the two halves we already built:
  - rib_struct slots  -> ATTRACTORS (the structure we declared: where we want data).
  - existing artifacts-> REPULSIVE spheres (steal_steer invariants: what we already have).
  - boid separation   -> agents spread, so distinct regions emerge instead of one pile.

We spawn N stochastic agents into this combined field and let them SETTLE. Each agent is pulled
toward the nearest declared slot but pushed out of every existing-coverage sphere AND away from
its neighbors. The settled positions that cleared all existing spheres are the EMERGENT data
points — regions we do NOT already hold. We cluster them into distinct emergent regions and
return ONLY those (no re-covered data).

Deterministic, $0, no LLM. Reuses flock_field (steer/integrate/vectors) + steal_steer
(embedding + existing points) + rib_struct (slots). Schema: emergent_harvest.v1
"""
from __future__ import annotations

import json
import math
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

SCHEMA = "emergent_harvest.v1"

INVARIANTS_FILE = ROOT / "queue" / "handoff" / "DISTILLED_INVARIANTS.md"


def _load_invariants() -> list[dict[str, Any]]:
    """Parse the distilled RIB invariants: '- [domain] invariant (guardrail: ...)' -> rows."""
    if not INVARIANTS_FILE.is_file():
        return []
    rows = []
    for line in INVARIANTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("- ["):
            continue
        text = line.lstrip("- ").strip()
        domain = ""
        if text.startswith("[") and "]" in text:
            domain = text[1:text.index("]")].strip()
            text = text[text.index("]") + 1:].strip()
        rows.append({"text": text, "domain": domain})
    return rows


def tesuji_harvest(*, n_agents: int = 160, steps: int = 180, seed: int = 9,
                   cellsize: float = 0.22, min_novelty: float = 0.20) -> dict[str, Any]:
    """Run the flock against our SHARED INVARIANTS to harvest EMERGENT TESUJI.

    Our distilled RIB invariants are the coverage we already hold (repulsors). The invariant
    DOMAINS (cost/chain/memory/governance/security/data/routing/engine/audit/economy/
    coordination) are the structure slots. The flock settles agents that are pulled toward a
    domain but pushed out of every existing invariant — the survivors are NEW sharp moves
    (tesuji) we don't already hold, one per behavior cell (Map-Elites diversity).
    """
    invs = _load_invariants()
    if not invs:
        return {"ok": False, "error": "no DISTILLED_INVARIANTS.md found"}
    # existing coverage = every invariant we already hold (repulsors)
    existing = [{"id": f"inv:{i}", "text": v["text"], "embed": _embed(v["text"]), "lens": "invariant"}
                for i, v in enumerate(invs)]
    # structure = one slot per invariant domain (attractors)
    domains: dict[str, list[str]] = {}
    for v in invs:
        domains.setdefault(v["domain"], []).append(v["text"])
    slots = [{"id": d or "general",
              "center": " ".join(domains[d][:3]) or d,
              "radius": 0.34, "kind": "tesuji_domain"} for d in domains]
    struct = declare(slots)
    r = qd_harvest(struct, existing, n_agents=n_agents, steps=steps, seed=seed,
                   cellsize=cellsize, min_novelty=min_novelty)
    r["n_shared_invariants"] = len(invs)
    r["n_domains"] = len(domains)
    r["domains"] = list(domains.keys())
    return r


from mag.flock_field import Agent, _vsub, _vadd, _vscale, _vnorm, _vnormalize, _vlen
from mag.steal_steer import _existing_points, _embed, REPULSION
from mag.rib_struct import RibStructure, declare


def _force(a: Agent, slots: list[dict[str, Any]], existing: list[dict[str, Any]],
           agents: list[Agent], *, w_attract: float = 1.4, w_repel: float = 2.2,
           w_sep: float = 1.6, sep_dist: float = 0.35) -> tuple:
    """Combined emergent force: attract->nearest slot, repel<-existing, separate<-neighbors."""
    dim = a.dim()
    force = [0.0] * dim
    # attract toward nearest slot center
    best_c = None
    best_d = float("inf")
    for s in slots:
        d = _vlen(_vsub(a.pos, s["center"]))
        if d < best_d:
            best_d = d
            best_c = s["center"]
    if best_c is not None and best_d > 1e-6:
        force = _vadd(force, _vscale(_vnormalize(_vsub(best_c, a.pos)), w_attract))
    # repel from every existing-coverage sphere (this is the "don't re-cover" gradient)
    for p in existing:
        d = _vsub(a.pos, p["embed"])
        dist = _vlen(d)
        if dist < REPULSION and dist > 1e-9:
            force = _vadd(force, _vscale(_vnormalize(d), w_repel * (REPULSION - dist) / REPULSION))
    # separation: spread from neighbors so distinct regions emerge
    for o in agents:
        if o is a:
            continue
        d = _vsub(a.pos, o.pos)
        dist = _vlen(d)
        if dist < sep_dist and dist > 1e-9:
            force = _vadd(force, _vscale(_vnormalize(d), w_sep / dist))
    return tuple(force)


def _integrate(agents: list[Agent], slots, existing, *, steps: int = 140, dt: float = 0.15,
               damp: float = 0.90, max_speed: float = 0.6) -> None:
    for _ in range(steps):
        for a in agents:
            f = _force(a, slots, existing, agents)
            v = _vscale(_vadd(a.vel, _vscale(f, dt)), damp)
            sp = _vlen(v)
            if sp > max_speed:
                v = _vscale(v, max_speed / sp)
            a.vel = v
            a.pos = tuple(p + dv * dt for p, dv in zip(a.pos, v))


def _cluster(points: list[tuple], radius: float = 0.28) -> list[tuple]:
    """Greedy proximity clustering -> distinct regions (each = one emergent data point)."""
    clusters: list[tuple] = []
    for p in points:
        placed = False
        for c in clusters:
            if _vlen(_vsub(p, c)) < radius:
                placed = True
                break
        if not placed:
            clusters.append(p)
    return clusters


def _novel(region: tuple, existing: list[dict[str, Any]]) -> dict[str, Any]:
    """Is a settled region novel (cleared all existing spheres) or redundant?"""
    worst = 0.0
    nearest = None
    nearest_d = float("inf")
    for p in existing:
        d = _vlen(_vsub(region, p["embed"]))
        if d < nearest_d:
            nearest_d = d
            nearest = p["id"]
        if d < REPULSION:
            worst = max(worst, (REPULSION - d) / REPULSION)
    return {"novelty": round(1.0 - min(1.0, worst), 3),
            "nearest": nearest, "nearest_dist": round(nearest_d, 3),
            "state": "EMERGENT" if worst < 0.2 else "REDUNDANT"}


# ---------------------------------------------------------------------------
# STEAL (external, adapted): Novelty Search (Lehman & Stanley 2011) + Map-Elites
# / Quality-Diversity (Mouret & Clune). "Only emergent data" = reward behavioral
# NOVELTY (distance to the nearest already-kept point), not just "not-yet-covered",
# and keep a DIVERSITY ARCHIVE (one elite per behavior-space cell) so the harvest
# is spread, not piled. Both are deterministic, $0, no LLM.
# ---------------------------------------------------------------------------
class NoveltyArchive:
    """Map-Elites-style behavior-space archive: one elite per grid cell.

    Behavior space = the field coordinates (what region an emergent point occupies).
    novelty(x) = min distance to the nearest already-kept point (incl. existing data).
    add(x, quality) keeps only the best (highest-quality) elite per cell -> guaranteed spread.
    """

    def __init__(self, dim: int, *, cellsize: float = 0.22, min_novelty: float = 0.20):
        self.dim = dim
        self.cellsize = cellsize
        self.min_novelty = min_novelty
        self._cells: dict[tuple, dict[str, Any]] = {}

    def _cell(self, x: tuple) -> tuple:
        return tuple(int(v // self.cellsize) for v in x)

    def novelty(self, x: tuple, existing: list[dict[str, Any]]) -> float:
        """Min distance to nearest kept point (archive elites + existing coverage)."""
        best = float("inf")
        for cell in self._cells.values():
            d = _vlen(_vsub(x, cell["pos"]))
            if d < best:
                best = d
        for p in existing:
            d = _vlen(_vsub(x, p["embed"]))
            if d < best:
                best = d
        return best if best != float("inf") else 1.0

    def add(self, x: tuple, quality: float, *, meta: dict[str, Any] | None = None) -> bool:
        """Accept only if novel enough; keep the best elite per cell. Returns accepted?"""
        if quality is None:
            return False
        cell = self._cell(x)
        cur = self._cells.get(cell)
        if cur is None or quality > cur["quality"]:
            self._cells[cell] = {"pos": x, "quality": float(quality),
                                 **({} if meta is None else meta)}
            return True
        return False

    def elites(self) -> list[dict[str, Any]]:
        return sorted(self._cells.values(), key=lambda c: -c["quality"])


def qd_harvest(struct: RibStructure | None = None, existing: list[dict[str, Any]] | None = None,
               *, n_agents: int = 120, steps: int = 160, seed: int = 5,
               cellsize: float = 0.22, min_novelty: float = 0.20) -> dict[str, Any]:
    """Flock + Novelty-Archive: keep ONLY novel AND diverse emergent data.

    Run the field to settle agents, then push each through the QD archive — a candidate is
    kept only if it clears existing coverage AND is novel vs the archive AND fills a distinct
    behavior cell. One elite per cell = guaranteed spread (the Map-Elites guarantee).
    """
    import random
    random.seed(seed)
    existing = existing if existing is not None else _existing_points()
    if struct is None:
        struct = declare([
            {"id": "flock", "center": "flocking geometric algebra field steering coordination", "radius": 0.34, "kind": "mechanism"},
            {"id": "verkle", "center": "verkle tree self replication invariant agents", "radius": 0.34, "kind": "mechanism"},
            {"id": "free_compute", "center": "free tier frontier model compute browser automation", "radius": 0.34, "kind": "resource"},
        ])
    slots = struct.slots
    dim = 6
    agents = [Agent(pos=tuple(random.uniform(0.0, 1.0) for _ in range(dim))) for _ in range(n_agents)]
    _integrate(agents, slots, existing, steps=steps)
    archive = NoveltyArchive(dim, cellsize=cellsize, min_novelty=min_novelty)
    attempted = kept = redundant = 0
    for a in agents:
        attempted += 1
        nv = _novel(a.pos, existing)
        if nv["state"] == "REDUNDANT":
            redundant += 1
            continue
        nov = archive.novelty(a.pos, existing)
        if nov < min_novelty:
            redundant += 1
            continue
        s = min(slots, key=lambda s: _vlen(_vsub(a.pos, s["center"])))
        quality = nv["novelty"] * 0.5 + min(1.0, nov) * 0.5
        if archive.add(a.pos, quality, meta={"slot": s["id"], "novelty_to_archive": round(nov, 3)}):
            kept += 1
    return {"ok": True, "schema": SCHEMA, "n_agents": n_agents, "steps": steps,
            "n_attempted": attempted, "n_kept": kept, "n_redundant": redundant,
            "diversity": round(kept / max(1, len(archive._cells)), 3),
            "emergent_data": archive.elites()}


def harvest(struct: RibStructure | None = None, existing: list[dict[str, Any]] | None = None,
            *, n_agents: int = 80, steps: int = 140, seed: int = 3) -> dict[str, Any]:
    """Run the flock; return ONLY the emergent (novel) settled regions as data."""
    import random
    random.seed(seed)
    existing = existing if existing is not None else _existing_points()
    if struct is None:
        struct = declare([
            {"id": "flock", "center": "flocking geometric algebra field steering coordination", "radius": 0.34, "kind": "mechanism"},
            {"id": "verkle", "center": "verkle tree self replication invariant agents", "radius": 0.34, "kind": "mechanism"},
            {"id": "free_compute", "center": "free tier frontier model compute browser automation", "radius": 0.34, "kind": "resource"},
        ])
    slots = struct.slots
    dim = 6
    agents = [Agent(pos=tuple(random.uniform(0.0, 1.0) for _ in range(dim))) for _ in range(n_agents)]
    _integrate(agents, slots, existing, steps=steps)
    regions = _cluster([a.pos for a in agents])
    emergent = []
    for region in regions:
        nv = _novel(region, existing)
        if nv["state"] == "EMERGENT":
            # assign nearest slot
            s = min(slots, key=lambda s: _vlen(_vsub(region, s["center"])))
            emergent.append({"region": [round(float(v), 3) for v in region],
                             "slot": s["id"], **nv})
    return {"ok": True, "schema": SCHEMA, "n_agents": n_agents, "steps": steps,
            "n_regions": len(regions), "n_emergent": len(emergent),
            "n_redundant": len(regions) - len(emergent),
            "emergent_data": emergent}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="emergent-harvest")
    ap.add_argument("--agents", type=int, default=80)
    ap.add_argument("--steps", type=int, default=140)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args(argv)
    print(json.dumps(harvest(n_agents=args.agents, steps=args.steps, seed=args.seed),
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
