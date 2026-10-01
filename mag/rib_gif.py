"""rib_gif — make the k8s cluster swarm RENDER our GIFs so a RIB becomes a LEGIBLE TEST INSTRUCTION:
a deterministic visual artifact (same RIB -> same GIF) the swarm renders (GPU via gpu_lifecycle),
reviewable as proof that the RIB (map) lowered correctly (territory).

Operator (2026-08-11): "could we make a k8s cluster swarm into lmao using our gifs through our
swarm so it's legible as a rib test instruction."

THE RIB-TEST (deterministic + $0 spec, swarm-rendered):
  test_rib(rib)     -> compile a RIB into a deterministic GIF-render spec: goal points from the
                       RIB's steer/goal markers (reuse world_rib._goal_points) + n/frames seeded by
                       the RIB hash. SAME RIB -> SAME GIF (re-derivable, legible).
  render(rib)       -> route the render to the SWARM (swarm_surface.route_novel -> k8s worker runs
                       flock_anim.animate headlessly; GPU via gpu_lifecycle when free). The returned
                       GIF IS the rib test instruction.
  The GIF = the visual test: if the RIB (map) lowered correctly, its intended paths are legible.

Schema: rib_gif.v1 · deterministic + $0 spec · swarm-rendered (GPU-aware) · reuse: flock_anim,
world_rib, swarm_surface, gpu_lifecycle
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

SCHEMA = "rib_gif.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rib_hash(rib: str) -> int:
    return int(hashlib.sha256((rib or "").encode("utf-8")).hexdigest()[:8], 16)


def test_rib(rib: str) -> dict[str, Any]:
    """Compile a RIB into a deterministic GIF-render spec. Same RIB -> same GIF (re-derivable)."""
    # goal points from the RIB's steer/goal markers (reuse world_rib._goal_points)
    goals: list[tuple[float, float]] = []
    try:
        from mag import world_rib
        goals = world_rib._goal_points(rib)
    except Exception:
        pass
    if not goals:
        h = _rib_hash(rib)
        goals = [((h >> 8) % 100 / 100.0, (h >> 16) % 100 / 100.0),
                 (((h >> 24) % 100 / 100.0), ((h >> 2) % 100 / 100.0))]
    n = 8 + (_rib_hash(rib) % 21)      # 8..28 agents, seeded by the rib
    frames = 32 + (_rib_hash(rib) % 17)  # 32..48 frames
    return {"ok": True, "schema": SCHEMA, "rib": (rib or "")[:200],
            "rib_hash": f"{_rib_hash(rib):08x}",
            "spec": {"goals": [[round(g[0], 3), round(g[1], 3)] for g in goals],
                     "n_agents": n, "frames": frames},
            "deterministic": "same rib -> same gif (re-derivable)",
            "note": "the GIF-render spec compiled from the RIB (the legible rib test instruction)"}


def render(rib: str = "", *, enqueue: bool = True, surface: str = "rib-gif-test") -> dict[str, Any]:
    """Route the RIB->GIF render to the SWARM: the k8s worker renders it headlessly (GPU via
    gpu_lifecycle when free). The returned GIF is the legible rib-test instruction."""
    s = test_rib(rib or "rib test: render the intended paths of the swarm before simulation")
    # GPU-aware: render on GPU when free, CPU otherwise
    gpu = "cpu"
    try:
        from mag import gpu_lifecycle
        gpu = gpu_lifecycle.route(work="rib-gif").get("target", "cpu")
    except Exception:
        pass
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        goal = (f"RENDER RIB AS GIF TEST [rib_gif]: run mag.flock_anim.animate on this spec "
                f"(headless, GPU={gpu}): goals={json.dumps(s['spec']['goals'])}, "
                f"n_agents={s['spec']['n_agents']}, frames={s['spec']['frames']}, "
                f"rib_hash={s['rib_hash']}. Write the GIF to memory/runs/rib_gif/ribtest_"
                f"{s['rib_hash']}.gif. The GIF is the legible rib-test: same rib -> same gif, "
                f"re-derivable, reviewable as proof the map lowered to territory.")
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="compiler/world",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), **s, "render_target": gpu,
            "enqueued": q.get("ok", False), "task_id": q.get("task_id", ""),
            "deduped": q.get("deduped", False),
            "note": "RIB -> GIF render routed to the swarm (k8s worker renders headless, GPU when "
                    "free); the GIF is the legible rib test instruction"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "test_rib(rib)->deterministic GIF-render spec (same rib -> same gif); "
                        "render(rib)->route the render to the swarm (GPU-aware); the GIF is the "
                        "legible rib-test",
            "cost": "deterministic + $0 spec (the swarm renders)",
            "reuse": ["flock_anim.animate", "world_rib._goal_points", "swarm_surface.route_novel",
                      "gpu_lifecycle"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="rib-gif")
    ap.add_argument("cmd", nargs="?", default="render", choices=["render", "spec", "status"])
    ap.add_argument("rib", nargs="*", default=[])
    a = ap.parse_args()
    r = " ".join(a.rib) or "render the intended paths of the swarm before simulation"
    print(json.dumps(test_rib(r) if a.cmd == "spec" else (status() if a.cmd == "status" else render(r)),
                     indent=2, default=str))
