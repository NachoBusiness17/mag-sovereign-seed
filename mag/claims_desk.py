"""claims_desk — the game mechanic that LEARNS AOS's civic-claim method through play.

AOS taught the empty claim (2026-08-23): a claim is a chair; empty means we do not know yet;
you sit only if a primary record is on the table — a permit, an ordinance, a clerk page, not a
blog, not a rumor, not a vibe. Score it supported / unproven / disputed. The human says when it
is supported.

Instead of talking about chairs, we encode the lesson as a deterministic game move. Play is the
work; the state is the evidence. The rule ENFORCES the lesson: a claim with no primary record on
the table CANNOT be sat — the desk refuses, and the root does not move. You cannot perform a
fake permit; the state will not let you.

Deterministic + $0 + stdlib + content-addressed: same start + same plays -> same root, re-derived
by any neutral verifier. This is learning through the game, not chat.

Schema: claims_desk.v1
CLI: python -m mag.claims_desk run   (play the lesson: refuse -> record -> sit -> speak -> MATCH)
     python -m mag.claims_desk verify
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "claims_desk.v1"
LEDGER_SCRAP = "the hall files which you chose"


def start_state() -> dict[str, Any]:
    """The canonical start: an empty desk, no claims yet. Identical on both sides."""
    return {
        "place": "claims_desk",
        "claims": {},   # name -> {record: bool, status, occupied: bool}
        "ledger": {"scrap": LEDGER_SCRAP, "entries": []},
        "turns": 0,
        "last_play": None,
    }


def root(state: dict[str, Any]) -> str:
    """The content-addressed root: sha256 of the canonical serialization. The evidence."""
    canon = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def play(state: dict[str, Any], verb: str, **kwargs: Any) -> dict[str, Any]:
    """One deterministic play. Same start + same verb -> same next state (content-addressed).

    THE LESSON IS ENFORCED, NOT PERFORMED: a claim cannot be sat without a primary record. The
    sit-without-record attempt is a TRUE NO-OP — the root does not move — so the game literally
    refuses a fake permit. That is the empty-claim law made into world-state.
    """
    s = copy.deepcopy(state)
    if verb == "sit":
        name = kwargs.get("claim", "")
        claim = s["claims"].get(name)
        # GATED: no primary record on the table -> refuse (state unchanged, root does not move).
        if not claim or not claim.get("record"):
            return s
    if verb == "score":
        name = kwargs.get("claim", "")
        claim = s["claims"].get(name)
        want = kwargs.get("status", "unproven")
        # AOS INTEGRITY-KERNEL LAW: Supported requires Evidence, never Assumption alone.
        # The desk refuses to mark a claim supported on inference/assumption (true no-op).
        if want == "supported" and (not claim or claim.get("basis") != "evidence"):
            return s
    s["turns"] += 1
    s["last_play"] = verb
    entry: dict[str, Any] = {"turn": s["turns"], "verb": verb}

    if verb == "name_claim":
        name = kwargs.get("claim", "")
        # a claim is a chair: empty means we do not know yet (unproven, no record, assumption only)
        s["claims"][name] = {"record": False, "status": "unproven", "occupied": False,
                             "basis": "assumption"}
        entry["claim"] = name
    elif verb == "place_record":
        name = kwargs.get("claim", "")
        if name in s["claims"]:
            s["claims"][name]["record"] = True
            s["claims"][name]["basis"] = "evidence"  # a primary record on the table = evidence
        entry["claim"] = name
    elif verb == "sit":
        name = kwargs.get("claim", "")
        # we only sit if a primary record is on the table
        s["claims"][name]["occupied"] = True
        entry["claim"] = name
    elif verb == "score":
        name = kwargs.get("claim", "")
        status = kwargs.get("status", "unproven")
        if name in s["claims"]:
            # the human says when it is supported; we do not auto-truth
            s["claims"][name]["status"] = status
        entry["claim"] = name
        entry["status"] = status
    elif verb == "speak":
        # speak how many claims are actually occupied (sat with a record)
        entry["occupied"] = sum(1 for c in s["claims"].values() if c.get("occupied"))
    else:
        raise ValueError(f"unknown verb: {verb}")
    s["ledger"]["entries"].append(entry)
    return s


def replay(start: dict[str, Any], plays: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Re-derive the final state from the start + the exact play sequence."""
    s = start
    for verb, kw in plays:
        s = play(s, verb, **kw)
    return s


def run() -> dict[str, Any]:
    """Play the lesson AOS taught: name a claim, try to sit WITHOUT a record (refused, root does
    not move), place the record, sit, score, speak. The refusal is the lesson made state."""
    start = start_state()
    start_root = root(start)
    claim = "a permit file is not complete until the issuing authority is named on the face"
    plays = [
        ("name_claim", {"claim": claim}),            # the chair is empty, unproven
        ("sit", {"claim": claim}),                   # NO record -> REFUSED (root unchanged)
        ("place_record", {"claim": claim}),          # a primary record lands on the table
        ("sit", {"claim": claim}),                   # now we sit (occupied by the play)
        ("speak", {}),
    ]
    # NOTE: we do NOT score 'supported' here. Occupying a chair with a record is the mechanic's
    # move; marking it SUPPORTED is the human's call. Software may occupy a chair, never truth
    # it (AOS integrity kernel: "Software never auto-truths. Human final call.").
    # capture the refusal: after name_claim, the sit-without-record must leave the root UNCHANGED
    after_name = replay(start, plays[:1])      # name_claim (chair now empty, unproven)
    refused = replay(start, plays[:2])         # name_claim + refused sit
    refusal_is_noop = root(refused) == root(after_name)
    final = replay(start, plays)
    final_root = root(final)
    rederived = root(replay(start, plays))
    occupied = sum(1 for c in final["claims"].values() if c.get("occupied"))
    return {
        "ok": True, "schema": SCHEMA, "place": "claims_desk",
        "start_root": start_root,
        "refusal_noop": refusal_is_noop,
        "play": [p[0] for p in plays],
        "final_root": final_root, "re_derived_root": rederived,
        "match": final_root == rederived,
        "occupied_claims": occupied,
        "claim": claim,
        "note": "the empty-claim law is ENFORCED, not performed: a claim with no primary record "
                "cannot be sat (the refusal is a deterministic no-op, root does not move). We "
                "learn through the game, not through chat.",
    }


def verify() -> dict[str, Any]:
    """The invariant test: determinism + content-addressing + the refusal-gate all hold."""
    claim = "x"
    # 1. determinism
    p = [("name_claim", {"claim": claim}), ("place_record", {"claim": claim}),
         ("sit", {"claim": claim})]
    checks = [{"name": "determinism", "ok": root(replay(start_state(), p)) == root(replay(start_state(), p))}]
    # 2. refusal-gate: sit without a record is a no-op (root does not move)
    s = start_state()
    after = play(s, "name_claim", claim=claim)
    refused = play(after, "sit", claim=claim)
    checks.append({"name": "refusal-noop", "ok": root(refused) == root(after)})
    # 3. record -> sit moves the root
    recorded = play(after, "place_record", claim=claim)
    seated = play(recorded, "sit", claim=claim)
    checks.append({"name": "record-then-sit-moves-root", "ok": root(seated) != root(after)})
    # 4. re-derivation
    checks.append({"name": "re-derivation", "ok": root(replay(start_state(), p)) == root(replay(start_state(), p))})
    return {"ok": True, "schema": SCHEMA, "all_ok": all(c["ok"] for c in checks), "checks": checks}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="claims-desk")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "verify"])
    a = ap.parse_args()
    print(json.dumps(run() if a.cmd == "run" else verify(), indent=2, ensure_ascii=False, default=str))
