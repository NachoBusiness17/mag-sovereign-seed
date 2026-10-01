"""probe_route — the probe-before-route gate (LISTING ≠ SERVABLE, 2026-09-13).

THE INCIDENT CLASS: free-lane slugs listed in a catalog or memory card were routed
lanes without a live check. 09-12: stepfun/step-3.7-flash + upstage/solar-pro4
returned HTTP 400 on minimal payloads (gated listings). 09-13: a 20-wide wave
re-fired both anyway — 6 lanes burned — because the recipe note was in memory but
not in the runner. This organ puts the check IN the path.

Gate law: a slug gets lanes only if a minimal-payload probe returned non-empty
content within TTL. HTTP-error = dead. HTTP-ok but empty content twice = flaky
(passes the gate with a warning — thinking models can return None at tiny budgets;
the 09-13 wave false-excluded ling-sante/ling-fin at max_tokens=16, so the probe
budget is now 512, retry 1024 once on empty).

Schema: probe_route.v1
State: state/probe_route.json (verdict cache, TTL default 6h — free-lane
availability flips provider-side; the 09-12→09-13 flip proves 7d is too long).
CLI:
  python -m mag.probe_route probe --url URL --key-env NAME --slugs a,b,c [--json]
  python -m mag.probe_route route  --url URL --key-env NAME --slugs a,b,c [--json]
  python -m mag.probe_route selftest --url URL --key-env NAME   # dogfood receipt
Keys are read from env, never printed.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "probe_route.json"
SCHEMA = "probe_route.v1"
PROBE_TIMEOUT = 25
TTL_HOURS = 6.0
MAX_TOKENS = 512          # amendment: 16 false-killed thinking models (empty content)
RETRY_TOKENS = 1024       # one retry on HTTP-ok-but-empty
# Canonical fallback order when a lane's preferred slug fails the gate (gate owns routing).
FALLBACK_CHAIN = ["inclusionai/ling-3.0-flash-sante:free", "meituan/longcat-2.0:free",
                  "inclusionai/ling-3.0-flash-fin:free", "poolside/laguna-s-2.1:free"]


def _assert_public_https(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"inference-api.nousresearch.com", "openrouter.ai", "api.deepseek.com", "api.z.ai"}:
        raise ValueError(f"blocked host: {parsed.hostname!r}")
    for *_x, sockaddr in socket.getaddrinfo(parsed.hostname, 443):
        if not ipaddress.ip_address(sockaddr[0]).is_global:
            raise ValueError(f"blocked non-public address: {sockaddr[0]}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _post(url: str, key: str, slug: str, max_tokens: int, timeout: int) -> tuple[str | None, str]:
    """Returns (content_or_None, error_or_empty)."""
    payload = {"model": slug, "messages": [{"role": "user", "content": "Say OK."}], "max_tokens": max_tokens}
    try:
        _assert_public_https(url)
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                                     method="POST")
        with _OPENER.open(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()[:80], ""
        return None, ""
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:140]}"


def probe_one(slug: str, url: str, key: str, use_cache: bool = True) -> dict:
    """Probe one slug with TTL cache. Verdict: live | flaky | dead."""
    now = time.time()
    cache = {}
    if use_cache and STATE.is_file():
        try:
            cache = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    hit = cache.get(slug)
    if use_cache and hit and (now - hit.get("ts_epoch", 0)) < TTL_HOURS * 3600 and hit.get("verdict") in {"live", "flaky"}:
        return {**hit, "cached": True}

    t0 = time.time()
    content, err = _post(url, key, slug, MAX_TOKENS, PROBE_TIMEOUT)
    verdict = "flaky"
    if content:
        verdict = "live"
    elif err:  # HTTP-level failure
        verdict = "dead"
    elif not content and not err:
        content2, err2 = _post(url, key, slug, RETRY_TOKENS, PROBE_TIMEOUT)
        if content2:
            verdict = "live"
            err = ""
        else:
            verdict = "flaky" if not err2 else "dead"
            err = err2
    row = {"schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(), "ts_epoch": now,
           "slug": slug, "verdict": verdict, "latency_ms": round((time.time() - t0) * 1000),
           "probe_tokens": MAX_TOKENS, "http_or_content_note": err, "cached": False}
    if not use_cache:
        row["cached"] = False
    cache[slug] = row
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass
    return row


def route(slugs: list[str], url: str, key_env: str) -> dict:
    """The gate: live/flaky slugs pass, dead slugs are excluded with reasons."""
    key = _key(key_env)
    live, excluded = [], []
    for slug in slugs:
        row = probe_one(slug, url, key)
        if row["verdict"] in {"live", "flaky"}:
            live.append(slug)
            if row["verdict"] == "flaky":
                excluded.append({"slug": slug, "reason": "flaky (passes gate, watch it)"})
        else:
            excluded.append({"slug": slug, "reason": f"dead: {row.get('http_or_content_note') or 'no content'}"})
    return {"live": live, "excluded": excluded}


def _key(key_env: str) -> str:
    import os
    return os.environ.get(key_env, "")


def selftest(url: str, key_env: str) -> int:
    """Dogfood receipt: the wave-7 list. stepfun + solar MUST be dead; ling pair must NOT be dead."""
    wave7 = ["inclusionai/ling-3.0-flash-sante:free", "inclusionai/ling-3.0-flash-fin:free",
             "meituan/longcat-2.0:free", "poolside/laguna-s-2.1:free",
             "stepfun/step-3.7-flash:free", "upstage/solar-pro4:free"]
    key = _key(key_env)
    if not key:
        print("SELFTEST FAIL: key env empty")
        return 2
    rows = [probe_one(s, url, key, use_cache=False) for s in wave7]
    by = {r["slug"]: r["verdict"] for r in rows}
    checks = [
        ("stepfun excluded as dead", by.get("stepfun/step-3.7-flash:free") == "dead"),
        ("solar excluded as dead", by.get("upstage/solar-pro4:free") == "dead"),
        ("ling-sante NOT dead (live or flaky)", by.get("inclusionai/ling-3.0-flash-sante:free") in {"live", "flaky"}),
        ("ling-fin NOT dead (live or flaky)", by.get("inclusionai/ling-3.0-flash-fin:free") in {"live", "flaky"}),
        ("longcat live", by.get("meituan/longcat-2.0:free") == "live"),
    ]
    for r in rows:
        print(f"  {r['slug']:45s} {r['verdict']:6s} {r['latency_ms']}ms {r['http_or_content_note']}")
    passed = sum(1 for _, ok in checks if ok)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"SELFTEST {passed}/{len(checks)}")
    return 0 if passed == len(checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="probe_route")
    ap.add_argument("action", choices=["probe", "route", "selftest"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--key-env", required=True)
    ap.add_argument("--slugs", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.action == "selftest":
        return selftest(args.url, args.key_env)
    slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
    if not slugs:
        print("no slugs given")
        return 2
    result = route(slugs, args.url, args.key_env)
    print(json.dumps(result, indent=2) if args.json else
          f"live: {result['live']}\nexcluded: {[e['slug'] for e in result['excluded']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
