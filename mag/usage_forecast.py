"""Usage forecast + calibration — estimate usage from the right-size engine, then verify.

The operator's insight: we right-size EVERY ask (model + depth + assembled context), so we know
exactly what we pass to each provider BEFORE the API call. So we can:

  1. ESTIMATE upfront: run each ask through self_drive.plan -> real model + context_chars,
     convert chars->tokens, price per model (MODEL_RATES), aggregate over the queue.
  2. CALIBRATE: compare projection vs actual provider_usage to learn our own bias (tesuji)
     -> a per-model correction factor, so the estimator gets better over time.
  3. RESEARCH: use this + the live APIs to test how best to feed models complex data
     (context strategies) — see the enqueued research pack.

Deterministic ($0, no LLM beyond the router's own deterministic planning).

CLI:  python -m mag.usage_forecast goal "<goal>"        (one ask)
      python -m mag.usage_forecast queue                 (forecast pending queue goals)
      python -m mag.usage_forecast calibrate             (projection vs actual bias)
Schema: usage_forecast.v1
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import ROOT

USAGE = ROOT / "logs" / "provider_usage.jsonl"
CHARS_PER_TOKEN = 4.0

# Estimated output tokens by router model_shape (deterministic planning defaults).
SHAPE_OUT = {"cheap": 400, "balanced": 700, "heavy": 1800, "reasoning": 1400}

# Typical input cache-hit ratio per provider for the cache-adjusted estimate (deepseek verified).
TYPICAL_HIT = {"deepseek": 0.97, "deepseek_overmind": 0.97, "xai": 0.5, "openai": 0.3,
               "github_models": 0.3, "groq": 0.3, "gemini": 0.3, "openrouter": 0.3}

SCHEMA = "usage_forecast.v1"


def _rates() -> dict[str, dict[str, float]]:
    try:
        from mag.cache_map import MODEL_RATES
        return MODEL_RATES
    except Exception:
        return {}


def _shared_context_chars() -> int:
    """Compute the assembled context size once (same frozen prefix across a batch)."""
    try:
        from mag.self_drive import cached_context
        return len((cached_context("") or {}).get("text") or "")
    except Exception:
        return 0


def estimate_ask(goal: str, agent_state: str | None = None,
                 ctx_chars: int | None = None) -> dict[str, Any]:
    """Estimate one ask using the real right-size engine output (model + context_chars)."""
    if ctx_chars is None:
        from mag.self_drive import plan

        p = plan(goal, agent_state=agent_state)
        if not p.get("ok"):
            return {"ok": False, "goal": goal[:200], "error": p.get("error") or "plan failed"}
        model = str(p.get("model") or "?")
        shape = str(p.get("model_shape") or "balanced")
        cchars = int(p.get("context_chars") or 0)
        redraft = str(p.get("redrafted_prompt") or "")
    else:
        # Cheap batch path: model/shape from the router only (no full context rebuild).
        from mag.model_pick import recommend_model
        rec = recommend_model(goal)
        model = str(rec.get("model") or "?")
        shape = str(rec.get("model_shape") or "balanced")
        cchars = ctx_chars
        from mag.self_drive import redraft as _redraft
        redraft = _redraft(goal, model_shape=shape)

    input_tok = int((cchars + len(redraft)) / CHARS_PER_TOKEN)
    output_tok = int(SHAPE_OUT.get(shape, 700))

    rates = _rates()
    rate = rates.get(model)
    usd_miss = 0.0
    usd_typical = 0.0
    if rate:
        hit_ratio = TYPICAL_HIT.get("deepseek", 0.5)
        usd_miss = (input_tok / 1e6 * rate["miss"]) + (output_tok / 1e6 * rate["out"])
        usd_typical = (input_tok / 1e6 * (rate["hit"] * hit_ratio + rate["miss"] * (1 - hit_ratio))) \
            + (output_tok / 1e6 * rate["out"])

    return {
        "ok": True,
        "goal": goal[:200],
        "agent_state": agent_state,
        "model": model,
        "model_shape": shape,
        "context_chars": cchars,
        "input_tokens_est": input_tok,
        "output_tokens_est": output_tok,
        "usd_est_miss": round(usd_miss, 6),
        "usd_est_typical": round(usd_typical, 6),
        "source": "right_size_engine",
    }


def forecast(goals: list[str], agent_state: str | None = None) -> dict[str, Any]:
    """Aggregate per-ask estimates over a list of goals -> per-model/global projection."""
    # Compute the shared frozen-prefix context size once (it's ~constant across a batch).
    ctx_chars = _shared_context_chars() or None
    per_model: dict[str, list[float]] = defaultdict(lambda: [0.0] * 4)  # input, out, usd_miss, usd_typical
    asks = []
    for g in goals:
        if not (g or "").strip():
            continue
        e = estimate_ask(g, agent_state=agent_state, ctx_chars=ctx_chars)
        if not e.get("ok"):
            continue
        asks.append(e)
        b = per_model[e["model"]]
        b[0] += e["input_tokens_est"]
        b[1] += e["output_tokens_est"]
        b[2] += e["usd_est_miss"]
        b[3] += e["usd_est_typical"]
    models = [{"model": k, "input_tokens_est": int(v[0]), "output_tokens_est": int(v[1]),
               "usd_est_miss": round(v[2], 6), "usd_est_typical": round(v[3], 6), "asks": sum(
                   1 for a in asks if a["model"] == k)}
              for k, v in per_model.items()]
    models.sort(key=lambda x: -x["usd_est_typical"])
    return {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "asks": len(asks),
        "input_tokens_est": sum(m["input_tokens_est"] for m in models),
        "output_tokens_est": sum(m["output_tokens_est"] for m in models),
        "usd_est_miss": round(sum(m["usd_est_miss"] for m in models), 6),
        "usd_est_typical": round(sum(m["usd_est_typical"] for m in models), 6),
        "by_model": models,
    }


def queue_goals(limit: int = 60) -> list[str]:
    """Pull real pending goals from the orchestrator queue."""
    out = []
    try:
        from mag.orchestrator import list_queue
        for q in list_queue(limit=limit):
            g = str(q.get("goal") or "").strip()
            if g and q.get("status") in ("queued", "running"):
                out.append(g)
    except Exception:
        pass
    return out


def queue_forecast(limit: int = 60) -> dict[str, Any]:
    """Forecast the currently queued work (the pipeline we're about to send)."""
    goals = queue_goals(limit=limit)
    f = forecast(goals)
    f["source"] = "queue"
    f["goal_count"] = len(goals)
    return f


def calibrate(*, hours: int = 24, goals: list[str] | None = None) -> dict[str, Any]:
    """Project a goal set and compare to actual provider_usage to learn projection bias.

    Statistical/aggregate (per-model), since per-ask goal linkage needs the session_id we
    now capture — this is the honest calibration surface. Returns a per-model correction
    factor (projected_input / actual_prompt) to apply to future forecasts.
    """
    goal_src = goals if goals is not None else queue_goals(limit=60)
    proj = forecast(goal_src)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    actual: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # model -> [prompt_tokens, out]
    if USAGE.is_file():
        for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if str(r.get("ts") or "") < cutoff:
                continue
            if str(r.get("provider") or "") in ("ollama", "test_provider"):
                continue
            m = str(r.get("model") or "?")
            actual[m][0] += int(r.get("prompt_tokens") or 0)
            actual[m][1] += int(r.get("completion_tokens") or 0)
    factors = []
    for pm in proj["by_model"]:
        a = actual.get(pm["model"])
        if not a or a[0] <= 0:
            continue
        ratio = pm["input_tokens_est"] / a[0]
        factors.append({"model": pm["model"], "projected_input": pm["input_tokens_est"],
                        "actual_prompt": int(a[0]), "correction_factor": round(ratio, 4)})
    return {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "goals_projected": len(goal_src),
        "by_model_correction": factors,
        "note": "correction_factor = projected_input/actual_prompt; <1 means we over-project "
                "(context_chars overstates), >1 means under-project. Apply to future forecasts.",
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="usage-forecast", description="Right-size-based usage forecast + calibration")
    sub = ap.add_subparsers(dest="cmd")
    p_goal = sub.add_parser("goal", help="estimate one ask")
    p_goal.add_argument("goal", nargs="+")
    p_goal.add_argument("--agent-state", default=None)
    sub.add_parser("queue", help="forecast pending queue goals")
    p_cal = sub.add_parser("calibrate", help="projection vs actual bias")
    p_cal.add_argument("--hours", type=int, default=24)
    args = ap.parse_args(argv)
    if args.cmd == "goal":
        print(json.dumps(estimate_ask(" ".join(args.goal), agent_state=args.agent_state), indent=2, default=str))
    elif args.cmd == "queue":
        print(json.dumps(queue_forecast(), indent=2, default=str))
    elif args.cmd == "calibrate":
        print(json.dumps(calibrate(hours=args.hours), indent=2, default=str))
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
