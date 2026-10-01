"""Work tiers — a state machine so we always know what happens to work after its state.

The operator asked: "we should have tiers of work where we know after its state what
happens to it." This module makes that EXPLICIT and deterministic: each TIER of work
(research-pack, coding-run, dispatch/task, handoff, improvement) defines a
STATE -> (next_state, action) transition table. So no piece of work is ever a loose end —
after every state we know exactly what fires next (and which passive system does it).

This is the work-side of tesuji-everywhere: work moves through a known pipeline to a
terminal (case-law, verified-done, or failure-KB) — never just "left there."

CLI:  python -m mag.work_tiers [tier]   (show the state machine(s))
      python -m mag.work_tiers --all
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SCHEMA = "work_tiers.v1"

# TIER_TRANSITIONS: tier -> { state -> (next_state, action, by) }
# "by" = the passive system / actor that performs the transition.
TIER_TRANSITIONS: dict[str, dict[str, tuple[str, str, str]]] = {
    "research-pack": {
        "queued":      ("running", "spawn on cheap tier", "drainer"),
        "running":     ("done", "agent writes .answer.{remote,local}.md", "agent"),
        "done":        ("fold_to_case_law", "record decision in skill_ledger", "research_fold cadence"),
        "fold_to_case_law": ("case_law", "decision inheritable by router/decision layer", "skill_ledger"),
        "case_law":    ("terminal", "precedent — no further action", "—"),
        "failed":      ("failure_kb", "signature + remedy + recurring_patterns", "failure_kb"),
    },
    "coding-run": {
        "queued":      ("running", "spawn by router model_shape", "drainer"),
        "running":     ("verify", "spec_gate freeze/check + byte-diff", "spec_gate / usefulness-oracle"),
        "verify":      ("verified", "fold verified outcome to case law", "skill_ledger"),
        "verified":    ("case_law", "decision with verified outcome", "skill_ledger"),
        "case_law":    ("terminal", "precedent", "—"),
        "failed":      ("failure_kb", "remedy + recurring", "failure_kb"),
        "useless":     ("failure_kb", "pass-but-useless -> useless_output signature", "usefulness-oracle"),
    },
    "dispatch": {
        "queued":      ("running", "classify seat + context_plan", "router"),
        "running":     ("handoff" , "if is_handoff attach maze; else fresh context pack", "context_pack/session_maze"),
        "handoff":     ("done", "assemble maze + spawn on model_shape", "session_maze"),
        "done":        ("case_law", "fold routing decision + outcome", "skill_ledger"),
        "case_law":    ("terminal", "precedent", "—"),
        "failed":      ("failure_kb", "remedy", "failure_kb"),
    },
    "handoff": {
        "queued":      ("running", "assemble session maze (map-is-the-territory)", "session_maze"),
        "running":     ("done", "deeper model reads state/HANDOFF.md", "agent"),
        "done":        ("case_law", "fold handoff outcome", "skill_ledger"),
        "case_law":    ("terminal", "precedent", "—"),
        "failed":      ("failure_kb", "remedy", "failure_kb"),
    },
    "improvement": {
        "queued":      ("running", "spawn improve task", "drainer"),
        "running":     ("candidate", "L2 scoring -> candidates.jsonl", "improve_loop"),
        "candidate":   ("fold_to_case_law", "record decision / labeled row", "skill_ledger"),
        "fold_to_case_law": ("case_law", "inheritable", "skill_ledger"),
        "case_law":    ("terminal", "precedent", "—"),
        "failed":      ("failure_kb", "remedy", "failure_kb"),
    },
}


def next_for(tier: str, state: str) -> dict[str, Any]:
    """What happens to work of `tier` currently in `state`? Deterministic."""
    table = TIER_TRANSITIONS.get(tier)
    if not table:
        return {"ok": False, "error": f"unknown tier: {tier}", "known": sorted(TIER_TRANSITIONS)}
    if state == "terminal":
        return {"ok": True, "tier": tier, "state": state, "terminal": True}
    trans = table.get(state)
    if not trans:
        return {"ok": False, "tier": tier, "state": state,
                "error": f"no transition for {tier}/{state}", "known_states": sorted(table)}
    next_state, action, by = trans
    return {"ok": True, "tier": tier, "state": state,
            "next_state": next_state, "action": action, "by": by, "terminal": next_state == "terminal"}


def describe(tier: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "tier": tier,
            "transitions": {s: {"next_state": n, "action": a, "by": b} for s, (n, a, b) in TIER_TRANSITIONS[tier].items()}}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="work-tiers", description="Show the work-tier state machines")
    ap.add_argument("tier", nargs="?", default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)
    if args.tier and args.tier in TIER_TRANSITIONS:
        print(json.dumps(describe(args.tier), indent=2, default=str))
    else:
        print(json.dumps({"schema": SCHEMA, "tiers": {t: describe(t) for t in TIER_TRANSITIONS}}, indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
