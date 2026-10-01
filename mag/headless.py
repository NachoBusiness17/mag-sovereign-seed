"""headless — shared Windows headless-spawn helper.

One source of truth for `creationflags` so NO console window ever pops from a
subprocess while a user is gaming. The codebase history proved `DETACHED_PROCESS`
alone is NOT enough (window-storm lesson) — `CREATE_NO_WINDOW` is REQUIRED.

  no_window_flags(detached=False) -> int  creationflags for a headless spawn.
  run_headless(args, **kw) -> CompletedProcess   subprocess.run with no window.
  popen_headless(args, **kw) -> Popen            subprocess.Popen with no window.

On non-Windows, returns 0 / behaves like plain subprocess (headless anyway).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Capture the TRUE original Popen/run AT MODULE IMPORT (before any wrapper can be installed),
# so install_no_window_defaults() always wraps the real class even if it is called twice or
# the ambient subprocess.Popen has already been replaced by something (idempotency + safety).
_REAL_Popen = subprocess.Popen
_REAL_run = subprocess.run


def no_window_flags(*, detached: bool = False) -> int:
    """creationflags that guarantee no console window on Windows (0 elsewhere)."""
    if os.name != "nt":
        return 0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if detached:
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    return flags


def _force_no_window(kw: dict) -> None:
    """OR CREATE_NO_WINDOW into ANY creationflags.

    `setdefault` was the bug: callers that pass explicit creationflags (e.g.
    CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS, without CREATE_NO_WINDOW) bypassed
    it, so headed consoles still popped. OR-ing guarantees no window ever, even when
    the caller already set flags. Non-Windows: leave flags alone (headless anyway).
    """
    if os.name == "nt":
        existing = kw.get("creationflags") or 0
        kw["creationflags"] = existing | no_window_flags()


def install_no_window_defaults() -> None:
    """DEFINITIVE FIX (frontier, 2026-08-10): on Windows, default EVERY subprocess
    spawn to CREATE_NO_WINDOW by monkey-patching subprocess.Popen/.run ONCE at process
    start. This covers every spawn site in the whole process tree (including indirect
    / library ones: shell, run_python, orchestrator, janitor->agent->tools) so no
    console window can EVER appear — with ONE mechanism and NO stateful tracking lists.
    `_force_no_window` ORs CREATE_NO_WINDOW into explicit flags too (setdefault was
    the leak). Idempotent. Call at the top of every entry point (main.py, mag.ghost daemon).
    """
    if os.name != "nt":
        return
    if getattr(subprocess, "_mag_nowin", False):
        return  # already installed — idempotent (called at the top of every entry point)

    # Popen wrapper MUST be a CLASS (subclass of the true original), NOT a function:
    # asyncio.windows_utils does `class Popen(subprocess.Popen)` — subclassing a plain
    # function raises `TypeError: function() argument 'code' must be code, not str`
    # and crashes any process that imports asyncio (ghost-daemon crash, 2026-08-11).
    # We wrap _REAL_Popen (captured at module import), never the ambient (already-wrapped)
    # subprocess.Popen, so this is safe to call more than once.
    class _Popen(_REAL_Popen):
        def __init__(self, *a, **k):
            _force_no_window(k)
            super().__init__(*a, **k)

    def _run(*a, **k):
        _force_no_window(k)
        return _REAL_run(*a, **k)

    subprocess.Popen = _Popen
    subprocess.run = _run
    subprocess._mag_nowin = True


def run_headless(args, **kw: Any) -> subprocess.CompletedProcess:
    """subprocess.run with CREATE_NO_WINDOW (plus NEW_PROCESS_GROUP).

    FIX (2026-08-16, escalated root-cause): the monkey-patched `subprocess.run(capture_output=True)`
    + CREATE_NO_WINDOW combo deadlocks on Windows pipe buffering — the child writes until the OS
    pipe buffer fills (~4-64KB), blocks on write(), while the parent blocks on communicate()'s
    stdout_thread.join(). Neither progresses -> the 360s hang (swarm local drain, all session).
    Self-steal: reuse popen_headless (Popen + CREATE_NO_WINDOW) + explicit pipes + communicate(timeout),
    and force PYTHONUNBUFFERED so the child drains incrementally instead of buffering a big block.
    Same guarantee (windowless), no pipe-buffer deadlock.
    """
    kw.setdefault("creationflags", no_window_flags())
    # force unbuffered so a chatty child drains incrementally (kills the pipe-buffer deadlock)
    env = dict(kw.pop("env", None) or _spawn_env())
    env.setdefault("PYTHONUNBUFFERED", "1")
    kw["env"] = env
    timeout = kw.pop("timeout", None)
    capture = kw.pop("capture_output", False)
    if capture:
        proc = popen_headless(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, text=kw.pop("text", False),
                              creationflags=kw.pop("creationflags", None) or no_window_flags(),
                              **kw)
        out, err = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)
    return subprocess.run(args, **kw)


def popen_headless(args, **kw: Any) -> subprocess.Popen:
    """subprocess.Popen with CREATE_NO_WINDOW (plus NEW_PROCESS_GROUP [+ DETACHED])."""
    kw.setdefault("creationflags", no_window_flags(detached=bool(kw.pop("detached", False))))
    kw.setdefault("env", _spawn_env())
    return subprocess.Popen(args, **kw)


# ---------------------------------------------------------------------------
# CANONICAL SPAWNER — ONE interpreter, headless, used by every framework spawn.
# Fixes the daemon-cascade bug: venv/uv doubling came from spawn sites resolving
# `sys.executable` (which becomes the uv python once running under uv). Every
# framework subprocess must run under this single resolved binary.
# ---------------------------------------------------------------------------
def _resolve_python() -> str:
    """THE canonical project interpreter — the REAL interpreter, NOT the venv shim.

    LAW (2026-08-10): the `.venv/Scripts/python.exe` shim re-execs into the base
    interpreter as a CHILD -> every spawn doubles to 2 PIDs and the host
    reap/seat-exit=-1 mismatches (the 3-day window-storm + crash-loop root).
    Resolve the real interpreter from `pyvenv.cfg 'home'` and spawn it DIRECTLY,
    with `PYTHONPATH` pointed at the venv site-packages (see `_spawn_env`), so
    every framework process is a SINGLE PID and packages still resolve.
    VERIFIED (2026-08-10): base python + PYTHONPATH imports mag/config/fastapi.
    """
    try:
        from config import ROOT
    except Exception:
        ROOT = Path(__file__).resolve().parent.parent
    cfg = ROOT / ".venv" / "pyvenv.cfg"
    try:
        home = None
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.lower().startswith("home"):
                home = s.split("=", 1)[1].strip()
                break
        if home:
            real = Path(home) / "python.exe"
            if real.is_file():
                return str(real)
    except Exception:
        pass
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.is_file() else sys.executable


def _spawn_env(base_env: dict | None = None) -> dict:
    """Spawn env for the REAL interpreter: PYTHONPATH = project root + venv
    site-packages, so bypassing the venv shim still resolves `mag`/`config`/deps.
    """
    try:
        from config import ROOT
    except Exception:
        ROOT = Path(__file__).resolve().parent.parent
    env = dict(base_env or os.environ)
    pp = [str(ROOT), str(ROOT / ".venv" / "Lib" / "site-packages")]
    old = env.get("PYTHONPATH")
    if old:
        pp.append(old)
    env["PYTHONPATH"] = os.pathsep.join(pp)
    return env


# The one interpreter every framework spawn should use (never sys.executable, never the shim).
PYTHON = _resolve_python()


def py_cmd(args: list[str]) -> list[str]:
    """Prefix a command with the canonical project python."""
    return [PYTHON, *args]


def run_py(args: list[str], **kw: Any) -> subprocess.CompletedProcess:
    """Headless subprocess.run under the canonical python."""
    return run_headless(py_cmd(args), **kw)


def popen_py(args: list[str], **kw: Any) -> subprocess.Popen:
    """Headless subprocess.Popen under the canonical python."""
    return popen_headless(py_cmd(args), **kw)


def _selfcheck() -> None:
    if os.name == "nt":
        assert no_window_flags() & getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    print("headless helper OK")


if __name__ == "__main__":
    _selfcheck()
