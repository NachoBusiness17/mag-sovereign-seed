"""verkle_rib — map the verkle knots DIRECTLY onto RIB/RenderMan geometric data.

The operator's directive (2026-08-09): "the verkle knot needs to be directly mapped to the
renderman data." RenderMan's geometry is the structural substrate (renderman.py already maps
BVH->verkle, bubbles->sovereignty membranes, geometry-cache->parsed structure). So each Verkle
knot's behavioral telemetry — dominant_theme, theme_vector_normalized (the 8-dim behavioral
vector), tension_index, session duration — is RENDERED as a point/curve in RIB space:

  knot -> { pos: theme_vector (RIB point), tension: scalar shading, theme: label,
            session: provenance, chain_proof: verkle root }

This is the bridge: the shared chain (behavior) and the RIB (structure/shape) become the SAME
geometry. Points feed flock_field (as invariant/attractor seeds) and shape_map (as portable
structure) — so the behavioral data populates the field we steer and the shape we transmit.

Deterministic, $0, no LLM. Schema: verkle_rib.v1
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "verkle_rib.v1"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
RIB_OUT = ROOT / "queue" / "handoff" / "VERKLE_RIB.json"


def _read_chain() -> list[dict[str, Any]]:
    if not CHAIN.is_file():
        return []
    out = []
    for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _tension_band(t: float) -> str:
    return "HIGH" if t >= 0.7 else ("MID" if t >= 0.55 else "LOW")


def rib_points(*, dim: int = 8) -> list[dict[str, Any]]:
    """Map every verkle knot to a RIB/RenderMan geometric point (theme_vector = position)."""
    points = []
    for k in _read_chain():
        tv = k.get("theme_vector_normalized") or []
        try:
            tension = float(k.get("tension_index") or 0.0)
        except (TypeError, ValueError):
            tension = 0.0
        # RIB position = the behavioral theme vector (pad/trim to dim)
        pos = [float(x) for x in tv[:dim]]
        pos += [0.0] * (dim - len(pos))
        points.append({
            "pos": [round(v, 4) for v in pos],
            "tension": round(tension, 4),
            "tension_band": _tension_band(tension),
            "theme": str(k.get("dominant_theme") or "untagged"),
            "session": str(k.get("session_id") or "")[:20],
            "chain_proof": str(k.get("verkle_root") or "")[:16],
            "n_leaves": k.get("n_leaves"),
        })
    return points


def export(*, dim: int = 8) -> dict[str, Any]:
    """Write the verkle->RIB map (all knots as RIB geometry) to queue/handoff/VERKLE_RIB.json."""
    pts = rib_points(dim=dim)
    themes: dict[str, int] = {}
    for p in pts:
        themes[p["theme"]] = themes.get(p["theme"], 0) + 1
    doc = {"schema": SCHEMA, "n_knots": len(pts), "dim": dim,
           "themes": dict(sorted(themes.items(), key=lambda kv: -kv[1])),
           "points": pts}
    RIB_OUT.parent.mkdir(parents=True, exist_ok=True)
    RIB_OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n_knots": len(pts), "themes": doc["themes"],
            "path": str(RIB_OUT)}


def summary() -> dict[str, Any]:
    pts = rib_points()
    themes: dict[str, int] = {}
    for p in pts:
        themes[p["theme"]] = themes.get(p["theme"], 0) + 1
    return {"ok": True, "schema": SCHEMA, "n_knots": len(pts),
            "themes": dict(sorted(themes.items(), key=lambda kv: -kv[1])),
            "tension_bands": {b: sum(1 for p in pts if p["tension_band"] == b) for b in ("HIGH", "MID", "LOW")}}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="verkle-rib")
    ap.add_argument("cmd", nargs="?", default="summary", choices=["summary", "export"])
    ap.add_argument("--dim", type=int, default=8)
    args = ap.parse_args(argv)
    if args.cmd == "summary":
        print(json.dumps(summary(), indent=2, default=str))
    else:
        print(json.dumps(export(dim=args.dim), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
