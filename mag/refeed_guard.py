#!/usr/bin/env python3
"""refeed_guard.py — B1 refeed-tax guard over the ZCode session DB. $0, read-only.

The refeed tax (measured 09-05): burn-pool quota lost to re-fed context —
122M input tokens vs 0.5M output in one weekend pool. This guard measures the
CHAR PROXY shape of it per session: input side = user text + tool/tool_result
part chars (every turn re-feeds prior tool output back to the model), output
side = assistant text chars. Chars are a PROXY for tokens, never tokens —
real provider token sums from step-finish parts ride along as tok_* fields
for cross-check only.

CLI:
  python -m mag.refeed_guard measure [--days N] [--threshold R]

Writes ROOT/state/refeed_guard_latest.json. Exit code 0 always (guard is a
measurement, not a gate-crasher — the gate reads the JSON verdict).
DB is opened READ-ONLY via file:...?mode=ro; secrets never echoed (titles
redacted with the live_feed SECRET regex). No daemons, no schedulers.
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"
OUT = REPO / "state" / "refeed_guard_latest.json"

DEFAULT_DAYS = 7
DEFAULT_THRESHOLD = 200      # flag when in_chars:out_chars exceeds 200:1
FLAG_MIN_IN_CHARS = 100_000  # ignore micro-sessions below this input floor
SECRET = re.compile(r"(sk-[A-Za-z0-9]{6,}|Bearer\s+\S+|[A-Fa-f0-9]{32,}|xox[baprs]-\S+)")

for _p in (OUT,):
    if REPO not in _p.resolve().parents:
        raise ValueError(f"write target escapes repo: {_p}")


def redact(s, n=48):
    return SECRET.sub("[REDACTED]", s or "").replace("\n", " ").strip()[:n]


def measure(days: int, threshold: int) -> dict:
    cutoff_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - days * 86_400_000
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    cur.execute(
        "SELECT id, title, time_updated FROM session "
        "WHERE time_updated > ? ORDER BY time_updated DESC", (cutoff_ms,))
    sessions = cur.fetchall()

    per_session, daily = {}, {}
    for s in sessions:
        sid = s["id"]
        row = per_session.setdefault(sid, {
            "id": sid[:8], "title": redact(s["title"]),
            "day": datetime.fromtimestamp(s["time_updated"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "in_chars": 0, "out_chars": 0, "reasoning_chars": 0,
            "tok_in": 0, "tok_out": 0, "tok_cache_read": 0,
        })
        cur.execute(
            "SELECT p.data AS pdata, m.data AS mdata FROM part p "
            "JOIN message m ON p.message_id = m.id "
            "WHERE p.session_id = ?", (sid,))
        for p in cur.fetchall():
            try:
                pd = json.loads(p["pdata"])
                md = json.loads(p["mdata"])
            except Exception:
                continue
            role, kind = md.get("role", "?"), pd.get("type", "?")
            if kind == "text":
                n = len(pd.get("text", "") or "")
                if role == "user":
                    row["in_chars"] += n
                elif role == "assistant":
                    row["out_chars"] += n
            elif kind == "tool":  # tool call + tool result: the re-fed body
                st = pd.get("state") or {}
                try:
                    row["in_chars"] += len(json.dumps(st.get("input"), sort_keys=True))
                    out = st.get("output")
                    row["in_chars"] += len(out if isinstance(out, str) else json.dumps(out, sort_keys=True))
                except (TypeError, ValueError):
                    pass
            elif kind == "reasoning":
                row["reasoning_chars"] += len(pd.get("text", "") or "")
            elif kind == "step-finish":
                tk = pd.get("tokens") or {}
                row["tok_in"] += int(tk.get("input") or 0)
                row["tok_out"] += int(tk.get("output") or 0)
                row["tok_cache_read"] += int((tk.get("cache") or {}).get("read") or 0)
        d = daily.setdefault(row["day"], {"day": row["day"], "sessions": 0, "in_chars": 0, "out_chars": 0})
        d["sessions"] += 1
        d["in_chars"] += row["in_chars"]
        d["out_chars"] += row["out_chars"]

    out_rows = []
    for row in per_session.values():
        row["ratio"] = round(row["in_chars"] / row["out_chars"], 1) if row["out_chars"] else None
        row["refeed_flag"] = bool(row["out_chars"]) and row["ratio"] is not None \
            and row["ratio"] > threshold and row["in_chars"] >= FLAG_MIN_IN_CHARS
        out_rows.append(row)
    out_rows.sort(key=lambda r: r["in_chars"], reverse=True)
    days_rows = sorted(daily.values(), key=lambda d: d["day"])

    total_in = sum(r["in_chars"] for r in out_rows)
    total_out = sum(r["out_chars"] for r in out_rows)
    flagged = [r for r in out_rows if r["refeed_flag"]]
    verdict = "REFEED_HEAVY" if flagged else "CLEAN"

    payload = {
        "guard": "refeed_guard B1",
        "unit": "CHARS_PROXY_NOT_TOKENS",
        "verdict": verdict,
        "threshold_in_out_ratio": threshold,
        "flag_min_in_chars": FLAG_MIN_IN_CHARS,
        "window_days": days,
        "totals": {
            "sessions": len(out_rows),
            "in_chars": total_in,
            "out_chars": total_out,
            "ratio": round(total_in / total_out, 1) if total_out else None,
            "tok_in_stepfinish": sum(r["tok_in"] for r in out_rows),
            "tok_out_stepfinish": sum(r["tok_out"] for r in out_rows),
            "tok_cache_read_stepfinish": sum(r["tok_cache_read"] for r in out_rows),
        },
        "flagged_sessions": [
            {"id": r["id"], "title": r["title"], "in_chars": r["in_chars"],
             "out_chars": r["out_chars"], "ratio": r["ratio"]} for r in flagged],
        "sessions": out_rows,
        "daily": days_rows,
        "db_path": str(DB),
    }
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser(prog="refeed_guard")
    sub = ap.add_subparsers(dest="cmd")
    m = sub.add_parser("measure")
    m.add_argument("--days", type=int, default=DEFAULT_DAYS)
    m.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    args = ap.parse_args(argv)
    if args.cmd not in ("measure", None):
        ap.error("unknown command")
    try:
        payload = measure(args.days, args.threshold)
    except Exception as e:  # exit code 0 always; the JSON carries the failure
        payload = {"guard": "refeed_guard B1", "verdict": "ERROR", "error": repr(e)}
    payload["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")

    t = payload.get("totals", {})
    print(f"REFEED GUARD (char proxy, {payload.get('window_days','?')}d) verdict={payload.get('verdict')}")
    print(f"  sessions={t.get('sessions')} in={t.get('in_chars',0):,} out={t.get('out_chars',0):,} "
          f"ratio={t.get('ratio')} (chars, PROXY not tokens)")
    print(f"  step-finish real tokens: in={t.get('tok_in_stepfinish',0):,} out={t.get('tok_out_stepfinish',0):,} "
          f"cache_read={t.get('tok_cache_read_stepfinish',0):,}")
    for r in payload.get("flagged_sessions", [])[:5]:
        print(f"  FLAG {r['id']} in={r['in_chars']:,} out={r['out_chars']:,} ratio={r['ratio']} | {r['title']}")
    print(f"  json -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
