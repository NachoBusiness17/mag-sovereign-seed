"""signals — ONE shared, tunable signal model for the whole sovereign system.

STEAL (both, per standing directive):
  - SELF-STEAL: we already had scattered signal mechanisms — mycelium.salience (confidence /
    recency / refs / contradiction rails with weights), mine_diamonds (4-rail diamond signal),
    one_sizer (naive mode-vote tier choice), arena_learning (win_rate). This module consolidates
    the ONE model they all should share so "refine signals everywhere" means editing ONE file.
  - EXTERNAL STEAL (adapted to our deterministic, $0 shape):
      * Wilson score interval  — statistically sound LOWER-BOUND confidence for small-sample
        win rates (replaces the naive `ok_rate >= 0.7` threshold that over-trusts n=3).
      * UCB1 / Beta posterior  — exploration-exploitation + Bayesian confidence from
        successes/failures, so a move/tier/seat is trusted in proportion to evidence.
      * EWMA + half-life decay — smooth recency weighting (replaces hard recency cutoffs).

Every rail is normalized to [0,1], deterministic, no LLM, and all weights live in ONE dict
(SIGNALS) so the whole system's signal behavior is tunable from a single place.

Schema: signals.v1
"""
from __future__ import annotations

import math
from typing import Any, Iterable

SCHEMA = "signals.v1"

# ---------------------------------------------------------------------------
# One place to tune every signal rail in the system.
# ---------------------------------------------------------------------------
SIGNALS: dict[str, dict[str, float]] = {
    # Diamond/decision signal rails (base, convergence, recency, savings) — mine_diamonds.
    "diamond": {"base": 0.35, "convergence": 0.30, "recency": 0.20, "savings": 0.15},
    # Salience rails — mycelium (confidence, recency, refs-in, contradiction penalty).
    "salience": {"confidence": 0.45, "recency": 0.30, "refs": 0.15, "penalty": 0.20},
    # Proven-move gate.
    "proven_move": {"min_n": 3.0, "min_lower": 0.5, "z": 1.96},
    # Recency decay (half-life in seconds): 1 day for moves, 7 days for case law.
    "decay": {"move_half_life": 86400.0, "case_law_half_life": 604800.0},
}

W = SIGNALS["diamond"]


def wilson_lower(successes: float, n: float, *, z: float | None = None) -> float:
    """Wilson score interval LOWER bound — conservative confidence in a win rate.

    The naive `successes/n` over-trusts small samples (3/3 = 1.0 says "perfect"). Wilson
    shrinks toward 0.5 with low n, so a 3/3 (lower≈0.44) ranks below a 20/20 (lower≈0.86).
    This is THE fix for "refine signals": it stops tiny samples from looking like diamonds.
    """
    z = z if z is not None else SIGNALS["proven_move"]["z"]
    if n <= 0:
        return 0.0
    p = successes / n
    if n == 1:
        return 0.0
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return max(0.0, min(1.0, (center - margin) / denom))


def ucb1(wins: float, n: float, total: float, *, c: float = 1.0) -> float:
    """UCB1 upper-confidence exploration bonus (normalized)."""
    if n <= 0:
        return c
    mean = wins / n
    explore = c * math.sqrt(2.0 * math.log(max(1.0, total)) / n)
    return max(0.0, min(1.0, mean + explore))


def beta_score(successes: float, failures: float, *, a0: float = 1.0, b0: float = 1.0) -> float:
    """Beta posterior mean (Bayesian confidence): (a0+s) / (a0+b0+s+f).

    With a uniform prior this is just (1+s)/(2+s+f) — smoother than a raw rate and never
    returns 0 or 1 for a single observation. Cheap and deterministic.
    """
    return (a0 + successes) / (a0 + b0 + successes + failures) if (successes + failures) > 0 else a0 / (a0 + b0)


def recency_decay(age_seconds: float, *, half_life: float | None = None) -> float:
    """Exponential recency decay: 1.0 when fresh -> ~0 as age >> half_life.

    Self-stolen from mycelium's `0.7^gap` and made tunable via half-life. age<=0 => 1.0.
    """
    hl = half_life if half_life is not None else SIGNALS["decay"]["move_half_life"]
    if hl <= 0:
        return 1.0
    return math.pow(0.5, max(0.0, age_seconds) / hl)


def ewma_update(old: float, new: float, *, alpha: float = 0.3) -> float:
    """Exponential moving average update — smooth recency without a hard cutoff."""
    return alpha * new + (1.0 - alpha) * old


def normalize(x: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(0.0, min(1.0, (float(x) - lo) / (hi - lo) if hi > lo else 0.0))


def combine(rails: dict[str, float], *, weights: dict[str, float] | None = None) -> float:
    """Weighted sum of normalized rails; weights default to SIGNALS['diamond']."""
    w = weights or W
    total_w = sum(max(0.0, float(v)) for v in w.values()) or 1.0
    return round(
        sum(float(w.get(k, 0.0)) * normalize(rails.get(k, 0.0)) for k in w) / total_w,
        3,
    )


def proven_move(successes: int, n: int, *, min_n: int | None = None,
                min_lower: float | None = None) -> dict[str, Any]:
    """Statistically sound "is this a proven move?" gate.

    Replaces the naive `len>=3 and ok_rate>=0.7` (which called 3/3 a diamond). A move is
    proven only when its Wilson LOWER bound clears min_lower AND it has enough samples.
    Returns {proven, wilson_lower, n, win_rate, delta_to_gate}.
    """
    min_n = int(min_n if min_n is not None else SIGNALS["proven_move"]["min_n"])
    min_lower = min_lower if min_lower is not None else SIGNALS["proven_move"]["min_lower"]
    lower = wilson_lower(successes, n)
    win_rate = successes / n if n else 0.0
    return {
        "proven": bool(n >= min_n and lower >= min_lower),
        "wilson_lower": round(lower, 3),
        "n": int(n),
        "win_rate": round(win_rate, 3),
        "delta_to_gate": round(lower - min_lower, 3),
        "min_n": min_n,
        "min_lower": min_lower,
    }


def quantize_band(score: float) -> str:
    """Map a [0,1] signal to a coarse band — self-stolen from attention_ranker P1..P4."""
    if score >= 0.72:
        return "P1"
    if score >= 0.52:
        return "P2"
    if score >= 0.32:
        return "P3"
    return "P4"


def stats() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "signals": SIGNALS,
            "proven_move_examples": {
                "3_of_3": proven_move(3, 3),
                "5_of_5": proven_move(5, 5),
                "20_of_20": proven_move(20, 20),
                "2_of_2": proven_move(2, 2),
                "7_of_10": proven_move(7, 10),
            }}


if __name__ == "__main__":
    import json
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(json.dumps(stats(), indent=2, default=str))
