"""Failsafe: watch Mag integral; catch-up when it returns; optional restart.

  python main.py guard          # loop: doctor + catch-up if needed
  python main.py guard --once
"""
from __future__ import annotations

import os
import subprocess
import sys
from mag import headless
import time
from pathlib import Path
from typing import Any

from config import ROOT
from mag.health import catch_up, in_mag_cage, sanity
from mag.runtime import write_heartbeat


def doctor_print(s: dict[str, Any]) -> None:
    print(f"status={s.get('status')} live_stale={s.get('recording', {}).get('live_stale')}")
    miss = s.get("missing_while_down") or []
    if miss:
        print("missing:", "; ".join(miss))
    lanes = s.get("lanes") or {}
    for k, v in lanes.items():
        print(f"  {k}: ok={v.get('ok')} {v.get('note') or v.get('error') or ''}")


def ensure_lab(restart: bool = False) -> dict[str, Any]:
    try:
        from mag.power import is_off

        if is_off():
            return {
                "ok": True,
                "action": "power_off",
                "hint": "Stack intentionally off — mag.cmd power start",
                "sanity": sanity(),
            }
    except Exception:
        pass
    s = sanity()
    if s.get("status") == "up" and not s.get("recording", {}).get("live_stale"):
        return {"ok": True, "action": "healthy", "sanity": s}
    if s.get("status") == "up" and s.get("recording", {}).get("live_stale"):
        cu = catch_up()
        return {"ok": cu.get("ok"), "action": "catch_up", "catch_up": cu, "sanity": sanity()}
    if restart:
        if in_mag_cage() or os.environ.get("MAG_CONTAINER") == "1":
            return {
                "ok": False,
                "action": "refuse_host_lab",
                "hint": (
                    "Already in mag-sovereign. Do not spawn host python main.py lab. "
                    "From the host: docker compose restart mag"
                ),
                "sanity": s,
            }
        # spawn lab detached — last resort on disposable-dev soil only
        py = headless.PYTHON
        creation = 0
        if sys.platform == "win32":
            creation = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                        | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))  # type: ignore[attr-defined]
        log = ROOT / "logs" / "lab_guard.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as lf:
            subprocess.Popen(
                [py, str(ROOT / "main.py"), "lab", "--no-dashboard"],
                cwd=str(ROOT),
                stdout=lf,
                stderr=lf,
                creationflags=creation if sys.platform == "win32" else 0,
                start_new_session=(sys.platform != "win32"),
            )
        time.sleep(3)
        cu = catch_up()
        return {"ok": True, "action": "restarted_lab", "catch_up": cu, "sanity": sanity()}
    return {
        "ok": False,
        "action": "need_lab",
        "hint": (
            r"scripts\mag_exec.ps1 doctor; docker compose restart mag. "
            "Host python main.py lab is last resort (second supervisor if cage is up)."
        ),
        "sanity": s,
    }


def guard_loop(interval: float = 30.0, *, once: bool = False, restart: bool = False) -> None:
    print(f"Mag guard (interval={interval}s). Failsafe for integral process.")
    while True:
        res = ensure_lab(restart=restart)
        print(f"--- guard {time.strftime('%H:%M:%S')} action={res.get('action')} ---")
        doctor_print(res.get("sanity") or sanity())
        try:
            write_heartbeat(guard="ok", guard_action=res.get("action"))
        except Exception:
            pass
        if once:
            break
        time.sleep(interval)
