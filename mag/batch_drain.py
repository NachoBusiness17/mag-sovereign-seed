"""batch_drain — launch BIG fuel-feed drains DETACHED so they come back on their own (2026-08-24).

The lesson (operator, 2026-08-24): a big batch launched through a terminal DIES when the terminal
gets reused/cleaned (proven: the 32-batch never landed — ledger shows only 1/8/8/16, fuel went UP
not down). Big batches must be launched DETACHED: no window, no terminal, no parent process to
kill them. They run, write their result to disk, and "come back on their own."

This module is the canonical detached launcher for fuel_feed.run(batch=N):

  launch(batch, *, poll_s, timeout_s) -> spawns a DETACHED python process that runs
      fuel_feed.run(batch=N) and writes the FULL result (lane spread, gates, errors,
      per-signal detail) to memory/runs/fuel_feed/detached/<ts>.json when done.
      Returns immediately with the pid + result path. The process survives terminal cleanup.

  status() -> which detached drains are running / done / failed (reads the result files).

  collect() -> the results of every completed detached drain (for the k3s scribe to analyze).

CLI: python -m mag.batch_drain launch 32 | status | collect
Schema: batch_drain.v1 · deterministic launcher (the drain itself is the paid work)
"""
from __future__ import annotations

import argparse
import json
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

SCHEMA = "batch_drain.v1"
RUNS = ROOT / "memory" / "runs" / "fuel_feed" / "detached"

# The DETACHED CHILD — written to a real .py file, not -c inline (shell-quoting proof).
# Runs fuel_feed.run(batch=N), writes the FULL result (lane spread, gates, errors, per-signal
# detail) to the result_path. The process is detached: no terminal can kill it.
_CHILD_TEMPLATE = (
    "import json, sys, traceback\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, r'%s')\n"
    "try:\n"
    "    from mag import fuel_feed as f\n"
    "    r = f.run(batch=%d)\n"
    "    payload = {k: r.get(k) for k in ('ok', 'action', 'fired', 'detail')}\n"
    "    payload['results'] = r.get('results') or []\n"
    "    payload['status'] = 'done'\n"
    "    import datetime as _dt\n"
    "    payload['finished_at'] = _dt.datetime.now(_dt.timezone.utc).isoformat().replace('+00:00', 'Z')\n"
    "except Exception as e:\n"
    "    payload = {'ok': False, 'status': 'failed', 'error': str(e)[:500],\n"
    "               'traceback': traceback.format_exc()[-2000:]}\n"
    "try:\n"
    "    Path(r'%s').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')\n"
    "except Exception:\n"
    "    pass\n"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_python() -> str:
    """The canonical interpreter — same resolution as headless._resolve_python."""
    try:
        from mag import headless
        return headless._resolve_python()
    except Exception:  # noqa: BLE001
        return sys.executable


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def launch(batch: int, *, poll_s: float = 8.0) -> dict[str, Any]:
    """Launch a DETACHED drain of `batch` signals. Returns immediately; the process survives
    terminal cleanup and writes its result file when done. THE operator's fix for big batches."""
    import subprocess

    from mag import headless
    batch = max(1, int(batch))
    RUNS.mkdir(parents=True, exist_ok=True)
    ts = _now().replace(":", "-").replace(".", "-")
    result_path = RUNS / f"drain-{batch}-{ts}.json"
    # mark it RUNNING now (so status() sees it even before the process writes)
    _write_result(result_path, {"schema": SCHEMA, "batch": batch, "status": "running",
                                "launched_at": _now(), "pid": None, "result_path": str(result_path)})

    # Write the child to a temp .py FILE (not -c inline): -c with nested quotes is fragile
    # across shells and got mangled by PowerShell quoting. A real file is unambiguous.
    child = RUNS / "_child_drain.py"
    child.write_text(
        _CHILD_TEMPLATE % (str(ROOT), batch, str(result_path)),
        encoding="utf-8")

    # DETACHED + CREATE_NO_WINDOW (the headless lesson): no window, no terminal, survives cleanup
    env = headless._spawn_env()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [_resolve_python(), str(child)],
        creationflags=headless.no_window_flags(detached=True),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    # update the running marker with the real pid
    marker = json.loads(result_path.read_text(encoding="utf-8"))
    marker["pid"] = proc.pid
    _write_result(result_path, marker)
    return {"ok": True, "schema": SCHEMA, "batch": batch, "pid": proc.pid,
            "status": "running", "launched_at": marker["launched_at"],
            "result_path": str(result_path.relative_to(ROOT)).replace("\\", "/"),
            "note": "detached drain launched — it survives terminal cleanup and writes its "
                    "result when done; collect() reads it"}


def status() -> dict[str, Any]:
    """Which detached drains are running / done / failed."""
    RUNS.mkdir(parents=True, exist_ok=True)
    running, done, failed = [], [], []
    for p in sorted(RUNS.glob("drain-*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        row = {"batch": d.get("batch"), "pid": d.get("pid"),
               "launched_at": d.get("launched_at"), "path": p.name}
        st = d.get("status")
        if st == "running":
            # check if the pid is actually still alive. NEVER os.kill(pid, 0) here:
            # on Windows sig 0 means TerminateProcess (documented in orchestrator.py
            # 2026-08-03) — it KILLS the process it was meant to probe. This exact bug
            # killed every detached drain I checked with status() (2026-08-24).
            alive = False
            pid = d.get("pid")
            if pid:
                alive = _pid_alive(int(pid))
            if alive:
                running.append(row)
            else:
                # pid gone and no result written -> it died silently
                if not (d.get("finished_at") or d.get("error")):
                    row["died"] = True
                    failed.append(row)
                else:
                    row["status"] = st
                    done.append(row)
        elif st == "done":
            done.append(row)
        else:
            failed.append(row)
    return {"ok": True, "schema": SCHEMA, "n_running": len(running), "n_done": len(done),
            "n_failed": len(failed), "running": running, "done": done, "failed": failed,
            "note": "detached drains — running survive terminals, done wrote their result"}


def _pid_alive(pid: int) -> bool:
    """Safe liveness — NEVER os.kill(pid, 0) on Windows (that's TerminateProcess). Uses psutil
    when available (orchestrator's proven path), else tasklist (authoritative on Windows)."""
    if not pid or pid <= 0:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:  # noqa: BLE001
        pass
    if sys.platform == "win32":
        try:
            import subprocess
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                               capture_output=True, text=True, timeout=15)
            return str(pid) in (r.stdout or "")
        except Exception:  # noqa: BLE001
            pass
        return False
    try:
        import os
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def collect() -> dict[str, Any]:
    """The results of every completed detached drain — what the k3s scribe analyzes."""
    RUNS.mkdir(parents=True, exist_ok=True)
    results = []
    for p in sorted(RUNS.glob("drain-*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("status") == "done":
            results.append(d)
    return {"ok": True, "schema": SCHEMA, "n_done": len(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.batch_drain")
    ap.add_argument("cmd", choices=["launch", "status", "collect"])
    ap.add_argument("batch", nargs="?", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "launch":
        if not a.batch:
            print("batch required: python -m mag.batch_drain launch 32", file=sys.stderr)
            return 1
        print(json.dumps(launch(a.batch), indent=2, ensure_ascii=False))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(collect(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
