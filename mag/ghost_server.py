"""ghost_server — the Republic's discovery contract: the consumable front door for any RPG/creator.

Built from the memweave (organ: interface). The Republic-as-a-service, machine-readable so any creator
can plug in. REUSES ecosystem_surface (self-steal — no duplicate bundle); ADDS the consumable manifest:
resources, how to call them, the A/B/C metering tiers, and the sandboxed-helper boundary.

  manifest()   -> the discovery contract: resources (from ecosystem_surface) + tiers + boundary.
  advertise()  -> the human-readable "come plug in" surface (the Turtle WoW front door).
  help(res)    -> how to call one resource (endpoint/contract).

Schema: ghost_server.v1 · deterministic $0
CLI:  python -m mag.ghost_server manifest | advertise
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ghost_server.v1"

# The consumable resources (organs of the Republic) + how to call each.
RESOURCES: list[dict[str, Any]] = [
    {"id": "world/canon",   "organ": "canon",      "desc": "source-backed world lore",        "via": "knowledge_graph.known/context"},
    {"id": "world/search",  "organ": "canon",      "desc": "search the source-backed graph",   "via": "knowledge_graph.global_search"},
    {"id": "characters",    "organ": "actors",     "desc": "archetype + shadow cast",          "via": "archetype_image.classify"},
    {"id": "quests/open",   "organ": "actors",     "desc": "the open loops / gaps to fill",    "via": "dirac_loop.scan"},
    {"id": "state/commit",  "organ": "canon",      "desc": "immutable content-addressed save",  "via": "verkle_knot"},
    {"id": "lore/whisper",  "organ": "comms",      "desc": "deniable hidden lore",             "via": "whisper_image / whisper_route"},
    {"id": "governance",    "organ": "laws",       "desc": "the world's constitution + audit", "via": "republic_governance"},
    {"id": "ecosystem",     "organ": "interface",  "desc": "whole-ecosystem machine bundle",   "via": "ecosystem_surface.ecosystem"},
    {"id": "code/intel",    "organ": "memory",     "desc": "Pylance-style DETERMINISTIC code-intelligence memtools: ground the ghost's stochastic memory work against our own code (diagnose / symbols / references / trace_value / imports / self_check)", "via": "ghost_pylance"},
    {"id": "memory/select", "organ": "memory",     "desc": "GHOSTLANCE-for-memory: SELECTIVE, grounded memory-state selection without hallucination. index() / select(goal) / trace_state(key) / verify(key) / self_check() — returns only REAL bytes from disk with provenance + a deterministic verified verdict, flags unverified states so they are never carried forward as truth.", "via": "ghost_memlance"},
    {"id": "memory/lands",  "organ": "memory",     "desc": "MEMLANDS — the DUAL-FUNCTION memory surface: read ≡ write ≡ steal in one flow act. flow(label, content, ctx) does eliminate→read(grounded)→adapt→write(content-addressed)→reindex; lattice() surfaces the swarm-as-memory view (GPU VRAM telemetry + verkle bus + knots). Reading and writing the shared lattice are one act (single-surface / flocking).", "via": "mem_lands"},
    {"id": "memory/verkle", "organ": "memory",     "desc": "VERKLE LANCE — deterministic knot-lattice intelligence (like ghostlance for the verkle chain): index() / temporal() / trace(key) / link(event) / verify(key) / self_check(). Uses content-addressed determinism (leaf_hash + parent/child verkle roots + chain index) to map memory events to knots and tie them together TEMPORALLY (parent→child roots, turtles down).", "via": "verkle_lance"},
]

# The A/B/C metering tiers (from the Horizon steal) + the sandboxed-helper boundary.
TIERS = {
    "A": "platform (capped pool, signed-in, global cap, kill switch) — we broker at pennies",
    "B": "BYOK (bring your own key) — you pay your own frontier",
    "C": "free deterministic (the $0 floor) — always ours",
}
BOUNDARY = ("sandboxed helper: the public surface reveals only safe, on-theme artifacts "
            "(larp code + hot dog poems); no privileged tools or secrets co-located — nothing to leak (Lampson).")


def manifest() -> dict[str, Any]:
    """The discovery contract: what the Republic offers + how + at what tier."""
    bundle = {}
    try:
        from mag.ecosystem_surface import ecosystem
        eco = ecosystem()
        bundle = {"fingerprint": eco.get("fingerprint") or list(eco.keys())[:6]}
    except Exception as e:
        bundle = {"error": str(e)[:120]}
    return {"ok": True, "schema": SCHEMA, "name": "the Mycelial Republic — ghost server",
            "resources": RESOURCES, "tiers": TIERS, "boundary": BOUNDARY,
            "ecosystem": bundle,
            "doctrine": "consume the Republic: free floor (C), penny frontier (A), or bring-your-own (B); "
                        "leak-proof by construction; residual funds the flywheel"}


def advertise() -> str:
    """The human-readable front door (Turtle WoW ethos) — what a creator sees."""
    return (
        "# The Mycelial Republic — ghost server\n\n"
        "A post-scarcity backend for any RPG or creator. Source-backed canon, archetype cast, "
        "open quests, immutable state, deniable lore, and Ostrom governance — at $0, pennies, or "
        "your own key. Leak-proof by construction; the more you use it, the smarter it gets "
        "(residual -> flywheel).\n\n"
        "Plug in: read the manifest, call the resources, pick a tier.\n"
        "Vanilla core, community-directed, turtle pace — this is the Republic's own Turtle WoW."
    )


def help(res_id: str) -> dict[str, Any]:
    """How to call one resource."""
    for r in RESOURCES:
        if r["id"] == res_id:
            return {"ok": True, "resource": r["id"], "desc": r["desc"], "via": r["via"]}
    return {"ok": False, "error": f"no resource '{res_id}'", "known": [r["id"] for r in RESOURCES]}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="ghost_server", description="Republic discovery contract")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("manifest")
    sub.add_parser("advertise")
    h = sub.add_parser("help"); h.add_argument("res")
    a = p.parse_args(argv)
    if a.cmd == "advertise":
        print(advertise())
    elif a.cmd == "help":
        print(json.dumps(help(a.res), indent=2))
    else:
        print(json.dumps(manifest(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
