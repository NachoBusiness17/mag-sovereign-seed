"""game_score — the GWAP SCOREBOARD: real folded work, never fake points (Foldit steal, 2026-08-16).

The operator: "a fun mud that tricks people into doing work" + "be a game company not an agent."
Foldit's genius is the SCORE IS REAL PROGRESS (score = how well-folded; high scores for each puzzle;
leaderboards + groups). The GWAP mandate (STEAL_GWAP_FUN_MUD_TRICKS_PEOPLE_INTO_WORK_20260816.md):
  * SCORE TRACKS REAL FOLDED WORK, never fake points (the honesty law).
  * game_world is the authority; chat is one party seat.
  * No new world/store/graph — sharpen what exists.

THE SCORE (grounded, cannot be faked — every term is read from the verkle chain / real state):
  * agreement_loot   — game_mud: invariants folded by >=2 agreeing witnesses (Roshomon core).
                      REAL: claim() only succeeds on genuine convergence. = OUTPUT-AGREEMENT half.
  * rooms_conquered  — dungeon_dev: rooms (real tasks) folded as knots. = MACROTASK half (Foldit).
  * world_changes    — game_world.n_changes: every verkle-anchored world change (the ledger itself).
  * TOTAL            — the world-built score. A bigger total = more real work folded into the world.

This is the leaderboard the fun hides behind: players/agents see a number that quietly equals how
much real work the world absorbed. Fun (progress) and work (knots) are THE SAME ACT.

Schema: game_score.v1 · deterministic + $0 · reuse: game_world, game_mud, dungeon_dev
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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "game_score.v1"


def _safe(fn: Any, *a: Any, **k: Any) -> Any:
    try:
        return fn(*a, **k)
    except Exception:
        return None


def _mud_loot() -> int:
    from mag import game_mud
    s = _safe(game_mud.status)
    if not s:
        return 0
    return int(s.get("invariants") or 0)


def _dungeon_conquered() -> int:
    from mag import dungeon_dev
    s = _safe(dungeon_dev.dungeon_state)
    if not s:
        return 0
    return int(s.get("n_conquered") or len(s.get("conquered") or []))


def _world_changes() -> int:
    from mag import game_world
    s = _safe(game_world.world_status)
    if not s:
        return 0
    return int(s.get("n_changes") or 0)


def score() -> dict[str, Any]:
    """The GWAP scoreboard: real folded work from both halves, grounded in game_world authority."""
    agreement_loot = _mud_loot()
    rooms_conquered = _dungeon_conquered()
    world_changes = _world_changes()
    total = agreement_loot + rooms_conquered + world_changes
    return {
        "ok": True, "schema": SCHEMA,
        "score": {
            "agreement_loot": agreement_loot,      # OUTPUT-AGREEMENT half (game_mud, real convergence)
            "rooms_conquered": rooms_conquered,     # MACROTASK half (dungeon_dev, real tasks)
            "world_changes": world_changes,         # the verkle ledger itself (game_world authority)
            "total": total,                          # the world-built score (real work, never fake)
        },
        "honest": "every term is read from real folded state (agreement-convergence / conquered "
                  "tasks / verkle chain) — the score cannot be faked; fun and work are the same act",
        "reuse": ["game_world", "game_mud", "dungeon_dev"],
        "note": "the GWAP scoreboard — a fun number that quietly equals real work folded into the world",
    }


def main(argv: list[str] | None = None) -> int:
    import json as _json
    print(_json.dumps(score(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
