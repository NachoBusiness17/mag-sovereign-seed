"""swarm_snapshot — the fortress board + the overseer's eye (DFHack, day one).

The Operator's frame (2026-09-05): the fleet is Dwarf Fortress; our toolsets are
DFHack — we can read the RUNNING process memory (db tables, room tape, chain,
cards) the way DFHack reads dwarf thoughts. This organ is the first overlay:

    collect  14 days of live state from the fleet's memory surfaces ($0, stdlib)
    render   ONE PNG "fortress board" (4 panels, block bars, no text —
             the vision model reads PATTERN, the digest anchors NUMBERS)
    read     the local vision model (ollama qwen2.5vl:3b on the drive) studies
             board + digest together and reports anomalies the numbers miss
    bank     memory/runs/swarm_snapshot/<ts>/ board.png digest.txt vision_read.md

Surfaces read (the memory addresses DFHack would map):
    db model_usage   burn by model/day/agent + error counts   (api face)
    db sessions      distinct seats active per day             (behavioral face)
    watch/room.jsonl events per day by seat                   (society face)
    verkle_chain     knots sealed per day                      (memory face)
    watch/*.md       cards filed per day                       (archaeology face)

CLI:
    python -m mag.swarm_snapshot            # collect + render + vision read
    python -m mag.swarm_snapshot --no-read  # board + digest only

Falsifier: the vision read is scored against the digest — every number it claims
is checked; hit-rate printed in the receipt. A board the eye cannot read at
better than chance gets redesigned, not believed.
"""

from __future__ import annotations

import argparse
import base64
import collections
import datetime as dt
import json
import sqlite3
import struct
import urllib.request
import zlib
from pathlib import Path

HOME = Path.home()
DB = HOME / ".zcode" / "cli" / "db" / "db.sqlite"
REPO = Path(__file__).resolve().parent.parent
ROOM = REPO / "watch" / "room.jsonl"
CHAIN = REPO / "memory" / "biography" / "verkle_chain.jsonl"
WATCH = REPO / "watch"
OUT = REPO / "memory" / "runs" / "swarm_snapshot"
OLLAMA = "http://127.0.0.1:11434/api/generate"
OLLAMA_ALLOWED = {("http", "127.0.0.1", 11434)}  # loopback-only, fleet law
VISION_MODEL = "qwen2.5vl:3b"
DAYS = 14


def _guard_url(url: str) -> None:
    """Fence (Mimosa): protocol + host + port allowlist, no inference from input."""
    from urllib.parse import urlparse
    p = urlparse(url)
    if (p.scheme, p.hostname, p.port) not in OLLAMA_ALLOWED:
        raise ValueError("endpoint outside allowlist: %r" % url)


# ---------- collect ----------

def day_key(epoch_ms: int) -> str:
    return dt.datetime.fromtimestamp(epoch_ms / 1000, dt.timezone.utc).strftime("%m-%d")


def days_back(n: int) -> list:
    now = dt.datetime.now(dt.timezone.utc)
    return [(now - dt.timedelta(days=i)).strftime("%m-%d") for i in range(n - 1, -1, -1)]


def collect() -> dict:
    days = days_back(DAYS)
    cut = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DAYS)).timestamp() * 1000)
    d = {"days": days, "burn_by_model": collections.defaultdict(lambda: collections.defaultdict(int)),
         "burn_by_agent": collections.defaultdict(int), "sessions_per_day": collections.defaultdict(set),
         "errors_per_day": collections.defaultdict(int), "room_per_day": collections.defaultdict(int),
         "room_by_seat": collections.defaultdict(int), "chain_per_day": collections.defaultdict(int),
         "cards_per_day": collections.defaultdict(int), "totals": {}}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        for started, model, agent, sess, tok, err in con.execute(
                "SELECT started_at, model_id, agent, session_id, computed_total_tokens, error_type "
                "FROM model_usage WHERE started_at > ? AND computed_total_tokens IS NOT NULL", (cut,)):
            dk = day_key(started)
            d["burn_by_model"][model][dk] += tok
            d["burn_by_agent"][agent or "?"] += tok
            if sess:
                d["sessions_per_day"][dk].add(sess)
            if err:
                d["errors_per_day"][dk] += 1
    finally:
        con.close()
    if ROOM.exists():
        for line in ROOM.open(encoding="utf-8", errors="replace"):
            try:
                row = json.loads(line)
                d["room_per_day"][row.get("ts", "")[5:10]] += 1
                d["room_by_seat"][row.get("seat", "?")] += 1
            except Exception:
                pass
    if CHAIN.exists():
        for line in CHAIN.open(encoding="utf-8", errors="replace"):
            try:
                d["chain_per_day"][json.loads(line).get("ts", "")[5:10]] += 1
            except Exception:
                pass
    for p in WATCH.glob("*.md"):
        dk = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).strftime("%m-%d")
        d["cards_per_day"][dk] += 1
    d["totals"] = {
        "total_tokens_14d": sum(sum(m.values()) for m in d["burn_by_model"].values()),
        "errors_14d": sum(d["errors_per_day"].values()),
        "room_events_14d": sum(d["room_per_day"].values()),
        "cards_14d": sum(d["cards_per_day"].values()),
        "agents_active": len(d["burn_by_agent"]),
    }
    return d


# ---------- render (stdlib PNG, technique stolen from burn_steer.py) ----------

def render(d: dict, path: Path) -> None:
    W, H = 960, 640
    px = bytearray(bytes((16, 16, 22)) * (W * H))

    def rect(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(H, y1)):
            base = y * W
            for x in range(max(0, x0), min(W, x1)):
                i = (base + x) * 3
                px[i:i + 3] = bytes(c)

    GREEN, AMBER, RED, WHITE, CYAN, PURPLE, PINK = ((57, 211, 128), (240, 180, 70), (240, 90, 90),
                                                    (235, 235, 235), (80, 200, 220), (170, 130, 240),
                                                    (240, 120, 180))
    pal = [GREEN, CYAN, PURPLE, AMBER, PINK]
    days = d["days"]
    models = sorted(d["burn_by_model"], key=lambda m: -sum(d["burn_by_model"][m].values()))[:3]

    def bar_frame(panel):
        x0, y0, x1, y1, hc = panel
        rect(x0, y0, x1, y0 + 14, hc)
        rect(x0 + 2, y0 + 22, x1 - 2, y1 - 14, (34, 34, 44))
        for i in range(0, DAYS, 7):
            slot = (x1 - x0 - 16) / DAYS
            bx = int(x0 + 8 + i * slot + slot / 2)
            rect(bx, y1 - 12, bx + 2, y1 - 8, (90, 90, 104))

    def draw_bars(panel, series, color):
        x0, y0, x1, y1, _ = panel
        vals = [series.get(day, 0) for day in days]
        mx = max(vals) or 1
        slot = (x1 - x0 - 16) / DAYS
        bw = max(6, int(slot * 0.7))
        for i, v in enumerate(vals):
            bh = int((y1 - 14 - (y0 + 22)) * v / mx)
            bx = int(x0 + 8 + i * slot + (slot - bw) / 2)
            rect(bx, y1 - 14 - bh, bx + bw, y1 - 14, color)

    # panel A: stacked top-3 model burn (MTok/day)
    pa = (30, 30, 470, 300, (30, 80, 50))
    pb = (490, 30, 930, 300, (30, 60, 90))
    pc = (30, 340, 470, 610, (80, 40, 80))
    pd = (490, 340, 930, 610, (90, 70, 30))
    bar_frame(pa)
    x0, y0, x1, y1, _ = pa
    model_series = {m: {day: d["burn_by_model"][m].get(day, 0) / 1e6 for day in days} for m in models}
    daily_tot = {day: sum(model_series[m].get(day, 0) for m in models) for day in days}
    mx = max(daily_tot.values()) or 1
    slot = (x1 - x0 - 16) / DAYS
    bw = max(6, int(slot * 0.7))
    for i, day in enumerate(days):
        yb = y1 - 14
        for mi, m in enumerate(models):
            bh = int((y1 - 14 - (y0 + 22)) * model_series[m].get(day, 0) / mx)
            bx = int(x0 + 8 + i * slot + (slot - bw) / 2)
            rect(bx, yb - bh, bx + bw, yb, pal[mi])
            yb -= bh
    # panel B: seats active per day (white) + error ticks (red)
    bar_frame(pb)
    draw_bars(pb, {day: len(d["sessions_per_day"].get(day, ())) for day in days}, WHITE)
    ex0, ey0, ex1, ey1, _ = pb
    emx = max(list(d["errors_per_day"].values()) + [1])
    eslot = (ex1 - ex0 - 16) / DAYS
    for i, day in enumerate(days):
        e = d["errors_per_day"].get(day, 0)
        if e:
            eh = max(4, int(50 * e / emx))
            bx = int(ex0 + 8 + i * eslot + eslot / 2)
            rect(bx, ey0 + 22, bx + 3, ey0 + 22 + eh, RED)
    # panel C: room events/day (pink); panel D: chain knots/day (amber)
    bar_frame(pc)
    draw_bars(pc, {day: d["room_per_day"].get(day, 0) for day in days}, PINK)
    bar_frame(pd)
    draw_bars(pd, {day: d["chain_per_day"].get(day, 0) for day in days}, AMBER)
    # header strip: one lit square per seat that burned in the window
    for i in range(min(d["totals"]["agents_active"], 40)):
        rect(30 + i * 22, 8, 30 + i * 22 + 16, 20, pal[i % len(pal)])

    raw = b"".join(b"\x00" + bytes(px[y * W * 3:(y + 1) * W * 3]) for y in range(H))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 6))
                     + chunk(b"IEND", b""))


# ---------- digest ----------

def digest(d: dict) -> str:
    L = ["SWARM SNAPSHOT DIGEST %s (14 days to %s)" % (
        dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), d["days"][-1]), ""]
    t = d["totals"]
    L += ["CENSUS: %.1fB tokens 14d | %d seats | %d errors | %d room events | %d chain knots (14d) | %d cards"
          % (t["total_tokens_14d"] / 1e9, t["agents_active"], t["errors_14d"], t["room_events_14d"],
             sum(d["chain_per_day"].values()), t["cards_14d"]), ""]
    L.append("BURN BY MODEL (MTok/day, last 14 days; top-3 drawn as stacked bars panel A):")
    for m in sorted(d["burn_by_model"], key=lambda m: -sum(d["burn_by_model"][m].values()))[:6]:
        tot = sum(d["burn_by_model"][m].values())
        row = " ".join("%5.1f" % (d["burn_by_model"][m].get(day, 0) / 1e6) for day in d["days"])
        L.append("  %-22s %10.1fM tot | %s" % (m, tot / 1e6, row))
    L.append("")
    L.append("BURN BY AGENT (seat, 14d total):")
    for a, v in sorted(d["burn_by_agent"].items(), key=lambda kv: -kv[1])[:10]:
        L.append("  %-20s %10.1fM" % (a, v / 1e6))
    L.append("")
    L.append("SESSIONS/DAY (distinct seats): " + " ".join(str(len(d["sessions_per_day"].get(day, ()))) for day in d["days"]))
    L.append("ERRORS/DAY (model_usage error_type): " + " ".join(str(d["errors_per_day"].get(day, 0)) for day in d["days"]))
    L.append("ROOM EVENTS/DAY: " + " ".join(str(d["room_per_day"].get(day, 0)) for day in d["days"]))
    L.append("ROOM BY SEAT (14d): " + ", ".join("%s=%d" % kv for kv in sorted(d["room_by_seat"].items(), key=lambda kv: -kv[1])[:8]))
    L.append("CHAIN KNOTS/DAY: " + " ".join(str(d["chain_per_day"].get(day, 0)) for day in d["days"]))
    L.append("CARDS FILED/DAY: " + " ".join(str(d["cards_per_day"].get(day, 0)) for day in d["days"]))
    return "\n".join(L)


# ---------- the overseer's eye ----------

def vision_read(png: Path, digest_text: str) -> str:
    _guard_url(OLLAMA)
    b64 = base64.b64encode(png.read_bytes()).decode()
    prompt = (
        "You are the DFHack overseer of an AI-agent fortress. Panel A = daily token burn, "
        "stacked bars for top-3 models (14 days). Panel B = distinct seats active per day, "
        "with RED ticks above for daily error counts. Panel C = room tape events per day. "
        "Panel D = chain knots sealed per day. Squares in the top strip = seats that burned.\n"
        "Below is the exact numbers digest. Compare what you SEE against the numbers: report "
        "(1) shape of the burn (rising/falling/spiky) and which days peak, (2) any anomaly the "
        "bars reveal that the digest numbers hide (gaps, one-day spikes, error bursts), "
        "(3) one operational recommendation for the fortress. Be concrete, no filler.\n\n" + digest_text)
    req = urllib.request.Request(OLLAMA, data=json.dumps({
        "model": VISION_MODEL, "prompt": prompt, "stream": False,
        "images": [b64], "options": {"num_predict": 400, "temperature": 0.2}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=420) as r:
        return json.loads(r.read()).get("response", "")


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(prog="mag.swarm_snapshot")
    ap.add_argument("--no-read", action="store_true", help="board + digest only, skip vision")
    a = ap.parse_args()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT / ts
    out.mkdir(parents=True, exist_ok=True)
    d = collect()
    png = out / "board.png"
    render(d, png)
    dig = digest(d)
    (out / "digest.txt").write_text(dig, encoding="utf-8")
    print("[board] %s (%d KB)" % (png, png.stat().st_size // 1024))
    print(dig.split("BURN BY AGENT")[0])
    if a.no_read:
        return
    print("[eye] %s is looking..." % VISION_MODEL)
    try:
        read = vision_read(png, dig)
    except Exception as e:
        read = "(the overseer is blind this pass: %s)" % e
        print(read)
    (out / "vision_read.md").write_text("# OVERSEER READ (%s, %s)\n\n%s\n" % (VISION_MODEL, ts, read), encoding="utf-8")
    if not read.startswith("("):
        print(read[:1200])
    print("[banked] %s" % out)


if __name__ == "__main__":
    main()
