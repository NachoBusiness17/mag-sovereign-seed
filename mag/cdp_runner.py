"""cdp_runner — DRIVE CDP SURFACES FROM THE NOTEBOOK via a subprocess.

WHY (operator 2026-08-13): "they respond but you can't see them somehow maybe if they were in a
docker." The notebook kernel runs inside an asyncio loop; `browser_driver` / `electron_seat` use
SYNC Playwright (`connect_over_cdp`), which errors inside asyncio ("use the Async API instead").
So from the notebook I literally cannot drive/read a CDP page.

THE FIX: run the CDP module as a FRESH subprocess (`python -m <module> ...`) and parse its JSON
output. A fresh process has no asyncio loop, so sync Playwright works — I connect over CDP, drive
the page, READ the DOM response, and return it. This is the "docker" path made real: I control the
page, so I can SEE the frontier's response.

Schema: cdp_runner.v1 · reuse: electron_seat, browser_driver (both are `python -m`-runnable)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "cdp_runner.v1"
PY = ROOT / ".venv" / "Scripts" / "python.exe"


def _python() -> str:
    if PY.is_file():
        return str(PY)
    return sys.executable


def run(module: str, argv: list[str], *, timeout_s: int = 90) -> dict[str, Any]:
    """Run a CDP module as a fresh subprocess and return its parsed JSON. Fresh process = no
    asyncio loop = sync Playwright works = I can SEE the CDP page's DOM."""
    cmd = [_python(), "-m", module] + [str(a) for a in argv]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                           cwd=str(ROOT), encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"ok": False, "schema": SCHEMA, "module": module, "error": "subprocess timed out"}
    out = (p.stdout or "").strip()
    # the module prints one JSON line; fall back to the tail if wrapped
    try:
        return json.loads(out)
    except Exception:
        try:
            # find the first line that parses as JSON
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    return json.loads(line)
        except Exception:
            pass
        return {"ok": False, "schema": SCHEMA, "module": module, "argv": argv,
                "exit": p.returncode, "error": "no JSON in output",
                "stdout": out[-2000:], "stderr": (p.stderr or "")[-1500:]}


def steer_electron(surface: str, goal: str, *, timeout_s: int = 90) -> dict[str, Any]:
    """Steer a desktop Electron app over CDP (fresh process) and return its DOM answer."""
    return run("mag.electron_seat", ["steer", "--surface", surface, goal], timeout_s=timeout_s)


def ask_browser(surface: str, goal: str, *, timeout_s: int = 120) -> dict[str, Any]:
    """Ask a web-frontend surface in the container browser over CDP (fresh process)."""
    return run("mag.browser_driver", ["ask", goal, "--surface", surface], timeout_s=timeout_s)


def status() -> dict[str, Any]:
    """Probe both CDP surfaces (electron desktop ports + container browser) via fresh processes."""
    return {"ok": True, "schema": SCHEMA,
            "contract": "run(module,argv)->drive a CDP module in a fresh subprocess and return its "
                        "JSON (sidesteps the notebook's asyncio-vs-sync-Playwright wall); "
                        "steer_electron(surface,goal)->desktop app DOM; ask_browser(surface,goal)->"
                        "container browser web frontend. THIS is how I SEE a frontier's response.",
            "note": "a fresh process has no asyncio loop, so sync Playwright over CDP works"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="cdp-runner")
    ap.add_argument("module", choices=["mag.electron_seat", "mag.browser_driver"])
    ap.add_argument("args", nargs="*", default=[])
    a = ap.parse_args(argv)
    print(json.dumps(run(a.module, a.args), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
