"""Skill ledger — the "how far to the goal" counter + auto-produced items.

The system needs two things to right-size model use automatically:
  1. DECISIONS — verified routing decision+outcome pairs (case law), target ~100-1000,
     so the router learns which model + reasoning level works per task shape.
  2. LABELED ROWS — classified text rows for a home-grown LoRA classifier, target
     ~500-5000, produced by the "local bulk classify → DeepSeek sample audit" runner.

Every record is appended automatically (agent runs, router calls, classify runner)
and the counter is served over REST so the dashboard can show progress.

REST:
  GET  /api/v1/skill-ledger                  -> progress()
  POST /api/v1/skill-ledger/record           -> record_decision(body)
  POST /api/v1/skill-ledger/labeled-row      -> record_labeled_row(body)

CLI:
  main.py skill-ledger progress | record ... | labeled-row ... | seed-bench
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

DECISIONS_PATH = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
LABELED_PATH = ROOT / "memory" / "runs" / "classify" / "rows.jsonl"
BENCH_DIR = ROOT / "memory" / "runs" / "local_bench"

TARGETS = {"decisions": 1000, "labeled_rows": 5000}

# B2-410 (2026-09-26): the `outcome` field is a REGISTRY, not an open vocabulary.
# Before this block the field had exactly one special value ("ok", the only one
# best_moves counts) while icon_drop's fold wrote raw status strings into it
# ("failed", "skipped_no_powershell", "unknown"; B2-378), so any consumer that
# must treat a skip differently from a failure had to import icon_drop's
# private literals. Registry pattern follows the events key registry
# (mag/events_key_schema.py): the constant lives here, every known value has a
# meaning line, and new writers register before first use.
OUTCOME_WIN = "ok"  # verified success; the ONLY value best_moves counts as a win
OUTCOME_REGISTRY: dict[str, str] = {
    "ok": "verified success (record_decision contract; seed_bench maps bench ok=True here)",
    "fail": "verified failure (record_decision contract; seed_bench maps bench ok=False here)",
    "failed": "icon_drop fold status, pre-B2-378 rows; same meaning as fail, spelled out",
    "skipped_no_powershell": "icon_drop fold status: attempt never ran (PowerShell unavailable); NOT a failure, must not count as either a win or a fail",
    "unknown": "icon_drop fold status: outcome could not be determined; neither win nor fail",
    "skipped": "generic skip: attempt never ran for a named non-failure reason",
}


def normalize_outcome(value: str | None) -> str | None:
    """Map registered aliases onto the canonical vocabulary; unknown strings
    pass through unchanged (registry feedback loop: a consumer meeting one
    files it here). None stays None = decision-only row."""
    if value is None:
        return None
    v = str(value).strip()
    if v == "failed":
        return "fail"
    return v or None


def is_win(value: str | None) -> bool:
    """True only for the registered win value; skips and unknowns are not wins."""
    return normalize_outcome(value) == OUTCOME_WIN


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _count(path: Path) -> int:
    if not path.is_file():
        return 0
    n = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for _ in f:
            n += 1
    return n


def proven_moves(*, min_count: int = 3, min_ok_rate: float = 0.7, limit: int = 12) -> list[dict[str, Any]]:
    """The case-law moves that have PROVEN (count >= min_count and ok_rate >= min_ok_rate).

    This turns skill_ledger from a write-only sink into a context source: the moves
    the stateless agent can trust, because they've been verified across >=min_count tries.
    Deterministic, $0. Consumed by context_pack as the L1c proven-moves layer.
    """
    if not DECISIONS_PATH.is_file():
        return []
    buckets: dict[str, dict[str, Any]] = {}
    try:
        lines = DECISIONS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = str(row.get("task_shape") or row.get("goal") or "")[:120]
        if not key:
            continue
        b = buckets.setdefault(key, {"count": 0, "ok": 0, "model": row.get("model"), "provider": row.get("provider")})
        b["count"] += 1
        if is_win(row.get("outcome")):
            b["ok"] += 1
    out = []
    for key, b in buckets.items():
        ok_rate = b["ok"] / b["count"] if b["count"] else 0
        if b["count"] >= min_count and ok_rate >= min_ok_rate:
            out.append({
                "move": key,
                "count": b["count"],
                "ok_rate": round(ok_rate, 2),
                "model": b.get("model"),
                "provider": b.get("provider"),
            })
    out.sort(key=lambda x: (x["count"], x["ok_rate"]), reverse=True)
    return out[:limit]


def record_decision(
    *,
    goal: str,
    task_shape: str,
    provider: str,
    model: str,
    reasoning_level: str = "none",
    seat: str = "",
    outcome: str | None = None,
    detail: str = "",
    source: str = "router",
    content_hash: str = "",
) -> dict[str, Any]:
    """Record one routing decision (+ optional verified outcome) as case law."""
    row = {
        "schema": "skill_ledger.decision.v1",
        "ts": _now(),
        "goal": (goal or "")[:300],
        "task_shape": task_shape,
        "provider": provider,
        "model": model,
        "reasoning_level": reasoning_level,
        "seat": seat,
        "outcome": outcome,  # registry: see OUTCOME_REGISTRY (None = decision only)
        "detail": (detail or "")[:200],
        "source": source,
    }
    if content_hash:
        row["content_hash"] = content_hash[:40]
    return _append(DECISIONS_PATH, row)


def record_labeled_row(
    *,
    text: str,
    label: str,
    classifier: str,
    confidence: float | None = None,
    audited_by: str | None = None,
    source: str = "classify_runner",
) -> dict[str, Any]:
    """Record one labeled row for the training pipeline (S-bin / eval fixtures)."""
    row = {
        "schema": "skill_ledger.labeled_row.v1",
        "ts": _now(),
        "text": (text or "")[:2000],
        "label": label,
        "classifier": classifier,
        "confidence": confidence,
        "audited_by": audited_by,
        "source": source,
    }
    return _append(LABELED_PATH, row)


def progress() -> dict[str, Any]:
    """Counter toward the targets — served over REST."""
    decisions = _count(DECISIONS_PATH)
    labeled = _count(LABELED_PATH)
    return {
        "ok": True,
        "schema": "skill_ledger.progress.v1",
        "decisions": decisions,
        "decisions_target": TARGETS["decisions"],
        "decisions_pct": round(100 * decisions / TARGETS["decisions"], 1),
        "labeled_rows": labeled,
        "labeled_target": TARGETS["labeled_rows"],
        "labeled_pct": round(100 * labeled / TARGETS["labeled_rows"], 2),
        "paths": {"decisions": str(DECISIONS_PATH), "labeled": str(LABELED_PATH)},
        "layman": (
            f"{decisions}/{TARGETS['decisions']} routing decisions · "
            f"{labeled}/{TARGETS['labeled_rows']} labeled rows"
        ),
    }


def seed_from_bench(*, limit: int = 200) -> dict[str, Any]:
    """Seed the ledger from the latest local_bench runs (task → model/outcome)."""
    if not BENCH_DIR.is_dir():
        return {"ok": False, "error": "no local_bench runs"}
    runs = sorted(BENCH_DIR.glob("*/results.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    added = 0
    for run in runs[:limit]:
        try:
            rows = json.loads(run.read_text(encoding="utf-8")).get("rows") or []
        except Exception:
            continue
        for r in rows:
            record_decision(
                goal=f"[bench] {r.get('task')}",
                task_shape=str(r.get("task")),
                provider=str(r.get("provider") or "ollama"),
                model=str(r.get("model")),
                reasoning_level="none",
                seat=str(r.get("provider") or "ollama"),
                outcome="ok" if r.get("ok") else "fail",
                detail=str(r.get("note") or "")[:100],
                source="bench",
            )
            added += 1
    return {"ok": True, "seeded": added, "progress": progress()}


def seed_from_training(
    *, path: Path | None = None, min_quality: float = 0.7, limit: int = 600
) -> dict[str, Any]:
    """Fold refined training data (operator-correction lessons) into the ledger as case law.

    Reads memory/training/refined_training_data.jsonl — the richest operator-teaching
    corpus (1,157 rows) — and records high-quality (>= min_quality) rows as decisions,
    so the stateless agent's proven_moves reflects what the operator ACTUALLY taught.
    Deterministic, $0. Idempotent-ish: dedupes by content_hash.
    """
    p = path or ROOT / "memory" / "training" / "refined_training_data.jsonl"
    if not p.is_file():
        return {"ok": False, "error": f"no training file: {p}"}
    # existing hashes already in ledger (source=training)
    seen: set[str] = set()
    if DECISIONS_PATH.is_file():
        try:
            for line in DECISIONS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("source") == "training" and row.get("content_hash"):
                    seen.add(str(row["content_hash"]))
        except OSError:
            pass
    added = 0
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"ok": False, "error": "read failed"}
    for line in lines:
        if added >= limit:
            break
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (row.get("quality_score") or 0) < min_quality:
            continue
        h = str(row.get("content_hash") or "")
        if h and h in seen:
            continue
        instruction = str(row.get("instruction") or "").strip()[:160]
        output = str(row.get("output") or "").strip()
        if not instruction:
            continue
        record_decision(
            goal=f"[training] {instruction}",
            task_shape=instruction,
            provider="ollama",
            model="copilot",
            reasoning_level="none",
            seat="copilot",
            outcome="ok",
            detail=output[:120],
            source="training",
            content_hash=h,
        )
        if h:
            seen.add(h)
        added += 1
    return {"ok": True, "seeded": added, "progress": progress()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skill-ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("progress")
    sub.add_parser("seed-bench")
    p_r = sub.add_parser("record")
    p_r.add_argument("--goal", required=True)
    p_r.add_argument("--task-shape", required=True)
    p_r.add_argument("--provider", default="ollama")
    p_r.add_argument("--model", required=True)
    p_r.add_argument("--reasoning", default="none")
    p_r.add_argument("--outcome", default=None)
    p_l = sub.add_parser("labeled-row")
    p_l.add_argument("--text", required=True)
    p_l.add_argument("--label", required=True)
    p_l.add_argument("--classifier", default="gemma4:latest")
    p_l.add_argument("--confidence", type=float, default=None)
    args = ap.parse_args(argv)

    if args.cmd == "progress":
        print(json.dumps(progress(), indent=2))
    elif args.cmd == "seed-bench":
        print(json.dumps(seed_from_bench(), indent=2, default=str))
    elif args.cmd == "record":
        r = record_decision(
            goal=args.goal, task_shape=args.task_shape, provider=args.provider,
            model=args.model, reasoning_level=args.reasoning, outcome=args.outcome,
        )
        print(json.dumps(r, indent=2))
    elif args.cmd == "labeled-row":
        r = record_labeled_row(text=args.text, label=args.label, classifier=args.classifier, confidence=args.confidence)
        print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
