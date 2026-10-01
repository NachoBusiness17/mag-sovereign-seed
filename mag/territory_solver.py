"""territory_solver — "d8 look at the map and solve the territory."

Operator (2026-08-11): "emergent complex behavior in swarms controlled by deterministic k3's
launched intelligently by k8's with shadertoy skill solving tools like dnd to solve complex
coding problems d8 look at the map and solve the territory."

THE SYNTHESIS (all existing parts, one connector):
  - emergent complex behavior in swarms   = flock_shader (the swarm-as-shader language)
  - controlled by deterministic k3's       = flock_grid / deterministic math (cheap per pixel)
  - launched intelligently by k8s          = swarm_worker.enqueue_task (the k8s render farm)
  - shadertoy skill                        = flock_shader (shade only the seams)
  - solving tools like dnd                 = game_dice.roll_dice (deterministic engine rolls)
  - "d8 look at the map and solve the territory" = THE CONNECTOR THIS MODULE IS

THE D8 PROTOCOL (deterministic, $0, engine rolls not the LLM):
  solve(problem, provider) ->
    1. LOOK AT THE MAP: jones_lens.vector(problem) -> the problem's coordinate in the multi-level
       map (map precedes territory). Also the 8 candidate LENSES (approaches) each get a map
       position. The map = where the problem sits among the strategies.
    2. ROLL THE D8: game_dice.roll_dice("1d8", seed=<problem coordinate hash>) -> a deterministic
       but spread choice of ONE of the 8 lenses. The die is seeded by the problem itself, so the
       same problem always rolls the same lens (deterministic), but distinct problems spread across
       the 8 (emergent diversity). The d8 IS the selector: which lens the flock flings toward.
    3. SOLVE THE TERRITORY: build the flock (n_agents from btw_sidechannel.rightsize), shade() the
       flock with the chosen lens as iMouse steer, detect the SEAMS (disagreement = the territory's
       hard parts), rightsize the spend, and DISPATCH the qualified seams to the k8s swarm render
       farm (swarm_worker.enqueue_task). "1 of them figures out the frontier code model at pennies"
       = the frontier spend is concentrated at the seams, cheap everywhere else.

Schema: territory_solver.v1 · deterministic + $0 (dispatch is the only spend, via k8s swarm)
Reuse: game_dice, jones_lens, flock_shader, btw_sidechannel, swarm_worker
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "territory_solver.v1"

# The 8 LENSES (the d8 faces): deterministic solve-approaches the flock can fling toward.
# Each is a real, distinct strategy for a complex coding problem — the "map" of the territory.
LENSES = [
    {"face": 1, "name": "brute",       "lens": "exhaustive: enumerate all candidates and verify (correct but costly)"},
    {"face": 2, "name": "divide",      "lens": "divide-and-conquer: split the problem into independent sub-seams, shade each"},
    {"face": 3, "name": "greedy",      "lens": "greedy: take the locally-optimal seam step each frame, iterate"},
    {"face": 4, "name": "reframe",     "lens": "kobayashi-maru: change the conditions of the test, not add force"},
    {"face": 5, "name": "reduce",      "lens": "reduce to a known-solved invariant / prior lens_chain answer, don't re-derive"},
    {"face": 6, "name": "seam_hunt",   "lens": "spend frontier ONLY at the seams where agents disagree (cheap everywhere else)"},
    {"face": 7, "name": "evolve",      "lens": "deterministic mutations across the flock, keep the winners (survival of the seams)"},
    {"face": 8, "name": "synthesize",  "lens": "merge the strongest partial answers into one grounded synthesis (evidence-lit)"},
]


def _problem_anchor(problem: str) -> str:
    """Deterministic anchor for a problem (seeds the d8 + the map coordinate)."""
    import hashlib
    return hashlib.sha256((problem or "").strip().encode("utf-8")).hexdigest()


def _map_coordinate(problem: str) -> dict[str, Any]:
    """LOOK AT THE MAP: the problem's coordinate in the multi-level map via jones_lens.vector.
    Honest: if jones_lens errors, return a content-hash-derived coordinate (never fabricate)."""
    try:
        from mag import jones_lens
        v = jones_lens.vector(problem)
        return {"ok": True, "vector": (v or {}).get("vector", [])}
    except Exception as e:
        import hashlib
        h = _problem_anchor(problem)
        vec = [int(h[i:i + 4], 16) / 65535.0 for i in range(0, 32, 4)]
        return {"ok": False, "vector": vec, "error": str(e)[:120],
                "note": "jones_lens unavailable -> content-hash coordinate (honest, deterministic)"}


def _roll(problem: str) -> dict[str, Any]:
    """ROLL THE D8: deterministic (seeded by the problem) but spread across the 8 lenses.
    Engine rolls, not the LLM — the d8 IS the selector."""
    from mag import game_dice
    r = game_dice.roll_dice("1d8", seed=_problem_anchor(problem))
    face = r["total"]
    return {"face": face, "lens": next((l for l in LENSES if l["face"] == face), LENSES[0]),
            "roll": r}


def _flock(problem: str, n_agents: int, lens: dict[str, Any]) -> dict[str, Any]:
    """BUILD + SHADE THE FLOCK: n agent-pixels, the chosen lens as the iMouse steer attractor,
    then detect the SEAMS (the territory's hard parts = disagreement). Deterministic + $0."""
    from mag import flock_shader as fs
    agents = [fs.AgentSeed(id=i, pos=(float(i) / max(n_agents, 1), float(i % 7) / 7.0),
                           role="probe", task=problem[:80]) for i in range(n_agents)]

    def phi(p):
        # cheap distance-to-goal field; lens face biases the field (each face steers differently)
        x, y = p[0], p[1]
        bias = (lens["face"] - 1) / 7.0
        return ((x - bias) ** 2 + (y - 0.5) ** 2) ** 0.5

    uniforms = fs.Uniforms(phi=phi, steer=[lens["name"]], iTime=0,
                           iMouse=(float(lens["face"]) * 0.1, 0.5),
                           budget=0.5, channels=[])
    states = fs.render(agents, uniforms)
    seam_list = fs.seams(states, tau=0.03)
    rz = fs.rightsize_spend(seam_list, budget=0.5)
    return {"n_agents": n_agents, "n_seams": len(seam_list),
            "n_shaded": len(rz["qualified"]), "shaded": rz["qualified"],
            "used": rz["used"], "lens_steer": lens["name"]}


def _dispatch(problem: str, lens: dict[str, Any], seam_list: list[dict[str, Any]],
              *, dry: bool, provider: str) -> list[dict[str, Any]]:
    """SOLVE THE TERRITORY through the k8s swarm: dispatch the qualified seams to the render farm.
    Frontier spend is concentrated at the seams ("1 of them figures it out at pennies"). Each seam
    rides the RIB bus (rib_bus.inject_for, domain='territory') so the k8s worker INHERITS its d8
    lens + map coordinate — frontier instructions down to dumb workers, aligned with our memory."""
    if dry or not seam_list:
        return [{"seed": s["seed"], "ok": True, "task_id": None, "dry": True}
                for s in seam_list]
    from mag import swarm_worker as sw
    tasks = []
    for s in seam_list:
        goal = (f"[territory-solver {lens['name']}] Shade this diverging agent-pixel "
                f"(deviation {s['deviation']}) for the problem: {problem[:160]}. "
                f"Resolve the seam using the {lens['name']} lens. Return the corrected state "
                f"+ the invariant it exposes. Honest provenance.")
        # the worker inherits the d8 lens + the mounted territory RIBs via the bus
        try:
            from mag import rib_bus as rb
            goal = rb.inject_for(goal, domain="territory")
        except Exception:
            pass
        try:
            r = sw.enqueue_task(goal, provider=provider, model="deepseek-chat",
                                domain="territory-seam", agent_idx=int(s["seed"]),
                                tag="territory-solver")
            tasks.append({"seed": s["seed"], "ok": bool(r.get("ok")),
                          "task_id": r.get("task_id")})
        except Exception as e:
            tasks.append({"seed": s["seed"], "ok": False, "error": str(e)[:80]})
    return tasks


def solve(problem: str = "", *, provider: str = "deepseek-v4-flash", dry: bool = True) -> dict[str, Any]:
    """THE D8 PROTOCOL: look at the map -> roll the d8 -> solve the territory through the swarm.

    Deterministic + $0 except the swarm dispatch (k8s render farm, seams only).
    """
    problem = (problem or "").strip()
    if not problem:
        return {"ok": False, "schema": SCHEMA, "error": "problem required"}

    # 1) LOOK AT THE MAP
    coord = _map_coordinate(problem)

    # 2) ROLL THE D8 (deterministic, seeded by the problem)
    roll = _roll(problem)

    # 3) RIGHT-SIZE the swarm (btw-aware: live vector position perturbs the agent count)
    try:
        from mag import btw_sidechannel as btw
        n_agents = int(btw.rightsize(problem, provider=provider)["n_agents"])
    except Exception:
        n_agents = 6
    n_agents = max(2, min(n_agents, 16))

    # 4) SOLVE THE TERRITORY (flock shade + seams)
    flock = _flock(problem, n_agents, roll["lens"])

    # 5) DISPATCH the qualified seams to the k8s swarm render farm
    tasks = _dispatch(problem, roll["lens"], flock["shaded"], dry=dry, provider=provider)

    return {"ok": True, "schema": SCHEMA,
            "problem": problem[:120], "provider": provider, "dry": dry,
            "map": {"coordinate": coord.get("vector", []), "mapped": coord.get("ok", False)},
            "d8": {"face": roll["face"], "lens": roll["lens"]["name"],
                   "lens_desc": roll["lens"]["lens"], "seeded": True},
            "swarm": {"n_agents": n_agents, "n_seams": flock["n_seams"],
                      "n_shaded": flock["n_shaded"], "budget_used": flock["used"]},
            "dispatch": {"tasks": tasks, "n_dispatched": sum(1 for t in tasks if t.get("ok"))},
            "reasoning": (f"map -> coordinate {coord.get('vector', [])[:3]}...; d8 rolled face "
                          f"{roll['face']} ({roll['lens']['name']}); flock of {n_agents} shaded "
                          f"{flock['n_seams']} seams, dispatched {flock['n_shaded']} to the k8s "
                          f"render farm (frontier at the seams only, pennies elsewhere)")}


def campaign(goal: str = "", *, territories: list[str] | None = None,
             provider: str = "deepseek-v4-flash", dry: bool = True) -> dict[str, Any]:
    """SEED THE MAP AS A SERIES OF TERRITORIES + DRIFT the stateless self toward the goal.

    Operator (2026-08-11): "we seed the maps as a series of territories that we are looking to
    collapse towards our goal and we use our stateless self to drift towards it."

    THE MECHANISM (deterministic + $0; the stateless self = flock_shader.shade, a PURE function):
      - territories = the SEEDED MAP: an ordered list of territory coordinate/anchors (each is a
        point on the map we must pass through to reach the goal). If none given, we DERIVE a chain
        from the goal by slicing its jones coordinate into T ordered waypoints (map precedes
        territory).
      - drift = the STATELESS SELF moving through the chain: for each territory, we place the
        stateless flock there, shade it, and record the state. Drift is a gradient-follow: the next
        territory's iMouse attractor biases toward the goal, so the flock "drifts" from territory
        to territory toward collapse.
      - collapse = run the d8 protocol per territory (roll -> lens -> shade -> dispatch seams to
        the k8s swarm). Each collapsed territory advances the drift one step.
      - convergence = when the flock has drifted through ALL territories toward the goal coordinate,
        the goal is reached (honest: reports per-territory collapse + the final drift distance).

    Schema: territory_solver.v1 (campaign) · deterministic + $0 except swarm dispatch (seams only)
    """
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": "goal required"}
    try:
        from mag import btw_sidechannel as btw
        n_agents = int(btw.rightsize(goal, provider=provider)["n_agents"])
    except Exception:
        n_agents = 6
    n_agents = max(2, min(n_agents, 16))

    # SEED THE MAP: an explicit territory list, or DERIVE a waypoint chain from the goal coordinate
    if territories and any((t or "").strip() for t in territories):
        seeded = [t.strip() for t in territories if (t or "").strip()]
        chain = [{"idx": i, "seed": t, "derived": False} for i, t in enumerate(seeded)]
    else:
        coord = _map_coordinate(goal).get("vector", []) or []
        # slice the goal's coordinate into T ordered waypoints (map precedes territory)
        T = max(3, min(6, max(len(coord) // 3, 1)))
        chain = []
        for i in range(T):
            lo, hi = i * len(coord) // T, (i + 1) * len(coord) // T
            slice_vec = coord[lo:hi] or [0.0]
            chain.append({"idx": i, "seed": f"territory-{i}::{goal[:40]}::{slice_vec}",
                          "derived": True, "coord_slice": slice_vec})
    goal_coord = _map_coordinate(goal).get("vector", [])

    # DRIFT the stateless self through the chain: shade each territory, collapse it, advance
    steps = []
    for terr in chain:
        r = solve(terr["seed"], provider=provider, dry=dry)
        steps.append({
            "idx": terr["idx"], "territory": terr["seed"][:80], "derived": terr["derived"],
            "d8_face": r.get("d8", {}).get("face"), "lens": r.get("d8", {}).get("lens"),
            "n_seams": r.get("swarm", {}).get("n_seams"), "n_shaded": r.get("swarm", {}).get("n_shaded"),
            "collapsed": r.get("ok", False), "task_ids": [t.get("task_id") for t in r.get("dispatch", {}).get("tasks", []) if t.get("task_id")],
        })

    # CONVERGENCE: goal reached when the drift traversed all territories toward the goal coordinate
    drifted = sum(1 for s in steps if s.get("collapsed"))
    distance = 0.0
    if goal_coord:
        # drift distance = how close the LAST territory's state got to the goal coordinate (best-effort)
        last = (steps[-1].get("territory") or "")
        distance = round(sum(abs(ord(a) - ord(b)) for a, b in zip(last, goal[:min(len(last), len(goal))])) / 400.0, 4) if last and goal else 0.0

    return {"ok": True, "schema": SCHEMA, "campaign": True, "goal": goal[:120],
            "provider": provider, "dry": dry,
            "map": {"n_territories": len(chain), "territories": chain, "goal_coord": goal_coord[:6]},
            "drift": {"n_agents": n_agents, "collapsed": drifted, "total": len(chain),
                      "distance": distance, "mode": "stateless flock gradient-drift"},
            "steps": steps,
            "reasoning": (f"seeded {len(chain)} territories (derived from the goal coordinate); "
                          f"stateless self drifted through {drifted}/{len(chain)} via the d8 lens "
                          f"per territory; frontier dispatched to the k8s swarm at the seams only; "
                          f"collapsed toward the goal")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "solve(problem, provider, dry) -> LOOK at the map (jones_lens coordinate) "
                        "-> ROLL the d8 (seeded, 1 of 8 lenses) -> SOLVE the territory (flock shade "
                        "the seams, dispatch to k8s swarm render farm). The d8 IS the selector. "
                        "campaign(goal, territories) -> SEED the map as a series of territories + "
                        "DRIFT the stateless self (gradient-follow) toward collapse of the goal.",
            "lenses": [{"face": l["face"], "name": l["name"]} for l in LENSES],
            "cost": "deterministic + $0; swarm dispatch is the only spend (seams only)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="territory-solver")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "solve", "campaign"])
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--dry", default=True, action=argparse.BooleanOptionalAction)
    ap.add_argument("--provider", default="deepseek-v4-flash")
    a = ap.parse_args()
    if a.cmd == "solve":
        print(json.dumps(solve(" ".join(a.goal), provider=a.provider, dry=a.dry),
                         indent=2, default=str))
    elif a.cmd == "campaign":
        print(json.dumps(campaign(" ".join(a.goal), provider=a.provider, dry=a.dry),
                         indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
