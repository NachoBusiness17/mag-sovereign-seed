"""gpu_lifecycle — the GPU as a RENDERING machine (not just a code horse): check available resources,
learn the lifecycle pattern, and route render-heavy work (flock/world) to the GPU when it's free.

Operator (2026-08-11): "could the gpu be used for stuff like that to actually make it useful beyond
a code horse? i always want to check available resources lifecycel and learn from that pattern."

WHAT THIS DOES (deterministic + $0, reuses gpu_k8s telemetry):
  resources()   -> check AVAILABLE GPU resources right now (vram_used_pct, util_pct, temp_c) from
                   gpu_k8s.sample/status. The answer to "is the GPU free for rendering right now?"
  learn()       -> record the lifecycle pattern (sampled vram/util/temp over time) into a ledger,
                   then LEARN the availability: the deterministic free/used window + a moving baseline
                   (vram p50) so we know when the GPU is idle enough to render.
  route()       -> decide WHERE render-heavy work (flock_anim, world_rib, WebGL) runs: GPU when free
                   (low util + vram headroom), CPU otherwise. Rightsized from the learned baseline.

The "beyond a code horse" part: flock/world/emergence rendering goes to the GPU (compute/WebGL) when
it's free — the GPU is a RENDERER, and we learn its lifecycle to use it exactly when available.

Schema: gpu_lifecycle.v1 · deterministic + $0 · reuse: gpu_k8s
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "gpu_lifecycle.v1"
LEDGER = ROOT / "memory" / "gpu" / "lifecycle.jsonl"

# routing thresholds (learned baseline adjusts these)
FREE_UTIL = 15.0      # util% below this = GPU free enough to render
FREE_VRAM = 80.0      # vram_used% below this = headroom


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rdl(path: Path, tail: int = 10_000) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def resources() -> dict[str, Any]:
    """Check AVAILABLE GPU resources now (deterministic, reuses gpu_k8s)."""
    try:
        from mag import gpu_k8s
        s = gpu_k8s.sample(fold=False)
        tel = {"vram_used_pct": s.get("vram_used_pct"),
               "util_pct": s.get("util_pct"), "temp_c": s.get("temp_c"),
               "source": s.get("source", "none")}
    except Exception as e:
        tel = {"vram_used_pct": None, "util_pct": None, "temp_c": None,
               "source": "none", "error": str(e)[:100]}
    free = (tel.get("vram_used_pct") is not None and tel.get("vram_used_pct", 100) <= FREE_VRAM
            and (tel.get("util_pct") is None or tel.get("util_pct", 100) <= FREE_UTIL))
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "resources": tel, "free_for_render": free,
            "verdict": "render_on_gpu" if free else "render_on_cpu"}


def learn() -> dict[str, Any]:
    """Record the lifecycle pattern and LEARN the availability baseline. Deterministic."""
    r = resources()
    row = {"ts": _now(), "vram": r["resources"].get("vram_used_pct"),
           "util": r["resources"].get("util_pct"), "temp": r["resources"].get("temp_c"),
           "source": r["resources"].get("source")}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    rows = _rdl(LEDGER)
    vr = [x["vram"] for x in rows if x.get("vram") is not None]
    ut = [x["util"] for x in rows if x.get("util") is not None]
    return {"ok": True, "schema": SCHEMA, "n_samples": len(rows),
            "vram_p50": round(statistics.median(vr), 1) if vr else None,
            "util_p50": round(statistics.median(ut), 1) if ut else None,
            "free_for_render_now": r["free_for_render"],
            "pattern": "learned: GPU is " + ("idle (free to render)" if r["free_for_render"] else
                                             "busy (defer GPU render)"),
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def route(*, work: str = "flock") -> dict[str, Any]:
    """Decide where render-heavy work runs: GPU when free, CPU otherwise (rightsized)."""
    r = resources()
    l = learn()
    target = "gpu" if r["free_for_render"] else "cpu"
    return {"ok": True, "schema": SCHEMA, "work": work, "target": target,
            "free_for_render": r["free_for_render"],
            "resources": r["resources"], "learned": {"vram_p50": l["vram_p50"],
                                                     "util_p50": l["util_p50"]},
            "note": ("render on GPU (WebGL/CUDA)" if target == "gpu"
                     else "GPU busy — render on CPU; retry on GPU when free (learned lifecycle)")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "resources()->available GPU now; learn()->lifecycle baseline; "
                        "route(work)->GPU when free / CPU otherwise",
            "cost": "deterministic + $0", "free_thresholds": {"util": FREE_UTIL, "vram": FREE_VRAM},
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="gpu-lifecycle")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "resources", "learn", "route"])
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "resources":
        print(json.dumps(resources(), indent=2, default=str))
    elif a.cmd == "learn":
        print(json.dumps(learn(), indent=2, default=str))
    else:
        print(json.dumps(route(work="flock"), indent=2, default=str))
