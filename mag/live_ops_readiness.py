"""Read-only live-operations readiness snapshot.

This is the final preflight surface for a paused or cold-booted Mag.  It reads
existing receipts and state files, never starts a process, calls a provider,
spends a lane, or prints credentials.  ``ready`` means the operator can safely
choose a lifecycle action; it does not claim that the fleet is currently live.
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "live_ops_readiness.v1"
OUT = ROOT / "memory" / "runs" / "live_ops" / "readiness.json"


def _exists(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    return {"path": rel, "exists": path.is_file() or path.is_dir(),
            "bytes": path.stat().st_size if path.is_file() else None}


def _supervisor_snapshot() -> dict[str, Any]:
    path = ROOT / "memory" / "supervisor" / "state.json"
    if not path.is_file():
        return {"state_file": False, "running": [], "note": "no supervisor receipt"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state_file": True, "running": [], "error": str(exc)[:120]}
    running: list[str] = []
    for name, row in data.items() if isinstance(data, dict) else []:
        if not isinstance(row, dict) or row.get("status") != "running":
            continue
        pid = int(row.get("pid") or 0)
        alive = False
        if pid > 0:
            try:
                if os.name == "nt":
                    import ctypes
                    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                    alive = bool(handle)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                else:
                    os.kill(pid, 0)
                    alive = True
            except Exception:
                alive = False
        if alive:
            running.append(str(name))
    return {"state_file": True, "running": running,
            "declared": sorted(data) if isinstance(data, dict) else []}


def _port_observer(port: int) -> dict[str, Any]:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.35):
            return {"port": port, "open": True}
    except OSError:
        return {"port": port, "open": False}


def _container_controller_hint(observers: dict[str, dict[str, Any]]) -> bool:
    """Recognize the existing container supervisor without shelling to Docker."""
    path = ROOT / "state" / "mag_launch.json"
    if not path.is_file() or not any(item.get("open") for item in observers.values()):
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # PID 1 is the expected supervisor PID inside the Mag container.
        return int(data.get("supervisor_pid") or 0) == 1
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def snapshot() -> dict[str, Any]:
    supervisor = _supervisor_snapshot()
    checks = {
        "agent_state_latest": _exists("memory/agent_state/LATEST.json"),
        "agent_state_audit": _exists("memory/runs/verkle_recovery/agent_state_audit_20260901.json"),
        "biography_tip": _exists("memory/biography/verkle_tip.json"),
        "trajectory_bounds": _exists("watch/openclaw_traj.jsonl.bounds.meta.json"),
        "trajectory_rib": _exists("memory/runs/trajectory_rib/compiled.jsonl.meta.json"),
        "artifact_index": _exists("memory/runs/verkle_recovery/artifact_index_20260901.meta.json"),
        "organ_map": _exists("memory/runs/organ_map/latest.json"),
        "live_report": _exists("state/LIVE_REPORT.md"),
    }
    missing = [name for name, check in checks.items() if not check["exists"]]
    observers = {"dashboard_8765": _port_observer(8765), "ghost_9000": _port_observer(9000)}
    container_controller = _container_controller_hint(observers)
    try:
        from mag.operator_mode import read as read_operator_mode, pause_reason
        operator_mode = read_operator_mode()
        operator_pause = pause_reason()
    except Exception as exc:
        operator_mode = {"mode": "invalid", "reason": str(exc)[:120]}
        operator_pause = "operator_mode_unavailable"
    warnings: list[str] = []
    if not supervisor["running"] and any(item["open"] for item in observers.values()) and not container_controller:
        warnings.append("dashboard/ghost port is open while the recorded supervisor has no live child; identify the external controller before starting anything")
    lifecycle = "container_live" if container_controller else ("live" if supervisor["running"] else "paused_or_down")
    controller = "docker_or_mag_launch" if container_controller else ("host_supervisor" if supervisor["running"] else "unknown")
    if operator_pause:
        lifecycle = f"{lifecycle}_paused"
    return {
        "ok": not missing,
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lifecycle": lifecycle,
        "controller": controller,
        "operator_mode": operator_mode,
        "ready_for_operator_action": not missing,
        "spend": {"provider_calls": 0, "estimated_cost": 0, "secrets_read": False},
        "supervisor": supervisor,
        "local_observers": observers,
        "checks": checks,
        "missing_receipts": missing,
        "warnings": warnings,
        "laws": [
            "do not start a second supervisor",
            "do not promote WIRED to LIVE without a fresh invocation receipt",
            "do not rewrite a commitment chain in place",
            "unbounded trajectory rows remain evidence, not compiled authority",
        ],
        "next": (f"{operator_pause}; keep the controller/UI up and resume explicitly when ready" if operator_pause else ("inspect the external controller before enabling a second one" if warnings else ("Docker/mag_launch already owns lifecycle; do not start a host supervisor" if container_controller else ("operator may start the single approved lifecycle controller" if not missing else "restore missing receipts before enabling live ops")))),
    }


def write_snapshot() -> dict[str, Any]:
    result = snapshot()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    result["output"] = str(OUT)
    return result


def main() -> int:
    print(json.dumps(write_snapshot(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
