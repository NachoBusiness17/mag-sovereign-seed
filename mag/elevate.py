"""Elevate — shape the RIGHT-SIZED ask for the strongest model, then capture it.

Lesson (2026-08-09, operator): when a task needs more reach than the current tier,
I used to stall or hand-roll a giant prompt instead of doing one deliberate ask and
capturing it. This module encodes the deliberate-ask protocol (context-tax research):

    FROZEN PREFIX (byte-identical, cache-shared) + SMALL PRECISE ASK + OUTPUT CONTRACT
    + ACCEPTANCE + QUANTIZATION TARGET.

The right size = token budget on the PREFIX (cache hit), NOT on the ask (miss tax).
A tight 10-20 line ask beats a 200-line prompt every time.

Capture: every shaped ask + its outcome is folded to pro_library (a transferable
move) + skill_ledger (case law), so the *style* of the request becomes reusable and
the next launch auto-proposes the right-sized ask instead of guessing.

CLI: python -m mag.elevate <goal> [--model grok-4.5] [--dry] [--capture]
REST: GET/POST /api/v1/elevate
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Signals that a task probably deserves a stronger model (judgment / high-stakes).
_ELEVATE_SIGNALS = (
    "review", "audit", "assess", "decide", "recommend", "design", "architect",
    "opspec", "security", "legal", "contract", "partner", "client", "publish",
    "deploy", "public", "risk", "strategy", "evaluate", "synthesize", "judgment",
)


def should_elevate(goal: str) -> bool:
    g = goal.lower()
    return any(s in g for s in _ELEVATE_SIGNALS)


def _frozen_prefix(goal: str) -> str:
    """Best-effort frozen prefix from the session maze (byte-stable, cache-shared)."""
    try:
        from mag.session_maze import assemble as maze_assemble
        m = maze_assemble()
        if isinstance(m, dict) and m.get("maze"):
            return f"=== FROZEN STATE (session maze) ===\n{m['maze']}"
    except Exception:
        pass
    return "=== FROZEN STATE (minimal) ===\nSovereign agent system. Evidence-first, tri-state claims, OPSEC G1-G8, human final call."


def shape_ask(goal: str, *, model: str = "grok-4.5", max_words: int = 250,
              output_contract: str | None = None) -> dict:
    """Build the right-sized ask: frozen prefix + small precise ask + contract."""
    contract = output_contract or (
        f"Return <= {max_words} words. Shape: 1) direct answer 2) 3 options + a "
        "recommended pick with reasoning 3) explicit uncertainty. No filler, no "
        "re-pasting the prefix. Do not invent facts; mark assumptions."
    )
    ask = (
        f"Given ONLY the frozen state above, answer this one question:\n"
        f"  {goal}\n"
        f"Constraints: stay inside the frozen state; do not request private data; "
        f"human makes the final call on anything public."
    )
    prefix = _frozen_prefix(goal)
    full = f"{prefix}\n\n{ask}\n\nOUTPUT CONTRACT:\n{contract}"
    return {
        "schema": "elevate_ask.v1",
        "model": model,
        "goal": goal,
        "frozen_prefix_chars": len(prefix),
        "ask_chars": len(ask),
        "contract": contract,
        "estimated_tokens": int(len(full) / 4),
        "ask": ask,
        "full_prompt": full,
    }


def capture(ask: dict, outcome: str, *, model: str = "grok-4.5") -> dict:
    """Fold the shaped ask + outcome to pro_library (move) + skill_ledger (case law)."""
    rec = {"pro_library": None, "skill_ledger": None}
    try:
        from mag.pro_library import add_move
        sig = _slug(ask.get("goal", ""))
        rec["pro_library"] = add_move(
            signature=f"elevate,{sig},ask,outcome:{outcome}",
            kind="steer",
            move=(
                f"Elevate with a deliberate ask: frozen prefix (cache-shared) + "
                f"tight ask (~{ask.get('ask_chars', 0)} chars) + output contract "
                f"(<=N words, shape, uncertainty). Model={model}. "
                f"Outcome={outcome}. Do not stall; fire one shaped ask."
            ),
        )
    except Exception as e:
        rec["pro_library"] = {"ok": False, "error": str(e)[:200]}
    try:
        from mag.skill_ledger import record_decision
        rec["skill_ledger"] = record_decision(
            goal=f"elevate:{_slug(ask.get('goal', ''))[:60]}",
            outcome=outcome,
        )
    except Exception as e:
        rec["skill_ledger"] = {"ok": False, "error": str(e)[:200]}
    return rec


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def elevate(goal: str, *, model: str = "grok-4.5", dry: bool = True,
            capture_result: bool = True) -> dict:
    """Shape the ask; dry returns the shaped ask. Always folds to case law."""
    shaped = shape_ask(goal, model=model)
    # Where the ask would be dispatched (queue/grok batch) — dry just reports.
    dispatch = {
        "dry": dry,
        "route": "queue:grok-batch" if not dry else "none (dry)",
        "note": "fire via mag.orchestrator.spawn_task(tag='grok-elevate') when live",
    }
    rec = {}
    if capture_result:
        rec = capture(shaped, "shaped", model=model)
    return {"ok": True, "shaped": shaped, "dispatch": dispatch, "captured": rec}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m mag.elevate <goal> [--model grok-4.5] [--live]")
        return 1
    goal = args[0]
    model = "grok-4.5"
    if "--model" in args:
        i = args.index("--model")
        if i + 1 < len(args):
            model = args[i + 1]
    dry = "--live" not in args
    print(json.dumps(elevate(goal, model=model, dry=dry), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
