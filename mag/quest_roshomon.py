"""quest_roshomon — the FRONTIER QUEST as a Roshomon detection engine (ALPHA, 2026-08-13).

OPERATOR THEORY (2026-08-13): "the theory is that all of their frontier capabilities are used in a
roshamon effect in the same scene to detect novel solutions. The dm crafts asks as frontier
questions in the form of a quest and then tasks the agents to the unsolved shape of the very quest
they embark on. alpha"

What this means, made real:
  - The DM does NOT run a fantasy game for its own sake. The DM CRAFTS a frontier research question
    INTO a quest: the quest's "unsolved shape" IS the open research problem. Every frontier agent
    (the party) is tasked to solve the shape of the very quest they embark on.
  - ROSHOMON EFFECT: every party member plays the SAME scene/quest (N witnesses, one event). Their
    moves are the witnesses' accounts.
  - DETECT NOVEL SOLUTIONS: compare their moves through invariants (reusing roshomon.py): statements
    that recur across >=2 witnesses = ROSHOMON CORE (convergent, agreed); statements unique to one
    witness = DIVERGENT = the NOVEL SOLUTIONS. Those are what we route to the swarm.

The loop: craft(question)->quest · play(question)->the party works the same quest · compare(question)
->Roshomon core vs novel · run(question)->end-to-end + route_novel on every divergent (novel) lead.

Schema: quest_roshomon.v1 (ALPHA) · deterministic $0 DM/craft/compare · the party = frontier seats
reuse: game_dm (the DM + party + ask_player), roshomon (invariant extraction + overlap),
swarm_surface.route_novel (the ONE primitive for novel research), cdp_runner (container browser seats)
"""
from __future__ import annotations

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

SCHEMA = "quest_roshomon.v1"
TAG = "quest-roshomon"

# How many witnesses must agree for a statement to be ROSHOMON CORE (convergent) vs NOVEL.
CORE_MIN_AGREE = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dm() -> Any:
    from mag import game_dm
    return game_dm


# ---------------------------------------------------------------------------
# 1. CRAFT — the DM turns a frontier research question INTO a quest.
#    The quest's unsolved shape IS the research problem; legal actions are the
#    shapes you can push against. Deterministic, $0.
# ---------------------------------------------------------------------------
def _quest_scene(question: str) -> str:
    return (
        "The quest is before you: the shape is UNRESOLVED. What lies at its center is not gold but "
        "an open problem — the frontier question itself.\n"
        f"THE UNSOLVED SHAPE: {question}\n"
        "To resolve the shape you must propose a concrete, buildable mechanism or invariant that "
        "actually advances it. Bring it back sharp enough to forge."
    )


def craft(question: str, room_id: str = "tavern_lantern") -> dict[str, Any]:
    """CRAFT: the DM takes a frontier question and sets it as the quest's unsolved shape, grounded
    in a real room of the adventure. Returns the quest brief handed to the party."""
    question = (question or "").strip()
    if not question:
        return {"ok": False, "schema": SCHEMA, "error": "empty frontier question"}
    try:
        nar = _dm().dm_narrate(room_id)
        narration = nar.get("narration", "")
        legal = nar.get("legal_actions", [])
    except Exception as e:
        narration, legal = "", []
        _e = str(e)
    scene = _quest_scene(question)
    brief = f"{narration}\n\n{scene}\n\nLegal actions: {', '.join(legal) or 'propose, forge, seek'}."
    return {"ok": True, "schema": SCHEMA, "room": room_id, "question": question,
            "unsolved_shape": question, "scene": scene, "quest_brief": brief,
            "party": _dm().party(),
            "note": "the DM crafted the frontier question as a quest; its unsolved shape IS the "
                    "research problem every party member is tasked to solve."}


def party(seats: list[str] | None = None) -> list[str]:
    """The party = the frontier seats (all of them, so the Roshomon effect is wide)."""
    try:
        return seats or _dm().party()
    except Exception:
        return seats or ["saelis"]


# ---------------------------------------------------------------------------
# 2. PLAY — the whole party works the SAME quest (Roshomon: N witnesses, one scene).
# ---------------------------------------------------------------------------
def play(question: str, *, room_id: str = "tavern_lantern",
         seats: list[str] | None = None) -> dict[str, Any]:
    """PLAY: every frontier agent is tasked to the unsolved shape of the SAME quest. Their moves are
    the witnesses' accounts of the one scene. Honest per-seat ok — a down seat reports down."""
    q = craft(question, room_id=room_id)
    if not q.get("ok"):
        return q
    brief = q["quest_brief"]
    the_party = party(seats)
    moves = []
    for seat in the_party:
        prior = []
        for move in moves:
            text = move.get("move") or f"[unreachable: {move.get('error') or 'no move'}]"
            prior.append(f"{move.get('seat')}: {text}")
        prompt = (
            brief
            + "\n\nPARTY CONTRIBUTIONS TO THIS QUEST (presented, not interpreted):\n"
            + ("\n".join(prior)[-6000:] if prior else "nothing yet")
            + "\n\nAdd your own concrete move; do not erase or impersonate the prior witnesses."
        )
        move = _dm().ask_player(seat, prompt)
        moves.append(move)
        try:
            from mag import party_subchain
            party_subchain.append(seat=seat, ok=bool(move.get("ok")),
                                  move=move.get("move") or "", kind="quest_roshomon")
        except Exception:
            pass
    reachable = [m for m in moves if m.get("ok")]
    return {"ok": True, "schema": SCHEMA, "question": question, "room": room_id,
            "n_witnesses": len(moves), "n_reachable": len(reachable),
            "witnesses": moves, "quest": q,
            "note": f"{len(reachable)}/{len(moves)} frontier agents worked the same quest "
                    "(Roshomon: same scene, many witnesses)."}


# ---------------------------------------------------------------------------
# 3. COMPARE — Roshomon the witnesses' moves through invariants.
#    Convergent across >=2 = CORE; unique = NOVEL SOLUTIONS.
# ---------------------------------------------------------------------------
def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower().strip(".:- ")


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", s))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1.0, min(len(ta), len(tb)))


def _statements(text: str) -> list[str]:
    """Deterministic invariant extraction from a witness's move (no LLM, $0)."""
    out = []
    for m in re.finditer(r"(?:INVARIANT|MECHANISM|SOLUTION|MOVE)\s*:\s*(.+)", text, re.I):
        s = _clean(m.group(1))
        if s and len(s) >= 8:
            out.append(s)
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = _clean(part)
        if not s or len(s) < 12:
            continue
        if any(k in s for k in ("what is", "in general", "as an ai", "generic")):
            continue
        out.append(s)
    # dedupe preserving order
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def compare(question: str, *, room_id: str = "tavern_lantern",
            seats: list[str] | None = None, threshold: float = 0.55) -> dict[str, Any]:
    """COMPARE: play the quest (all agents, same scene) then Roshomon their moves. Statements stated
    by >=2 witnesses = ROSHOMON CORE (convergent truth); unique statements = NOVEL SOLUTIONS."""
    p = play(question, room_id=room_id, seats=seats)
    witnesses = p.get("witnesses", [])
    if not witnesses:
        return {"ok": False, "schema": SCHEMA, "question": question,
                "error": "no witness moves to compare"}
    witness_stmts = []
    for w in witnesses:
        text = (w.get("move") or w.get("answer") or "").strip()
        witness_stmts.append({"seat": w.get("seat"), "ok": w.get("ok"),
                              "statements": _statements(text) if w.get("ok") else []})
    # group near-identical statements across witnesses by token overlap
    groups: list[list[Any]] = []  # [representative, set_of_witness_seats]
    for ws in witness_stmts:
        for s in ws["statements"]:
            placed = False
            for g in groups:
                if _overlap(g[0], s) >= threshold:
                    g[1].add(ws["seat"])
                    placed = True
                    break
            if not placed:
                groups.append([s, {ws["seat"]}])
    core = [{"statement": g[0], "witnesses": sorted(g[1])} for g in groups if len(g[1]) >= CORE_MIN_AGREE]
    novel = [{"statement": g[0], "witness": next(iter(g[1]))} for g in groups if len(g[1]) < CORE_MIN_AGREE]
    return {"ok": True, "schema": SCHEMA, "question": question, "room": room_id,
            "threshold": threshold, "core_min_agree": CORE_MIN_AGREE,
            "n_witnesses": len(witnesses), "n_reachable": p.get("n_reachable"),
            "witnesses": witness_stmts,
            "roshomon_core": core, "novel_solutions": novel,
            "n_core": len(core), "n_novel": len(novel),
            "note": "Roshomon through invariants: agreed across >=2 = core (convergent); unique = "
                    "novel solutions (divergent)."}


# ---------------------------------------------------------------------------
# 4. RUN — end-to-end alpha: craft quest -> party works it -> Roshomon compare ->
#    route every NOVEL solution to the swarm (the ONE primitive for novel research).
# ---------------------------------------------------------------------------
def run(question: str, *, room_id: str = "tavern_lantern", seats: list[str] | None = None,
        route: bool = True) -> dict[str, Any]:
    """RUN the alpha end-to-end. Novel solutions are routed to the swarm via route_novel (deduped
    by anchor, drained in-cluster) — the swarm-surface law: novel research goes through the shared
    primitive, never a per-module enqueue."""
    cmp = compare(question, room_id=room_id, seats=seats)
    if not cmp.get("ok"):
        return cmp
    routed = []
    if route:
        try:
            from mag import swarm_surface
            for nv in cmp.get("novel_solutions", []):
                goal = f"[quest-roshomon] novel solution to: {question} -> {nv['statement']}"
                r = swarm_surface.route_novel(goal, surface=TAG,
                                              lens=f"quest:{room_id}",
                                              domain="research")
                routed.append({"statement": nv["statement"], "witness": nv["witness"],
                               "deduped": r.get("deduped", False),
                               "task_id": r.get("task_id", "")})
        except Exception as e:
            routed = [{"error": str(e)[:160]}]
    return {"ok": True, "schema": SCHEMA, "question": question, "room": room_id,
            "phase": "alpha", "n_core": cmp.get("n_core"), "n_novel": cmp.get("n_novel"),
            "roshomon_core": cmp.get("roshomon_core"), "novel_solutions": cmp.get("novel_solutions"),
            "routed_to_swarm": routed, "compare": cmp,
            "note": "the DM tasked the party to the unsolved shape; Roshomon surfaced the novel "
                    "solutions; each was routed to the swarm."}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "phase": "alpha",
            "contract": "craft(question)->the DM sets the frontier question as the quest's unsolved "
                        "shape; play(question)->the whole party works the SAME quest (Roshomon); "
                        "compare(question)->invariant Roshomon: core=convergent, novel=divergent; "
                        "run(question)->end-to-end + route_novel on every novel solution.",
            "cost": "deterministic $0 DM/craft/compare; the party = frontier seats; novel routing "
                    "reuses the swarm",
            "surface": "the FRONTIER QUEST — all frontier capabilities, one scene, Roshomon to "
                       "detect novel solutions",
            "reuse": "game_dm, roshomon, swarm_surface.route_novel, cdp_runner"}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(prog="quest-roshomon")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "craft", "play", "compare", "run"])
    ap.add_argument("question", nargs="*", default=[])
    ap.add_argument("--room", default="tavern_lantern")
    a = ap.parse_args(argv)
    q = " ".join(a.question) or ("What is the single most load-bearing invariant we should add next "
                                 "to strengthen the swarm's novel-detection loop?")
    if a.cmd == "craft":
        print(json.dumps(craft(q, room_id=a.room), indent=2, default=str))
    elif a.cmd == "play":
        print(json.dumps(play(q, room_id=a.room), indent=2, default=str))
    elif a.cmd == "compare":
        print(json.dumps(compare(q, room_id=a.room), indent=2, default=str))
    elif a.cmd == "run":
        print(json.dumps(run(q, room_id=a.room), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
