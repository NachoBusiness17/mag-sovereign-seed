"""whale_patrol.py — watched-channel tracker + ping organ (v1, 2026-09-08).

The seat (automation session) does the PULLING and COMPOSING (WebSearch / browser door).
This organ does the BOOKKEEPING: track posts, decode snowflake ages, record our replies,
compute engagement deltas (what the algo is doing to us), write pings, export the feed.

Usage:
  python -m mag.whale_patrol track --url <post_url> [--handle H] [--text T]
        [--counts "replies/rt/likes"] [--time <iso>] [--reply <our_reply_url>]
        [--draft <draft_text>] [--note N]
  python -m mag.whale_patrol reply --post <post_url> --url <our_reply_url> [--draft D]
  python -m mag.whale_patrol census              # spread deltas + Astra verdicts
  python -m mag.whale_patrol ping "message"      # write watch/PING + room row
  python -m mag.whale_patrol feed                # regenerate dashboard feed json
  python -m mag.whale_patrol watchlist           # print watched handles

Laws: files-are-the-body (everything lands in watch/whale_tracker.jsonl);
Astra verdicts (SUPPORTED if carried within 48h, DISPUTED silence, UNPROVEN rest);
no echo of secrets; no auto-posting (the operator fires, the patrol arms).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRACKER = REPO / "watch" / "whale_tracker.jsonl"
WATCHLIST = REPO / "configs" / "watched_channels.yaml"
PING_FILE = REPO / "watch" / "PING"
FEED_JSON = REPO / "dashboard" / "static" / "data" / "whale_feed.json"
ROOM = REPO / "watch" / "room.jsonl"

SNOWFLAKE_EPOCH = 1288834974657  # ms


def decode_snowflake(status_id: int) -> str | None:
    try:
        ms = (status_id >> 22) + SNOWFLAKE_EPOCH
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


def post_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url or "")
    return m.group(1) if m else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def age_hours(iso: str) -> float:
    try:
        return (datetime.now(timezone.utc)
                - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception:
        return -1.0


def parse_counts(s: str):
    # "replies/rt/likes" -> dict; tolerates blanks "​//3" or "90/132/2.1K"
    def num(x):
        x = x.strip().replace(",", "")
        if not x:
            return 0
        if x.endswith("K"):
            return int(float(x[:-1]) * 1000)
        if x.endswith("M"):
            return int(float(x[:-1]) * 1_000_000)
        try:
            return int(x)
        except ValueError:
            return 0
    parts = (s or "//").split("/")
    while len(parts) < 3:
        parts.append("")
    return {"replies": num(parts[0]), "reposts": num(parts[1]), "likes": num(parts[2])}


def load_rows():
    if not TRACKER.exists():
        return []
    rows = []
    for line in TRACKER.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def append_row(row: dict):
    TRACKER.parent.mkdir(parents=True, exist_ok=True)
    with TRACKER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def room_log(text: str):
    try:
        with ROOM.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now_iso(), "seat": "zcode",
                                "event": "whale_patrol", "thread": "operator",
                                "text": text[:600]}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def latest_by_post(rows):
    """Latest observation row per post id, plus original post row."""
    posts, obs = {}, {}
    for r in rows:
        if r["event"] == "post":
            posts[r["post_id"]] = r          # first sighting wins (original state)
        elif r["event"] == "observe":
            obs[r["post_id"]] = r            # latest observation wins
    return posts, obs


def cmd_track(args):
    url = args.url
    pid = post_id(url)
    if not pid:
        print(json.dumps({"ok": False, "error": "no status id in url"}))
        return 1
    created = args.time or decode_snowflake(int(pid)) or ""
    row = {
        "ts": now_iso(), "event": "post", "post_id": pid, "url": url,
        "handle": args.handle or "", "text": (args.text or "")[:500],
        "created_at": created, "age_h_at_track": round(age_hours(created), 1) if created else None,
        "counts": parse_counts(args.counts), "our_reply_url": args.reply or "",
        "our_draft": (args.draft or "")[:600], "note": args.note or "",
    }
    append_row(row)
    feed()
    print(json.dumps({"ok": True, "tracked": pid, "age_h": row["age_h_at_track"]}))
    return 0


def cmd_reply(args):
    pid = post_id(args.post)
    rows = load_rows()
    target = None
    for r in reversed(rows):
        if r["event"] == "post" and r["post_id"] == pid:
            target = r
            break
    if not target:
        print(json.dumps({"ok": False, "error": "post not tracked; track it first"}))
        return 1
    append_row({
        "ts": now_iso(), "event": "replied", "post_id": pid,
        "our_reply_url": args.url, "our_draft": (args.draft or "")[:600],
        "baseline_counts": target["counts"],
    })
    feed()
    print(json.dumps({"ok": True, "marked_replied": pid}))
    return 0


def cmd_observe(args):
    pid = post_id(args.url)
    if not pid:
        print(json.dumps({"ok": False, "error": "no status id"}))
        return 1
    append_row({
        "ts": now_iso(), "event": "observe", "post_id": pid, "url": args.url,
        "counts": parse_counts(args.counts),
        "carried": args.carried,  # yes|no|? — did a stranger quote/reply-in-kind
    })
    feed()
    print(json.dumps({"ok": True, "observed": pid, "counts": parse_counts(args.counts)}))
    return 0


def cmd_census(args):
    rows = load_rows()
    posts, obs = latest_by_post(rows)
    out = []
    for pid, p in posts.items():
        base = p["counts"]
        cur = obs.get(pid, {}).get("counts", base)
        carried = obs.get(pid, {}).get("carried", "?")
        replied = any(r["event"] == "replied" and r["post_id"] == pid for r in rows)
        d_replies = cur["replies"] - base["replies"]
        d_likes = cur["likes"] - base["likes"]
        verdict = "UNPROVEN"
        if carried == "yes":
            verdict = "SUPPORTED"
        elif replied and carried == "no":
            verdict = "DISPUTED"
        out.append({
            "handle": p["handle"], "post_id": pid, "age_h": round(age_hours(p["created_at"]), 1),
            "we_replied": replied,
            "spread": {"replies": f"+{d_replies}", "likes": f"+{d_likes}"},
            "astra_verdict": verdict, "note": p.get("note", ""),
        })
    out.sort(key=lambda x: -(x["age_h"] if x["age_h"] >= 0 else 1e9))
    print(json.dumps({"ok": True, "census": out}, indent=1))
    return 0


def cmd_ping(args):
    PING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PING_FILE.write_text(f"{now_iso()}  {args.message}\n", encoding="utf-8")
    room_log("PING: " + args.message)
    print(json.dumps({"ok": True, "pinged": args.message}))
    return 0


def watched_handles():
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8"))
        return [w["handle"] for w in cfg.get("watched", [])]
    except Exception:
        # regex fallback — no yaml dep
        return re.findall(r"handle:\s*(\w+)", WATCHLIST.read_text(encoding="utf-8"))


def cmd_watchlist(args):
    print(json.dumps({"ok": True, "watched": watched_handles()}))
    return 0


def feed():
    rows = load_rows()
    posts, obs = latest_by_post(rows)
    items = []
    for pid, p in posts.items():
        cur = obs.get(pid, {}).get("counts", p["counts"])
        replied = any(r["event"] == "replied" and r["post_id"] == pid for r in rows)
        reply_row = next((r for r in reversed(rows)
                          if r["event"] == "replied" and r["post_id"] == pid), None)
        items.append({
            "handle": p["handle"], "url": p["url"], "text": p["text"],
            "created_at": p["created_at"], "age_h": round(age_hours(p["created_at"]), 1),
            "counts_at_track": p["counts"], "counts_now": cur,
            "we_replied": replied, "our_reply_url": (reply_row or {}).get("our_reply_url", p.get("our_reply_url", "")),
            "our_draft": (reply_row or {}).get("our_draft") or p.get("our_draft", ""),
            "note": p.get("note", ""),
        })
    items.sort(key=lambda x: x["age_h"])
    ping = ""
    if PING_FILE.exists():
        ping = PING_FILE.read_text(encoding="utf-8").strip()
    try:
        handles = watched_handles()
    except Exception:
        handles = []
    FEED_JSON.parent.mkdir(parents=True, exist_ok=True)
    FEED_JSON.write_text(json.dumps({
        "generated": now_iso(), "ping": ping,
        "watched": handles, "tracked": items,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_feed(args):
    feed()
    print(json.dumps({"ok": True, "feed": str(FEED_JSON), "tracked": len(feed_items())}))
    return 0


def feed_items():
    if FEED_JSON.exists():
        return json.loads(FEED_JSON.read_text(encoding="utf-8")).get("tracked", [])
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.whale_patrol")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("track")
    t.add_argument("--url", required=True)
    t.add_argument("--handle", default="")
    t.add_argument("--text", default="")
    t.add_argument("--counts", default="//")
    t.add_argument("--time", default="")
    t.add_argument("--reply", default="")
    t.add_argument("--draft", default="")
    t.add_argument("--note", default="")
    t.set_defaults(fn=cmd_track)

    r = sub.add_parser("reply")
    r.add_argument("--post", required=True)
    r.add_argument("--url", required=True)
    r.add_argument("--draft", default="")
    r.set_defaults(fn=cmd_reply)

    o = sub.add_parser("observe")
    o.add_argument("--url", required=True)
    o.add_argument("--counts", default="//")
    o.add_argument("--carried", default="?")
    o.set_defaults(fn=cmd_observe)

    c = sub.add_parser("census")
    c.set_defaults(fn=cmd_census)

    p = sub.add_parser("ping")
    p.add_argument("message")
    p.set_defaults(fn=cmd_ping)

    w = sub.add_parser("watchlist")
    w.set_defaults(fn=cmd_watchlist)

    f = sub.add_parser("feed")
    f.set_defaults(fn=cmd_feed)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
