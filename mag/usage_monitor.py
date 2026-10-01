"""usage_monitor — LIVE API-usage monitoring to catch cache-miss / cost spikes BEFORE they hit.

Operator RULE (2026-08-11): "as a rule we need to monitor live api use data to catch this shit
before it hits. Training! https://platform.deepseek.com/usage"

WHAT THIS DOES (deterministic + $0, module functions only):
  1. watch(rows, window) — ROLLING-WINDOW spike detection on the LIVE per-request feed
     (logs/provider_usage.jsonl, which we already write with cache_hit/miss per request). This is the
     real-time "before it hits" source: a burst of miss tokens from one mid-context edit is caught on
     the rolling window, not after the hourly bill.
  2. check_now(...) — sample the recent window right now; if a spike is present, FOLD it immediately
     as a training signal (behavioral_event kind=cache_miss_spike) so the 50x tax is never invisible
     and the system learns its own bursts live.
  3. live_poll(...) — BEST-EFFORT cross-check against the authoritative DeepSeek usage page
     (platform.deepseek.com/usage) via mag.browser_driver if available. Never fails the monitor if the
     page/auth isn't reachable — the local live feed is the always-on signal.
  4. The RULE itself is surfaced via rule() so the cadence/autorun can enforce "monitor live usage."

Schema: usage_monitor.v1 · deterministic + $0 · reuse: cost_learn spike thresholds, behavioral_analytics
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "usage_monitor.v1"
USAGE = ROOT / "logs" / "provider_usage.jsonl"
# re-use cost_learn's spike thresholds as the default (single source of truth for "what's a spike")
try:
    from mag.cost_learn import MISS_SPIKE_THRESHOLD as _T
    MISS_SPIKE_THRESHOLD = _T
except Exception:
    MISS_SPIKE_THRESHOLD = 100_000
MISS_RATIO_SPIKE = 0.20
ROLLING_WINDOW_REQS = 60   # detect over the last N requests (live, not hourly)
ROLLING_WINDOW_MIN = 5     # or the last N minutes, whichever is tighter


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_recent(n: int = 2000) -> list[dict[str, Any]]:
    if not USAGE.is_file():
        return []
    out = []
    try:
        for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def watch(rows: list[dict[str, Any]] | None = None, *, window: int = ROLLING_WINDOW_REQS,
          minutes: float = ROLLING_WINDOW_MIN) -> dict[str, Any]:
    """Rolling-window spike detection on live usage. Miss burst (50x tax) caught here, live."""
    rows = rows if rows is not None else _read_recent()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)

    def _parse(s):
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception:
            return now

    recent_t = [r for r in rows if (now - _parse(str(r.get("ts") or ""))) <= timedelta(minutes=minutes)]
    hit = sum(int(r.get("cache_hit_tokens") or 0) for r in recent_t)
    miss = sum(int(r.get("cache_miss_tokens") or 0) for r in recent_t)
    tin = hit + miss
    ratio = miss / tin if tin else 0.0
    is_spike = (miss >= MISS_SPIKE_THRESHOLD) or (ratio >= MISS_RATIO_SPIKE)
    return {"schema": SCHEMA, "ts": _now_iso(), "rows_in_window": len(recent_t),
            "hit_tokens": int(hit), "miss_tokens": int(miss),
            "hit_ratio": round(hit / tin, 4) if tin else None,
            "is_spike": is_spike, "threshold": MISS_SPIKE_THRESHOLD,
            "likely_cause": "mid_context_edit" if is_spike else "normal",
            "note": "monitor live usage to catch cache-miss before it hits the bill"}


def check_now(*, fold: bool = True) -> dict[str, Any]:
    """Sample the live window now; if a spike is present, fold it as a training signal immediately."""
    w = watch()
    if fold and w["is_spike"]:
        try:
            from mag.behavioral_analytics import log_behavioral_event
            log_behavioral_event(
                kind="cache_miss_spike",
                detail=f"LIVE miss={w['miss_tokens']:,} ratio={w['hit_ratio']} "
                       f"window={w['rows_in_window']} cause={w['likely_cause']} BEFORE bill")
            w["folded"] = True
        except Exception as e:
            w["fold_error"] = str(e)[:120]
    w["folded"] = w.get("folded", False)
    return w


def live_poll(*, url: str = "https://platform.deepseek.com/usage", fallback: bool = True) -> dict[str, Any]:
    """BEST-EFFORT cross-check of the authoritative DeepSeek usage page via browser_driver.
    Never fails the monitor: if the page/auth isn't reachable, falls back to the local live feed.
    FIX (2026-08-11): browser_driver has NO fetch_text/page_text — only open_url/connect/ask, so
    the old browser path silently fell back to local. Use connect() + page.inner_text instead."""
    page_text = None
    try:
        from mag import browser_driver
        c = browser_driver.connect()
        if c.get("ok") and browser_driver._host_allowed(url):
            page = c["page"]
            page.goto(url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            try:
                page_text = page.locator("body").inner_text()[:6000]
            except Exception:
                page_text = page.content()[:6000]
            try:
                page.close()
                c["page"]._mag_pw.stop()
            except Exception:
                pass
    except Exception as e:
        page_text = None
    if page_text:
        return {"ok": True, "schema": SCHEMA, "source": url, "page": page_text,
                "note": "browser path (connect+inner_text); login/auth are operator-owned"}
    if fallback:
        return {"ok": True, "schema": SCHEMA, "source": url, "note": "browser not reachable or not "
                "allowlisted; using local live feed", "local": watch()}
    return {"ok": False, "schema": SCHEMA, "source": url, "error": "not reachable"}


def rule() -> dict[str, Any]:
    """The standing operator rule: monitor live API usage to catch spikes before they hit."""
    return {"ok": True, "schema": SCHEMA, "rule": "monitor live api use data (provider_usage.jsonl + "
            "platform.deepseek.com/usage) to catch cache-miss/cost spikes BEFORE they hit; fold each "
            "spike as a training signal (cache_miss_spike). URL: https://platform.deepseek.com/usage",
            "threshold_miss_tokens": MISS_SPIKE_THRESHOLD, "threshold_ratio": MISS_RATIO_SPIKE}


def status() -> dict[str, Any]:
    w = watch()
    return {"ok": True, "schema": SCHEMA, "live_feed": str(USAGE.relative_to(ROOT)).replace("\\", "/"),
            "window_reqs": ROLLING_WINDOW_REQS, "window_min": ROLLING_WINDOW_MIN,
            "current": w, "rule": rule()["rule"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="usage-monitor")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "watch", "check", "rule", "poll"])
    a = ap.parse_args()
    import json as _j
    if a.cmd == "watch":
        print(_j.dumps(watch(), indent=2, default=str))
    elif a.cmd == "check":
        print(_j.dumps(check_now(), indent=2, default=str))
    elif a.cmd == "rule":
        print(_j.dumps(rule(), indent=2, default=str))
    elif a.cmd == "poll":
        print(_j.dumps(live_poll(), indent=2, default=str))
    else:
        print(_j.dumps(status(), indent=2, default=str))
