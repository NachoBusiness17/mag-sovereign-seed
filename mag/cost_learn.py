"""Cost/cache learning fold — analyze provider interactions and fold back into the system.

Deterministic ($0, no LLM). Reads the enriched provider seam (logs/provider_usage.jsonl now
carries cache_hit/miss, latency_ms, session_id), computes per-provider/model economics over a
window, writes a daily leaf, and folds cost-learning decisions into the skill_ledger so the
router gets case law on which provider/model is cheapest per hit ratio.

Tesuji shape: MEASURE (provider rows) -> FOLD (leaf + skill_ledger + behavioral_events)
-> APPLY (router reads case law). Idempotent via a last-fold timestamp.

CLI:  python -m mag.cost_learn [--hours 24] [--fold]
      python -m mag.cost_learn --cadence        (autorun-safe idempotent fold)

Schema: cost_learn.v1
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
STATE_DIR = ROOT / "memory" / "runs" / "cost_learn"
DAILY_DIR = ROOT / "memory" / "improve" / "daily"
STATE = STATE_DIR / "state.json"

SCHEMA = "cost_learn.v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _last_ts(rows: list[dict[str, Any]]) -> str:
    ts = [str(r.get("ts") or "") for r in rows]
    return max(ts) if ts else ""


def _rates() -> dict[str, dict[str, float]]:
    try:
        from mag.cache_map import MODEL_RATES
        return MODEL_RATES
    except Exception:
        return {}


def _priced(row: dict[str, Any], rates: dict[str, dict[str, float]]) -> float:
    """Accurate cost for a row that carries the cache split; else 0 (unpriced)."""
    if row.get("cache_hit_tokens") is None and row.get("cache_miss_tokens") is None:
        return 0.0
    rate = rates.get(str(row.get("model") or ""))
    if not rate:
        return 0.0
    h = int(row.get("cache_hit_tokens") or 0)
    m = int(row.get("cache_miss_tokens") or 0)
    o = int(row.get("completion_tokens") or 0)
    return h / 1e6 * rate["hit"] + m / 1e6 * rate["miss"] + o / 1e6 * rate["out"]


def analyze(*, hours: int = 24, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Compute per-provider/model economics over the last `hours` of interactions."""
    all_rows = rows if rows is not None else _read_jsonl(USAGE)
    cutoff = (_now() - timedelta(hours=hours)).isoformat()
    win = [r for r in all_rows if str(r.get("ts") or "") >= cutoff]

    rates = _rates()
    # model -> [calls, ok, prompt, comp, hit, miss, split_rows, latency_sum, usd]
    per_model: dict[str, list[float]] = defaultdict(lambda: [0.0] * 9)
    per_provider: dict[str, list[float]] = defaultdict(lambda: [0.0] * 9)
    for r in win:
        if str(r.get("provider") or "") in ("ollama", "test_provider"):
            continue
        m = str(r.get("model") or "?")
        p = str(r.get("provider") or "?")
        ok = 1 if r.get("ok") is True else 0
        prompt = int(r.get("prompt_tokens") or 0)
        comp = int(r.get("completion_tokens") or 0)
        hit = int(r.get("cache_hit_tokens") or 0)
        miss = int(r.get("cache_miss_tokens") or 0)
        lat = int(r.get("latency_ms") or 0)
        usd = _priced(r, rates)
        split = 1 if (r.get("cache_hit_tokens") is not None) else 0
        for b in (per_model[m], per_provider[p]):
            b[0] += 1; b[1] += ok; b[2] += prompt; b[3] += comp
            b[4] += hit; b[5] += miss; b[6] += split; b[7] += lat; b[8] += usd

    def entry(b: list[float]) -> dict[str, Any]:
        tin = b[4] + b[5]
        return {
            "calls": int(b[0]), "ok_calls": int(b[1]),
            "input_tokens": int(b[2]), "output_tokens": int(b[3]),
            "hit_tokens": int(b[4]), "miss_tokens": int(b[5]),
            "split_rows": int(b[6]),
            "avg_latency_ms": round(b[7] / b[0], 1) if b[0] else 0.0,
            "hit_ratio": round(b[4] / tin, 4) if tin else None,
            "priced_usd": round(b[8], 6),
        }

    models = sorted((entry(v) | {"model": k} for k, v in per_model.items()),
                    key=lambda x: -x["priced_usd"])
    providers = sorted((entry(v) | {"provider": k} for k, v in per_provider.items()),
                       key=lambda x: -x["priced_usd"])

    return {
        "schema": SCHEMA,
        "ts": _now().isoformat(),
        "window_hours": hours,
        "rows_in_window": len(win),
        "total_priced_usd": round(sum(e["priced_usd"] for e in models), 6),
        "by_model": models,
        "by_provider": providers,
        "spikes": _detect_spikes(win, rates),
    }


# STEAL (2026-08-11): cache-miss spike detection — make the 50x tax auto-surface.
# DeepSeek caches by PREFIX, time-windowed (~1h); a mid-context edit invalidates a long prefix at
# once -> a BURST of miss tokens. Detect hourly miss bursts (not per-call averages, which hide
# bursts). Deterministic + $0.
MISS_SPIKE_THRESHOLD = 100_000   # miss tokens in one hour bucket -> flag
MISS_RATIO_SPIKE = 0.20          # miss_ratio >= 20% in a bucket -> flag


def _detect_spikes(win: list[dict[str, Any]], rates: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """Bucket rows by UTC hour; flag buckets whose miss tokens / ratio are a spike (the 50x tax)."""
    from collections import defaultdict
    buckets: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])  # hit, miss, out
    for r in win:
        if str(r.get("provider") or "") in ("ollama", "test_provider"):
            continue
        if r.get("cache_hit_tokens") is None and r.get("cache_miss_tokens") is None:
            continue
        h = str(r.get("ts") or "")[:13]  # 'YYYY-MM-DDTHH'
        b = buckets[h]
        b[0] += int(r.get("cache_hit_tokens") or 0)
        b[1] += int(r.get("cache_miss_tokens") or 0)
        b[2] += int(r.get("completion_tokens") or 0)
    spikes = []
    for hour, (hit, miss, out) in sorted(buckets.items()):
        tin = hit + miss
        ratio = miss / tin if tin else 0.0
        if miss >= MISS_SPIKE_THRESHOLD or ratio >= MISS_RATIO_SPIKE:
            rate = rates.get("deepseek-v4-flash") or rates.get("deepseek") or {}
            est_waste = miss / 1e6 * (rate.get("miss", 0.14) - rate.get("hit", 0.0028))
            spikes.append({"hour": hour, "miss_tokens": int(miss), "hit_ratio": round(hit / tin, 4) if tin else None,
                           "est_waste_usd": round(est_waste, 4),
                           "likely_cause": "mid_context_edit" if ratio >= 0.05 else "cold_start"})
    return spikes


def render_leaf(a: dict[str, Any]) -> str:
    lines = [
        f"# Cost/Learn Leaf ({a['ts'][:10]})",
        "",
        f"- Window: last {a['window_hours']}h · {a['rows_in_window']} provider interactions · priced ${a['total_priced_usd']:.4f}",
        "",
        "## By provider",
        "",
        "| provider | calls | input_tok | hit_ratio | avg_lat_ms | priced_usd |",
        "|---|---|---|---|---|---|",
    ]
    for p in a["by_provider"]:
        hr = f"{p['hit_ratio']*100:.0f}%" if p["hit_ratio"] is not None else "n/a"
        lines.append(f"| {p['provider']} | {p['calls']} | {p['input_tokens']:,} | {hr} | {p['avg_latency_ms']} | ${p['priced_usd']:.4f} |")
    lines += ["", "## By model", "", "| model | provider-agnostic | calls | hit_ratio | priced_usd |", "|---|---|---|---|---|"]
    for e in a["by_model"]:
        hr = f"{e['hit_ratio']*100:.0f}%" if e["hit_ratio"] is not None else "n/a"
        lines.append(f"| {e['model']} | - | {e['calls']} | {hr} | ${e['priced_usd']:.4f} |")
    # STEAL (2026-08-11): cache-miss spikes visible in every leaf — the 50x tax auto-surfaces.
    if a.get("spikes"):
        lines += ["", "## Cache-miss spikes (50x tax)", "",
                  "| hour | miss_tokens | hit_ratio | est_waste_usd | likely_cause |", "|---|---|---|---|---|"]
        for s in a["spikes"]:
            hr = f"{s['hit_ratio']*100:.0f}%" if s["hit_ratio"] is not None else "n/a"
            lines.append(f"| {s['hour']} | {s['miss_tokens']:,} | {hr} | ${s['est_waste_usd']:.4f} | {s['likely_cause']} |")
    lines += ["", "## Fixed / subscription surfaces (no per-call token API)", "",
              "| surface | label | cost_kind | est |", "|---|---|---|---|"]
    try:
        from mag.cache_map import SUBSCRIPTIONS
        for s in SUBSCRIPTIONS:
            est = f"${s.get('est_usd_per_month', 0):.2f}/mo" if s.get("cost_kind") == "subscription" else f"${s.get('est_usd_per_run', 0):.2f}/run"
            lines.append(f"| {s['surface']} | {s['label']} | {s['cost_kind']} | {est} |")
    except Exception:
        pass
    return "\n".join(lines)


def fold(a: dict[str, Any]) -> dict[str, Any]:
    """Write the leaf + fold cost-learning decisions into the skill_ledger (deterministic)."""
    leaf = render_leaf(a)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    leaf_path = DAILY_DIR / f"cost-{a['ts'][:10]}.md"
    leaf_path.write_text(leaf, encoding="utf-8")

    folded = 0
    try:
        from mag.skill_ledger import record_decision
        for p in a["by_provider"][:6]:  # cap to avoid spam
            if p["calls"] < 3:
                continue
            hr = f"{p['hit_ratio']*100:.1f}%" if p["hit_ratio"] is not None else "n/a"
            record_decision(
                goal=f"cost_learning window {a['window_hours']}h",
                task_shape="cost_learning",
                provider=p["provider"],
                model="(aggregate)",
                outcome="ok",
                detail=f"calls={p['calls']} input={p['input_tokens']:,} hit={hr} "
                       f"lat={p['avg_latency_ms']}ms priced=${p['priced_usd']:.4f}",
                source="cost_learn",
            )
            folded += 1
    except Exception:
        pass

    # P3: feed the economics into the training pipeline as a labeled row so the
    # system's own cost/cache behavior becomes training signal, not just telemetry.
    try:
        from mag.skill_ledger import record_labeled_row
        record_labeled_row(
            text=leaf[:1500],
            label="cost_learning",
            classifier="deterministic",
            source="cost_learn",
        )
    except Exception:
        pass

    try:
        from mag.behavioral_analytics import log_behavioral_event
        log_behavioral_event(kind="cost_learn", detail=f"priced=${a['total_priced_usd']:.4f}")
    except Exception:
        pass

    # STEAL (2026-08-11): fold each cache-miss spike as a training signal so the 50x tax is never
    # invisible — the system learns its own cost bursts (cache-miss-spike detection).
    spike_folded = 0
    for s in a.get("spikes") or []:
        try:
            from mag.behavioral_analytics import log_behavioral_event
            log_behavioral_event(kind="cache_miss_spike",
                                 detail=f"hour={s['hour']} miss={s['miss_tokens']:,} "
                                        f"ratio={s['hit_ratio']} waste=${s['est_waste_usd']:.4f} "
                                        f"cause={s['likely_cause']}")
            spike_folded += 1
        except Exception:
            pass

    return {"ok": True, "leaf": str(leaf_path), "skill_ledger_decisions": folded,
            "spike_folded": spike_folded, "n_spikes": len(a.get("spikes") or [])}


def recent_cost_evidence(limit: int = 5) -> dict[str, Any]:
    """Read recent cost_learn skill_ledger decisions into compact routing evidence.

    This is the APPLY half of the tesuji loop: the router (model_pick/self_drive) reads
    measured provider economics instead of guessing. Deterministic, $0.
    """
    led = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
    rows = []
    if led.is_file():
        for line in led.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            if "cost_learn" not in line or '"source": "cost_learn"' not in line:
                continue
            try:
                rows.append(json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
    by_provider: dict[str, list[float]] = defaultdict(lambda: [0.0] * 3)  # calls, priced_usd, hit_pct
    for r in rows[-limit:]:
        prov = str(r.get("provider") or "")
        try:
            calls = float(r.get("detail", "").split("calls=")[1].split(" ")[0]) if "calls=" in str(r.get("detail")) else 0.0
        except Exception:
            calls = 0.0
        by_provider[prov][0] += calls
    evidence = []
    for prov, b in sorted(by_provider.items(), key=lambda kv: -kv[1][0]):
        evidence.append({"provider": prov, "calls": int(b[0])})
    return {"source": "cost_learn", "providers": evidence, "n": len(evidence)}


def run_cadence(*, hours: int = 24) -> dict[str, Any]:
    """Idempotent fold for the autorun loop: only fold if new usage rows exist since last fold."""
    rows = _read_jsonl(USAGE)
    last = ""
    if STATE.is_file():
        try:
            last = (json.loads(STATE.read_text(encoding="utf-8")) or {}).get("last_ts") or ""
        except Exception:
            last = ""
    cur = _last_ts(rows)
    if cur and cur <= last:
        return {"ok": True, "action": "skip", "reason": "no_new_usage_since_last_fold"}
    a = analyze(hours=hours, rows=rows)
    f = fold(a)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_ts": cur, "folded_at": _now().isoformat()}, indent=2), encoding="utf-8")
    return {"ok": True, "action": "folded", "analysis": a, "fold": f}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="cost-learn", description="Cost/cache learning fold")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--fold", action="store_true", help="also write leaf + skill_ledger")
    ap.add_argument("--cadence", action="store_true", help="idempotent autorun fold")
    args = ap.parse_args(argv)
    if args.cadence:
        res = run_cadence(hours=args.hours)
    else:
        a = analyze(hours=args.hours)
        res = a
        if args.fold:
            res["fold"] = fold(a)
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
