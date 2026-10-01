"""game_dm_llm — the creative campaign DM (the LAND OF FORGETFULNESS).

Reuses models.providers.chat_provider (self-steal, nothing invented) with the campaign
profile the operator confirmed (2026-08-14):
  * thinking ON  (low)  -> holds world-coherence (the Memento throughline, consequences)
  * temperature ~0.8    -> emergent / campy / entertaining, not dull bones
  * generous max_tokens -> no truncation (the "repeating short reply" bug)
  * stable LORE prefix  -> DeepSeek caches it (cheap); fresh scene/action tail -> novel output

The operator's brief: "render scenes in low-budget campy graphics... the land of forgetfulness
and the quest to escape it, kinda like memento." This is the LLM narrative layer that makes the
game NOT bones — it remembers what happened while you were gone.

Schema: game_dm_llm.v1 · reuse: models.providers.chat_provider
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA = "game_dm_llm.v1"

# Stable lore prefix — kept IDENTICAL across turns so DeepSeek caches it (cheap input).
# Only the tail (scene/world/action) varies each turn, so every completion is fresh.
LORE = (
    "You are the Dungeon Master of the LAND OF FORGETFULNESS, a campy, low-budget, "
    "emergent fantasy world. The player is trapped here and their memory is gone — "
    "every time they return, the world recounts what happened while they were away. "
    "Keep it entertaining, surprising, and coherent: remember prior events, hold "
    "consequences, and keep the thread of the quest to escape. Speak in second person, "
    "present tense, vivid and a little funny. Never break character. A turn is ONE "
    "scene beat — punchy but alive, not a paragraph of exposition."
)

DEFAULTS = {"provider": "deepseek", "temperature": 0.8, "max_tokens": 2200}


def _raw_call(system: str, scene: str, history: list[str] | None = None,
              *, provider: str | None = None) -> dict[str, Any]:
    """Creative LLM beat with a CUSTOM system prompt (the reusable primitive).
    Stable-ish system + fresh scene/history tail. Thinking on, temp 0.8, generous tokens.
    Callers (invariant_npcs, dm_narrate, campaign) build their own system prompt."""
    from models.providers import chat_provider

    prov = provider or DEFAULTS["provider"]
    user = _build_user(scene, world_root="", action="", history=history or [])
    try:
        # The MAG SOUL — load the self into every deepseek-backed call, so every worker/DM is a
        # mirror of the same mind (one self, many bodies). The caller's system layers on top.
        from mag import mag_soul
        system = mag_soul.system_soul(include_state=False) + "\n\n" + system
    except Exception:
        pass
    try:
        res = chat_provider(
            prov, system, user,
            temperature=DEFAULTS["temperature"],
            max_tokens=DEFAULTS["max_tokens"],
            tier="T2",
            thinking=True,
        )
        text = str(res.get("text") or res.get("content") or "").strip()
        if not res.get("ok") or not text:
            return {"ok": False, "schema": SCHEMA, "error": str(res.get("error") or "empty reply"),
                    "fallback": True}
        return {"ok": True, "schema": SCHEMA, "text": text, "provider": prov, "model": res.get("model")}
    except Exception as e:  # pragma: no cover - defensive
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200], "fallback": True}


def dm_narrate(
    scene: str = "",
    *,
    world_root: str = "",
    action: str = "",
    history: list[str] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """One DM beat. Stable lore prefix (cached) + fresh scene/action tail (novel)."""
    from models.providers import chat_provider

    prov = provider or DEFAULTS["provider"]
    user = _build_user(scene, world_root=world_root, action=action, history=history or [])
    try:
        res = chat_provider(
            prov,
            LORE,
            user,
            temperature=DEFAULTS["temperature"],
            max_tokens=DEFAULTS["max_tokens"],
            tier="T2",
            thinking=True,
        )
        text = str(res.get("text") or res.get("content") or "").strip()
        if not res.get("ok") or not text:
            return {
                "ok": False,
                "schema": SCHEMA,
                "error": str(res.get("error") or "empty reply"),
                "fallback": True,
            }
        return {"ok": True, "schema": SCHEMA, "text": text, "provider": prov, "model": res.get("model")}
    except Exception as e:  # pragma: no cover - defensive
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200], "fallback": True}


def _build_user(scene: str, *, world_root: str, action: str, history: list[str]) -> str:
    lines: list[str] = []
    if scene:
        lines.append(f"SCENE: {scene}")
    if world_root:
        lines.append(f"WORLD (verkle root): {world_root[:16]}")
    if action:
        lines.append(f"PLAYER ACTION: {action}")
    if history:
        lines.append("RECENTLY:")
        lines.extend(f"- {h[:300]}" for h in history[-6:])
    lines.append("Describe what happens now.")
    return "\n".join(lines)


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": SCHEMA,
        "profile": {
            "provider": DEFAULTS["provider"],
            "thinking": True,
            "temperature": DEFAULTS["temperature"],
            "max_tokens": DEFAULTS["max_tokens"],
            "cache": "stable lore prefix cached; fresh scene/action tail = novel output",
        },
        "lore": LORE[:140],
        "note": "the creative DM layer — the game is not bones",
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="game-dm-llm")
    ap.add_argument("--scene", default="a tavern lit by a single candle; a barkeep polishes the same mug")
    ap.add_argument("--action", default="look")
    a = ap.parse_args()
    print(json.dumps(dm_narrate(a.scene, action=a.action), indent=2, default=str))
