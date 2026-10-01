"""Pro library — the aimbot for AI (white-hat reality exploits).

A transferable library of winning moves (tesuji) applied like an aimbot:
  SENSE the live state → MATCH the winning signature → INJECT the move at the
  seam → LEARN the outcome.

Folds into existing behavioral systems:
  - mag/tesuji_shell       capture every emergent win (add/fire)
  - mag/skill_ledger       record each matched move + outcome (case law)
  - mag/operator_inbox     the injection channel (steer via commit_guidance)
  - mag/operator_inbox      log_behavioral_event for every aim (pro_fire/pro_learn)
  - mag/behavioral_synth    daily leaf can surface the top pro moves

Move kinds (maps_to prefix, mirroring tesuji_shell):
  steer: guidance text injected via operator_inbox at the checkpoint
  skill: a transferable skill to surface for the context pack / job
  spec:  a designation/constraint for the executor
  tip:   a tip for decision_framework.surface_tips

CLI:  main.py pro-library add|aim|match|fire|learn|stats|seed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

LIB_PATH = ROOT / "memory" / "improve" / "pro_library.json"
KINDS = ("steer", "skill", "spec", "tip")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not LIB_PATH.is_file():
        return {"schema": "pro_library.v1", "moves": []}
    try:
        data = json.loads(LIB_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"schema": "pro_library.v1", "moves": []}
    except Exception:
        return {"schema": "pro_library.v1", "moves": []}


def _save(data: dict[str, Any]) -> None:
    LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _signature_terms(signature: str | list[str]) -> list[str]:
    terms: list[str] = []
    for s in ([signature] if isinstance(signature, str) else signature):
        terms.extend(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) >= 3)
    return list(dict.fromkeys(terms))


# Terms too generic to discriminate — a signature dominated by these matches
# everything (the "fires on anything" over-fire risk the eval caught).
_SIGNATURE_STOP = {
    "agent", "tool", "file", "model", "task", "system", "code", "ai", "llm",
    "the", "and", "but", "with", "from", "this", "that", "work", "thing",
    "make", "need", "want", "use", "get", "would", "also", "like", "can",
    "state", "result", "output", "goal", "running", "agent",
}


def _generic_ratio(terms: list[str]) -> float:
    if not terms:
        return 1.0
    return sum(1 for t in terms if t in _SIGNATURE_STOP) / len(terms)


# ---------------------------------------------------------------- capture ----
def add_move(
    signature: str | list[str],
    kind: str,
    move: str,
    *,
    effect: str = "",
    maps_to: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Add a pro move (a transferable win) and capture it as a tesuji shell."""
    kind = (kind or "steer").strip().lower()
    if kind not in KINDS:
        return {"ok": False, "error": f"kind must be one of {KINDS}"}
    move_text = (move or "").strip()
    if not move_text:
        return {"ok": False, "error": "empty move"}
    terms = _signature_terms(signature)
    if len(terms) < 2:
        return {"ok": False, "error": "signature too thin — need >= 2 discriminative terms"}
    if _generic_ratio(terms) >= 0.5:
        return {"ok": False, "error": "signature too generic (stopword-heavy) — would over-fire; use specific state terms"}
    data = _load()
    rec = {
        "id": f"pro-{uuid.uuid4().hex[:10]}",
        "signature": terms,
        "kind": kind,
        "move": move_text[:800],
        "effect": (effect or "")[:400],
        "maps_to": (maps_to or "")[:200] or f"{kind}:{move_text[:40]}",
        "tags": [str(t)[:40] for t in (tags or [])[:8]],
        "wins": 0,
        "tries": 0,
        "created": _now(),
        "last_used": None,
    }
    data.setdefault("moves", []).append(rec)
    _save(data)
    try:
        from mag.tesuji_shell import log_tesuji_shell

        log_tesuji_shell(
            what=f"[pro:{kind}] {move_text[:200]}",
            surprise=effect or f"signature: {signature}",
            maps_to=rec["maps_to"],
            source="pro-library",
            tags=tags or [kind],
        )
    except Exception:
        pass
    return {"ok": True, "move": rec, "progress": stats()}


# ------------------------------------------------------------------- sense ----
def sense(state: dict[str, Any]) -> str:
    """Normalize a live state snapshot into a signature-matching text."""
    parts: list[str] = []
    for k in ("goal", "text", "detail", "error", "last_tool", "phase", "summary"):
        v = str(state.get(k) or "")
        if v:
            parts.append(v)
    for t in state.get("last_tools") or []:
        parts.append(str(t))
    return " ".join(parts).lower()


def match(state: dict[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    """Return the best pro moves for the current state (signature overlap)."""
    text = sense(state)
    data = _load()
    scored: list[dict[str, Any]] = []
    for m in data.get("moves") or []:
        sig = m.get("signature") or []
        if not sig:
            continue
        hits = sum(1 for t in sig if t and t in text)
        if hits <= 0:
            continue
        score = hits / len(sig)
        scored.append({"score": round(score, 2), "hits": hits, "move": m})
    scored.sort(key=lambda x: (x["score"], x["move"].get("wins", 0)), reverse=True)
    return scored[:limit]


# ------------------------------------------------------------------- inject ----
def fire(move: dict[str, Any], *, goal: str = "", session_id: str | None = None) -> dict[str, Any]:
    """Inject the move at the seam (steer → operator_inbox; others → event + payload)."""
    kind = move.get("kind") or "steer"
    move_text = str(move.get("move") or "")
    out: dict[str, Any] = {"ok": True, "kind": kind, "move_id": move.get("id"), "text": move_text[:200]}
    if kind == "steer":
        try:
            from mag.operator_inbox import commit_guidance

            r = commit_guidance(move_text, source="pro-library")
            out["injected"] = bool(r.get("ok"))
            out["channel"] = "operator_inbox"
        except Exception as e:
            out["injected"] = False
            out["error"] = str(e)[:120]
    elif kind == "skill":
        out["action"] = "add_skill_to_pack"
    elif kind == "spec":
        out["action"] = "designate_executor"
    elif kind == "tip":
        out["action"] = "surface_tip"
    _mark_used(move.get("id"))
    try:
        from mag.operator_inbox import log_behavioral_event

        log_behavioral_event(
            kind="pro_fire",
            detail=f"[{kind}] {move_text[:120]}",
            tool=kind,
            phase="pro_aim",
            session_id=session_id,
            provider="pro-library",
        )
    except Exception:
        pass
    return out


def _mark_used(move_id: str | None) -> None:
    if not move_id:
        return
    data = _load()
    for m in data.get("moves") or []:
        if m.get("id") == move_id:
            # learn() owns tries/wins — fire only records usage, else a
            # fire→learn cycle double-counts tries and caps win_rate at 50%.
            m["last_used"] = _now()
            break
    _save(data)


# ------------------------------------------------------------------- learn ----
def learn(move_id: str, *, outcome: str, detail: str = "", goal: str = "") -> dict[str, Any]:
    """Record the outcome of a fired move (win/loss) into the case-law stack."""
    data = _load()
    target = None
    for m in data.get("moves") or []:
        if m.get("id") == move_id:
            target = m
            break
    if target is None:
        return {"ok": False, "error": "no such move"}
    win = (outcome or "").strip().lower() in ("ok", "win", "good", "1", "true")
    if win:
        target["wins"] = int(target.get("wins") or 0) + 1
    target["tries"] = int(target.get("tries") or 0) + 1
    _save(data)
    try:
        from mag.skill_ledger import record_decision

        record_decision(
            goal=goal or f"pro-move {move_id}",
            task_shape=f"pro:{target.get('kind')}",
            provider="pro-library",
            model=target.get("kind"),
            reasoning_level="none",
            seat="pro-library",
            outcome=outcome,
            detail=detail or str(target.get("effect") or "")[:200],
            source="pro_learn",
        )
    except Exception:
        pass
    try:
        from mag.operator_inbox import log_behavioral_event

        log_behavioral_event(
            kind="pro_learn",
            detail=f"{move_id} -> {outcome} ({target.get('move', '')[:80]})",
            tool=target.get("kind"),
            phase="pro_learn",
            provider="pro-library",
        )
    except Exception:
        pass
    return {"ok": True, "move": target, "win": win}


# ------------------------------------------------------------------- aim ----
def aim_once(
    state: dict[str, Any],
    *,
    goal: str = "",
    session_id: str | None = None,
    limit: int = 1,
    fire_moves: bool = True,
) -> dict[str, Any]:
    """The whole loop: SENSE → MATCH → INJECT (→ caller learns later)."""
    text = sense(state)
    matches = match(state, limit=limit)
    fired = []
    for m in matches:
        f = fire(m["move"], goal=goal, session_id=session_id) if fire_moves else {"ok": True, "preview": True, "move": m["move"]["id"]}
        fired.append({**f, "score": m["score"]})
    return {
        "ok": True,
        "schema": "pro_aim.v1",
        "state_text": text[:300],
        "matches": [{"id": x["move"]["id"], "score": x["score"], "kind": x["move"]["kind"], "text": x["move"]["move"][:120]} for x in matches],
        "fired": fired,
    }


def stats() -> dict[str, Any]:
    data = _load()
    moves = data.get("moves") or []
    by_kind: dict[str, int] = {}
    wins = tries = 0
    for m in moves:
        by_kind[m.get("kind")] = by_kind.get(m.get("kind"), 0) + 1
        wins += int(m.get("wins") or 0)
        tries += int(m.get("tries") or 0)
    return {
        "ok": True,
        "schema": "pro_library.stats.v1",
        "moves": len(moves),
        "by_kind": by_kind,
        "total_tries": tries,
        "total_wins": wins,
        "win_rate": round(100 * wins / tries, 1) if tries else None,
        "path": str(LIB_PATH),
    }


def seed_default_moves() -> dict[str, Any]:
    """Seed the library with the transferable wins discovered today."""
    seeds = [
        ("claimed edits but no file change, tool result empty, done with no diff",
         "steer",
         "Verify via OUR systems before declaring done (get_errors + read the actual file bytes on disk). Trust bytes, not reports. Do NOT use git diff.",
         "catches false-success hallucination before escalation",
         "steer:false-success-verify"),
        ("about to edit a file, base may have changed, spec frozen",
         "spec",
         "Re-check the frozen base fingerprint (spec_gate) before applying; if drift, re-freeze or escalate.",
         "kills wrong-offset applies",
         "spec:wrong-offset-gate"),
        ("task vague, executor likely to fake, need constraint",
         "spec",
         "Emit a penny-spec (deepseek-v4-flash) from the frozen state first, then hand the designation to the cheap executor.",
         "designations make dwarves/7B execute instead of fake",
         "spec:penny-designation"),
        ("agent looping, repeating tool, about to burn tokens",
         "steer",
         "Escalate to the next smarter tier; stop local token bleed (escalate_on_loop).",
         "stops degenerate loops early",
         "steer:loop-escalate"),
        ("need to steer mid-round, decision point reached",
         "tip",
         "Drop the guidance at the checkpoint via operator_inbox — the seat drains it at the seam.",
         "seam placement = the tesuji timing",
         "steer:seam-placement"),
    ]
    added = 0
    for sig, kind, move, effect, maps_to in seeds:
        r = add_move(sig, kind, move, effect=effect, maps_to=maps_to, tags=["seed"])
        if r.get("ok"):
            added += 1
    return {"ok": True, "seeded": added, "stats": stats()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pro-library")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    sub.add_parser("seed")
    sub.add_parser("list")
    p_add = sub.add_parser("add")
    p_add.add_argument("--signature", required=True)
    p_add.add_argument("--kind", default="steer", choices=KINDS)
    p_add.add_argument("--move", required=True)
    p_add.add_argument("--effect", default="")
    p_match = sub.add_parser("match")
    p_match.add_argument("--text", required=True)
    p_aim = sub.add_parser("aim")
    p_aim.add_argument("--text", required=True)
    p_aim.add_argument("--no-fire", action="store_true")
    p_fire = sub.add_parser("fire")
    p_fire.add_argument("id")
    p_learn = sub.add_parser("learn")
    p_learn.add_argument("id")
    p_learn.add_argument("--outcome", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif args.cmd == "seed":
        print(json.dumps(seed_default_moves(), indent=2))
    elif args.cmd == "list":
        print(json.dumps([{"id": m["id"], "kind": m["kind"], "sig": m["signature"][:6], "move": m["move"][:60], "wins": m["wins"], "tries": m["tries"]} for m in (_load().get("moves") or [])], indent=2))
    elif args.cmd == "add":
        print(json.dumps(add_move(args.signature, args.kind, args.move, effect=args.effect), indent=2, default=str))
    elif args.cmd == "match":
        print(json.dumps(match({"text": args.text}), indent=2, default=str))
    elif args.cmd == "aim":
        print(json.dumps(aim_once({"text": args.text}, fire_moves=not args.no_fire), indent=2, default=str))
    elif args.cmd == "fire":
        data = _load()
        m = next((x for x in data.get("moves") or [] if x["id"] == args.id), None)
        print(json.dumps(fire(m) if m else {"ok": False, "error": "no such move"}, indent=2, default=str))
    elif args.cmd == "learn":
        print(json.dumps(learn(args.id, outcome=args.outcome), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
