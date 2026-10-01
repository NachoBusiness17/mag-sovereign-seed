"""Loop discipline audit — mine trails for wasteful repetition.

Reads governor autorun trail, orchestrator queue, and Verkle gaps to surface:
  - plan theater (same queue re-planned N× with no drain progress)
  - stuck queued goals (never start / never finish)
  - verkle gap fan-out (orphan residual → many scut jobs)

CLI: python main.py loop-audit [--json] [--tail N]
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

AUTORUN_TRAIL = ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl"
ORCH_TRAIL = ROOT / "memory" / "runs" / "orchestrator_trail.jsonl"

# Above this, recommend operator action (not a hard kill).
PLAN_THEATER_WARN = 24
PLAN_THEATER_ERROR = 80
STUCK_QUEUED_WARN = 40


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, *, tail: int | None = None) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if tail is not None and tail > 0:
        lines = lines[-tail:]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except json.JSONDecodeError:
            continue
    return out


def _goal_key(goal: str) -> str:
    """Stable dedupe key — verkle goals collapse to session id."""
    g = (goal or "").strip()
    m = re.match(r"^\[verkle\]\s+summarize-session\s+(\S+)", g, re.I)
    if m:
        return f"[verkle] summarize-session {m.group(1)}"
    m2 = re.search(r"summarize-session for (\S+)", g, re.I)
    if m2 and g.lower().startswith("[verkle]"):
        return f"[verkle] summarize-session {m2.group(1)}"
    return g[:200]


def verkle_gap_goal(gap: dict[str, Any]) -> str | None:
    """One canonical queue goal per verkle gap (session-scoped when possible)."""
    act = str(gap.get("action") or "").strip()
    detail = str(gap.get("detail") or "")
    if not act:
        return None
    m = re.search(r"summarize-session for (\S+)", act, re.I)
    if m:
        return f"[verkle] summarize-session {m.group(1)}"
    m2 = re.search(r"residual without knot:\s*(\S+\.json)", detail, re.I)
    if m2:
        sid = m2.group(1).replace(".json", "")
        return f"[verkle] summarize-session {sid}"
    if "backfill-sessions" in act:
        return "[verkle] backfill-sessions --all"
    if "lattice-backfill" in act:
        return "[verkle] lattice-backfill"
    if "verkle-audit" in act:
        return "[verkle] verkle-audit --synth"
    return f"[verkle] {detail[:120]} — {act}"[:300]


def plan_fingerprint(plan: dict[str, Any]) -> str:
    """Hash of queued goal set — unchanged queue should not re-log full plans."""
    goals = sorted(_goal_key(str(q.get("goal") or "")) for q in plan.get("orchestrator_queued") or [])
    joined = "|".join(goals)
    import hashlib

    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def analyze_autorun_trail(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mine autorun trail for plan theater and action mix."""
    replan_counts: Counter[str] = Counter()
    phases: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    drain_starts = 0
    last_progress_idx = -1

    for i, r in enumerate(rows):
        phase = r.get("phase")
        if phase:
            phases[str(phase)] += 1

        if r.get("schema") == "autorun_once.v1":
            act = r.get("action")
            if act:
                actions[str(act)] += 1
            if act == "drain":
                d = r.get("drain") or {}
                if d.get("action") == "started":
                    drain_starts += 1
                    last_progress_idx = i
            elif act == "governor":
                g = r.get("governor") or {}
                if g.get("ok"):
                    last_progress_idx = i

            plan = r.get("plan") or {}
            goals_src = plan.get("orchestrator_queued") or []
            if not goals_src and r.get("queued_goals"):
                goals_src = [{"goal": g} for g in r["queued_goals"]]
            for q in goals_src:
                goal = q.get("goal") if isinstance(q, dict) else str(q)
                replan_counts[_goal_key(str(goal or ""))] += 1

    plan_only_tail = 0
    if rows:
        for r in reversed(rows[-120:]):
            if r.get("schema") != "autorun_once.v1":
                continue
            if r.get("action") in ("drain", "governor") and (r.get("drain") or r.get("governor")):
                break
            if r.get("action") in ("busy", "paused", "dry"):
                continue
            plan_only_tail += 1

    top_replan = [{"goal": g, "count": c} for g, c in replan_counts.most_common(15)]

    findings: list[dict[str, Any]] = []
    for item in top_replan:
        c = item["count"]
        if c >= PLAN_THEATER_ERROR:
            findings.append(
                {
                    "kind": "plan_theater",
                    "severity": "error",
                    "goal": item["goal"],
                    "count": c,
                    "message": f"Goal re-planned {c}× with no completion signal — likely stuck queue or paused drainer",
                }
            )
        elif c >= PLAN_THEATER_WARN:
            findings.append(
                {
                    "kind": "plan_theater",
                    "severity": "warn",
                    "goal": item["goal"],
                    "count": c,
                    "message": f"Goal re-planned {c}× — check queue drain / operator_active pause",
                }
            )

    if plan_only_tail >= PLAN_THEATER_WARN:
        findings.append(
            {
                "kind": "idle_autorun",
                "severity": "warn" if plan_only_tail < PLAN_THEATER_ERROR else "error",
                "count": plan_only_tail,
                "message": f"Last {plan_only_tail} autorun ticks show no drain/governor progress",
            }
        )

    return {
        "n_rows": len(rows),
        "phases": dict(phases),
        "actions": dict(actions),
        "drain_starts": drain_starts,
        "plan_only_tail": plan_only_tail,
        "top_replan": top_replan,
        "findings": findings,
    }


def analyze_queue() -> dict[str, Any]:
    """Live orchestrator queue — stuck queued entries."""
    try:
        from mag.orchestrator import list_queue
    except Exception as e:
        return {"ok": False, "error": str(e)}

    queued = [q for q in list_queue(limit=100) if q.get("status") == "queued"]
    running = [q for q in list_queue(limit=100) if q.get("status") == "running"]
    by_goal: Counter[str] = Counter()
    for q in queued:
        by_goal[_goal_key(str(q.get("goal") or ""))] += 1

    dupes = [{"goal": g, "count": c} for g, c in by_goal.items() if c > 1]
    stuck = [{"queue_id": q.get("queue_id"), "goal": (q.get("goal") or "")[:120]} for q in queued]

    findings: list[dict[str, Any]] = []
    if len(queued) >= STUCK_QUEUED_WARN:
        findings.append(
            {
                "kind": "queue_depth",
                "severity": "warn",
                "count": len(queued),
                "message": f"{len(queued)} goals stuck in queued — drainer may be paused or spawn failing",
            }
        )
    for d in dupes:
        findings.append(
            {
                "kind": "queue_duplicate",
                "severity": "warn",
                "goal": d["goal"],
                "count": d["count"],
                "message": "Same goal enqueued multiple times — enqueue dedupe missing or bypassed",
            }
        )

    return {
        "ok": True,
        "queued_n": len(queued),
        "running_n": len(running),
        "duplicate_goals": dupes,
        "stuck_sample": stuck[:12],
        "findings": findings,
    }


def recommendations(findings: list[dict[str, Any]]) -> list[str]:
    """Operator-facing fixes keyed on finding kinds."""
    kinds = {f.get("kind") for f in findings}
    recs: list[str] = []
    if "plan_theater" in kinds or "idle_autorun" in kinds:
        recs.append(
            "Check MAG_OPERATOR_ACTIVE / drainer pause — autorun re-plans without draining burns ticks, not tokens."
        )
        recs.append(
            "Clear stale test goals from orchestrator queue; use `orchestrator queue list` and mark failed or delete JSON."
        )
    if "queue_depth" in kinds or "queue_duplicate" in kinds:
        recs.append("Enable enqueue dedupe: refuse second queued entry with same normalized goal.")
    if any("verkle" in str(f.get("goal", "")).lower() for f in findings):
        recs.append(
            "Batch verkle backfill: one `backfill-sessions --all` beats N× per-orphan summarize-session scut jobs."
        )
    if not recs:
        recs.append("Trails look healthy — keep one outcome per leaf; cap autorun plan logging when fingerprint unchanged.")
    return recs


def run_audit(*, tail: int = 2500) -> dict[str, Any]:
    """Full loop discipline report."""
    rows = _read_jsonl(AUTORUN_TRAIL, tail=tail)
    autorun = analyze_autorun_trail(rows)
    queue = analyze_queue()

    verkle_gaps_n = 0
    try:
        from mag.verkle_audit import verkle_gaps

        verkle_gaps_n = len(verkle_gaps())
    except Exception:
        pass

    all_findings = list(autorun.get("findings") or []) + list(queue.get("findings") or [])
    if verkle_gaps_n > 6:
        all_findings.append(
            {
                "kind": "verkle_fanout",
                "severity": "info",
                "count": verkle_gaps_n,
                "message": f"{verkle_gaps_n} verkle gaps — prefer batch actions over per-session queue rows",
            }
        )

    out: dict[str, Any] = {
        "ok": True,
        "schema": "loop_audit.v1",
        "ts": _utc(),
        "autorun": autorun,
        "queue": queue,
        "verkle_gaps_n": verkle_gaps_n,
        "findings": all_findings,
        "recommendations": recommendations(all_findings),
    }
    return out


def format_report(audit: dict[str, Any]) -> str:
    lines = [
        f"# Loop audit — {audit.get('ts', '')[:19]}",
        "",
        "## Summary",
        f"- Autorun trail rows (tail): {audit.get('autorun', {}).get('n_rows', 0)}",
        f"- Plan-only tail: {audit.get('autorun', {}).get('plan_only_tail', 0)}",
        f"- Queue queued: {audit.get('queue', {}).get('queued_n', '?')}",
        f"- Findings: {len(audit.get('findings') or [])}",
        "",
    ]
    for f in audit.get("findings") or []:
        lines.append(f"- **{f.get('severity', '?')}** `{f.get('kind')}`: {f.get('message')}")
    lines.extend(["", "## Recommendations"])
    for r in audit.get("recommendations") or []:
        lines.append(f"- {r}")
    top = (audit.get("autorun") or {}).get("top_replan") or []
    if top:
        lines.extend(["", "## Top re-planned goals"])
        for t in top[:8]:
            lines.append(f"- {t.get('count')}× {t.get('goal', '')[:100]}")
    return "\n".join(lines) + "\n"


def _cli(argv: list[str] | None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="loop-audit")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--tail", type=int, default=2500, help="Autorun trail lines to scan")
    args = p.parse_args(argv)
    audit = run_audit(tail=args.tail)
    if args.json:
        print(json.dumps(audit, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_report(audit))
    sev = [f for f in audit.get("findings") or [] if f.get("severity") == "error"]
    return 1 if sev else 0
