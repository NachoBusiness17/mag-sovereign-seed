"""queue_analysis — automated QUEUE ANALYSIS: dedupe + rightsize + value/novelty/tokenomics
when the swarm queue piles up (the operator's dedupe-idea, automated).

Operator (2026-08-10): "we do dedupes when things pile up can that be an automated task of que
analysis for rightsizing training and tokenomics and research value and novelty?"

THE MECHANISM (automate what we do by hand when the queue piles up):
  1. inspect()      — count the real queue: total, by status, by domain, oldest age.
  2. dedupe()       — find near-duplicate goals (token-overlap over the queue) -> drop the dup,
                      keep ONE canonical + record the dedupe (don't pay the swarm twice).
  3. rightsize()    — classify each task: cheap (local/ollama/flash), frontier (deep/grok),
                      or already-covered (cache hit) -> re-tier. Only novel+valuable escalate.
  4. value()        — novelty gate: is the goal already in the knowledge graph / corpus? If yes
                      = cache hit (drop/steer away); if no = novel (worth the swarm spend).
  5. tokenomics()   — estimate the token/cost budget of the pending queue (deepseek hit/miss
                      rates) so we know what a drain actually costs before spending.
  6. analyze()      — the full automated pass, producing a queue-health report + recommended
                      actions (dedupe N, downgrade N, escalate N, drop N cache-hits).

Honesty: value = NOVELTY (real coverage check against our graph/corpus), not self-congratulation.
A cache-hit (we already know it) is flagged to drop, never to re-run. cost is an ESTIMATE from
real rates, labeled as such.

Schema: queue_analysis.v1 · deterministic $0 (no LLM in the analysis) ·
CLI: python -m mag.queue_analysis inspect | analyze [--apply] | status
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

SCHEMA = "queue_analysis.v1"
QUEUE_DIR = ROOT / "memory" / "runs" / "swarm_worker" / "queue"
REPORT = ROOT / "memory" / "runs" / "queue_analysis" / "report.json"

# DeepSeek real rates (window_hop): hit $0.0028/M, miss $0.14/M, out $0.28/M.
RATES = {"hit_per_m": 0.0028, "miss_per_m": 0.14, "out_per_m": 0.28}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _words(text: str) -> set[str]:
    return set(w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{3,}", text or ""))


def _overlap(a: str, b: str) -> float:
    ta, tb = _words(a), _words(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1.0, min(len(ta), len(tb)))


def inspect() -> dict[str, Any]:
    tasks = _read_tasks()
    statuses = Counter(t.get("status", "?") for t in tasks)
    domains = Counter(str(t.get("domain") or "?") for t in tasks)
    return {"ok": True, "schema": SCHEMA, "n_queued": len(tasks),
            "by_status": dict(statuses), "by_domain": dict(domains.most_common(10))}


def dedupe(*, threshold: float = 0.55) -> dict[str, Any]:
    """Find near-duplicate goals in the queue (token-overlap) -> drop dups, keep one canonical."""
    tasks = _read_tasks()
    kept, dropped, groups = [], [], []
    for i, t in enumerate(tasks):
        goal = str(t.get("goal") or "")
        placed = False
        for g in groups:
            if _overlap(g["goal"], goal) >= threshold:
                g["dups"].append({"task_id": t.get("task_id"), "goal": goal[:60]})
                dropped.append(t.get("task_id"))
                placed = True
                break
        if not placed:
            groups.append({"goal": goal, "dups": []})
            kept.append(t)
    return {"ok": True, "schema": SCHEMA, "threshold": threshold,
            "n_queued": len(tasks), "n_groups": len(groups),
            "n_droppable_dups": len(dropped), "dropped_ids": dropped[:20],
            "groups": [{"canonical": g["goal"][:70], "n_dups": len(g["dups"])} for g in groups]}


def _cache_hit(goal: str) -> bool:
    """Novelty gate: does our knowledge graph / corpus already cover this goal?"""
    try:
        from mag.knowledge_graph import known
        if known(goal).get("known"):
            return True
    except Exception:
        pass
    try:
        from mag import lens_chain as lc
        for p, _ in lc._steal_docs():
            pw = _words(p.stem)
            if pw and _overlap(goal, p.stem) >= 0.4:
                return True
    except Exception:
        pass
    return False


def rightsize() -> dict[str, Any]:
    """Classify each task: cheap vs frontier vs cache-hit. Re-tier by value+novelty."""
    tasks = _read_tasks()
    cheap, frontier, cache_hit = [], [], []
    # signal words for frontier judgment
    frontier_sig = ("deep", "research", "frontier", "grok", "architect", "synthesize",
                    "judgment", "strategy", "design", "root cause")
    for t in tasks:
        goal = str(t.get("goal") or "")
        if _cache_hit(goal):
            cache_hit.append({"task_id": t.get("task_id"), "goal": goal[:60]})
        elif any(s in goal.lower() for s in frontier_sig):
            frontier.append({"task_id": t.get("task_id"), "goal": goal[:60]})
        else:
            cheap.append({"task_id": t.get("task_id"), "goal": goal[:60]})
    return {"ok": True, "schema": SCHEMA, "n_queued": len(tasks),
            "n_cheap": len(cheap), "n_frontier": len(frontier), "n_cache_hit": len(cache_hit),
            "cheap": cheap, "frontier": frontier, "cache_hit": cache_hit}


def tokenomics(*, est_input_tokens: int = 3000, est_output_tokens: int = 800) -> dict[str, Any]:
    """Estimate the token/cost budget of the pending queue (deepseek rates). ESTIMATE, labeled."""
    tasks = _read_tasks()
    n = len(tasks)
    # assume ~half the prefix is a cache hit (shared preamble), half miss
    hit_tokens = n * est_input_tokens * 0.5
    miss_tokens = n * est_input_tokens * 0.5
    out_tokens = n * est_output_tokens
    cost = (hit_tokens / 1e6 * RATES["hit_per_m"]) + (miss_tokens / 1e6 * RATES["miss_per_m"]) \
        + (out_tokens / 1e6 * RATES["out_per_m"])
    return {"ok": True, "schema": SCHEMA, "n_queued": n,
            "est_input_tokens": est_input_tokens, "est_output_tokens": est_output_tokens,
            "est_hit_tokens": int(hit_tokens), "est_miss_tokens": int(miss_tokens),
            "est_out_tokens": int(out_tokens),
            "est_cost_usd": round(cost, 4),
            "note": "ESTIMATE from deepseek rates (hit $0.0028/M, miss $0.14/M, out $0.28/M); "
                    "authoritative = operator billing"}


def apply(*, threshold: float = 0.55, drop_cache_hits: bool = True) -> dict[str, Any]:
    """ACTUALLY clear the pile: delete dropped-duplicate + cache-hit task files, keep one canonical.
    The analysis identifies them; this applies it. Guarded (never deletes a file that fails). Returns
    how many were removed. Deterministic + $0.

    This is the 'bones, not sacred cows' cull: the queue's 958 tasks collapse to ~123 unique groups
    because an orphan-sense re-enqueue flood inflated ONE task to 522 copies. We delete the dups and
    the cache-hits (already-known work — never re-run), keeping the canonical novel few.
    """
    tasks = _read_tasks()
    n_before = len(tasks)
    removed = 0
    # 1) dedupe: keep the FIRST task per overlap group as canonical, mark the rest as dups
    groups: list[dict[str, Any]] = []
    dropped_ids: set[str] = set()
    for t in tasks:
        goal = str(t.get("goal") or "")
        for g in groups:
            if _overlap(g["goal"], goal) >= threshold:
                dropped_ids.add(str(t.get("task_id")))
                break
        else:
            groups.append({"goal": goal})
    # 2) cache-hits (already known) are waste to re-run — drop them too
    doomed: set[str] = set(dropped_ids)
    if drop_cache_hits:
        for t in tasks:
            if _cache_hit(str(t.get("goal") or "")):
                doomed.add(str(t.get("task_id")))
    # 3) delete the doomed files, guarded
    kept = 0
    for t in tasks:
        tid = str(t.get("task_id"))
        if tid in doomed:
            f = QUEUE_DIR / f"{tid}.json"
            try:
                if f.exists():
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        else:
            kept += 1
    return {"ok": True, "schema": SCHEMA, "n_before": n_before, "removed": removed,
            "remaining": n_before - removed, "n_groups": len(groups),
            "note": "deleted duplicate + cache-hit tasks; kept the canonical novel few"}


def analyze() -> dict[str, Any]:
    """The full automated queue-analysis pass: inspect + dedupe + rightsize + value + tokenomics,
    producing a health report + recommended actions."""
    ins = inspect()
    ded = dedupe()
    rs = rightsize()
    tok = tokenomics()
    report = {
        "schema": SCHEMA, "ts": _now(),
        "inspect": ins, "dedupe": ded, "rightsize": rs, "tokenomics": tok,
        "recommended_actions": {
            "drop_duplicates": ded["n_droppable_dups"],
            "drop_cache_hits": rs["n_cache_hit"],
            "keep_cheap": rs["n_cheap"] - ded["n_droppable_dups"],
            "escalate_to_frontier": rs["n_frontier"],
            "est_drain_cost_usd": tok["est_cost_usd"],
        },
        "provenance": "OUR queue analysis, deterministic $0 — ESTIMATES labeled, not claims",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(REPORT)
    return report


def status() -> dict[str, Any]:
    ins = inspect()
    return {"ok": True, "schema": SCHEMA, "n_queued": ins["n_queued"],
            "by_status": ins["by_status"], "report": str(REPORT) if REPORT.is_file() else "not built"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Automated swarm queue analysis: dedupe+rightsize+value+tokenomics")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["inspect", "analyze", "apply", "status"])
    ap.add_argument("--apply", action="store_true", help="actually delete dups/cache-hits (apply the analysis)")
    a = ap.parse_args()
    if a.cmd == "inspect":
        print(json.dumps(inspect(), ensure_ascii=False, indent=2))
    elif a.cmd == "apply":
        print(json.dumps(apply(), ensure_ascii=False, indent=2))
    elif a.cmd == "analyze":
        print(json.dumps(analyze(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
