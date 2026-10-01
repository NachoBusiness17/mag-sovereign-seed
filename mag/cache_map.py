"""Cache/economy map — attribute DeepSeek cache hit/miss onto verkle-anchored sessions.

Joins two existing deterministic stores (no LLM, $0):
  - logs/provider_usage.jsonl  (real deepseek rows carry cache_hit_tokens / cache_miss_tokens)
  - memory/biography/verkle_chain.jsonl  (421 sessions, each with [start_minute,end_minute] + dominant_theme)

A usage row's timestamp is bucketed into the verkle session whose [start,end] window contains it,
so cost + cache-waste is mapped onto the verkle knot's theme graph. Where no session window matches
(e.g. dashboard/interactive chat not part of a knot session) it's bucketed as "unmapped".

Flash rates (configs/cost_rates.yaml + DeepSeek pricing page):
  input cache-hit  $0.0028/M   input cache-miss $0.14/M   output $0.28/M

CLI:  python -m mag.cache_map            -> print the map (json)
      python -m mag.cache_map --write    -> also persist memory/runs/cache_map/<ts>/MAP.md + map.json

Schema: cache_map.v1
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

USAGE = ROOT / "logs" / "provider_usage.jsonl"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
TIP = ROOT / "memory" / "biography" / "verkle_tip.json"
OUT_DIR = ROOT / "memory" / "runs" / "cache_map"

# Per-model USD/M rates (input hit/miss + output). Verified for DeepSeek from real billing;
# other providers are public list/approx (cost_rates.yaml is the seat-level fallback).
MODEL_RATES = {
    # DeepSeek (verified from billing line items 2026-08-09)
    "deepseek-v4-flash": {"hit": 0.0028, "miss": 0.14, "out": 0.28},
    "deepseek-v4-pro": {"hit": 0.003625, "miss": 0.435, "out": 0.87},
    "deepseek-chat": {"hit": 0.14, "miss": 0.14, "out": 0.28},  # legacy alias
    # xAI / Grok (cached <200k: $0.30/$2; output $6)
    "grok-4.5": {"hit": 0.30, "miss": 2.0, "out": 6.0},
    "grok-4-latest": {"hit": 0.30, "miss": 2.0, "out": 6.0},
    "grok-3": {"hit": 0.30, "miss": 2.0, "out": 6.0},
    "grok-3-mini": {"hit": 0.30, "miss": 2.0, "out": 6.0},
    # OpenAI / Codex
    "gpt-4o-mini": {"hit": 0.30, "miss": 0.30, "out": 1.20},
    "gpt-4o": {"hit": 2.50, "miss": 2.50, "out": 10.0},
    # Anthropic / Claude (sonnet 4 / haiku 3.5)
    "claude-sonnet-4-20250514": {"hit": 3.0, "miss": 3.0, "out": 15.0},
    "claude-3-5-haiku-20241022": {"hit": 0.80, "miss": 0.80, "out": 4.0},
    "claude-3-5-sonnet-20241022": {"hit": 3.0, "miss": 3.0, "out": 15.0},
    # GitHub Models / Copilot free tier
    "Meta-Llama-3.3-70B-Instruct": {"hit": 0.30, "miss": 0.30, "out": 0.90},
    # Groq (llama chat names retired in the 09-24 contraction; prices from the
    # models API pricing field, per MTok: prompt / completion / input_cache_read)
    "openai/gpt-oss-120b": {"hit": 0.075, "miss": 0.15, "out": 0.60},
    "openai/gpt-oss-20b": {"hit": 0.0375, "miss": 0.075, "out": 0.30},
    # Google / Gemini
    "gemini-2.0-flash": {"hit": 0.10, "miss": 0.10, "out": 0.40},
    "gemini-1.5-flash": {"hit": 0.075, "miss": 0.075, "out": 0.30},
    # OpenRouter / catch-all
    "openrouter/auto": {"hit": 0.50, "miss": 0.50, "out": 1.50},
}

SCHEMA = "cache_map.v1"

# Fixed/subscription surfaces with NO per-call token API (Copilot chat, Codex CLI, Cursor).
# Tracked as fixed/subscription cost so they appear in the map instead of being invisible.
SUBSCRIPTIONS = [
    {"surface": "cursor", "label": "Cursor Composer", "cost_kind": "fixed_per_call",
     "est_usd_per_run": 0.15, "note": "subscription/seat; no per-call token API"},
    {"surface": "copilot", "label": "GitHub Copilot chat", "cost_kind": "subscription",
     "est_usd_per_month": 10.0, "note": "no per-call token API"},
    {"surface": "codex", "label": "OpenAI Codex CLI", "cost_kind": "fixed_per_call",
     "est_usd_per_run": 0.05, "note": "no public token breakdown"},
]

# Authoritative ground truth per provider where we have it (from billing exports).
BILLING_AUTH = {
    "deepseek": {
        "date": "2026-08-09", "hit_ratio": 0.970, "usd_per_day": 1.34,
        "source": "DeepSeek billing export (operator pasted 2026-08-09)",
    },
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _iso_min(ts: str | None) -> str:
    """Normalize an ISO-ish timestamp to 'YYYY-MM-DDTHH:MM' for window comparison."""
    if not ts:
        return ""
    t = (ts or "").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return (ts or "")[:16]
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def latest_rows_per_session(chain_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest-per-session resolution for v2 append-leaves chains (AH19, 2026-09-30).

    v1: one row per session (amend-in-place) — this is the identity (input
    returned unchanged). v2: a re-save APPENDS a new (session_id, session_seq)
    row, so one session spans multiple rows; the time-window join and session
    counts must read the session's LATEST row only (last matching row in chain
    order — the same rule as verkle_knot.latest_leaf_for_session's fallback),
    or one session double-counts as N windows / N sessions and a stale earlier
    window shadows the live one (VERKLE_V2_DECISION.md §2.2). Rows with no
    session_id pass through in place (each is its own entry).
    """
    latest: dict[str, dict[str, Any]] = {}
    for r in chain_rows:
        sid = str(r.get("session_id") or "")
        if sid:
            latest[sid] = r  # chain is append-ordered: last occurrence wins
    if len(latest) == len(chain_rows):
        return chain_rows  # pure v1 (no duplicate sids): byte-identical behavior
    out: list[dict[str, Any]] = []
    emitted: set[str] = set()
    for r in chain_rows:
        sid = str(r.get("session_id") or "")
        if not sid:
            out.append(r)
        elif sid not in emitted and latest.get(sid) is r:
            out.append(r)
            emitted.add(sid)
    return out


def is_remote(r: dict[str, Any]) -> bool:
    """Any real, non-local provider call worth pricing (excludes ollama + tests)."""
    prov = str(r.get("provider") or "")
    if prov in ("ollama", "test_provider"):
        return False
    if (r.get("meta") or {}).get("test"):
        return False
    if r.get("ok") is not True:
        return False
    return (int(r.get("prompt_tokens") or 0) + int(r.get("completion_tokens") or 0)) > 0


def recent_hit_ratio(rows: list[dict[str, Any]] | None = None) -> float:
    """Real cache hit ratio from the most recent provider usage split rows. Falls back to
    the billing-authoritative ratio when no split rows are captured. Consumed by
    right_size_skills._cache_likely (previously a dead import -> always True)."""
    rows = rows if rows is not None else _read_jsonl(USAGE)
    split = [r for r in rows if is_remote(r)
             and r.get("cache_hit_tokens") is not None
             and r.get("cache_miss_tokens") is not None]
    if split:
        h = sum(int(r.get("cache_hit_tokens") or 0) for r in split)
        m = sum(int(r.get("cache_miss_tokens") or 0) for r in split)
        if (h + m) > 0:
            return round(h / (h + m), 4)
    for prov, b in (BILLING_AUTH or {}).items():
        hr = b.get("hit_ratio")
        if hr is not None:
            return float(hr)
    return 0.0


def _bucket(ts: str, sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the verkle session whose [start,end] window contains ts (last match wins)."""
    key = _iso_min(ts)
    if not key:
        return None
    for s in sessions:  # chain is append-ordered; last match wins
        start = _iso_min(s.get("start_minute"))
        end = _iso_min(s.get("end_minute"))
        if start and end and start <= key <= end:
            return s
    return None


def build_map(*, usage_rows: list[dict[str, Any]] | None = None,
              chain_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = usage_rows if usage_rows is not None else _read_jsonl(USAGE)
    raw_chain = chain_rows if chain_rows is not None else _read_jsonl(CHAIN)
    # AH19 (2026-09-30) rows!=sessions: under v2 append-leaves one session
    # spans multiple rows; the window join and session counts read the LATEST
    # row per session only (identity on v1 chains). raw row count is kept in
    # the output — rows and sessions are different denominators (census law).
    chain = latest_rows_per_session(raw_chain)
    rows_remote = [r for r in rows if is_remote(r)]

    # Precompute session windows ONCE.  The old bucket() linearly scanned every
    # verkle window for every usage row (31k x 2.4k on this checkout), turning a
    # read-only cache map into an accidental quadratic workload.  Build a
    # sweep-line index instead: usage timestamps are sorted once, windows enter
    # by start time, and a max-heap preserves the original "last match wins"
    # rule for overlapping sessions.
    windows: list[tuple[str, str, str, int]] = []
    for ordinal, s in enumerate(chain):
        start = _iso_min(s.get("start_minute"))
        end = _iso_min(s.get("end_minute"))
        if start and end:
            windows.append((start, end, str((s or {}).get("dominant_theme") or "unmapped"), ordinal))
    windows.sort(key=lambda w: (w[0], w[3]))

    row_keys = {_iso_min(r.get("ts", "")) for r in rows_remote}
    row_keys.discard("")
    window_cursor = 0
    active: list[tuple[int, str, str]] = []
    bucket_by_key: dict[str, str] = {}
    for key in sorted(row_keys):
        while window_cursor < len(windows) and windows[window_cursor][0] <= key:
            start, end, theme, ordinal = windows[window_cursor]
            if end >= start:
                heapq.heappush(active, (-ordinal, end, theme))
            window_cursor += 1
        while active and active[0][1] < key:
            heapq.heappop(active)
        bucket_by_key[key] = active[0][2] if active else ""

    def bucket(ts: str) -> str:
        return bucket_by_key.get(_iso_min(ts), "")

    def row_split(r):
        """Return (hit, miss) if this row carries the cache split, else None."""
        h = r.get("cache_hit_tokens")
        m = r.get("cache_miss_tokens")
        if h is None and m is None:
            return None
        return (int(h or 0), int(m or 0))

    # theme bucket: prompt_in, out, calls, hit, miss, split_rows
    by_theme: dict[str, list[float]] = defaultdict(lambda: [0.0] * 6)
    # provider bucket: prompt_in, out, calls, hit, miss, split_rows, usd(accurate, split-only), all_miss_usd
    by_provider: dict[str, list[float]] = defaultdict(lambda: [0.0] * 8)
    unmapped = [0.0] * 6
    for r in rows_remote:
        prompt = int(r.get("prompt_tokens") or 0)
        outc = int(r.get("completion_tokens") or 0)
        sp = row_split(r)
        hit = miss = 0
        if sp:
            hit, miss = sp
        theme = bucket(r.get("ts", ""))
        b = by_theme[theme] if theme else unmapped
        b[0] += prompt
        b[1] += outc
        b[2] += 1
        if sp:
            b[3] += hit
            b[4] += miss
            b[5] += 1
        pb = by_provider[str(r.get("provider") or "?")]
        pb[0] += prompt
        pb[1] += outc
        pb[2] += 1
        rate = MODEL_RATES.get(str(r.get("model") or ""))
        if sp and rate:
            pb[3] += hit
            pb[4] += miss
            pb[5] += 1
            pb[6] += hit / 1e6 * rate["hit"] + miss / 1e6 * rate["miss"] + outc / 1e6 * rate["out"]
            pb[7] += (hit + miss) / 1e6 * rate["miss"] + outc / 1e6 * rate["out"]

    def hit_ratio_of(b):
        tin = b[3] + b[4]
        return round(b[3] / tin, 4) if tin else 0.0

    themes = []
    for theme, b in sorted(by_theme.items(), key=lambda kv: -kv[1][0]):
        themes.append({
            "theme": theme,
            "calls": int(b[2]),
            "input_tokens": int(b[0]),
            "output_tokens": int(b[1]),
            "hit_tokens": int(b[3]),
            "miss_tokens": int(b[4]),
            "split_rows": int(b[5]),
            "split_hit_ratio": hit_ratio_of(b),
        })

    th = sum(b[0] for b in by_theme.values())
    to = sum(b[1] for b in by_theme.values())
    sp_h = sum(b[3] for b in by_theme.values())
    sp_m = sum(b[4] for b in by_theme.values())
    sp_n = sum(b[5] for b in by_theme.values())
    # Fold unmapped into totals.
    th += unmapped[0]; to += unmapped[1]; sp_h += unmapped[3]; sp_m += unmapped[4]; sp_n += unmapped[5]
    total_calls = sum(b[2] for b in by_theme.values()) + unmapped[2]

    def prov_hr(b):
        tin = b[3] + b[4]
        return round(b[3] / tin, 4) if tin else None

    providers = []
    for prov, b in sorted(by_provider.items(), key=lambda kv: -kv[1][0]):
        auth = (BILLING_AUTH or {}).get(prov)
        providers.append({
            "provider": prov,
            "calls": int(b[2]),
            "input_tokens": int(b[0]),
            "output_tokens": int(b[1]),
            "split_rows": int(b[5]),
            "hit_ratio": prov_hr(b),
            "priced_usd": round(b[6], 6),
            "if_all_miss_usd": round(b[7], 6),
            "billing_authoritative": auth,
        })

    tip = {}
    if TIP.is_file():
        try:
            tip = json.loads(TIP.read_text(encoding="utf-8"))
        except Exception:
            tip = {}

    return {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "verkle": {
            "n_sessions": len(chain),
            "n_chain_rows": len(raw_chain),
            "note": ("n_sessions is latest-row-per-session (AH19 v2 append-leaves); "
                     "n_chain_rows is the raw chain length — different denominators"),
            "n_leaves": int(tip.get("n_leaves") or 0),
            "root": tip.get("root") or "",
            "root_short": tip.get("root_short") or (tip.get("root") or "")[:16],
        },
        "ledger": {
            "calls": int(total_calls),
            "input_tokens": int(th),
            "output_tokens": int(to),
            "split_rows": int(sp_n),
            "split_hit_ratio": round(sp_h / (sp_h + sp_m), 4) if (sp_h + sp_m) else None,
            "split_coverage": round((sp_h + sp_m) / th, 4) if th else 0.0,
            "note": "input_tokens is real (prompt_tokens, all rows); hit/miss split only captured on "
                    "split_rows; authoritative figures from billing block where present.",
        },
        "billing": BILLING_AUTH,
        "by_theme": themes,
        "by_provider": providers,
        "subscriptions": SUBSCRIPTIONS,
    }


def render_md(m: dict[str, Any]) -> str:
    L = m["ledger"]
    split_hdr = f"- **Split hit ratio: {L['split_hit_ratio']*100:.1f}%** (captured on {L['split_rows']:,} rows, {L['split_coverage']*100:.1f}% of input)" if L.get("split_hit_ratio") is not None else "- Split not captured"
    lines = [
        "# Cache / Economy Map (cache_map.v1)",
        "",
        f"- Generated: `{m['ts']}`",
        f"- Verkle: {m['verkle']['n_sessions']} sessions / {m['verkle']['n_leaves']} knot leaves · root `{m['verkle']['root_short']}`",
        "",
        "## Ledger totals (all remote providers)",
        "",
        f"- Calls: **{L['calls']:,}** · input **{L['input_tokens']:,} tok** · output {L['output_tokens']:,} tok",
        f"- {split_hdr}",
        "",
        "## By provider",
        "",
        "| provider | calls | input_tok | output_tok | hit_ratio | priced_usd | billing_authoritative |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in m["by_provider"]:
        hr = f"{p['hit_ratio']*100:.1f}%" if p["hit_ratio"] is not None else "n/a"
        auth = ""
        if p.get("billing_authoritative"):
            b = p["billing_authoritative"]
            auth = f"{b['hit_ratio']*100:.1f}% / ${b['usd_per_day']:.2f}/d"
        lines.append(
            f"| {p['provider']} | {p['calls']} | {p['input_tokens']:,} | {p['output_tokens']:,} | {hr} | ${p['priced_usd']:.4f} | {auth} |"
        )
    lines += [
        "",
        "## Input tokens by verkle theme",
        "",
        "| theme | calls | input_tok | output_tok | split_hit_ratio |",
        "|---|---|---|---|---|",
    ]
    for t in m["by_theme"]:
        shr = f"{t['split_hit_ratio']*100:.0f}%" if t["split_rows"] else "n/a"
        lines.append(
            f"| {t['theme']} | {t['calls']} | {t['input_tokens']:,} | {t['output_tokens']:,} | {shr} |"
        )
    lines += [
        "",
        "## Fixed / subscription surfaces (no per-call token API)",
        "",
        "| surface | label | cost_kind | est | note |",
        "|---|---|---|---|---|",
    ]
    for s in m.get("subscriptions") or []:
        est = f"${s.get('est_usd_per_month', 0):.2f}/mo" if s.get("cost_kind") == "subscription" else f"${s.get('est_usd_per_run', 0):.2f}/run"
        lines.append(f"| {s['surface']} | {s['label']} | {s['cost_kind']} | {est} | {s['note']} |")
    lines += [
        "",
        "_Note: input_tokens is read from `prompt_tokens` (present on every row) = real volume. `priced_usd` is computed only where the cache hit/miss split is captured (split_rows); otherwise the authoritative billing figure is authoritative where present. Rates per model in MODEL_RATES (DeepSeek verified from billing, others public/approx)._",
        "",
        "_Deterministic join of logs/provider_usage.jsonl onto memory/biography/verkle_chain.jsonl by time window. No LLM, $0._",
    ]
    return "\n".join(lines)


def persist(m: dict[str, Any]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = OUT_DIR / ts
    d.mkdir(parents=True, exist_ok=True)
    (d / "map.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "MAP.md").write_text(render_md(m), encoding="utf-8")
    return d


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="cache-map", description="Map DeepSeek cache hit/miss onto verkle sessions")
    ap.add_argument("--write", action="store_true", help="persist MAP.md + map.json under memory/runs/cache_map/<ts>/")
    args = ap.parse_args(argv)
    m = build_map()
    if args.write:
        d = persist(m)
        print(json.dumps({"ok": True, "path": str(d), "map": m}, indent=2, default=str)[:6000])
    else:
        print(json.dumps(m, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
