"""burn_steer — the vision-steerer for the Weekend Build 300M burn (2026-09-05).

Operator order: "this is exactly why we need the vision model steering this 300m
burn." Root failure it fixes: blind parallel subagents collided with the operator's
other sessions and died on "user concurrency limit exceeded" (A2, 04:20Z) — burn
concurrency belonged to nobody and cost us a worker.

Design: NO model calls, NO subagents, NO host daemons (laws 11/13/16). This organ
reads telemetry, renders THE BURN BOARD (stdout + dashboard/static/burn_board.html
so it lives on the operator's surface), and appends a typed steer row. The VISION
leg is the seat itself: a vision-capable model (this 5.3-flash seat) READS the board
at each steering pass and judges pace/collision/next-build. The board is the retina;
the seat is the steerer; this file is the optic nerve.

  python -m mag.burn_steer            # one steering pass, $0
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"
BOARD_HTML = ROOT / "dashboard" / "static" / "burn_board.html"
STEER_LOG = ROOT / "memory" / "burn" / "steer_log.jsonl"

POOL_TOKENS = 300_000_000          # Weekend Build pool (his panel, 09-05)
BURN_START = "2026-09-04 20:00"    # UTC — ramp 0 fired ~03:4xZ but burn clock
                                   # starts at the evening's first weekend push
STALE_SESSION_MIN = 10             # a session updated within this window is LIVE


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _read_telemetry() -> dict:
    db = sqlite3.connect(f"file:///{DB.as_posix()}?mode=ro", uri=True)
    c = db.cursor()
    c.execute(
        "SELECT datetime(started_at/1000,'unixepoch'), agent, computed_total_tokens "
        "FROM model_usage WHERE status='completed' "
        "AND datetime(started_at/1000,'unixepoch') >= ? ORDER BY started_at",
        (BURN_START,),
    )
    rows = c.fetchall()
    by_hour = defaultdict(float)
    by_agent = defaultdict(float)
    total = 0
    for t, agent, tok in rows:
        n = (tok or 0) / 1e6
        by_hour[t[:13]] += n
        by_agent[agent] += n
        total += tok or 0
    c.execute(
        "SELECT id, title, datetime(time_updated/1000,'unixepoch') FROM session "
        "ORDER BY time_updated DESC LIMIT 12"
    )
    now = _utcnow()
    live = []
    for sid, title, tu in c.fetchall():
        try:
            dt = datetime.fromisoformat(tu).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        age_min = (now - dt).total_seconds() / 60
        if age_min <= STALE_SESSION_MIN:
            live.append({"id": sid[:24], "title": (title or "?")[:40],
                         "age_min": round(age_min, 1)})
    c.execute("SELECT COUNT(*) FROM part p JOIN message m ON m.id=p.message_id "
              "WHERE p.data LIKE '%reasoning%' "
              "AND m.time_created > (strftime('%s','now')-86400)*1000")
    try:
        reasoning_24h = c.fetchone()[0]
    except Exception:
        reasoning_24h = -1
    return {"total_mtok": round(total / 1e6, 1), "by_hour": dict(by_hour),
            "by_agent": {k: round(v, 1) for k, v in by_agent.items()},
            "live_sessions": live, "reasoning_parts_24h": reasoning_24h}


def _board_text(t: dict) -> str:
    pool_left = max(0.0, POOL_TOKENS / 1e6 - t["total_mtok"])
    hours = sorted(t["by_hour"])
    spark = " ".join(f"{h[-2:]}h:{t['by_hour'][h]:.0f}M" for h in hours[-9:])
    lines = [
        "== BURN BOARD (weekend build) ==========",
        f"pool: {t['total_mtok']:.0f}M burned / {POOL_TOKENS//1000000}M "
        f"-> {pool_left:.0f}M left ({100*t['total_mtok']/(POOL_TOKENS/1e6):.0f}% spent)",
        f"hourly (UTC Mtok): {spark or '(none)'}",
        f"by agent: " + ", ".join(f"{k}={v}M" for k, v in
                                  sorted(t['by_agent'].items(), key=lambda x: -x[1])),
        f"LIVE SESSIONS (last {STALE_SESSION_MIN}m): {len(t['live_sessions'])}"
        + ("  <-- COLLISION RISK if >1 and spawning" if len(t["live_sessions"]) > 1 else ""),
    ]
    for s in t["live_sessions"]:
        lines.append(f"  live: {s['title']} ({s['age_min']}m ago)")
    lines.append(f"thought bank 24h: {t['reasoning_parts_24h']} reasoning parts")
    lines.append("laws in effect: 16 one-steerer (no parallel bg subagents) | "
                 "15 reserve-patience | 13 no new host runtimes")
    return "\n".join(lines)


def _write_board_html(t: dict, text: str) -> None:
    pool_left = max(0.0, POOL_TOKENS / 1e6 - t["total_mtok"])
    rows = "".join(
        f"<tr><td>{h}:00</td><td>{t['by_hour'][h]:.1f}M</td></tr>"
        for h in sorted(t["by_hour"]))
    live = "".join(
        f"<li><b>{s['title']}</b> — {s['age_min']}m ago</li>"
        for s in t["live_sessions"]) or "<li>none</li>"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Burn Board</title>
<style>body{{background:#111;color:#ddd;font-family:monospace;margin:2em}}
.big{{font-size:1.6em}} table{{border-collapse:collapse}} td{{padding:2px 12px;border:1px solid #333}}</style>
</head><body><h1>BURN BOARD — Weekend Build</h1>
<p class="big">{t['total_mtok']:.0f}M burned / {POOL_TOKENS//1000000}M — <b>{pool_left:.0f}M left</b></p>
<p>by agent: {', '.join(f'{k}={v}M' for k,v in sorted(t['by_agent'].items(), key=lambda x:-x[1]))}</p>
<p>live sessions ({len(t['live_sessions'])}):</p><ul>{live}</ul>
<p>thought bank 24h: {t['reasoning_parts_24h']} reasoning parts banked</p>
<table><tr><th>hour (UTC)</th><th>Mtok</th></tr>{rows}</table>
<pre>{text}</pre></body></html>"""
    BOARD_HTML.parent.mkdir(parents=True, exist_ok=True)
    BOARD_HTML.write_text(html, encoding="utf-8")


def _write_board_png(t: dict, path: Path) -> None:
    """Hand-rolled PNG retina (stdlib only — no PIL/matplotlib in the cage):
    pool gauge bar + hourly burn bars + agent split, drawn on an RGB canvas.
    Dogfood fix 09-11: the board was born mute (rects only, zero glyphs) —
    added a 5x7 bitmap font so the retina passes the readable law."""
    import zlib, struct

    W, H = 640, 360
    px = bytearray(bytes((17, 17, 23)) * (W * H))  # #111117 background

    def rect(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(H, y1)):
            base = y * W
            for x in range(max(0, x0), min(W, x1)):
                i = (base + x) * 3
                px[i:i + 3] = bytes(c)

    # 5x7 bitmap font, one 5-bit row per line, msb = left pixel
    FONT = {
        'A': (14, 17, 17, 31, 17, 17, 17), 'B': (30, 17, 17, 30, 17, 17, 30),
        'C': (14, 17, 16, 16, 16, 17, 14), 'D': (30, 17, 17, 17, 17, 17, 30),
        'E': (31, 16, 16, 30, 16, 16, 31), 'F': (31, 16, 16, 30, 16, 16, 16),
        'G': (14, 17, 16, 23, 17, 17, 15), 'H': (17, 17, 17, 31, 17, 17, 17),
        'I': (14, 4, 4, 4, 4, 4, 14), 'K': (17, 18, 20, 24, 20, 18, 17),
        'L': (16, 16, 16, 16, 16, 16, 31), 'M': (17, 27, 21, 21, 17, 17, 17),
        'N': (17, 25, 21, 19, 17, 17, 17), 'O': (14, 17, 17, 17, 17, 17, 14),
        'P': (30, 17, 17, 30, 16, 16, 16), 'R': (30, 17, 17, 30, 20, 18, 17),
        'S': (15, 16, 16, 14, 1, 1, 30), 'T': (31, 4, 4, 4, 4, 4, 4),
        'U': (17, 17, 17, 17, 17, 17, 14), 'V': (17, 17, 17, 17, 10, 10, 4),
        'W': (17, 17, 21, 21, 21, 27, 17), 'X': (17, 10, 4, 4, 4, 10, 17),
        'Y': (17, 10, 4, 4, 4, 4, 4), 'Z': (31, 1, 2, 4, 8, 16, 31),
        '0': (14, 17, 19, 21, 25, 17, 14), '1': (4, 12, 4, 4, 4, 4, 14),
        '2': (14, 17, 1, 6, 8, 16, 31), '3': (30, 1, 1, 14, 1, 1, 30),
        '4': (2, 6, 10, 18, 31, 2, 2), '5': (31, 16, 30, 1, 1, 17, 14),
        '6': (6, 8, 16, 30, 17, 17, 14), '7': (31, 1, 2, 4, 8, 8, 8),
        '8': (14, 17, 17, 14, 17, 17, 14), '9': (14, 17, 17, 15, 1, 2, 12),
        ' ': (0, 0, 0, 0, 0, 0, 0), '/': (1, 2, 2, 4, 8, 8, 16),
        '%': (25, 26, 2, 4, 8, 11, 19), '(': (2, 4, 8, 8, 8, 4, 2),
        ')': (8, 4, 2, 2, 2, 4, 8), '-': (0, 0, 0, 14, 0, 0, 0),
        '>': (8, 4, 2, 1, 2, 4, 8), '.': (0, 0, 0, 0, 0, 6, 6),
        ':': (0, 6, 6, 0, 6, 6, 0), '\x97': (0, 0, 0, 31, 0, 0, 0),
    }

    def text(s, x0, y0, c, scale=2):
        for i, ch in enumerate(s):
            g = FONT.get(ch.upper(), FONT[' '])
            for ry, row in enumerate(g):
                for rx in range(5):
                    if row & (16 >> rx):
                        rect(x0 + i * 6 * scale + rx * scale,
                             y0 + ry * scale,
                             x0 + i * 6 * scale + (rx + 1) * scale,
                             y0 + (ry + 1) * scale, c)

    GREEN, RED, GREY, WHITE, AMBER = (57, 211, 128), (240, 90, 90), (70, 70, 84), (230, 230, 230), (240, 180, 70)
    burned_frac = min(1.0, t["total_mtok"] / (POOL_TOKENS / 1e6))

    text("BURN BOARD", 20, 8, WHITE, 2)
    text(">NOW", 560, 8, AMBER, 2)

    # pool gauge: 600x30 bar, green->amber->red as it empties
    rect(20, 34, 620, 64, GREY)
    g = int(600 * (1 - burned_frac))
    rect(20, 34, 20 + g, 64, GREEN if burned_frac < 0.7 else (AMBER if burned_frac < 0.9 else RED))

    pool_m = int(POOL_TOKENS / 1e6)
    spent = int(round(100 * t["total_mtok"] / pool_m)) if pool_m else 0
    left = max(0, pool_m - int(t["total_mtok"]))
    text(f"{int(t['total_mtok'])}M/{pool_m}M - {left} LEFT ({spent}%)",
         20, 72, GREEN if burned_frac < 0.9 else RED, 3)

    # hourly bars: last 18 hours, scale to max
    hours = sorted(t["by_hour"])[-18:]
    if hours:
        mx = max(t["by_hour"][h] for h in hours) or 1.0
        bw, gap = 24, 8
        x0 = 20
        for h in hours:
            bh = int(150 * t["by_hour"][h] / mx)
            rect(x0, 290 - bh, x0 + bw, 290, WHITE)
            x0 += bw + gap

    # agent split bar (bottom): agent share of burn
    x0 = 20
    total = t["total_mtok"] or 1.0
    colors = [GREEN, AMBER, RED, WHITE]
    for i, (ag, m) in enumerate(sorted(t["by_agent"].items(), key=lambda kv: -kv[1])):
        w = int(600 * m / total)
        rect(x0, 310, x0 + w, 330, colors[i % len(colors)])
        x0 += w

    top_ag = sorted(t["by_agent"].items(), key=lambda kv: -kv[1])[:1]
    for ag, m in top_ag:
        text(f"{ag} {int(m)}M", 20, 338, GREY, 2)

    raw = b"".join(b"\x00" + bytes(px[y * W * 3:(y + 1) * W * 3]) for y in range(H))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def steer() -> str:
    t = _read_telemetry()
    text = _board_text(t)
    _write_board_html(t, text)
    png_path = BOARD_HTML.with_name("burn_board.png")
    _write_board_png(t, png_path)
    STEER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with STEER_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _utcnow().isoformat(timespec="seconds"),
                             "schema": "burn_steer.v1", "telemetry": t,
                             "board": "dashboard/static/burn_board.html",
                             "retina": "dashboard/static/burn_board.png"},
                            ensure_ascii=False, default=str) + "\n")
    print(text)
    print(f"\nboard: {BOARD_HTML}\nretina: {png_path}")
    return text


if __name__ == "__main__":
    try:
        steer()
    except Exception as e:  # a steerer never dies on one bad pass
        print(f"burn_steer failed: {e}", file=sys.stderr)
        sys.exit(1)
