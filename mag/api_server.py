"""Mag API Gateway — FastAPI backend (Epoch 1 · Pillar I).

Requirement (a): FastAPI backend.

This module exposes the :mod:`mag.api_gateway` route registry over FastAPI.
Every route is gated by the ``X-API-Key`` header (enforced as a FastAPI
dependency, so it cannot be skipped per-route). The gateway registry is
bridged via a catch-all route, so any endpoint registered with
``@api_gateway.route(...)`` is served automatically — later epochs just
register handlers and they appear here.

Run it::

    python main.py api            # uvicorn on 127.0.0.1:8001
    python main.py api --port 9000

Or directly::

    python -m uvicorn mag.api_server:app --host 127.0.0.1 --port 8001

Dependency-light: importing this module pulls FastAPI/uvicorn but NOT the
LangGraph daemon chain or model stack. Handlers stay lazy.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from mag import api_gateway as gw
from mag import mcp_http  # noqa: F401 — registers POST /mcp on the gateway registry

DEFAULT_HOST = "127.0.0.1"
# :8000 is reserved for backend.server (/health and /run_task), which is the
# local tool API used by the agent seat. Keep the authenticated gateway on its
# own default port so `main.py api` cannot silently replace the tool backend.
DEFAULT_PORT = 8001

app = FastAPI(
    title="Mag API Gateway",
    version="0.1.0",
    description="Sovereign local HTTP surface for Mag (Epoch 1). "
    "All endpoints require the X-API-Key header.",
)

# 2026-08-29: the operator's board page (file:// on the desktop) fetches this
# loopback-bound service — allow cross-origin from anywhere; the port never
# leaves the machine and every route still requires the key.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def require_api_key(x_api_key: str | None = Header(default=None),
                     request: "Request" = None) -> None:
    """FastAPI dependency — reject requests without a valid API key.

    2026-08-29: the key may also ride ?key= (operator's board page on the
    desktop; the gateway layer accepts it too — both doors agree).
    """
    key = x_api_key
    if not key and request is not None:
        key = request.query_params.get("key")
    if not gw.check_api_key({"X-API-Key": key or ""}):
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


# --- bridge: serve every route in the gateway registry ---


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    dependencies=[Depends(require_api_key)],
)
async def gateway_bridge(path: str, request: Request) -> JSONResponse:
    """Catch-all: dispatch to the gateway registry handler for this path.

    The gateway registry (``mag/api_gateway``) owns routing + the security
    gate; this bridge just adapts the ASGI request into the gateway's
    ``(params, body) -> (status, dict)`` contract.
    """
    # Reconstruct the path (FastAPI strips the leading slash in {path:path}).
    full_path = "/" + path if path else "/"

    # Parse JSON body if present.
    body: dict[str, Any] | None = None
    if request.method in ("POST", "PUT", "PATCH"):
        raw = await request.body()
        if raw:
            try:
                body = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "error": "invalid JSON body"},
                )

    # Headers as a plain dict for the gateway gate; query params flow too
    # (2026-08-29: fixes ?n= being ignored; enables ?key= browser access).
    headers = {k: v for k, v in request.headers.items()}
    query = dict(request.query_params)

    status, payload = gw.dispatch(request.method, full_path, headers=headers,
                                  body=body, query=query)
    return JSONResponse(status_code=status, content=payload)


# --- direct convenience endpoints (also gated) ---


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Launch the FastAPI app via uvicorn (blocking)."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
