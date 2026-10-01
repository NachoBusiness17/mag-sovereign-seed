"""top_processes — the bug-hunt STARTS here: top CPU/memory processes for ghost sense.

Operator (2026-08-11): "in the past we bug hunted and never went to the top processes with ghost
sense so we should start that way moving forward." Standing rule: when errors appear (lower-right
toasts), check TOP PROCESSES FIRST via ghost sense, then descend into files.

Adapted from the standard process-monitoring pattern (psutil top). Deterministic + graceful:
if psutil is missing, returns an honest error (no crash). Schema: top_processes.v1
"""
from __future__ import annotations

import time
from typing import Any

SCHEMA = "top_processes.v1"
_SNAPSHOT_CACHE: tuple[float, list[dict[str, Any]]] | None = None
_CACHE_TTL_S = 5.0


def _snapshot() -> list[dict[str, Any]]:
    """Take one bounded-enough host snapshot for both rankings.

    ``cmdline`` was included here for display only, but on Windows it can make
    psutil block on a protected or half-dead process.  Ghost is an observer;
    process census must not become the thing it is trying to diagnose.
    """
    global _SNAPSHOT_CACHE
    now = time.monotonic()
    if _SNAPSHOT_CACHE and now - _SNAPSHOT_CACHE[0] < _CACHE_TTL_S:
        return list(_SNAPSHOT_CACHE[1])
    # Do not request memory_info/cmdline here.  On Windows a protected process
    # can block those psutil accessors indefinitely.  CPU/name are enough for
    # the first diagnostic cut; the missing memory field is explicit rather
    # than a fabricated zero.
    try:
        import psutil
        rows: list[dict[str, Any]] = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                info = p.info
                rows.append({"pid": info.get("pid"), "name": info.get("name") or "?",
                             "cpu": round(info.get("cpu_percent") or 0.0, 2),
                             "mem": None, "cmd": ""})
            except Exception:
                continue
    except Exception:
        rows = []
    _SNAPSHOT_CACHE = (now, rows)
    return list(rows)


def top_cpu(n: int = 8) -> list[dict[str, Any]]:
    """Top N processes by CPU percent (the 'top' view). Deterministic snapshot."""
    rows = _snapshot()
    rows.sort(key=lambda r: -r["cpu"])
    return rows[:max(1, int(n))]


def top_memory(n: int = 8) -> list[dict[str, Any]]:
    """Top N processes by memory percent."""
    rows = _snapshot()
    rows.sort(key=lambda r: -(r.get("mem") or 0.0))
    return rows[:max(1, int(n))]


def top_processes(n: int = 8) -> dict[str, Any]:
    """The bug-hunt entry surface: top CPU + top memory + host totals. Graceful if psutil missing."""
    try:
        import psutil  # noqa: F401
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"psutil required: {str(e)[:120]}"}
    cpu = top_cpu(n)
    mem = top_memory(n)
    return {"ok": True, "schema": SCHEMA, "n": len(cpu), "top_cpu": cpu, "top_memory": mem,
            "memory_available": any(r.get("mem") is not None for r in cpu),
            "note": "CPU/name snapshot only; per-process memory is withheld because protected Windows processes can block the observer"}


def main(argv: list[str] | None = None) -> int:
    import json, sys
    print(json.dumps(top_processes(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
