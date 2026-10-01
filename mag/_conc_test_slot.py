"""_conc_test_slot — start/end one worker of the group-of-five concurrency probe.

Operator GO 2026-09-05: measure what max concurrent requests do to the Max
coding-plan seat. Each worker leases a slot in the gate (lane 'codingplan',
model 'max-flash-5x', cap 5) and appends START/DONE rows to a shared JSONL so
overlapping wall-clocks prove real parallelism on the operator's surface.

CLI:
  python -m mag._conc_test_slot start <worker-name>
  python -m mag._conc_test_slot end <worker-name>
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag import concurrency_gate as cg  # noqa: E402

STATE_DIR = ROOT / "memory" / "runs" / "overseer"
TOKENS = STATE_DIR / "_conc_tokens.json"
ROWS = STATE_DIR / "conc_test_20260905.jsonl"
MODEL = "max-flash-5x"
LANE = "codingplan"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _append(row: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with ROWS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _tokens() -> dict:
    try:
        return json.loads(TOKENS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_tokens(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("start", "end"):
        print(__doc__)
        sys.exit(2)
    cmd, name = sys.argv[1], sys.argv[2]
    toks = _tokens()
    if cmd == "start":
        tok = cg.acquire(MODEL, lane=LANE, owner=name, timeout=90)
        toks[name] = tok
        _save_tokens(toks)
        _append({"w": name, "ev": "START", "ts": _now(), "epoch": time.time(),
                 "slot": tok})
        print(f"{name} START slot={tok}")
    else:
        tok = toks.pop(name, None)
        _save_tokens(toks)
        released = cg.release(tok) if tok else False
        _append({"w": name, "ev": "DONE", "ts": _now(), "epoch": time.time(),
                 "released": released})
        print(f"{name} DONE released={released}")


if __name__ == "__main__":
    main()
