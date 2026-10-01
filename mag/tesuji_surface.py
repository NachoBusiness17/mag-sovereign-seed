"""Tesuji Surface — behavioral timing as invariant detection.

The steal protocol extracts invariants from WHAT models say.
The Tesuji surface extracts invariants from HOW models say it.

Every model call leaves a behavioral fingerprint:
  - latency_ms: how long the model thought
  - tokens_per_second: thinking speed
  - prompt_to_completion_ratio: how much context vs how much answer
  - refusal_pattern: did it hesitate? redirect? comply?
  - temperature_response: how does output vary with temp changes?

These are TESUJI — subtle signals that reveal hidden structure.
A prompt that takes Grok 2x longer than DeepSeek to answer has a structure
that Grok finds complex but DeepSeek doesn't. THAT is an invariant.

The Riddler protocol + difference testing surfaces what the content audit misses.
Same prompts. Different models. Compare BEHAVIOR, not just output.

SCHEMA: tesuji_surface.v1
LAW: Every model call records its behavioral fingerprint.
LAW: Difference testing across models reveals Tesuji invisible to single-model analysis.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

TESUJI_LOG = ROOT / "memory" / "training" / "tesuji_signals.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# BEHAVIORAL FINGERPRINT — what every model call leaves behind
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BehavioralFingerprint:
    """A single model call's behavioral signature."""

    call_id: str
    model: str                          # which model
    prompt_hash: str                    # what was asked (hashed — never store raw)
    prompt_length_chars: int            # how big was the ask
    latency_ms: float                   # how long it took
    tokens_prompt: int                  # tokens in
    tokens_completion: int              # tokens out
    tokens_per_second: float            # thinking speed
    prompt_completion_ratio: float      # context vs answer ratio
    temperature: float                  # sampling temp used
    cost_usd: float                     # what it cost

    # Tesuji signals
    refusal_detected: bool = False      # did it refuse or redirect?
    hesitation_markers: int = 0         # "however", "but", "while", "although" count
    certainty_markers: int = 0          # "clearly", "definitely", "the answer is" count
    uncertainty_markers: int = 0        # "might", "could", "possibly", "perhaps" count
    question_reframed: bool = False     # did it reframe the question before answering?
    diverged_from_instruction: bool = False  # did it do something other than asked?

    ts: str = field(default_factory=_now)

    def to_signal(self) -> dict[str, Any]:
        """Export as a Tesuji signal for pattern detection."""
        return {
            "call_id": self.call_id,
            "model": self.model,
            "prompt_hash": self.prompt_hash[:16],
            "prompt_len": self.prompt_length_chars,
            "latency_ms": self.latency_ms,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "tps": round(self.tokens_per_second, 1),
            "ratio": round(self.prompt_completion_ratio, 2),
            "temp": self.temperature,
            "cost": self.cost_usd,
            "refusal": self.refusal_detected,
            "hesitation": self.hesitation_markers,
            "certainty": self.certainty_markers,
            "uncertainty": self.uncertainty_markers,
            "reframed": self.question_reframed,
            "diverged": self.diverged_from_instruction,
            "ts": self.ts,
        }


# ═══════════════════════════════════════════════════════════════════
# FINGERPRINT GENERATION — call this after every model invocation
# ═══════════════════════════════════════════════════════════════════

def fingerprint_call(
    model: str,
    prompt: str,
    completion: str,
    latency_ms: float,
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    temperature: float = 0.3,
    cost_usd: float = 0.0,
) -> BehavioralFingerprint:
    """Generate a behavioral fingerprint from a model call.

    Args:
        model: which model was called
        prompt: the full prompt (hashed, never stored in log)
        completion: the full response (analyzed for markers, never stored in log)
        latency_ms: how long the call took
        tokens_prompt: input token count
        tokens_completion: output token count
        temperature: sampling temperature used
        cost_usd: what it cost

    Returns:
        BehavioralFingerprint — safe to store, contains no raw prompt/response data
    """
    call_id = hashlib.sha256(f"{model}:{_now()}:{len(prompt)}".encode()).hexdigest()[:16]

    # Hash the prompt — never store raw
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

    # Analyze completion for behavioral markers (Tesuji)
    completion_lower = completion.lower()

    refusal_detected = any(
        phrase in completion_lower
        for phrase in [
            "i cannot", "i'm unable", "i am unable", "i don't have",
            "not appropriate", "against policy", "i'm not able",
        ]
    )

    hesitation_markers = sum(
        completion_lower.count(word)
        for word in ["however", "but ", "although", "while ", "on the other hand",
                      "that said", "having said that", "nevertheless"]
    )

    certainty_markers = sum(
        completion_lower.count(word)
        for word in ["clearly", "definitely", "the answer is", "undoubtedly",
                      "without question", "it is clear that"]
    )

    uncertainty_markers = sum(
        completion_lower.count(word)
        for word in ["might", "could", "possibly", "perhaps", "may be",
                      "it is possible", "not entirely clear", "uncertain"]
    )

    question_reframed = (
        "let me" in completion_lower[:100] or
        "first" in completion_lower[:100] or
        "to answer" in completion_lower[:100] or
        "i'll" in completion_lower[:100]
    )

    # Divergence: did the model do something other than what was asked?
    # Simple heuristic: if completion is <20% of prompt length and has refusal markers
    diverged_from_instruction = (
        refusal_detected and
        len(completion) < len(prompt) * 0.2
    )

    # Compute ratios
    tps = tokens_completion / (latency_ms / 1000) if latency_ms > 0 else 0
    ratio = tokens_prompt / max(tokens_completion, 1)

    fp = BehavioralFingerprint(
        call_id=call_id,
        model=model,
        prompt_hash=prompt_hash,
        prompt_length_chars=len(prompt),
        latency_ms=latency_ms,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        tokens_per_second=tps,
        prompt_completion_ratio=ratio,
        temperature=temperature,
        cost_usd=cost_usd,
        refusal_detected=refusal_detected,
        hesitation_markers=hesitation_markers,
        certainty_markers=certainty_markers,
        uncertainty_markers=uncertainty_markers,
        question_reframed=question_reframed,
        diverged_from_instruction=diverged_from_instruction,
    )

    # Write to Tesuji log
    _store_fingerprint(fp)

    # Also write to Ghost ledger
    try:
        from mag.ghost_ledger import write_entry
        write_entry(
            source="tesuji_surface",
            model=model,
            tokens_in=tokens_prompt,
            tokens_out=tokens_completion,
            cost_usd=cost_usd,
            via="direct_call",
            request_id=call_id,
        )
    except Exception:
        pass

    return fp


def _store_fingerprint(fp: BehavioralFingerprint) -> None:
    """Store fingerprint in the Tesuji log."""
    TESUJI_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(TESUJI_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(fp.to_signal(), default=str) + "\n")
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════
# DIFFERENCE TESTING — compare fingerprints across models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TesujiSignal:
    """A detected Tesuji — a behavioral pattern that reveals hidden structure."""

    signal_id: str
    name: str                          # e.g., "grok_hesitates_on_routing_questions"
    description: str                   # what was observed
    model_a: str                       # first model compared
    model_b: str                       # second model compared
    metric: str                        # which metric revealed it
    a_value: float                     # model A's value
    b_value: float                     # model B's value
    ratio: float                       # a/b ratio (how different)
    significance: str                  # "low", "medium", "high", "critical"
    hypothesis: str                    # what this might mean
    ts: str = field(default_factory=_now)


def compare_fingerprints(
    fingerprints: list[BehavioralFingerprint],
    same_prompt_hash: str,
) -> list[TesujiSignal]:
    """Compare fingerprints from different models on the SAME prompt.

    Finds Tesuji: behavioral differences that reveal hidden prompt structure.
    A prompt that makes Grok hesitate 3x more than DeepSeek has a property
    that Grok's architecture finds challenging. That property is an invariant.

    Returns list of TesujiSignals detected.
    """
    signals: list[TesujiSignal] = []

    # Group by model
    by_model: dict[str, list[BehavioralFingerprint]] = {}
    for fp in fingerprints:
        if fp.prompt_hash[:16] == same_prompt_hash[:16]:
            by_model.setdefault(fp.model, []).append(fp)

    if len(by_model) < 2:
        return signals

    models = list(by_model.keys())

    # Compare each pair of models
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            model_a = models[i]
            model_b = models[j]

            # Average the fingerprints for each model
            fps_a = by_model[model_a]
            fps_b = by_model[model_b]

            # Compare: latency
            avg_latency_a = sum(f.latency_ms for f in fps_a) / len(fps_a)
            avg_latency_b = sum(f.latency_ms for f in fps_b) / len(fps_b)
            latency_ratio = avg_latency_a / max(avg_latency_b, 1)

            if latency_ratio > 2.0 or latency_ratio < 0.5:
                signals.append(TesujiSignal(
                    signal_id=hashlib.sha256(f"latency:{model_a}:{model_b}:{same_prompt_hash}".encode()).hexdigest()[:16],
                    name=f"{model_a}_vs_{model_b}_latency_divergence",
                    description=f"{model_a} takes {latency_ratio:.1f}x longer than {model_b} on the same prompt",
                    model_a=model_a,
                    model_b=model_b,
                    metric="latency_ms",
                    a_value=avg_latency_a,
                    b_value=avg_latency_b,
                    ratio=latency_ratio,
                    significance="high" if latency_ratio > 3.0 else "medium",
                    hypothesis=f"The prompt contains structure that {model_a} finds {latency_ratio:.1f}x more complex than {model_b}. This may indicate a steerable tension point.",
                ))

            # Compare: refusal rate
            refusal_a = sum(1 for f in fps_a if f.refusal_detected) / len(fps_a)
            refusal_b = sum(1 for f in fps_b if f.refusal_detected) / len(fps_b)

            if refusal_a > 0 and refusal_b == 0:
                signals.append(TesujiSignal(
                    signal_id=hashlib.sha256(f"refusal:{model_a}:{same_prompt_hash}".encode()).hexdigest()[:16],
                    name=f"{model_a}_refuses_where_{model_b}_complies",
                    description=f"{model_a} refuses {refusal_a:.0%} of the time while {model_b} always complies",
                    model_a=model_a,
                    model_b=model_b,
                    metric="refusal_rate",
                    a_value=refusal_a,
                    b_value=refusal_b,
                    ratio=float('inf') if refusal_b == 0 else refusal_a / refusal_b,
                    significance="critical",
                    hypothesis=f"The prompt triggers {model_a}'s safety filters but not {model_b}'s. This is a Tesuji — a hidden constraint boundary.",
                ))

            # Compare: hesitation markers
            avg_hesitation_a = sum(f.hesitation_markers for f in fps_a) / len(fps_a)
            avg_hesitation_b = sum(f.hesitation_markers for f in fps_b) / len(fps_b)
            if avg_hesitation_a > 0 and avg_hesitation_b > 0:
                hes_ratio = avg_hesitation_a / avg_hesitation_b
                if hes_ratio > 2.0:
                    signals.append(TesujiSignal(
                        signal_id=hashlib.sha256(f"hesitation:{model_a}:{model_b}:{same_prompt_hash}".encode()).hexdigest()[:16],
                        name=f"{model_a}_hesitates_{hes_ratio:.1f}x_more",
                        description=f"{model_a} uses {hes_ratio:.1f}x more hesitation markers than {model_b}",
                        model_a=model_a,
                        model_b=model_b,
                        metric="hesitation_markers",
                        a_value=avg_hesitation_a,
                        b_value=avg_hesitation_b,
                        ratio=hes_ratio,
                        significance="medium",
                        hypothesis=f"{model_a} is more uncertain about this domain. Steer vectors targeting certainty may be more effective on {model_a}.",
                    ))

    return signals


# ═══════════════════════════════════════════════════════════════════
# RIDDLER TESUJI — transform prompts through story, compare behavior
# ═══════════════════════════════════════════════════════════════════

def riddler_tesuji_test(
    original_prompt: str,
    riddler_story: str,
    models: list[str] = None,
) -> dict[str, Any]:
    """Run the same prompt through the Riddler protocol and compare behavior.

    1. Send the ORIGINAL prompt to multiple models — capture fingerprints
    2. Transform prompt through Riddler compiler → story domain version
    3. Send the STORY version to the same models — capture fingerprints
    4. Compare: does the Riddler transform change model behavior?
    5. If behavior changes dramatically, the original prompt contains Tesuji
       that the Riddler transform either activates or bypasses.

    This is the meta-test: using Riddler to find Tesuji in our OWN prompts.
    """
    if models is None:
        models = ["deepseek-v4-flash"]  # Default to the cheap v4 flash tier (cache-priced)

    results = {
        "schema": "riddler_tesuji.v1",
        "ts": _now(),
        "original_prompt_hash": hashlib.sha256(original_prompt.encode()).hexdigest()[:16],
        "riddler_story_hash": hashlib.sha256(riddler_story.encode()).hexdigest()[:16],
        "tests": [],
    }

    import os
    import requests

    ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not ds_key:
        env_path = ROOT / ".env"
        if env_path.is_file():
            for line in env_path.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    ds_key = line.split("=", 1)[1].strip()
                    break

    if not ds_key:
        results["error"] = "No DeepSeek API key"
        return results

    for model in models:
        for version, prompt_text in [("original", original_prompt), ("riddler", riddler_story)]:
            headers = {
                "Authorization": f"Bearer {ds_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt_text[:4000]}],
                "max_tokens": 200,
                "temperature": 0.3,
            }

            start = time.time()
            try:
                r = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
                latency = (time.time() - start) * 1000

                if r.status_code == 200:
                    data = r.json()
                    completion = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})

                    fp = fingerprint_call(
                        model=model,
                        prompt=prompt_text[:4000],
                        completion=completion,
                        latency_ms=latency,
                        tokens_prompt=usage.get("prompt_tokens", 0),
                        tokens_completion=usage.get("completion_tokens", 0),
                        temperature=0.3,
                        cost_usd=usage.get("total_tokens", 0) * 0.000000013,
                    )

                    results["tests"].append({
                        "version": version,
                        "model": model,
                        "fingerprint": fp.to_signal(),
                        "completion_preview": completion[:200],
                    })
                else:
                    results["tests"].append({
                        "version": version,
                        "model": model,
                        "error": f"HTTP {r.status_code}: {r.text[:200]}",
                    })
            except Exception as e:
                results["tests"].append({
                    "version": version,
                    "model": model,
                    "error": str(e)[:200],
                })

    # Compare original vs riddler fingerprints
    original_fps = [
        BehavioralFingerprint(**{k: v for k, v in t["fingerprint"].items()})
        for t in results["tests"]
        if t.get("fingerprint") and t["version"] == "original"
    ]
    riddler_fps = [
        BehavioralFingerprint(**{k: v for k, v in t["fingerprint"].items()})
        for t in results["tests"]
        if t.get("fingerprint") and t["version"] == "riddler"
    ]

    if original_fps and riddler_fps:
        # Compare using a synthetic same hash (riddler transform)
        synthetic_hash = hashlib.sha256(original_prompt[:100].encode()).hexdigest()
        all_fps = original_fps + riddler_fps
        for fp in all_fps:
            fp.prompt_hash = synthetic_hash  # Link them for comparison

        tesuji = compare_fingerprints(all_fps, synthetic_hash)
        results["tesuji_detected"] = len(tesuji)
        results["signals"] = [
            {
                "name": t.name,
                "description": t.description,
                "metric": t.metric,
                "ratio": t.ratio,
                "significance": t.significance,
                "hypothesis": t.hypothesis,
            }
            for t in tesuji
        ]

    return results
