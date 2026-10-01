"""thought_bank_app — bank the ZCode app's own reasoning parts into the thought bank.

WHERE THE THOUGHTS LIVE (measured 2026-09-05, corrects the 02:1xZ "app thinking
uncapturable" claim — DISPUTED->FALSE): ~/.zcode/cli/db/db.sqlite table `part`,
rows where json data.type == "reasoning", full verbatim text in data.text.
The app's trajectory viewer renders these. 64,246 parts and counting.

v0: read-only pass over all reasoning parts -> append to
memory/thinking/app_reasoning.jsonl as {part_id, session_id, message_id, ts,
model, chars, text}. Dedup on part_id (append-only, delete-as-append safe).
Silent-fail on any single bad row. $0, local, no model calls.

Usage:
  python -m mag.thought_bank_app            # incremental harvest (default)
  python -m mag.thought_bank_app --census   # counts only, no writes
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB = Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"
OUT = Path(__file__).resolve().parent.parent / "memory" / "thinking" / "app_reasoning.jsonl"


def _rows(c: sqlite3.Cursor):
    """Yield (part_id, session_id, message_id, time_created, part_data,
    provider, model, tokens, cost) with message JSON parsed in Python —
    message.data carries providerID/modelID/tokens/cost (no SQL columns)."""
    c.execute(
        "SELECT p.id, p.session_id, p.message_id, p.time_created, p.data, m.data "
        "FROM part p LEFT JOIN message m ON m.id = p.message_id "
        "ORDER BY p.time_created ASC"
    )
    for pid, sid, mid, tc, pdata, mdata in c.fetchall():
        provider = model = None
        tokens = cost = None
        try:
            md = json.loads(mdata) if mdata else {}
            provider = md.get("providerID")
            model = md.get("modelID")
            tokens = md.get("tokens")
            cost = md.get("cost")
        except Exception:
            pass
        yield pid, sid, mid, tc, pdata, provider, model, tokens, cost


def harvest(census_only: bool = False) -> int:
    if not DB.exists():
        print(f"no db at {DB}")
        return 0
    db = sqlite3.connect(f"file:///{DB.as_posix()}?mode=ro", uri=True)
    c = db.cursor()
    seen: set[str] = set()
    if OUT.exists():
        with OUT.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    seen.add(json.loads(line)["part_id"])
                except Exception:
                    continue
    banked = skipped = 0
    out_rows: list[str] = []
    for pid, sid, mid, tc, pdata, provider, model, tokens, cost in _rows(c):
        try:
            d = json.loads(pdata)
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("type") != "reasoning":
            continue
        if pid in seen:
            skipped += 1
            continue
        text = d.get("text") or ""
        if not text.strip():
            continue
        ts = (
            datetime.fromtimestamp(tc / 1000, tz=timezone.utc).isoformat()
            if tc else None
        )
        row = {
            "part_id": pid,
            "session_id": sid,
            "message_id": mid,
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "cost": cost,
            "ts": ts,
            "chars": len(text),
            "sha16": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16],
            "text": text,
        }
        out_rows.append(json.dumps(row, ensure_ascii=False))
        banked += 1
    if census_only:
        print(f"census: {banked} new reasoning parts, {skipped} already banked")
        return banked
    if out_rows:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(out_rows) + "\n")
    print(f"banked {banked} reasoning parts -> {OUT} ({skipped} already banked)")
    return banked


if __name__ == "__main__":
    try:
        harvest(census_only="--census" in sys.argv)
    except Exception as e:  # silent-fail doctrine: never break a session on bank errors
        print(f"thought_bank_app failed: {e}", file=sys.stderr)
