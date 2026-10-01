"""Single process supervisor — one thing runs the whole framework (P1+P2).

Collapses the long-lived loops (governor/autorun, ghost, ...) that used to run
as separate terminals into ONE supervisor that owns them as managed subprocesses:
start / stop / restart / reap via REST or CLI. The dashboard + Control Room stay
the single surface; the operator stops opening N python tabs.

Loops are blocking `while True` (drain_loop, autorun_loop), so they are supervised
as subprocesses (the pattern conductor/agentswarm use) rather than threads — a
subprocess can be reliably killed/restarted; a blocking thread cannot be.

Registry (extensible): each loop = {cmd, default, desc}. `default` loops start on
`up`. ghost is registered but opt-in (not auto-started) to avoid surprise behavior.
Only ONE autorun loop should run system-wide (it already does fill+drain+governor
+cadence) — don't also run a standalone drainer alongside it.

NOTE: this is the PROCESS supervisor. The slow-thinking governor lives in
`mag/supervisor.py` (separate concern) — do not confuse the two.

CLI:   python -m mag.process_supervisor up|down|status|start <name>|stop <name>|restart <name>
REST:  GET /api/v1/supervisor            (status)
       POST /api/v1/supervisor {action: start|stop|restart, name}
       POST /api/v1/supervisor {action: up|down}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mag import runtime_policy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_PATH = ROOT / "memory" / "supervisor" / "state.json"
LOG_PATH = ROOT / "logs" / "supervisor.jsonl"

# Resolve the project's REAL interpreter (bypass the venv shim). LAW (2026-08-10): the
# shim re-execs into a uv child that OPENS A CONSOLE WINDOW on every spawn — and this
# supervisor crash-restarts loops, so a crash-loop = a window storm. Use the real
# interpreter + _spawn_env so packages resolve in a single PID with no window.
try:
    from mag.headless import _resolve_python as _hp, _spawn_env
    PYTHON = _hp()
except Exception:
    _PY = ROOT / ".venv" / "Scripts" / "python.exe"
    PYTHON = str(_PY) if _PY.is_file() else sys.executable

_GHOST_SRC = (
    "import time\n"
    "from mag.ghost import cycle\n"
    "while True:\n"
    "    try: cycle()\n"
    "    except Exception: pass\n"
    "    time.sleep(120)\n"
)

LOOP_DEFS: dict[str, dict[str, Any]] = {
    "autorun": {
        "cmd": ["-c", "from mag.governor_autorun import autorun_loop; autorun_loop(5.0)"],
        "default": True,
        "desc": "governor/autorun: fill + drain + governor + cadence (the consolidated loop)",
        "health_url": "http://127.0.0.1:8765/api/v1/health",
    },
    "ghost": {
        "cmd": ["-c", _GHOST_SRC],
        "default": False,
        "desc": "ghost auto-deploy cadence (opt-in)",
    },
    "ghost-daemon": {
        "cmd": ["-m", "mag.ghost", "--daemon", "--port", "9000"],
        "default": False,
        "desc": "Ghost daemon (FastAPI :9000). DEFAULT OFF on the host since 2026-09-19: "
                "state/DOCKER_ONLY reserves ghost runtime for the container supervisor and "
                "ghost.py blocks host starts anyway, so default True was an eternal "
                "crash-loop (spawn -> blocked -> exit -> respawn). The container runs it.",
        "health_url": "http://127.0.0.1:9000/api/v1/health",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mag_launch_active() -> bool:
    """True when mag_launch.py is the live controller (its supervisor is up and healthy).

    mag_launch owns every slot (backend/dashboard/lab/mirror/drainer) and spawns the governor
    as `main.py autorun` — the CANONICAL carrier of the AOS bus. If mag_launch is up, it is the
    ONE controller for the autorun loop; process_supervisor must NOT also reap/restart its own
    `autorun_loop(5.0)` or we get DOUBLE-SUPERVISION (L8, 2026-08-10 / 2026-08-23): two
    supervisors both respawn the governor carrier -> duplicate `autorun_loop` processes fight
    the shared bus state -> 3-4 answers generated, none sent. Detected via mag_launch's state
    file (its supervisor_pid alive) or its health ports.
    """
    try:
        state = ROOT / "state" / "mag_launch.json"
        if state.is_file():
            import json as _json
            data = _json.loads(state.read_text(encoding="utf-8")) or {}
            sup = int(data.get("supervisor_pid") or 0)
            if sup and _pid_alive(sup):
                return True
    except Exception:
        pass
    # fallback: mag_launch serves the dashboard/backend health ports
    try:
        if _health_ok("http://127.0.0.1:8765/") and _health_ok("http://127.0.0.1:8000/health"):
            return True
    except Exception:
        pass
    return False


def _container_mode() -> bool:
    """Under MAG_CONTAINER=1, mag_launch.py + Docker restart policy are the ONE controller.

    The container supervisor (mag_launch) already spawns/owns every slot, and Docker's
    `restart: unless-stopped` reconciles the container. If process_supervisor ALSO reaps/
    auto-restarts loops here, we get DOUBLE-SUPERVISION (L8, 2026-08-10): many modules call
    status() -> reap() -> auto-restart of the default 'autorun' loop, so `autorun_loop(5.0)`
    accumulates and the dashboard starves (~82% CPU). Gate ALL spawn/respawn off under the
    container; process_supervisor becomes a passive observer only.
    """
    return os.environ.get("MAG_CONTAINER", "").strip().lower() in ("1", "true", "yes") \
        or _mag_launch_active()


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(data: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _log(event: str, **meta: Any) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **meta}
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _health_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        from mag.orchestrator import _pid_alive as _alive

        return bool(_alive(pid))
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False


def _kill_tree(pid: int) -> None:
    try:
        from mag.orchestrator import _kill_tree as _kt

        _kt(pid)
        return
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0,
        )
    except Exception:
        pass


def _spawn(name: str) -> dict[str, Any] | None:
    cfg = LOOP_DEFS.get(name)
    if not cfg:
        return None
    creationflags = 0
    if os.name == "nt":
        # CREATE_NO_WINDOW is REQUIRED for headless spawns — DETACHED_PROCESS alone
        # still opens a console window on the desktop (the window-storm source).
        # Same pattern as orchestrator / seat_guard / power / tts.
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_f = open(ROOT / "logs" / f"supervisor_{name}.out.log", "a", encoding="utf-8")
    try:
        from mag.headless import _spawn_env as _se
        env = _se()
        env.setdefault("MAG_SLOT", name)
        env.setdefault("MAG_SOURCE", "process_supervisor")
        proc = subprocess.Popen(
            [PYTHON] + list(cfg["cmd"]),
            cwd=str(ROOT),
            stdout=out_f,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            close_fds=True,
            env=env,
        )
    except Exception as e:
        out_f.close()
        _log("spawn_failed", name=name, error=str(e)[:200])
        return None
    _log("started", name=name, pid=proc.pid)
    return {"pid": proc.pid, "started_at": _now(), "cmd": " ".join(cfg["cmd"])}


def start_loop(name: str) -> dict[str, Any]:
    if _container_mode():
        # Container: mag_launch owns the loops. Never spawn here (double-supervision, L8).
        return {"ok": True, "name": name, "container_controller": True,
                "detail": "mag_launch.py + Docker own loop lifecycle under MAG_CONTAINER=1"}
    if name not in LOOP_DEFS:
        return {"ok": False, "error": f"unknown loop: {name}", "known": sorted(LOOP_DEFS)}
    state = _load_state()
    cur = state.get(name)
    if cur and _pid_alive(cur.get("pid")):
        return {"ok": True, "name": name, "already_running": True, "pid": cur["pid"]}
    spawned = _spawn(name)
    if not spawned:
        return {"ok": False, "name": name, "error": "spawn failed"}
    state[name] = {"status": "running", "started_at_ts": time.time(), "crash_times": [], **spawned}
    _save_state(state)
    return {"ok": True, "name": name, "pid": spawned["pid"], "started": True}


def stop_loop(name: str) -> dict[str, Any]:
    if name not in LOOP_DEFS:
        return {"ok": False, "error": f"unknown loop: {name}", "known": sorted(LOOP_DEFS)}
    state = _load_state()
    cur = state.get(name)
    if not cur:
        return {"ok": True, "name": name, "already_stopped": True}
    if cur.get("pid"):
        _kill_tree(cur["pid"])
    state.pop(name, None)
    _save_state(state)
    _log("stopped", name=name, pid=cur.get("pid"))
    return {"ok": True, "name": name, "stopped": True}


def restart_loop(name: str) -> dict[str, Any]:
    stop_loop(name)
    return start_loop(name)


# crashLoopBackOff (K8s-style) restart policy for supervised default loops.
BACKOFF_BASE_S = 2.0      # first backoff after a crash
BACKOFF_MAX_S = 300.0     # hard cap on any single backoff
BACKOFF_WINDOW_S = 60.0   # crashes within this window count toward the backoff
SUCCESS_WINDOW_S = 120.0  # a loop up this long resets its crash counter


def _backoff_seconds(crash_times: list[float], now: float) -> float:
    """Exponential backoff by recent-crash count (K8s crashLoopBackOff), capped. 0 => restart now."""
    recent = [t for t in crash_times if now - t <= BACKOFF_WINDOW_S]
    if not recent:
        return 0.0
    return min(BACKOFF_BASE_S * (2 ** (len(recent) - 1)), BACKOFF_MAX_S)


# Re-exported for tests and callers; the policy itself lives in mag.runtime_policy
# (B2-51 2026-09-26: was a private copy here that drifted from the child copies).
DOCKER_ONLY_MARKER = runtime_policy.DOCKER_ONLY_MARKER


def _policy_blocked(name: str) -> bool:
    """True when policy forbids this host from running this loop at all.

    Drainer-scoped: only loops whose cmd carries governor_autorun. Whether the
    host is blocked at all is decided by mag.runtime_policy.host_runtime_blocked,
    the SAME predicate the drainer child evaluates at startup, so the gate and
    the child can never disagree again.

    Receipt (B2-51 autopsy, 2026-09-26; corrects the 2026-09-19 comment, whose
    "5,708 'blocked' lines" was the last line number of the blocked streak
    misread as a count and whose "marked 'crashed' for 20 days" claim is
    unsupported on disk): the Docker-only marker existed continuously
    2026-08-30 22:56 -0400 until its 2026-09-22 rename to
    state/DOCKER_ONLY.stale-20260922; the child self-block landed 2026-09-14
    (d575bc168); from then on a host respawn printed "[autorun] blocked:
    Docker-only runtime is active" and exited at startup, and this supervisor
    classified that policy exit as a crash: 28 auto_restarts on 09-19
    (15:06-17:31Z, final four 17:30:39/46 and 17:31:02/17Z), 44 on 09-16,
    9 on 09-14; logs/supervisor_autorun.out.log holds 232 consecutive blocked
    lines (5477-5708). Blocked-by-policy is a state, not a crash; the gate
    lifts when the marker is removed or MAG_ALLOW_HOST_RUNTIME=1.
    """
    cfg = LOOP_DEFS.get(name) or {}
    if not any("governor_autorun" in str(part) for part in cfg.get("cmd", [])):
        return False
    return runtime_policy.host_runtime_blocked(marker=DOCKER_ONLY_MARKER)


def reap(auto_restart: bool = True) -> dict[str, Any]:
    """Mark dead loops (crashed); auto-restart default loops with crashLoopBackOff.

    `auto_restart=True` (default) brings a crashed DEFAULT loop back so the
    framework "just works" — process transfer is transparent, nobody babysits
    terminals. Non-default (opt-in) loops are NOT auto-restarted.

    A default loop that dies is auto-restarted, throttled by exponential backoff
    (K8s crashLoopBackOff): the more it has crashed recently, the longer we wait
    before the next attempt — so an instantly-dying loop backs off instead of
    respawning every instant. That infinite instant respawn was the 2026-08-09
    desktop window storm. It never stops retrying (self-healing preserved), and
    a loop that stays up for SUCCESS_WINDOW_S resets its crash counter, so a
    transient blip never accrues into a long backoff.

    A loop this host may not run at all (the Docker-only drainer behind
    state/DOCKER_ONLY) is marked blocked_by_policy instead of crashed and is not
    respawned here; the container supervisor owns it (B2-51 autopsy, 2026-09-26).
    """
    if _container_mode():
        # L8: under the container, mag_launch + Docker are the single controller. Be a
        # PASSIVE OBSERVER — never mark-and-restart loops (that re-spawned autorun_loop
        # and starved the dashboard). State is advisory only here.
        return {"ok": True, "container_controller": True,
                "detail": "mag_launch.py + Docker own loop lifecycle under MAG_CONTAINER=1",
                "crashed": [], "auto_restarted": []}
    state = _load_state()
    now = time.time()
    changed: list[str] = []
    restarted: list[str] = []
    for name, cur in list(state.items()):
        status = cur.get("status")
        if status == "running":
            if _pid_alive(cur.get("pid")):
                # healthy: once it has been up long enough, forget past crashes
                started = cur.get("started_at_ts") or 0
                if cur.get("crash_times") and (now - started) >= SUCCESS_WINDOW_S:
                    cur["crash_times"] = []
                    state[name] = cur
                continue
            # the loop died -> crashed
            cur["status"] = "crashed"
            cur["crashed_at"] = _now()
            crashes = [t for t in cur.get("crash_times", []) if now - t <= BACKOFF_WINDOW_S]
            crashes.append(now)
            cur["crash_times"] = crashes
            changed.append(name)
            if auto_restart and LOOP_DEFS.get(name, {}).get("default"):
                if _policy_blocked(name):
                    cur["status"] = "blocked_by_policy"
                    cur.pop("next_retry_at", None)
                    _log("policy_blocked", name=name)
                    state[name] = cur
                    continue
                wait = _backoff_seconds(crashes, now)
                cur["next_retry_at"] = now + wait
                if wait >= BACKOFF_MAX_S:
                    _log("crash_backoff", name=name, wait_s=round(wait), crashes=len(crashes))
                    try:
                        from mag import failure_kb
                        failure_kb.log_failure(
                            kind="crash_loop", tool="process_supervisor",
                            detail=f"loop '{name}' crash-looping; crashLoopBackOff {wait:.0f}s",
                            phase="supervisor")
                    except Exception:
                        pass
                state[name] = cur
            else:
                state[name] = cur
        elif (status == "crashed"
              and auto_restart
              and LOOP_DEFS.get(name, {}).get("default")
              and cur.get("next_retry_at")
              and now >= cur["next_retry_at"]):
            # backoff expired -> restart (unless policy forbids this host)
            if _policy_blocked(name):
                cur["status"] = "blocked_by_policy"
                cur.pop("next_retry_at", None)
                _log("policy_blocked", name=name)
                changed.append(name)
                state[name] = cur
                continue
            spawned = _spawn(name)
            if spawned:
                state[name] = {"status": "running", "started_at_ts": now,
                               "crash_times": cur.get("crash_times", []), **spawned}
                restarted.append(name)
                _log("auto_restarted", name=name, pid=spawned["pid"])
            else:
                _log("auto_restart_failed", name=name)
        elif (status == "blocked_by_policy"
              and auto_restart
              and LOOP_DEFS.get(name, {}).get("default")
              and not _policy_blocked(name)):
            # policy gate lifted (marker removed / MAG_ALLOW_HOST_RUNTIME=1) ->
            # the loop is this host's to run again; resume self-healing
            spawned = _spawn(name)
            if spawned:
                state[name] = {"status": "running", "started_at_ts": now,
                               "crash_times": [], **spawned}
                restarted.append(name)
                _log("policy_resumed", name=name, pid=spawned["pid"])
            else:
                _log("policy_resume_failed", name=name)
    if changed or restarted:
        _save_state(state)
    return {"ok": True, "crashed": changed, "auto_restarted": restarted}


def status() -> dict[str, Any]:
    reap()
    state = _load_state()
    loops = []
    for name, cfg in LOOP_DEFS.items():
        cur = state.get(name)
        alive = bool(cur and _pid_alive(cur.get("pid")))
        loops.append({
            "name": name,
            "desc": cfg.get("desc", ""),
            "default": bool(cfg.get("default")),
            "running": alive,
            "pid": cur.get("pid") if cur else None,
            "status": "running" if alive else (cur.get("status", "stopped") if cur else "stopped"),
            "started_at": cur.get("started_at") if cur else None,
        })
    return {
        "ok": True,
        "schema": "supervisor.v1",
        "ts": _now(),
        "running": [l["name"] for l in loops if l["running"]],
        "loops": loops,
        "state_path": str(STATE_PATH),
        "python": PYTHON,
    }


def start_all() -> dict[str, Any]:
    out = {}
    for name, cfg in LOOP_DEFS.items():
        if cfg.get("default"):
            out[name] = start_loop(name)
    return {"ok": True, "started": out}


def stop_all() -> dict[str, Any]:
    out = {}
    for name in LOOP_DEFS:
        out[name] = stop_loop(name)
    return {"ok": True, "stopped": out}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    name = argv[1] if len(argv) > 1 else None
    if cmd == "up":
        print(json.dumps(start_all(), indent=2, ensure_ascii=False))
    elif cmd == "down":
        print(json.dumps(stop_all(), indent=2, ensure_ascii=False))
    elif cmd == "start" and name:
        print(json.dumps(start_loop(name), indent=2, ensure_ascii=False))
    elif cmd == "stop" and name:
        print(json.dumps(stop_loop(name), indent=2, ensure_ascii=False))
    elif cmd == "restart" and name:
        print(json.dumps(restart_loop(name), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
