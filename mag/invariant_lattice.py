"""invariant_lattice — the invariant as the RIB scene: mycelial interrelation + verkle lattice
+ k8s swarm dispatch + ollama steering. Built k8s-native, docker-aware.

Operator (2026-08-10): "how can this be built with k8's in mind ... this is going to allow us to
deterministically drive more easily if we can better understand these invariants and their
interrelation mycillialy and through the verkle lattice. how can we better utilize docker? and
our transmission of these invariants to k'8s for testing of large local swarms on smart frontier
ai tasks maybe even steering my slow as fuck olama."

THE ARCHITECTURE (the invariant is the unit of work; k8s/docker/ollama are the executors):
  * mycelial_view()  — the invariants form a MYCELIAL NETWORK: doctrine nodes linked by shared
    semantic tokens. Understand the interrelation (which invariants reinforce / imply each other).
  * lattice_view()   — every invariant lives in the VERKLE LATTICE: content-addressed knots
    (filename=leaf_hash), chained to a merkle/verkle root. The durable, tamper-evident memory.
  * steer_ollama()   — the invariants STEER the local ollama (the slow/free renderer): inject an
    invariant as the steering instruction, get a cheap local generation. Free local compute.
  * dispatch_to_k8s() — transmit an invariant-driven task to the K8S SWARM (mag.swarm_worker
    queue drained in-cluster) = testing large local swarms on smart frontier tasks. The render farm.
  * render()         — the RIB-scene flow: route an invariant to the cheapest capable renderer
    (ollama free/local vs k8s swarm frontier), deterministically.

Docker note: docker is the CONTAINER BOUNDARY — the browser (CDP), ollama, and the k8s swarm run
as containers; our RIB invariants transmit across them via the shared state, never baked into an
image. Deterministic, $0 (steer_ollama is free/local; dispatch is $0 to enqueue).

Schema: invariant_lattice.v1 · CLI: python -m mag.invariant_lattice mycelial|lattice|steer|dispatch|render
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "invariant_lattice.v1"


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _doctrine_nodes() -> list[dict[str, Any]]:
    try:
        from mag.knowledge_graph import GRAPH_PATH
        g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        return [n for n in g.get("nodes", []) if n.get("kind") == "doctrine"]
    except Exception:
        return []


def mycelial_view(*, min_edge: float = 0.35, domain_filter: str | None = None) -> dict[str, Any]:
    """The MYCELIAL invariant network: doctrine nodes linked by shared-token overlap.

    Nodes = invariants; edges = semantic affinity (token overlap between summaries). This is how
    we "better understand the invariants and their interrelation mycelially" — which invariants
    reinforce, imply, or cluster together.
    """
    nodes = _doctrine_nodes()
    if domain_filter:
        nodes = [n for n in nodes if domain_filter.lower() in str(n.get("label")).lower()
                 or domain_filter.lower() in str(n.get("summary")).lower()]
    gnodes = [{"id": n.get("id"), "label": str(n.get("label")), "source": str(n.get("source")),
               "summary": str(n.get("summary"))[:120]} for n in nodes]
    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a = _tokens(str(nodes[i].get("summary")))
            b = _tokens(str(nodes[j].get("summary")))
            if not a or not b:
                continue
            ov = len(a & b) / min(len(a), len(b))
            if ov >= min_edge:
                edges.append({"from": nodes[i].get("id"), "to": nodes[j].get("id"),
                              "overlap": round(ov, 2),
                              "shared": sorted(a & b)[:8]})
    return {"ok": True, "schema": SCHEMA, "n_invariants": len(gnodes), "n_edges": len(edges),
            "nodes": gnodes, "edges": edges}


def lattice_view(*, limit: int = 20) -> dict[str, Any]:
    """The VERKLE LATTICE: content-addressed knots (filename=leaf_hash) chained to a merkle root.
    The durable memory every invariant anchors into — tamper-evident, content-addressed."""
    try:
        from mag.verkle_knot import KNOTS, _merkle_root, _leaf_hash
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}
    if not KNOTS.is_dir():
        return {"ok": False, "schema": SCHEMA, "error": "no knot dir"}
    files = sorted(KNOTS.glob("*.json"))
    hashes = []
    rows = []
    for f in files[-limit:]:
        try:
            leaf = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        hashes.append(str(leaf.get("leaf_hash") or f.stem))
        rows.append({"file": f.name, "leaf_hash": str(leaf.get("leaf_hash"))[:12],
                     "theme": str(leaf.get("theme") or "")[:30],
                     "summary": str(leaf.get("summary") or "")[:80]})
    root = _merkle_root(hashes) if hashes else None
    return {"ok": True, "schema": SCHEMA, "n_knots": len(files), "shown": len(rows),
            "merkle_root": root[:24] if root else None, "knots": rows}


def steer_ollama(invariant: str, *, model: str | None = None, timeout: int = 90) -> dict[str, Any]:
    """Steer the LOCAL ollama (the slow/free renderer) with an invariant as the instruction.

    The invariant becomes the steering seed: inject it into a cheap local generation so the local
    model acts on the invariant (free compute — deterministically steers behavior without frontier
    spend). Uses gpu_ghost's ollama path (SELF-steal)."""
    try:
        from mag import gpu_ghost as gg
    except Exception as e:
        return {"ok": False, "error": f"gpu_ghost import: {e}"}
    try:
        models = gg._ollama_models()
        if not models:
            return {"ok": False, "schema": SCHEMA, "error": "ollama not up / no local models",
                    "hint": "start the ollama container (docker compose --profile ollama up -d)"}
        m = model or gg._pick_model(models)
        prompt = (f"[INVARIANT STEER] Act on this invariant: {invariant}\n"
                  f"Return ONE concrete action this invariant implies for our system.")
        out = gg._ollama_generate(prompt, m, timeout=timeout)
        return {"ok": True, "schema": SCHEMA, "surface": "ollama(local/free)", "model": m,
                "invariant": invariant[:120], "output": (out or "")[:1200]}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200]}


def dispatch_to_k8s(goal: str, *, domain: str = "invariant-task", k8s: bool = True) -> dict[str, Any]:
    """Transmit an invariant-driven task to the K8S SWARM for large local swarm testing on smart
    frontier tasks. Writes to mag.swarm_worker's dedicated queue (drained in-cluster by the
    mag-swarm CronJob). Deterministic $0 to enqueue; the cluster renders it."""
    from mag import swarm_worker as sw
    return sw.enqueue_task(goal, provider="deepseek", model="deepseek-chat",
                           domain=domain, agent_idx=0, tag=f"lattice-{domain}")


def render(invariant: str, *, prefer: str = "auto") -> dict[str, Any]:
    """The RIB-scene flow: route an invariant to the cheapest capable renderer.

    prefer='auto' -> try ollama (free/local) first, else k8s swarm (frontier).
    prefer='ollama' -> local only. prefer='k8s' -> frontier swarm only.
    """
    if prefer in ("auto", "ollama"):
        local = steer_ollama(invariant)
        if local.get("ok"):
            local["renderer"] = "ollama"
            local["prefer"] = prefer
            return local
        if prefer == "ollama":
            return local
    return dispatch_to_k8s(invariant, domain="invariant-render")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="invariant-lattice")
    ap.add_argument("cmd", nargs="?", default="mycelial",
                    choices=["mycelial", "lattice", "steer", "dispatch", "render"])
    ap.add_argument("--invariant", default="")
    ap.add_argument("--domain", default="")
    ap.add_argument("--prefer", default="auto")
    args = ap.parse_args(argv)
    if args.cmd == "mycelial":
        print(json.dumps(mycelial_view(domain_filter=args.domain or None), indent=2, default=str))
    elif args.cmd == "lattice":
        print(json.dumps(lattice_view(), indent=2, default=str))
    elif args.cmd == "steer":
        print(json.dumps(steer_ollama(args.invariant), indent=2, default=str))
    elif args.cmd == "dispatch":
        print(json.dumps(dispatch_to_k8s(args.invariant, domain=args.domain or "invariant-task"),
                         indent=2, default=str))
    else:
        print(json.dumps(render(args.invariant, prefer=args.prefer), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
