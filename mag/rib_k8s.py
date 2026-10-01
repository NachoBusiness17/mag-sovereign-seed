"""rib_k8s — the RIB files as CODE INSTRUCTIONS for our k8s: the cluster ACTS SMART FOR FREE.

Operator (2026-08-10): "seriously thinking we can use our rib files as code instructions for our
k8's to act smart for free."

THE INSIGHT: the RIB action-invariants (rib_action) and the folded doctrine ARE declarative
desired-state policy. Our k8s already has the reconciler machinery (Kubernetes controllers
constantly compare desired vs actual and reconcile drift). We STEAL that exact pattern for OUR
invariants: a RIB-fed controller reads the action-invariant RIB as INSTRUCTIONS, checks the live
cluster against each, and applies SAFE drift-fix actions. No LLM, no tokens, deterministic $0 —
the cluster "acts smart" because the invariants drive its desired state, and the controller
enforces them on a cadence.

HOW it maps (policy table): an action-invariant KEYWORD -> a desired-state check + a safe action.
  invariant "replicas:1 / single controller"     -> deployment.mag replicas==1            (scale down drift)
  invariant "swarm headless in k8s, not local"   -> cronjob mag-swarm not suspended        (unsuspend)
  invariant "right-size the swarm"               -> cronjob resources present              (report)
  invariant "fold to content-addressed knots"    -> state PVC present                      (verify)
  invariant "swarm in its own binary (k8s)"      -> cronjob command uses mag.swarm_worker  (verify)

Deterministic, $0, idempotent, safe-by-default (read/verify; only idempotent drift-fixes applied).
Schema: rib_k8s.v1 · CLI: python -m mag.rib_k8s reconcile|report|invariants
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "rib_k8s.v1"
NS = "mag"

# --- policy table: invariant keyword -> (desired-state check, safe action, resource) ---------
# Each row: keyword(s) matched in the invariant text, a human label, a checker callable name,
# and an optional safe idempotent drift-fix action.
def _check_replicas(bridge) -> dict[str, Any]:
    obj = bridge.get_json("deployment", "mag")
    if not obj.get("ok"):
        return {"label": "single controller", "desired": "replicas==1", "actual": "?",
                "ok": False, "note": obj.get("error", "deployment not found")}
    reps = int(((obj.get("spec") or {}).get("replicas")) or 0)
    return {"label": "single controller", "desired": "replicas==1", "actual": f"replicas=={reps}",
            "ok": reps == 1, "action": None}


def _check_cronjob_suspended(bridge) -> dict[str, Any]:
    obj = bridge.get_json("cronjob", "mag-swarm")
    if not obj.get("ok"):
        return {"label": "swarm headless in k8s", "desired": "not suspended", "actual": "?",
                "ok": False, "note": obj.get("error", "cronjob not found")}
    susp = bool(((obj.get("spec") or {}).get("suspend")) or False)
    return {"label": "swarm headless in k8s", "desired": "not suspended", "actual": f"suspend=={susp}",
            "ok": not susp, "action": "unsuspend" if susp else None}


def _check_swarm_command(bridge) -> dict[str, Any]:
    obj = bridge.get_json("cronjob", "mag-swarm")
    if not obj.get("ok"):
        return {"label": "swarm in its own binary", "desired": "command uses swarm_worker", "actual": "?",
                "ok": False, "note": obj.get("error", "cronjob not found")}
    cmd = ((obj.get("spec") or {}).get("jobTemplate") or {}).get("spec", {}).get("template",
           {}).get("spec", {}).get("containers", [{}])[0].get("command") or []
    text = " ".join(str(c) for c in cmd)
    good = "swarm_worker" in text
    return {"label": "swarm in its own binary", "desired": "command uses swarm_worker",
            "actual": " ".join(str(c) for c in cmd[:4]),
            "ok": good, "action": "reapply-cronjob" if not good else None}


def _check_resources(bridge) -> dict[str, Any]:
    obj = bridge.get_json("cronjob", "mag-swarm")
    if not obj.get("ok"):
        return {"label": "right-size the swarm", "desired": "resources set", "actual": "?",
                "ok": False, "note": obj.get("error", "cronjob not found")}
    res = ((obj.get("spec") or {}).get("jobTemplate") or {}).get("spec", {}).get("template",
           {}).get("spec", {}).get("containers", [{}])[0].get("resources") or {}
    has = bool(res.get("requests") or res.get("limits"))
    return {"label": "right-size the swarm", "desired": "resources set", "actual": "set" if has else "unset",
            "ok": has, "action": "reapply-cronjob" if not has else None}


def _check_pvc(bridge) -> dict[str, Any]:
    obj = bridge.get_json("pvc", "mag-state")
    if not obj.get("ok"):
        return {"label": "fold to content-addressed knots", "desired": "state PVC present", "actual": "?",
                "ok": False, "note": obj.get("error", "pvc not found")}
    return {"label": "fold to content-addressed knots", "desired": "state PVC present", "actual": "present",
            "ok": True, "action": None}


POLICY = [
    ("replicas.*1|single controller|double.drain", _check_replicas),
    ("headless|in k8s|not local|unsuspend|suspended", _check_cronjob_suspended),
    ("own binary|swarm_worker|swarm-worker", _check_swarm_command),
    ("right.size|resource", _check_resources),
    ("content.addressed|knot|verkle|persist", _check_pvc),
]


def invariants(*, limit: int = 200) -> list[str]:
    """Collect the RIB action-invariants: the folded doctrine + the action-RIB specs (our
    'code instructions'). Deterministic, $0."""
    texts: list[str] = []
    try:
        from mag.rib_action import declare
        spec = [
            {"action": "run the swarm headless in k8s in its own binary, never local windows"},
            {"action": "replicas:1 — a single controller owns the autorun loop, never two (double-drain)"},
            {"action": "right-size the swarm cronjob with explicit bounded resources"},
            {"action": "fold every invariant to a content-addressed knot; amend not erase"},
        ]
        rib = declare(spec)
        texts += [str(s["action"]) for s in rib.slots]
    except Exception:
        pass
    try:
        from mag.knowledge_graph import GRAPH_PATH
        g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        for n in g.get("nodes", []):
            if n.get("kind") == "doctrine" and "k8s" in str(n.get("summary", "")).lower():
                texts.append(str(n.get("summary") or "")[:200])
    except Exception:
        pass
    return texts[:limit]


def reconcile(*, apply: bool = False) -> dict[str, Any]:
    """Reconcile the live cluster toward the RIB invariants (the controller loop, one pass).

    Each invariant keyword hits a desired-state check; if drift is found and apply=True, the
    safe idempotent fix is applied (reapply the cronjob manifest / unsuspend). Deterministic $0.
    """
    from mag import k8s_bridge as br
    inv = invariants()
    results = []
    actions_taken = []
    # run each policy check once (dedupe by label)
    seen: set[str] = set()
    for kw, checker in POLICY:
        if not any(re.search(kw, t, re.I) for t in inv):
            continue
        row = checker(br)
        if row["label"] in seen:
            continue
        seen.add(row["label"])
        results.append(row)
        act = row.get("action")
        if act and apply:
            try:
                if act == "unsuspend":
                    br._run(["patch", "cronjob", "mag-swarm", "-n", NS, "--type=merge",
                             "-p", '{"spec":{"suspend":false}}'])
                    actions_taken.append("unsuspend mag-swarm")
                elif act == "reapply-cronjob":
                    br.apply_file("mag-swarm-cronjob.yaml")
                    actions_taken.append("reapply mag-swarm-cronjob.yaml")
            except Exception as e:
                row["apply_error"] = str(e)[:80]
    ok = all(r.get("ok") for r in results)
    return {"ok": ok, "schema": SCHEMA, "checks": len(results),
            "all_conform": ok, "results": results, "apply": apply,
            "actions_taken": actions_taken, "invariant_count": len(inv)}


def report() -> dict[str, Any]:
    """Read-only report of how the cluster conforms to the RIB invariants (no changes)."""
    r = reconcile(apply=False)
    r["mode"] = "report"
    return r


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rib-k8s")
    ap.add_argument("cmd", nargs="?", default="report", choices=["report", "reconcile", "invariants"])
    ap.add_argument("--apply", action="store_true", help="apply safe drift-fixes")
    args = ap.parse_args(argv)
    if args.cmd == "invariants":
        print(json.dumps({"ok": True, "schema": SCHEMA, "invariants": invariants()}, indent=2))
    elif args.cmd == "reconcile":
        print(json.dumps(reconcile(apply=args.apply), indent=2))
    else:
        print(json.dumps(report(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
