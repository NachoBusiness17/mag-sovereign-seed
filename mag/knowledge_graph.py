"""knowledge_graph — one accurate, source-backed graph so things are 'just known spookily'.

The operator's ask (2026-08-10): "how can we use our system to produce an accurate knowledge graph
so i don't have to keep telling you to do these things they just are known spookily."

ANSWER: the substrate already exists and is content-addressed + verifiable —
  * verkle_chain.jsonl   — the shared fact ledger (every knot = a fact/event, tamper-evident)
  * code_map             — code-as-knowledge: module -> purpose -> invariants (LAW/DOCTRINE/SCHEMA)
  * skill_ledger         — case law (what worked, maps_to a module/skill)
  * memory/steal         — stolen knowledge (families + deltas)
  * ai_landscape         — the bleeding-edge registry mapped onto our modules
  * archetype_image      — the lens/archetype reading of any concept

This module TIES them into one queryable graph (nodes + source-backed edges) and adds the missing
piece: auto-consult. `known(query)` pulls the relevant subgraph for any ask and returns a compact
'we already know this' bundle — so the agent doesn't need to be re-told. `context()` turns it into
a session preamble (like cold_boot but from the whole graph). `fold()` grows the graph with each
new discovery, so knowledge accumulates and the operator never re-explains.

Deterministic, $0, no LLM. Every node carries a SOURCE (file/ref) so accuracy is grounded, not
hallucinated — 'known spookily' = 'known from the actual record.'

Schema: knowledge_graph.v1
CLI: python -m mag.knowledge_graph build | known "<query>" | context "<query>" | fold <label> <kind> "<note>" | status
"""
from __future__ import annotations

import argparse
import json
import re
import sys
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

SCHEMA = "knowledge_graph.v2"  # v2 = GraphRAG communities + Mem0 multi-signal + Letta dream
GRAPH_PATH = ROOT / "memory" / "knowledge_graph.json"

# Kinds regenerated from sources on every build(); every other kind is a hand-fold that build()
# must PRESERVE (amend-not-erase) so the weave accumulates and percolates instead of being wiped.
_COLLECTOR_KINDS = {"module", "knot", "case_law", "steal", "landscape"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


# ─────────────────────────────────────────────── node collectors (source-backed) ──
def _nodes_code() -> list[dict[str, Any]]:
    """code-as-knowledge: every mag module -> purpose + invariants (from code_map)."""
    nodes: list[dict[str, Any]] = []
    mag = ROOT / "mag"
    if not mag.is_dir():
        return nodes
    for p in sorted(mag.glob("*.py")):
        if p.name.startswith("_"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        doc = (re.search(r'"""(.*?)"""', text, re.S) or [None, ""])[1]
        purpose = ""
        invariants: list[str] = []
        for ln in (doc or "").splitlines():
            s = ln.strip()
            if not s:
                continue
            if not purpose:
                purpose = s[:160]
            if s.lower().startswith(("law", "doctrine", "schema", "invariant", "constitution", "never", "always")):
                invariants.append(s[:200])
        nodes.append({"id": f"module:{p.name}", "kind": "module", "label": p.stem,
                      "purpose": purpose, "invariants": invariants[:6],
                      "source": str(p)})
    return nodes


def _nodes_verkle() -> list[dict[str, Any]]:
    """the fact ledger: verkle knots -> theme (content-addressed)."""
    nodes: list[dict[str, Any]] = []
    for p in (ROOT / "memory" / "biography").glob("verkle_chain*.jsonl"):
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            nodes.append({"id": f"knot:{str(r.get('leaf_hash') or r.get('hash') or '')[:16]}",
                          "kind": "knot", "label": r.get("theme") or "knot",
                          "summary": str(r.get("summary") or "")[:200],
                          "tension": r.get("tension_index"),
                          "ts": r.get("ts") or r.get("t") or r.get("time") or "", "source": str(p)})
    return nodes[-400:]  # recent, bounded


def _nodes_case_law() -> list[dict[str, Any]]:
    """case law: skill_ledger moves -> signature + maps_to."""
    nodes: list[dict[str, Any]] = []
    p = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
    if not p.is_file():
        return nodes
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-300:]:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        nodes.append({"id": f"law:{str(r.get('id') or '')[:12]}", "kind": "case_law",
                      "label": r.get("title") or r.get("pattern") or r.get("id") or "law",
                      "summary": str(r.get("move") or r.get("summary") or r.get("pattern") or "")[:200],
                      "maps_to": r.get("maps_to") or r.get("skill") or "", "source": str(p)})
    return nodes


def _nodes_steal() -> list[dict[str, Any]]:
    """stolen knowledge: memory/steal docs -> family (from filename)."""
    nodes: list[dict[str, Any]] = []
    d = ROOT / "memory" / "steal"
    if not d.is_dir():
        return nodes
    for p in sorted(d.glob("*.md")):
        first = p.read_text(encoding="utf-8", errors="replace").splitlines()
        title = next((l.strip().lstrip("# ").strip() for l in first if l.strip()), p.stem)
        nodes.append({"id": f"steal:{p.stem}", "kind": "steal", "label": p.stem,
                      "summary": title[:200], "source": str(p)})
    return nodes


def _nodes_landscape() -> list[dict[str, Any]]:
    """the bleeding-edge registry: family -> we_have modules + delta."""
    nodes: list[dict[str, Any]] = []
    try:
        from mag.ai_landscape import LANDSCAPE
        for f in LANDSCAPE:
            nodes.append({"id": f"family:{f['family']}", "kind": "landscape",
                          "label": f["family"], "summary": f.get("name", ""),
                          "we_have": f.get("we_have", []),
                          "delta": f.get("delta", ""), "source": "mag/ai_landscape.py"})
    except Exception:
        pass
    return nodes


# ─────────────────────────────────────────────── graph assembly ──
def _edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for n in nodes:
        if n["kind"] == "module":
            for inv in n.get("invariants", [])[:4]:
                edges.append({"from": n["id"], "to": f"invariant:{_norm(inv)[:40]}",
                              "rel": "has_invariant", "text": inv[:120]})
        if n["kind"] == "landscape":
            for m in n.get("we_have", [])[:4]:
                edges.append({"from": n["id"], "to": f"module:{Path(str(m)).name}",
                              "rel": "already_inside", "text": str(m)[:120]})
        if n.get("maps_to"):
            edges.append({"from": n["id"], "to": f"module:{Path(str(n['maps_to'])).name}",
                          "rel": "maps_to", "text": str(n["maps_to"])[:120]})
    return edges


# ─────────────────────────────────────────────── v2: GraphRAG + Mem0 + Letta steals ──
# kind importance for multi-signal retrieval (Mem0): modules/landscape > steal > law > knot
_KIND_WEIGHT = {"module": 3, "landscape": 3, "steal": 2, "case_law": 2, "knot": 1, "doctrine": 2}


def _community_detect(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    """Deterministic community detection (label propagation) over module/invariant/landscape edges."""
    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e["from"], set()).add(e["to"])
        adj.setdefault(e["to"], set()).add(e["from"])
    ids = [n["id"] for n in nodes]
    labels = {nid: i for i, nid in enumerate(ids)}
    for _ in range(6):
        changed = False
        for nid in ids:
            nb = adj.get(nid, set())
            if not nb:
                continue
            counts: dict[int, int] = {}
            for b in nb:
                counts[labels.get(b, -1)] = counts.get(labels.get(b, -1), 0) + 1
            best = max(counts, key=lambda k: (counts[k], -k))
            if labels[nid] != best:
                labels[nid] = best
                changed = True
        if not changed:
            break
    comp: dict[int, list[str]] = {}
    for nid in ids:
        comp.setdefault(labels[nid], []).append(nid)
    mapping: dict[str, int] = {}
    for ci, members in enumerate(comp.values()):
        for nid in members:
            mapping[nid] = ci
    return mapping


def _community_summaries(nodes: list[dict[str, Any]], mapping: dict[str, int]) -> list[dict[str, Any]]:
    """Community summaries (GraphRAG): cluster nodes -> one summary per community."""
    by_comm: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        by_comm.setdefault(mapping[n["id"]], []).append(n)
    summaries = []
    for ci, members in by_comm.items():
        kinds: dict[str, int] = {}
        for m in members:
            kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
        labels = [m["label"] for m in members[:8]]
        summaries.append({"community": ci, "size": len(members), "kinds": kinds,
                          "members": [m["id"] for m in members[:14]],
                          "summary": "; ".join(labels)[:400]})
    return sorted(summaries, key=lambda s: -s["size"])


def global_search(query: str) -> dict[str, Any]:
    """GraphRAG Global Search: answer holistic questions via community summaries."""
    g = _read_graph() or build()
    nodes = g.get("nodes", []); edges = g.get("edges", [])
    mapping = _community_detect(nodes, edges)
    summaries = _community_summaries(nodes, mapping)
    q = _norm(query); qwords = set(w for w in q.split() if len(w) > 2)
    scored = []
    for s in summaries:
        hay = _norm(s["summary"])
        score = sum(1 for w in qwords if w in hay)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda t: -t[0])
    return {"ok": True, "schema": SCHEMA, "mode": "global", "hits": len(scored),
            "communities": [s for _, s in scored[:6]]}


def local_search(query: str) -> dict[str, Any]:
    """GraphRAG Local Search: seed entities -> fan out to neighbors."""
    g = _read_graph() or build()
    nodes = g.get("nodes", []); edges = g.get("edges", [])
    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e["from"], set()).add(e["to"])
        adj.setdefault(e["to"], set()).add(e["from"])
    q = _norm(query); qwords = set(w for w in q.split() if len(w) > 2)
    seeds = [n for n in nodes
             if any(w in _norm(f"{n['label']} {n.get('purpose','')} {n.get('summary','')}") for w in qwords)]
    results = []
    for s in seeds[:5]:
        neighbors = [n for n in nodes if n["id"] in adj.get(s["id"], set())][:8]
        results.append({"seed": s["label"], "seed_kind": s["kind"],
                        "neighbors": [{"id": n["id"], "label": n["label"], "kind": n["kind"]}
                                      for n in neighbors]})
    return {"ok": True, "schema": SCHEMA, "mode": "local", "seeds": len(seeds), "results": results}


def _node_text(n: dict[str, Any]) -> str:
    """The searchable haystack for a node (all text signals we index over)."""
    return _norm(f"{n['label']} {n.get('purpose','')} {n.get('summary','')} "
                 f"{' '.join(n.get('invariants',[]))} {' '.join(n.get('we_have',[]))} "
                 f"{n.get('delta','')} {n.get('maps_to','')}")


def _tokenize(text: str) -> list[str]:
    """Deterministic tokenizer: lowercase alnum runs, drop stopwords + 1-2 char tokens."""
    _STOP = {"the", "and", "for", "with", "our", "that", "this", "from", "into", "over",
             "how", "can", "you", "your", "what", "have", "has", "are", "was", "its", "not",
             "all", "any", "one", "but", "per", "via", "mag"}
    return [w for w in _norm(text).split()
            if len(w) > 2 and w not in _STOP]


def _bm25_index(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic BM25 index over the node corpus (no external deps).
    BM25 = sum over query terms of IDF * (tf*(k1+1)) / (tf + k1*(1 - b + b*dl/avgdl))."""
    k1, b = 1.2, 0.75
    docs = [_tokenize(_node_text(n)) for n in nodes]
    n_docs = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    avgdl = sum(len(d) for d in docs) / max(n_docs, 1)
    idf = {w: max(0.1, ((n_docs - f + 0.5) / (f + 0.5)) + 1.0) for w, f in df.items()}
    return {"docs": docs, "idf": idf, "avgdl": avgdl, "k1": k1, "b": b}


def _bm25_score(idx: dict[str, Any], qwords: list[str], doc: list[str]) -> float:
    """Score one document against the BM25 index."""
    dl = len(doc)
    tf: dict[str, int] = {}
    for w in doc:
        tf[w] = tf.get(w, 0) + 1
    s = 0.0
    for w in qwords:
        if w not in tf:
            continue
        idf = idx["idf"].get(w, 0.0)
        f = tf[w]
        s += idf * (f * (idx["k1"] + 1)) / (f + idx["k1"] * (1 - idx["b"] + idx["b"] * dl / max(idx["avgdl"], 1)))
    return s


def _entity_overlap(qwords: set[str], n: dict[str, Any]) -> int:
    """Entity fusion (mem0): overlap between query tokens and the node's KEY identifiers
    (label / maps_to / we_have / invariants) — links facts that share entities, not just raw text."""
    hay = _tokenize(f"{n['label']} {n.get('maps_to','')} {' '.join(n.get('we_have',[]))} "
                    f"{' '.join(n.get('invariants',[]))}")
    return sum(1 for w in qwords if w in set(hay))


def _temporal_score(n: dict[str, Any], max_i: int) -> float:
    """Temporal ranker (mem0 time-aware): later knots/case-law are 'now-er' -> ranked for the
    current state, not just date-filtered. Deterministic by chain index."""
    if n["kind"] not in ("knot", "case_law"):
        return 0.0
    i = n.get("_i", 0)
    return 0.15 * (i / max(max_i, 1))  # recency weight scales 0..0.15 with chain position


def _score_node(n: dict[str, Any], qwords: set[str], idx: dict[str, Any]) -> dict[str, Any]:
    """True multi-signal (mem0): BM25 relevance + entity overlap + kind importance + temporal.
    Returns a BREAKDOWN so retrieval can say WHY a node won (honest provenance on the X-ray)."""
    doc = idx["docs"][n.get("_i", 0)] if 0 <= n.get("_i", 0) < len(idx["docs"]) else _tokenize(_node_text(n))
    bm25 = _bm25_score(idx, list(qwords), doc)
    entity = _entity_overlap(qwords, n)
    w = _KIND_WEIGHT.get(n["kind"], 1)
    temp = _temporal_score(n, max(len(idx["docs"]) - 1, 1))
    total = bm25 * w + entity * 0.5 + temp
    return {"total": total, "bm25": round(bm25, 3), "entity": entity,
            "temporal": round(temp, 3), "kind_weight": w}


def _rank_known(query: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Shared multi-signal ranker for known()/context(). Builds the corpus once, scores all nodes,
    returns (top nodes w/ why, diagnostics)."""
    q = _norm(query)
    qwords = set(_tokenize(query))
    nodes = build()["nodes"]
    for i, n in enumerate(nodes):
        n["_i"] = i
    idx = _bm25_index(nodes)
    scored = []
    for n in nodes:
        sc = _score_node(n, qwords, idx)
        if sc["total"] > 0:
            scored.append((sc["total"], sc, n))
    scored.sort(key=lambda t: -t[0])
    top = [dict(n, _why=sc, _score=round(tot, 3)) for tot, sc, n in scored[:12]]
    return top, {"nodes": len(nodes), "qwords": sorted(qwords)[:12]}


def capability_atom(*, domain: str = "general") -> dict[str, Any]:
    """MAG'S BPE SURFACE — the ONE atomic handle for this capability (operator law: new capabilities
    are addressable as atoms in our tokenizer; FACTS are NOT steered, only CAPABILITIES are).

    SELF-STEAL correction (2026-08-15, sacred-cow audit): mint_ribs() folded every retrieval hit
    into a `KNOWN[...]` steer atom — WRONG. RIBs are INSTRUCTIONS; a retrieval hit is a FACT. Seats
    should not carry per-hit facts in compiled steer. The honest surface is ONE capability handle the
    steering can reference ("consult multi-signal retrieval"), not N injected facts.

    This mints a single RIB atom advertising the multi-signal retrieval CAPABILITY so a seat can be
    steered to it — deterministic, deduped by content hash, $0."""
    atom = ("CAPABILITY: consult knowledge_graph.known()/context() for source-backed multi-signal "
            "retrieval (BM25 relevance + entity overlap + temporal ranker), each hit annotated with "
            "a _why breakdown; facts live in the knowledge layer, instructions in the atom layer.")
    try:
        from mag import rib_bus
        r = rib_bus.publish_rib(atom, domain=domain, source="knowledge_graph.capability",
                                target_rank="T2", fold=True, publish=True)
        return {"ok": True, "schema": SCHEMA, "mode": "capability_atom", "domain": domain,
                "key": r.get("key", ""), "verkle": bool(r.get("verkle", {}).get("ok", r.get("verkle"))),
                "published": r.get("published", False),
                "note": "ONE capability atom minted (not per-hit facts) — seats are steered TO the "
                        "retrieval capability; facts stay in the knowledge layer"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "mode": "capability_atom", "error": str(e)[:120]}


def dream(prune: bool = True) -> dict[str, Any]:
    """LETTA 'dreaming': offline consolidation of the graph while idle. Reclusters, summarizes,
    prunes duplicate knots/case-law, and folds a 'dreamed' community summary. This is the aimbotting
    engine — the graph self-maintains toward accuracy with zero operator effort."""
    g = build()
    nodes = g.get("nodes", []); edges = g.get("edges", [])
    mapping = _community_detect(nodes, edges)
    summaries = _community_summaries(nodes, mapping)
    pruned = 0
    if prune:
        seen: set[tuple[str, str]] = set()
        kept: list[dict[str, Any]] = []
        for i, n in enumerate(nodes):
            n["_i"] = i
            if n["kind"] in ("knot", "case_law"):
                key = (n["kind"], _norm(str(n.get("summary") or n["label"]))[:80])
                if key in seen:
                    pruned += 1
                    continue
                seen.add(key)
            kept.append(n)
        nodes = kept
    # persist community-augmented graph (versioned, content-addressed, amend-not-erase)
    g["nodes"] = nodes
    g["communities"] = summaries
    g["last_dream"] = _now()
    GRAPH_PATH.write_text(json.dumps(g, ensure_ascii=False, default=str), encoding="utf-8")
    try:
        from mag.schema_registry import checkpoint
        checkpoint("knowledge_graph", {"nodes": len(nodes), "edges": len(edges),
                                        "communities": len(summaries), "pruned": pruned},
                   label="dream")  # versioned history: LATEST + versions/, amend-never-erase
    except Exception:
        pass
    # fold a dreamed summary as a doctrine node so the consolidation itself becomes known
    fold("dreamed-communities", "doctrine",
         f"dreamed {len(summaries)} community/communities over {len(nodes)} node(s); pruned {pruned} duplicate(s)",
         source="dream")
    return {"ok": True, "schema": SCHEMA, "mode": "dream", "communities": len(summaries),
            "nodes": len(nodes), "edges": len(edges), "pruned": pruned}


def build() -> dict[str, Any]:
    nodes = (_nodes_code() + _nodes_verkle() + _nodes_case_law() + _nodes_steal() + _nodes_landscape())
    # PRESERVE hand-folded nodes (doctrine etc.) — build() must NOT clobber the weave.
    # Collector kinds are regenerated from sources each build; every other kind is a hand-fold
    # that accumulates and must survive rebuilds (amend-not-erase), else percolation is impossible.
    folded = [n for n in _read_graph().get("nodes", []) if n.get("kind") not in _COLLECTOR_KINDS]
    seen = {n["id"] for n in nodes}
    for n in folded:
        if n.get("id") not in seen:
            nodes.append(n)
    edges = _edges(nodes)
    graph = {"schema": SCHEMA, "ts": _now(), "nodes": nodes, "edges": edges}
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, default=str), encoding="utf-8")
    graph["counts"] = _counts(nodes)
    return graph


def _counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    c: dict[str, int] = {}
    for n in nodes:
        c[n["kind"]] = c.get(n["kind"], 0) + 1
    return c


# ─────────────────────────────────────────────── auto-consult (the 'spookily known') ──
def known(query: str) -> dict[str, Any]:
    """Pull the relevant subgraph for any ask — what we ALREADY know, source-backed.
    v2 multi-signal (mem0): BM25 relevance + entity overlap + kind importance + temporal ranker,
    each node annotated with a _why breakdown so the answer is honest about WHY it won."""
    top, diag = _rank_known(query)
    lens: dict[str, Any] = {}
    try:
        from mag.archetype_image import classify, ARCHETYPES
        name = classify(query)
        a = ARCHETYPES.get(name) or {}
        lens = {"archetype": a.get("canon", name), "lens": a.get("lens"),
                "shadow": a.get("shadow"), "essence": a.get("essence"), "minds": a.get("minds", [])}
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "query": query, "hits": len(top),
            "mode": "multi-signal-v2", "known": top, "lens": lens, "diagnostics": diag,
            "summary": f"already know {len(top)} source-backed node(s) about this; nothing to re-derive",
            "accuracy": "every node carries a source (verkle/code/ledger/steal/landscape); each hit "
                        "carries a _why breakdown (bm25/entity/temporal/kind_weight)"}


def context(query: str, max_chars: int = 2400) -> str:
    """A compact session preamble from the graph — inject so the agent 'just knows'."""
    k = known(query)
    if not k.get("known"):
        return f"# Known — nothing on '{query}'\n\nBoot cold on this."
    lines = [f"# Known (auto-consulted knowledge graph) — '{query}'", ""]
    ln = k.get("lens") or {}
    if ln:
        lines.append(f"- **Lens:** {ln.get('archetype')} / {ln.get('lens')} — {ln.get('essence')} · shadow: {ln.get('shadow')}")
    for n in k["known"][:8]:
        body = n.get("purpose") or n.get("summary") or n.get("label")
        lines.append(f"- [{n['kind']}] **{n.get('label')}**: {str(body)[:180]}")
    text = "\n".join(lines)
    return text if len(text) <= max_chars else text[:max_chars] + " …"


def fold(label: str, kind: str, note: str, source: str = "session") -> dict[str, Any]:
    """Grow the graph with a new discovered node (knowledge accumulates)."""
    g = _read_graph()
    nid = f"{kind}:{_norm(label)[:40]}"
    if any(n["id"] == nid for n in g.get("nodes", [])):
        return {"ok": True, "schema": SCHEMA, "id": nid, "already_present": True}
    g.setdefault("nodes", []).append({"id": nid, "kind": kind, "label": label,
                                      "summary": note[:200], "source": source})
    GRAPH_PATH.write_text(json.dumps(g, ensure_ascii=False, default=str), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "id": nid, "already_present": False,
            "counts": _counts(g.get("nodes", []))}


def _read_graph() -> dict[str, Any]:
    if GRAPH_PATH.is_file():
        try:
            return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {"nodes": [], "edges": []}


def status() -> dict[str, Any]:
    g = build()
    return {"ok": True, "schema": SCHEMA, "counts": g["counts"], "n_edges": len(g.get("edges", [])),
            "graph_path": str(GRAPH_PATH)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="knowledge_graph", description="accurate source-backed knowledge graph + auto-consult")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("build")
    k = sub.add_parser("known"); k.add_argument("query", nargs="+")
    c = sub.add_parser("context"); c.add_argument("query", nargs="+")
    g = sub.add_parser("global"); g.add_argument("query", nargs="+")
    l = sub.add_parser("local"); l.add_argument("query", nargs="+")
    sub.add_parser("dream")
    f = sub.add_parser("fold"); f.add_argument("label"); f.add_argument("kind"); f.add_argument("note", nargs="+")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "build":
        g = build(); print(json.dumps({"counts": g["counts"], "n_edges": len(g.get("edges", []))}, indent=2))
    elif a.cmd == "known":
        print(json.dumps(known(" ".join(a.query)), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "context":
        print(context(" ".join(a.query)))
    elif a.cmd == "global":
        print(json.dumps(global_search(" ".join(a.query)), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "local":
        print(json.dumps(local_search(" ".join(a.query)), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "dream":
        print(json.dumps(dream(), indent=2, ensure_ascii=False))
    elif a.cmd == "fold":
        print(json.dumps(fold(a.label, a.kind, " ".join(a.note)), indent=2, ensure_ascii=False))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
