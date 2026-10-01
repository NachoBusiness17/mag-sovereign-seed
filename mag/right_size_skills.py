"""right_size_skills — right-size each pipeline skill to the ask, cache state, and model type.

The skill pipeline declares a static `tier` per skill (local/flash/grok). That's metadata,
not execution reality: the cheapest CAPABLE tier for a given ask depends on the ask SHAPE
(exec vs reasoning vs heavy — self_drive.plan/model_pick) and whether the ask reuses the
frozen-prefix cache (RC dimension of rightsize_all). This module is the pure, deterministic
right-sizer: given a skill's declared tier + the ask, return the EFFECTIVE tier/model/effort
and whether the frozen-prefix cache likely applies (so repeated asks hit at $0.0028/M, not $0.14/M).

Law #7 (grok = frontier only) and Law #6 (fold the choice back) are applied here.

Schema: right_size_skills.v1
CLI: python -m mag.right_size_skills <skill_id> "<prompt>" | catalog
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "right_size_skills.v1"
_FLASH = "deepseek-v4-flash"
_PRO = "deepseek-v4-pro"
_LOCAL = "local"

# Ask shapes (from self_drive/model_pick) -> cheapest capable model type.
_SHAPE_MODEL = {
    "exec": _FLASH,        # exec: flash does it, spend-on-spec
    "balanced": _FLASH,
    "reasoning": _PRO,     # reasoning/plan: pro pays
    "heavy": _PRO,
    "local": _LOCAL,
}
# Declared skill tier as a ceiling on escalation: a "local" skill may escalate to flash,
# a "flash" skill to pro, but never a "local" skill all the way to grok.
_TIER_RANK = {"local": 0, "flash": 1, "grok": 2}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ask_shape(prompt: str) -> str:
    """Classify the ask shape without assembling the full handoff context.

    Right-sizing is an admission decision made for every skill. Calling
    ``self_drive.plan`` here recursively built health/model/context packs for
    each skill, turning a cheap routing probe into repeated expensive I/O.
    ``model_pick`` owns the shape classifier and is the appropriate lightweight
    surface for this decision.
    """
    try:
        from mag.model_pick import recommend_model

        p = recommend_model(prompt or "")
        return str(p.get("model_shape") or "balanced")
    except Exception:
        return "balanced"


def _cache_likely(prompt: str, shape: str) -> bool:
    """Best-effort signal: does this ask reuse the frozen-prefix cache path?
    Short/repeated exec-shaped asks with the stable invariant prefix hit the cache.
    We can't see the live provider split here, so this is a heuristic, not a fact."""
    t = (prompt or "").strip().lower()
    if not t:
        return False
    # exec/balanced + short + no per-ask novel frontier demand -> cache-reusable prefix
    if shape in ("exec", "balanced") and len(t) < 400:
        try:
            from mag.cache_map import recent_hit_ratio
            return recent_hit_ratio() >= 0.5
        except Exception:
            return True
    return False


def right_size(skill_id: str, prompt: str, declared_tier: str = "local") -> dict[str, Any]:
    """Pure: given a skill's declared tier + the ask, return the effective tier/model/effort
    and cache signal. Never escalates a cheap skill to grok (Law #7); folds the choice."""
    shape = _ask_shape(prompt)
    shape_model = _SHAPE_MODEL.get(shape, _FLASH)
    rank = _TIER_RANK.get(declared_tier, 0)

    # Effective tier: cheapest capable = min(declared rank, shape demand), but never grok
    # unless the skill is declared grok AND the ask is genuinely frontier (Law #7).
    if declared_tier == "grok":
        effective = "grok" if shape in ("heavy", "reasoning") else "flash"
    elif rank == 0:  # local skill
        effective = "local" if shape == "local" else "flash"
    else:  # flash skill
        effective = "pro" if shape in ("heavy", "reasoning") else "flash"

    model = _SHAPE_MODEL.get(effective, _FLASH)
    if effective == "local":
        model = _LOCAL
    cache_likely = _cache_likely(prompt, shape)
    reasoning_level = "high" if effective == "pro" else "none"

    return {
        "schema": SCHEMA,
        "ts": _now(),
        "skill": skill_id,
        "declared_tier": declared_tier,
        "effective_tier": effective,
        "model": model,
        "model_shape": shape,
        "reasoning_level": reasoning_level,
        "cache_likely": cache_likely,
        "note": (f"ask is {shape}; running {effective} "
                 + ("(likely frozen-prefix cache hit)" if cache_likely else "(cold)")),
    }


def catalog(prompt: str | None = None) -> dict[str, Any]:
    """Right-size every registered pipeline skill (optionally against a probe prompt)."""
    try:
        from mag.skill_pipeline import SKILLS
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160]}
    probe = prompt or "status"
    rows = []
    for sid, sk in SKILLS.items():
        rows.append(right_size(sid, probe, declared_tier=sk.get("tier", "local")))
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "prompt": probe,
            "count": len(rows), "rows": rows}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "catalog":
        print(json.dumps(catalog(argv[1] if len(argv) > 1 else None), indent=2,
                         ensure_ascii=False, default=str))
        return 0
    if len(argv) >= 2:
        sid, prompt = argv[0], " ".join(argv[1:])
        try:
            from mag.skill_pipeline import SKILLS
            tier = SKILLS.get(sid, {}).get("tier", "local")
        except Exception:
            tier = "local"
        print(json.dumps(right_size(sid, prompt, tier), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(catalog(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
