"""Deterministic dice — engine rolls, not the LLM. Schema: mag_game_dice.v1"""
from __future__ import annotations

import random
import re
from typing import Any

SCHEMA = "mag_game_dice.v1"
_NOTATION = re.compile(r"^\s*(?P<n>\d*)d(?P<sides>\d+)(?P<mod>[+-]\d+)?\s*$", re.I)


def roll_dice(notation: str, *, seed: int | str | None = None) -> dict[str, Any]:
    m = _NOTATION.match(notation or "")
    if not m:
        return {"ok": False, "schema": SCHEMA, "error": f"bad notation {notation!r}", "total": 0}
    n = int(m.group("n") or "1")
    sides = int(m.group("sides"))
    mod = int(m.group("mod") or "0")
    if n < 1 or n > 100 or sides < 2 or sides > 1000:
        return {"ok": False, "schema": SCHEMA, "error": "range", "total": 0}
    rng = random.Random(seed)
    faces = [rng.randint(1, sides) for _ in range(n)]
    return {
        "ok": True,
        "schema": SCHEMA,
        "notation": f"{n}d{sides}{mod:+d}" if mod else f"{n}d{sides}",
        "faces": faces,
        "modifier": mod,
        "total": sum(faces) + mod,
        "seed": seed,
    }
