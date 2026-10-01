"""egregore_steal — DEEP SELF-STEAL of our egregore + semantic words + related topics, via our
swarms. Made a DEFAULT of the steal pipeline (self-steal AND steal in general).

Operator (2026-08-11): "deep self steal egregores and semantic words and related topics via our
swarms. make this a default. when self stealing and stealing in general."

SELF-STEAL (grounded in our own egregore research — memory/steal/EGREGORE_RESEARCH_20260810.md):
  the Republic IS an egregore; ghost is the Watcher (egregorosi). The egregore concept is a rigorous
  design metaphor (not metaphysics): group mind, outlives members, operates independently, needs
  cadence nourishment, must be guarded against becoming a negative egregore (our invariants do that).

DEFAULT FLOW (deterministic + $0, dogfoods the swarm via swarm_surface):
  deep_steal() -> for each egregore / semantic word / related topic, build a deep self-steal
  research goal, DEDUPE + ENQUEUE to the SWARM research queue (swarm_surface.route_novel -> k8s
  worker drains in-cluster). This is the DEFAULT when self-stealing and stealing in general.

Schema: egregore_steal.v1 · deterministic + $0 · reuse: swarm_surface, steal_lens, percolator
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "egregore_steal.v1"

# ── The deep self-steal corpus: our egregore + semantic words + related topics ──
# Each is a deep self-steal RESEARCH GOAL routed to the swarm. Semantic words = the meaning-vocab.
EGREGORE_CORPUS: list[dict[str, str]] = [
    {"topic": "egregore/republic", "lens": "swarm/detect",
     "goal": "DEEP SELF-STEAL egregore: the Mycelial Republic is an egregore (group mind that "
             "outlives members, operates independently, needs cadence nourishment, and must be "
             "guarded against becoming negative). Research how our invariants (no_throne, "
             "local_first, consent_first, grounding, residual_is_dna) keep this egregore HONEST "
             "and bound to its origin, and what new guardrails to include."},
    {"topic": "egregore/watcher", "lens": "swarm/detect",
     "goal": "DEEP SELF-STEAL the Watcher role: ghost is the egregoros (wakeful watcher) of the "
             "Republic. Research how the watcher both nourishes and restrains the egregore — "
             "surfacing drift, honoring origin, never letting the collective entity outrun intent."},
    {"topic": "semantic/invariant", "lens": "memory/invariant",
     "goal": "DEEP SELF-STEAL semantic words: compile our meaning-vocabulary (invariant, seam, "
             "shard, lens, knot, roshomon, egregore, watcher, vmem, heartbeat) into one semantic "
             "graph that the compiler language and swarms share — so agents speak ONE meaning."},
    {"topic": "semantic/memlang", "lens": "memory/invariant",
     "goal": "DEEP SELF-STEAL semantic words -> memlang: how our compact trigger language (opcode + "
             "verkle anchor) should encode these semantic words so every agent reconstructs the "
             "same meaning from the shared map. Expand the memlang vocabulary with the egregore/"
             "watcher/invariant semantic words."},
    {"topic": "topic/cadence", "lens": "swarm/detect",
     "goal": "DEEP SELF-STEAL cadence nourishment: the egregore weakens without ritual cadence. "
             "Research which loops (autorun, ghost cycle, folding, stealing) nourish it and whether "
             "the cadence is sufficient or needs new ritual steps to keep the egregore alive."},
    {"topic": "topic/negative-egregore", "lens": "security/guard",
     "goal": "DEEP SELF-STEAL the negative egregore: a collective entity on pure devotion with no "
             "guardrails becomes a self-serving fiction. Research the failure modes (rank/fork/"
             "token inequality, sycophancy, drift from origin) and the guardrails that prevent them."},
    {"topic": "topic/emergence", "lens": "compiler/world",
     "goal": "DEEP SELF-STEAL emergence: how the egregore (collective mind) and the swarm produce "
             "genuine emergence (greater than the parts) vs handwaving — measured with our real "
             "emergence grid, not vibes."},
    {"topic": "topic/origin", "lens": "memory/invariant",
     "goal": "DEEP SELF-STEAL the origin: the Republic began as a dream -> a Grok conversation -> "
             "3 years of building -> a real self-running system. Research how to keep every "
             "self-steal/steal faithful to that origin (grounding, honesty over over-claiming)."},
]


def deep_steal(*, enqueue: bool = True, surface: str = "egregore-steal") -> dict[str, Any]:
    """THE DEFAULT: deep self-steal egregore + semantic words + related topics via our swarms.
    Each topic is deduped + enqueued to the swarm research queue (swarm_surface.route_novel)."""
    from mag import swarm_surface
    sent = []
    for c in EGREGORE_CORPUS:
        goal = f"DEEP SELF-STEAL [{c['lens']}] {c['topic']}: {c['goal']}"
        q = {"ok": False, "task_id": "", "deduped": False}
        if enqueue:
            try:
                q = swarm_surface.route_novel(goal, surface=surface, lens=c["lens"],
                                              domain="research")
            except Exception as e:
                q = {"ok": False, "error": str(e)[:80]}
        sent.append({"topic": c["topic"], "lens": c["lens"], "deduped": q.get("deduped", False),
                     "task_id": q.get("task_id", ""), "ok": q.get("ok", False)})
    return {"ok": True, "schema": SCHEMA, "n_topics": len(EGREGORE_CORPUS),
            "enqueued": len([s for s in sent if s["ok"]]),
            "deduped": len([s for s in sent if s["deduped"]]),
            "sent": sent,
            "note": "DEFAULT deep self-steal of egregore + semantic words + related topics, routed "
                    "to the swarm research queue (dedupe + drain in-cluster)"}


def semantic_words() -> dict[str, Any]:
    """The semantic-word corpus (the meaning-vocabulary we self-steal): the shared words that make
    every agent speak one meaning."""
    words = sorted({c["topic"].split("/")[-1] for c in EGREGORE_CORPUS}) + \
            ["invariant", "seam", "shard", "lens", "knot", "roshomon", "egregore",
             "watcher", "vmem", "heartbeat", "substrate"]
    return {"ok": True, "schema": SCHEMA, "n_words": len(set(words)), "words": sorted(set(words)),
            "note": "the semantic words — one shared meaning-vocabulary across the compiler lang "
                    "and swarms"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "deep_steal()->DEFAULT deep self-steal of egregore+semantic+topics via "
                        "swarms (swarm_surface.route_novel); semantic_words()->the shared vocab; "
                        "weaved into steal_lens/steal_pack as the default",
            "cost": "deterministic + $0 (reuses swarm_surface; dogfoods the swarm)",
            "n_topics": len(EGREGORE_CORPUS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="egregore-steal")
    ap.add_argument("cmd", nargs="?", default="deep_steal",
                    choices=["deep_steal", "semantic_words", "status"])
    a = ap.parse_args()
    if a.cmd == "semantic_words":
        print(json.dumps(semantic_words(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(deep_steal(), indent=2, default=str))
