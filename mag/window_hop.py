"""window_hop — hop a long task through fresh call windows to exploit context length cheaply.

Grounding (context engineering for long-horizon agents, Anthropic 2025-09-29):
  - "context rot": as tokens in the window grow, recall degrades — context is a finite
    attention budget with diminishing marginal returns. Waiting for bigger windows is not
    the fix; compaction + structured note-taking + sub-agents are.
  - Compaction: summarize a near-full window, reinitiate a NEW window with the summary.
  - Structured note-taking (agentic memory): persist notes OUTSIDE the window, pull them
    back later. This is exactly our verkle knots / RIB handoffs / corpus-sync.

How this becomes a RIGHTSIZING lever (the one_sizer + cache economics):
  - DeepSeek cache: hit $0.0028/M, miss $0.14/M (50x), out $0.28/M (cache_map.MODEL_RATES).
  - Cache hits require a BYTE-STABLE prefix. A naive growing single context eventually
    invalidates / rot-s; a hopped run keeps a stable prefix (system + invariant + distilled
    note) and only appends the new delta — so every reused token bills at cache-HIT.
  - Because each hop's window is BOUNDED (small, high-signal, cache-friendly), one_sizer can
    keep the CHEAPEST-CAPABLE tier for arbitrarily long tasks: task length no longer forces a
    bigger tier. Length is decoupled from tier cost.

Model (per hop i): window = STABLE prefix + distilled note_{i-1} + delta_i
  - hop 1:      miss = stable + delta_1 ; out = out_1
  - hop i (>=2): hit = stable + note_{i-1} ; miss = delta_i ; out = out_i
Naive: one growing window, every token billed at MISS once (no byte-stable reuse) and
eventually exceeds the window.

Schema: window_hop.v1 · deterministic $0 · CLI: python -m mag.window_hop plan --segs ...
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from mag.cache_map import MODEL_RATES
except Exception:
    MODEL_RATES = {}

RATE = MODEL_RATES.get("deepseek-v4-flash") or {"hit": 0.0028, "miss": 0.14, "out": 0.28}

SCHEMA = "window_hop.v1"


@dataclass
class Seg:
    """One hop segment of a long task."""
    name: str
    delta_tokens: int   # fresh working tokens this hop (drawn/read, miss-charged)
    out_tokens: int     # output tokens this hop (work + distilled note)


def _usd(tokens: int, rate: float) -> float:
    return tokens / 1e6 * rate


def plan(*, stable_prefix_tokens: int, note_tokens: int, segs: list[Seg]) -> dict[str, Any]:
    """Price window-hopping vs a naive single growing context under real cache rates."""
    # HOPPED
    hop_costs = []
    for i, s in enumerate(segs):
        if i == 0:
            hit, miss, out = 0, stable_prefix_tokens + s.delta_tokens, s.out_tokens
        else:
            hit, miss, out = stable_prefix_tokens + note_tokens, s.delta_tokens, s.out_tokens
        c = _usd(hit, RATE["hit"]) + _usd(miss, RATE["miss"]) + _usd(out, RATE["out"])
        hop_costs.append({"hop": i + 1, "seg": s.name, "hit_tok": hit, "miss_tok": miss,
                          "out_tok": out, "cost_usd": round(c, 6)})
    hopped_total = round(sum(h["cost_usd"] for h in hop_costs), 6)
    hopped_in_total = sum(h["hit_tok"] + h["miss_tok"] for h in hop_costs)
    hopped_hit_ratio = round(sum(h["hit_tok"] for h in hop_costs) / max(1, hopped_in_total), 4)

    # NAIVE: one growing window, all input billed at miss once; note re-read each time as miss
    naive_in = stable_prefix_tokens + sum(s.delta_tokens for s in segs)
    # in the naive one-context view, the accumulated notes are part of the growing input (miss)
    naive_in += note_tokens * (len(segs) - 1)
    naive_out = sum(s.out_tokens for s in segs)
    naive_cost = round(_usd(naive_in, RATE["miss"]) + _usd(naive_out, RATE["out"]), 6)

    savings = round(naive_cost - hopped_total, 6)
    savings_x = round(naive_cost / max(1e-9, hopped_total), 2)

    max_naive_window = naive_in
    max_hop_window = stable_prefix_tokens + note_tokens + max(s.delta_tokens for s in segs)

    return {
        "ok": True, "schema": SCHEMA,
        "rates": {"hit": RATE["hit"], "miss": RATE["miss"], "out": RATE["out"]},
        "hops": hop_costs,
        "hopped": {"total_usd": hopped_total, "input_hit_ratio": hopped_hit_ratio},
        "naive": {"total_usd": naive_cost, "input_tokens": naive_in, "max_window": max_naive_window},
        "rightsizing": {
            "savings_usd": savings, "savings_x": savings_x,
            "max_hop_window": max_hop_window, "max_naive_window": max_naive_window,
            "bounded": max_hop_window < max_naive_window,
            "note": ("Because each hop's window is bounded + its reused prefix bills at cache-HIT, "
                     "one_sizer can hold the CHEAPEST-CAPABLE tier for arbitrarily long tasks: "
                     "length no longer forces a bigger tier."),
        },
    }


def main(argv: list[str] | None = None) -> int:
    import argparse, json, sys as _sys
    p = argparse.ArgumentParser(prog="window_hop")
    p.add_argument("--stable", type=int, default=4000, help="stable system/invariant prefix tokens")
    p.add_argument("--note", type=int, default=1500, help="distilled note tokens per hop")
    p.add_argument("--segs", type=int, default=10, help="number of hops")
    p.add_argument("--delta", type=int, default=8000, help="delta tokens per hop")
    p.add_argument("--out", type=int, default=1200, help="output tokens per hop")
    a = p.parse_args(argv)
    segs = [Seg(f"seg{i+1}", a.delta, a.out) for i in range(a.segs)]
    print(json.dumps(plan(stable_prefix_tokens=a.stable, note_tokens=a.note, segs=segs),
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
