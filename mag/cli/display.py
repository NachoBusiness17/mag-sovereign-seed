"""Human-readable CLI display helpers for Mag commands.

Replaces raw JSON dumps with boxed, aligned, color-aware output.
Machine callers can still pass --json to get the raw dict.

Usage:
    from mag.cli.display import box, kv, table, badge, section, hr

    box("Doctor", [
        kv("status", "up"),
        kv("live_stale", False),
    ])
    table(["lane", "ok", "note"], [["watch", True, "ok"], ...])
"""
from __future__ import annotations

import os
import sys
from typing import Any, Iterable, Sequence

# ANSI colors — auto-disable when not a TTY or on Windows without VT support
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
if os.name == "nt" and _USE_COLOR:
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7
        )
    except Exception:
        _USE_COLOR = False


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


def badge(ok: bool, yes: str = "ok", no: str = "FAIL") -> str:
    return green(yes) if ok else red(no)


def hr(char: str = "-", width: int = 60) -> str:
    return char * width


def section(title: str, char: str = "=") -> str:
    return f"\n{cyan(bold(title))}\n{char * len(title)}"


def kv(key: str, value: Any, width: int = 22) -> str:
    """Aligned key: value row."""
    val = str(value)
    if isinstance(value, bool):
        val = green("yes") if value else red("no")
    return f"  {cyan(key.ljust(width))} {val}"


def box(title: str, lines: Iterable[str], width: int = 60) -> str:
    """Render a boxed section with a title bar."""
    lines = list(lines)
    inner = max([len(title) + 2] + [len(l) for l in lines] + [0])
    inner = min(inner, width)
    top = "┌" + "─" * (inner + 2) + "┐"
    mid = "│ " + bold(title).ljust(inner) + " │"
    bot = "└" + "─" * (inner + 2) + "┘"
    out = [top, mid]
    for l in lines:
        out.append("│ " + l.ljust(inner) + " │")
    out.append(bot)
    return "\n".join(out)


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Render an aligned table. Rows are sequences; cells str()'d."""
    rows = [list(r) for r in rows]
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))
    sep = "  ".join("─" * w for w in widths)
    out = ["  " + "  ".join(bold(h).ljust(w) for h, w in zip(headers, widths))]
    out.append("  " + sep)
    for r in rows:
        cells = []
        for i, cell in enumerate(r):
            w = widths[i] if i < len(widths) else 0
            cells.append(str(cell).ljust(w))
        out.append("  " + "  ".join(cells))
    return "\n".join(out)


def ok_line(msg: str) -> str:
    return f"  {green('✓')} {msg}"


def err_line(msg: str) -> str:
    return f"  {red('✗')} {msg}"


def warn_line(msg: str) -> str:
    return f"  {yellow('!')} {msg}"
