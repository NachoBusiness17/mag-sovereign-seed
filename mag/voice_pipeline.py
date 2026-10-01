"""Voice pipeline: local format → DeepSeek swarm → human spoken answer.

Budget: ≤90s total. Crash-safe: every step timed; soft-fail forward.
Local-first: always prove local can format before paying DeepSeek.

Schema: mag_voice_pipeline.v1
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

SCHEMA = "mag_voice_pipeline.v1"
TOTAL_BUDGET_S = float(os.environ.get("MAG_VOICE_PIPELINE_BUDGET_S", "90") or "90")

FORMAT_SYSTEM = """You clean up messy voice transcripts for another AI.
Output ONLY a short structured brief — no fluff:
INTENT: one line
KEY POINTS: bullet-like short lines (max 5)
QUESTION: the single question or ask to answer
CONSTRAINTS: any musts (or "none")
Keep under 120 words. Plain text."""

SWARM_PLAN_SYSTEM = """You are Mag's research conductor (DeepSeek).
Given a cleaned operator brief, list 2-4 concrete steps to answer well.
One line per step. No markdown headers. Under 80 words."""

SWARM_ANSWER_SYSTEM = """You are Mag answering the operator after a quick team huddle.
Use the plan + brief. Be useful and specific.
Still write for speech: short paragraphs, no bullet walls, no code unless asked.
Under 180 words."""

HUMAN_SYSTEM = """You rewrite AI answers so they sound like a real person talking to a friend.
Rules:
- 2 to 4 short sentences
- contractions (I'm, you're, we'll, that's)
- warm, calm, not corporate
- no markdown, no bullets, no "As an AI"
- no "Great question!" openers
- under 70 words
- ready for text-to-speech"""


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _clip(text: str, n: int = 900) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _chat(
    provider: str,
    system: str,
    user: str,
    *,
    tier: str,
    max_tokens: int,
    model: str | None = None,
    temperature: float = 0.35,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    """chat_provider with hard wall-clock timeout (won't hang the pipeline)."""
    if timeout_s < 1.5:
        return {"ok": False, "error": "no time left", "text": ""}

    def _run() -> dict[str, Any]:
        from models.providers import chat_provider

        kwargs: dict[str, Any] = {
            "tier": tier,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if model:
            kwargs["model"] = model
        return chat_provider(provider, system, user, **kwargs)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            res = fut.result(timeout=timeout_s)
        if not isinstance(res, dict):
            return {"ok": False, "error": "bad response", "text": ""}
        text = str(res.get("text") or res.get("content") or "").strip()
        return {
            "ok": bool(res.get("ok") and text),
            "text": text,
            "error": res.get("error"),
            "model": res.get("model"),
            "provider": provider,
        }
    except FuturesTimeout:
        return {"ok": False, "error": f"timeout after {timeout_s:.0f}s", "text": "", "provider": provider}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "text": "", "provider": provider}


def _local_model() -> str:
    return (os.environ.get("MAG_VOICE_LOCAL_MODEL") or "gemma:2b").strip() or "gemma:2b"


def run_voice_pipeline(
    transcript: str,
    *,
    session_id: str = "",
    history_block: str = "",
) -> dict[str, Any]:
    """
    1) Local formats speech for DeepSeek
    2) DeepSeek plans (swarm step A)
    3) DeepSeek answers (swarm step B)
    4) Local humanizes for TTS
    Hard cap TOTALTOTAL_BUDGET_S}s. Always returns a speakable string if possible.
    """
    t0 = time.monotonic()
    deadline = t0 + TOTAL_BUDGET_S
    steps: list[dict[str, Any]] = []
    raw = (transcript or "").strip()
    if not raw:
        return {
            "ok": False,
            "schema": SCHEMA,
            "error": "empty transcript",
            "speak_text": "I didn't catch anything — say that again?",
            "answer": "I didn't catch anything — say that again?",
            "steps": steps,
            "elapsed_ms": 0,
        }

    # --- 1 Local format (prove local works) ---
    t_fmt = min(14.0, max(4.0, _remaining(deadline) * 0.18))
    fmt_user = raw
    if history_block:
        fmt_user = f"Recent conversation:\n{history_block}\n\nLatest speech:\n{raw}"
    fmt = _chat(
        "ollama",
        FORMAT_SYSTEM,
        fmt_user,
        tier="T1",
        max_tokens=180,
        model=_local_model(),
        temperature=0.2,
        timeout_s=t_fmt,
    )
    steps.append(
        {
            "step": "local_format",
            "ok": fmt.get("ok"),
            "ms": int((time.monotonic() - t0) * 1000),
            "error": fmt.get("error"),
            "model": fmt.get("model") or _local_model(),
        }
    )
    brief = fmt.get("text") if fmt.get("ok") else ""
    if not brief:
        # Local still "worked" as pass-through — pipeline continues
        brief = (
            f"INTENT: respond to operator voice note\n"
            f"KEY POINTS: (raw speech)\n"
            f"QUESTION: {_clip(raw, 400)}\n"
            f"CONSTRAINTS: keep answer short for speech"
        )
        steps[-1]["passthrough"] = True

    if _remaining(deadline) < 8:
        spoken = _emergency_human(raw)
        return _done(True, raw, brief, "", spoken, steps, t0, route="local_only_budget")

    # --- 2 DeepSeek swarm plan ---
    t_plan = min(22.0, max(6.0, _remaining(deadline) * 0.28))
    plan = _chat(
        "deepseek",
        SWARM_PLAN_SYSTEM,
        f"Operator brief:\n{brief}",
        tier="T2",
        max_tokens=120,
        temperature=0.3,
        timeout_s=t_plan,
    )
    steps.append(
        {
            "step": "swarm_plan",
            "ok": plan.get("ok"),
            "ms": int((time.monotonic() - t0) * 1000),
            "error": plan.get("error"),
            "model": plan.get("model"),
        }
    )
    plan_text = plan.get("text") if plan.get("ok") else "1) Answer directly from the brief\n2) Give one clear next step"

    if _remaining(deadline) < 10:
        # No time for full answer — humanize plan lightly
        spoken = _humanize_fallback(brief, plan_text, raw)
        return _done(True, raw, brief, plan_text, spoken, steps, t0, route="swarm_plan_only")

    # --- 3 DeepSeek swarm answer ---
    t_ans = min(40.0, max(10.0, _remaining(deadline) - 12.0))
    ans = _chat(
        "deepseek",
        SWARM_ANSWER_SYSTEM,
        f"Brief:\n{brief}\n\nTeam plan:\n{plan_text}\n\nWrite the reply now.",
        tier="T2",
        max_tokens=280,
        temperature=0.4,
        timeout_s=t_ans,
    )
    steps.append(
        {
            "step": "swarm_answer",
            "ok": ans.get("ok"),
            "ms": int((time.monotonic() - t0) * 1000),
            "error": ans.get("error"),
            "model": ans.get("model"),
        }
    )
    long_answer = ans.get("text") if ans.get("ok") else ""
    if not long_answer:
        long_answer = (
            f"I worked through your note. Here's the short version: {_clip(raw, 200)}. "
            "DeepSeek was slow or unavailable, so this is a local backup — try again or switch to local mode."
        )
        steps[-1]["fallback"] = True

    # --- 4 Local humanize for TTS ---
    t_hum = min(14.0, max(3.0, _remaining(deadline) - 1.0))
    hum = _chat(
        "ollama",
        HUMAN_SYSTEM,
        f"Rewrite for speaking out loud:\n\n{long_answer}",
        tier="T1",
        max_tokens=140,
        model=_local_model(),
        temperature=0.55,
        timeout_s=t_hum,
    )
    steps.append(
        {
            "step": "local_humanize",
            "ok": hum.get("ok"),
            "ms": int((time.monotonic() - t0) * 1000),
            "error": hum.get("error"),
            "model": hum.get("model") or _local_model(),
        }
    )
    spoken = hum.get("text") if hum.get("ok") else ""
    if not spoken:
        spoken = _regex_humanize(long_answer)

    spoken = _final_tts_polish(spoken)
    ok = bool(spoken)
    return _done(ok, raw, brief, plan_text, spoken, steps, t0, route="local_format_swarm_human", long_answer=long_answer)


def _regex_humanize(text: str) -> str:
    t = re.sub(r"[#*_`]+", "", text or "")
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    # Keep first ~3 sentences
    parts = re.split(r"(?<=[.!?])\s+", t)
    t = " ".join(parts[:4]).strip()
    if len(t) > 420:
        t = t[:419].rsplit(" ", 1)[0] + "."
    return t or "I heard you, but I couldn't shape a clean answer. Say it one more time?"


def _final_tts_polish(text: str) -> str:
    t = _regex_humanize(text)
    # Soften stiff openers
    for bad in (
        "Certainly! ",
        "Certainly. ",
        "Of course! ",
        "Of course. ",
        "Great question! ",
        "Great question. ",
        "As an AI, ",
        "As an AI ",
    ):
        if t.startswith(bad):
            t = t[len(bad) :]
    return t.strip()


def _emergency_human(raw: str) -> str:
    return (
        "I caught that, but I'm short on time this turn. "
        f"You said something like: {_clip(raw, 120)}. Want me to dig in again?"
    )


def _humanize_fallback(brief: str, plan: str, raw: str) -> str:
    return _final_tts_polish(
        f"Here's where I got: {_clip(plan, 200)}. "
        f"On your point — {_clip(raw, 100)} — I can go deeper if you want."
    )


def _done(
    ok: bool,
    raw: str,
    brief: str,
    plan: str,
    spoken: str,
    steps: list[dict[str, Any]],
    t0: float,
    *,
    route: str,
    long_answer: str = "",
) -> dict[str, Any]:
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return {
        "ok": ok,
        "schema": SCHEMA,
        "route": route,
        "seat": "pipeline",
        "provider": "ollama+deepseek",
        "transcript": raw,
        "brief": brief,
        "plan": plan,
        "long_answer": long_answer,
        "answer": spoken,
        "speak_text": spoken,
        "speak": True,
        "server_tts": False,
        "steps": steps,
        "elapsed_ms": elapsed_ms,
        "budget_s": TOTAL_BUDGET_S,
        "within_budget": elapsed_ms <= int(TOTAL_BUDGET_S * 1000) + 500,
        "token_note": "local format → deepseek swarm → local humanize; ≤90s",
    }
