"""cast_guard — baked-in defense for the cast/wearable LAN server: LAN-only + probe detection.

Operator (2026-08-11): "lets keep it lan only for now and detect people trying to gate into it as
a baked in defense as we've discussed heavily about security in the past."

WHAT IT DOES (deterministic, $0, in-process — no external service):
  1. LAN-ONLY — a control route is refused unless the client is on a private/local range (the cast
     server may bind :8766 with --lan, but CONTROLLING it still requires a LAN client + token).
  2. TOKEN — reuses mag.remote_control.authorized(token_from_headers) (X-Mag-Token vs
     MAG_REMOTE_TOKEN env). The token is the operator's own secret; the wearable sends it via header.
  3. PROBE DETECTION — every failed auth / non-LAN attempt is logged to
     memory/security/cast_probes.jsonl (ip, path, reason, ts). Repeated failures from one IP are
     rate-limited and the IP is TEMPORARILY BLOCKED (in-process block window) — the "detect people
     trying to gate into it" seam.
  4. FAIL-OPEN vs FAIL-CLOSED — control routes are FAIL-CLOSED (deny by default). Read-only display
     routes stay viewable (the Roku cast surface). This is baked-in: no config to forget.

Schema: cast_guard.v1 · deterministic + $0 · reuse: remote_control (token)
"""
from __future__ import annotations

import ipaddress
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

SCHEMA = "cast_guard.v1"
PROBES_PATH = ROOT / "memory" / "security" / "cast_probes.jsonl"

# in-process block table: ip -> {until_ts, fails}
_BLOCKS: dict[str, dict[str, float]] = {}
FAIL_LIMIT = 5          # fail auth this many times within window -> block
BLOCK_WINDOW = 600.0    # seconds
RATE_MS = 600           # min ms between control calls per IP (rate limit)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_lan(ip: str) -> bool:
    """True when the client address is private/local (LAN-only). Deterministic."""
    if not ip:
        return False
    if ip in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    return a.is_private or a.is_loopback or a.is_link_local


def _log_probe(ip: str, path: str, reason: str) -> None:
    PROBES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROBES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "ip": ip, "path": path, "reason": reason}) + "\n")


_last_call: dict[str, float] = {}


def rate_limited(ip: str) -> bool:
    now = time.time() * 1000
    prev = _last_call.get(ip, 0)
    if now - prev < RATE_MS:
        return True
    _last_call[ip] = now
    return False


def blocked(ip: str) -> bool:
    b = _BLOCKS.get(ip)
    if not b:
        return False
    if time.time() >= b["until"]:
        _BLOCKS.pop(ip, None)
        return False
    return True


def _register_fail(ip: str) -> bool:
    """Count a failed attempt; if it hits FAIL_LIMIT within the window, block. Returns blocked."""
    now = time.time()
    b = _BLOCKS.get(ip)
    if not b or now >= b.get("_win_end", now + BLOCK_WINDOW):
        b = {"fails": 0, "_win_end": now + BLOCK_WINDOW}
        _BLOCKS[ip] = b
    b["fails"] = b.get("fails", 0) + 1
    if b["fails"] >= FAIL_LIMIT:
        b["until"] = now + BLOCK_WINDOW
        _log_probe(ip, "", "temporary_block")
        return True
    return False


def guard(ip: str, path: str, token: str | None = None, *, control: bool = True) -> dict[str, Any]:
    """Baked-in gate for a route. control=True => fail-closed (token + LAN required)."""
    if blocked(ip):
        return {"ok": False, "deny": "blocked", "reason": "ip_temporarily_blocked"}
    if rate_limited(ip):
        return {"ok": False, "deny": "rate_limited", "reason": "too_fast"}
    if not _is_lan(ip):
        _log_probe(ip, path, "non_lan")
        _register_fail(ip)
        return {"ok": False, "deny": "non_lan", "reason": "lan_only"}
    if control:
        try:
            from mag import remote_control
            if not remote_control.authorized(token):
                _log_probe(ip, path, "bad_token")
                _register_fail(ip)
                return {"ok": False, "deny": "unauthorized", "reason": "token_required"}
        except Exception:
            return {"ok": False, "deny": "unauthorized", "reason": "guard_error"}
    return {"ok": True, "lan": True, "control": control}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "fail_limit": FAIL_LIMIT,
            "block_window_s": int(BLOCK_WINDOW), "lan_only": True,
            "token": "MAG_REMOTE_TOKEN", "control": "fail_closed",
            "probes": str(PROBES_PATH.relative_to(ROOT)).replace("\\", "/"),
            "n_blocked": len([k for k, v in _BLOCKS.items() if time.time() < v.get("until", 0)])}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="cast-guard")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), indent=2))
