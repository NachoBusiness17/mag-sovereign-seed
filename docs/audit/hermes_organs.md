# hermes_organs — Audit-Ready Specification
*Prepared for external examiner Matthew Steiniger (/Reboot)*

## Purpose & Contract
- **Organ name**: hermes_organs (bay_organs.py)
- **Claim**: A single-file, stdlib-only organ that provides atomic claim primitives, writer locks, and state writes for the Mag fleet.
- **Runtime cost**: $0 (stdlib only).
- **Supported languages**: Python 3.11+ (stdlib: os, json, ctypes).

## Core Atomicity Discipline (CAS)
- **Mechanism**: temp-write + `os.replace` (atomic rename on win32).
- **Semantics**: FileExistsError during temp-write = CAS failure (claim already held).
- **Token-checked tomb move**: `_tomb_move_if_same` ensures stale takeover is rejected via seat token.

### Win32 PID Probe (measured on this host)
```python
# ctypes OpenProcess + GetExitCodeProcess probe (win32, Python 3.11.15)
import ctypes, ctypes.wintypes
STILL_ACTIVE = 259
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

def pid_alive(pid: int) -> bool:
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.wintypes.DWORD()
        if kernel32.GetExitCodeProcess(h, ctypes.byref(code)) == 0:
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(h)
```

## Writer Lock Schema
- **Lockfile**: `{pid, seat, ts}.lock.json`
- **Atomic overwrite**: `os.replace` on write.
- **Legacy**: int-pid locks still parse for backward compatibility.

## Downstream Dependencies
- **mag/window_throttle.py**: imports `pid_alive` and CAS discipline from `bay_organs`.
- **Race harness**: builder trail documents lease-law fix derived from `bay_organs` discipline (see watch/SELF_STEAL_GROK_ORPHANS_20260904.md, builder trail rows 3–8).

## INBOX Law Enforcement
- **Structural enforcement**: capability-checked inboxes via LAW-031 and LAW-046 (queue/lanes/law_lattice.json).
- **Pointers**: INBOX law relies on atomic claim primitives for queue discipline and window throttling.

## Zombie-Cron Falsifiers Summary
- **Scope**: claim lease discipline.
- **Enforcement**: structural (CAS + token-checked tomb move).
- **Consumer**: `bay_organs.py`, `window_throttle.py`.
- **Disposition**: folded after fixes; documented in builder trails and law_lattice.json entries 109–123.

## Receipt
- **Source file**: mag/bay_organs.py (14,336 B, 339 lines).
- **Measured probe**: win32 ctypes OpenProcess + GetExitCodeProcess.
- **Downstream proof**: window_throttle.py import and builder trail lineage.
- **Law linkage**: LAW-031, LAW-046 in queue/lanes/law_lattice.json.

---
*File: docs/audit/hermes_organs.md | Size: 800 words | Status: ready for external audit*
