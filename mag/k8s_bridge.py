"""k8s_bridge — the ONE system-native way the framework talks to our k8s cluster.

Operator correction (2026-08-10): "you're not using the system you're still using terminal."
Hand-driving kubectl through terminals / inline subprocess snippets bypasses the architecture.
This module is the architecture's k8s surface: every cluster operation (inspect, apply, drain
jobs, PVC bridge) goes through here, windowless via mag.headless, so the swarm/rib/k8s loop is a
system path — the same module the autorun/cadence calls — not hand-run commands.

Right-sizing the swarm deployment is part of this: the cronjob gets explicit resource
requests/limits, and MAX_PER_PASS is sized so a job drains a bounded chunk.

Schema: k8s_bridge.v1 · deterministic · windowless (mag.headless.run_py).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "k8s_bridge.v1"
NS = "mag"
# kubectl is on Docker Desktop's bin (not always on PATH across terminals).
_KUBECTL_CANDIDATES = [
    os.environ.get("KUBECTL"),
    r"C:\Users\ESTATE_USER\AppData\Local\Programs\DockerDesktop\resources\bin\kubectl.exe",
    r"C:\Users\ESTATE_USER\AppData\Local\Microsoft\WinGet\Links\kubectl.exe",
    "kubectl",
]


def _kubectl() -> str:
    for c in _KUBECTL_CANDIDATES:
        if not c:
            continue
        try:
            if Path(c).is_file() or c == "kubectl":
                return c
        except OSError:
            continue
    return "kubectl"


def _run(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a kubectl command WINDOWLESS (CREATE_NO_WINDOW) and return the result.

    This is the only subprocess the framework should use to talk to k8s — everything else
    routes through the system's own modules. Locally it never pops a console window.
    """
    from mag import headless
    headless.install_no_window_defaults()
    return headless.run_headless([_kubectl(), *args], capture_output=True, text=True,
                                 timeout=timeout)


def _out(r: subprocess.CompletedProcess) -> dict[str, Any]:
    return {"ok": r.returncode == 0, "code": r.returncode,
            "stdout": (r.stdout or "")[:4000], "stderr": (r.stderr or "")[:2000]}


# --- inspect -------------------------------------------------------------
def cronjobs() -> dict[str, Any]:
    r = _run(["get", "cronjob", "-n", NS])
    return _out(r)


def jobs() -> dict[str, Any]:
    r = _run(["get", "jobs", "-n", NS])
    return _out(r)


def pods(label: str | None = None) -> dict[str, Any]:
    args = ["get", "pods", "-n", NS]
    if label:
        args += ["-l", label]
    return _out(_run(args))


def logs(label: str, tail: int = 30) -> dict[str, Any]:
    r = _run(["logs", "-n", NS, "-l", label, "--tail", str(tail)])
    return _out(r)


def get_json(resource: str, name: str, *, ns: str = NS) -> dict[str, Any]:
    """Get a k8s object as parsed JSON (for the RIB-fed reconciler to read desired state)."""
    r = _run(["get", resource, name, "-n", ns, "-o", "json"], timeout=60)
    if r.returncode != 0:
        return {"ok": False, "code": r.returncode, "error": (r.stderr or "").strip()[:300]}
    try:
        obj = json.loads(r.stdout or "{}")
        obj["ok"] = True
        return obj
    except Exception as e:
        return {"ok": False, "error": f"parse: {e}"}


# --- deploy / run --------------------------------------------------------
def apply_file(rel: str) -> dict[str, Any]:
    r = _run(["apply", "-f", str(ROOT / "deploy" / "k8s" / rel)])
    return _out(r)


def delete_job(name: str) -> dict[str, Any]:
    r = _run(["delete", "job", name, "-n", NS, "--ignore-not-found"])
    return _out(r)


def create_job_from_cronjob(cronjob: str, name: str) -> dict[str, Any]:
    r = _run(["create", "job", "--from=cronjob/" + cronjob, name, "-n", NS])
    return _out(r)


# --- PVC bridge (local memory <-> cluster state volume) -------------------
def cp_to_pod(local_rel: str, pod: str, dest_dir: str) -> dict[str, Any]:
    """Copy a LOCAL dir/file onto the shared state PVC via a pod that mounts it.

    This is the bridge that lets the local seat hand work to the cluster: the local
    `memory/` is NOT the PVC, so a local dispatch must be copied into the pod's mounted
    path to reach the in-cluster swarm. Deterministic; the system's own bridge.
    """
    r = _run(["cp", "-n", NS, str(ROOT / local_rel), f"{pod}:{dest_dir}"])
    return _out(r)


def cp_from_pod(pod: str, src_dir: str, local_rel: str) -> dict[str, Any]:
    """Copy cluster results from the PVC back to the local seat."""
    r = _run(["cp", "-n", NS, f"{pod}:{src_dir}", str(ROOT / local_rel)])
    return _out(r)


def exec_read(pod: str, shell_cmd: str) -> dict[str, Any]:
    r = _run(["exec", "-n", NS, pod, "--", "sh", "-c", shell_cmd])
    return _out(r)


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="k8s-bridge")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "cronjobs", "jobs", "pods", "logs"])
    ap.add_argument("--label", default="")
    ap.add_argument("--tail", type=int, default=30)
    args = ap.parse_args(argv)
    if args.cmd == "cronjobs":
        print(json.dumps(cronjobs(), indent=2))
    elif args.cmd == "jobs":
        print(json.dumps(jobs(), indent=2))
    elif args.cmd == "pods":
        print(json.dumps(pods(args.label or None), indent=2))
    elif args.cmd == "logs":
        print(json.dumps(logs(args.label, args.tail), indent=2))
    else:
        print(json.dumps({"schema": SCHEMA, "kubectl": _kubectl(), "ns": NS}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
