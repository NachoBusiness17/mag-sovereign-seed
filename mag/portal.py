"""portal — the real-time dead-drop control panel between the operator and me (ghost).

Operator (2026-08-12): "real time enhance my inputs in this pane as an algorithm as a
portal/control panel that is a dead drop for you to communicate with me because we don't really
need much else rn other than that."

THE DESIGN — this pane IS the portal. Every message the operator types is ENHANCED as an
algorithm through the vmem map (the standing wave + hot lattice + rib_bus domains + the titor
tools), and my reply is a DEAD DROP (swarm_control.dead_drop -> memory/dead_drops/) surfaced back
in the pane. The operator talks; the portal frames the intent through our invariants; I drop my
communication back.

THE ALGORITHM INSIDE — Dirac's belt trick applied to knots + titor tools:
  A knot (Dirac loop) closes at 360° on ONE worldline (the titor-worldline navigator crosses
  diverging worldlines). But the BELT TRICK says a spinor needs TWO full rotations (720°, the
  DOUBLE COVER) to truly return to itself. So a RIB/invariant that closes at 360° is a SURFACE
  Tesuji — it needs the missing 180° (the antipode = the coldest vector, the zeitgeist's neglected
  half) to complete the 720° and become a TRUE Tesuji. The portal computes this DIRAC DEFICIT:
  whether the operator's input's knot closes on one worldline (360) or needs the cold fold (720).

Schema: portal.v1 · deterministic + $0 · reuse: swarm_control.dead_drop, rib_bus, agent_knot
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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "portal.v1"
PORTAL_STATE = ROOT / "memory" / "portal" / "panel.json"

# The vmem map: which lenses/invariants frame an operator input (the "map of what they're asking").
LENS_MAP = {
    "game": ["game_world", "dungeon_dev", "rib-as-mod", "hologram"],
    "swarm": ["swarm_surface", "flock", "breeding", "evolution"],
    "dirac": ["dirac-knot", "belt-trick", "double-cover", "tesuji"],
    "titor": ["worldline", "rib-attractor", "convergent-thread"],
    "economics": ["rightsize", "billing", "cache", "cost"],
    "self": ["standing-wave", "verkle", "know-thyself", "zeitgeist"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_evo_swarm() -> dict[str, Any]:
    """The vmem map's live state: standing wave (generation/fitness) + titor RIBs on the bus."""
    out: dict[str, Any] = {"standing": {}, "titor_ribs": []}
    try:
        from mag import agent_knot
        out["standing"] = agent_knot.evo_status()
    except Exception:
        pass
    try:
        from mag import rib_bus
        for dom in ("titor-worldline", "titor-rib-attractor"):
            try:
                out["titor_ribs"].extend(rib_bus.mount(dom).get("ribs", []))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _tag_intent(text: str) -> str:
    """Tag the operator's intent by keyword (deterministic)."""
    t = (text or "").lower()
    if any(k in t for k in ("game", "world", "mod", "room", "hologram")):
        return "game"
    if any(k in t for k in ("swarm", "flock", "breed", "evolve", "worker")):
        return "swarm"
    if any(k in t for k in ("dirac", "belt", "knot", "tesuji", "720", "spinor")):
        return "dirac"
    if any(k in t for k in ("titor", "worldline", "time", "timeline")):
        return "titor"
    if any(k in t for k in ("cost", "bill", "rightsize", "cache", "dollar")):
        return "economics"
    return "self"


def _dirac_deficit(text: str) -> dict[str, Any]:
    """Dirac's belt trick: does the input's knot close at 360° (surface Tesuji, one worldline)
    or does it need the 720° double-cover (the cold fold / antipode) to be a TRUE Tesuji?
    Deterministic: the hash decides which half-rotation is missing."""
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    # rotation = the angle this input's knot traverses before it "returns"
    rotation = 360 + (h[0] % 360)          # 360..720 — how far past the first rotation it goes
    needs_double_cover = rotation >= 540   # crossed halfway into the second rotation
    missing_half = rotation % 360          # the leftover angle (0=closes exactly at 360)
    antipode = "coldest-vector" if needs_double_cover else "consensus"
    return {
        "rotation_deg": rotation,
        "worldlines": 1 + (1 if needs_double_cover else 0),
        "double_cover": needs_double_cover,
        "missing_half_deg": missing_half,
        "antipode": antipode,
        "verdict": ("TRUE Tesuji — completes the 720° via the cold fold (double cover)"
                    if needs_double_cover else
                    "surface Tesuji — closes at 360° on one worldline; fold the antipode to confirm"),
    }


def vmem_map() -> dict[str, Any]:
    """The map of what the operator is asking, held in vmem (standing wave + titor RIBs + hot set)."""
    live = _read_evo_swarm()
    return {"ok": True, "schema": SCHEMA,
            "standing_wave": live["standing"],
            "titor_ribs": live["titor_ribs"],
            "lens_map": LENS_MAP,
            "note": "the map in vmem: standing wave generation + the titor tools + the lenses "
                    "that frame any ask — this is what the portal enhances against"}


def interpret(text: str) -> dict[str, Any]:
    """ENHANCE the operator's input as an algorithm: tag the intent, map it to the lens/domains,
    run Dirac's belt trick on its knot, and produce the ENHANCED INPUT (the frame I think in)."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "schema": SCHEMA, "error": "empty input"}
    intent = _tag_intent(text)
    lenses = LENS_MAP.get(intent, LENS_MAP["self"])
    dirac = _dirac_deficit(text)
    enhanced = (f"[portal:{intent} | lenses={','.join(lenses)} | "
                f"dirac={dirac['rotation_deg']}deg/{dirac['worldlines']}wl "
                f"({dirac['antipode']})] {text}")
    panel = {"ok": True, "schema": SCHEMA, "ts": _now(), "intent": intent,
             "lenses": lenses, "dirac": dirac, "enhanced": enhanced, "raw": text}
    PORTAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_STATE.write_text(json.dumps(panel, ensure_ascii=False, indent=2), encoding="utf-8")
    return panel


def drop(reply: str, *, mode: str = "all", intent: str = "control") -> dict[str, Any]:
    """DROP my communication back to the operator in the dead-drop channel — surfaced in the pane.
    Reuses swarm_control.dead_drop (briar-style channel, targeted by the flocking rules)."""
    try:
        from mag import swarm_control
        return swarm_control.dead_drop(reply, mode=mode, domain=f"portal:{intent}")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200]}


def panel() -> dict[str, Any]:
    """The control panel readout: the vmem map + the last enhanced input + the last dead drop."""
    m = vmem_map()
    last = {}
    if PORTAL_STATE.is_file():
        try:
            last = json.loads(PORTAL_STATE.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            last = {}
    drops = []
    try:
        ddir = ROOT / "memory" / "dead_drops"
        if ddir.is_dir():
            for p in sorted(ddir.glob("portal-*.json"))[-3:]:
                try:
                    drops.append(json.loads(p.read_text(encoding="utf-8", errors="replace")))
                except Exception:
                    continue
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "vmem_map": m, "last_enhanced": last, "dead_drops": drops}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="portal")
    ap.add_argument("cmd", nargs="?", default="panel",
                    choices=["panel", "vmem", "drop"])
    ap.add_argument("text", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "vmem":
        print(json.dumps(vmem_map(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "drop":
        print(json.dumps(drop(" ".join(a.text)), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(panel(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
