"""cost_governor — per-task health-ADAPTIVE cost gate (2026-08-16, operator spec).

"Allow emergence but stop ourselves from blowing 50c on a FAILED task; allow ourselves
to spend a dollar on a USEFUL one we know is going well."

This is NOT a flat cap (the old deepseek daily token cap was a sacred cow — it counted
cache hits and blocked legitimate research). The ceiling ADAPTS to task health:

  SAFE    ceiling $0.50  — a task that has NOT yet produced useful output is cut here.
                          (operator: "stop ourselves from blowing 50c on a failed task")
  USEFUL  ceiling $1.00  — a task that IS producing real output may spend this.
                          (operator: "allow ourselves to spend a dollar on a useful one")

Spend is measured in DOLLARS on BILLABLE tokens (cache MISS + completion) at real prices,
never cache-hit tokens (near-free, ~$0.0028/M) — trust the bill, not the log field.

Health = the task produced real (non-empty, non-error) output. That's the grounded signal
that a task is "going well": it earned more room. A failing/looping task never crosses
the SAFE ceiling.

Ledger: memory/runs/cost_governor/{task_id}.json  (append-only attempts per task)

Pricing for new attempts is delegated to ``mag.cost_truth``.  Older attempt
rows retain the rate that was recorded when they were made; they are not
silently rewritten as if an invoice had been reissued.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

LEDGER_DIR = ROOT / "memory" / "runs" / "cost_governor"

# Operator-specified adaptive ceilings (USD).
SAFE_CEILING_USD = 0.50     # failed/unproven task cut here
USEFUL_CEILING_USD = 1.00   # a task producing real output may spend this

# Real billable prices (USD per token) — grounded on the 2026-08-12 billing CSV.
# Off-peak DeepSeek-v4-flash defaults are retained as compatibility constants.
# price_usd() below uses the canonical receipt pricing schedule, including the
# current weekday peak multiplier, for new attempts.
MISS_USD_PER_TOK = 0.00000022   # $0.22 / 1M cache-miss input (off-peak)
OUT_USD_PER_TOK = 0.00000066    # $0.66 / 1M completion output (off-peak)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(task_id: str) -> dict[str, Any]:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    p = LEDGER_DIR / f"{task_id}.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"task_id": task_id, "attempts": [], "abandoned": False, "abandon_reason": ""}


def _save(ledger: dict[str, Any]) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    p = LEDGER_DIR / f"{ledger['task_id']}.json"
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def price_usd(miss_tokens: int = 0, completion_tokens: int = 0) -> float:
    """Billable cost in dollars: cache MISS + completion only. Never cache-hit tokens."""
    try:
        from mag.cost_truth import price_tokens

        return float(price_tokens(
            "deepseek",
            "deepseek-v4-flash",
            cache_miss_tokens=miss_tokens,
            completion_tokens=completion_tokens,
            at=datetime.now(timezone.utc),
        ).get("calculated_usd") or 0)
    except Exception:
        return round(
            int(miss_tokens or 0) * MISS_USD_PER_TOK
            + int(completion_tokens or 0) * OUT_USD_PER_TOK,
            6,
        )


def spend(task_id: str) -> float:
    """Total billable USD across all attempts of this task."""
    return round(sum(float(a.get("cost") or 0) for a in _load(task_id).get("attempts", [])), 6)


def proven_useful(task_id: str) -> bool:
    """Health signal: has this task EVER produced real (non-empty, non-error) output?"""
    for a in _load(task_id).get("attempts", []):
        if a.get("ok") and a.get("produced_output"):
            return True
    return False


def ceiling(task_id: str) -> float:
    """Adaptive ceiling: USEFUL once the task has proven useful, else SAFE."""
    return USEFUL_CEILING_USD if proven_useful(task_id) else SAFE_CEILING_USD


def check(task_id: str) -> dict[str, Any]:
    """The governor's verdict: is this task allowed to spend more right now?"""
    led = _load(task_id)
    s = spend(task_id)
    c = ceiling(task_id)
    health = proven_useful(task_id)
    allowed = bool(led.get("abandoned")) is False and s < c
    return {
        "schema": "cost_governor.check.v1",
        "task_id": task_id,
        "allowed": allowed,
        "spend_usd": s,
        "ceiling_usd": c,
        "health": "useful" if health else "unproven",
        "abandoned": bool(led.get("abandoned")),
        "abandon_reason": led.get("abandon_reason") or "",
        "reason": (
            "abandoned" if led.get("abandoned")
            else "healthy-useful-extended" if health
            else "safe-ceiling" if not allowed
            else "open"
        ),
    }


def record(
    task_id: str,
    *,
    miss_tokens: int = 0,
    completion_tokens: int = 0,
    ok: bool = False,
    produced_output: bool = False,
    detail: str = "",
) -> dict[str, Any]:
    """Record one attempt's billable cost + health, then return the updated verdict."""
    led = _load(task_id)
    cost = price_usd(miss_tokens, completion_tokens)
    led["attempts"].append(
        {
            "ts": _now(),
            "miss_tokens": int(miss_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "cost": cost,
            "ok": bool(ok),
            "produced_output": bool(produced_output),
            "detail": (detail or "")[:160],
        }
    )
    _save(led)
    return check(task_id)


def mark_abandoned(task_id: str, reason: str = "") -> dict[str, Any]:
    """Honestly mark a task as cost-capped/abandoned — it will NOT run again."""
    led = _load(task_id)
    led["abandoned"] = True
    led["abandon_reason"] = (reason or "cost-capped")[:200]
    led["abandoned_at"] = _now()
    _save(led)
    return check(task_id)


def summary(task_id: str) -> dict[str, Any]:
    led = _load(task_id)
    return {
        "task_id": task_id,
        "attempts": len(led.get("attempts", [])),
        "spend_usd": spend(task_id),
        "ceiling_usd": ceiling(task_id),
        "proven_useful": proven_useful(task_id),
        "abandoned": bool(led.get("abandoned")),
        "abandon_reason": led.get("abandon_reason") or "",
    }


def sweep_abandoned(*, max_entries: int = 50) -> dict[str, Any]:
    """List abandoned (cost-capped) tasks — for honest reporting, not hidden work."""
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(LEDGER_DIR.glob("*.json"))[:max_entries]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("abandoned"):
            out.append(
                {
                    "task_id": d.get("task_id"),
                    "spend_usd": round(
                        sum(float(a.get("cost") or 0) for a in d.get("attempts", [])), 6
                    ),
                    "reason": d.get("abandon_reason"),
                }
            )
    return {"ok": True, "abandoned": out, "n": len(out)}
