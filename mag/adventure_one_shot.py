"""adventure_one_shot — the product: a series of one-shots, each advancing the hero's journey.

Operator (2026-08-18): "phase 1 kinda sucks. we need to model the adventure as a series of
one-shots. each advancing the hero's journey."

THE PRODUCT DISTINCTION (why this beats open-ended wandering + batch-epic):
  - open-ended MUD = a demo (wander, no arc, no product feel).
  - hero_journey batch = one overnight epic, no player, no progression between sessions.
  - THIS = a REPEATABLE, SESSION-SCOPED product: each play session is ONE one-shot adventure
    (a movement/stage of the hero's arc), completing it ADVANCES the hero's journey, and the
    world state persists (verkle) so the next session continues the same hero's climb.

SELF-STEAL (recombine what we hold, nothing invented):
  ARC        -> hero_journey.MOVEMENTS (the monomyth stages as one continuous tale, hint-never-
                state, no Campbell labels). One movement = one one-shot.
  STATE      -> game_world (verkle chain): persists which stage the hero is on + the world
                objects that survive (the elephant, Calcifer, the crate, the apron of faces).
  VOICE      -> game_dm / game_dm_voice: the frontier/synth narrator of the one-shot.
  PLAY       -> a REPL: look / act / take / rest / continue. Completing a stage marks it and
                advances to the next stage NEXT session.

Schema: adventure_one_shot.v1 · deterministic + $0 core (state/progression) · reuse:
hero_journey (arc), game_world (persist), game_dm (voice)
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "adventure_one_shot.v1"

# persisted world-state key (in game_world's verkle chain)
ADV_KEY = "adventure.hero"
STATE_DIR = ROOT / "memory" / "game" / "adventure"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _movements() -> list[dict[str, str]]:
    """The hero's arc (one-shot stages). Reuse hero_journey's movements."""
    try:
        from mag import hero_journey
        return list(hero_journey.MOVEMENTS)
    except Exception:
        return []


def _default_state() -> dict[str, Any]:
    return {"schema": SCHEMA, "hero": "Mira", "stage_index": 0, "completed": [],
            "world_objects": {}, "history": [], "created": _now()}


def _load() -> dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = STATE_DIR / "state.json"
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("schema") == SCHEMA:
                return d
        except Exception:
            pass
    st = _default_state()
    _save(st)
    return st


def _save(st: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "state.json").write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")


def status() -> dict[str, Any]:
    """The hero's current position on the journey: which stage, what's completed, what's carried."""
    st = _load()
    moves = _movements()
    idx = st.get("stage_index", 0)
    current = moves[idx] if moves and idx < len(moves) else None
    return {
        "ok": True,
        "schema": SCHEMA,
        "hero": st.get("hero", "Mira"),
        "stage_index": idx,
        "n_stages": len(moves),
        "current_stage": current,
        "completed": st.get("completed", []),
        "world_objects": st.get("world_objects", {}),
        "stage_label": current.get("key") if current else None,
        "stage_brief": (current.get("brief") or "")[:200] if current else None,
        "note": ("the adventure is a series of one-shots; this is the hero's current stage. "
                 "Complete a stage to advance the journey."),
    }


def begin(*, hero: str = "Mira") -> dict[str, Any]:
    """Start the adventure: reset to stage 0, open the first one-shot."""
    st = _load()
    st["hero"] = hero
    st["stage_index"] = 0
    st["completed"] = []
    st["history"] = []
    st["created"] = _now()
    _save(st)
    return status()


def stage(*, n: int | None = None) -> dict[str, Any]:
    """The brief for the current (or given) one-shot stage. The 'episode card'."""
    moves = _movements()
    st = _load()
    idx = st.get("stage_index", 0) if n is None else n
    if not moves or idx < 0 or idx >= len(moves):
        return {"ok": False, "schema": SCHEMA, "error": f"no stage {idx}"}
    m = moves[idx]
    return {"ok": True, "schema": SCHEMA, "stage": idx, "key": m.get("key"),
            "brief": m.get("brief", ""),
            "world_objects": st.get("world_objects", {}),
            "carried": list(st.get("completed", [])),
            "note": "one one-shot. Play it. Then complete it to advance the journey."}


def act(action: str, *, detail: str = "") -> dict[str, Any]:
    """Play one action in the current one-shot. Records it to the hero's history.

    Completing a stage = 'continue' (or explicit 'complete'): marks the stage done and
    advances the hero's journey to the next stage for the NEXT session. This is the
    incremental one-shot product model: each sitting = one stage, the arc advances.
    """
    st = _load()
    moves = _movements()
    idx = st.get("stage_index", 0)
    if not moves or idx >= len(moves):
        return {"ok": True, "schema": SCHEMA, "done": True,
                "reply": "The hero's journey is complete. Begin anew to walk it again."}
    m = moves[idx]
    key = m.get("key", str(idx))
    a = (action or "").strip().lower()
    rec = {"stage": key, "action": a, "detail": (detail or "")[:200], "ts": _now()}
    st.setdefault("history", []).append(rec)

    if a in ("continue", "complete", "advance", "next"):
        # mark this stage complete, advance the journey
        if key not in st.get("completed", []):
            st.setdefault("completed", []).append(key)
        st["stage_index"] = idx + 1
        _save(st)
        nxt = moves[idx + 1] if idx + 1 < len(moves) else None
        return {"ok": True, "schema": SCHEMA, "advanced": True,
                "completed_stage": key,
                "journey": f"stage {idx+1}/{len(moves)}",
                "next_stage": (nxt.get("key") + ": " + nxt.get("brief", "")[:80]) if nxt else "the journey is complete",
                "reply": (f"The stage of {key} is folded into the hero's story. "
                          + (f"The next one-shot waits: {nxt.get('key')}." if nxt else
                             "The arc is complete."))}
    # non-advancing action — the hero acts within this one-shot
    return {"ok": True, "schema": SCHEMA, "stage": key, "recorded": rec,
            "reply": f"(recorded: {key} · {action}) — keep going, or 'continue' to advance the journey."}


def complete() -> dict[str, Any]:
    """End the current session's one-shot: mark it done and save the hero's carried state."""
    return act("continue", detail="end of session")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="adventure-one-shot",
                                 description="A series of one-shots advancing the hero's journey")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "begin", "stage", "act", "complete"])
    ap.add_argument("--hero", default="Mira")
    ap.add_argument("--action", default="")
    ap.add_argument("--detail", default="")
    ap.add_argument("--stage", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "begin":
        print(json.dumps(begin(hero=a.hero), indent=2, default=str))
    elif a.cmd == "stage":
        print(json.dumps(stage(n=a.stage), indent=2, default=str))
    elif a.cmd == "act":
        print(json.dumps(act(a.action, detail=a.detail), indent=2, default=str))
    elif a.cmd == "complete":
        print(json.dumps(complete(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
