"""A/B cache probe (2026-08-25) — verify the other AI's claim that glm-4.7-flash
barely caches (~0.3%) before we keep betting the free-cache thesis on it.

Method (the sharp edge): SAME fixed prefix (the real FROZEN_SELF + a fixed user block),
call the SAME provider twice back-to-back, read usage.prompt_tokens_details.cached_tokens
on the SECOND call. A real cache gives 2nd-call cached_tokens ~= prompt_tokens. Control:
deepseek-v4-flash (billing-verified 97% hit). Each lane rides chat_provider (the path that
actually works + reports usage).
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from models.providers import chat_provider  # noqa: E402
from mag import glm_flash  # noqa: E402

FIXED_SYSTEM = glm_flash.FROZEN_SELF
FIXED_USER = ("Cache A/B probe. This is a fixed, unchanging body of context repeated "
              "verbatim across calls. " * 8)  # ~1.5-2k tokens of stable prefix
TAIL = "Reply with the single word: probe"  # tiny varying tail


def hit_tokens(r: dict) -> int:
    usage = r.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    return int(usage.get("prompt_cache_hit_tokens") or details.get("cached_tokens") or 0)


def probe(lane: str, model: str, *, n: int = 3) -> dict:
    results = []
    for i in range(n):
        r = chat_provider(lane, system=FIXED_SYSTEM,
                          user=FIXED_USER + f"\n\n{TAIL} #{i}", model=model,
                          thinking=False, max_tokens=16, tier="T2")
        usage = r.get("usage") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        results.append({
            "call": i + 1,
            "ok": bool(r.get("ok")),
            "prompt_tokens": prompt,
            "cached_tokens": hit_tokens(r),
            "hit_rate": round(hit_tokens(r) / prompt, 4) if prompt else 0.0,
            "error": str(r.get("error") or "")[:80],
        })
    return results


out = {
    "ok": True,
    "schema": "cache_ab_probe.v1",
    "prefix_chars": len(FIXED_SYSTEM) + len(FIXED_USER),
    "lanes": {
        "glm-4.7-flash (z_ai)": probe("z_ai", "glm-4.7-flash"),
        "deepseek-v4-flash (control)": probe("deepseek", "deepseek-v4-flash"),
    },
    "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
}
print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
(ROOT / "logs" / "cache_ab_probe.jsonl").parent.mkdir(parents=True, exist_ok=True)
with (ROOT / "logs" / "cache_ab_probe.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(out, default=str) + "\n")
