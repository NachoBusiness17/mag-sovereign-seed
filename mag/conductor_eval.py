"""Deterministic evaluation harness for the L-conductor policy."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT
from mag.conductor import detect_phase, phase_policy

SUITE_PATH = ROOT / "configs" / "conductor_eval.yaml"
EVAL_DIR = ROOT / "memory" / "improve" / "evals" / "conductor"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_suite(path: Path = SUITE_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("cases", [])
    return data


def _check_case(case: dict[str, Any]) -> dict[str, Any]:
    goal = str(case.get("goal") or "")
    expected = dict(case.get("expect") or {})
    phase = detect_phase(goal)
    overlay = phase_policy(goal, phase=phase, base=dict(case.get("base") or {}))
    actual = {
        "phase": phase,
        "suggested_seat": overlay.get("suggested_seat"),
        "factory_gate_ok": (overlay.get("factory_gate") or {}).get("ok"),
        "tier": (overlay.get("factory_gate") or {}).get("tier"),
        "note": overlay.get("conductor_note") or "",
    }
    failures: list[str] = []
    for key in ("phase", "suggested_seat", "factory_gate_ok", "tier"):
        if key in expected and actual.get(key) != expected.get(key):
            failures.append(f"{key}: expected {expected.get(key)!r}, got {actual.get(key)!r}")
    if expected.get("note_contains") and str(expected["note_contains"]).lower() not in actual["note"].lower():
        failures.append(f"note missing {expected['note_contains']!r}")
    return {
        "id": case.get("id"),
        "ok": not failures,
        "goal": goal,
        "expected": expected,
        "actual": actual,
        "failures": failures,
    }


def run_eval(*, write: bool = True, suite_path: Path = SUITE_PATH) -> dict[str, Any]:
    suite = load_suite(suite_path)
    results = [_check_case(case) for case in suite.get("cases") or []]
    passed = sum(1 for row in results if row["ok"])
    total = len(results)
    score = passed / total if total else 0.0
    threshold = float(suite.get("threshold") or 1.0)
    now = datetime.now(timezone.utc)
    report = {
        "schema": "conductor_eval.v1",
        "ts": now.isoformat(),
        "suite": _display_path(suite_path),
        "gate": suite.get("gate") or "conductor_eval",
        "ok": bool(total) and score >= threshold,
        "score": round(score, 4),
        "threshold": threshold,
        "passed": passed,
        "total": total,
        "results": results,
    }
    if write:
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        dated = EVAL_DIR / f"{now.date().isoformat()}.json"
        dated.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (EVAL_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["path"] = _display_path(dated)
    return report
