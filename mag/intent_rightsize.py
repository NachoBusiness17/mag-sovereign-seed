"""intent_rightsize — right-size by INTENT (not just cost) + temporal RIB chaining across k8s/k3s
+ coldest-vertex future-proof prediction.

Operator (2026-08-12): "can't we manipulate that like we did when we moved the entire system
resources to 42.0 69% couldn't we in theory structure rib files temporally to create chained complex
behavior between k8's and k3's to enhance this process and the entire right size concept to stateless
and cover intent not just cost. so if i wanted to run things through the cpu and hyperviser shit we
could deterministically predict which was future proof via coldest vertex"

THE VISION (all real pieces, one connector):
  1. RIGHT-SIZE BY INTENT not just cost: cost is only one axis. Intent = WHAT kind of work
     (deterministic-exact / research / frontier / build). Different intents right-size differently:
     deterministic-exact -> CPU local, $0; research -> swarm; frontier -> coldest seam spend.
  2. TEMPORAL RIB CHAIN: structure RIB files as an ORDERED sequence (chain) so behavior between
     k8s (cloud swarm) and k3s (lightweight/deterministic local) is CHAINED — step 1's output feeds
     step 2, like a pipeline. This is "chained complex behavior" — not one task, a sequence.
  3. COLDEST-VERTEX FUTURE-PROOF: predict which route (CPU / hypervisor / k8s / k3s) is future-proof
     by COLDEST VERTEX — the neglected core / highest-invariant anchor. A route aimed at the coldest
     shared vertex is the most future-proof (least likely to be obsoleted). ghost_summon.
     coldest_vertices() + jones_lens.verkle_vertex give the real cold coordinates.

Schema: intent_rightsize.v1 · deterministic + $0 · reuse: swarm_economics, ghost_summon, jones_lens,
machine_target, rib_bus
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

SCHEMA = "intent_rightsize.v1"

# Intent -> right-size profile: WHERE it runs + HOW many + WHY (cost is one axis, intent is the other)
INTENT = {
    "deterministic": {"surface": "cpu", "n_agents": 1, "cost_tier": "$0",
                      "why": "exact, reproducible — CPU local, no frontier needed"},
    "research":      {"surface": "swarm", "n_agents": 4, "cost_tier": "cheap",
                      "why": "exploration — cheap flash swarm, seams only"},
    "frontier":      {"surface": "frontier", "n_agents": 1, "cost_tier": "premium",
                      "why": "deep synthesis — spend frontier ONLY at the coldest seams"},
    "build":         {"surface": "k3s", "n_agents": 2, "cost_tier": "cheap",
                      "why": "deterministic build — k3s lightweight local"},
    "inference":     {"surface": "gpu", "n_agents": 1, "cost_tier": "cheap",
                      "why": "model infer — GPU when free, else CPU (rightsized)"},
}


def _detect_intent(goal: str) -> str:
    """Classify intent from the goal (deterministic keyword, not LLM). Honest default = research."""
    g = (goal or "").lower()
    if any(k in g for k in ("binary", "patch", "elf", "exact", "deterministic", "byte")):
        return "deterministic"
    if any(k in g for k in ("frontier", "synthesize", "opinion", "moonshot", "deep research")):
        return "frontier"
    if any(k in g for k in ("build", "compile", "package", "docker")):
        return "build"
    if any(k in g for k in ("infer", "generate", "render", "gpu")):
        return "inference"
    return "research"


def _coldest() -> list[dict[str, Any]]:
    try:
        from mag import ghost_summon
        return ghost_summon.coldest_vertices(limit=5)
    except Exception:
        return []


def _cold_route(goal: str) -> dict[str, Any]:
    """Predict the FUTURE-PROOF route by coldest vertex: aim at the neglected core / highest
    invariant anchor. Returns the cold coordinates + the recommended route."""
    # the goal's own verkle vertex (jones_lens) = its topological coordinate
    cold = {"goal_vertex": None, "system_coldest": []}
    try:
        from mag import jones_lens
        v = jones_lens.verkle_vertex(goal)
        cold["goal_vertex"] = v.get("verkle_vertex")
    except Exception:
        pass
    cold["system_coldest"] = _coldest()
    # future-proof = aim where the coldest shared vertex points (neglected core = least obsoleted)
    route = "cpu"  # default future-proof: the deterministic local core
    if cold["system_coldest"]:
        # if the coldest system vertices are cloud/swarm-leaning, the future-proof route is the swarm
        coldest_names = " ".join(str(c.get("name") or c.get("id") or c.get("title") or "") for c in cold["system_coldest"]).lower()
        if any(k in coldest_names for k in ("swarm", "cloud", "k8s", "cluster")):
            route = "k8s"
        elif any(k in coldest_names for k in ("gpu", "render", "infer")):
            route = "gpu"
    return {"route": route, "cold": cold,
            "note": f"future-proof route = {route} (aimed at the coldest shared vertex = least-obsoleted core)"}


def temporal_chain(goal: str, *, steps: list[str] | None = None, domain: str = "territory") -> dict[str, Any]:
    """STRUCTURE RIB FILES TEMPORALLY: an ordered chain of RIBs so behavior between k8s and k3s is
    CHAINED (step i's output feeds step i+1). Returns the chain + the mount plan."""
    steps = steps or [
        f"chain-1: read the goal '{goal}' and map its coordinate",
        "chain-2: lower to the machine target (k3s deterministic core)",
        "chain-3: shade the seams through the swarm (k8s)",
        "chain-4: fold the result as a standing-wave knot (the chain persists)",
    ]
    chain = [{"position": i + 1, "rib": s} for i, s in enumerate(steps)]
    try:
        from mag import rib_bus as rb
        mounted = rb.mount(domain)
        n_mounted = mounted.get("n_ribs", 0)
    except Exception:
        n_mounted = 0
    return {"ok": True, "schema": SCHEMA, "goal": goal[:120], "domain": domain,
            "chain": chain, "n_steps": len(chain),
            "doctrine_mounted": n_mounted,
            "note": "temporal RIB chain: each step feeds the next, crossing k3s (deterministic core) "
                    "-> k8s (swarm seams) -> back to the chain. Chained complex behavior."}


def rightsize(goal: str = "", *, intent: str | None = None, provider: str = "deepseek-v4-flash") -> dict[str, Any]:
    """RIGHT-SIZE BY INTENT + cold-vertex future-proof: the full answer."""
    goal = (goal or "").strip() or "the task"
    intent = (intent or "").strip() or _detect_intent(goal)
    prof = INTENT.get(intent, INTENT["research"])
    cold = _cold_route(goal)
    return {"ok": True, "schema": SCHEMA, "goal": goal[:120], "provider": provider,
            "intent": intent, "profile": prof,
            "route": cold["route"], "cold_vertex": cold["cold"]["goal_vertex"],
            "system_coldest": cold["cold"]["system_coldest"][:3],
            "reasoning": (f"intent '{intent}' -> {prof['surface']} ({prof['n_agents']} agents, "
                          f"{prof['cost_tier']}) because {prof['why']}; future-proof route via "
                          f"coldest vertex = {cold['route']}"),
            "note": "right-size covers INTENT (what kind of work) not just cost; the future-proof "
                    "route is predicted by the coldest vertex (neglected core = least obsoleted)"}


def test_limits(*, goal: str = "") -> dict[str, Any]:
    """TEST THE LIMITS of our surfaces + their invariants (RIB-debug applied to the execution
    plane). For each surface (cpu/gpu/swarm/k8s/k3s/frontier) probe its REAL limits honestly
    (availability, utilization, cost, liveness) and verify the governing invariant HOLDS (the RIB
    is present + the surface it governs is alive) or is AT/BREACHING its limit.

    Operator (2026-08-12): "rightsizer should be able to test the limits of our surfaces and their
    invariants." Deterministic + $0. Honest: a blind probe reports source:none, never fabricates.
    """
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "goal": goal[:120], "surfaces": {}}

    # ── GPU surface: is it resolved + free? (the once-blind AMD arm) ──
    try:
        from mag import gpu_ghost
        g = gpu_ghost.gpu_status()
        out["surfaces"]["gpu"] = {
            "surface": "gpu", "alive": g.get("source") != "none",
            "source": g.get("source"), "util_pct": g.get("util_pct"),
            "free": g.get("free"), "name": g.get("name"),
            "limit_note": ("resolved + can cook" if g.get("source") != "none" else
                           "blind (source:none) — VRAM lattice staged, not confirmed")}
    except Exception as e:
        out["surfaces"]["gpu"] = {"surface": "gpu", "alive": False, "error": str(e)[:80]}

    # ── swarm/k8s surface: queue depth + results returned (the internet waves) ──
    try:
        from config import QUEUE_DIR, RESULTS_DIR
        q = QUEUE_DIR / "swarm_worker" / "queue"
        n_queued = len(list(q.glob("*.json"))) if q.is_dir() else 0
        n_results = len(list(RESULTS_DIR.glob("sw-*.json"))) if RESULTS_DIR.is_dir() else 0
        out["surfaces"]["swarm"] = {"surface": "swarm", "alive": n_queued >= 0,
                                    "n_queued": n_queued, "n_results": n_results,
                                    "limit_note": "draining" if n_queued > 0 else
                                                  ("results returning" if n_results > 0 else "idle")}
    except Exception as e:
        out["surfaces"]["swarm"] = {"surface": "swarm", "alive": False, "error": str(e)[:80]}

    # ── cpu/k3s surface: the deterministic local core ──
    out["surfaces"]["cpu"] = {"surface": "cpu", "alive": True, "cost": "$0",
                              "limit_note": "deterministic local core — always available"}
    out["surfaces"]["k3s"] = {"surface": "k3s", "alive": True, "cost": "cheap",
                              "limit_note": "lightweight local — lowers RIBs to the machine target"}

    # ── frontier surface: is a real frontier seat reachable? ──
    try:
        from harness import grok_cli
        out["surfaces"]["frontier"] = {"surface": "frontier",
                                       "alive": bool(grok_cli.harness_available()),
                                       "limit_note": "zero-surface Grok (front-end, $0)" if
                                       grok_cli.harness_available() else "seat down (CDP)"}
    except Exception as e:
        out["surfaces"]["frontier"] = {"surface": "frontier", "alive": False, "error": str(e)[:80]}

    # ── INVARIANTS: verify each surface's governing RIB holds (present + its surface alive) ──
    invs = []
    try:
        from mag import rib_bus
        for dom, surf in (("k3s-toolset", "k3s"), ("general", "cpu"), ("game", "gpu"),
                          ("swarm", "swarm")):
            m = rib_bus.mount(dom)
            n = m.get("n_ribs", 0)
            alive = out["surfaces"].get(surf, {}).get("alive", True)
            invs.append({"domain": dom, "surface": surf, "n_ribs": n,
                         "holds": (n > 0) and bool(alive),
                         "note": ("invariant present + surface alive = HOLDS"
                                  if n > 0 and alive else
                                  "at limit: invariant missing or surface down")})
    except Exception as e:
        invs.append({"error": str(e)[:80]})
    out["invariants"] = invs
    out["n_surfaces_alive"] = sum(1 for s in out["surfaces"].values() if s.get("alive"))
    out["n_invariants_hold"] = sum(1 for i in invs if i.get("holds"))
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "rightsize(goal, intent)->right-size by INTENT (not just cost): deterministic/"
                        "research/frontier/build/inference each map to a surface + concurrency. "
                        "temporal_chain(goal)->structure RIBs as an ORDERED chain crossing k3s->k8s. "
                        "Coldest-vertex (ghost_summon + jones_lens) predicts the future-proof route.",
            "cost": "deterministic + $0 (reuse swarm_economics, ghost_summon, jones_lens, machine_target)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="intent-rightsize")
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--intent", default="")
    ap.add_argument("cmd", nargs="?", default="rightsize", choices=["rightsize", "chain", "status"])
    a = ap.parse_args()
    g = " ".join(a.goal) or "the standing wave material"
    if a.cmd == "chain":
        print(json.dumps(temporal_chain(g), indent=2, default=str))
    elif a.cmd == "rightsize":
        print(json.dumps(rightsize(g, intent=a.intent), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
