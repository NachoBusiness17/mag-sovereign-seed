#!/usr/bin/env python3
"""BURST PROBE 2026-09-03 — measure the fleet's lanes live. Keys loaded from .env, NEVER printed.
Network guard: single hardcoded https URL, host validated against an allowlist before every request."""
import json, time, urllib.request, urllib.error, urllib.parse, threading, os, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env"), encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            ENV[k.strip()] = v.strip()

ALLOWED_HOST = "api.z.ai"
ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
KEY_MAIN = ENV.get("ZAI_API_KEY", "")
KEY_PRO = ENV.get("ZAI_API_KEY_Pro", ENV.get("ZAI_API_KEY_PRO", KEY_MAIN))


def call(model, prompt, key, max_tokens=8, thinking=None, timeout=75):
    parsed = urllib.parse.urlparse(ENDPOINT)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        raise ValueError("blocked: endpoint must be https://%s" % ALLOWED_HOST)
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    if thinking:
        body["thinking"] = thinking
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return (r.status, time.time() - t0, None)
    except urllib.error.HTTPError as e:
        try:
            code = json.loads(e.read()).get("error", {}).get("code")
        except Exception:
            code = "HTTP%d" % e.code
        return (e.code, time.time() - t0, code)
    except Exception as e:
        return (0, time.time() - t0, type(e).__name__)


def wave(n, fn):
    out, threads, barrier = [], [], threading.Barrier(n)

    def run(i):
        barrier.wait()
        out.append(fn(i))

    for i in range(n):
        t = threading.Thread(target=run, args=(i,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return out


def summarize(tag, results):
    ok = [lat for status, lat, _ in results if status == 200]
    errs = {}
    for status, _, code in results:
        if status != 200:
            errs[str(code)] = errs.get(str(code), 0) + 1
    if ok:
        p95 = sorted(ok)[max(0, int(len(ok) * 0.95) - 1)]
        lat = "p50=%.1fs p95=%.1fs max=%.1fs" % (statistics.median(ok), p95, max(ok))
    else:
        lat = "n/a"
    print("%s: %d/%d ok | %s | errors: %s" % (tag, len(ok), len(results), lat, errs or "none"))


if __name__ == "__main__":
    print("=== A. single-call latency x3 (judgment + budget lanes) ===")
    for model, key in [("glm-5.3-flash", KEY_PRO), ("glm-5.3", KEY_PRO),
                       ("glm-4-32b-0414-128k", KEY_PRO), ("glm-4.5-flash", KEY_MAIN)]:
        rs = [call(model, "Reply with exactly: ok %d" % i, key) for i in range(3)]
        summarize("%s x3 serial" % model, rs)

    print("=== B. 5.3-flash concurrency ladder (Pro credit key) ===")
    for n in (10, 25, 50):
        rs = wave(n, lambda i: call("glm-5.3-flash", "nonce %d: reply ok" % i, KEY_PRO))
        summarize("5.3-flash x%d simultaneous" % n, rs)

    print("=== C. 4.7-flash single-flight + thinking-disabled ping (free) ===")
    rs = wave(2, lambda i: call("glm-4.7-flash", "nonce %d: reply ok" % i, KEY_MAIN))
    summarize("4.7-flash x2 (expect 1 error @conc=1)", rs)
    s, l, c = call("glm-4.7-flash", "Reply ok", KEY_MAIN, max_tokens=16, thinking={"type": "disabled"})
    print("4.7-flash thinking-disabled ping: status=%s code=%s (200=disableable, 1210=forced)" % (s, c))

    print("=== D. 8K free-trial throttle law (4.5-flash, free) ===")
    long_prompt = "summarize: " + ("alpha beta gamma delta " * 2300)
    rs = wave(2, lambda i: call("glm-4.5-flash", long_prompt, KEY_MAIN, max_tokens=16))
    summarize("4.5-flash ~9Ktok x2 (8K law?)", rs)
    rs = wave(2, lambda i: call("glm-4.5-flash", "nonce %d: reply ok" % i, KEY_MAIN, max_tokens=16))
    summarize("4.5-flash short x2 control", rs)
