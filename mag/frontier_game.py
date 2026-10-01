"""frontier_game — THE FRONTIER GAME PLAYS, AND ITS PLAY BUILDS OUR GAME.

Operator (2026-08-13): "those are all legacy i want the frontier game to play its building our
game while they play." So: the party (our frontier seats) plays turn-based at the table, and every
move that ADVANCES is folded as a content-addressed VERKLE KNOT into the world (game_world). The
world is the server-authoritative truth (game_world.v1); play == building: each accepted move grows
the world's entity count, committed to a self-verifying root. The DM narrates the emerging world
that the play itself is constructing. This is the "dnd in an mmo mud that solves topological knot
problems" — the frontiers play the game, and the game is literally built by their play.

THE LOOP (deterministic DM core + the frontiers as the builders):
  play(region, rounds) ->
    DM narrates the current room + the emerging world (what the play has built so far)
    each party member moves IN TURN (honest per-seat ok — down seats report down, never fabricate)
    advancing moves -> game_world.set_state("game.frontier.<rnd>.<seat>", {move, region}) folds a
                       verkle knot -> the world grows (entities += 1) -> server-authoritative truth
    render the world
  The entity count IS the game being built. The root IS the proof it's real.

Schema: frontier_game.v1 · deterministic $0 DM core · reuse: game_dm, game_environment, game_world,
game_world_render
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "frontier_game.v1"
DEFAULT_REGION = "the_mirror_sea"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env() -> tuple[Any, Any, Any, Any]:
    from mag import game_dm, game_environment, game_world, game_world_render
    return game_dm, game_environment, game_world, game_world_render


def _is_echo(move: str, prompt: str) -> bool:
    """True when a 'move' is just the prompt echoing back (a broken read-back, not real play). An
    echo must NEVER build the world — it's not a frontier decision."""
    m = (move or "").strip().lower()
    p = (prompt or "").strip().lower()
    if not m:
        return True
    # the whole prompt, or the DM scene text, reappearing in the 'move' = echo, not a decision
    if len(p) > 40 and (m.startswith(p[:40]) or p[:60] in m):
        return True
    if any(t in m for t in ("make your party decision", "you are a player at the table",
                            "the dm set this scene", "what do you do? root it in your nature")):
        return True
    return False


def _region_judge(seat: str, move: str, region_key: str) -> tuple[str, str]:
    """Region-aware DM ruling: does the move engage the region's invariant, or hold the line?"""
    m = (move or "").lower()
    if not m.strip():
        return "no_move", "no action taken"
    _, game_environment, _, _ = _env()
    scene = game_environment.REGIONS.get(region_key, {})
    kw = re.findall(r"[a-z]+", scene.get("invariant", "") + " " + scene.get("desc", ""))
    hits = [w for w in kw if w in m and len(w) > 3]
    if hits:
        return "advances", f"engages the thread ({', '.join(sorted(set(hits))[:3])})"
    if any(w in m for w in ("wait", "watch", "listen", "kneel", "stay", "observe", "hold")):
        return "advances", "holds the line, aware"
    return "wastes", "burns a turn without pressing the thread"


def _render() -> str:
    try:
        _, _, _, game_world_render = _env()
        return (game_world_render.render().get("ascii") or "")
    except Exception:
        return ""


def _container_moves(prompt: str, region: str) -> list[dict[str, Any]]:
    """Ask the CONTAINER free-frontend seats (the 'docker' path — visible over CDP). Honest: if the
    container browser is down, each seat reports down. Never fabricate an answer."""
    out: list[dict[str, Any]] = []
    try:
        from mag import cdp_runner
    except Exception as e:
        return [{"seat": "container", "ok": False, "move": "", "error": str(e)[:80]}]
    for surf in ("grok", "deepseek"):  # free visible container seats
        try:
            r = cdp_runner.ask_browser(surf, prompt, timeout_s=60)
            text = str(r.get("answer") or r.get("text") or "").strip()
            if text:
                out.append({"seat": f"container:{surf}", "ok": True, "move": text,
                            "verdict": _region_judge(f"container:{surf}", text, region)[0],
                            "detail": _region_judge(f"container:{surf}", text, region)[1]})
            else:
                out.append({"seat": f"container:{surf}", "ok": False, "move": "",
                            "error": (r.get("error") or "no answer")[:80]})
        except Exception as e:
            out.append({"seat": f"container:{surf}", "ok": False, "move": "", "error": str(e)[:80]})
    return out


def play(region: str = DEFAULT_REGION, rounds: int = 2,
         container: bool = False) -> dict[str, Any]:
    """PLAY THE FRONTIER GAME — turn-based, DM-led, and every advancing move BUILDS the world as a
    verkle knot. Returns the session log + the world's entity count (the game built by the play).
    container=True also seats the container free-frontend seats (the visible 'docker' path)."""
    game_dm, game_environment, game_world, _ = _env()
    rounds = max(1, int(rounds))
    log: list[dict[str, Any]] = []
    round_states: list[dict[str, Any]] = []
    try:
        from mag.party_subchain import want_full as _want_full
        _full = _want_full()
    except Exception:
        _full = False
    def _hist(entries, n_fallback):
        rows = list(entries) if _full else list(entries)[-n_fallback:]
        bits = []
        for e in rows:
            mv = e.get('move') or ''
            bits.append(e['seat'] + ': ' + mv)
        return '; '.join(bits) or 'nothing yet'

    for rnd in range(1, rounds + 1):
        scene = game_environment.explore(region)
        prompt = (f"You are a player at the table in {scene['region']}. The DM set this scene: "
                  f"{scene['desc']}. Party has already set in motion: "
                  f"{_hist(log, 3)}. "
                  f"Make YOUR party decision in character — what do YOU do? Root it in your nature. "
                  f"One clear action.")
        for seat in game_dm.party():
            # Rebuild after every move so later seats see earlier seats from this same round.
            prompt = (f"You are a player at the table in {scene['region']}. The DM set this scene: "
                      f"{scene['desc']}. Party has already set in motion: "
                      f"{_hist(log, 6)}. "
                      "Make YOUR party decision in character. Root it in your nature. One clear action.")
            mv = game_dm.ask_player(seat, prompt)
            if not mv.get("ok"):
                log.append({"seat": seat, "ok": False, "move": "", "error": (mv.get("error") or "")[:80]})
                try:
                    from mag import party_subchain
                    party_subchain.append(seat=seat, ok=False, move="", kind="frontier_game")
                except Exception:
                    pass
                continue
            verdict, detail = _region_judge(seat, mv.get("move", ""), region)
            if _is_echo(mv.get("move", ""), prompt):
                verdict, detail = "no_move", "echo of the prompt — not a real move (never folds)"
            entry = {"seat": seat, "ok": True, "move": (mv.get("move") or "").strip(),
                     "verdict": verdict, "detail": detail}
            log.append(entry)
            try:
                from mag import party_subchain
                party_subchain.append(seat=seat, ok=True, move=entry["move"],
                                      kind="frontier_game")
            except Exception:
                pass
            if verdict == "advances":
                # PLAY == BUILD: fold the advancing move as a verkle knot into the world.
                game_world.set_state(
                    f"game.frontier.{_now().replace(':','-')}.{seat}",
                    {"seat": seat, "region": region, "move": entry["move"], "ts": _now()},
                    source="frontier_game")
        if container:
            for entry in _container_moves(prompt, region):
                if entry.get("ok") and _is_echo(entry.get("move", ""), prompt):
                    entry["verdict"], entry["detail"] = "no_move", "echo — never folds"
                log.append(entry)
                if entry.get("ok") and entry.get("verdict") == "advances":
                    game_world.set_state(
                        f"game.frontier.{_now().replace(':','-')}.{entry['seat']}",
                        {"seat": entry["seat"], "region": region, "move": entry["move"], "ts": _now()},
                        source="frontier_game")
        round_states.append({"round": rnd, "region": region,
                             "world_entities": game_world.world_status().get("n_entities", 0),
                             "ascii": _render()})
    ws = game_world.world_status()
    return {"ok": True, "schema": SCHEMA, "region": region, "rounds": rounds,
            "moves": log, "round_states": round_states,
            "world_entities": ws.get("n_entities", 0),
            "world_root": ws.get("root", ""),
            "reachable": f"{sum(1 for m in log if m.get('ok'))}/{len(log)} frontier moves landed",
            "note": "the frontier game played, and each advancing move was folded as a verkle knot "
                    "into the world — the game was built by the play (server-authoritative truth)"}


def status() -> dict[str, Any]:
    game_dm, game_environment, game_world, _ = _env()
    ws = game_world.world_status()
    return {"ok": True, "schema": SCHEMA,
            "contract": "play(region,rounds)->the party plays turn-based; every advancing move is "
                        "folded as a verkle knot into game_world, so PLAY BUILDS the game (entity "
                        "count grows, committed to a self-verifying root); status()->world entities",
            "cost": "deterministic $0 DM core; the frontier seats are the scarce players",
            "surface": "the frontier game — the party plays, and the play builds our game",
            "party": game_dm.party(),
            "world_entities": ws.get("n_entities", 0),
            "world_root": ws.get("root", ""),
            "regions": sorted(game_environment.REGIONS),
            "honest_gate": "frontier moves need the seats reachable; down seats report down, never "
                           "fabricated"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="frontier-game")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "play"])
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--rounds", type=int, default=2)
    a = ap.parse_args(argv)
    if a.cmd == "play":
        print(json.dumps(play(a.region, a.rounds), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
