"""SEED STUB - llm
The estate runtime carries the multi-lane LLM router (Ollama / OpenRouter /
Gemini). This stub exists so load-bearing organs (daemon, judge) import cleanly
from the seed alone without API keys. Replace with your own chat() adapter.
"""
import json, re
from typing import Any


def chat(*args: Any, **kwargs: Any) -> str:
    return "{}"


def extract_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}
