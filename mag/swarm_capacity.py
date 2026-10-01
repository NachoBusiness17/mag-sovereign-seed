"""swarm_capacity — how many swarm agents can OUR machine host, and how to expand compute at $0.

Operator (2026-08-10): "how many could my machine host while doing the cloud ai driving them with
frontier data via our system with swarms out doing each subsystem task and finding more resources
to expand compute yet keep us at zero."

The flocking k8s swarm is best modeled as an ATTRACTOR / RESERVOIR network (the action-RIB
three-body dynamics = collective computation; NOT gradient backprop). The capacity question is
answered from REAL machine + cluster facts, deterministically, $0.

MODEL (I/O-bound swarm): a stateless agent mostly WAITS on the cloud AI (network I/O), so it is
NOT CPU-bound — we can oversubscribe many agents per core (they idle while the frontier responds).
The binding constraint is RAM, not CPU, for the cloud-driven swarm. LOCAL inference (ollama) is
GPU-serialized (one generation at a time on the local GPU), so local agents are queued, not
concurrent.

host_capacity()        -> max concurrent cloud-driven agents on the host (RAM-limited).
cluster_capacity()     -> k8s allocatable cpu/mem + max swarm-worker pods.
recommend_replicas()   -> how many mag-swarm worker pods to run for a target concurrency.
free_compute_surface() -> the $0 expansion surface (ollama local + free tiers) available now.

Schema: swarm_capacity.v1 · deterministic $0 · CLI: python -m mag.swarm_capacity host|cluster|free
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "swarm_capacity.v1"
# per stateless agent footprint (python base + context + overhead), GB
PER_AGENT_RAM_GB = 0.20
# I/O-bound oversubscription: an agent idles ~80% of the time waiting on cloud AI -> many per core
IO_AGENTS_PER_CORE = 12
# headroom: leave this much host RAM free for OS + the supervisor pod + ollama
HEADROOM_GB = 8.0
# local GPU inference is serialized (one gen at a time)
LOCAL_SERIAL = True


def host_capacity() -> dict[str, Any]:
    """Max concurrent cloud-driven swarm agents the HOST can support (RAM-limited, I/O-bound)."""
    import os, ctypes
    cpus = os.cpu_count() or 1
    class MEM(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEM(); m.dwLength = ctypes.sizeof(MEM)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    avail = m.ullAvailPhys / 1024 ** 3
    usable = max(0.0, avail - HEADROOM_GB)
    ram_limited = int(usable / PER_AGENT_RAM_GB)
    cpu_limited = int(cpus * IO_AGENTS_PER_CORE)
    max_agents = min(ram_limited, cpu_limited)
    return {"ok": True, "schema": SCHEMA, "cpus": cpus, "avail_ram_gb": round(avail, 1),
            "usable_ram_gb": round(usable, 1), "per_agent_ram_gb": PER_AGENT_RAM_GB,
            "ram_limited_agents": ram_limited, "cpu_limited_agents": cpu_limited,
            "max_concurrent_agents": max_agents,
            "model": "I/O-bound swarm, RAM-limited; local ollama inference is GPU-serialized"}


def cluster_capacity(*, node: str = "mag-control-plane") -> dict[str, Any]:
    """k8s cluster allocatable cpu/mem + max mag-swarm worker pods (via the system k8s path)."""
    from mag import k8s_bridge as br
    obj = br.get_json("node", node)
    if not obj.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": obj.get("error", "node not found")}
    alloc = (obj.get("status") or {}).get("allocatable") or {}
    cpu = alloc.get("cpu", "?")
    mem = alloc.get("memory", "?")
    def _gi(m: str) -> float:
        try:
            if m.endswith("Ki"):
                return int(m[:-2]) / 1024 / 1024
            return float(m) / 1024 ** 3 if "i" not in m else float(m)
        except Exception:
            return 0.0
    mem_gb = _gi(str(mem))
    # each mag-swarm pod requests 100m/256Mi -> max pods bounded by cpu and mem
    cpu_n = float(str(cpu).rstrip("m")) / 1000 if str(cpu).endswith("m") else float(cpu)
    max_pods_cpu = int(cpu_n / 0.1)
    max_pods_mem = int(mem_gb / 0.256)
    max_pods = max(1, min(max_pods_cpu, max_pods_mem))
    return {"ok": True, "schema": SCHEMA, "node": node, "alloc_cpu": cpu, "alloc_mem_gb": round(mem_gb, 1),
            "max_swarm_worker_pods": max_pods,
            "note": "each worker pod runs up to MAX_PER_PASS agents per pass"}


def recommend_replicas(*, target_agents: int | None = None) -> dict[str, Any]:
    """How many mag-swarm worker pods to run for a target concurrency (or the host max)."""
    host = host_capacity()
    clust = cluster_capacity()
    target = target_agents or host.get("max_concurrent_agents") or 100
    # MAX_PER_PASS=8 agents per worker pass -> pods needed (bounded by cluster allocatable)
    agents_per_pod = 8
    needed = max(1, -(-target // agents_per_pod))  # ceil
    max_pods = clust.get("max_swarm_worker_pods") or 1
    replicas = min(needed, max_pods)
    return {"ok": True, "schema": SCHEMA, "target_agents": target, "agents_per_pod": agents_per_pod,
            "needed_pods": needed, "max_pods_allocatable": max_pods,
            "recommended_replicas": replicas,
            "achievable_agents": replicas * agents_per_pod}


def free_compute_surface() -> dict[str, Any]:
    """The $0 expansion surface available NOW: local ollama models + free-tier detectors."""
    local = []
    try:
        from mag import gpu_ghost as gg
        local = gg._ollama_models()
    except Exception:
        pass
    free_tiers = []
    try:
        from mag import afk_loop
        r = afk_loop.freebie_scan()
        free_tiers = (r.get("found") or r.get("surfaces") or [])
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "local_ollama_models": local,
            "local_inference": "GPU-serialized (1 gen at a time) but FREE",
            "free_tier_surfaces": free_tiers,
            "surface": "ollama(local GPU) + free tiers + browser free frontends (perplexity/deepseek/grok)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-capacity")
    ap.add_argument("cmd", nargs="?", default="host", choices=["host", "cluster", "free", "replicas"])
    ap.add_argument("--target", type=int, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "cluster":
        print(json.dumps(cluster_capacity(), indent=2, default=str))
    elif args.cmd == "free":
        print(json.dumps(free_compute_surface(), indent=2, default=str))
    elif args.cmd == "replicas":
        print(json.dumps(recommend_replicas(target_agents=args.target), indent=2, default=str))
    else:
        print(json.dumps(host_capacity(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
