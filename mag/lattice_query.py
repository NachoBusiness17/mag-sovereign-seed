"""Queryable lattice store — nodes/edges on disk (not session DNA).

Store: memory/lattice/nodes.jsonl + edges.jsonl
Law: read-only viewport; files seeded by mag.lattice_backfill.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "lattice_query.v1"
LATTICE_DIR = ROOT / "memory" / "lattice"
NODES_PATH = LATTICE_DIR / "nodes.jsonl"
EDGES_PATH = LATTICE_DIR / "edges.jsonl"


def _rel_store_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            rows.append(o)
    return rows


def load_nodes() -> list[dict[str, Any]]:
    return _read_jsonl(NODES_PATH)


def load_edges() -> list[dict[str, Any]]:
    return _read_jsonl(EDGES_PATH)


def query_by_theme(theme: str) -> list[dict[str, Any]]:
    """Nodes whose dominant_theme matches or theme token appears in text/id."""
    t = (theme or "").strip().lower()
    if not t:
        return []
    out: list[dict[str, Any]] = []
    for n in load_nodes():
        dom = str(n.get("dominant_theme") or "").lower()
        nid = str(n.get("id") or "").lower()
        body = str(n.get("text") or n.get("unit_id") or "").lower()
        if dom == t or t in dom or t in nid or t in body:
            out.append(n)
    return out


def neighbors(node_id: str) -> dict[str, Any]:
    """Incident edges and adjacent node ids for a node."""
    nid = (node_id or "").strip()
    if not nid:
        return {"node_id": nid, "edges": [], "nodes": []}
    edges_out: list[dict[str, Any]] = []
    neighbor_ids: set[str] = set()
    for e in load_edges():
        src = str(e.get("source") or "")
        tgt = str(e.get("target") or "")
        if src == nid or tgt == nid or src.startswith(nid) or tgt.startswith(nid):
            edges_out.append(e)
            if src != nid:
                neighbor_ids.add(src)
            if tgt != nid:
                neighbor_ids.add(tgt)
    nodes_by_id = {str(n.get("id") or ""): n for n in load_nodes()}
    adj = [nodes_by_id[i] for i in sorted(neighbor_ids) if i in nodes_by_id]
    return {"node_id": nid, "edges": edges_out, "nodes": adj}


def summary() -> dict[str, Any]:
    nodes = load_nodes()
    edges = load_edges()
    kinds = Counter(str(n.get("kind") or "unknown") for n in nodes)
    themes = Counter(
        str(n.get("dominant_theme") or "—")
        for n in nodes
        if n.get("kind") == "session_knot"
    )
    edge_kinds = Counter(str(e.get("kind") or "unknown") for e in edges)
    store_exists = NODES_PATH.is_file() or EDGES_PATH.is_file()
    return {
        "schema": SCHEMA,
        "ok": True,
        "store_exists": store_exists,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "kinds": dict(kinds),
        "edge_kinds": dict(edge_kinds),
        "theme_histogram": dict(themes),
        "paths": {
            "nodes": _rel_store_path(NODES_PATH),
            "edges": _rel_store_path(EDGES_PATH),
        },
    }


def graph_viewport(*, sample_n: int = 5) -> dict[str, Any]:
    """Compact graph section for dashboard/API."""
    s = summary()
    nodes = load_nodes()
    edges = load_edges()
    return {
        "node_count": s["node_count"],
        "edge_count": s["edge_count"],
        "kinds": s.get("kinds") or {},
        "edge_kinds": s.get("edge_kinds") or {},
        "theme_histogram": s.get("theme_histogram") or {},
        "sample_nodes": nodes[:sample_n],
        "sample_edges": edges[:sample_n],
        "store_exists": s.get("store_exists"),
    }
