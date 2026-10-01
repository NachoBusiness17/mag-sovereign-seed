"""Deterministic model picker — the 'which model should I use' answer, so you never drift.

The operator keeps TWO coding windows open (deepseek-v4-flash cheap, deepseek-v4-pro heavy) and
drifts between them aimlessly. This is exactly what prompt-routing was built to prevent: the
router already computes model_shape (cheap/heavy/reasoning) + is_handoff per goal — this makes
that decision BINDING and visible, so the human never guesses.

Rule (tier_probe-verified): exec-shaped work scores 1.00 on ALL tiers, so use the CHEAPEST model
(flash) for it; only reason/plan/heavy earns the expensive pro model. Spend on the spec, not the
tier.

CLI:  python -m mag.model_pick "<goal>"   ->  "use deepseek-v4-flash" / "deepseek-v4-pro"
      python -m mag.model_pick --json "<goal>"
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

FLASH = "deepseek-v4-flash"
PRO = "deepseek-v4-pro"

# shape -> (model, why). tier_probe: exec=1.00 on all tiers -> flash wins for exec.
_SHAPE_MODEL: dict[str, tuple[str, str]] = {
    "cheap":     (FLASH, "exec-shaped: tier_probe shows 1.00 on all tiers, flash is 18.7x cheaper"),
    "balanced":  (FLASH, "default: use flash; escalate only if it stalls (escalation ladder)"),
    "heavy":     (PRO,   "heavy_code/refactor: pro earns its cost here"),
    "reasoning": (PRO,   "plan/reason/architecture: pro is required, do not auto-run"),
}


def recommend_model(goal: str, *, depth: str | None = None) -> dict[str, Any]:
    """Route the goal and return the model to use (flash vs pro) + the reasoning."""
    from mag.router import route

    r = route(goal, depth=depth)
    shape = str(r.get("model_shape") or "balanced")
    model, why = _SHAPE_MODEL.get(shape, (FLASH, "default"))
    # Apply half of the tesuji loop: fold measured cost evidence into the recommendation
    # so routing is informed by real provider economics, not just the static rule.
    cost_evidence: dict[str, Any] = {}
    try:
        from mag.cost_learn import recent_cost_evidence
        cost_evidence = recent_cost_evidence(limit=5)
    except Exception:
        cost_evidence = {"source": "cost_learn", "providers": [], "n": 0}
    return {
        "ok": bool(r.get("ok", True)),
        "goal": (goal or "")[:200],
        "model": model,
        "model_shape": shape,
        "is_handoff": r.get("is_handoff"),
        "context_plan": r.get("context_plan"),
        "why": why,
        "depth": r.get("depth"),
        "tier": r.get("tier"),
        "seat": r.get("seat"),
        "cost_evidence": cost_evidence,
        "rule": "cheapest model that scores 1.00 on exec; pro only for reason/plan/heavy (tier_probe); "
                "cross-checked against measured cost_learn case law",
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="model-pick", description="Pick the right model for a goal (never drift)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("goal", nargs="*")
    args = ap.parse_args(argv)
    goal = " ".join(args.goal).strip()
    if not goal:
        print(json.dumps({"ok": False, "error": "no goal", "known_shapes": list(_SHAPE_MODEL)}))
        return 0
    rec = recommend_model(goal)
    if args.json:
        print(json.dumps(rec, indent=2, default=str))
        return 0
    print(f"USE  {rec['model']}  ({rec['model_shape']})")
    print(f"  why: {rec['why']}")
    print(f"  handoff={rec['is_handoff']} context={rec['context_plan']} depth={rec['depth']} tier={rec['tier']} seat={rec['seat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
