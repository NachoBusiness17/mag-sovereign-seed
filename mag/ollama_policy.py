"""Ollama load policy — one-hot GPU on 6GB AMD (RX 5600 XT).

Keeps janitor (gemma:2b) + one active role model; evicts others from VRAM.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any

from config import ROOT, ollama_base

JANITOR = os.environ.get("MAG_JANITOR_MODEL", "gemma:2b")
DESK_DEFAULT = os.environ.get("MAG_DESK_MODEL", "gemma4-desk")
KEEP_ALIVE = os.environ.get("MAG_OLLAMA_KEEP", "gemma:2b,gemma4-desk,qwen-desk")


def _base() -> str:
    return ollama_base().rstrip("/")


def list_loaded() -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{_base()}/api/ps", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m for m in (data.get("models") or []) if isinstance(m, dict)]
    except Exception:
        return []


def _ollama_stop(model: str) -> dict[str, Any]:
    name = (model or "").strip()
    if not name:
        return {"ok": False, "error": "empty model"}
    try:
        proc = subprocess.run(
            ["ollama", "stop", name],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ROOT),
        )
        return {
            "ok": proc.returncode == 0,
            "model": name,
            "stdout": (proc.stdout or "").strip()[:200],
            "stderr": (proc.stderr or "").strip()[:200],
        }
    except Exception as exc:
        return {"ok": False, "model": name, "error": str(exc)[:200]}


def enforce_one_hot(*, keep: str | None = None, also_keep_janitor: bool = True) -> dict[str, Any]:
    """Unload all loaded models except keep (+ janitor if also_keep_janitor)."""
    if os.environ.get("MAG_OLLAMA_ONE_HOT", "1").strip().lower() in ("0", "false", "no", "off"):
        return {"ok": True, "skipped": True, "reason": "MAG_OLLAMA_ONE_HOT off"}

    primary = (keep or DESK_DEFAULT).strip()
    allowed = {primary.split(":")[0], primary}
    if also_keep_janitor:
        allowed.add(JANITOR)
        allowed.add(JANITOR.split(":")[0])

    loaded = list_loaded()
    stopped: list[dict[str, Any]] = []
    kept: list[str] = []

    for m in loaded:
        name = str(m.get("name") or "")
        base = name.split(":")[0]
        if name in allowed or base in allowed:
            kept.append(name)
            continue
        stopped.append(_ollama_stop(name))

    return {
        "ok": True,
        "keep": primary,
        "janitor": JANITOR if also_keep_janitor else None,
        "kept": kept,
        "stopped": stopped,
        "n_loaded_before": len(loaded),
        "n_stopped": sum(1 for s in stopped if s.get("ok")),
    }


def ensure_desk_model(model: str | None = None) -> dict[str, Any]:
    """One-hot for desk turn — evict hermes/full gemma4, keep desk + janitor."""
    target = (model or DESK_DEFAULT).strip()
    out = enforce_one_hot(keep=target, also_keep_janitor=True)
    out["desk_model"] = target
    return out


def status() -> dict[str, Any]:
    loaded = list_loaded()
    rows = []
    for m in loaded:
        size = float(m.get("size") or 0)
        vram = float(m.get("size_vram") or 0)
        rows.append(
            {
                "name": m.get("name"),
                "size_gb": round(size / 1e9, 2) if size else None,
                "vram_gb": round(vram / 1e9, 2) if vram else None,
                "gpu_pct": round(100 * vram / size, 1) if size and vram else None,
                "context_length": m.get("context_length"),
            }
        )
    return {
        "ok": True,
        "janitor": JANITOR,
        "desk_default": DESK_DEFAULT,
        "one_hot": os.environ.get("MAG_OLLAMA_ONE_HOT", "1") not in ("0", "false", "no", "off"),
        "loaded": rows,
        "n_loaded": len(rows),
    }
