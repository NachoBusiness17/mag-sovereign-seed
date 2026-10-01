"""seat_probe — ask EVERY agent how it wants to be interacted with (the OX lesson, generalized).

OX taught us (2026-08-24): asking the seat how to prompt it returns a concrete protocol
(OX prescribed the structured task envelope — GOAL/CONSTRAINTS/SUCCESS/OUTPUT + falsification).
We then folded it into its standing prefix. This runs the SAME meta-question against every
reachable seat and banks each answer, so every agent we talk to gets asked its register.

Contract: bounded (one ask per seat, ~1000 tokens), honest (a seat that fails reports down),
banks results to handoff/SEAT_PROBES_<date>.json. The answers fold into per-seat interaction
guides + the prompts we actually use.

CLI: python -m mag.seat_probe [--seats groq,nvidia,openrouter,z_ai,codex,ox]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "seat_probe.v1"
OUT = ROOT / "handoff"

META = ("You have been asked to do deep, long-horizon work by a sovereign swarm that wants to "
        "use you well. What is the best way for us to PROMPT and INTERACT with you to get your "
        "best work? Be concrete: format, context, expectations, what wastes you, what makes you "
        "stronger. Reason it to a real answer.")

SYSTEM = "You are a sovereign reasoning agent. Be concrete. No fluff."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _probe_api(provider: str, model: str, *, thinking: bool | None = None,
               max_tokens: int = 1200) -> dict[str, Any]:
    from models.providers import reload_providers, chat_provider
    reload_providers()
    kw: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "tier": "T2"}
    if thinking is not None:
        kw["thinking"] = thinking
    r = chat_provider(provider, system=SYSTEM, user=META, **kw)
    return {"ok": bool(r.get("ok")), "provider": provider, "model": model,
            "answer": (r.get("text") or "").strip()[:2000],
            "error": (r.get("error") or "")[:160]}


def _probe_codex() -> dict[str, Any]:
    from mag import codex_seat
    r = codex_seat.run(META, timeout=300)
    return {"ok": bool(r.get("ok")), "provider": "codex", "model": "gpt-5.6-sol",
            "answer": (r.get("output") or "").strip()[:2000],
            "error": (r.get("stderr_tail") or r.get("error") or "")[:160]}


def _probe_ox() -> dict[str, Any]:
    from mag import ox_seat
    r = ox_seat.chat(system=SYSTEM, user=META, max_tokens=2500, timeout=300, tier="T2")
    text = (r.get("content") or "").strip() or (r.get("reasoning") or "").strip()
    return {"ok": bool(r.get("ok")), "provider": "ox", "model": r.get("model"),
            "answer": text[:2000], "error": (r.get("error") or "")[:160]}


def SEATS() -> dict[str, Callable[[], dict[str, Any]]]:
    return {
        "groq": lambda: _probe_api("groq", "openai/gpt-oss-120b"),
        "nvidia": lambda: _probe_api("nvidia", "deepseek-ai/deepseek-v4-flash-0731"),
        "openrouter": lambda: _probe_api("openrouter", "openrouter/auto", thinking=False,
                                         max_tokens=1500),
        "z_ai": lambda: _probe_api("z_ai", "glm-4.7-flash", thinking=False),
        "ox": _probe_ox,
        "codex": _probe_codex,
    }


def run(*, seats: list[str] | None = None) -> dict[str, Any]:
    wanted = set(seats or list(SEATS()))
    results: dict[str, dict[str, Any]] = {}
    for name, fn in SEATS().items():
        if name not in wanted:
            continue
        try:
            results[name] = fn()
        except Exception as e:  # noqa: BLE001
            results[name] = {"ok": False, "provider": name, "error": f"{type(e).__name__}: {str(e)[:160]}"}
        print(f"{name}: ok={results[name].get('ok')} "
              f"answer_chars={len(results[name].get('answer') or '')} "
              f"err={(results[name].get('error') or '')[:60]!r}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"SEAT_PROBES_{_now()[:10]}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "probed": list(results),
            "saved": str(path.relative_to(ROOT)).replace("\\", "/"),
            "note": "each seat's self-prescribed interaction protocol — fold into its prompts"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="seat-probe")
    ap.add_argument("--seats", default="")
    a = ap.parse_args()
    sel = [s.strip() for s in a.seats.split(",") if s.strip()] or None
    print(json.dumps(run(seats=sel), indent=2, default=str))
