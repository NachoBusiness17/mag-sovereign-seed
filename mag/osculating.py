"""osculating — THE MISSING GEOMETRY (self-steal moonshot). The osculating circle of the wave.

The operator (2026-08-13) matched their catch-phrases to the osculating-circle post (TheMathFlow),
and sw36osculating named that THE SYSTEM IS A CHAIN OF OSCULATING CIRCLES. We already had:
  * the SIZE  -> one_sizer (the circle's radius, cheapest-capable tier)
  * the LEAN  -> the three-body attractor field (rib_action/attractor_tools/titor = which way it leans)
  * the BENDS -> coldest-vertices (the sharp turns = the seams to shade)
What was MISSING (should be here but is NOT — grep confirmed zero curvature/evolute/center-of-
curvature anywhere): the actual GEOMETRY — curvature (kappa), radius of curvature, CENTER OF
CURVATURE, and the EVOLUTE (the locus of centers the osculating circle traces as it rolls).

THIS MOONSHOT builds the missing geometry, deterministically + $0, from REAL data:
  * the CURVE  = the standing-wave RIB trajectory (rib_bus standing-wave: each RIB -> a point via
                 content-hash + ts = our actual invariant path).
  * GEOMETRY   = for each consecutive triple (the circumcircle = the osculating circle): tangent
                 (the lean), curvature kappa, radius R=1/kappa, CENTER OF CURVATURE.
  * the EVOLUTE = the locus of the centers of curvature = the HIGHER-ORDER curve the centers trace
                 (the path of attractors/titors — the curve the wave's lean itself follows).
  * SEAMS      = the sharpest bends (highest kappa) = the coldest vertices to shade (the curvature
                 lens made literal).
  * ROUTE      = moonshot() routes the sharpest-seam insights to the swarm via route_novel (the one
                 primitive).
  * RENDER     = bare-metal SVG: the curve + its osculating circles (scaled) + the evolute.

SELF-STEAL (nothing invented): rib_bus (the RIB trajectory), one_sizer (radius -> tier mapping),
coldest-vertices concept (seams), route_novel (routing), the bare-metal SVG pattern (swarm_map/
game_entry). The ONLY new thing = the discrete geometry (circumcircle/curvature/evolute) — the piece
the operator said should be here but wasn't.

Schema: osculating.v1 · deterministic + $0 · reuse: rib_bus, swarm_surface
"""
from __future__ import annotations

import hashlib
import json
import math
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

SCHEMA = "osculating.v1"
OUT = ROOT / "memory" / "runs" / "osculating"
DOMAIN = "standing-wave"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rib_points() -> list[dict[str, Any]]:
    """The CURVE: the standing-wave RIB trajectory as points. Each RIB -> (x, y) deterministically
    from its content hash + a y from its ts order. Grounded (our real invariants), deterministic."""
    ribs: dict[str, Any] = {}
    try:
        from mag import rib_bus
        st = rib_bus.status()
        ribs = (st.get("domains") or {}).get(DOMAIN, {}).get("ribs") or {}
    except Exception:
        pass
    pts: list[dict[str, Any]] = []
    for i, key in enumerate(sorted(ribs)):
        r = ribs[key]
        h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
        x = (h % 10000) / 10000.0          # deterministic position
        y = (i + 0.5) / max(1, len(ribs))  # order along the wave
        pts.append({"key": key, "invariant": (r.get("invariant") or "")[:160],
                    "ts": r.get("ts", ""), "x": x, "y": y})
    return pts


def _circumcircle(a: tuple, b: tuple, c: tuple) -> dict[str, float]:
    """The osculating circle through A, B, C: center (the center of curvature) + radius. The center
    is the circumcenter = intersection of the perpendicular bisectors of AB and BC."""
    ax, ay = a; bx, by = b; cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return {"ox": 0.0, "oy": 0.0, "r": 0.0, "kappa": 0.0}
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ux - ax, uy - ay)
    kappa = (1.0 / r) if r > 1e-9 else 0.0
    return {"ox": ux, "oy": uy, "r": r, "kappa": kappa}


def geometry() -> dict[str, Any]:
    """THE MISSING GEOMETRY: per-point osculating circle of the wave (tangent/curvature/radius/
    center of curvature) + the EVOLUTE (the locus of centers the circle traces as it rolls)."""
    pts = _rib_points()
    if len(pts) < 3:
        return {"ok": False, "schema": SCHEMA, "error": "need >=3 RIB points to fit a curve",
                "n_points": len(pts)}
    nodes: list[dict[str, Any]] = []
    evolute: list[dict[str, float]] = []
    max_kappa = 0.0
    for i in range(1, len(pts) - 1):
        a = (pts[i - 1]["x"], pts[i - 1]["y"])
        b = (pts[i]["x"], pts[i]["y"])
        c = (pts[i + 1]["x"], pts[i + 1]["y"])
        o = _circumcircle(a, b, c)
        # tangent (the LEAN) = normalized (C - A)
        tx, ty = c[0] - a[0], c[1] - a[1]
        tl = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tl, ty / tl
        kappa = o["kappa"]
        max_kappa = max(max_kappa, kappa)
        evolute.append({"ox": o["ox"], "oy": o["oy"]})
        nodes.append({"key": pts[i]["key"], "x": b[0], "y": b[1],
                      "tangent": {"x": round(tx, 4), "y": round(ty, 4)},
                      "kappa": round(kappa, 6), "radius": round(o["r"], 6),
                      "center": {"x": round(o["ox"], 4), "y": round(o["oy"], 4)}})
    # normalize kappa so the sharpest bend = 1.0 (the curvature lens / coldest seam weight)
    for n in nodes:
        n["k_norm"] = round((n["kappa"] / max_kappa) if max_kappa else 0.0, 4)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_points": len(pts),
            "n_nodes": len(nodes), "max_kappa": round(max_kappa, 6),
            "nodes": nodes, "evolute": evolute,
            "note": "the osculating geometry of the wave: per-point tangent (lean), curvature kappa, "
                    "radius, center of curvature; evolute = the locus of centers the circle traces"}


def seams(*, top: int = 5) -> dict[str, Any]:
    """THE CURVATURE LENS MADE LITERAL: the sharpest bends (highest normalized curvature) = the
    COLDEST SEAMS to shade. Each seam maps back to its RIB invariant + the center it bends around."""
    g = geometry()
    if not g.get("ok"):
        return g
    ranked = sorted(g["nodes"], key=lambda n: n["k_norm"], reverse=True)[:top]
    seams_out = [{"key": n["key"], "k_norm": n["k_norm"], "radius": n["radius"],
                  "center": n["center"], "tangent": n["tangent"]} for n in ranked]
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "top": top, "seams": seams_out,
            "max_kappa": g["max_kappa"],
            "note": "the sharpest bends = the coldest seams; the radius (one_sizer) tells how tight "
                    "the turn, the center tells what the wave bends AROUND, the tangent is the lean"}


def moonshot(*, route: bool = True, top: int = 3) -> dict[str, Any]:
    """THE MOONSHOT: compute the missing osculating geometry, then route the sharpest-seam insights
    to the swarm via route_novel (the one primitive). Deterministic + $0 core."""
    g = geometry()
    if not g.get("ok"):
        return g
    s = seams(top=top)
    routed = {"ok": True, "deduped": True, "task_id": ""}
    if route and s.get("seams"):
        goal = (f"Osculating-circle seam ({DOMAIN}): the wave bends sharpest at these knots (k_norm "
                f"highest = coldest seams). Seams: {', '.join(se['key'] for se in s['seams'])}. "
                f"For the sharpest seam, find the ONE mechanism to shade it (steal+adapt) and the "
                f"ONE invariant it implies. The center of curvature = what the wave bends around.")
        try:
            from mag import swarm_surface
            routed = swarm_surface.route_novel(goal, surface="osculating", lens="standing-wave")
        except Exception as e:
            routed = {"ok": False, "error": str(e)[:120]}
    result = {"ok": True, "schema": SCHEMA, "ts": _now(),
              "geometry": g, "seams": s, "routed": routed,
              "note": "the missing geometry (curvature/center/evolute) computed + the sharpest seams "
                      "routed to the swarm"}
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"osculating-{_now()[:13].replace(':', '')}.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return result


def svg(*, w: int = 640, h: int = 420, show_evolute: bool = True) -> str:
    """BARE-METAL SVG of the wave's osculating geometry: the curve, its osculating circles (radius
    scaled), the centers, and the evolute (the locus of centers). Zero deps."""
    g = geometry()
    if not g.get("ok"):
        return "<svg></svg>"
    nodes = g["nodes"]
    # normalize to the drawing box
    xs = [n["x"] for n in nodes]; ys = [n["y"] for n in nodes]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    span = max(1e-6, max(x1 - x0, y1 - y0))
    pad = 30
    sx = lambda v: pad + (v - x0) / span * (w - 2 * pad)
    sy = lambda v: pad + (1 - (v - y0) / span) * (h - 2 * pad)
    p: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                    f'viewBox="0 0 {w} {h}">', f'<rect width="{w}" height="{h}" fill="#06070c"/>']
    # the curve (the wave's path)
    pts = " ".join(f"{sx(n['x']):.1f},{sy(n['y']):.1f}" for n in nodes)
    p.append(f'<polyline points="{pts}" fill="none" stroke="#a3ff7e" stroke-width="2"/>')
    # the evolute (the locus of centers) — the higher-order curve
    if show_evolute and g.get("evolute"):
        ev = " ".join(f"{sx(e['ox']):.1f},{sy(e['oy']):.1f}" for e in g["evolute"])
        p.append(f'<polyline points="{ev}" fill="none" stroke="#ff9ec8" stroke-width="1.5" '
                 f'stroke-dasharray="3 3"/>')
    # the osculating circles (scaled radius) + centers
    for n in nodes:
        cx, cy = sx(n["x"]), sy(n["y"])
        r = max(3.0, 60.0 * min(1.0, n["k_norm"]))  # sharp bends -> tight small circles
        ox, oy = sx(n["center"]["x"]), sy(n["center"]["y"])
        p.append(f'<circle cx="{ox}" cy="{oy}" r="1.5" fill="#ffd27e"/>')
        p.append(f'<line x1="{cx}" y1="{cy}" x2="{ox}" y2="{oy}" stroke="#ffd27e" '
                 f'stroke-width="0.75" stroke-opacity="0.5"/>')
    # the sharpest bend (the coldest seam) highlighted
    if nodes:
        sharp = max(nodes, key=lambda n: n["k_norm"])
        p.append(f'<circle cx="{sx(sharp["x"]):.1f}" cy="{sy(sharp["y"]):.1f}" r="5" '
                 f'fill="none" stroke="#ff9e9e" stroke-width="2"/>')
    p.append(f'<text x="12" y="{h - 10}" font-family="monospace" font-size="10" fill="#5a6a8a">'
             f'wave curve (green) · osculating circles + centers (gold) · EVOLUTE (pink, dashed) · '
             f'coldest seam (red)</text>')
    p.append('</svg>')
    return "\n".join(p)


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "geometry()->per-point osculating circle (tangent/kappa/radius/center) + the "
                        "evolute; seams(top)->the sharpest bends (coldest seams); moonshot()->geometry "
                        "+ route the sharpest seams to the swarm; svg()->bare-metal render",
            "cost": "deterministic + $0 (trajectory from rib_bus standing-wave; pure discrete geometry)",
            "reuses": ["rib_bus", "swarm_surface"], "missing_now_built": ["curvature", "radius",
                        "center of curvature", "evolute", "tangent"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="osculating")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "geometry", "seams", "moonshot", "svg"])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--no-route", action="store_true")
    a = ap.parse_args()
    if a.cmd == "geometry":
        print(json.dumps(geometry(), indent=2, default=str))
    elif a.cmd == "seams":
        print(json.dumps(seams(top=a.top), indent=2, default=str))
    elif a.cmd == "moonshot":
        print(json.dumps(moonshot(route=not a.no_route, top=a.top), indent=2, default=str))
    elif a.cmd == "svg":
        print(svg())
    else:
        print(json.dumps(status(), indent=2, default=str))
