"""cache_router — interrupt-aware cache-preservation routing (the 50x shrink).

CONSUMES what we already built:
  * invariant.py    — the byte-stable prefix (SEPARATE/PIN/VERIFY). prefix_stable = invariant.check().
  * cache_map.py    — MODEL_RATES (hit/miss/out) + real hit ratio + is_remote on provider_usage.jsonl.
  * behavioral_analytics — the edit/interrupt pattern (minute behavioral signals).

THE DECISION (per turn):
  * prefix STABLE + edit is APPEND (late)  -> call DeepSeek at cache-HIT economics (50x flash / 30x pro saved; pro corrected 2026-09-25 from the stale 120x, pre-Sept-10 pricing table).
  * prefix VOLATILE / edit is EARLY/MID    -> route the volatile tail to a cheap/free tier (ollama /
    grok_free / free) so the invalidated region is NEVER paid at the 50x miss rate.

PROOF (the deliverable):
  audit()    — real cost split on provider_usage.jsonl: hit/miss tokens, hit ratio, actual cost vs
               cost-if-all-hit, and the "50x waste" = the miss-token penalty actually paid.
  simulate() — replay the log under the router: estimate what routing volatile rows to free saves
               (the 50x region shrinks).

Schema: cache_router.v1 · deterministic · $0
CLI: python -m mag.cache_router audit | route "<goal>" [--edit append|early|mid] [--tail N] |
                            simulate | status
"""
from __future__ import annotations

import argparse
import json
import sys
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

SCHEMA = "cache_router.v1"
USAGE = ROOT / "logs" / "provider_usage.jsonl"
FREE_MODEL = "ollama"          # cheap/free leg for the volatile tail


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_usage() -> list[dict[str, Any]]:
    if not USAGE.is_file():
        return []
    out = []
    for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _rates() -> dict[str, dict[str, float]]:
    try:
        from mag.cache_map import MODEL_RATES
        return MODEL_RATES
    except Exception:
        return {}


def _is_remote(r: dict[str, Any]) -> bool:
    try:
        from mag.cache_map import is_remote
        return bool(is_remote(r))
    except Exception:
        return bool(r.get("ok")) and (r.get("prompt_tokens") or 0) > 0


def _prefix_stable() -> bool | None:
    """Is the session prefix byte-stable right now? (invariant.check)."""
    try:
        from mag.invariant import check
        c = check()
        return bool(c.get("stable")) if isinstance(c, dict) else None
    except Exception:
        return None


def _row_cost(r: dict[str, Any], rates: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Cost of one usage row using per-model hit/miss/out rates. Returns hit/miss tokens + cost.

    FIX (2026-08-16): rows WITHOUT a recorded cache split (cache_hit_tokens / cache_miss_tokens
    absent — local, openrouter, gemini, early deepseek rows) were treated as 100% cache MISS
    (miss = prompt_tokens), inflating the miss count ~500x and tanking hit_ratio to ~6.6% when the
    real DeepSeek bill is ~98% hit. Now only rows that RECORD the split contribute hit/miss; the
    rest are unpriced for input (billing is authoritative, matching cache_map.row_split)."""
    model = str(r.get("model") or r.get("provider") or "deepseek-chat")
    rt = rates.get(model) or rates.get("deepseek-chat") or {"hit": 0.14, "miss": 0.14, "out": 0.28}
    has_split = (r.get("cache_hit_tokens") is not None) or (r.get("cache_miss_tokens") is not None)
    if has_split:
        hit = int(r.get("cache_hit_tokens") or 0)
        miss = int(r.get("cache_miss_tokens") or 0)
    else:
        hit = miss = 0  # no recorded split -> do NOT fabricate a miss
    out = int(r.get("completion_tokens") or 0)
    cost = hit / 1e6 * rt["hit"] + miss / 1e6 * rt["miss"] + out / 1e6 * rt["out"]
    return {"hit": hit, "miss": miss, "out": out, "cost": round(cost, 6),
            "hit_rate": rt["hit"], "miss_rate": rt["miss"], "has_split": has_split}


def audit() -> dict[str, Any]:
    """Real cost + cache-waste on provider_usage.jsonl. Proves where the 50x region is.

    Honest split (FIX 2026-08-16): hit_ratio is computed ONLY on rows that RECORD a cache split.
    Rows without cache_hit/miss fields are unpriced for input (billing is authoritative), so they
    can no longer fake a ~500x miss that buried the real ~98% DeepSeek hit rate."""
    rows = _read_usage()
    rates = _rates()
    remote = [r for r in rows if _is_remote(r)]
    tot_hit = tot_miss = tot_out = 0
    split_rows = 0
    unpriced_input = 0
    cost_actual = cost_if_hit = 0.0
    by_model: dict[str, dict[str, Any]] = {}
    for r in remote:
        c = _row_cost(r, rates)
        tot_hit += c["hit"]; tot_miss += c["miss"]; tot_out += c["out"]
        if c["has_split"]:
            split_rows += 1
        else:
            unpriced_input += int(r.get("prompt_tokens") or 0)
        cost_actual += c["cost"]
        cost_if_hit += (c["hit"] + c["miss"]) / 1e6 * c["hit_rate"] + c["out"] / 1e6 * 0.28
        b = by_model.setdefault(str(r.get("model") or r.get("provider")), {"hit": 0, "miss": 0, "cost": 0.0})
        b["hit"] += c["hit"]; b["miss"] += c["miss"]; b["cost"] += c["cost"]
    hit_ratio = round(tot_hit / max(1, tot_hit + tot_miss), 4)
    # 50x waste = extra paid because miss tokens weren't hits (hit_rate vs miss_rate)
    waste = 0.0
    for m, b in by_model.items():
        rt = rates.get(m) or rates.get("deepseek-chat") or {"hit": 0.14, "miss": 0.14, "out": 0.28}
        waste += b["miss"] / 1e6 * (rt["miss"] - rt["hit"])
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "remote_rows": len(remote),
            "split_rows": split_rows,
            "hit_tokens": tot_hit, "miss_tokens": tot_miss, "output_tokens": tot_out,
            "hit_ratio": hit_ratio,
            "unpriced_input_tokens": unpriced_input,
            "cost_actual_usd": round(cost_actual, 6),
            "cost_if_all_hit_usd": round(cost_if_hit, 6),
            "fifty_x_waste_usd": round(waste, 6),
            "by_model": {m: {"hit": b["hit"], "miss": b["miss"], "cost": round(b["cost"], 6)} for m, b in by_model.items()},
            "note": "hit_ratio computed ONLY on rows that record a cache split (split_rows); rows without a split are unpriced for input (billing authoritative). fifty_x_waste = extra paid because cache-miss tokens billed at miss rate vs hit rate."}


def route(goal: str = "", *, edit: str = "append", tail_tokens: int = 0,
          prefix_stable: bool | None = None) -> dict[str, Any]:
    """Per-turn decision: DeepSeek at cache-hit economics, OR route the volatile tail to free/local."""
    stable = _prefix_stable() if prefix_stable is None else prefix_stable
    edit = (edit or "append").lower()
    mid = edit in ("early", "mid")
    if (stable is not False) and not mid:
        # prefix is byte-stable AND edit is append-only -> cache-hit economics (50x saved)
        cost = tail_tokens / 1e6 * 0.0028  # flash hit rate
        return {"ok": True, "schema": SCHEMA, "provider": "deepseek", "model": "deepseek-v4-flash",
                "cache_hit": True, "cost_est_usd": round(cost, 6), "prefix_stable": stable,
                "rationale": "stable prefix + append -> DeepSeek cache-hit (50x saved)"}
    # volatile: mid-context edit or prefix drifted -> don't pay the 50x miss on the tail
    return {"ok": True, "schema": SCHEMA, "provider": "local", "model": FREE_MODEL,
            "cache_hit": False, "cost_est_usd": 0.0, "prefix_stable": stable,
            "rationale": f"volatile({edit})/prefix-stable={stable} -> route tail to {FREE_MODEL}, avoid 50x miss",
            "avoided_50x_tokens": tail_tokens}


def simulate(*, free_tail_tokens: int = 0) -> dict[str, Any]:
    """Replay the real log under the router: how much the 50x region shrinks if volatile rows go free."""
    a = audit()
    rates = _rates()
    # assume rows with low hit ratio (miss-heavy) are the 'volatile' ones the router would route to free
    volatile_miss = 0
    for r in _read_usage():
        if not _is_remote(r):
            continue
        c = _row_cost(r, rates)
        if c["miss"] > 0 and c["hit"] == 0:  # fully-invalidated = volatile
            volatile_miss += c["miss"]
    saved = volatile_miss / 1e6 * 0.14  # what we'd save by not paying flash miss on those tokens
    return {"ok": True, "schema": SCHEMA, "audit": a,
            "volatile_miss_tokens": volatile_miss,
            "router_saves_usd": round(saved, 6),
            "note": "volatile = rows with cache-miss but no cache-hit (invalidated prefix) -> routed to free"}


def status() -> dict[str, Any]:
    a = audit()
    return {"ok": True, "schema": SCHEMA, "usage_file": str(USAGE),
            "remote_rows": a["remote_rows"], "hit_ratio": a["hit_ratio"],
            "fifty_x_waste_usd": a["fifty_x_waste_usd"], "prefix_stable_now": _prefix_stable()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cache_router", description="interrupt-aware cache-preservation router")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("audit")
    r = sub.add_parser("route"); r.add_argument("goal", nargs="*", default=[])
    r.add_argument("--edit", default="append"); r.add_argument("--tail", type=int, default=0)
    sub.add_parser("simulate")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "audit":
        print(json.dumps(audit(), indent=2, ensure_ascii=False))
    elif a.cmd == "route":
        print(json.dumps(route(" ".join(a.goal), edit=a.edit, tail_tokens=a.tail), indent=2, ensure_ascii=False))
    elif a.cmd == "simulate":
        print(json.dumps(simulate(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
