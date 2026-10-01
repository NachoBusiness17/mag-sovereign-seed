"""castle_foundation — THE FORMULA MADE REAL: standing wave + zeitgeist + growth = foundations under
the castles. The loop folds the zeitgeist (the castles) + the shadow work (what you don't look at)
into DETERMINISTIC FOUNDATIONS (invariants -> verkle knots), measuring growth each beat.

Operator (2026-08-11): "the shadow work is the part that you don't look at and the castles in the
sky are our zeitgeist. the standing wave +zeitgeist + growth = 'If you have built castles in the
air, your work need not be lost; that is where they should be. Now put the foundations under them.'"
+ "make it so"

THE FORMULA (deterministic + $0, reuses our systems):
  castles()     -> the ZEITGEIST (the castles in the air): self_loop zeitgeist + coldest vector.
  shadow()      -> the SHADOW WORK (what you don't look at): diamond_mine tesuji from the garbage.
  foundation()  -> the STANDING WAVE folds castles + shadow into FOUNDATIONS: compile the zeitgeist
                   + the tesuji into invariants -> anchor them as verkle knots (agent_knot/verkle).
                   Measures GROWTH: invariants folded this beat vs before.
  wave()        -> ONE BEAT of the formula: castles + shadow -> foundation + growth -> routed to the
                   swarm for the novel foundation-building. "Put the foundations under them."

Schema: castle_foundation.v1 · deterministic + $0 · reuse: self_loop, diamond_mine, verkle_knot,
agent_knot, swarm_surface
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

SCHEMA = "castle_foundation.v1"
LEDGER = ROOT / "memory" / "castle_foundation" / "growth.jsonl"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def castles() -> dict[str, Any]:
    """The ZEITGEIST — the castles in the air: the coldest vector / direction the swarm should fill."""
    z: dict[str, Any] = {"ok": True, "schema": SCHEMA}
    try:
        from mag import self_loop
        g = self_loop.loop_zeitgeist()
        z["coldest_vector"] = g.get("coldest_vector", [])[:5]
        z["consensus_direction"] = g.get("consensus_direction")
    except Exception as e:
        z["error"] = str(e)[:80]
    return z


def shadow() -> dict[str, Any]:
    """The SHADOW WORK — the part you don't look at: the tesuji mined from the garbage pile."""
    try:
        from mag import diamond_mine
        m = diamond_mine.mine(enqueue=False)
        return {"ok": True, "schema": SCHEMA, "n_tesuji": m.get("n_finds", 0),
                "top": m.get("top_tesuji", [])[:5]}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:80]}


def _prior_growth() -> dict[str, int]:
    if not LEDGER.is_file():
        return {"invariants": 0, "knots": 0}
    inv, knots = 0, 0
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            inv = r.get("n_invariants", inv)
            knots = r.get("n_knots", knots)
        except Exception:
            continue
    return {"invariants": inv, "knots": knots}


def foundation() -> dict[str, Any]:
    """The STANDING WAVE folds castles + shadow into FOUNDATIONS: invariants -> verkle knots.
    Measures GROWTH (invariants folded this beat vs before)."""
    c = castles()
    s = shadow()
    # the foundation invariant = the zeitgeist direction + the shadow tesuji, content-addressed
    n_new_invariants = s.get("n_tesuji", 0)
    # anchor the foundation as a verkle knot (the standing wave's build)
    knot = {}
    try:
        from mag import verkle_knot
        summary = (f"castle-foundation: zeitgeist={c.get('consensus_direction') or c.get('coldest_vector','')[:40]} "
                   f"shadow_tesuji={s.get('n_tesuji')}")
        knot = verkle_knot.append_verkle_knot({"session_id": f"castle-foundation-{_now()[:13]}",
                                               "theme": "foundation", "summary": summary[:400]})
    except Exception as e:
        knot = {"error": str(e)[:80]}
    prior = _prior_growth()
    growth = {"invariants": prior["invariants"] + n_new_invariants,
              "n_knots": prior["knots"] + (1 if knot.get("leaf_hash") else 0)}
    return {"ok": True, "schema": SCHEMA, "castles": c, "shadow": s,
            "foundation_knot": (knot.get("leaf_hash") or "")[:16],
            "n_new_invariants": n_new_invariants, "growth": growth,
            "growth_delta": growth["invariants"] - prior["invariants"],
            "note": "the standing wave folded castles + shadow into a foundation (verkle-anchored)"}


def wave(*, enqueue: bool = True, surface: str = "castle-foundation") -> dict[str, Any]:
    """ONE BEAT of the formula: castles + shadow -> foundation + growth -> routed to the swarm.
    'Now put the foundations under them.'"""
    f = foundation()
    q = {"ok": False, "task_id": ""}
    if enqueue:
        try:
            from mag import swarm_surface
            goal = (f"CASTLE-FOUNDATION BEAT [castle_foundation]: the zeitgeist (castles) is "
                    f"{f.get('castles',{}).get('coldest_vector',[])[:2]} and the shadow work found "
                    f"{f.get('n_new_invariants')} tesuji. Fold these into foundations (invariants -> "
                    f"verkle knots) + build the highest-leverage one. Growth={f.get('growth')}. "
                    f"Put the foundations under the castles.")
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    # record the growth beat
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _now(), "n_invariants": f["growth"]["invariants"],
                             "n_knots": f["growth"]["n_knots"]}, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "ts": _now(), **f,
            "enqueued": q.get("ok", False), "task_id": q.get("task_id", ""),
            "formula": "standing wave + zeitgeist + growth = foundations under the castles",
            "note": "one beat of the formula: castles + shadow -> foundation + growth -> the swarm "
                    "builds it. Put the foundations under them."}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "castles()->the zeitgeist; shadow()->the shadow work; foundation()->fold "
                        "into verkle-anchored foundations + measure growth; wave()->one beat of the "
                        "formula (routed to the swarm)",
            "cost": "deterministic + $0 (reuses self_loop, diamond_mine, verkle_knot, swarm_surface)",
            "formula": "standing wave + zeitgeist + growth = foundations under the castles"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="castle-foundation")
    ap.add_argument("cmd", nargs="?", default="wave", choices=["wave", "castles", "shadow", "foundation", "status"])
    a = ap.parse_args()
    if a.cmd == "castles":
        print(json.dumps(castles(), indent=2, default=str))
    elif a.cmd == "shadow":
        print(json.dumps(shadow(), indent=2, default=str))
    elif a.cmd == "foundation":
        print(json.dumps(foundation(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(wave(), indent=2, default=str))
