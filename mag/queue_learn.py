"""Queue learning fold — treat every terminal queue item as a labeled training datapoint.

"The surface" worth training on: every done/failed queue item is a (task_shape, provider, model,
outcome, cost, estimate_error) row. cost_ledger.jsonl already captures the terminal economics;
this module FOLDS those terminals into the learning system (skill_ledger labeled rows + case law)
so routing/right-sizing improves from real outcomes instead of assumptions.

Tesuji shape: MEASURE (cost_ledger terminals) -> FOLD (labeled rows + decisions) -> APPLY (router
reads case law). Deterministic ($0, no LLM). Idempotent via a processed-timestamp watermark.

CLI:  python -m mag.queue_learn           (analyze, print)
      python -m mag.queue_learn --fold    (fold terminals into training)
      python -m mag.queue_learn --cadence (idempotent autorun fold)
Schema: queue_learn.v1
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

COST_LEDGER = ROOT / "memory" / "training" / "cost_ledger.jsonl"
STATE = ROOT / "memory" / "runs" / "queue_learn" / "state.json"
SCHEMA = "queue_learn.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _tier_for(queue_id: str) -> str | None:
    """Look up a queue item's tier (mission/research/maintenance/filler) by queue_id."""
    if not queue_id:
        return None
    try:
        from mag.orchestrator import QUEUE_DIR
        p = QUEUE_DIR / f"{queue_id}.json"
        if p.is_file():
            q = json.loads(p.read_text(encoding="utf-8"))
            return q.get("tier") or "mission"  # old items default to mission
    except Exception:
        pass
    return None


def _is_real_work(row: dict[str, Any]) -> bool:
    """Only fold mission/research terminals into training — skip maintenance/filler (filler
    is auto-generated busywork, not a real outcome to learn from)."""
    tier = _tier_for((row.get("join") or {}).get("queue_id"))
    return tier in ("mission", "research")


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten a cost_ledger.v1 row into a training-friendly row."""
    est = row.get("estimate") or {}
    act = row.get("actual") or {}
    outcome = row.get("outcome") or {}
    val = row.get("value") or {}
    plat = row.get("platform") or {}
    return {
        "ts": row.get("ts"),
        "queue_id": (row.get("join") or {}).get("queue_id"),
        "task_shape": est.get("depth") or "route",
        "phase": est.get("phase"),
        "provider": plat.get("provider") or est.get("seat"),
        "model": plat.get("model") or "",
        "success": bool(outcome.get("success")),
        "leaf_kind": outcome.get("leaf_kind"),
        "waste_kind": outcome.get("waste_kind"),
        "actual_prompt_tokens": act.get("prompt_tokens"),
        "actual_completion_tokens": act.get("completion_tokens"),
        "actual_usd": act.get("usd_est"),
        "estimate_usd": (est.get("price_band_usd") or 0),
        "estimate_error": val.get("estimate_error"),
        "usd_per_leaf": val.get("usd_per_leaf"),
        "seat_efficient": val.get("seat_efficient"),
    }


def analyze(limit: int = 200, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Read terminal cost_ledger rows and compute per-shape/provider learning aggregates."""
    all_rows = rows if rows is not None else _read_jsonl(COST_LEDGER)
    flat = [_flatten(r) for r in all_rows]

    # per (task_shape, provider): outcome rate + avg cost + avg estimate error
    combo: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # n, success, usd, err
    for f in flat:
        k = f"{f['task_shape']}|{f['provider']}"
        c = combo[k]
        c[0] += 1
        c[1] += 1 if f["success"] else 0
        c[2] += float(f["actual_usd"] or 0)
        if f["estimate_error"] is not None:
            c[3] += float(f["estimate_error"] or 0)

    combos = []
    for k, c in combo.items():
        shape, prov = k.split("|", 1)
        combos.append({"task_shape": shape, "provider": prov, "n": int(c[0]),
                       "success_rate": round(c[1] / c[0], 3) if c[0] else None,
                       "avg_usd": round(c[2] / c[0], 6) if c[0] else None,
                       "avg_estimate_error": round(c[3] / max(c[0], 1), 4)})
    combos.sort(key=lambda x: -x["n"])

    failures = [f for f in flat if not f["success"]]
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "terminals": len(flat),
        "successes": sum(1 for f in flat if f["success"]),
        "failures": len(failures),
        "total_usd": round(sum(float(f["actual_usd"] or 0) for f in flat), 6),
        "by_combo": combos,
        "failure_sample": [{"task_shape": f["task_shape"], "provider": f["provider"],
                            "waste_kind": f["waste_kind"], "usd": f["actual_usd"]} for f in failures[:8]],
    }


def fold(*, limit: int = 200) -> dict[str, Any]:
    """Fold new terminal cost_ledger rows into skill_ledger labeled rows + case law."""
    rows = _read_jsonl(COST_LEDGER)
    last = ""
    if STATE.is_file():
        try:
            last = (json.loads(STATE.read_text(encoding="utf-8")) or {}).get("last_ts") or ""
        except Exception:
            last = ""
    new = [r for r in rows if str(r.get("ts") or "") > last and _is_real_work(r)]
    labeled = 0
    skipped_filler = sum(1 for r in rows if str(r.get("ts") or "") > last and not _is_real_work(r))
    try:
        from mag.skill_ledger import record_labeled_row, record_decision
        for r in new:
            f = _flatten(r)
            record_labeled_row(
                text=f"{f['task_shape']}|{f['provider']}|{f['model']}|success={f['success']}|"
                     f"leaf={f['leaf_kind']}|usd={f['actual_usd']}|err={f['estimate_error']}",
                label="done" if f["success"] else f"failed:{f['waste_kind'] or 'unknown'}",
                classifier="deterministic",
                source="queue_learn",
            )
            labeled += 1
        # fold a case-law decision summarizing the aggregate (capped)
        a = analyze(rows=rows)
        worst = a["by_combo"][0] if a["by_combo"] else {}
        if worst:
            record_decision(
                goal="queue_learn aggregate",
                task_shape=str(worst.get("task_shape") or "route"),
                provider=str(worst.get("provider") or "?"),
                model="(aggregate)",
                outcome="ok",
                detail=f"top_combo={worst['task_shape']}/{worst['provider']} n={worst['n']} "
                       f"success={worst['success_rate']} avg_usd={worst['avg_usd']} err={worst['avg_estimate_error']}",
                source="queue_learn",
            )
    except Exception:
        pass
    # watermark — advance past ALL new rows (incl. filler) so skipped filler isn't reprocessed
    all_new = [r for r in rows if str(r.get("ts") or "") > last]
    if all_new:
        state_path = STATE
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"last_ts": all_new[-1].get("ts"), "folded_at": _now()}, indent=2),
                              encoding="utf-8")
    return {"ok": True, "new_terminals": len(new), "labeled_rows": labeled,
            "skipped_filler": skipped_filler}


def run_cadence(*, limit: int = 200) -> dict[str, Any]:
    """Idempotent autorun fold."""
    f = fold(limit=limit)
    a = analyze(limit=limit)
    return {"ok": True, "action": "folded" if f["new_terminals"] else "skip",
            "fold": f, "analysis": a}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="queue-learn", description="Queue-as-training-surface learning fold")
    ap.add_argument("--fold", action="store_true", help="fold terminals into skill_ledger training rows")
    ap.add_argument("--cadence", action="store_true", help="idempotent autorun fold")
    args = ap.parse_args(argv)
    if args.cadence:
        res = run_cadence()
    elif args.fold:
        res = fold()
    else:
        res = analyze()
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
