"""Local model pulse — CPU + Ollama process signal for 'thinking' display.

Combines:
  - Ollama /api/ps (model loaded)
  - Ollama/llama process CPU (psutil when available)
  - System CPU spike (operator-calibrated proxy for gemma inference)
  - Desk session flag (memory/working/local_thinking.json) during _invoke_local_llm

Schema: mag_local_pulse.v1
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_local_pulse.v1"
THINKING_FLAG = ROOT / "memory" / "working" / "local_thinking.json"
DEFAULT_PROC_CPU = float(os.environ.get("MAG_LOCAL_PROC_CPU", "25"))
DEFAULT_SYS_CPU = float(os.environ.get("MAG_LOCAL_SYS_CPU", "55"))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_local_thinking(*, active: bool, model: str = "", source: str = "desk") -> None:
    THINKING_FLAG.parent.mkdir(parents=True, exist_ok=True)
    if not active:
        try:
            THINKING_FLAG.unlink(missing_ok=True)
        except OSError:
            pass
        return
    THINKING_FLAG.write_text(
        json.dumps(
            {"active": True, "ts": _utc(), "model": model, "source": source},
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_desk_flag() -> dict[str, Any]:
    if not THINKING_FLAG.is_file():
        return {}
    try:
        return json.loads(THINKING_FLAG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ollama_ps(timeout: float = 0.6) -> dict[str, Any]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        models = data.get("models") if isinstance(data, dict) else []
        enriched: list[dict[str, Any]] = []
        for m in models or []:
            if not isinstance(m, dict):
                continue
            size = float(m.get("size") or 0)
            vram = float(m.get("size_vram") or 0)
            gpu_pct = round(100.0 * vram / size, 1) if size > 0 and vram > 0 else None
            enriched.append(
                {
                    "name": m.get("name"),
                    "size_gb": round(size / 1e9, 2) if size else None,
                    "vram_gb": round(vram / 1e9, 2) if vram else None,
                    "gpu_pct": gpu_pct,
                    "context_length": m.get("context_length"),
                }
            )
        return {"ok": True, "models": enriched, "raw": models or [], "n": len(enriched)}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "models": [], "n": 0, "error": str(exc)[:120]}


def _cpu_samples() -> dict[str, Any]:
    out: dict[str, Any] = {"system_pct": None, "ollama_proc_pct": None, "procs": []}
    try:
        import psutil

        out["system_pct"] = round(float(psutil.cpu_percent(interval=0.12)), 1)
        proc_total = 0.0
        names: list[str] = []
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if "ollama" not in name and "llama" not in name:
                continue
            try:
                pct = proc.cpu_percent(interval=0.0)
            except Exception:
                pct = 0.0
            if pct:
                proc_total += float(pct)
                names.append(name)
        out["ollama_proc_pct"] = round(proc_total, 1)
        out["procs"] = sorted(set(names))
    except Exception as exc:
        out["error"] = str(exc)[:120]
    return out


def build_local_pulse(
    *,
    proc_threshold: float | None = None,
    sys_threshold: float | None = None,
) -> dict[str, Any]:
    proc_thr = DEFAULT_PROC_CPU if proc_threshold is None else proc_threshold
    sys_thr = DEFAULT_SYS_CPU if sys_threshold is None else sys_threshold

    ps = _ollama_ps()
    cpu = _cpu_samples()
    desk = _read_desk_flag()

    sys_cpu = cpu.get("system_pct")
    proc_cpu = cpu.get("ollama_proc_pct")
    models = ps.get("models") or []
    model_names = [str(m.get("name") or "?") for m in models if isinstance(m, dict)]
    desk_model = (desk.get("model") or "").strip()
    active_gpu = None
    for m in models:
        if not isinstance(m, dict):
            continue
        if desk_model and m.get("name") != desk_model and not str(m.get("name", "")).startswith(desk_model.split(":")[0]):
            continue
        if m.get("gpu_pct") is not None:
            active_gpu = m
            break
    if active_gpu is None and models:
        active_gpu = models[0] if isinstance(models[0], dict) else None

    desk_active = bool(desk.get("active"))
    gpu_pct = (active_gpu or {}).get("gpu_pct")
    gpu_thinking = gpu_pct is not None and gpu_pct >= 15 and desk_active
    proc_hot = proc_cpu is not None and proc_cpu >= proc_thr
    sys_hot = sys_cpu is not None and sys_cpu >= sys_thr and bool(model_names) and (gpu_pct is None or gpu_pct < 50)
    cpu_thinking = proc_hot or sys_hot

    thinking = desk_active or cpu_thinking or gpu_thinking

    if thinking:
        state = "thinking"
    elif ps.get("ok") and model_names:
        state = "loaded"
    elif ps.get("ok"):
        state = "idle"
    else:
        state = "offline"

    sources: list[str] = []
    if desk_active:
        sources.append("desk_session")
    if proc_hot:
        sources.append("ollama_proc_cpu")
    if sys_hot:
        sources.append("system_cpu")
    if gpu_thinking:
        sources.append("gpu_vram")

    headline = {
        "thinking": "Local · thinking",
        "loaded": "Local · model loaded",
        "idle": "Local · idle",
        "offline": "Local · Ollama offline",
    }[state]

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "state": state,
        "thinking": thinking,
        "headline": headline,
        "cpu": {
            "system_pct": sys_cpu,
            "ollama_proc_pct": proc_cpu,
            "procs": cpu.get("procs") or [],
            "proc_threshold": proc_thr,
            "sys_threshold": sys_thr,
        },
        "ollama_ps": {
            "ok": ps.get("ok"),
            "models": model_names[:5],
            "n_loaded": len(model_names),
            "active": active_gpu,
        },
        "gpu": {
            "vram_pct": gpu_pct,
            "vram_gb": (active_gpu or {}).get("vram_gb"),
            "size_gb": (active_gpu or {}).get("size_gb"),
            "context_length": (active_gpu or {}).get("context_length"),
            "note": "RX 5600 XT 6GB — gemma4@65536 ctx spills to CPU; use gemma4-desk@8192",
        },
        "desk_session": {
            "active": desk_active,
            "model": desk.get("model"),
            "source": desk.get("source"),
            "since": desk.get("ts"),
        },
        "sources": sources,
        "note": "CPU spike + desk flag = thinking; REST-only signal for Stack/Desk/Display.",
    }
