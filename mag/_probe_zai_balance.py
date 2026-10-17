"""Probe z.ai for a balance/credits endpoint (2026-08-25).

The operator reports AutoClaw shows ~30k credits. Check whether the balance is
programmatically readable via the z.ai API with our key. NEVER print the key.
"""
import json
import os
import sys
import urllib.request
import urllib.error

ROOT = r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent"
# load ZAI_API_KEY from .env without printing it
key = ""
try:
    with open(ROOT + r"\.env", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("ZAI_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
except Exception as e:  # noqa: BLE001
    print("env read error:", e)

if not key:
    print("no ZAI_API_KEY found")
    sys.exit(1)
print("key present:", key[:6] + "...len" + str(len(key)))

endpoints = [
    ("https://api.z.ai/api/paas/v4/credits", "paas/credits"),
    ("https://api.z.ai/api/paas/v4/balance", "paas/balance"),
    ("https://api.z.ai/api/paas/v4/me", "paas/me"),
    ("https://api.z.ai/api/paas/v4/user", "paas/user"),
    ("https://api.z.ai/api/credits", "api/credits"),
    ("https://api.z.ai/api/v1/user/credits", "v1/user/credits"),
    ("https://api.z.ai/api/user/balance", "user/balance"),
]

for url, label in endpoints:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", errors="replace")[:500]
            print(f"[{label}] HTTP {r.status} -> {body}")
    except urllib.error.HTTPError as e:
        print(f"[{label}] HTTP {e.code} -> {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:  # noqa: BLE001
        print(f"[{label}] ERR {type(e).__name__} {str(e)[:120]}")
