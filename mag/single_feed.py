"""single_feed — one stream for the watcher: aggregate the fleet's feeds.

Born 2026-09-05, operator: "a vision model watching all our feeds in a single
feed watching for shapes and wrong assumptions, dropping clues into agent
inboxes, dropping breadcrumbs." The watcher cannot watch ten logs; it watches
ONE snapshot. This module builds that snapshot from the feeds that already
exist — nothing new is instrumented, everything already writes.

Sources (tail-n): lane trails, lane_scheduler.log, window_spawns audit,
thought bank, handshakes ledger, room.jsonl, day ledger, census verdict.
Output: memory/feed/feed_snapshot.jsonl (rows) + feed_snapshot.md (rendered,
capped for a model context).
"""

from __future__ import annotations

import datetime
import io
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "memory" / "feed"

SOURCES = [
    ("lane_scheduler", ROOT / "logs" / "lane_scheduler.log", 12),
    ("window_spawns", ROOT / "logs" / "window_spawns.jsonl", 3),
    ("thought_bank", ROOT / "memory" / "thinking" / "glm-5.3-flash.jsonl", 3),
    ("handshakes", ROOT / "state" / "handshakes.jsonl", 12),
    ("room", ROOT / "queue" / "room.jsonl", 3),
    ("day_ledger", ROOT / "watch" / "DAY_LEDGER_2026-09-04.md", 6),
]


def _tail(path: Path, n: int) -> list[str]:
    try:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            return [l.rstrip() for l in f if l.strip()][-n:]
    except OSError:
        return []


def build_snapshot(max_chars: int = 24000) -> dict[str, Any]:
    """Aggregate feed tails into rows + a rendered snapshot; return stats."""
    rows: list[dict[str, Any]] = []
    sections: list[str] = []
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # lane trails (each lane's last 4 rows)
    lanes_dir = ROOT / "queue" / "lanes"
    lane_tails: list[str] = []
    if lanes_dir.is_dir():
        for trail in sorted(lanes_dir.glob("*/trail.jsonl")):
            for line in _tail(trail, 4):
                lane_tails.append(f"[{trail.parent.name}] {line[-220:]}")
    if lane_tails:
        sections.append("## LANE TRAILS\n" + "\n".join(lane_tails[-40:]))
    for name, path, n in SOURCES:
        lines = _tail(path, n)
        if not lines:
            continue
        sections.append(f"## {name.upper()}\n" + "\n".join(l[-260:] for l in lines))
        for l in lines:
            rows.append({"ts": ts, "feed": name, "line": l[-400:]})
    # census verdict (latest PROSE_CENSUS first line under the title)
    censuses = sorted((ROOT / "watch").glob("PROSE_CENSUS_*.md"))
    if censuses:
        head = censuses[-1].read_text(encoding="utf-8", errors="replace").splitlines()[:4]
        sections.append("## PROSE CENSUS (latest)\n" + "\n".join(head))
    md = f"# FLEET FEED SNAPSHOT — {ts}\n\n" + "\n\n".join(sections)
    md = md[:max_chars]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "feed_snapshot.md").write_text(md, encoding="utf-8")
    with io.open(OUT_DIR / "feed_snapshot.jsonl", "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"ts": ts, "rows": len(rows), "sections": len(sections),
            "chars": len(md), "path": str(OUT_DIR / "feed_snapshot.md")}


if __name__ == "__main__":
    print(json.dumps(build_snapshot()))
