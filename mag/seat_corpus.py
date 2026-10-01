"""Seat send corpus — what to send each lane, from Mag bytes + what they told us.

Not a new router. Compiles providers.yaml send laws (thinking, cache, jail,
pack size) with live key-presence and fuel_feed ok-rates. OpenClaw reads the
JSON at /mag/memory/runs/seat_corpus/latest.json.

    .\\.venv\\Scripts\\python.exe -m mag.seat_corpus compile
    .\\.venv\\Scripts\\python.exe -m mag.seat_corpus show deepseek
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _rel_posix(path) -> str:
    """Repo-relative posix path, absolute when outside ROOT.

    Cause (ball3 follow-up sweep 2026-09-29): display/receipt derivations
    raised ValueError whenever the path lived outside the repo (the suite
    runs use an out-of-repo pytest basetemp). Same fix as the driver-meter
    lane's _rel_posix in tools/stealth_driver.py.
    """
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()



SCHEMA = "seat_corpus.v1"
OUT = ROOT / "memory" / "runs" / "seat_corpus" / "latest.json"
PROFILE = ROOT / "memory" / "runs" / "fuel_feed" / "lane_profile.jsonl"

# What Mag measured / they published. Never paste keys.
SEND_LAWS: dict[str, dict[str, Any]] = {
    "ollama": {
        "send": "full local context ok; janitor pack default 1200 chars for ask",
        "why": "free local; T0/T1 allowed",
        "thinking": "n/a",
        "pack_chars": 4000,
        "never": ["pay a remote for scut"],
        "openclaw_ref": "ollama/qwen2.5-coder:7b",
        "cost": "electricity",
        "capture": "always-on janitor",
    },
    "deepseek": {
        "send": "pack+goal only; thinking OFF; disable_thinking in yaml",
        "why": "v4 thinking-on eats max_tokens → empty content (verified 2026-08-03)",
        "thinking": "off",
        "pack_chars": 1800,
        "never": ["T0", "T1", "full chat_history", "thinking on with small max_tokens"],
        "openclaw_ref": "deepseek/deepseek-v4-flash",
        "cost": "paid fallback; cache hits cheap on 1M window",
        "capture": "swarm-scale 30M tok/day budget; cache-mine the prefix",
    },
    "deepseek_overmind": {
        "send": "same as deepseek; second key chain",
        "why": "failover pool",
        "thinking": "off",
        "pack_chars": 1800,
        "never": ["T0", "T1"],
        "openclaw_ref": "deepseek/deepseek-v4-flash",
        "cost": "paid",
        "capture": "explicit --provider deepseek_overmind",
    },
    "z_ai": {
        "send": "opencode/harness only; frozen prefix if raw",
        "why": "coding-plan key; raw API 1305/1302 + fence",
        "thinking": "off",
        "pack_chars": 800,
        "never": ["raw chat_provider as default", "T0"],
        "openclaw_ref": "zai/glm-4.7-flash",
        "cost": "plan quota; 1310 until 2026-09-02",
        "capture": "OpenClaw zai plugin + opencode",
        "opencode_only": True,
    },
    "z_ai2": {
        "send": "frozen FROZEN_SELF + tiny tail; thinking off; glm-4.7-flash",
        "why": "funded Pro; 97-99.9% cache hit measured 2026-08-26",
        "thinking": "off",
        "pack_chars": 400,
        "never": ["volatile prefix", "thinking on"],
        "openclaw_ref": "zai-pro/glm-4.7-flash",
        "cost": "$0 on cache hit",
        "capture": "cache-mine standing self",
    },
    "z_ai3": {
        "send": "same as z_ai2; Lite key; prefer glm-4.5-flash if 4.7 congested",
        "why": "funded Lite cache lane",
        "thinking": "off",
        "pack_chars": 400,
        "never": ["volatile prefix"],
        "openclaw_ref": "zai-lite/glm-4.7-flash",
        "cost": "$0 on cache hit",
        "capture": "cache-mine",
    },
    "z_ai4": {
        "send": "opencode only (coding-plan #2)",
        "why": "same 1310 wall as z_ai until weekly reset",
        "thinking": "off",
        "pack_chars": 800,
        "never": ["raw API as swarm default"],
        "openclaw_ref": "zai-2/glm-4.7-flash",
        "cost": "plan quota",
        "opencode_only": True,
        "capture": "OpenClaw zai-2 lane",
    },
    "groq": {
        "send": "short prompts; dual-key rotation; gpt-oss-120b",
        "why": "free daily; they dropped llama ids (roster 2026-08-24)",
        "thinking": "n/a",
        "pack_chars": 1200,
        "never": ["old llama-* ids"],
        "openclaw_ref": "groq/openai/gpt-oss-120b",
        "cost": "free tier",
        "capture": "fast bulk",
    },
    "openrouter": {
        "send": "pack+goal; disable_thinking; /auto may ignore thinking:off",
        "why": "auto routes to reasoners that eat small budgets (verified)",
        "thinking": "off (may be ignored on /auto — raise max_tokens)",
        "pack_chars": 1500,
        "never": ["tiny max_tokens with /auto"],
        "openclaw_ref": "openrouter/auto",
        "cost": "free lanes + funded account failover",
        "capture": "18 free lanes if rotated",
    },
    "openai": {
        "send": "short pack; gpt-4o-mini default in Mag; OpenClaw catalog is gpt-5.x",
        "why": "paid; Mag defers peak",
        "thinking": "provider default",
        "pack_chars": 1200,
        "never": ["T0", "T1", "dump Mag DNA"],
        "openclaw_ref": "openai/gpt-5.6-sol",
        "cost": "paid",
        "capture": "OpenClaw picker when judgment isn't Grok TUI",
    },
    "xai": {
        "send": "pack+goal; max_completion_tokens not max_tokens",
        "why": "Grok 4.5 deprecated max_tokens; API ≠ this TUI",
        "thinking": "provider",
        "pack_chars": 1800,
        "never": ["confuse with Grok TUI seats"],
        "openclaw_ref": "xai/grok-4.3",
        "cost": "paid",
        "capture": "API when TUI budget is eject",
    },
    "together": {
        "send": "same DeepSeek flash id; thinking off",
        "why": "free trial; Mag pulled from $0 channel when key went paid",
        "thinking": "off",
        "pack_chars": 1500,
        "never": ["assume $0"],
        "openclaw_ref": "together/deepseek-ai/DeepSeek-V4-Pro",
        "cost": "trial/paid",
        "capture": "OpenClaw fallback #2",
    },
    "nvidia": {
        "send": "deepseek-ai/deepseek-v4-flash-0731; short",
        "why": "102 models; flash-0731 verified 3.4s",
        "thinking": "n/a",
        "pack_chars": 1200,
        "never": ["wrong id namespace"],
        "openclaw_ref": "nvidia/deepseek-ai/deepseek-v4-flash-0731",
        "cost": "free credits",
        "capture": "fuel_feed lane",
    },
    "cerebras": {
        "send": "gpt-oss-120b; browser UA in Mag chat_provider",
        "why": "Cloudflare 1010 without UA; llama ids don't exist",
        "thinking": "n/a",
        "pack_chars": 1200,
        "never": ["llama ids", "CEREBAS typo as the only name — Mag aliases it"],
        "openclaw_ref": "cerebras/gpt-oss-120b",
        "cost": "free tier",
        "capture": "~3000 tok/s",
    },
    "google": {
        "send": "GEMINI_API_KEY when filled; flash",
        "why": "empty in Mag .env as of audit",
        "thinking": "adaptive on 3.x",
        "pack_chars": 1200,
        "never": ["claim live without probe"],
        "openclaw_ref": "google/gemini-3.5-flash",
        "cost": "free/paid",
        "capture": "picker ready when key lands",
    },
    "anthropic": {
        "send": "ANTHROPIC_API_KEY when filled",
        "why": "empty in Mag .env as of audit",
        "thinking": "provider",
        "pack_chars": 1800,
        "never": ["T0", "T1"],
        "openclaw_ref": "anthropic/claude-sonnet-5",
        "cost": "paid",
        "capture": "picker ready",
    },
}

# B2-521 DORMANT GATE (2026-09-26): the registry still compiled drive-laws for cerebras and
# nvidia after B2-36/B2-61 declared both dormant (card-gated 30-day trial, chat 402
# no-credit; NVIDIA 410 EOL; mag/doctor.py:607: dormant is a declared state). latest.json
# is what OpenClaw reads to pick a seat, so a dormant row is an invitation to drive a dead
# lane. Dormant provider rows drop out here, the B2-133 law (mag/dormant.py); operator GO
# flips the flag and the rows return with no code edit. Receipt:
# watch/inbox/burn_wave_20260926/B2_521_cerebras_stragglers_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids  # noqa: E402

SEND_LAWS = {pid: law for pid, law in SEND_LAWS.items()
             if pid not in _dormant_provider_ids()}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _key_present(pcfg: dict[str, Any]) -> bool:
    from models.providers import _key_env_names, _api_key
    if pcfg.get("free_local"):
        return True
    if _api_key(pcfg):
        return True
    for n in _key_env_names(pcfg):
        if os.environ.get(n):
            return True
    return False


def _lane_ok_rates(limit: int = 400) -> dict[str, dict[str, float]]:
    if not PROFILE.is_file():
        return {}
    tallies: dict[str, list[int]] = {}
    try:
        lines = PROFILE.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return {}
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        lane = str(row.get("lane") or "")
        if not lane:
            continue
        tallies.setdefault(lane, [0, 0])
        tallies[lane][1] += 1
        if row.get("ok"):
            tallies[lane][0] += 1
    return {k: {"ok": v[0], "n": v[1], "ok_rate": round(v[0] / v[1], 3) if v[1] else 0.0}
            for k, v in tallies.items()}


def compile_corpus() -> dict[str, Any]:
    from models.providers import load_providers, get_provider
    from models.env_load import load_dotenv
    try:
        load_dotenv()
    except Exception:
        pass
    cfg = load_providers()
    rates = _lane_ok_rates()
    lanes: dict[str, Any] = {}
    for pid, law in SEND_LAWS.items():
        pcfg = get_provider(pid) or get_provider({"google": "gemini"}.get(pid, pid)) or {}
        row = dict(law)
        row["id"] = pid
        row["configured"] = bool(pcfg)
        row["key_present"] = _key_present(pcfg) if pcfg else False
        row["models"] = list(pcfg.get("models") or [])[:6]
        row["disable_thinking"] = bool(pcfg.get("disable_thinking"))
        row["opencode_only"] = bool(pcfg.get("opencode_only") or law.get("opencode_only"))
        row["paid"] = bool(pcfg.get("paid"))
        if pid in rates:
            row["fuel_ok_rate"] = rates[pid]
        lanes[pid] = row
    prefer = list((cfg.get("defaults") or {}).get("prefer_order") or [])
    out = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "prefer_order": prefer,
        "law": "pack+goal; thinking off on reasoners; T0/T1 never remote; freeze prefix once",
        "lanes": lanes,
        "openclaw": "read-only /mag/memory/runs/seat_corpus/latest.json — pick model, send this contract",
        "governor": "Mag container+worker only. OpenClaw hooks FILE; they do not supervise.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out["path"] = _rel_posix(OUT)
    return out


def show(lane: str) -> dict[str, Any]:
    data = compile_corpus()
    row = (data.get("lanes") or {}).get(lane)
    if not row:
        return {"ok": False, "error": f"unknown lane {lane}", "known": list((data.get("lanes") or {}))}
    return {"ok": True, "schema": SCHEMA, "lane": row}


def main(argv: list[str] | None = None) -> int:
    import sys
    args = list(argv if argv is not None else sys.argv[1:])
    cmd = args[0] if args else "compile"
    if cmd == "show":
        out = show(args[1] if len(args) > 1 else "")
    else:
        out = compile_corpus()
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
