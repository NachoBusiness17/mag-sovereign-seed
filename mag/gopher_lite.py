"""gopher_lite — the idle-key gopher (2026-09-23, operator: "wire it into our systems
as some sort of useful gopher").

Rides ZAI_API_KEY_2 — the second z.ai Lite pool found sitting idle (probe 09-23: ~1%
used, separate account from the primary lane; KEY_3 probes identical = same account,
second name). Import law applied: this file is the defaults audit —

  SPENDS:    z.ai Lite credits from the KEY_2 pool ONLY (2,000/5h + 10,000/wk per
             z.ai's own meter; the primary lane's pool is never touched).
  GATE:      own daily ceiling (state/fuel/gopher_pacing.jsonl, GOPHER_DAILY_CREDITS,
             default 200 credits ≈ 10.6M tokens — a cap, not a target; set 0 to kill).
  METER:     every call appends a row to logs/provider_usage.jsonl in the estate
             schema with meta.key_env="ZAI_GOPHER_KEY2", so the existing meters see it.
  CHORES:    one per tick, deterministic rotation, tiny prompts (temperature 0,
             max_tokens 800): label-farm (JEV-1: receipts dossier → Fleet-Bench rows)
             and primary-lane census (pure metering, $0).
  KEY SAFETY: key read from .env via flight_recorder; never printed, never logged.
  SSRF LAW:  every outbound https URL passes lite_guard._safe_https_url; redirects
             refused via lite_guard._OPENER. No loopback targets in this file.

CLI: python -m mag.gopher_lite --once | --loop MINUTES | --chore NAME | --status
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag import lite_guard  # noqa: E402  (SSRF validator + no-redirect opener + quota)

PACING = ROOT / "state" / "fuel" / "gopher_pacing.jsonl"
USAGE = ROOT / "logs" / "provider_usage.jsonl"
LABEL_FARM = ROOT / "state" / "fuel" / "label_farm.jsonl"
CENSUS = ROOT / "state" / "fuel" / "free_lane_census.jsonl"
DOSSIER = ROOT / "corpus" / "canon" / "ARISTOCRACY_LEDGER_RECEIPTS_20260923.md"
KEY_VAR = "ZAI_API_KEY_2"
KEY_ENV_LABEL = "ZAI_GOPHER_KEY2"
URL = "https://api.z.ai/api/paas/v4/chat/completions"
MONITOR_URL = lite_guard._MONITOR_URL
MODEL = "glm-4.7-flash"
TOK_PER_CREDIT = 53_000
DEFAULT_CEILING = 200

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _key() -> str:
    try:
        from mag.flight_recorder import load_env
        env = load_env()
    except Exception:
        env = {}
    return (env.get(KEY_VAR) or "").strip()


def _ceiling() -> int:
    try:
        return int(os.environ.get("GOPHER_DAILY_CREDITS", str(DEFAULT_CEILING)))
    except ValueError:
        return DEFAULT_CEILING


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def spent_today_credits() -> float:
    if not PACING.is_file():
        return 0.0
    tokens = 0
    for line in PACING.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict) and r.get("day") == _today():
            tokens += int(r.get("tokens") or 0)
    return tokens / TOK_PER_CREDIT


def gate(door: str, est_tokens: int) -> dict:
    ceiling = _ceiling()
    if ceiling <= 0:
        return {"ok": False, "why": "GOPHER_DAILY_CREDITS=0 (kill switch)"}
    spent = spent_today_credits()
    if spent + est_tokens / TOK_PER_CREDIT > ceiling:
        return {"ok": False, "why": f"daily ceiling {ceiling} credits reached (spent {spent:.2f})"}
    return {"ok": True, "spent": spent, "ceiling": ceiling}


def record(tokens: int, note: str) -> None:
    PACING.parent.mkdir(parents=True, exist_ok=True)
    with PACING.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"day": _today(), "ts": datetime.now(timezone.utc).isoformat(),
                            "tokens": tokens, "credits": tokens / TOK_PER_CREDIT, "note": note}) + "\n")


def meter_row(model: str, tokens: int, ok: bool, note: str) -> None:
    """Same schema as the estate's provider_usage.jsonl so existing meters see the lane."""
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(), "provider": "z_ai3", "model": model,
            "calls": 1, "prompt_tokens": 0, "completion_tokens": tokens, "cache_hit_tokens": 0,
            "cache_miss_tokens": tokens, "session_id": "gopher-lite", "latency_ms": 0,
            "tokens": tokens, "ok": ok,
            "meta": {"key_env": KEY_ENV_LABEL, "door": note}}) + "\n")


def _post_json(url: str, payload: dict, key: str, timeout: int = 180) -> dict | None:
    """The only outbound door: https + SSRF validator + no-redirect opener (Mimosa law)."""
    if not lite_guard._safe_https_url(url):
        raise RuntimeError("SSRF guard rejected url")
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with lite_guard._OPENER.open(req, timeout=timeout) as r:        return json.loads(r.read().decode())


def chat(prompt: str, door: str) -> dict:
    k = _key()
    if not k:
        return {"ok": False, "error": f"{KEY_VAR} absent in .env"}
    g = gate(door, est_tokens=4000)
    if not g.get("ok"):
        return {"ok": False, "error": g["why"]}
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": 3000,
               "thinking": {"type": "disabled"}}
    try:
        try:
            d = _post_json(URL, payload, k)
        except Exception as first:
            # some GLM endpoints reject the thinking param — retry plain (reasoning fallback below)
            payload.pop("thinking", None)
            try:
                d = _post_json(URL, payload, k)
            except Exception:
                raise first
    except Exception as e:
        meter_row(MODEL, 0, False, door + " fail " + type(e).__name__)
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)[:120]}
    msg = d["choices"][0]["message"]
    text = (msg.get("content") or "").strip()
    used_reasoning_fallback = False
    if not text:
        text = (msg.get("reasoning_content") or "").strip()
        used_reasoning_fallback = bool(text)
    tokens = int(d.get("usage", {}).get("total_tokens") or 0)
    record(tokens, door)
    meter_row(MODEL, tokens, bool(text), door + ("" if text else " EMPTY_CONTENT"))
    if not text:
        return {"ok": False, "error": "empty content (reasoning ate the budget)", "tokens": tokens}
    return {"ok": True, "text": text, "tokens": tokens,
            "reasoning_fallback": used_reasoning_fallback,
            "spent_credits_today": round(spent_today_credits(), 3)}


def chore_label_farm() -> dict:
    if not DOSSIER.is_file():
        return {"ok": False, "error": "dossier missing"}
    head = DOSSIER.read_text(encoding="utf-8", errors="replace")[:9000]
    r = chat("Turn these verified receipt rows into Fleet-Bench labeled rows. "
             "Output ONLY JSONL, one object per receipt family: "
             '{"claim":"...","tier":"stranger-replayable|contested|do-not-post",'
             '"anchor_url":"...","label":"capture|deception|experiment|trafficking|money"}. '
             "No prose.\n\n" + head, "label-farm")
    if r.get("ok"):
        LABEL_FARM.parent.mkdir(parents=True, exist_ok=True)
        with LABEL_FARM.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                "rows": r["text"][:4000]}) + "\n")
        r["wrote"] = str(LABEL_FARM)
    return r


def chore_census() -> dict:
    """$0 chore: read the meters, append a census row. No LLM call. No loopback targets."""
    row: dict = {"ts": datetime.now(timezone.utc).isoformat()}
    try:
        from mag import lite_guard as lg
        q = lg.provider_quota()
        row["primary_lite_weekly_remaining"] = (q or {}).get("weekly_remaining")
    except Exception as e:
        row["primary_lite_weekly_remaining"] = "err:" + type(e).__name__
    try:
        from mag.flight_recorder import load_env
        k = (load_env().get(KEY_VAR) or "").strip()
        if k and lite_guard._safe_https_url(MONITOR_URL):
            req = urllib.request.Request(MONITOR_URL, headers={"Authorization": "Bearer " + k})
            with lite_guard._OPENER.open(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        else:
            d = {}
        lim = (d.get("data", {}).get("limits") or [{}])[0]
        row["gopher_key2_remaining"] = lim.get("remaining")
        row["gopher_key2_pct"] = lim.get("percentage")
    except Exception as e:
        row["gopher_key2_remaining"] = "err:" + type(e).__name__
    CENSUS.parent.mkdir(parents=True, exist_ok=True)
    with CENSUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return {"ok": True, "census": row, "tokens": 0}


CHORES = {"label-farm": chore_label_farm, "census": chore_census}


def run_once(chore: str | None = None) -> dict:
    if chore is None:
        # deterministic rotation: alternate by UTC hour
        chore = ("label-farm", "census")[int(datetime.now(timezone.utc).strftime("%H")) % 2]
    fn = CHORES.get(chore)
    if fn is None:
        return {"ok": False, "error": "unknown chore " + chore}
    out = fn()
    out["chore"] = chore
    return out


def status() -> dict:
    return {"spent_credits_today": round(spent_today_credits(), 3),
            "ceiling": _ceiling(), "key_var": KEY_VAR,
            "key_present": bool(_key()),
            "ledger": str(PACING), "label_farm_rows": LABEL_FARM.is_file(),
            "census_rows": CENSUS.is_file()}


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--status" in args:
        print(json.dumps(status(), indent=1))
    elif "--loop" in args:
        i = args.index("--loop")
        mins = int(args[i + 1]) if len(args) > i + 1 else 60
        while True:
            print(json.dumps(run_once()))
            time.sleep(mins * 60)
    else:
        chore = args[args.index("--chore") + 1] if "--chore" in args else None
        print(json.dumps(run_once(chore), indent=1))
