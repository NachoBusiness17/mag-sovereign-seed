"""electron_seat — DRIVE THE DESKTOP ELECTRON APPS OVER CDP, not keystrokes/paste/OCR.

STOLEN (2026-08-13, operator: "use copy paste ... or inject with memory directly ... they need
to reply and it takes time" then "wrong tool" — the external fetch was the wrong tool; the win
is already OURS). Self-steal from `browser_driver` (Playwright-over-CDP: connect_over_cdp +
per-surface DOM selectors) + `chatgpt_desktop`/`grok_desktop` (the native desktop surfaces).

THE STEAL: the ChatGPT / Grok DESKTOP apps are Electron = Chromium. If launched with
`--remote-debugging-port=<port>`, they expose a CDP endpoint like the container browser. So we
point the SAME connect_over_cdp machinery at the app itself and drive its real DOM:

  INJECT  -> page.evaluate: set the input's value DIRECTLY (textarea) or the contenteditable's
             text (ProseMirror) + dispatch input events. NO typing, NO clipboard paste, NO OCR.
  SUBMIT  -> Enter (or click the send button).
  READ    -> poll the answer node's inner_text until it settles/grows — REAL-TIME, not a fixed
             sleep, because "they need to reply and it takes time."

This is the closest accessible thing to "inject directly into memory" for a closed Electron app:
we write straight into the renderer's input DOM over the app's own debugging protocol.

HONEST GATE (sw55): the app must be RUNNING with a remote-debugging port open, else steer()
reports down — never fabricate. Selectors are a starting point, not gospel (DOMs change).

Schema: electron_seat.v1 · deterministic $0 (front-end only) · reuse: browser_driver (connect_over_cdp),
chatgpt_desktop/grok_desktop (the desktop surfaces), seat_registry
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

SCHEMA = "electron_seat.v1"

# Per-surface: the desktop app's CDP port + DOM selectors (starting point, not gospel).
# chatgpt-desktop mirrors the web ChatGPT DOM; grok-desktop the Grok DOM.
ELECTRON_SURFACES: dict[str, dict[str, Any]] = {
    "chatgpt-desktop": {
        "port": 9333,
        "input": "#prompt-textarea",
        "input_mode": "contenteditable",   # ProseMirror div
        "submit": "Enter",
        "answer": "[data-message-author-role='assistant']",
    },
    "grok-desktop": {
        "port": 9334,
        "input": "textarea, [contenteditable='true']",
        "input_mode": "auto",              # try fill, fall back to contenteditable
        "submit": "Enter",
        "answer": ".message, [data-message-author-role='assistant'], article",
    },
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _heartbeat(surface: str, goal: str) -> None:
    try:
        from mag import seat_registry
        seat_registry.heartbeat(surface, goal=goal[:120], task_id=None)
    except Exception:
        pass


def _connect(port: int) -> dict[str, Any]:
    """Connect Playwright over CDP to the Electron app's remote-debugging port and grab its
    EXISTING page (the app's main window) — not a new tab. Reuses browser_driver.connect()."""
    ep = f"http://127.0.0.1:{port}"
    try:
        from mag import browser_driver
        c = browser_driver.connect(endpoint=ep)
        if not c.get("ok"):
            return {"ok": False, "error": c.get("error", "cannot connect")}
        page = c["page"]
        return {"ok": True, "page": page}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"cannot connect to electron CDP on :{port}: {e}",
                "hint": f"relaunch the app with --remote-debugging-port={port} so CDP is exposed"}


def _inject(page: Any, text: str, mode: str) -> None:
    """Inject the prompt DIRECTLY into the app's input DOM via JS. textarea -> set value + input
    event; contenteditable (ProseMirror) -> set innerHTML/text + input event. No typing, no paste."""
    if mode == "contenteditable":
        page.evaluate("""(text) => {
            const el = document.querySelector('[contenteditable="true"]');
            if (!el) return false;
            el.focus();
            el.textContent = text;
            el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
            return true;
        }""", text)
    else:
        page.evaluate("""(text) => {
            const el = document.querySelector('textarea');
            if (!el) return false;
            el.focus();
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(el, text);
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }""", text)


def _read_answer(page: Any, sel: str, wait_s: float = 30.0) -> str:
    """Poll the answer node in real time until it settles/grows — the model needs time to reply."""
    last, stable = "", 0
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            txt = (page.locator(sel).last.inner_text() or "").strip()
        except Exception:
            txt = ""
        if txt and txt == last:
            stable += 1
            if stable >= 3:
                return txt
        elif txt:
            last, stable = txt, 0
        time.sleep(1.0)
    return last


def steer(surface: str = "chatgpt-desktop", goal: str = "", *, max_wait_s: int = 40) -> dict[str, Any]:
    """STEER a desktop Electron app over CDP: inject the prompt DIRECTLY into the input DOM, submit,
    poll the answer in real time. Honest — if the app isn't running with a debug port, report down."""
    cfg = ELECTRON_SURFACES.get(surface)
    if not cfg:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown surface {surface!r}; "
                f"known: {sorted(ELECTRON_SURFACES)}"}
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "surface": surface, "error": "empty goal"}
    _heartbeat(surface, goal)
    c = _connect(cfg["port"])
    if not c.get("ok"):
        return {"ok": False, "schema": SCHEMA, "surface": surface, "error": c.get("error"),
                "hint": c.get("hint")}
    page = c["page"]
    try:
        _inject(page, goal, cfg["input_mode"])
        if cfg["submit"] == "Enter":
            page.keyboard.press("Enter")
        answer = _read_answer(page, cfg["answer"], wait_s=min(max_wait_s, 40.0))
        ok = bool(answer.strip())
        return {"ok": ok, "schema": SCHEMA, "surface": surface, "goal": goal[:160],
                "reply": answer[:4000] if ok else "",
                "note": ("read the app's answer over CDP (direct DOM, no typing/paste/OCR)" if ok
                         else "sent over CDP but no answer settled yet (honest)")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "surface": surface, "goal": goal[:160],
                "error": str(e)[:200]}
    finally:
        try:
            page.close()
            c["page"]._mag_pw.stop()
        except Exception:
            pass


def status() -> dict[str, Any]:
    probes = {}
    for surface, cfg in ELECTRON_SURFACES.items():
        c = _connect(cfg["port"])
        probes[surface] = {"port": cfg["port"], "cdp_ok": bool(c.get("ok"))}
        if c.get("ok"):
            try:
                c["page"].close()
                c["page"]._mag_pw.stop()
            except Exception:
                pass
    return {"ok": True, "schema": SCHEMA,
            "contract": "steer(surface,goal)->connect to the desktop Electron app over its CDP port, "
                        "inject the prompt DIRECTLY into the input DOM (no typing/paste/OCR), submit, "
                        "poll the answer in real time; status()->which desktop apps expose a debug port",
            "cost": "deterministic $0 (front-end only)",
            "surface": "the desktop Electron apps (ChatGPT/Grok) over their remote-debugging CDP port",
            "honest_gate": "the app must be RUNNING with --remote-debugging-port open; else down",
            "probes": probes}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(prog="electron-seat")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "steer"])
    ap.add_argument("--surface", default="chatgpt-desktop")
    ap.add_argument("goal", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "steer":
        print(json.dumps(steer(a.surface, " ".join(a.goal) or "you are an adventurer; what do you do?"),
                         indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
