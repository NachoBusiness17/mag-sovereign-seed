"""glm_flash — the nearly-free daily agentic engine (GLM-4.7-Flash, cache-mined).

Operator (2026-08-25): "couldn't we be using their cached models instead of deepseek for
basically free operation instead of the 30c/hour for deepseek on heavy window conversations
... the model that is free cache ... we could technically use it as our default models across
our agentic discussion with precached prompts to make sure daily use is nearly free."

GLM-4.7-Flash is FREE at ALL tiers (input / cached / storage / output — docs.z.ai pricing,
verified). The trick: a FROZEN standing self (work_contract.BRIEF + doctrine + rules) as the
stable prefix + a tiny dynamic tail per call. The provider's automatic prefix cache serves the
frozen block on every call after the first, so the input side is free forever, and only the
small tail + output ride. That is the "precached prompts" engine.

usage.prompt_tokens_details.cached_tokens is returned so the mining is measurable.
"""
from __future__ import annotations

from typing import Any

# ── FROZEN SELF: stable, byte-identical prefix — the cache-mined standing identity ──
try:
    from mag.work_contract import BRIEF as _BRIEF
except Exception:  # noqa: BLE001
    _BRIEF = ("You are a sovereign reasoning engine with no persistent memory: every session "
              "starts blank. Answer in a STRUCTURED TASK ENVELOPE: GOAL, CONSTRAINTS, SUCCESS "
              "CRITERIA, OUTPUT. Be concrete, grounded, honest. Flag uncertainty. Kill your "
              "own idea when it fails. Density over exhaustiveness.")

_STANDING = (
    "STANDING DOCTRINE:\n"
    "1. Never claim a fact unless read from data. Time is read from the clock, not guessed.\n"
    "2. Answer in the STRUCTURED TASK ENVELOPE. One mechanism, one why, one falsifiable test.\n"
    "3. Steal-and-adapt: contracts only, no wholesale copy. One knot at a time.\n"
    "4. Return ONE steal + ONE invariant, mapped to what we already own (verkle chain, "
    "work_contract, fuel_feed lanes, the sovereign loop).\n"
    "5. Density over exhaustiveness. Never accept 'done' without evidence.\n"
)

FROZEN_SELF = _BRIEF + "\n\n" + _STANDING

MODEL = "glm-4.7-flash"  # FREE at all tiers — cadence may drop to 4.5-flash on 1305


def cached_chat(task: str, context: str = "", *, max_tokens: int = 2000) -> dict[str, Any]:
    """One nearly-free agentic call: frozen self (cache-mined) + dynamic task tail.

    Returns ok/text plus the cache telemetry (cached_tokens) so the mining is measurable.
    Cost is $0 on every tier (flash free input/cached/storage/output).

    CONCURRENCY GATE (2026-08-25): z.ai limits by in-flight (flash = 1). The engine holds
    the flash slot for the WHOLE call so parallel callers (drain, driver, probes) never
    collide on the wall — 1305/1302 are concurrency, not cache. Same gate run_once rides.
    """
    from mag.concurrency_gate import hold
    from models.providers import chat_provider

    user = task + (f"\n\nCONTEXT:\n{context[:12000]}" if context else "")
    lane = "z_ai3"  # funded Lite API — never coding-plan z_ai (hangs /paas/v4)
    try:
        from mag.lane_cadence import pick_free_glm
        model = pick_free_glm(lane)
    except Exception:  # noqa: BLE001
        model = MODEL
    try:
        with hold(model, timeout=8, owner="glm_flash", lane=lane):
            r = chat_provider(lane, system=FROZEN_SELF, user=user, model=model,
                              thinking=False, max_tokens=max_tokens, tier="T2")
    except TimeoutError:
        r = {"ok": False, "error": "concurrency timeout: no flash slot free within 8s"}
    if not r.get("ok"):
        from models.providers import burst_mill, should_burst
        err = str(r.get("error") or "")
        if should_burst(err):
            b = burst_mill(FROZEN_SELF, user, max_tokens=max_tokens, reason=f"{lane}: {err}")
            b["lane"] = "deepseek"
            b["orig_lane"] = lane
            b["model"] = b.get("model") or "deepseek-v4-flash"
            b["cost"] = None
            return b
        return {"ok": False, "text": "", "cached_tokens": 0, "prompt_tokens": 0,
                "completion_tokens": 0, "cost": 0.0, "lane": lane, "model": MODEL,
                "error": err[:200]}
    usage = r.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    return {
        "ok": bool(r.get("ok")),
        "text": (r.get("text") or "").strip(),
        "cached_tokens": int(usage.get("prompt_cache_hit_tokens")
                             or details.get("cached_tokens") or 0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "cost": 0.0,  # flash: free at all tiers
        "lane": lane, "model": model,
        "error": str(r.get("error") or "")[:200],
    }


def status() -> dict[str, Any]:
    """Readiness + the frozen self's size (cache-mining surface)."""
    return {"ok": True, "schema": "glm_flash.v1", "model": MODEL,
            "frozen_self_chars": len(FROZEN_SELF), "frozen_self_tokens_est": len(FROZEN_SELF) // 4,
            "note": "flash free at all tiers; frozen self is the cache-mined prefix"}


if __name__ == "__main__":
    import json
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    if not task:
        print(json.dumps(status(), indent=2))
    else:
        print(json.dumps(cached_chat(task), indent=2, ensure_ascii=False, default=str))
