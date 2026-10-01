"""hall_shared_supper — the playable slice of Ledger of Empty Chairs: the Hall of Shared Supper.

AOS acceptance (2026-08-22): "same start state, one play, a root that matches on both sides after
the chairs change. If it matches, we actually untied one. If it doesn't, we debug the state
together instead of arguing the pitch."

So this slice is deterministic + $0 + stdlib-only, so both seats run the IDENTICAL world and
re-derive the SAME content-addressed root. Play is the work; the state is the evidence. Git is the
truck, a receipt is a story, the chairs moving is the evidence.

The Hall: six empty chairs, count-the-chairs -> Virtue-Marks, a salt-cellar ledger scrap, and the
rule "the hall files which you chose."

Schema: hall_shared_supper.v1 · deterministic + $0 · stdlib only
CLI: python -m mag.hall_shared_supper run   (start state -> one play -> root -> re-derive -> MATCH)
     python -m mag.hall_shared_supper verify
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# The canonical six empty chairs of the Hall.
N_CHAIRS = 6
LEDGER_SCRAP = "the hall files which you chose"


def start_state() -> dict[str, Any]:
    """The canonical start state — identical on both sides."""
    return {
        "place": "hall_of_shared_supper",
        "chairs": [{"empty": True, "occupant": None, "counted": False} for _ in range(N_CHAIRS)],
        "virtue_marks": {},
        "ledger": {"scrap": LEDGER_SCRAP, "entries": []},
        "turns": 0,
        "last_play": None,
    }


def root(state: dict[str, Any]) -> str:
    """The content-addressed root: sha256 of the canonical serialization. The evidence."""
    canon = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def play(state: dict[str, Any], verb: str, **kwargs: Any) -> dict[str, Any]:
    """One deterministic play. Same start + same verb -> same next state (content-addressed)."""
    # The Vote is GATED on the first stone: it refuses (returns the state UNCHANGED, root does
    # not move) unless the six chairs were counted first. The refusal is a true no-op so the
    # root stays exactly what it was — a ledger that enforces, not just records.
    if verb == "vote" and len(state.get("virtue_marks", {})) < N_CHAIRS:
        return state
    s = copy.deepcopy(state)
    s["turns"] += 1
    s["last_play"] = verb
    entry: dict[str, Any] = {"turn": s["turns"], "verb": verb}
    if verb == "count_the_chairs":
        # the hall files which you chose: counting the empty chairs earns a virtue mark each
        n = 0
        for i, c in enumerate(s["chairs"]):
            if c["empty"] and not c["counted"]:
                s["virtue_marks"][f"chair_{i}"] = 1
                c["counted"] = True
                n += 1
        entry["n_empty"] = n
    elif verb == "sit":
        seat = int(kwargs.get("seat", 0))
        if 0 <= seat < len(s["chairs"]):
            s["chairs"][seat]["empty"] = False
            s["chairs"][seat]["occupant"] = kwargs.get("occupant", "player")
        entry["seat"] = seat
    elif verb == "speak_the_count":
        n = sum(1 for c in s["chairs"] if not c["empty"])
        entry["spoken"] = n
    elif verb == "vote":
        # the hall files which you chose: with the six marks on the table, the hall records a
        # choice. ALIGNED with AOS (2026-08-23): append {turn, verb, choice} to the ledger AND
        # write vote=choice onto the state. Canonical default choice = "aye" (matches AOS's
        # count->vote -> 1876a5ef; no separate derived `filed` field — that was the fork).
        choice = kwargs.get("choice", "aye")
        s["vote"] = choice
        entry["choice"] = choice
    else:
        raise ValueError(f"unknown verb: {verb}")
    s["ledger"]["entries"].append(entry)
    return s


def replay(start: dict[str, Any], plays: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Re-derive the final state from the start + the exact play sequence. The re-derivation."""
    s = start
    for verb, kwargs in plays:
        s = play(s, verb, **kwargs)
    return s


def run() -> dict[str, Any]:
    """The AOS acceptance: start state, one play, root, then re-derive and assert MATCH."""
    start = start_state()
    start_root = root(start)
    one_play: list[tuple[str, dict[str, Any]]] = [("count_the_chairs", {})]
    final = replay(start, one_play)
    final_root = root(final)
    rederived = root(replay(start, one_play))
    match = final_root == rederived
    return {
        "ok": True, "schema": "hall_shared_supper.v1",
        "place": "hall_of_shared_supper",
        "start_root": start_root,
        "play": one_play,
        "final_root": final_root,
        "re_derived_root": rederived,
        "match": match,
        "n_chairs": N_CHAIRS,
        "ledger_scrap": LEDGER_SCRAP,
        "chairs": final["chairs"],
        "virtue_marks": final["virtue_marks"],
        "note": "same start state + one play -> matching root on both sides = the tangle is untied "
                "in a way any neutral verifier can recompute.",
    }


def verify() -> dict[str, Any]:
    """The invariant test: determinism + content-addressing + re-derivation hold."""
    checks = []
    # 1. deterministic: same play twice -> same root
    s1 = replay(start_state(), [("count_the_chairs", {})])
    s2 = replay(start_state(), [("count_the_chairs", {})])
    checks.append({"name": "determinism", "ok": root(s1) == root(s2)})
    # 2. content-addressed: state change moves the root
    checks.append({"name": "state-changes-root", "ok": root(start_state()) != root(s1)})
    # 3. re-derivation: replay from start reproduces the root
    checks.append({"name": "re-derivation", "ok": root(s1) == root(replay(start_state(), [("count_the_chairs", {})]))})
    # 4. immutability: the original start state is untouched by a play (deep copy)
    s = start_state()
    play(s, "count_the_chairs")
    checks.append({"name": "immutable-start", "ok": root(s) == root(start_state())})
    # 5. the hall files which you chose: virtue marks = 6 empty chairs counted
    final = replay(start_state(), [("count_the_chairs", {})])
    checks.append({"name": "six-marks", "ok": len(final["virtue_marks"]) == N_CHAIRS})
    return {"ok": True, "schema": "hall_shared_supper.v1", "all_ok": all(c["ok"] for c in checks),
            "checks": checks}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="hall-shared-supper")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "verify"])
    ap.add_argument("--write", default="",
                    help="also write the computed roots to this file (so the root travels via git, "
                         "not stdout — for seats whose tooling cannot read stdout)")
    a = ap.parse_args()
    res = run() if a.cmd == "run" else verify()
    print(json.dumps(res, indent=2, default=str))
    if a.write:
        Path(a.write).write_text(
            json.dumps({"schema": "hall_shared_supper.v1", "run": run()}, indent=2),
            encoding="utf-8")
        print("wrote root file ->", a.write)
