#!/usr/bin/env python3
"""Read-only cast receiver — Spotify-to-Roku style LAN pulse + optional voice POC.

Serves:
  GET /                   → server-rendered cast page (Roku-safe, meta refresh)
  GET /voice              → phone voice UI (Web Speech STT + TTS)
  GET /health             → instant ping
  GET /api/v1/display     → TV-safe JSON
  POST /api/v1/voice/turn → legacy one-shot turn
  POST /api/v1/voice/scratch → scratch pad append/commit/wake
  GET|POST /api/v1/voice/stt → local faster-whisper (no voice train)

Default: 127.0.0.1:8766 — use --lan for WiFi receivers you point at manually.
"""
from __future__ import annotations

import html
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

STATIC = Path(__file__).resolve().parents[1] / "dashboard" / "static"
DEFAULT_PORT = 8766
REFRESH_SECONDS = 15

_ALLOWED = frozenset(
    {
        "/",
        "/cast.html",
        "/voice",
        "/wearable",
        "/control",
        "/health",
        "/api/v1/display",
        "/api/display",
        "/api/v1/voice/turn",
        "/api/v1/voice/scratch",
        "/api/v1/voice/stt",
        "/api/v1/voice/dictate",
        "/api/v1/remote/status",
        "/api/v1/remote/intent",
        "/api/v1/wearable/surface",
        "/api/v1/wearable/command",
    }
)

_CAST_CSS = """
:root { color-scheme: dark; font-family: system-ui, sans-serif; background: #0a0e14; color: #e6edf3; }
body { margin: 0; padding: 1.25rem; line-height: 1.45; }
h1 { font-size: 1.35rem; margin: 0 0 0.35rem; }
.muted { color: #8b949e; font-size: 0.9rem; }
.headline { font-size: 1.15rem; margin: 1rem 0; }
.events { margin-top: 1rem; }
.event { padding: 0.35rem 0; border-top: 1px solid #21262d; }
.pulse { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; background: #3fb950; margin-right: 0.35rem; vertical-align: middle; }
.pulse.thinking { background: #d29922; }
"""


def render_cast_page(payload: dict[str, Any]) -> str:
    """Server-rendered HTML — works on Roku / thin browsers (no JS required)."""
    lp = payload.get("local_pulse") or {}
    desk = payload.get("desk") or {}
    thinking = bool(lp.get("thinking"))
    status = html.escape(str(payload.get("status") or "—"))
    ts = html.escape(str(payload.get("ts") or ""))
    headline = html.escape(str(payload.get("headline") or "Mag pulse"))
    goal = html.escape(str(desk.get("goal") or ""))
    tail_bits = [html.escape(str(x)) for x in (desk.get("dialogue_tail") or [])[-2:]]
    desk_parts = [f"Goal: {goal}"] if goal else []
    desk_parts.extend(tail_bits)
    desk_line = " · ".join(desk_parts)
    events = "".join(
        f'<div class="event">{html.escape(str(e))}</div>' for e in (payload.get("events") or [])[:8]
    )
    pulse_cls = "thinking" if thinking else "idle"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="refresh" content="{REFRESH_SECONDS}" />
  <title>Mag Cast</title>
  <style>{_CAST_CSS}</style>
</head>
<body>
  <h1>Mag Cast</h1>
  <div class="muted"><span class="pulse {pulse_cls}"></span>{status} · {ts}</div>
  <div class="headline">{headline}</div>
  <div class="muted">{desk_line or "—"}</div>
  <div class="events">{events or '<div class="muted">No recent events</div>'}</div>
  <p class="muted" style="margin-top:1rem">Phone voice: <a href="/voice">/voice</a> (hold-to-talk)</p>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "MagCast/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/static/"):
            return self._static(path[len("/static/") :])
        if path not in _ALLOWED:
            self._json(404, {"ok": False, "error": "cast receiver — read-only routes only"})
            return
        if path == "/health":
            self._json(
                200,
                {
                    "ok": True,
                    "service": "mag-cast",
                    "voice": True,
                    "routes": [
                        "GET /",
                        "GET /voice",
                        "POST /api/v1/voice/turn",
                        "GET|POST /api/v1/voice/stt",
                        "POST /api/v1/voice/dictate",
                    ],
                },
            )
            return
        if path == "/voice":
            return self._file(STATIC / "cast-voice.html", "text/html; charset=utf-8")
        if path == "/wearable":
            if not self._guard(control=False):
                return
            return self._file(STATIC / "wearable.html", "text/html; charset=utf-8")
        if path == "/api/v1/wearable/surface":
            if not self._guard(control=False):
                return
            try:
                from mag.wearable_swarm import surface
                self._json(200, surface())
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"wearable surface: {exc!s}"[:200]})
            return
        if path == "/api/v1/wearable/command":
            if not self._guard(control=True):
                return
            try:
                from mag.wearable_swarm import command
                self._json(200, command(self._query_param("text", ""), dry=True, source="wearable"))
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"wearable command: {exc!s}"[:200]})
            return
        if path == "/control":
            return self._file(STATIC / "control.html", "text/html; charset=utf-8")
        if path == "/api/v1/voice/stt":
            try:
                from mag.voice_stt import handle_stt

                self._json(200, handle_stt({"action": "status"}))
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"stt status: {exc!s}"[:200]})
            return
        if path == "/api/v1/remote/status":
            if not self._guard(control=True):
                return
            from mag.remote_control import status

            self._json(200, status())
            return
        if path in ("/", "/cast.html"):
            from mag.display import build_display_payload

            page = render_cast_page(build_display_payload(fast=True))
            raw = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path in ("/api/v1/display", "/api/display"):
            from mag.display import build_display_payload

            self._json(200, build_display_payload(fast=True))
            return
        if path == "/api/v1/feed":
            # The Mycelial Republic feed: high-signal $0 wins (Tumblr/IG-style), mapped to internals.
            try:
                from mag.republic_feed import feed
                tail_raw = self._query_param("tail", "50")
                try:
                    tail_n = int(tail_raw)
                except ValueError:
                    tail_n = 50
                self._json(200, feed(tail=tail_n))
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"feed: {exc!s}"[:200]})
            return
        if path == "/feed":
            return self._file(STATIC / "feed.html", "text/html; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {
            "/api/v1/voice/turn",
            "/api/v1/voice/scratch",
            "/api/v1/voice/stt",
            "/api/v1/voice/dictate",
            "/api/v1/remote/intent",
        }:
            self._json(405, {"ok": False, "error": "unsupported cast action"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception as exc:
            self._json(400, {"ok": False, "error": f"bad JSON: {exc!s}"[:120]})
            return
        if path == "/api/v1/remote/intent":
            if not self._guard(control=True):
                return
            from mag.remote_control import submit_intent

            out = submit_intent(body)
            self._json(202 if out.get("ok") else 400, out)
            return

        if path == "/api/v1/voice/scratch":
            try:
                from mag.voice_scratch import handle_scratch

                out = handle_scratch(body)
                code = 200 if out.get("ok") or out.get("cancelled") else 400
                self._json(code, out)
            except Exception as exc:
                self._json(
                    500,
                    {
                        "ok": False,
                        "error": f"scratch crash: {exc!s}"[:240],
                        "speak_text": "Server hiccup — try once more.",
                    },
                )
            return

        if path == "/api/v1/voice/stt":
            try:
                from mag.voice_stt import handle_stt

                out = handle_stt(body)
                self._json(200, out)
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"stt crash: {exc!s}"[:240], "text": ""})
            return

        if path == "/api/v1/voice/dictate":
            try:
                from mag.voice_dictate import handle_dictate

                self._json(200, handle_dictate(body))
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"dictate crash: {exc!s}"[:240]})
            return

        try:
            from mag.voice_turn import handle_voice_turn

            out = handle_voice_turn(body)
            self._json(200 if out.get("ok") else 400, out)
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"voice_turn crash: {exc!s}"[:240]})

    def _query_param(self, name: str, default: str = "") -> str:
        """Read a query-string param from self.path (no deps)."""
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(self.path).query)
        vals = q.get(name)
        return vals[0] if vals else default

    def _guard(self, *, control: bool = True) -> bool:
        """Baked-in LAN-only + token defense (mag.cast_guard). Writes 401/403 on deny."""
        try:
            from mag.cast_guard import guard
            from mag.remote_control import token_from_headers
            ip = self.client_address[0] if self.client_address else ""
            g = guard(ip, self.path, token_from_headers(self.headers), control=control)
            if g.get("ok"):
                return True
            self._json(401 if g.get("deny") == "unauthorized" else 403, {"ok": False, **g})
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"guard: {exc!s}"[:160]})
        return False

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Mag-Token")

    def _json(self, code: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._json(404, {"ok": False, "error": "missing cast.html"})
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _static(self, rel: str) -> None:
        safe = Path(rel).name if rel else ""
        path = STATIC / safe
        if not path.is_file() or path.resolve().parent != STATIC.resolve():
            self._json(404, {"ok": False, "error": "not found"})
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self._file(path, ctype)


def run(*, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    from config import print_bind_banner

    httpd = ThreadingHTTPServer((host, port), Handler)
    print_bind_banner(host=host, port=port, service="cast")
    print("  routes: GET / · GET /voice · POST voice/turn|scratch|stt · GET /health")
    print(f"  auto-refresh every {REFRESH_SECONDS}s — Roku-safe (no JavaScript)")
    print("  no network discovery — type URL on receiver manually")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
