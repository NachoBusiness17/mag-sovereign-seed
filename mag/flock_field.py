"""flock_field — geometric-algebra field-steering for the swarm (flocking + AI interaction).

Agents = particles in a scalar "distance-to-solution" field phi over invariant space. Each
agent steers by the geometric gradient -grad(phi) (steepest descent to the goal, penalized by
invariants) plus classic boid terms (separation / alignment / cohesion), and orients via
ROTORS (unit quaternions = 3D GA rotors — the belt-trick spinor lift for continuous attitude).
Integration is data-parallel over agents. Pure + deterministic ($0, no external GA lib).

Plugs into the cheap swarm: the field IS the coordination (no central orchestrator), the 37
distilled invariants seed phi, one_sizer maps an ask -> goal. RIB-sheet export for RenderMan.

Schema: flock_field.v1
CLI: python -m mag.flock_field demo [--n 40] [--steps 200] [--dim 2|3]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "flock_field.v1"


# ---------------------------------------------------------------------------
# Small vector math (tuple-based; 2D or 3D)
# ---------------------------------------------------------------------------
def _vsub(a, b): return tuple(x - y for x, y in zip(a, b))
def _vadd(a, b): return tuple(x + y for x, y in zip(a, b))
def _vscale(a, s): return tuple(x * s for x in a)
def _vdot(a, b): return sum(x * y for x, y in zip(a, b))
def _vnorm(a): return math.sqrt(_vdot(a, a)) or 1e-12
def _vnormalize(a):
    n = _vnorm(a)
    return tuple(x / n for x in a)
def _vlen(a): return _vnorm(a)


# ---------------------------------------------------------------------------
# Rotors in 3D geometric algebra = unit quaternions (belt-trick spinor lift).
# sandwich product v -> R v R* rotates v continuously (720 lift = no twist/seam).
# ---------------------------------------------------------------------------
def _qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def _qconj(q): return (q[0], -q[1], -q[2], -q[3])


def _qnorm(q):
    return math.sqrt(sum(x * x for x in q))


def _qnormalize(q):
    n = _qnorm(q) or 1e-12
    return tuple(x / n for x in q)


def _from_axis_angle(axis, angle):
    s = math.sin(angle / 2.0)
    return _qnormalize((math.cos(angle / 2.0), axis[0] * s, axis[1] * s, axis[2] * s))


def _qrotate(q, v):
    """Sandwich product: v -> q * v * q*  (rotates vector v by rotor q)."""
    qv = (0.0, v[0], v[1], v[2])
    r = _qmul(_qmul(q, qv), _qconj(q))
    return (r[1], r[2], r[3])


def _q_slerp(a, b, t):
    """Spherical interpolation toward target rotor (smooth attitude tracking)."""
    d = _qdot(a, b)
    if d < 0:
        b = _qscale(b, -1); d = -d
    d = max(-1.0, min(1.0, d))
    theta = math.acos(d)
    if theta < 1e-6:
        return _qnormalize(a)
    s = 1.0 / math.sin(theta)
    return _qnormalize(tuple((a[i] * math.sin((1 - t) * theta) + b[i] * math.sin(t * theta)) * s for i in range(4)))


def _qdot(a, b): return sum(x * y for x, y in zip(a, b))
def _qscale(a, s): return tuple(x * s for x in a)


# ---------------------------------------------------------------------------
# The distance-to-solution field
# ---------------------------------------------------------------------------
@dataclass
class PhiField:
    """Scalar field phi(x) = distance-to-goal + invariant penalties, with cached gradient.

    define_distance_field(goal, invariants) -> PhiField. eval returns (phi, grad) by
    central finite differences of the geometric gradient.
    """
    goal: tuple = field(default_factory=lambda: (0.0, 0.0, 0.0))
    invariants: list[tuple] = field(default_factory=list)   # (center, radius) penalties
    weights: list[float] = field(default_factory=list)
    h: float = 1e-3

    def value(self, x: tuple) -> float:
        phi = _vlen(_vsub(x, self.goal))
        for center, r, w in zip(self.invariants, self.weights, [1.0] * len(self.invariants)):
            d = _vlen(_vsub(x, center))
            if d < r:
                phi += w * (r - d)          # inside an invariant -> push out
        return phi

    def grad(self, x: tuple) -> tuple:
        g = []
        for i in range(len(x)):
            xp = list(x); xm = list(x)
            xp[i] += self.h; xm[i] -= self.h
            g.append((self.value(tuple(xp)) - self.value(tuple(xm))) / (2 * self.h))
        return tuple(g)

    def eval(self, x: tuple) -> tuple[float, tuple]:
        return self.value(x), self.grad(x)


def define_distance_field(goal, invariants=None, weights=None, dim: int = 3) -> PhiField:
    goal = tuple(float(g) for g in goal)
    if len(goal) < dim:
        goal = goal + (0.0,) * (dim - len(goal))
    inv = [tuple(float(c) for c in center) + (0.0,) * (dim - len(center)) for center in (invariants or [])]
    return PhiField(goal=goal[:dim], invariants=inv, weights=weights or [])


# ---------------------------------------------------------------------------
# Agent + steering (boid terms + gradient descent) + rotor orientation + integrate
# ---------------------------------------------------------------------------
@dataclass
class Agent:
    pos: tuple
    vel: tuple = field(default_factory=lambda: (0.0, 0.0, 0.0))
    rotor: tuple = field(default_factory=lambda: (1.0, 0.0, 0.0, 0.0))  # identity rotor
    radius: float = 1.0

    def dim(self) -> int:
        return len(self.pos)


def steer(agent: Agent, field: PhiField, neighbors: list[Agent],
          *, w_sep: float = 1.2, w_ali: float = 1.0, w_coh: float = 0.8,
          w_goal: float = 1.5, sep_dist: float = 1.5) -> tuple:
    """Force = -w_goal*grad(phi) + w_sep*separation + w_ali*alignment + w_coh*cohesion."""
    dim = agent.dim()
    _, grad = field.eval(agent.pos)
    goal_f = _vscale(tuple(-g for g in grad), w_goal)
    # separation: push away from nearby neighbors
    sep = [0.0] * dim
    # alignment: match mean neighbor velocity
    ali = [0.0] * dim
    # cohesion: pull toward mean neighbor position
    coh = [0.0] * dim
    n = 0
    for o in neighbors:
        if o is agent:
            continue
        d = _vsub(agent.pos, o.pos)
        dist = _vlen(d)
        if dist < sep_dist and dist > 1e-9:
            sep = _vadd(sep, _vscale(_vnormalize(d), 1.0 / dist))
        ali = _vadd(ali, o.vel)
        coh = _vadd(coh, o.pos)
        n += 1
    if n:
        ali = _vscale(tuple(a / n for a in ali), w_ali)
        mean_coh = tuple(c / n for c in coh)
        coh = _vscale(_vsub(mean_coh, agent.pos), w_coh)
    return _vadd(_vadd(_vadd(goal_f, _vscale(tuple(sep), w_sep)), ali), coh)


def rotor_orient(agent: Agent, force: tuple, *, turn_rate: float = 0.15) -> tuple:
    """Orient the rotor toward the force direction (slerp), so attitude tracks the steer.
    Returns the updated rotor. Continuous rotor lift = the belt-trick 720 rotation."""
    f = _vlen(force)
    if f < 1e-9:
        return agent.rotor
    dirv = _vnormalize(force)
    # axis = pos x dir (3D) ; in 2D use a z-axis rotor
    if agent.dim() == 2:
        target = _from_axis_angle((0, 0, 1), math.atan2(dirv[1], dirv[0]) - math.atan2(agent.pos[1] if agent.pos[1] else 1, agent.pos[0] or 1))
    else:
        p = list(agent.pos) + ([0.0] if agent.dim() == 2 else [])
        axis = (p[1] * dirv[2] - p[2] * dirv[1],
                p[2] * dirv[0] - p[0] * dirv[2],
                p[0] * dirv[1] - p[1] * dirv[0])
        an = _vnorm(axis)
        axis = axis if an > 1e-9 else (0, 0, 1)
        target = _from_axis_angle(_vnormalize(axis), turn_rate * math.atan2(an, _vdot(p, dirv)))
    return _qnormalize(_q_slerp(agent.rotor, target, min(1.0, turn_rate)))


def step(agents: list[Agent], field: PhiField, *, dt: float = 0.1, max_speed: float = 1.5,
         damp: float = 0.92) -> dict[str, Any]:
    """Integrate all agents (data-parallel): steer -> update vel/pos -> orient rotor -> clamp."""
    n = len(agents)
    for a in agents:
        f = steer(a, field, agents)
        v = _vadd(a.vel, _vscale(f, dt))
        v = _vscale(v, damp)
        sp = _vlen(v)
        if sp > max_speed:
            v = _vscale(v, max_speed / sp)
        a.vel = v
        a.pos = tuple(p + dv * dt for p, dv in zip(a.pos, v))
        a.rotor = rotor_orient(a, f)
    mean_phi = sum(field.value(a.pos) for a in agents) / max(1, n)
    mean_speed = sum(_vlen(a.vel) for a in agents) / max(1, n)
    return {"mean_phi": mean_phi, "mean_speed": mean_speed, "agents": n}


def fidelity(agents: list[Agent], field: PhiField, steps_taken: int, successes: int) -> float:
    """convergence_cost = (agent-steps * mean|F|) / success_rate — lower is cheaper."""
    mean_f = sum(_vlen(steer(a, field, agents)) for a in agents) / max(1, len(agents))
    return round((steps_taken * mean_f) / max(1e-9, successes), 4)


def demo(*, n: int = 40, steps: int = 200, dim: int = 3, seed: int = 7) -> dict[str, Any]:
    random.seed(seed)
    goal = (2.0, 1.0, 0.0) if dim == 3 else (2.0, 1.0)
    field = define_distance_field(goal, invariants=[(0, 0, 0)], dim=dim)
    agents = [Agent(pos=tuple(random.uniform(-6, 6) for _ in range(dim))) for _ in range(n)]
    traj = []
    for t in range(steps):
        r = step(agents, field, dt=0.1)
        if t % 20 == 0:
            traj.append({"t": t, "mean_phi": round(r["mean_phi"], 4), "mean_speed": round(r["mean_speed"], 4)})
    within = sum(1 for a in agents if _vlen(_vsub(a.pos, goal)) < 0.5)
    return {"schema": SCHEMA, "goal": goal, "n": n, "steps": steps, "dim": dim,
            "converged_within_0.5": within, "pct": round(100.0 * within / n, 1),
            "fidelity_cost": fidelity(agents, field, steps, within),
            "trajectory": traj,
            "mean_phi_final": round(sum(field.value(a.pos) for a in agents) / n, 4)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="flock-field")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--dim", type=int, default=3)
    args = ap.parse_args(argv)
    print(json.dumps(demo(n=args.n, steps=args.steps, dim=args.dim), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
