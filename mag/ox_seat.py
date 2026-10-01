"""ox_seat — the free frontier reasoning seat for stealth/ox-alpha, BOUNDED so we can burn it down.

WHY THIS EXISTS (2026-08-22): ox-alpha (stealth/ox-alpha via OpenRouter) is a FREE frontier
reasoning model built for long-horizon agentic/coding/security work. Verified: HTTP 200, real
content, cost 0, reasoning_details live, cached-token shared-prefix working. BUT the stock
architecture path (models.providers.chat_openrouter -> chat_provider) does an UNBOUNDED blocking
non-streaming call that HANGS on ox-alpha's slow reasoning (E2E P50 ~18s, worst far worse). To
actually USE the seat at scale, we bound the call: max_tokens + a hard timeout, pull content, report
cost. This is the deterministic handle that makes the free seat burnable to our ends.

CONTRACT / HONESTY:
  * T2+ PUBLIC only — ox-alpha is a retained-log provider (prompts retained, not used for training).
    Never route T0/T1 (private/live) here. That's the OPSEC routing policy.
  * Free NOW ("use it while you can") — if the bill stops being $0, this seat stops being the
    default. It is an on-demand seat, not a permanent dependency.
  * reasoning is ON by default on this model; we bound max_tokens so the response returns fast.

Schema: ox_seat.v1 · deterministic wrapper over a free frontier seat · cost reported per call
CLI: python -m mag.ox_seat chat "<prompt>" [--system "..."] [--max-tokens 400] | status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ox_seat.v1"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# PROVEN SAFE WIDTH (probed 2026-08-23, operator-confirmed 2026-08-24): 8. At 16 and 32 the
# seat throttles (429/empty -> the whole batch is junk). This semaphore is the HARD CEILING at
# the choke point — no caller (drill, burn, swarm, channel) can exceed 8 concurrent calls.
MAX_CONCURRENT = 8
_seat_slot = threading.BoundedSemaphore(MAX_CONCURRENT)

# The operator runs TWO OpenRouter accounts (nacho + fostertron/SD) as two pools — each key
# is its own concurrency/free window. Using BOTH (rotating per call) doubles the burn.
_KEY_ENVS = ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2", "OR_API_KEY", "OR_API_KEY_2")
_key_rotation = 0


def _load_keys() -> list[str]:
    """All distinct OpenRouter keys available (env first, then .env). Never from the CLI."""
    found: list[str] = []
    for name in _KEY_ENVS:
        v = os.environ.get(name, "") or ""
        if v:
            v = v.strip().strip('"').strip("'")
            if v and v not in found:
                found.append(v)
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            for name in _KEY_ENVS:
                if s.startswith(f"{name}="):
                    v = s.split("=", 1)[1].strip().strip('"').strip("'")
                    if v and v not in found:
                        found.append(v)
    return found


def _load_key() -> str:
    """Rotating key picker (2026-08-24): use BOTH operator accounts — each call lands on the
    next key so both pools burn the free window. Reads env then .env; never the command line."""
    global _key_rotation
    keys = _load_keys()
    if not keys:
        return ""
    _key_rotation += 1
    return keys[_key_rotation % len(keys)]


def _load_model() -> str:
    m = os.environ.get("OPENROUTER_MODEL", "")
    if m:
        return m
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("OPENROUTER_MODEL="):
                return s.split("=", 1)[1].strip()
    return "stealth/ox-alpha"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def chat(system: str = "", user: str = "", *, max_tokens: int = 400,
         timeout: int = 120, tier: str = "T2", model: str | None = None) -> dict[str, Any]:
    """Bounded chat call to the free frontier seat. T2+ public only (retained-log provider).
    Returns content + cost + cache telemetry. Honest: raises/handles HTTP errors.
    `model` overrides OPENROUTER_MODEL (used by the dedicated AOS agent to target DeepSeek)."""
    if tier in ("T0", "T1"):
        return {"ok": False, "schema": SCHEMA, "error": f"refused: tier {tier} may not touch the "
                                                        "retained-log remote seat"}
    key = _load_key()
    if not key:
        return {"ok": False, "schema": SCHEMA, "error": "no OPENROUTER_API_KEY in .env"}
    model = model or _load_model()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        with _seat_slot:  # max 8 concurrent calls — 16/32 throttle (proven)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "schema": SCHEMA, "model": model, "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "model": model,
                "error": f"{type(e).__name__}: {str(e)[:200]}"}
    ch = (b.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    usage = b.get("usage") or {}
    pd = usage.get("prompt_tokens_details") or {}
    return {
        "ok": True, "schema": SCHEMA, "model": b.get("model") or model,
        "content": msg.get("content"),
        "reasoning": msg.get("reasoning") or msg.get("reasoning_details"),
        "finish_reason": ch.get("finish_reason"),
        "cost": usage.get("cost", 0),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cached_tokens": pd.get("cached_tokens", 0),
        "ts": _now(),
        "note": "free frontier reasoning seat, bounded call (retained-log provider, T2+ only)",
    }


def status() -> dict[str, Any]:
    keys = _load_keys()
    return {"ok": True, "schema": SCHEMA, "model": _load_model(),
            "keys_set": len(keys),
            "key_accounts": "both (nacho + fostertron/SD), rotating per call" if len(keys) > 1
                             else ("one" if keys else "none"),
            "max_concurrent": MAX_CONCURRENT,
            "contract": "chat(system, user, max_tokens, timeout) -> bounded call to the free seat; "
                        "reports content + cost + cache telemetry; T2+ only (retained-log provider); "
                        "hard-capped at 8 concurrent (16/32 throttle)",
            "cost": "free while the stealth preview holds ('use it while you can'); on-demand seat, "
                    "not a default"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="ox-seat")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "chat"])
    ap.add_argument("prompt", nargs="?", default="")
    ap.add_argument("--system", default="You are the free frontier reasoning seat for a sovereign "
                                         "swarm. Answer with substance, concretely, no fluff.")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()
    if a.cmd == "chat":
        print(json.dumps(chat(a.system, a.prompt, max_tokens=a.max_tokens, timeout=a.timeout),
                         indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
