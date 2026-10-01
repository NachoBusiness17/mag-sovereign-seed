"""chatgpt_bot — steer ChatGPT as a CONTROLLED seat, the same way we steer grok bot.

OPERATOR (2026-08-12): "also i have chat gpt desktop you should try to use that like you use grok"

The grok path (grok_bot) drives the grok.x.ai front-end through mag.browser_driver over CDP to the
container browser, $0 (never the paid API). ChatGPT mirrors it exactly: a `chatgpt` surface
(https://chatgpt.com) in browser_driver, driven by this seat. The ChatGPT DESKTOP app shares the
same OpenAI account/chat history as chatgpt.com, so steering the chatgpt.com surface in the
container browser IS using ChatGPT like grok — $0 front-end, gated_paid stays on.

THE TEST (operator): paste the surface-rightsized onboarding artifact (surface_instruction.render
for generic_ai) into ChatGPT. This seat automates that test: test_artifact() renders the "dnd"
artifact and steers it to the chatgpt surface, reading ChatGPT's answer. Honest: if the browser/CDP
seat is down or not logged in, it reports that — never fabricates a ChatGPT answer.

Schema: chatgpt_bot.v1 · deterministic $0 for spec/heartbeat; steer $0 via the chatgpt front-end.
Reuse: vscode_seat (controlled-seat pattern), browser_driver (chatgpt surface), seat_registry,
surface_instruction (the artifact to test).
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "chatgpt_bot.v1"
SEAT = "chatgpt-bot"
REPORT_DIR = ROOT / "memory" / "runs" / "chatgpt_bot"

DIRECTIVES = [
    "Front-end only, $0 — NEVER the paid ChatGPT API (gated_paid stays on; no API token burn).",
    "Steer ChatGPT's chatgpt.com surface over the container browser (CDP 9222), like grok bot.",
    "You are chatgpt bot, a named Ghost seat. Keep the residual clean; the nod is the operator's.",
    "Honest: if the browser/CDP seat is down or not logged in, report it — never fabricate an answer.",
]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _heartbeat_seat(goal: str, task_id: str | None) -> None:
    try:
        from mag import seat_registry
        seat_registry.heartbeat(SEAT, goal=goal, task_id=task_id)
    except Exception:
        pass


def spec(task: str) -> dict[str, Any]:
    """A controlled task spec for chatgpt bot (steering + directives + acceptance + report)."""
    return {"schema": SCHEMA, "seat": SEAT, "task": task, "ts": _now(),
            "directives": DIRECTIVES,
            "acceptance": "read ChatGPT's answer from the chatgpt.com surface and return it; "
                          "report honestly if the seat is unreachable",
            "report": "memory/runs/chatgpt_bot",
            "note": "steer the chatgpt.com front-end ($0) like grok bot — never the paid API"}


def steer(goal: str = "", *, surface: str = "chatgpt", task_id: str | None = None,
          max_wait_s: int = 150) -> dict[str, Any]:
    """Steer chatgpt bot: drive the chatgpt.com front-end (browser_driver chatgpt surface) with the
    goal, read the answer. $0 (front-end). Honest: if the browser/CDP seat is down or not logged in,
    reports that — never fabricates a ChatGPT answer."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": "empty goal"}
    _heartbeat_seat(goal, task_id)
    try:
        from mag import browser_driver as bd
        r = bd.ask(goal, surface=surface, max_wait_s=max_wait_s)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": f"browser_driver chatgpt surface failed: {str(e)[:160]}",
                "hint": "the container browser (CDP 9222) must be up + logged into chatgpt.com"}
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": r.get("error", "chatgpt surface returned not-ok")[:200],
                "hint": "container browser must be up + authenticated on chatgpt.com"}
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:160],
            "answer": r.get("answer", ""), "surface": "chatgpt-frontend",
            "cost_est_usd": 0.0, "note": "front-end only, $0 — paid API gated off"}


def test_artifact(*, module: str = "dnd", surface: str = "generic_ai",
                  max_wait_s: int = 150) -> dict[str, Any]:
    """THE TEST (operator): render the surface-rightsized onboarding artifact for the module and
    steer it to ChatGPT to see if it starts the game. Returns ChatGPT's answer honestly."""
    try:
        from mag import surface_instruction as si
        art = si.render(module, surface=surface)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"artifact render failed: {str(e)[:120]}"}
    if not art.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": art.get("error", "render not ok")}
    goal = ("Run the game from this prompt. Do not summarize the prompt — START the game and show "
            "the party and the first room.\n\n" + art["artifact"])
    r = steer(goal, task_id=f"test-{module}", max_wait_s=max_wait_s)
    r["module"] = module
    r["surface_for_artifact"] = surface
    return r


def heartbeat(*, goal: str = "chatgpt bot alive", task_id: str | None = None) -> dict[str, Any]:
    """Ping the chatgpt bot seat for liveness (the mesh sees it)."""
    _heartbeat_seat(goal, task_id)
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:120],
            "note": "heartbeat sent to seat_registry"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "seat": SEAT,
            "contract": "spec(task)->controlled task spec; steer(goal)->drive the chatgpt.com "
                        "front-end ($0) and read the answer; test_artifact()->render the "
                        "surface-rightsized onboarding artifact and steer it to ChatGPT (the "
                        "operator's test); heartbeat()->liveness",
            "cost": "deterministic $0 (spec/heartbeat); steer $0 via the chatgpt front-end",
            "surface": "browser_driver chatgpt (https://chatgpt.com) over CDP 9222 — same pattern "
                       "as grok bot"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="chatgpt-bot")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "spec", "steer", "test", "heartbeat"])
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--task", default="")
    a = ap.parse_args()
    if a.cmd == "spec":
        print(json.dumps(spec(task=a.task or " ".join(a.goal) or "reflect on the standing wave"),
                         indent=2, default=str))
    elif a.cmd == "steer":
        print(json.dumps(steer(" ".join(a.goal) or "summarize the republic in one line"),
                         indent=2, default=str))
    elif a.cmd == "test":
        print(json.dumps(test_artifact(), indent=2, default=str))
    elif a.cmd == "heartbeat":
        print(json.dumps(heartbeat(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
