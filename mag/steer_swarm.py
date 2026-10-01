"""steer_swarm — steer N swarm workers to ENGAGE an existing task, each inheriting the doctrine.

Operator (2026-08-12): "how can we steer those swarms to engage in existing tasks" + "yes".

THE MISSING JOINT: we can spawn swarms (route_novel) and we have doctrine injection
(rib_bus.inject_for), but there was no single primitive that says "here's an EXISTING task, spawn N
workers to engage it with the mounted doctrine." This is that primitive.

  engage(task_id, n, domain)  -> read the existing task (orchestrator.task_status), wrap its goal
                                 with rib_bus.inject_for(domain) so each worker inherits HOW to
                                 engage, and spawn N workers via swarm_surface.route_novel (the one
                                 shared primitive, deduped). Honest: if the task doesn't exist or has
                                 no goal, reports that; never fabricates.
  plan(task_id, n, domain)    -> dry-run: what engage() WOULD do (no spawn, $0).

Schema: steer_swarm.v1 · deterministic $0 for plan/read; engage spawns to the swarm (frontier drains)
Reuse: orchestrator.task_status, rib_bus.inject_for, swarm_surface.route_novel
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "steer_swarm.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_task(task_id: str) -> dict[str, Any] | None:
    """Read an existing task from EITHER store: the orchestrator task store (t-* / q-*) OR the
    swarm worker queue (sw-* — the spec files the k8s worker drains). Honest: whichever it lives in."""
    task_id = (task_id or "").strip()
    if not task_id:
        return None
    # 1) orchestrator task store
    try:
        from mag import orchestrator as orc
        t = orc.task_status(task_id)
        if t:
            return t
    except Exception:
        pass
    # 2) swarm worker queue (sw-* spec files)
    try:
        from mag import swarm_worker as sw
        p = sw.QUEUE_DIR / f"{task_id}.json"
        if p.is_file():
            import json
            q = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            # present as a task-like record: goal + status + a source marker
            return {"task_id": task_id, "goal": q.get("goal") or "", "status": q.get("status") or "queued",
                    "provider": q.get("provider"), "tag": q.get("tag"), "_store": "swarm-worker"}
    except Exception:
        pass
    # 3) queue entry (q-*) via orchestrator list_queue
    try:
        from mag import orchestrator as orc
        for q in orc.list_queue(limit=200):
            if q.get("queue_id") == task_id:
                return {"task_id": task_id, "goal": q.get("goal") or "", "status": q.get("status") or "queued",
                        "provider": q.get("provider"), "tag": q.get("tag"), "_store": "orchestrator-queue"}
    except Exception:
        pass
    return None


def _inject_doctrine(goal: str, domain: str) -> str:
    """Wrap the goal with the mounted RIB doctrine so the worker inherits HOW to engage."""
    try:
        from mag import rib_bus as rb
        return rb.inject_for(goal, domain=domain)
    except Exception:
        return goal


# DEFAULT ACCEPTANCE RIB — the complex-behavior-test contract every testable ask carries. The
# worker must satisfy these for the return to count (RIB-debug law: trusted bytes, not reports).
_DEFAULT_ACCEPTANCE = [
    "Return ONE steal + ONE invariant — a single, named, structural answer; no lists of options.",
    "Grounded, not fabricated: every claim must come from the fetched/observed bytes, with the ONE "
    "source named. If the source is unknown or blocked, say so honestly — never invent.",
    "Mapped to our shape (contracts only, no wholesale copy): name WHICH of our surfaces it changes.",
    "Testable: the invariant must be stated so it can be verified against our chain/knots.",
]


def testable_ask(goal: str, *, domain: str = "research",
                 acceptance: list[str] | None = None) -> dict[str, Any]:
    """Make a swarm ask a COMPLEX BEHAVIOR TEST: inject the mounted instruction set (rib_bus.
    inject_for) so the worker knows HOW to behave, then append an ACCEPTANCE RIB — the invariants /
    assertions the return must satisfy. The worker's output is verifiable against it (RIB-debug).

    Returns {ok, ask, injected, acceptance, note}. The `ask` string is what you route via
    route_novel / enqueue. Deterministic + $0 (pure text assembly)."""
    acc = list(acceptance) if acceptance else list(_DEFAULT_ACCEPTANCE)
    injected = _inject_doctrine(goal, domain)
    acc_block = "\n".join(f"  - {a}" for a in acc)
    ask = (f"{injected}\n\n"
           f"ACCEPTANCE RIB (this is a behavior TEST — your return must satisfy these, or it "
           f"does not count):\n{acc_block}\n"
           f"Return ONLY the result that satisfies the acceptance RIB.")
    return {"ok": True, "schema": SCHEMA, "injected": injected != goal,
            "acceptance": acc, "ask": ask, "note": "self-testing ask: instruction set + acceptance RIB"}


def plan(*, task_id: str, n: int = 3, domain: str = "territory") -> dict[str, Any]:
    """Dry-run: what engage() would do — read the task, show the wrapped goal, $0, no spawn."""
    task = _read_task(task_id)
    if not task:
        return {"ok": False, "schema": SCHEMA, "error": f"no existing task {task_id}"}
    goal = str(task.get("goal") or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": f"task {task_id} has no goal"}
    wrapped = _inject_doctrine(goal, domain)
    return {"ok": True, "schema": SCHEMA, "dry": True, "task_id": task_id, "n": n, "domain": domain,
            "status": task.get("status"), "goal": goal[:160],
            "doctrine_injected": wrapped != goal,
            "wrapped_goal": wrapped[:300],
            "note": "PLAN only — no spawn, $0. engage() would spawn n workers on this."}


def engage(*, task_id: str, n: int = 3, domain: str = "territory") -> dict[str, Any]:
    """STEER n swarm workers to ENGAGE an existing task: read it, inject the doctrine, spawn via
    route_novel (deduped, the one shared primitive). Honest: never fabricates."""
    task = _read_task(task_id)
    if not task:
        return {"ok": False, "schema": SCHEMA, "error": f"no existing task {task_id}"}
    goal = str(task.get("goal") or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": f"task {task_id} has no goal"}
    wrapped = _inject_doctrine(goal, domain)

    spawned = []
    for i in range(max(1, int(n))):
        # each worker gets a SELF-TESTING ask: the doctrine + the acceptance RIB it must satisfy
        ta = testable_ask(goal, domain=domain)
        engage_goal = (f"[steer-swarm {task_id} worker {i+1}/{n}] ENGAGE the existing task:\n"
                       f"{ta['ask']}")
        try:
            from mag import swarm_surface
            r = swarm_surface.route_novel(engage_goal, surface=f"steer-swarm:{task_id}",
                                          lens=domain, domain="research")
            spawned.append({"worker": i + 1, "ok": bool(r.get("ok")),
                            "deduped": r.get("deduped"), "task_id": r.get("task_id")})
        except Exception as e:
            spawned.append({"worker": i + 1, "ok": False, "error": str(e)[:120]})

    return {"ok": True, "schema": SCHEMA, "task_id": task_id, "n": n, "domain": domain,
            "status": task.get("status"), "doctrine_injected": wrapped != goal,
            "spawned": spawned,
            "n_spawned": sum(1 for s in spawned if s.get("ok") and not s.get("deduped")),
            "note": f"steered {len(spawned)} workers to engage existing task {task_id}, "
                    f"each inheriting the {domain} doctrine via the bus"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "engage(task_id, n, domain)->read the existing task, wrap its goal with "
                        "rib_bus.inject_for (the doctrine), spawn n workers via route_novel to "
                        "engage it; plan()->dry-run. The missing joint between spawn-swarms and "
                        "engage-existing-tasks.",
            "cost": "deterministic $0 (plan/read); engage spawns to the swarm (frontier drains)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="steer-swarm")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "plan", "engage"])
    ap.add_argument("task_id", nargs="?", default="")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--domain", default="territory")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd == "plan" or (a.cmd == "engage" and a.dry):
        print(json.dumps(plan(task_id=a.task_id, n=a.n, domain=a.domain), indent=2, default=str))
    elif a.cmd == "engage":
        print(json.dumps(engage(task_id=a.task_id, n=a.n, domain=a.domain), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
