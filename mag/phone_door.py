"""phone_door — the tailnet phone-door hook (Ponytail discipline, 2026-09-07).

The operator's phone reaches the fleet through tailscale serve. Android battery
optimization puts the tunnel to sleep ("idle") and the door dies SILENTLY — the
zero-fire drain Ponytail warns about. This hook wakes the tunnel and records its
fire-rate, so door health is measured, not assumed.

Ponytail rules honored: every fire logged; a hook with 0 fires in 72h gets a prune
note; the door counts as UP only when a ping actually succeeds.

CLI:
  python -m mag.phone_door ensure     # ping the phone, log the fire, wake if asleep
  python -m mag.phone_door status     # fire-rate: last 10 fires, ok count, prune check
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "memory" / "runs" / "phone_door_log.jsonl"
PHONE = "moto-g-5g---2024"
PRUNE_H = 72


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ensure() -> dict:
    try:
        out = subprocess.run(["tailscale", "ping", "--c", "2", PHONE],
                             capture_output=True, text=True, timeout=30).stdout
        ok = "pong from" in out
        latency = out.split("in ")[-1].strip() if ok else ""
    except Exception as exc:
        ok, out, latency = False, "", f"ERR {type(exc).__name__}"
    row = {"ts": _now(), "hook": "phone-door", "ok": ok, "phone": PHONE, "latency": latency}
    _log(row)
    return row


def status() -> str:
    if not LOG.is_file():
        return "no fires logged yet — door health unknown"
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    recent = rows[-10:]
    oks = sum(1 for r in recent if r.get("ok"))
    last = rows[-1]
    lines = [f"fires: {len(rows)} total, {oks}/{len(recent)} ok in last {len(recent)}",
             f"last: {last['ts']} ok={last.get('ok')} latency={last.get('latency', '')}"]
    age_h = (time.time() - LOG.stat().st_mtime) / 3600 if LOG.is_file() else 999
    if age_h > PRUNE_H:
        lines.append(f"PRUNE NOTE: door silent {age_h:.0f}h — the tailnet door is presumed down")
    return "\n".join(lines)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ensure"
    if cmd == "ensure":
        r = ensure()
        print(json.dumps(r, ensure_ascii=False))
    elif cmd == "status":
        print(status())
    else:
        print(__doc__)
