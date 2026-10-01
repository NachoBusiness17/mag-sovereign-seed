"""Tapestry visual grammar — Steiniger temperature + Verkle knot shapes (ops only).

Maps tension_index / S / Q_proxy to suggestive geometry — not physics cosplay.
Used by mag/tapestry.py pack builder and dashboard/static/tapestry.js renderer.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def steiniger_temperature(
    *,
    tension_index: float | None = None,
    S: float | None = None,
    Q_proxy: float | None = None,
) -> float:
    """0=cold/static · 1=hot/multi-frame tension (visual metaphor)."""
    parts: list[float] = []
    if tension_index is not None:
        parts.append(_clamp(float(tension_index)))
    if S is not None:
        # S roughly in [-8, 4] in tapestry — map to 0..1
        parts.append(_clamp((float(S) + 4.0) / 10.0))
    if Q_proxy is not None:
        parts.append(_clamp(float(Q_proxy)))
    if not parts:
        return 0.45
    return _clamp(sum(parts) / len(parts))


def tension_band(temp: float) -> str:
    if temp < 0.28:
        return "cold"
    if temp < 0.52:
        return "neutral"
    if temp < 0.72:
        return "warm"
    return "hot"


def knot_params_from_hash(seed: str) -> tuple[int, int, float]:
    """Deterministic trefoil-family (p,q) + twist from leaf/tip hash."""
    h = hashlib.sha256((seed or "mag").encode()).digest()
    p = 2 + (h[0] % 4)  # 2..5
    q = 3 + (h[1] % 5)  # 3..7
    if p == q:
        q = (q % 5) + 3
    twist = (h[2] / 255.0) * math.tau
    return p, q, twist


def visual_profile(
    kind: str,
    *,
    tension_index: float | None = None,
    S: float | None = None,
    Q_proxy: float | None = None,
    chain_index: int = 0,
    seed: str = "",
    n_children: int = 0,
    duration_min: float | None = None,
    core: bool = False,
) -> dict[str, Any]:
    """Shape + scale hints for Three.js — stored on each tapestry node."""
    temp = steiniger_temperature(tension_index=tension_index, S=S, Q_proxy=Q_proxy)
    band = tension_band(temp)
    k = (kind or "unknown").lower()

    if k == "root":
        return {
            "shape": "icosahedron",
            "scale": [1.15, 1.15, 1.15],
            "temp": temp,
            "band": band,
            "emissive": 0.55,
            "note": "chain tip — cold anchor",
        }

    if k == "session":
        # Ellipsoid: stretch Y with duration; XZ with tension (dynamic body swell)
        dur = _clamp((duration_min or 30.0) / 180.0) if duration_min else 0.35
        sx = 0.85 + 0.55 * temp
        sy = 0.75 + 0.85 * dur + 0.25 * temp
        sz = 0.85 + 0.45 * temp
        return {
            "shape": "ellipsoid",
            "scale": [sx, sy, sz],
            "temp": temp,
            "band": band,
            "emissive": 0.35 + 0.45 * temp,
            "note": "workday bead — static/dynamic tension",
        }

    if k == "lattice":
        p, q, twist = knot_params_from_hash(seed or f"chain:{chain_index}")
        # Chain depth modulates knot tightness
        tight = 0.72 + 0.08 * (chain_index % 4)
        return {
            "shape": "torus_knot",
            "scale": [tight, tight, tight],
            "temp": max(0.12, min(0.42, temp * 0.5)),
            "band": "cold",
            "knot_p": p,
            "knot_q": q,
            "knot_twist": twist,
            "chain_index": chain_index,
            "emissive": 0.22,
            "ghost": True,
            "note": "Verkle leaf — topological commitment bead",
        }

    if k == "subsession":
        sc = 0.55 + 0.08 * min(n_children, 8)
        return {
            "shape": "tetrahedron",
            "scale": [sc, sc * (0.9 + 0.2 * temp), sc],
            "temp": temp,
            "band": band,
            "emissive": 0.28 + 0.35 * temp,
            "note": "operator turn — hot prompt surface",
        }

    if k == "run":
        sc = 0.5 + 0.06 * min(n_children, 12)
        return {
            "shape": "octahedron",
            "scale": [sc, sc * 1.15, sc],
            "temp": min(0.65, temp * 0.85),
            "band": band,
            "emissive": 0.32,
            "note": "orchestrator run — tool loop crystal",
        }

    if k == "theme":
        sc = 0.65 + 0.05 * min(n_children, 20)
        return {
            "shape": "dodecahedron",
            "scale": [sc, sc * 0.75, sc],
            "temp": temp,
            "band": band,
            "emissive": 0.25,
            "core": core,
            "note": "theme cluster — slow cold basin",
        }

    if k == "doc":
        return {
            "shape": "box",
            "scale": [1.2, 0.35, 1.0],
            "temp": 0.18,
            "band": "cold",
            "emissive": 0.2,
            "note": "constitution shell",
        }

    if k == "turn":
        return {
            "shape": "sphere",
            "scale": [0.65 + 0.25 * temp, 0.65 + 0.25 * temp, 0.65 + 0.25 * temp],
            "temp": temp,
            "band": band,
            "emissive": 0.3,
            "note": "summary bullet",
        }

    return {
        "shape": "sphere",
        "scale": [0.7, 0.7, 0.7],
        "temp": temp,
        "band": band,
        "emissive": 0.25,
        "note": kind,
    }


def lattice_chain_offset(chain_index: int, *, x: float, y: float, z: float) -> tuple[float, float, float]:
    """Stagger Verkle beads along a micro-helix under the day bead."""
    t = chain_index * 0.85
    return (
        x + 0.22 * math.cos(t),
        y - 0.75 - 0.14 * chain_index,
        z + 0.22 * math.sin(t),
    )
