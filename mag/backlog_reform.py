"""backlog_reform — address a queued backlog INTELLIGENTLY through the new systems.

The operator's directive (2026-08-09): the 87-task backlog must be "addressed intelligently
and reframed via our new systems" — NOT blindly drained one-by-one. The new allocation stack
already decides work: flock_scheduler (embed -> field-separate -> cluster -> DEDUPE -> one_sizer
tier), one_sizer (cheapest-capable tier), signals (priority). This module runs the backlog
through that stack and produces a CURATED DISPATCH PLAN:

  - DEDUPE: near-identical tasks collapse (flock_scheduler clusters them) -> duplicates absorbed
    into their canonical task, never run redundantly.
  - RIGHT-TIER: each canonical task gets its cheapest-capable (tier, model) from one_sizer.
  - PRIORITY: order by a signal so the drainer eats high-value work first.

Deterministic, $0, no LLM. Reuses orchestrator + flock_scheduler + one_sizer + signals.
Schema: backlog_reform.v1
"""
from __future__ import annotations

import json
import sys
from collections import Counter
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

SCHEMA = "backlog_reform.v1"


def _load_queued() -> list[dict[str, Any]]:
    """Queued tasks from the orchestrator (status == queued), with their goals."""
    from mag import orchestrator as orch
    try:
        entries = orch.list_queue(limit=1000)
    except Exception:
        entries = []
    return [e for e in entries if str(e.get("status")) == "queued"]


def reform(*, apply: bool = False, priority: bool = True) -> dict[str, Any]:
    """Reframe the queued backlog via flock_scheduler + one_sizer + signals.

    Returns the curated dispatch plan. If apply=True, mutates the queue: duplicates are marked
    done (absorbed into their canonical), canonical tasks are promoted by priority so the
    drainer eats the curated plan.
    """
    from mag import flock_scheduler as fs

    queued = _load_queued()
    goals = [str(e.get("goal") or "") for e in queued]
    plan = fs.plan(goals, domain="general")
    assignments = plan.get("assignments", [])

    # map task -> queue_id
    task_to_qid = {}
    for e in queued:
        g = str(e.get("goal") or "")
        task_to_qid.setdefault(g, e.get("queue_id"))

    # dedupe: absorbed duplicates (non-canonical) -> queue_id(s) to drop
    dup_qids = []
    for grp in plan.get("dedupe_groups", []):
        kept = str(grp.get("kept") or "")
        for d in grp.get("duplicates", []):
            qid = task_to_qid.get(str(d))
            if qid:
                dup_qids.append({"queue_id": qid, "dup": str(d)[:80],
                                 "absorbed_into": str(kept)[:80]})

    # canonical tasks -> (queue_id, tier, model)
    canonical = []
    for a in assignments:
        if a.get("is_duplicate"):
            continue
        qid = task_to_qid.get(str(a.get("task") or ""))
        canonical.append({"queue_id": qid, "goal": str(a.get("task"))[:120],
                          "tier": a.get("tier"), "model": a.get("model"),
                          "learned_tier": a.get("learned_tier")})

    tier_dist = Counter(a.get("tier") for a in canonical)

    applied = {"duplicates_absorbed": 0, "canonical_promoted": 0}
    if apply:
        from mag import orchestrator as orch
        # absorb duplicates (mark done so drainer skips them)
        for d in dup_qids:
            try:
                q = orch._queue_load(d["queue_id"])
                if q:
                    q["status"] = "done"
                    q["detail"] = f"deduped-absorbed-into:{d['absorbed_into'][:40]}"
                    orch._queue_save(q)
                    applied["duplicates_absorbed"] += 1
            except Exception:
                pass
        # promote canonical by priority so drainer eats the curated order first
        if priority:
            for i, c in enumerate(canonical):
                if not c.get("queue_id"):
                    continue
                try:
                    orch.promote_queue(c["queue_id"], priority=max(1, 10 - i))
                    applied["canonical_promoted"] += 1
                except Exception:
                    pass

    return {"ok": True, "schema": SCHEMA, "queued_total": len(queued),
            "unique_tasks": plan.get("unique_tasks"),
            "deduped": len(dup_qids),
            "canonical_tasks": len(canonical),
            "tier_distribution": dict(tier_dist),
            "duplicates": dup_qids[:20],
            "canonical": canonical[:40],
            "applied": applied}


def summary() -> dict[str, Any]:
    r = reform(apply=False)
    return {"ok": True, "schema": SCHEMA, "queued_total": r["queued_total"],
            "unique_tasks": r["unique_tasks"], "deduped": r["deduped"],
            "canonical_tasks": r["canonical_tasks"], "tier_distribution": r["tier_distribution"]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="backlog-reform")
    ap.add_argument("--apply", action="store_true", help="mutate queue: absorb dups, promote canonical")
    args = ap.parse_args(argv)
    print(json.dumps(reform(apply=args.apply), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
