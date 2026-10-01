"""GSTD forest probe — MIT DePIN seat readiness (v5 pipe, safe to run now).

Read-only: health check, clone inventory, local Ollama baseline, route recommendation.
Logs training events for L-conductor / switchboard distillation.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from config import ROOT

REPORT_PATH = ROOT / "memory" / "improve" / "gstd_probe_report.json"
GSTD_API = os.environ.get("GSTD_API_URL", "https://app.gstdtoken.com").rstrip("/")
CLONE_ROOTS = (
    ROOT / "reference" / "gstdcoin",
    ROOT / "mine" / "raw" / "gstdcoin",
)
EXPECTED_REPOS = ("ai", "web", "A2A", "gstdbot", "contracts", "gstd-bridge")


def _utc_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _http_json(url: str, *, timeout: float = 12.0) -> tuple[int, dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw.strip() else {"error": raw[:200]}
        except json.JSONDecodeError:
            body = {"error": raw[:200]}
        return exc.code, body
    except Exception as exc:
        return 0, {"ok": False, "error": str(exc)[:200]}


def _local_ollama_bench() -> dict[str, Any]:
    from mag.desk_model_probe import _bench_model

    from models.registry import model_for

    model = model_for("desk_orchestrator")
    return _bench_model(model, timeout=90)


def _clone_inventory() -> dict[str, Any]:
    root = None
    for candidate in CLONE_ROOTS:
        if candidate.is_dir():
            root = candidate
            break
    if not root:
        return {"ok": False, "root": None, "repos": [], "n": 0}

    repos: list[dict[str, Any]] = []
    for name in EXPECTED_REPOS:
        path = root / name
        repos.append({"name": name, "present": path.is_dir(), "path": str(path)})
    present = sum(1 for r in repos if r["present"])
    return {
        "ok": present >= 3,
        "root": str(root),
        "repos": repos,
        "n": present,
        "refresh": "scripts/pull_gstdcoin_repos.cmd",
    }


def _gstd_health() -> dict[str, Any]:
    t0 = time.perf_counter()
    code, body = _http_json(f"{GSTD_API}/api/v1/health")
    ms = round((time.perf_counter() - t0) * 1000)
    return {
        "ok": code == 200,
        "http": code,
        "latency_ms": ms,
        "api": GSTD_API,
        "body": body if isinstance(body, dict) else {"raw": str(body)[:200]},
        "has_api_key": bool(os.environ.get("GSTD_API_KEY")),
    }


def _gstd_stats() -> dict[str, Any]:
    """Probe GET /api/v1/stats (Phase T0 read-only shadow)."""
    t0 = time.perf_counter()
    code, body = _http_json(f"{GSTD_API}/api/v1/stats")
    ms = round((time.perf_counter() - t0) * 1000)
    return {
        "ok": code == 200,
        "http": code,
        "latency_ms": ms,
        "api": GSTD_API,
        "body": body if isinstance(body, dict) else {"raw": str(body)[:200]},
    }


def _route_recommendation(
    *,
    local: dict[str, Any],
    gstd: dict[str, Any],
    clones: dict[str, Any],
) -> dict[str, Any]:
    local_ok = bool(local.get("ok")) or bool(local.get("tokens_per_sec"))
    local_tps = local.get("tokens_per_sec") or 0
    gstd_ok = bool(gstd.get("ok"))

    if local_ok and local_tps >= 8 and (local.get("gpu_pct") or 0) >= 80:
        primary = "local"
        reason = f"local desk fast enough ({local_tps} t/s, GPU {local.get('gpu_pct')}%)"
    elif local_ok:
        primary = "local"
        reason = "local ok but slow — tune model or ctx before GSTD default"
    elif gstd_ok:
        primary = "gstd"
        reason = "local failed — probe GSTD worker when API key enrolled"
    else:
        primary = "deepseek"
        reason = "local + GSTD probe down — use remote for judgment"

    return {
        "primary": primary,
        "fallback": "deepseek" if primary != "deepseek" else "local",
        "reason": reason,
        "gstd_ready": gstd_ok and clones.get("n", 0) >= 3,
        "test_next": (
            "Run gstdbot edge with OLLAMA_HOST=127.0.0.1:11434"
            if clones.get("n", 0) >= 3
            else "scripts/pull_gstdcoin_repos.cmd"
        ),
    }


def run_gstd_probe(*, bench_local: bool = True) -> dict[str, Any]:
    clones = _clone_inventory()
    gstd = _gstd_health()
    stats = _gstd_stats()
    local: dict[str, Any] = {"ok": False, "skipped": True}
    if bench_local:
        try:
            local = _local_ollama_bench()
        except Exception as exc:
            local = {"ok": False, "error": str(exc)[:200]}

    route = _route_recommendation(local=local, gstd=gstd, clones=clones)
    report = {
        "ok": True,
        "ts": _utc_iso(),
        "schema": "mag_gstd_probe.v1",
        "clones": clones,
        "gstd_health": gstd,
        "gstd_stats": stats,
        "local_bench": local,
        "route": route,
        "note": "Probe only — does not register node or spend GSTD credits",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    from mag.training_events import emit

    emit(
        "route_decision",
        join={"seat": "gstd-inference", "phase": "v5_probe"},
        input_data={
            "gstd_ok": gstd.get("ok"),
            "clones_n": clones.get("n"),
            "local_model": local.get("model"),
        },
        action={"route_primary": route.get("primary"), "test_next": route.get("test_next")},
        outcome={
            "local_tps": local.get("tokens_per_sec"),
            "local_gpu_pct": local.get("gpu_pct"),
            "gstd_latency_ms": gstd.get("latency_ms"),
            "reason": route.get("reason"),
        },
        pattern_tags=["gstd_probe", f"route_{route.get('primary')}"],
    )
    report["report_path"] = str(REPORT_PATH)
    return report


def build_gstd_stack_row() -> dict[str, Any]:
    """Lightweight row for Stack research strip — no full bench."""
    clones = _clone_inventory()
    code, _ = _http_json(f"{GSTD_API}/api/v1/health", timeout=4.0)
    st = "ok" if code == 200 else ("idle" if clones.get("n") else "offline")
    return {
        "id": "gstd_probe",
        "label": "GSTD probe",
        "status": st,
        "text": (
            f"API {'up' if code == 200 else 'down'} · {clones.get('n', 0)}/{len(EXPECTED_REPOS)} repos"
        ),
        "api": "python main.py probe gstd",
        "proof": str(REPORT_PATH),
    }
