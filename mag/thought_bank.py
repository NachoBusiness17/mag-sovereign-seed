"""thought_bank — THE single choke point for banking model thinking.

2026-09-05, operator: "this should happen with all models by design" and "this
is literally steering data in real time." Every caller that talks to a model
banks the thought here — verbatim, silent-fail, local disk, $0. One door; the
prose census flags unbanked callers until they adopt this.

Usage (one line for any OpenAI-shaped response dict):
    from mag.thought_bank import bank_response
    bank_response("glm-4.7-flashx", prompt, data, lane="cache_mine")
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BANK_DIR = ROOT / "memory" / "thinking"


def _safe_model(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "-", model)[:40] or "unknown"


def bank(model: str, prompt: str, reasoning: str, answer: str,
         usage: dict | None = None, lane: str = "") -> bool:
    """Append one verbatim thought row. Returns True if banked."""
    if not reasoning:
        return False
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "model": model, "lane": lane,
           "prompt_sha16": hashlib.sha256(prompt.encode()).hexdigest()[:16],
           "reasoning": reasoning,
           "answer": (answer or "")[:2000],
           "usage": usage or {}}
    with io.open(BANK_DIR / (_safe_model(model) + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True


def bank_response(model: str, prompt: str, data: dict, lane: str = "") -> bool:
    """Extract thinking from an OpenAI-shaped response dict and bank it."""
    try:
        msg = (data.get("choices") or [{}])[0].get("message", {})
        return bank(model, prompt, msg.get("reasoning_content") or "",
                    msg.get("content") or "", data.get("usage", {}), lane)
    except Exception:  # noqa: BLE001 — bank, never break
        return False
