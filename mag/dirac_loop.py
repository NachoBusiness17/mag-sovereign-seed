"""dirac_loop — Dirac loops + knot-topology problem solving on the knowledge graph.

RESEARCH STEAL (grounded):
  * Cycle space / first homology H1 (graph theory): the independent loops of a graph form a vector
    space over Z2; its dimension is the CIRCUIT RANK = first BETTI number beta1 = m - n + c
    (edges - vertices + connected components).
  * Fundamental cycle basis: take a spanning forest; for each non-tree edge e, the cycle
    C_e = e + the tree path between its endpoints. These m-n+c cycles form a basis — deterministic,
    O(V+E). THIS is the algorithm for finding the Dirac loops.
  * Discrete Dirac / graph Laplacian: the kernel (zero-eigenvalue count) = number of connected
    components; beta1 counts the independent loops (H1). Verkle root = the topological invariant:
    same root = same knot = verify-without-replay.

THE MAP (operator's frame):
  * A problem/session is a KNOT (closed loop of steps). Its topological invariant = the content root.
  * A DIRAC LOOP = an independent cycle in the knowledge graph. Walking it (holonomy) returns a value.
  * A loop whose invariant ALREADY exists in the lattice = CLOSED/SOLVED (Tesuji, verify-without-replay).
  * A loop whose invariant is NOVEL = OPEN = a GAP the swarm/flock should fill.

Schema: dirac_loop.v1 · deterministic · $0
CLI: python -m mag.dirac_loop scan [--scope operational|knowledge|all] | cycles | rank | spectrum
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
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

SCHEMA = "dirac_loop.v1"
_GRAPH_ERROR = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _graph(scope: str = "operational") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load the selected graph without treating declarations as live evidence.

    The operational organ graph is the default because it exposes the lifecycle that can
    overflow or stall.  ``knowledge`` preserves the older source-backed content graph, and
    ``all`` combines both.  Isolated nodes are kept as components.
    """
    global _GRAPH_ERROR
    _GRAPH_ERROR = ""
    scope = (scope or "operational").strip().lower()
    if scope not in {"operational", "knowledge", "all"}:
        _GRAPH_ERROR = f"unknown graph scope: {scope}"
        return [], []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    if scope in {"operational", "all"}:
        try:
            from mag.organ_map import operational_graph
            g = operational_graph()
            nodes.extend(g.get("nodes", []))
            edges.extend(g.get("edges", []))
        except Exception as exc:
            _GRAPH_ERROR = f"operational graph: {str(exc)[:160]}"
    if scope in {"knowledge", "all"}:
        try:
            from mag.knowledge_graph import build
            g = build()
            nodes.extend(g.get("nodes", []))
            edges.extend(g.get("edges", []))
        except Exception as exc:
            _GRAPH_ERROR = f"knowledge graph: {str(exc)[:160]}"
    return nodes, edges


def _all_vertices(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    """All distinct vertices: real nodes + dangling edge endpoints (invariant:/module: targets).
    The cycle graph must treat every edge endpoint as a vertex or components/forest disagree."""
    v: set[str] = set()
    for n in nodes:
        v.add(n["id"])
    for e in edges:
        v.add(e["from"])
        v.add(e["to"])
    return sorted(v)


def _components(edges: list[dict[str, Any]], node_ids: list[str]) -> int:
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        adj[e["from"]].append(e["to"])
        adj[e["to"]].append(e["from"])
    seen: set[str] = set()
    c = 0
    for n in node_ids:
        if n in seen:
            continue
        c += 1
        stack = [n]
        seen.add(n)
        while stack:
            u = stack.pop()
            for v in adj.get(u, []):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return c


def _spanning_forest(edges: list[dict[str, Any]], node_ids: list[str]):
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        adj[e["from"]].append(e["to"])
        adj[e["to"]].append(e["from"])
    parent: dict[str, str] = {}
    tree_edges: set[frozenset] = set()
    seen: set[str] = set()
    for n in node_ids:
        if n in seen:
            continue
        stack = [n]
        seen.add(n)
        while stack:
            u = stack.pop()
            for v in adj.get(u, []):
                if v not in seen:
                    seen.add(v)
                    parent[v] = u
                    tree_edges.add(frozenset((u, v)))
                    stack.append(v)
    return parent, tree_edges


def _ancestors(parent: dict[str, str], node: str) -> list[str]:
    chain = [node]
    while node in parent:
        node = parent[node]
        chain.append(node)
    return chain


def _tree_path(parent: dict[str, str], u: str, v: str) -> list[str]:
    """Path in the spanning tree between u and v (undirected)."""
    au = _ancestors(parent, u)
    av = _ancestors(parent, v)
    au_set = set(au)
    lca = next((x for x in av if x in au_set), v)
    up = au[: au.index(lca) + 1]   # u -> lca
    down = av[: av.index(lca)]     # v -> lca (exclusive), reversed later
    return up + list(reversed(down))


def fundamental_cycles(*, scope: str = "operational") -> dict[str, Any]:
    """The Dirac loops = fundamental cycle basis (spanning forest + one cycle per non-tree edge)."""
    nodes, edges = _graph(scope)
    node_ids = _all_vertices(nodes, edges)
    by_id = {n["id"]: n for n in nodes}
    parent, tree_edges = _spanning_forest(edges, node_ids)
    loops = []
    for e in edges:
        u, v = e["from"], e["to"]
        if frozenset((u, v)) in tree_edges:
            continue
        path = _tree_path(parent, u, v)
        loops.append({"edge": f"{u}->{v}", "path": path,
                      "labels": [str(by_id.get(x, {}).get("label") or x) for x in path]})
    return {"scope": scope, "loops": loops, **({"error": _GRAPH_ERROR} if _GRAPH_ERROR else {})}


def loop_invariant(labels: list[str]) -> str:
    """The topological invariant of a loop: content-root hash of its member labels (verkle-like).
    Same set -> same invariant -> same knot, independent of traversal order."""
    return _h("dirac_loop:" + "|".join(sorted(set(labels))))


def _known_invariants(*, scope: str = "operational") -> set[str]:
    """Existing solved-shapes: knot/case-law/doctrine node hashes UNION the
    banked loop-invariants ledger (BANKED_FILE).

    2026-09-27 structural fix (found closing loop 3): the two formulas never
    met — this function hashed individual node labels while loop_invariant()
    hashes the sorted-joined label-SET, so closed_solved could never fire on
    any scope. Closure is now a receipt-backed act: bank(loop_edge, receipt)
    writes the loop's invariant + proving receipt to the banked ledger and
    scan() honors it. Adding graph edges never closes loops (every non-tree
    edge is itself a loop generator) — only banking the holonomy does."""
    known: set[str] = set()
    try:
        nodes, _ = _graph(scope)
        for n in nodes:
            lab = str(n.get("label") or n.get("summary") or "")
            if n["kind"] in ("knot", "case_law", "doctrine") and lab:
                known.add(_h("dirac_loop:" + lab[:200]))
    except Exception:
        pass
    try:
        if BANKED_FILE.is_file():
            for line in BANKED_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                inv = row.get("invariant")
                if isinstance(inv, str) and inv:
                    known.add(inv)
    except Exception:
        pass
    return known


BANKED_FILE = ROOT / "watch" / "inbox" / "DIRAC_BANKED_INVARIANTS.jsonl"


def bank(edge: str, receipt: str, seat: str = "zcode") -> dict[str, Any]:
    """Bank one loop's holonomy: record its invariant + the receipt proving
    the closed contract. The tesuji act — verify-without-replay from now on.
    The loop stays in the graph; its GAP status ends."""
    fc = fundamental_cycles()
    target = None
    for lp in fc["loops"]:
        if lp["edge"] == edge or edge in lp["edge"]:
            target = lp
            break
    if target is None:
        return {"ok": False, "error": f"no enumerated loop matches edge {edge!r}; "
                f"known edges: {[l['edge'] for l in fc['loops']]}"}
    inv = loop_invariant(target["labels"])
    row = {
        "ts": _now(), "schema": SCHEMA, "kind": "banked_loop",
        "edge": target["edge"], "invariant": inv,
        "labels": target["labels"], "receipt": str(receipt).strip(),
        "seat": seat,
    }
    BANKED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BANKED_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "banked": row}


def rank(*, scope: str = "operational") -> dict[str, Any]:
    """Circuit rank = first Betti number beta1 = m - n + c: the number of independent Dirac loops."""
    nodes, edges = _graph(scope)
    n = len(_all_vertices(nodes, edges))
    m = len(edges)
    c = _components(edges, _all_vertices(nodes, edges))
    beta1 = m - n + c
    return {"ok": not bool(_GRAPH_ERROR), "schema": SCHEMA, "scope": scope,
            "n_vertices": n, "n_edges": m,
            "components": c, "betti1": beta1, "beta1": beta1,
            "dirac_loops": max(beta1, 0),
            **({"error": _GRAPH_ERROR} if _GRAPH_ERROR else {}),
            "note": "beta1 = m - n + c = number of independent Dirac loops (first Betti number)"}


def spectrum(*, scope: str = "operational") -> dict[str, Any]:
    """Discrete Dirac/Laplacian: count zero eigenvalues = connected components; beta1 = loops.
    Computed on the edge-graph (Laplacian L = D - A). Deterministic, no heavy deps."""
    nodes, edges = _graph(scope)
    ids = _all_vertices(nodes, edges)
    idx = {nid: i for i, nid in enumerate(ids)}
    n = len(ids)
    deg = [0] * n
    for e in edges:
        a, b = idx.get(e["from"]), idx.get(e["to"])
        if a is not None and b is not None:
            deg[a] += 1
            deg[b] += 1
    # connected components via BFS = multiplicity of the zero eigenvalue of the Laplacian
    c = _components(edges, ids)
    return {"ok": not bool(_GRAPH_ERROR), "schema": SCHEMA, "scope": scope,
            "n_vertices": n, "n_edges": len(edges),
            "connected_components": c, "kernel_dim": c,
            "betti1": len(edges) - n + c,
            **({"error": _GRAPH_ERROR} if _GRAPH_ERROR else {}),
            "note": "kernel dim of graph Laplacian = components"}


def scan(*, scope: str = "operational") -> dict[str, Any]:
    """Full Dirac-loop scan: beta1, the loops, and each loop closed(solved)/open(gap)."""
    fc = fundamental_cycles(scope=scope)
    loops = fc["loops"]
    known = _known_invariants(scope=scope)
    closed, open_loops = [], []
    for lp in loops:
        inv = loop_invariant(lp["labels"])
        status = "closed" if inv in known else "open"
        (closed if status == "closed" else open_loops).append({**lp, "invariant": inv, "status": status})
    r = rank(scope=scope)
    return {"ok": bool(r.get("ok")), "schema": SCHEMA, "scope": scope, "ts": _now(),
            "betti1": r["betti1"], "n_loops": len(loops),
            "closed_solved": len(closed), "open_gaps": len(open_loops),
            "closed": closed[:8], "open": open_loops[:8],
            **({"error": r.get("error")} if r.get("error") else {}),
            "note": "closed = invariant already in lattice (solved, verify-without-replay); "
                    "open = novel invariant = a gap the swarm should fill"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dirac_loop", description="Dirac loops + knot topology on the knowledge graph")
    sub = p.add_subparsers(dest="cmd")
    for name in ("scan", "cycles", "rank", "spectrum"):
        # Accept --scope both before and after the subcommand.  Suppress the
        # subparser default so a global --scope is not overwritten.
        sub.add_parser(name).add_argument(
            "--scope", choices=("operational", "knowledge", "all"),
            default=argparse.SUPPRESS,
        )
    p_bank = sub.add_parser("bank", help="bank a loop's holonomy (close the gap; receipt required)")
    p_bank.add_argument("--edge", required=True)
    p_bank.add_argument("--receipt", required=True)
    p_bank.add_argument("--seat", default="zcode")
    p.add_argument("--scope", choices=("operational", "knowledge", "all"), default="operational")
    a = p.parse_args(argv)
    if a.cmd == "scan":
        print(json.dumps(scan(scope=a.scope), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "cycles":
        print(json.dumps(fundamental_cycles(scope=a.scope), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "rank":
        print(json.dumps(rank(scope=a.scope), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "spectrum":
        print(json.dumps(spectrum(scope=a.scope), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "bank":
        print(json.dumps(bank(edge=a.edge, receipt=a.receipt, seat=a.seat),
                         indent=2, ensure_ascii=False, default=str))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
