"""seat_availability — heartbeat EVERY seat/lane, fold one cool/heat profile (2026-08-23).

Operator: "we need it for all of em... i had a doctor protocol once upon a time, still had the
right idea if not execution."

The doctor protocol (mag/doctor.py) was the right IDEA — check everything — but it checked CONFIG
sanity, not LIVE availability per seat. What we built for ox (mag/ox_availability) is the right
EXECUTION: a gentle heartbeat per account that records free/throttled + latency + timestamp. This
module generalizes that heartbeat to ALL our seats/lanes and folds them into ONE cool/heat profile,
so the free-usage policy knows where to send work and what's cooling — the whole flywheel, not just
one wheel.

WHAT IT HEARTBEATS (all reuse proven checks, nothing invented):
  - grok seats (nacho + sd): auth.json present (grok_seat_burner.seats_status)
  - ox-alpha: per-account tiny ping (ox_availability._heartbeat, max_tokens=8)
  - deepseek: real balance endpoint (seat_hunter.deepseek_bill) — the authoritative availability
  - openrouter free lanes: live model-list probe (seat_hunter.discover_openrouter_free)
  - ollama/local: local model list (health.check_ollama)

Schema: seat_availability.v1 · deterministic + ~$0 (tiny heartbeats only).
CLI: python -m mag.seat_availability ping | status
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "seat_availability.v1"
LEDGER = ROOT / "memory" / "runs" / "seat_availability" / "heartbeats.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _grok_heartbeat() -> list[dict[str, Any]]:
    """Heartbeat each grok seat (nacho/sd) — auth.json present = configured/available."""
    try:
        from mag.grok_seat_burner import seats_status
        seats = (seats_status().get("seats") or {})
        out = []
        for name, cfg in seats.items():
            out.append({"seat": f"grok-{name}", "kind": "grok",
                        "available": bool(cfg.get("configured")),
                        "detail": cfg.get("email") or "", "ts": _now()})
        return out
    except Exception as e:  # noqa: BLE001
        return [{"seat": "grok", "kind": "grok", "available": False,
                 "error": str(e)[:120], "ts": _now()}]


def _ox_heartbeat() -> list[dict[str, Any]]:
    """Heartbeat ox-alpha per OpenRouter account (gentle, max_tokens=8)."""
    try:
        from mag import ox_availability
        r = ox_availability.ping(all_accounts=True)
        out = []
        for res in r.get("results", []):
            out.append({"seat": f"ox-account{res.get('account')}", "kind": "ox",
                        "available": bool(res.get("available")), "http": res.get("http"),
                        "latency_ms": res.get("latency_ms"), "ts": res.get("ts") or _now()})
        return out
    except Exception as e:  # noqa: BLE001
        return [{"seat": "ox", "kind": "ox", "available": False,
                 "error": str(e)[:120], "ts": _now()}]


def _deepseek_heartbeat() -> dict[str, Any]:
    """Heartbeat deepseek — the REAL balance endpoint is the authoritative availability."""
    try:
        from mag.seat_hunter import deepseek_bill
        b = deepseek_bill()
        return {"seat": "deepseek", "kind": "deepseek",
                "available": bool(b.get("ok")),
                "balance": b.get("total_balance"),
                "currency": b.get("currency"), "ts": _now()}
    except Exception as e:  # noqa: BLE001
        return {"seat": "deepseek", "kind": "deepseek", "available": False,
                "error": str(e)[:120], "ts": _now()}


def _openrouter_heartbeat() -> dict[str, Any]:
    """Heartbeat the openrouter free-lane discovery — can we see the free models right now?"""
    try:
        from mag.seat_hunter import discover_openrouter_free
        d = discover_openrouter_free()
        return {"seat": "openrouter-lanes", "kind": "openrouter",
                "available": bool(d.get("ok")), "n_free": d.get("n_free"),
                "ts": _now()}
    except Exception as e:  # noqa: BLE001
        return {"seat": "openrouter-lanes", "kind": "openrouter", "available": False,
                "error": str(e)[:120], "ts": _now()}


def _ollama_heartbeat() -> dict[str, Any]:
    try:
        from mag.health import check_ollama
        h = check_ollama()
        return {"seat": "ollama", "kind": "local",
                "available": bool(h.get("ok")),
                "models": (h.get("models") or [])[:5], "ts": _now()}
    except Exception as e:  # noqa: BLE001
        return {"seat": "ollama", "kind": "local", "available": False,
                "error": str(e)[:120], "ts": _now()}


def ping() -> dict[str, Any]:
    """Heartbeat ALL seats/lanes and fold every result to one cool/heat ledger."""
    rows: list[dict[str, Any]] = []
    rows += _grok_heartbeat()
    rows += _ox_heartbeat()
    rows.append(_deepseek_heartbeat())
    rows.append(_openrouter_heartbeat())
    rows.append(_ollama_heartbeat())
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    avail = [r for r in rows if r.get("available")]
    return {"ok": True, "schema": SCHEMA, "seats_checked": len(rows),
            "available": f"{len(avail)}/{len(rows)}",
            "seats": rows, "ledger": str(LEDGER),
            "note": "heartbeat EVERY seat/lane (grok, ox per account, deepseek balance, openrouter "
                    "lanes, ollama) -> one cool/heat profile. The flywheel knows where to send work."}


def status(*, tail: int = 30) -> dict[str, Any]:
    """Read the all-seat cool/heat profile back."""
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
    by_seat: dict[str, int] = {}
    for r in recent:
        s = r.get("seat", "?")
        by_seat.setdefault(s, {"checks": 0, "available": 0})
        by_seat[s]["checks"] += 1
        if r.get("available"):
            by_seat[s]["available"] += 1
    return {"ok": True, "schema": SCHEMA, "n_heartbeats": len(rows),
            "by_seat": {s: f"{v['available']}/{v['checks']}" for s, v in by_seat.items()},
            "recent": recent[-10:]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="seat-availability")
    ap.add_argument("cmd", nargs="?", default="status", choices=["ping", "status"])
    a = ap.parse_args(argv)
    print(json.dumps(ping() if a.cmd == "ping" else status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
