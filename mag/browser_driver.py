"""browser_driver — Playwright-over-CDP driver for the CONTAINER browser seat.

Ghost connects over CDP (ws://127.0.0.1:9222) to the headless Chromium running in the
`browser` docker service — NOT the desktop. Drives allowlisted FREE web frontends
(DeepSeek chat, Perplexity deep research, Grok, ChatGPT, Claude) instead of paying
their APIs. The host only needs the `playwright` pip package (no browser download;
the container owns the browser). host_allowlist is enforced via browser_env.

Schema: browser_driver.v1
CLI: python -m mag.browser_driver open <url> | ask "<goal>" [--surface deepseek|perplexity] | status
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "browser_driver.v1"
CDP_CONNECT_TIMEOUT_MS = max(
    250, int(float(os.environ.get("MAG_CDP_CONNECT_TIMEOUT_SECONDS", "2")) * 1000)
)


def _cdp_endpoint() -> str:
    try:
        from mag import browser_env as be
        return str(be.load_config().get("cdp") or "ws://127.0.0.1:9222")
    except Exception:
        return "ws://127.0.0.1:9222"


def _host_allowed(url: str) -> bool:
    try:
        from mag import browser_env as be
        return bool(be.is_host_allowed(url))
    except Exception:
        return False


# Per-surface: URL + how to type a query + how to read the last answer (best-effort;
# DOMs change — selectors are a starting point, not gospel).
SURFACES: dict[str, dict[str, Any]] = {
    "deepseek": {
        "url": "https://chat.deepseek.com",
        "query_placeholder": "textarea",
        "submit": "Press Enter",
        "answer": ".ds-markdown",
    },
    "perplexity": {
        "url": "https://www.perplexity.ai",
        "query_placeholder": "textarea",
        "submit": "Press Enter",
        "answer": ".prose",
    },
    "grok": {
        "url": "https://grok.x.ai",
        "query_placeholder": "textarea",
        "submit": "Press Enter",
        "answer": ".message",
    },
    "chatgpt": {
        "url": "https://chatgpt.com",
        "query_placeholder": "#prompt-textarea",
        "mode": "contenteditable",  # ProseMirror div, not a textarea — type via keyboard, not fill
        "submit": "Press Enter",
        "answer": "[data-message-author-role='assistant']",
    },
    "x": {
        "url": "https://x.com/home",
        "query_placeholder": "input[data-testid='searchBox_input']",
        "submit": "Press Enter",
        "answer": "article",
    },
}


def _normalize_cdp(ep: str) -> str:
    """connect_over_cdp needs the http endpoint so it can resolve the real browser WS from
    /json/version; a bare ws:// hits the root path and 404s (host-loopback seat, 2026-08-14)."""
    if ep.startswith("ws://"):
        ep = "http://" + ep[len("ws://"):]
    return ep


def connect(*, endpoint: str | None = None) -> Any:
    """Connect to the containerized browser over CDP. Returns a Playwright browser context
    handle (or a dict with error). Requires the `playwright` pip package on the host."""
    # browser-gate (2026-09-22): the browser container was retired with the docker
    # world. A seat that reaches for the dead CDP socket dies with an uncaught
    # EPIPE in the playwright node driver — the whole agent, not just the web
    # tools. Default OFF; MAG_BROWSER_CDP=1 re-enables when a browser exists.
    import os as _os
    if _os.environ.get("MAG_BROWSER_CDP", "").strip().lower() not in ("1", "true", "yes"):
        return {"ok": False,
                "error": "browser CDP disabled — browser container retired 2026-09-22; "
                         "seats run browserless (web tools degrade to fetch-only). "
                         "Set MAG_BROWSER_CDP=1 when a browser container returns.",
                "browserless": True}
    ep = _normalize_cdp(endpoint or _cdp_endpoint())
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"ok": False, "error": "playwright not installed on host — pip install playwright "
                                      "(the container owns the browser; host only needs the client)",
                "detail": str(e)[:160]}
    # Probe the HTTP side of CDP before starting Playwright.  A stale forwarded
    # port can accept TCP while never completing the websocket handshake; that
    # used to make every observer (ghost sense, frontier seat status, preflight)
    # inherit an unbounded browser wait.
    try:
        urllib.request.urlopen(
            ep.rstrip("/") + "/json/version", timeout=CDP_CONNECT_TIMEOUT_MS / 1000
        ).close()
    except Exception as e:
        return {"ok": False, "error": f"cannot reach container CDP at {ep}: {e}",
                "hint": "start the browser container: docker compose --profile browser up -d"}
    try:
        pw = None
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(ep, timeout=CDP_CONNECT_TIMEOUT_MS)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page._mag_pw = pw  # keep playwright alive
        return {"ok": True, "endpoint": ep, "page": page}
    except Exception as e:
        try:
            pw.stop()
        except Exception:
            pass
        return {"ok": False, "error": f"cannot connect to container CDP at {ep}: {e}",
                "hint": "start the browser container: docker compose --profile browser up -d"}


def open_url(url: str) -> dict[str, Any]:
    """Navigate the container browser to an ALLOWLISTED url. Refuses non-allowlisted hosts."""
    if not _host_allowed(url):
        return {"ok": False, "error": f"{url} not on the browser allowlist",
                "note": "add the host to configs/browser_env.yaml hosts if you want it"}
    c = connect()
    if not c.get("ok"):
        return c
    page = c["page"]
    try:
        page.goto(url, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        return {"ok": True, "url": page.url, "title": page.title()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    finally:
        try:
            page.close()
            c["page"]._mag_pw.stop()
        except Exception:
            pass


def ask(goal: str, *, surface: str = "deepseek", max_wait_s: int = 120) -> dict[str, Any]:
    """Open a free-frontend surface, type the goal, submit, read the last answer. Best-effort."""
    cfg = SURFACES.get(surface)
    if not cfg:
        return {"ok": False, "error": f"unknown surface {surface!r}; known: {sorted(SURFACES)}"}
    if not _host_allowed(cfg["url"]):
        return {"ok": False, "error": f"{cfg['url']} not on the allowlist"}
    c = connect()
    if not c.get("ok"):
        return c
    page = c["page"]
    try:
        page.goto(cfg["url"], timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        q = page.locator(cfg["query_placeholder"]).first
        q.click()
        if cfg.get("mode") == "contenteditable":
            # ProseMirror-style editable (e.g. ChatGPT) — type via keyboard, not .fill()
            page.keyboard.type(goal, delay=8)
        else:
            q.fill(goal)
        if cfg["submit"] == "Press Enter":
            page.keyboard.press("Enter")
        # wait for an answer node to appear / settle
        sel = cfg["answer"]
        try:
            page.wait_for_selector(sel, timeout=max_wait_s * 1000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        text = ""
        try:
            text = page.locator(sel).last.inner_text()
        except Exception:
            text = page.locator("body").inner_text()[:4000]
        return {"ok": True, "surface": surface, "url": page.url,
                "answer": (text or "")[:8000], "hint": "answer is raw DOM text; login/captcha are operator-owned"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    finally:
        try:
            page.close()
            c["page"]._mag_pw.stop()
        except Exception:
            pass


def status() -> dict[str, Any]:
    c = connect()
    if c.get("ok"):
        c["page"].close()
        c["page"]._mag_pw.stop()
    return {"schema": SCHEMA, "cdp": _cdp_endpoint(),
            "container_connected": bool(c.get("ok")), "error": c.get("error"),
            "surfaces": sorted(SURFACES)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    if cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif cmd == "open" and len(argv) > 1:
        print(json.dumps(open_url(argv[1]), indent=2, default=str))
    elif cmd == "ask" and len(argv) > 1:
        surface = "deepseek"
        if "--surface" in argv:
            i = argv.index("--surface")
            surface = argv[i + 1]
            del argv[i:i + 2]
        print(json.dumps(ask(" ".join(argv[1:]), surface=surface), indent=2, default=str)[:6000])
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
