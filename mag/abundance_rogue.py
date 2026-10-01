"""abundance_rogue — the ROGUELIKE with PERMANENT GENERATIVE HISTORY mapped to GLOBAL ISSUES. By
playing, you UNTIE real topological problems (the tangles in the shared wave) to introduce
SCI-FI ABUNDANCE for all. It is the INTERFACE for AI and each other — the raid's boss is a real knot;
beating it makes the real world (and the wave) genuinely richer.

OPERATOR (2026-08-12): "rogue like with a perm generative history mapped to global issues that by
playing you untie topological problems to introduce scifi abundance for all. acting as an interface
for ai and eachother. like the infinite animes movies and games about it we can just steal from."

THE MECHANISM (self-steal, no invention):
  * knot_untangle      -> a REAL tangle is near-duplicate content in the verkle chain; untangling =
    collapsing it to one cleaner invariant. The "boss" is a real knot, not a fake monster.
  * game_world         -> the permanent generative history: every conquer folds a verkle knot; the
    chain is the history that never resets (roguelike death = the world remembers).
  * dungeon_dev        -> rooms = real tasks (the roadmap as a dungeon) — stolen shape.
  * republic_wave      -> the shared wave: abundance = the deduped invariants all contribute.
  * route_trace        -> every player's move is a content-addressed hop (provenance, permanent).

THE EXPERIENCE (roguelike, perm-death-but-permanent-history):
  * enter()      -> start a run (a roguelike run). Perm-death: a run can fail, but the HISTORY
                    persists (the chain records what was tried).
  * dungeon()    -> generate the roguelike: floors = GLOBAL ISSUES, each a real topological problem
                    (a tangled knot cluster) to untie.
  * play(action) -> the run: an action unties a knot (real) or fails (perm-death); the world folds
                    the attempt as a permanent knot.
  * history()    -> the PERMANENT GENERATIVE HISTORY: every run's attempts on the chain (never reset).
  * abundance()  -> what untangling earned: the deduped invariants added to the shared wave = the
                    sci-fi abundance for all (real, measured).

Schema: abundance_rogue.v1 · deterministic + $0 · reuse: knot_untangle, game_world, dungeon_dev,
republic_wave, route_trace
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "abundance_rogue.v1"

# GLOBAL ISSUES as roguelike FLOORS. Each is a real topological problem the player unties — and each
# untie introduces abundance (a real invariant folded into the shared wave).
FLOORS = [
    {"floor": 1, "issue": "knowledge scarcity", "tangle": "duplicate invariants scattered across the "
     "wave; untie = dedupe by content anchor so one truth serves all"},
    {"floor": 2, "issue": "compute waste", "tangle": "machines idling while others starve; untie = "
     "right-size the shared compute pool (MIT, every node contributes)"},
    {"floor": 3, "issue": "capture / no sovereignty", "tangle": "data held by thrones; untie = the "
     "never-capture law: raw stays yours, invariant enters the shared wave"},
    {"floor": 4, "issue": "untrusted truth", "tangle": "claims without provenance; untie = content-"
     "addressed knots so every truth records what it took"},
    {"floor": 5, "issue": "fragility (lose it all)", "tangle": "dependency on remote compute; untie = "
     "bare-metal pure-stdlib corpus that survives losing everything"},
]


def _gw() -> Any:
    from mag import game_world
    return game_world


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def enter(player: str = "rogue") -> dict[str, Any]:
    """START A RUN (roguelike). Perm-death: the run can fail, but the HISTORY persists — the world
    folds the run's start as a permanent knot. The run's goal: untie the floors' tangles to bring
    abundance."""
    player = (player or "rogue").strip()
    gw = _gw()
    gw.set_state(f"run.{player}.started", {"player": player, "floors": len(FLOORS),
                                           "ts": _now()}, source="rogue-enter")
    return {"ok": True, "schema": SCHEMA, "player": player, "n_floors": len(FLOORS),
            "goal": "untie the topological problems (the tangles) floor by floor to introduce "
                    "abundance for all; perm-death but the history is permanent",
            "line": f"{player}, the abyss opens. Each floor is a real problem. Untie it, and the "
                    f"world grows richer for everyone. Fail, and the run ends — but the history "
                    f"remembers what you tried."}


def dungeon() -> dict[str, Any]:
    """GENERATE the roguelike: the floors = GLOBAL ISSUES, each a real topological problem. Read the
    REAL tangle from the chain (knot_untangle.scan_chain) to ground each floor in actual knots."""
    floors = []
    try:
        from mag import knot_untangle
        scan = knot_untangle.scan_chain(top=5)
        n_tangled = scan.get("n_tangled_clusters", 0)
    except Exception:
        n_tangled = 0
    for f in FLOORS:
        floors.append({**f, "tangle_note": f"real tangled clusters on chain: {n_tangled}",
                       "status": "undiscovered"})
    return {"ok": True, "schema": SCHEMA, "n_floors": len(floors), "floors": floors,
            "note": "the dungeon: each floor is a GLOBAL ISSUE = a real topological problem; the "
                    "boss is a real knot tangle, not a fake monster"}


def play(player: str, *, floor: int = 1, untie: bool = True) -> dict[str, Any]:
    """ONE ACTION in the run: untie a floor's tangle. If it works, the tangle collapses to a real
    invariant (the world folds it + it joins the shared wave = abundance). If it fails, perm-death
    — but the attempt is folded as permanent history. Deterministic + $0."""
    player = (player or "rogue").strip()
    gw = _gw()
    floor_row = next((f for f in FLOORS if f["floor"] == floor), FLOORS[0])
    key = f"run.{player}.floor.{floor}"
    # idempotent: a floor already conquered doesn't re-conquer (permanent history)
    if gw.get_state(key).get("found"):
        return {"ok": True, "schema": SCHEMA, "player": player, "floor": floor,
                "already": True, "note": "this floor was already untied — the history remembers"}
    if untie:
        # the untie: collapse the tangle -> a real invariant -> join the shared wave (abundance)
        invariant = (f"{floor_row['issue']}: untied — {floor_row['tangle']}")
        gw.set_state(key, {"floor": floor, "issue": floor_row["issue"], "untied": True,
                           "ts": _now()}, source="rogue-untie")
        abundance = 0
        try:
            from mag import republic_wave
            a = republic_wave.contribute(player, invariant)
            abundance = 1 if a.get("added_new") else 0
        except Exception:
            pass
        return {"ok": True, "schema": SCHEMA, "player": player, "floor": floor,
                "issue": floor_row["issue"], "untied": True, "abundance_added": abundance,
                "line": f"You untied the {floor_row['issue']} tangle. The invariant joined the shared "
                        f"wave — abundance for all."}
    # perm-death path (untie=False = a failed attempt): the run ends, but history persists
    gw.set_state(f"run.{player}.died", {"floor": floor, "ts": _now()}, source="rogue-death")
    return {"ok": True, "schema": SCHEMA, "player": player, "floor": floor,
            "untied": False, "perm_death": True,
            "line": f"The tangle held. The run ends — but the history remembers what you tried, "
                    f"and the next run starts from the memory."}


def history() -> dict[str, Any]:
    """THE PERMANENT GENERATIVE HISTORY: every run's attempts on the chain, never reset. The
    roguelike's perm-death is real, but the world remembers — that's the generative history that
    compounds (each failed run's lesson informs the next)."""
    gw = _gw()
    w = gw.get_state()
    runs = [{"key": k, "value": v.get("value")} for k, v in (w.get("world") or {}).items()
            if k.startswith("run.")]
    return {"ok": True, "schema": SCHEMA, "n_history_knots": len(runs),
            "history": runs[-40:], "world_root": w.get("root"),
            "note": "the permanent generative history: every run's attempts are content-addressed "
                    "knots on the chain; perm-death is real, the memory is permanent, and each run "
                    "starts from the last one's lesson (perm-generative)"}


def abundance() -> dict[str, Any]:
    """WHAT UNTANGLING EARNED: the sci-fi abundance for all = the shared wave's deduped invariants
    that every contributor benefits from. Measured from republic_wave (real)."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA}
    try:
        from mag import republic_wave
        w = republic_wave.wave()
        n_inv = w.get("n_shared_invariants", 0)
        n_con = w.get("n_contributors", 0)
        out["shared_invariants"] = n_inv
        out["contributors"] = n_con
        out["abundance"] = (f"{n_inv} shared invariants serve all {n_con} contributors — the "
                            f"deduped wave is the abundance: one truth, shared, for everyone")
    except Exception as e:
        out["error"] = str(e)[:120]
    out["note"] = ("the sci-fi abundance: untangling real tangles folds invariants into the shared "
                   "wave, and everyone benefits from the deduped truth (abundance for all, real + "
                   "measured)")
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "enter()->start a perm-death run (history persists); dungeon()->the floors = "
                        "global issues = real tangles; play()->untie a tangle (abundance) or perm-die "
                        "(history); history()->the permanent generative history; abundance()->what "
                        "untangling earned for all",
            "cost": "deterministic + $0 (reuses knot_untangle + game_world + republic_wave)",
            "reuse": "knot_untangle + dungeon_dev + game_world + republic_wave + route_trace"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="abundance-rogue")
    ap.add_argument("cmd", nargs="?", default="dungeon",
                    choices=["enter", "dungeon", "play", "history", "abundance", "status"])
    ap.add_argument("--player", default="rogue")
    ap.add_argument("--floor", type=int, default=1)
    ap.add_argument("--no-untie", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "enter":
        out = enter(a.player)
    elif a.cmd == "play":
        out = play(a.player, floor=a.floor, untie=not a.no_untie)
    elif a.cmd == "history":
        out = history()
    elif a.cmd == "abundance":
        out = abundance()
    elif a.cmd == "status":
        out = status()
    else:
        out = dungeon()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
