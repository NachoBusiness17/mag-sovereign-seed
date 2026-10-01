"""wow_manifest — manifest the Turtle WoW/WoWHead foundation the CORRECT way: each invariant as a
VERKLE KNOT (structure), interpreted by a RIB, rendered through the RENDERING LANGUAGE.

OPERATOR (2026-08-12): "based on our verkle structure and rendering language" + "well the ribs
interpret that" + "yes" (to building it the right way). SELF-STEAL (reuses our own machinery):
  verkle_knot.append_verkle_knot  -> the VERKLE STRUCTURE (immutable content-addressed chain)
  rib_bus.publish_rib             -> the RIB INTERPRETS the invariant (doctrine layer)
  world_rib.compile               -> the RENDERING LANGUAGE (RIB -> world, re-derivable)

THE PATH (per invariant): invariant -> verkle knot (data) -> RIB interprets (instruction) ->
world_rib renders (output). The RIB is the interpreter between the verkle structure and the render.

Schema: wow_manifest.v1 · deterministic + $0 · reuse: verkle_knot, rib_bus, world_rib
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "wow_manifest.v1"

# The WoW-k8s foundation invariants (self-stolen from STEAL_WOW_MODDING_TURTLE_K8S_FOUNDATION).
WOW_INVARIANTS = [
    "WORLD: world state is a verkle-anchored chain (server-authoritative; workers are presentation and cannot falsify).",
    "MOD: addon/hook = RIB-as-mod via rib_bus.mount (additive, never shadow the authoritative path).",
    "SAVED: saved variables = per-domain memory/rib_bus/<domain>.json (durable mod state).",
    "EVENT: event-driven world = verkle event bus (mag:verkle / mag:rib / mag:sense), no polling.",
    "EMULATOR: emulator = k8s swarm (stateless workers re-render; verkle chain = replayable protocol).",
    "CONTENT: Turtle-style content pipeline = swarm-authored RIBs as custom content on a stable k8s core.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _knot(invariant: str, i: int) -> dict[str, Any]:
    """Append ONE WoW invariant as a VERKLE KNOT (the immutable structure). Deterministic $0."""
    from mag.verkle_knot import append_verkle_knot
    minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    commit = hashlib.sha256(invariant.encode("utf-8")).hexdigest()[:16]
    dossier = {
        "session_id": f"wow_manifest_{i}",
        "time": {"created_at": {"iso_minute": minute, "unix_minute": None, "date": None},
                 "updated_at": {"iso_minute": minute, "unix_minute": None, "date": None}},
        "scalar_knot": {"duration_minutes": 0.1, "tension_index": str(i), "residual_weight": 1.0,
                        "theme_vector": {"dominant": "wow_manifest", "basis": ["wow", "verkle", "rib"],
                                         "raw": [i, 0.0, 0.0, 0.0], "normalized": [1.0, 0.0, 0.0, 0.0]}},
        "content_commit": {"hex": commit},
        "rib": {"domain": "wow", "invariant": invariant[:400], "source": "wow-k8s-foundation"},
    }
    return append_verkle_knot(dossier)


def _rib(invariant: str) -> dict[str, Any]:
    """The RIB INTERPRETS the invariant (the instruction/doctrine layer)."""
    from mag import rib_bus
    return rib_bus.publish_rib(invariant, domain="wow", source="wow-k8s-foundation", target_rank="T2")


def _render(invariant: str, i: int) -> dict[str, Any]:
    """The RENDERING LANGUAGE: world_rib compiles the invariant (RIB) into a world. Guarded."""
    try:
        from mag import world_rib
        field = world_rib.compile(invariant, w=64, h=64)
        return {"ok": True, "scale": i, "rendered": bool(field is not None),
                "provenance": "RIB -> world, re-derivable (map precedes territory)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "scale": i}


def manifest() -> dict[str, Any]:
    """THE CORRECT MANIFESTATION: for each WoW invariant -> verkle knot + RIB interprets + render."""
    rows = []
    knots = 0
    for i, inv in enumerate(WOW_INVARIANTS):
        k = _knot(inv, i)
        r = _rib(inv)
        w = _render(inv, i)
        rows.append({"i": i, "invariant": inv[:60], "verkle_knot": k.get("ok"),
                     "knot_root": (k.get("root") or "")[:16], "rib_published": r.get("ok"),
                     "rendered": w.get("rendered", w.get("ok"))})
        if k.get("ok"):
            knots += 1
    # the verkle root of the whole manifestation (the chain)
    root = ""
    try:
        from mag import verkle_knot
        st = verkle_knot.status() if hasattr(verkle_knot, "status") else {}
        root = (st.get("root") or "")[:16]
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_invariants": len(WOW_INVARIANTS),
            "n_knots": knots, "verkle_root": root, "manifestation": rows,
            "path": "invariant -> verkle knot -> RIB interprets -> world_rib renders (re-derivable)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="wow-manifest")
    ap.add_argument("cmd", nargs="?", default="manifest", choices=["manifest"])
    a = ap.parse_args()
    print(json.dumps(manifest(), ensure_ascii=False, indent=2, default=str))
