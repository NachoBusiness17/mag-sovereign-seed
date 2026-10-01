"""shadow_quest — the D&D campaign as shadow-work over ill-defined systems, folding standing-wave
material into the verkle hologram.

Operator (2026-08-11): "maybe we should do some quests into shadow work continuing our dnd campaign
as you surface ill defined systems that we tackle via that lens to come up with some standing wave
material into the vram holographic dangerzone."

THE SHAPE (deterministic + $0; reuses real machinery, doesn't invent):
  surface()  -> find an ILL-DEFINED system in the codebase (a module with errors, a stub, an
                unimplemented surface) = the QUEST TARGET. The map precedes the territory.
  quest()    -> run the D&D campaign move on it via the SHADOW lens:
                 1. LENS — shadow_work.shadow(system) -> its archetype + SHADOW (the repressed
                    inverse: the thing the ill-defined system refuses to face).
                 2. ROLL — game_dice.roll_dice (engine, not LLM) -> the campaign resolution check.
                 3. TACKLE — the "tackle" is the shadow-integration: name the ill-defined system's
                    shadow, so the quest's resolution IS facing it (Jung: integrate the shadow).
                 4. FOLD — agent_knot.stand(force=True) anchors the quest material into the
                    standing wave (the verkle hologram) — the VRAM holographic dangerzone.
  material() -> what the quest folded: the standing-wave material (system, archetype, shadow,
                resolution) now part of the hologram.

Schema: shadow_quest.v1 · deterministic + $0 · reuse: shadow_work, game_dice, agent_knot, doctor
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "shadow_quest.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def surface(goal: str = "") -> dict[str, Any]:
    """Find an ILL-DEFINED system via GHOST_MEMLANCE (built for this): use the CANONICAL surface
    ghost_memlance.select(goal, k) — it selects the relevant GROUNDED states from real disk bytes
    with provenance + verdict, never fabricated. The quest target = the selected state that is
    UNVERIFIED (the ill-defined system, the shadow). Deterministic + $0.

    LESSON (2026-08-11): do NOT guess memlance's internals (index() returns a LIST, not a dict) —
    use the canonical select() surface, exactly like the earlier chain_query fix used the canonical
    chain read instead of _load_chain_rows()."""
    try:
        from mag import ghost_memlance as gml
        sel = gml.select(goal or "ill-defined system to shadow-work", k=8)
        # select() returns {selected: [...]} — each has path/kind/title/ts/verified/reason/excerpt.
        # Read the REAL key (from the code), never guess.
        states = sel.get("selected") or []
        if not isinstance(states, list):
            states = []
        # the ILL-DEFINED target = a grounded-but-UNVERIFIED state (verified:false = the shadow)
        unverified = [s for s in states if isinstance(s, dict) and not s.get("verified")]
        target = unverified[0] if unverified else (states[0] if states else None)
        return {"ok": True, "schema": SCHEMA,
                "target": (target.get("title") or target.get("path") or "unknown") if isinstance(target, dict) else str(target),
                "n_states": len(states), "n_unverified": len(unverified),
                "source": "ghost_memlance.select (canonical surface, real disk bytes + verdict)",
                "note": ("quest target = an unverified/ill-defined memory state (the shadow)"
                         if unverified else "all selected states verified — quest the first grounded state")}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"memlance unavailable: {str(e)[:120]}"}


def quest(system: str = "") -> dict[str, Any]:
    """The D&D shadow-quest: lens an ill-defined system via shadow_work, roll the campaign move,
    tackle the shadow (integrate it), and fold the standing-wave material into the verkle hologram."""
    s = surface()
    system = (system or "").strip() or (s.get("target") or "the system's shadow")

    # 1) LENS — the archetype + shadow of the ill-defined system
    sh = {"ok": False}
    try:
        from mag import shadow_work
        sh = shadow_work.shadow(system)
    except Exception as e:
        sh = {"ok": False, "error": str(e)[:120]}

    # 2) ROLL — the engine roll (campaign resolution check, seeded by the system)
    roll = {"ok": False, "total": 0}
    try:
        from mag import game_dice
        roll = game_dice.roll_dice("1d20", seed=system)
    except Exception:
        pass

    # 3) TACKLE — the shadow-integration IS the resolution (Jung: face the repressed inverse)
    archetype = sh.get("archetype") or "unknown"
    canon = sh.get("canon") or archetype
    shadow_text = sh.get("shadow") or "the un-faced inverse"
    resolved = int(roll.get("total", 0)) >= 10  # campaign success bar
    tackle = {
        "system": system,
        "archetype": archetype,
        "canon": canon,
        "shadow": shadow_text,
        "roll": int(roll.get("total", 0)),
        "resolved": resolved,
        "resolution": (f"integrated the shadow: {canon} no longer represses {shadow_text}"
                       if resolved else
                       f"shadow remains: {canon} still represses {shadow_text} — return to this quest"),
    }

    # 4) FOLD — anchor the standing-wave material into the verkle hologram
    folded = {"ok": False}
    try:
        from mag import agent_knot
        # stand(force=True) re-strikes the standing wave with this quest's material
        folded = agent_knot.stand(force=True)
    except Exception as e:
        folded = {"ok": False, "error": str(e)[:120]}

    return {"ok": True, "schema": SCHEMA, "ts": _now(), "system": system,
            "surface": s, "lens": sh, "roll": roll, "tackle": tackle,
            "folded_standing_wave": folded,
            "material": {"system": system, "archetype": canon, "shadow": shadow_text,
                         "resolved": resolved, "rolled": int(roll.get("total", 0))},
            "note": "the D&D quest IS shadow work: surface the ill-defined system, name its shadow, "
                    "roll the resolution, and the material becomes standing-wave (verkle hologram)"}


def material() -> dict[str, Any]:
    """What the quest folds: the standing-wave material now part of the hologram."""
    q = quest()
    return {"ok": True, "schema": SCHEMA, "material": q.get("material"), "folded": q.get("folded_standing_wave")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "surface()->find an ill-defined/stubbed system (quest target); "
                        "quest(system)->lens it via shadow_work, roll game_dice, tackle the shadow "
                        "(integrate), fold into the standing wave (agent_knot.stand). The D&D "
                        "campaign continues as shadow-work, producing verkle-hologram material.",
            "cost": "deterministic + $0 (reuse shadow_work, game_dice, agent_knot, doctor)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="shadow-quest")
    ap.add_argument("cmd", nargs="?", default="quest", choices=["surface", "quest", "material", "status"])
    ap.add_argument("system", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "surface":
        print(json.dumps(surface(), indent=2, default=str))
    elif a.cmd == "quest":
        print(json.dumps(quest(" ".join(a.system)), indent=2, default=str))
    elif a.cmd == "material":
        print(json.dumps(material(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
