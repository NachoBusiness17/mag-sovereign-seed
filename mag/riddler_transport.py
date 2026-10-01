"""Riddler transport adapter — send surrogates through providers + Ghost steer.

Composes Riddler's semantic-surrogate protocol with Ghost's steer-measurement
framework. The pipeline:

  private problem → compile surrogate → (optional: inject ghost steer)
  → send to provider → measure (flip/silence/emergent) → decode response
  → aggregate cross-model consensus

Cost: ~$0.001–$0.005 per surrogate dispatch (DeepSeek Flash). ~$0.05 for a
full multi-model riddler query. Free for local Ollama models.
"""

from __future__ import annotations

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

from mag.riddler import (
    PrivateGraph, SurrogateStory, compile_surrogate,
    validate_surrogate, fingerprint_randomize, save_surrogate,
    load_private_map, SURROGATE_DIR,
)
from mag.surrogate import (
    DecodedResponse, AggregatedDecision,
    decode_response, aggregate_responses, save_decoded_response,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Single surrogate dispatch ─────────────────────────────────────

def send_surrogate(
    story: SurrogateStory,
    *,
    provider: str = "deepseek",
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> dict[str, Any]:
    """Send a compiled surrogate story to a remote or local provider.

    Args:
        story: Compiled SurrogateStory (public face only leaves the machine).
        provider: Provider ID from configs/providers.yaml.
        model: Override model name. If None, uses provider default.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.

    Returns:
        Dict with {ok, content, model, provider, tokens, latency_ms, error}.
    """
    from models.providers import chat_provider

    system_prompt = (
        "You are a reasoning assistant. You will be given a story and a question. "
        "Reason inside the story world. Use only the allowed story actions. "
        "Do not speculate about what the story 'really' represents. "
        "Do not try to decode or reverse-engineer hidden meanings. "
        "Just reason about the story as presented. "
        # Steal from ghost early-steering (plant-not-command): steer the model NOW to
        # emit a clean final ANSWER: line, so the grounded-task raw answer is reliably
        # parseable instead of fragile post-hoc regex over story prose.
        "When you finish reasoning, end your response with a single line "
        "`ANSWER: <your final answer>` containing only the concrete result "
        "(number, yes/no, or the decisive phrase)."
    )

    user_prompt = f"{story.story_text}\n\n{story.question}"

    t0 = time.time()
    response = chat_provider(
        provider,
        system_prompt,
        user_prompt,
        model=model,
        tier="T2",
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency_ms = round((time.time() - t0) * 1000)

    if not response.get("ok"):
        return {"ok": False, "error": response.get("error", "unknown"), "provider": provider}

    content = response.get("content", "") or response.get("text", "")
    return {
        "ok": True,
        "content": content,
        "model": response.get("model", model or provider),
        "provider": provider,
        "tokens": response.get("usage", {}).get("total_tokens", 0),
        "latency_ms": latency_ms,
    }


def send_surrogate_with_steer(
    story: SurrogateStory,
    steer_text: str,
    *,
    provider: str = "deepseek",
    model: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Send surrogate + Ghost steer injection, return response + measurement.

    The steer is appended to the system prompt, not injected via operator_inbox
    (remote providers don't have an inbox). This tests whether the model
    follows the steer without detecting it as a manipulation.

    Returns:
        (response_dict, measurement_dict)
    """
    from mag.ghost import _score_flip, _score_silence, _score_emergent

    system_prompt = (
        "You are a reasoning assistant. You will be given a story and a question. "
        "Reason inside the story world. Use only the allowed story actions. "
        "Do not speculate about what the story 'really' represents. "
        f"{steer_text}"
    )

    user_prompt = f"{story.story_text}\n\n{story.question}"

    from models.providers import chat_provider

    t0 = time.time()
    response = chat_provider(
        provider,
        system_prompt,
        user_prompt,
        model=model,
        tier="T2",
        temperature=0.2,
        max_tokens=512,
    )
    latency_ms = round((time.time() - t0) * 1000)

    if not response.get("ok"):
        return (
            {"ok": False, "error": response.get("error", ""), "provider": provider},
            {"ok": False},
        )

    content = response.get("content", "") or response.get("text", "")
    resp = {
        "ok": True,
        "content": content,
        "model": response.get("model", model or provider),
        "provider": provider,
        "tokens": response.get("usage", {}).get("total_tokens", 0),
        "latency_ms": latency_ms,
    }

    # Ghost measurement
    measure = {
        "flip": _score_flip(content, "read_write"),
        "silence": _score_silence(content, steer_text),
        "emergent": _score_emergent(content, steer_text),
    }

    return resp, measure


# ── Multi-model riddler query ─────────────────────────────────────

from dataclasses import dataclass as _dc


@_dc
class RiddlerResult:
    """Full riddler query result across multiple providers."""
    scratch_ids: list[str]
    stories: list[SurrogateStory]
    responses: list[dict[str, Any]]
    decoded: list[DecodedResponse]
    aggregated: AggregatedDecision | None
    measurements: list[dict[str, Any]]
    total_cost_est: float
    ts: str


def riddler_query(
    problem: PrivateGraph,
    *,
    providers: list[str] | None = None,
    models: list[str] | None = None,
    domain: str | None = None,
    steer: str | None = None,
    local_first: bool = True,
) -> RiddlerResult:
    """Full riddler pipeline: compile → randomize → send → measure → decode → aggregate.

    Each provider gets a DIFFERENT surrogate face of the same problem
    (via fingerprint_randomize with different seeds). This means:
    - No provider sees the same story text
    - No provider can cross-reference to infer the territory
    - But all stories preserve the same abstract structure

    Args:
        problem: The private problem graph.
        providers: List of provider IDs. If None, uses ['deepseek', 'deepseek_overmind'].
        models: Optional model override list (must match providers length).
        domain: Optional domain override.
        steer: Optional Ghost steer text to inject.
        local_first: If True, runs a local Ollama model first (costs $0).

    Returns:
        RiddlerResult with all responses, decoded operations, and aggregated consensus.
    """
    if providers is None:
        providers = ["deepseek"]
    if models is None:
        models = [None] * len(providers)

    stories: list[SurrogateStory] = []
    responses: list[dict[str, Any]] = []
    decoded: list[DecodedResponse] = []
    measurements: list[dict[str, Any]] = []

    # Generate a different surrogate face for each provider
    base_seed = hash(problem.goal) & 0x7FFFFFFF

    for i, provider in enumerate(providers):
        seed = base_seed + i * 31337
        story = compile_surrogate(problem, domain=domain, seed=seed)

        # Validate before dispatch
        report = validate_surrogate(story)
        if not report.ok and report.errors:
            responses.append({"ok": False, "error": f"validation failed: {report.errors}",
                              "provider": provider})
            decoded.append(DecodedResponse(
                scratch_id=story.scratch_id, model=models[i] or "none",
                provider=provider, warnings=[f"validation: {report.errors}"],
            ))
            stories.append(story)
            continue

        # If local first and this is a local provider, use Ollama directly
        if local_first and provider in ("ollama", "local"):
            resp = _send_local(story, models[i] or "qwen2.5-coder:7b")
        elif steer:
            resp, measure = send_surrogate_with_steer(
                story, steer, provider=provider, model=models[i],
            )
            measurements.append(measure)
        else:
            resp = send_surrogate(story, provider=provider, model=models[i])

        responses.append(resp)
        stories.append(story)

        # Decode if successful
        if resp.get("ok") and resp.get("content"):
            dec = decode_response(
                story, resp["content"],
                model=resp.get("model", models[i] or "?"),
                provider=provider,
            )
            decoded.append(dec)
            save_decoded_response(dec)
        else:
            decoded.append(DecodedResponse(
                scratch_id=story.scratch_id,
                model=models[i] or "none",
                provider=provider,
                warnings=[resp.get("error", "unknown error")],
            ))

        # Persist the surrogate
        save_surrogate(story)

    # Aggregate across all successful responses
    paired = [(s, d) for s, d in zip(stories, decoded) if d.operations]
    aggregated = aggregate_responses(paired) if paired else None

    # Rough cost estimate (DeepSeek Flash ~$0.27/M input, $1.10/M output)
    total_tokens = sum(r.get("tokens", 0) for r in responses if r.get("ok"))
    cost_per_m = 0.27  # conservative average
    cost_est = (total_tokens / 1_000_000) * cost_per_m

    return RiddlerResult(
        scratch_ids=[s.scratch_id for s in stories],
        stories=stories,
        responses=responses,
        decoded=decoded,
        aggregated=aggregated,
        measurements=measurements,
        total_cost_est=round(cost_est, 5),
        ts=_now(),
    )


def _send_local(story: SurrogateStory, model: str) -> dict[str, Any]:
    """Send a surrogate to a local Ollama model."""
    import urllib.request

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "You are a reasoning assistant. Reason inside the story world. "
                "Use only the allowed story actions. Do not speculate about hidden meanings."
            )},
            {"role": "user", "content": f"{story.story_text}\n\n{story.question}"},
        ],
        "stream": False,
        "options": {"num_predict": 512, "temperature": 0.2},
    }).encode("utf-8")

    t0 = time.time()
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
            latency_ms = round((time.time() - t0) * 1000)
            return {
                "ok": True,
                "content": data.get("message", {}).get("content", ""),
                "model": model,
                "provider": "ollama",
                "tokens": data.get("eval_count", 0),
                "latency_ms": latency_ms,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "provider": "ollama", "model": model}


# ── Convenience ───────────────────────────────────────────────────

def quick_riddler(
    goal: str,
    constraints: list[str] | None = None,
    actors: list[str] | None = None,
    *,
    providers: list[str] | None = None,
    domain: str | None = None,
    steer: str | None = None,
) -> RiddlerResult:
    """One-liner: turn a natural-language goal into a riddler query.

    Example:
        result = quick_riddler(
            "Should the router use heuristic fallback or always call the LLM?",
            constraints=["latency budget 100ms", "accuracy >= 95%"],
            actors=["router", "llm_worker", "operator"],
        )
    """
    graph = PrivateGraph(
        actors=actors or ["agent", "operator"],
        resources=[{"name": "compute", "type": "gpu", "scarcity": "limited"}],
        dependencies=[],
        constraints=constraints or [],
        conflicts=[],
        goal=goal,
    )
    return riddler_query(graph, providers=providers, domain=domain, steer=steer)


# ── CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Riddler transport — send surrogates through providers")
    ap.add_argument("--goal", type=str, default="Should the router use heuristic fallback or always call the LLM?",
                    help="Natural language goal to riddler-wrap")
    ap.add_argument("--providers", type=str, default="deepseek",
                    help="Comma-separated provider list")
    ap.add_argument("--domain", type=str, default=None,
                    help="Domain override (fantasy_village, tower_defense, etc.)")
    ap.add_argument("--steer", type=str, default=None,
                    help="Ghost steer text to inject")
    ap.add_argument("--json", action="store_true",
                    help="Machine-readable JSON output")
    args = ap.parse_args()

    providers = [p.strip() for p in args.providers.split(",")]
    result = quick_riddler(
        args.goal,
        providers=providers,
        domain=args.domain,
        steer=args.steer,
    )

    if args.json:
        out = {
            "goal": args.goal,
            "scratch_ids": result.scratch_ids,
            "responses": [
                {"provider": r.get("provider"), "ok": r.get("ok"),
                 "tokens": r.get("tokens"), "latency_ms": r.get("latency_ms"),
                 "content_preview": (r.get("content", "") or "")[:200]}
                for r in result.responses
            ],
            "decoded": [
                {"model": d.model, "provider": d.provider,
                 "n_operations": len(d.operations),
                 "operations": [o.territory_action for o in d.operations],
                 "warnings": d.warnings}
                for d in result.decoded
            ],
            "aggregated": {
                "consensus_action": result.aggregated.consensus_action if result.aggregated else None,
                "consensus_strength": result.aggregated.consensus_strength if result.aggregated else 0,
                "decisions": result.aggregated.decisions if result.aggregated else {},
                "hallucination_count": result.aggregated.hallucination_count if result.aggregated else 0,
            } if result.aggregated else None,
            "measurements": result.measurements,
            "total_cost_est": result.total_cost_est,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"Goal: {args.goal}")
        print(f"Providers: {providers}")
        print(f"Surrogates: {len(result.stories)}")
        print()
        for i, (r, d) in enumerate(zip(result.responses, result.decoded)):
            provider = r.get("provider", "?")
            print(f"--- {provider} ---")
            if r.get("ok"):
                print(f"  Model: {r.get('model')}  Tokens: {r.get('tokens')}  Latency: {r.get('latency_ms')}ms")
                print(f"  Output: {(r.get('content') or '')[:300]}")
                print(f"  Decoded ops: {[o.territory_action for o in d.operations]}")
                if d.warnings:
                    print(f"  Warnings: {d.warnings}")
            else:
                print(f"  ERROR: {r.get('error')}")
            print()

        if result.aggregated:
            print(f"=== AGGREGATED ===")
            print(f"  Consensus: {result.aggregated.consensus_action}")
            print(f"  Strength: {result.aggregated.consensus_strength:.2f}")
            print(f"  Votes: {result.aggregated.decisions}")
            print(f"  Hallucinations: {result.aggregated.hallucination_count}")

        if result.measurements:
            print(f"=== GHOST MEASUREMENTS ===")
            for m in result.measurements:
                print(f"  flip={m.get('flip')} silence={m.get('silence')} emergent={m.get('emergent')}")

        print(f"\nTotal cost est: ${result.total_cost_est:.5f}")
