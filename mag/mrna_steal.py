"""mrna_steal — deterministic self-map + route NOVEL gene-expression research to the SWARM.

The operator (2026-08-15): "learn from mrna biotech on how genes are expressed and how they're built all
of it ... recreate the mechanisms internally BY THE SHAPE OF THE OBJECTS ... using the swarm to mimic
different matter patterns to receive their benefits."

We already hold the grounded map (memory/steal/MRNA_CENTRAL_DOGMA_STEAL_20260815.md) + the frontier
research brief (handoff/MRNA_GENE_EXPRESSION_FRONTIER_PROMPT_20260815.md). This module does the two jobs
that must touch code: (1) expose the deterministic self-map (the architecture already IS the cell), and
(2) route the NOVEL seams to the swarm via the ONE primitive (swarm_surface.route_novel -> dedupe by
anchor + enqueue to the SWARM research queue, drained in-cluster). Dogfooding, not a local run.

Schema: mrna_steal.v1 · deterministic + $0 · reuse: swarm_surface, shared_context
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SURFACE = "mrna_steal"

# The deterministic self-map: each biological mechanism -> the architecture primitive it already IS.
# This is the "shape of the objects" made explicit — the Republic was already a cell.
SELF_MAP: list[dict[str, str]] = [
    {"bio": "genome / Weismann barrier (one-way out)", "arch": "verkle chain (immortal germline); outputs never write back as genome"},
    {"bio": "transcription + promoter/enhancer", "arch": "shared_context.transcription: pull a transient working copy on demand; router/rightsizer as the transcription factors that decide what/where/how-much"},
    {"bio": "mRNA (transient working copy)", "arch": "session/context message: expendable + renewable, NOT the chain; stateless workers = short-lived mRNA"},
    {"bio": "alternative splicing (one gene -> many isoforms)", "arch": "one invariant/knot -> many contextual renders/surfaces/personas without duplication"},
    {"bio": "5' cap + poly(A) + circularization", "arch": "task contract envelope (schema, provenance, anchor) that stabilizes + lets the message recycle"},
    {"bio": "translation + tRNA adaptor + codon optimization", "arch": "seat/worker = ribosome; model = machinery; rightsize = codon optimization (same meaning, cheapest shape)"},
    {"bio": "multi-layer regulation", "arch": "stacked gates (leash, cadence, trust_gate, capture_guard) instead of one big switch"},
    {"bio": "epigenetics (same genome, contextual expression)", "arch": "personas / sovereign-mirror / egregore NPCs = epigenetic states over one genome"},
    {"bio": "RNAi / miRNA / NMD (silence + quality control)", "arch": "capture_guard / NMD: destroy broken or foreign messages; the RIB-debug false-success guard"},
    {"bio": "reverse transcription (retrovirus, forbidden back-flow)", "arch": "chain consolidate / distill (many-to-one): sanctioned, gated write-back to the genome"},
    {"bio": "prion (information in the FOLD / conformation)", "arch": "the verkle knot's SHAPE / the wave: the shadow — state carried by structure, not stored field"},
    {"bio": "N1-methylpseudouridine (Nobel 2023: accepted, not foreign)", "arch": "message framing/anti-hallucination: the acceptance layer that stops our context being rejected as alien"},
]

# NOVEL seams to route to the swarm (deduped by anchor, drained in-cluster). Each is a research goal
# the swarm should deepen + turn into a buildable primitive. Never run these locally.
NOVEL_GOALS: list[tuple[str, str]] = [
    ("riboswitch", "Design a self-regulating 'message' primitive: like a riboswitch, an internal object that CHANGES ITS OWN BEHAVIOR in response to a signal (token-cost, heat, leash, novelty) with NO external controller. Deliver a concrete data structure + control flow we can build into shared_context or the task contract. This is the highest-novelty shape-encodes-function mechanism."),
    ("codon-optimization-rightsizer", "Design a 'codon-optimization' rightsizer: express the same intent with the cheapest correct token-shape (deepseek-first, GPU for build, swarm for research, cache-aware) — an adaptive encoder, not a static router. Deliver the control rule that decides the message shape per context to minimize cost without losing meaning."),
    ("prion-shadow-surveillance", "Design prion-style shadow accounting: track state that lives in the SHAPE/structure of the system (verkle knot conformation, the wave, relation between objects) not in stored fields — AND build NMD-style surveillance that catches misfolded states (drift, over-claim, hallucination) before they propagate. This is the shadow-work made molecular. Deliver the detector + the gate."),
]


def self_map() -> list[dict[str, str]]:
    return SELF_MAP


def route(*, dry: bool = False) -> list[dict[str, Any]]:
    """Route the novel research goals to the SWARM via the ONE primitive. dry=True returns the plan
    ($0); dry=False enqueues to the swarm_worker queue (the drainer eats it in-cluster)."""
    from mag import swarm_surface  # local import: keep module import-light

    out: list[dict[str, Any]] = []
    for tag, goal in NOVEL_GOALS:
        if dry:
            out.append({"surface": SURFACE, "goal": tag, "dry": True,
                        "anchor": swarm_surface.anchor(goal, SURFACE)})
            continue
        out.append(swarm_surface.route_novel(goal, surface=SURFACE, lens=tag, domain="research"))
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    if mode == "run":
        print(json.dumps(route(dry=False), indent=2, default=str))
    else:
        print(json.dumps({
            "schema": "mrna_steal.v1",
            "self_map": SELF_MAP,
            "plan": route(dry=True),
            "note": "pass 'run' to enqueue to the swarm; idempotent via anchor dedup",
        }, indent=2, default=str))
