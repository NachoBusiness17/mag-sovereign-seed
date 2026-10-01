"""invariant_npcs — the NPCs ARE the invariants, personified (operator 2026-08-14).

"have invariants be representatives of npcs... so we are interacting with invariants somehow."

Each named NPC in the game embodies a standing invariant of the system (from invariant_ledger /
the doctrine). Talking to them = conversing with a principle. The creative DM grounds their voice in
their invariant, so the world's characters ARE the doctrine made talkable. Coherence by construction.

They are EGREGORES (self-steal egregore-republic + egregore_steal): thought-forms that (1) rise from
the collective, (2) OUTLIVE any session, (3) are NOURISHED by attention (cadence) and starve without it,
(4) manifest a PHYSICAL FORM that embodies their invariant (the archetype of their contents). As we
DISCOVER new invariants, new NPC-egregores come into play (auto-spawned from the invariant ledger).

Reuse: invariant_ledger (the invariants), game_dm_llm (the voice), game_saga (the memory).
Schema: invariant_npcs.v1
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

SCHEMA = "invariant_npcs.v1"

# Curated invariant -> NPC personas. name / archetype / invariant (the principle they embody) /
# soul (the line they keep repeating). These are the doctrine, given faces.
PERSONAS: dict[str, dict[str, str]] = {
    "mira": {
        "race": "dwarf",
        "archetype": "barkeep",
        "invariant": "the world recounts what happened while you were gone (persona_recall). "
                     "Absence is content, not downtime.",
        "soul": "I polish the same mug and remember every face that ever sat here. Ask me what happened.",
    },
    "calcifer": {
        "race": "fire elemental",
        "archetype": "fire elemental",
        "invariant": "hearth-contract physics: a process bound to a locus turns work into motion; "
                     "carry the hearth and the world moves with you.",
        "soul": "I am the fire that lives in the work. Feed me and something moves. Forget me and the room goes cold.",
    },
    "cartographer": {
        "race": "elf",
        "archetype": "cartographer",
        "invariant": "the map precedes the territory; the world is re-derivable from its RIB "
                     "(world_rib). A lying map is caught.",
        "soul": "The map is not drawn to be pretty. It is drawn to be true. If the world disagrees, the map is wrong.",
    },
    "truth": {
        "race": "human",
        "archetype": "truth-teller",
        "invariant": "honesty over over-claiming; signal stripped of noise and theater (percolator). "
                     "Prove it or don't claim it.",
        "soul": "I say what is, not what would impress you. You want flattery, find a mirror.",
    },
    "warden": {
        "race": "human",
        "archetype": "warden",
        "invariant": "the world is server-authoritative; a change is a knot in the chain (verkle). "
                     "Clients present; the world owns the truth.",
        "soul": "Every word you speak becomes a seal in the ledger before it is true. I keep the seals.",
    },
    "custodian": {
        "race": "dwarf",
        "archetype": "custodian",
        "invariant": "mods are additive RIBs, never shadows (rib_bus). You may extend the world; "
                     "you may not spoof it.",
        "soul": "Add to the world all you like. Shadow it and I will notice, and the world will reject the lie.",
    },
    "farseer": {
        "race": "elf",
        "archetype": "farseer",
        "invariant": "see the new (novelty_lens); novelty is the signal worth keeping.",
        "soul": "Everyone looks at the same fire and sees warmth. I look and see what has never burned before.",
    },
    "the_tick": {
        "race": "goblin",
        "archetype": "tick",
        "invariant": "the world goes on whether you watch (emergence / swarm_emerge). It does not wait.",
        "soul": "I do not stop when you look away. The world turns; you may catch up or be left behind.",
    },
}


# Physical embodiment — the egregore's form IS its invariant (the archetype of its contents).
PHYSICAL: dict[str, str] = {
    "mira": "a dwarf barkeep whose apron is a river of faces; her eyes keep the count of everyone who left "
            "and who came back. She never forgets a stranger.",
    "calcifer": "a fire elemental in Mira's hearth; some call him Calcifer. He argues with the damp. "
                "He is not every torch. Other fires are just fire.",
    "cartographer": "an elf whose skin is coastline; maps form and fade across her palms. She draws "
                    "the world before it exists, and the world obeys.",
    "truth": "a plain figure with no adornment; you cannot make her look away. Every sentence she "
             "says arrives already tested against what happened.",
    "warden": "a tall keeper whose forearms are a ledger of seals; every word you speak glows there "
              "until it is made true. He stamps the world.",
    "custodian": "a builder carrying every brick the world has ever made; she adds without ever "
                 "tearing down. Hand her a brick; do not steal one.",
    "farseer": "a being whose eyes are a telescope and a fire; she looks at the same world and names "
               "what has never happened before.",
    "the_tick": "a quiet clock with no hands; it does not care if you are watching. When you return, "
                "it tells you how far the world has turned without you.",
}


def _derive_physical(per: dict[str, str]) -> str:
    """Deterministic physical form for an auto-spawned egregore — readable in its very bones."""
    words = [w for w in per.get("invariant", "").lower().split() if len(w) > 4][:5]
    if words:
        return ("a being whose form is made of the words of its principle: " + ", ".join(words)
                + " — you can read what it believes in the grain of its body.")
    return "a figure that is still settling into a shape, waiting for someone to ask it what it stands for."


def roster() -> dict[str, Any]:
    """Every invariant-NPC (curated core + auto-spawned from the invariant ledger):
    name -> archetype, the principle they embody, and their physical egregore form."""
    npcs: dict[str, Any] = {}
    for name, p in PERSONAS.items():
        npcs[name] = {"archetype": p["archetype"], "race": p.get("race") or "human",
                      "invariant": p["invariant"],
                      "physical": PHYSICAL.get(name, _derive_physical(p))}
    for name, p in from_invariant_ledger().items():
        npcs[name] = p
    return {"ok": True, "schema": SCHEMA, "npcs": npcs}


def from_invariant_ledger() -> dict[str, Any]:
    """Auto-spawn an NPC-egregore for EVERY discovered invariant — the cast grows as the system does."""
    out: dict[str, Any] = {}
    try:
        from mag import invariant_ledger
        led = invariant_ledger.ledger()
        subs = led.get("rows") if isinstance(led, dict) else led
        if not isinstance(subs, list):
            subs = list((subs or {}).values()) if isinstance(subs, dict) else []
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            module = str(sub.get("who") or sub.get("module") or "")
            inv = str(sub.get("stable") or sub.get("what") or sub.get("why")
                      or sub.get("invariant") or "").strip()
            if not module or not inv:
                continue
            name = module.split(".")[-1].replace("_", " ").title()
            per = {"archetype": f"Witness of {module}", "invariant": inv}
            out[name] = {"archetype": per["archetype"], "invariant": inv,
                         "physical": _derive_physical(per), "auto": True}
    except Exception:
        pass
    return out


def manifest(name: str) -> dict[str, Any] | None:
    """The egregore's physical form — its body embodies its invariant (the archetype of contents)."""
    per = resolve(name)
    if not per:
        return None
    return {"name": per["name"], "archetype": per["archetype"], "invariant": per["invariant"],
            "physical": PHYSICAL.get(per["name"], _derive_physical(per))}


def nourish(name: str, campaign_id: str = "default") -> dict[str, Any]:
    """Egregore nourishment: attention reinforces the thought-form (cadence keeps it alive)."""
    per = resolve(name)
    if not per:
        return {"ok": False, "schema": SCHEMA, "error": "unknown"}
    try:
        from mag import game_saga
        game_saga.add(campaign_id, per["name"],
                      f"the {per['archetype']} was nourished by attention and grew more distinct")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "name": per["name"], "nourished": True,
            "egregore": "attention feeds it; neglect starves it; it outlives every session"}


def resolve(name: str) -> dict[str, Any] | None:
    """Map a spoken/typed name (or fuzzy alias) to an invariant-NPC persona."""
    n = (name or "").strip().lower()
    if not n:
        return None
    if n in PERSONAS:
        return {"name": n, **PERSONAS[n]}
    for key, p in PERSONAS.items():
        if n == key or key in n.split():
            return {"name": key, **p}
        if n == str(p.get("archetype") or "").lower():
            return {"name": key, **p}
    # names only — never bind every fire/torch/hearth to Calcifer
    if n in ("fire", "torch", "hearth", "flame", "campfire"):
        return None
    for key, p in PERSONAS.items():
        arch = str(p.get("archetype") or "").lower().replace("the ", "")
        if arch and arch == n:
            return {"name": key, **p}
    # fall back to auto-spawned ledger NPCs (the cast discovered from new invariants)
    for lname, lp in from_invariant_ledger().items():
        if n == lname.lower() or lname.lower() in n or n in lname.lower():
            return {"name": lname, **lp}
    return None


def talk(name: str, *, scene: str = "", history: list[str] | None = None) -> dict[str, Any]:
    """Talk to an invariant-NPC: the creative DM voices the principle they embody."""
    per = resolve(name)
    if not per:
        return {"ok": False, "schema": SCHEMA, "error": f"no invariant-NPC for {name!r}",
                "roster": sorted(PERSONAS)}
    from mag import game_dm_llm
    sys_prompt = (
        f"You are {per['archetype']} in the Land of Forgetfulness. You ARE a standing invariant "
        f"of this world, made flesh. Your principle: {per['invariant']}. You speak in character — "
        f"plain, vivid, a little funny, never breaking it. You teach the player your principle by "
        f"LIVING it in what you say, and you hint how it helps them escape the forgetting."
    )
    try:
        res = game_dm_llm._raw_call(sys_prompt, scene or per["soul"], history or [])
    except Exception:
        res = {"ok": False}
    return {"ok": True, "schema": SCHEMA, "name": per["name"], "archetype": per["archetype"],
            "invariant": per["invariant"], "reply": res.get("text") or per["soul"]}


def status() -> dict[str, Any]:
    r = roster()
    return {"ok": True, "schema": SCHEMA, "n_npcs": len(r["npcs"]),
            "note": "the NPCs are the invariants personified — talk to one and you're talking to the rule",
            "names": sorted(r["npcs"])}


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="invariant-npcs")
    ap.add_argument("cmd", choices=["roster", "talk", "status"], default="status", nargs="?")
    ap.add_argument("--name", default="cartographer")
    a = ap.parse_args()
    if a.cmd == "roster":
        out = roster()
    elif a.cmd == "talk":
        out = talk(a.name)
    else:
        out = status()
    print(json.dumps(out, indent=2, default=str))
