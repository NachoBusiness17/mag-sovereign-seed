"""frontier_salon_cli - the CLI entry for `python -m mag.frontier_salon`. Split from the library
module (Q-011, 2026-09-28): the huang-gate additions pushed mag/frontier_salon.py over the 400-line
ratchet cap, and extracting the argparse tail beats registering new debt. Behavior unchanged:
roundtable now also carries the huang gate flags (--why, --baseline-surface, --baseline-answer).
"""
from __future__ import annotations

import argparse
import json

from mag.frontier_salon import roundtable, salon, salon_project, status


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="frontier-salon")
    ap.add_argument("cmd", nargs="?", default="project",
                    choices=["status", "project", "salon", "roundtable"])
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--participants", default="")
    ap.add_argument("--why", default="", help="huang gate: why the escalation is justified")
    ap.add_argument("--baseline-surface", default="", help="huang gate: baseline seat asked first")
    ap.add_argument("--baseline-answer", default="", help="huang gate: what the baseline seat said")
    a = ap.parse_args(argv)
    if a.cmd == "roundtable":
        selected = [p.strip() for p in a.participants.split(",") if p.strip()] or None
        print(json.dumps(roundtable(
            a.question or "Roundtable this.", participants=selected, rounds=a.rounds, why=a.why,
            baseline={"surface": a.baseline_surface, "answer": a.baseline_answer},
        ), indent=2, default=str))
    elif a.cmd == "salon":
        print(json.dumps(salon(a.question or "Salon this."), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(salon_project(), indent=2, default=str))
    return 0
