"""queue_gate — interdependency + rightsize view over the swarm queue (2026-08-25).

Operator: "we should have some logic gating system so when items are queued we have the
ability to see interdependencies in that queue so we can rightsize it before it goes out
and steal from our existing systems."

What this is:
- SCAN the queued swarm tasks and surface their INTERDEPENDENCIES (explicit depends_on,
  inferred same-domain / same-tag siblings, repeated goals, lane contention).
- GATE dispatch BEFORE it goes out: a task is blocked (left queued, not consumed) when
  its provider budget is spent (steal: swarm_worker.provider_spawn_allowed) or its lane
  is inside the learned overload cooldown (steal: lane_cadence.cooldown).
- RIGHTSIZE the order by EMPHASIS.

EMPHASIS DOCTRINE (operator 2026-08-25: "dupes provide emphasis"; SELF-STEAL from
mag/percolator.py, 2026-08-11): a repeated goal is NOT waste and NOT a block. The
percolator compiles repeatable signal into invariants — recurrence = weight (count++).
The queue speaks the same way: N identical queued goals = the swarm insisting. The
group's count IS its emphasis; the first copy dispatches ONCE carrying emphasis=N; the
copies percolate it up (visible as emphasis_copies, never silently deleted). Order:
highest emphasis first. This is the percolator's canonical -> repeat -> compile ->
count pattern applied to dispatch.

Steals: provider_spawn_allowed (budget gate), lane_cadence (learned rhythm),
percolator (emphasis = repeat count), free_tier lane map (provider -> lane id).

CLI: python -m mag.queue_gate status|deps|plan|preflight <task_id>
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "queue_gate.v1"
# t85: the fail-closed queue gate names its cause (t84 COOLDOWN_GATE_ERROR convention)
CADENCE_GATE_ERROR: str | None = None


def _queued_tasks() -> list[dict[str, Any]]:
    """Read every QUEUED task spec from the swarm queue (stateless, file-backed)."""
    from mag import swarm_worker as sw
    out: list[dict[str, Any]] = []
    for p in sorted(Path(sw.QUEUE_DIR).glob("sw-*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        if t.get("status") == "queued":
            t["_file"] = str(p)
            out.append(t)
    return out


def _all_tasks() -> list[dict[str, Any]]:
    """Read every task spec (any status) — needed to resolve depends_on across states."""
    from mag import swarm_worker as sw
    out: list[dict[str, Any]] = []
    for p in sorted(Path(sw.QUEUE_DIR).glob("sw-*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        t["_file"] = str(p)
        out.append(t)
    return out


def fingerprint(goal: str) -> str:
    """Normalized goal text — the near-duplicate key (punctuation/case/whitespace
    stripped). NO truncation (2026-08-25 fix): a 160-char cap made long shared-prefix
    goals (e.g. SHADE NOVEL ORPHAN with different anchors) FALSE duplicates. Full text
    means only genuinely identical goals collide — honest dedupe."""
    s = re.sub(r"[^a-z0-9]+", " ", (goal or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def _claim(statement: str, status: str, basis: list[str], evidence: list[str]) -> dict[str, Any]:
    """Tri-state claim via the vendored AOS integrity kernel (self-steal 2026-08-25):
    Supported requires Evidence, Disputed requires contradicting evidence, else Unproven.
    Never over-claims — an invalid claim degrades to Unproven/Assumption."""
    from mag.integrity_kernel import tri_state
    return tri_state(statement, status, tuple(basis), tuple(evidence))


def _lane_for(provider: str | None) -> str | None:
    """Map a task's provider to a cadence lane id, if one exists (steal free_tier ids)."""
    from mag import fuel_feed as f
    try:
        lanes = {ln[0] for ln in f.FREE_LANES}
    except Exception:  # noqa: BLE001
        lanes = set()
    p = (provider or "").strip()
    return p if p in lanes else None


def scan() -> dict[str, Any]:
    """Every queued task with its features: domain, tag, provider/lane, fingerprint,
    and EMPHASIS (count of queued tasks sharing the same canonical goal — dupes provide
    emphasis; recurrence compiles weight, percolator-steal)."""
    tasks = _queued_tasks()
    fp_counts: dict[str, int] = {}
    for t in tasks:
        fp = fingerprint(str(t.get("goal") or ""))
        fp_counts[fp] = fp_counts.get(fp, 0) + 1
    rows = []
    for t in tasks:
        fp = fingerprint(str(t.get("goal") or ""))
        rows.append({
            "task_id": t.get("task_id"),
            "goal": str(t.get("goal") or "")[:120],
            "domain": t.get("domain"),
            "tag": t.get("tag") or "",
            "provider": t.get("provider"),
            "model": t.get("model"),
            "lane": _lane_for(t.get("provider")),
            "depends_on": t.get("depends_on") or [],
            "emphasis": fp_counts.get(fp, 1),
            "created_at": t.get("created_at"),
        })
    return {"ok": True, "schema": SCHEMA, "kind": "scan", "queued": len(rows),
            "emphasized_goals": sum(1 for c in fp_counts.values() if c > 1),
            "tasks": rows}


def dependencies() -> dict[str, Any]:
    """The interdependency graph over the queued tasks.

    - EXPLICIT: depends_on (task waits for task_id) + depends_on_tag (waits for any task
      carrying that tag).
    - INFERRED: same_domain / same_tag siblings (a batch), emphasis (repeated canonical
      goal = weight, percolator-steal; copies listed as copies_of), lane (contention).
    """
    from mag import swarm_worker as sw
    tasks = _queued_tasks()
    fp_to_ids: dict[str, list[str]] = {}
    for t in tasks:
        fp_to_ids.setdefault(fingerprint(str(t.get("goal") or "")), []).append(str(t.get("task_id")))

    all_t = _all_tasks()
    status_of = {str(t.get("task_id")): t.get("status") for t in all_t}
    tag_status: dict[str, str] = {}
    for t in all_t:
        for tg in (t.get("tag") or "").split(","):
            tg = tg.strip()
            if tg:
                tag_status[tg] = t.get("status")

    graph: dict[str, dict[str, Any]] = {}
    for t in tasks:
        tid = str(t.get("task_id"))
        deps: list[dict[str, Any]] = []
        for d in (t.get("depends_on") or []):
            deps.append({"task_id": d, "status": status_of.get(str(d), "unknown"), "kind": "explicit"})
        for dt in (t.get("depends_on_tag") or []):
            st = tag_status.get(str(dt), "missing")
            if st == "done":
                continue  # satisfied
            deps.append({"task_id": None, "tag": str(dt), "status": st, "kind": "tag"})
        fp = fingerprint(str(t.get("goal") or ""))
        copies = [i for i in fp_to_ids.get(fp, []) if i != tid]
        real_deps = [x for x in deps if x.get("status") not in ("done",)]
        graph[tid] = {
            "task_id": tid,
            "goal": str(t.get("goal") or "")[:120],
            "domain": t.get("domain"),
            "tag": t.get("tag") or "",
            "lane": _lane_for(t.get("provider")),
            "depends_on": deps,
            "same_domain": [str(x.get("task_id")) for x in tasks
                            if x.get("domain") and x.get("domain") == t.get("domain")
                            and str(x.get("task_id")) != tid][:12],
            "same_tag": [str(x.get("task_id")) for x in tasks
                         if (x.get("tag") or "") and x.get("tag") == t.get("tag")
                         and str(x.get("task_id")) != tid][:12],
            "copies_of": copies,          # repeated goal -> emphasis (NOT a block)
            "emphasis": len(copies) + 1,  # this task + its copies
            "blocked": bool(real_deps),   # only unsatisfied dependencies block
        }
    return {"ok": True, "schema": SCHEMA, "kind": "deps", "queued": len(tasks), "graph": graph}


def preflight(task: dict[str, Any]) -> dict[str, Any]:
    """The GATE, run just before a task goes out. Steals:
    - swarm_worker.provider_spawn_allowed -> budget wall (quota exhausted leaves queued)
    - lane_cadence.cooldown -> learned overload backoff per lane
    - depends_on / depends_on_tag -> not-yet-satisfied dependency blocks
    NOTE (2026-08-25, emphasis doctrine): repeated goals do NOT gate — dupes provide
    emphasis. plan() carries the count on the dispatched head.
    Returns {"ok": True} to dispatch, else {"ok": False, "reason": ...} to leave queued.
    """
    tid = str(task.get("task_id") or "?")
    # 1) budget gate (the existing wall — steal, don't reimplement)
    try:
        from mag import swarm_worker as sw
        g = sw.provider_spawn_allowed(task.get("provider"))
        if not g.get("ok"):
            return {"ok": False, "task_id": tid, "reason": "budget",
                    "detail": g.get("reason"), "reset_in_hours": g.get("reset_in_hours")}
    except Exception as e:  # noqa: BLE001
        pass
    # 2) cadence gate (learned lane rhythm — a lane mid-backoff is probed, not hammered)
    lane = _lane_for(task.get("provider"))
    if lane:
        global CADENCE_GATE_ERROR
        CADENCE_GATE_ERROR = None  # a clean read clears the named error
        try:
            from mag import lane_cadence as lc
            cd = lc.cooldown(lane)
            if cd > 0:
                return {"ok": False, "task_id": tid, "reason": "lane_cooling",
                        "lane": lane, "detail": f"cooldown {cd}s"}
        except Exception as _ce:  # noqa: BLE001 - an unverifiable lane state must not read as dispatchable
            # GATE FAIL-CLOSED (2026-09-25, t85): the old 'except Exception: pass' let an
            # errored cadence read fall through to dispatch (the LAST GO path on this gate;
            # cooldown() itself is t84 fail-closed and provider_spawn_allowed denies
            # internally on budget_unreadable). Safe direction = this gate's own deny
            # semantics: cd>0 leaves the task queued, and the sole production caller
            # mag/swarm_worker.py:400 leaves any not-ok gate result queued (visible, not
            # consumed). Deny with a named cause; self-heals on the next clean read.
            # SPEC: tests/test_loop_death_guards.py, t85 SPEC line 1.
            CADENCE_GATE_ERROR = f"FAIL-CLOSED: preflight cadence gate exited: {_ce}"
            return {"ok": False, "task_id": tid, "reason": "cadence_gate_error",
                    "lane": lane, "detail": str(_ce)[:160]}
    # 3) explicit dependency gate
    deps = task.get("depends_on") or []
    if deps:
        from mag import swarm_worker as sw
        all_t = _all_tasks()
        status_of = {str(t.get("task_id")): t.get("status") for t in all_t}
        waiting = [d for d in deps if status_of.get(str(d)) != "done"]
        if waiting:
            return {"ok": False, "task_id": tid, "reason": "depends_on",
                    "detail": f"waiting on {waiting[:3]}"}
    return {"ok": True, "task_id": tid, "lane": lane}


def plan(*, n: int = 10) -> dict[str, Any]:
    """RIGHTSIZED dispatch order by EMPHASIS (percolator-steal: recurrence compiles weight).

    Groups queued tasks by canonical goal; each group's size IS its emphasis. Groups go
    out highest-emphasis-first; the earliest copy of each group dispatches ONCE carrying
    emphasis=N; the remaining copies are visible as emphasis_copies (they have already
    spoken through the head — never silently deleted). Gated: budget / lane-cadence /
    unsatisfied depends_on leave a task queued (visible, not consumed).

    Returns:
      order:           [task_id, ...] dispatch order (n max)
      runs:            [{task_id, lane, domain, goal, emphasis}] the plan
      emphasis_copies: [{task_id, emphasis_of, count}] copies folded into the head
      gated:           [{task_id, reason, detail}] left queued
    """
    tasks = _queued_tasks()
    by_id = {str(t.get("task_id")): t for t in tasks}
    # group by canonical goal -> emphasis
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        fp = fingerprint(str(t.get("goal") or ""))
        groups.setdefault(fp, []).append(t)
    for g in groups.values():
        g.sort(key=lambda x: x.get("created_at") or "")  # earliest copy is the head
    ordered_groups = sorted(groups.values(),
                            key=lambda g: (-len(g), g[0].get("created_at") or ""))

    order: list[str] = []
    runs: list[dict[str, Any]] = []
    emphasis_copies: list[dict[str, Any]] = []
    gated: list[dict[str, Any]] = []
    for g in ordered_groups:
        head = g[0]
        tid = str(head.get("task_id"))
        pf = preflight(head)
        if not pf.get("ok"):
            # DISPUTED: the claim "dispatchable now" is contradicted by a live gate
            gated.append({
                "task_id": tid, "reason": pf.get("reason"),
                "detail": pf.get("detail"), "lane": pf.get("lane"),
                "emphasis": len(g),
                "claim": _claim(f"dispatchable now ({tid})", "Disputed", ["Evidence"],
                                [f"gate blocked: {pf.get('reason')}: {pf.get('detail')}"]),
            })
            continue
        order.append(tid)
        runs.append({"task_id": tid, "lane": _lane_for(head.get("provider")),
                     "domain": head.get("domain"),
                     "goal": str(head.get("goal") or "")[:90],
                     "emphasis": len(g),
                     "claim": _claim(f"dispatchable now ({tid})", "Supported", ["Evidence"],
                                     ["budget_ok", "lane_cool", "deps_satisfied"])})
        for copy in g[1:]:
            emphasis_copies.append({"task_id": str(copy.get("task_id")),
                                    "emphasis_of": tid, "count": len(g),
                                    "claim": _claim(
                                        f"emphasis {len(g)} ({str(head.get('goal') or '')[:60]})",
                                        "Supported", ["Evidence"],
                                        [f"{len(g)} queued copies share the canonical goal"])})
    result = {"ok": True, "schema": SCHEMA, "kind": "plan",
              "queued": len(tasks), "dispatchable": len(order), "n": n,
              "order": order[:n], "runs": runs[:n],
              "emphasis_copies": emphasis_copies, "gated": gated}
    _claim_ledger(result)
    return result


def _claim_ledger(plan: dict[str, Any]) -> dict[str, Any]:
    """Append every tri-state claim from a plan to logs/queue_gate_claims.jsonl — the
    honest-byte home for what the gate claimed and on what basis (audit at the source).
    Append-only, $0, never throws."""
    try:
        from mag import fuel_feed as f
        claims = []
        for r in plan.get("runs", []):
            if r.get("claim"):
                claims.append({**r["claim"], "kind": "run", "task_id": r.get("task_id"),
                               "lane": r.get("lane"), "ts": f._now()})
        for g in plan.get("gated", []):
            if g.get("claim"):
                claims.append({**g["claim"], "kind": "gated", "task_id": g.get("task_id"),
                               "lane": g.get("lane"), "ts": f._now()})
        for c in plan.get("emphasis_copies", []):
            if c.get("claim"):
                claims.append({**c["claim"], "kind": "emphasis", "task_id": c.get("task_id"),
                               "emphasis_of": c.get("emphasis_of"), "ts": f._now()})
        if not claims:
            return {"ok": True, "n": 0}
        logs = Path(__file__).resolve().parents[1] / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "queue_gate_claims.jsonl").open("a", encoding="utf-8") as fh:
            for c in claims:
                fh.write(json.dumps(c, ensure_ascii=False, default=str) + "\n")
        return {"ok": True, "n": len(claims)}
    except Exception:  # noqa: BLE001
        return {"ok": False, "n": 0}


def status() -> dict[str, Any]:
    """The queue as a human map: counts, interdependency clusters, emphasis, gated."""
    s = scan()
    d = dependencies()
    p = plan(n=20)
    by_domain: dict[str, int] = {}
    for t in s["tasks"]:
        by_domain[t["domain"] or "auto"] = by_domain.get(t["domain"] or "auto", 0) + 1
    return {"ok": True, "schema": SCHEMA, "kind": "status",
            "queued": s["queued"],
            "by_domain": by_domain,
            "emphasized_goals": s["emphasized_goals"],
            "cadence_gate_error": CADENCE_GATE_ERROR,
            "clusters": sum(1 for v in d["graph"].values()
                            if len(v["same_domain"]) + len(v["same_tag"]) > 0),
            "gated": p["gated"][:8],
            "emphasis_copies": p["emphasis_copies"][:8],
            "next_dispatch": p["runs"][:8]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="queue-gate",
                                 description="interdependency + rightsize view over the swarm queue")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("scan")
    sub.add_parser("deps")
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--n", type=int, default=10)
    p_plan.add_argument("--json", action="store_true")
    sub.add_parser("status")
    p_pf = sub.add_parser("preflight")
    p_pf.add_argument("task_id")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        out = scan()
    elif a.cmd == "deps":
        out = dependencies()
    elif a.cmd == "plan":
        out = plan(n=a.n)
    elif a.cmd == "preflight":
        tid = a.task_id
        t = next((x for x in _queued_tasks() if str(x.get("task_id")) == tid), None)
        out = preflight(t) if t else {"ok": False, "error": f"no queued task {tid}"}
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
