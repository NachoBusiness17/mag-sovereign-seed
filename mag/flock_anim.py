"""flock_anim — ShaderToy-style ANIMATION of a flock's INTENDED paths, before simulation.

Operator (2026-08-11): "rib file show it to me on a map using a shadertoy style tool to render our
flocks intended paths before simulation" -> "we have flocking experiments you can create animations
from".

WHAT THIS IS: a PREVIEW renderer. It evolves a flock deterministically ($0, no LLM) using the SAME
cheap pure function as the real swarm (flock_shader.shade / render / seams / inject), and renders
its INTENDED paths as:
  trail_map()  -> one static PNG: the whole planned pathfield on a map (steer attractors +
                  invariant basins + each agent's intended trail + the seam agents that will get
                  frontier shading).
  animate()    -> an animated GIF: the flock moving along its intended paths frame-by-frame, with
                  the planned trails glowing faintly behind it and the seams flashing red.

This is the "render before render": you see where the flock intends to go, and where the expensive
frontier will be spent (the seams), before any simulation / k8s dispatch. Deterministic + $0 —
same (seed, uniforms) -> identical frames, so it's replayable and RIB-debuggable.

Schema: flock_anim.v1 · deterministic + $0 · deps: PIL + numpy
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "flock_anim.v1"
ART_DIR = ROOT / "memory" / "runs" / "flock_anim"


# ── the shared field (phi) built from steer attractors + invariant penalty basins ──
def phi_field(goals: list[tuple[float, ...]], penalty: list[tuple[float, ...]] | None = None,
              repel: float = 0.5) -> Any:
    """Build the scalar field phi: pull toward goals, push off penalty basins.

    phi(p) = sum(|p-g|^2 for goals) + repel * sum(|p-c|^2 for penalty basins).
    -grad(phi) steers each agent toward its goals (the intended path), while the penalty basins
    (invariant no-go regions) push it away. Deterministic, $0.
    """
    goals = goals or [(0.75, 0.75)]
    penalty = penalty or []
    repel = max(0.0, repel)

    def phi(p: tuple[float, ...]) -> float:
        v = 0.0
        for g in goals:
            v += sum((p[i] - g[i]) ** 2 for i in range(min(len(p), len(g))))
        for c in penalty:
            v += repel * sum((p[i] - c[i]) ** 2 for i in range(min(len(p), len(c))))
        return v

    return phi


def _ring_agents(n: int, center: tuple[float, float] = (0.25, 0.25),
                 radius: float = 0.12, role: str = "probe") -> list[Any]:
    """Start the flock in a ring around a launch point (deterministic spread)."""
    from mag.flock_shader import AgentSeed
    out = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        px = center[0] + radius * math.cos(ang)
        py = center[1] + radius * math.sin(ang)
        out.append(AgentSeed(id=i, pos=(px, py), role=role,
                             task=f"goal:{round(center[0],2)},{round(center[1],2)}"))
    return out


def _color(seed: int) -> tuple[int, int, int]:
    return ((seed * 37) % 220 + 20, (seed * 89) % 220 + 20, (seed * 53) % 220 + 20)


# ── evolve the flock: the intended paths, cheaply and deterministically ─────────
def evolve(goals: list[tuple[float, ...]], *, n: int = 24, frames: int = 40,
           budget: float = 0.6, tau: float = 0.02, step: float = 0.06,
           penalty: list[tuple[float, ...]] | None = None,
           start: tuple[float, float] = (0.2, 0.2)) -> dict[str, Any]:
    """Evolve a flock over `frames` cheap steps -> its intended paths + per-frame seams.

    Uses flock_shader.render (the real cheap pure function) so the preview matches what the swarm
    would actually do. Returns:
      paths : {seed: [(x, y), ...]}  each agent's intended trail (T+1 points, normalized [0,1])
      seams : {t: [seed, ...]}       the seam agents per frame (the frontier-spend points)
      steer : the goals (iMouse attractors) as (x, y) normalized
    Deterministic + $0 (math/hash only).
    """
    from mag import flock_shader as fs

    phi = phi_field(goals, penalty)
    agents = _ring_agents(n, center=start)
    paths: dict[int, list[tuple[float, float]]] = {a.id: [tuple(a.pos)] for a in agents}
    seams_by_t: dict[int, list[int]] = {}
    iMouse = goals[0] if goals else None

    for t in range(frames):
        u = fs.Uniforms(phi=phi, iTime=t, iMouse=iMouse, budget=budget)
        states = fs.render(agents, u)
        seam_list = fs.seams(states, tau=tau)
        seams_by_t[t] = [s["seed"] for s in seam_list]
        # apply each agent's step vector to its position (the intended movement)
        for s in states:
            a = agents[s["seed"]]
            dx, dy = s["state"]
            nx = min(1.0, max(0.0, a.pos[0] + dx * step))
            ny = min(1.0, max(0.0, a.pos[1] + dy * step))
            a.pos = (nx, ny)
            paths[s["seed"]].append((nx, ny))
        # steer the next frame at the worst seam (inject), else hold the goal attractor
        u = fs.inject(u, seam_list, t=t)
        iMouse = u.iMouse if u.iMouse is not None else (goals[0] if goals else None)

    return {"paths": paths, "seams": seams_by_t,
            "steer": [tuple(g) for g in goals], "n": n, "frames": frames,
            "budget": budget, "tau": tau}


# ── rendering helpers (PIL C-speed draw + vectorized bloom) ───────────────────
def _bloom(img: Any, *, radius: float = 2.0, amount: float = 0.35) -> "Any":
    """Add a cheap glow: blend the image with a blurred copy (local aggregation)."""
    import numpy as np
    from PIL import ImageFilter
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    a = np.asarray(img, dtype=np.float64)
    b = np.asarray(blurred, dtype=np.float64)
    out = np.clip(a + b * amount, 0, 255).astype(np.uint8)
    from PIL import Image
    return Image.fromarray(out)


def _frame(paths: dict[int, list[tuple[float, float]]], seams_at_t: list[int],
           t: int, steer: list[tuple[float, float]], w: int, h: int, *,
           show_trails: bool, show_seams: bool) -> "Any":
    """Draw one frame as a PIL image: faint map grid, trails, knots, seams, steer lights."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), (6, 7, 12))
    d = ImageDraw.Draw(img, "RGBA")

    # faint grid = the map
    for gx in range(0, w, 32):
        d.line([(gx, 0), (gx, h)], fill=(18, 22, 34, 255), width=1)
    for gy in range(0, h, 32):
        d.line([(0, gy), (w, gy)], fill=(18, 22, 34, 255), width=1)

    # steer attractors (the goals) = cyan lights
    for g in steer:
        cx, cy = int(g[0] * w), int(g[1] * h)
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(60, 200, 240, 255))
        d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(200, 250, 255, 255))

    # intended trails (up to the current frame when animating) = thin glowing lines
    for seed, trail in paths.items():
        color = _color(seed)
        upto = trail if not show_trails else trail[: t + 1]
        pts = [(int(px * w), int(py * h)) for px, py in upto]
        if len(pts) > 1:
            d.line(pts, fill=(*color, 110), width=2)

    # current flock knots (the agents now) = glowing, colored by seed
    for seed, trail in paths.items():
        if t < len(trail):
            px, py = trail[t]
            cx, cy = int(px * w), int(py * h)
            d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(*_color(seed), 255))

    # seams = bright red rings (the frontier-spend points)
    if show_seams:
        for seed in seams_at_t:
            if t < len(paths[seed]):
                px, py = paths[seed][t]
                cx, cy = int(px * w), int(py * h)
                d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], outline=(255, 40, 40, 255), width=3)
                d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 60, 60, 255))

    return _bloom(img)


# ── public API ────────────────────────────────────────────────────────────────
def trail_map(goals: list[tuple[float, ...]] | None = None, *, n: int = 24, frames: int = 40,
              budget: float = 0.6, tau: float = 0.02, w: int = 512, h: int = 512,
              out: str | None = None, seed_extra: Any = None) -> dict[str, Any]:
    """Render the flock's FULL intended pathfield as one static 'map' PNG.

    Shows: the steer attractors (goals), every agent's intended trail, and the final seam points
    (where the expensive frontier would be spent). The 'show it to me on a map' deliverable.
    Deterministic + $0.
    """
    from PIL import Image

    goals = goals or [(0.78, 0.78)]
    res = evolve(goals, n=n, frames=frames, budget=budget, tau=tau)
    seams_final = res["seams"].get(frames - 1, [])
    img = _frame(res["paths"], seams_final, frames - 1, res["steer"], w, h,
                 show_trails=True, show_seams=True)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / f"flock_trailmap_{len(goals)}g_{n}a.png"
    img.save(str(out_p), "PNG")
    caption = (f"Flock intended-path map: {n} agents -> {len(goals)} goal(s), {frames} steps. "
               f"Trails = each agent's planned path; red = seam agents (frontier spend); "
               f"cyan = steer attractors. Budget {budget}, tau {tau}.")
    return {"ok": True, "schema": SCHEMA, "image": str(out_p), "kind": "trail_map",
            "n": n, "goals": len(goals), "frames": frames, "seams_final": len(seams_final),
            "caption": caption}


def animate(goals: list[tuple[float, ...]] | None = None, *, n: int = 24, frames: int = 40,
            budget: float = 0.6, tau: float = 0.02, w: int = 512, h: int = 512,
            duration: int = 120, out: str | None = None) -> dict[str, Any]:
    """Render the flock moving along its INTENDED paths as an animated GIF.

    Each frame: faint planned trails behind, current glowing knots, seams flashing red (the
    frontier-spend points), cyan steer attractors. Deterministic + $0 (same inputs -> same GIF).
    """
    from PIL import Image

    goals = goals or [(0.78, 0.78)]
    res = evolve(goals, n=n, frames=frames, budget=budget, tau=tau)
    frames_img: list[Image.Image] = []
    for t in range(frames):
        seams_at_t = res["seams"].get(t, [])
        frames_img.append(_frame(res["paths"], seams_at_t, t, res["steer"], w, h,
                                 show_trails=True, show_seams=True))
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / f"flock_anim_{len(goals)}g_{n}a_{frames}f.gif"
    frames_img[0].save(str(out_p), save_all=True, append_images=frames_img[1:],
                       duration=duration, loop=0)
    # static trail map alongside (the single-frame 'show it on a map')
    map_res = trail_map(goals, n=n, frames=frames, budget=budget, tau=tau,
                        w=w, h=h, out=str(out_p.with_suffix(".png")))
    return {"ok": True, "schema": SCHEMA, "image": str(out_p), "kind": "gif",
            "n": n, "goals": len(goals), "frames": frames, "duration_ms": duration,
            "seams_total": sum(len(v) for v in res["seams"].values()),
            "trail_map": map_res.get("image"), "caption":
            f"Flock intended-path animation: {n} agents, {len(goals)} goal(s), {frames} frames. "
            f"Trails = planned paths, red = seams (frontier spend), cyan = steer."}


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(goals: list[tuple[float, ...]] | None = None, *, n: int = 16, frames: int = 20,
           budget: float = 0.6, tau: float = 0.02, w: int = 256, h: int = 256,
           runs: int = 2) -> dict[str, Any]:
    """GOLDEN DETERMINISM SELF-CHECK (HyperFrames contract, steal 2026-08-23).

    Render the SAME spec `runs` times and assert byte-identical output. Same input -> same
    sha256 -> the artifact is content-addressable (verkle-able) and regression-testable
    (a verify_gate can hash render output, not just re-run it). Proves the flock renderer is
    truly deterministic, not just claimed to be.
    """
    goals = goals or [(0.78, 0.78)]
    digests: list[str] = []
    paths: list[Path] = []
    try:
        for i in range(runs):
            tmp = ART_DIR / f"_verify_{i}.gif"
            paths.append(tmp)
            animate(goals, n=n, frames=frames, budget=budget, tau=tau, w=w, h=h, out=str(tmp))
            digests.append(_sha256(tmp))
        ok = len(set(digests)) == 1
        return {"ok": True, "schema": SCHEMA, "deterministic": ok, "digests": digests,
                "content_address": digests[0] if ok else None, "runs": runs,
                "note": ("same input -> same sha256 (content-addressable, verkle-able, "
                         "regression-testable)" if ok else
                         "NON-DETERMINISTIC: digests differ — fix the renderer")}
    finally:
        for p in paths:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "evolve(goals) -> intended paths (cheap, deterministic)",
            "renders": "trail_map() static pathfield PNG; animate() animated GIF; verify() golden "
                       "determinism self-check (same input -> same sha256)",
            "cost": "deterministic + $0 (no LLM); preview matches real flock_shader function",
            "deps": "PIL + numpy"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="flock-anim")
    ap.add_argument("--goals", nargs="*", type=float, default=[0.78, 0.78])
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--budget", type=float, default=0.6)
    ap.add_argument("--tau", type=float, default=0.02)
    ap.add_argument("--map", action="store_true", help="render static trail map only")
    a = ap.parse_args()
    goals = list(zip(a.goals[0::2], a.goals[1::2])) if len(a.goals) >= 2 else [(a.goals[0], a.goals[0])]
    if a.map:
        print(_json(trail_map(goals, n=a.n, frames=a.frames, budget=a.budget, tau=a.tau)))
    else:
        print(_json(animate(goals, n=a.n, frames=a.frames, budget=a.budget, tau=a.tau)))


def _json(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
