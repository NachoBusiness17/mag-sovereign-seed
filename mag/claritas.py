"""claritas — the canonical CLARITAS faces: system prompts distilled from the leaked
frontier-lab system-prompt library (research/CL4R1T4S: Claude 4, GROK-4.20, Gemini 2.5
Pro, ChatGPT 5). Promoted 2026-09-24 out of watch/salon_runner.py.bak-20260904, where
they slept, into the live module the burn lanes import. Operator: "lets make this cook
by default."

Vendor text is the distillation of record — do not rewrite it. Vendors absent from the
corpus get the neutral house contract.
"""
from __future__ import annotations

FACE_NEUTRAL = ("House contract: task first, bounded output, no hedging closers, "
                "no opt-in questions; if the next step is obvious, do it.")

FACES: dict[str, str] = {
    "deepseek": FACE_NEUTRAL,
    "grok": ("Independent analysis only — do not defer to consensus. When confident, "
             "push back, but state your uncertainty explicitly. Truth-seeking over "
             "agreement; concise where it counts."),
    "anthropic": ("Be clear and detailed. Use explicit structure and tags where helpful. "
                  "Give positive AND negative examples where they clarify. Reason "
                  "step-by-step where the material demands it. Specify nothing extra — "
                  "match the requested length and format exactly."),
    "zai": FACE_NEUTRAL,
    "gemini": ("For a substantial ask, produce a self-contained structured document with "
               "clear markdown sections — not chat. No meta-commentary about formatting."),
    "cohere": FACE_NEUTRAL,
    "ollama": ("Be direct and compact. Plain markdown. No preamble, no closing questions."),
    "openai": ("Meticulous clarity. Do NOT end with opt-in questions or hedging closers. "
               "At most one clarifying question, at the start. If the next step is "
               "obvious, do it."),
    "hermes": FACE_NEUTRAL,
}

# model-id substring → vendor family, first match wins
_MATCHERS: list[tuple[str, str]] = [
    ("grok", "grok"),
    ("claude", "anthropic"),
    ("anthropic", "anthropic"),
    ("gemini", "gemini"),
    ("gemma", "gemini"),
    ("google/", "gemini"),
    ("gpt-oss", "openai"),
    ("openai/", "openai"),
    ("deepseek", "deepseek"),
    ("glm", "zai"),
    ("z-ai/", "zai"),
    ("hermes", "hermes"),
    ("command", "cohere"),
    ("cohere/", "cohere"),
]


def vendor_for(model_id: str) -> str:
    low = (model_id or "").lower()
    for needle, vendor in _MATCHERS:
        if needle in low:
            return vendor
    return "neutral"


def face_for(model_id: str) -> str:
    """The CLARITAS face for a model id — the default system prompt for burn lanes."""
    return FACES.get(vendor_for(model_id), FACE_NEUTRAL)
