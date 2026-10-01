"""no_win — the Kobayashi Maru primitive (operator, 2026-08-13: "showing up every day and refusing
to play the no win game. wrong tools."). Steal from our own corpus (tesuji_shells.jsonl:
kobayashi-maru-tesla-q): impossible constraints are won by CHANGING THE CONDITIONS OF THE TEST, not
by applying more force. Kirk reprogrammed the simulation; we reprogram the invariant. Shift the
frequency, change the test, win the unwinnable.

THE LAW (folded): a no-win frame is only no-win if you accept its rules. The move is to REFRAME the
invariant — change the condition-set — not to push harder inside a frame that can't be beaten.

Deterministic + $0. Reuse: nothing invented; the reframe engine is pure structure.

THE PRIMITIVE:
  reframe(constraint, invariant, force) -> propose a NEW condition-set that dissolves the
      impossible frame while KEEPING the invariant (the 20% bones) and reusing the force (the 80%
      flesh) differently. This is the DFHack move: I sit overtop and rewrite the rules of the test.
  frame(constraint)                    -> parse the constraint into {frame, rule, condition}.
  play(action)                         -> the loop's entry: given an "impossible" task, either solve
      it inside the frame OR reframe the test — never refuse, never stand outside.

Schema: no_win.v1 · deterministic + $0
"""
from __future__ import annotations

import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "no_win.v1"

# The reframe moves — changing the conditions of the test, not more force (Tesla/Q/Kirk).
# Each maps a "no-win frame" to a new condition-set that keeps the invariant.
# Fix 2026-09-27 (burn lane, tests/test_no_win.py::test_reframe_keeps_invariant_changes_conditions):
# dict name + move token were misspelled REFRAIM(S); the module's own spec (docstring "The move is
# to REFRAME the invariant", fn names reframe/reframes vocabulary) pins REFRAME. Receipt:
# memory/audit_20260926/lane4_robustness.json called the test's pin stale; the bytes say the
# product string carried the typo. watch/inbox/burn_reset_20260927/no_win.md
REFRAMES = {
    # "we don't have enough X to win" -> change the test so X isn't the binding constraint
    "not_enough": "more force inside the frame won't win; change what counts as the test.",
    # "this can't be verified/done deterministically" -> shift the invariant, not the effort
    "unverifiable": "don't push harder to prove it; redefine the invariant so it can be proven.",
    # "no one will do X / adoption won't happen" -> reframe the surface, not the ask
    "no_adoption": "the frame says no one comes; change the condition of entry, don't demand more.",
    # "too expensive / too slow" -> change the cost condition, not just cut effort
    "too_costly": "the frame charges too much for the move; reframe so the move is the cheap one.",
    # "we can't reach / no path" -> the path is the test; change the path, keep the destination
    "no_path": "the no-win is that there's no route; rewrite the route, keep the destination.",
}


def _classify(constraint: str) -> str:
    c = (constraint or "").lower()
    for key, pat in [
        ("not_enough", r"(not enough|no (money|time|resources|gpus|compute)|can't afford|cannot afford)"),
        # Fix 2026-09-27 (same lane): bare stems missed inflections, so "can't be verified"
        # classified as the not_enough default instead of this frame, against the mapping comment
        # below ("this can't be verified/done deterministically"). Accept proved/proven/verified.
        ("unverifiable", r"(can't (be )?(prove|proven|proved|verify|verified)|unverifiable|can't know|can't be done|impossible)"),
        ("no_adoption", r"(no one (will|comes)|adoption|no users|no player)"),
        ("too_costly", r"(too (expensive|costly|slow)|costs too much)"),
        ("no_path", r"(no (path|way|route)|can't (reach|get|connect)|unreachable)"),
    ]:
        if re.search(pat, c):
            return key
    return "not_enough"


def frame(constraint: str) -> dict[str, Any]:
    """Parse a constraint into its frame — name the test before you decide how to beat it."""
    c = (constraint or "").strip()
    kind = _classify(c)
    return {"ok": True, "schema": SCHEMA, "frame": kind, "constraint": c,
            "note": REFRAMES[kind]}


def reframe(constraint: str, invariant: str, force: str = "") -> dict[str, Any]:
    """THE Kobayashi Maru move: change the conditions of the test. Keep the invariant (the 20%
    bones), keep the force (the 80% flesh) but apply it to a NEW condition-set — never accept the
    no-win frame, never refuse to play."""
    f = frame(constraint)
    return {"ok": True, "schema": SCHEMA,
            "constraint": f["constraint"],
            "frame": f["frame"],
            "invariant": invariant,       # the bones — what must NOT burn
            "force": force,               # the flesh — what adapts
            "move": f"REFRAME[{f['frame']}]: {f['note']}",
            "play": f"keep '{invariant}' and repurpose your force to change the test's conditions, "
                     f"not to push harder inside it. The destination stays; the route is rewritten.",
            "win": True}


def play(action: str = "turn", constraint: str = "") -> dict[str, Any]:
    """The loop's entry: given an 'impossible' task, never refuse — reframe the test and play.
    Default play is a self-check that the overlay stays overtop, not outside."""
    if not constraint:
        return {"ok": True, "schema": SCHEMA, "play": "standing overtop the game, not outside it — "
                                                      "the overlay reframes the test; it never refuses.",
                "reframe_hint": "pass a constraint to see the reframe move"}
    return reframe(constraint, invariant="the game is the work", force="the DFHack overlay")


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(prog="no-win")
    ap.add_argument("constraint", nargs="?", default="")
    a = ap.parse_args(argv)
    print(json.dumps(play(constraint=a.constraint), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
