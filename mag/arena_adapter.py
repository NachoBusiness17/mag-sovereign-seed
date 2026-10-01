"""TextArena ↔ Mag seat bridge — capability probes without custom game code.

Optional dependency: pip install textarena
Schema: mag_arena_adapter.v1
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT

SCHEMA = "mag_arena_adapter.v1"
PROBES_CFG = ROOT / "configs" / "arena_probes.yaml"
STATE_PATH = ROOT / "memory" / "working" / "arena_probe.json"

try:
    import textarena as ta

    _HAS_TEXTARENA = True
except ImportError:
    ta = None  # type: ignore
    _HAS_TEXTARENA = False


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_probes() -> dict[str, Any]:
    if not PROBES_CFG.is_file():
        return {"games": {}}
    try:
        return yaml.safe_load(PROBES_CFG.read_text(encoding="utf-8")) or {"games": {}}
    except Exception:
        return {"games": {}}


def probe_meta(game_id: str) -> dict[str, Any]:
    """Resolve probe_type + routing_task for a TextArena env_id."""
    games = (_load_probes().get("games") or {})
    meta = games.get(game_id) or {}
    return {
        "game_id": game_id,
        "probe_type": str(meta.get("probe_type") or "structured_handoff"),
        "routing_task": str(meta.get("routing_task") or "structured_handoff"),
        "seats": int(meta.get("seats") or 2),
    }


def list_games() -> dict[str, Any]:
    """Games from arena_probes.yaml — no TextArena import required."""
    games = (_load_probes().get("games") or {})
    items = [
        {"game_id": gid, **(meta if isinstance(meta, dict) else {})}
        for gid, meta in games.items()
    ]
    return {
        "ok": True,
        "schema": SCHEMA,
        "textarena": _HAS_TEXTARENA,
        "games": items,
        "n": len(items),
    }


class MagSeatAgent:
    """Callable agent: seat id → Mag model registry / chat_provider / llm.chat."""

    def __init__(self, seat: str) -> None:
        self.seat = (seat or "local").strip().lower()
        self.last_messages: list[str] = []

    def __call__(self, observation: str) -> str:
        obs = (observation or "").strip()
        self.last_messages = [obs[:500]] if obs else []
        if os.environ.get("MAG_ARENA_RANDOM", "0") in ("1", "true", "yes"):
            action = _random_action(obs)
            self.last_messages.append(f"[random] {action}")
            return action
        try:
            action = self._llm_action(obs)
        except Exception as exc:
            action = _random_action(obs)
            self.last_messages.append(f"[fallback:{exc!s:.80}] {action}")
            return action
        self.last_messages.append(action[:200])
        return action

    def _llm_action(self, observation: str) -> str:
        seat = self.seat
        prompt = (
            f"You are playing a text game as seat '{seat}'.\n\n"
            f"{observation}\n\n"
            "Reply with your action only — one line, no explanation."
        )
        if seat in ("remote", "deepseek", "remote_meta_a", "remote_meta_b"):
            from models.providers import chat_provider

            res = chat_provider(
                "deepseek",
                "Arena seat. Reply one action only.",
                prompt,
                tier="T1",
                max_tokens=64,
                temperature=0.3,
            )
            return str(res.get("text") or res.get("content") or "").strip()
        from llm import chat
        from models.registry import model_for

        model = model_for("desk_orchestrator")
        return chat(model, "Reply one game action only.", prompt, temperature=0.3).strip()


def _random_action(observation: str) -> str:
    """Cheap legal-ish pick for tests — parse bracketed options or digits."""
    opts = re.findall(r"\[([^\]]+)\]", observation)
    if opts:
        return random.choice(opts).strip()
    nums = re.findall(r"\b([1-9])\b", observation)
    if nums:
        return random.choice(nums)
    words = re.findall(r"\b([A-HJ-Z][1-9]|[a-h][1-8][a-h][1-8])\b", observation)
    if words:
        return random.choice(words)
    return random.choice(("pass", "1", "a", "yes", "no"))


def _seat_for_player(player_id: int, seats: list[str]) -> str:
    if 0 <= player_id < len(seats):
        return seats[player_id]
    return seats[player_id % len(seats)] if seats else "local"


def _winner_from_rewards(rewards: Any, seats: list[str]) -> str | None:
    if not isinstance(rewards, dict) or not rewards:
        return None
    try:
        best_pid = max(rewards, key=lambda k: float(rewards[k]))
        if float(rewards[best_pid]) <= 0:
            return None
        return _seat_for_player(int(best_pid), seats)
    except (TypeError, ValueError, KeyError):
        return None


def run_probe(
    *,
    game_id: str,
    seats: list[str] | tuple[str, ...] | None = None,
    render: bool = False,
    max_steps: int = 80,
) -> dict[str, Any]:
    """Play one TextArena game with Mag seats; record telemetry via arena_learning."""
    if not _HAS_TEXTARENA:
        return {"ok": False, "error": "textarena not installed — pip install textarena"}

    meta = probe_meta(game_id)
    seat_list = list(seats) if seats else ["local", "remote"]
    n_players = max(meta.get("seats", 2), len(seat_list))
    while len(seat_list) < n_players:
        seat_list.append(f"seat_{len(seat_list)}")
    seat_list = seat_list[:n_players]

    probe_type = meta["probe_type"]
    gid = "probe-" + uuid.uuid4().hex[:10]
    message_log: list[dict[str, Any]] = []

    try:
        env = ta.make(env_id=game_id)
        if render:
            env = ta.wrappers.SimpleRenderWrapper(
                env=env,
                player_names={i: seat_list[i] for i in range(n_players)},
            )
        # ta.make() already includes LLMObservationWrapper — do not double-wrap
    except Exception as exc:
        return {"ok": False, "error": f"env init failed: {exc!s}"[:200], "game_id": game_id}

    agents = {i: MagSeatAgent(seat_list[i]) for i in range(n_players)}

    try:
        env.reset(num_players=n_players)
    except TypeError:
        env.reset()

    from mag import arena_learning as al

    done = False
    steps = 0
    while not done and steps < max_steps:
        player_id, observation = env.get_observation()
        seat = _seat_for_player(player_id, seat_list)
        agent = agents[player_id]
        t0 = time.perf_counter()
        action = agent(str(observation))
        timing_ms = int((time.perf_counter() - t0) * 1000)
        done, step_info = env.step(action=action)
        steps += 1
        illegal = bool(isinstance(step_info, dict) and step_info.get("invalid"))
        al.record_move(
            seat=seat,
            game=game_id,
            ok=not illegal,
            move=action[:32],
            illegal=illegal,
            timing_ms=timing_ms,
            game_id=gid,
            messages=list(agent.last_messages),
            probe_type=probe_type,
        )
        message_log.append(
            {
                "step": steps,
                "player_id": player_id,
                "seat": seat,
                "action": action[:120],
                "illegal": illegal,
                "timing_ms": timing_ms,
                "messages": list(agent.last_messages),
            }
        )

    rewards: Any = {}
    game_info: Any = {}
    try:
        closed = env.close()
        if isinstance(closed, tuple) and len(closed) >= 2:
            rewards, game_info = closed[0], closed[1]
        elif isinstance(closed, dict):
            rewards = closed
    except Exception:
        pass

    winner = _winner_from_rewards(rewards, seat_list)
    status = "draw" if winner is None else "finished"
    white, black = seat_list[0], seat_list[1] if len(seat_list) > 1 else "remote"

    rec = al.record_game_end(
        game=game_id,
        white=white,
        black=black,
        status=status,
        winner=winner,
        moves=steps,
        game_id=gid,
        probe_type=probe_type,
    )

    state = {
        "schema": SCHEMA,
        "game_id": gid,
        "game": game_id,
        "probe_type": probe_type,
        "routing_task": meta["routing_task"],
        "seats": seat_list,
        "status": status,
        "winner": winner,
        "steps": steps,
        "rewards": rewards,
        "game_info": game_info if isinstance(game_info, dict) else {},
        "message_log": message_log,
        "updated_ts": _utc(),
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

    return {
        "ok": True,
        "probe": state,
        "record": rec,
        "message_log": message_log,
        "league": rec.get("league"),
    }
