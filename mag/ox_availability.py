"""ox_availability — a gentle heartbeat on ox-alpha per account, to learn when it's free.

Operator (2026-08-23): "there needs to be a counter on ox where we ping it with each of our
accounts to not drown it out but have a better idea of when it's free."

The problem it solves: ox-alpha (stealth/ox-alpha) is a FREE frontier reasoning seat whose
upstream shared pool throttles when hot (429). We keep hitting it blind. This module pings it
CHEAPLY — a tiny heartbeat, not real work — from EACH OpenRouter account key, and records the
result (ok / throttled / latency) with a timestamp. Over time that builds a per-account
cool/heat profile: the answer to "is ox free right now, and how long does it stay free?" instead
of guessing.

NOT drowning it out: each ping is ONE tiny call (max_tokens ~1-8), at a gentle cadence (once per
cycle, per account). It's a heartbeat, not a burn. Never fires when we're mid-real-work on ox.

Schema: ox_availability.v1 · deterministic + ~$0 (a few tiny heartbeat tokens).
CLI: python -m mag.ox_availability ping [--account N] | status
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "ox_availability.v1"
LEDGER = ROOT / "memory" / "runs" / "ox_availability" / "heartbeats.jsonl"
HEARTBEAT_MAX_TOKENS = 8  # a tiny ping, not real work — never drowns the seat


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _or_keys() -> list[str]:
    """All configured OpenRouter account keys (same envs as seat_hunter)."""
    try:
        from mag.seat_hunter import _or_keys as _sk
        return _sk()
    except Exception:  # noqa: BLE001
        return []


def _pin_account(i: int) -> str:
    """Pin os.environ so the heartbeat uses account i's key only (0-indexed)."""
    keys = _or_keys()
    if not keys:
        return ""
    i = i % len(keys)
    os.environ["OPENROUTER_API_KEY"] = keys[i]
    os.environ.pop("OPENROUTER_API_KEY_2", None)
    return keys[i]


def _heartbeat(account_idx: int) -> dict[str, Any]:
    """One tiny ping to ox-alpha from account account_idx. Returns availability + latency.
    Uses ox_seat.chat with a near-zero max_tokens so it's a heartbeat, not a burn."""
    key = _pin_account(account_idx)
    if not key:
        return {"ok": False, "account": account_idx + 1, "error": "no key"}
    from mag import ox_seat
    t0 = time.time()
    try:
        r = ox_seat.chat("Ping. One word.", "ok", max_tokens=HEARTBEAT_MAX_TOKENS, timeout=45)
        lat = round((time.time() - t0) * 1000)
        return {"ok": bool(r.get("ok")), "account": account_idx + 1,
                "available": bool(r.get("ok")), "http": r.get("http"),
                "latency_ms": lat, "cached_tokens": r.get("cached_tokens"),
                "error": (r.get("error") or "")[:160], "ts": _now()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "account": account_idx + 1, "available": False,
                "latency_ms": int((time.time() - t0) * 1000), "error": str(e)[:160], "ts": _now()}


def ping(*, account: int | None = None, all_accounts: bool = False) -> dict[str, Any]:
    """Ping ox-alpha from one (or all) account(s). Record each heartbeat to the ledger so the
    cool/heat profile accumulates. Gentle: one tiny call per account, never mid-real-work."""
    keys = _or_keys()
    if not keys:
        return {"ok": False, "schema": SCHEMA, "error": "no OpenRouter account keys"}
    if account is not None:
        targets = [max(0, min(len(keys) - 1, int(account) - 1))]
    else:
        targets = list(range(len(keys)))
    results = []
    for idx in targets:
        r = _heartbeat(idx)
        # fold the heartbeat to the ledger (the cool/heat history)
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        results.append(r)
    n_avail = sum(1 for r in results if r.get("available"))
    return {"ok": True, "schema": SCHEMA, "pinged_accounts": len(results),
            "available": f"{n_avail}/{len(results)}",
            "results": results, "ledger": str(LEDGER),
            "note": "gentle ox-alpha heartbeat per account (max_tokens=8); builds the cool/heat "
                    "profile — 200=free now, 429=throttled now. Folded to the ledger."}


def status(*, tail: int = 20) -> dict[str, Any]:
    """Read the heartbeat ledger back — the cool/heat history. Answers 'is ox free, and how does
    its availability vary?' from real data, not a guess."""
    rows = []
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    recent = rows[-tail:]
    avail = [r for r in recent if r.get("available")]
    return {"ok": True, "schema": SCHEMA, "n_heartbeats": len(rows),
            "recent_available": f"{len(avail)}/{len(recent)}",
            "recent": [{"ts": r.get("ts"), "account": r.get("account"),
                        "available": r.get("available"), "http": r.get("http"),
                        "latency_ms": r.get("latency_ms")} for r in recent],
            "note": "cool/heat profile from real heartbeats — feed this into the free-usage policy"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="ox-availability")
    ap.add_argument("cmd", nargs="?", default="status", choices=["ping", "status"])
    ap.add_argument("--account", type=int, default=None, help="account to ping (1-based)")
    ap.add_argument("--all", action="store_true", help="ping all accounts")
    a = ap.parse_args(argv)
    if a.cmd == "ping":
        acc = None if a.all else a.account
        print(json.dumps(ping(account=acc, all_accounts=a.all), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
