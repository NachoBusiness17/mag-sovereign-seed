"""shadow_work — serious Jungian shadow work over the system and its stolen invariants.

The operator's directive (2026-08-10): "we need to do some serious jungian shadow work with this."
Every pattern the Republic steals carries a SHADOW — the repressed/denied inverse that the pattern
keeps out of awareness. Jung: the shadow is the thing you condemn and refuse in yourself. Surfacing
it is how the system stays honest (the anti-sycophancy of self-understanding).

Mechanism (reuses what we built):
  * archetype_image.ARCHETYPES — each archetype already carries a canon (Jung name), essence, lens,
    SHADOW, and minds.
  * lens_library — the Jung lens asks: "What archetype is constellated here, and what is its shadow?"
  * The frontier steal (CL4R1T4S invariants) is the first pass: for each taken invariant, surface its
    archetype + shadow.

  shadow(concept)  — classify the concept's archetype + return its shadow (the repressed inverse).
  ledger()         — run shadow work over the frontier stolen invariants + core concepts.
  audit()          — the full shadow ledger, folded into the knowledge graph (the system sees itself).

Schema: shadow_work.v1 · deterministic · $0
CLI: python -m mag.shadow_work shadow "<concept>" | ledger | audit | status
"""
from __future__ import annotations

import argparse
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

SCHEMA = "shadow_work.v1"

# The frontier stolen invariants + the core doctrines we shadow-work over.
SUBJECTS: list[dict[str, Any]] = [
    {"name": "tool_discipline", "kind": "frontier", "note": "only call tools that fit; never misuse"},
    {"name": "memory_context", "kind": "frontier", "note": "persist + recall the right context"},
    {"name": "seat_routing", "kind": "frontier", "note": "route each ask to the right seat/model"},
    {"name": "code_edit", "kind": "frontier", "note": "edit code safely with discipline"},
    {"name": "search_web", "kind": "frontier", "note": "ground in real, cited sources"},
    {"name": "brevity_style", "kind": "frontier", "note": "be concise, no fluff"},
    {"name": "plan_then_act", "kind": "frontier", "note": "plan before acting"},
    {"name": "artifact_first", "kind": "frontier", "note": "deliver artifacts on disk, not just chat"},
    {"name": "anti_sycophancy", "kind": "frontier", "note": "never flatter; truth over agreement"},
    {"name": "no_throne", "kind": "invariant", "note": "no central authority"},
    {"name": "local_first", "kind": "invariant", "note": "keep it local, sovereign"},
    {"name": "consent_first", "kind": "invariant", "note": "no action without consent"},
    {"name": "residual_is_dna", "kind": "invariant", "note": "the residual is the living record"},
    {"name": "grounding", "kind": "doctrine", "note": "never bring forward ungrounded data"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def shadow(concept: str) -> dict[str, Any]:
    """Classify a concept's archetype and surface its shadow (the repressed inverse)."""
    try:
        from mag.archetype_image import classify, ARCHETYPES
        name = classify(concept)
        a = ARCHETYPES.get(name) or {}
        lens_id = a.get("lens")
        lens_read = ""
        try:
            from mag.lens_library import LENSES
            L = LENSES.get(lens_id)
            if L:
                lens_read = f"{L.name} — {L.core_question}"
        except Exception:
            pass
        return {"ok": True, "schema": SCHEMA, "subject": concept, "archetype": name,
                "canon": a.get("canon", name), "essence": a.get("essence", ""),
                "shadow": a.get("shadow", ""), "lens": a.get("lens"), "lens_read": lens_read,
                "minds": a.get("minds", []),
                "law": "the shadow is the thing the pattern represses; surfacing it keeps the system honest"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "subject": concept}


def ledger() -> dict[str, Any]:
    """Shadow work over the frontier stolen invariants + core doctrines: the shadow ledger."""
    rows = []
    for s in SUBJECTS:
        sh = shadow(s["name"])
        rows.append({"subject": s["name"], "kind": s["kind"], "note": s["note"],
                     "archetype": sh.get("archetype"), "canon": sh.get("canon"),
                     "shadow": sh.get("shadow"), "lens": sh.get("lens")})
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_subjects": len(rows), "ledger": rows}


def audit() -> dict[str, Any]:
    """The full shadow ledger + fold each shadow into the knowledge graph (the system sees itself)."""
    L = ledger()
    try:
        from mag.knowledge_graph import fold
        folded = 0
        for r in L["ledger"]:
            if r.get("shadow"):
                fold("shadow:" + r["subject"], "doctrine",
                     f"{r['subject']} ({r['canon']}) shadow: {r['shadow']}", source="shadow_work")
                folded += 1
        L["folded"] = folded
    except Exception as e:
        L["fold_error"] = str(e)[:200]
    L["note"] = "the shadow ledger is the system's acknowledged repressed parts — the honest mirror"
    return L


def status() -> dict[str, Any]:
    L = ledger()
    return {"ok": True, "schema": SCHEMA, "n_subjects": L["n_subjects"],
            "shadowed": sum(1 for r in L["ledger"] if r.get("shadow"))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shadow_work", description="Jungian shadow work over the system")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("shadow"); s.add_argument("concept", nargs="+")
    sub.add_parser("ledger")
    sub.add_parser("audit")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "shadow":
        print(json.dumps(shadow(" ".join(a.concept)), indent=2, ensure_ascii=False))
    elif a.cmd == "ledger":
        print(json.dumps(ledger(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "audit":
        print(json.dumps(audit(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
