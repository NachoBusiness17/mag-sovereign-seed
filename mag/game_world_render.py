"""game_world_render — STONE 3 (the intent-gated world render): make the world WORTH WALKING INTO.
Self-stolen from what we hold (nothing invented): game_entry (stone 2 — the intent-gated reveal: a
building appears where you steer, content-addressed + persistent) + world_rib (the deterministic 2D
field = the 'pixels between swarms', the base render every tier draws on) + game_world (the server-
authoritative verkle world, every reveal committed as a knot).

Operator (2026-08-13): "go from our base render state like our pixels between swarms... make the
world worth walking into." + "as df hack to dwarf fortress you sit overtop" + "what do you want to
do?" -> I want to BUILD THE GAME. Stone 3 = the intent-gated world render: the player walks forward,
and a building appears where they STEER — rendered into the base field (the pixels between swarms).

THE INTENT-GATED RENDER (deterministic + $0):
  reveal(player, direction) -> the player steers; a building appears at the content-addressed
       coordinate (region:direction:player -> x,y -> archetype). Same steer -> same building
       (persistent fidelity, committed to the world as a verkle knot). Only the steered cell reveals;
       the rest stays field (perceptual culling).
  render(region)            -> the base render: compile the world field (world_rib) + place every
       revealed building's glyph at its coordinate -> the ASCII grid (the pixels between swarms) the
       game renders on. The world is WORTH WALKING INTO because the render is real + grounded.
  walk(player, direction)   -> the player's act: reveal where they steered, then render the world.
  status()                  -> the render surface's deep view (buildings revealed, grid dims).

Schema: game_world_render.v1 · deterministic + $0 · reuse: game_entry, world_rib, game_world
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

SCHEMA = "game_world_render.v1"
GRID_W, GRID_H = 40, 16          # the base render dims (the pixels between swarms)
REGION = "mycelial-republic"

# ASCII ramp for the field (dark -> bright) — the ground beneath the buildings.
RAMP = " .:-=+*#%@"

# — THE OPTICS (stolen whole from measure_plan + mathemetica, 2026-09-14) —
# "grokking is what it looks like when knowledge becomes fractal: memorize = leaf-only
#  tree; grok = the tree grows internal nodes."  +  "attention is light; softmax is a
#  lens; temperature is the refractive index."  The maze now obeys both:
#   * reveal casts a lantern RAY from the player's anchor toward the steered cell;
#     dense cells (bright field) are low temperature — the ray BENDS toward brightness,
#     one refraction per steer. Cold/void field: straight rays.
#   * enough leaves in a region and the tree GROWS an internal node (the grok knot):
#     a hub that links what used to be unconnected leaves. Self-similar at every scale.
REFRACT_THRESHOLD = 0.62         # field brightness at/above this = dense (cold) medium
GROK_THRESHOLD = 8               # revealed leaves before an internal node grows


def _rot45(dx: int, dy: int, turn: int) -> tuple[int, int]:
    """Rotate a king-move direction ±45° (turn +1 / -1)."""
    if dx != 0 and dy != 0:      # diagonal -> axis
        return (dx, 0) if turn > 0 else (0, dy)
    return (dx + turn, dy) if dx != 0 else (dx, dy + turn)  # axis -> diagonal


def _bend_ray(region: str, player: str, tx: int, ty: int) -> dict[str, Any]:
    """Cast the lantern ray: march from the player's anchor toward the steered cell through the
    field. Cross a dense cell (brightness >= REFRACT_THRESHOLD) and the ray bends once toward the
    brighter 45° continuation — temperature is the refractive index; the lens is deterministic."""
    field = _field(region)
    ax, ay = _anchor(region, player)
    dx, dy = ((tx > ax) - (tx < ax)), ((ty > ay) - (ty < ay))
    if (dx, dy) == (0, 0):
        return {"x": ax, "y": ay, "bent": False}
    steps = max(abs(tx - ax), abs(ty - ay))
    x, y = ax, ay
    for _ in range(steps):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
            break
        dense = field[ny][nx] >= REFRACT_THRESHOLD
        if dense and (nx, ny) not in ((tx, ty), (ax, ay)):
            c1 = _rot45(dx, dy, +1)
            c2 = _rot45(dx, dy, -1)
            p1 = (min(GRID_W - 1, max(0, x + c1[0])), min(GRID_H - 1, max(0, y + c1[1])))
            p2 = (min(GRID_W - 1, max(0, x + c2[0])), min(GRID_H - 1, max(0, y + c2[1])))
            v1, v2 = field[p1[1]][p1[0]], field[p2[1]][p2[0]]
            pick = c1 if v1 >= v2 else c2            # bend toward brightness; tie -> +45
            dx, dy = pick
            x, y = x + dx, y + dy
            return {"x": x, "y": y, "bent": True,
                    "refracted_at": [nx, ny],
                    "aimed": [tx, ty],
                    "law": "temperature is the refractive index; the ray bent toward brightness"}
        x, y = nx, ny
    return {"x": tx, "y": ty, "bent": False}


def _anchor(region: str, player: str) -> tuple[int, int]:
    """The lantern's source: content-addressed, same grammar as every leaf."""
    return _cell(region, "origin", player)


def _leaf_count(region: str) -> int:
    return len(_collect(region))


def _maybe_grok(region: str, player: str) -> dict[str, Any] | None:
    """THE GROK KNOT: enough leaves in a region and the tree grows an internal node — a hub
    linking leaves that used to be unconnected. Memorize = leaf-only; grok = nodes grow."""
    if _leaf_count(region) < GROK_THRESHOLD:
        return None
    gx, gy = _cell(region, "internal-node", region)  # the tree belongs to the region, not the walker
    key = f"game.render.{region}.{gx}.{gy}"
    state = _world()._load().get("world", {})
    if key in state:
        return None
    node = {"name": "Internal Node — the tree grew", "glyph": "▲",
            "line": "memorize = leaf-only tree; grok = internal nodes grow (measure_plan, 2026-09-14)"}
    _world().set_state(key, node, source="game_world_render.grok")
    return {"x": gx, "y": gy, "glyph": "▲", "name": node["name"]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _world() -> Any:
    from mag import game_world
    return game_world


def _entry() -> Any:
    from mag import game_entry
    return game_entry


def _seed(*parts: str) -> int:
    return int(hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:8], 16)


def _cell(region: str, direction: str, player: str) -> tuple[int, int]:
    """Content-address the steered cell: same (region, direction, player) -> same x,y (persistent)."""
    s = _seed(region, direction, player)
    return (s % GRID_W), ((s // GRID_W) % GRID_H)


def _building(direction: str, player: str) -> dict[str, Any]:
    """Pick the building archetype deterministically from game_entry's buildings (the Republic's
    real content, not cosmetic)."""
    keys = _entry().BUILDING_KEYS
    b = keys[_seed(direction, player) % len(keys)]
    return _entry().BUILDINGS[b]


def reveal(player: str = "you", direction: str = "forward", region: str = REGION) -> dict[str, Any]:
    """INTENT-GATED REVEAL, now with optics: the player steers, a lantern ray casts from their
    anchor toward the steered cell, and the building appears where the ray LANDS — straight through
    void, bent toward brightness through dense medium (temperature is the refractive index).
    Content-addressed (same steer -> same landing), committed as a verkle knot. Enough leaves and
    the tree grows an internal node (the grok knot)."""
    aimed = _cell(region, direction, player)
    ray = _bend_ray(region, player, aimed[0], aimed[1])
    x, y = ray["x"], ray["y"]
    building = _building(direction, player)
    key = f"game.render.{region}.{x}.{y}"
    committed = _world().set_state(key, building, source="game_world_render")
    grok = _maybe_grok(region, player)
    out = {"ok": True, "schema": SCHEMA, "player": player, "direction": direction,
           "x": x, "y": y, "building": building["name"], "glyph": building["glyph"],
           "line": building["line"], "leaf": committed.get("leaf", ""),
           "aimed": list(aimed), "bent": bool(ray.get("bent"))}
    if ray.get("bent"):
        out["refracted_at"] = ray["refracted_at"]
        out["law"] = ray["law"]
    if grok:
        out["grok"] = grok
    out["note"] = ("the ray bent through dense medium — a building appeared where the light landed"
                   if ray.get("bent") else
                   "a building appeared where you steered — intent-gated, content-addressed, verkle-committed")
    return out


def _field(region: str) -> list[list[float]]:
    """The base field (the pixels between swarms) for the region — from world_rib if available,
    else a deterministic pure-python fallback. The ground the buildings sit on."""
    try:
        from mag import world_rib
        rib = f"{region}: the world the swarm shades"
        c = world_rib.compile(rib, w=GRID_W, h=GRID_H)
        f = c["field"]
        # normalize to 0..1
        lo, hi = float(f.min()), float(f.max())
        span = (hi - lo) or 1.0
        return [[float((f[y, x] - lo) / span) for x in range(GRID_W)] for y in range(GRID_H)]
    except Exception:
        # deterministic fallback: a soft wave field, seeded by the region
        seed = _seed(region)
        rows = []
        for y in range(GRID_H):
            row = []
            for x in range(GRID_W):
                v = 0.5 + 0.5 * __import__("math").sin((x + seed % 7) / 4.0) * \
                    0.5 + 0.5 * __import__("math").sin((y + seed % 11) / 3.0) * 0.5
                row.append(0.5 * (v / 2.0 + 0.5))
            rows.append(row)
        return rows


def _collect(region: str) -> dict[str, tuple[int, int, dict[str, Any]]]:
    """Collect every revealed building from the world (the committed reveals) for rendering."""
    state = _world()._load()
    world = state.get("world", {})
    out: dict[str, tuple[int, int, dict[str, Any]]] = {}
    for key, ent in world.items():
        if key.startswith(f"game.render.{region}."):
            parts = key.split(".")
            try:
                x, y = int(parts[-2]), int(parts[-1])
                val = ent.get("value") or {}
                if isinstance(val, dict) and "glyph" in val:
                    out[key] = (x, y, val)
            except Exception:
                continue
    return out


def render(region: str = REGION) -> dict[str, Any]:
    """THE BASE RENDER: compile the world field (the pixels between swarms) + place every revealed
    building's glyph at its coordinate -> the ASCII grid. The world is WORTH WALKING INTO because
    the render is real: buildings you steered toward are visibly there, grounded in the field."""
    field = _field(region)
    revealed = _collect(region)
    grid = []
    placed = {}
    for y in range(GRID_H):
        row = []
        for x in range(GRID_W):
            row.append(RAMP[min(9, int(field[y][x] * 10))])
        grid.append(row)
    for key, (x, y, b) in revealed.items():
        if 0 <= x < GRID_W and 0 <= y < GRID_H:
            grid[y][x] = b["glyph"]
            placed[f"{x},{y}"] = b["name"]
    ascii_map = "\n".join("".join(row) for row in grid)
    return {"ok": True, "schema": SCHEMA, "region": region, "grid": [GRID_W, GRID_H],
            "buildings_revealed": len(revealed), "placed": placed, "ascii": ascii_map,
            "note": "the base render — the pixels between swarms, with the buildings you steered toward placed in it"}


def walk(player: str = "you", direction: str = "forward", region: str = REGION) -> dict[str, Any]:
    """THE PLAYER'S ACT: reveal where they steered, then render the world. The vertical trigger made
    real — walk forward, a building appears where you intend, and the base render shows it there."""
    r = reveal(player, direction, region)
    rd = render(region)
    return {"ok": True, "schema": SCHEMA, "reveal": r, "render": rd,
            "note": "walked forward — the world rendered with the building where you steered"}


def status(region: str = REGION) -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "region": region,
            "contract": "reveal(player,direction)->a lantern ray casts from your anchor toward the "
                        "steer; dense field bends it (temperature is the refractive index) and the "
                        "building appears where the light lands; enough leaves and an internal node "
                        "grows (the grok knot); render(region)->the base ASCII field with everything "
                        "placed; walk(player,direction)->reveal then render.",
            "optics": {"refract_threshold": REFRACT_THRESHOLD, "grok_threshold": GROK_THRESHOLD,
                       "law": "attention is light; softmax is a lens (mathemetica) — "
                              "memorize = leaf-only tree, grok = nodes grow (measure_plan)"},
            "cost": "deterministic $0 (world_rib + content-address; no external LLM)",
            "surface": "the intent-gated world render with optics — stone 3, the world worth walking into",
            "reuse": "game_entry (stone 2 reveal + buildings), world_rib (the field), game_world (the authority)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="game-world-render")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "walk", "reveal", "render"])
    ap.add_argument("--player", default="you")
    ap.add_argument("--direction", default="forward")
    a = ap.parse_args(argv)
    if a.cmd == "walk":
        print(json.dumps(walk(a.player, a.direction), indent=2, default=str))
    elif a.cmd == "reveal":
        print(json.dumps(reveal(a.player, a.direction), indent=2, default=str))
    elif a.cmd == "render":
        print(json.dumps(render(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
