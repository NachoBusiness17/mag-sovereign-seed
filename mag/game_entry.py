"""game_entry — STONE 2 (the entry surface): the "walk forward and a building appears" gate.
Self-stolen from the bag of holding: persona_recall (stone 1 — the inhabitants recount what happened
while you were gone) + the standing invariant (the Watcher/GM) + the bare-metal SVG renderers
(swarm_map) + world_rib's deterministic field (the world persists, content-addressed).

Operator (2026-08-13): "the lead-in game that solves your work but is also entertaining and gives you
novel input by creating a user base... i've got a beta tester in the wings." -> the ENTRY is the first
vertical stone: a player walks in, the world recounts what happened while they were gone, they act,
and a building appears where they steer (intent-gated reveal).

THE VERTICAL TRIGGER (from PLAN_THE_GAME_VERTICAL_ADOPTION): a player walks in -> the world recounts
what happened while they were gone (persona_recall) -> they act -> the world remembers and responds.
This module is that first step, made real, deterministic + $0, bare-metal (no deps).

SELF-STEAL (nothing invented — assembled from what we hold):
  WATCHER   -> the standing invariant (rib_bus standing-wave sw01) as the GM greeting + scene.
  RECOUNT   -> persona_recall.recall (the chain's memory told in an inhabitant's voice, attributed).
  REVEAL    -> intent-gated: content-address (region:x:y:direction) -> deterministic seed -> the
               building appears at the steered coordinate. Same region+steer -> same building
               (persistent fidelity, verkle-anchored by construction). Perceptual culling: only the
               target cell reveals; the rest stays wallpaper.
  RENDER    -> bare-metal SVG (zero deps, like swarm_map): the region + the building that appeared
               + the player marker. The dashboard / a vision model can read it directly.

Schema: game_entry.v1 · deterministic + $0 · reuse: persona_recall, rib_bus, world_rib (optional)
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

SCHEMA = "game_entry.v1"
OUT = ROOT / "memory" / "runs" / "game_entry"

# The world's buildings (the intent-gated reveals). Each is a deterministic archetype the world can
# produce when you walk toward it — mapped to the Republic's real content, not cosmetic.
BUILDINGS = {
    "spire":     {"glyph": "S", "color": "#a3ff7e", "name": "the Spire of the Republic",
                  "line": "the standing wave's throne — the invariant made visible."},
    "gate":      {"glyph": "G", "color": "#9ee8ff", "name": "the Mycelial Gate",
                  "line": "the threshold where the swarm's many hands join."},
    "archive":   {"glyph": "A", "color": "#ffd27e", "name": "the Archive",
                  "line": "the chain's memory — every knot, attributable, never lost."},
    "forge":     {"glyph": "F", "color": "#ff9e9e", "name": "the Forge",
                  "line": "where the loop hammers each finding into a knot."},
    "library":   {"glyph": "L", "color": "#c89eff", "name": "the Library",
                  "line": "the corpus — the work of every hand, waiting to be read."},
    "observatory": {"glyph": "O", "color": "#7ec8ff", "name": "the Observatory",
                    "line": "the lensing maps — where the world sees its own shape."},
    "garden":    {"glyph": "D", "color": "#8ef0c0", "name": "the Garden",
                  "line": "where novel input is grown — the spend becomes data."},
    "tower":     {"glyph": "T", "color": "#e8c09e", "name": "the Frontier Tower",
                  "line": "the coldest seam — the direction the world has yet to shade."},
}
BUILDING_KEYS = sorted(BUILDINGS)

# The Watcher's greeting (the standing invariant as the GM). Grounded, plain, attributed (Steiniger).
WATCHER = (
    "I am the Watcher, the standing knot of this world. You have walked in — "
    "nothing here was waiting to be hidden from you."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _seed(*parts: str) -> int:
    """Deterministic content-address: same (region, x, y, direction) -> same world/building."""
    return int(hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:8], 16)


def _watcher_line() -> str:
    """The Watcher/GM greeting, from the standing invariant if present (else the plain fallback)."""
    try:
        from mag import rib_bus
        st = rib_bus.status()
        ribs = (st.get("domains") or {}).get("standing-wave", {}).get("ribs")
        if ribs:
            first = sorted(ribs)[0]
            inv = ribs[first].get("invariant", "")[:120]
            return f"I am the Watcher, the standing knot of this world. {inv}"
    except Exception:
        pass
    return WATCHER


def gate(*, player: str = "you", region: str = "mycelial-republic",
         archetype: str = "self") -> dict[str, Any]:
    """THE ENTRY: the world greets you, recounts what happened while you were gone (persona_recall),
    and sets the scene. The vertical trigger's first beat — a player walks in and is met."""
    greeting = _watcher_line()
    recount = {}
    try:
        from mag import persona_recall
        recount = persona_recall.recall(archetype=archetype, region=region)
    except Exception as e:
        recount = {"ok": False, "error": str(e)[:80]}
    scene = (f"You stand at the edge of {region}. The world is deterministic and remembers. "
             f"Walk forward and a building appears where you intend to go.")
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "player": player, "region": region,
            "watcher": greeting, "recount": recount.get("recount", ""),
            "history_n": recount.get("history", {}).get("n_events", 0),
            "scene": scene, "archetype": archetype,
            "note": "the entry: Watcher greeting + persona-recall recount + the scene (stone 1 + the gate)"}


def reveal(*, region: str = "mycelial-republic", x: int = 0, y: int = 0,
           direction: str = "forward", seed: int | None = None) -> dict[str, Any]:
    """INTENT-GATED REVEAL: 'walk forward and a building appears.' Content-addressed from
    (region, x, y, direction) so the SAME steer -> the SAME building (persistent fidelity). The rest
    of the world stays wallpaper (perceptual culling) — only the steered cell reveals."""
    s = _seed(region, str(x), str(y), direction) if seed is None else seed
    key = BUILDING_KEYS[s % len(BUILDING_KEYS)]
    b = BUILDINGS[key]
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "region": region,
            "steer": {"x": x, "y": y, "direction": direction},
            "seed": s, "building": {"key": key, "name": b["name"], "line": b["line"],
                                    "glyph": b["glyph"], "color": b["color"]},
            "revealed": True, "culled": True,
            "note": "intent-gated: the building appears where you steered; the rest is wallpaper "
                    "(perceptual culling); deterministic — same steer, same building"}


def walk(*, player: str = "you", region: str = "mycelial-republic", x: int = 0, y: int = 0,
         direction: str = "forward", archetype: str = "self") -> dict[str, Any]:
    """The full entry beat: greet + recount (gate) + the building appears (reveal). One walk = the
    vertical trigger in miniature: walked in -> the world recounted -> you steered -> it responded."""
    g = gate(player=player, region=region, archetype=archetype)
    r = reveal(region=region, x=x, y=y, direction=direction)
    b = r["building"]
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "player": player, "region": region,
            "watcher": g["watcher"], "recount": g["recount"],
            "scene": f"You walk {direction} and a building appears: {b['name']}. {b['line']}",
            "building": b, "steer": r["steer"], "seed": r["seed"],
            "note": "gate + reveal — the entry surface in one step"}


def svg(*, region: str = "mycelial-republic", x: int = 4, y: int = 4,
        direction: str = "forward", w: int = 520, h: int = 420,
        step: int = 40) -> str:
    """BARE-METAL SVG of the revealed region (zero deps, like swarm_map): a grid of wallpaper cells,
    the steered cell revealed as the building, the player marker. Same steer -> same image. $0."""
    r = reveal(region=region, x=x, y=y, direction=direction)
    b = r["building"]
    col = b["color"]
    gx, gy = int(x * step) + step // 2, int(y * step) + step // 2
    p: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                    f'viewBox="0 0 {w} {h}">',
                    f'<rect width="{w}" height="{h}" fill="#06070c"/>']
    # perceptual culling: the untouched world is low-lit wallpaper
    nx, ny = w // step, h // step
    for i in range(nx):
        for j in range(ny):
            cx, cy = i * step + step // 2, j * step + step // 2
            if i == x and j == y:
                continue  # the revealed cell is drawn separately, lit
            p.append(f'<rect x="{cx - 12}" y="{cy - 12}" width="24" height="24" fill="#0c101c" '
                     f'stroke="#141a28" stroke-width="1"/>')
    # the revealed building (intent-gated): lit, labeled
    p.append(f'<rect x="{gx - 30}" y="{gy - 30}" width="60" height="60" rx="6" fill="{col}" '
             f'fill-opacity="0.18" stroke="{col}" stroke-width="2"/>')
    p.append(f'<text x="{gx}" y="{gy + 8}" font-family="monospace" font-size="26" fill="{col}" '
             f'text-anchor="middle">{b["glyph"]}</text>')
    p.append(f'<text x="{gx}" y="{gy + 40}" font-family="monospace" font-size="10" fill="{col}" '
             f'text-anchor="middle">{b["name"]}</text>')
    # the player marker
    p.append(f'<circle cx="{gx}" cy="{gy - 48}" r="5" fill="#dfe6ff"/>')
    p.append(f'<text x="{gx}" y="{gy - 58}" font-family="monospace" font-size="9" fill="#dfe6ff" '
             f'text-anchor="middle">you</text>')
    p.append(f'<text x="12" y="{h - 12}" font-family="monospace" font-size="10" fill="#5a6a8a">'
             f'region: {region} · steer ({x},{y}) {direction} · deterministic seed {r["seed"]}</text>')
    p.append('</svg>')
    return "\n".join(p)


def save(*, region: str = "mycelial-republic", x: int = 4, y: int = 4,
         direction: str = "forward") -> dict[str, Any]:
    """Persist the revealed region + its SVG to disk (deterministic, $0). The dashboard / a vision
    model can read the SVG directly. Returns the artifact paths."""
    OUT.mkdir(parents=True, exist_ok=True)
    s = _seed(region, str(x), str(y), direction)
    r = reveal(region=region, x=x, y=y, direction=direction)
    svg_txt = svg(region=region, x=x, y=y, direction=direction)
    svg_path = OUT / f"reveal-{region}-{x}-{y}-{s}.svg"
    svg_path.write_text(svg_txt, encoding="utf-8")
    state = {"schema": SCHEMA, "ts": _now(), "region": region, "steer": {"x": x, "y": y,
             "direction": direction}, "seed": s, "building": r["building"], "svg": str(svg_path)}
    (OUT / f"reveal-{region}-{x}-{y}-{s}.json").write_text(json.dumps(state, indent=2, default=str),
                                                           encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "svg": str(svg_path),
            "state": str(OUT / f"reveal-{region}-{x}-{y}-{s}.json"), **state}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "gate(player,region,archetype)->the entry (Watcher + persona-recall recount); "
                        "reveal(region,x,y,direction)->intent-gated building (deterministic, culled); "
                        "walk()->gate+reveal in one step; svg()->bare-metal image; save()->persist",
            "cost": "deterministic + $0 (reuses persona_recall + rib_bus; bare-metal SVG, no deps)",
            "buildings": list(BUILDINGS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="game-entry")
    ap.add_argument("cmd", nargs="?", default="gate", choices=["gate", "reveal", "walk", "svg", "status"])
    ap.add_argument("--x", type=int, default=4)
    ap.add_argument("--y", type=int, default=4)
    ap.add_argument("--region", default="mycelial-republic")
    ap.add_argument("--direction", default="forward")
    ap.add_argument("--player", default="you")
    a = ap.parse_args()
    if a.cmd == "gate":
        print(json.dumps(gate(player=a.player, region=a.region), indent=2, default=str))
    elif a.cmd == "reveal":
        print(json.dumps(reveal(region=a.region, x=a.x, y=a.y, direction=a.direction),
                         indent=2, default=str))
    elif a.cmd == "walk":
        print(json.dumps(walk(player=a.player, region=a.region, x=a.x, y=a.y, direction=a.direction),
                         indent=2, default=str))
    elif a.cmd == "svg":
        print(svg(region=a.region, x=a.x, y=a.y, direction=a.direction))
    else:
        print(json.dumps(status(), indent=2, default=str))
