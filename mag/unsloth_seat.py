"""Unsloth Studio GPU seat — detect, start/stop, Stack/REST payload.

CLI: python main.py unsloth status|start|stop
REST: GET/POST /api/v1/unsloth
State: memory/working/unsloth_seat.json · log: logs/unsloth_seat.log
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

from config import CONFIGS_DIR, ROOT

SCHEMA = "mag_unsloth_seat.v1"
SEAT_ID = "unsloth-studio"
STATE_PATH = ROOT / "memory" / "working" / "unsloth_seat.json"
LOG_PATH = ROOT / "logs" / "unsloth_seat.log"
DEFAULT_AGENTS = ("hermes", "pi", "codex", "claude")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def unsloth_exe() -> Path:
    """Resolve Unsloth Studio CLI (~/.unsloth/studio/bin/unsloth.exe on Windows)."""
    env = (os.environ.get("UNSLOTH_EXE") or os.environ.get("UNSLOTH_STUDIO_BIN") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    home = Path.home()
    for candidate in (
        home / ".unsloth" / "studio" / "bin" / "unsloth.exe",
        home / ".unsloth" / "studio" / "bin" / "unsloth",
    ):
        if candidate.is_file():
            return candidate
    return home / ".unsloth" / "studio" / "bin" / "unsloth.exe"


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        from mag_launch import _pid_alive as launch_alive

        return bool(launch_alive(int(pid)))
    except Exception:
        pass
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            try:
                ec = wintypes.DWORD()
                ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(ec))
                return ec.value == 259
            finally:
                ctypes.windll.kernel32.CloseHandle(h)
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(data: dict[str, Any]) -> dict[str, Any]:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _run_version(exe: Path) -> str:
    if not exe.is_file():
        return ""
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=12,
            cwd=str(ROOT),
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return out.splitlines()[0][:80] if out else ""
    except Exception:
        return ""


def _desk_gpu_hint() -> dict[str, Any]:
    """Ollama desk model from lanes.yaml + optional Unsloth cache scan."""
    hint: dict[str, Any] = {
        "desk_model": "gemma4-desk",
        "gpu_note": "RX 5600 XT · 6GB — desk via Ollama; Unsloth for fine-tune/chat/agent",
        "cache_models": [],
    }
    lanes_path = CONFIGS_DIR / "lanes.yaml"
    if lanes_path.is_file():
        try:
            import yaml

            lanes = yaml.safe_load(lanes_path.read_text(encoding="utf-8")) or {}
            lm = lanes.get("local_models") or {}
            if lm.get("desk_orchestrator"):
                hint["desk_model"] = str(lm["desk_orchestrator"])
        except Exception:
            pass

    cache_roots = [
        Path.home() / ".cache" / "huggingface" / "hub",
        Path.home() / ".unsloth",
    ]
    found: list[str] = []
    for root in cache_roots:
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("*"):
                if len(found) >= 6:
                    break
                name = p.name.lower()
                if "qwen" in name and p.is_dir():
                    tag = p.name[:48]
                    if tag not in found:
                        found.append(tag)
        except OSError:
            continue
    hint["cache_models"] = found[:4]
    return hint


def _log_tail(n: int = 24) -> list[str]:
    if not LOG_PATH.is_file():
        return []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-max(1, min(n, 120)) :]
    except OSError:
        return []


def unsloth_status(*, log_lines: int = 0) -> dict[str, Any]:
    """Installed, version, running pid, GPU hints."""
    exe = unsloth_exe()
    installed = exe.is_file()
    version = _run_version(exe) if installed else ""
    state = _read_state()
    pid = int(state.get("pid") or 0) or None
    running = bool(pid and _pid_alive(pid))
    if pid and not running:
        state = dict(state)
        state["status"] = "stopped"
        state["stopped"] = _utc()
        _write_state(state)

    gpu = _desk_gpu_hint()
    payload: dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "seat_id": SEAT_ID,
        "installed": installed,
        "exe": str(exe),
        "version": version,
        "running": running,
        "pid": pid if running else None,
        "mode": state.get("mode") if running else None,
        "model": state.get("model") if running else None,
        "agent": state.get("agent") if running else None,
        "mag_task_id": state.get("mag_task_id"),
        "started": state.get("started"),
        "log_path": str(LOG_PATH),
        "state_path": str(STATE_PATH),
        "gpu_hint": gpu,
        "api": "GET /api/v1/unsloth",
    }
    if log_lines > 0:
        payload["log_tail"] = _log_tail(log_lines)
    return payload


def _kill_pid(pid: int) -> None:
    if not pid:
        return
    try:
        from mag.power import _kill_tree

        _kill_tree(pid)
    except Exception:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass


def unsloth_stop(*, unregister: bool = True) -> dict[str, Any]:
    """Stop detached Unsloth process tracked in state file."""
    state = _read_state()
    pid = int(state.get("pid") or 0) or None
    tid = str(state.get("mag_task_id") or "").strip()

    if pid and _pid_alive(pid):
        _kill_pid(pid)
        time.sleep(0.4)

    still = pid and _pid_alive(pid)
    if unregister and tid:
        try:
            from mag.seat_registry import unregister

            unregister(tid, status="done", detail="unsloth_stop")
        except Exception:
            pass

    new_state = {
        **state,
        "status": "stopped" if not still else "running",
        "stopped": _utc(),
        "pid": None if not still else pid,
    }
    _write_state(new_state)

    st = unsloth_status()
    return {
        **st,
        "ok": not still,
        "action": "stop",
        "pid": pid,
        "killed": bool(pid and not still),
        "mag_task_id": tid or None,
        "error": "process still alive" if still else None,
    }


def unsloth_start(
    *,
    mode: str = "chat",
    model: str = "",
    agent: str = "hermes",
    register_seat: bool = True,
) -> dict[str, Any]:
    """Spawn detached unsloth chat or coding-agent process."""
    exe = unsloth_exe()
    if not exe.is_file():
        return {
            "ok": False,
            "action": "start",
            "error": f"Unsloth not found at {exe}",
            **unsloth_status(),
        }

    cur = _read_state()
    old_pid = int(cur.get("pid") or 0) or None
    if old_pid and _pid_alive(old_pid):
        return {
            "ok": True,
            "action": "start",
            "already_running": True,
            "pid": old_pid,
            **unsloth_status(),
        }

    mode = (mode or "chat").strip().lower()
    agent = (agent or "hermes").strip().lower()
    model = (model or "").strip()

    cmd: list[str] = [str(exe)]
    if mode == "agent":
        if agent not in DEFAULT_AGENTS:
            agent = "hermes"
        cmd.extend(["start", agent])
    else:
        cmd.append("chat")
        if model:
            cmd.append(model)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    creation = 0
    if sys.platform == "win32":
        creation = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))  # type: ignore[attr-defined]

    with LOG_PATH.open("a", encoding="utf-8") as lf:
        lf.write(f"\n--- unsloth_start {time.strftime('%Y-%m-%d %H:%M:%S')} mode={mode} ---\n")
        lf.write(" ".join(cmd) + "\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=lf,
            stderr=lf,
            creationflags=creation if sys.platform == "win32" else 0,
            start_new_session=(sys.platform != "win32"),
        )

    mag_task_id = cur.get("mag_task_id")
    if register_seat:
        try:
            from mag.seat_registry import register

            rec = register(
                seat=SEAT_ID,
                goal=f"Unsloth GPU {mode}" + (f" · {model}" if model else ""),
                mode="local_gpu",
                pid=proc.pid,
                tag="unsloth_studio",
                parent="desktop",
            )
            mag_task_id = rec.get("task_id")
        except Exception:
            mag_task_id = mag_task_id or None

    state = {
        "schema": SCHEMA,
        "seat_id": SEAT_ID,
        "status": "running",
        "pid": proc.pid,
        "mode": mode,
        "model": model or None,
        "agent": agent if mode == "agent" else None,
        "cmd": cmd,
        "started": _utc(),
        "mag_task_id": mag_task_id,
        "source": "unsloth_studio",
    }
    _write_state(state)

    st = unsloth_status()
    return {
        **st,
        "ok": True,
        "action": "start",
        "pid": proc.pid,
        "running": True,
        "mode": mode,
        "model": model or None,
        "agent": agent if mode == "agent" else None,
        "mag_task_id": mag_task_id,
        "log_path": str(LOG_PATH),
    }


def unsloth_chat(*, model: str = "", prompt: str = "", timeout: float = 120.0) -> dict[str, Any]:
    """One-shot inference via `unsloth inference` (non-interactive)."""
    exe = unsloth_exe()
    if not exe.is_file():
        return {"ok": False, "action": "chat", "error": f"Unsloth not found at {exe}"}

    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "action": "chat", "error": "prompt required for one-shot chat"}

    cmd = [str(exe), "inference"]
    if model:
        cmd.append(model)
    cmd.extend(["--prompt", prompt])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(10.0, timeout),
            cwd=str(ROOT),
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "action": "chat",
            "model": model or None,
            "reply": out[:4000] if out else err[:4000],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "action": "chat", "error": f"timeout after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "action": "chat", "error": str(exc)[:200]}


def build_unsloth_payload(*, log_lines: int = 0) -> dict[str, Any]:
    """Stack/REST viewport — status + agent row hints."""
    st = unsloth_status(log_lines=log_lines)
    running = bool(st.get("running"))
    mode = st.get("mode") or "chat"
    gpu = st.get("gpu_hint") or {}
    desk = gpu.get("desk_model") or "gemma4-desk"
    cache = gpu.get("cache_models") or []
    gpu_text = desk
    if cache:
        gpu_text += f" · cache: {', '.join(cache[:2])}"

    agent_row = {
        "kind": "unsloth_gpu",
        "id": SEAT_ID,
        "name": "Unsloth Studio",
        "goal": f"GPU {mode}" + (f" · pid {st.get('pid')}" if running else " · idle"),
        "status": "running" if running else ("installed" if st.get("installed") else "missing"),
        "phase": mode,
        "provider": "unsloth_studio",
        "pid": st.get("pid"),
        "api": "GET /api/v1/unsloth",
    }

    research_row = {
        "id": "unsloth_studio",
        "label": "Unsloth GPU",
        "status": "ok" if running else ("idle" if st.get("installed") else "warn"),
        "text": (
            f"{st.get('version') or 'installed'} · {gpu_text}"
            if st.get("installed")
            else f"not installed — expected {st.get('exe')}"
        ),
        "api": "GET /api/v1/unsloth",
        "proof": str(STATE_PATH),
    }

    return {
        **st,
        "agent_row": agent_row,
        "research_row": research_row,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="mag unsloth", description="Unsloth Studio GPU seat")
    sub = p.add_subparsers(dest="action")

    sub.add_parser("status", help="Show install + running state")
    ps = sub.add_parser("start", help="Start detached chat or coding agent")
    ps.add_argument("--mode", default="chat", choices=["chat", "agent"])
    ps.add_argument("--model", default="", help="Model for chat mode")
    ps.add_argument("--agent", default="hermes", help="Agent for start mode (hermes, pi, …)")
    ps.add_argument("--no-register", action="store_true", help="Skip seat_registry")
    sub.add_parser("stop", help="Stop tracked Unsloth process")

    args = p.parse_args(argv)
    action = args.action or "status"

    if action == "status":
        print(json.dumps(unsloth_status(), indent=2, default=str))
        return 0
    if action == "start":
        res = unsloth_start(
            mode=args.mode,
            model=args.model,
            agent=args.agent,
            register_seat=not args.no_register,
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if action == "stop":
        res = unsloth_stop()
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
