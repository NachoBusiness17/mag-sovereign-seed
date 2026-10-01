"""Surface audit — deterministic inventory of every execution surface.

Companion to the full surface audit (memory/runs/surface_audit/AUDIT-2026-08-09.md).
The framework_map seams check *integrity*; this module enumerates the *surface
split* (CLI, dashboard REST, cast/voice REST, launchers, providers, loops,
extension commands, dashboard tabs) live from code so it never goes stale.

Display+tracking research (memory/research_packs/20260809T_surface-display-and-tracking-research.md):
  - one source of truth -> N surfaces (Surface Hub in VS Code, dashboard panel, CLI)
  - version-stamped snapshot so viewers detect staleness
  - agent-authored inline-SVG charts (donut of group counts)

Schema: surface_audit.v1
Consumed by: REST GET /api/v1/surface-audit · VS Code Surface Hub view · dashboard.
LAW: read-only, deterministic, no LLM.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "surface_audit.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _version(ts: str) -> str:
    return ts.replace(":", "").replace("-", "").replace("+00:00", "Z").split(".")[0]


def _cast_routes() -> int:
    txt = _read(ROOT / "mag" / "cast_server.py")
    m = re.search(r"_ALLOWED\s*=\s*frozenset\s*\(\s*\{(.*?)\}", txt, re.S)
    if not m:
        return 0
    return len(re.findall(r'"([^"]+)"', m.group(1)))


def _loops() -> int:
    txt = _read(ROOT / "mag" / "loops_registry.py")
    return len(re.findall(r'"id"\s*:\s*"([A-Za-z0-9_\-]+)"', txt))


def _ext_commands() -> int:
    pkg = ROOT / "vscode-mag-map" / "package.json"
    if not pkg.is_file():
        return 0
    try:
        return len(json.loads(pkg.read_text(encoding="utf-8")).get("contributes", {}).get("commands", []))
    except Exception:
        return 0


def _dashboard_tabs() -> int:
    idx = ROOT / "dashboard" / "static" / "index.html"
    if not idx.is_file():
        return 0
    return len(set(re.findall(r'data-open-tab="([^"]+)"', _read(idx))))


def _launchers() -> int:
    return len(list(ROOT.glob("*.cmd"))) + len(list((ROOT / "scripts").glob("*.cmd")))


def collect_surfaces() -> list[dict[str, Any]]:
    """Live surface split, newest-first-ish (stable order)."""
    from mag import framework_map as fm

    items = fm.render().get("items") or []
    by_kind: dict[str, int] = {}
    for it in items:
        k = it.get("kind")
        by_kind[k] = by_kind.get(k, 0) + 1
    return [
        {"id": "cli", "label": "CLI subcommands", "count": by_kind.get("cli", 0)},
        {"id": "route_dashboard", "label": "Dashboard REST routes", "count": by_kind.get("route", 0)},
        {"id": "route_cast", "label": "Cast/voice routes", "count": _cast_routes()},
        {"id": "launcher", "label": "Launchers (.cmd)", "count": _launchers()},
        {"id": "provider", "label": "Model providers", "count": by_kind.get("provider", 0)},
        {"id": "loop", "label": "Loops (registry)", "count": _loops()},
        {"id": "ext_command", "label": "VS Code commands", "count": _ext_commands()},
        {"id": "tab", "label": "Dashboard tabs", "count": _dashboard_tabs()},
    ]


def audit() -> dict[str, Any]:
    """Full surface-audit payload: surfaces + groups + seam verdict + checks."""
    from mag import framework_map as fm

    ts = _now()
    payload = fm.render()
    items = payload.get("items") or []
    groups = [
        {
            "id": g["id"],
            "icon": g.get("icon", ""),
            "label": g.get("label", ""),
            "count": sum(1 for i in items if i.get("group") == g["id"]),
        }
        for g in (payload.get("groups") or [])
    ]
    verdict = "n/a"
    checks: list[dict[str, Any]] = []
    try:
        reps = fm.list_reports(tail=1)
        if reps:
            verdict = reps[0].get("verdict", "n/a")
            checks = reps[0].get("checks") or []
    except Exception:
        pass
    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": ts,
        "version": _version(ts),
        "entries": len(items),
        "surfaces": collect_surfaces(),
        "groups": groups,
        "verdict": verdict,
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, ensure_ascii=False, default=str))
