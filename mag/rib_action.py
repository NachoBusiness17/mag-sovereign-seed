"""rib_action — RIB structures for ACTIONS, not static concepts: the three-body invariant bus.

Operator (2026-08-10): "shouldn't you be constructing ribs for actions within ai as a way to
communicate the invariants more easily to evoke complex 3 body behavior between them we can
influence?"

This is the upgrade to rib_struct: instead of declaring RIB slots as static CONCEPT centers
(data we want to collect), we declare slots as ACTION INVARIANTS — the verb+object+constraint
rules the agents themselves act on (e.g. "route through the architecture queue, never terminal").
The slots are the shared vocabulary. Multiple agents (3+ = "three-body") live in this action-space
and evolve under flock dynamics: each body's ACTION is the resultant of
  * its OWN action-invariant (attractor it holds),
  * COHESION toward agents whose action-invariants ALIGN (they reinforce each other),
  * SEPARATION from agents whose action-invariants CONFLICT (they push apart),
so coordination/conflict EMERGES between them — complex three-body behavior.

WE INFLUENCE the system by tuning the action-invariant field: `influence()` adds/boosts an
action-invariant attractor (or adds a repellor) so the swarm's collective action steers toward a
desired invariant. `emit_actions()` decodes each body's converged position back to the nearest
action invariant = the ACTION MESSAGE it communicates to the others.

Deterministic, $0, no LLM. Reuses flock_field (Agent/step, three-body forces) + steal_steer
(_embed). Schema: rib_action.v1
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "rib_action.v1"

from mag.flock_field import Agent, step, _vlen, _vsub, _vadd, _vscale, _vnormalize  # noqa: E402
from mag.steal_steer import _embed, _existing_points, _field  # noqa: E402


class ActionRib:
    """A declared constellation of ACTION-INVARIANT slots in action-space.

    spec = [{"id": "a1", "action": "route through the architecture queue, never terminal",
             "radius": 0.3}, ...]. Each slot's center is the embedding of its action invariant.
    """

    def __init__(self, spec: list[dict[str, Any]]):
        self.spec = spec
        self.slots = []
        for s in spec:
            act = str(s.get("action") or s.get("id") or "act")
            self.slots.append({
                "id": str(s.get("id") or "act"),
                "action": act,
                "center": _embed(act),
                "radius": float(s.get("radius") or 0.3),
                "weight": float(s.get("weight") or 1.0),
            })

    def __len__(self) -> int:
        return len(self.slots)


def declare(spec: list[dict[str, Any]]) -> ActionRib:
    return ActionRib(spec)


def spawn_agents(rib: ActionRib, *, n: int | None = None, seed: int = 3) -> list[Agent]:
    """Spawn N bodies in action-space, each anchored to a declared action-invariant.

    n defaults to one per slot. Each agent starts AT its slot's center (it "holds" that
    action invariant); the flock dynamics then let alignment/conflict move them.
    """
    random.seed(seed)
    if n is None or n <= 0:
        n = len(rib.slots)
    agents = []
    for i in range(n):
        slot = rib.slots[i % len(rib.slots)]
        # start at the slot center with a small jitter so dynamics actually evolve
        pos = tuple(c + random.uniform(-0.05, 0.05) for c in slot["center"])
        agents.append(Agent(pos=pos, vel=(0.0, 0.0, 0.0)))
    return agents


def _collective_center(rib: ActionRib) -> tuple:
    """The weighted mean of all action-invariant attractors = the swarm's collective intent."""
    dim = len(rib.slots[0]["center"]) if rib.slots else 3
    acc = [0.0] * dim
    wsum = 0.0
    for s in rib.slots:
        w = max(0.0, s["weight"])
        for d in range(dim):
            acc[d] += s["center"][d] * w
        wsum += w
    if wsum <= 0:
        wsum = 1.0
    return tuple(a / wsum for a in acc)


def run_three_body(rib: ActionRib, *, agents: list[Agent] | None = None,
                   steps: int = 60, dt: float = 0.1, seed: int = 3,
                   w_goal: float = 1.5, w_ali: float = 1.2, w_coh: float = 0.9,
                   w_sep: float = 1.4) -> dict[str, Any]:
    """Evolve the action swarm as a three-body system.

    Shared field: goal = the collective action-invariant attractor; existing data = repellors
    (so agents don't collapse onto already-covered ground). The flock `step` neighbour terms
    (alignment/cohesion/separation) provide the THREE-BODY coupling: aligned action-invariants
    attract, conflicting ones repel -> emergent coordination/conflict between the bodies.

    Returns the trajectory + each body's final action (via emit_actions).
    """
    from mag.steal_steer import _field
    if agents is None:
        agents = spawn_agents(rib, seed=seed)
    goal = _collective_center(rib)
    field = _field(goal, _existing_points(), radius=0.32)
    traj = []
    for t in range(steps):
        step(agents, field, dt=dt, max_speed=0.5, damp=0.9)
        if t % 15 == 0:
            traj.append({"t": t, "n": len(agents)})
    return {"ok": True, "schema": SCHEMA, "steps": steps, "agents": len(agents),
            "goal": list(round(float(v), 3) for v in goal),
            "trajectory": traj,
            "actions": emit_actions(rib, agents)}


def influence(rib: ActionRib, *, action: str, strength: float = 2.0) -> dict[str, Any]:
    """INFLUENCE the swarm: add/boost an action-invariant attractor in the shared field.

    Adding a strong action-invariant attractor shifts the collective center, so the three-body
    dynamics steer the swarm toward the desired behavior. This is HOW we steer the digital realm:
    by injecting an action-invariant (the invariant as the steering message), the emergent
    coordination among agents is influenced. Deterministic, $0.
    """
    found = any(str(s.get("action")).strip() == action.strip() for s in rib.slots)
    if found:
        # boost the existing attractor's weight in BOTH spec and slots (they must stay in sync)
        new_w = max(1.0, strength)
        for s in rib.spec:
            if str(s.get("action")).strip() == action.strip():
                s["weight"] = float(s.get("weight") or 1.0) * new_w
        for s in rib.slots:
            if str(s.get("action")).strip() == action.strip():
                s["weight"] = float(s.get("weight") or 1.0) * new_w
    else:
        rib.spec.append({"id": f"influence_{len(rib.slots)}", "action": action,
                         "radius": 0.3, "weight": max(1.0, strength)})
        rib.slots.append({"id": rib.spec[-1]["id"], "action": action,
                          "center": _embed(action), "radius": 0.3,
                          "weight": max(1.0, strength)})
    return {"ok": True, "schema": SCHEMA, "influenced": action, "strength": strength,
            "new_collective": list(round(float(v), 3) for v in _collective_center(rib)),
            "n_slots": len(rib.slots)}


def emit_actions(rib: ActionRib, agents: list[Agent]) -> list[dict[str, Any]]:
    """Decode each body's final action-position to its nearest action-invariant = the ACTION
    MESSAGE it communicates to the other bodies. This is the invariant it broadcasts."""
    out = []
    for i, a in enumerate(agents):
        best, best_d = None, float("inf")
        for s in rib.slots:
            d = _vlen(_vsub(a.pos, s["center"]))
            if d < best_d:
                best_d, best = d, s
        out.append({"agent": i, "action": best["action"] if best else None,
                    "distance": round(best_d, 3)})
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rib-action")
    ap.add_argument("cmd", nargs="?", default="demo", choices=["demo"])
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--agents", type=int, default=6)
    args = ap.parse_args(argv)
    spec = [
        {"id": "route", "action": "route async work through the architecture queue, never terminal"},
        {"id": "headless", "action": "spawn nothing that pops a window; use headless CREATE_NO_WINDOW"},
        {"id": "fold", "action": "fold every invariant to a content-addressed knot, amend not erase"},
        {"id": "steal", "action": "self-steal and external-steal the invariant, never the DNA"},
        {"id": "dogfood", "action": "probe the real system every cycle so failures surface"},
        {"id": "influence", "action": "steer the swarm by injecting an action-invariant attractor"},
    ]
    rib = declare(spec)
    r = run_three_body(rib, agents=spawn_agents(rib, n=args.agents, seed=3),
                       steps=args.steps, seed=3)
    r["rib"] = [{"id": s["id"], "action": s["action"]} for s in rib.slots]
    print(json.dumps(r, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
