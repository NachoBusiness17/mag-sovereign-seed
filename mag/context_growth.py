"""Context-growth analyzer — measure per-session context growth to find where spend balloons.

Calibration finding: per-call input is dominated by growing multi-turn context (~500 calls/goal,
~62K tok/call), NOT the initial frozen prefix. This analyzer makes that visible per session so we
can target repack/compaction at the ballooners. Uses the STOLEN patterns from
memory/steal/CONTEXT_GROWTH_STEAL_20260809.md (tool-schema-aware + 0.85x-window headroom,
compaction-summary-as-checkpoint, rolling breaker). Reuses existing context machinery
(agent_cli.repack_messages, usable_context_budget, repack_ratio) — does NOT rebuild it.

Deterministic ($0, no LLM). Schema: context_growth.v1

CLI:  python -m mag.context_growth [--hours N] [--cadence]
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
OUT_DIR = ROOT / "memory" / "runs" / "context_growth"
SCHEMA = "context_growth.v1"


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


def _repack_budget() -> tuple[int, float]:
    """Best-effort repack budget + ratio from agent_cli (reuse existing machinery)."""
    try:
        from mag.agent_cli import usable_context_budget, _repack_ratio
        return int(usable_context_budget("deepseek")), float(_repack_ratio())
    except Exception:
        return 0, 0.62


def analyze(*, hours: int = 24, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Group provider usage by session_id and characterize context growth per session."""
    all_rows = rows if rows is not None else _read_jsonl(USAGE)
    cutoff = (_now() - timedelta(hours=hours)).isoformat()
    win = [r for r in all_rows if str(r.get("ts") or "") >= cutoff]

    budget, ratio = _repack_budget()
    target = int(budget * ratio) if budget else 0

    # session -> ordered calls with prompt_tokens
    sessions: dict[str, list[tuple[str, int, int]]] = defaultdict(list)  # sid -> [(ts, prompt, out)]
    no_sid = 0
    for r in win:
        if str(r.get("provider") or "") in ("ollama", "test_provider"):
            continue
        sid = str(r.get("session_id") or "").strip()
        if not sid:
            no_sid += 1
            continue
        sessions[sid].append((str(r.get("ts") or ""), int(r.get("prompt_tokens") or 0),
                              int(r.get("completion_tokens") or 0)))

    session_rows = []
    for sid, calls in sessions.items():
        calls.sort(key=lambda c: c[0])
        first = calls[0][1]
        last = calls[-1][1]
        peak = max(c[1] for c in calls)
        avg = sum(c[1] for c in calls) / len(calls)
        cumulative = sum(c[1] for c in calls)
        growth = last - first
        steep = (last - first) / max(len(calls), 1)  # avg growth per call
        # repack-candidate score: how much cumulative input exceeds a repacked budget baseline
        est_saved = max(0, cumulative - (target * max(len(calls) - 2, 0)))
        session_rows.append({
            "session_id": sid,
            "calls": len(calls),
            "first_ctx": first,
            "last_ctx": last,
            "peak_ctx": peak,
            "avg_ctx": int(avg),
            "cumulative_input": cumulative,
            "growth": growth,
            "growth_per_call": int(steep),
            "est_repack_saved_tokens": int(est_saved),
        })
    session_rows.sort(key=lambda s: -s["cumulative_input"])

    return {
        "schema": SCHEMA,
        "ts": _now().isoformat(),
        "window_hours": hours,
        "rows_in_window": len(win),
        "sessions_with_sid": len(sessions),
        "rows_without_sid": no_sid,
        "repack_budget": budget,
        "repack_ratio": ratio,
        "repack_target": target,
        "top_sessions": session_rows[:15],
        "n_sessions": len(session_rows),
        "total_session_cumulative_input": sum(s["cumulative_input"] for s in session_rows),
        "total_est_repack_saved_tokens": sum(s["est_repack_saved_tokens"] for s in session_rows),
    }


def render_md(a: dict[str, Any]) -> str:
    lines = [
        f"# Context Growth ({a['ts'][:10]})",
        "",
        f"- Window: last {a['window_hours']}h · {a['rows_in_window']} rows · {a['sessions_with_sid']} sessions "
        f"· {a['rows_without_sid']} rows w/o session_id",
        f"- Repack target ~{a['repack_target']} tok (budget {a['repack_budget']} × {a['repack_ratio']:.0%})",
        f"- Total session cumulative input: **{a['total_session_cumulative_input']:,} tok** · est repack saved: {a['total_est_repack_saved_tokens']:,}",
        "",
        "## Top sessions by cumulative input",
        "",
        "| session | calls | first | last | peak | avg | cumulative | growth/call | est_repack_saved |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in a["top_sessions"]:
        lines.append(f"| {s['session_id'][:28]} | {s['calls']} | {s['first_ctx']:,} | {s['last_ctx']:,} | "
                     f"{s['peak_ctx']:,} | {s['avg_ctx']:,} | {s['cumulative_input']:,} | "
                     f"{s['growth_per_call']:,} | {s['est_repack_saved_tokens']:,} |")
    lines += [
        "",
        "_Deterministic join of logs/provider_usage.jsonl by session_id. New rows carry session_id; "
        "historical rows without it are counted as rows_without_sid. Reuses agent_cli repack machinery._",
    ]
    return "\n".join(lines)


def run_cadence(*, hours: int = 24) -> dict[str, Any]:
    """Idempotent maintenance leaf: write latest context-growth report (overwrite per day)."""
    a = analyze(hours=hours)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    leaf = OUT_DIR / f"context_growth_{a['ts'][:10]}.md"
    leaf.write_text(render_md(a), encoding="utf-8")
    return {"ok": True, "action": "wrote", "leaf": str(leaf),
            "n_sessions": a["n_sessions"],
            "total_cumulative_input": a["total_session_cumulative_input"],
            "est_repack_saved": a["total_est_repack_saved_tokens"]}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="context-growth", description="Per-session context-growth analyzer")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--cadence", action="store_true", help="write maintenance leaf")
    args = ap.parse_args(argv)
    res = run_cadence(hours=args.hours) if args.cadence else analyze(hours=args.hours)
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
