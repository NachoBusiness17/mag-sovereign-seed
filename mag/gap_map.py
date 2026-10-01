"""Gap map — map the boundary between cheap-capable and frontier-required work.

Answers: "does it make sense to stack frontier asks until a complexity threshold, and can we
map that gap?" Yes for DEFERRABLE frontier-worthy work — but only if we can classify
cheap-capable vs frontier-required. This maps that boundary empirically from real queue
outcomes (cost_ledger): for each task shape, the cheap system's success rate + cost; where
cheap fails (low success) or is expensive, that's the FRONTIER GAP.

Also provides a STACK accumulator: frontier-worthy asks accumulate a complexity score; when
the stack crosses a threshold, signal "ready to batch-elevate to grok" (amortizes prompt-cache
+ stupidity tax).

Deterministic ($0, no LLM). Schema: gap_map.v1
CLI:  python -m mag.gap_map            (map the gap)
      python -m mag.gap_map --stack <complexity>   (accumulate a frontier-worthy ask)
      python -m mag.gap_map --stack-status
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
STACK_FILE = ROOT / "memory" / "runs" / "gap_map" / "stack.json"
SCHEMA = "gap_map.v1"

# Cheap success below this = frontier gap (cheap system can't reliably do it).
SUCCESS_BAR = 0.6
# Accumulated complexity at which to batch-elevate the frontier stack to grok.
STACK_THRESHOLD = 6.0


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


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    est = row.get("estimate") or {}
    act = row.get("actual") or {}
    val = row.get("value") or {}
    plat = row.get("platform") or {}
    return {
        "task_shape": est.get("depth") or "route",
        "provider": plat.get("provider") or est.get("seat"),
        "success": bool((row.get("outcome") or {}).get("success")),
        "usd": float(act.get("usd_est") or 0),
    }


def _is_cheap(provider: str) -> bool:
    p = str(provider or "").lower()
    return p in ("ollama", "deepseek", "deepseek_overmind")


def analyze(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Map the cheap-vs-frontier gap per task shape from real terminal outcomes."""
    all_rows = rows if rows is not None else _read_jsonl(COST_LEDGER)
    flat = [_flatten(r) for r in all_rows]

    # per task_shape: [n, cheap_success, cheap_n, cheap_usd]
    agg: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for f in flat:
        if not _is_cheap(f["provider"]):
            continue  # only cheap (local/deepseek) outcomes define the gap
        a = agg[f["task_shape"]]
        a[0] += 1
        a[1] += 1 if f["success"] else 0
        a[2] += f["usd"]
        a[3] += 0  # placeholder

    shapes = []
    for shape, (n, succ, usd, _p) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        if n < 2:
            continue
        rate = succ / n
        shapes.append({
            "task_shape": shape,
            "cheap_calls": int(n),
            "cheap_success_rate": round(rate, 3),
            "cheap_avg_usd": round(usd / n, 6),
            "frontier_gap": rate < SUCCESS_BAR,
        })
    shapes.sort(key=lambda s: (s["frontier_gap"], -s["cheap_success_rate"]))

    gap_shapes = [s["task_shape"] for s in shapes if s["frontier_gap"]]
    return {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "success_bar": SUCCESS_BAR,
        "cheap_capable_shapes": [s for s in shapes if not s["frontier_gap"]],
        "frontier_gap_shapes": [s for s in shapes if s["frontier_gap"]],
        "n_cheap_shapes": len(shapes),
        "n_frontier_gap": len(gap_shapes),
        "frontier_gap_names": gap_shapes,
        "recommendation": ("stack+batch-elevate frontier-gap shapes to grok; keep cheap for the rest"
                           if gap_shapes else "cheap system handles all observed shapes; no gap to stack"),
    }


# ---- STACK ACCUMULATOR -----------------------------------------------
def _load_stack() -> dict[str, Any]:
    if STACK_FILE.is_file():
        try:
            return json.loads(STACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"items": [], "complexity": 0.0}
    return {"items": [], "complexity": 0.0}


def stack_ask(goal: str, complexity: float = 1.0, *, threshold: float | None = None) -> dict[str, Any]:
    """Accumulate a frontier-worthy ask; when complexity crosses the threshold, signal batch-elevate."""
    thr = threshold if threshold is not None else STACK_THRESHOLD
    s = _load_stack()
    s.setdefault("items", []).append({"goal": (goal or "")[:200], "complexity": float(complexity),
                                      "at": datetime.now(timezone.utc).isoformat()})
    s["complexity"] = round(float(s.get("complexity") or 0) + float(complexity), 3)
    ready = s["complexity"] >= thr
    STACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    STACK_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "stack_complexity": s["complexity"], "threshold": thr,
            "items": len(s["items"]), "ready_to_batch_elevate": ready}


def stack_status() -> dict[str, Any]:
    s = _load_stack()
    return {"ok": True, "complexity": s.get("complexity", 0), "threshold": STACK_THRESHOLD,
            "items": len(s.get("items", [])),
            "ready_to_batch_elevate": float(s.get("complexity", 0)) >= STACK_THRESHOLD}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="gap-map", description="Map cheap-vs-frontier gap + frontier stack")
    ap.add_argument("--stack", type=float, metavar="COMPLEXITY", help="accumulate a frontier-worthy ask of this complexity")
    ap.add_argument("--stack-status", action="store_true", help="show frontier stack accumulation status")
    ap.add_argument("--stack-goal", default="", help="goal label for --stack")
    args = ap.parse_args(argv)
    if args.stack is not None:
        print(json.dumps(stack_ask(args.stack_goal or "frontier-worthy ask", args.stack), indent=2, default=str))
    elif args.stack_status:
        print(json.dumps(stack_status(), indent=2, default=str))
    else:
        print(json.dumps(analyze(), indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
