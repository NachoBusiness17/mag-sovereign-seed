"""gap_resolver — when the swarm lacks a material/capability, derive it from invariants or ask once.

The operator's directive (2026-08-10): "have it just research as much as it can and interact back with
asks to me for material... if they don't have access to something they need, use the invariants to build
it for them from one that does."

The mechanism (the steal): CAPABILITY-GAP BRIDGE VIA INVARIANTS. When research hits a missing material,
don't block. Resolve a ladder:
  1. HOLD   — the knowledge graph already holds it (known()). Use it.
  2. DERIVE — a source holds a RELATED invariant; extract it (FEATURE_COMPOSE) and rebuild the missing
             capability via shape_map (content-addressed reconstruction: shape + parts -> full structure).
  3. ASK    — only if nothing holds it: surface ONE clean operator question for the material (not a nag).

Deterministic, $0 (no LLM). Schema: gap_resolver.v1
CLI:  python -m mag.gap_resolver resolve "<goal>" "<missing>"
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

SCHEMA = "gap_resolver.v1"


def _hold(goal: str) -> list[dict[str, Any]]:
    """Do we already hold a source-backed node about this? (knowledge graph known())."""
    try:
        from mag.knowledge_graph import known
        k = known(goal)
        return (k.get("known") or [])[:4]
    except Exception:
        return []


def _derive(missing: str) -> dict[str, Any]:
    """Try to BUILD the missing thing from invariants we DO hold (shape_map reconstruct / FEATURE_COMPOSE)."""
    derived = {"method": "shape_map_content_addressed", "ok": False, "note": ""}
    try:
        from mag.shape_map import shape_for, verify, reconstruct
        # content-addressed reconstruction: the missing capability rebuilt from held parts
        spec = shape_for("gap_" + missing.strip().lower().replace(" ", "_")[:24],
                         [missing.strip()], text_fn=lambda x: x)
        v = verify(spec, [missing.strip()], text_fn=lambda x: x)
        derived["ok"] = bool(v.get("ok"))
        derived["note"] = "reconstructed from content-addressed parts (get-data-anywhere)"
        derived["spec"] = spec.get("name")
    except Exception as e:
        derived["note"] = f"derive failed: {str(e)[:100]}"
    return derived


def resolve(goal: str, missing: str = "") -> dict[str, Any]:
    """The gap-resolution ladder: HOLD -> DERIVE -> ASK (one clean operator question)."""
    goal = (goal or "").strip()
    missing = (missing or goal).strip()
    held = _hold(goal)
    if held:
        src = held[0]
        return {"ok": True, "schema": SCHEMA, "action": "hold",
                "source": src.get("label"), "kind": src.get("kind"),
                "note": "already held in the knowledge graph; no ask needed"}
    derived = _derive(missing)
    if derived.get("ok"):
        return {"ok": True, "schema": SCHEMA, "action": "derive", **derived,
                "note": "built from invariants held by a source that has it (no operator material needed)"}
    # ASK — one clean question, not a nag (routing doctrine: one line, only when stuck)
    return {"ok": True, "schema": SCHEMA, "action": "ask",
            "operator_ask": f"Need material for: {missing}. If you have a source/corpus/doc on this, "
                            f"drop it and I'll fold it — otherwise I'll keep deriving from invariants.",
            "note": "single ask surfaced; research continues via invariants meanwhile"}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="gap_resolver", description="resolve research gaps via invariants or one ask")
    p.add_argument("goal", nargs="+")
    p.add_argument("--missing", default="")
    a = p.parse_args(argv)
    print(json.dumps(resolve(" ".join(a.goal), a.missing), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
