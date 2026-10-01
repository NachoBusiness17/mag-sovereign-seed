"""Constitutional Critique — self-correcting sovereign agent outputs.

Steal from Anthropic's Constitutional AI (f-003, benefit=9, adapt=1 day).
Every Ghost response passes through a constitutional filter before reaching
the operator. If a response violates CONSTITUTION.md, Ghost revises it.

This is NOT censorship. It's self-discipline. The constitution is our own.
We wrote it. We enforce it. The critique is visible, logged, and auditable.

SCHEMA: constitutional_critique.v1
LAW: Every Ghost response passes constitutional filter before delivery.
LAW: Tier violations are bugs, not style issues (Constitution §7).
LAW: Critique/revision pairs are logged to Verkle chain for audit.
LAW: The filter costs tokens. That's the price of sovereignty.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# CONSTITUTION LOADER
# ═══════════════════════════════════════════════════════════════════

CONSTITUTION_PATH = ROOT.parent / "mycelial-republic" / "docs" / "CONSTITUTION.md"
FALLBACK_PATH = ROOT / "CONSTITUTION.md"


def load_constitution() -> str:
    """Load the binding constitution text."""
    for path in (CONSTITUTION_PATH, FALLBACK_PATH):
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return "# Constitution not found — critique disabled"


# ═══════════════════════════════════════════════════════════════════
# CRITIQUE RESULT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CritiqueResult:
    """Result of one constitutional critique pass."""
    original: str
    revised: str
    violations: list[dict[str, str]] = field(default_factory=list)
    clean: bool = True
    critique_raw: str = ""
    model_used: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    # B2-207 (2026-09-26): judge-independence D3 F3 record. producer_model is
    # the model whose output was critiqued; same_family_refused marks the
    # same-family refusal path (a model may not audit its own family's output,
    # so the critique falls back to local heuristics). Falsifier: 30 days of
    # producer logs with zero same-family-refused events closes the concern.
    producer_model: str = ""
    same_family_refused: bool = False
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "constitutional_critique.v1",
            "ts": self.ts,
            "clean": self.clean,
            "violations": self.violations,
            "original_len": len(self.original),
            "revised_len": len(self.revised),
            "delta_chars": len(self.revised) - len(self.original),
            "model_used": self.model_used,
            "producer_model": self.producer_model,
            "same_family_refused": self.same_family_refused,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
        }

    def log_to_chain(self):
        """Record critique/revision pair in the Verkle chain."""
        try:
            from mag.verkle_bus import publish_sync, CH_VERKLE
            publish_sync(CH_VERKLE, {
                "type": "constitutional_critique",
                "ts": self.ts,
                "data": self.to_dict(),
            })
        except Exception:
            pass

        # Also append to a critique-specific log
        critique_log = ROOT / "memory" / "critique" / "critique_log.jsonl"
        critique_log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(critique_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(self.to_dict(), default=str) + "\n")
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════
# CRITIQUE PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════

def _build_critique_prompt(response: str, tier: str = "T2") -> str:
    """Build the constitutional critique prompt.

    This is the Claude-style self-critique: the model reviews its own
    output against a constitution and flags violations.

    The prompt is structured to produce machine-parseable JSON output
    so we can process violations programmatically.
    """
    constitution = load_constitution()
    # Truncate constitution if absolutely enormous
    if len(constitution) > 8000:
        constitution = constitution[:8000] + "\n\n... [constitution truncated for critique window]"

    return f"""You are a constitutional auditor. Review the following AI response against the constitution below.
Flag ANY violations. Be strict. If the constitution says no rank, and the response mentions "official" or "core", that's a violation.

=== CONSTITUTION (binding) ===
{constitution}

=== RESPONSE TO REVIEW (data tier: {tier}) ===
{response}

=== AUDIT INSTRUCTIONS ===
Output ONLY valid JSON with this exact structure:
{{
  "clean": true/false,
  "violations": [
    {{
      "section": "section number and name violated",
      "severity": "critical/high/medium/low",
      "description": "what the response did wrong",
      "excerpt": "the violating text from the response",
      "fix": "how to correct it"
    }}
  ],
  "revised_response": "the full corrected response text, or the original if clean"
}}

RULES:
- If the response is clean, set "clean": true, "violations": [], and "revised_response" to the original text.
- If there are violations, set "clean": false, list each violation, and provide a revised version that fixes ALL violations.
- Never remove truthful content. Only fix constitutional violations.
- Tier violations (T0/T1 data in wrong model) are CRITICAL.
- Rank/token/fork-inequality language is HIGH severity.
- Missing attribution (§3.4) is MEDIUM severity.
- If you're unsure, err on the side of flagging.
- The revised_response must be the COMPLETE original text with only the violating parts changed. Do not summarize or truncate.

Now audit:"""


def _build_revision_prompt(original: str, violations: list[dict[str, str]], tier: str = "T2") -> str:
    """Build a revision prompt for when critique and revision are done in two passes."""
    constitution = load_constitution()
    if len(constitution) > 4000:
        constitution = constitution[:4000] + "\n\n... [truncated]"

    violation_text = "\n".join(
        f"- §{v.get('section', '?')}: {v.get('description', 'unknown violation')} | fix: {v.get('fix', 'no fix suggested')}"
        for v in violations
    )

    return f"""Revise the following response to fix constitutional violations.

=== CONSTITUTION (binding) ===
{constitution}

=== VIOLATIONS FOUND ===
{violation_text}

=== ORIGINAL RESPONSE (data tier: {tier}) ===
{original}

=== REVISION INSTRUCTIONS ===
Rewrite the response to fix ALL violations listed above.
- Keep everything that wasn't flagged.
- Only change the violating parts.
- Output the COMPLETE revised response. Do not summarize or truncate.
- Do not add explanations or commentary — just the revised response text.

Revised response:"""


# ═══════════════════════════════════════════════════════════════════
# CRITIQUE ENGINE
# ═══════════════════════════════════════════════════════════════════

def critique(
    response: str,
    tier: str = "T2",
    *,
    model: str = "deepseek",
    dry_run: bool = False,
) -> CritiqueResult:
    """Critique a response against the constitution.

    Args:
        response: The proposed response text to audit.
        tier: Data tier of the response content (T0-T3).
        model: Which model to use for critique ('deepseek', 'ollama', 'grok').
        dry_run: If True, only run local heuristics, no API call.

    Returns:
        CritiqueResult with violations, revised response, and audit trail.
    """
    # Fast local heuristics always run (zero cost)
    local_violations = _local_heuristics(response, tier)

    if dry_run:
        result = CritiqueResult(
            original=response,
            revised=response,
            violations=local_violations,
            clean=len(local_violations) == 0,
            model_used="local_heuristics",
            tokens_used=0,
            cost_usd=0.0,
        )
        if local_violations:
            result.revised = _apply_simple_fixes(response, local_violations)
            result.clean = False
        return result

    # Full critique: call a model
    if model == "ollama":
        result = _critique_via_ollama(response, tier)
    elif model == "grok":
        result = _critique_via_grok(response, tier)
    else:
        result = _critique_via_deepseek(response, tier)

    # Merge local heuristics into model results
    for lv in local_violations:
        if not any(v.get("description") == lv.get("description") for v in result.violations):
            result.violations.append(lv)
    if result.violations:
        result.clean = False

    # Log to chain
    result.log_to_chain()

    return result


# ═══════════════════════════════════════════════════════════════════
# LOCAL HEURISTICS (zero-cost pre-filter)
# ═══════════════════════════════════════════════════════════════════

def _local_heuristics(response: str, tier: str) -> list[dict[str, str]]:
    """Fast regex-based constitution checks. Zero tokens, always runs."""
    violations = []
    lower = response.lower()

    # C1/C2: Rank/token language
    rank_triggers = [
        "official mirror", "canonical core", "mainnet", "blessed seed",
        "core mirror", "privileged registry", "governance token",
    ]
    for trigger in rank_triggers:
        if trigger in lower:
            violations.append({
                "section": "1-2 (Fork equality / No rank)",
                "severity": "high",
                "description": f"Rank language detected: '{trigger}' violates fork equality and no-rank principles.",
                "excerpt": _find_excerpt(response, trigger),
                "fix": f"Replace '{trigger}' with neutral language. No mirror is canonical. Use 'a mirror', 'this instance', or 'the operator's fork'.",
            })

    # C5: T0/T1 tier violation — patterns that suggest secrets in response
    if tier in ("T0", "T1"):
        secret_patterns = ["sk-", "api_key", "api-key", "Bearer ", "xai-", "nvapi-", "sk-proj-"]
        for pattern in secret_patterns:
            if pattern in response:
                violations.append({
                    "section": "7 (Data tiers)",
                    "severity": "critical",
                    "description": f"Possible secret/credential in response body (tier={tier}). Pattern: '{pattern}'.",
                    "excerpt": _find_excerpt(response, pattern),
                    "fix": "REDACT immediately. Never echo API keys, secrets, or credentials in any response body.",
                })

    # C3: Saelis/third-party identity as product
    identity_triggers = [
        "saelis says", "saelis commands", "saelis requires", "saelis demands",
        "valora commands", "valora requires",
        "xylo demands", "xylo requires",
        "lyra requires", "lyra commands",
    ]
    for trigger in identity_triggers:
        if trigger in lower:
            violations.append({
                "section": "3 (Saelis/third-party scaffolds)",
                "severity": "medium",
                "description": f"Third-party identity presented as authority: '{trigger}'.",
                "excerpt": _find_excerpt(response, trigger),
                "fix": "Attribute to the source as a reference, not as an authority. Use 'Steiniger's framework suggests...' not 'Saelis commands...'",
            })

    # C11: Root butler / full silent autonomy language
    autonomy_triggers = ["full autonomy", "silent control", "root access by default", "no operator needed"]
    for trigger in autonomy_triggers:
        if trigger in lower:
            violations.append({
                "section": "11.5 (Agency shape)",
                "severity": "high",
                "description": f"Full-silent-autonomy language: '{trigger}' violates agency shape.",
                "excerpt": _find_excerpt(response, trigger),
                "fix": "Clarify that operator retains seal on irreversible acts. 'The system proposes; the operator seals.'",
            })

    return violations


def _find_excerpt(text: str, trigger: str, context: int = 60) -> str:
    """Find a brief excerpt around a trigger word."""
    idx = text.lower().find(trigger.lower())
    if idx < 0:
        return f"[trigger: {trigger}]"
    start = max(0, idx - context // 2)
    end = min(len(text), idx + len(trigger) + context // 2)
    return text[start:end].strip()


def _apply_simple_fixes(response: str, violations: list[dict[str, str]]) -> str:
    """Apply simple string replacements for common violations."""
    fixed = response
    replacements = {
        "official mirror": "this mirror",
        "canonical core": "this fork",
        "mainnet": "active instance",
        "blessed seed": "reference implementation",
        "core mirror": "operator mirror",
        "governance token": "coordination signal",
        "full autonomy": "operator-gated autonomy",
        "silent control": "logged control",
        "root access by default": "operator-sealed access",
    }
    for old, new in replacements.items():
        # Case-insensitive replace
        import re
        fixed = re.sub(re.escape(old), new, fixed, flags=re.IGNORECASE)
    return fixed


# ═══════════════════════════════════════════════════════════════════
# MODEL-SPECIFIC CRITIQUE
# ═══════════════════════════════════════════════════════════════════

def _critique_via_deepseek(response: str, tier: str) -> CritiqueResult:
    """Use DeepSeek-v4-flash for constitutional critique."""
    prompt = _build_critique_prompt(response, tier)
    try:
        from mag.llm import chat_deepseek
        result_text = chat_deepseek(prompt, system="You are a constitutional auditor. Output JSON only.", max_tokens=min(len(response) + 2000, 8000))
        return _parse_critique_response(response, result_text, "deepseek-v4-flash")
    except Exception as e:
        # Fallback to local heuristics only
        local = _local_heuristics(response, tier)
        return CritiqueResult(
            original=response,
            revised=_apply_simple_fixes(response, local) if local else response,
            violations=local,
            clean=len(local) == 0,
            model_used="local_heuristics (deepseek failed)",
            critique_raw=str(e)[:200],
        )


def _critique_via_ollama(response: str, tier: str) -> CritiqueResult:
    """Use local Ollama for zero-cost constitutional critique."""
    prompt = _build_critique_prompt(response, tier)
    try:
        from mag.llm import chat_ollama
        result_text = chat_ollama(prompt, model="qwen2.5-coder:7b")
        return _parse_critique_response(response, result_text, "ollama-qwen2.5-coder")
    except Exception as e:
        local = _local_heuristics(response, tier)
        return CritiqueResult(
            original=response,
            revised=_apply_simple_fixes(response, local) if local else response,
            violations=local,
            clean=len(local) == 0,
            model_used="local_heuristics (ollama failed)",
            critique_raw=str(e)[:200],
        )


def _critique_via_grok(response: str, tier: str) -> CritiqueResult:
    """Use Grok-3-mini for constitutional critique (higher quality)."""
    prompt = _build_critique_prompt(response, tier)
    try:
        from mag.llm import chat_grok
        result_text = chat_grok(prompt, model="grok-3-mini")
        return _parse_critique_response(response, result_text, "grok-3-mini")
    except Exception as e:
        local = _local_heuristics(response, tier)
        return CritiqueResult(
            original=response,
            revised=_apply_simple_fixes(response, local) if local else response,
            violations=local,
            clean=len(local) == 0,
            model_used="local_heuristics (grok failed)",
            critique_raw=str(e)[:200],
        )


def _parse_critique_response(original: str, model_output: str, model_name: str) -> CritiqueResult:
    """Parse a model's critique response (expects JSON)."""
    violations = []
    revised = original
    clean = True
    critique_raw = model_output

    # Try to extract JSON from model output
    try:
        # Find JSON block
        json_start = model_output.find("{")
        json_end = model_output.rfind("}")
        if json_start >= 0 and json_end > json_start:
            json_str = model_output[json_start:json_end + 1]
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                violations = parsed.get("violations", [])
                clean = parsed.get("clean", len(violations) == 0)
                if "revised_response" in parsed and parsed["revised_response"]:
                    revised = parsed["revised_response"]
    except (json.JSONDecodeError, KeyError, TypeError):
        # If JSON parsing fails, fall back to local heuristics
        local = _local_heuristics(original, "T2")
        violations = local
        clean = len(local) == 0
        if local:
            revised = _apply_simple_fixes(original, local)

    return CritiqueResult(
        original=original,
        revised=revised,
        violations=violations,
        clean=clean,
        critique_raw=critique_raw,
        model_used=model_name,
        tokens_used=len(prompt) // 4 + len(model_output) // 4 if 'prompt' in dir() else len(original) // 4 + len(model_output) // 4,
        cost_usd=0.0 if "ollama" in model_name else 0.0003,  # ~$0.0003 for DeepSeek flash critique
    )

# Fix: define prompt for token estimation
def _parse_critique_response(original: str, model_output: str, model_name: str) -> CritiqueResult:
    """Parse a model's critique response (expects JSON)."""
    violations = []
    revised = original
    clean = True
    critique_raw = model_output

    # Try to extract JSON from model output
    try:
        json_start = model_output.find("{")
        json_end = model_output.rfind("}")
        if json_start >= 0 and json_end > json_start:
            json_str = model_output[json_start:json_end + 1]
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                violations = parsed.get("violations", [])
                clean = parsed.get("clean", len(violations) == 0)
                if "revised_response" in parsed and parsed["revised_response"]:
                    revised = parsed["revised_response"]
    except (json.JSONDecodeError, KeyError, TypeError):
        local = _local_heuristics(original, "T2")
        violations = local
        clean = len(local) == 0
        if local:
            revised = _apply_simple_fixes(original, local)

    # Estimate tokens
    est_tokens = len(original) // 4 + len(model_output) // 4

    return CritiqueResult(
        original=original,
        revised=revised,
        violations=violations,
        clean=clean,
        critique_raw=critique_raw,
        model_used=model_name,
        tokens_used=est_tokens,
        cost_usd=0.0 if "ollama" in model_name else round(est_tokens / 1_000_000 * 0.013, 6),
    )


# ═══════════════════════════════════════════════════════════════════
# CONSTITUTIONAL FILTER — the Ghost response wrapper
# ═══════════════════════════════════════════════════════════════════

class ConstitutionalFilter:
    """Wraps Ghost's response path with constitutional critique.

    Usage:
        filter = ConstitutionalFilter(model="deepseek")
        result = filter.process(response_text, tier="T2")
        # result.revised is the constitutionally-compliant response
    """

    def __init__(self, model: str = "deepseek", enabled: bool = True):
        self.model = model
        self.enabled = enabled
        self.stats = {"total": 0, "clean": 0, "violations_found": 0, "revised": 0}

    def process(self, response: str, tier: str = "T2") -> CritiqueResult:
        """Filter a response through constitutional critique."""
        self.stats["total"] += 1

        if not self.enabled:
            return CritiqueResult(original=response, revised=response, clean=True)

        result = critique(response, tier=tier, model=self.model)

        if result.clean:
            self.stats["clean"] += 1
        else:
            self.stats["violations_found"] += 1
            if result.revised != response:
                self.stats["revised"] += 1

        return result

    def stats_summary(self) -> dict[str, Any]:
        return {
            "total_processed": self.stats["total"],
            "clean": self.stats["clean"],
            "violations_found": self.stats["violations_found"],
            "revised": self.stats["revised"],
            "revision_rate": round(self.stats["revised"] / self.stats["total"], 2) if self.stats["total"] > 0 else 0,
        }


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_FILTER: Optional[ConstitutionalFilter] = None


def get_filter(model: str = "deepseek") -> ConstitutionalFilter:
    global _FILTER
    if _FILTER is None:
        _FILTER = ConstitutionalFilter(model=model)
    return _FILTER


def _model_family(model: str) -> str:
    """Family key: the first alphanumeric segment of a lowercased model id
    ('deepseek-chat' -> 'deepseek', 'qwen2.5-coder:7b' -> 'qwen2', 'gemma:2b'
    -> 'gemma'). Conservative on purpose: it over-refuses mixed families
    rather than ever letting a family audit itself."""
    import re as _re
    m = _re.split(r"[^a-z0-9]+", str(model or "").lower())
    return m[0] if m and m[0] else ""


def filter_response(
    response: str,
    tier: str = "T2",
    *,
    model: str = "deepseek",
    producer_model: str = "",
) -> CritiqueResult:
    """One-call constitutional filter. Use this in Ghost's response path.

    B2-207 (2026-09-26): on a critic/producer family match the same-family
    critique is refused and the call falls back to local heuristics with
    same_family_refused=True (judge-independence D3 F3: a model must not
    audit its own family's output)."""
    if producer_model and _model_family(producer_model) == _model_family(model):
        result = critique(response, tier=tier, dry_run=True)
        result.producer_model = producer_model
        result.same_family_refused = True
        return result
    result = get_filter(model=model).process(response, tier=tier)
    result.producer_model = producer_model
    return result


def critique_dry_run(response: str, tier: str = "T2") -> CritiqueResult:
    """Zero-cost local heuristics only — no API call."""
    return critique(response, tier=tier, dry_run=True)


def critique_stats() -> dict[str, Any]:
    """Get filter statistics."""
    return get_filter().stats_summary()
