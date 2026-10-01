"""pin_audit — LAW-058 enforcement: find every session pinned to a premium model.

Operator root-cause order (2026-09-05, after the Lite 73.2M incident, the Boss pin, the
Sancho cadence session, and a concurrency failover all showed the same face):
"anything pinned to 5.3 needs to be on 5.3-flash within all automated tasks and systems."

What this organ does ($0, read-only on the session db):
  1. Lists every session whose runtime/model_selection pin is GLM-5.3 (full) — the burn hazard.
  2. Flags RECENT ones (updated within --hours, default 24) as LIVE HAZARD (reopenable/burning).
  3. Reports the config defaults (config.json + headless-settings.json) so drift is visible.
  4. Writes a one-screen brief to watch/receipts/pin_audit_latest.txt + appends JSONL history.

Known behavior (documented 2026-09-05): out-of-band DB pin edits are REVERTED by the running
app (it holds session state in memory and writes back). Durable pin changes happen in-app
(model picker) or with the app closed. This organ DETECTS; the picker FIXES.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

DB = Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"
CONFIG = Path.home() / ".zcode" / "cli" / "config.json"
HEADLESS = Path.home() / ".zcode" / "cli" / "headless-settings.json"
OUT_TXT = ROOT / "watch" / "receipts" / "pin_audit_latest.txt"
OUT_JSONL = ROOT / "watch" / "receipts" / "pin_audit_history.jsonl"
PREMIUM = {"GLM-5.3"}
SAFE = {"GLM-5.3-Flash", "GLM-4.7-Flash"}


def main(argv: list[str] | None = None) -> int:
    hours = 24.0
    if argv and argv[0].isdigit():
        hours = float(argv[0])
    cutoff = time.time() - hours * 3600

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    rows = []
    for (s, t_upd, d) in cur.execute(
        "SELECT session_id, time_updated, data FROM session_entry "
        "WHERE type='runtime/model_selection'"
    ):
        try:
            pin = json.loads(d)
        except Exception:
            continue
        title_row = cur.execute("SELECT title, time_updated FROM session WHERE id=?", (s,)).fetchone()
        rows.append(
            {
                "session": s,
                "title": (title_row[0] if title_row else "?"),
                "model": pin.get("modelId"),
                "thought": pin.get("thoughtLevel"),
                "pin_updated": t_upd / 1000.0,
            }
        )
    total_sessions = cur.execute("SELECT COUNT(*) FROM session").fetchone()[0]
    con.close()

    premium = [r for r in rows if r["model"] in PREMIUM]
    live = [r for r in premium if r["pin_updated"] >= cutoff]
    safe_n = sum(1 for r in rows if r["model"] in SAFE)
    unpinned = total_sessions - len(rows)

    cfg_flash = False
    for cf in (CONFIG, HEADLESS):
        try:
            txt = cf.read_text(encoding="utf-8")
            cfg_flash = cfg_flash or ("GLM-5.3-Flash" in txt)
        except OSError:
            pass

    lines = [f"PIN AUDIT — {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
             f"sessions: {total_sessions} | pinned: {len(rows)} | unpinned(inherit Flash default): {unpinned}",
             f"config defaults on Flash: {cfg_flash}",
             f"PREMIUM-PINNED (GLM-5.3 full): {len(premium)} | live in last {hours:.0f}h: {len(live)}"]
    for r in sorted(premium, key=lambda x: -x["pin_updated"])[:15]:
        age_h = (time.time() - r["pin_updated"]) / 3600
        flag = " ← LIVE HAZARD" if r in live else ""
        lines.append(
            f"  - {r['title'][:44]:44s} thought={r['thought']} pin-age={age_h:6.1f}h{flag}"
        )
    if live:
        lines.append("ACTION: reopen the live ones and set the picker to GLM-5.3-Flash (in-app flips stick; DB edits while the app runs get reverted).")
    else:
        lines.append("ACTION: none — no live premium pins.")
    brief = "\n".join(lines) + "\n"

    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(brief, encoding="utf-8")
    with open(OUT_JSONL, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                             "total": total_sessions, "premium": len(premium),
                             "live": len(live), "cfg_flash": cfg_flash}) + "\n")
    print(brief)
    return 1 if live else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
