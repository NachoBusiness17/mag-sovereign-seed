"""LITE PACING GUARD — law 15 made structural (2026-09-05).

Root failure (operator: "the lite subscription key is fucking me again"): every
automatic door (swarm default, rib_chat cache-mining, scheduled lane shifts) rode
the Lite key because each was BUILT while Lite was believed the $0 lane. The
09-05 promo verdict proved Lite metered (2,000 credits/5h + 10,000/wk, real
credits, ~53K tok/credit) and no structure flipped with the belief. Prose laws
don't execute; this ledger does.

Rule: automatic doors may ride z_ai3/Lite only under the daily pacing ceiling —
law 15's durable fix (~1,400 of the 10,000/wk pool per day). Lite stays what
ZAI_LITE_LAW always said it is: a burst lane, not a default carrier.

Ledger: state/fuel/lite_pacing.jsonl (append-only, mounted, survives recreates).
Units: rows carry billable tokens; credits = tokens / TOK_PER_CREDIT.

Lever: env LITE_DAILY_CREDITS=0 disables the ceiling (operator emergency only);
LITE_WEEKLY_RESET names the next weekly pool refill for the denial message.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "fuel" / "lite_pacing.jsonl"
TOK_PER_CREDIT = 53_000  # measured 09-04 on the cache-farming doctrine (billing rows)
DEFAULT_CEILING = 1400   # law 15: 10,000/wk pool paced over 7 days

# ── PROVIDER SIDE OF THE METER (found 09-05, Ponytail half of the salon) ──────────
# The undocumented monitor endpoints z.ai's own subscription UI calls (door found
# via openusage's provider notes; verified live with the Lite key same hour — 200
# OK, billed nothing). Reads need only the key: NO browser, NO Google tap. The
# Google accounts (nachobusinesscorp@gmail.com / ESTATE_USERrtron@gmail.com) are only
# needed for dashboard WRITES (quota reset button etc).
_MONITOR_URL = "https://api.z.ai/api/monitor/usage/quota/limit"
_MODEL_USAGE_URL = "https://api.z.ai/api/monitor/usage/model-usage"
_TOOL_USAGE_URL = "https://api.z.ai/api/monitor/usage/tool-usage"
_SUBSCRIPTION_URL = "https://api.z.ai/api/biz/subscription/list"
_KEY_VARS = ("ZAI_API_KEY_Lite", "ZAI_API_KEY_L", "ZAI_API_KEY_LITE", "ZAI_API_KEY")
_QUOTA_LOG = ROOT / "state" / "fuel" / "lite_quota_log.jsonl"
_CACHE: dict = {"ts": 0.0, "data": None}
_CACHE_TTL = 600.0  # the meter moves slowly; doors re-read at most every 10 min


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _safe_https_url(url: str) -> bool:
    """Mimosa SSRF guard (mirrors lane_runner): https only, host must resolve to a
    PUBLIC address, redirects refused. Blocks private/loopback/link-local/metadata."""
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme != "https" or not p.hostname:
            return False
        for info in socket.getaddrinfo(p.hostname, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


def _ceiling() -> int:
    try:
        v = int(os.environ.get("LITE_DAILY_CREDITS", str(DEFAULT_CEILING)))
    except ValueError:
        return DEFAULT_CEILING
    return v


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _refill_note() -> str:
    reset = os.environ.get("LITE_WEEKLY_RESET", "").strip()
    if reset:
        return f"weekly pool refills {reset}"
    return "weekly pool refills on the ~7-day cycle (last observed rollover 2026-09-05)"


def spent_today() -> float:
    """Credits burned today (UTC) per the ledger; unreadable rows are skipped, not fatal."""
    if not LEDGER.is_file():
        return 0.0
    today = _today()
    tokens = 0
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001 — a bad line never bricks the fleet
            continue
        if isinstance(r, dict) and r.get("day") == today:
            tokens += int(r.get("tokens") or 0)
    return tokens / TOK_PER_CREDIT


def _key() -> str:
    for v in _KEY_VARS:
        k = os.environ.get(v, "").strip()
        if k:
            return k
    try:  # host-side callers: .env at call time (values never logged/echoed)
        from mag.flight_recorder import load_env
        env = load_env()
        for v in _KEY_VARS:
            k = env.get(v, "").strip()
            if k:
                return k
    except Exception:  # noqa: BLE001
        pass
    return ""


def provider_quota(force: bool = False) -> dict | None:
    """Live provider truth: the weekly pool + 5h bucket straight from z.ai's monitor
    endpoint. Cached 10 min; every successful read appends to lite_quota_log.jsonl
    so the weekly ledger-vs-provider delta has a trail. None on any failure."""
    now = time.time()
    if not force and _CACHE["data"] is not None and now - _CACHE["ts"] < _CACHE_TTL:
        return _CACHE["data"]
    key = _key()
    if not key or not _safe_https_url(_MONITOR_URL):
        return None
    try:
        req = urllib.request.Request(_MONITOR_URL, headers={
            "Authorization": "Bearer " + key, "User-Agent": "opencode/1.0"})
        with _OPENER.open(req, timeout=15) as r:
            d = json.loads(r.read())
        data = d.get("data") or {}
        session = weekly = None
        for L in data.get("limits") or []:
            if L.get("type") != "CREDIT_LIMIT":
                continue
            win = {"used": L.get("currentValue"), "limit": L.get("usage"),
                   "remaining": L.get("remaining"), "pct": L.get("percentage"),
                   "resets_at_ms": L.get("nextResetTime")}
            if L.get("unit") == 3:      # hours-unit window = the 5h bucket (unit 3, number 5)
                session = win
            else:                        # multi-day window = the weekly pool (unit 6, number 1)
                weekly = win
        out = {"level": data.get("level"), "session": session, "weekly": weekly, "ts": now}
        _CACHE.update(ts=now, data=out)
        try:
            _QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
            with _QUOTA_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"schema": "lite_quota.v1",
                                    "ts": datetime.now(timezone.utc).isoformat(),
                                    "weekly": weekly, "session": session}) + "\n")
        except Exception:  # noqa: BLE001 — bank, not break
            pass
        return out
    except Exception:  # noqa: BLE001 — meter unreachable -> fail-safe, not fail-shut
        return None


def usage_detail(start: str, end: str) -> dict | None:
    """The dashboard's graphs, raw — no browser needed. Per-model token totals,
    hourly series, call counts, and z.ai-MCP tool counts for a window
    ('YYYY-MM-DD HH:MM:SS' strings, vendor timezone). NOTE: tool-usage tracks
    z.ai's OWN MCP tools, NOT client apps — per-window attribution comes from
    ledger-delta (this guard's ledger vs these provider totals)."""
    key = _key()
    if not key:
        return None
    qs = urllib.parse.urlencode({"startTime": start, "endTime": end})
    out: dict = {}
    for name, base in (("model", _MODEL_USAGE_URL), ("tool", _TOOL_USAGE_URL)):
        if not _safe_https_url(base):
            return None
        try:
            req = urllib.request.Request(base + "?" + qs, headers={
                "Authorization": "Bearer " + key, "User-Agent": "opencode/1.0"})
            with _OPENER.open(req, timeout=15) as r:
                out[name] = json.loads(r.read()).get("data") or {}
        except Exception:  # noqa: BLE001 — partial detail beats none
            out[name] = {}
    try:
        _QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
        summary = {"model": {r.get("modelName"): r.get("totalTokens")
                             for r in out["model"].get("modelSummaryList") or []},
                   "calls": sum(out["model"].get("modelCallCount") or []),
                   "tokens": sum(t for t in (out["model"].get("tokensUsage") or [])
                                 if isinstance(t, (int, float)))}
        with _QUOTA_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"schema": "lite_usage_detail.v1",
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "window": [start, end], **summary}) + "\n")
    except Exception:  # noqa: BLE001 — bank, not break
        pass
    return out


def _dynamic_ceiling(configured: int) -> int:
    """Law-15 teeth: clamp the daily ceiling to what the ACTUAL remaining pool affords
    until the weekly reset (remaining / days_left). Meter unreachable -> configured
    (fail-safe). configured <= 0 stays the unlimited operator lever."""
    if configured <= 0:
        return configured
    w = (provider_quota() or {}).get("weekly") or {}
    rem, reset = w.get("remaining"), w.get("resets_at_ms")
    if not rem or not reset:
        return configured
    days = max((reset / 1000 - time.time()) / 86400, 0.25)
    return max(1, min(configured, int(rem / days)))


def check(door: str) -> dict:
    """Gate for any automatic door about to touch the Lite key. ceiling<=0 = unlimited."""
    c = _dynamic_ceiling(_ceiling())
    s = spent_today()
    out = {"ok": c <= 0 or s < c, "spent": round(s, 2), "ceiling": c, "door": door}
    if not out["ok"]:
        reset = ((provider_quota() or {}).get("weekly") or {}).get("resets_at_ms")
        when = (datetime.fromtimestamp(reset / 1000, tz=timezone.utc).strftime("%b %d %H:%MZ")
                if reset else _refill_note())
        out["deny"] = (f"lite daily pacing ceiling spent {out['spent']}/{c} credits "
                       f"(law 15) — daily ledger resets 00:00Z; weekly pool refills {when}")
    return out


def record(door: str, tokens: int, note: str = "") -> None:
    """Bank billable tokens for a Lite call that actually went out. Silent-fail."""
    if tokens <= 0:
        return
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        row = {"schema": "lite_pacing.v1", "ts": datetime.now(timezone.utc).isoformat(),
               "day": _today(), "door": door, "tokens": int(tokens)}
        if note:
            row["note"] = str(note)[:200]
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001 — bank, not break
        pass


def status() -> dict:
    """Human surface: today's pacing state + live provider truth (for lanes.html /
    the room / the economist's weekly delta check)."""
    c = _dynamic_ceiling(_ceiling())
    s = spent_today()
    q = provider_quota() or {}
    w = q.get("weekly") or {}
    return {"spent_credits": round(s, 2), "ceiling": c,
            "pct": round(100 * s / c, 1) if c > 0 else None,
            "ledger": str(LEDGER),
            "provider_weekly_used": w.get("used"), "provider_weekly_remaining": w.get("remaining"),
            "provider_resets_at_ms": w.get("resets_at_ms"),
            "refill": _refill_note()}
