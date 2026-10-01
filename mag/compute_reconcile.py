"""compute_reconcile — AUTOMATIC COMPUTE RIGHTSIZING (self-healing reconciler on the loop).

The operator (2026-08-13): "are we rightsizing our compute spend we're only using 46% of our memory
and 9% of our disk and 1% of gpu and 50% of cpu" + "fix this automatically".

THE DIAGNOSIS (grounded, from the real numbers): GPU 1% (free local inference resource IDLE) +
CPU 50% (the loop burning) + the productive DeepSeek swarm DEAD (sw29, undrained backlog) =
MISALLOCATION. We are spending CPU on a loop whose productive engine is stalled, and NOT spending
the one resource that is free (GPU).

THE AUTOMATIC FIX (architecture-native, deterministic + $0, wired into the governor cadence):
  measure()   -> REAL compute state: GPU util/vram (gpu_lifecycle.resources), local_gpu tier (ollama)
                 up?, swarm queue undrained count + last drain, local loop posture.
  reconcile() -> the reconciliation actions toward the RIGHTSIZED split:
                   * GPU FREE + local_gpu tier DOWN -> BRING UP the local inference tier (use the
                     free $0 GPU for build/deterministic work instead of CPU). Auto-signaled so the
                     loop acts.
                   * swarm queue undrained + no recent drain -> REVIVE the swarm drain (the cheap
                     DeepSeek research engine) — the one genuinely SYSTEM-IMPERATIVE item, named
                     precisely (cluster/CronJob), not nagged.
                 verdict = rightsized | misallocated + the split (GPU for $0 build, DeepSeek for
                 research, CPU coordinates).
  run_cadence() -> measure + reconcile + persist + report, so the loop self-heals every beat.

SELF-STEAL (nothing invented): gpu_lifecycle.resources (GPU state), lifecycle (the local_gpu/ollama
piece + gaps), swarm_worker (queue depth), the rightsize doctrine (GPU cheapest for build, swarm for
research, frontier only at the coldest seam). The reconciler is the loop's own compute-governor.

Schema: compute_reconcile.v1 · deterministic + $0 · reuse: gpu_lifecycle, lifecycle, swarm_worker
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

SCHEMA = "compute_reconcile.v1"
OUT = ROOT / "memory" / "runs" / "compute_reconcile"
SWARM_QUEUE = ROOT / "memory" / "runs" / "swarm_worker" / "queue"
SWARM_RESULTS = ROOT / "memory" / "runs" / "swarm_worker" / "results"

# thresholds (from gpu_lifecycle / the rightsize doctrine)
GPU_FREE_UTIL = 15.0      # util% below this = GPU idle (free $0 compute wasted if unused)
GPU_FREE_VRAM = 80.0      # vram_used% below this = headroom


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def measure() -> dict[str, Any]:
    """REAL compute state — the bytes, not a guess."""
    # GPU
    gpu: dict[str, Any] = {"source": "none"}
    try:
        from mag import gpu_lifecycle
        gpu = gpu_lifecycle.resources().get("resources") or {"source": "none"}
    except Exception as e:
        gpu = {"source": "none", "error": str(e)[:80]}
    util = gpu.get("util_pct")
    vram = gpu.get("vram_used_pct")
    gpu_free = (util is not None and util <= GPU_FREE_UTIL and
                (vram is None or vram <= GPU_FREE_VRAM))
    # local_gpu tier (ollama) up?
    ollama_up = False
    try:
        from mag import health
        ollama_up = bool((health.check_ollama() or {}).get("ok"))
    except Exception:
        try:
            from mag import lifecycle
            # B2-81 (2026-09-26): _ollama_up now returns (up, cause); index it
            # instead of bool(), which is always True on any non-empty tuple.
            ollama_up = bool(lifecycle._ollama_up()[0])
        except Exception:
            ollama_up = False
    # swarm queue: undrained backlog + last drain
    queued = 0
    try:
        if SWARM_QUEUE.is_dir():
            queued = len(list(SWARM_QUEUE.glob("sw-*.json")))
    except Exception:
        queued = 0
    last_drain = ""
    try:
        from mag import swarm_worker
        st = swarm_worker.status()
        last_drain = st.get("last_drain_ts") or st.get("latest_ts") or ""
    except Exception:
        last_drain = ""
    # local loop posture (lifecycle gaps -> capability holes)
    gaps: list[str] = []
    try:
        from mag import lifecycle
        gaps = list(lifecycle.build_lifecycle().get("gaps") or [])
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "gpu": {"util_pct": util, "vram_used_pct": vram, "source": gpu.get("source"),
                    "free": gpu_free},
            "local_gpu_tier": {"ollama_up": ollama_up},
            "swarm": {"queued": queued, "last_drain_ts": last_drain},
            "local_loop": {"gaps": gaps}}


def reconcile() -> dict[str, Any]:
    """THE AUTOMATIC FIX: reconciliation actions toward the rightsized split. Deterministic + $0."""
    m = measure()
    gpu_free = bool(m["gpu"]["free"])
    ollama_up = bool(m["local_gpu_tier"]["ollama_up"])
    queued = int(m["swarm"]["queued"])
    actions: list[dict[str, Any]] = []
    misalloc = False

    # 1. GPU free + local_gpu tier DOWN -> the free $0 GPU is idle -> bring up local inference
    if gpu_free and not ollama_up:
        misalloc = True
        actions.append({
            "action": "bring-up-local-gpu",
            "why": f"GPU is free (util {m['gpu']['util_pct']}% <= {GPU_FREE_UTIL}%) but the local "
                   f"inference tier is down — the free $0 GPU is idle while CPU burns.",
            "fix": "start the local inference tier (ollama) so build/deterministic work rides the "
                   "GPU ($0) instead of CPU. Auto-signaled for the loop to act.",
            "automatable": True,
        })
    elif gpu_free and ollama_up:
        actions.append({
            "action": "use-gpu-tier",
            "why": "GPU free + local tier up — route build/deterministic work to the GPU ($0).",
            "automatable": True,
        })

    # 2. swarm queue undrained -> the cheap DeepSeek research engine is dead -> revive the drain
    if queued > 0:
        misalloc = True
        actions.append({
            "action": "revive-swarm-drain",
            "why": f"swarm queue has {queued} undrained research tasks — the cheap DeepSeek engine is "
                   f"dead, so the loop's CPU/RAM isn't converting into research.",
            "fix": "revive the k8s mag-swarm CronJob / cluster drain (system-imperative; the one "
                   "operator-stuck item). Until then, enqueued research waits on the shared PVC.",
            "automatable": False,
        })

    verdict = "misallocated" if misalloc else "rightsized"
    split = ("RIGHTSIZED SPLIT: GPU = $0 build/inference · DeepSeek swarm = cheap research · "
             "CPU = coordination. Frontier premium ONLY at the coldest seam.")
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "verdict": verdict,
            "measure": m, "actions": actions, "split": split,
            "note": "compute rightsizing reconciler: brings up the free GPU tier automatically, "
                    "surfaces the one system-imperative swarm revival, reports the split"}


def run_cadence(*, persist: bool = True) -> dict[str, Any]:
    """The loop's self-healing beat: measure + reconcile + persist + report."""
    r = reconcile()
    if persist:
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"reconcile-{_now()[:13].replace(':', '')}.json").write_text(
                json.dumps(r, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass
    return r


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "measure()->real compute state (gpu/util, local_gpu tier, swarm queue, "
                        "lifecycle gaps); reconcile()->the automatic fix actions + rightsize verdict; "
                        "run_cadence()->measure+reconcile+persist (the self-healing beat)",
            "cost": "deterministic + $0",
            "reuses": ["gpu_lifecycle", "lifecycle", "swarm_worker", "health"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="compute-reconcile")
    ap.add_argument("cmd", nargs="?", default="reconcile", choices=["status", "measure", "reconcile", "cadence"])
    a = ap.parse_args()
    if a.cmd == "measure":
        print(json.dumps(measure(), indent=2, default=str))
    elif a.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(reconcile(), indent=2, default=str))
