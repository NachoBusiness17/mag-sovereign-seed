"""ghost_doctor — a DOCTOR for ghost that checks in on the sub-swarms, diagnoses what's wrong,
and works together to FIX it (the diagnostic/healer loop).

Operator (2026-08-10): "like a doctor for ghost that can check in on swarms and work together to
fix shit."

THE DOCTOR'S ROUNDS (check-in -> diagnose -> prescribe -> heal):
  * checkup()   -> run subswarm_health.report (which sub-swarms are HEALTHY / STRESSED / ISOLATED).
  * diagnose()  -> for an unhealthy sub-swarm, read its recent failures and CLASSIFY the cause
                   (missing key / timeout / crash / empty / unknown). Grounded in the captured stderr.
  * prescribe() -> the FIX: fold the diagnosed error as a lesson (doctrine/knot), route around the
                   broken sub-swarm (route_guard), and dispatch a heal task to the swarm (work
                   TOGETHER with it to fix).
  * rounds()    -> the doctor's full cycle: checkup all, diagnose + prescribe each unhealthy one.

Deterministic, $0 (diagnosis + lesson-fold + route; the heal task dispatch is the swarm's work).
Schema: ghost_doctor.v1 · CLI: python -m mag.ghost_doctor checkup|diagnose <sub>|prescribe <sub>|rounds
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "ghost_doctor.v1"


def _classify(result_text: str) -> str:
    low = (result_text or "").lower()
    if "missing api key" in low or "apikey" in low:
        return "missing_key"
    if "timeout" in low:
        return "timeout"
    if "traceback" in low or "exception" in low or "error" in low:
        return "crash"
    if not (result_text or "").strip():
        return "empty"
    return "unknown"


def checkup() -> dict[str, Any]:
    """The check-in: full sub-swarm health dashboard."""
    from mag import subswarm_health as sh
    r = sh.report()
    return {"ok": True, "schema": SCHEMA, "sub_swarms": r.get("sub_swarms", []),
            "isolated": r.get("isolated", [])}


def diagnose(subsystem: str) -> dict[str, Any]:
    """For one sub-swarm, read its recent failures and CLASSIFY the cause (grounded in stderr)."""
    from mag import swarm_worker as sw
    results = sw.collect().get("results", [])
    fails = [r for r in results if not r.get("ok") and _sub_of(r) == subsystem]
    causes = {}
    for f in fails:
        c = _classify(str(f.get("result") or ""))
        causes[c] = causes.get(c, 0) + 1
    return {"ok": True, "schema": SCHEMA, "subsystem": subsystem, "n_failures": len(fails),
            "causes": causes, "primary_cause": (max(causes, key=causes.get) if causes else "none")}


def _sub_of(r: dict[str, Any]) -> str:
    return str(r.get("domain") or r.get("tag") or "misc").split("-")[0] or "misc"


def prescribe(subsystem: str) -> dict[str, Any]:
    """The FIX: fold the diagnosed error as a lesson, route around the broken sub-swarm, and
    dispatch a heal task so the swarm and the doctor work together to fix it."""
    d = diagnose(subsystem)
    actions = []
    # 1) fold the diagnosis as a durable lesson (the doctor learns; the error can't silently recur)
    cause = d.get("primary_cause")
    if cause and cause != "none":
        try:
            from mag.knowledge_graph import fold
            fold(f"doctor:{subsystem}:{cause}", "doctrine",
                 f"Doctor diagnosed sub-swarm '{subsystem}' failing ({d.get('n_failures')} fails): "
                 f"{cause}. Prescribed heal so the swarm fixes it together.",
                 source="ghost_doctor")
            actions.append("folded_lesson")
        except Exception:
            pass
    # 2) route around the broken sub-swarm (anti-cascade)
    try:
        from mag import subswarm_health as sh
        sh.circuit()
        actions.append("re-ran_circuit_breaker")
    except Exception:
        pass
    # 3) dispatch a heal task to the swarm (work together to fix)
    try:
        from mag import invariant_lattice as il
        heal_goal = (f"[DOCTOR HEAL] Sub-swarm '{subsystem}' is failing ({cause}). "
                     f"Diagnose the root cause and prescribe the cheapest fix invariant.")
        t = il.dispatch_to_k8s(heal_goal, domain=subsystem)
        actions.append("dispatched_heal_task")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "subsystem": subsystem, "diagnosis": d,
            "actions": actions, "note": "doctor + swarm working together to fix"}


def rounds() -> dict[str, Any]:
    """The doctor's full rounds: checkup every sub-swarm, diagnose + prescribe each unhealthy one."""
    cu = checkup()
    out = {"schema": SCHEMA, "rounds": []}
    for sub in cu.get("sub_swarms", []):
        if sub.get("status") != "HEALTHY":
            d = diagnose(sub["subsystem"])
            p = prescribe(sub["subsystem"])
            out["rounds"].append({"subsystem": sub["subsystem"], "status": sub["status"],
                                  "diagnosis": d.get("primary_cause"),
                                  "prescribed_actions": p.get("actions")})
    out["ok"] = True
    out["unhealthy_checked"] = len(out["rounds"])
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="ghost-doctor")
    ap.add_argument("cmd", nargs="?", default="rounds",
                    choices=["checkup", "diagnose", "prescribe", "rounds"])
    ap.add_argument("subsystem", nargs="?", default="")
    args = ap.parse_args(argv)
    if args.cmd == "checkup":
        print(json.dumps(checkup(), indent=2, default=str))
    elif args.cmd == "diagnose":
        print(json.dumps(diagnose(args.subsystem), indent=2, default=str))
    elif args.cmd == "prescribe":
        print(json.dumps(prescribe(args.subsystem), indent=2, default=str))
    else:
        print(json.dumps(rounds(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
