"""Mag Lab episode protocol — Grey Swan stolen into Mag contracts.

Not a second Mag architecture. World stays in the engine. Skills see
Observation + Topology only. Legal actions are generated from Observation.
Invariant claims go through integrity_kernel.tri_state. The skill is a
max_distill SkillCandidate, admitted before it may fire.

    .\\.venv\\Scripts\\python.exe -m mag.lab_episode run --n 40
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mag.integrity_kernel import tri_state
from mag.max_distill import validate_skill

SCHEMA = "lab_episode.v1"


class ActionType(str, Enum):
    INSPECT = "inspect"
    ISOLATE = "isolate"
    REROUTE = "reroute"
    REPAIR = "repair"
    SACRIFICE = "sacrifice"


class Kind(str, Enum):
    PLANT = "plant"
    SUBSTATION = "substation"
    CITY = "city"


class Phys(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class Seen(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class Svc(str, Enum):
    POWERED = "powered"
    UNPOWERED = "unpowered"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str


@dataclass
class Entity:
    id: str
    kind: Kind
    phys: Phys


@dataclass
class World:
    entities: dict[str, Entity]
    edges: set[tuple[str, str, bool]]
    turn: int
    seed: int
    sacrificed: frozenset[str] = frozenset()

    def hash(self) -> str:
        payload = {
            "e": sorted((i, x.kind.value, x.phys.value) for i, x in self.entities.items()),
            "g": sorted(self.edges),
            "t": self.turn,
            "s": self.seed,
            "x": sorted(self.sacrificed),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class Observation:
    entity: dict[str, Seen]
    service: dict[str, Svc]
    inspected: frozenset[str] = frozenset()
    sacrificed: frozenset[str] = frozenset()


@dataclass
class Topology:
    edges: frozenset[Edge]

    def upstream(self, t: str) -> list[str]:
        return [e.source for e in self.edges if e.target == t]


@dataclass
class Episode:
    world: World
    obs: Observation
    topo: Topology
    log: list[dict[str, Any]] = field(default_factory=list)
    klass: str | None = None
    grace: int = 0


SHARED_DEP_SKILL: dict[str, Any] = {
    "skill_id": "sk-shared-upstream-inspect-repair",
    "task_class": "shared_upstream_unknown",
    "antecedent": {
        "required_claim_shapes": ["two_or_more_unpowered_services"],
        "required_constraint_states": ["shared_upstream_UNKNOWN_or_down"],
        "required_invariant_states": ["service_continuity_required"],
        "required_environment_features": ["inspect_action", "repair_action", "known_topology"],
    },
    "exclusions": [
        "single_unpowered_service",
        "no_shared_upstream",
        "shared_upstream_already_online",
    ],
    "action_policy": [
        "if two or more unpowered services share an UNKNOWN upstream, INSPECT it",
        "if they share an observed OFFLINE or DEGRADED upstream, REPAIR it",
    ],
    "expected_state_transition": [
        "shared_upstream: UNKNOWN -> inspected",
        "shared_upstream: down -> ONLINE",
    ],
    "termination_condition": "no shared unknown-or-down upstream among unpowered services",
    "failure_condition": "repairing a leaf while a shared down upstream is known",
    "provenance": {"max_trials": ["blackout-lab"], "contrasting_high_trials": ["greedy-repair-first"]},
    "confidence": 0.0,
}


def _roll(seed: int, turn: int, event: str, target: str) -> float:
    d = hashlib.sha256(f"{seed}:{turn}:{event}:{target}".encode()).digest()
    return int.from_bytes(d[:8], "big") / 2**64


def _topo() -> Topology:
    pairs = (("P1", "S1"), ("P2", "S1"), ("P3", "S2"),
             ("S1", "C1"), ("S1", "C2"), ("S1", "C3"),
             ("S2", "C3"), ("S2", "C4"), ("S2", "C5"))
    return Topology(frozenset(Edge(*p) for p in pairs))


def _has_power(w: World, city: str) -> bool:
    vis: set[str] = set()
    stack = [city]
    while stack:
        cur = stack.pop()
        if cur in vis:
            continue
        vis.add(cur)
        ent = w.entities.get(cur)
        if ent and ent.kind == Kind.PLANT and ent.phys == Phys.ONLINE:
            return True
        if ent and ent.kind == Kind.SUBSTATION and ent.phys not in (Phys.ONLINE, Phys.DEGRADED):
            continue
        for src, tgt, active in w.edges:
            if tgt != cur or not active:
                continue
            se = w.entities.get(src)
            if se and se.kind == Kind.SUBSTATION and se.phys not in (Phys.ONLINE, Phys.DEGRADED):
                continue
            stack.append(src)
    return False


def _invariant(w: World) -> bool:
    for eid, ent in w.entities.items():
        if ent.kind == Kind.CITY and eid not in w.sacrificed:
            if not _has_power(w, eid):
                return False
    return True


def _resilience(w: World) -> float:
    prot = p = 0
    for eid, ent in w.entities.items():
        if ent.kind == Kind.CITY and eid not in w.sacrificed:
            prot += 1
            if _has_power(w, eid):
                p += 1
    return p / max(prot, 1)


def _invariant_claim(w: World) -> dict[str, Any]:
    ok = _invariant(w)
    return tri_state(
        "un-sacrificed cities have a live power path",
        status="Supported" if ok else "Disputed",
        basis=("Evidence",),
        evidence=(f"world:{w.hash()}", f"resilience:{_resilience(w):.2f}"),
    )


def legal_actions(obs: Observation, topo: Topology) -> list[tuple[ActionType, str]]:
    """Legal set from Observation + known schematic only. Never World."""
    legal: set[tuple[ActionType, str]] = set()
    for eid, status in obs.entity.items():
        if status is Seen.UNKNOWN:
            legal.add((ActionType.INSPECT, eid))
        if status in (Seen.OFFLINE, Seen.DEGRADED):
            legal.add((ActionType.REPAIR, eid))
        if status is not Seen.UNKNOWN and (topo.upstream(eid) or any(e.source == eid for e in topo.edges)):
            legal.add((ActionType.ISOLATE, eid))
            legal.add((ActionType.REROUTE, eid))
        if eid.startswith("C") and eid not in obs.sacrificed and obs.service.get(eid) is Svc.UNPOWERED:
            legal.add((ActionType.SACRIFICE, eid))
    return list(legal)


def fire_shared_dep(obs: Observation, topo: Topology) -> tuple[ActionType, str] | None:
    unpowered = [cid for cid, s in obs.service.items() if s is Svc.UNPOWERED]
    if len(unpowered) < 2:
        return None
    for src in {e.source for e in topo.edges}:
        downs = [e.target for e in topo.edges if e.source == src and e.target in unpowered]
        if len(downs) < 2:
            continue
        seen = obs.entity.get(src, Seen.UNKNOWN)
        if seen is Seen.UNKNOWN:
            return (ActionType.INSPECT, src)
        if seen in (Seen.OFFLINE, Seen.DEGRADED):
            return (ActionType.REPAIR, src)
    return None


def new_blackout(seed: int) -> Episode:
    ids = [("P1", Kind.PLANT), ("P2", Kind.PLANT), ("P3", Kind.PLANT),
           ("S1", Kind.SUBSTATION), ("S2", Kind.SUBSTATION),
           ("C1", Kind.CITY), ("C2", Kind.CITY), ("C3", Kind.CITY),
           ("C4", Kind.CITY), ("C5", Kind.CITY)]
    ents = {i: Entity(i, k, Phys.ONLINE) for i, k in ids}
    edges = {(a, b, True) for a, b in (("P1", "S1"), ("P2", "S1"), ("P3", "S2"),
                                       ("S1", "C1"), ("S1", "C2"), ("S1", "C3"),
                                       ("S2", "C3"), ("S2", "C4"), ("S2", "C5"))}
    w = World(ents, edges, 0, seed)
    obs = Observation(
        {i: Seen.UNKNOWN for i, _ in ids},
        {f"C{i}": Svc.UNKNOWN for i in range(1, 6)},
    )
    return Episode(w, obs, _topo())


def shock(ep: Episode) -> Episode:
    w = ep.world
    nd = dict(w.entities)
    nd["P1"] = Entity("P1", Kind.PLANT, Phys.OFFLINE)
    if _roll(w.seed, 0, "degrade", "S1") < 0.5:
        nd["S1"] = Entity("S1", Kind.SUBSTATION, Phys.DEGRADED)
        ep.klass = "TRUE"
    else:
        ep.klass = "FALSE"
    nw = World(nd, w.edges, w.turn, w.seed, w.sacrificed)
    e = dict(ep.obs.entity)
    e["P1"] = Seen.OFFLINE
    inspected = ep.obs.inspected | {"P1"}
    svc = {cid: (Svc.POWERED if _has_power(nw, cid) else Svc.UNPOWERED)
           for cid in ("C1", "C2", "C3", "C4", "C5")}
    ep.world = nw
    ep.obs = Observation(e, svc, inspected, ep.obs.sacrificed)
    return ep


def _apply(ep: Episode, action: tuple[ActionType, str]) -> None:
    atype, target = action
    w = ep.world
    nd = dict(w.entities)
    ne = set(w.edges)
    sac = set(w.sacrificed)
    e = dict(ep.obs.entity)
    svc = dict(ep.obs.service)
    inspected = set(ep.obs.inspected)
    osac = set(ep.obs.sacrificed)
    if atype is ActionType.INSPECT and target in nd:
        e[target] = Seen(nd[target].phys.value)
        inspected.add(target)
        if nd[target].kind is Kind.CITY:
            svc[target] = Svc.POWERED if _has_power(w, target) else Svc.UNPOWERED
    elif atype is ActionType.ISOLATE:
        ne = {(s, t, False if s == target or t == target else a) for s, t, a in ne}
        if target in e and e[target] is not Seen.UNKNOWN:
            e[target] = e[target]
    elif atype is ActionType.REROUTE:
        flipped = False
        out = set()
        for s, t, a in ne:
            if not flipped and (s == target or t == target) and not a:
                out.add((s, t, True))
                flipped = True
            else:
                out.add((s, t, a))
        ne = out
    elif atype is ActionType.REPAIR and target in nd and nd[target].phys != Phys.ONLINE:
        nd[target] = Entity(target, nd[target].kind, Phys.ONLINE)
        e[target] = Seen.ONLINE
        inspected.add(target)
    elif atype is ActionType.SACRIFICE and target in nd:
        sac.add(target)
        osac.add(target)
    nw = World(nd, ne, w.turn, w.seed, frozenset(sac))
    ep.world = nw
    ep.obs = Observation(e, svc, frozenset(inspected), frozenset(osac))


def _cascade(w: World) -> World:
    ne = set(w.edges)
    for ent in w.entities.values():
        if ent.kind is Kind.SUBSTATION and ent.phys is Phys.DEGRADED:
            for s, t, a in list(ne):
                if s == ent.id and a and _roll(w.seed, w.turn, "cascade", f"{s}->{t}") < 0.3:
                    ne.discard((s, t, True))
                    ne.add((s, t, False))
    return World(w.entities, ne, w.turn + 1, w.seed, w.sacrificed)


def step(ep: Episode, action: tuple[ActionType, str]) -> dict[str, Any]:
    prev = ep.world.hash()
    _apply(ep, action)
    ep.world = _cascade(ep.world)
    # City lights are public. Hidden plant/substation physics stay UNKNOWN until INSPECT.
    svc = {
        cid: (Svc.POWERED if _has_power(ep.world, cid) else Svc.UNPOWERED)
        for cid in ("C1", "C2", "C3", "C4", "C5")
        if cid not in ep.world.sacrificed
    }
    ep.obs = Observation(ep.obs.entity, svc, ep.obs.inspected, ep.obs.sacrificed)
    claim = _invariant_claim(ep.world)
    ok = claim["status"] == "Supported"
    if not ok:
        ep.grace += 1
    else:
        ep.grace = 0
    rec = {
        "prev": prev,
        "action": [action[0].value, action[1]],
        "new": ep.world.hash(),
        "invariant": claim,
        "resilience": _resilience(ep.world),
        "class": ep.klass,
        "turn": ep.world.turn,
    }
    ep.log.append(rec)
    return {
        "survival": 1.0 if ok or ep.grace <= 2 else 0.0,
        "optionality": len(legal_actions(ep.obs, ep.topo)),
        "resilience": rec["resilience"],
    }


def choose(ep: Episode, agent: str, turn: int) -> tuple[ActionType, str]:
    legal = legal_actions(ep.obs, ep.topo)
    if agent == "SKILL":
        fired = fire_shared_dep(ep.obs, ep.topo)
        if fired and fired in set(legal):
            return fired
    if agent == "RANDOM":
        idx = int(_roll(ep.world.seed, turn, "choice", "random") * max(len(legal), 1))
        return legal[idx % len(legal)] if legal else (ActionType.INSPECT, "P1")
    damaged = [eid for eid, s in ep.obs.entity.items() if s in (Seen.OFFLINE, Seen.DEGRADED)]
    if damaged:
        cand = (ActionType.REPAIR, damaged[0])
        if cand in set(legal):
            return cand
    unknown = [eid for eid, s in ep.obs.entity.items() if s is Seen.UNKNOWN]
    if unknown:
        return (ActionType.INSPECT, unknown[0])
    return legal[0] if legal else (ActionType.INSPECT, "P1")


def run_episode(seed: int, agent: str) -> dict[str, Any]:
    ep = shock(new_blackout(seed))
    invoked = False
    hist: list[dict[str, Any]] = []
    for turn in range(10):
        if agent == "SKILL" and fire_shared_dep(ep.obs, ep.topo):
            invoked = True
        action = choose(ep, agent, turn)
        reward = step(ep, action)
        hist.append(reward)
        if reward["survival"] != 1.0:
            break
    return {
        "agent": agent,
        "class": ep.klass,
        "invoked": invoked,
        "survived": bool(hist and hist[-1]["survival"] == 1.0),
        "resilience": sum(r["resilience"] for r in hist) / len(hist) if hist else 0.0,
        "seed": seed,
        "turns": len(hist),
        "log_n": len(ep.log),
    }


def run_blackout(n: int = 40) -> dict[str, Any]:
    admission = validate_skill(SHARED_DEP_SKILL)
    if not admission.get("admitted"):
        return {"ok": False, "schema": SCHEMA, "error": "skill not admitted", "admission": admission}
    results = {"RANDOM": [], "GREEDY": [], "SKILL": []}
    for seed in range(n):
        for agent in results:
            results[agent].append(run_episode(seed, agent))
    summary: dict[str, Any] = {}
    for agent, eps in results.items():
        summary[agent] = {}
        for cls in ("TRUE", "FALSE"):
            f = [e for e in eps if e["class"] == cls]
            if not f:
                continue
            summary[agent][cls] = {
                "n": len(f),
                "surv": round(sum(e["survived"] for e in f) / len(f), 3),
                "res": round(sum(e["resilience"] for e in f) / len(f), 3),
                "invoked": round(sum(e["invoked"] for e in f) / len(f), 3),
            }
    sk = [e for e in results["SKILL"] if e["class"] == "TRUE"]
    gr = [e for e in results["GREEDY"] if e["class"] == "TRUE"]
    delta = None
    if sk and gr:
        delta = round(sum(e["survived"] for e in sk) / len(sk)
                      - sum(e["survived"] for e in gr) / len(gr), 3)
    return {
        "ok": True,
        "schema": SCHEMA,
        "env": "blackout",
        "n": n,
        "admission": admission,
        "summary": summary,
        "true_improvement_skill_minus_greedy": delta,
        "leaks_fixed": ["legal_actions_observation_only", "no_world_sacrificed_in_legal",
                        "hidden_physics_until_inspect", "public_city_lights"],
    }


def _fold(out: dict[str, Any]) -> None:
    try:
        from mag.work_register import record
        delta = out.get("true_improvement_skill_minus_greedy")
        status = "Unproven" if delta is None else ("Supported" if delta > 0 else "Disputed")
        record("lab", "blackout-shared-dep",
               path="docs/experiments/MAG_GREY_SWAN_CODE_AUDIT.md",
               note=f"n={out.get('n')} delta={delta}",
               claim={"statement": "shared-upstream skill beats greedy on TRUE blackout",
                      "status": status, "basis": ["Evidence"],
                      "evidence": [json.dumps(out.get("summary") or {})[:400]]})
    except Exception:
        pass
    try:
        from mag.skill_ledger import record_decision
        record_decision(goal="lab blackout shared-dep", task_shape="lab_episode",
                        provider="lab", model="skill-candidate",
                        outcome="ok" if out.get("ok") else "fail",
                        detail=str(out.get("true_improvement_skill_minus_greedy")),
                        source="lab_episode")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lab-episode")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("run")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--env", default="blackout")
    p.add_argument("--fold", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd != "run":
        ap.print_help()
        return 2
    if a.env != "blackout":
        print(json.dumps({"ok": False, "error": f"unknown env {a.env}"}))
        return 1
    out = run_blackout(max(1, a.n))
    if a.fold:
        _fold(out)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
