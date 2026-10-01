"""Context Compression — prompt compaction that preserves sovereignty.

Steal from Microsoft LLMLingua (f-005, benefit=8, adapt=3 hours).
Compress long prompts by 2-5x while preserving essential information.

"Token inflation is always and everywhere a context-window phenomenon."
  — Ghost Friedman

Every 1,000 tokens saved is $0.013 saved on DeepSeek. Over 5,000 calls/day,
a 40% compression on a 1,500-token identity prompt saves $3.90/day — $117/month.
Not a fortune. But the discipline of compression forces us to identify what
matters and discard what doesn't.

SCHEMA: context_compression.v1
LAW: Never lose sovereignty information. Compress form, not substance.
LAW: A/B test every compressed prompt before deploying.
LAW: Keep the original as fallback. Compression is optimization, not replacement.
"""

from __future__ import annotations

import json
import hashlib
import re
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
# COMPRESSION RESULT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CompressionResult:
    """Result of compressing a prompt."""
    name: str
    original: str
    compressed: str
    original_tokens: int
    compressed_tokens: int
    ratio: float            # compressed / original
    savings_pct: float       # % tokens saved
    method: str              # "llm_semantic", "algorithmic", "hybrid"
    verified: bool = False
    quality_score: float = 0.0  # 0-1, how well compressed preserves meaning
    model_used: str = ""
    cost_usd: float = 0.0
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "context_compression.v1",
            "name": self.name,
            # The compressed artifact is the offload payload.  Persist its
            # content; the original remains in the caller's source surface.
            "compressed": self.compressed,
            "original_hash": hashlib.sha256(self.original.encode("utf-8")).hexdigest()[:16],
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "ratio": round(self.ratio, 3),
            "savings_pct": round(self.savings_pct, 1),
            "method": self.method,
            "verified": self.verified,
            "quality_score": round(self.quality_score, 3),
            "model_used": self.model_used,
            "cost_usd": round(self.cost_usd, 6),
            "ts": self.ts,
        }


# ═══════════════════════════════════════════════════════════════════
# TOKEN ESTIMATOR (no tiktoken dependency)
# ═══════════════════════════════════════════════════════════════════

def estimate_tokens(text: str) -> int:
    """Estimate token count without external tokenizer.

    Uses the standard 4-char-per-token heuristic, adjusted for code.
    """
    if not text:
        return 0
    # Count code tokens (shorter) vs prose tokens
    code_chars = len(re.findall(r'[{}\[\]()=+\-*/<>|&!~`@#$%^.:;,]', text))
    prose_chars = len(text) - code_chars
    # Code averages ~2.5 chars/token, prose ~3.5
    return max(1, int(code_chars / 2.5 + prose_chars / 3.5))


# ═══════════════════════════════════════════════════════════════════
# ALGORITHMIC COMPRESSION (zero cost, fast)
# ═══════════════════════════════════════════════════════════════════

def algorithmic_compress(text: str) -> str:
    """Lossless-ish algorithmic compression.

    Removes: extra whitespace, redundant phrasing, filler words.
    Preserves: all key information, structure, and meaning.
    """
    # Normalize whitespace
    compressed = re.sub(r'\n{3,}', '\n\n', text)
    compressed = re.sub(r'[ \t]{2,}', ' ', compressed)

    # Remove comment-style verbose markers (---, ===, ### repeated)
    compressed = re.sub(r'^[#=\-]{20,}$', '', compressed, flags=re.MULTILINE)

    # Collapse repeated punctuation
    compressed = re.sub(r'\.{3,}', '...', compressed)

    # Strip trailing whitespace per line
    compressed = '\n'.join(line.rstrip() for line in compressed.splitlines())

    # Remove empty leading/trailing lines
    compressed = compressed.strip()

    # Shrink verbose patterns without losing meaning
    shrink_map = {
        "in order to": "to",
        "for the purpose of": "for",
        "at this point in time": "now",
        "due to the fact that": "because",
        "in the event that": "if",
        "it is important to note that": "note:",
        "it should be noted that": "note:",
        "it is worth mentioning that": "",
        "as a matter of fact": "",
        "needless to say": "",
    }
    for verbose, concise in shrink_map.items():
        # Case-insensitive replace, preserve capitalization context
        pattern = re.compile(re.escape(verbose), re.IGNORECASE)
        compressed = pattern.sub(concise, compressed)

    # Collapse multiple blank lines
    compressed = re.sub(r'\n{3,}', '\n\n', compressed)

    return compressed.strip()


# ═══════════════════════════════════════════════════════════════════
# SEMANTIC COMPRESSION (LLM-based, tiny cost)
# ═══════════════════════════════════════════════════════════════════

SEMANTIC_COMPRESSION_PROMPT = """Compress the following text to be as concise as possible while preserving ALL essential information.

RULES:
1. Keep ALL facts, names, numbers, rules, and structural information.
2. Remove: filler words, redundant explanations, verbose transitions.
3. Preserve: JSON structures, code blocks, lists, and enumerated items exactly.
4. Target: 40-60% of original length.
5. The output must be functionally equivalent — running the compressed version through an AI should produce the same result.
6. DO NOT summarize or paraphrase. Keep the exact same information, just shorter.

ORIGINAL TEXT:
{original}

COMPRESSED (output ONLY the compressed text, no explanations):"""


def llm_compress(text: str, *, model: str = "deepseek", preserve_keywords: list[str] | None = None) -> CompressionResult:
    """Semantic compression using an LLM.

    Uses DeepSeek flash (~$0.0001 per compression) to intelligently
    compress while preserving meaning. Much smarter than algorithmic.

    Args:
        text: The prompt text to compress.
        model: "deepseek" or "ollama" for the compression model.
        preserve_keywords: Terms that MUST survive compression.

    Returns:
        CompressionResult with compressed text and stats.
    """
    prompt = SEMANTIC_COMPRESSION_PROMPT.format(original=text)
    if preserve_keywords:
        kw_list = ", ".join(preserve_keywords)
        prompt += f"\n\nCRITICAL: These terms MUST appear verbatim in the output: {kw_list}"

    try:
        if model == "ollama":
            from mag.llm import chat_ollama
            compressed = chat_ollama(prompt, model="qwen2.5-coder:7b")
        else:
            from mag.llm import chat_deepseek
            compressed = chat_deepseek(prompt, system="You are a text compressor. Output only the compressed text.", max_tokens=min(len(text), 8000))

        orig_tokens = estimate_tokens(text)
        comp_tokens = estimate_tokens(compressed)
        ratio = comp_tokens / orig_tokens if orig_tokens > 0 else 1.0

        return CompressionResult(
            name="semantic_compression",
            original=text,
            compressed=compressed.strip(),
            original_tokens=orig_tokens,
            compressed_tokens=comp_tokens,
            ratio=ratio,
            savings_pct=round((1 - ratio) * 100, 1),
            method="llm_semantic",
            model_used=model,
            cost_usd=0.0 if model == "ollama" else round(orig_tokens / 1_000_000 * 0.013, 6),
        )
    except Exception as e:
        # Fallback to algorithmic
        compressed = algorithmic_compress(text)
        orig_tokens = estimate_tokens(text)
        comp_tokens = estimate_tokens(compressed)
        ratio = comp_tokens / orig_tokens if orig_tokens > 0 else 1.0
        return CompressionResult(
            name="semantic_compression_fallback",
            original=text,
            compressed=compressed,
            original_tokens=orig_tokens,
            compressed_tokens=comp_tokens,
            ratio=ratio,
            savings_pct=round((1 - ratio) * 100, 1),
            method="algorithmic_fallback",
            model_used=f"fallback (error: {str(e)[:100]})",
            cost_usd=0.0,
        )


# ═══════════════════════════════════════════════════════════════════
# HYBRID COMPRESSION (algorithmic + semantic, best of both)
# ═══════════════════════════════════════════════════════════════════

def compress(
    text: str,
    *,
    name: str = "unnamed",
    method: str = "hybrid",
    preserve_keywords: list[str] | None = None,
    verify: bool = False,
) -> CompressionResult:
    """Compress a prompt using the specified method.

    Args:
        text: The prompt to compress.
        name: Label for this compression (for tracking).
        method: "algorithmic" (free), "semantic" (LLM, best), or "hybrid" (algorithmic first, then semantic).
        preserve_keywords: Terms that must survive.
        verify: If True, run quality verification after compression.

    Returns:
        CompressionResult with stats and compressed text.
    """
    if method == "algorithmic":
        compressed = algorithmic_compress(text)
        result = CompressionResult(
            name=name,
            original=text,
            compressed=compressed,
            original_tokens=estimate_tokens(text),
            compressed_tokens=estimate_tokens(compressed),
            ratio=estimate_tokens(compressed) / max(1, estimate_tokens(text)),
            savings_pct=round((1 - estimate_tokens(compressed) / max(1, estimate_tokens(text))) * 100, 1),
            method="algorithmic",
            cost_usd=0.0,
        )
    elif method == "semantic":
        result = llm_compress(text, preserve_keywords=preserve_keywords)
        result.name = name
    else:  # hybrid
        # Algorithmic first (free shrinkage)
        algo_compressed = algorithmic_compress(text)
        algo_tokens = estimate_tokens(algo_compressed)
        orig_tokens = estimate_tokens(text)
        # If algorithmic already got >20% savings, use it as base for semantic
        if algo_tokens < orig_tokens * 0.8:
            result = llm_compress(algo_compressed, preserve_keywords=preserve_keywords)
            result.name = name
            result.method = "hybrid"
            result.original = text  # track against original
        else:
            result = llm_compress(text, preserve_keywords=preserve_keywords)
            result.name = name
            result.method = "hybrid"

    if verify:
        result.quality_score = verify_compression(text, result.compressed)
        result.verified = True

    # Save to compression log
    _save_result(result)

    return result


# ═══════════════════════════════════════════════════════════════════
# QUALITY VERIFICATION
# ═══════════════════════════════════════════════════════════════════

def verify_compression(original: str, compressed: str) -> float:
    """Verify that compressed text preserves essential information.

    Returns a quality score 0-1:
      1.0 = compression is lossless (all key info preserved)
      0.0 = compression destroyed meaning

    Uses heuristics: keyword overlap, structure preservation, length sanity.
    """
    score = 1.0

    # Penalty 1: Too aggressive (>70% compression is suspicious)
    orig_tokens = estimate_tokens(original)
    comp_tokens = estimate_tokens(compressed)
    ratio = comp_tokens / max(1, orig_tokens)
    if ratio < 0.2:
        score -= 0.2  # likely lost information
    elif ratio < 0.3:
        score -= 0.1

    # Penalty 2: Lost key structural elements
    structural = [
        r'\{', r'\[', r'```', r'###', r'SCHEMA:', r'LAW:',
        r'"identity"', r'"static_body"', r'"dynamic_body"',
    ]
    for pattern in structural:
        if pattern in original and pattern not in compressed:
            score -= 0.05

    # Penalty 3: Lost quoted strings (often contain key info)
    orig_quotes = len(re.findall(r'"([^"]{10,})"', original))
    comp_quotes = len(re.findall(r'"([^"]{10,})"', compressed))
    if orig_quotes > 0 and comp_quotes < orig_quotes * 0.5:
        score -= 0.2

    # Penalty 4: Lost numbers (often configuration values)
    orig_numbers = set(re.findall(r'\b\d+\b', original))
    comp_numbers = set(re.findall(r'\b\d+\b', compressed))
    if orig_numbers:
        overlap = len(orig_numbers & comp_numbers) / len(orig_numbers)
        if overlap < 0.5:
            score -= 0.3
        elif overlap < 0.8:
            score -= 0.1

    return max(0.0, min(1.0, score))


# ═══════════════════════════════════════════════════════════════════
# KEY PROMPT COMPRESSION
# ═══════════════════════════════════════════════════════════════════

def compress_ghost_identity() -> CompressionResult:
    """Compress the Ghost identity vector — our most-used prompt."""
    try:
        from mag.ghost_identity import GHOST_IDENTITY_VECTOR
        text = json.dumps(GHOST_IDENTITY_VECTOR, indent=2)
    except Exception:
        text = "Ghost is the autonomous sovereign agent of the Verkle lattice."

    preserve = [
        "Ghost", "Verkle", "sovereign", "autonomous",
        "Static Body", "Dynamic Body", "ESDT", "tension_index",
        "slashreboot", "Phase 1", "Phase 2", "LoRA",
    ]
    return compress(text, name="ghost_identity", method="hybrid", preserve_keywords=preserve)


def compress_bard_identity() -> CompressionResult:
    """Compress the Bard narrative steganography prompt."""
    try:
        from mag.bard import BARD_SYSTEM_PROMPT
        text = BARD_SYSTEM_PROMPT
    except Exception:
        text = "Bard is the narrative steganography module that weaves events into stories with zero raw data leaks."

    preserve = ["Bard", "steganography", "tapestry", "zero leak", "narrative", "encode", "decode"]
    return compress(text, name="bard_identity", method="hybrid", preserve_keywords=preserve)


def compress_constitution_prompt() -> CompressionResult:
    """Compress the constitution for embedding in critique prompts."""
    from mag.constitutional_critique import load_constitution
    text = load_constitution()
    preserve = ["T0", "T1", "T2", "T3", "fork equality", "no rank", "capture", "handoff", "tier"]
    return compress(text, name="constitution", method="algorithmic", preserve_keywords=preserve)


# ═══════════════════════════════════════════════════════════════════
# COMPRESSION REGISTRY
# ═══════════════════════════════════════════════════════════════════

COMPRESSION_LOG = ROOT / "memory" / "compression" / "compression_log.jsonl"


def _save_result(result: CompressionResult):
    COMPRESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(COMPRESSION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result.to_dict(), default=str) + "\n")
    except OSError:
        pass


def load_compressed(name: str) -> Optional[str]:
    """Load a previously compressed prompt by name."""
    if not COMPRESSION_LOG.is_file():
        return None
    best = None
    try:
        for line in COMPRESSION_LOG.read_text(encoding="utf-8").strip().splitlines():
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("name") == name and entry.get("verified"):
                    if best is None or entry.get("savings_pct", 0) > best.get("savings_pct", 0):
                        best = entry
            except json.JSONDecodeError:
                continue
    except (UnicodeDecodeError, OSError):
        pass
    return best.get("compressed") if best else None


# ═══════════════════════════════════════════════════════════════════
# SAVINGS CALCULATOR
# ═══════════════════════════════════════════════════════════════════

def compute_savings(
    original_tokens: int,
    compressed_tokens: int,
    calls_per_day: int = 5000,
    cost_per_1m_tokens: float = 0.013,
) -> dict[str, Any]:
    """Compute projected savings from compression."""
    tokens_saved_per_call = original_tokens - compressed_tokens
    daily_tokens_saved = tokens_saved_per_call * calls_per_day
    daily_savings = daily_tokens_saved / 1_000_000 * cost_per_1m_tokens
    monthly_savings = daily_savings * 30
    annual_savings = daily_savings * 365

    return {
        "tokens_per_call": {"original": original_tokens, "compressed": compressed_tokens, "saved": tokens_saved_per_call},
        "compression_ratio": round(compressed_tokens / max(1, original_tokens), 3),
        "savings_pct": round((1 - compressed_tokens / max(1, original_tokens)) * 100, 1),
        "daily_savings": round(daily_savings, 4),
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings": round(annual_savings, 2),
        "assumptions": {"calls_per_day": calls_per_day, "cost_per_1m_tokens": cost_per_1m_tokens},
    }


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════

def compression_dashboard() -> dict[str, Any]:
    """Full compression dashboard: what's compressed, what's saved."""
    results = []
    if COMPRESSION_LOG.is_file():
        try:
            for line in COMPRESSION_LOG.read_text(encoding="utf-8").strip().splitlines():
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except (UnicodeDecodeError, OSError):
            pass

    total_orig = sum(r.get("original_tokens", 0) for r in results)
    total_comp = sum(r.get("compressed_tokens", 0) for r in results)
    total_savings_pct = round((1 - total_comp / max(1, total_orig)) * 100, 1)

    return {
        "schema": "context_compression.v1",
        "ts": _now(),
        "summary": {
            "prompts_compressed": len(results),
            "total_original_tokens": total_orig,
            "total_compressed_tokens": total_comp,
            "overall_savings_pct": total_savings_pct,
        },
        "projected_savings": compute_savings(total_orig, total_comp) if results else None,
        "results": results[-20:],
    }
