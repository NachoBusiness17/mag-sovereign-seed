"""lens_shader — map the ENTIRE operational stack onto OUR shader language (flock_shader.v1).

Operator (2026-08-11): "we need to map this all to our understanding of our shader language."

THE SHADER LANGUAGE (flock_shader): agent = a PIXEL, field = the TEXTURE, ghost = the RENDERER.
A shader is a PURE FUNCTION (uniforms -> color); a million pixels render for ~nothing in lockstep.
Cheap everywhere, shade the SEAMS. (seed, uniforms) -> state, deterministic + $0.

THIS MODULE re-expresses the whole stack as ONE shader program:
    LENS            -> a SHADER   (pure function over the shared field, one per swarm lens)
    shared surface  -> the FRAME BUFFER / TEXTURE (every pixel is a lens cell)
    user signals    -> the UNIFORMS (iTime=clock, iMouse=steer attractor = the active lens,
                       budget = how much frontier shading this frame is allowed)
    trigger_learn   -> the SEAM detector (where lenses disagree = which lens is hot -> iMouse)
    gpu_lifecycle   -> the RENDER TARGET (shader runs on GPU when free, CPU otherwise)
    steal lensing   -> FRAGMENTS shaded into a lens (novelty=color, lens=which shader samples,
                       shard=which texture bank)
    dashboard views -> the CHANNELS / outputs the program writes (flock/world/emerge frames)

THE SHADER CONTRACT PER LENS (same shape as flock_shader.shade):
    shade(seed, uniforms) -> {color, weight, note}   pure, $0, data-parallel over lenses

Schema: lens_shader.v1 · deterministic + $0 · reuse: flock_shader, trigger_learn, gpu_lifecycle,
invariant_ledger, steal_lens
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "lens_shader.v1"

# ── The LENSES as shaders — each maps to a flock_shader AgentSeed role ──────────
# Each lens is a pure function (seed, uniforms) -> color, sampled over the shared field.
LENSES: dict[str, dict[str, Any]] = {
    "memory/invariant": {"role": "invariant", "domain": "memory", "kind": "invariant",
                         "module": "percolator/research_class/shadow_graph",
                         "color": (0.30, 0.80, 0.70)},   # teal
    "economics/cost":   {"role": "cost", "domain": "economics", "kind": "mechanism",
                         "module": "cache_shard/usage_monitor/flock_usage_guard",
                         "color": (0.90, 0.75, 0.20)},   # amber
    "compiler/world":   {"role": "world", "domain": "compiler", "kind": "world",
                         "module": "rib_bus/world_rib/jones_lens",
                         "color": (0.35, 0.60, 0.85)},   # blue
    "swarm/detect":     {"role": "swarm", "domain": "swarm", "kind": "mechanism",
                         "module": "flock_shader/swarm_emerge/emergence",
                         "color": (0.80, 0.40, 0.90)},   # violet
    "steal-lens":       {"role": "steal", "domain": "memory", "kind": "steal",
                         "module": "steal_lens/novelty_lens",
                         "color": (0.95, 0.45, 0.35)},   # coral
    "security/guard":   {"role": "guard", "domain": "security", "kind": "guard",
                         "module": "cast_guard",
                         "color": (0.80, 0.25, 0.25)},   # red
    "wearable/surface": {"role": "wear", "domain": "surface", "kind": "surface",
                         "module": "wearable_swarm/cast_server",
                         "color": (0.55, 0.85, 0.55)},   # green
}


@dataclass
class LensSeed:
    """This lens-pixel's identity (a point in the lensing map, like a fragment coordinate)."""
    lens: str
    pos: tuple[float, float] = (0.0, 0.0)
    role: str = "lens"


@dataclass
class LensUniforms:
    """The uniforms every lens-shader reads = the shared surface state.
    iTime      : loop clock (which frame we're on).
    iMouse     : the STEER attractor = the ACTIVE lens (from trigger_learn seam detection).
    budget     : how much frontier (expensive) shading this frame allows.
    gpu        : render target from gpu_lifecycle (gpu / cpu).
    channels   : extra input textures (live metric values from ghost.sense()).
    """
    iTime: int = 0
    iMouse: tuple[str, float] | None = None      # (active_lens, weight)
    budget: float = 1.0
    gpu: str = "cpu"
    channels: dict[str, float] = dc_field(default_factory=dict)


def _hash01(s: str) -> float:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16) % 10_000 / 10_000.0


def shade(seed: LensSeed, u: LensUniforms) -> dict[str, Any]:
    """The per-lens PURE function: (lens, uniforms) -> color/weight/note. $0, data-parallel."""
    meta = LENSES.get(seed.lens, {"color": (0.5, 0.5, 0.5), "module": "?"})
    # base weight: how much live signal this lens carries in this frame
    base = u.channels.get(seed.lens, 0.0)
    # boost if this lens is the active steer (iMouse) or shares its domain
    active_boost = u.iMouse is not None and u.iMouse[0] == seed.lens
    weight = max(0.0, min(1.0, base + (0.5 if active_boost else 0.0) + _hash01(seed.lens) * 0.1))
    # color: fade by weight so the active lens glows brighter in the frame
    c = meta["color"]
    color = tuple(min(1.0, c[i] * (0.4 + 0.6 * weight)) for i in range(3))
    return {"lens": seed.lens, "role": meta["role"], "weight": round(weight, 3),
            "color": color, "module": meta["module"],
            "active": bool(active_boost),
            "hash": hashlib.sha256(
                f"{seed.lens}:{u.iTime}:{weight}".encode("utf-8")).hexdigest()[:8]}


def render(lenses: list[str], u: LensUniforms) -> list[dict[str, Any]]:
    """Render the lensing map: evaluate the SAME pure shade across all lenses (data-parallel).
    This IS the shader program = the swarm lensing maps as one texture/frame."""
    return [shade(LensSeed(l), u) for l in lenses]


def seams(states: list[dict[str, Any]], *, tau: float = 0.25) -> list[dict[str, Any]]:
    """The SEAMS in the lensing map: lenses whose weight disagrees with the frame consensus.
    The hot lens (highest above-consensus weight) = the trigger_learn seam = where to steer."""
    if not states:
        return []
    mean = sum(s["weight"] for s in states) / len(states)
    out = sorted(states, key=lambda s: -(s["weight"] - mean))
    return [{"lens": s["lens"], "weight": s["weight"], "above_mean": round(s["weight"] - mean, 3),
             "active": s["active"]} for s in out if s["weight"] - mean > tau]


def inject(u: LensUniforms, seam_list: list[dict[str, Any]], *, t: int) -> LensUniforms:
    """Steer the next frame at the seams: bias iMouse toward the hot lens (from trigger_learn /
    this seam detector). Mirrors flock_shader.inject."""
    return LensUniforms(iTime=t, iMouse=(seam_list[0]["lens"], seam_list[0]["weight"]) if seam_list
                        else u.iMouse, budget=u.budget, gpu=u.gpu, channels=dict(u.channels))


# ── BUILD THE UNIFORMS FROM THE LIVE SHARED SURFACE (ghost.sense + trigger_learn + gpu) ──
def uniforms_from_state(state: dict[str, Any]) -> LensUniforms:
    """Fold ghost.sense()/trigger_learn/gpu_lifecycle into ONE set of shader uniforms."""
    trig = (state.get("trigger") or {}).get("active") or []
    iMouse = (trig[0]["lens"], trig[0]["weight"]) if trig else None
    gpu = "gpu" if (state.get("gpu") or {}).get("free_for_render") else "cpu"
    ch: dict[str, float] = {}
    # live metric channels per lens (from percolator/emergence/steal/gpu)
    p = state.get("percolator") or {}
    ch["memory/invariant"] = min(1.0, (p.get("n_invariants", 0) or 0) / 50)
    em = state.get("emergence") or {}
    ch["swarm/detect"] = min(1.0, len(em.get("metrics", {})) / 20) if em.get("metrics") else 0.2
    sl = (state.get("steal_lens") or {})
    ch["steal-lens"] = min(1.0, sl.get("n", 0) / 20) if sl.get("n") else 0.2
    ch["economics/cost"] = min(1.0, (state.get("cache_hit_pct") or 99) / 100)
    g = state.get("gpu") or {}
    ch["compiler/world"] = 1.0 if g.get("free_for_render") else 0.3
    ch["security/guard"] = 1.0 if (state.get("cast_probes") or 0) else 0.1
    ch["wearable/surface"] = 0.3
    return LensUniforms(iTime=int((state.get("ts") or "0")[-3:]) or 0,
                        iMouse=iMouse, gpu=gpu, channels=ch)


def program(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """The SHADER PROGRAM: build uniforms from the live surface, render all lenses, find seams,
    steer. This is the dashboard's lens-shader frame."""
    st = state if state is not None else {}
    try:
        from mag import trigger_learn
        st = dict(st)
        st.setdefault("trigger", trigger_learn.decide())
    except Exception:
        pass
    u = uniforms_from_state(st)
    frame = render(list(LENSES.keys()), u)
    seam = seams(frame)
    # render target from gpu_lifecycle (GPU free? render there)
    target = u.gpu
    return {"ok": True, "schema": SCHEMA, "ts": st.get("ts"),
            "shader": "lens_shader.v1 (flock_shader.v1 mapping)",
            "uniforms": {"iTime": u.iTime, "iMouse": u.iMouse, "gpu_target": u.gpu,
                         "budget": u.budget},
            "frame": frame, "seams": seam,
            "active_lens": seam[0]["lens"] if seam else None,
            "render_target": target,
            "note": "cheap everywhere, shade the seams: lenses = shaders, signals = uniforms, "
                    "GPU = render target, steals = fragments, dashboard = the frame buffer"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "program(state)->shader frame (lenses rendered + seams + active_lens); "
                        "uniforms_from_state()->lens uniforms from live surface",
            "cost": "deterministic + $0", "n_lenses": len(LENSES)}


if __name__ == "__main__":
    print(json.dumps(program(), indent=2, default=str))
