"""chatgpt_desktop — steer the ChatGPT DESKTOP APP natively (operator 2026-08-13: "you have chat
gpt you have that desktop app too"). Self-stolen from chatgpt_bot (the controlled-seat pattern:
spec/steer/heartbeat/status + honest ok flags) + vscode_seat. The desktop app is a REAL native
window on this PC (Electron, class Chrome_WidgetWin_1) — drivable by keystrokes WITHOUT the CDP
browser / firewall that blocks 9222.

THE MECHANISM (external steal — driving an Electron chat app):
  connect()  -> attach to the running ChatGPT desktop app window(s) via pywinauto (win32 backend).
  _focus()   -> bring the window to the foreground so the injection lands in the chat input.
  steer(goal)-> CLIPBOARD-PASTE the goal into the chat (pyperclip + ^v, one shot — NOT typing),
                send Enter, wait, then read the answer back via screenshot + Windows OCR. Honest
                ok — if the window can't be driven or the answer can't be read, report it, never
                fabricate.

THE LAW (honest, sw55): the desktop app is the surface; if it isn't focused/drivable or the answer
can't be read back, we report that plainly — never a made-up ChatGPT answer.

Schema: chatgpt_desktop.v1 · deterministic $0 · reuse: chatgpt_bot (seat pattern), pywinauto
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

SCHEMA = "chatgpt_desktop.v1"
SEAT = "chatgpt-desktop"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _heartbeat(goal: str) -> None:
    try:
        from mag import seat_registry
        seat_registry.heartbeat(SEAT, goal=goal, task_id=None)
    except Exception:
        pass


def connect() -> dict[str, Any]:
    """Attach to the running ChatGPT desktop app window(s). Returns the list of matching top-level
    windows (Electron, class Chrome_WidgetWin_1). Honest if none are found."""
    try:
        from pywinauto import Desktop
        desk = Desktop(backend="uia")
        wins = [w for w in desk.windows()
                if (w.window_text() or "").strip().lower() == "chatgpt"]
        return {"ok": bool(wins), "schema": SCHEMA, "n_windows": len(wins),
                "windows": [w.window_text() for w in wins[:5]],
                "note": "attached to the ChatGPT desktop app window(s) — the native surface, no CDP"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160]}


def _focus() -> dict[str, Any]:
    """Bring the ChatGPT window to the foreground so keystrokes land in the chat input."""
    c = connect()
    if not c.get("ok"):
        return {"ok": False, "error": "no chatgpt window to focus"}
    try:
        # use win32 backend for reliable window-level focus/keystrokes on Electron
        from pywinauto import Desktop
        desk = Desktop(backend="win32")
        for w in desk.windows():
            if (w.window_text() or "").strip().lower() == "chatgpt":
                try:
                    w.set_focus()
                    return {"ok": True, "focused": w.window_text()}
                except Exception:
                    continue
        return {"ok": False, "error": "could not focus the chatgpt window"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _read_clipboard() -> str:
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        try:
            return (root.clipboard_get() or "").strip()
        finally:
            root.destroy()
    except Exception:
        return ""


def _copy_all() -> None:
    """Select-all + copy from the focused window (the message area) to the clipboard."""
    try:
        from pywinauto.keyboard import send_keys
        send_keys("^a", pause=0.2)
        send_keys("^c", pause=0.3)
    except Exception:
        pass


def steer(goal: str = "", *, max_wait_s: int = 45, read_back: bool = True) -> dict[str, Any]:
    """STEER the ChatGPT desktop app: type the goal into the chat, send Enter, wait for the answer,
    then read it back via the clipboard. HONEST — if the window can't be driven or the answer can't
    be read, report it, never fabricate."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": "empty goal"}
    _heartbeat(goal)
    f = _focus()
    if not f.get("ok"):
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": f.get("error", "cannot focus the chatgpt desktop app"),
                "hint": "the ChatGPT desktop app must be running + its window focusable"}
    try:
        # CLIPBOARD-PASTE injection (operator 2026-08-13: "use copy paste ... it takes time"):
        # put the whole prompt on the clipboard, then paste once (^v) + Enter — NOT keystroke
        # typing. One shot, fast, no per-character drift. Mirrors the verified grok_desktop._paste.
        import pyperclip  # type: ignore
        pyperclip.copy(goal)
        from pywinauto.keyboard import send_keys
        send_keys("^v", pause=0.3)          # paste the prompt in one shot
        send_keys("{ENTER}", pause=0.3)     # submit
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": f"clipboard-paste drive failed: {str(e)[:160]}"}
    time.sleep(min(max_wait_s, 20))  # bounded wait for the model to answer
    answer = ""
    if read_back:
        # RELIABLE read-back: screenshot the window + Windows OCR (the clipboard copy returned
        # empty because Electron accessibility is OFF -> UIA tree empty). Verified working.
        try:
            from mag import win_ocr
            from pywinauto import Desktop as _Desk
            for _w in _Desk(backend="win32").windows():
                if (_w.window_text() or "").strip().lower() == "chatgpt":
                    answer = win_ocr.window_text(_w, focus=True)
                    break
        except Exception:
            answer = ""
    if not answer:
        return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:160],
                "sent": True, "read_back": False, "answer": "",
                "note": "sent to the ChatGPT desktop app; could not read the answer back via OCR "
                        "(honest — the window may not be visible/focused)"}
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:160],
            "sent": True, "read_back": True, "answer": answer[-4000:],
            "surface": "chatgpt-desktop-app", "cost_est_usd": 0.0,
            "note": "steered the ChatGPT desktop app natively + read the answer back via screenshot "
                    "+ Windows OCR, $0 — no CDP, no paid API"}


def heartbeat(*, goal: str = "chatgpt desktop alive") -> dict[str, Any]:
    _heartbeat(goal)
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:120],
            "note": "heartbeat sent to seat_registry"}


def status() -> dict[str, Any]:
    c = connect()
    return {"ok": True, "schema": SCHEMA, "seat": SEAT,
            "contract": "connect()->attach to the ChatGPT desktop app window; steer(goal)->"
                        "clipboard-paste (^v) + Enter + read back via OCR (honest); "
                        "heartbeat()->liveness",
            "cost": "deterministic $0 (the desktop app, front-end only, no paid API)",
            "surface": "the ChatGPT DESKTOP app (Electron window) — native, no CDP 9222",
            "connected_windows": c.get("n_windows", 0)}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(prog="chatgpt-desktop")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "steer", "connect", "heartbeat"])
    ap.add_argument("goal", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "steer":
        print(json.dumps(steer(" ".join(a.goal) or "hello — test the desktop surface"),
                         indent=2, default=str))
    elif a.cmd == "connect":
        print(json.dumps(connect(), indent=2, default=str))
    elif a.cmd == "heartbeat":
        print(json.dumps(heartbeat(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
