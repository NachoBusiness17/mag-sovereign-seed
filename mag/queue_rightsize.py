"""queue_rightsize — rightsize + dedup the orchestrator queue (cheapest capable tier, no overlap).

Lesson (2026-08-09): ~21,000 DeepSeek calls burned money because the queue ran
mis-rightsized (loop-escalate on expensive `deepseek_overmind`) and redundant
overlapping work (3 grok buffers on related topics, duplicate goals).

RIGHT-SIZE rule (per doctrine / tier_probe — spend on the spec, not the tier):
    ollama (free local)      : janitor / steward / verkle / maintenance / agent-state
    deepseek-v4-flash        : exec-shaped, research-packs, loop-escalate, refine-fix, handoff
    deepseek-v4-pro          : ONLY heavy code / design / reasoning (rare)
    grok-4.5                 : frontier synthesis (grok-batch buffers) — and overlapping
                               grok buffers should be MERGED into fewer calls

apply(dry=True default) rewrites each queued task's provider/model to the rightsized
tier (idempotent) and collapses exact-duplicate goals (keeps one). Backs up originals
to memory/runs/orchestrator/queue_backup_<ts>/.

Schema: queue_rightsize.v1
CLI: python -m mag.queue_rightsize analyze|apply [--apply]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "queue_rightsize.v1"
QUEUE_DIR = ROOT / "memory" / "runs" / "orchestrator" / "queue"

# tag -> cheapest capable tier/model
TAG_TIER: dict[str, str] = {
    # free local (janitor / maintenance / classify)
    "verkle-gap": "ollama",
    "steward-steward-daily": "ollama",
    "agent-state": "ollama",
    "cheap-swarm": "ollama",
    # cheap flash (exec-shaped / research / escalations)
    "loop-escalate": "deepseek-v4-flash",
    "research-pack": "deepseek-v4-flash",
    "refine-fix": "deepseek-v4-flash",
    "handoff-HANDOFF-2026": "deepseek-v4-flash",
    "code": "deepseek-v4-flash",
    "pytest": "deepseek-v4-flash",
    "refactor": "deepseek-v4-flash",
    "implement": "deepseek-v4-flash",
    # frontier synthesis — keep grok, but these should be merged (overlap)
    "grok-batch-buffer_2_memory_handoff": "grok-4.5",
    "grok-batch-buffer_3_system_architecture": "grok-4.5",
    "grok-batch-buffer_1_thought_disconnect_swarm": "grok-4.5",
}
# grok buffers that overlap on 'sovereign architecture synthesis' -> merge into 1 call
GROK_MERGE_GROUP = "grok-batch-buffer"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _queued() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not QUEUE_DIR.is_dir():
        return rows
    for p in sorted(QUEUE_DIR.glob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if j.get("status") == "queued":
            rows.append({"file": p, "data": j})
    return rows


def _norm(goal: str) -> str:
    g = (goal or "").strip().lower()
    g = re.sub(r"^\s*(\[.*?\]\s*)+", "", g)  # strip leading [tag] markers
    return g[:80]


def analyze() -> dict[str, Any]:
    rows = _queued()
    tags: Counter = Counter()
    models: Counter = Counter()
    wrong: list[dict[str, Any]] = []
    by_norm: dict[str, list[str]] = defaultdict(list)
    grok_buffers: list[str] = []
    for r in rows:
        d = r["data"]
        tag = str(d.get("tag") or "none")
        model = str(d.get("model") or d.get("provider") or "?")
        tags[tag] += 1
        models[model] += 1
        rec = TAG_TIER.get(tag)
        if rec and model != rec:
            wrong.append({"file": r["file"].name, "tag": tag, "model": model,
                          "should": rec, "goal": (d.get("goal") or "")[:50]})
        n = _norm(d.get("goal") or "")
        if n:
            by_norm[n].append(r["file"].name)
        if tag and tag.startswith(GROK_MERGE_GROUP):
            grok_buffers.append(r["file"].name)
    dupes = {g: fs for g, fs in by_norm.items() if len(fs) > 1}
    return {
        "schema": SCHEMA, "ts": _now(), "ok": True,
        "queued_total": len(rows),
        "by_tag": dict(tags), "by_model": dict(models),
        "mis_rightsized": wrong, "mis_rightsized_count": len(wrong),
        "duplicates": dupes, "duplicate_groups": len(dupes),
        "grok_buffers": grok_buffers, "grok_buffer_count": len(grok_buffers),
        "overlap_note": (f"{len(grok_buffers)} grok buffers overlap on architecture "
                         "synthesis — merge into one call to save grok tokens") if len(grok_buffers) > 1 else "none",
    }


def apply(*, dry: bool = True) -> dict[str, Any]:
    """Rewrite queued tasks to the rightsized tier + collapse duplicate goals."""
    rows = _queued()
    if not dry:
        backup = QUEUE_DIR.parent / f"queue_backup_{_now()[:19].replace(':', '')}"
        backup.mkdir(parents=True, exist_ok=True)
        for r in rows:
            shutil.copy2(r["file"], backup / r["file"].name)

    changed = []
    dropped_dupes = []
    seen_norm: set[str] = set()
    for r in rows:
        d = r["data"]
        tag = str(d.get("tag") or "none")
        rec = TAG_TIER.get(tag)
        n = _norm(d.get("goal") or "")

        # collapse exact-duplicate goals (keep first)
        if n in seen_norm:
            dropped_dupes.append(r["file"].name)
            if not dry:
                r["file"].unlink(missing_ok=True)
            continue
        if n:
            seen_norm.add(n)

        if rec and d.get("model") != rec:
            d["model"] = rec
            d["provider"] = "xai" if rec == "grok-4.5" else ("ollama" if rec == "ollama" else "deepseek")
            if not dry:
                r["file"].write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
            changed.append({"file": r["file"].name, "tag": tag, "model": rec})
    # LAW #6: fold the rightsize decision as case law so the loop self-improves.
    if not dry and changed:
        try:
            from mag.skill_ledger import record_decision
            by_tag: dict[str, int] = Counter(c["tag"] for c in changed)
            for tag, n in by_tag.items():
                try:
                    record_decision(
                        goal=f"rightsize queue tag={tag} ({n} tasks)",
                        task_shape="ops", provider="deepseek",
                        model=TAG_TIER.get(tag, "?"), outcome="ok",
                        detail=f"rightsized {n} queued {tag} tasks to cheapest capable tier (self-learning law #6)",
                        source="queue_rightsize",
                    )
                except Exception:
                    pass
        except Exception:
            pass
    return {
        "schema": SCHEMA, "ts": _now(), "ok": True, "dry": dry,
        "rightsized": changed, "rightsized_count": len(changed),
        "dupes_dropped": dropped_dupes, "dupes_dropped_count": len(dropped_dupes),
        "note": "grok buffers should be merged (overlap) — see analyze()",
    }


def learn() -> dict[str, Any]:
    """LAW #6 self-improvement: read recent task OUTCOMES by tag and recommend tier
    escalations/downgrades. If a tag's tasks keep FAILING on its current tier, escalate;
    if they keep succeeding cheaply, stay. Folds into case law via record_decision."""
    from collections import defaultdict
    td = ROOT / "memory" / "runs" / "orchestrator" / "tasks"
    outcomes: dict[str, dict[str, int]] = defaultdict(lambda: {"done": 0, "fail": 0})
    if td.is_dir():
        for p in td.glob("*.json"):
            try:
                j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            tag = str(j.get("tag") or "none")
            st = str(j.get("status") or "?")
            if st in ("done", "ok", "complete"):
                outcomes[tag]["done"] += 1
            elif st in ("failed", "timeout", "died", "stalled", "killed"):
                outcomes[tag]["fail"] += 1
    recs = []
    for tag, o in outcomes.items():
        total = o["done"] + o["fail"]
        if total < 3:
            continue
        rate = o["done"] / total
        if rate >= 0.8:
            recs.append({"tag": tag, "outcome": "keep_tier", "success_rate": round(rate, 2),
                         "note": f"tag '{tag}' succeeds at {round(rate*100)}% — keep cheap tier"})
        elif rate < 0.5:
            recs.append({"tag": tag, "outcome": "escalate_tier", "success_rate": round(rate, 2),
                         "note": f"tag '{tag}' fails at {round((1-rate)*100)}% — consider higher tier"})
    # fold escalations as case law
    for r in recs:
        if r["outcome"] == "escalate_tier":
            try:
                from mag.skill_ledger import record_decision
                record_decision(goal=f"self-learn tier for tag={r['tag']}",
                                task_shape="ops", provider="deepseek", model="flash",
                                outcome="learn", detail=r["note"], source="queue_rightsize.learn")
            except Exception:
                pass
    return {"schema": SCHEMA, "ts": _now(), "ok": True,
            "recommendations": recs, "count": len(recs)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "analyze").lower()
    do_apply = "--apply" in argv
    if cmd == "learn":
        print(json.dumps(learn(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "apply" or (cmd == "analyze" and do_apply):
        print(json.dumps(apply(dry=not do_apply), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(analyze(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
