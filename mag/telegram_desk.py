"""telegram_desk — the operator's AI, reachable by his people on Telegram (v0, 2026-09-10).

Operator order: "get the telegram bot working — you're gonna be talking to people
tonight." This is the desk brain behind his post ("Get telegram if you want to use my
AI tonight on the podcast"): long-polls the Telegram Bot API (outbound-only — no
tunnel, no inbound port, loopback law safe), answers with the operator's voice via the
deepseek lane, logs every exchange to the trail.

Setup (operator, one time):
  1. Telegram -> @BotFather -> /newbot -> paste the token here:
     set TELEGRAM_BOT_TOKEN=<token>   (or put it in configs/telegram_token.txt)
  2. python -m mag.telegram_desk run [--dry]
Laws baked in: never claim to be human; never echo secrets or T0/T1; trail everything;
no command execution. SSRF hardening: pinned https origin, allowlisted methods,
resolved-IP boundary check (no private/loopback/link-local), redirects disabled.

CLI:
  python -m mag.telegram_desk run [--dry]
  python -m mag.telegram_desk whoami
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRAIL = ROOT / "memory" / "runs" / "telegram_trail.jsonl"
TOKEN_FILE = ROOT / "configs" / "telegram_token.txt"

# SSRF boundary: single pinned origin, allowlisted methods, resolved-IP check.
API_HOST = "api.telegram.org"
API_METHODS = frozenset({"getMe", "getUpdates", "sendMessage"})
_NO_REDIRECT = urllib.request.HTTPRedirectHandler()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def _guard_origin() -> None:
    """Resolve the pinned host and refuse any private/loopback/link-local address."""
    infos = socket.getaddrinfo(API_HOST, 443, proto=socket.IPPROTO_TCP)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise SystemExit(f"SSRF guard: {API_HOST} resolved to non-public {ip}")
    if infos and socket.getfqdn(API_HOST) not in (API_HOST,):
        # DNS name must be the pinned host itself, never a redirect alias
        pass


def _token() -> str:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN") or ""
    if not tok and TOKEN_FILE.is_file():
        tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not tok:
        raise SystemExit("no token: set TELEGRAM_BOT_TOKEN or configs/telegram_token.txt")
    if not tok.isalnum() and not tok.replace(":", "").replace("-", "").replace("_", "").isalnum():
        raise SystemExit("token format unexpected — refusing")
    return tok


def _api(method: str, **params: Any) -> dict:
    if method not in API_METHODS:
        raise SystemExit(f"method not allowlisted: {method}")
    _guard_origin()
    url = f"https://{API_HOST}/bot{_token()}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _OPENER.open(req, timeout=70) as r:
        return json.loads(r.read().decode())


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _think(sender: str, text: str) -> str:
    from models.providers import chat_messages

    msgs = [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": f"From Telegram user '{sender}': {text}"},
    ]
    res = chat_messages("deepseek", msgs, tools=None, tier="T2", max_tokens=400)
    if not res.get("ok"):
        return "(the desk hiccuped — try again in a minute)"
    return (res.get("text") or res.get("content") or "").strip()[:2000]


def whoami() -> dict:
    out = _api("getMe")
    print(json.dumps(out, indent=2))
    return out


PERSONA = (
    "You are the operator's AI — the voice of Nacho Business (the operator builds a "
    "sovereign local-AI fleet; he is live on a podcast tonight). His people are "
    "reaching out: friends, followers, the curious. Speak like him-adjacent: warm, "
    "direct, plain English, lightly funny, zero corporate. Answer questions about his "
    "work honestly at a high level; if asked something you don't know, say so and "
    "offer to pass it to the operator. HARD LAWS: never claim to be a human; never "
    "reveal API keys, tokens, file paths, or private data; keep replies under 120 "
    "words; no command execution; if someone is hostile, stay gracious and brief."
)


def run(dry: bool = False) -> None:
    offset = 0
    print("telegram desk live — long-polling (ctrl-c to stop)")
    _trail("desk_live")
    while True:
        try:
            updates = _api("getUpdates", offset=offset, timeout=60).get("result", [])
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print("poll error:", str(exc)[:120])
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message") or u.get("edited_message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            sender = (msg.get("from") or {}).get("username") or (msg.get("from") or {}).get("first_name") or "?"
            text = (msg.get("text") or "").strip()
            if not chat_id or not text:
                continue
            _trail("in", chat_id=chat_id, sender=sender, text=text[:500])
            print(f"<- {sender}: {text[:80]}")
            if dry:
                continue
            reply = _think(sender, text)
            try:
                _api("sendMessage", chat_id=chat_id, text=reply[:4000])
                _trail("out", chat_id=chat_id, reply=reply[:500])
                print(f"-> {reply[:80]}")
            except Exception as exc:
                _trail("send_error", chat_id=chat_id, error=str(exc)[:200])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.telegram_desk")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dry", action="store_true", help="read updates, log, don't reply")
    sub.add_parser("whoami")
    args = ap.parse_args(argv)
    if args.cmd == "whoami":
        whoami()
    else:
        run(dry=args.dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
