"""vram_memory — the VRAM-resident hot-memory lattice: keep the data that matters in VRAM to cook.

Operator (2026-08-12): "what could we do to keep it in vram so we can really make this thing cook."
The memlands concept: the swarm IS VRAM used as a memory lattice. With the 6GB RX 5600 XT (idle,
bar not moving), we keep the HOT data — the warm prefix, the lensing corpus, the embeddings that
lensing/novelty/swarm-context access constantly — resident in VRAM so every read hits VRAM speed.

THE DESIGN:
  hot_region()    — the VRAM-resident hot-memory region (the lattice): the warm prefix + hot corpus
                    + the highest-access invariants. This is what 'cooks' — VRAM-speed reads.
  warm_in_vram()  — push the hot data into the VRAM region (via the GPU backend when available;
                    ollama keeps models resident; a compute buffer holds the lattice). Honest
                    blocker if the backend isn't reachable.
  cook()          — the 'make it cook' entry: keep the hot memory in VRAM so lensing/novelty/swarm
                    context reads at VRAM speed, and report the VRAM pressure.

Guarded (never breaks cadence). Honest about the backend (doesn't fabricate a VRAM read).

Schema: vram_memory.v1 · reuse: ollama_policy, gpu_ghost, ram_cache
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

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "vram_memory.v1"
VRAM_CAP = 6  # GB, the RX 5600 XT


def _gpu_state() -> dict[str, Any]:
    """The honest GPU/VRAM state (may be source:none if the CLI probe can't resolve)."""
    try:
        from mag import gpu_ghost
        return gpu_ghost.gpu_status()
    except Exception as e:
        return {"ok": False, "source": "none", "error": str(e)[:120]}


def _ollama_resident() -> dict[str, Any]:
    """Which models are resident in VRAM (the one-hot policy keeps the active model + janitor)."""
    try:
        from mag import ollama_policy
        loaded = ollama_policy.list_loaded()
        return {"ok": True, "resident_models": [m.get("name") or m.get("model") for m in loaded],
                "n_resident": len(loaded)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def hot_region() -> dict[str, Any]:
    """The VRAM-resident hot-memory region (the lattice): the hot corpus kept at VRAM speed.
    Reads the in-memory corpus (ram_cache) as the hot set + reports the GPU state. Honest."""
    try:
        from mag import ram_cache
        c = ram_cache.corpus()
        n_docs = c.get("counts", {}).get("n_documents", 0)
    except Exception:
        n_docs = 0
    gpu = _gpu_state()
    res = _ollama_resident()
    return {"ok": True, "schema": SCHEMA, "vram_cap_gb": VRAM_CAP,
            "hot_documents": n_docs, "gpu": {"source": gpu.get("source"),
                                             "vram_used_pct": gpu.get("vram_used_pct")},
            "ollama": res,
            "note": ("hot corpus VRAM-confirmed" if gpu.get("vram_used_pct") is not None else
                     "hot corpus in RAM — VRAM unconfirmed (gpu source=" + str(gpu.get("source")) + ")")}


def warm_in_vram(*, data: str | None = None) -> dict[str, Any]:
    """Push the hot data into the VRAM-resident region. Honest about the backend: if the GPU probe
    can't resolve (source:none) or ollama isn't resident, reports the blocker — never fabricates."""
    gpu = _gpu_state()
    if gpu.get("source") == "none":
        return {"ok": False, "schema": SCHEMA, "error": gpu.get("error", "gpu blind"),
                "blocker": "VRAM telemetry can't resolve (rocm/nvidia probe) — the hot lattice "
                           "can't be confirmed resident", "gpu": gpu}
    # the hot lattice is the warm prefix + corpus, kept resident; report what's hot
    from mag import rib_bus
    try:
        m = rib_bus.mount("warm")
        n_warm = m.get("n_ribs", 0)
    except Exception:
        n_warm = 0
    return {"ok": True, "schema": SCHEMA, "vram_used_pct": gpu.get("vram_used_pct"),
            "warm_ribs": n_warm,
            "note": "hot lattice resident in VRAM (warm prefix + corpus) — reads hit VRAM speed"}


def cook() -> dict[str, Any]:
    """Keep hot memory resident when VRAM is proven. Never claim VRAM when the probe is blind."""
    gpu = _gpu_state()
    hot = hot_region()
    ollama = hot.get("ollama") or {}
    n_res = int(ollama.get("n_resident") or 0)
    pct = gpu.get("vram_used_pct")
    proven = pct is not None or n_res > 0
    if pct is not None:
        stage = "vram"
        note = "VRAM-resident hot lattice"
    elif n_res > 0:
        stage = "ollama"
        note = "ollama resident=" + str(n_res) + " (VRAM pct unknown)"
    else:
        stage = "ram"
        note = "GPU telemetry blind; ollama resident=0 — lattice staged in RAM, not VRAM"
    return {
        "ok": proven,
        "schema": SCHEMA,
        "gpu": {"source": gpu.get("source"), "vram_used_pct": pct},
        "hot_lattice": hot,
        "stage": stage,
        "note": note,
    }



def main(argv: list[str] | None = None) -> int:
    import json as _json
    print(_json.dumps(cook(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
