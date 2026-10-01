"""swarm_render — ShaderToy-style renderer: turn the swarm state into images a vision model reads.

Operator (2026-08-11): "can we have a shadertoy renderer so we can feed this shit to vision models
too?"

We already have the pure-function renderer (mag/shader_bus.render -> deterministic register PNG).
This wires the FULL swarm state into vision-model-ready images:
  flock_image(agents, seams, lights)  -> the flock + its seams + evidence lights, one glowing frame
  ownership_image(plan, edits)        -> line-builder ownership (each line colored by its worker)
Each image is deterministic ($0, pure function -> bytes) and saved as PNG for a vision model.

Schema: swarm_render.v1
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "swarm_render.v1"
ART_DIR = ROOT / "memory" / "runs" / "swarm_render"


def flock_image(agents: list[Any], seams: list[dict[str, Any]] | None = None,
                lights: list[Any] | None = None, *, t: float = 0.0,
                w: int = 256, h: int = 256, out: str | None = None) -> dict[str, Any]:
    """Render the flock + seams + evidence lights as one ShaderToy-style frame -> PNG.

    Builds a state list for mag.shader_bus.render: agents = glowing knots (color by seed/role),
    seams = bright red + larger (the divergences to shade), lights = colored glows (evidence).
    Deterministic + $0 (pure function -> bytes). Returns path + a caption for the vision model.
    """
    from mag import shader_bus as sb
    state: list[dict[str, Any]] = []
    # evidence lights first (the lighting sources)
    for li in (lights or []):
        color = list(getattr(li, "color", (200, 200, 200)))
        origin = getattr(li, "origin", (w / 4, h / 4))
        shadow = getattr(li, "shadow", 1.0)
        state.append({"x": float(origin[0]) * w + w / 4, "y": float(origin[1]) * h + h / 4,
                      "color": [int(c * 0.6 + 80) for c in color[:3]], "shadow": shadow})
    # flock agents as glowing knots (color by seed hash)
    for a in (agents or []):
        pos = getattr(a, "pos", None) or getattr(a, "origin", (0, 0))
        sid = int(getattr(a, "id", 0) or 0)
        state.append({"x": float(pos[0]) * w + w / 2, "y": float(pos[1]) * h + h / 2,
                      "color": [(sid * 37) % 255, (sid * 89) % 255, (sid * 53) % 255]})
    # seams = bright red, larger (the divergences the render farm shades)
    for s in (seams or []):
        seed_id = int(s.get("seed", 0) or 0)
        # approximate seam pos from its seed id (deterministic)
        state.append({"x": (seed_id * 53) % w, "y": (seed_id * 97) % h,
                      "color": [255, 40, 40], "radius": 30})
    frame = sb.render(state, t=t, w=w, h=h)
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / f"flock_t{round(t, 2)}.png"
    Image.fromarray(frame).save(str(out_p), "PNG")
    caption = (f"Swarm render: {len(agents or [])} agents, {len(seams or [])} seams (red, to shade), "
               f"{len(lights or [])} evidence lights. ShaderToy-style register frame.")
    return {"ok": True, "schema": SCHEMA, "image": str(out_p), "w": w, "h": h,
            "agents": len(agents or []), "seams": len(seams or []), "lights": len(lights or []),
            "caption": caption}


def ownership_image(plan_doc: dict[str, Any], *, w: int = 256, h: int = 96,
                    out: str | None = None) -> dict[str, Any]:
    """Render line-builder ownership as an image: each file line colored by its owning worker.

    A horizontal strip, one row per worker, each row = its owned line range colored distinct.
    A vision model can SEE which worker owns which lines (the conflict-free partition).
    Deterministic + $0.
    """
    import numpy as np
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    ownership = plan_doc.get("ownership", {})
    n_lines = int(plan_doc.get("n_lines", 0) or 0)
    palette = [(66, 133, 244), (52, 168, 83), (255, 193, 7), (234, 67, 53),
               (171, 71, 188), (255, 112, 67), (0, 172, 193), (158, 158, 158)]
    rows = max(1, len(ownership))
    arr = np.zeros((rows, max(1, n_lines), 3), dtype=np.uint8)
    for i, (worker, (s, e)) in enumerate(ownership.items()):
        color = palette[i % len(palette)]
        arr[i, s:e, :] = color
    arr = np.repeat(arr, h // rows, axis=0)
    img = Image.fromarray(arr).resize((w, h), Image.NEAREST)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / "ownership.png"
    img.save(str(out_p), "PNG")
    return {"ok": True, "schema": SCHEMA, "image": str(out_p), "n_lines": n_lines,
            "n_workers": len(ownership), "caption": f"Line ownership: {len(ownership)} workers, "
                                                    "each color = one worker's owned line range"}


# ── VISUAL MACHINE LANGUAGE (ShaderToy "Chromatic Particle Tides" steal) ─────────
# The shader is the ENCODING layer that turns a raw state buffer into READABLE visual language:
#   low-res trail buffer  = compression (keep essential state low-res, upscale) = verkle/quantizer
#   bloom (4-neighbor)    = local aggregation (each pixel blends with neighbors) = cohesion/context
#   exponential tone-map  = normalization (wide dynamic range -> communicable range)
#   gamma                 = display encoding
#   vignette              = focus/attention (bright core, dimmed edges)
# Applied to our swarm renders, this is how code/state becomes a visual machine language readable
# by vision models, and the texture lives in the VRAM register (shader_bus). Deterministic + $0.


def post_process(frame: "Any", *, bloom: float = 0.38, exposure: float = 1.25,
                 gamma: float = 2.2, vignette_strength: float = 0.18) -> "Any":
    """Apply the shader's post-process pipeline to a rendered frame (numpy uint8 -> uint8).

    bloom (4-neighbor avg, blended) -> exp tone-map -> gamma -> vignette. Pure, deterministic.
    """
    import numpy as np
    a = np.asarray(frame, dtype=np.float64) / 255.0
    # bloom: 4-neighbor average
    bloom_pass = (np.roll(a, 1, 0) + np.roll(a, -1, 0) +
                  np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 4.0
    color = a + (a + bloom_pass - a) * bloom  # mix(color, color+bloom, amount)
    # exponential tone-map + gamma
    color = 1.0 - np.exp(-color * exposure)
    color = np.power(np.maximum(color, 0.0), 1.0 / gamma)
    # vignette
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    centered_u = (xx / w) * 2.0 - 1.0
    centered_v = (yy / h) * 2.0 - 1.0
    vig = np.clip(1.0 - vignette_strength * (centered_u ** 2 + centered_v ** 2), 0.0, 1.0)
    color *= vig[..., None] if color.ndim == 3 else vig
    return np.clip(color * 255.0, 0, 255).astype(np.uint8)


def visual_language(state: list[dict[str, Any]], *, w: int = 256, h: int = 256,
                    out: str | None = None) -> dict[str, Any]:
    """Render swarm state -> post-process -> PNG: the visual machine language for a vision model.

    Uses shader_bus.render (the register frame) then post_process (the encoding layer). The PNG is
    the 'visual machine language' a vision model reads; the underlying texture is the VRAM register.
    Deterministic + $0.
    """
    from mag import shader_bus as sb
    frame = sb.render(state, t=0.0, w=w, h=h)
    out_frame = post_process(frame)
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / "visual_language.png"
    Image.fromarray(out_frame).save(str(out_p), "PNG")
    return {"ok": True, "schema": SCHEMA, "image": str(out_p), "w": w, "h": h,
            "caption": ("Visual machine language: swarm state encoded via bloom + tone-map + gamma "
                        "+ vignette. Readable by vision models; texture is the VRAM register.")}


def main(argv: list[str] | None = None) -> int:
    import sys
    from mag.flock_shader import AgentSeed, Light
    from mag import line_builder as lb
    agents = [AgentSeed(id=i, pos=(float(i % 3 - 1) / 3, float(i % 2) / 3)) for i in range(6)]
    seams = [{"seed": 99, "deviation": 0.9}]
    lights = [Light(origin=(0.05, 0.05), color=(1, 0, 0)), Light(origin=(0.5, 0.5), color=(0, 1, 0))]
    a = flock_image(agents, seams, lights)
    demo = "\n".join(f"line{i}" for i in range(10))
    p = lb.plan(demo, 3)
    b = ownership_image(p)
    print(json.dumps({"flock": a, "ownership": b}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
