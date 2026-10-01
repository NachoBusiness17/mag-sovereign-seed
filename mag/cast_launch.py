"""cast_launch — the ARCHITECTURE PATH for launching the LAN voice/dashboard server (the phone-
dictate surface). The operator's 'launch it' is a system-imperative op that should go through the
architecture (extension_deploy precedent), not a raw terminal spawn.

OPERATOR (2026-08-13): "my daughter demands my presence... i need to take this from the desktop to my
phone so i can dictate" + "launch it plz" + correction "wrong tool" (terminal is the wrong tool for a
framework op).

THE PATH (self-steal, extension_deploy precedent — op with no path gets a REST route):
  launch(host, port) -> start the cast_server/dashboard on the LAN (0.0.0.0) via our own runtime
                        (mag.cast_server.run / the dashboard), headless. The phone reaches it at
                        http://<PC-IP>:8765/voice (hold-to-talk dictate).
  REST: POST /api/v1/cast/launch  -> launch()  (mirrors POST /api/v1/extension/deploy)

Schema: cast_launch.v1 · deterministic · reuse: cast_server, runtime, extension_deploy (the precedent)
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

SCHEMA = "cast_launch.v1"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765


def launch(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Start the LAN voice/dashboard server via OUR OWN runtime (cast_server.run), headless. The
    phone reaches it at http://<PC-IP>:<port>/voice (hold-to-talk dictate). This is the architecture
    path — not a raw terminal spawn."""
    try:
        from mag import cast_server
        # cast_server.run is the framework's own launch (windowless, supervised) — never a terminal.
        cast_server.run(host=host, port=port)
        return {"ok": True, "schema": SCHEMA, "host": host, "port": port,
                "url": f"http://{host}:{port}/voice",
                "note": "LAN voice/dashboard launched via the framework's own runtime (not a terminal)"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "host": host, "port": port,
                "error": f"cast launch failed: {str(e)[:160]}"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "launch(host,port)->start the LAN voice/dashboard via cast_server.run (the "
                        "architecture path); REST POST /api/v1/cast/launch",
            "phone_usage": "on the same Wi-Fi, open http://<PC-LAN-IP>:8765/voice, hold-to-talk, "
                           "dictate, hear the answer",
            "reuses": ["cast_server", "extension_deploy (the op-with-no-path precedent)"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="cast-launch")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "launch"])
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = ap.parse_args()
    if a.cmd == "launch":
        print(json.dumps(launch(host=a.host, port=a.port), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
