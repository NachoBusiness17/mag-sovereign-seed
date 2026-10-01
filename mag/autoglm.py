"""autoglm — AutoGLM-Phone brain seat on the z.ai key (2026-09-04).

The embodied lane, vendor-documented (docs/ref/zai_docs_mirror/guides/vlm/
autoglm-phone-multilingual.md): screenshot in → ONE action out. The vendor designed the
loop but does not host it — the harness (screenshot, adb execution, receipts) is the
fleet's. This organ is the BRAIN HALF ONLY: image + instruction → action JSON.

Structure mirrors mag/vision.py (the committed pattern): base64 data-URL image in the
user message, Bearer key from env/.env, urllib POST, JSON dict out. No subprocess here —
adb execution stays in the shell lane.

SSRF posture (mimosa-audited 09-04): endpoint is pinned (https + api.z.ai only),
resolved addresses must be public (no loopback/private/link-local), redirects refused.

CLI: python -m mag.autoglm act <image_path> "<instruction>"
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "autoglm.v1"
MODEL = os.environ.get("AUTOGLM_MODEL", "autoglm-phone-multilingual")
API_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"  # 09-16: coding-plan keys 1113 on the old /api/paas/v4 path even with full pool
PINNED_SCHEME = "https"
PINNED_HOST = "api.z.ai"
KEY_NAMES = ("ZAI_API_KEY_Lite", "ZAI_API_KEY_Pro", "ZAI_API_KEY")  # Calcifer lane first

ACTION_GRAMMAR = (
    'Reply with ONE action as JSON only, one of: '
    '{"action":"tap","x":<int>,"y":<int>} | {"action":"type","text":"..."} | '
    '{"action":"swipe","x1":<int>,"y1":<int>,"x2":<int>,"y2":<int>} | '
    '{"action":"back"} | {"action":"home"} | {"action":"wait"} | '
    '{"action":"take_over","reason":"..."}'
)


def _validate_endpoint() -> None:
    """SSRF guard: pinned scheme+host; every resolved address must be public."""
    parsed = urllib.parse.urlparse(API_URL)
    if parsed.scheme != PINNED_SCHEME or parsed.hostname != PINNED_HOST:
        raise ValueError("endpoint is not on the pinned allowlist")
    infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    for _, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("pinned endpoint resolves to a non-public address — refusing")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow redirects — the request stays on the pinned host or dies."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _key() -> str:
    for name in KEY_NAMES:
        v = os.environ.get(name)
        if v:
            return v
    try:
        for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            if k in KEY_NAMES and v.strip():
                return v.strip().strip('"').strip("'")
    except Exception:  # noqa: BLE001
        pass
    return ""


def _image_url(image: str) -> str:
    if image.startswith(("http://", "https://", "data:")):
        return image
    b64 = base64.b64encode(Path(image).read_bytes()).decode("utf-8")
    return "data:image/png;base64," + b64


def _parse_action(text: str) -> dict[str, Any]:
    """First '{' to last '}' via string ops; malformed → honest take_over, never a guess."""
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict) and "action" in obj:
                return obj
        except json.JSONDecodeError:
            pass
    return {"action": "take_over", "reason": "unparseable reply: " + text[:200]}


def act(image: str, instruction: str, *, max_tokens: int = 1024) -> dict[str, Any]:
    """Screenshot + instruction → one action dict (or honest take_over)."""
    instruction = (instruction or "").strip()
    if not instruction:
        return {"ok": False, "schema": SCHEMA, "error": "no instruction"}
    key = _key()
    if not key:
        return {"ok": False, "schema": SCHEMA, "error": "no ZAI key in env or .env"}
    try:
        _validate_endpoint()
    except (ValueError, OSError) as e:
        return {"ok": False, "schema": SCHEMA, "error": "endpoint guard: " + str(e)[:200]}
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": _image_url(image)}},
            {"type": "text", "text": "You are an Android UI agent. The screenshot is the "
             "current screen. Task: " + instruction + " " + ACTION_GRAMMAR},
        ]}],
        "temperature": 0.0, "top_p": 0.85, "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    })
    try:
        with _OPENER.open(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        text = str((choice.get("message") or {}).get("content") or "").strip()
        return {"ok": True, "schema": SCHEMA, "model": MODEL,
                "action": _parse_action(text), "raw": text[:400],
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "schema": SCHEMA, "error": "HTTP " + str(e.code) + ": "
                + e.read().decode("utf-8", errors="replace")[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": type(e).__name__ + ": " + str(e)[:200]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autoglm", description="AutoGLM-Phone brain seat (z.ai)")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("act")
    p.add_argument("image")
    p.add_argument("instruction")
    p.add_argument("--max-tokens", type=int, default=1024)
    a = ap.parse_args(argv)
    if a.cmd == "act":
        out = act(a.image, a.instruction, max_tokens=a.max_tokens)
    else:
        out = {"ok": False, "error": "usage: python -m mag.autoglm act <image> <instruction>"}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
