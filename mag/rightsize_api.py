"""rightsize_api — RESTful endpoint registry ("database") for the rightsizing ghost tools.

The rightsizing ghost (rightsize_all / queue_rightsize / grok_rightsize / self_drive /
ghost_grok_dashboard) exposes a small REST surface. This module is the DERIVED catalog of
those endpoints, persisted as a JSON registry under memory/endpoints/rightsize.json — the
framework's "files are truth" invariant. No SQLite at this scale (2026 RESTful best-practices
steal: small, read-mostly, append-rarely -> JSON file is correct; files under memory/ are the
source of truth, the API is a viewport).

It never goes stale: the catalog is derived from this module's declared TOOLS + their
endpoint shapes + handler docstrings, not hand-maintained.

2026 conventions applied (per steal): /api/v1 path versioning, snake_case JSON, ISO 8601
*_at timestamps, {ok,...} success envelope, RFC 9457 application/problem+json errors.

Schema: rightsize_api.v1
CLI: python -m mag.rightsize_api build|status
REST (dashboard/rest.py): GET /api/v1/rightsize  · POST /api/v1/rightsize/{audit,apply} · GET /api/v1/rightsize/endpoints
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "rightsize_api.v1"
REGISTRY_PATH = ROOT / "memory" / "endpoints" / "rightsize.json"
VERSION = "v1"

# The rightsizing ghost toolset + its REST/CLI surface. This is the single source the
# registry is derived from — add a tool here and `build()` picks it up.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "rightsize_all",
        "group": "rightsize",
        "desc": "audit+apply rightsizing across ALL subsystems (RQ queue, RR routing, RG grok, RC cache, RL cadence, RT tokens)",
        "cli": "python -m mag.rightsize_all audit|apply [--apply]",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/rightsize", "summary": "rightsizing status + endpoint registry"},
            {"method": "POST", "path": "/api/v1/rightsize/audit", "summary": "run rightsize_all.audit() (report-only, $0)"},
            {"method": "POST", "path": "/api/v1/rightsize/apply", "summary": "apply fixable rightsizing (dry by default)"},
        ],
    },
    {
        "name": "queue_rightsize",
        "group": "rightsize",
        "desc": "analyze/apply/learn queue tier mis-sizing (cheap work on expensive tier)",
        "cli": "python -m mag.queue_rightsize analyze|apply|learn [--apply]",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/rightsize/queue", "summary": "analyze queue rightsizing"},
        ],
    },
    {
        "name": "grok_rightsize",
        "group": "rightsize",
        "desc": "right-size grok elevation (frontier only; gate + failover key chain)",
        "cli": "python -m mag.grok_rightsize (module)",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/rightsize/grok", "summary": "grok rightsizing/gate status"},
        ],
    },
    {
        "name": "self_drive",
        "group": "rightsize",
        "desc": "model/tier right-sizing by goal shape (flash exec, pro reasoning, local janitor)",
        "cli": "python -m mag.self_drive plan|drive [goal]",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/rightsize/self", "summary": "self_drive model right-sizing status"},
        ],
    },
    {
        "name": "ghost_grok_dashboard",
        "group": "rightsize",
        "desc": "tokens-saved-vs-projected dashboard counter (shared-language cost reducer)",
        "cli": "python -m mag.ghost_grok_dashboard (module)",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/tokens/saved", "summary": "tokens saved vs projected + est USD"},
        ],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build() -> dict[str, Any]:
    """Derive + persist the endpoint registry for the rightsizing ghost tools."""
    reg = {
        "schema": SCHEMA,
        "version": VERSION,
        "updated_at": _now(),
        "source": "derived from mag/rightsize_api.TOOLS",
        "tools": TOOLS,
        "endpoint_count": sum(len(t["endpoints"]) for t in TOOLS),
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    return reg


def status() -> dict[str, Any]:
    """Read the persisted registry (or build if absent)."""
    if not REGISTRY_PATH.is_file():
        return build()
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return build()


def endpoints() -> list[dict[str, Any]]:
    """Flatten the registry to a list of {method, path, summary, tool, group, version} for REST."""
    out: list[dict[str, Any]] = []
    for t in TOOLS:
        for e in t["endpoints"]:
            out.append({
                "method": e["method"], "path": e["path"], "summary": e["summary"],
                "tool": t["name"], "group": t.get("group", "rightsize"), "version": VERSION,
            })
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd == "build":
        print(json.dumps(build(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
