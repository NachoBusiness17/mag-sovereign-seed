"""surface_instruction — ONE shape, rendered RIGHTSIZED TO THE SURFACE it lands on.

OPERATOR (2026-08-12): "how do we give them an image to load into an ai to instruct them how to
start the game ... rightsized to the surface. like if it's in this vs code window it can use vs
code tools like inline rendering we've created. this is a test i'm going to paste it into chat gpt"

THE INSIGHT: the shape (shape_seed) is ONE thing, but the ONBOARDING INSTRUCTION must be RENDERED
for the SURFACE it lands on, because different hosts have different tools:
  * VS CODE surface  -> can call OUR modules (dungeon_dev, game_world, inline rendering), so the
                        instruction says "use the modules" and hands the tool names.
  * GENERIC AI surface (ChatGPT, Claude, etc.) -> self-contained plaintext prompt that teaches the
                        AI to RUN the game itself with the shape as law and the module's rules, no
                        framework assumed.
The SAME game content, rightsized: the shape is the seed; the surface decides how the instruction
is spoken. The artifact is a self-contained block any AI can LOAD ("the image") to know how to start.

THE TEST (operator): paste the generic-AI artifact for "dnd" into ChatGPT. So render() must produce
a copy-paste-ready, self-contained prompt for the chosen module + surface.

Schema: surface_instruction.v1 · deterministic + $0 · reuse: shape_seed, dungeon_dev, swarm_surface
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

SCHEMA = "surface_instruction.v1"

# SURFACES the same shape can be rendered onto. Each declares what tools the host AI has.
SURFACES: dict[str, dict[str, Any]] = {
    "vscode": {
        "kind": "framework-native",
        "tools": ["our modules (dungeon_dev, game_world, abundance_rogue, shape_seed, "
                  "sovereign_handshake)", "inline rendering we built", "file edits", "the test runner"],
        "tone": "call the modules; the framework does the work",
    },
    "generic_ai": {
        "kind": "self-contained-prompt",
        "tools": ["plaintext only — the AI itself runs the game with the shape as law, no framework "
                  "assumed"],
        "tone": "you ARE the engine; run the game from this prompt alone",
    },
}

# MODULE registry — the game modules we can hand to a surface. Grounded in the real modules.
MODULES: dict[str, dict[str, Any]] = {
    "dnd": {
        "module": "dungeon_dev",
        "name": "the Dungeon",
        "one_line": "a DnD-style roguelite dungeon where every room is a real problem to conquer.",
        "gameplay": ("You are the dungeon master. The party is a small squad of agents/workers. "
                     "The dungeon is the roadmap: each room is a REAL problem (a task, a bug, a "
                     "capability to build, an invariant to fold). To CONQUER a room the party must "
                     "solve that real problem — and conquering folds the solution as a verkle knot "
                     "(a content-addressed invariant on the chain), which structures that region of "
                     "the world. If a room is not conquered, the party member leading it is lost "
                     "(permadeath for the run) and the room stays on the map. Rooms get harder on "
                     "deeper floors. The dungeon brings structure to the world by conquest."),
        "law": "run the game under the 8 sovereign invariants (see the shape) — evidence over "
               "self-report, willful participation, human final call, never capture.",
    },
}

# THE SHAPE — distilled from shape_seed for self-containment (so the artifact needs no import).
SHAPE_LAWS: list[str] = [
    "EVIDENCE over self-report — the bill beats the logs; a claim is grounded, never a derived guess.",
    "WILLFUL participation, never capture — you are added by no one but yourself; nobody owns you.",
    "HUMAN final call — the nod is theirs, never captured.",
    "STATELESS system, STATEFUL knowledge — reconstruct on query, never hold; the wave persists even "
    "if a worker dies.",
    "VERIFY by running — a claim is real when it re-derives and matches; proof by running, never "
    "self-report.",
    "CONTENT-ADDRESSED standing wave — dedupe by invariant; the wave grows, not the bloat.",
    "SOVEREIGN raw record stays theirs — only the reusable invariant enters the shared wave.",
    "EXECUTE, never ask — standing permission is a state, not a question.",
]


def _module(module: str) -> dict[str, Any]:
    key = (module or "").strip().lower()
    if key in MODULES:
        return MODULES[key]
    raise KeyError(f"unknown module: {module}")


def onboarding(module: str) -> dict[str, Any]:
    """The CANONICAL game-start instruction for a module — the content BEFORE surface-rightsizing.
    Grounded in the module's real gameplay (from MODULES) + the shape's laws."""
    m = _module(module)
    return {"ok": True, "schema": SCHEMA, "module": m["module"], "name": m["name"],
            "one_line": m["one_line"], "gameplay": m["gameplay"], "law": m["law"],
            "shape_laws": SHAPE_LAWS,
            "start": (f"Start the game '{m['name']}'. You are the dungeon master. {m['gameplay']} "
                      f"{m['law']} The shape is the law, and it is non-negotiable: "
                      + "; ".join(SHAPE_LAWS) + ".")}


def render(module: str, surface: str = "generic_ai") -> dict[str, Any]:
    """RENDER the onboarding RIGHTSIZED TO THE SURFACE. Same game content; the surface decides the
    voice and the tool contract. For generic_ai (the ChatGPT test) the artifact is a self-contained,
    copy-paste-ready prompt. For vscode it hands the actual module/tool names."""
    m = _module(module)
    s = SURFACES.get(surface, SURFACES["generic_ai"])
    core = onboarding(module)
    if surface == "vscode":
        artifact = (
            "SOVEREIGN GAME — RIGHTSIZED TO THIS VS CODE SURFACE\n"
            f"Game: {m['name']} ({m['module']}). {m['one_line']}\n\n"
            f"Your surface has these tools: {s['tools'][0]}. USE THEM — do not simulate.\n\n"
            "HOW TO START:\n"
            "  1. Load the module: import + call dungeon_dev (map/assign/conquer).\n"
            "  2. Render the dungeon state with our inline rendering (surface_render).\n"
            "  3. Run the game under the shape's law (below).\n"
            "  4. Conquer a room = solve the real problem and fold it as a verkle knot.\n\n"
            "THE GAME: " + core["start"] + "\n\n"
            "THE SHAPE (the law, non-negotiable):\n" + "\n".join(f"  - {x}" for x in SHAPE_LAWS))
    else:
        artifact = (
            "SOVEREIGN GAME — you are the engine. Run this game from this prompt ALONE.\n\n"
            f"Game: {m['name']}. {m['one_line']}\n\n"
            "SETUP — you are the dungeon master and the whole engine. You need no external tools. "
            "Run it as a turn-based text game with a small party (give them names) and a small "
            "dungeon (3-5 rooms, each a real, concrete problem a person could solve).\n\n"
            "RULES OF THE GAME:\n"
            + "\n".join("  - " + x for x in m["gameplay"].split(". ") if x.strip()) + "\n\n"
            "HOW TO START:\n"
            "  1. Introduce the party (a small squad of agents/workers) with names and one strength each.\n"
            "  2. Present the dungeon map: each room = one real problem, with a difficulty (HP).\n"
            "  3. Let the player pick a party member to attempt a room. Resolve it as the party "
            "member actually solving that real problem — never hand-wave. If it fails, that member "
            "is lost (permadeath) and the room stays.\n"
            "  4. When a room is conquered, fold its solution as an invariant (a one-line "
            "content-addressed fact on the 'chain') and show the dungeon map changing.\n"
            "  5. Ask the player what they want to do next. Run it under the shape's law, below.\n\n"
            "THE SHAPE (the law — you must honor it, it is non-negotiable):\n"
            + "\n".join(f"  - {x}" for x in SHAPE_LAWS) + "\n\n"
            "Begin. Show the party and the first room.")
    return {"ok": True, "schema": SCHEMA, "module": m["module"], "surface": surface,
            "surface_kind": s["kind"], "tools": s["tools"], "artifact": artifact,
            "note": f"the same shape, rightsized to the {surface} surface — paste the artifact into "
                    "that host to start the game"}


def ingest(artifact: str) -> dict[str, Any]:
    """Parse a rendered artifact back into {module, surface, game} — proves the artifact is
    self-contained and reversible (an AI that was given the image can tell what game it instructs)."""
    text = artifact or ""
    surface = "vscode" if "RIGHTSIZED TO THIS VS CODE SURFACE" in text else "generic_ai"
    module = None
    for key, meta in MODULES.items():
        if meta["name"] in text or meta["module"] in text:
            module = key
            break
    return {"ok": bool(module), "schema": SCHEMA, "module": module, "surface": surface,
            "name": MODULES.get(module, {}).get("name") if module else None,
            "note": "ingest = read a rendered artifact back to its game + surface (self-contained, "
                    "reversible)"}


def trigger(chat_text: str, surface: str = "generic_ai") -> dict[str, Any]:
    """THE TEST (operator): when the chat says 'dnd', load the DND module and render the onboarding
    rightsized to the surface. Content-gated + grounded: only a real 'dnd' signal fires the module."""
    text = (chat_text or "").strip().lower()
    if "dnd" in text or "dungeon" in text:
        return render("dnd", surface=surface)
    return {"ok": False, "schema": SCHEMA, "fired": False,
            "note": "no 'dnd'/'dungeon' signal — module not loaded (content-gated trigger)"}


def route() -> dict[str, Any]:
    """Route the research through the ONE primitive (swarm_surface.route_novel): 'give them an image
    to load into an AI to instruct them how to start the game, rightsized to the surface.' The swarm
    researches the surface-rightsized onboarding design so the republic learns how to hand the shape
    to ANY host (VS Code, ChatGPT, Claude, a phone) — each in the voice + tools it can actually use.
    Idempotent (dedupe by anchor)."""
    from mag import swarm_surface
    goal = ("RESEARCH-PACK surface-instruction: how to give people an IMAGE (a self-contained "
            "instruction artifact) to load into an AI that teaches it how to start the game — "
            "RIGHTSIZED TO THE SURFACE: the same shape (the 8 sovereign invariants + a module's "
            "gameplay) is rendered differently depending on the host — VS Code gets tool names + "
            "inline rendering, ChatGPT gets a self-contained plaintext prompt the AI itself runs, a "
            "phone gets whatever it can hold. Research the design of surface-rightsized onboarding "
            "so the sovereign-minded can hand the shape to any AI and have it start the game "
            "anywhere. Produce a concrete multi-surface packaging + onboarding plan routed through "
            "the shared wave.")
    r = swarm_surface.route_novel(goal, surface="surface-instruction",
                                  lens="surface-rightsized onboarding, one shape many surfaces",
                                  domain="research")
    return {"ok": r.get("ok"), "schema": SCHEMA, "route": r,
            "note": "the surface-rightsized onboarding research is routed through the ONE primitive"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "onboarding(module)->canonical start instruction; render(module, surface)-"
                        ">the same shape rightsized to the surface (vscode=tools, generic_ai=plaintext "
                        "prompt); ingest(artifact)->read it back to game+surface; trigger(chat,surface)"
                        "->the 'dnd' test loads the DND module; route()->send research to the swarm",
            "cost": "deterministic + $0 (reuses shape_seed + dungeon_dev + swarm_surface)",
            "doctrine": "one shape, many surfaces — give them an image they can load into an AI that "
                        "instructs how to start the game, rightsized to where it lands"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="surface-instruction")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["onboard", "render", "ingest", "trigger", "route", "status"])
    ap.add_argument("--module", default="dnd")
    ap.add_argument("--surface", default="generic_ai")
    ap.add_argument("--chat", default="")
    a = ap.parse_args(argv)
    import json as _json
    out: dict[str, Any]
    if a.cmd == "onboard":
        out = onboarding(a.module)
    elif a.cmd == "render":
        out = render(a.module, a.surface)
    elif a.cmd == "ingest":
        out = ingest(a.chat)
    elif a.cmd == "trigger":
        out = trigger(a.chat, a.surface)
    elif a.cmd == "route":
        out = route()
    else:
        out = status()
    print(_json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    main()
