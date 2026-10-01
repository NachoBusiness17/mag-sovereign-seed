"""problem_knot — map PROBLEMS to KNOT TOPOLOGY and use SWARMS to solve them.

Operator (2026-08-10): "how can we map problems to knot topology and use swarms to solve them
deep research."

THE MECHANISM (connects the whole arc — verkle lattice + swarm + Roshomon + attractor tools):

  1. PROBLEM -> KNOT: a problem is encoded as a VERKLE KNOT — content-addressed (leaf_hash =
     address), merkle-chained (parent_verkle_root = what it builds on). Same problem = same knot
     (dedupe); every problem knows its parent (topology/provenance).
  2. KNOT TOPOLOGY: problems form a LATTICE — each problem links to its parent and to related
     problems (shared invariants / same domain). We navigate this topology mycelially to find the
     most load-bearing open problem to solve next.
  3. SWARM SOLVES IT: the swarm (k8s render farm) reads a problem-knot and dispatches N agents as
     ROSHOMON witnesses — each attacks a slice of the problem; the convergent core is the solution.
  4. SOLUTION -> CHILD KNOT: the converged invariant folds as a CHILD knot linked to the problem,
     growing the lattice. Solved problems spawn sub-problems (child knots) the swarm picks up.

So the lattice IS the problem space: content-addressed, topologically navigable, and the swarm is
the renderer that turns each problem-knot into solved sub-knots. Deterministic $0 for declare/
topology/dispatch; the agent calls are the swarm's intended work.

Schema: problem_knot.v1 · CLI: python -m mag.problem_knot declare|topology|solve
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "problem_knot.v1"
OUT_DIR = ROOT / "memory" / "runs" / "problem_knot"
REGISTRY = OUT_DIR / "registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(s: str, n: int = 40) -> str:
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in (s or "p").lower())
    return (s or "p")[:n]


def _registry() -> dict[str, Any]:
    if REGISTRY.is_file():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {"problems": {}}


def _save(reg: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def declare_problem(goal: str, *, domain: str = "general", invariants: list[str] | None = None,
                    parent_knot: str | None = None, relation: str = "or") -> dict[str, Any]:
    """Encode a PROBLEM as a verkle knot: content-addressed, merkle-chained to its parent.

    relation (AND-OR steal): a problem knot is an AND-OR node in the decomposition tree.
      'or'  -> solved when ANY child is solved (alternatives / a goal satisfied by one path)
      'and' -> solved when ALL children are solved (all sub-problems required)
    The knot is the problem's identity + provenance in the lattice. Returns the knot + leaf_hash.
    Deterministic $0 (a verkle write)."""
    if not (goal or "").strip():
        return {"ok": False, "error": "empty problem goal"}
    from mag.verkle_knot import append_verkle_knot
    inv = invariants or []
    relation = relation if relation in ("and", "or") else "or"
    sid = f"problem-{_slug(goal)}"
    dossier = {
        "session_id": sid,
        "theme": f"problem:{domain}",
        "summary": f"PROBLEM ({domain}, {relation}): {goal.strip()[:400]}"
                   + (f" | invariants: {'; '.join(inv)[:400]}" if inv else ""),
        "meta": {"kind": "problem", "domain": domain, "parent_knot": parent_knot,
                 "invariants": inv, "relation": relation},
    }
    leaf = append_verkle_knot(dossier)
    lh = str(leaf.get("leaf_hash") or "")
    reg = _registry()
    reg["problems"][lh] = {
        "goal": goal.strip()[:400], "domain": domain, "invariants": inv,
        "parent_knot": parent_knot, "children": [], "relation": relation,
        "solved": False, "solution_invariant": None,
        "leaf_hash": lh, "verkle_root": str(leaf.get("verkle_root") or ""),
        "created_at": _now(),
    }
    if parent_knot and parent_knot in reg["problems"]:
        reg["problems"][parent_knot]["children"].append(lh)
    _save(reg)
    return {"ok": True, "schema": SCHEMA, "problem_knot": lh,
            "verkle_root": leaf.get("verkle_root"), "path": str(leaf.get("path")),
            "parent_knot": parent_knot, "relation": relation, "session_id": sid}


def problem_topology(*, domain: str | None = None, root: str | None = None) -> dict[str, Any]:
    """The KNOT TOPOLOGY: the problem lattice — each problem, its parent, children, and related
    problems (shared invariants / same domain). Navigate mycelially to find the open problem."""
    reg = _registry()
    probs = reg.get("problems", {})
    if domain:
        probs = {k: v for k, v in probs.items() if v.get("domain") == domain}
    nodes = [{"knot": k, "goal": v.get("goal")[:80], "domain": v.get("domain"),
              "parent": v.get("parent_knot"), "children": v.get("children", []),
              "relation": v.get("relation", "or"), "solved": bool(v.get("solved")),
              "n_invariants": len(v.get("invariants", []))} for k, v in probs.items()]
    roots = [n for n in nodes if not n["parent"]]
    return {"ok": True, "schema": SCHEMA, "n_problems": len(nodes), "n_roots": len(roots),
            "n_solved": sum(1 for n in nodes if n["solved"]),
            "topology": nodes, "roots": [n["knot"] for n in roots]}


def dispatch_solver(problem_knot: str, *, n_agents: int = 3) -> dict[str, Any]:
    """Dispatch N swarm agents as ROSHOMON witnesses to solve a problem-knot (via the k8s swarm).

    Each agent attacks a slice of the problem; the convergent core is the solution. Deterministic
    $0 to enqueue; the k8s cluster renders it."""
    reg = _registry()
    p = reg.get("problems", {}).get(problem_knot)
    if not p:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown problem knot {problem_knot[:12]}"}
    from mag import swarm_worker as sw
    goal = p.get("goal") or ""
    inv = p.get("invariants") or []
    launched = []
    for i in range(n_agents):
        g = (f"[PROBLEM {p.get('domain')}] {goal}"
             + (f"\n[KNOWN INVARIANTS] {'; '.join(inv)[:300]}" if inv else "")
             + f"\nGive ONE concrete solution-invariant that resolves this problem (INVARIANT: one line).")
        r = sw.enqueue_task(g, provider="deepseek", model="deepseek-chat",
                            domain=p.get("domain") or "problem", agent_idx=i,
                            tag=f"problem-solve-{problem_knot[:8]}")
        launched.append({"witness": i, "ok": bool(r.get("ok")), "task_id": r.get("task_id")})
    return {"ok": True, "schema": SCHEMA, "problem_knot": problem_knot,
            "n_agents": n_agents, "launched": launched}


def _propagate_solved(reg: dict[str, Any], knot: str) -> list[str]:
    """STIGMERGY + AND-OR steal: after a knot is solved, propagate solved-state up the lattice.

    For each ancestor: a problem is solved when (relation='or') ANY child is solved, or
    (relation='and') ALL children are solved. Returns the knots newly marked solved.
    The verkle lattice is the shared state (the 'pheromone trail') every agent reads/writes."""
    probs = reg.get("problems", {})
    newly = []
    cur = probs.get(knot)
    seen = set()
    while cur is not None and cur.get("parent_knot") and cur["parent_knot"] not in seen:
        parent_k = cur["parent_knot"]
        seen.add(parent_k)
        parent = probs.get(parent_k)
        if not parent or parent.get("solved"):
            break
        kids = [probs.get(c) for c in parent.get("children", [])]
        kids = [k_ for k_ in kids if k_]
        if not kids:
            break
        if parent.get("relation") == "or":
            solved = any(k_.get("solved") for k_ in kids)
        else:  # and
            solved = all(k_.get("solved") for k_ in kids)
        if solved:
            parent["solved"] = True
            newly.append(parent_k)
            cur = parent
        else:
            break
    return newly


def fold_solution(problem_knot: str, invariant: str) -> dict[str, Any]:
    """Fold a converged solution-invariant as a CHILD knot linked to the problem (grows the lattice),
    then PROPAGATE solved-state up the AND-OR lattice (stigmergic solution propagation)."""
    reg = _registry()
    p = reg.get("problems", {}).get(problem_knot)
    if not p:
        return {"ok": False, "error": f"unknown problem knot {problem_knot[:12]}"}
    from mag.verkle_knot import append_verkle_knot
    leaf = append_verkle_knot({
        "session_id": f"solution-{_slug(str(p.get('goal'))[:30])}-{uuid.uuid4().hex[:6]}",
        "theme": f"solution:{p.get('domain')}",
        "summary": f"SOLUTION for {problem_knot[:12]}: {invariant[:400]}",
        "meta": {"kind": "solution", "problem_knot": problem_knot,
                 "parent_knot": problem_knot},
    })
    lh = str(leaf.get("leaf_hash") or "")
    if problem_knot in reg["problems"] and lh not in reg["problems"][problem_knot]["children"]:
        reg["problems"][problem_knot]["children"].append(lh)
    # mark THIS problem solved + propagate up the AND-OR lattice
    p["solved"] = True
    p["solution_invariant"] = invariant[:400]
    propagated = _propagate_solved(reg, problem_knot)
    _save(reg)
    return {"ok": True, "schema": SCHEMA, "solution_knot": lh, "problem_knot": problem_knot,
            "invariant": invariant[:160], "verkle_root": leaf.get("verkle_root"),
            "solved": True, "propagated_parents_solved": propagated}


def solve(goal: str, *, domain: str = "general", n_agents: int = 3,
          invariants: list[str] | None = None) -> dict[str, Any]:
    """The full flow: declare the problem as a knot -> dispatch the swarm to solve it.
    (Folding happens when the swarm results converge — call fold_solution with the Roshomon core.)"""
    d = declare_problem(goal, domain=domain, invariants=invariants)
    if not d.get("ok"):
        return d
    s = dispatch_solver(d["problem_knot"], n_agents=n_agents)
    return {"ok": True, "schema": SCHEMA, **d, "dispatch": s}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="problem-knot")
    ap.add_argument("cmd", nargs="?", default="topology", choices=["declare", "topology", "solve"])
    ap.add_argument("--goal", default="")
    ap.add_argument("--domain", default="general")
    ap.add_argument("--agents", type=int, default=3)
    args = ap.parse_args(argv)
    if args.cmd == "declare":
        print(json.dumps(declare_problem(args.goal, domain=args.domain), indent=2, default=str))
    elif args.cmd == "solve":
        print(json.dumps(solve(args.goal, domain=args.domain, n_agents=args.agents), indent=2, default=str))
    else:
        print(json.dumps(problem_topology(domain=args.domain or None), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
