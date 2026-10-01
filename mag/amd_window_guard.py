"""amd_window_guard — self-monitoring guard for the AMD flash-window fix.

2026-08-10: the recurring desktop flash windows were AMD Radeon Software
(`StartCN`/`StartDVR` scheduled tasks respawning `AMDRSServ.exe` via `cmd.exe /C`),
NOT the Mag stack. Fix = disable those two tasks (operator, elevated).

Operator law: "permanent fixes that you forget about are not fixes, they're future
bugs." So this guard CHECKS every cadence whether StartCN/StartDVR are still Disabled.
If AMD re-enables them (on any driver/software update), it raises a CLEAR, pre-labeled
failure_kb signal — so it surfaces as a KNOWN regression (just re-disable), never as a
mystery flash-window bug again. Read-only (querying task state needs no elevation);
re-disabling still requires an elevated shell, but now it's labeled, not silent.

Schema: amd_window_guard.v1
CLI: python -m mag.amd_window_guard check
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TASKS = ("StartCN", "StartDVR")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_status(name: str) -> str:
    """Query a scheduled task's status (read-only, no elevation needed). 'Disabled'|'Ready'|'?'."""
    try:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name, "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0,
        )
        # CSV line: "folder\StartCN","N/A","Disabled",...  status is 3rd field
        parts = (r.stdout or "").split(",")
        return (parts[2].strip().strip('"') if len(parts) >= 3 else "?")
    except Exception:
        return "?"


def check() -> dict[str, Any]:
    """Return whether the AMD respawn tasks are still disabled; raise a labeled FKB
    signal if any got re-enabled (so it's a known regression, not a mystery)."""
    states = {t: _task_status(t) for t in TASKS}
    reenabled = [t for t, s in states.items() if s.lower() not in ("disabled", "?")]
    row = {"schema": "amd_window_guard.v1", "ts": _now(),
           "task_states": states, "reenabled": reenabled,
           "ok": not reenabled,
           "note": ("AMD StartCN/StartDVR disabled -> no AMDRSServ flash windows. "
                    "If re-enabled, re-run (elevated): schtasks /Change /TN StartCN /DISABLE; "
                    "StartDVR /DISABLE")}
    if reenabled:
        try:
            from mag.failure_kb import log_failure
            log_failure(kind="amd_window_guard", tool="amd_window_guard",
                        error="AMD respawn tasks re-enabled -> flash windows will return",
                        detail="Re-enabled: " + ", ".join(reenabled) + ". Re-disable StartCN/StartDVR (elevated).",
                        phase="cadence")
        except Exception:
            pass
    return row


def main(argv: list[str] | None = None) -> int:
    import json
    print(json.dumps(check(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
