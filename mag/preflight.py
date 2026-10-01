"""Pre-flight Check — verify the stack is ready before boot.

Runs before docker compose up or Ghost daemon start. Catches the most
common failure modes: missing .env, broken imports, missing directories,
Docker issues, chain discipline violations.

SCHEMA: preflight.v1
LAW: Never boot without a clean pre-flight. Red = stop, fix, re-check.
LAW: Pre-flight is zero-cost. No API calls. No side effects.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PreFlightResult:
    """Result of pre-flight check."""
    go: bool                    # can we boot?
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "go": self.go,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "ts": self.ts,
        }


def run_preflight() -> PreFlightResult:
    """Run all pre-flight checks. Returns go/no-go."""
    result = PreFlightResult(go=True)

    # ── 1. .env check ──
    env_path = ROOT / ".env"
    result.checks[".env exists"] = env_path.is_file()
    if not result.checks[".env exists"]:
        result.errors.append(".env file missing — copy from .env.example or create one with API keys")
        result.go = False
    else:
        # Check for at least one API key
        env_text = env_path.read_text(encoding="utf-8")
        has_deepseek = "DEEPSEEK_API_KEY=" in env_text and "DEEPSEEK_API_KEY=sk-" in env_text
        has_grok = "XAI_API_KEY=" in env_text and "XAI_API_KEY=xai-" in env_text
        result.checks["deepseek_key_set"] = has_deepseek
        result.checks["grok_key_set"] = has_grok
        if not has_deepseek and not has_grok:
            result.warnings.append("No API keys detected — only local Ollama models will work")

    # ── 2. Directory structure ──
    required_dirs = ["memory", "logs", "state", "queue", "configs"]
    for d in required_dirs:
        p = ROOT / d
        exists = p.is_dir()
        result.checks[f"dir:{d}"] = exists
        if not exists:
            result.warnings.append(f"Directory {d}/ missing — will be created at boot")

    # ── 3. Constitution check ──
    const_paths = [
        ROOT.parent / "mycelial-republic" / "docs" / "CONSTITUTION.md",
        ROOT / "CONSTITUTION.md",
    ]
    const_found = any(p.is_file() for p in const_paths)
    result.checks["constitution_found"] = const_found
    if not const_found:
        result.warnings.append("CONSTITUTION.md not found — constitutional critique will be disabled")

    # ── 4. Module import chain ──
    modules = [
        "mag.ghost_ledger",
        "mag.tokenomics",
        "mag.frontier_scout",
        "mag.constitutional_critique",
        "mag.context_compression",
        "mag.context_checkpoint",
        "mag.mixture_of_agents",
        "mag.dspy_sovereign",
        "mag.task_router",
        "mag.vast_launcher",
        "mag.lora_pipeline",
        "mag.copilot_bridge",
    ]
    import_ok = True
    for mod in modules:
        try:
            __import__(mod)
            result.checks[f"import:{mod}"] = True
        except Exception as e:
            result.checks[f"import:{mod}"] = False
            result.errors.append(f"Import failed: {mod} — {str(e)[:100]}")
            import_ok = False
    if not import_ok:
        result.go = False

    # ── 5. Python version ──
    import sys
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    result.checks["python_version"] = sys.version_info >= (3, 11)
    if not result.checks["python_version"]:
        result.errors.append(f"Python {py_ver} — need 3.11+")
        result.go = False
    else:
        result.checks["python_version"] = True

    # ── 6. Docker check (optional) ──
    docker_available = False
    try:
        import shutil
        docker_available = shutil.which("docker") is not None
    except Exception:
        pass
    result.checks["docker_available"] = docker_available
    if not docker_available:
        result.warnings.append("Docker not found — can't use docker compose up. Use python mag_launch.py instead.")

    # ── 7. Chain discipline ──
    try:
        from mag.chain_query import chain
        tail = chain.tail(5)
        result.checks["chain_discipline"] = True
        result.checks["chain_entries"] = len(tail)
    except Exception:
        result.checks["chain_discipline"] = False
        result.warnings.append("Chain query failed — doctor check recommended before boot")

    # ── 8. Training data check ──
    training_data = ROOT / "memory" / "training" / "sovereign_training_data.jsonl"
    result.checks["training_data_exists"] = training_data.is_file()
    if training_data.is_file():
        lines = training_data.read_text(encoding="utf-8").strip().splitlines()
        result.checks["training_examples"] = len(lines)

    # ── Summary ──
    passes = sum(1 for v in result.checks.values() if v)
    total = len(result.checks)
    result.checks["preflight_score"] = f"{passes}/{total} checks passed"

    return result


def preflight_dashboard() -> dict[str, Any]:
    """Run pre-flight and return dashboard-ready result."""
    pf = run_preflight()
    return {
        "schema": "preflight.v1",
        "go": pf.go,
        "score": pf.checks.get("preflight_score", "?"),
        "errors": pf.errors,
        "warnings": pf.warnings,
        "checks": {k: v for k, v in pf.checks.items() if k != "preflight_score"},
        "boot_command": (
            "docker compose up -d --build"
            if pf.checks.get("docker_available")
            else "python mag_launch.py"
        ),
        "ts": pf.ts,
    }
