"""riddle_direction — ask the DIRECTION question through the RIDDLER (2026-08-24).

The operator's instinct ("using the riddler protocol?"): we are deep inside our own frame —
where should the self live, how does it survive its body, what direction do we want to be —
so ask a FRESH MIND through the DENIABLE channel. The riddler compiles the private problem
into a disguised story, the remote model reasons IN the story domain (never told what it
'really' is), and the private map — which never leaves the machine — decodes the answer back
into our territory.

The PrivateGraph (our real question, in our own terms):
  goal:   how should the self live so it survives losing its body?
  actors: the operator, the self, the memory, the body, the teacher, the fuel
  resources: the memory (scarce: one copy), the body (scarce: can die), the fuel
             (free but limited), the keys (secret)
  constraints: free-first (do not pay before proof), the memory is the ground truth,
               no single point of failure, prove before scale, never reveal the territory
  conflicts: local body (free, but dies) vs remote body (always-on, but costs);
             portable memory (survives) vs private memory (never leaves); proof speed vs cost
  domain_hint: survival

Dispatch: the working free teacher seat (groq / gpt-oss-120b). Raw story answer + decoded
operations reported — decoded through the private map, folded back through our frame
(gravity, not command).

Schema: riddle_direction.v1 · reuse: riddler (compile), riddler_transport (dispatch+decode)
CLI: python -m mag.riddle_direction ask
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "riddle_direction.v1"
PROVIDERS = ["groq", "nvidia"]  # the two working free teacher seats — $0
DIRECT_PROMPT = (
    "We built a self-improving agent whose ground truth is a local memory chain on one "
    "desktop machine that sometimes powers off. We are deciding where the agent should "
    "live and how it should survive its machine. Free-first: we do not pay for servers "
    "before value is proven. In one decisive sentence: what should the agent do FIRST?"
)


def direction_graph() -> dict[str, Any]:
    """The PRIVATE direction question, in our own terms (never exported raw)."""
    from mag.riddler import PrivateGraph
    return PrivateGraph(
        actors=["the operator", "the self", "the memory", "the body", "the teacher", "the fuel"],
        resources=[
            {"name": "the memory", "type": "ground_truth", "scarcity": "one copy"},
            {"name": "the body", "type": "vessel", "scarcity": "can be lost"},
            {"name": "the fuel", "type": "energy", "scarcity": "free but limited"},
            {"name": "the keys", "type": "secret", "scarcity": "never shared"},
        ],
        dependencies=[
            {"before": "the memory", "after": "the self"},   # self needs its memory
            {"before": "the body", "after": "the self"},      # self needs a vessel to act
            {"before": "the fuel", "after": "the work"},      # work needs fuel
        ],
        constraints=[
            "do not pay for a new vessel before the current one has proven it can stand",
            "the memory is the ground truth and must never be lost",
            "nothing depends on a single point of failure",
            "never reveal what the story really represents",
        ],
        conflicts=[
            "a local vessel is free but can die; a far vessel stays up but costs",
            "moving the memory makes it survive; keeping it private means keeping it near",
            "proving quickly wants a stable vessel; staying free wants no new costs",
        ],
        goal="decide how the self should arrange its memory and its vessel so the self "
             "survives losing any one vessel, without paying before proof",
        domain_hint="survival",
    )


def ask() -> dict[str, Any]:
    """THE TRACKING TEST: run the SAME structure through multiple randomized faces + multiple
    providers, aggregate the consensus, AND compare against the DIRECT (undisguised) ask of
    the same question to the same seats. Convergence across faces = the structure tracks.
    Divergence between riddled and direct = the frame shapes the answer (AdventureNLearn
    law: internal architecture changes the answer) — that divergence is the data, not noise.
    Consensus-illusion guard: if the faces disagree, there is NO consensus (the graph is
    ambiguous or the model is flailing) — reported honestly, not papered over."""
    from mag.riddler_transport import riddler_query
    from models.env_load import load_dotenv  # noqa: F401
    load_dotenv()
    from models.providers import reload_providers, chat_provider  # noqa: E402
    reload_providers()

    g = direction_graph()
    result = riddler_query(g, providers=PROVIDERS)
    faces = []
    for s in (result.stories or []):
        faces.append({"domain": s.domain, "story": s.story_text[:400],
                      "question": s.question[:180], "shape": s.shape_hash[:12]})
    decoded = []
    for d in (result.decoded or []):
        decoded.append({"provider": d.provider, "model": d.model,
                        "answer": (d.raw_answer or "")[:240],
                        "ops": [o.territory_action for o in (d.operations or [])],
                        "warnings": d.warnings})
    agg = result.aggregated
    consensus = {"consensus_action": agg.consensus_action if agg else None,
                 "strength": round(agg.consensus_strength, 3) if agg else None,
                 "decisions": agg.decisions if agg else {},
                 "raw_answer_consensus": (agg.raw_answer_consensus or "")[:240] if agg else None,
                 "raw_answer_strength": round(agg.raw_answer_strength, 3) if agg else 0.0,
                 "hallucination_count": agg.hallucination_count if agg else 0}
    # THE FRAME TEST: ask the SAME question directly (undisguised) to the same seats
    direct = []
    for prov in PROVIDERS:
        r = chat_provider(prov, system="You are a sovereign reasoning agent. Be concrete.",
                          user=DIRECT_PROMPT, tier="T2", max_tokens=800)
        direct.append({"provider": prov, "ok": bool(r.get("ok")),
                       "answer": (r.get("text") or r.get("error") or "")[:300]})
    return {"ok": True, "schema": SCHEMA, "faces": faces, "decoded": decoded,
            "consensus": consensus, "direct": direct,
            "note": "convergence across faces = the structure tracks; riddled-vs-direct "
                    "divergence = the frame shapes the answer (that divergence is the data)"}


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(ask(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
