"""Release registry — version gates + behavioral memory (release_milestone).

Machine truth: configs/releases.yaml
Operator gate log: memory/improve/releases/gates.jsonl
Training events: memory/training/events.jsonl (pattern release_milestone)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import CONFIGS_DIR, ROOT

REGISTRY_PATH = CONFIGS_DIR / "releases.yaml"
GATES_LOG = ROOT / "memory" / "improve" / "releases" / "gates.jsonl"
RELEASES_DIR = ROOT / "docs" / "ref" / "releases"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {"schema": "mag_releases.v1", "releases": []}
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("releases", [])
    return data


def get_release(version_id: str) -> dict[str, Any] | None:
    vid = (version_id or "").strip().lstrip("v")
    if not vid:
        return None
    for rel in load_registry().get("releases") or []:
        rid = str(rel.get("id") or "").lstrip("v")
        if rid == vid:
            return rel
    return None


def list_releases() -> list[dict[str, Any]]:
    return list(load_registry().get("releases") or [])


def notes_path(version_id: str) -> Path | None:
    rel = get_release(version_id)
    if not rel:
        return None
    p = rel.get("notes_path")
    return (ROOT / p) if p else None


def status_summary() -> dict[str, Any]:
    rows = []
    for rel in list_releases():
        vid = rel.get("id")
        gates = rel.get("gates") or []
        passed = _gates_passed_for(vid)
        regime = _regime_passed_for(vid)
        rows.append({
            "id": vid,
            "status": rel.get("status"),
            "era": rel.get("era"),
            "notes_path": rel.get("notes_path"),
            "gates_defined": len(gates),
            "gates_passed": len(passed),
            "gate_ids": [g.get("id") for g in gates if isinstance(g, dict)],
            # B2-209 display split: era milestones reported beside, never
            # inside, the graduation-gate count (VERSION_REGISTRY.md Regime
            # milestones: "not a graduation gate and never flips a version
            # to shipped")
            "regime_passed": len(regime),
            "regime_ids": regime,
        })
    return {"ok": True, "releases": rows, "registry": str(REGISTRY_PATH)}


# Mag subprocess analogs — steal from loops_registry + modules.yaml
SUBPROCESS_MAP: dict[str, dict[str, str]] = {
    "v1": {
        "analog": "remote_activation_seat",
        "layer": "viewport",
        "loop": "strike → LOAD pack",
        "trail": "docs/ref/strike_origin.md",
        "module": "dispatch / Grok TUI",
    },
    "v2": {
        "analog": "residual_dna + modules",
        "layer": "cold",
        "loop": "SessionEnd → registry",
        "trail": "memory/ · configs/modules.yaml",
        "module": "residual_dna, context_pack, improve",
    },
    "v3": {
        "analog": "orchestrator_run",
        "layer": "warm_mid",
        "loop": "fill → route → execute",
        "trail": "memory/runs/governor_autorun_trail.jsonl",
        "module": "orchestrator, governor_autorun, factory",
    },
    "v4": {
        "analog": "factory + conductor",
        "layer": "harness",
        "loop": "plan → freeze → audit → promote",
        "trail": "memory/runs/conductor_trail.jsonl",
        "module": "conductor, training_events, steward",
    },
    "v5": {
        "analog": "switchboard_peers",
        "layer": "meta",
        "loop": "mesh → route → optional seat",
        "trail": "configs/seat_playbook.yaml · mine/curated/",
        "module": "switchboard, seat_score (planned)",
    },
}


REGIME_PREFIX = "regime_"   # VERSION_REGISTRY.md Regime milestones: era milestone marker


def _gates_passed_for(version_id: str) -> list[str]:
    """Distinct PASSED graduation gates for a version. B2-209 (aligning this
    code with VERSION_REGISTRY.md, which already ruled regime milestones "not
    a graduation gate and never flips a version to shipped"): regime_ rows are
    excluded here so a version cannot drift toward shipped on era milestones;
    status_summary reports them beside the count."""
    vid = (version_id or "").strip().lstrip("v")
    out: list[str] = []
    for row in read_gate_log(limit=200, version=version_id):
        if row.get("ok") and row.get("gate_id"):
            gid = str(row["gate_id"])
            if gid.startswith(REGIME_PREFIX):
                continue
            if gid not in out:
                out.append(gid)
    return out


def _regime_passed_for(version_id: str) -> list[str]:
    """Distinct PASSED regime_ era milestones for a version (display split,
    B2-209). The mirror of _gates_passed_for: only regime_ rows count."""
    vid = (version_id or "").strip().lstrip("v")
    out: list[str] = []
    for row in read_gate_log(limit=200, version=version_id):
        if row.get("ok") and row.get("gate_id"):
            gid = str(row["gate_id"])
            if gid.startswith(REGIME_PREFIX) and gid not in out:
                out.append(gid)
    return out


def _path_exists(rel: str) -> bool:
    if not rel:
        return False
    p = ROOT / rel.split(" · ")[0].split()[0]
    return p.is_file() or p.is_dir()


def build_subprocess_map() -> dict[str, Any]:
    """Version registry enriched with Mag subprocess analogs (loops_registry style)."""
    releases_out: list[dict[str, Any]] = []
    for rel in list_releases():
        vid = str(rel.get("id") or "")
        sp = SUBPROCESS_MAP.get(vid, {})
        notes = rel.get("notes_path") or ""
        passed = _gates_passed_for(vid)
        gates = rel.get("gates") or []
        releases_out.append({
            **rel,
            "subprocess": sp,
            "notes_on_disk": _path_exists(notes),
            "gates_passed": passed,
            "gates_remaining": [
                g.get("id") for g in gates
                if isinstance(g, dict) and g.get("id") not in passed
            ],
        })
    return {
        "schema": "mag_version_subprocess.v1",
        "ts": _now(),
        "law": "Versions are runs with trails — not marketing labels.",
        "doc": "docs/ref/releases/MAG_VERSION_SUBPROCESS_MAP.md",
        "releases": releases_out,
        "operator_definitions": load_registry().get("operator_definitions") or {},
    }


def format_subprocess_text(reg: dict[str, Any] | None = None) -> str:
    r = reg or build_subprocess_map()
    lines = [
        f"# Mag version subprocess map ({r.get('ts', '')[:19]})",
        "",
        "| Ver | Status | Subprocess | Layer | Gates |",
        "|-----|--------|------------|-------|-------|",
    ]
    for row in r.get("releases") or []:
        sp = row.get("subprocess") or {}
        g_ok = len(row.get("gates_passed") or [])
        g_tot = len(row.get("gates") or [])
        lines.append(
            f"| {row.get('id')} | {row.get('status')} | {sp.get('analog', '—')} | "
            f"{sp.get('layer', '—')} | {g_ok}/{g_tot} |"
        )
    lines.extend(["", r.get("law") or "", "", f"Detail: {r.get('doc') or ''}"])
    return "\n".join(lines)


def _append_gate_log(row: dict[str, Any]) -> None:
    GATES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with GATES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def read_gate_log(*, limit: int = 50, version: str | None = None) -> list[dict[str, Any]]:
    if not GATES_LOG.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in GATES_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        if version and str(o.get("version", "")).lstrip("v") != version.lstrip("v"):
            continue
        out.append(o)
    return out[-limit:]


def record_gate(
    version: str,
    gate_id: str,
    *,
    ok: bool = True,
    note: str = "",
    evidence_path: str = "",
) -> dict[str, Any]:
    """Record a version graduation gate — FILE to gates.jsonl + training event."""
    rel = get_release(version)
    if not rel:
        return {"ok": False, "error": f"unknown version {version!r}"}
    vid = str(rel.get("id") or version)
    gid = (gate_id or "").strip()
    if not gid:
        return {"ok": False, "error": "gate_id required"}

    row = {
        "schema": "mag_release_gate.v1",
        "ts": _now(),
        "version": vid,
        "gate_id": gid,
        "ok": bool(ok),
        "note": (note or "")[:2000],
        "evidence_path": (evidence_path or "")[:500],
        "commitment": rel.get("commitment"),
    }
    _append_gate_log(row)

    gates_rel = str(GATES_LOG)
    try:
        gates_rel = str(GATES_LOG.relative_to(ROOT))
    except ValueError:
        pass

    try:
        from mag.training_events import emit

        emit(
            "release_milestone",
            join={"version": vid, "gate_id": gid},
            input_data={"version": vid, "gate_id": gid, "note": note[:500]},
            action={"kind": "gate_record", "ok": ok},
            outcome={"filed": True, "gates_log": gates_rel},
            pattern_tags=["release", vid, gid],
            tier_max="T2",
            exportable=True,
        )
    except Exception:
        pass

    return {"ok": True, "recorded": row}


def format_notes_text(version_id: str) -> str:
    p = notes_path(version_id)
    if not p or not p.is_file():
        return f"(no release notes at registry path for {version_id})"
    return p.read_text(encoding="utf-8", errors="replace")
