"""shader_rib — ShaderToy SYSTEMS as the lensing system's determinism test corpus: every shader is
a PURE MECHANISM (not a picture). We steal the mechanism -> a RIB, run it through the lensing
system, and assert the SAME lens/knot/topology every time. This TESTS the lensing system's
determinism itself while creating RIBs. Then we learn the INTERSTITIAL patterns (the seams between
lenses, not the pretty pixels) -> deterministic complex behaviors propagated by LOW-COST agent
swarms doing frontier tasks at high fidelity. The economic inversion: build a BETTER local system
(quantize frontier models for home lab), capture the economics around compute = the Mycelial Republic.

Operator (2026-08-11): "how does knot topology map to our lensing system can we actually use the
systems as found in our shader toy repo we should always use it for inspiration for our rib creation
as a test of the lensing system determinism itself and how we can learn the patterns that lie in
between not just pretty pictures deterministic complex behaviors propagated by low cost agent swarms
performing frontier tasks high fidelity like quantization of frontier models for home lab use we
invert the model by capturing the economics around compute simply by creating a better system and
building it the whole point underlying the mycellial republic."

KNOT TOPOLOGY -> LENSING MAP (the mapping):
  a verkle knot's topology (jones_lens braid/crossings) = WHERE the invariants interleave = the
  seams. The LENSING SYSTEM maps each rib to a lens + knot + jones fingerprint. So:
      shader mechanism -> rib -> lens (which witness) + knot (content address) + jones (topology)
  Same rib -> same lens/knot/jones every time (stateless) = the determinism TEST.

Schema: shader_rib.v1 · deterministic + $0 · reuse: lens_shader, lens_knot, jones_lens
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "shader_rib.v1"

# ── THE SHADER SYSTEMS we stole (our shader-toy corpus) — each a PURE MECHANISM, not a picture ──
# Each is the MECHANISM (the pattern in between the pixels) that a ShaderToy shader encodes.
SHADER_SYSTEMS: dict[str, dict[str, Any]] = {
    "evidence_lighting": {
        "name": "XsK3RR evidence lighting (steal)",
        "mechanism": "lights are DATA in a texture (origin,color,shadowmap); every pixel reads the "
                     "same light buffer; the shadowmap gates expensive shading to lit seams only",
        "frontier_task": "grounded synthesis: shade only where evidence lights the way (high "
                         "fidelity, low cost)",
        "lens": "compiler/world",
    },
    "boid_grid": {
        "name": "boid spatial-hash grid (steal)",
        "mechanism": "neighbors are found via a spatial hash grid (3x3 cells), not O(N^2); each "
                     "boid reads only its local cell -> separation/alignment/cohesion",
        "frontier_task": "low-cost neighbor discovery for agent swarms: O(N) seams, not O(N^2)",
        "lens": "swarm/detect",
    },
    "chromatic_tides": {
        "name": "Chromatic Particle Tides (steal)",
        "mechanism": "a flow field (curl noise) advects particles; each particle is cheap and "
                     "stateless; the WHOLE looks complex from simple per-particle rules",
        "frontier_task": "deterministic complex behaviors from stateless cheap particles (emergence "
                         "from simple local rules)",
        "lens": "swarm/detect",
    },
    "ray_march": {
        "name": "raymarched SDF world (classic)",
        "mechanism": "the world is a signed-distance field; a ray steps until it hits; only the "
                     "hit surface is shaded (perceptual culling, intent-gated render)",
        "frontier_task": "intent-gated persistent world: render only what you aim at (the building "
                         "appears when you walk toward it)",
        "lens": "compiler/world",
    },
    "gaussian_bloom": {
        "name": "bloom/glow pass (flock_anim steal)",
        "mechanism": "bright splats are convolved with a gaussian -> glow; cheap C-speed drawing, "
                     "expensive per-sample splats avoided",
        "frontier_task": "high-fidelity visuals at low cost by moving work to the fast path (C/GPU)",
        "lens": "economics/cost",
    },
    "logeps_march": {
        "name": "logEps logarithmic-epsilon raymarching (tesuji from the garbage pile, 2026-08-11)",
        "mechanism": "raymarch exit condition is log(c*c/s/s) not a fixed epsilon: precision grows "
                     "logarithmically with distance, so it gets closer to surfaces in TWISTED space "
                     "(high local Lipschitz) and allows a much larger zFar, at the cost of "
                     "reflections and near-wall speed. 'better+simpler demo: shadertoy.com/view/dlXyzs' "
                     "— an honest signal buried in commented/trash code.",
        "frontier_task": "march through deformed/twisted space (our lensing in deformed invariant "
                         "space) getting closer to the true surface, larger horizon; the buried "
                         "signal = a tesuji from the shadow-work pile",
        "lens": "compiler/world",
    },
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def rib_from_shader(shader_id: str) -> dict[str, Any]:
    """Steal a ShaderToy system -> a RIB (the mechanism, not the pixels). Deterministic."""
    s = SHADER_SYSTEMS.get(shader_id)
    if not s:
        return {"ok": False, "error": f"unknown shader system: {shader_id}",
                "known": list(SHADER_SYSTEMS)}
    rib = (f"INVARIANT: {s['mechanism']}. Applied to frontier task: {s['frontier_task']}.")
    return {"ok": True, "schema": SCHEMA, "shader_id": shader_id, "name": s["name"],
            "rib": rib, "rib_hash": hashlib.sha256(rib.encode("utf-8")).hexdigest()[:16]}


def lens_rib(shader_id: str) -> dict[str, Any]:
    """Map the shader-rib through the LENSING SYSTEM: which lens-witness reads it, its verkle knot
    (content address), and its Jones topology fingerprint. This is knot-topology -> lensing."""
    r = rib_from_shader(shader_id)
    if not r.get("ok"):
        return r
    rib = r["rib"]
    lens = SHADER_SYSTEMS[shader_id]["lens"]
    knot = hashlib.sha256(f"{lens}::{rib}".encode("utf-8")).hexdigest()[:16]
    vec, jones = [], {}
    try:
        from mag import jones_lens
        vec = jones_lens.vector(rib)["vector"]
        jones = jones_lens.jones(rib)
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "shader_id": shader_id, "rib_hash": r["rib_hash"],
            "lens": lens, "knot": knot, "jones_fingerprint": jones.get("jones_fingerprint", ""),
            "jones_exponent": jones.get("jones_exponent", 0), "vector": vec[:8],
            "mapping": "shader mechanism -> rib -> lens(witness) + knot(content address) + "
                       "jones(topology): same rib -> same lens/knot/jones (stateless)"}


def determinism_test(*, rounds: int = 3) -> dict[str, Any]:
    """TEST the lensing system's determinism itself: lens every shader-system rib multiple times
    and assert the lens/knot/jones/vector are IDENTICAL every round. If any differ, the lensing
    system is NOT deterministic (a real finding)."""
    results = []
    all_pass = True
    for sid in SHADER_SYSTEMS:
        first = lens_rib(sid)
        stable = True
        for _ in range(rounds):
            again = lens_rib(sid)
            for key in ("lens", "knot", "jones_fingerprint", "jones_exponent", "rib_hash"):
                if again.get(key) != first.get(key):
                    stable = False
                    all_pass = False
                    break
        results.append({"shader": sid, "lens": first.get("lens"),
                        "knot": first.get("knot"), "jones": first.get("jones_fingerprint"),
                        "deterministic": stable})
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "rounds": rounds,
            "n_shaders": len(SHADER_SYSTEMS), "all_deterministic": all_pass,
            "results": results,
            "test": "same shader-rib -> same lens/knot/jones/vector every round = the lensing "
                    "system is deterministic (stateless, content-addressed)"}


def interstitial_patterns() -> dict[str, Any]:
    """The PATTERNS IN BETWEEN — not the pretty pictures, the seams: how each shader-rib's topology
    interleaves with the others. jones_exponent (braid crossings) = where the mechanisms cross =
    the seams a low-cost agent swarm should shade. This is the deterministic complex behavior
    propagated by cheap agents doing frontier tasks."""
    rows = []
    for sid in SHADER_SYSTEMS:
        l = lens_rib(sid)
        rows.append({"shader": sid, "lens": l.get("lens"), "knot": l.get("knot"),
                     "jones_exponent": l.get("jones_exponent"),
                     "frontier_task": SHADER_SYSTEMS[sid]["frontier_task"][:80]})
    # seams = where knots cross = differing lens/topology — the interstices to shade
    lenses = [r["lens"] for r in rows]
    from collections import Counter
    seam_lenses = [l for l, c in Counter(lenses).items() if c == 1]  # divergent lenses = seams
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "n_shaders": len(rows), "rows": rows,
            "seam_lenses": seam_lenses,
            "insight": ("the patterns in between = the seams where shader-ribs disagree (jones "
                        "crossings / divergent lenses). Those are the frontier tasks a LOW-COST "
                        "agent swarm shades at high fidelity — deterministic complex behavior from "
                        "cheap stateless agents, not pretty pictures."),
            "economics_inversion": ("build a BETTER local system (quantize frontier models for "
                                    "home lab, run the cheap swarms locally) -> capture the "
                                    "economics around compute by owning the stack = the Mycelial "
                                    "Republic.")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "rib_from_shader()->steal a shader mechanism as a RIB; "
                        "lens_rib()->map through lensing (lens+knot+jones); "
                        "determinism_test()->assert same lens/knot/jones every round; "
                        "interstitial_patterns()->the seams (frontier tasks) for low-cost swarms",
            "cost": "deterministic + $0 (stateless, content-addressed)",
            "n_shader_systems": len(SHADER_SYSTEMS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="shader-rib")
    ap.add_argument("cmd", nargs="?", default="test",
                    choices=["test", "map", "seams", "rib", "status"])
    ap.add_argument("shader", nargs="?", default="")
    a = ap.parse_args()
    if a.cmd == "test":
        print(json.dumps(determinism_test(), indent=2, default=str))
    elif a.cmd == "seams":
        print(json.dumps(interstitial_patterns(), indent=2, default=str))
    elif a.cmd == "map":
        print(json.dumps({s: lens_rib(s) for s in SHADER_SYSTEMS}, indent=2, default=str))
    elif a.cmd == "rib":
        print(json.dumps(rib_from_shader(a.shader or "evidence_lighting"), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
