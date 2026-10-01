"""Append-only seat economics ledger joined to queue terminal outcomes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import ROOT

LEDGER = ROOT / "memory" / "training" / "cost_ledger.jsonl"
USAGE = ROOT / "logs" / "provider_usage.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return rows


def task_estimate(goal: str, *, provider: str, model: str | None = None) -> dict[str, Any]:
    """Freeze the cheap planning prior when a queue row is created."""
    from mag.cost_simulator import estimate_goal

    lowered = goal.lower()
    pack_mode = "build" if "[build]" in lowered else "audit" if "audit" in lowered else "plan" if "[priority]" in lowered else "janitor" if "[steward]" in lowered or "[improve]" in lowered else "route"
    estimate = estimate_goal(goal, seat=provider, pack_mode=pack_mode, dry=True)
    line = estimate.get("line") or {}
    return {
        "schema": "task_estimate.v1",
        "depth": pack_mode,
        "phase": estimate.get("phase") or "execute",
        "context_need_tokens": int(line.get("tokens_in") or 0),
        "output_tokens": int(line.get("tokens_out") or 0),
        "price_band_usd": float(estimate.get("total_usd_est") or 0),
        "seat": line.get("seat") or provider,
        "model": model or "",
    }


def _actual(provider: str, started_at: str, ended_at: str, rows: Iterable[dict[str, Any]], model: str = "") -> dict[str, Any]:
    """Join terminal work to receipt economics using the canonical billable split."""
    from mag.cost_truth import aggregate_rows

    selected = [r for r in rows if str(r.get("provider") or "") == provider and started_at <= str(r.get("ts") or "") <= ended_at]
    agg = aggregate_rows(selected, fallback_model=model)
    return {
        "prompt_tokens": agg["prompt_tokens"],
        "input_tokens": agg["input_tokens"],
        "cache_hit_tokens": agg["cache_hit_tokens"],
        "cache_miss_tokens": agg["cache_miss_tokens"],
        "billable_tokens": agg["billable_tokens"],
        "completion_tokens": agg["completion_tokens"],
        "usd_est": agg["calculated_api_cost_usd"],
        "usd_fixed": 0.0,
        "calls": agg["calls"],
        "accounted_calls": agg["accounted_calls"],
        "priced_calls": agg["priced_calls"],
        "unpriced_calls": agg["unpriced_calls"],
        "pricing_coverage": agg["pricing_coverage"],
        "split_coverage": agg["split_coverage"],
        "pricing_schema": "cost_truth.v1",
    }


def emit_terminal(queue: dict[str, Any], task: dict[str, Any], *, usage_rows: Iterable[dict[str, Any]] | None = None, ledger_path: Path = LEDGER) -> dict[str, Any]:
    """File one idempotent cost_ledger.v1 row for a terminal queue item."""
    queue_id = str(queue.get("queue_id") or "")
    task_id = str(task.get("task_id") or queue.get("task_id") or "")
    prior = _read_jsonl(ledger_path)
    if any((r.get("join") or {}).get("queue_id") == queue_id for r in prior):
        return {"ok": True, "action": "already_filed", "queue_id": queue_id}
    provider = str(queue.get("provider") or task.get("provider") or "deepseek")
    estimate = queue.get("task_estimate") or task_estimate(str(queue.get("goal") or ""), provider=provider, model=queue.get("model"))
    started = str(queue.get("usage_started_at") or task.get("started_at") or queue.get("created_at") or "")
    ended = str(task.get("ended_at") or datetime.now(timezone.utc).isoformat())
    actual = _actual(provider, started, ended, usage_rows if usage_rows is not None else _read_jsonl(USAGE), model=str(queue.get("model") or task.get("model") or ""))
    success = task.get("status") == "done"
    leaf_kind = "test" if success and ("test" in str(queue.get("goal") or "").lower() or "proof" in str(queue.get("goal") or "").lower()) else ("none" if not success else "terminal")
    est_usd = float(estimate.get("price_band_usd") or 0)
    row = {
        "schema": "cost_ledger.v1",
        "ts": ended,
        "join": {"queue_id": queue_id, "task_id": task_id, "session_id": str(task.get("session_id") or f"orc-{task_id}")},
        "estimate": estimate,
        "actual": actual,
        "outcome": {"success": success, "leaf_kind": leaf_kind, "waste_kind": None if success else "agent_churn"},
        "value": {
            "usd_per_leaf": actual["usd_est"] if leaf_kind != "none" else None,
            "estimate_error": round((actual["usd_est"] - est_usd) / max(est_usd, 0.000001), 4),
            "seat_efficient": provider == "ollama" or (success and leaf_kind != "none"),
        },
        "platform": {"provider": provider, "model": queue.get("model") or task.get("model") or "", "seat": estimate.get("seat") or provider},
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "action": "filed", "row": row, "path": str(ledger_path)}
