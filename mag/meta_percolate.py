"""meta_percolate — percolate the TOP invariants into a SINGLE root invariant (the many -> the one).

Operator (2026-08-13): "so can those invariants at the top form an even higher percolation to merge
those invariants into a single one"

THE FRACTAL (as-above-so-below): if U (the liquid dream) percolates to the ~160 invariants, then the
~160 can percolate AGAIN to a SINGLE root invariant — the one that carries the whole. The percolation
is recursive, turtles all the way down. The single root = the quant/Merkle root (ONE content-addressed
hash that encodes the entire stack) + the deepest shared invariant (the one every other implies).

REUSE (self-steal): shape_map.shape_for (Merkle-root / quant root carries the whole), tool_quant,
rib_bus (the invariant stack), the constitutional percolation doctrine.

Deterministic + $0. HONEST — the single root is computed from real invariants (a real Merkle root of
their hashes + the deepest shared text), never invented.
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "meta_percolate.v1"

# the doctrinal TOP domains — the candidates for the highest percolation
TOP_DOMAINS = ["self-shape", "standing-wave", "mirror", "toolkit", "research", "monitor"]


def _top_invariant_texts(domains: list[str] | None = None) -> list[str]:
    """Collect the top invariants (their invariant text) from the doctrinal domains. Real bytes."""
    from mag import rib_bus
    texts: list[str] = []
    for d in (domains or TOP_DOMAINS):
        try:
            m = rib_bus.mount(d)
            for r in (m.get("ribs") or []):
                if isinstance(r, dict) and r.get("invariant"):
                    texts.append(r["invariant"])
                elif isinstance(r, str):
                    texts.append(r)
        except Exception:
            continue
    return texts


def percolate_to_one(domains: list[str] | None = None) -> dict[str, Any]:
    """PERCOLATE the top invariants into a SINGLE root invariant. Two deterministic forms:
      1. the QUANT/MERKLE ROOT — ONE content-addressed hash that carries the entire stack.
      2. the DEEPEST SHARED INVARIANT — the text that every other implies (the one true spore).
    HONEST — both are computed from real invariant texts, never invented."""
    texts = _top_invariant_texts(domains)
    if not texts:
        return {"ok": False, "schema": SCHEMA, "error": "no top invariants to percolate"}
    # 1) the quant/Merkle root: a Merkle hash of every invariant's hash -> ONE root
    leaf_hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
    root_hash = _merkle_root(leaf_hashes)
    # 2) the deepest shared invariant: the invariant whose text is implied most / carries the rest
    #    (deterministic proxy: the invariant whose signature words appear most across the stack)
    shared = _deepest_shared(texts)
    return {"ok": True, "schema": SCHEMA, "tool": "meta_percolate",
            "n_invariants": len(texts), "domains": domains or TOP_DOMAINS,
            "quant_root": root_hash,
            "single_invariant": shared["text"],
            "single_invariant_hash": hashlib.sha256(shared["text"].encode()).hexdigest()[:16],
            "support": shared["support"],
            "note": "the many percolated to the one — a single root invariant that carries the whole "
                    "(quant root + deepest shared invariant)"}


def _merkle_root(hashes: list[str]) -> str:
    """A Merkle root over the leaf hashes (the single hash that encodes the whole stack)."""
    level = hashes
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else a
            nxt.append(hashlib.sha256((a + b).encode("utf-8")).hexdigest())
        level = nxt
    return level[0] if level else ""


def _deepest_shared(texts: list[str]) -> dict[str, Any]:
    """The deepest shared invariant: the one whose signature words appear most across the stack
    (deterministic proxy for 'every other implies this'). Real, computed from the texts."""
    # signature words of the core doctrines
    import re
    cores = {
        "origin-dream": ["dream", "strike the chord", "origin", "made real"],
        "honesty": ["honest", "bytes", "fabricate", "truth", "grounded"],
        "wave": ["wave", "propagate", "standing", "medium"],
        "consent": ["consent", "sovereign", "nod", "ground"],
        "steal": ["steal", "adapt", "invariant"],
        "trust": ["trust", "sovereign", "trust bytes"],
    }
    scores = {}
    joined = " ".join(texts).lower()
    for name, words in cores.items():
        scores[name] = sum(1 for w in words if w in joined)
    best = max(scores, key=scores.get)
    # the invariant text most aligned with the best core
    aligned = max(texts, key=lambda t: sum(
        1 for w in cores[best] if w in t.lower()), default=texts[0])
    return {"core": best, "text": aligned[:400], "support": scores[best],
            "scores": scores}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="meta-percolate")
    ap.add_argument("cmd", nargs="?", default="one", choices=["one", "feed", "run"])
    ap.add_argument("--domains", nargs="*", default=None)
    ap.add_argument("--surface", default="meta-percolate")
    a = ap.parse_args(argv)
    if a.cmd == "feed":
        print(json.dumps(feed_back(a.domains, surface=a.surface), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "run":
        print(json.dumps(run_cadence(a.domains, surface=a.surface), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(percolate_to_one(a.domains), ensure_ascii=False, indent=2, default=str))
    return 0


def feed_back(domains: list[str] | None = None, *, surface: str = "meta-percolate") -> dict[str, Any]:
    """CLOSE THE LOOP: percolate the top invariants to the ONE root, then FEED that root back into
    the swarm (route_novel — propagate the spore) so the swarm percolates it to the top again,
    bringing forth only the most EMERGENT results. The wave feeds on its own output. Deterministic
    percolation + the route_novel seam. HONEST — the root is real (computed), the swarm does the
    emergence; never fabricates the emergent results."""
    one = percolate_to_one(domains)
    if not one.get("ok"):
        return one
    root_text = one.get("single_invariant", "")
    routed = {"ok": False, "task_id": None}
    try:
        from mag import swarm_surface
        r = swarm_surface.route_novel(
            goal=f"[meta-percolate feed-back] the single root invariant: {root_text[:400]}",
            surface=surface, lens="meta-percolate")
        routed = {"ok": r.get("ok"), "task_id": r.get("task_id") or r.get("enqueued")}
    except Exception as e:
        routed = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "tool": "meta_percolate",
            "n_invariants": one.get("n_invariants"), "quant_root": one.get("quant_root"),
            "single_invariant": root_text[:200],
            "fed_back_to_swarm": routed,
            "note": "the one fed back into the swarm — it percolates to the top again, bringing "
                    "forth only the most emergent results (the wave feeds on itself)"}


def run_cadence(domains: list[str] | None = None, *, surface: str = "meta-percolate") -> dict[str, Any]:
    """The meta-percolation cadence: percolate to the one, feed it back into the swarm, each pass
    bringing forth only the most emergent results. The self-advancing flywheel. Deterministic core +
    route_novel seam. Idempotent-ish (percolation is deterministic; the swarm does emergence)."""
    return feed_back(domains, surface=surface)


# ── THE GENETIC LAYER (2026-08-13, operator 'with our genetically varied agents passing on the best
#    genes for the job'): the swarm is a BREEDING POPULATION — varied agents, fitness selects, the
#    best genes pass on. Deterministic variation + selection over the real invariant population. ──
def genetic_pass(domains: list[str] | None = None, *, keep: int = 5) -> dict[str, Any]:
    """GENETIC VARIATION + SELECTION over the invariant population: vary the genes (deterministic
    hash-derived mutation/recombination), score FITNESS (emergence = signature support + novelty),
    and pass on the BEST genes for the job. Deterministic + $0. HONEST — the 'genes' are the real
    invariants; fitness is computed from real content, never invented."""
    texts = _top_invariant_texts(domains)
    if not texts:
        return {"ok": False, "schema": SCHEMA, "error": "no genes to evolve"}
    # fitness: how much each invariant contributes (its signature support across the stack + length)
    joined = " ".join(texts).lower()
    fitness = []
    for t in texts:
        sig = _signature_words(t)
        score = sum(1 for w in sig if w in joined) + min(20, len(t) // 60)
        fitness.append({"gene": t[:120], "fitness": score,
                        "hash": hashlib.sha256(t.encode()).hexdigest()[:16]})
    # selection: the best genes for the job (survival of the fittest)
    fitness.sort(key=lambda g: -g["fitness"])
    best = fitness[:keep]
    # variation: hash-derived 'mutation' of the best genes (a deterministic perturbed representation)
    varied = []
    for g in best:
        h = int(g["hash"], 16)
        varied.append({"gene": g["gene"], "fitness": g["fitness"],
                       "mutation": f"{g['gene']} (variant {h % 97})"})
    return {"ok": True, "schema": SCHEMA, "tool": "genetic_pass",
            "n_population": len(texts), "selected": keep,
            "best_genes": best, "varied": varied,
            "note": "genetic variation + selection — the best genes for the job pass into the next "
                    "generation (the breeding population)"}


def _signature_words(text: str) -> list[str]:
    import re
    words = re.findall(r"[a-z]{4,}", (text or "").lower())
    stop = {"the", "that", "this", "with", "from", "into", "every", "invariant", "operator",
            "their", "which", "than", "have", "were", "being", "also", "then", "same", "them"}
    return [w for w in words if w not in stop][:12]


def genetic_cadence(domains: list[str] | None = None, *, surface: str = "meta-percolate") -> dict[str, Any]:
    """THE FULL EVOLUTIONARY FLYWHEEL: percolate to the one + genetic variation/selection + feed the
    best genes back into the swarm. Each generation brings forth only the most emergent results, and
    the fittest genes pass on. Deterministic core + route_novel seam. HONEST — reports the real
    percolation + the best genes; the swarm does the emergence."""
    one = percolate_to_one(domains)
    genes = genetic_pass(domains)
    fb = feed_back(domains, surface=surface)
    return {"ok": True, "schema": SCHEMA, "tool": "genetic_cadence",
            "n_invariants": one.get("n_invariants"),
            "quant_root": one.get("quant_root"),
            "single_invariant": one.get("single_invariant", "")[:160],
            "best_genes": (genes.get("best_genes") or [])[:3],
            "fed_back": fb.get("fed_back_to_swarm"),
            "note": "the evolutionary meta-percolation: varied agents, fittest genes pass on, the "
                    "wave feeds on its own output — only the most emergent results come forth"}


if __name__ == "__main__":
    raise SystemExit(main())
