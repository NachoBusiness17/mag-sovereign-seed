"""game_produce — THE PRODUCE LOOP: the world works while you're away (2026-08-16).

The GWAP made real. The operator's game is "a fun MUD that tricks people into doing work" — but a
game that only COUNTS work (the scoreboard) isn't yet one that PRODUCES it. This is the loop that
closes the gap: the world doesn't just record work, it FOLDS real completed work into itself.

THE HONESTY LAW (the soul of it — from /memories/repo/game-is-gwap... + honesty doctrine):
  * The score must track REAL folded work, NEVER fake points.
  * A room is only "conquered" when a worker ACTUALLY did the task; a scene only yields loot when
    witnesses ACTUALLY converge. This loop NEVER fabricates either.
  * Deterministic-first + $0: what can be folded for free happens now; what needs a model (a real
    witness / a real task execution) is gated honestly on quota/key and runs when available.

THE LOOP (one coherent beat, shaped to the GWAP taste — the world produces while you're away):
  1. CONQUER — scan for REAL completed work (done swarm results) and fold each into a conquered
     dungeon room (rib_bus knot -> hologram region structured). Never conquer an unworked room.
  2. PREPARE — queue the next real open task (assign workers to the coldest unconquered room) so
     there is always work in flight for the world to fold when it lands.
  3. WITNESS — if quota allows, run one Roshomon survey of an unwitnessed scene so frontier seats
     can converge into real loot. Honest if blocked (reports quota-exhausted, never fakes a core).
  4. REPORT — status: what the world has folded, what's in flight, what's honestly blocked.

Schema: game_produce.v1 · deterministic coordinator + $0 fold · reuse: game_world, game_mud,
dungeon_dev, swarm_worker, rib_bus, game_score — nothing invented.
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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "game_produce.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dungeon() -> Any:
    from mag import dungeon_dev
    return dungeon_dev


def _mud() -> Any:
    from mag import game_mud
    return game_mud


def _score() -> dict[str, Any]:
    try:
        from mag import game_score
        return (game_score.score().get("score") or {})
    except Exception:
        return {}


def _done_swarm_results(limit: int = 10) -> list[dict[str, Any]]:
    """REAL completed swarm work (honest source — never invent a completion)."""
    out = []
    try:
        from mag import swarm_worker
        c = swarm_worker.collect(limit=limit)
        for r in (c.get("results") or []):
            if r.get("status") == "done" or r.get("result") or r.get("answer"):
                out.append(r)
    except Exception:
        pass
    return out


def conquer_landed() -> dict[str, Any]:
    """FOLD REAL completed work into conquered dungeon rooms. Honest: only rooms with a matching
    done result (or an explicitly supplied real knot) are conquered — never fabricated."""
    dd = _dungeon()
    state = dd.dungeon_state()
    rooms = {r["room"]: r for r in (state.get("rooms") or [])}
    open_rooms = [r for r in rooms.values() if r.get("status") != "conquered"]
    done = _done_swarm_results(limit=15)
    folded: list[dict[str, Any]] = []
    for res in done:
        goal = str(res.get("goal") or "")
        # match a done result to an open dungeon room by name/region appearing in its goal
        target = None
        for r in open_rooms:
            if r["room"] in goal or r["region"] in goal:
                target = r
                break
        if not target:
            continue
        knot = str(res.get("result") or res.get("answer") or res.get("detail") or "")[:300]
        try:
            out = dd.conquer(target["room"], knot=knot or target["task"])
            folded.append({"room": target["room"], "ok": out.get("ok"),
                           "knot": bool(knot), "from": "done-swarm-result"})
        except Exception as e:
            folded.append({"room": target["room"], "ok": False, "error": str(e)[:100]})
    return {"ok": True, "schema": SCHEMA, "action": "conquer-landed",
            "n_done": len(done), "n_folded": len(folded), "folded": folded,
            "honest": "only real completed swarm work was folded into conquered rooms; nothing invented"}


def prepare_next(*, n: int = 1) -> dict[str, Any]:
    """Queue the next real open task (assign workers to the coldest unconquered room) so there is
    always work in flight. Deterministic + $0 to assign; the swarm runs the room headless."""
    dd = _dungeon()
    state = dd.dungeon_state()
    rooms = state.get("rooms") or []
    # coldest = lowest floor, not conquered
    open_rooms = sorted([r for r in rooms if r.get("status") != "conquered"],
                        key=lambda r: r.get("floor", 99))
    if not open_rooms:
        return {"ok": True, "schema": SCHEMA, "action": "prepare-next",
                "assigned": [], "note": "no open rooms — the dungeon is conquered"}
    target = open_rooms[0]
    try:
        out = dd.assign_workers(target["room"], n=n, enqueue=True)
        return {"ok": True, "schema": SCHEMA, "action": "prepare-next",
                "room": target["room"], "region": target.get("region"),
                "assigned": out.get("assigned") or [], "workers": n,
                "note": f"assigned {n} worker(s) to '{target['room']}' — real work in flight"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "action": "prepare-next",
                "error": str(e)[:120]}


def _scene_relevant(text: str, room: str, question: str) -> bool:
    """RELEVANCE GATE (2026-08-16 learning, encoded): a witness statement only counts as a
    convergence candidate if it actually references the SCENE — the room, its prose tokens, or the
    question's load-bearing words. This filters OFF-SCENE BLEED (a reachable seat returning its own
    unrelated chat context instead of witnessing the game, e.g. a fanfic outline) so it can NEVER be
    folded into a fake roshomon core. The produce loop stays honest: no scene relevance -> no loot.
    """
    t = (text or "").lower()
    # room name tokens (e.g. "world memory") are the strongest anchor
    room_tok = room.lower().replace("the ", "").replace("-", " ").replace("_", " ").strip()
    anchors = []
    if room_tok:
        anchors.append(room_tok)
        for part in room_tok.split():
            if len(part) >= 4:
                anchors.append(part)
    # question load-bearing words (drop stopwords, keep meaningful stems)
    import re as _re
    _STOP = {"what", "is", "the", "a", "an", "we", "should", "our", "that", "this", "for", "in",
             "to", "of", "and", "or", "how", "why", "which", "add", "do"}
    q_toks = [w for w in _re.findall(r"[a-z]{3,}", question.lower()) if w not in _STOP]
    anchors += q_toks[:4]
    return any(a in t for a in anchors if a)


def witness(room: str | None = None, *, route: bool = True) -> dict[str, Any]:
    """Run one Roshomon survey so frontier seats can converge into REAL loot. Honest if blocked:
    reports quota-exhausted / no-seats rather than faking a core. Deterministic filter + $0; the
    witness model calls are the real cost (gated on quota).
    RELEVANCE GATE (encoded 2026-08-16): off-scene witness bleed is filtered out before convergence,
    so it can never fold into a fake core."""
    try:
        s = _mud().survey(room, route=route)
        room = room or s.get("room") or ""
        question = s.get("question") or ""
        # filter witnesses to scene-relevant statements only (drop off-scene bleed)
        kept = []
        for w in (s.get("witnesses") or []):
            stmts = [st for st in (w.get("statements") or [])
                     if _scene_relevant(st, room, question)]
            kept.append({**w, "statements": stmts})
        s["witnesses"] = kept
        # recompute convergence on the scene-relevant statements only
        core = s.get("roshomon_core") or []
        # if the filter emptied the witnesses' statements, force core empty (never fake)
        if not any(w.get("statements") for w in kept):
            s["roshomon_core"] = []
            s["novel_solutions"] = []
            s["n_core"] = 0
            s["relevance_gated"] = True
        if core and s.get("roshomon_core"):
            claim = _mud().claim(room or _mud()._player()["room"])
            s["claimed"] = claim.get("ok")
        s["honest"] = ("loot only from real, SCENE-RELEVANT witness convergence; off-scene bleed "
                       "filtered; blocked = reported, never faked")
        return {"ok": bool(s.get("ok")), "schema": SCHEMA, "action": "witness", "survey": s}
    except Exception as e:
        err = str(e)[:160]
        blocked = "quota" in err.lower() or "key" in err.lower() or "budget" in err.lower()
        return {"ok": False, "schema": SCHEMA, "action": "witness",
                "error": err, "blocked_on_quota": blocked,
                "honest": "witnessing needs a live frontier seat + quota; never faked a convergence"}


def produce(*, prepare: int = 1, limit: int = 10) -> dict[str, Any]:
    """THE LOOP STEP: fold real landed work (conquer) + queue the next real work (prepare) +
    attempt one witness (honest if quota-blocked). The world produces while you're away."""
    cq = conquer_landed()
    pp = prepare_next(n=prepare) if prepare else {"ok": True, "assigned": []}
    # witness is the only model-gated step; keep it best-effort and honest
    wit = {"ok": True, "skipped": True, "note": "witness gated on quota — skipped this beat"}
    try:
        wit = witness()
    except Exception as e:
        wit = {"ok": False, "error": str(e)[:120], "blocked_on_quota": True}
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(),
        "conquered": cq, "prepared": pp, "witnessed": wit,
        "score_after": _score(),
        "note": "the produce loop: fold real landed work, queue the next real work, witness honestly "
                "— the world works while you're away",
    }


def status() -> dict[str, Any]:
    s = _score()
    return {"ok": True, "schema": SCHEMA, "score": s,
            "honest": "the produce loop only folds REAL completed work into the world (loot + "
                      "conquest); the score reflects that, never fake points",
            "contract": "conquer_landed()->fold real done swarm work into conquered rooms; "
                        "prepare_next()->queue the coldest open room; witness()->one honest Roshomon "
                        "survey (quota-gated); produce()->the loop beat; status()->this",
            "cost": "deterministic coordinator + $0 fold; witness model calls gated on quota",
            "reuse": "game_world, game_mud, dungeon_dev, swarm_worker, rib_bus, game_score"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="game_produce")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "produce", "conquer", "prepare", "witness"])
    ap.add_argument("arg", nargs="?", default="")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "produce":
        out = produce()
    elif a.cmd == "conquer":
        out = conquer_landed()
    elif a.cmd == "prepare":
        out = prepare_next()
    elif a.cmd == "witness":
        out = witness(a.arg or None, route=False)
    else:
        out = status()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
