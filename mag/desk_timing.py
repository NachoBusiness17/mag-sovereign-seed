"""Desk agent response timing — elapsed ms + token estimates per speaker."""
from __future__ import annotations

import time
from typing import Any

_MAX_RECENT = 24

_SPEAKER_LABELS: dict[str, str] = {
    "local": "Local",
    "remote": "DeepSeek",
    "conductor": "Orchestrator",
    "remote_meta_a": "Meta-A",
    "remote_meta_b": "Meta-B",
    "scheduler_triage": "Triage",
    "janitor": "Janitor",
}

_recent: list[dict[str, Any]] = []


def speaker_label(speaker: str) -> str:
    return _SPEAKER_LABELS.get((speaker or "").strip().lower(), speaker or "?")


def estimate_tokens(text: str | None) -> int | None:
    """Rough token estimate when provider omits counts (~4 chars/token)."""
    if not text:
        return None
    n = len(str(text))
    return max(1, n // 4) if n else None


def fill_token_estimates(
    *,
    timing: dict[str, Any],
    prompt_text: str = "",
    completion_text: str = "",
) -> dict[str, Any]:
    """Fill missing token counts for behavioral metrics."""
    tin = timing.get("tokens_in")
    tout = timing.get("tokens_out")
    if tin is None and prompt_text:
        timing["tokens_in"] = estimate_tokens(prompt_text)
        timing["tokens_in_estimated"] = True
    if tout is None and completion_text:
        timing["tokens_out"] = estimate_tokens(completion_text)
        timing["tokens_out_estimated"] = True
    return timing


def extract_provider_tokens(usage: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """OpenAI-compat usage: prompt_tokens + completion_tokens."""
    if not usage:
        return None, None
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    if pt is None and ct is None:
        # Anthropic-style
        pt = usage.get("input_tokens")
        ct = usage.get("output_tokens")
    if pt is None and ct is None:
        return None, None
    return (int(pt) if pt is not None else None, int(ct) if ct is not None else None)


def extract_ollama_tokens(body: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """Ollama /api/generate or /api/chat response token counts."""
    if not body:
        return None, None
    tin = body.get("prompt_eval_count")
    tout = body.get("eval_count")
    if tin is None and tout is None:
        return None, None
    return (int(tin) if tin is not None else None, int(tout) if tout is not None else None)


def make_timing(
    *,
    speaker: str,
    elapsed_ms: int,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    return {
        "speaker": speaker,
        "elapsed_ms": int(elapsed_ms),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "provider": provider,
    }


def record_timing(entry: dict[str, Any]) -> dict[str, Any]:
    """Append to rolling buffer; return the entry."""
    global _recent
    _recent = (_recent + [entry])[-_MAX_RECENT:]
    return entry


def recent_timings(*, limit: int = 8) -> list[dict[str, Any]]:
    return list(_recent[-max(1, limit) :])


def last_by_speaker() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _recent:
        sp = str(row.get("speaker") or "")
        if sp:
            out[sp] = row
    return out


def format_elapsed(ms: int | None) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


def format_tokens(tokens_in: int | None, tokens_out: int | None) -> str | None:
    if tokens_in is not None and tokens_out is not None:
        return f"{tokens_in + tokens_out} tok"
    if tokens_out is not None:
        return f"{tokens_out} tok"
    if tokens_in is not None:
        return f"{tokens_in} tok"
    return None


def format_timing_badge(entry: dict[str, Any]) -> str:
    label = speaker_label(str(entry.get("speaker") or ""))
    elapsed = format_elapsed(entry.get("elapsed_ms"))
    tok = format_tokens(entry.get("tokens_in"), entry.get("tokens_out"))
    return f"{label} {elapsed}" + (f" · {tok}" if tok else "")


def format_timing_row(entries: dict[str, dict[str, Any]] | None = None) -> str:
    """Compact row for UI: Local 2.3s · 142 tok | DeepSeek 1.1s · 89 tok"""
    by = entries if entries is not None else last_by_speaker()
    order = ("local", "remote", "conductor", "remote_meta_a", "remote_meta_b", "scheduler_triage", "janitor")
    bits: list[str] = []
    seen: set[str] = set()
    for sp in order:
        if sp in by:
            bits.append(format_timing_badge(by[sp]))
            seen.add(sp)
    for sp, row in by.items():
        if sp not in seen:
            bits.append(format_timing_badge(row))
    return " | ".join(bits)


class Timer:
    """Simple perf_counter wrapper."""

    __slots__ = ("_t0",)

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)


def reset_timings() -> None:
    """Clear buffer (tests / dialogue reset)."""
    global _recent
    _recent = []
