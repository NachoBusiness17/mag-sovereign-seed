"""resume_order — when resuming after a huge queue, pick tasks by PROJECT ZEITGEIST and BLOCKERS.

Operator (2026-08-10): "when resuming work after having a huge queue use our rightsizer to pick in
order of project zeitgeist and blockers."

THE MECHANISM (resume ordering, not just FIFO):
  1. ZEITGEIST  — what is the project converging on RIGHT NOW? Use model_health.health():
                    bottleneck_priority (thin domains to steer at) + steer_at = the true current
                    zeitgeist. Tasks matching a high-zeitgeist domain rank FIRST.
  2. BLOCKERS   — what is blocking other work? Use the problem_knot registry: OPEN/unsolved knots
                    are blockers. A task that resolves an open knot (unblocks) ranks ABOVE one that
                    doesn't.
  3. RIGHTSIZE  — after zeitgeist+blocker ranking, apply tier discipline (cheap-first, escalate
                    only what's needed) so the highest-value unblocking work runs on the cheapest
                    capable tier.
  4. pick()     — the resume decision: which queued task to run FIRST given zeitgeist + blockers.

Honesty: zeitgeist = REAL convergence (multi-lens bottleneck from model_health), not vibes;
blockers = REAL open knots from the problem registry. A task's zeitgeist score is computed from
actual domain overlap, deterministic $0.

Schema: resume_order.v1 · CLI: python -m mag.resume_order rank | pick [--dry] | status
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
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

SCHEMA = "resume_order.v1"
QUEUE_DIR = ROOT / "memory" / "runs" / "swarm_worker" / "queue"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _toks(s: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(w) > 2}


_STOP = {"the", "and", "for", "are", "with", "that", "this", "from", "what", "how",
         "when", "where", "our", "your", "they", "them", "have", "has", "its", "not"}


def _read_tasks() -> list[dict[str, Any]]:
    if not QUEUE_DIR.is_dir():
        return []
    tasks = []
    for p in sorted(QUEUE_DIR.glob("*.json")):
        try:
            tasks.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return tasks


def _zeitgeist() -> dict[str, float]:
    """Project zeitgeist: domain -> zeitgeist weight (bottleneck priority), from model_health.
    Higher = more load-bearing/thin = where the project is converging + needs work."""
    try:
        from mag import model_health as mh
        h = mh.health()
        # bottleneck_priority = thin domains sorted by bottleneck (highest first)
        prio = h.get("bottleneck_priority") or []
        out = {}
        for i, d in enumerate(prio):
            # earlier in priority = higher zeitgeist weight (thin + load-bearing)
            out[str(d).lower()] = round(max(0.0, 1.0 - i / max(1, len(prio))), 3)
        # steer_at = the single thinnest domain = peak zeitgeist
        steer = h.get("steer_at")
        if steer and str(steer).lower() in out:
            out[str(steer).lower()] = 1.0
        return out
    except Exception:
        return {}


def _blockers() -> list[str]:
    """Open/unsolved problem knots = blockers. Read the problem_knot registry."""
    try:
        from mag import problem_knot as pk
        reg = pk._registry()
        return [str(k) for k in reg if not reg[k].get("solved")]
    except Exception:
        return []


def _task_blocker_score(goal: str, blockers: list[str]) -> float:
    """Does this task resolve a blocker? Overlap with open knot goals."""
    if not blockers:
        return 0.0
    gt = _toks(goal) - _STOP
    best = 0.0
    for b in blockers:
        bt = _toks(b) - _STOP
        if gt and bt:
            ov = len(gt & bt) / max(1.0, min(len(gt), len(bt)))
            best = max(best, ov)
    return round(best, 3)


def _task_zeitgeist_score(goal: str, zeit: dict[str, float]) -> float:
    """Does this task align with the project zeitgeist? Overlap with high-zeitgeist domains."""
    if not zeit:
        return 0.0
    gt = _toks(goal) - _STOP
    score = 0.0
    for domain, weight in zeit.items():
        dt = _toks(domain) - _STOP
        if gt and dt:
            ov = len(gt & dt) / max(1.0, min(len(gt), len(dt)))
            score = max(score, ov * weight)
    return round(score, 3)


def rank() -> dict[str, Any]:
    """Rank every queued task by zeitgeist + blocker score (the resume order)."""
    tasks = _read_tasks()
    zeit = _zeitgeist()
    blockers = _blockers()
    ranked = []
    for t in tasks:
        goal = str(t.get("goal") or "")
        if not goal:
            continue
        zg = _task_zeitgeist_score(goal, zeit)
        bl = _task_blocker_score(goal, blockers)
        # composite: zeitgeist (0.6) + blocker (0.4); unblocking the zeitgeist is highest
        score = round(0.6 * zg + 0.4 * bl, 3)
        ranked.append({"task_id": t.get("task_id"), "goal": goal[:80],
                       "status": t.get("status"), "zeitgeist": zg,
                       "blocker": bl, "score": score})
    ranked.sort(key=lambda r: -r["score"])
    return {"ok": True, "schema": SCHEMA, "n_queued": len(ranked),
            "zeitgeist_domains": list(zeit), "n_blockers": len(blockers),
            "ranked": ranked}


def pick(*, dry: bool = True) -> dict[str, Any]:
    """The RESUME decision: which queued task to run FIRST given zeitgeist + blockers, then
    rightsize (cheap-first, escalate only needed). dry=True = just report the pick ($0)."""
    r = rank()
    if not r["ranked"]:
        return {"ok": True, "schema": SCHEMA, "pick": None, "note": "queue empty"}
    top = r["ranked"][0]
    pick_ = {
        "task_id": top["task_id"], "goal": top["goal"],
        "score": top["score"], "zeitgeist": top["zeitgeist"], "blocker": top["blocker"],
        "why": (f"matches project zeitgeist ({top['zeitgeist']}) and/or unblocks a "
                f"blocker ({top['blocker']})"),
    }
    # rightsize: classify the picked task's tier (cheap vs frontier) — cheap-first.
    tier = "cheap"
    frontier_sig = ("deep", "research", "frontier", "grok", "architect", "synthesize",
                    "judgment", "strategy", "root cause", "design")
    if any(s in str(top["goal"]).lower() for s in frontier_sig):
        tier = "frontier"
    pick_["rightsized_tier"] = tier
    if not dry:
        # (apply would run it — enqueue already exists; here we just report the ordered pick)
        pass
    return {"ok": True, "schema": SCHEMA, "pick": pick_,
            "n_ranked": len(r["ranked"]), "dry": dry,
            "note": f"resume with {r['n_queued']} queued; zeitgeist domains: {r['zeitgeist_domains']}; "
                    f"{r['n_blockers']} blockers"}


def status() -> dict[str, Any]:
    r = rank()
    return {"ok": True, "schema": SCHEMA, "n_queued": r["n_queued"],
            "zeitgeist_domains": r["zeitgeist_domains"], "n_blockers": r["n_blockers"],
            "top_pick": r["ranked"][0] if r["ranked"] else None}


# ─────────────────────────────────────────────── COMPILER-STACK (let-me-build⇒steal) ──
# Operator (2026-08-10): "let me build" now maps to "let me steal" — don't hand-write code,
# send the intent through OUR COMPILER STACK (RIB → swarm → render → fold). This enqueues the
# resume_order mechanism ITSELF as a render task the cluster compiles/validates.
def compile_(*, dry: bool = True) -> dict[str, Any]:
    """Send the resume_order mechanism through the compiler stack (swarm render task) for
    validation. dry=True = plan ($0); dry=False enqueues to the swarm_worker queue."""
    from mag import swarm_worker as sw
    goal = ("COMPILER-STACK VALIDATION: review the resume_order mechanism — ranking queued tasks "
            "by project zeitgeist (model_health bottleneck/steer_at) then blockers (problem_knot "
            "open knots) then rightsize tier. Confirm the ordering is sound: zeitgeist 0.6 + "
            "blocker 0.4, cheap-first. Return one sharp verdict on the mechanism.")
    if dry:
        return {"ok": True, "schema": SCHEMA, "dry": True, "task_id": None, "goal": goal[:80]}
    r = sw.enqueue_task(goal, provider="deepseek", model="deepseek-chat",
                        domain="resume-order-compile", agent_idx=0, tag="resume-compile")
    return {"ok": True, "schema": SCHEMA, "dry": False, "task_id": r.get("task_id"),
            "queue": r.get("queue"), "goal": goal[:80]}


def promote_drainer(*, top: int = 3, boost: int = 5) -> dict[str, Any]:
    """DRAINER HOOK (steal: overlay resume-order score on the orchestrator drainer).
    Before the drainer picks the next task, PROMOTE the highest-zeitgeist / blocker-unblocking
    queued tasks so _next_queued (which sorts by tier then priority) serves them first.
    This makes the queue auto-resume by project zeitgeist + blockers, not just FIFO.
    NOTE: ranks the ORCHESTRATOR queue (what drain_once actually drains), not the swarm queue."""
    from mag import orchestrator as orch
    zeit = _zeitgeist()
    blockers = _blockers()
    # rank the orchestrator's queued entries by zeitgeist + blocker
    scored = []
    for q in orch.list_queue(limit=200):
        if q.get("status") != "queued":
            continue
        goal = str(q.get("goal") or "")
        zg = _task_zeitgeist_score(goal, zeit)
        bl = _task_blocker_score(goal, blockers)
        score = round(0.6 * zg + 0.4 * bl, 3)
        scored.append({"queue_id": q.get("queue_id"), "goal": goal[:80],
                       "zeitgeist": zg, "blocker": bl, "score": score})
    scored.sort(key=lambda x: -x["score"])
    promoted = []
    for entry in scored[:top]:
        if entry["score"] <= 0:
            continue
        p = orch.promote_queue(entry["queue_id"], priority=boost)
        if p.get("ok"):
            promoted.append({"queue_id": entry["queue_id"], "priority": boost,
                             "score": entry["score"], "goal": entry["goal"]})
    return {"ok": True, "schema": SCHEMA, "n_promoted": len(promoted),
            "promoted": promoted, "n_queued_orch": len(scored),
            "zeitgeist_domains": list(zeit), "n_blockers": len(blockers)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Resume-order the queue by zeitgeist + blockers")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["rank", "pick", "compile", "promote", "status"])
    ap.add_argument("--dry", action="store_true", default=False, help="plan only ($0); default REAL")
    a = ap.parse_args()
    if a.cmd == "rank":
        print(json.dumps(rank(), ensure_ascii=False, indent=2))
    elif a.cmd == "pick":
        print(json.dumps(pick(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "compile":
        print(json.dumps(compile_(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "promote":
        print(json.dumps(promote_drainer(top=3, boost=5), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
