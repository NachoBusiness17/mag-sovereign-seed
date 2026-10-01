"""Vast training job-spec validation and cost-only dry runs (v5 V1)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from config import ROOT

CFG_PATH = ROOT / "configs" / "vast_train.yaml"


def load_config() -> dict[str, Any]:
    return yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}


def _resolve_export(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def validate_export(export_path: str | Path) -> dict[str, Any]:
    """Validate a redacted JSONL export and its signed sidecar manifest."""
    cfg = load_config().get("export") or {}
    path = _resolve_export(export_path)
    manifest_path = path.with_suffix(".manifest.json")
    errors: list[str] = []
    manifest: dict[str, Any] = {}
    if not path.is_file():
        errors.append("export JSONL not found")
    if not manifest_path.is_file():
        errors.append("export manifest not found")
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid manifest: {exc}")
    if manifest and manifest.get("schema") != cfg.get("required_manifest_schema"):
        errors.append("manifest schema mismatch")
    if manifest and manifest.get("source_schema") != cfg.get("required_source_schema"):
        errors.append("source schema mismatch")
    rows = 0
    digest = ""
    if path.is_file():
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        for line in raw.decode("utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"invalid JSONL row {rows + 1}")
                break
            rows += 1
            if row.get("schema") != cfg.get("required_source_schema"):
                errors.append(f"row {rows} schema mismatch")
                break
            if row.get("tier_max") not in {"T0", "T1", "T2"}:
                errors.append(f"row {rows} exceeds T2 export cap")
                break
    if rows < int(cfg.get("min_exported_rows") or 1):
        errors.append("export has too few rows")
    if manifest.get("n_exported") is not None and int(manifest["n_exported"]) != rows:
        errors.append("manifest row count mismatch")
    if manifest.get("sha256") and manifest["sha256"] != digest:
        errors.append("manifest sha256 mismatch")
    return {"ok": not errors, "path": str(path), "manifest_path": str(manifest_path), "rows": rows, "sha256": digest, "errors": errors}


def build_job_spec(export_path: str | Path, *, base_model: str | None = None, hyperparams: dict[str, Any] | None = None, max_hours: float | None = None) -> dict[str, Any]:
    cfg = load_config()
    model_id = base_model or str(cfg.get("default_base_model") or "")
    model = (cfg.get("base_models") or {}).get(model_id)
    if not model:
        return {"ok": False, "error": f"unknown base model: {model_id}"}
    hours = float(max_hours if max_hours is not None else cfg.get("default_max_hours") or 1)
    if hours <= 0 or hours > float(cfg.get("max_hours_per_job") or 24):
        return {"ok": False, "error": "max_hours exceeds configured bounds"}
    params = dict(model.get("default_hyperparams") or {})
    params.update(hyperparams or {})
    return {"ok": True, "schema": "mag_vast_train_job.v1", "export_path": str(_resolve_export(export_path)), "base_model": model_id, "hyperparams": params, "max_hours": hours, "min_gpu_ram_gb": int(model.get("min_gpu_ram_gb") or 0)}


def estimate_cost(spec: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    need = int(spec.get("min_gpu_ram_gb") or 0)
    candidates = []
    for gpu, rate in (cfg.get("gpu_hourly_rates_usd") or {}).items():
        ram = int(gpu.rsplit("_", 1)[-1].replace("gb", "")) if "gb" in gpu else 0
        if ram >= need:
            candidates.append((float(rate), gpu, ram))
    if not candidates:
        return {"ok": False, "error": f"no configured GPU satisfies {need}GB"}
    hourly, gpu, ram = min(candidates)
    total = round(hourly * float(spec["max_hours"]), 2)
    cap = float(cfg.get("max_usd_per_job") or 0)
    return {"ok": total <= cap, "gpu": gpu, "gpu_ram_gb": ram, "hourly_usd": hourly, "max_hours": spec["max_hours"], "estimated_max_usd": total, "spend_cap_usd": cap, "error": None if total <= cap else "estimate exceeds spend cap"}


def dry_run(export_path: str | Path, *, base_model: str | None = None, hyperparams: dict[str, Any] | None = None, max_hours: float | None = None) -> dict[str, Any]:
    validation = validate_export(export_path)
    spec = build_job_spec(export_path, base_model=base_model, hyperparams=hyperparams, max_hours=max_hours)
    estimate = estimate_cost(spec) if spec.get("ok") else {"ok": False, "error": spec.get("error")}
    return {"ok": bool(validation.get("ok") and spec.get("ok") and estimate.get("ok")), "schema": "mag_vast_train_dry.v1", "dry": True, "validation": validation, "job": spec, "estimate": estimate, "launched": False}
