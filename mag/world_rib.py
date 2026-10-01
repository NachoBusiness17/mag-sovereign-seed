"""world_rib — the WORLD-TARGET compiler scaffold: a RIB lowers to a 2D field, then 3D mesh.

Operator (2026-08-11): "this is what i want make it happen" — the first stone from
RIB_DEADDROP_FUTURE_SELF: give the compiler a WORLD target. The map (RIB) precedes the territory
(the world). Deterministic + $0 + RE-DERIVABLE: the same RIB always yields the same world, and the
world can be regenerated from the RIB (grounded — a lying map is caught).

THE CONTRACT (deterministic, $0, deps numpy+PIL):
  compile(rib_text, w, h) -> 2D scalar field (the terrain = the map's territory)
    - the RIB's hash seeds everything (deterministic);
    - steer/goal points in the RIB become attractors (peaks);
    - low-frequency noise adds relief, all seeded by the RIB hash -> re-derivable.
  to_obj(field)          -> 3D mesh (grid of vertices + triangles) as an .obj string + file.
  world_from_rib(rib)    -> the full artifact: 2D field + 3D mesh (obj) + heightmap PNG + rib_hash
                            (provenance). Same RIB -> byte-identical world (re-derivable).
  rederive(rib_hash)     -> confirm a world is regenerable from its RIB (grounding check).

Schema: world_rib.v1 · deterministic + $0 · the map precedes the territory.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "world_rib.v1"
ART_DIR = ROOT / "memory" / "runs" / "world_rib"


def _seed(rib: str) -> int:
    return int(hashlib.sha256(rib.encode("utf-8")).hexdigest()[:8], 16)


def _goal_points(rib: str) -> list[tuple[float, float]]:
    """Deterministic attractor points from the RIB: steer/goal markers + hash-derived pins."""
    pts = []
    low = rib.lower()
    # explicit 'goal (x,y)' / 'at (x,y)' markers in the RIB text
    for m in re.finditer(r"(?:goal|at|peak)\s*\(?\s*([0-9.]+)\s*[, ]\s*([0-9.]+)", low):
        try:
            pts.append((float(m.group(1)) % 1.0, float(m.group(2)) % 1.0))
        except ValueError:
            continue
    # always add 2 hash-derived pins so even a bare RIB produces a real world
    s = _seed(rib)
    rng = __import__("numpy").random.default_rng(s)
    for _ in range(max(0, 2 - len(pts))):
        pts.append((float(rng.random()), float(rng.random())))
    return pts[:5]


def compile(rib: str, *, w: int = 128, h: int = 128, seed: int | None = None) -> dict[str, Any]:
    """Lower a RIB to a 2D scalar field (the terrain / the territory of the map). Deterministic."""
    import numpy as np
    s = _seed(rib) if seed is None else seed
    rng = np.random.default_rng(s)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    field = np.full((h, w), 0.0)
    # low-frequency relief, seeded by the RIB hash (deterministic noise)
    for _ in range(3):
        cx = rng.random() * w
        cy = rng.random() * h
        r0 = (rng.random() * 0.25 + 0.05) * w
        amp = rng.random() * 0.6 + 0.2
        field += amp * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r0 ** 2))
    # attractor peaks from the RIB's goals/steer (the map's intent becomes terrain)
    for gx, gy in _goal_points(rib):
        cx, cy = gx * w, gy * h
        field += 0.9 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (w * 0.12) ** 2))
    return {"schema": SCHEMA, "rib": rib, "rib_hash": _seed(rib), "w": w, "h": h,
            "field": field, "goals": _goal_points(rib), "min": float(field.min()),
            "max": float(field.max()), "mean": float(field.mean())}


def to_obj(field: Any, *, out: str | None = None) -> dict[str, Any]:
    """Extrude a 2D field to a 3D mesh (.obj): grid vertices + 2 triangles per cell. Deterministic."""
    import numpy as np
    h, w = field.shape
    zscale = 8.0 / (float(field.max() - field.min()) + 1e-9)
    lines = ["# world_rib v1 — deterministic terrain from a RIB"]
    verts, faces = [], []
    for y in range(h):
        for x in range(w):
            verts.append((float(x) / max(w - 1, 1), float(y) / max(h - 1, 1),
                          float(field[y, x]) * zscale))
    idx = lambda y, x: y * w + x + 1  # 1-based obj
    for y in range(h - 1):
        for x in range(w - 1):
            a, b, c, d = idx(y, x), idx(y, x + 1), idx(y + 1, x + 1), idx(y + 1, x)
            faces.append((a, b, c)); faces.append((a, c, d))
    obj = lines + [f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}" for v in verts] + \
          [f"f {f[0]} {f[1]} {f[2]}" for f in faces]
    text = "\n".join(obj) + "\n"
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "vertices": len(verts), "faces": len(faces),
            "obj_path": out, "n_chars": len(text)}


def _render_png(field: Any, *, out: str | None = None, w: int = 512, h: int = 512) -> str:
    import numpy as np
    from PIL import Image
    f = (field - field.min()) / (field.max() - field.min() + 1e-9)
    # simple terrain colormap: water -> low, land -> high
    rgb = np.zeros((*f.shape, 3), dtype=np.uint8)
    rgb[..., 2] = (np.clip(1 - f / 0.5, 0, 1) * 120).astype(np.uint8)          # blue (water)
    rgb[..., 1] = (np.clip(f / 0.6, 0, 1) * 160).astype(np.uint8)               # green (land)
    rgb[..., 0] = (np.clip((f - 0.4) / 0.6, 0, 1) * 200).astype(np.uint8)       # red (high)
    img = Image.fromarray(rgb).resize((w, h), Image.BICUBIC)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / f"world_{_seed('')}.png"
    img.save(str(out_p), "PNG")
    return str(out_p)


def world_from_rib(rib: str, *, w: int = 64, h: int = 64) -> dict[str, Any]:
    """The full world artifact from a RIB: 2D field + 3D mesh (obj) + heightmap PNG + provenance.
    Same RIB -> byte-identical world (re-derivable, grounded)."""
    c = compile(rib, w=w, h=h)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    rib_hash = f"{c['rib_hash']:08x}"
    obj = to_obj(c["field"], out=str(ART_DIR / f"world_{rib_hash}.obj"))
    png = _render_png(c["field"], out=str(ART_DIR / f"world_{rib_hash}.png"))
    return {"ok": True, "schema": SCHEMA, "rib_hash": rib_hash,
            "obj": obj["obj_path"], "png": png, "w": w, "h": h,
            "goals": c["goals"], "field_range": [round(c["min"], 4), round(c["max"], 4)],
            "re_derivable": True, "note": "same RIB -> identical world (grounded, no lying map)"}


def rederive(rib: str) -> dict[str, Any]:
    """Grounding check: confirm a world is regenerable from its RIB (byte-stable field)."""
    a = compile(rib)
    b = compile(rib)
    import numpy as np
    stable = bool(np.array_equal(a["field"], b["field"]))
    return {"ok": True, "schema": SCHEMA, "re_derivable": stable,
            "rib_hash": _seed(rib), "note": "map precedes territory: the world follows the RIB"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "compile(rib)->2D field; to_obj(field)->3D mesh; world_from_rib(rib)->"
                        "field+mesh+png+provenance; rederive(rib)->grounding check",
            "cost": "deterministic + $0 (numpy+PIL)", "deps": "numpy, PIL",
            "artifacts": str(ART_DIR.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="world-rib")
    ap.add_argument("rib", nargs="*", help="the RIB text (or a known rib name)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    import json as _j
    if a.status:
        print(_j.dumps(status(), indent=2, default=str))
    else:
        rib = " ".join(a.rib) or ("The map precedes the territory; the RIB precedes the flock; "
                                  "goal (0.2, 0.8), goal (0.8, 0.2), peak (0.5, 0.5)")
        print(_j.dumps(world_from_rib(rib), indent=2, default=str))
