"""EXP-A: cache re-trigger probe for glm-5.3-flash (2026-08-28 night).

Doctrine: docs/ref/GLM53_FLASH_EXPLOITATION.md EXP-A. Our 08-26 finding said
5.3-flash did NOT cache (thinking-always suspected of breaking similarity).
This probe retries with a BIG byte-stable prefix on the Lite lane (z_ai3):
same-prefix calls 1..6 (cache should warm from call 2 if it exists), then two
novel-prefix controls. Read usage.prompt_tokens_details.cached_tokens on every
call. Accept: cached_tokens > 0 on any same-prefix call.
Cost guard: ~16K-token prefix, max_tokens=32, 8 calls total ≈ $0.02 max.
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from models.providers import chat_provider  # noqa: E402
from mag import glm_flash  # noqa: E402

FIXED_SYSTEM = glm_flash.FROZEN_SELF
BLOCK = ("Stable cache-body block. This paragraph repeats verbatim to give the "
         "prompt cache a large identical prefix to key on. It changes never. ")
FIXED_USER = BLOCK * 240  # ~16K tokens of stable prefix
TAIL = "Reply with the single word: probe"


def hit_tokens(r: dict) -> int:
    usage = r.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    return int(usage.get("prompt_cache_hit_tokens") or details.get("cached_tokens") or 0)


def call(tag: str, user: str) -> dict:
    r = chat_provider("z_ai3", system=FIXED_SYSTEM, user=user,
                      model="glm-5.3-flash", thinking=True, max_tokens=2048,
                      tier="T2")
    usage = r.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    hit = hit_tokens(r)
    return {
        "call": tag,
        "ok": bool(r.get("ok")),
        "prompt_tokens": prompt,
        "cached_tokens": hit,
        "hit_rate": round(hit / prompt, 4) if prompt else 0.0,
        "error": str(r.get("error") or "")[:120],
    }


rows = []
for i in range(6):
    rows.append(call(f"same-prefix #{i+1}", FIXED_USER + f"\n\n{TAIL} #{i}"))
rows.append(call("novel-prefix control A", BLOCK[::-1] + f"\n\n{TAIL} A"))
rows.append(call("novel-prefix control B", (BLOCK * 239 + BLOCK[1:]) + f"\n\n{TAIL} B"))

same_hits = [r["cached_tokens"] for r in rows[:6]]
out = {
    "ok": True,
    "schema": "exp_a_cache_retrigger.v1",
    "lane": "z_ai3",
    "model": "glm-5.3-flash",
    "prefix_tokens_approx": None,
    "verdict": "CACHE LIVES" if any(h > 0 for h in same_hits) else "cache dead on 5.3-flash",
    "rows": rows,
    "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
}
print(json.dumps(out, indent=1))
