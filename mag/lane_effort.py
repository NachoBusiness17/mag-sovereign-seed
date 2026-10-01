"""Lane effort tiers -- Anthropic effort-scaling budgets by fan-out width.

Fold row: corpus/steal/MASTER_MICKEY17_V2_20260924.md top-steal #6
[lane: anthropic-multiagent, owed]. Closes watch/inbox/mickey/G4_4_wiring.md:38
"effort budgets as first-class lane parameter -- BUILD".

Source (quoted verbatim in the fold row, anthropic.com/engineering/multi-agent-research-system):
  "Simple fact-finding requires just 1 agent with 3-10 tool calls, direct
   comparisons might need 2-4 subagents with 10-15 calls each, and complex
   research might use more than 10 subagents with clearly divided responsibilities."

Three tiers, verbatim:
  T1 fact_finding : 1 lane,        3-10 calls   (scope: total for the lane)
  T2 comparison   : 2-4 lanes,     10-15 calls  (scope: per lane)
  T3 complex      : >10 lanes      (scope: gate-governed; the source gives no call count)

Named failure mode (fold row #6 action): overinvestment in simple queries --
paying T2/T3 effort for a T1 task. effort_for_width() therefore snaps
conservatively: widths 5-10 lie between the measured bands (source is silent),
so they fall DOWN to T2's per-lane budget rather than up to uncapped T3.
The value-per-token gate, not the tier, owns any widening.

Value gate grounding (fold row preamble): Anthropic runs multi-agent research
"with a ~15x token premium explicitly gated on task value". The gate encodes
that: a fan-out wider than 1 lane must clear 15x the single-lane value-per-token
bar before it is admitted.

This module is pure: no network, no file I/O on the decision path. It extends
the lane config family (mag/lanes.py + configs/lanes.yaml) with effort budgets;
it does not duplicate lanes.py. Operator dials (baseline_vpt, premium,
per-tier call overrides) may live under `effort_tiers:` in configs/lanes.yaml;
absent overrides the verbatim defaults above hold.

Schema: lane_effort.v1
"""
from __future__ import annotations

from typing import Any

SCHEMA = "lane_effort.v1"

# --- The three tiers, verbatim bands -----------------------------------------
# provenance: verbatim=True -> the number is in the source quote.
#             verbatim=False -> extrapolation, reason named in `note`.
EFFORT_TIERS: dict[str, dict[str, Any]] = {
    "fact_finding": {
        "tier": 1,
        "label": "simple fact-finding",
        "min_lanes": 1,
        "max_lanes": 1,
        "min_calls": 3,
        "max_calls": 10,
        "calls_scope": "total",  # "1 agent with 3-10 tool calls" -- one lane total
        "verbatim": True,
        "note": "",
    },
    "comparison": {
        "tier": 2,
        "label": "direct comparison",
        "min_lanes": 2,
        "max_lanes": 4,
        "min_calls": 10,
        "max_calls": 15,
        "calls_scope": "per_lane",  # "10-15 calls each" -- per subagent
        "verbatim": True,
        "note": "",
    },
    "complex": {
        "tier": 3,
        "label": "complex research",
        "min_lanes": 11,  # ">10 subagents" -> smallest qualifying width is 11
        "max_lanes": None,
        # Source gives no call count for complex research. Floor = T2's measured
        # band (a complex lane should not get fewer calls than a comparison
        # lane); ceiling = None (gate-governed, not tier-capped).
        "min_calls": 15,
        "max_calls": None,
        "calls_scope": "per_lane_floor",  # min per lane, no tier ceiling
        "verbatim": False,
        "note": "lanes verbatim (>10); call floor extrapolated from T2's measured band; source silent on complex call counts",
    },
}

# Widths 5-10 fall between the source's measured bands (2-4 and >10). They snap
# down to T2's per-lane budget: measured where possible, conservative where not.
WIDTH_GAP_SNAP = "comparison"

# --- Value-per-token gate dials ----------------------------------------------
# Fold row preamble: "~15x token premium explicitly gated on task value".
MULTIAGENT_TOKEN_PREMIUM = 15.0  # applies to any fan-out wider than 1 lane
DEFAULT_BASELINE_VPT = 1.0       # baseline value units per 1k tokens, 1 lane


def _lane_config() -> dict[str, Any]:
    """Operator overrides from configs/lanes.yaml `effort_tiers:` block, if any."""
    try:
        from mag.lanes import load_lanes

        cfg = load_lanes().get("effort_tiers")
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def tier_config(name: str) -> dict[str, Any]:
    """A tier's effective config: module defaults merged with yaml overrides."""
    base = dict(EFFORT_TIERS[name])
    over = _lane_config().get("tiers")
    if isinstance(over, dict) and isinstance(over.get(name), dict):
        base.update(over[name])
    return base


def effort_for_width(width: int | None) -> dict[str, Any]:
    """Map a fan-out width to its effort tier. Deterministic, no I/O.

    width <= 1  -> fact_finding (verbatim)
    width 2-4   -> comparison   (verbatim)
    width 5-10  -> comparison, snapped (source silent; conservative snap-down)
    width >= 11 -> complex      (verbatim ">10 lanes")
    """
    try:
        w = int(width)
    except (TypeError, ValueError):
        w = 1
    w = max(1, w)
    t1_max = int(tier_config("fact_finding")["max_lanes"])
    t2_max = int(tier_config("comparison")["max_lanes"])
    if w <= t1_max:
        name = "fact_finding"
        snapped = False
    elif w <= t2_max:
        name = "comparison"
        snapped = False
    elif w < EFFORT_TIERS["complex"]["min_lanes"]:
        name = WIDTH_GAP_SNAP
        snapped = True
    else:
        name = "complex"
        snapped = False
    cfg = tier_config(name)
    return {
        "schema": SCHEMA,
        "tier": name,
        "tier_no": cfg["tier"],
        "width": w,
        "min_calls": cfg["min_calls"],
        "max_calls": cfg["max_calls"],
        "calls_scope": cfg["calls_scope"],
        "verbatim": bool(cfg["verbatim"]) and not snapped,
        "snapped": snapped,
        "note": cfg.get("note", "")
        + (" width 5-10 lies between the source's measured bands; snapped down to comparison's per-lane budget" if snapped else ""),
    }


def call_budget_for_width(width: int | None) -> tuple[int, int | None]:
    """(min_calls, max_calls) for a fan-out width. max_calls None = gate-governed."""
    e = effort_for_width(width)
    return int(e["min_calls"]), (None if e["max_calls"] is None else int(e["max_calls"]))


def value_token_gate(
    *,
    value: float,
    tokens: float,
    width: int = 1,
    baseline_vpt: float | None = None,
    multiagent_premium: float | None = None,
) -> dict[str, Any]:
    """Value-per-token admission gate for a lane fan-out.

    Admits when the fan-out's value density clears a premium-scaled bar:

        value_per_1k_tokens = value / (tokens / 1000)
        required            = baseline_vpt * premium
        premium             = 1.0 for width <= 1 (the single-agent baseline)
                              MULTIAGENT_TOKEN_PREMIUM (15x) otherwise, per the
                              fold row: "~15x token premium ... gated on task value"

    `value` is on the caller's own scale (priority-weighted utility, expected
    yield, whatever the runner scores); `tokens` is the estimated total token
    cost of the whole fan-out. Boundary equality admits (>=). Nonpositive value
    or token estimates are rejected outright: no free rides, no unestimated
    fan-outs. Pure and deterministic; the caller logs via mag.lanes.log_usage.
    """
    cfg = _lane_config()
    base = float(baseline_vpt if baseline_vpt is not None else cfg.get("baseline_vpt", DEFAULT_BASELINE_VPT))
    premium_dial = float(
        multiagent_premium if multiagent_premium is not None else cfg.get("multiagent_premium", MULTIAGENT_TOKEN_PREMIUM)
    )
    try:
        w = max(1, int(width))
    except (TypeError, ValueError):
        w = 1
    premium = 1.0 if w <= 1 else max(1.0, premium_dial)
    required = base * premium

    v = float(value or 0.0)
    t = float(tokens or 0.0)
    if v <= 0:
        return _gate_result(False, 0.0, required, base, premium, w, "rejected: nonpositive value estimate")
    if t <= 0:
        return _gate_result(False, 0.0, required, base, premium, w, "rejected: nonpositive token estimate")
    vpt = v / (t / 1000.0)
    if vpt >= required:
        why = "admitted: %.4g value/1k tokens >= required %.4g (premium %gx)" % (vpt, required, premium)
        return _gate_result(True, vpt, required, base, premium, w, why)
    why = "rejected: %.4g value/1k tokens < required %.4g (premium %gx)" % (vpt, required, premium)
    return _gate_result(False, vpt, required, base, premium, w, why)


def _gate_result(
    admitted: bool,
    vpt: float,
    required: float,
    base: float,
    premium: float,
    width: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "admitted": admitted,
        "value_per_1k_tokens": round(vpt, 6),
        "required_vpt": round(required, 6),
        "baseline_vpt": base,
        "premium": premium,
        "width": width,
        "reason": reason,
    }


def fanout_gate(
    *,
    width: int,
    value: float,
    tokens: float,
    baseline_vpt: float | None = None,
) -> dict[str, Any]:
    """One-call entrypoint for fan-out runners: tier budget + admission verdict.

    Combines effort_for_width(width) with value_token_gate(value, tokens, width)
    so a pack builder (mag/fanout.py) can budget lanes and gate the spend in one
    deterministic step.
    """
    effort = effort_for_width(width)
    gate = value_token_gate(
        value=value, tokens=tokens, width=effort["width"], baseline_vpt=baseline_vpt
    )
    return {
        "schema": SCHEMA,
        "width": effort["width"],
        "tier": effort["tier"],
        "tier_no": effort["tier_no"],
        "budget": {
            "min_calls": effort["min_calls"],
            "max_calls": effort["max_calls"],
            "calls_scope": effort["calls_scope"],
        },
        "verbatim": effort["verbatim"],
        "snapped": effort["snapped"],
        "admitted": gate["admitted"],
        "value_per_1k_tokens": gate["value_per_1k_tokens"],
        "required_vpt": gate["required_vpt"],
        "reason": gate["reason"],
        "note": effort["note"],
    }


def selftest() -> bool:
    """Run all checks; return True iff every one passes. Also runnable as a script."""
    checks: list[tuple[str, bool]] = []

    def ck(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    # 1. Three tiers, verbatim bands.
    ck("three tiers exist", list(EFFORT_TIERS) == ["fact_finding", "comparison", "complex"])
    t1, t2, t3 = (EFFORT_TIERS[k] for k in EFFORT_TIERS)
    ck("T1 verbatim: 1 lane, 3-10 calls total",
       t1["min_lanes"] == 1 and t1["max_lanes"] == 1 and (t1["min_calls"], t1["max_calls"]) == (3, 10)
       and t1["calls_scope"] == "total" and t1["verbatim"])
    ck("T2 verbatim: 2-4 lanes, 10-15 calls each",
       (t2["min_lanes"], t2["max_lanes"]) == (2, 4) and (t2["min_calls"], t2["max_calls"]) == (10, 15)
       and t2["calls_scope"] == "per_lane" and t2["verbatim"])
    ck("T3 lanes verbatim >10; calls gate-governed (source silent)",
       t3["min_lanes"] == 11 and t3["max_lanes"] is None and t3["max_calls"] is None
       and not t3["verbatim"] and "source silent" in t3["note"])

    # 2. effort_for_width mapping.
    for w, want, snap in [(1, "fact_finding", False), (2, "comparison", False), (4, "comparison", False),
                          (5, "comparison", True), (10, "comparison", True), (11, "complex", False),
                          (25, "complex", False), (0, "fact_finding", False), (None, "fact_finding", False)]:
        got = effort_for_width(w)
        ck(f"width {w} -> {want} (snapped={snap})",
           got["tier"] == want and got["snapped"] == snap)

    # 3. Budgets follow the tiers.
    ck("width 1 budget 3-10 total", call_budget_for_width(1) == (3, 10))
    ck("width 3 budget 10-15 per lane", call_budget_for_width(3) == (10, 15))
    ck("width 7 snaps to comparison budget", call_budget_for_width(7) == (10, 15))
    ck("width 12 floor 15, ceiling None (gate-governed)", call_budget_for_width(12) == (15, None))

    # 4. Gate: single-lane baseline (premium 1x, default bar 1.0 per 1k tokens).
    g = value_token_gate(value=20, tokens=1000, width=1)
    ck("single lane admits above baseline", g["admitted"] and g["premium"] == 1.0)
    g = value_token_gate(value=0.5, tokens=1000, width=1)
    ck("single lane rejects below baseline", not g["admitted"] and abs(g["value_per_1k_tokens"] - 0.5) < 1e-9)
    g = value_token_gate(value=1.0, tokens=1000, width=1)
    ck("boundary equality admits", g["admitted"])

    # 5. Gate: multi-lane 15x premium (fold row: ~15x token premium gated on value).
    for w in (2, 4, 7, 12):
        g = value_token_gate(value=10, tokens=1000, width=w)
        ck(f"width {w} rejects at 10 < 15x1.0", not g["admitted"] and g["premium"] == 15.0)
        g = value_token_gate(value=20, tokens=1000, width=w)
        ck(f"width {w} admits at 20 >= 15x1.0", g["admitted"])

    # 6. Guards: no free rides, no unestimated fan-outs.
    ck("value 0 rejected", not value_token_gate(value=0, tokens=1000, width=3)["admitted"])
    ck("tokens 0 rejected", not value_token_gate(value=100, tokens=0, width=3)["admitted"])
    ck("negative value rejected", not value_token_gate(value=-5, tokens=1000, width=3)["admitted"])

    # 7. Dials are honored.
    g = value_token_gate(value=10, tokens=1000, width=4, baseline_vpt=0.5)
    ck("baseline_vpt dial lowers the bar (10 >= 0.5*15)", g["admitted"])
    g = value_token_gate(value=10, tokens=1000, width=4, multiagent_premium=2.0)
    ck("premium dial honored (10 >= 1.0*2)", g["admitted"] and g["premium"] == 2.0)

    # 8. One-call fanout_gate integration.
    r = fanout_gate(width=3, value=30, tokens=1000)
    ck("fanout_gate: T2, budget 10-15 per lane, admitted",
       r["tier"] == "comparison" and r["budget"] == {"min_calls": 10, "max_calls": 15, "calls_scope": "per_lane"}
       and r["admitted"])
    r = fanout_gate(width=1, value=0.1, tokens=1000)
    ck("fanout_gate: cheap single-lane probe still budgeted 3-10 but not admitted",
       r["tier"] == "fact_finding" and r["budget"]["min_calls"] == 3 and not r["admitted"])

    # 9. yaml override surface reads without crashing (contents are operator's).
    cfg = _lane_config()
    ck("effort_tiers override surface is a dict or absent", isinstance(cfg, dict) or cfg == {})

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS" if ok else "FAIL") + "  " + n)
    print("%d/%d checks passed" % (len(checks) - len(failed), len(checks)))
    return not failed


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    ok = selftest()
    sys.exit(0 if ok else 1)
