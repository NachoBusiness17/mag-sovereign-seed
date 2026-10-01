"""win_powershell - absolute powershell.exe resolution (B2-375, 2026-09-26).

Disease (watch/inbox/burn_wave_20260926/QUEUE.md B2-375): mag/lifecycle.py:187
passes the literal "powershell.exe" in a list to the CmdRunner and
mag/health.py:24 (CAGE_DOCTOR) plus mag/window_audit.py:44 carry
whole-command string forms. A PATH-scrubbed launch context that hides the
WindowsPowerShell directory fails all three with the same [Errno 2] disease,
because subprocess PATH lookup never finds powershell via System32 (the
binary lives in System32\\WindowsPowerShell\\v1.0\\, a directory the estate's
hardened launch contexts do not carry on PATH).

Law: every spawn of powershell resolves the binary to an absolute path at
call time. shutil.which is honored first (custom installs), then the two
known System32 locations (Sysnative covers 32-bit interpreter on 64-bit OS).
Fail-closed: if nothing resolves, FileNotFoundError names the cause instead
of an opaque [Errno 2] from deep inside subprocess.
"""
from __future__ import annotations

import os
import shutil
from functools import lru_cache

_CANDIDATES = (
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe",
)


@lru_cache(maxsize=1)
def powershell_exe() -> str:
    """Absolute path to powershell.exe; FileNotFoundError if unresolvable."""
    for name in ("powershell", "powershell.exe"):
        found = shutil.which(name)
        if found:
            return found
    for cand in _CANDIDATES:
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError(
        "powershell.exe not resolvable: PATH carries no WindowsPowerShell "
        "directory and the System32 candidates are absent (B2-375)"
    )
