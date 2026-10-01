"""shadow_graph — the garbage becomes a SHADOW WORK REPOSITORY: a latent knowledge graph.

Operator (2026-08-11): "sense where else this system exists and extend the capability for latent
signals. maybe our garbage file should have its own knowledge graph as a shadow work repository to
formalize the jungian process of examining the past continuously looking to apply current knowlege
to create coherent instructions on the fly via our vmemory k8 system swarms."

THE JUNGIAN LOOP (formalized, deterministic + $0, no LLM):
  build()          -> scan the garbage/noise files (memory/ghost/noise/*.jsonl + .fp.jsonl) and build
                      a knowledge graph: nodes = significant tokens, edges = co-occurrence weight.
                      This is the SHADOW WORK REPOSITORY — the past we discarded, made navigable.
  latent_signal()  -> extend the percolator's EXPLICIT keyword lens with LATENT signals: a theme
                      hiding in the garbage (tokens whose graph frequency is high, i.e. recurring
                      discarded meaning) — what the noise keeps saying without saying.
  sense_system()   -> SENSE WHERE ELSE THIS SYSTEM EXISTS: map a latent theme to its lens + the
                      similar systems already under it (reuses novelty_lens/research_class). The
                      shadow theme is connected to the known map.
  jungal_loop()    -> the continuous process: examine the past (top latent clusters) -> apply current
                      knowledge (novelty vs the classified corpus) -> emit a COHERENT RIB instruction
                      on the fly (rib_bus.publish_rib, domain shadow) for the vmemory/k8 swarms to
                      mount + execute.

Schema: shadow_graph.v1 · deterministic + $0 · stdlib only
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "shadow_graph.v1"
NOISE_DIR = ROOT / "memory" / "ghost" / "noise"
SHADOW_DIR = ROOT / "memory" / "shadow_graph"
GRAPH_PATH = SHADOW_DIR / "graph.json"
_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_STOP = frozenset("the a an of to and or for in on at by with from as is are was were be been being "
                  "it its this that these those we you they i he she them our their your my his her "
                  "do does did not no nor so but if then than too very can will just should would "
                  "about into over after under again some any each more most other such only own same "
                  "me my follow subscribe follow me dm click link sign up".split())
MIN_FREQ = 2  # a token must appear this many times in the garbage to be a latent theme


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 2]


def _noise_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not NOISE_DIR.is_dir():
        return rows
    for f in sorted(NOISE_DIR.glob("*.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip():
                    try:
                        o = json.loads(line)
                        if isinstance(o, dict):
                            o["_src"] = f.name
                            rows.append(o)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return rows


def build(*, force: bool = False) -> dict[str, Any]:
    """Build the shadow-work knowledge graph from the garbage. Deterministic + $0."""
    if GRAPH_PATH.is_file() and not force:
        try:
            return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    rows = _noise_rows()
    node_freq: dict[str, int] = defaultdict(int)
    edges: dict[tuple[str, str], int] = defaultdict(int)
    n_discarded = 0
    for r in rows:
        sent = str(r.get("sentence") or r.get("detail") or "")
        toks = _tokens(sent)
        if not toks:
            continue
        n_discarded += 1
        for t in toks:
            node_freq[t] += 1
        for i in range(len(toks)):
            for j in range(i + 1, len(toks)):
                a, b = toks[i], toks[j]
                if a != b:
                    edges[tuple(sorted((a, b)))] += 1
    nodes = {t: c for t, c in node_freq.items() if c >= MIN_FREQ}
    # keep only edges between surviving nodes, weight = co-occurrence
    edgelist = {f"{a}__{b}": w for (a, b), w in edges.items() if a in nodes and b in nodes}
    graph = {"schema": SCHEMA, "n_discarded": n_discarded, "n_nodes": len(nodes),
             "n_edges": len(edgelist), "nodes": nodes, "edges": edgelist}
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    return graph


def latent_signal(sentence: str, *, graph: dict[str, Any] | None = None) -> dict[str, Any]:
    """LATENT signals in a discarded sentence: tokens the garbage keeps repeating (graph freq >=
    MIN_FREQ) that are NOT in the percolator's explicit lexicon. Deterministic."""
    graph = graph or build()
    nodes = graph.get("nodes") or {}
    toks = _tokens(sentence)
    latent = [t for t in toks if nodes.get(t, 0) >= MIN_FREQ]
    return {"ok": True, "schema": SCHEMA, "n_tokens": len(toks), "latent": latent,
            "latent_freqs": {t: nodes.get(t, 0) for t in latent},
            "is_latent_signal": len(latent) >= 2,
            "note": "latent signal = recurring discarded meaning, beyond the explicit keyword lens"}


def sense_system(theme: str) -> dict[str, Any]:
    """SENSE WHERE ELSE THIS SYSTEM EXISTS: map a latent theme to its lens + similar systems."""
    try:
        from mag import novelty_lens
        kl = novelty_lens.keyword_lens(theme)
        nv = novelty_lens.novelty(theme)
        return {"ok": True, "schema": SCHEMA, "theme": theme, "lens": kl["lens"],
                "kind": kl["kind"], "similar_systems": kl["similar_systems"],
                "novelty": nv["novelty"], "verdict": nv["verdict"]}
    except Exception as e:
        return {"ok": True, "schema": SCHEMA, "theme": theme, "error": str(e)[:120]}


def jungal_loop(*, top: int = 3, emit_rib: bool = True) -> dict[str, Any]:
    """The JUNGIAN LOOP: examine the past (top latent clusters) -> apply current knowledge -> emit a
    coherent RIB instruction on the fly for the vmemory/k8 swarms. Deterministic + $0."""
    graph = build()
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or {}
    # top latent clusters = highest-weight co-occurring pairs
    ranked = sorted(edges.items(), key=lambda kv: -kv[1])[:top]
    clusters = []
    for pair, w in ranked:
        a, b = pair.split("__")
        theme = f"{a} {b}"
        sensed = sense_system(theme)
        clusters.append({"pair": (a, b), "weight": w, "lens": sensed["lens"],
                         "similar_systems": sensed["similar_systems"],
                         "novelty": sensed["novelty"]})
        if emit_rib:
            try:
                from mag import rib_bus
                rib = (f"Shadow-work instruction (latent theme '{a} {b}'): apply current knowledge to "
                       f"this recurring discarded signal; route it via the {sensed['lens']} lens to "
                       f"the mirrored systems {', '.join(sensed['similar_systems'] or ['(none)'])}.")
                rib_bus.publish_rib(rib, domain="shadow", source="shadow_graph",
                                    target_rank="T2", fold=True, publish=True)
            except Exception:
                pass
    return {"ok": True, "schema": SCHEMA, "n_discarded": graph.get("n_discarded", 0),
            "n_nodes": graph.get("n_nodes", 0), "clusters": clusters, "emit_rib": emit_rib}


def status() -> dict[str, Any]:
    g = build()
    return {"ok": True, "schema": SCHEMA,
            "contract": "build()->shadow graph from garbage; latent_signal(s)->latent themes; "
                        "sense_system(theme)->where else it exists; jungal_loop()->emit RIBs on the fly",
            "cost": "deterministic + $0 (stdlib only)",
            "n_discarded": g.get("n_discarded", 0), "n_nodes": g.get("n_nodes", 0),
            "n_edges": g.get("n_edges", 0),
            "graph_path": str(GRAPH_PATH.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="shadow-graph")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "build", "latent", "sense", "jungal"])
    ap.add_argument("--text", default="", help="latent: a discarded sentence")
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "build":
        print(json.dumps(build(force=True), indent=2, default=str))
    elif a.cmd == "latent":
        print(json.dumps(latent_signal(a.text or "follow me subscribe now dm me click the link"),
                         indent=2, default=str))
    elif a.cmd == "sense":
        print(json.dumps(sense_system(a.text or "cache miss"), indent=2, default=str))
    else:
        print(json.dumps(jungal_loop(top=a.top), indent=2, default=str))
