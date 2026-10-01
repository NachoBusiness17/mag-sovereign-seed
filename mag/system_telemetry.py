"""system_telemetry — REAL disk + ethernet + vEthernet + CPU/mem + GPU telemetry, cross-linked.

The operator (2026-08-11): "we need to look at disk and ethernet and v ethernet. we need all of
these systems talking to eachother truly not handwaiving via our selfsteal internals."

So: no fake numbers. This surface reads ACTUAL OS telemetry (psutil; Windows-aware for the
vEthernet/WSL virtual NIC), tags each network interface (physical ethernet vs virtual vEthernet vs
loopback), and CROSS-LINKS the surfaces so the governor + ghost.sense() see the whole machine as
one coherent surface — CPU/mem/GPU/disk/net all talking to each other, not silos.

  cpu_mem()  -> psutil.cpu_percent + virtual_memory (real)
  gpu()      -> gpu_lifecycle.resources (real, guarded)
  disk()     -> psutil.disk_partitions + disk_usage per mount (real)
  net()      -> per-interface: bytes_sent/recv, up, + interface tag (ethernet / vEthernet / loopback)
  sense()    -> the whole machine in one surface
  crosslink()-> correlations between surfaces (GPU busy <-> cloud egress; disk high <-> throttle)

Deterministic + $0. Guarded: any missing sensor degrades that sensor only. Schema: system_telemetry.v1
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "system_telemetry.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tag_interface(name: str) -> str:
    n = (name or "").lower()
    if "vethernet" in n or "wsl" in n or "hyper-v" in n:
        return "vEthernet"          # the WSL/Hyper-V virtual NIC (the container's link to the host)
    if n in ("loopback", "lo") or name.startswith("Loopback"):
        return "loopback"
    if any(v in n for v in ("virtual", "tap", "tun", "vmnet", "docker", "br-", "veth", "npcap")):
        return "virtual"
    return "ethernet"               # physical NIC


def cpu_mem() -> dict[str, Any]:
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {"ok": True, "cpu_pct": psutil.cpu_percent(interval=1),
                "mem_total_gb": round(vm.total / 1e9, 1), "mem_used_gb": round(vm.used / 1e9, 1),
                "mem_pct": vm.percent}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def gpu() -> dict[str, Any]:
    try:
        from mag.gpu_lifecycle import resources as gr
        g = gr()
        return {"ok": True, "free_for_render": g.get("free_for_render"),
                "resources": g.get("resources")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def disk() -> dict[str, Any]:
    try:
        import psutil
        mounts = []
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                mounts.append({"mount": p.mountpoint, "device": p.device,
                               "total_gb": round(u.total / 1e9, 1),
                               "used_gb": round(u.used / 1e9, 1), "pct": u.percent,
                               "fs": p.fstype})
            except Exception:
                continue
        return {"ok": True, "mounts": mounts}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def net() -> dict[str, Any]:
    """Per-interface network telemetry (real bytes sent/recv) + interface tagging."""
    try:
        import psutil
        io = psutil.net_io_counters(pernic=True) or {}
        stats = psutil.net_if_stats() or {}
        ifaces = []
        total_sent = total_recv = 0
        for name, c in io.items():
            ifaces.append({
                "interface": name, "tag": _tag_interface(name),
                "up": bool((stats.get(name) or {}).isup if hasattr((stats.get(name) or {}), "isup") else None),
                "bytes_sent": c.bytes_sent, "bytes_recv": c.bytes_recv,
                "packets_sent": c.packets_sent, "packets_recv": c.packets_recv,
            })
            total_sent += c.bytes_sent
            total_recv += c.bytes_recv
        return {"ok": True, "total_bytes_sent": total_sent, "total_bytes_recv": total_recv,
                "ethernet": [i for i in ifaces if i["tag"] == "ethernet"],
                "vethernet": [i for i in ifaces if i["tag"] == "vEthernet"],
                "interfaces": ifaces}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def sense() -> dict[str, Any]:
    """The WHOLE machine as one cross-linked surface (real data, no handwaving)."""
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "cpu_mem": cpu_mem(), "gpu": gpu(), "disk": disk(), "net": net()}


def crosslink() -> dict[str, Any]:
    """Correlations between surfaces so they TRULY talk — not handwaved, from real numbers."""
    s = sense()
    links: list[dict[str, Any]] = []
    # 1) GPU busy <-> cloud egress: if the GPU can't run local, work goes to the cloud (net egress).
    g = s.get("gpu") or {}
    n = s.get("net") or {}
    gpu_free = bool(g.get("free_for_render"))
    total_egress = n.get("total_bytes_sent", 0)
    if not gpu_free and total_egress:
        links.append({"from": "gpu", "to": "net",
                      "signal": "GPU not free -> work egresses to cloud",
                      "egress_bytes": total_egress})
    # 2) disk high <-> throttle: if any disk is near full, the system should throttle writes.
    for m in (s.get("disk") or {}).get("mounts", []):
        if m.get("pct", 0) >= 90:
            links.append({"from": "disk", "to": "governor",
                          "signal": f"disk {m['mount']} at {m['pct']}% -> throttle write-heavy work",
                          "pct": m["pct"]})
    # 3) memory pressure <-> replicas: high mem% signals the governor to not scale up workers.
    cm = s.get("cpu_mem") or {}
    if cm.get("mem_pct", 0) >= 85:
        links.append({"from": "mem", "to": "governor",
                      "signal": f"mem {cm['mem_pct']}% -> cap worker replicas", "mem_pct": cm["mem_pct"]})
    # 4) CPU saturation <-> scale out (compressible, safe) but not on I/O-bound agents.
    if (cm.get("cpu_pct") or 0) >= 85:
        links.append({"from": "cpu", "to": "governor",
                      "signal": f"cpu {cm['cpu_pct']}% -> scale-out candidate (compressible)",
                      "cpu_pct": cm["cpu_pct"]})
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_links": len(links), "links": links,
            "note": "cross-surface signals: the surfaces talk to each other from real numbers"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "cpu_mem()/gpu()/disk()/net()->real OS telemetry (psutil, Windows-aware "
                        "vEthernet tagging); sense()->whole machine; crosslink()->surface "
                        "correlations so they truly talk. $0 deterministic.",
            "cost": "deterministic + $0 (psutil)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="system-telemetry")
    ap.add_argument("cmd", nargs="?", default="sense", choices=["sense", "net", "disk", "crosslink", "status"])
    a = ap.parse_args()
    r = {"sense": sense, "net": net, "disk": disk, "crosslink": crosslink, "status": status}[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
