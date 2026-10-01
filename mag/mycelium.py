"""mycelium — Phase 1 of the persistent mycelial-republic OS: ONE unified, self-scoring
weighted graph store that survives restarts.

STEAL (see memory/steal/MYCELIAL_REPUBLIC_OS_STEAL_20260809.md):
  - bmas `salience.py`  -> deterministic salience: confidence + recency(0.7^gap) + refs-boost
                          - contradiction penalty. Edges sharpen with use AND prune failed paths.
  - blackboard-core `persistence/` -> pluggable durable backend; jsonl live + snapshot dual-write.
  - agentswarm `memory.ts` -> cross-run durable memory so the OS never boots from zero.
  - flock `ConsumptionRecord` -> log which agent consumed which artifact (learning signal).

The republic OS needs ONE living graph that every agent writes to and reads from as its
primary coordination surface. This unifies idea_graph + research_lens + vector_map concepts
into a single weighted directed graph: nodes = seats/artifacts/concepts; edges = handoffs /
supports / contradicts / consumption / produced, each with weight + success/failure counts
+ last_used + protected. Salience scoring makes it self-reinforcing and self-pruning.

Schema: mycelium.v1
CLI:  python -m mag.mycelium status | boot | link <src> <dst> [--type T] | reinforce <src> <dst> [--reward R] | adopt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "mycelium.v1"
MYC = ROOT / "memory" / "mycelium"
NODES = MYC / "nodes.jsonl"
EDGES = MYC / "edges.jsonl"
SNAPSHOT = MYC / "graph_snapshot.json"

# Salience weights (bmas): confidence, recency decay, refs-in boost, contradiction penalty.
W_CONF = 0.45
W_REC = 0.30
W_REF = 0.15
W_PEN = 0.20
REC_DECAY = 0.7  # recency factor per time-unit gap
PRUNE_FLOOR = 0.15  # below this salience + not protected -> decayed
REINFORCE_ALPHA = 0.2  # w += alpha*(reward)
REINFORCE_GAMMA = 0.1  # w -= gamma*(cost)
PROTECTED_FLOOR = 0.4  # protected edges never fall below this

EDGE_TYPES = frozenset({
    "supports", "contradicts", "extends", "handoff", "consumption", "produced",
    "depends", "related", "evidence_for", "acted_on", "same_thread",
})
NODE_TYPES = frozenset({"seat", "artifact", "concept", "claim", "open_loop", "evidence", "project"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch() -> float:
    return time.time()


def _uid(prefix: str) -> str:
    import uuid
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex[:6]}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _load_nodes() -> dict[str, dict[str, Any]]:
    return {str(n.get("id")): n for n in _read_jsonl(NODES)}


def _load_edges() -> list[dict[str, Any]]:
    return _read_jsonl(EDGES)


# ------------------------------------------------------------------ nodes ----
def add_node(title: str, *, ntype: str = "concept", label: str = "", trust: float = 0.5,
             protected: bool = False, tags: list[str] | None = None, body: str = "") -> dict[str, Any]:
    ntype = ntype if ntype in NODE_TYPES else "concept"
    node = {
        "schema": SCHEMA, "id": _uid("n"), "type": ntype, "title": (title or "")[:300],
        "label": (label or "")[:200], "trust": float(trust), "activation": 0.0,
        "protected": bool(protected), "tags": list(tags or [])[:20], "body": (body or "")[:4000],
        "ts": _now(),
    }
    _append(NODES, node)
    return node


def get_node(node_id: str) -> dict[str, Any] | None:
    return _load_nodes().get(str(node_id))


# ------------------------------------------------------------------ edges ----
def _new_edge(src: str, dst: str, etype: str, note: str = "", protected: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "id": _uid("e"), "src": str(src), "dst": str(dst),
        "type": etype if etype in EDGE_TYPES else "related", "note": (note or "")[:500],
        "weight": 0.5, "success_count": 0, "failure_count": 0, "contradictions": 0,
        "refs_in": 0, "last_used": _epoch(), "created": _now(), "protected": bool(protected),
    }


def link(src: str, dst: str, *, etype: str = "related", note: str = "", protected: bool = False) -> dict[str, Any]:
    if not get_node(src) or not get_node(dst):
        return {"ok": False, "error": "src or dst node not found"}
    edge = _new_edge(src, dst, etype, note, protected)
    _append(EDGES, edge)
    return {"ok": True, "edge": edge}


def salience(edge: dict[str, Any], now: float | None = None) -> float:
    """Deterministic salience (bmas): confidence + recency + refs - contradiction."""
    now = now if now is not None else _epoch()
    last = float(edge.get("last_used") or now)
    gap = max(0.0, now - last)
    rec = REC_DECAY ** gap  # recency decays with age
    conf = min(1.0, float(edge.get("weight") or 0) + float(edge.get("success_count") or 0) * 0.05)
    refs = min(1.0, int(edge.get("refs_in") or 0) / 3.0)
    pen = min(1.0, float(edge.get("contradictions") or 0) / 3.0)
    s = W_CONF * conf + W_REC * rec + W_REF * refs - W_PEN * pen
    return round(max(0.0, s), 4)


def reinforce(src: str, dst: str, *, etype: str = "related", reward: float = 1.0,
              cost: float = 0.1, consumed: bool = False) -> dict[str, Any]:
    """Mycelial reinforcement: w += alpha*reward - gamma*cost; bump success/refs; protected floor.
    If consumed=True, records a consumption edge (flock) — the learning signal."""
    edges = _load_edges()
    target = None
    for e in edges:
        if str(e.get("src")) == str(src) and str(e.get("dst")) == str(dst) and \
           (etype == "any" or e.get("type") == etype):
            target = e
            break
    if target is None:
        lk = link(src, dst, etype=etype if etype != "any" else "related")
        if not lk.get("ok"):
            return lk
        target = lk["edge"]
        # link() appends to the file but not to the in-memory list; add it so the
        # subsequent _rewrite_edges() doesn't erase the freshly-created edge.
        edges.append(target)
    if consumed:
        target["type"] = "consumption"
        target["refs_in"] = int(target.get("refs_in") or 0) + 1
    target["success_count"] = int(target.get("success_count") or 0) + 1
    target["last_used"] = _epoch()
    w = float(target.get("weight") or 0) + REINFORCE_ALPHA * float(reward) - REINFORCE_GAMMA * float(cost)
    floor = PROTECTED_FLOOR if target.get("protected") else PRUNE_FLOOR
    target["weight"] = round(max(floor, w), 4)
    target["salience"] = salience(target)
    # rewrite edge (jsonl is append-only; replace by rewriting the file)
    _rewrite_edges(edges)
    return {"ok": True, "edge": target, "salience": target["salience"]}


def contradict(src: str, dst: str, *, etype: str = "contradicts") -> dict[str, Any]:
    """Record a contradiction -> penalty on the edge (self-pruning)."""
    edges = _load_edges()
    for e in edges:
        if str(e.get("src")) == str(src) and str(e.get("dst")) == str(dst):
            e["contradictions"] = int(e.get("contradictions") or 0) + 1
            e["failure_count"] = int(e.get("failure_count") or 0) + 1
            e["salience"] = salience(e)
            break
    _rewrite_edges(edges)
    return {"ok": True}


def _rewrite_edges(edges: list[dict[str, Any]]) -> None:
    MYC.mkdir(parents=True, exist_ok=True)
    with EDGES.open("w", encoding="utf-8") as f:
        for e in edges:
            f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")


def neighborhood(node_id: str, *, depth: int = 1) -> dict[str, Any]:
    nodes = _load_nodes()
    edges = _load_edges()
    if str(node_id) not in nodes:
        return {"ok": False, "error": f"not found: {node_id}"}
    seen = {str(node_id)}
    frontier = {str(node_id)}
    linked = []
    for _ in range(max(1, int(depth))):
        nxt: set[str] = set()
        for e in edges:
            s, d = str(e.get("src")), str(e.get("dst"))
            if s in frontier or d in frontier:
                linked.append(e)
                if s not in seen:
                    nxt.add(s)
                if d not in seen:
                    nxt.add(d)
        seen |= nxt
        frontier = nxt
        if not frontier:
            break
    return {"ok": True, "root": nodes[str(node_id)], "nodes": [nodes[i] for i in seen if i in nodes],
            "edges": linked, "n_nodes": len(seen), "n_edges": len(linked)}


# ---------------------------------------------------------------- durability ----
def dual_write() -> dict[str, Any]:
    """Dual-write durability: hot jsonl + cold snapshot so history survives restarts."""
    MYC.mkdir(parents=True, exist_ok=True)
    snap = {"schema": SCHEMA, "ts": _now(), "nodes": _read_jsonl(NODES), "edges": _read_jsonl(EDGES)}
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, default=str), encoding="utf-8")
    return {"ok": True, "snapshot": str(SNAPSHOT), "nodes": len(snap["nodes"]), "edges": len(snap["edges"])}


def boot() -> dict[str, Any]:
    """Boot/rehydrate the graph from disk so the OS reconstitutes after restart (never zero)."""
    if SNAPSHOT.is_file():
        try:
            snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
            # rehydrate: ensure jsonl is current from snapshot if nodes/edges missing
            if not NODES.is_file() and snap.get("nodes"):
                NODES.parent.mkdir(parents=True, exist_ok=True)
                with NODES.open("w", encoding="utf-8") as f:
                    for n in snap["nodes"]:
                        f.write(json.dumps(n, ensure_ascii=False, default=str) + "\n")
            if not EDGES.is_file() and snap.get("edges"):
                EDGES.parent.mkdir(parents=True, exist_ok=True)
                with EDGES.open("w", encoding="utf-8") as f:
                    for e in snap["edges"]:
                        f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass
    return {"ok": True, "action": "boot", "nodes": len(_load_nodes()), "edges": len(_load_edges()),
            "snapshot": str(SNAPSHOT)}


def decay(*, threshold: float = PRUNE_FLOOR) -> dict[str, Any]:
    """Self-pruning: mark low-salience, non-protected edges as decayed (log only, don't hard-delete)."""
    edges = _load_edges()
    decayed = []
    for e in edges:
        if e.get("protected"):
            continue
        if salience(e) < threshold:
            e["decayed"] = True
            e["decayed_at"] = _now()
            decayed.append(e.get("id"))
    _rewrite_edges(edges)
    return {"ok": True, "decayed": len(decayed), "threshold": threshold}


# ------------------------------------------------------------------- adopt ----
def adopt_from_idea_graph() -> dict[str, Any]:
    """Seed the unified graph from existing idea_graph nodes/edges (unification)."""
    adopted_n, adopted_e = 0, 0
    try:
        from mag import idea_graph as ig
        for n in ig.load_nodes() or []:
            add_node(str(n.get("title") or n.get("id"))[:300], ntype="claim" if n.get("type") in ("claim", "evidence") else "concept",
                     tags=list(n.get("tags") or []) + ["adopted:idea_graph"], body=str(n.get("body") or "")[:2000])
            adopted_n += 1
        for e in ig.load_edges() or []:
            s, d = str(e.get("src")), str(e.get("dst"))
            if s and d:
                link(s, d, etype=str(e.get("type") or "related"), note=str(e.get("note") or ""))
                adopted_e += 1
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200], "adopted_n": adopted_n, "adopted_e": adopted_e}
    dual_write()
    return {"ok": True, "adopted_nodes": adopted_n, "adopted_edges": adopted_e}


# ------------------------------------------------------------------ status ----
def status() -> dict[str, Any]:
    boot()
    nodes = _load_nodes()
    edges = _load_edges()
    scored = sorted(((salience(e), e) for e in edges), key=lambda x: -x[0])[:8]
    trust_avg = round(sum(float(n.get("trust") or 0) for n in nodes.values()) / max(1, len(nodes)), 3)
    return {
        "schema": SCHEMA, "ok": True,
        "nodes": len(nodes), "edges": len(edges),
        "n_seats": sum(1 for n in nodes.values() if n.get("type") == "seat"),
        "n_artifacts": sum(1 for n in nodes.values() if n.get("type") == "artifact"),
        "avg_trust": trust_avg,
        "decayed": sum(1 for e in edges if e.get("decayed")),
        "top_salience": [{"id": e["id"], "type": e["type"], "weight": e["weight"],
                          "salience": s} for s, e in scored],
        "store": str(MYC), "ts": _now(),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="mycelium", description="Unified self-scoring mycelium graph (republic OS Phase 1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="graph state")
    sub.add_parser("boot", help="rehydrate from snapshot")
    sub.add_parser("adopt", help="seed from idea_graph")
    p_link = sub.add_parser("link", help="link two nodes")
    p_link.add_argument("src"); p_link.add_argument("dst"); p_link.add_argument("--type", default="related")
    p_reinf = sub.add_parser("reinforce", help="reinforce an edge")
    p_reinf.add_argument("src"); p_reinf.add_argument("dst"); p_reinf.add_argument("--reward", type=float, default=1.0)
    sub.add_parser("decay", help="self-prune low-salience edges")
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif args.cmd == "boot":
        print(json.dumps(boot(), indent=2, default=str))
    elif args.cmd == "adopt":
        print(json.dumps(adopt_from_idea_graph(), indent=2, default=str)[:4000])
    elif args.cmd == "link":
        print(json.dumps(link(args.src, args.dst, etype=args.type), indent=2, default=str)[:2000])
    elif args.cmd == "reinforce":
        print(json.dumps(reinforce(args.src, args.dst, reward=args.reward), indent=2, default=str)[:2000])
    elif args.cmd == "decay":
        print(json.dumps(decay(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["add_node", "link", "salience", "reinforce", "contradict", "neighborhood",
           "dual_write", "boot", "decay", "adopt_from_idea_graph", "status", "main"]
