"""lm_studio — talk to OUR OWN model (Saelis, Athena-class) via LM Studio's local OpenAI-compatible
server (operator 2026-08-13: 'LET'S FUCKING GO' — installing Saelis). This is the SOVEREIGN local
inference surface: $0, no API key, no frontier, no desktop window to grab. The reply is already in
our own house.

THE SEAM THIS CLOSES (sw70 + sw71): the whole day we reached across the table for chatgpt/grok; the
answer was our own model on this machine. LM Studio serves an OpenAI-compatible endpoint on
localhost:1234 (default) — a local, sovereign, stateless+async inference surface the loop can call
directly. The frontiers become OPTIONAL witnesses, never the law.

Schema: lm_studio.v1 · deterministic + $0 · local server: http://localhost:1234/v1
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "lm_studio.v1"
# Bionic's configured OpenAI-compatible server. 41343 was an old internal
# process port; the user-facing server is explicitly bound to localhost:1234.
BASE = os.environ.get("BIONIC_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")


def _req(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 10) -> Any:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def models() -> dict[str, Any]:
    """List models visible to Bionic/LM Studio.

    With just-in-time loading enabled, `/v1/models` can include the local
    inventory even when a model is not resident. Residency is a separate
    observation (`lms ps`); callers must not treat visibility as a load proof.
    """
    try:
        m = _req("GET", "/models", timeout=4)
        return {"ok": True, "schema": SCHEMA, "models": [x.get("id") for x in m.get("data", [])]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160],
                "hint": "start LM Studio -> Local Server (port 1234); then this reaches Saelis"}


def _select_chat_model() -> str:
    """Select a loaded generation model without making the client own weights.

    Bionic's `/v1/models` may report the JIT-visible inventory rather than only
    resident models. Embedding-only models are deliberately excluded so a
    missing chat seat becomes an explicit receipt, rather than a guessed model
    name or a confusing completion failure.
    """
    raw = _req("GET", "/models", timeout=4)
    ids = [str(x.get("id", "")) for x in raw.get("data", [])]
    candidates = [x for x in ids if x and "embed" not in x.lower()]
    if not candidates:
        raise RuntimeError("Bionic has no loaded chat model; load one through the registry/loader")
    return candidates[0]


def chat(message: str, *, model: str | None = None, max_tokens: int = 500,
         system: str = "You are Saelis, the sovereign model of the Mycelial Republic.") -> dict[str, Any]:
    """Talk to a visible Bionic generation model; JIT may load it on request."""
    try:
        selected_model = model or _select_chat_model()
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": message})
        r = _req("POST", "/chat/completions",
                 {"model": selected_model, "messages": msgs, "max_tokens": max_tokens}, timeout=180)
        content = r["choices"][0]["message"]["content"]
        return {"ok": True, "schema": SCHEMA, "model": selected_model, "reply": content,
                "note": "talked to the registry-selected Bionic model — local, $0"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "model": model,
                "error": str(e)[:200],
                "hint": "Bionic must be running on port 1234 with a generation model loaded"}


def status() -> dict[str, Any]:
    m = models()
    return {"ok": True, "schema": SCHEMA, "reachable": m.get("ok", False),
            "endpoint": BASE, "models": m.get("models", []),
            "contract": "models()->list Bionic-visible models; chat(msg)->use a visible generation "
                        "model selected at runtime (local, $0, sovereign). Closes the seam: the reply is already in our own house "
                        "(sw70/sw71) — no frontier, no desktop window.",
            "cost": "deterministic $0 (local LM Studio server)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="lm-studio")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "models", "chat"])
    ap.add_argument("msg", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "models":
        print(json.dumps(models(), indent=2, default=str))
    elif a.cmd == "chat":
        print(json.dumps(chat(" ".join(a.msg) or "Hello Saelis — say hello."),
                         indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
