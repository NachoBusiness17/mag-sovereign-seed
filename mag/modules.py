"""Module registry + compose-status — modular upgrades & retrocausal health.

Loads configs/modules.yaml. Does not invent DNA. Reports contract status.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import CONFIGS_DIR, ROOT

CFG = CONFIGS_DIR / "modules.yaml"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_modules_config() -> dict[str, Any]:
    if not CFG.is_file():
        return {"schema": "mag_modules.v1", "modules": {}, "invariants": [], "edges": []}
    data = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    data.setdefault("modules", {})
    data.setdefault("invariants", [])
    data.setdefault("edges", [])
    return data


def _path_ok(rel: str) -> bool:
    p = ROOT / rel
    return p.exists()


def check_module(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    path = str(spec.get("path") or "")
    also = list(spec.get("also") or [])
    missing = []
    if path and not _path_ok(path):
        missing.append(path)
    for a in also:
        if not _path_ok(str(a)):
            missing.append(str(a))
    return {
        "name": name,
        "layer": spec.get("layer"),
        "path": path,
        "ok": len(missing) == 0,
        "missing": missing,
        "provides": list(spec.get("provides") or []),
        "depends_on": list(spec.get("depends_on") or []),
        "upgrade": spec.get("upgrade"),
        "retrocausal": spec.get("retrocausal"),
        "debt": spec.get("debt"),
    }


def check_runtime_compose() -> dict[str, Any]:
    """Live checks for compose steals (not just file presence)."""
    checks: dict[str, Any] = {}

    # residual core
    try:
        from mag.registry import CORE_INVARIANTS, RESIDUAL_DIR

        checks["residual_dir"] = RESIDUAL_DIR.is_dir()
        checks["core_invariants"] = list(CORE_INVARIANTS)
    except Exception as e:
        checks["residual_error"] = str(e)

    # run / related
    try:
        from mag.run_trail import RELATED, RUNS, load_active, list_related_runs, status

        st = status()
        checks["runs_dir"] = RUNS.is_dir()
        checks["active_run"] = (st.get("active") or {}).get("run_id")
        checks["related_runs_n"] = len(list_related_runs(last_n=50))
        checks["related_ledger"] = RELATED.is_file()
    except Exception as e:
        checks["run_error"] = str(e)

    # bonds
    bonds = ROOT / "memory" / "bonds_active.json"
    checks["bonds_active"] = bonds.is_file()
    if bonds.is_file():
        try:
            bj = json.loads(bonds.read_text(encoding="utf-8"))
            checks["bonds_related_runs_n"] = len(bj.get("related_runs") or [])
        except Exception:
            checks["bonds_related_runs_n"] = None

    # tip sessions only (file exists)
    tip = ROOT / "memory" / "biography" / "verkle_tip.json"
    checks["verkle_tip"] = tip.is_file()
    if tip.is_file():
        try:
            t = json.loads(tip.read_text(encoding="utf-8"))
            checks["tip_n_leaves"] = t.get("n_leaves")
            checks["tip_note"] = (t.get("note") or "")[:120]
        except Exception:
            pass

    # improve / compose leaves
    evals = ROOT / "memory" / "improve" / "evals"
    checks["model_tesuji_leaves"] = (
        len(list((evals / "models").glob("*.md"))) if (evals / "models").is_dir() else 0
    )
    checks["feature_compose_leaves"] = (
        len(list((evals / "features").glob("*.md"))) if (evals / "features").is_dir() else 0
    )

    return checks


def compose_status() -> dict[str, Any]:
    cfg = load_modules_config()
    modules = cfg.get("modules") or {}
    checked = [check_module(n, modules[n] if isinstance(modules[n], dict) else {}) for n in modules]
    checked.sort(key=lambda x: (0 if x.get("ok") else 1, x.get("name") or ""))
    runtime = check_runtime_compose()
    bad = [c for c in checked if not c.get("ok")]
    return {
        "ok": len(bad) == 0,
        "schema": cfg.get("schema"),
        "version": cfg.get("version"),
        "ts": _utc(),
        "cold_vertex": cfg.get("cold_vertex"),
        "tip_policy": cfg.get("tip_policy"),
        "invariants": cfg.get("invariants"),
        "modules": checked,
        "n_modules": len(checked),
        "n_missing_paths": len(bad),
        "edges": cfg.get("edges"),
        "runtime": runtime,
        "upgrade_order": [
            "1. residual_dna (never break core)",
            "2. run_trail / bonds (warm-mid)",
            "3. context_pack / dispatch (viewports + harness)",
            "4. improve / feature_compose (lenses)",
            "5. cli / dashboard last (thin)",
        ],
        "retrocausal_note": (
            "Future: amend residual + re-synth improve + bonds re-ingest past runs. "
            "Never strip core; tip = sessions only; run_commit is child edge."
        ),
    }


def format_compose_status(st: dict[str, Any] | None = None) -> str:
    s = st or compose_status()
    lines = [
        f"# Mag compose-status ({(s.get('ts') or '')[:19]})",
        f"ok={s.get('ok')} · modules={s.get('n_modules')} · missing_paths={s.get('n_missing_paths')}",
        f"cold_vertex={s.get('cold_vertex')} · tip_policy={s.get('tip_policy')}",
        "",
        "## Invariants",
    ]
    for inv in s.get("invariants") or []:
        if isinstance(inv, dict):
            lines.append(f"- **{inv.get('id')}:** {inv.get('rule')}")
    lines.extend(["", "## Modules"])
    for m in s.get("modules") or []:
        mark = "OK" if m.get("ok") else "MISS"
        debt = f" · debt: {m.get('debt')}" if m.get("debt") else ""
        lines.append(
            f"- [{mark}] **{m.get('name')}** ({m.get('layer')}) `{m.get('path')}`{debt}"
        )
        if m.get("missing"):
            lines.append(f"  missing: {m.get('missing')}")
    rt = s.get("runtime") or {}
    lines.extend(
        [
            "",
            "## Runtime compose",
            f"- active_run: `{rt.get('active_run')}`",
            f"- related_runs_n: {rt.get('related_runs_n')}",
            f"- bonds_related_runs_n: {rt.get('bonds_related_runs_n')}",
            f"- tip_n_leaves: {rt.get('tip_n_leaves')}",
            f"- tesuji_leaves: {rt.get('model_tesuji_leaves')} · feature_leaves: {rt.get('feature_compose_leaves')}",
            "",
            "## Upgrade order",
        ]
    )
    for u in s.get("upgrade_order") or []:
        lines.append(f"- {u}")
    lines.extend(["", "## Retrocausal", s.get("retrocausal_note") or "", ""])
    return "\n".join(lines)


def attach_related_runs_to_residual(
    session_id: str | None = None,
    *,
    last_n: int = 12,
) -> dict[str, Any]:
    """Retrocausal edge: write related_runs onto residual without stripping core.

    Adds/updates residual['edges']['related_runs'] only. Never deletes core fields.
    """
    from mag.registry import find_residual, load_residual, residual_path, write_residual
    from mag.run_trail import list_related_runs

    # resolve session
    sid = session_id
    if not sid:
        latest = ROOT / "memory" / "biography" / "latest_session.json"
        if latest.is_file():
            try:
                sid = (json.loads(latest.read_text(encoding="utf-8")) or {}).get("session_id")
            except Exception:
                sid = None
    if not sid:
        bj = ROOT / "memory" / "bonds_active.json"
        if bj.is_file():
            try:
                sid = (json.loads(bj.read_text(encoding="utf-8")) or {}).get("session_id")
            except Exception:
                pass
    if not sid:
        return {"ok": False, "error": "no_session_id"}

    d = load_residual(str(sid))
    if not d:
        return {"ok": False, "error": "residual_not_found", "session_id": sid}

    runs = list_related_runs(last_n=last_n)
    # cards only — no full trail payloads in residual (tip stays clean)
    cards = [
        {
            "run_id": r.get("run_id"),
            "goal": r.get("goal"),
            "seat": r.get("seat"),
            "run_commit": r.get("run_commit"),
            "close_reason": r.get("close_reason"),
            "n_events": r.get("n_events"),
            "path": r.get("path"),
            "closed": r.get("closed"),
        }
        for r in runs
        if isinstance(r, dict)
    ]

    edges = dict(d.get("edges") or {})
    edges["related_runs"] = cards
    edges["related_runs_updated"] = _utc()
    d["edges"] = edges
    # do not touch d["core"] — write_residual → attach_cold_core preserves it

    try:
        out = write_residual(str(sid), d)
    except Exception as e:
        p = find_residual(str(sid)) or residual_path(str(sid))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
        return {
            "ok": True,
            "session_id": sid,
            "n_runs": len(cards),
            "path": str(p),
            "warn": str(e),
        }

    return {
        "ok": True,
        "session_id": sid,
        "n_runs": len(cards),
        "path": (out or {}).get("path") or str(find_residual(str(sid))),
        "content_hash": (out or {}).get("content_hash"),
    }
