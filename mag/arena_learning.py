"""Arena learning — competitive seat probes → profiles → nervous/switchboard routing.

Records match outcomes from agent_arena, emits training events, builds cost/value
profiles for routing (fast/slow, high/low information seats).

Schema: mag_arena_learning.v1
Trail: memory/runs/arena_learning_trail.jsonl
Profiles: memory/training/arena_profiles.jsonl
League snapshot: memory/training/arena_league.json
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_arena_learning.v1"
TRAIL = ROOT / "memory" / "runs" / "arena_learning_trail.jsonl"
PROFILES_PATH = ROOT / "memory" / "training" / "arena_profiles.jsonl"
LEAGUE_PATH = ROOT / "memory" / "training" / "arena_league.json"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _resolve_model(seat: str) -> str:
    seat = (seat or "unknown").strip().lower()
    mapping = {
        "local": "desk_orchestrator",
        "remote": "deepseek",
        "deepseek": "deepseek",
        "conductor": "desk_conductor",
    }
    role = mapping.get(seat, seat)
    try:
        from models.registry import model_for

        return model_for(role)
    except Exception:
        return role


def record_move(
    *,
    seat: str,
    game: str = "chess",
    ok: bool,
    move: str = "",
    illegal: bool = False,
    timing_ms: int | None = None,
    game_id: str | None = None,
    messages: list[str] | None = None,
    probe_type: str = "",
) -> dict[str, Any]:
    """One move attempt — feeds seat weakness detection."""
    row = {
        "schema": SCHEMA,
        "kind": "move",
        "ts": _utc(),
        "seat": seat,
        "model": _resolve_model(seat),
        "game": game,
        "ok": ok,
        "move": (move or "")[:32],
        "illegal": illegal,
        "timing_ms": timing_ms,
        "game_id": game_id,
        "probe_type": (probe_type or "").strip() or None,
        "messages": [str(m)[:240] for m in (messages or [])[:8]] or None,
    }
    row = {k: v for k, v in row.items() if v is not None}
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if illegal:
        _trail("illegal_move", seat=seat, model=row["model"], move=row["move"], game_id=game_id)
    return row


def record_game_end(
    *,
    game: str,
    white: str,
    black: str,
    status: str,
    winner: str | None,
    moves: int,
    game_id: str | None = None,
    move_log: list[dict[str, Any]] | None = None,
    probe_type: str = "",
) -> dict[str, Any]:
    """Game finished — update league + emit training event."""
    white_m = _resolve_model(white)
    black_m = _resolve_model(black)
    outcome = {
        "schema": SCHEMA,
        "kind": "game",
        "ts": _utc(),
        "game_id": game_id or f"arena-{uuid.uuid4().hex[:8]}",
        "game": game,
        "white": white,
        "black": black,
        "white_model": white_m,
        "black_model": black_m,
        "status": status,
        "winner": winner,
        "moves": moves,
        "probe_type": (probe_type or "").strip() or None,
    }
    if not outcome.get("probe_type"):
        outcome.pop("probe_type", None)
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome, ensure_ascii=False) + "\n")

    league = rebuild_league(game=game, probe_type=probe_type or None)
    _trail("game_end", game_id=outcome["game_id"], status=status, winner=winner, moves=moves)

    try:
        from mag.training_events import emit

        emit(
            "arena_match",
            join={
                "game_id": outcome["game_id"],
                "white": white,
                "black": black,
            },
            input_data={
                "game": game,
                "white_model": white_m,
                "black_model": black_m,
            },
            action={"moves": moves, "status": status},
            outcome={
                "winner": winner,
                "league_top": (league.get("rankings") or [])[:2],
            },
            pattern_tags=["arena_match", game, f"status_{status}"]
            + ([f"probe_{probe_type}"] if probe_type else []),
            tier_max="T2",
        )
    except Exception:
        pass

    return {"ok": True, "record": outcome, "league": league}


def _read_profile_rows(
    *,
    game: str | None = None,
    probe_type: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    if not PROFILES_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in PROFILES_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if game and o.get("game") != game:
            continue
        if probe_type and o.get("probe_type") != probe_type:
            continue
        rows.append(o)
    return rows[-limit:]


def rebuild_league(*, game: str = "chess", probe_type: str | None = None) -> dict[str, Any]:
    """Aggregate seat/model stats for switchboard + nervous routing."""
    stats: dict[str, dict[str, Any]] = {}

    def _bucket(seat: str, model: str) -> dict[str, Any]:
        key = f"{seat}:{model}"
        if key not in stats:
            stats[key] = {
                "seat": seat,
                "model": model,
                "game": game,
                "probe_type": probe_type,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "games": 0,
                "illegal_moves": 0,
                "move_attempts": 0,
                "timing_ms_total": 0,
                "timing_ms_n": 0,
            }
        return stats[key]

    for row in _read_profile_rows(game=game, probe_type=probe_type):
        kind = row.get("kind")
        if kind == "move":
            seat = str(row.get("seat") or "unknown")
            model = str(row.get("model") or _resolve_model(seat))
            b = _bucket(seat, model)
            b["move_attempts"] += 1
            if row.get("illegal"):
                b["illegal_moves"] += 1
            t = row.get("timing_ms")
            if isinstance(t, int):
                b["timing_ms_total"] += t
                b["timing_ms_n"] += 1
        elif kind == "game":
            white = str(row.get("white") or "local")
            black = str(row.get("black") or "remote")
            winner = row.get("winner")
            st = str(row.get("status") or "")
            for seat, model in (
                (white, str(row.get("white_model") or _resolve_model(white))),
                (black, str(row.get("black_model") or _resolve_model(black))),
            ):
                b = _bucket(seat, model)
                b["games"] += 1
                if st == "draw" or not winner:
                    b["draws"] += 1
                elif winner == seat:
                    b["wins"] += 1
                else:
                    b["losses"] += 1

    rankings: list[dict[str, Any]] = []
    for b in stats.values():
        g = max(1, int(b["games"]))
        attempts = max(1, int(b["move_attempts"]))
        avg_ms = int(b["timing_ms_total"] / b["timing_ms_n"]) if b["timing_ms_n"] else None
        win_rate = b["wins"] / g
        illegal_rate = b["illegal_moves"] / attempts
        # Value: strong play, cheap, legal
        value = win_rate * 0.6 + (1.0 - min(illegal_rate, 1.0)) * 0.4
        if avg_ms and avg_ms > 8000:
            value *= 0.85
        strengths: list[str] = []
        weaknesses: list[str] = []
        if win_rate >= 0.55:
            strengths.append("win_rate")
        if illegal_rate <= 0.1:
            strengths.append("legal_moves")
        if avg_ms and avg_ms < 5000:
            strengths.append("fast_local")
        if illegal_rate > 0.25:
            weaknesses.append("illegal_move_rate")
        if avg_ms and avg_ms > 12000:
            weaknesses.append("slow")
        if b["wins"] == 0 and g >= 2:
            weaknesses.append("no_wins_yet")
        rankings.append(
            {
                **b,
                "win_rate": round(win_rate, 3),
                "illegal_rate": round(illegal_rate, 3),
                "avg_timing_ms": avg_ms,
                "value_score": round(value, 3),
                "strengths": strengths,
                "weaknesses": weaknesses,
            }
        )
    rankings.sort(key=lambda x: (x["value_score"], x["win_rate"]), reverse=True)

    league = {
        "schema": SCHEMA,
        "ts": _utc(),
        "game": game,
        "probe_type": probe_type,
        "rankings": rankings,
        "n_seats": len(rankings),
        "routing_hint": routing_hint(game=game, probe_type=probe_type, league=rankings),
    }
    LEAGUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEAGUE_PATH.write_text(json.dumps(league, indent=2), encoding="utf-8")
    return league


def league_snapshot(*, game: str = "chess", probe_type: str | None = None) -> dict[str, Any]:
    if LEAGUE_PATH.is_file() and not probe_type:
        try:
            data = json.loads(LEAGUE_PATH.read_text(encoding="utf-8"))
            if data.get("game") == game and data.get("rankings"):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return rebuild_league(game=game, probe_type=probe_type)


def routing_hint(
    *,
    game: str = "chess",
    task: str = "structured_handoff",
    budget: str = "low",
    probe_type: str | None = None,
    league: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost/value seat recommendation from arena probes."""
    ranks = league if league is not None else league_snapshot(game=game, probe_type=probe_type).get("rankings") or []
    if probe_type:
        ranks = [r for r in ranks if not r.get("probe_type") or r.get("probe_type") == probe_type]
    if not ranks:
        return {
            "task": task,
            "budget": budget,
            "probe_type": probe_type,
            "recommend": "local",
            "reason": "no arena data — default slow seat",
        }
    best = ranks[0]
    cheap = next((r for r in ranks if r.get("avg_timing_ms") and r["avg_timing_ms"] < 6000), best)
    accurate = next((r for r in ranks if r.get("illegal_rate", 1) < 0.15), best)
    if budget == "low" or task in ("scut", "canvas_move", "handoff"):
        pick = cheap if cheap.get("illegal_rate", 1) < 0.3 else best
        return {
            "task": task,
            "budget": budget,
            "probe_type": probe_type,
            "recommend": pick.get("seat"),
            "model": pick.get("model"),
            "value_score": pick.get("value_score"),
            "reason": "arena league — low budget favors fast legal local",
        }
    pick = accurate
    return {
        "task": task,
        "budget": budget,
        "probe_type": probe_type,
        "recommend": pick.get("seat"),
        "model": pick.get("model"),
        "value_score": pick.get("value_score"),
        "reason": "arena league — high budget favors accuracy",
    }


def ingest_arena_state(state: dict[str, Any]) -> dict[str, Any] | None:
    """Called when arena game ends — derive training record from disk state."""
    if not state.get("game_id"):
        return None
    status = str(state.get("status") or "ongoing")
    if status == "ongoing":
        return None
    gid = str(state.get("game_id"))
    for row in _read_profile_rows():
        if row.get("kind") == "game" and row.get("game_id") == gid:
            return None
    history = state.get("move_history") or []
    return record_game_end(
        game=str(state.get("game") or "chess"),
        white=str(state.get("white") or "local"),
        black=str(state.get("black") or "remote"),
        status=status,
        winner=state.get("winner"),
        moves=len(history),
        game_id=str(state.get("game_id")),
        move_log=history,
    )


def run_tournament(
    *,
    game: str = "chess",
    rounds: int = 1,
    seats: tuple[str, ...] = ("local", "remote"),
    random_moves: bool = True,
) -> dict[str, Any]:
    """Probe seat pairs competitively — feeds learning loop."""
    from mag import agent_arena as arena

    if not arena._HAS_CHESS:
        return {"ok": False, "error": "python-chess not installed"}

    import os

    if random_moves:
        os.environ["MAG_ARENA_RANDOM"] = "1"

    results: list[dict[str, Any]] = []
    n = max(1, min(rounds, 10))
    seat_list = list(seats) or ["local", "remote"]

    for i in range(n):
        white, black = seat_list[i % len(seat_list)], seat_list[(i + 1) % len(seat_list)]
        arena.new_game(game=game, white=white, black=black)
        plies = 0
        while plies < 120:
            st = arena.status()
            if not st.get("active") or st.get("status") != "ongoing":
                break
            turn = st.get("turn_seat") or "local"
            before = arena._load()
            turn_res = arena.agent_turn(seat=turn)
            plies += 1
            if not turn_res.get("ok"):
                record_move(
                    seat=turn,
                    game=game,
                    ok=False,
                    move=str(turn_res.get("raw_pick") or ""),
                    illegal=True,
                    game_id=before.get("game_id"),
                )
                break
            record_move(
                seat=turn,
                game=game,
                ok=True,
                move=str(turn_res.get("applied") or turn_res.get("raw_pick") or ""),
                game_id=before.get("game_id"),
            )
        final = arena._load()
        rec = ingest_arena_state(final)
        if rec:
            results.append(rec)

    league = league_snapshot(game=game)
    return {"ok": True, "rounds": n, "games": len(results), "results": results, "league": league}


def nervous_glance() -> dict[str, Any]:
    """Compact block for nervous_system.build_glance."""
    league = league_snapshot()
    ranks = league.get("rankings") or []
    top = ranks[0] if ranks else None
    try:
        league_path = str(LEAGUE_PATH.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        league_path = str(LEAGUE_PATH)
    return {
        "schema": SCHEMA,
        "active_game": bool(_read_json_safe(ROOT / "memory" / "working" / "agent_arena.json").get("game_id")),
        "n_seats_ranked": len(ranks),
        "top_seat": top.get("seat") if top else None,
        "top_value": top.get("value_score") if top else None,
        "routing_hint": league.get("routing_hint"),
        "path": league_path,
    }


def _read_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
