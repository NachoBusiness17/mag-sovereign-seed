"""platform_kill — a fast, deterministic 'kill all Mag terminal platforms' skill.

Shadow / Ghost / the operator can call this to tear down EVERY Mag platform
process + the container in one pass, instead of hunting per-process. Reusable,
idempotent, fast.

What it stops (in order, one sweep):
  1. Host Mag python processes (autorun loops, backend, dashboard, ghost, drainer,
     lab, orchestrator drains, synthesis scribe, legacy/leaked loops) — taskkill /T /F.
  2. The containerized stack (mag-sovereign + redis) via docker_ops.down().
  3. process_supervisor tracked loops + state (so nothing auto-restarts after).

Safety: `dry=True` reports without killing. Never touches VS Code / the editor.

Schema: platform_kill.v1
CLI:  python -m mag.platform_kill [--dry]          (main.py platform-kill [--dry])
REST: POST /api/v1/platform/kill {dry:bool}        (GET = report what it WOULD kill)
"""
from __future__ import annotations

import json
import shutil
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

SCHEMA = "platform_kill.v1"
MAG_CMD_MARKERS = (
    "governor_autorun import autorun_loop", "main.py agent", "main.py autorun",
    "main.py dashboard", "main.py lab", "orchestrator drain", "backend.server",
    "mag.ghost", "synthesis_agent", "mag_launch", "main.py orchestrator",
    "seat_guard", "main.py supervisor", "process_supervisor",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _enum_host_pids() -> list[dict[str, Any]]:
    """Enumerate host Mag python processes (their own python.exe / pythonw.exe)."""
    out: list[dict[str, Any]] = []
    try:
        import psutil  # type: ignore
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = " ".join(proc.info.get("cmdline") or [])
                if any(m in cmd for m in MAG_CMD_MARKERS) and "platform_kill" not in cmd:
                    out.append({"pid": proc.info["pid"], "cmd": cmd[:200]})
            except Exception:
                continue
    except ImportError:
        import subprocess
        # B2-85 2026-09-26: bare "powershell" is not on PATH in every launch
        # context (sig run_shell:e566037def80 "[Errno 2] ... powershell",
        # 7,964 FKB rows since 2026-09-19). Resolve the full path; System32
        # fallback when PATH lookup misses (pattern mag/process_reaper.py).
        ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
        if not ps_exe and sys.platform == "win32":
            ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if not ps_exe:
            return out
        r = subprocess.run([ps_exe, "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process | "
                            "Where-Object { $_.Name -in @('python.exe','pythonw.exe') } | "
                            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        try:
            data = json.loads(r.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            for p in data or []:
                cmd = (p.get("CommandLine") or "")
                if any(m in cmd for m in MAG_CMD_MARKERS) and "platform_kill" not in cmd:
                    out.append({"pid": p.get("ProcessId"), "cmd": cmd[:200]})
        except Exception:
            pass
    return out


def kill_all(*, dry: bool = False) -> dict[str, Any]:
    """Kill every Mag platform process + container in one pass. Deterministic, idempotent."""
    import subprocess
    import os

    host = _enum_host_pids()
    killed_host: list[dict[str, Any]] = []
    errors: list[str] = []
    for p in host:
        pid = p["pid"]
        if dry:
            killed_host.append({"pid": pid, "cmd": p["cmd"], "dry": True})
            continue
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
            else:
                import signal
                os.kill(pid, signal.SIGKILL)
            killed_host.append({"pid": pid, "cmd": p["cmd"], "dry": False})
        except Exception as e:
            errors.append(f"pid {pid}: {str(e)[:100]}")

    # Containerized stack
    container = {"stopped": False, "dry": dry, "error": None}
    if not dry:
        try:
            from mag.docker_ops import down
            d = down()
            container["stopped"] = bool(d.get("ok"))
            container["detail"] = d.get("err") or d.get("out", "")[:120]
        except Exception as e:
            container["error"] = str(e)[:120]
    else:
        try:
            from mag.docker_ops import status as dstatus
            container["would_stop"] = bool(dstatus().get("containers"))
        except Exception:
            pass

    # Reset supervisor state so nothing auto-restarts after
    supervisor = {"reset": False}
    if not dry:
        try:
            from mag.process_supervisor import stop_all
            supervisor["stop_all"] = stop_all()
            supervisor["reset"] = True
        except Exception as e:
            supervisor["error"] = str(e)[:120]

    return {
        "schema": SCHEMA, "ts": _now(), "ok": not errors, "dry": dry,
        "host_killed": killed_host, "host_killed_count": len(killed_host),
        "container": container, "supervisor": supervisor, "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry" in argv
    print(json.dumps(kill_all(dry=dry), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
