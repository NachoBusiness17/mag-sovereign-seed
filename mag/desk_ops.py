"""Desk operator shortcuts — refresh, wipe, lab reload without UI clicks.

CLI:  python main.py desk refresh|wipe|reset|restart-lab|reload|local-only
      python main.py lab --lan          # explicit WiFi opt-in (saved for reload)
      python main.py lab --local-only   # back to 127.0.0.1 only
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from config import ROOT


def _python_exe() -> str:
    """Real interpreter (bypass the venv shim -> no double PID / no window on spawn)."""
    try:
        from mag.headless import _resolve_python
        return _resolve_python()
    except Exception:
        pass
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def _get_json(url: str, *, timeout: float = 3.0) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw.strip() else {"error": raw[:200]}
        except json.JSONDecodeError:
            body = {"error": raw[:200] or str(exc)}
        return exc.code, body
    except Exception as exc:
        return 0, {"ok": False, "error": str(exc)[:200]}


def _post_json(url: str, body: dict[str, Any], *, timeout: float = 180.0) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            out = json.loads(raw) if raw.strip() else {"error": raw[:200]}
        except json.JSONDecodeError:
            out = {"error": raw[:200] or str(exc)}
        return exc.code, out
    except Exception as exc:
        return 0, {"ok": False, "error": str(exc)[:200]}


def lab_up(*, port: int = 8765, timeout: float = 2.0) -> bool:
    code, _ = _get_json(f"http://127.0.0.1:{port}/api/v1/nervous", timeout=timeout)
    return code == 200


def cast_up(*, port: int = 8766, timeout: float = 2.0) -> bool:
    code, _ = _get_json(f"http://127.0.0.1:{port}/health", timeout=timeout)
    return code == 200


def lab_pid(*, port: int = 8765) -> int | None:
    from mag.power import _pids_on_port

    pids = _pids_on_port(port)
    return pids[0] if pids else None


def restart_lab(*, port: int = 8765, wait_s: float = 12.0, local_only: bool = False) -> dict[str, Any]:
    """Kill dashboard listener on :8765 and spawn a fresh lab (other python windows untouched)."""
    from config import clear_lab_bind, read_lab_bind
    from mag.power import _kill_tree, _pids_on_port

    if local_only:
        clear_lab_bind()

    old_pids = _pids_on_port(port)
    for pid in old_pids:
        _kill_tree(pid)
    if old_pids:
        time.sleep(1.5)

    log = ROOT / "logs" / "lab_desk_ops.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    creation = 0
    if sys.platform == "win32":
        creation = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))  # type: ignore[attr-defined]
    argv = [_python_exe(), str(ROOT / "main.py"), "lab", "--port", str(port)]
    if not local_only and read_lab_bind().get("lan"):
        argv.append("--lan")
    with log.open("a", encoding="utf-8") as lf:
        lf.write(f"\n--- desk_ops restart {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        proc = subprocess.Popen(
            argv,
            cwd=str(ROOT),
            stdout=lf,
            stderr=lf,
            creationflags=creation if sys.platform == "win32" else 0,
            start_new_session=(sys.platform != "win32"),
        )

    deadline = time.time() + wait_s
    while time.time() < deadline:
        if lab_up(port=port):
            new_pid = lab_pid(port=port)
            return {
                "ok": True,
                "action": "restart_lab",
                "old_pids": old_pids,
                "new_pid": new_pid,
                "spawn_pid": proc.pid,
                "port": port,
                "log": str(log),
            }
        time.sleep(0.5)

    return {
        "ok": False,
        "action": "restart_lab",
        "error": f"lab did not come up on :{port} within {wait_s}s",
        "old_pids": old_pids,
        "spawn_pid": proc.pid,
        "log": str(log),
    }


def desk_post(body: dict[str, Any], *, port: int = 8765, timeout: float = 180.0) -> dict[str, Any]:
    if not lab_up(port=port):
        return {"ok": False, "error": f"lab down on :{port} — run: python main.py desk restart-lab"}
    code, out = _post_json(f"http://127.0.0.1:{port}/api/v1/desk-dialogue", body, timeout=timeout)
    out.setdefault("http_status", code)
    if code != 200:
        out.setdefault("ok", False)
    return out


def desk_refresh(*, port: int = 8765, clear_dialogue: bool = True) -> dict[str, Any]:
    return desk_post({"refresh_local": True, "clear_dialogue": clear_dialogue}, port=port)


def desk_wipe(*, port: int = 8765) -> dict[str, Any]:
    return desk_post({"wipe_board": True}, port=port)


def desk_reset(*, port: int = 8765, clear_canvas: bool = False) -> dict[str, Any]:
    return desk_post(
        {"reset_dialogue": True, "clear_dialogue": clear_canvas},
        port=port,
    )


def desk_local_only(*, port: int = 8765) -> dict[str, Any]:
    """Force localhost bind and restart lab — clears saved LAN preference."""
    restarted = restart_lab(port=port, local_only=True)
    restarted["action"] = "local_only"
    restarted["hint"] = "Dashboard is localhost-only again (127.0.0.1)"
    return restarted


def desk_reload(*, port: int = 8765) -> dict[str, Any]:
    """Restart lab (new code) + refresh local seat + verify Stack route."""
    restarted = restart_lab(port=port)
    if not restarted.get("ok"):
        return restarted

    refreshed = desk_refresh(port=port)
    code, stack = _get_json(f"http://127.0.0.1:{port}/api/v1/stack?limit=5", timeout=5.0)
    code2, pulse = _get_json(f"http://127.0.0.1:{port}/api/v1/local-pulse", timeout=5.0)

    return {
        "ok": True,
        "action": "reload",
        "restart": restarted,
        "refresh": refreshed,
        "stack_ok": code == 200,
        "local_pulse_ok": code2 == 200,
        "stack_headline": stack.get("headline") if code == 200 else stack.get("error"),
        "hint": "Hard-refresh browser (Ctrl+Shift+R) on Desk tab",
    }
