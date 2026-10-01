#!/usr/bin/env python3
"""FLIGHT RECORDER v0 (2026-09-03, operator GO late) — every fleet model call becomes a typed
telemetry row, so the burst doctrine (docs/ref/BURST_DOCTRINE_20260903.md) gets re-fit on
production shapes instead of synthetic pings. Coverage thesis: operations must leave records.

Stdlib only. Additive organ: it wraps calls, it never changes call semantics. Fail-open:
a telemetry error prints loudly to stderr and NEVER breaks the wrapped call.

ROW SCHEMA — JSONL append to watch/flight_recorder.jsonl, one row per call:
  {"ts", "lane", "model", "subsystem", "latency_ms", "status", "error_code",
   "in_tok", "out_tok", "cached_tok", "credits_est"}
  - ts          ISO-8601 UTC with milliseconds, e.g. 2026-09-03T23:41:07.123Z
  - status      "ok" | "error"  (latency percentiles in summarize() use ok rows only)
  - error_code  vendor code (e.g. 1302), "HTTP<status>", or exception class name; None when ok
  - in/out/cached_tok  from the response usage block when the wrapped fn returns one,
                normalised across provider usage shapes; else None. cached_tok first
                non-None of: openai usage.prompt_tokens_details.cached_tokens (or flat
                usage.cached_tokens), deepseek usage.prompt_cache_hit_tokens, anthropic
                usage.cache_read_input_tokens. cache_miss_tok captures deepseek
                usage.prompt_cache_miss_tokens when the vendor exposes it (else None).
                in/out_tok fall back to anthropic usage.input_tokens/output_tokens so
                cache share stays computable on every provider.
  - credits_est computed ONLY when the caller passes a rates dict
                ({"in_per_ktok","out_per_ktok","cached_per_ktok"} — credits per 1K tokens).
                NEVER hardcoded here; keys/credentials are never logged and never written rows.

NETWORK GUARD (same pattern as mag/_probe_burst_20260903.py): validate https + host
allowlist BEFORE any request via guard_endpoint(); keys come from .env parsed at call time
via load_env(). The recorder itself opens no sockets — the wrapped fn does.

USAGE EXAMPLE — how the burst probe (mag/_probe_burst_20260903.py) adopts it. Keep the
probe's call() shape, but return the parsed JSON body so usage tokens get captured:

    from flight_recorder import record_call, load_env, guard_endpoint

    ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
    guard_endpoint(ENDPOINT, {"api.z.ai"})            # raises before any request if violated
    KEY = load_env()["ZAI_API_KEY_Pro"]               # .env at call time; never printed

    def chat(model, prompt, key, max_tokens=8, thinking=None, timeout=75):
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens}
        if thinking:
            body["thinking"] = thinking
        req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))          # dict -> usage captured
        except urllib.error.HTTPError as e:                          # vendor error body -> row
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"error": {"code": "HTTP%d" % e.code}}

    RATES = {"glm-5.3-flash": {"in_per_ktok": 0.000075, "out_per_ktok": 0.00025,
                               "cached_per_ktok": 0.0000375}}        # receipted, caller-supplied
    status, resp = record_call(chat, "api", "glm-5.3-flash", "probe",   # lane, model, subsystem positional
                               rates=RATES["glm-5.3-flash"],
                               model="glm-5.3-flash", prompt="nonce 0: reply ok",
                               key=KEY, max_tokens=8)
    # -> one row appended to watch/flight_recorder.jsonl; (status, resp) returned unchanged.

    summarize(subsystem="probe")   # doctrine re-fit surface: count, p50/p95, ok-rate, tokens

Run the built-in dogfood (burst probe re-run through the recorder):
    python mag/flight_recorder.py
"""
import json
import math
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOG = os.path.join(ROOT, "watch", "flight_recorder.jsonl")
ROW_FIELDS = ("ts", "lane", "model", "subsystem", "latency_ms", "status", "error_code",
              "in_tok", "out_tok", "cached_tok", "cache_miss_tok", "credits_est")
_LOCK = threading.Lock()  # JSONL appends are lock-serialised (burst probes are multithreaded)


# ---------------------------------------------------------------- network guard + secrets

def load_env(root=None):
    """Parse .env at call time. Values are returned to the caller and are never logged,
    never echoed, never written to any JSONL row."""
    path = os.path.join(root or ROOT, ".env")
    env = {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def guard_endpoint(endpoint, allowed_hosts):
    """https + host allowlist, validated BEFORE any request. Same law as the burst probe."""
    p = urllib.parse.urlparse(endpoint)
    if p.scheme != "https":
        raise ValueError("blocked: endpoint must be https (got %r)" % p.scheme)
    if p.hostname not in set(allowed_hosts):
        raise ValueError("blocked: host %r not in allowlist %s" % (p.hostname, sorted(allowed_hosts)))
    return True


# ---------------------------------------------------------------- row construction

def _utcnow():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (now.microsecond // 1000)


def _interpret(result):
    """-> (status, error_code, usage_dict). Accepts a parsed JSON dict (preferred), a legacy
    (status, latency, code) tuple from the old probe pattern, or anything (treated as ok)."""
    status, error_code, usage = "ok", None, {}
    if isinstance(result, dict):
        usage = result.get("usage") or {}
        err = result.get("error")
        if err:
            status = "error"
            if isinstance(err, dict):
                error_code = err.get("code", str(err.get("message", "unknown"))[:64])
            else:
                error_code = str(err)[:64]
    elif isinstance(result, (tuple, list)) and result and isinstance(result[0], int):
        status = "ok" if 200 <= result[0] < 300 else "error"
        if status == "error":
            error_code = result[2] if len(result) > 2 and result[2] is not None else "HTTP%d" % result[0]
    return status, error_code, usage


def _extract_tokens(usage):
    """-> (in_tok, out_tok, cached_tok, cache_miss_tok), normalised across provider usage
    shapes. cached_tok is the first non-None of:
      openai    usage.prompt_tokens_details.cached_tokens (or flat usage.cached_tokens)
      deepseek  usage.prompt_cache_hit_tokens          (miss -> cache_miss_tok)
      anthropic usage.cache_read_input_tokens
    in/out_tok fall back to anthropic usage.input_tokens/output_tokens. Unknown shapes
    keep the legacy behaviour (all None); rows written before cache_miss_tok existed
    simply lack the field (readers must .get it)."""
    if not isinstance(usage, dict):
        return None, None, None, None
    in_tok = usage.get("prompt_tokens")
    if in_tok is None:
        in_tok = usage.get("input_tokens")           # anthropic
    out_tok = usage.get("completion_tokens")
    if out_tok is None:
        out_tok = usage.get("output_tokens")         # anthropic
    details = usage.get("prompt_tokens_details")
    cached = None
    for cand in (details.get("cached_tokens") if isinstance(details, dict) else None,
                 usage.get("cached_tokens"),         # openai flat variant
                 usage.get("prompt_cache_hit_tokens"),   # deepseek
                 usage.get("cache_read_input_tokens")):  # anthropic
        if cand is not None:
            cached = cand
            break
    miss = usage.get("prompt_cache_miss_tokens")     # deepseek; None elsewhere
    return in_tok, out_tok, cached, miss


def _credits_est(in_tok, out_tok, cached_tok, rates):
    """credits = ((in-cached)*in_rate + cached*cached_rate + out*out_rate) / 1000.
    Missing cached rate defaults to the input rate (conservative). No rates, no estimate."""
    if not in_tok and not out_tok:
        return None
    in_rate = float(rates.get("in_per_ktok", 0) or 0)
    out_rate = float(rates.get("out_per_ktok", 0) or 0)
    cached_rate = float(rates.get("cached_per_ktok", in_rate) or in_rate)
    cached = cached_tok or 0
    billable_in = max((in_tok or 0) - cached, 0)
    return round((billable_in * in_rate + cached * cached_rate + (out_tok or 0) * out_rate) / 1000.0, 9)


def _emit(row, log_path=None):
    """Fail-open append: telemetry errors are loudly reported on stderr and never propagate."""
    try:
        path = log_path or DEFAULT_LOG
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        line = json.dumps({k: row.get(k) for k in ROW_FIELDS}, ensure_ascii=True)
        with _LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as e:  # noqa: BLE001 - fail-open by design
        sys.stderr.write("[flight_recorder] EMIT FAILED (call result unaffected): %r\n" % (e,))


def record_call(fn, lane, model, subsystem, /, rates=None, log_path=None, **call_kwargs):
    """Wrap ONE API call: run it, time it, emit a typed telemetry row, return (status, result).

    fn is called as fn(**call_kwargs). lane/model/subsystem are POSITIONAL-ONLY so a wrapped
    fn may keep its own `model=` (or `lane=`/`subsystem=`) kwarg without collision.
    `rates` and `log_path` belong to the recorder; every other kwarg is forwarded to fn
    untouched. If fn raises, the error row is emitted and the exception re-raises — the
    recorder observes, it never swallows.
    """
    t0 = time.perf_counter()
    try:
        result = fn(**call_kwargs)
    except Exception as e:  # noqa: BLE001 - re-raised after the row is written
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        code = ("HTTP%s" % e.code) if hasattr(e, "code") and e.code else type(e).__name__
        _emit({"ts": _utcnow(), "lane": lane, "model": model, "subsystem": subsystem,
               "latency_ms": latency_ms, "status": "error", "error_code": code,
               "in_tok": None, "out_tok": None, "cached_tok": None,
               "cache_miss_tok": None, "credits_est": None}, log_path)
        raise
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    status, error_code, usage = _interpret(result)
    in_tok, out_tok, cached_tok, cache_miss_tok = _extract_tokens(usage)
    est = _credits_est(in_tok, out_tok, cached_tok, rates) if rates else None
    _emit({"ts": _utcnow(), "lane": lane, "model": model, "subsystem": subsystem,
           "latency_ms": latency_ms, "status": status, "error_code": error_code,
           "in_tok": in_tok, "out_tok": out_tok, "cached_tok": cached_tok,
           "cache_miss_tok": cache_miss_tok, "credits_est": est}, log_path)
    return status, result


# ---------------------------------------------------------------- the doctrine re-fit surface

def _read_rows(log_path=None):
    path = log_path or DEFAULT_LOG
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001 - a torn row must not kill the summary
                continue
    return rows


def _pctl(sorted_xs, q):
    if not sorted_xs:
        return None
    idx = max(0, min(len(sorted_xs) - 1, int(math.ceil(q * len(sorted_xs))) - 1))
    return sorted_xs[idx]


def _agg(rows):
    lat = sorted(r["latency_ms"] for r in rows if r.get("status") == "ok"
                 and isinstance(r.get("latency_ms"), (int, float)))
    ok = sum(1 for r in rows if r.get("status") == "ok")
    return {
        "count": len(rows), "ok": ok,
        "ok_rate": round(ok / len(rows), 4) if rows else None,
        "p50_ms": _pctl(lat, 0.50), "p95_ms": _pctl(lat, 0.95),
        "in_tok": sum(r.get("in_tok") or 0 for r in rows),
        "out_tok": sum(r.get("out_tok") or 0 for r in rows),
        "cached_tok": sum(r.get("cached_tok") or 0 for r in rows),
        "credits_est": round(sum(r.get("credits_est") or 0 for r in rows), 9),
    }


def summarize(subsystem=None, since=None, log_path=None, out=None):
    """Read the flight recorder JSONL and print per-lane / per-model / per-subsystem:
    count, p50/p95 latency (ok rows only), ok-rate, token totals, credits estimate.
    `since` is an ISO timestamp or any prefix ("2026-09-03T23"). Returns the summary dict.
    This is the surface the burst doctrine gets re-fit on."""
    out = out or sys.stdout
    rows = _read_rows(log_path)
    if since:
        rows = [r for r in rows if str(r.get("ts", "")) >= since]
    if subsystem:
        rows = [r for r in rows if r.get("subsystem") == subsystem]
    total = _agg(rows)
    out.write("=== flight_recorder: %s | rows=%d | subsystem=%s since=%s ===\n" % (
        os.path.basename(log_path or DEFAULT_LOG), total["count"], subsystem or "*", since or "*"))
    out.write("TOTAL: n=%d ok=%.1f%% p50=%sms p95=%sms in=%s out=%s cached=%s credits=%s\n" % (
        total["count"], (total["ok_rate"] or 0) * 100, total["p50_ms"], total["p95_ms"],
        total["in_tok"], total["out_tok"], total["cached_tok"], total["credits_est"]))
    summary = {"total": total, "by_lane": {}, "by_model": {}, "by_subsystem": {}}
    for dim, key in (("by_lane", "lane"), ("by_model", "model"), ("by_subsystem", "subsystem")):
        groups = {}
        for r in rows:
            groups.setdefault(r.get(key) or "?", []).append(r)
        out.write("-- %s --\n" % dim)
        for name in sorted(groups):
            a = _agg(groups[name])
            summary[dim][name] = a
            out.write("  %-22s n=%-4d ok=%6.1f%% p50=%-7s p95=%-7s in=%-8s out=%-7s cached=%-8s credits=%s\n" % (
                str(name)[:22], a["count"], (a["ok_rate"] or 0) * 100,
                a["p50_ms"], a["p95_ms"], a["in_tok"], a["out_tok"], a["cached_tok"], a["credits_est"]))
    return summary


# ---------------------------------------------------------------- first dogfood: the recorder
# eats its own campaign — the burst probe re-run THROUGH record_call (subsystem="probe").
# call() pattern lifted from mag/_probe_burst_20260903.py; wave() thread bug fixed (args=(i,)).

ALLOWED_HOST = "api.z.ai"
ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"

# Caller-supplied rates (credits per kTok). Receipted where the reference has rows;
# Unproven splits marked. Nothing here is secret and nothing is hardcoded inside the recorder.
RATES = {
    "glm-5.3-flash": {"in_per_ktok": 0.000075, "out_per_ktok": 0.00025,
                      "cached_per_ktok": 0.0000375},            # receipted; cached = 50% in
    "glm-5.3": {"in_per_ktok": 0.0014, "out_per_ktok": 0.00462,
                "cached_per_ktok": 0.0007},                     # in receipted; out/cached = law-5 3.3x estimate, Unproven
    "glm-4-32b-0414-128k": {"in_per_ktok": 0.0001, "out_per_ktok": 0.0001,
                            "cached_per_ktok": 0.00005},        # vendor row = single NORMAL rate; split Unproven
}


def api_call(model, prompt, key, max_tokens=8, thinking=None, timeout=75):
    """The probe's call() pattern, returning the parsed JSON body so usage is captured."""
    guard_endpoint(ENDPOINT, {ALLOWED_HOST})
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens}
    if thinking:
        body["thinking"] = thinking
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"error": {"code": "HTTP%d" % e.code}}


def _dogfood():
    env = load_env()
    key_pro = env.get("ZAI_API_KEY_Pro", "")
    key_main = env.get("ZAI_API_KEY", "")
    guard_endpoint(ENDPOINT, {ALLOWED_HOST})
    print("=== FLIGHT RECORDER DOGFOOD 2026-09-03 — burst probe re-run through record_call ===")
    print("[guard] endpoint https://%s allowlisted pre-flight; keys from .env (names only, never values)" % ALLOWED_HOST)
    print("[guard] every call wrapped: record_call(api_call, lane, model, subsystem='probe', ...)")

    def rc(model, prompt, key, lane, max_tokens=8, thinking=None):
        return record_call(api_call, lane, model, "probe", rates=RATES.get(model),
                           model=model, prompt=prompt, key=key,
                           max_tokens=max_tokens, thinking=thinking)

    def wave(n, fn):
        out, threads, barrier = [], [], threading.Barrier(n)

        def run(i):
            barrier.wait()
            out.append(fn(i))

        for i in range(n):
            t = threading.Thread(target=run, args=(i,))  # probe bug fixed: args=(i,)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        return out

    def show(tag, results):
        ok = [lat for st, lat, _ in results if st == "ok"]
        errs = {}
        for st, _, code in results:
            if st != "ok":
                errs[str(code)] = errs.get(str(code), 0) + 1
        if ok:
            lat = "p50=%.1fs p95=%.1fs max=%.1fs" % (
                sorted(ok)[len(ok) // 2], _pctl(sorted(ok), 0.95), max(ok))
        else:
            lat = "n/a"
        print("%s: %d/%d ok | %s | errors: %s" % (tag, len(ok), len(results), lat, errs or "none"))

    def runner(model, prompt, key, lane, **kw):
        t0 = time.perf_counter()
        try:
            st, resp = rc(model, prompt, key, lane, **kw)
            code = resp.get("error", {}).get("code") if isinstance(resp, dict) else None
            return (st, time.perf_counter() - t0, code)
        except Exception as e:  # noqa: BLE001 - transport-level; row already emitted
            return ("error", time.perf_counter() - t0, type(e).__name__)

    print("=== A. single-call latency x3 (judgment + budget lanes) ===")
    for model, key, lane in [("glm-5.3-flash", key_pro, "api"), ("glm-5.3", key_pro, "api"),
                             ("glm-4-32b-0414-128k", key_pro, "api"), ("glm-4.5-flash", key_main, "free")]:
        rs = [runner(model, "Reply with exactly: ok %d" % i, key, lane) for i in range(3)]
        show("%s x3 serial" % model, rs)

    print("=== B. 5.3-flash concurrency ladder (Pro credit key) ===")
    for n in (10, 25, 50):
        rs = wave(n, lambda i: runner("glm-5.3-flash", "nonce %d: reply ok" % i, key_pro, "api"))
        show("5.3-flash x%d simultaneous" % n, rs)

    print("=== C. 4.7-flash single-flight + thinking-disabled ping (free) ===")
    rs = wave(2, lambda i: runner("glm-4.7-flash", "nonce %d: reply ok" % i, key_main, "free"))
    show("4.7-flash x2 (expect 1 error @conc=1)", rs)
    st, resp = rc("glm-4.7-flash", "Reply ok", key_main, "free", max_tokens=16,
                  thinking={"type": "disabled"})
    code = resp.get("error", {}).get("code") if isinstance(resp, dict) else None
    print("4.7-flash thinking-disabled ping: status=%s code=%s (200=disableable, 1210=forced)" % (st, code))

    print("=== D. 8K free-trial throttle law (4.5-flash, free) ===")
    long_prompt = "summarize: " + ("alpha beta gamma delta " * 2300)
    rs = wave(2, lambda i: runner("glm-4.5-flash", long_prompt, key_main, "free", max_tokens=16))
    show("4.5-flash ~9Ktok x2 (8K law?)", rs)
    rs = wave(2, lambda i: runner("glm-4.5-flash", "nonce %d: reply ok" % i, key_main, "free", max_tokens=16))
    show("4.5-flash short x2 control", rs)

    print("=== flight_recorder.summarize(subsystem='probe') — doctrine re-fit surface ===")
    summarize(subsystem="probe")


if __name__ == "__main__":
    _dogfood()
