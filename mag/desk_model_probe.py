"""Desk model A/B probe — gemma4-desk vs qwen-desk on local GPU."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from config import ROOT, ollama_base

REPORT_PATH = ROOT / "memory" / "working" / "desk_model_probe.json"
PROBE_PROMPT = (
    "You are the desk local orchestrator. Reply with exactly two sections:\n"
    "### Reply\nOne sentence acknowledging the operator note.\n"
    "### Canvas edit\n### Local · probe\n- one bullet next step\n"
)
CANDIDATES = (
    ("gemma4-desk", "gemma4-desk"),
    ("qwen-desk", "qwen-desk"),
)


def _base() -> str:
    return ollama_base().rstrip("/")


def _tags() -> list[str]:
    try:
        with urllib.request.urlopen(f"{_base()}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [str(m.get("name") or "") for m in (data.get("models") or []) if m.get("name")]
    except Exception:
        return []


def _has_model(name: str, tags: list[str]) -> bool:
    base = name.split(":")[0]
    return name in tags or any(t == name or t.startswith(base + ":") for t in tags)


def ensure_qwen_desk(*, pull: bool = True) -> dict[str, Any]:
    tags = _tags()
    if _has_model("qwen-desk", tags):
        return {"ok": True, "model": "qwen-desk", "action": "exists"}

    base = "qwen2.5:3b-instruct"
    if pull and not _has_model(base, tags):
        proc = subprocess.run(
            ["ollama", "pull", base],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            cwd=str(ROOT),
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": "pull failed",
                "stderr": (proc.stderr or "")[:300],
            }

    mf = f"""FROM qwen2.5:3b-instruct
PARAMETER num_ctx 8192
PARAMETER temperature 0.35
PARAMETER top_p 0.9
"""
    mf_path = ROOT / "memory" / "working" / "Modelfile.qwen-desk"
    mf_path.parent.mkdir(parents=True, exist_ok=True)
    mf_path.write_text(mf, encoding="utf-8")
    proc = subprocess.run(
        ["ollama", "create", "qwen-desk", "-f", str(mf_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        cwd=str(ROOT),
    )
    return {
        "ok": proc.returncode == 0,
        "model": "qwen-desk",
        "action": "created",
        "stderr": (proc.stderr or "")[:200],
    }


def _gpu_pct_for(model: str) -> float | None:
    try:
        with urllib.request.urlopen(f"{_base()}/api/ps", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for m in data.get("models") or []:
            if not isinstance(m, dict):
                continue
            if str(m.get("name", "")).startswith(model.split(":")[0]):
                size = float(m.get("size") or 0)
                vram = float(m.get("size_vram") or 0)
                if size and vram:
                    return round(100 * vram / size, 1)
    except Exception:
        pass
    return None


def _bench_model(model: str, *, timeout: float = 120.0) -> dict[str, Any]:
    from mag.ollama_policy import enforce_one_hot

    enforce_one_hot(keep=model, also_keep_janitor=False)
    payload = {
        "model": model,
        "prompt": PROBE_PROMPT,
        "stream": False,
        "keep_alive": "2m",
        "options": {"num_predict": 256, "temperature": 0.35},
    }
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(
            f"{_base()}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        text = str(data.get("response") or "")
        eval_ns = int(data.get("eval_duration") or 0)
        load_ns = int(data.get("load_duration") or 0)
        eval_count = int(data.get("eval_count") or 0)
        tps = round(eval_count / (eval_ns / 1e9), 1) if eval_ns and eval_count else None
        has_reply = "### Reply" in text or "### reply" in text.lower()
        has_canvas = "### Canvas edit" in text or "### Local" in text
        return {
            "ok": bool(text.strip()),
            "model": model,
            "elapsed_ms": elapsed_ms,
            "load_ms": round(load_ns / 1e6) if load_ns else None,
            "eval_ms": round(eval_ns / 1e6) if eval_ns else None,
            "tokens_per_sec": tps,
            "gpu_pct": _gpu_pct_for(model),
            "has_reply": has_reply,
            "has_canvas": has_canvas,
            "preview": text[:240],
        }
    except Exception as exc:
        return {
            "ok": False,
            "model": model,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
            "error": str(exc)[:200],
        }


def run_probe(*, pull_qwen: bool = True) -> dict[str, Any]:
    tags = _tags()
    if not tags:
        return {"ok": False, "error": "Ollama unreachable"}

    setup: list[dict[str, Any]] = []
    if pull_qwen and not _has_model("qwen-desk", tags):
        setup.append(ensure_qwen_desk(pull=True))

    results: list[dict[str, Any]] = []
    for _label, model in CANDIDATES:
        if not _has_model(model, _tags()) and model == "qwen-desk":
            results.append({"ok": False, "model": model, "error": "qwen-desk missing after setup"})
            continue
        if not _has_model(model, _tags()) and model == "gemma4-desk":
            results.append({"ok": False, "model": model, "error": "run scripts/setup_desk_gpu.ps1 first"})
            continue
        results.append(_bench_model(model))

    ok_rows = [r for r in results if r.get("ok")]
    winner = None
    if ok_rows:
        winner = sorted(
            ok_rows,
            key=lambda r: (
                -(r.get("tokens_per_sec") or 0),
                r.get("elapsed_ms") or 999999,
                -(r.get("gpu_pct") or 0),
            ),
        )[0]["model"]

    report = {
        "ok": bool(ok_rows),
        "winner": winner,
        "candidates": results,
        "setup": setup,
        "recommendation": (
            f"Set desk_orchestrator: {winner} in configs/lanes.yaml"
            if winner
            else "No successful probe — check Ollama models"
        ),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    from mag.training_events import emit

    emit(
        "route_decision",
        join={"probe": "desk_model_ab", "hardware": "RX5600XT_6GB"},
        input_data={"candidates": [c[1] for c in CANDIDATES]},
        action={"winner": winner},
        outcome={
            "results": [
                {
                    "model": r.get("model"),
                    "tps": r.get("tokens_per_sec"),
                    "gpu_pct": r.get("gpu_pct"),
                    "elapsed_ms": r.get("elapsed_ms"),
                    "ok": r.get("ok"),
                }
                for r in results
            ]
        },
        pattern_tags=["desk_model_probe", f"winner_{winner or 'none'}"],
    )
    report["report_path"] = str(REPORT_PATH)
    return report
