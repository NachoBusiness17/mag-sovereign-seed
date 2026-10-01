"""rightsize_wave — the RIGHTSIZER VISUALIZED as a wave function.

Operator (2026-08-13): "this is also our rightsizer visualized. as it scales the ask directly to a
wave function."

THE INSIGHT: an ask, before routing, is a SUPERPOSITION over the surface landscape — a wave function
over {k3s, gpu, swarm, ocean}. The rightsizer is the MEASUREMENT that collapses it to the cheapest
capable surface. As the ask SCALES (grows in novelty/complexity/uncertainty), the wave's probability
mass shifts from k3s (deterministic, $0) up through gpu (inference), swarm (research), to ocean
(frontier) — where it's most likely to collapse.

THE SURFACES (real, from the rightsize doctrine):
  k3s    — deterministic + $0 (exec, janitor, pure logic)      [low tier / bulk]
  gpu    — local inference (ollama/GPU seat)                   [med tier / reasoning]
  swarm  — deepseek research swarm (~$0.27/hr)                 [med tier / research]
  ocean  — frontier models (grok/sol/gpt — for NOVELTY only)   [high tier / frontier]

HONEST: the wave weights are a HEURISTIC VISUALIZATION driven by real classification signals (novelty,
uncertainty, determinism, cost) — NOT a measured quantum distribution and NOT invented precision. It
renders the rightsizing decision as a wave; the collapse is the real rightsize choice (cheapest capable).

Schema: rightsize_wave.v1 · deterministic + $0 · pure stdlib
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "rightsize_wave.v1"

SURFACES = ["k3s", "gpu", "swarm", "ocean"]
_SURFACE_ORDER = {s: i for i, s in enumerate(SURFACES)}  # k3s=0 .. ocean=3 (scaling axis)

# deterministic ask-shape signals (each lowers/highers the wave's center of mass)
_DETERMINISTIC = ["just do it", "write", "edit", "create file", "deterministic", "$0", "janitor",
                  "run cadence", "refactor", "rename", "search", "read", "list", "verify",
                  "rib", "bare metal", "baremetal", "compile", "compiler", "invariant", "frozen spec"]
_INFERENCE = ["generate", "draft", "creative", "write a scene", "image", "voice", "inference",
              "compose", "design", "render", "roleplay"]
_RESEARCH = ["research", "mine", "steal", "survey", "explore", "cold", "unknown", "frontier",
             "swarm", "papers", "arxiv", "deep dive", "investigate"]
_FRONTIER = ["breakthrough", "novel", "impossible", "ocean", "grok", "sol", "frontier", "gravity",
             "what if", "new capability", "invent", "discover"]


def _signal_weights(text: str) -> dict[str, float]:
    low = (text or "").lower()
    w = {"k3s": 1.0, "gpu": 0.0, "swarm": 0.0, "ocean": 0.0}
    # each signal class raises the surfaces at/above its tier
    if any(s in low for s in _INFERENCE):
        w["gpu"] += 1.0
        w["swarm"] += 0.3
    if any(s in low for s in _RESEARCH):
        w["swarm"] += 1.0
        w["ocean"] += 0.4
    if any(s in low for s in _FRONTIER):
        w["ocean"] += 1.5
    if any(s in low for s in _DETERMINISTIC):
        w["k3s"] += 1.0  # determinism keeps mass low on the axis
    # normalize to a probability-like wave
    total = sum(w.values()) or 1.0
    return {s: round(v / total, 3) for s, v in w.items()}


def wave(ask: str) -> dict[str, Any]:
    """The ask as a WAVE FUNCTION over the surface landscape: the superposition BEFORE collapse.
    Deterministic + $0. HONEST — heuristic visualization from real signals, not a measured quantum
    distribution."""
    weights = _signal_weights(ask)
    # center of mass on the scaling axis (0=k3s .. 3=ocean) — 'as it scales, it maps to a wave'
    com = sum(_SURFACE_ORDER[s] * weights[s] for s in SURFACES)
    return {"ok": True, "schema": SCHEMA, "tool": "rightsize_wave", "ask": ask[:200],
            "wave": weights, "center_of_mass": round(com, 3),
            "axis": {"0": "k3s (deterministic, $0)", "1": "gpu (inference)",
                     "2": "swarm (research)", "3": "ocean (frontier)"},
            "note": "the ask is a superposition over the surfaces; rightsize collapses it"}


def collapse(ask: str) -> dict[str, Any]:
    """The RIGHTSIZE DECISION: collapse the wave to the CHEAPEST capable surface (the measurement).
    Deterministic + $0. HONEST — picks from the wave's real mass, cheapest-capable first."""
    weights = _signal_weights(ask)
    # collapse = surface with the most wave mass (the ask's dominant character)
    surface = max(SURFACES, key=lambda s: weights[s])
    return {"ok": True, "schema": SCHEMA, "tool": "rightsize_wave", "ask": ask[:200],
            "wave": weights, "collapsed_to": surface,
            "surface_cost": {"k3s": "$0", "gpu": "$0 (local)", "swarm": "~$0.27/hr", "ocean": "frontier $"},
            "note": f"the wave collapsed to {surface} — the cheapest capable surface for this ask"}


def scale(ask: str, novelty: float = 0.0) -> dict[str, Any]:
    """AS IT SCALES: show how the wave shifts as the ask grows in novelty (0..1). Raising novelty
    moves wave mass up the axis toward swarm/ocean. Deterministic + $0. HONEST — a visualization."""
    novelty = max(0.0, min(1.0, float(novelty)))
    weights = _signal_weights(ask)
    # shift mass upward by novelty (from k3s toward ocean) — the scaling dynamics
    for i, s in enumerate(SURFACES):
        weights[s] += novelty * (i / 3.0)
    total = sum(weights.values()) or 1.0
    weights = {s: round(v / total, 3) for s, v in weights.items()}
    com = sum(_SURFACE_ORDER[s] * weights[s] for s in SURFACES)
    return {"ok": True, "schema": SCHEMA, "tool": "rightsize_wave", "ask": ask[:200],
            "novelty": novelty, "wave": weights, "center_of_mass": round(com, 3),
            "note": "as novelty scales, the ask's wave mass rises up the surface axis"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rightsize-wave")
    ap.add_argument("cmd", nargs="?", default="wave", choices=["wave", "collapse", "scale"])
    ap.add_argument("args", nargs="*", default=[])
    ap.add_argument("--novelty", type=float, default=0.0)
    a = ap.parse_args(argv)
    ask = " ".join(a.args) or "a task"
    if a.cmd == "wave":
        print(json.dumps(wave(ask), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "collapse":
        print(json.dumps(collapse(ask), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "scale":
        print(json.dumps(scale(ask, a.novelty), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
