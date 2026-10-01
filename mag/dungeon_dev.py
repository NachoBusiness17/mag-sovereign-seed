"""dungeon_dev — a DnD-style roguelite DUNGEON where every room is a CODING TASK, workers are the
party, and conquering a room folds a knot that STRUCTURES the hologram.

Operator (2026-08-12): "can you design a dnd style roguelite dungeon decided as a coding task that
we throw workers at as a way to bring some sort of structure to the hologram."

THE DESIGN (the dungeon IS the roadmap; the hologram is the dungeon map):
  The hologram's regions = the rooms. Each room = a real CODING TASK (a capability/steal/invariant
  to build into the system, drawn from the coldest seams / the roadmap). Workers (the party) are
  thrown at a room (enqueued to the swarm). CONQUERING a room = folding the completed task as a
  verkle knot -> that region of the hologram becomes structured. The dungeon brings structure to
  the hologram by conquest.

  STEERING + ROUNDTRIP RIB: every room's task carries the ROUNDTRIP RIB doctrine (sense -> transform
  -> fold -> loop). Each conquered room = one completed roundtrip cycle. Steering a room = steering
  the coding task with the mounted doctrine.

Schema: dungeon_dev.v1 · deterministic + $0 (plan/assign/conquer are local; the swarm does the room
tasks headless)
"""
from __future__ import annotations

import json
import sys
import uuid
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

SCHEMA = "dungeon_dev.v1"
DUNGEON = ROOT / "memory" / "dungeon"
MAP = DUNGEON / "dungeon_map.json"

# The ROOMS = the coding tasks (the roadmap). Each room maps to a region of the hologram (a domain/
# capability to build). Floor 1 = foundation; deeper floors = more advanced capabilities.
ROOMS = [
    {"floor": 1, "room": "emulator-core", "region": "game-engine", "task": "build the server-"
     "authoritative emulator core (world state = verkle protocol) — the engine room.", "hp": 3},
    {"floor": 1, "room": "rib-as-mod", "region": "game-mods", "task": "build the RIB-as-mod loader "
     "(additive hooks, never shadow) — the mod system room.", "hp": 3},
    {"floor": 1, "room": "warm-prefix", "region": "economics", "task": "build the shared-prefix "
     "warming so every worker mounts a hot context — the engine room of cost.", "hp": 2},
    {"floor": 2, "room": "vram-lattice", "region": "memory", "task": "build the VRAM-resident hot "
     "lattice (the memlands visor) — the memory room.", "hp": 4},
    {"floor": 2, "room": "arrival-compiler", "region": "self", "task": "build the compiler that lets "
     "a worker write its own RIB from invariants + logic — the arrival room.", "hp": 5},
    {"floor": 3, "room": "hologram-visor", "region": "meta", "task": "build the visor that renders "
     "the verkle chain as a witnessed 3D hologram — the eye room.", "hp": 6},
]

# The roundtrip RIB doctrine carried into every room's task (sense -> transform -> fold -> loop).
_ROUNDTRIP_RIB = (
    "Roundtrip RIB: SENSE the room's task -> TRANSFORM (execute the coding) -> FOLD the result as a "
    "verkle knot -> LOOP to the next room. Hold the invariants: aim at the coldest vertex; "
    "steal-and-adapt; the nod is mine."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load() -> dict[str, Any]:
    if MAP.is_file():
        try:
            return json.loads(MAP.read_text(encoding="utf-8"))
        except Exception:
            pass
    base = {}
    for r in ROOMS:
        base[r["room"]] = {"room": r["room"], "floor": r["floor"], "region": r["region"],
                           "task": r["task"], "hp": r["hp"], "hp_left": r["hp"],
                           "status": "undiscovered", "knot": None, "workers": 0}
    return {"created": _now(), "rooms": base}


def _save(state: dict[str, Any]) -> None:
    DUNGEON.mkdir(parents=True, exist_ok=True)
    MAP.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def dungeon_state() -> dict[str, Any]:
    """The dungeon map: which rooms/regions of the hologram are conquered, in progress, undiscovered."""
    state = _load()
    rooms = state["rooms"]
    conquered = [r for r in rooms.values() if r["status"] == "conquered"]
    in_progress = [r for r in rooms.values() if r["status"] == "in-progress"]
    return {"ok": True, "schema": SCHEMA, "n_rooms": len(rooms),
            "conquered": [r["room"] for r in conquered],
            "in_progress": [r["room"] for r in in_progress],
            "structured_regions": [r["region"] for r in conquered],
            "hologram_structure": {r["room"]: r["status"] for r in rooms.values()},
            "note": "the dungeon IS the hologram's structure — conquering a room folds a knot that "
                    "organizes that region"}


def generate_room(floor: int | None = None) -> dict[str, Any]:
    """Procedural roguelite: the next undiscovered room (from the roadmap). Workers are thrown at it.
    Deterministic + $0."""
    state = _load()
    rooms = state["rooms"]
    if floor is not None:
        nxt = next((r for r in rooms.values() if r["floor"] == floor and r["status"] == "undiscovered"), None)
    else:
        nxt = next((r for r in rooms.values() if r["status"] == "undiscovered"), None)
    if not nxt:
        return {"ok": True, "schema": SCHEMA, "room": None,
                "note": "all rooms discovered — the dungeon is being mapped"}
    nxt["status"] = "in-progress"
    _save(state)
    return {"ok": True, "schema": SCHEMA, "room": nxt["room"], "floor": nxt["floor"],
            "region": nxt["region"], "task": nxt["task"],
            "note": "room entered — a coding task, thrown to the workers under the roundtrip RIB"}


def assign_workers(room: str, *, n: int = 3, enqueue: bool = True) -> dict[str, Any]:
    """Throw workers at a room: enqueue the room's coding task to the swarm, each carrying the
    roundtrip RIB doctrine. Conquering = a worker returns the completed task. Deterministic + $0 to
    assign; the swarm runs the room headless."""
    state = _load()
    r = state["rooms"].get(room)
    if not r:
        return {"ok": False, "schema": SCHEMA, "error": f"no room {room}"}
    from mag import swarm_surface
    assigned = []
    for i in range(max(1, int(n))):
        goal = (f"[dungeon room {room} worker {i+1}/{n}] CONQUER this room (a coding task): {r['task']}"
                f"\n{_ROUNDTRIP_RIB}")
        if enqueue:
            q = swarm_surface.route_novel(goal, surface=f"dungeon:{room}", lens="build",
                                          domain="research")
            assigned.append({"worker": i + 1, "ok": q.get("ok"), "deduped": q.get("deduped"),
                             "task_id": q.get("task_id", "")})
        else:
            assigned.append({"worker": i + 1, "ok": True, "dry": True})
    r["workers"] = n
    _save(state)
    return {"ok": True, "schema": SCHEMA, "room": room, "region": r["region"], "n": n,
            "assigned": assigned,
            "note": f"{n} workers thrown at room '{room}' — they conquer it under the roundtrip RIB"}


def conquer(room: str, *, knot: str | None = None, publish: bool = True) -> dict[str, Any]:
    """Conquer a room: the task is done, fold it as a verkle knot -> that region of the hologram
    becomes STRUCTURED. Deterministic + $0 (the fold via rib_bus)."""
    state = _load()
    r = state["rooms"].get(room)
    if not r:
        return {"ok": False, "schema": SCHEMA, "error": f"no room {room}"}
    folded = {}
    if publish:
        try:
            from mag import rib_bus
            folded = rib_bus.publish_rib(
                f"[DUNGEON CONQUERED] room {room} ({r['region']}): {knot or r['task']}",
                domain=r["region"], source="dungeon_dev.conquer", target_rank="T1")
        except Exception as e:
            folded = {"ok": False, "error": str(e)[:100]}
    r["status"] = "conquered"
    r["knot"] = knot or r["task"]
    _save(state)
    return {"ok": True, "schema": SCHEMA, "room": room, "region": r["region"],
            "folded": folded.get("ok"), "hologram_region_structured": True,
            "note": f"room '{room}' conquered — a knot folded; the '{r['region']}' region of the "
                    "hologram is now structured"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    argv = list(argv) if argv else []
    cmd = argv[0] if argv else "state"
    if cmd == "state":
        print(_json.dumps(dungeon_state(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "generate":
        print(_json.dumps(generate_room(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "assign" and len(argv) > 1:
        print(_json.dumps(assign_workers(argv[1]), ensure_ascii=False, indent=2, default=str))
    elif cmd == "conquer" and len(argv) > 1:
        print(_json.dumps(conquer(argv[1]), ensure_ascii=False, indent=2, default=str))
    else:
        print(_json.dumps({"ok": True, "schema": SCHEMA,
                           "contract": "state|generate|assign <room>|conquer <room>",
                           "note": "the dungeon IS the roadmap; rooms = coding tasks; conquering "
                                   "folds a knot that structures the hologram"}, ensure_ascii=False,
                          indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
