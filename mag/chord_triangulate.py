"""chord_triangulate — the X field instrument (deterministic scan of the stochastic feed).

Operator teaching (2026-09-06): he posted "1112" three times across two accounts — 14h
apart, then a 3-second echo from the organ account @GHOST_HANDLE — so the seat would
discover that X's own metadata (timestamps, deltas, ratios) is a deterministic invariant
field, explorable like our visual tools (lightmap, burn_board, swarm_snapshot).

Law: deep self-steal — every noisy field we conquered, we conquered by finding the
deterministic invariant inside it. X was still read as vibes. Now it is scanned.

Invariants (all from the fxtwitter mirror, $0, no auth, two-strike bail):
  dt          — seconds between posts (the echo latency)
  identical   — byte-equal content (the chord)
  view_vel    — views per hour since posting (reach velocity)
  like_ratio  — likes/views (engagement quality, scale-free)
  cold_start  — views ÷ follower count (the rising-tide baseline)
  echo_class  — seed / reseed / echo (by author-pair + dt)

SSRF guard (Mimosa 2026-09-06): scheme+host FIXED to the fxtwitter mirror, user/sid
strictly validated, host pre-resolved with public-IP enforcement, redirects refused.

Usage: python mag/chord_triangulate <user/id or id> ... (>=2 posts)
Output: ASCII chord field to stdout + JSON to watch/receipts/chord_<ts>.json
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

MIRROR = "https://api.fxtwitter.com/{user}/status/{sid}"
UA = {"User-Agent": "chord_triangulate/1.0 (fleet field instrument; fxtwitter mirror)"}
OUT_DIR = ROOT / "watch" / "receipts"

ALLOWED_HOST = "api.fxtwitter.com"
ALLOWED_URL_PREFIX = f"https://{ALLOWED_HOST}/"
_USER_RE = re.compile(r"^[A-Za-z0-9_]{1,20}$")
_SID_RE = re.compile(r"^[0-9]{10,25}$")


def _validate(user: str, sid: str) -> tuple[str, str] | None:
    if not _USER_RE.match(user or "") or not _SID_RE.match(sid or ""):
        return None
    return user, sid


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # refuse every redirect
        raise urllib.error.HTTPError(a[1], 302, "redirects refused by policy", a[3], None)


_OPENER = urllib.request.build_opener(_NoRedirect)


def _guard_host(host: str) -> None:
    """Resolve and refuse any non-public address (anti-SSRF, anti-DNS-rebinding:
    resolution is checked immediately before each request)."""
    for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"refusing non-public resolved address: {ip}")


def _get(url: str, timeout: int = 30):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != ALLOWED_HOST:
        raise ValueError("blocked non-allowlisted url")
    _guard_host(parts.hostname)
    req = urllib.request.Request(url, headers=UA)
    with _OPENER.open(req, timeout=timeout) as r:
        return json.load(r)


def fetch(user: str, sid: str, strikes: int = 2) -> dict | None:
    """fxtwitter fetch, two-strike bail (fleet law)."""
    v = _validate(user, sid)
    if not v:
        raise ValueError(f"invalid tokens: {user!r}/{sid!r}")
    url = MIRROR.format(user=v[0], sid=v[1])
    for attempt in range(strikes):
        try:
            t = _get(url).get("tweet")
            if t:
                return t
        except Exception:
            time.sleep(2.0 * (attempt + 1))
    return None


def parse_ts(t: dict) -> float:
    """fxtwitter carries created_timestamp (epoch, reliable); created_at is
    Twitter-format ('Sun Sep 06 03:12:14 +0000 2026') when present."""
    ts = t.get("created_timestamp")
    if ts:
        return float(ts)
    s = t.get("created_at") or ""
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").timestamp()
    except ValueError:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def scan(posts: list[dict]) -> dict:
    out: dict = {"scanned": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "points": []}
    for t in posts:
        au = t["author"]["screen_name"]
        created = parse_ts(t)
        ts_epoch = created
        views = int(t.get("views") or 0)
        likes = int(t.get("likes") or 0)
        followers = max(1, int(t["author"].get("followers") or 1))
        age_h = max(1 / 3600.0, (time.time() - created) / 3600.0)
        out["points"].append({
            "author": au,
            "id": t.get("id"),
            "ts": t["created_at"],
            "text": (t.get("text") or "").strip(),
            "_ts": created,
            "dt_prev_s": None,
            "identical_prev": None,
            "echo_class": "seed",
            "view_vel_per_h": round(views / age_h, 1),
            "like_ratio": round(likes / views, 4) if views else 0.0,
            "cold_start": round(views / followers, 3),
            "followers": followers,
        })
    out["points"].sort(key=lambda p: parse_ts(p["_raw_ts_dict"])) if False else out["points"].sort(key=lambda p: p["_ts"])
    for i in range(1, len(out["points"])):
        prev, cur = out["points"][i - 1], out["points"][i]
        cur["dt_prev_s"] = round(cur["_ts"] - prev["_ts"], 1)
        cur["identical_prev"] = (cur["text"] == prev["text"])
        cur["echo_class"] = ("echo" if (cur["identical_prev"] and cur["author"] != prev["author"]
                                        and cur["dt_prev_s"] <= 60) else "reseed")
    out["chord"] = all(p["identical_prev"] for p in out["points"][1:]) if len(out["points"]) > 1 else False
    first_author = out["points"][0]["author"] if out["points"] else None
    out["min_echo_latency_s"] = min(
        (p["dt_prev_s"] for p in out["points"][1:] if p["author"] != first_author),
        default=None)
    return out


def render(field: dict) -> str:
    L = ["CHORD FIELD — deterministic scan of the stochastic feed",
         f"scanned {field['scanned']} | chord={'YES' if field['chord'] else 'no'} | "
         f"min cross-author latency={field['min_echo_latency_s']}s", ""]
    for p in field["points"]:
        bar = "#" * max(1, min(40, int(p["view_vel_per_h"] / 5) or 1))
        L.append(f"{p['echo_class'].upper():6s} @{p['author'][:18]:18s} {p['ts']}  "
                 f"dt_prev={str(p['dt_prev_s'])}s  vel={p['view_vel_per_h']}v/h {bar}")
        L.append(f"        cold_start={p['cold_start']} (views/follower)  "
                 f"like_ratio={p['like_ratio']}  text={p['text'][:40]!r}")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    posts = []
    for arg in argv:
        arg = arg.strip().replace("https://x.com/", "").replace("http://x.com/", "")
        if "/" in arg:
            user, sid = arg.rsplit("/", 1)
        else:
            user, sid = "NachoQuixotic", arg
        try:
            t = fetch(user, sid)
        except ValueError as e:
            print(f"[chord] blocked: {e}", file=sys.stderr)
            continue
        if not t:
            print(f"[chord] two-strike bail on {user}/{sid}", file=sys.stderr)
            continue
        posts.append(t)
    if len(posts) < 2:
        print("need >=2 resolvable posts", file=sys.stderr)
        return 1
    field = scan(posts)
    print(render(field))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"chord_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(field, indent=1), encoding="utf-8")
    print(f"\nfield saved: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
