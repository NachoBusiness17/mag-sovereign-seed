"""window_audit — passive RECORD of every flash-crash window spawn (observer, no action).

Operator (2026-08-10): "flash crash windows that spawn 8 times and die regularly — there
needs to be a record of this somewhere. It's just a window on the desktop that spawns 8
times and dies regularly."

This is a pure APPEND-ONLY audit of python processes that appear with a visible console
window (System32 conhost) and die. Every NEW windowed python is recorded (ts/pid/parent/
cmd), and its death is recorded when it disappears. It NEVER kills or acts — a stateless
observer — so it does not violate the stateless design. It is wired into the ghost daemon
as a background loop so the flash-crash burst is captured over time.

Log: logs/window_spawns.jsonl
Schema: window_audit.v1
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from mag.win_powershell import powershell_exe
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOG = ROOT / "logs" / "window_spawns.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _snapshot() -> dict[int, dict[str, Any]]:
    """pid -> {pid, parent, cmd} for python/pythonw processes WITH a visible window."""
    out: dict[int, dict[str, Any]] = {}
    try:
        ps = (powershell_exe() + " -NoProfile -Command "
              r"Get-Process python,pythonw -ErrorAction SilentlyContinue | "
              r"Where-Object { $_.MainWindowTitle } | "
              r"Select-Object Id,@{N='P';E={(Get-CimInstance Win32_Process -Filter ('ProcessId={0}' -f $_.Id)).ParentProcessId}},@{N='C';E={(Get-CimInstance Win32_Process -Filter ('ProcessId={0}' -f $_.Id)).CommandLine}} | "
              r"ConvertTo-Json -Compress")
        r = subprocess.run(ps, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=8,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
        d = json.loads(r.stdout.strip() or "[]")
        if isinstance(d, dict):
            d = [d]
        for p in d or []:
            pid = int(p.get("Id"))
            out[pid] = {"pid": pid, "parent": p.get("P"), "cmd": (p.get("C") or "")[:400]}
    except Exception:
        pass
    return out


def _record(row: dict[str, Any]) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def poll_once(known: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """One audit pass: record NEW windowed pids (spawn) and DEATHS of gone ones."""
    cur = _snapshot()
    for pid, info in cur.items():
        if pid not in known:
            _record({"schema": "window_audit.v1", "ts": _now(), "event": "spawn",
                     "pid": pid, "parent": info.get("parent"), "cmd": info.get("cmd")})
    for pid, info in known.items():
        if pid not in cur:
            _record({"schema": "window_audit.v1", "ts": _now(), "event": "death",
                     "pid": pid, "cmd": info.get("cmd")})
    return cur


def run_once() -> dict[str, Any]:
    """One audit pass (spawn+death diff) — returns counts. Read-only."""
    before = {}
    after = poll_once(before)
    return {"ok": True, "spawned": sum(1 for p in after.values() if p["pid"] in after),
            "windowed_now": len(after), "log": str(LOG)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    once = bool(argv and argv[0] == "once")
    known: dict[int, dict[str, Any]] = {}
    if once:
        known = poll_once(known)
        print(json.dumps({"ok": True, "windowed_now": len(known), "log": str(LOG)},
                         indent=2, default=str))
        return 0
    # continuous recorder (used by the daemon background loop)
    while True:
        known = poll_once(known)
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
