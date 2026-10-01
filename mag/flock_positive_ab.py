"""flock_positive_ab — the A/B harness for the positive-flock law (LM9, 2026-09-30).

Measures the operator's law (2026-09-30): does POSITIVE steering (food the
operator places — luring) move the school better than THREAT steering (the
player chases, fish flee/tire)? Same board, same seed, same N ticks, same
target for both arms; the steering laws are mag/flock_positive.py (the
instrument and the game's flock.gd share constants by the drift law).

ARMS:
  THREAT: a single-cursor herder against the flee gradient. Four policies
    measured (the census — no reasonable single cursor transits the school):
      "herd" (default): pressure the REARMOST fish from directly behind
        (HERDER_GAP px, inside FLEE_RADIUS 20, outside CATCH_RADIUS 3.5 — a
        school-mover, not a hunter).
      "chase": chase the rearmost fish itself — literally the current game
        behavior (V6 tuned chase-bites). At 9 px/s the cursor outruns the
        6.7 px/s flee terminal and catches every tired fish: fishing, not
        herding.
      "standoff": park behind the school CENTROID. Measured deadlock: the
        school compresses just outside the threat bubble (nearest fish
        23.1px vs the 20px bubble) and panic FREEZES.
      "lead": walk toward a point 60px beyond the centroid (through the
        school). The flock parts around the bubble; fish behind the cursor
        flee BACKWARD; the school pins at spawn.
  POSITIVE: cursor parked off-board; food placed AT the target. The
    wettest-pool pull (game.gd) is excluded from both arms — a third force
    orthogonal to the threat/positive axis, and the target is not the
    wettest pool; excluding it isolates the operator's variable. FOOD_PULL
    is the game's own POOL_PULL magnitude 22, so the positive arm holds no
    secret force advantage.

METRICS (per arm):
  t80_seconds       first sim-second with >=80% of the seeded school alive
                    within TARGET_RADIUS of the target (None = never)
  panic_entries     flee-STATE ENTRIES (transitions into the flee branch) —
                    the error counter of the operator's law
  calm_entries      feed-state entries (transitions into eating)
  catches           tired fish caught inside CATCH_RADIUS (threat-only error)
  cohesion_mean_px  time-mean of mean distance to the alive-school centroid
  mean_nn_final_px  final mean nearest-neighbor distance (school tightness)

CLI: python -m mag.flock_positive_ab ab [--ticks 5400] [--seed 20260929]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from mag.flock_positive import (  # noqa: F401  (re-export: the family face)
    DT,
    FLEE_RADIUS,
    HZ,
    POOLS,
    CATCH_RADIUS,
    DRAG,
    Fish,
    FoodSource,
    SCHEMA,
    seed_school,
    step_positive,
    step_threat,
    _add,
    _len,
    _norm,
    _scale,
    _sub,
)

TARGET_RADIUS = 25.0    # "at target" = inside this radius of the target point
HERDER_SPEED = 9.0      # px/s — beats the 6.7 px/s flee terminal (a fair chase)
HERDER_GAP = 8.0        # pressure point behind the rearmost fish (px)
PARKED_PLAYER = (-300.0, -300.0)  # positive-arm cursor: off-board, no threat
THREAT_POLICIES = ("herd", "chase", "standoff", "lead")


@dataclass
class Episode:
    """One arm of the A/B: mode + board + seed + budget + rolling metrics."""
    mode: str                        # "threat" | "positive"
    seed: int
    ticks: int
    target: tuple[float, float]
    fish: list[Fish] = field(default_factory=list)
    food: list[FoodSource] = field(default_factory=list)
    player: tuple[float, float] = (0.0, 0.0)
    policy: str = "herd"             # threat-arm cursor policy
    sim_time: float = 0.0
    panic_entries: int = 0
    calm_entries: int = 0
    catches: int = 0
    t80_seconds: float | None = None
    cohesion_sum: float = 0.0
    cohesion_ticks: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return self.ticks / HZ


def _herder_target(ep: Episode) -> tuple[float, float]:
    """The threat-arm cursor policy (see the module docstring census)."""
    alive = [f for f in ep.fish if f.alive]
    if not alive:
        return ep.player
    cx = sum(f.pos[0] for f in alive) / len(alive)
    cy = sum(f.pos[1] for f in alive) / len(alive)
    if ep.policy == "standoff":
        away = _norm(_sub((cx, cy), ep.target))
        if away == (0.0, 0.0):
            away = (-1.0, 0.0)
        return _add((cx, cy), _scale(away, HERDER_GAP + 2.0))
    if ep.policy == "lead":
        toward = _norm(_sub(ep.target, (cx, cy)))
        if toward == (0.0, 0.0):
            toward = (1.0, 0.0)
        return _add((cx, cy), _scale(toward, 60.0))
    # "herd" and "chase": the rearmost fish, pressured from behind or chased
    rearmost = max(alive, key=lambda f: _len(_sub(f.pos, ep.target)))
    if ep.policy == "chase":
        return rearmost.pos
    behind = _norm(_sub(rearmost.pos, ep.target))
    if behind == (0.0, 0.0):
        behind = (-1.0, 0.0)
    return _add(rearmost.pos, _scale(behind, HERDER_GAP))


def run_episode(mode: str, *, seed: int = 20260929, ticks: int = 5400,
                target: str = "crown", food_amount: float = 3000.0,
                n_fish: int = 12, log_every: int = 0,
                policy: str = "herd") -> Episode:
    """Run one arm. Same board, same seed, same tick budget, same target for
    both modes — only the steering law differs. Deterministic end to end."""
    if mode not in ("threat", "positive"):
        raise ValueError(f"mode must be threat|positive, got {mode!r}")
    if policy not in THREAT_POLICIES:
        raise ValueError(f"policy must be one of {THREAT_POLICIES}, got {policy!r}")
    ep = Episode(mode=mode, seed=seed, ticks=ticks, target=POOLS[target],
                 fish=seed_school(seed, n=n_fish), policy=policy)
    prev_fleeing = [False] * len(ep.fish)
    prev_feeding = [False] * len(ep.fish)
    frac = 0.0
    if mode == "threat":
        ep.player = _add(POOLS["spring"], (-100.0, 0.0))  # cursor enters left of the school
    else:
        ep.player = PARKED_PLAYER
        ep.food = [FoodSource(pos=POOLS[target], amount=food_amount)]

    for t in range(ticks):
        sim_t = t / HZ
        if mode == "threat":
            # move the herder cursor first (a frame's input precedes the sim)
            want = _herder_target(ep)
            step_v = _sub(want, ep.player)
            if _len(step_v) > HERDER_SPEED * DT:
                step_v = _scale(_norm(step_v), HERDER_SPEED * DT)
            ep.player = _add(ep.player, step_v)
        for i, f in enumerate(ep.fish):
            if not f.alive:
                continue
            if mode == "threat":
                step_threat(f, ep.fish, ep.player, DT, sim_t)
            else:
                step_positive(f, ep.fish, ep.food, DT, sim_t)
            if f.fleeing and not prev_fleeing[i]:
                ep.panic_entries += 1
            if f.feeding and not prev_feeding[i]:
                ep.calm_entries += 1
            if not f.alive and mode == "threat":
                ep.catches += 1
            prev_fleeing[i] = f.fleeing and f.alive
            prev_feeding[i] = f.feeding and f.alive
        ep.sim_time = (t + 1) / HZ

        alive = [f for f in ep.fish if f.alive]
        if alive:
            cx = sum(f.pos[0] for f in alive) / len(alive)
            cy = sum(f.pos[1] for f in alive) / len(alive)
            mean_c = sum(_len(_sub(f.pos, (cx, cy))) for f in alive) / len(alive)
            ep.cohesion_sum += mean_c
            ep.cohesion_ticks += 1
            frac = sum(1 for f in alive if _len(_sub(f.pos, ep.target)) < TARGET_RADIUS) / len(ep.fish)
            if ep.t80_seconds is None and frac >= 0.8:
                ep.t80_seconds = ep.sim_time
        if log_every and (t + 1) % log_every == 0:
            ep.log.append({"t": t + 1, "sec": round(ep.sim_time, 2),
                           "alive": len(alive),
                           "at_target_frac": round(frac, 3) if alive else 0.0,
                           "panic": ep.panic_entries, "calm": ep.calm_entries,
                           "mean_cohesion_px": round(mean_c, 2) if alive else None})
    return ep


def _final_mean_nn(ep: Episode) -> float:
    alive = [f for f in ep.fish if f.alive]
    if len(alive) < 2:
        return float("nan")
    total = 0.0
    for f in alive:
        nn = min(_len(_sub(f.pos, o.pos)) for o in alive if o is not f)
        total += nn
    return total / len(alive)


def episode_metrics(ep: Episode) -> dict[str, Any]:
    alive = [f for f in ep.fish if f.alive]
    frac_final = (sum(1 for f in alive if _len(_sub(f.pos, ep.target)) < TARGET_RADIUS)
                  / max(1, len(ep.fish)))
    return {
        "mode": ep.mode,
        "policy": ep.policy,
        "seed": ep.seed,
        "ticks": ep.ticks,
        "seconds": ep.seconds,
        "target": [round(ep.target[0], 1), round(ep.target[1], 1)],
        "alive_final": len(alive),
        "t80_seconds": round(ep.t80_seconds, 2) if ep.t80_seconds is not None else None,
        "at_target_frac_final": round(frac_final, 3),
        "panic_entries": ep.panic_entries,
        "panic_per_sec": round(ep.panic_entries / ep.seconds, 3),
        "calm_entries": ep.calm_entries,
        "calm_per_sec": round(ep.calm_entries / ep.seconds, 3),
        "catches": ep.catches,
        "cohesion_mean_px": round(ep.cohesion_sum / max(1, ep.cohesion_ticks), 2),
        "mean_nn_final_px": round(_final_mean_nn(ep), 2),
        "food_left": round(sum(s.amount for s in ep.food), 1) if ep.food else None,
        "mean_satiation_final": round(sum(f.satiation for f in alive) / max(1, len(alive)), 3) if alive else None,
    }


def run_ab(*, seed: int = 20260929, ticks: int = 5400, target: str = "crown",
           food_amount: float = 3000.0) -> dict[str, Any]:
    """The A/B: same board, same seed, same budget, same target. The threat
    arm runs the best-faith school-mover policy (herd); the census runs all
    four single-cursor threat policies so the receipt's "no threat policy
    transits the school" claim is byte-backed, not hand-copied. Returns both
    arms' metrics + the operator's-law verdict (positive moves the school
    with fewer panic errors; also faster-or-equal and no looser)."""
    threat = run_episode("threat", seed=seed, ticks=ticks, target=target)
    positive = run_episode("positive", seed=seed, ticks=ticks, target=target,
                           food_amount=food_amount)
    tm, pm = episode_metrics(threat), episode_metrics(positive)
    census = {p: episode_metrics(run_episode("threat", seed=seed, ticks=ticks,
                                             target=target, policy=p))
              for p in THREAT_POLICIES}
    t80_t, t80_p = tm["t80_seconds"], pm["t80_seconds"]
    verdict = {
        "fewer_panic_errors": pm["panic_entries"] < tm["panic_entries"],
        "faster_or_equal_t80": (t80_p is not None and (t80_t is None or t80_p <= t80_t)),
        "tighter_or_equal_cohesion": pm["cohesion_mean_px"] <= tm["cohesion_mean_px"],
        "survivors": (pm["alive_final"], tm["alive_final"]),
        "no_threat_policy_transits": all(
            census[p]["t80_seconds"] is None for p in THREAT_POLICIES),
    }
    verdict["operator_law_holds"] = (verdict["fewer_panic_errors"]
                                     and verdict["faster_or_equal_t80"]
                                     and verdict["tighter_or_equal_cohesion"])
    return {"schema": SCHEMA, "ab": {"threat": tm, "positive": pm},
            "threat_policy_census": census, "verdict": verdict}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="mag.flock_positive_ab")
    ap.add_argument("cmd", choices=["ab"], help="run the A/B harness")
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--ticks", type=int, default=5400)
    ap.add_argument("--target", default="crown", choices=sorted(POOLS))
    ap.add_argument("--food", type=float, default=3000.0)
    args = ap.parse_args(argv)
    print(json.dumps(run_ab(seed=args.seed, ticks=args.ticks,
                            target=args.target, food_amount=args.food), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
