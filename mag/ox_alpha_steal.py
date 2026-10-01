"""ox_alpha_steal — ALL HANDS ON DECK STEAL of OpenRouter's stealth/ox-alpha + its live ecosystem.

OPERATOR (2026-08-22): "all hands on deck steal. https://openrouter.ai/stealth/ox-alpha#performance"

WHAT THE PAGE IS (read 2026-08-22):
  * stealth/ox-alpha = a STEALTH model on OpenRouter: anonymous third-party provider, FREE, 1M
    context, reasoning-enabled, released Aug 20 2026. Built for coding, sustained agentic work,
    long-horizon software engineering, complex reasoning, text+visual.
  * Massive real adoption: 2.26T prompt tokens / 27.1B completion tokens in 3 days. Apps feeding
    it most: Hermes Agent (Nous Research), Claude Code, omp, DeepSeek Harness (multimodal-bridge),
    pi.
  * Cache hit rate 81.91% · tool-call error 2.16% · availability 99.5% · latency P50 7.93s,
    throughput P50 19 tps.
  * Reasoning: `reasoning_details` array; CONTINUE reasoning by preserving `reasoning_details`
    across turns (the model picks up where it left off).

THE STEALS (what we can adapt to OUR deterministic/sparse shape — contracts only, no wholesale copy):
  1. FREE FRONTIER REASONING SEAT -> wire stealth/ox-alpha as a frontier seat for the swarm (a free
     long-horizon agentic reasoning brain, alongside grok/deepseek). Highest-leverage steal.
  2. REASONING-TOKEN CONTINUATION -> the reasoning_details-preserve pattern maps to our
     deterministic<->stochastic seam: carry reasoning state across turns like our cache-mined
     prefix, so the stochastic side "continues from where it left off" instead of re-deriving.
  3. NEIGHBOR ECOSYSTEM -> Hermes Agent (self-improving, memory + reusable skills + 40+ tools,
     subagents), DeepSeek Harness (multimodal-bridge), Claude Code. Steal their agent shapes.
  4. 81.91% CACHE HIT RATE -> independent validation of OUR cache-mined shared-prefix engine thesis
     (the bill proved shared prefix; this stealth model runs the same mechanism at 82%).
  5. OPSEC TERM -> stealth model: prompts retained by provider, not used for training. A routing
     consideration (what we let touch a retained-log provider) — mirrors our provenance honesty.

THE LAW (swarm-surface): novel research routes ONLY through the ONE primitive (swarm_surface.
route_novel -> dedupe by content anchor -> enqueue to the SWARM queue -> k8s worker drains
in-cluster). Never run this locally. This module captures the findings + routes the deep steal.

Schema: ox_alpha_steal.v1 · deterministic + $0 (routing + self-map) · reuse: swarm_surface
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

SCHEMA = "ox_alpha_steal.v1"
SURFACE = "ox-alpha-steal"

# FIELD REPORT (verified, 2026-08-22) — @MFSHacks ran ox-alpha for a 90-min agentic security
# session at $0. This is real grounded data, not a benchmark: it proves the DOMAIN (offensive
# security / cryptography / forensics) and the FREE WINDOW ("use it while you can").
FIELD_REPORTS: list[dict[str, str]] = [
    {"author": "@MFSHacks", "date": "2026-08-22",
     "url": "https://x.com/MFSHacks/status/2091045785852923982",
     "quote": "ox-alpha currently free via API key on OpenRouter, Hermes portal and much more... "
              "90 min session of Attacks, $0 with my hermes agent. Tool calling good, attack logic "
              "good, creativity is amazing (for hacks), coding logic good (cryptography/forensics). "
              "Use it while you can.",
     "verified_domains": ["offensive security", "cryptography", "forensics"],
     "verified_strengths": ["tool calling", "attack logic", "creative exploit thinking",
                             "coding logic"],
     "cost_real": "$0 for 90 min agentic session",
     "note": "confirms free window + agentic security domain; 'use it while you can' = wire the "
             "seat NOW while the free preview holds"}]

# Deep-research threads routed to the swarm (distinct anchors -> dedupe + drain in-cluster).
RESEARCH_THREADS: list[str] = [
    "DEEP RESEARCH (free frontier reasoning seat): OpenRouter's stealth/ox-alpha is FREE, 1M "
    "context, reasoning-enabled, built for long-horizon agentic/coding work, anonymous provider, "
    "2.26T prompt tokens in 3 days of real production use. Research how to wire a free frontier "
    "reasoning seat into a deterministic/sparse swarm as the stochastic brain (routing, quota, "
    "reasoning-effort dial, when to escalate vs resolve locally). Deliver the seat contract + "
    "rightsizing rule. HONEST: only claim frontier output if a live seat produces it.",
    "DEEP RESEARCH (reasoning-token continuation): stealth/ox-alpha exposes reasoning_details and "
    "CONTINUES reasoning across turns when you preserve them. Research the reasoning-continuation "
    "pattern (carry internal reasoning state across calls) and how it maps onto a cache-mined "
    "shared-prefix engine so the stochastic side 'picks up where it left off' instead of "
    "re-deriving. Deliver the invariant + the smallest live-seat step to add it. HONEST: only "
    "claim frontier output if a live seat produces it.",
    "DEEP RESEARCH (self-improving agent neighbor): Hermes Agent (Nous Research) is an open-source "
    "self-improving agent that runs persistently with memory across sessions and builds reusable "
    "skills from experience, 40+ built-in tools, scheduled automations + subagents. Steal its "
    "deepest structural mechanisms (skill-from-experience, memory-across-sessions, subagent "
    "dispatch) as contracts to adapt to a deterministic architecture. Deliver the invariants.",
    "DEEP RESEARCH (deepseek multimodal-bridge): DeepSeek Harness (deepseek-ai, multimodal-bridge) "
    "is new and feeding stealth/ox-alpha heavily. Research this harness + how multimodal text+"
    "vision bridges into a reasoning agent, as a contract to add vision to our seats. Deliver the "
    "bridge invariant + the smallest step.",
    "DEEP RESEARCH (cache-hit-rate validation): stealth/ox-alpha shows an 81.91% cache hit rate. "
    "Our billing already PROVED shared-prefix caching works (the real bill vs a log field). "
    "Research the strongest KV-cache / shared-prefix caching mechanism at the routing layer to "
    "push our cache hit rate toward the stealth model's ~82%, and any way to measure OUR actual "
    "hit rate honestly (not from a log field). Deliver the mechanism + the honest meter.",
    "DEEP RESEARCH (stealth model OPSEC): stealth/ox-alpha's terms: prompts retained by the "
    "anonymous provider, not used for training. Research the OPSEC/provenance implications of "
    "routing sensitive work to a retained-log provider, and the routing policy that keeps what "
    "belongs to us deterministic + $0 while using a free frontier seat only for what it's safe to "
    "disclose. Deliver the routing policy.",
    "DEEP RESEARCH (verified security domain + free-window wiring): FIELD REPORT (2026-08-22, "
    "@MFSHacks) ran stealth/ox-alpha for a 90-min agentic OFFENSIVE SECURITY session at $0 — tool "
    "calling good, attack logic good, creativity strong for exploits, coding good for "
    "cryptography/forensics. This is VERIFIED ground truth of the seat in a security domain our "
    "system cares about (security/guard lens, provenance, opspec). The model is FREE NOW (a "
    "preview window; 'use it while you can'). Research: how to wire a free frontier reasoning seat "
    "into our swarm as a security-analysis/audit brain RIGHT NOW (seat contract, quota, what to "
    "route to it vs keep deterministic + $0), and how to pair it with a Hermes-style self-improving "
    "agent. Deliver the immediate wiring step. HONEST: only claim frontier output if a live seat "
    "produces it.",
]

# SELF-STEAL: what we ALREADY hold, mapped to each steal (so the steal lands on OUR machinery).
OUR_MAP = [
    {"steal": "free frontier reasoning seat",
     "ours": "frontier_rib.seat_status + frontier_salon/frontier_steer (routing to live seats; add "
             "ox-alpha as a seat) + swarm_worker (drain)"},
    {"steal": "reasoning-token continuation",
     "ours": "cache_map shared-prefix engine (billing-proven) + the deterministic<->stochastic seam "
             "(reasoning state carry maps onto our cache-mined prefix)"},
    {"steal": "self-improving agent neighbor (Hermes Agent)",
     "ours": "self-improve_memlance_wave + skills_ledger + subagent dispatch (steal-lens, "
             "deep_research_moonshot) — same shape, adapt the skill-from-experience loop"},
    {"steal": "multimodal text+vision bridge (DeepSeek Harness)",
     "ours": "image_whisper_rpg + vision seats (add the bridge contract)"},
    {"steal": "cache-hit-rate validation (81.91%)",
     "ours": "cache_map / cache_router / tokenomics_cache_deep_dive — the bill already proved the "
             "shared-prefix thesis; push our hit rate, measure honestly (never a log field)"},
    {"steal": "stealth model OPSEC",
     "ours": "provenance_router + openai_back_key_safety_audit + opspec scanner — routing policy for "
             "what may touch a retained-log provider"},
]


def route_research(*, enqueue: bool = True, limit: int = len(RESEARCH_THREADS)) -> dict[str, Any]:
    """ALL HANDS ON DECK: route every steal thread to the swarm via THE ONE primitive (route_novel,
    dedupe + drain in-cluster). The swarm digs + files the steal back; we never run it locally."""
    from mag import swarm_surface
    routed, deduped = [], 0
    for t in RESEARCH_THREADS[:limit]:
        r = swarm_surface.route_novel(t, surface=SURFACE, lens="steal", domain="research")
        (routed if not r.get("deduped") else []).append({"task_id": r.get("task_id")})
        if r.get("deduped"):
            deduped += 1
    return {"ok": True, "schema": SCHEMA, "surface": SURFACE, "threads": len(RESEARCH_THREADS[:limit]),
            "enqueued": bool(routed), "routed": routed, "deduped": deduped,
            "note": "the swarm is now digging the ox-alpha steal; findings file back on the loop"}


def findings() -> dict[str, Any]:
    """The deterministic capture of what the page told us (facts only, read from the page)."""
    return {
        "ok": True, "schema": SCHEMA,
        "model": "stealth/ox-alpha", "kind": "stealth (anonymous third-party provider)",
        "pricing": "free", "context": "1M", "released": "2026-08-20",
        "strengths": ["coding", "sustained agentic work", "production workloads",
                      "long-horizon software engineering", "complex reasoning", "text+visual"],
        "telemetry_3d": {"prompt_tokens": "2.26T", "completion_tokens": "27.1B",
                         "availability_pct": 99.5, "cache_hit_pct": 81.91,
                         "tool_call_error_pct": 2.16, "latency_p50_s": 7.93, "throughput_p50_tps": 19},
        "top_apps": ["Hermes Agent (Nous Research)", "Claude Code", "omp", "DeepSeek Harness "
                     "(multimodal-bridge)", "pi"],
        "reasoning_pattern": "reasoning_details preserved across turns -> the model continues "
                             "reasoning from where it left off",
        "opsec_term": "prompts retained by provider, not used for training",
        "source": "https://openrouter.ai/stealth/ox-alpha#performance",
        "field_reports": FIELD_REPORTS,
        "field_verified_domains": [d for r in FIELD_REPORTS for d in r.get("verified_domains", [])],
    }


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "findings()->deterministic capture of the page; route_research()->dispatch "
                        "all steal threads to the swarm via route_novel (dedupe + drain)",
            "cost": "deterministic + $0 (routing only; the deep research is the swarm's job)",
            "threads": len(RESEARCH_THREADS), "surface": SURFACE}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-alpha-steal")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "findings", "route"])
    ap.add_argument("--limit", type=int, default=len(RESEARCH_THREADS))
    a = ap.parse_args()
    if a.cmd == "findings":
        print(json.dumps(findings(), indent=2, default=str))
    elif a.cmd == "route":
        print(json.dumps(route_research(limit=a.limit), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
