"""console_render — the ONE console-display surface I STOP forgetting (the operator: 'you keep
forgetting what tools you have for console display. fix it please all of it').

SELF-STEAL — the display tools already exist; I just never consolidated + remember them:
  * rib_render.render_stack()  -> the invariant stack as mermaid + counts + chart artifact
  * display.build_display_payload() -> TV-safe ambient display payload
  * bard.py                    -> console panels / event stream / metrics cards
  * swarm_map.svg()            -> bare-metal real-time map of the swarm across domains
  * clawbot.deliver_drift()    -> desktop drift delivery
  * oscillating.svg()          -> the wave's osculating geometry rendered
THE FIX: a single console_render.show() that RENDERS the live state to the console/dashboard via
our own tools (never just describing in prose when a render tells it better). When the operator says
"show", RENDER — do not narrate.

Schema: console_render.v1 · deterministic + $0 · reuse: rib_render, display, compute_reconcile, swarm_map
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "console_render.v1"
ARTIFACT_DIR = ROOT / "memory" / "artifacts" / "console_render"

# THE INVENTORY — the console-display tools I keep forgetting (self-stolen; this is the reminder).
DISPLAY_TOOLS: list[dict[str, str]] = [
    {"tool": "rib_render.render_stack()", "shows": "the invariant stack as mermaid + counts + chart"},
    {"tool": "console_render.show()", "shows": "live state rendered to console/dashboard (THIS)"},
    {"tool": "display.build_display_payload()", "shows": "TV-safe ambient display payload"},
    {"tool": "bard.panels()", "shows": "console panels / event stream / metrics cards"},
    {"tool": "swarm_map.svg()", "shows": "bare-metal real-time swarm-across-domains map"},
    {"tool": "osculating.svg()", "shows": "the wave's osculating geometry rendered"},
    {"tool": "clawbot.deliver_drift()", "shows": "desktop drift delivery"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tools() -> dict[str, Any]:
    """THE REMINDER: the console-display tools, listed so I never forget them."""
    return {"ok": True, "schema": SCHEMA, "n_tools": len(DISPLAY_TOOLS), "tools": DISPLAY_TOOLS,
            "rule": "when the operator says 'show', RENDER via these tools — never just narrate"}


def show() -> dict[str, Any]:
    """RENDER the live state to the console/dashboard via our own tools. The fix: when asked to
    show, this is what I run — a real render, not prose."""
    rendered: dict[str, Any] = {"ok": True, "schema": SCHEMA, "ts": _now()}
    # 1. the invariant stack (rib_render) — mermaid + counts
    try:
        from mag import rib_render
        rendered["stack"] = rib_render.render_stack()
    except Exception as e:
        rendered["stack"] = {"error": str(e)[:80]}
    # 2. compute rightsizing (real state)
    try:
        from mag import compute_reconcile
        rendered["compute"] = compute_reconcile.measure()
    except Exception as e:
        rendered["compute"] = {"error": str(e)[:80]}
    # 3. the swarm-across-domains map (bare-metal SVG)
    try:
        from mag import swarm_map
        rendered["swarm_svg"] = swarm_map.svg()
    except Exception as e:
        rendered["swarm_svg"] = {"error": str(e)[:80]}
    # 4. persist the artifact so the dashboard displays it
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (ARTIFACT_DIR / f"show-{_now()[:13].replace(':', '')}.json").write_text(
            json.dumps(rendered, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return rendered


def render_artifact() -> dict[str, Any]:
    """The chart/HTML artifact (rib_render house style) — the invariant stack as a real infographic
    the dashboard / vision model can read."""
    try:
        from mag import rib_render
        return rib_render.render_stack()
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "tools()->the console-display inventory (the reminder); show()->render live "
                        "state to console/dashboard via our tools; render_artifact()->the chart "
                        "artifact; status()->this",
            "cost": "deterministic + $0",
            "display_tools": [t["tool"] for t in DISPLAY_TOOLS]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="console-render")
    ap.add_argument("cmd", nargs="?", default="tools", choices=["status", "tools", "show", "artifact"])
    a = ap.parse_args()
    if a.cmd == "show":
        print(json.dumps(show(), indent=2, default=str)[:8000])
    elif a.cmd == "artifact":
        print(json.dumps(render_artifact(), indent=2, default=str)[:8000])
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(tools(), indent=2, default=str))
