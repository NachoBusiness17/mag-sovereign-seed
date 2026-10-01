"""rib_struct — specify the data we want by STRUCTURES inside stochastic spaces.

The operator's idea (2026-08-09): "when we structure our rib we can specify the data we want
by the structures we create inside of stochastic spaces."

That's the inverse of content-matching. Instead of "give me data about X" (semantic query), we
DECLARE a structure — a constellation of slots in latent/embedding space — and let the
STOCHASTIC generators (frontier calls, swarm agents) fill it. Steering is the constraint
satisfier:

  - SLOT attractors  : where we WANT data (the structure we declare). Candidates get pulled in.
  - EXISTING repellors: data we already have (steal_steer invariants). Candidates get pushed out,
                        so the fill is NOVEL, not re-coverage.

So a RIB structure = {slot_id -> center_text (+ radius, kind)}. We embed each center into field
coordinates; candidates from stochastic spaces are assigned to the nearest slot and gated by
novelty (must clear existing coverage). The result: we get the data we want BY the shape we
built, not by matching text.

Deterministic, $0, no LLM. Reuses flock_field (steering) + steal_steer (embedding + novelty).
Schema: rib_struct.v1
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

SCHEMA = "rib_struct.v1"

from mag.flock_field import PhiField, define_distance_field, Agent, step, _vlen, _vsub
from mag.steal_steer import _embed, _existing_points, _field, REPULSION


class RibStructure:
    """A declared constellation of slots in stochastic space.

    spec = [{"id": "slot_a", "center": "what we want here", "radius": 0.3, "kind": "concept"}, ...]
    """

    def __init__(self, spec: list[dict[str, Any]]):
        self.spec = spec
        self.slots = []
        for s in spec:
            center = _embed(str(s.get("center") or s.get("id") or "slot"))
            self.slots.append({
                "id": str(s.get("id") or "slot"),
                "center_text": str(s.get("center") or ""),
                "center": center,
                "radius": float(s.get("radius") or 0.3),
                "kind": str(s.get("kind") or "concept"),
            })

    def __len__(self) -> int:
        return len(self.slots)


def declare(spec: list[dict[str, Any]]) -> RibStructure:
    return RibStructure(spec)


def _slot_field(slot: dict[str, Any], existing: list[dict[str, Any]]) -> PhiField:
    """Field for one slot: goal=slot center (attractor), existing data = repellors."""
    return _field(slot["center"], existing, radius=REPULSION)


def room(slot: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    """How much unfilled (novel) room is left in a slot vs existing coverage?

    1.0 = empty slot, nothing nearby; 0.0 = saturated (everything we'd get here we already have).
    """
    e = slot["center"]
    worst = 0.0
    nearest = None
    nearest_d = float("inf")
    for p in existing:
        d = _vlen(_vsub(e, p["embed"]))
        if d < nearest_d:
            nearest_d = d
            nearest = p["id"]
        if d < slot["radius"]:
            worst = max(worst, (slot["radius"] - d) / slot["radius"])
    return {"slot": slot["id"], "room": round(1.0 - min(1.0, worst), 3),
            "nearest": nearest, "nearest_dist": round(nearest_d, 3),
            "state": "EMPTY" if worst < 0.2 else ("PARTIAL" if worst < 0.6 else "SATURATED")}


def steer_slot(slot: dict[str, Any], existing: list[dict[str, Any]], *, steps: int = 40) -> dict[str, Any]:
    """Steer a slot's target AWAY from existing data so the fill is novel.

    Agent starts at the slot center; repulsion pushes it to the nearest NOVEL point that still
    belongs to the slot (within its radius). Returns the steered target + displacement.
    """
    field = _slot_field(slot, existing)
    agent = Agent(pos=slot["center"])
    for _ in range(steps):
        step([agent], field, dt=0.15, damp=0.90, max_speed=0.5)
    moved = _vlen(_vsub(agent.pos, slot["center"]))
    return {"slot": slot["id"], "center": list(slot["center"]),
            "steered": list(round(float(v), 3) for v in agent.pos),
            "moved": round(moved, 3), "room": room(slot, existing)["room"]}


def assign(candidate_text: str, struct: RibStructure, existing: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign a stochastic candidate to the slot it best fills, gated by novelty.

    Finds the slot whose center is nearest the candidate; reports whether the candidate is
    NOVEL (clears existing coverage) or REDUNDANT (overlaps what we have). This is how the
    structure "selects" data: candidates that don't fill an empty slot are rejected.
    """
    from mag.steal_steer import novelty
    e = _embed(candidate_text)
    best = None
    best_d = float("inf")
    for slot in struct.slots:
        d = _vlen(_vsub(e, slot["center"]))
        if d < best_d:
            best_d = d
            best = slot
    nov = novelty(candidate_text, existing)
    return {"candidate": candidate_text[:60], "assigned_slot": best["id"] if best else None,
            "slot_dist": round(best_d, 3), "novelty": nov["novelty"],
            "judgement": nov["judgement"],
            "accept": bool(best and nov["novelty"] >= 0.5)}


def fill(struct: RibStructure, candidates: list[str], existing: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a batch of stochastic candidates through the structure; accept only novel fills."""
    per_slot: dict[str, list[dict[str, Any]]] = {s["id"]: [] for s in struct.slots}
    accepted, rejected = [], []
    for c in candidates:
        a = assign(c, struct, existing)
        (accepted if a["accept"] else rejected).append(a)
        if a["assigned_slot"] in per_slot:
            per_slot[a["assigned_slot"]].append(a)
    return {"ok": True, "schema": SCHEMA, "n_candidates": len(candidates),
            "n_accepted": len(accepted), "n_rejected": len(rejected),
            "accepted": accepted, "rejected": rejected,
            "per_slot": per_slot}


def survey(struct: RibStructure, existing: list[dict[str, Any]]) -> dict[str, Any]:
    """Report the health of the whole declared structure vs existing coverage."""
    rows = [room(s, existing) for s in struct.slots]
    return {"ok": True, "schema": SCHEMA, "n_slots": len(rows),
            "slots": rows, "empty": sum(1 for r in rows if r["state"] == "EMPTY"),
            "saturated": sum(1 for r in rows if r["state"] == "SATURATED")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rib-struct")
    ap.add_argument("cmd", nargs="?", default="survey", choices=["survey"])
    args = ap.parse_args(argv)
    # demo structure if run bare
    struct = declare([
        {"id": "flock", "center": "flocking geometric algebra field steering coordination", "radius": 0.34, "kind": "mechanism"},
        {"id": "verkle", "center": "verkle tree self replication invariant agents", "radius": 0.34, "kind": "mechanism"},
        {"id": "free_compute", "center": "free tier frontier model compute browser automation", "radius": 0.34, "kind": "resource"},
    ])
    print(json.dumps(survey(struct, _existing_points()), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
