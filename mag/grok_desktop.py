"""grok_desktop — drive the GROK DESKTOP APP as a native frontier seat, mirror of the VERIFIED
chatgpt_desktop pattern (operator, 2026-08-13: "do the same with grok bot"). The Grok desktop app
(window "Grok Bot", Electron class Chrome_WidgetWin_1) is a native surface on this PC — so it does
NOT depend on CDP 9222 or the host firewall that blocks the container browser.

SELF-STEAL: the exact working mechanism from chatgpt_desktop (verified 2026-08-13): Electron app
(UIA tree empty) -> drive by KEYSTROKES: focus -> clipboard-paste the prompt -> Enter -> wait ->
read the answer back via clipboard. Adapt the app target to Grok. Same seat pattern (heartbeat/spec/
steer, $0 front-end, honest ok flags) from chatgpt_bot/grok_bot.

Schema: grok_desktop.v1 · deterministic $0 (front-end only) · reuse: chatgpt_desktop (the verified
pattern), grok_bot (the seat), seat_registry, game_dm (the DM table can seat Grok natively)
"""
from __future__ import annotations

import sys
import time
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "grok_desktop.v1"
SEAT = "grok-desktop"

# Window names the Grok desktop app may present as (probe found "Grok Bot").
WINDOW_NAMES = ("grok", "grok bot")

DIRECTIVES = [
    "Front-end only, $0 — never burn an API key.",
    "Drive the GROK DESKTOP app natively (Electron window), NOT the container browser.",
    "You are grok-desktop, a named Ghost seat. Keep the residual clean; the nod is the operator's.",
    "Honest: if the app isn't running or the window can't be driven, report it — never fabricate.",
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


def _connect(max_tries: int = 3) -> Any:
    """Attach to the running Grok desktop app window (Electron). Mirrors chatgpt_desktop's verified
    connect. Matches by window title containing 'grok'."""
    from pywinauto import Application
    for _ in range(max_tries):
        try:
            app = Application(backend="uia").connect(title_re=".*[Gg]rok.*", timeout=10)
            wins = app.windows()
            if not wins:
                raise RuntimeError("no Grok windows")
            win = max(wins, key=lambda w: (w.element_info.rectangle.width() * w.element_info.rectangle.height())
                      if w.element_info.rectangle else 0)
            win.set_focus()
            return win
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0)
    raise RuntimeError(f"cannot attach to Grok desktop: {last}")


def _paste(win: Any, text: str) -> None:
    import pyperclip  # type: ignore
    pyperclip.copy(text)
    win.type_keys("^v")


def _submit(win: Any) -> None:
    win.type_keys("{ENTER}", pause=0.3)


def _read_response(win: Any, wait_s: float = 12.0) -> str:
    time.sleep(wait_s)
    try:
        win.type_keys("^a", pause=0.2)
        win.type_keys("^c", pause=0.3)
        import pyperclip  # type: ignore
        return (pyperclip.paste() or "").strip()
    except Exception:
        return ""


def steer(goal: str = "", *, max_wait_s: int = 30, task_id: str | None = None) -> dict[str, Any]:
    """Steer the Grok desktop app: focus -> paste the prompt -> submit -> read the answer back.
    Honest ok flag — never fabricate a Grok answer."""
    _heartbeat_seat(goal, task_id)
    prompt = (goal or "").strip() or "reflecting on the standing wave"
    try:
        win = _connect()
        _paste(win, prompt)
        time.sleep(0.5)
        _submit(win)
        reply = _read_response(win, wait_s=min(max_wait_s, 20.0))
        return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": prompt,
                "reply": reply[:2000] if reply else "",
                "note": "steered the Grok desktop app natively ($0); read the answer back"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "seat": SEAT, "goal": prompt,
                "error": str(e)[:160],
                "note": "Grok desktop unreachable/drive failed — reported honestly, not fabricated"}


def heartbeat(goal: str = "grok desktop alive") -> dict[str, Any]:
    _heartbeat_seat(goal, None)
    try:
        _connect()
        return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal,
                "note": "Grok desktop reachable (window attached)"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "seat": SEAT, "goal": goal,
                "error": str(e)[:160], "note": "Grok desktop not reachable"}


def spec(task: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "seat": SEAT, "task": task, "ts": _now(),
            "directives": DIRECTIVES,
            "acceptance": "read Grok's answer from the DESKTOP app and return it; report honestly if "
                          "the app is unreachable",
            "report": "memory/runs/grok_desktop",
            "note": "steer the Grok desktop app natively ($0) — no CDP, no browser, no API burn"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "seat": SEAT,
            "contract": "connect()->attach the running Grok desktop window (Electron, mirrors the "
                        "verified chatgpt_desktop); steer(goal)->focus+paste+submit+read back "
                        "(honest ok); heartbeat()->liveness; spec(task)->controlled seat spec.",
            "cost": "deterministic $0 (front-end only)",
            "surface": "the GROK DESKTOP app — a NATIVE frontier seat, no CDP 9222 dependency",
            "reuse": "chatgpt_desktop (verified pattern), grok_bot (the seat), seat_registry, game_dm"}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(prog="grok-desktop")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "steer", "heartbeat", "spec"])
    ap.add_argument("goal", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "steer":
        print(json.dumps(steer(" ".join(a.goal) or "you are an adventurer; what do you do?"),
                         indent=2, default=str))
    elif a.cmd == "heartbeat":
        print(json.dumps(heartbeat(), indent=2, default=str))
    elif a.cmd == "spec":
        print(json.dumps(spec(" ".join(a.goal) or "reflect on the game"), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
