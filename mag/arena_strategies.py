"""Arena strategies — ocean behaviors, spider steering, prompt modifiers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config import ROOT

CFG = ROOT / "configs" / "arena_strategies.yaml"
SCHEMA = "arena_strategies.v1"


def _load() -> dict[str, Any]:
    if not CFG.is_file():
        return {"strategies": {}, "defaults": {}}
    try:
        return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {"strategies": {}}
    except Exception:
        return {"strategies": {}, "defaults": {}}


def list_strategies() -> dict[str, Any]:
    cfg = _load()
    items = []
    for sid, meta in (cfg.get("strategies") or {}).items():
        if isinstance(meta, dict):
            items.append({"id": sid, **meta})
    return {"ok": True, "schema": SCHEMA, "strategies": items, "defaults": cfg.get("defaults") or {}}


def get_strategy(strategy_id: str) -> dict[str, Any]:
    cfg = _load()
    meta = (cfg.get("strategies") or {}).get(strategy_id) or {}
    if not isinstance(meta, dict):
        meta = {}
    ocean = str(meta.get("ocean") or "tide")
    ocean_map = cfg.get("ocean_to_spider") or {}
    return {
        "id": strategy_id,
        "label": meta.get("label") or strategy_id,
        "ocean": ocean,
        "spider_steer": meta.get("spider_steer") or ocean_map.get(ocean) or "observe",
        "routing_task": meta.get("routing_task") or "handoff",
        "prompt_suffix": str(meta.get("prompt_suffix") or "").strip(),
        "description": meta.get("description") or "",
    }


def default_for_seat(seat: str) -> str:
    cfg = _load()
    defaults = cfg.get("defaults") or {}
    if seat == "white" or seat == "local":
        return str(defaults.get("white") or "tide_janitor")
    return str(defaults.get("black") or "predator_strike")


def strategy_for_game_state(state: dict[str, Any], seat: str) -> dict[str, Any]:
    """Resolve strategy from game state (white/black seat ids)."""
    white = str(state.get("white") or "local")
    black = str(state.get("black") or "remote")
    strategies = state.get("strategies") or {}
    if seat == white:
        sid = str(strategies.get("white") or default_for_seat("white"))
    elif seat == black:
        sid = str(strategies.get("black") or default_for_seat("black"))
    else:
        sid = default_for_seat(seat)
    return get_strategy(sid)


def augment_move_prompt(base: str, *, strategy: dict[str, Any]) -> str:
    suffix = (strategy.get("prompt_suffix") or "").strip()
    if not suffix:
        return base
    return f"{base}\n\n{suffix}"


def emit_spider_arena_signal(
    *,
    event: str,
    state: dict[str, Any],
    seat: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Map arena events to spider/training signals for ocean behavior steering."""
    strat = strategy_for_game_state(state, seat)
    row = {
        "event": event,
        "seat": seat,
        "strategy": strat.get("id"),
        "ocean": strat.get("ocean"),
        "spider_steer": strat.get("spider_steer"),
        "game_id": state.get("game_id"),
    }
    if extra:
        row.update(extra)
    try:
        from mag.training_events import emit

        emit(
            "spider_signal",
            join={"game_id": str(state.get("game_id") or ""), "seat": seat},
            input_data={"ocean": strat.get("ocean"), "strategy": strat.get("id")},
            action={"arena_event": event, "spider_steer": strat.get("spider_steer")},
            outcome=extra or {},
            pattern_tags=["arena", str(strat.get("ocean") or ""), event],
            tier_max="T2",
        )
    except Exception:
        pass
    try:
        trail = ROOT / "memory" / "runs" / "arena_strategy_trail.jsonl"
        trail.parent.mkdir(parents=True, exist_ok=True)
        import json
        from datetime import datetime, timezone

        with trail.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"ts": datetime.now(timezone.utc).isoformat(), **row},
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:
        pass


def routing_hint_for_ocean(ocean: str) -> dict[str, Any]:
    cfg = _load()
    ocean_map = cfg.get("ocean_to_spider") or {}
    for sid, meta in (cfg.get("strategies") or {}).items():
        if isinstance(meta, dict) and meta.get("ocean") == ocean:
            return {
                "ocean": ocean,
                "strategy": sid,
                "spider_steer": meta.get("spider_steer") or ocean_map.get(ocean),
                "routing_task": meta.get("routing_task"),
            }
    return {"ocean": ocean, "spider_steer": ocean_map.get(ocean, "observe")}
