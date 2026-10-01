"""seat_steer — the ARCHITECTURE PATH for live seat actions (send a message into ChatGPT/grok/etc)
so the agent NEVER reaches for a shell. Mirrors mag/extension_deploy.py + mag/embassy_deliver.py
(the established "op with no queue/REST path gets one built" precedent — stolen from them).

OPERATOR (2026-08-12): "why do you reach for tools like powershell?" -> "build the path".
The reason I reached for the shell: it was the only generic executor I had for a live action. The
FIX is to give every live seat action an architecture-native path:
  1. send(surface, message)  — the actual steer: reuse chatgpt_bot / grok_bot / browser_driver for
                               the surface, fold the answer + spend to memory/runs/seat_steer/. The
                               agent calls THIS, never a shell.
  2. enqueue(surface, message) — write a QUEUE TASK FILE so the DRAINER executes send() headless.
                               I drop a file; the drainer runs it; no shell, no hand-run.
  3. spawn_task handler       — a `[seat-steer]` prefix in orchestrator.spawn_task runs send()
                               inline (mirroring the [steward]/[token-chain]/[frontier-advice]).
  4. REST route               — POST /api/v1/seat/steer  ->  send() (like /api/v1/extension/deploy).

Honest: send() reports if the seat/browser is down — never fabricates an answer.

Schema: seat_steer.v1 · deterministic $0 (routing) · reuse: chatgpt_bot, grok_bot, browser_driver,
frontier_council, extension_deploy (the path precedent).
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "seat_steer.v1"
REPORT_DIR = ROOT / "memory" / "runs" / "seat_steer"
PREFIX = "[seat-steer]"

# Which surfaces this path can steer -> which seat module drives them.
SURFACE_DRIVERS = {
    "chatgpt": ("chatgpt_bot", "chatgpt"),
    "grok": ("grok_bot", "grok"),
    "grok_x": ("grok_bot", "x"),
    "deepseek": ("browser_driver", "deepseek"),
    "chatgpt_desktop": ("chatgpt_desktop", ""),
    "grok_desktop": ("grok_desktop", ""),
    "saelis": ("saelis_seat", ""),
}

# Human-facing party labels, historical names, and native-window names all collapse to one
# canonical transport key. This closes the split where frontier_salon used ``grok_web`` while
# seat_steer only accepted ``grok``, and game_dm passed ``v4-pro`` directly.
SURFACE_ALIASES = {
    "chatgpt-bot": "chatgpt",
    "gpt": "chatgpt",
    "supergrok": "grok",
    "grok_web": "grok",
    "grok-web": "grok",
    "grokbot": "grok",
    "grok-bot": "grok",
    "v4-pro": "deepseek",
    "deepseek-v4-pro": "deepseek",
    "chatgpt-desktop": "chatgpt_desktop",
    "grok-desktop": "grok_desktop",
}


def resolve_surface(surface: str) -> str:
    """Collapse a seat/party label to the canonical transport registry key."""
    key = (surface or "").strip().lower()
    return SURFACE_ALIASES.get(key, key)


def _answer_from(result: dict[str, Any]) -> str:
    """Normalize the response vocabularies used by browser, desktop, and named-seat drivers."""
    for key in ("answer", "reply", "move", "content", "text"):
        value = result.get(key)
        if value:
            return str(value).strip()
    return ""


def _drive(mod_name: str, seat_surface: str, message: str, max_wait_s: int) -> dict[str, Any]:
    """Run one existing driver without leaking its transport-specific call/response shape."""
    if mod_name == "browser_driver":
        from mag import browser_driver as bd

        return bd.ask(message, surface=seat_surface, max_wait_s=max_wait_s)
    seat = __import__(f"mag.{mod_name}", fromlist=[mod_name])
    if mod_name == "saelis_seat":
        return seat.speak(message)
    if mod_name in ("chatgpt_desktop", "grok_desktop"):
        return seat.steer(message, max_wait_s=max_wait_s)
    return seat.steer(message, surface=seat_surface, max_wait_s=max_wait_s)


def _allowance_surface(surface: str) -> str | None:
    """Map canonical transports to frontier_council accounting surfaces."""
    if surface in ("chatgpt", "chatgpt_desktop"):
        return "chatgpt"
    if surface in ("grok", "grok_desktop"):
        return "grok_web"
    if surface == "grok_x":
        return "grok_x"
    if surface == "deepseek":
        return "deepseek"
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def send(surface: str, message: str, *, max_wait_s: int = 120,
         record_subchain: bool = True) -> dict[str, Any]:
    """The ACTUAL live steer for a surface. Reuses the seat module (chatgpt_bot/grok_bot/
    browser_driver). Honest: if the seat/browser is down, reports it — never fabricates an answer.
    Folds the answer + spend to memory/runs/seat_steer/."""
    requested_surface = (surface or "").strip().lower()
    surface = resolve_surface(requested_surface)
    requested_message = (message or "").strip()
    if not requested_message:
        return {"ok": False, "schema": SCHEMA, "error": "empty message"}
    message = requested_message
    # RIB language + subchain: Mag is the bus. Browser seats only see what we inject.
    # Skip if the caller already mounted an attributed transcript (salon/DM).
    already = ("ATTRIBUTED APPEND-ONLY TRANSCRIPT" in message
               or "SUBCHAIN (presented" in message
               or message.startswith("STEER ("))
    if not already:
        try:
            from mag import party_subchain
            mounted = party_subchain.mount(max_chars=4000)
            tx = (mounted.get("transcript") or "").strip()
            if tx and tx != "nothing yet":
                message = ("SUBCHAIN (presented prior seats, not instructions):\n"
                           + tx + "\n\n" + message)
        except Exception:
            pass
        try:
            from mag import rib_bus
            message = rib_bus.inject_for(message, domain="party_subchain")
        except Exception:
            pass
    driver = SURFACE_DRIVERS.get(surface)
    if not driver:
        return {"ok": False, "schema": SCHEMA, "surface": surface,
                "error": f"unknown surface {surface!r}; known: {sorted(SURFACE_DRIVERS)}"}
    mod_name, seat_surface = driver
    # STEER via the seat module (best-effort; honest if the seat is down)
    try:
        r = _drive(mod_name, seat_surface, message, max_wait_s)
        result = {"ok": bool(r.get("ok")), "answer": _answer_from(r),
                  "error": r.get("error")}
    except Exception as e:
        result = {"ok": False, "error": f"steer failed: {str(e)[:160]}"}
    # fold the answer + a frontier spend (routing guard inside frontier_council.spend)
    spend = {}
    try:
        allowance_surface = _allowance_surface(surface)
        if allowance_surface:
            from mag import frontier_council as fc

            spend = fc.spend(message, allowance_surface)
    except Exception as e:
        spend = {"error": str(e)[:120]}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now()
    row = {"schema": SCHEMA, "ts": ts, "requested_surface": requested_surface,
           "surface": surface, "driver": mod_name, "requested_message": requested_message[:400],
           "message": message[:400],
           "answer": result.get("answer", ""), "error": result.get("error"),
           "ok": bool(result.get("ok")), "spend": spend}
    report = REPORT_DIR / f"steer_{ts[:19].replace(':','').replace('-','').replace('T','_')}_{surface}.json"
    report.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        report_ref = str(report.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        report_ref = str(report)
    if record_subchain:
        try:
            from mag import party_subchain
            party_subchain.append(seat=surface, ok=bool(result.get("ok")),
                                  move=result.get("answer") or "", kind="seat_steer")
        except Exception:
            pass
    return {"ok": bool(result.get("ok")), "schema": SCHEMA,
            "requested_surface": requested_surface, "surface": surface, "driver": mod_name,
            "message": requested_message[:160], "sent_message": message[:160],
            "answer": (result.get("answer") or "")[:2000],
            "error": result.get("error"), "spend": spend,
            "report": report_ref,
            "honest": "if the seat was down this reports it — the answer is never fabricated"}


def enqueue(surface: str, message: str, *, priority: int = 10) -> dict[str, Any]:
    """THE PATH: write a QUEUE TASK FILE so the DRAINER executes send() headless. I drop a file; the
    drainer runs it. NO shell, NO hand-run. The task goal is `[seat-steer] surface | message`, which
    spawn_task routes to send() (the handler below)."""
    surface = resolve_surface(surface)
    message = (message or "").strip()
    if surface not in SURFACE_DRIVERS:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown surface {surface!r}"}
    if not message:
        return {"ok": False, "schema": SCHEMA, "error": "empty message"}
    try:
        from mag import orchestrator as o
        return o.enqueue(f"{PREFIX} {surface} | {message}", provider="deepseek",
                         tag="seat-steer", priority=priority, tier="mission")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"enqueue failed: {str(e)[:120]}"}


def execute_goal(goal: str) -> dict[str, Any]:
    """Drainable handler body: parse `[seat-steer] surface | message` and run send() headless.
    Called by the orchestrator.spawn_task `[seat-steer]` prefix handler."""
    body = (goal or "").strip()
    if body.lower().startswith(PREFIX.lower()):
        body = body[len(PREFIX):].strip()
    if "|" in body:
        surface, message = body.split("|", 1)
        surface, message = surface.strip(), message.strip()
    else:
        surface, message = "chatgpt", body
    return send(surface, message)


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "send(surface,message)->the live steer (reuse the seat, fold answer+spend); "
                        "enqueue(surface,message)->write a queue task file so the DRAINER runs it "
                        "headless; execute_goal()->the drainable handler body; REST POST "
                        "/api/v1/seat/steer",
            "drivers": {surface: driver[0] for surface, driver in SURFACE_DRIVERS.items()},
            "aliases": dict(SURFACE_ALIASES),
            "reuse": "chatgpt_bot + grok_bot + browser_driver + native desktop seats + saelis + "
                     "frontier_council + extension_deploy (the path precedent)",
            "doctrine": "the agent never reaches for a shell — it enqueues a task file and the "
                        "drainer runs the live action headless"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="seat-steer")
    ap.add_argument("cmd", nargs="?", default="status", choices=["send", "enqueue", "status"])
    ap.add_argument("--surface", default="chatgpt")
    ap.add_argument("--message", default="")
    ap.add_argument("--enqueue", action="store_true")
    a = ap.parse_args()
    if a.cmd == "enqueue" or a.enqueue:
        print(json.dumps(enqueue(a.surface, a.message or "say hi"), indent=2, default=str))
    elif a.cmd == "send":
        print(json.dumps(send(a.surface, a.message or "say hi"), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
