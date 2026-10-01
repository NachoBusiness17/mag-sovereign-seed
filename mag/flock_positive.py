"""flock_positive — the POSITIVE steering law for the Mountain school (LM9, 2026-09-30).

Operator law (2026-09-30): the fish behave under THREAT gradients (flee
pressure, tire mechanics — V6 tuned the chase-bites). Build the POSITIVE
mode: reward sources that ATTRACT. Fish seek food, gain satiation, and
satiation modulates explore-vs-exploit. This module is the LAW (steering);
the A/B harness that measures it lives in mag/flock_positive_ab.py.

TWO STEERING LAWS, ONE FILE:
  - step_threat: a per-line port of roblox_to_godot/systems/flock.gd step()
    (the V6-tuned behavior: flee push 6.0, FLEE_RADIUS 20, tire
    dt/COAST_TIME). Same constants, same branch order, same board (game.gd
    POOL_LAYOUT + _elev_y), same 60Hz tick. The pheromone trail is skipped:
    flock.gd trail is visual only (trail_steer() is never called inside
    step()), so it cannot move a fish and is not mirrored.
  - step_positive: replaces the flee branch with a food gradient — the same
    global-pull shape the game already uses for water (game.gd
    _pull_fish_to_water: POOL_PULL 22, gated by POOL_PREF_DIST 30), scaled
    by HUNGER (1 - satiation): hungry fish exploit the gradient, satiated
    fish explore (wiggle amplitude grows with satiation) and hold the food
    patch. Eating converts food units -> satiation; digestion spends it. No
    flee accrual, no fatigue, no catch window: the school never enters the
    panic state.

Constants are parse-checked against flock.gd by tests/test_flock_positive.py
(the drift law: the instrument must measure the game it plays).

Schema: flock_positive.v1 · deterministic ($0, pure Python, seeded RNG).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "flock_positive.v1"

# ---------------------------------------------------------------------------
# Constants — every one cited to its flock.gd / game.gd source line
# ---------------------------------------------------------------------------
FLEE_RADIUS = 20.0      # flock.gd FLEE_RADIUS (Z14)
CATCH_RADIUS = 3.5      # flock.gd CATCH_RADIUS
SCHOOL_RADIUS = 20.0    # flock.gd SCHOOL_RADIUS
SEP_RADIUS = 3.0        # flock.gd SEP_RADIUS
FATIGUE_DECAY = 0.4     # flock.gd FATIGUE_DECAY
DRAG = 0.985            # flock.gd DRAG
COAST_TIME = 0.8        # flock.gd COAST_TIME
FLEE_PUSH = 6.0         # flock.gd flee accel (Z14 2026-09-30: 2.5 -> 6.0)
WIGGLE = 0.05           # flock.gd wiggle amplitude
COHESION_W = 0.9        # flock.gd cohesion += d * 0.9
COHESION_APPLY = 0.55   # flock.gd cohesion / count * 0.55
SEP_PUSH = 0.6          # flock.gd separation -= norm(d) * 0.6 / max(dl, 0.1)
SEP_APPLY = 0.35        # flock.gd separation * 0.35

# Positive-mode constants (LM9; the pull magnitude cites game.gd POOL_PULL)
FOOD_PREF_DIST = 30.0   # game.gd POOL_PREF_DIST — stop pulling when near
FOOD_PULL = 22.0        # game.gd POOL_PULL — the game's own gentle steer
EAT_RADIUS = 10.0       # bite range at the food patch
EAT_RATE = 2.0          # food units per second while grazing
SATIATION_GAIN = 0.15   # satiation per food unit eaten
DIGEST_RATE = 0.04      # satiation per second spent not feeding
EXPLORE_BASE = 0.4      # wiggle amplitude floor (hunger explore noise)
EXPLORE_SAT = 1.2       # extra wiggle amplitude at full satiation

HZ = 60.0               # the game's frame step (game.gd _process -> step)
DT = 1.0 / HZ

# The board — game.gd POOL_LAYOUT with _elev_y = 600 - elev * 36 (game.gd)
POOLS: dict[str, tuple[float, float]] = {
    "spring": (130.0, 240.0),
    "terrace": (430.0, 384.0),
    "gate1": (280.0, 420.0),
    "hollow": (620.0, 492.0),
    "waste": (790.0, 600.0),
    "crown": (1010.0, 96.0),
}


def _add(a, b): return (a[0] + b[0], a[1] + b[1])
def _sub(a, b): return (a[0] - b[0], a[1] - b[1])
def _scale(a, s): return (a[0] * s, a[1] * s)
def _len(a): return math.hypot(a[0], a[1])


def _norm(a):
    n = _len(a)
    if n < 1e-12:
        return (0.0, 0.0)
    return (a[0] / n, a[1] / n)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
@dataclass
class Fish:
    """One fish: flock.gd's dictionary {pos, vel, fatigue, alive} + LM9 satiation."""
    pos: tuple[float, float]
    vel: tuple[float, float] = (0.0, 0.0)
    fatigue: float = 0.0
    satiation: float = 0.0
    alive: bool = True
    fleeing: bool = False   # inside the flee branch this tick (panic detector)
    feeding: bool = False   # grazing this tick (calm detector)


@dataclass
class FoodSource:
    """A reward source: attracts (positive gradient), depletes when grazed."""
    pos: tuple[float, float]
    amount: float

    def as_dict(self) -> dict[str, Any]:
        return {"pos": list(self.pos), "amount": round(self.amount, 3)}


def seed_school(seed: int, pool: str = "spring", n: int = 12) -> list[Fish]:
    """game.gd _build_flock mirrored: n fish at POOLS[pool] + jitter(±60, ±50),
    one seeded RNG (game.gd uses RandomNumberGenerator.seed 20260929; the
    Python harness uses random.Random(seed) — same LAW, same board, both
    arms of every A/B share the identical draw)."""
    rng = random.Random(seed)
    base = POOLS[pool]
    out = []
    for _ in range(n):
        jitter = (rng.uniform(-60.0, 60.0), rng.uniform(-50.0, 50.0))
        out.append(Fish(pos=_add(base, jitter)))
    return out


# ---------------------------------------------------------------------------
# THREAT steering (flock.gd step, per-line citations)
# ---------------------------------------------------------------------------
def step_threat(f: Fish, others: list[Fish], player: tuple[float, float],
                dt: float, sim_time: float) -> None:
    """flock.gd step() for one fish, branch order preserved, in place.

    1 flee/tire -> 2 drag -> 3 school -> 4 wiggle -> 5 catch -> 6 move.
    The trail loop is visual only (trail_steer is never called inside
    step) and is not mirrored.
    """
    to_player = _sub(player, f.pos)
    dist = _len(to_player)

    # flee when close and not spent, else rest (the V6/Z14 tuning)
    fleeing = dist < FLEE_RADIUS and f.fatigue < 1.0
    if fleeing:
        f.vel = _add(f.vel, _scale(_norm(_scale(to_player, -1.0)), FLEE_PUSH * dt))
        f.fatigue = min(f.fatigue + dt / COAST_TIME, 1.0)
    else:
        f.fatigue = max(f.fatigue - dt * FATIGUE_DECAY / COAST_TIME, 0.0)
    f.fleeing = fleeing

    f.vel = _scale(f.vel, DRAG ** (dt * HZ))                       # drag

    cohesion = (0.0, 0.0)                                          # school
    separation = (0.0, 0.0)
    count = 0
    for o in others:
        if o is f or not o.alive:
            continue
        d = _sub(o.pos, f.pos)
        dl = _len(d)
        if dl < SCHOOL_RADIUS:
            cohesion = _add(cohesion, _scale(d, COHESION_W))
            if dl < SEP_RADIUS:
                separation = _add(separation, _scale(_norm(_scale(d, -1.0)), SEP_PUSH / max(dl, 0.1)))
            count += 1
    if count > 0:
        f.vel = _add(f.vel, _scale(_add(_scale(cohesion, COHESION_APPLY / count),
                                        _scale(separation, SEP_APPLY)), dt))

    f.vel = _add(f.vel, _scale((math.sin(sim_time * 7.0 + f.pos[0] * 0.05),
                                math.cos(sim_time * 7.0 + f.pos[1] * 0.05)), WIGGLE * dt))

    if dist < CATCH_RADIUS and f.fatigue > 0.7:                    # catch
        f.alive = False
        return

    f.pos = _add(f.pos, _scale(f.vel, dt))                         # move


# ---------------------------------------------------------------------------
# POSITIVE steering (LM9: the new law)
# ---------------------------------------------------------------------------
def nearest_food(f: Fish, food: list[FoodSource]) -> FoodSource | None:
    """The strongest active food source for this fish = the nearest with
    amount > 0 (ties by list order — deterministic)."""
    best: FoodSource | None = None
    best_d = float("inf")
    for src in food:
        if src.amount <= 0.0:
            continue
        d = _len(_sub(src.pos, f.pos))
        if d < best_d:
            best_d = d
            best = src
    return best


def step_positive(f: Fish, others: list[Fish], food: list[FoodSource],
                  dt: float, sim_time: float) -> None:
    """Positive steering: the food gradient ATTRACTS (reward, not threat).

    Replaces the flee branch with (in the game's own pull shape, game.gd
    _pull_fish_to_water):
      1 FOOD SEEK — toward the nearest active source while farther than
        FOOD_PREF_DIST, scaled by hunger (1 - satiation): EXPLOIT when
        hungry, hold when fed.
      2 FEED — inside EAT_RADIUS, bite EAT_RATE*dt units off the source
        (only while not full — a full fish does not bite); satiation +=
        bite * SATIATION_GAIN. A feed-state ENTRY (not feeding -> feeding)
        is a calm event (the harness counts them like panic entries).
      3 DIGEST — not feeding: satiation decays; fatigue rests to 0 (flee
        never accrues — no panic state exists here).
      4 EXPLORE — wiggle amplitude grows with satiation (EXPLORE_BASE +
        EXPLORE_SAT * satiation): a fed school mills around the patch
        instead of drilling through it.
    Drag / school / move stay the flock.gd law (same citations as
    step_threat) so ONLY the threat-vs-food axis differs between arms.
    """
    src = nearest_food(f, food)
    fed = False
    if src is not None:
        to_src = _sub(src.pos, f.pos)
        d = _len(to_src)
        if d > FOOD_PREF_DIST:
            hunger = 1.0 - f.satiation
            f.vel = _add(f.vel, _scale(_norm(to_src), FOOD_PULL * hunger * dt))
        elif d < EAT_RADIUS and f.satiation < 1.0:
            bite = min(src.amount, EAT_RATE * dt)
            src.amount -= bite
            f.satiation = min(f.satiation + bite * SATIATION_GAIN, 1.0)
            fed = bite > 0.0
    feeding = fed
    if not feeding:
        f.satiation = max(f.satiation - dt * DIGEST_RATE, 0.0)
    f.feeding = feeding
    f.fleeing = False
    f.fatigue = max(f.fatigue - dt * FATIGUE_DECAY / COAST_TIME, 0.0)  # rest

    f.vel = _scale(f.vel, DRAG ** (dt * HZ))                       # drag

    cohesion = (0.0, 0.0)                                          # school
    separation = (0.0, 0.0)
    count = 0
    for o in others:
        if o is f or not o.alive:
            continue
        d2 = _sub(o.pos, f.pos)
        dl = _len(d2)
        if dl < SCHOOL_RADIUS:
            cohesion = _add(cohesion, _scale(d2, COHESION_W))
            if dl < SEP_RADIUS:
                separation = _add(separation, _scale(_norm(_scale(d2, -1.0)), SEP_PUSH / max(dl, 0.1)))
            count += 1
    if count > 0:
        f.vel = _add(f.vel, _scale(_add(_scale(cohesion, COHESION_APPLY / count),
                                        _scale(separation, SEP_APPLY)), dt))

    # wiggle, satiation-modulated (explore-vs-exploit)
    amp = WIGGLE * (EXPLORE_BASE + EXPLORE_SAT * f.satiation)
    f.vel = _add(f.vel, _scale((math.sin(sim_time * 7.0 + f.pos[0] * 0.05),
                                math.cos(sim_time * 7.0 + f.pos[1] * 0.05)), amp * dt))

    f.pos = _add(f.pos, _scale(f.vel, dt))                         # move
