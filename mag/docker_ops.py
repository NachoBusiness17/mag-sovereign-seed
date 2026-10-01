"""docker_ops — deterministic Docker containment probe + launch path.

The containerized deployment is a category-3 local op that previously only ran by
hand (terminal `docker compose up`). This gives it a framework path so it is
probed on cadence and launched/stopped via REST / CLI / queue instead of hand-run.

Containment = "agent subprocesses never get your full desktop." This module is the
measured twin of that claim: it reports the engine, validates the compose file,
lists containers, and flags native-process port conflicts (8765/8000/9000) that
would block a clean cutover.

Design rules (per doctrine):
  * Deterministic, $0, no LLM.
  * probe()/status() are report-only and SAFE (never mutate).
  * up()/down() mutate but are explicit actions (operator or a routed task).
  * run_cadence() only PROBES + logs to a jsonl for ghost/ops visibility. It never
    auto-ups or auto-downs.

CLI:  python -m mag.docker_ops status|probe|up|down
REST: GET  /api/v1/docker            (status/probe)
      POST /api/v1/docker {action: up|down}
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "logs" / "docker_ops.jsonl"
COMPOSE = ROOT / "docker-compose.yml"
# Host ports the compose file maps — these must be free of native procs for a cutover.
MAPPED_PORTS = (8765, 8000, 9000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, **meta: Any) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _now(), "event": event, **meta}) + "\n")
    except Exception:
        pass


# Docker Desktop install locations (the CLI is often NOT on the interactive shell PATH —
# that silent PATH gap was one reason the container brain couldn't be brought up).
_DOCKER_BIN_PATHS = [
    Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"),
    Path.home() / "AppData" / "Local" / "Docker" / "resources" / "bin" / "docker.exe",
    Path.home() / "AppData" / "Local" / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
]
_DOCKER_DESKTOP_PATHS = [
    Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
    Path.home() / "AppData" / "Local" / "Docker" / "Docker Desktop.exe",
    Path.home() / "AppData" / "Local" / "Programs" / "DockerDesktop" / "Docker Desktop.exe",
]
_ENGINE_WAIT_S = 120  # how long to wait for the engine after launching Docker Desktop


def _docker_bin() -> str:
    """Resolve the docker CLI executable: PATH first, else known Docker Desktop installs."""
    for p in _DOCKER_BIN_PATHS:
        if p.is_file():
            return str(p)
    return "docker"  # fall back to PATH (works when the shell has it)


def engine_reachable(timeout: int = 15) -> bool:
    """True if the Docker engine answers `docker version` (server side reachable)."""
    r = _run(["version", "--format", "{{.Server.Version}}"], timeout=timeout)
    return bool(r.get("ok") and (r.get("out") or "").strip())


def ensure_engine(wait: int = _ENGINE_WAIT_S) -> dict[str, Any]:
    """Launch Docker Desktop if the engine is down, then wait for it to come up.
    Returns {ok, launched, engine_reachable, waited_s}."""
    import os
    import time
    if engine_reachable():
        return {"ok": True, "launched": False, "engine_reachable": True, "waited_s": 0}
    launched = False
    for p in _DOCKER_DESKTOP_PATHS:
        if p.is_file():
            try:
                # launch detached, no window dependency on this shell
                if os.name == "nt":
                    subprocess.Popen([str(p)], close_fds=True,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                                     | getattr(subprocess, "DETACHED_PROCESS", 0))
                else:
                    subprocess.Popen([str(p)], close_fds=True)
                launched = True
            except Exception as e:
                _log("engine-launch-error", path=str(p), error=str(e)[:160])
            break
    waited = 0
    while waited < wait:
        if engine_reachable(timeout=8):
            return {"ok": True, "launched": launched, "engine_reachable": True, "waited_s": waited}
        time.sleep(3)
        waited += 3
    return {"ok": engine_reachable(), "launched": launched,
            "engine_reachable": engine_reachable(), "waited_s": waited}


def _run(args: list[str], cwd: Path = ROOT, timeout: int = 60) -> dict[str, Any]:
    """Run a docker CLI command; returns {ok, code, out, err}."""
    try:
        r = subprocess.run(
            [_docker_bin(), *args],
            cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return {"ok": r.returncode == 0, "code": r.returncode,
                "out": (r.stdout or "").strip(), "err": (r.stderr or "").strip()}
    except FileNotFoundError:
        return {"ok": False, "code": -1, "out": "", "err": "docker CLI not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -1, "out": "", "err": f"docker {args[0]} timed out"}


def _native_port_conflicts() -> list[dict[str, Any]]:
    """Which of the compose-mapped host ports are held by native (non-docker) procs."""
    conflicts: list[dict[str, Any]] = []
    # `docker ps` gives container->host mappings; anything on these ports NOT in a
    # running container is a native hold. We query netstat for listeners and
    # cross-check against container ports.
    try:
        cont_ports = set()
        ps = _run(["ps", "--format", "{{.Ports}}"])
        if ps.get("ok"):
            for line in ps["out"].splitlines():
                for tok in line.replace(",", " ").split():
                    if "->" in tok:
                        cont_ports.add(tok.split("->")[0].rsplit(":", 1)[-1])
        ns = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
        for line in (ns.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "TCP" and "LISTENING" in line:
                try:
                    port = int(parts[1].rsplit(":", 1)[-1])
                except Exception:
                    continue
                if port in MAPPED_PORTS and str(port) not in cont_ports:
                    pid = parts[-1] if parts[-1].isdigit() else None
                    conflicts.append({"port": port, "pid": pid})
    except Exception as e:
        _log("native-conflict-error", error=str(e)[:200])
    return conflicts


def probe() -> dict[str, Any]:
    """Deterministic report of Docker + compose + cutover readiness. Never mutates."""
    engine = _run(["version", "--format", "{{.Server.Version}}"])
    compose = _run(["compose", "config", "--quiet"])
    ps = _run(["ps", "-a", "--format", "{{.Names}}\t{{.Status}}"])
    containers: list[dict[str, str]] = []
    if ps.get("ok"):
        for line in ps["out"].splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                containers.append({"name": parts[0], "status": parts[1]})
    return {
        "ok": engine.get("ok"),
        "schema": "docker_ops.probe.v1",
        "ts": _now(),
        "engine": {"server_version": engine.get("out") or None,
                   "reachable": engine.get("ok"),
                   "error": engine.get("err") or None},
        "compose_file": str(COMPOSE),
        "compose_valid": compose.get("ok"),
        "compose_error": (compose.get("err") or "")[:300] if not compose.get("ok") else None,
        "containers": containers,
        "container_count": len(containers),
        "native_port_conflicts": _native_port_conflicts(),
        "cutover_ready": bool(engine.get("ok") and compose.get("ok")
                              and not _native_port_conflicts()),
    }


def status() -> dict[str, Any]:
    """Alias of probe (report-only), plus a light verdict for the dashboard."""
    p = probe()
    p["schema"] = "docker_ops.status.v1"
    if p["cutover_ready"]:
        p["verdict"] = "ready" if not p["containers"] else "running"
    elif not p["engine"].get("reachable"):
        p["verdict"] = "engine_down"
    elif not p["compose_valid"]:
        p["verdict"] = "compose_invalid"
    else:
        p["verdict"] = "port_conflict"
    return p


def up() -> dict[str, Any]:
    """Bring the stack up (build + start). Explicit action; not auto-called.
    Ensures the Docker engine is running first (self-starts Docker Desktop if needed)."""
    eng = ensure_engine()
    if not eng.get("engine_reachable"):
        _log("docker-up", ok=False, error="docker engine not reachable after launch attempt")
        return {"ok": False, "action": "up", "code": -1, "out": "", "err": "docker engine not reachable",
                "engine": eng, **status()}
    r = _run(["compose", "up", "-d", "--build"], timeout=600)
    _log("docker-up", ok=r["ok"], error=r["err"][:200] if r["err"] else None)
    return {"ok": r["ok"], "action": "up", "code": r["code"],
            "out": r["out"][:500], "err": (r["err"] or "")[:300], "engine": eng, **status()}


def down() -> dict[str, Any]:
    """Tear the stack down. Explicit action; not auto-called."""
    r = _run(["compose", "down"], timeout=180)
    _log("docker-down", ok=r["ok"], error=r["err"][:200] if r["err"] else None)
    return {"ok": r["ok"], "action": "down", "code": r["code"],
            "out": r["out"][:500], "err": (r["err"] or "")[:300], **status()}


def run_cadence() -> dict[str, Any]:
    """Passive probe for the governor cadence. Report-only; NEVER up/down."""
    p = probe()
    _log("docker-probe", reachable=p["engine"].get("reachable"),
         containers=p["container_count"], conflicts=len(p["native_port_conflicts"]),
         verdict=(p["cutover_ready"] and ("running" if p["containers"] else "ready")
                  or "not_ready"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    cmd = (args[0] if args else "status").lower()
    if cmd == "up":
        print(json.dumps(up(), indent=2, default=str))
    elif cmd == "down":
        print(json.dumps(down(), indent=2, default=str))
    elif cmd == "probe":
        print(json.dumps(probe(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))


if __name__ == "__main__":
    main()
