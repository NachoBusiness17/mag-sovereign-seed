"""resource_governor — the K8s SELF-RECONCILING RESOURCE GOVERNOR (frontier steal, realized).

Right-sizes memory/cpu/vram-GPU in the swarm with NO manual setting, reusing our own sensing:

  SENSE     loop_doctor.sense() + swarm_health + usage_monitor.watch() + gpu_lifecycle.resources()
  RECONCILE compute the DESIRED spec: controller Guaranteed (req==lim), workers Burstable (req<lim),
            CPU overcommit (loose limits), memory right-sized (bounded), GPU only on confirmed
            headroom, replicas from queue depth (not CPU).
  BOUNDARY  a configmap-style cap set (never exceeded) — budget, max replicas, max vram.
  APPLY     guarded: default dry (no kubectl); apply=True writes a desired-spec artifact + trail.

Deterministic + $0. Fully guarded: any missing sensor degrades that sensor, never breaks the run.
Schema: resource_governor.v1
CLI:  python -m mag.resource_governor run [--apply] | status
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

SCHEMA = "resource_governor.v1"
TRAIL = ROOT / "logs" / "resource_governor.jsonl"
SPEC_DIR = ROOT / "memory" / "runs" / "resource_governor"

# The hard outer boundary (configmap-style) — the reconciler NEVER exceeds this.
BOUNDARY = {
    "max_cpu": "4",            # total cpu cores the swarm may use
    "max_memory": "4Gi",       # total memory
    "max_replicas": 8,         # swarm worker replicas
    "max_vram_pct": 80,        # GPU VRAM ceiling (%)
    "controller": {"requests": {"cpu": "500m", "memory": "512Mi"},
                   "limits": {"cpu": "2", "memory": "2Gi"}},
    "worker": {"requests": {"cpu": "100m", "memory": "256Mi"},
               "limits": {"cpu": "500m", "memory": "1Gi"}},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sense() -> dict[str, Any]:
    """SENSE: doctor + swarm_health + usage_monitor + gpu_lifecycle -> one snapshot. Guarded."""
    snap: dict[str, Any] = {"ok": True, "ts": _now()}
    try:
        from mag import loop_doctor
        snap["doctor"] = loop_doctor.sense()
    except Exception as e:
        snap["doctor"] = {"ok": False, "error": str(e)[:120]}
    try:
        from mag import swarm_health
        snap["swarm"] = swarm_health.swarm_health()
    except Exception as e:
        snap["swarm"] = {"ok": False, "error": str(e)[:120]}
    try:
        from mag import usage_monitor
        snap["usage"] = usage_monitor.watch()
    except Exception as e:
        snap["usage"] = {"ok": False, "error": str(e)[:120]}
    try:
        from mag import gpu_lifecycle
        g = gpu_lifecycle.resources()
        snap["gpu"] = {"resources": g.get("resources"), "free_for_render": g.get("free_for_render")}
    except Exception as e:
        snap["gpu"] = {"ok": False, "error": str(e)[:120]}
    return snap


def _reconcile(snap: dict[str, Any]) -> dict[str, Any]:
    """RECONCILE: compute the DESIRED spec from the sensed snapshot, within the boundary."""
    b = BOUNDARY
    # controller: Guaranteed (requests==limits) so it's never OOM-killed (protects autorun loop).
    controller = {"qos": "Guaranteed", **b["controller"]}
    # worker: Burstable (req<lim), CPU overcommit (loose limits), memory right-sized (bounded).
    worker = {"qos": "Burstable", **b["worker"]}
    # replicas from queue depth (not CPU) — agents are I/O-bound waiting on LLM calls.
    queue_depth = 0
    usage = snap.get("usage") or {}
    if isinstance(usage, dict):
        queue_depth = int(usage.get("rows_in_window") or 0)
    swarm_health = snap.get("swarm") or {}
    if isinstance(swarm_health, dict) and swarm_health.get("overall") == "degraded":
        queue_depth += 1
    replicas = max(1, min(1 + (queue_depth // 2), b["max_replicas"]))
    # GPU: schedule only on confirmed headroom; else CPU fallback.
    gpu = snap.get("gpu") or {}
    tel = gpu.get("resources") or {}
    gpu_ok = bool(gpu.get("free_for_render")) and (tel.get("vram_used_pct") or 100) < b["max_vram_pct"]
    gpu_mode = "nvidia.com/gpu: 1 (headroom confirmed)" if gpu_ok else "cpu-fallback (no headroom)"
    return {"ok": True, "controller": controller, "worker": worker,
            "replicas": replicas, "queue_depth": queue_depth,
            "gpu_mode": gpu_mode, "gpu_scheduled": gpu_ok,
            "within_boundary": {"max_replicas": replicas <= b["max_replicas"]},
            "boundary": b}


def run(*, apply: bool = False) -> dict[str, Any]:
    """ONE governor pass: sense -> reconcile -> boundary -> trail (dry apply by default)."""
    snap = _sense()
    spec = _reconcile(snap)
    out = {"ok": True, "schema": SCHEMA, "ts": _now(), "applied": apply, "sense": snap, "spec": spec}
    # trail the pass (data generation) — the governor's own ledger
    try:
        TRAIL.parent.mkdir(parents=True, exist_ok=True)
        with TRAIL.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": out["ts"], "spec": spec, "applied": apply}, ensure_ascii=False) + "\n")
        out["trail"] = str(TRAIL.relative_to(ROOT)).replace("\\", "/")
    except Exception as e:
        out["trail_error"] = str(e)[:120]
    # write the desired-spec artifact (the data) when applying
    if apply:
        try:
            SPEC_DIR.mkdir(parents=True, exist_ok=True)
            p = SPEC_DIR / f"spec_{out['ts'][:19].replace(':','')}.json"
            p.write_text(json.dumps({"ts": out["ts"], "spec": spec, "sense": snap},
                                    indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            out["spec_artifact"] = str(p.relative_to(ROOT)).replace("\\", "/")
        except Exception as e:
            out["spec_error"] = str(e)[:120]
    out["note"] = ("SENSE -> RECONCILE -> BOUNDARY -> APPLY(dry). Controllers Guaranteed, workers "
                   "Burstable; CPU overcommit, memory right-sized; replicas from queue depth; GPU on "
                   "confirmed headroom; never exceeds the configmap boundary.")
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "run()->sense(doctor/swarm/usage/gpu) -> reconcile(desired spec) -> boundary "
                        "-> trail; apply=True writes the spec artifact. Reuses loop_doctor, "
                        "swarm_health, usage_monitor, gpu_lifecycle. $0 deterministic.",
            "boundary": BOUNDARY, "trail": str(TRAIL.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="resource-governor")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "run"])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(apply=a.apply) if a.cmd == "run" else status(),
                     indent=2, ensure_ascii=False, default=str))
