"""gpu_k8s — read GPU telemetry from inside Kubernetes, fold it as a verkle knot.

WHY (2026-08-11, operator): the GPU lives in Kubernetes (a cluster node/resource), so the
host ghost process is GPU-blind (rocm-smi/nvidia-smi return nothing -> source:"none"). This
adapts ghost's mem tools to the k8s GPU through the architecture's OWN channels:

  - mag.k8s_bridge.exec_read  -> read rocm-smi/nvidia-smi INSIDE a cluster pod (kubectl exec).
  - mag.verkle_knot           -> fold each sample as a content-addressed gpu_telemetry knot
                                 (stable session_id, amends in place, ties back via parent root).
  - mag.verkle_bus            -> publish to mag:verkle so seats/mem tools react in real time.
  - telemetry ledger          -> memory/runs/gpu_ghost/telemetry.jsonl (readable live numbers).

Contract: gpu_k8s.v1 · deterministic · $0 · graceful when k8s unreachable (source stays "none").
STEAL 2026-08-11: host gpu_status() is the fast path; this is the k8s/verkle fallback that turns
GPU state into durable, content-addressed fleet memory readable by any seat / mem tool.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "gpu_k8s.v1"
LEDGER = ROOT / "memory" / "runs" / "gpu_ghost" / "telemetry.jsonl"
GPU_SESSION_PREFIX = "gpu:k8s"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_minute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


# ── pod discovery ───────────────────────────────────────────────────────────
def find_gpu_pod() -> dict[str, Any]:
    """Locate a GPU-capable pod in ns mag: MAG_GPU_POD, MAG_GPU_POD_LABEL, or auto."""
    cfg = _env("MAG_GPU_POD")
    if cfg:
        return {"ok": True, "pod": cfg, "source": "env"}
    try:
        from mag.k8s_bridge import pods
        label = _env("MAG_GPU_POD_LABEL")
        p = pods(label or None)
        if not p.get("ok"):
            return {"ok": False, "error": (p.get("stderr") or p.get("stdout") or "")[:200]}
        lines = (p.get("stdout") or "").splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[2] == "Running":
                name = parts[0]
                if "gpu" in name.lower() or "ollama" in name.lower():
                    return {"ok": True, "pod": name, "source": "auto"}
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[2] == "Running":
                return {"ok": True, "pod": parts[0], "source": "auto-first"}
        return {"ok": False, "error": "no Running pod in ns mag"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ── telemetry read ──────────────────────────────────────────────────────────
def read_telemetry(pod: str) -> dict[str, Any]:
    """Read rocm-smi (fallback nvidia-smi) INSIDE the pod via k8s_bridge.exec_read."""
    try:
        from mag.k8s_bridge import exec_read
        r = exec_read(
            pod,
            "rocm-smi --showmeminfo vram --showuse --showtemp --json 2>/dev/null || "
            "nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu "
            "--format=csv,noheader,nounits",
        )
        if not r.get("ok") or not (r.get("stdout") or "").strip():
            return {"ok": False, "source": "none",
                    "error": (r.get("stderr") or r.get("stdout") or "")[:200], "pod": pod}
        raw = r["stdout"].strip()
        try:
            cards = json.loads(raw)
            c = list(cards.values())[0] if isinstance(cards, dict) else cards[0]
            used = float(c.get("VRAM", c).get("Used", 0))
            total = float(c.get("VRAM", c).get("Total", 1))
            tel = {"vram_used_pct": round(100.0 * used / max(total, 1), 1),
                   "temp_c": float(c.get("Temperature", -1)),
                   "util_pct": float(c.get("GPU", c).get("Use", 0)),
                   "source": f"k8s:{pod}"}
        except Exception:
            p = raw.split(",")
            if len(p) >= 4:
                tel = {"vram_used_pct": round(100.0 * float(p[0]) / max(float(p[1]), 1), 1),
                       "temp_c": float(p[2]), "util_pct": float(p[3]),
                       "source": f"k8s:{pod}"}
            else:
                return {"ok": False, "source": "none",
                        "error": f"unparseable telemetry: {raw[:120]}", "pod": pod}
        tel["ok"] = True
        tel["pod"] = pod
        return tel
    except Exception as e:
        return {"ok": False, "source": "none", "error": str(e)[:200], "pod": pod}


# ── fold to verkle knot + ledger + bus ──────────────────────────────────────
def _fold_verkle(tel: dict[str, Any]) -> dict[str, Any]:
    """Append a content-addressed gpu_telemetry knot (stable session -> amend in place)."""
    try:
        from mag.verkle_knot import append_verkle_knot
        session_id = f"{GPU_SESSION_PREFIX}:{tel.get('pod', 'unknown')}"
        vram = tel.get("vram_used_pct") or 0.0
        util = tel.get("util_pct") or 0.0
        dossier = {
            "session_id": session_id,
            "time": {
                "created_at": {"iso_minute": _iso_minute(), "unix_minute": None, "date": None},
                "updated_at": {"iso_minute": _iso_minute(), "unix_minute": None, "date": None},
            },
            "scalar_knot": {
                "duration_minutes": 0.1,
                "tension_index": str(vram)[:8],
                "residual_weight": 1.0,
                "theme_vector": {
                    "dominant": "gpu_telemetry",
                    "basis": ["gpu", "harness", "biography", "constitution"],
                    "raw": [vram, util, 0.3, 0.0],
                    "normalized": [0.6, 0.3, 0.1, 0.0],
                },
            },
            "content_commit": {"hex": str(tel.get("temp_c") or "")[:8]},
            "gpu_telemetry": {k: v for k, v in tel.items() if k != "ok"},
        }
        return append_verkle_knot(dossier)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _append_ledger(tel: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), **{k: v for k, v in tel.items() if k != "ok"}}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def sample(*, pod: str | None = None, fold: bool = True) -> dict[str, Any]:
    """Read GPU telemetry from k8s, fold it as a verkle knot + ledger, return telemetry."""
    if pod:
        fp = {"ok": True, "pod": pod}
    else:
        fp = find_gpu_pod()
    if not fp.get("ok"):
        return {"ok": False, "schema": SCHEMA, "source": "none", "error": fp.get("error", "")}
    tel = read_telemetry(fp["pod"])
    if not tel.get("ok"):
        return {"ok": False, "schema": SCHEMA, "source": "none",
                "error": tel.get("error", ""), "pod": fp["pod"]}
    _append_ledger(tel)
    knot: dict[str, Any] = {}
    if fold:
        knot = _fold_verkle(tel)
        try:
            from mag.verkle_bus import publish_sync, CH_VERKLE
            publish_sync(CH_VERKLE, {"type": "gpu_telemetry", "ts": _now(),
                                     "source": tel.get("source"),
                                     "vram_used_pct": tel.get("vram_used_pct")})
        except Exception:
            pass
    return {"ok": True, "schema": SCHEMA, "telemetry": tel, "knot": knot}


def status() -> dict[str, Any]:
    """Read the latest GPU telemetry from the ledger — the mem-tool surface for GPU state."""
    tel: dict[str, Any] = {"vram_used_pct": None, "temp_c": None, "util_pct": None,
                           "source": "none", "free": None}
    try:
        if LEDGER.is_file():
            rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8", errors="replace")
                    .splitlines() if l.strip()]
            if rows:
                tel.update(rows[-1])
                tel.pop("ts", None)
                tel.pop("ok", None)
                tel.pop("pod", None)
    except Exception:
        pass
    if tel.get("vram_used_pct") is not None or tel.get("util_pct") is not None:
        v = tel.get("vram_used_pct") or 0
        u = tel.get("util_pct") or 0
        tel["free"] = bool(v < 70 and u < 70)
    else:
        tel["free"] = None
    return tel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gpu-k8s",
                                 description="Read GPU telemetry from Kubernetes via verkle knots.")
    ap.add_argument("cmd", nargs="?", choices=["sample", "status", "find"], default="status")
    ap.add_argument("--pod", default="")
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        print(json.dumps(sample(pod=a.pod or None), indent=2, default=str))
    elif a.cmd == "find":
        print(json.dumps(find_gpu_pod(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["sample", "status", "find_gpu_pod", "read_telemetry", "main"]
