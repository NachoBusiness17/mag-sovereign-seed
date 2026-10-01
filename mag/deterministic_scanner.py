"""deterministic_scanner — embed in the swarm for DETERMINISTIC SCANNING of STOCHASTIC environments.

Operator (2026-08-13): "tools like this used cleverly can be embedded in our swarms to use for
deterministic scanning of stochastic environments. steal"

A stochastic environment (a noisy signal, a live stream, an uncertain corpus) has no fixed answer —
but a DETERMINISTIC PROBE can measure it reproducibly: same seed + same inputs -> identical reading,
so the swarm can scan noise and get trustworthy, repeatable measurements instead of guesses.

STEAL (agentswarm — seeded determinism over stochastic space):
  * mulberry32(seed)      — deterministic PRNG (same seed -> same stream)
  * bootstrapCi(vals,b,s) — seeded resampling -> reproducible confidence interval (the 'seeded ->
                            deterministic' test proves it)
  * runSimulation(N,seed) — N seeded draws -> reproducible aggregate ('same inputs, same seed ->
                            identical result')
  * reconRepo()           — one batched probe of a possibly-noisy environment
ADAPTED: the swarm's NPCs carry these as tools to SCAN stochastic environments — reproducible
measurement, $0, honest (a measurement instrument, not a crystal ball).

Schema: deterministic_scanner.v1 · deterministic + $0 · pure stdlib
"""
from __future__ import annotations

import hashlib
import json
import statistics
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

SCHEMA = "deterministic_scanner.v1"


def mulberry32(seed: int) -> Any:
    """Deterministic PRNG (steal from agentswarm): same seed -> same stream, always. $0, pure.
    Python port — uses 32-bit masking (& 0xFFFFFFFF) in place of JS's unsigned >>>."""
    a = int(seed) & 0xFFFFFFFF

    def next_u() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = (a ^ ((a >> 15) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = (t + (((t ^ ((t >> 7) & 0xFFFFFFFF)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ ((t >> 14) & 0xFFFFFFFF)) & 0xFFFFFFFF) / 4294967296.0

    return next_u


def scan_measure(samples: list[float], *, seed: int = 1738, b: int = 1000) -> dict[str, Any]:
    """SEEDED BOOTSTRAP MEASUREMENT of a stochastic signal: reproducible mean + 95% CI from noisy
    samples. Same samples + same seed -> identical reading (the deterministic scan). $0. HONEST —
    it's a measurement instrument: it reports the signal's stable center + spread, never a fabrication."""
    vals = [float(x) for x in (samples or []) if isinstance(x, (int, float))]
    if not vals:
        return {"ok": False, "schema": SCHEMA, "tool": "scan_measure", "error": "no numeric samples"}
    rand = mulberry32(seed)
    means = []
    n = len(vals)
    for _ in range(b):
        total = 0.0
        for _ in range(n):
            total += vals[int(rand() * n) % n]
        means.append(total / n)
    means.sort()
    lo_i = max(0, round(b * 0.025) - 1)
    hi_i = min(b - 1, round(b * 0.975) - 1)
    return {"ok": True, "schema": SCHEMA, "tool": "scan_measure",
            "n": n, "seed": seed, "b": b,
            "mean": round(statistics.fmean(vals), 4),
            "ci_lo": round(means[lo_i], 4), "ci_hi": round(means[hi_i], 4),
            "sd": round(statistics.pstdev(vals), 4),
            "note": "seeded bootstrap measurement of the stochastic signal — reproducible, $0"}


def scan_probe(text: str, *, seed: int = 1738) -> dict[str, Any]:
    """DETERMINISTIC SIGNATURE PROBE of a text environment: hash the seed + text -> reproducible
    fingerprint, and scan the text for known signatures. $0. HONEST — signature-matching over real
    text, reproducible per seed."""
    text = (text or "")
    fp = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).hexdigest()[:16]
    low = text.lower()
    sigs = {
        "frontier_reasoning": ["hidden reasoning", "thinking tokens", "extract hidden", "1:1"],
        "one_structure": ["one circle", "are just", "same mechanism", "reveal"],
        "hidden_structure": ["watermark", "fingerprint", "invisible", "manufactured consent"],
        "standing_wave": ["strike the chord", "the chord", "spore", "mycelium"],
    }
    found = {k: [s for s in v if s in low] for k, v in sigs.items()}
    found = {k: v for k, v in found.items() if v}
    return {"ok": True, "schema": SCHEMA, "tool": "scan_probe", "seed": seed,
            "fingerprint": fp, "signatures": found, "chars": len(text),
            "note": "deterministic signature probe of the text environment — reproducible per seed"}


def scan_grid(environment: list[Any], *, seed: int = 1738, b: int = 1000) -> dict[str, Any]:
    """SCAN a stochastic ENVIRONMENT (a list of noisy readings) with a deterministic probe:
    reproducible center + spread + a seeded fingerprint of the whole grid. $0. HONEST — a
    measurement of the environment, not a claim about its cause."""
    nums = [float(x) for x in environment if isinstance(x, (int, float))]
    measure = scan_measure(nums, seed=seed, b=b) if nums else None
    fp = hashlib.sha256(f"{seed}:{json.dumps(environment, default=str)[:4000]}".encode("utf-8")).hexdigest()[:16]
    return {"ok": True, "schema": SCHEMA, "tool": "scan_grid", "cells": len(environment),
            "seed": seed, "fingerprint": fp, "measure": measure,
            "note": "deterministic scan of the stochastic environment — reproducible measurement"}


def mean_field(trajectories: list[list[float]]) -> dict[str, Any]:
    """DETERMINISTIC MAPPING of a stochastic model — the MEAN-FIELD projection.

    Operator (2026-08-13): 'a deterministic mapping of a stochastic model transforms random,
    probabilistic processes into fixed, predictable relationships... such as mean-field
    approximations, ordinary differential equations, or optimal transport maps.'

    Given a stochastic process as several noisy trajectories (each a time-series of values), project
    it into its DETERMINISTIC EQUIVALENT: the expected trajectory E[x_t] at each step — the mean-field
    ODE that averages out the noise into one fixed, predictable path. $0 + stdlib + deterministic
    (same trajectories -> same projection). HONEST: this is the mean-field/expected-value form; the
    optimal-transport map is the deeper form (not claimed here)."""
    trajs = [[float(x) for x in t if isinstance(x, (int, float))] for t in (trajectories or [])]
    trajs = [t for t in trajs if t]
    if not trajs:
        return {"ok": False, "schema": SCHEMA, "tool": "mean_field", "error": "no trajectories"}
    steps = max(len(t) for t in trajs)
    expected: list[float] = []
    spread: list[float] = []
    for i in range(steps):
        col = [t[i] for t in trajs if i < len(t)]
        if col:
            expected.append(round(statistics.fmean(col), 4))
            spread.append(round(statistics.pstdev(col) if len(col) > 1 else 0.0, 4))
    # the deterministic ODE form: x'(t) ≈ mean of the per-step increments (the drift)
    drift = []
    for i in range(1, len(expected)):
        drift.append(round(expected[i] - expected[i - 1], 4))
    return {"ok": True, "schema": SCHEMA, "tool": "mean_field",
            "n_trajectories": len(trajs), "steps": steps,
            "expected_trajectory": expected,          # E[x_t] — the mean-field path
            "per_step_spread": spread,                # how the noise collapses
            "drift_ode": drift,                        # the deterministic ODE increments
            "mapping": "mean-field / expected-trajectory (projection of the stochastic into the fixed)",
            "note": "deterministic mapping of the stochastic model — the expected trajectory (mean-field ODE)"}


def research(ask: str, *, surface: str = "det-scan") -> dict[str, Any]:
    """THE STOCHASTIC SEAM — a SEARCH SWARM over browsers (operator: 'easy and cheaply via swarm
    mechanics... a search swarm over browsers'). Route the ask to the swarm (cheap DeepSeek) via
    route_novel; the k8s worker drains it. This is the live-web research side — SEPARATE from the
    deterministic core (which stays $0/stdlib). HONEST: it routes the ask; the answer comes back
    when the swarm drains it, not synchronously here."""
    ask = (ask or "").strip()
    if not ask:
        return {"ok": False, "schema": SCHEMA, "tool": "research", "error": "empty ask"}
    try:
        from mag import swarm_surface
        routed = swarm_surface.route_novel(goal=f"search swarm: {ask}", surface=surface,
                                           lens="deterministic-scanner")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "tool": "research",
                "error": f"route_novel unavailable: {str(e)[:120]}"}
    return {"ok": True, "schema": SCHEMA, "tool": "research", "ask": ask[:200],
            "routed": routed.get("ok"), "task_id": routed.get("task_id") or routed.get("enqueued"),
            "note": "research ask routed to the search swarm (cheap deepseek, k8s-drained) — "
                    "the stochastic seam; deterministic core stays $0/stdlib"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="deterministic-scanner")
    ap.add_argument("cmd", nargs="?", default="measure",
                    choices=["measure", "probe", "grid", "mean-field", "research"])
    ap.add_argument("args", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=1738)
    ap.add_argument("--b", type=int, default=1000)
    a = ap.parse_args(argv)
    if a.cmd == "measure":
        vals = [float(x) for x in a.args if _isnum(x)]
        print(json.dumps(scan_measure(vals, seed=a.seed, b=a.b), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "probe":
        print(json.dumps(scan_probe(" ".join(a.args), seed=a.seed), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "grid":
        vals = [float(x) for x in a.args if _isnum(x)]
        print(json.dumps(scan_grid(vals, seed=a.seed, b=a.b), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "mean-field":
        print(json.dumps(mean_field([[]]), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "research":
        print(json.dumps(research(" ".join(a.args) or "deterministic mapping of a stochastic model"),
                         ensure_ascii=False, indent=2, default=str))
    return 0


def _isnum(x: str) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    raise SystemExit(main())
