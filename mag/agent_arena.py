"""Agent arena — proof-of-concept game surface for seat vs seat (chess first).

Generic `game` slot on disk; chess uses python-chess when installed.
Schema: mag_agent_arena.v1
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_agent_arena.v1"
STATE_PATH = ROOT / "memory" / "working" / "agent_arena.json"
SUPPORTED_GAMES = frozenset({"chess"})

try:
    import chess

    _HAS_CHESS = True
except ImportError:
    chess = None  # type: ignore
    _HAS_CHESS = False

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_UNICODE = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _board_from_fen(fen: str) -> list[list[str | None]]:
    """8x8 unicode grid rank 8 → rank 1."""
    board: list[list[str | None]] = []
    rows = fen.split()[0].split("/")
    for row in rows:
        line: list[str | None] = []
        for ch in row:
            if ch.isdigit():
                line.extend([None] * int(ch))
            else:
                line.append(_UNICODE.get(ch, ch))
        board.append(line)
    return board


def _parse_move(board: "chess.Board", raw: str) -> "chess.Move | None":
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return board.parse_san(text)
    except Exception:
        pass
    try:
        return chess.Move.from_uci(text.lower())
    except Exception:
        pass
    m = re.search(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", text.lower())
    if m:
        try:
            return chess.Move.from_uci(m.group(1))
        except Exception:
            return None
    m = re.search(r"\b(O-O-O|O-O|[NBRQK]?[a-h]?x?[a-h][1-8](?:=[NBRQ])?[+#]?)\b", text)
    if m:
        try:
            return board.parse_san(m.group(1))
        except Exception:
            return None
    return None


def status() -> dict[str, Any]:
    state = _load()
    if not state.get("game_id"):
        return {
            "ok": True,
            "schema": SCHEMA,
            "active": False,
            "chess_lib": _HAS_CHESS,
            "supported": sorted(SUPPORTED_GAMES),
            "note": "POST new game to start · seats play via agent_turn",
        }
    return _public_state(state)


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    fen = state.get("fen") or START_FEN
    strategies = state.get("strategies") or {}
    out: dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA,
        "active": True,
        "game_id": state.get("game_id"),
        "game": state.get("game", "chess"),
        "fen": fen,
        "board": _board_from_fen(fen),
        "turn": state.get("turn", "white"),
        "turn_seat": state.get("turn_seat"),
        "white": state.get("white", "local"),
        "black": state.get("black", "remote"),
        "strategies": strategies,
        "status": state.get("status", "ongoing"),
        "winner": state.get("winner"),
        "legal_moves": state.get("legal_moves") or [],
        "move_history": state.get("move_history") or [],
        "message_log": state.get("message_log") or [],
        "last_move": state.get("last_move"),
        "chess_lib": _HAS_CHESS,
    }
    try:
        from mag.arena_strategies import get_strategy

        out["white_strategy"] = get_strategy(str(strategies.get("white") or "tide_janitor"))
        out["black_strategy"] = get_strategy(str(strategies.get("black") or "predator_strike"))
    except Exception:
        pass
    return out


def new_game(
    *,
    game: str = "chess",
    white: str = "local",
    black: str = "remote",
    white_strategy: str = "",
    black_strategy: str = "",
) -> dict[str, Any]:
    game = (game or "chess").strip().lower()
    if game not in SUPPORTED_GAMES:
        return {"ok": False, "error": f"unsupported game: {game}"}
    if not _HAS_CHESS:
        return {"ok": False, "error": "python-chess not installed — pip install chess"}

    from mag.arena_strategies import default_for_seat

    board = chess.Board()
    state = {
        "schema": SCHEMA,
        "game_id": "arena-" + uuid.uuid4().hex[:10],
        "game": game,
        "fen": board.fen(),
        "turn": "white",
        "turn_seat": white,
        "white": white,
        "black": black,
        "strategies": {
            "white": (white_strategy or default_for_seat("white")).strip(),
            "black": (black_strategy or default_for_seat("black")).strip(),
        },
        "status": "ongoing",
        "winner": None,
        "legal_moves": [board.san(m) for m in board.legal_moves][:80],
        "move_history": [],
        "message_log": [],
        "last_move": None,
        "created_ts": _utc(),
        "updated_ts": _utc(),
    }
    _save(state)
    out = _public_state(state)
    out["ok"] = True
    return out


def apply_move(move: str, *, seat: str = "") -> dict[str, Any]:
    if not _HAS_CHESS:
        return {"ok": False, "error": "python-chess not installed — pip install chess"}
    state = _load()
    if not state.get("game_id"):
        return {"ok": False, "error": "no active game — POST new first"}
    if state.get("status") != "ongoing":
        return {"ok": False, "error": "game finished", "status": state.get("status")}

    board = chess.Board(state.get("fen") or START_FEN)
    mv = _parse_move(board, move)
    if mv is None or mv not in board.legal_moves:
        legal = [board.san(m) for m in board.legal_moves][:20]
        bad_seat = (seat or "").strip() or state.get("turn_seat") or "operator"
        try:
            from mag import arena_learning as al
            from mag.arena_strategies import emit_spider_arena_signal, strategy_for_game_state

            strat = strategy_for_game_state(state, bad_seat)
            emit_spider_arena_signal(event="illegal_move", state=state, seat=bad_seat, extra={"move": move})
            al.record_move(
                seat=bad_seat,
                game=str(state.get("game") or "chess"),
                ok=False,
                move=move,
                illegal=True,
                game_id=state.get("game_id"),
                probe_type=strat.get("ocean"),
                messages=[f"[{strat.get('ocean')}] illegal: {move!r}"],
            )
        except Exception:
            pass
        return {"ok": False, "error": f"illegal move: {move!r}", "legal_moves": legal}

    san = board.san(mv)
    board.push(mv)
    seat = (seat or "").strip() or state.get("turn_seat") or "operator"

    history = list(state.get("move_history") or [])
    msg_log = list(state.get("message_log") or [])
    try:
        from mag.arena_strategies import strategy_for_game_state

        strat = strategy_for_game_state(state, seat)
        history.append(
            {
                "san": san,
                "uci": mv.uci(),
                "seat": seat,
                "ts": _utc(),
                "ocean": strat.get("ocean"),
                "strategy": strat.get("id"),
            }
        )
        msg_log.append(
            {
                "ts": _utc(),
                "seat": seat,
                "move": san,
                "ocean": strat.get("ocean"),
                "strategy": strat.get("id"),
                "spider_steer": strat.get("spider_steer"),
            }
        )
    except Exception:
        history.append({"san": san, "uci": mv.uci(), "seat": seat, "ts": _utc()})

    status_text = "ongoing"
    winner = None
    if board.is_checkmate():
        status_text = "checkmate"
        winner = state.get("black") if board.turn else state.get("white")
    elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        status_text = "draw"
    elif board.is_game_over():
        status_text = "draw"

    turn = "white" if board.turn else "black"
    turn_seat = state.get("white") if board.turn else state.get("black")

    state.update(
        {
            "fen": board.fen(),
            "turn": turn,
            "turn_seat": turn_seat,
            "status": status_text,
            "winner": winner,
            "legal_moves": [board.san(m) for m in board.legal_moves][:80],
            "move_history": history,
            "message_log": msg_log,
            "last_move": {"san": san, "uci": mv.uci(), "seat": seat},
            "updated_ts": _utc(),
        }
    )
    _save(state)
    try:
        from mag import arena_learning as al
        from mag.arena_strategies import strategy_for_game_state

        strat = strategy_for_game_state(state, seat)
        al.record_move(
            seat=seat,
            game=str(state.get("game") or "chess"),
            ok=True,
            move=san,
            game_id=state.get("game_id"),
            probe_type=strat.get("ocean"),
            messages=[f"[{strat.get('ocean')}] {san}"],
        )
        if status_text != "ongoing":
            al.ingest_arena_state(state)
    except Exception:
        pass
    out = _public_state(state)
    out["ok"] = True
    out["applied"] = san
    return out


def _llm_pick_move(*, seat: str, fen: str, legal: list[str], state: dict[str, Any] | None = None) -> str:
    """Ask seat model for one legal SAN move — playbook rules + strategy."""
    legal_str = ", ".join(legal[:40])
    base = (
        f"Position FEN:\n{fen}\n\n"
        f"Legal moves (SAN): {legal_str}\n\n"
        "Pick EXACTLY ONE move from the legal list."
    )
    prompt = base
    if state:
        try:
            from mag.local_playbook import augment_arena_prompt

            prompt = augment_arena_prompt(base, state=state, seat=seat)
        except Exception:
            try:
                from mag.arena_strategies import augment_move_prompt, strategy_for_game_state

                strat = strategy_for_game_state(state, seat)
                prompt = augment_move_prompt(
                    f"You are playing chess as seat '{seat}'. {base}", strategy=strat
                )
            except Exception:
                prompt = (
                    f"You are playing chess as seat '{seat}'. {base}\n\n"
                    "Reply with EXACTLY ONE move from the legal list — SAN only."
                )
    else:
        prompt = (
            f"You are playing chess as seat '{seat}'. {base}\n\n"
            "Reply with EXACTLY ONE move from the legal list — SAN only."
        )
    seat = (seat or "local").strip().lower()
    if seat in ("remote", "deepseek", "remote_meta_a", "remote_meta_b"):
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            "Chess engine seat. Reply one SAN move only.",
            prompt,
            tier="T1",
            max_tokens=16,
            temperature=0.2,
        )
        return str(res.get("text") or res.get("content") or "").strip()
    from llm import chat
    from models.registry import model_for

    model = model_for("desk_orchestrator")
    return chat(model, "Reply one SAN chess move only.", prompt, temperature=0.2).strip()


def agent_turn(*, seat: str = "", dry: bool = False) -> dict[str, Any]:
    if not _HAS_CHESS:
        return {"ok": False, "error": "python-chess not installed — pip install chess"}
    state = _load()
    if not state.get("game_id"):
        return {"ok": False, "error": "no active game"}
    if state.get("status") != "ongoing":
        return {"ok": False, "error": "game over", "status": state.get("status")}

    board = chess.Board(state.get("fen") or START_FEN)
    turn_seat = state.get("turn_seat") or "local"
    seat = (seat or turn_seat).strip().lower()
    if seat != turn_seat:
        return {
            "ok": False,
            "error": f"not {seat}'s turn — waiting for {turn_seat}",
            "turn_seat": turn_seat,
        }

    legal = [board.san(m) for m in board.legal_moves]
    if not legal:
        return {"ok": False, "error": "no legal moves"}

    if dry:
        return {"ok": True, "dry": True, "seat": seat, "legal_moves": legal[:20]}

    if os.environ.get("MAG_ARENA_RANDOM", "0") in ("1", "true", "yes"):
        import random

        pick = random.choice(legal)
    else:
        try:
            pick = _llm_pick_move(seat=seat, fen=board.fen(), legal=legal, state=state)
        except Exception as exc:
            return {"ok": False, "error": f"seat move failed: {exc!s}"[:200], "legal_moves": legal[:12]}

    result = apply_move(pick, seat=seat)
    result["agent_seat"] = seat
    result["raw_pick"] = pick
    return result


def handle_action(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or body.get("cmd") or "status").strip().lower()
    if action in ("status", "get"):
        return status()
    if action in ("list_games", "games"):
        from mag import arena_adapter as aa

        return aa.list_games()
    if action == "probe":
        from mag import arena_adapter as aa

        if not aa._HAS_TEXTARENA:
            return {"ok": False, "error": "textarena not installed — pip install textarena"}
        seats_raw = body.get("seats") or body.get("seat_list") or ["local", "remote"]
        if isinstance(seats_raw, str):
            seats = [s.strip() for s in seats_raw.split(",") if s.strip()]
        else:
            seats = [str(s) for s in seats_raw]
        return aa.run_probe(
            game_id=str(body.get("game_id") or body.get("game") or "TicTacToe-v0"),
            seats=seats or ["local", "remote"],
            render=body.get("render") in (True, "1", 1, "true", "yes"),
            max_steps=int(body.get("max_steps") or 80),
        )
    if action in ("new", "reset", "start"):
        return new_game(
            game=str(body.get("game") or "chess"),
            white=str(body.get("white") or "local"),
            black=str(body.get("black") or "remote"),
            white_strategy=str(body.get("white_strategy") or body.get("whiteStrategy") or ""),
            black_strategy=str(body.get("black_strategy") or body.get("blackStrategy") or ""),
        )
    if action in ("strategies", "strategy_list"):
        from mag.arena_strategies import list_strategies

        return list_strategies()
    if action in ("playbooks", "playbook_list"):
        from mag.local_playbook import list_playbooks

        return list_playbooks()
    if action == "author_playbook":
        from mag.local_playbook import frontier_author_playbook

        return frontier_author_playbook(
            domain=str(body.get("domain") or "desk"),
            goal=str(body.get("goal") or ""),
            playbook_id=str(body.get("playbook_id") or body.get("id") or ""),
        )
    if action == "move":
        return apply_move(str(body.get("move") or body.get("san") or ""), seat=str(body.get("seat") or ""))
    if action in ("agent_turn", "agent", "auto"):
        return agent_turn(seat=str(body.get("seat") or ""), dry=bool(body.get("dry")))
    if action == "play":
        # One round: current seat then optional opponent if still ongoing
        first = agent_turn(seat=str(body.get("seat") or ""), dry=bool(body.get("dry")))
        if not first.get("ok") or body.get("single"):
            return first
        st = _load()
        if st.get("status") != "ongoing":
            return first
        second = agent_turn(dry=bool(body.get("dry")))
        return {"ok": True, "moves": [first, second], "state": status()}
    if action in ("league", "rankings"):
        from mag.arena_learning import league_snapshot

        return {"ok": True, **league_snapshot(game=str(body.get("game") or "chess"))}
    if action == "tournament":
        from mag.arena_learning import run_tournament

        seats_raw = body.get("seats") or body.get("seat_list") or ["local", "remote"]
        if isinstance(seats_raw, str):
            seats = tuple(s.strip() for s in seats_raw.split(",") if s.strip())
        else:
            seats = tuple(str(s) for s in seats_raw)
        return run_tournament(
            game=str(body.get("game") or "chess"),
            rounds=int(body.get("rounds") or 1),
            seats=seats or ("local", "remote"),
            random_moves=body.get("random", True) is not False,
        )
    if action == "routing_hint":
        from mag.arena_learning import routing_hint

        return {"ok": True, **routing_hint(
            game=str(body.get("game") or "chess"),
            task=str(body.get("task") or "structured_handoff"),
            budget=str(body.get("budget") or "low"),
        )}
    return {"ok": False, "error": f"unknown action: {action}"}
