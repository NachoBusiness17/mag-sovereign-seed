"""Single integral Mag runtime: watch + companion + heartbeat (one process).

Killing this process freezes eyes + clerk until restarted. No multi-process maze.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

HEARTBEAT = ROOT / "watch" / "heartbeat.json"
PID_FILE = ROOT / "watch" / "mag.pid"


def write_heartbeat(**parts: Any) -> None:
    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {}
    if HEARTBEAT.is_file():
        try:
            prev = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prev = {}
    payload = {
        **prev,
        **parts,
        "ts": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
    }
    HEARTBEAT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def read_heartbeat() -> dict[str, Any]:
    if not HEARTBEAT.is_file():
        return {"ok": False, "alive": False, "reason": "no heartbeat — Mag not running"}
    try:
        data = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"ok": False, "alive": False, "reason": str(e)}
    age = None
    ts = data.get("ts")
    if ts:
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - t).total_seconds()
        except ValueError:
            age = None
    alive = age is not None and age < 90  # stale if no beat in 90s
    note = "Integral process is up."
    if not alive:
        from mag.health import reconnect_plan

        note = str(reconnect_plan().get("stale_note") or "")
    return {
        "ok": True,
        "alive": alive,
        "age_seconds": age,
        **data,
        "note": note,
    }


def start_watch_thread(interval: float = 5.0) -> threading.Thread:
    """Background Grok tail — baked into Mag, not a second CLI process."""
    stop = threading.Event()

    def _run() -> None:
        from watch.tail_session import once

        while not stop.is_set():
            try:
                once()
                write_heartbeat(watch="ok", watch_interval=interval)
            except Exception as e:
                write_heartbeat(watch="error", watch_error=str(e)[:300])
            stop.wait(interval)

    t = threading.Thread(target=_run, name="mag-watch-integral", daemon=True)
    t.stop_event = stop  # type: ignore[attr-defined]
    t.start()
    return t


def run_integral(
    *,
    mag_interval: float | None = None,
    watch_interval: float = 5.0,
    once: bool = False,
    with_dashboard: bool = False,
    host: str = "127.0.0.1",
    port: int = 8765,
    with_cast: bool = False,
    cast_lan: bool = False,
    cast_port: int = 8766,
) -> None:
    """One process: Mag run_loop (owns watch thread) + optional dashboard.

    Untangled: the dashboard thread starts FIRST, and the mag daemon chain is
    imported lazily + guarded. A daemon init failure (missing lib, HOME
    unresolvable, etc.) must degrade to a logged warning — never take the
    web server down with it.
    """
    # Console-safe prints even when invoked directly on a cp1252 console
    # (main.py does this too; a direct run_integral call must not die on \u2192).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    from mag.policy import load_policy

    pol = load_policy()
    sec = float(mag_interval if mag_interval is not None else pol.get("interval_seconds") or 120)
    w_sec = float(pol.get("watch_interval_seconds") or watch_interval)

    print("=== Mag integral runtime (one process) ===")
    print(f"  pid={os.getpid()}")
    print(f"  watch every {w_sec}s (baked into mag — no second process)")
    print(f"  mag cycle every {sec}s")
    print("  kill this → live board freezes; session amend resumes on restart")
    print("  session docs: amend same id (no duplicate dossiers)")
    write_heartbeat(status="starting", mag_interval=sec, watch_interval=w_sec)

    # Failsafe: always catch up eyes + living record on launch
    try:
        from mag.health import catch_up

        cu = catch_up()
        print(f"  catch-up: ok={cu.get('ok')} steps={len(cu.get('steps') or [])}")
        write_heartbeat(status="catch_up_done", catch_up_ok=cu.get("ok"))
    except Exception as e:
        print(f"  catch-up failed: {e}")

    if with_dashboard:
        def _dash() -> None:
            from dashboard.server import run as run_dashboard

            run_dashboard(host=host, port=port)

        threading.Thread(target=_dash, name="mag-dashboard", daemon=True).start()
        from config import print_bind_banner

        print_bind_banner(host=host, port=port)

    if with_cast:
        from config import resolve_bind_host

        cast_host = resolve_bind_host(
            lan=cast_lan,
            port=cast_port,
            service="cast",
        )

        def _cast() -> None:
            from mag.cast_server import run as run_cast

            run_cast(host=cast_host, port=cast_port)

        threading.Thread(target=_cast, name="mag-cast", daemon=True).start()
        from config import print_bind_banner

        print_bind_banner(host=cast_host, port=cast_port, service="cast")

    # Daemon chain imported AFTER the dashboard thread is up, and guarded:
    # a missing lib / broken import here logs a warning and keeps the server
    # alive instead of taking the whole process down.
    try:
        from mag.daemon import run_cycle, run_loop
    except Exception as e:  # noqa: BLE001
        print(f"  [daemon] init failed ({type(e).__name__}: {e}) — dashboard keeps running")
        write_heartbeat(status="daemon_failed", daemon_error=str(e)[:300])
        return

    try:
        if once:
            # one-shot: ensure a single watch refresh then cycle
            try:
                from watch.tail_session import once as watch_once

                watch_once()
            except Exception:
                pass
            out = run_cycle()
            write_heartbeat(status="once_done", last_action=(out.get("decision") or {}).get("action"))
            print(out)
        else:
            # run_loop starts the integral watch thread once
            run_loop(interval=sec, once=False)
    except KeyboardInterrupt:
        print("\nMag integral stopped.")
    finally:
        write_heartbeat(status="stopped")
        if PID_FILE.is_file():
            try:
                PID_FILE.unlink()
            except OSError:
                pass
