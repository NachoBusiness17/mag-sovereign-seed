"""Socratic prompt workshop — refine a prompt before launching a coding session.

Takes a rough prompt, runs a short Socratic Q&A (local model, no Grok) to
surface ambiguity, then produces a tightened final prompt ready to hand to a
coding session. Optionally speaks the refined prompt via mag.tts.

Learns from prior Mag work: pulls working.md, biography latest, and residual
bonds into the context so the refined prompt is grounded in what Mag already
knows and has built.

Usage:
    from mag.socratic import workshop
    final = workshop("build a tts module")
    # or CLI: python -m mag.socratic "build a tts module"
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

from config import ROOT
from mag.tts import speak_async

SOCRATIC_QUESTIONS = (
    "What is the concrete deliverable — a file, a command, a running service?",
    "Who consumes it and from where (local CLI, dashboard, LAN device)?",
    "What does 'done' look like — what check passes?",
    "What should it NOT do (scope guardrails)?",
    "What prior Mag work should it learn from (residual, working.md, biography)?",
)


def _clip(path: Path, n: int = 1200) -> str:
    try:
        t = path.read_text(encoding="utf-8").strip()
        return t if len(t) <= n else t[:n] + " …"
    except Exception:
        return ""


def _residual_text(max_chars: int = 800) -> str:
    """Read the latest residual bond JSON (tldr + open_loops) if present."""
    try:
        d = ROOT / "memory" / "biography" / "residual"
        if not d.is_dir():
            return ""
        files = sorted(d.glob("*.json"))
        if not files:
            return ""
        data = json.loads(files[-1].read_text(encoding="utf-8"))
        bits = []
        if data.get("tldr"):
            bits.append(f"tldr: {data['tldr']}")
        loops = data.get("open_loops") or []
        if loops:
            bits.append("open_loops: " + "; ".join(str(x) for x in loops))
        text = "\n".join(bits)
        return text if len(text) <= max_chars else text[:max_chars] + " …"
    except Exception:
        return ""


def prior_context(*, max_chars: int = 2500) -> str:
    """Gather prior Mag work context (working.md, biography latest, residual)."""
    parts: list[str] = []

    work = _clip(ROOT / "memory" / "working.md", 1200)
    if work:
        parts.append(f"## working.md\n{work}")

    bio = _clip(ROOT / "memory" / "biography" / "latest.md", 1200)
    if bio:
        parts.append(f"## biography latest\n{bio}")

    resid = _residual_text()
    if resid:
        parts.append(f"## residual bonds\n{resid}")

    joined = "\n\n".join(parts)
    if len(joined) > max_chars:
        joined = joined[:max_chars] + " …"
    return joined


def _ask_local(question: str) -> str:
    """Ask the local worker model a single question (best-effort)."""
    try:
        from llm import chat

        return chat(
            "worker",
            "You are a precise Socratic interviewer. Answer in one short sentence.",
            question,
            temperature=0.2,
        ).strip()
    except Exception:
        return ""


def workshop(
    prompt: str,
    *,
    rounds: int = 3,
    speak_result: bool = True,
    use_llm: bool = True,
    learn: bool = True,
) -> dict[str, Any]:
    """Refine `prompt` Socratically. Returns {final, transcript, ok}.

    `learn=True` (default) folds prior Mag work context (working.md, biography,
    residual) into the prompt so the refined result is grounded in prior work.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "empty prompt", "final": "", "transcript": []}

    transcript: list[dict[str, str]] = [{"role": "user", "text": prompt}]
    current = prompt

    # Learn from prior work: ground the prompt in what Mag already knows.
    if learn:
        ctx = prior_context()
        if ctx:
            current = (
                f"{current}\n\n## Prior Mag work to learn from\n{ctx}"
            )
            transcript.append({"role": "assistant", "text": "Prior Mag work context loaded."})

    for i in range(rounds):
        q = SOCRATIC_QUESTIONS[i % len(SOCRATIC_QUESTIONS)]
        if use_llm:
            a = _ask_local(
                f"Given this prompt: {current}\n\nSocratic question: {q}\n"
                "Answer as the operator clarifying intent, one short sentence."
            )
        else:
            a = ""
        transcript.append({"role": "assistant", "text": q})
        if a:
            transcript.append({"role": "user", "text": a})
            # Fold the clarification into the prompt (append as a constraint).
            current = f"{current}\n\nClarification {i+1}: {a}"

    final = current
    if speak_result:
        speak_async(f"Prompt refined. {final[:400]}")
    return {"ok": True, "final": final, "transcript": transcript, "rounds": rounds}


if __name__ == "__main__":
    p = " ".join(sys.argv[1:]) or "build a tts module"
    res = workshop(p)
    print("=== FINAL PROMPT ===")
    print(res.get("final"))
    print("=== TRANSCRIPT ===")
    for t in res.get("transcript", []):
        print(f"[{t['role']}] {t['text']}")
