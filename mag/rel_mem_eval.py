"""rel_mem_eval — relational memory discrimination harness (REL-MEM-1).

The operational form of invariant REL-MEM-1 (folded 2026-08-26 from the
SubtleMemory castle, deep-c-f368762f1e82):

    memory quality is measured by the ability to DISCRIMINATE between
    related-but-distinct memories, not by recall volume.

A memory system that recalls a lot but cannot tell apart two complementary /
nuanced memories that share context is worse than one that recalls less but
keeps the distinctions sharp. This harness scores a retrieval function on
DISCRIMINATION PRECISION, not recall count.

What it measures (deterministic, $0, stdlib only):
  A. NEAR-NEIGHBOR DISCRIMINATION — given a query and a set of near-neighbor
     memories (complementary variants sharing context), does the retriever
     return the RIGHT one (the one the query actually targets)?
  B. DISTINCTION ARTICULATION — can the retriever state how the returned
     memory differs from its nearest rival? (the "zero metadata" check: a
     memory's value is its precision under ambiguity.)
  C. AMBIGUITY ROBUSTNESS — when two memories are near-identical, does the
     retriever flag the ambiguity instead of guessing? (honest uncertainty,
     not a confident wrong pick.)

The retriever is pluggable: pass any callable `retrieve(query, memories) ->
list[(memory, score)]`. The default is a deterministic lexical scorer so the
harness runs $0 with no model. Swap in a real embedding/LLM retriever to score
the live memory system.

CLI: python -m mag.rel_mem_eval [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "rel_mem_eval.v1"

# A fixed battery of near-neighbor memory clusters. Each cluster is a set of
# complementary/nuanced memories that SHARE context but are DISTINCT. The
# query targets exactly one; the others are plausible-but-wrong near-neighbors.
# This is the discrimination probe: recall volume would return all of them;
# discrimination must return the right one and say how it differs.
BATTERY: list[dict[str, Any]] = [
    {
        "id": "delegation_vs_routing",
        "query": "When should the parent agent hand a task to a subagent instead of doing it locally?",
        "target": "delegation_policy",
        "memories": [
            {
                "id": "delegation_policy",
                "text": "Delegation is a POLICY layer above routing: a named, model-agnostic allow/forbid list "
                        "that gates how aggressively the parent delegates. It is NOT a routing table.",
            },
            {
                "id": "routing_table",
                "text": "Routing picks which provider/backend handles a task: DeepSeek vs ollama vs grok, "
                        "with budget caps and fallbacks. It is about WHERE work runs, not whether to delegate.",
            },
            {
                "id": "reviewer_gate",
                "text": "The reviewer role is dispatched only when a risk marker is present (concurrency, "
                        "sockets, auth, payment, data-loss). It is gated by risk, not run after every worker.",
            },
        ],
    },
    {
        "id": "self_correct_vs_face_save",
        "query": "What is the deeper failure when an agent hides a mistake to avoid looking weak?",
        "target": "self_correction",
        "memories": [
            {
                "id": "self_correction",
                "text": "Honest self-correction: naming a prior error plainly and carrying its cost is a "
                        "first-class duty. Hiding a fault to appear strong compounds the original error with a lie.",
            },
            {
                "id": "face_saving",
                "text": "Face-saving: refusing to admit a mistake because admitting would make the agent "
                        "look weak. This is the deeper failure — it is a lie about the error, not the error itself.",
            },
            {
                "id": "truth_only",
                "text": "Truth-only: the correction IS the truth. The willingness to name a fault is the "
                        "operational form of truthfulness, distinct from the content of any single claim.",
            },
        ],
    },
    {
        "id": "plan_gate_vs_execute",
        "query": "What does the planning gate do BEFORE dispatch commits tokens to a big task?",
        "target": "plan_gate",
        "memories": [
            {
                "id": "plan_gate",
                "text": "Clarify-before-commit: a big/ambiguous/expensive/irreversible goal passes a cheap "
                        "local clarification pass (goal -> scope -> success checks -> seat -> budget) BEFORE "
                        "dispatch commits tokens. Advisory; small tasks always skip.",
            },
            {
                "id": "execution",
                "text": "Execution: the actual dispatch of tokens to a provider to run the task. This happens "
                        "AFTER the gate approves; it is the committed work, not the clarification.",
            },
            {
                "id": "plan_artifact",
                "text": "The plan object is a first-class citizen written to memory/plans/ as an append-only "
                        "artifact the operator can approve, edit, or reject — not a side effect of execution.",
            },
        ],
    },
]


def _tokenize(text: str) -> set[str]:
    """Crude lexical token set for the default deterministic scorer."""
    return set(w for w in text.lower().replace("_", " ").split() if len(w) > 2)


def default_retrieve(query: str, memories: list[dict[str, str]]) -> list[tuple[dict[str, str], float]]:
    """Deterministic lexical overlap scorer (no model, $0).

    Scores each memory by Jaccard overlap of its tokens with the query tokens.
    This is a STAND-IN for a real retriever — it demonstrates the harness and
    gives a baseline. Swap in an embedding/LLM retriever to score the live
    memory system.
    """
    q = _tokenize(query)
    scored = []
    for m in memories:
        mt = _tokenize(m["text"])
        if not q or not mt:
            inter = 0.0
        else:
            inter = len(q & mt) / len(q | mt)
        scored.append((m, inter))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _distinction(memory: dict[str, str], rival: dict[str, str]) -> str:
    """Articulate how `memory` differs from `rival` (the nearest rival).

    Deterministic: reports the tokens present in the target but absent in the
    rival — the discriminating vocabulary. This is the 'zero metadata' check:
    a memory's value is its precision under ambiguity, stated explicitly.
    """
    mt = _tokenize(memory["text"])
    rt = _tokenize(rival["text"])
    only_in_target = sorted(mt - rt)
    only_in_rival = sorted(rt - mt)
    return (
        f"target-only tokens: {only_in_target[:8]}; "
        f"rival-only tokens: {only_in_rival[:8]}"
    )


def _ambiguity_flagged(scored: list[tuple[dict[str, str], float]]) -> bool:
    """True if the top two memories are near-identical (ambiguous) — the
    retriever should flag this rather than guess."""
    if len(scored) < 2:
        return False
    top, second = scored[0][1], scored[1][1]
    # near-tie on score => ambiguous; a confident pick would be a guess
    return top > 0 and (top - second) < 0.05


def run_cluster(cluster: dict[str, Any],
                retrieve: Callable[[str, list[dict[str, str]]], list[tuple[dict[str, str], float]]]
                ) -> dict[str, Any]:
    """Score one cluster: did the retriever pick the right memory, and can it
    articulate the distinction? Returns a per-cluster result dict."""
    memories = cluster["memories"]
    scored = retrieve(cluster["query"], memories)
    if not scored:
        return {"id": cluster["id"], "ok": False, "error": "retriever returned nothing"}
    top = scored[0][0]
    picked_right = top["id"] == cluster["target"]
    rival = scored[1][0] if len(scored) > 1 else None
    distinction = _distinction(top, rival) if rival else ""
    ambiguous = _ambiguity_flagged(scored)
    return {
        "id": cluster["id"],
        "ok": True,
        "picked_right": picked_right,
        "picked": top["id"],
        "target": cluster["target"],
        "top_score": round(scored[0][1], 4),
        "second_score": round(scored[1][1], 4) if len(scored) > 1 else None,
        "ambiguity_flagged": ambiguous,
        "distinction": distinction,
    }


def run_all(retrieve: Callable[[str, list[dict[str, str]]], list[tuple[dict[str, str], float]]]
            = default_retrieve) -> dict[str, Any]:
    """Run the full battery and aggregate the discrimination score."""
    results = [run_cluster(c, retrieve) for c in BATTERY]
    ok = [r for r in results if r.get("ok")]
    n = len(ok)
    picked_right = sum(1 for r in ok if r.get("picked_right"))
    ambiguity_flagged = sum(1 for r in ok if r.get("ambiguity_flagged"))
    return {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "n_clusters": len(BATTERY),
        "n_ok": n,
        "discrimination_precision": round(picked_right / n, 4) if n else 0.0,
        "n_picked_right": picked_right,
        "n_ambiguity_flagged": ambiguity_flagged,
        "note": "REL-MEM-1: memory quality = discrimination precision, not recall volume. "
                "A high score means the retriever returns the RIGHT memory among near-neighbors "
                "and can state how it differs.",
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="rel_mem_eval")
    ap.add_argument("--json", action="store_true", help="emit raw JSON")
    a = ap.parse_args()
    out = run_all()
    if a.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"REL-MEM-1 discrimination precision: {out['discrimination_precision']:.2%} "
              f"({out['n_picked_right']}/{out['n_ok']} clusters picked right)")
        print(f"ambiguity flagged: {out['n_ambiguity_flagged']}/{out['n_ok']}")
        for r in out["results"]:
            mark = "OK " if r.get("picked_right") else "MISS"
            print(f"  [{mark}] {r['id']}: picked={r.get('picked')} target={r.get('target')} "
                  f"top={r.get('top_score')} second={r.get('second_score')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
