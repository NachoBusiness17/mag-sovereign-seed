"""Steal protocol forest probe — clone inventory for orchestrator research repos."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import ROOT

REPORT_PATH = ROOT / "memory" / "improve" / "steal_protocol_probe_report.json"
CLONE_ROOTS = (
    ROOT / "mine" / "raw" / "steal_protocol",
)
EXPECTED = (
    "robzilla1738/agentswarm",
    "arvarik/bmas",
    "whiteducksoftware/flock",
    "hemantsingh443/blackboard-core",
    "Bradliebs/ollama-agent-harness",
    "marikarx/subagent-router",
    "Leeroo-AI/leeroo_orchestrator",
    "EIT-EAST-Lab/C3",
    "togethercomputer/moa",
    "microsoft/conductor",
    "claudioed/agent-blackboard",
)


def _clone_inventory() -> dict[str, Any]:
    root = None
    for candidate in CLONE_ROOTS:
        if candidate.is_dir():
            root = candidate
            break
    if not root:
        return {"ok": False, "root": None, "repos": [], "n": 0, "refresh": "scripts/pull_steal_protocol_repos.cmd"}

    repos: list[dict[str, Any]] = []
    for sub in EXPECTED:
        path = root / sub
        repos.append({"path": sub, "present": path.is_dir(), "abs": str(path)})
    present = sum(1 for r in repos if r["present"])
    return {
        "ok": present >= 3,
        "root": str(root),
        "repos": repos,
        "n": present,
        "expected": len(EXPECTED),
        "refresh": "scripts/pull_steal_protocol_repos.cmd",
    }


def run_steal_protocol_probe() -> dict[str, Any]:
    from datetime import datetime, timezone

    clones = _clone_inventory()
    out = {
        "ok": clones.get("ok"),
        "schema": "steal_protocol_probe.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "clones": clones,
        "index": "docs/ref/STEAL_PROTOCOL_REPOS_INDEX.md",
        "manifest": "configs/steal_protocol_repos.yaml",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def build_steal_stack_row() -> dict[str, Any]:
    inv = _clone_inventory()
    n = inv.get("n") or 0
    exp = inv.get("expected") or len(EXPECTED)
    st = "ok" if n >= exp else ("partial" if n else "offline")
    return {
        "id": "steal_protocol_forest",
        "label": "Steal protocol forest",
        "status": st,
        "text": f"{n}/{exp} repos · {inv.get('refresh')}",
    }
