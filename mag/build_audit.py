"""Factory build audit JSON writer — build_audit.v1 on disk (RUN B pilot)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "build_audit.v1"
AUDIT_DIR = ROOT / "memory" / "runs" / "build_audit"
FACTORY_DIR = ROOT / "memory" / "factory"

VALID_VERDICTS = frozenset({"pass", "fix", "reject", "pending"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_diff_stat() -> str:
    try:
        r = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()[-2000:]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def build_record(
    slug: str,
    *,
    verdict: str = "pending",
    spec_path: str = "",
    commands: list[str] | None = None,
    diff_stat: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    v = (verdict or "pending").strip().lower()
    if v not in VALID_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VALID_VERDICTS)}")
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("slug required")
    return {
        "schema": SCHEMA,
        "slug": slug,
        "verdict": v,
        "spec_path": (spec_path or "")[:500],
        "diff_stat": (diff_stat if diff_stat is not None else _git_diff_stat())[:4000],
        "commands": [str(c)[:500] for c in (commands or [])][:20],
        "timestamp": _now(),
        "note": (note or "")[:2000],
    }


def write_audit(
    slug: str,
    *,
    verdict: str = "pending",
    spec_path: str = "",
    commands: list[str] | None = None,
    diff_stat: str | None = None,
    note: str = "",
    dry: bool = False,
) -> dict[str, Any]:
    rec = build_record(
        slug,
        verdict=verdict,
        spec_path=spec_path,
        commands=commands,
        diff_stat=diff_stat,
        note=note,
    )
    rel_path = AUDIT_DIR / f"{slug}.json"
    try:
        path_display = str(rel_path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        path_display = str(rel_path).replace("\\", "/")
    if dry:
        return {
            "ok": True,
            "dry": True,
            "record": rec,
            "path": path_display,
        }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    FACTORY_DIR.mkdir(parents=True, exist_ok=True)
    rel_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    factory_path = FACTORY_DIR / f"build_audit-{slug}.json"
    factory_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        from mag.training_events import emit

        emit(
            "factory_cycle",
            join={"build_slug": slug, "verdict": rec["verdict"]},
            input_data={"slug": slug, "spec_path": rec["spec_path"]},
            action={"kind": "build_audit_write", "verdict": rec["verdict"]},
            outcome={"path": str(rel_path.relative_to(ROOT)).replace("\\", "/")},
            pattern_tags=["factory", "build_audit", rec["verdict"]],
            tier_max="T2",
            exportable=True,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "path": str(rel_path.relative_to(ROOT)).replace("\\", "/"),
        "factory_path": str(factory_path.relative_to(ROOT)).replace("\\", "/"),
        "record": rec,
    }


def load_audit(slug: str) -> dict[str, Any] | None:
    slug = (slug or "").strip()
    if not slug:
        return None
    candidates = [
        AUDIT_DIR / f"{slug}.json",
        FACTORY_DIR / f"build_audit-{slug}.json",
    ]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            o = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(o, dict):
            return o
    return None
