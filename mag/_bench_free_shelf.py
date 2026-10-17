"""Bench the OpenRouter free-model shelf across both keys (2026-08-25).

Self-steal: the shelf already exists (17 :free models, 2 keys). Measure which
actually answer, how fast, and which are throttled. Tiny calls only (max_tokens=8).
"""
import json, os, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")

# load keys from .env (names only, never printed)
keys = {}
for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line.startswith("OPENROUTER_API_KEY") or line.startswith("OR_API_KEY"):
        k, _, v = line.partition("=")
        if v.strip() and not v.strip().startswith("#"):
            keys[k.strip()] = v.strip()

KEY1 = keys.get("OPENROUTER_API_KEY") or keys.get("OR_API_KEY") or ""
KEY2 = keys.get("OPENROUTER_API_KEY_2") or keys.get("OR_API_KEY_2") or ""
print("keys: key1=" + str(bool(KEY1)) + " key2=" + str(bool(KEY2)))

d = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=15))
models = sorted(m["id"] for m in d.get("data", []) if m["id"].endswith(":free"))

def call(model, key):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
        "max_tokens": 8,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            j = json.loads(r.read().decode())
            return "ok", round(time.time() - t0, 1)
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}", round(time.time() - t0, 1)
    except Exception as e:
        return str(e)[:40], round(time.time() - t0, 1)

results = []
for m in models:
    s, ms = call(m, KEY1)
    used = "key1"
    if not s.startswith("ok") and KEY2:
        s2, ms2 = call(m, KEY2)
        if s2.startswith("ok"):
            s, ms, used = s2, ms2, "key2"
    results.append((m, s, ms, used))

ok = [r for r in results if r[1].startswith("ok")]
print(f"\nOK {len(ok)}/{len(results)}")
for m, s, ms, used in results:
    print(f"  {'OK ' if s.startswith('ok') else '-- '} {m:55} {s:12} {ms}s {used}")
