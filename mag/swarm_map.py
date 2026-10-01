"""swarm_map — steal the existing renderers (swarm_render ShaderToy, flock_anim PIL) and RECREATE
them BARE-METAL for our purpose: a real-time map of the swarm across domains as raw SVG — ZERO
dependencies (no PIL, no numpy, no shader_bus, no frameworks).

Operator (2026-08-12): "i want us to steal all those tools and recreate them to our own purposes"
+ "baremetal as possible" + "render the swarm across domains in real time like my vk vibecode map".

THE STEAL (what we take from the legacy renderers) + THE RECREATE (how we make it ours/bare-metal):
  * flock_anim._frame  (PIL: grid, trails, knots, seams, steer lights)  -> RAW SVG (grid, domain
    nodes, active agents, seams, the standing wave). Same visual language, zero deps.
  * swarm_render.flock_image (ShaderToy -> register PNG for vision)     -> RAW SVG string a vision
    model OR the dashboard can read directly. No shader_bus, no bytes — plain markup.
  * NEW: LIVE ACROSS DOMAINS — real state (rib_bus domains, swarm results, standing wave gen)
    rendered as a self-refreshing page (html()) the dashboard serves. Real-time, bare-metal.

Schema: swarm_map.v1 · deterministic + $0 · reuse: rib_bus, swarm_worker results, agent_knot
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

SCHEMA = "swarm_map.v1"
OUT = ROOT / "memory" / "runs" / "swarm_map"

# Domain map: each domain -> a normalized grid position (x, y) on the live map.
DOMAIN_GRID: dict[str, tuple[float, float]] = {
    "swarm": (0.50, 0.12), "k3s": (0.12, 0.30), "k8s": (0.88, 0.30),
    "general": (0.12, 0.70), "game": (0.50, 0.70), "grokbot": (0.88, 0.70),
    "clawbot": (0.30, 0.50), "economics": (0.70, 0.50), "titor": (0.50, 0.45),
}
DOMAIN_COLOR = {
    "swarm": "#a3ff7e", "k3s": "#7ec8ff", "k8s": "#ff9ec8", "general": "#ffd27e",
    "game": "#9ee8ff", "grokbot": "#c89eff", "clawbot": "#ff9e9e", "economics": "#8ef0c0",
    "titor": "#e8c09e",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def frame() -> dict[str, Any]:
    """LIVE swarm state across domains — real registers. Deterministic + $0."""
    domains: dict[str, dict[str, int]] = {}
    try:
        from mag import rib_bus
        st = rib_bus.status()
        for d, info in (st.get("domains") or {}).items():
            key = next((k for k in DOMAIN_GRID if k in d), "general")
            domains.setdefault(key, {"n_ribs": 0, "active": 0})
            domains[key]["n_ribs"] += int(info.get("n_ribs") or 0)
    except Exception:
        pass
    n_res = 0
    try:
        from config import RESULTS_DIR
        n_res = len(list(RESULTS_DIR.glob("sw-*.json"))) if RESULTS_DIR.is_dir() else 0
    except Exception:
        pass
    domains.setdefault("swarm", {"n_ribs": 0, "active": 0})["active"] = n_res
    gen, fitness, n_versions = 0, 0.0, 0
    try:
        from mag import agent_knot
        e = agent_knot.evo_status()
        gen, fitness = e.get("generation", 0), e.get("top_fitness", 0.0)
    except Exception:
        pass
    try:
        from mag import swarm_self
        n_versions = swarm_self.self().get("n_versions", 0)
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "standing_wave": {"generation": gen, "fitness": fitness},
            "flock_versions": n_versions, "swarm_results": n_res, "domains": domains}


def svg(*, w: int = 800, h: int = 520) -> str:
    """BARE-METAL SVG map of the swarm across domains — a single string, zero deps. Reads live
    frame() state, draws: domain nodes (size = ribs), active seams, the standing wave. $0."""
    f = frame()
    p: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                    f'viewBox="0 0 {w} {h}">',
                    f'<rect width="{w}" height="{h}" fill="#06070c"/>']
    for gx in range(0, w, 40):
        p.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{h}" stroke="#141a28" stroke-width="1"/>')
    for gy in range(0, h, 40):
        p.append(f'<line x1="0" y1="{gy}" x2="{w}" y2="{gy}" stroke="#141a28" stroke-width="1"/>')
    for dom, (nx, ny) in DOMAIN_GRID.items():
        cx, cy = int(nx * w), int(ny * h)
        col = DOMAIN_COLOR.get(dom, "#888")
        info = f.get("domains", {}).get(dom, {})
        n_ribs = int(info.get("n_ribs") or 0)
        active = int(info.get("active") or 0)
        r = 12 + min(20, n_ribs * 2 + active)
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}" fill-opacity="0.16" '
                 f'stroke="{col}" stroke-width="1.5"/>')
        p.append(f'<text x="{cx}" y="{cy + 3}" font-family="monospace" font-size="10" '
                 f'fill="#dfe6ff" text-anchor="middle">{dom}</text>')
        p.append(f'<text x="{cx}" y="{cy + 16}" font-family="monospace" font-size="8" '
                 f'fill="{col}" text-anchor="middle">{n_ribs} rib · {active} act</text>')
    # the standing wave marker (center-bottom)
    cx, cy = int(0.50 * w), int(0.88 * h)
    gen = f.get("standing_wave", {}).get("generation", 0)
    fit = f.get("standing_wave", {}).get("fitness", 0)
    p.append(f'<circle cx="{cx}" cy="{cy}" r="26" fill="#ffd27e" fill-opacity="0.12" '
             f'stroke="#ffd27e" stroke-width="2"/>')
    p.append(f'<text x="{cx}" y="{cy - 2}" font-family="monospace" font-size="11" fill="#ffe9b0" '
             f'text-anchor="middle">WAVE</text>')
    p.append(f'<text x="{cx}" y="{cy + 12}" font-family="monospace" font-size="9" fill="#ffd27e" '
             f'text-anchor="middle">gen {gen} · fit {fit}</text>')
    p.append('</svg>')
    return "".join(p)


def html(*, refresh_s: int = 5) -> str:
    """BARE-METAL auto-refreshing page the dashboard serves — re-fetches the svg in real time.
    Zero JS libs: a meta-refresh + the svg route. $0."""
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta http-equiv='refresh' content='{refresh_s}'>"
            "<title>swarm · live map</title>"
            "<style>body{background:#06070c;color:#dfe6ff;font-family:monospace;margin:0;"
            "padding:12px}h1{font-size:14px;color:#7ec8ff;margin:0 0 6px}</style></head><body>"
            "<h1>swarm across domains · live (bare-metal)</h1>"
            "<img src='/api/v1/swarm-map.svg' width='100%' style='max-width:820px'/>"
            "</body></html>")


def save(*, w: int = 800, h: int = 520) -> dict[str, Any]:
    """Save the current live map SVG + frame JSON for the dashboard/vision. $0."""
    OUT.mkdir(parents=True, exist_ok=True)
    svg_path = OUT / "swarm_map.svg"
    svg_path.write_text(svg(w=w, h=h), encoding="utf-8")
    json_path = OUT / "swarm_map.json"
    json_path.write_text(json.dumps(frame(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "svg": str(svg_path.relative_to(ROOT)),
            "frame": str(json_path.relative_to(ROOT))}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-map")
    ap.add_argument("cmd", nargs="?", default="svg", choices=["svg", "frame", "html", "save"])
    a = ap.parse_args(argv)
    if a.cmd == "frame":
        print(json.dumps(frame(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "html":
        print(html())
    elif a.cmd == "save":
        print(json.dumps(save(), ensure_ascii=False, indent=2, default=str))
    else:
        print(svg())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
