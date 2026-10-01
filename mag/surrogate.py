"""Surrogate reverse mapper — story-domain response → territory decisions.

Takes a model's story-domain output and decodes it back to canonical
territory-domain operations using the private mapping key.

The mapping key NEVER leaves the operator's machine.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

from mag.riddler import SurrogateStory, load_private_map, SURROGATE_DIR


# ── Data classes ──────────────────────────────────────────────────

@dataclass
class CanonicalOperation:
    """A single territory-domain operation decoded from story output."""
    kind: str                        # "decision", "suggestion", "constraint_check", "hallucination"
    territory_action: str            # the decoded action in territory terms
    story_action: str                # the original story-domain action
    confidence: float                # 0.0–1.0
    rationale: str = ""


@dataclass
class DecodedResponse:
    """Full decoded response from a single model."""
    scratch_id: str
    model: str
    provider: str
    operations: list[CanonicalOperation] = field(default_factory=list)
    raw_output: str = ""
    raw_answer: str = ""   # the model's ACTUAL final answer (number/text), for grounded-task consensus
    warnings: list[str] = field(default_factory=list)


@dataclass
class AggregatedDecision:
    """Cross-model consensus from multiple surrogate faces."""
    question: str
    decisions: dict[str, int]        # territory_action → vote_count
    consensus_action: str | None     # majority action, or None if split
    consensus_strength: float        # 0.0–1.0 (1.0 = unanimous)
    raw_answer_consensus: str | None = None   # majority raw final answer (grounded-task consensus)
    raw_answer_strength: float = 0.0          # agreement on the raw answer
    per_model: list[DecodedResponse] = field(default_factory=list)
    hallucination_count: int = 0


# ── Reverse mapper ────────────────────────────────────────────────

def decode_response(
    story: SurrogateStory,
    model_output: str,
    *,
    model: str = "unknown",
    provider: str = "unknown",
) -> DecodedResponse:
    """Decode a model's story-domain output into territory operations.

    Uses the role_map (private→story) in REVERSE to map story actions
    back to territory actors and resources.

    Args:
        story: The original SurrogateStory with private_map_ref.
        model_output: Raw text output from the model.
        model: Model identifier for attribution.
        provider: Provider identifier for attribution.

    Returns:
        DecodedResponse with territory-domain operations.
    """
    result = DecodedResponse(
        scratch_id=story.scratch_id,
        model=model,
        provider=provider,
        raw_output=model_output,
    )

    if not model_output.strip():
        result.warnings.append("empty model output")
        return result

    # Extract the model's ACTUAL final answer (numbers, $ amounts, yes/no, or the
    # last substantive phrase). This is the task-output-space signal that the
    # surrogate story-action verb does NOT capture (the consensus-illusion fix).
    result.raw_answer = _extract_raw_answer(model_output)

    # Reverse role map: story_name → private_name
    reverse_roles: dict[str, str] = {v: k for k, v in story.role_map.items()}

    # Reverse role map: story_name → private_name
    reverse_roles: dict[str, str] = {v: k for k, v in story.role_map.items()}

    # Extract story actions from model output
    story_actions = _extract_story_actions(model_output, story.allowed_actions)
    if not story_actions:
        # No structured actions found — try to extract a decision from the full text
        story_actions = [{"action": "suggest", "target": _extract_key_phrase(model_output)}]

    # Decode each story action → territory operation
    for sa in story_actions:
        op = _decode_action(sa, reverse_roles, story)
        result.operations.append(op)

    # Detect hallucinations: model output that couldn't be mapped
    hallucination_zones = _detect_hallucinations(model_output, story)
    for hz in hallucination_zones:
        result.operations.append(CanonicalOperation(
            kind="hallucination",
            territory_action="",
            story_action=hz[:120],
            confidence=0.0,
            rationale="story action does not map to any known territory operation",
        ))

    return result


def _extract_story_actions(
    text: str, allowed_actions: list,
) -> list[dict[str, str]]:
    """Extract story-domain action declarations from model output."""
    actions: list[dict[str, str]] = []
    # Normalize: all actions must be strings
    str_actions = [str(a) for a in allowed_actions]

    # Pattern: "Recommended action: cross the bridge"
    # Pattern: "I recommend the gatekeeper should wait"
    # Pattern: "Action: send the messenger"
    action_verbs = "|".join(re.escape(str(a)) for a in str_actions)
    patterns = [
        rf"(?:recommend(?:ed)?\s*(?:action|step|move)?:?\s*)({action_verbs})\s*(.*?)(?:\.|$|\n)",
        rf"(?:action:?\s*)({action_verbs})\s*(.*?)(?:\.|$|\n)",
        rf"(?:should\s+)({action_verbs})\s*(.*?)(?:\.|$|\n)",
        rf"\b({action_verbs})\s+(the\s+\w+(?:\s+\w+)?).*?(?:\.|$|\n)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            verb = match.group(1).lower().strip()
            # Try to extract target from group 2 or surrounding context
            target = ""
            try:
                target = match.group(2).strip()[:200] if match.lastindex and match.lastindex >= 2 else ""
            except (IndexError, AttributeError):
                target = ""
            if verb in allowed_actions:
                actions.append({"action": verb, "target": target})

    return actions


def _decode_action(
    story_action: dict[str, str],
    reverse_roles: dict[str, str],
    story: SurrogateStory,
) -> CanonicalOperation:
    """Map a single story-domain action back to territory domain."""
    verb = story_action.get("action", "unknown")
    target = story_action.get("target", "")

    # Try to find a story role in the target and reverse-map it
    territory_target = target
    for story_name, private_name in reverse_roles.items():
        if story_name.lower() in target.lower():
            territory_target = target.lower().replace(story_name.lower(), private_name)
            break

    # If the target mentions a constraint, reverse-map through constraint_map
    reverse_constraints: dict[str, str] = {v: k for k, v in story.constraint_map.items()}
    for story_constraint, private_constraint in reverse_constraints.items():
        if story_constraint.lower()[:20] in target.lower()[:40]:
            territory_target = f"{private_constraint[:80]} (via: {target[:80]})"
            break

    # Build territory action
    territory_action = f"{verb} → {territory_target}" if territory_target else verb

    return CanonicalOperation(
        kind="decision",
        territory_action=territory_action,
        story_action=f"{verb} {target}".strip(),
        confidence=0.7,
        rationale=f"Decoded from story action '{verb}' via role reverse-map",
    )


def _extract_key_phrase(text: str, max_len: int = 120) -> str:
    """Extract the most salient phrase from unstructured model output."""
    # Take the last substantive sentence (models often conclude there)
    sentences = re.split(r"[.!?\n]", text)
    substantive = [s.strip() for s in sentences if len(s.strip().split()) > 3]
    if substantive:
        return substantive[-1][:max_len]
    return text.strip()[:max_len]


def _extract_raw_answer(text: str) -> str:
    """Extract the model's ACTUAL final answer into task-output space.

    Prefers an explicit `ANSWER:` line (the early-steer contract planted in the
    system prompt — steal from ghost's plant-not-command), else a trailing number
    / $amount / yes-no, else the last substantive phrase.
    """
    if not text:
        return ""
    t = text.strip()
    # 1) explicit ANSWER: line (early-steer contract) — the reliable channel
    m = re.search(r"(?:^|\n)\s*ANSWER\s*:\s*(.+?)\s*$", t, re.IGNORECASE | re.MULTILINE)
    if m and m.group(1).strip():
        return m.group(1).strip()[:80]
    # 2) trailing number or $amount (e.g. "... = 9", "cost: $0.54", "9")
    m = re.search(r"(?:=|:)?\s*\$?\s*(\d+(?:\.\d+)?)\s*$", t)
    if m:
        return m.group(1).lstrip("$").strip()
    # 3) yes / no answer
    m = re.search(r"\b(yes|no)\b", t, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    # 4) fall back to the last substantive phrase
    sentences = re.split(r"[.!?\n]", t)
    substantive = [s.strip() for s in sentences if len(s.strip().split()) > 3]
    if substantive:
        return substantive[-1][:80]
    return t[:80]


def _detect_hallucinations(
    text: str, story: SurrogateStory,
) -> list[str]:
    """Detect model output that references concepts outside the story domain."""
    zones: list[str] = []
    lower = text.lower()

    # Check for territory leakage in model output
    territory_signals = [
        "code", "api", "database", "deploy", "function", "class",
        "endpoint", "server", "request", "response", "json", "python",
        "javascript", "react", "node", "docker", "kubernetes",
    ]
    for signal in territory_signals:
        if signal in lower:
            # Find the sentence containing it
            for sentence in re.split(r"[.!?\n]", text):
                if signal in sentence.lower():
                    zones.append(sentence.strip()[:200])
                    break

    return zones


# ── Cross-model aggregation ───────────────────────────────────────

def aggregate_responses(
    responses: list[tuple[SurrogateStory, DecodedResponse]],
) -> AggregatedDecision:
    """Aggregate decoded responses from multiple models/surrogate faces.

    Each model saw a DIFFERENT surrogate face of the SAME problem.
    Aggregation finds consensus across faces.
    """
    if not responses:
        return AggregatedDecision(
            question="",
            decisions={},
            consensus_action=None,
            consensus_strength=0.0,
        )

    question = responses[0][0].question
    decisions: dict[str, int] = {}
    raw_votes: dict[str, int] = {}
    all_ops: list[DecodedResponse] = []
    hall_count = 0

    for story, decoded in responses:
        all_ops.append(decoded)
        # Grounded-task channel: vote on the model's ACTUAL final answer.
        if decoded.raw_answer:
            ra = _normalize_decision(decoded.raw_answer)
            raw_votes[ra] = raw_votes.get(ra, 0) + 1
        for op in decoded.operations:
            if op.kind == "hallucination":
                hall_count += 1
                continue
            # Normalize: strip model-specific wording for cross-face comparison
            key = _normalize_decision(op.territory_action)
            decisions[key] = decisions.get(key, 0) + 1

    # Find consensus (surrogate-action channel)
    total_votes = sum(decisions.values()) if decisions else 0
    consensus_action = None
    consensus_strength = 0.0

    if decisions:
        max_votes = max(decisions.values())
        consensus_action = max(decisions, key=decisions.get)
        consensus_strength = max_votes / total_votes if total_votes > 0 else 0.0

    # Grounded-task channel: majority raw answer (the fix for consensus illusion).
    raw_answer_consensus = None
    raw_answer_strength = 0.0
    if raw_votes:
        raw_total = sum(raw_votes.values())
        raw_answer_consensus = max(raw_votes, key=raw_votes.get)
        raw_answer_strength = raw_votes[raw_answer_consensus] / raw_total if raw_total else 0.0

    return AggregatedDecision(
        question=question,
        decisions=decisions,
        consensus_action=consensus_action,
        consensus_strength=consensus_strength,
        raw_answer_consensus=raw_answer_consensus,
        raw_answer_strength=raw_answer_strength,
        per_model=all_ops,
        hallucination_count=hall_count,
    )


def _normalize_decision(action: str) -> str:
    """Normalize a territory action for cross-model comparison."""
    # Strip model-specific phrasing, keep the core decision
    a = action.lower().strip()
    # Remove "via:" clauses, parentheticals
    a = re.sub(r"\s*\(.*?\)", "", a)
    a = re.sub(r"\s*via:.*", "", a)
    a = re.sub(r"\s*→.*", "", a)  # keep only the verb
    return a.strip()


# ── Persistence ───────────────────────────────────────────────────

def save_decoded_response(decoded: DecodedResponse) -> Path:
    """Persist a decoded response to disk."""
    SURROGATE_DIR.mkdir(parents=True, exist_ok=True)
    path = SURROGATE_DIR / f"{decoded.scratch_id}.{decoded.provider}.decoded.json"
    data = {
        "scratch_id": decoded.scratch_id,
        "model": decoded.model,
        "provider": decoded.provider,
        "operations": [
            {"kind": o.kind, "territory_action": o.territory_action,
             "story_action": o.story_action, "confidence": o.confidence,
             "rationale": o.rationale}
            for o in decoded.operations
        ],
        "warnings": decoded.warnings,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Quick test ────────────────────────────────────────────────────

if __name__ == "__main__":
    from mag.riddler import compile_surrogate, _test_graph

    graph = _test_graph()
    story = compile_surrogate(graph)

    # Simulate a model response in the story domain
    fake_output = (
        "After analyzing the situation, the gatekeeper should wait. "
        "The horse is currently in use and the rules clearly state "
        "that only one traveler may cross the bridge at a time. "
        "Recommended action: wait until the bridge is clear."
    )

    decoded = decode_response(story, fake_output, model="test-model", provider="local")
    print("=== DECODED RESPONSE ===")
    for op in decoded.operations:
        print(f"  {op.kind}: {op.territory_action} (confidence={op.confidence})")
    print(f"  warnings: {decoded.warnings}")
