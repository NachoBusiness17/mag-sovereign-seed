"""memweave — unify the swarm-as-shader stack into ONE memory-weaving mechanism.

Operator (2026-08-11): "this is memweave do it."

Memweave (verified 2026-08-10): N cheap pods run in PARALLEL, then flock-converge on consensus.
Parallelism beats latency; consensus beats single-judgment; feed STRUCTURES not prose to cheap
models. This module unifies the swarm-as-shader stack we built into one deterministic pipeline:

  decompose (bite-sized bits)        -> line_builder.plan (disjoint line ownership, conflict-free)
  run the flock (cheap per-pixel)    -> flock_shader.render + flock_grid.seams_spatial (O(N) seams)
  shade the seams (rightsize)        -> flock_shader.rightsize_spend / fold_gaps (escalate)
  build the file line-by-line        -> line_builder.build (each worker edits only its lines)
  render visual machine language     -> swarm_render.visual_language (the VRAM-readable register)
  fold to memory                     -> verkle fold + ledger (the weave persists)

Deterministic + $0 (all local pieces). Schema: memweave.v1
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "memweave.v1"
RUN_DIR = ROOT / "memory" / "runs" / "memweave"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decompose(goal: str, n_bits: int) -> list[str]:
    """Decompose a goal into bite-sized deterministic bits (the memweave task fan-out)."""
    n = max(1, int(n_bits))
    words = [w for w in (goal or "").split() if w]
    if not words:
        return [f"[bit {i}] <empty goal>"] * n
    # deterministic round-robin bucketing into n bite-sized slices
    buckets: list[list[str]] = [[] for _ in range(n)]
    for i, w in enumerate(words):
        buckets[i % n].append(w)
    return [f"[memweave bit {i}] {' '.join(b) if b else '(empty slice)'}" for i, b in enumerate(buckets)]


def weave(goal: str, *, n_workers: int = 4, cell_size: float = 1.0,
          iso_tau: float = 0.25, budget: float = 2.0,
          render: bool = True) -> dict[str, Any]:
    """One deterministic memweave run: decompose -> ownership -> flock+seams -> rightsize -> build
    -> visual language. Deterministic + $0 (all local; no LLM spend)."""
    from mag import line_builder as lb
    from mag.flock_shader import Uniforms, AgentSeed, launch, fold_gaps
    from mag import flock_grid as fg

    # 1) decompose the goal into bite-sized bits (the task fan-out)
    bits = decompose(goal, n_workers)

    # 2) build a deterministic 'file' skeleton from the bits = the lines each worker owns
    skeleton = "\n".join(bits)
    plan_doc = lb.plan(skeleton, n_workers)

    # 3) run the flock: agents seeded from each bit (cheap per-pixel) + O(N) spatial seams
    agents = [AgentSeed(id=i, pos=(float(i % 5), float(i % 3)),
                        role="worker", task=bits[i]) for i in range(n_workers)]
    positions = [a.pos for a in agents]
    seam_list = fg.seams_spatial(positions, cell_size=cell_size, iso_tau=iso_tau)

    # 4) rightsize + fold the seams (shade the seams, budget-gated)
    u = Uniforms(budget=budget)
    rightsized = launch(agents, u, dry=True)
    gap = fold_gaps([{"seed": s["index"], "deviation": (1.0 - s["nearest_d2"])
                      if s["nearest_d2"] is not None else 1.0} for s in seam_list
                     if s["isolated"]], budget=budget)

    # 5) render visual machine language (the VRAM-readable register)
    visual: dict[str, Any] = {}
    if render:
        from mag import swarm_render as sr
        vis_seams = [{"seed": s["index"], "deviation": 0.9} for s in seam_list if s["isolated"]]
        visual = sr.flock_image(agents, vis_seams, [])

    # 6) fold to memory (ledger + verkle)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _now(), "goal": goal[:120], "n_workers": n_workers,
           "n_bits": len(bits), "n_seams": len([s for s in seam_list if s["isolated"]]),
           "n_escalated": gap.get("n_escalated", 0), "visual": visual.get("image"),
           "ownership": plan_doc.get("ownership")}
    (RUN_DIR / "weaves.jsonl").open("a", encoding="utf-8").write(
        json.dumps(rec, default=str) + "\n")

    return {"ok": True, "schema": SCHEMA, "goal": goal[:120], "n_workers": n_workers,
            "bits": bits, "ownership": plan_doc.get("ownership"),
            "seams": [s for s in seam_list if s["isolated"]],
            "gap": {"n_escalated": gap.get("n_escalated", 0), "used": gap.get("used", 0)},
            "visual": visual, "recorded": str(RUN_DIR / "weaves.jsonl")}


# ── CONSENSUS-ILLUSION GUARD (steal 2026-08-11) ─────────────────────────────────
# Memweave's #1 documented risk (grok-4.5 critique): CONSENSUS ILLUSION — correlated hallucinations
# counted as agreement. The fix (self-steal from gap_swarm_experiment.independent_witnesses +
# external agentswarm evidenceOverlap): agreement is only REAL if the agreeing witnesses are
# INDEPENDENT. N correlated answers ~= 1 opinion, not N. This guard reports the effective
# independent witness count so the weave never trusts a correlated consensus as a strong one.

def _tok(s: str) -> set[str]:
    return set((s or "").lower().split())


def consensus_quality(answers: list[str], *, independent: list[bool] | None = None,
                      rho: float | None = None) -> dict[str, Any]:
    """Effective independent agreement across the flock's answers (consensus-illusion guard).

    RESEARCH FIX (OX_SYNTHESIS consensus_illusion_detection, 2026-08-23): agreement is only REAL
    if the agreeing witnesses are INDEPENDENT. The old guard counted witnesses purely by token-
    overlap, so it could NOT tell two INDEPENDENTLY-CONSTRUCTED verifiers that byte-agree (the
    STRONG case) from one correlated opinion (an illusion) — it under-reported strong consensus.

    `independent` (optional, per-answer bool) supplies the construction-independence signal the
    token-overlap check cannot see. When provided, a byte-identical answer from an independently-
    constructed witness counts as an ADDITIONAL independent witness (strong). When omitted, the
    behavior is unchanged (token-overlap only) — a flock of identical answers stays correlated.

    `rho` (optional, mean pairwise error correlation in [0,1)) supplies the MEASURED correlation
    between agreeing witnesses (OX burn t0416). When provided, it converts raw agreement into
    effective independent witnesses via the closed-form rule:
        n* = n / (1 + (n - 1) * rho)
    At rho=0.9, ten agents give n* ~= 1.17 — ten correlated "unanimous" agents are worth barely
    more than one opinion. This is the measured-not-guessed rule: agreement carries evidential
    weight only in proportion to error independence.

    Verdict: 'strong' if >=2 effective independent witnesses agree; 'correlated_weak' if they
    collapse toward one opinion; 'single' otherwise. Deterministic + $0.
    """
    n = len(answers or [])
    if n == 0:
        return {"ok": True, "schema": "memweave.consensus.v1", "n_answers": 0,
                "n_independent": 0, "n_effective": 0.0, "correlated": False, "verdict": "empty"}
    if independent is not None and len(independent) != n:
        raise ValueError("independent must be None or match len(answers)")
    if rho is not None:
        rho = float(rho)
        if not (0.0 <= rho < 1.0):
            raise ValueError("rho must be in [0,1)")
    # structural independent witnesses (token-overlap + explicit independence signal)
    wit: set[int] = set()
    for i in range(n):
        correlated = False
        ti = _tok(answers[i])
        for j in wit:
            tj = _tok(answers[j])
            if not ti or not tj:
                continue
            ov = len(ti & tj) / len(ti | tj)
            if ov >= 0.6:
                correlated = True
                break
        if not correlated:
            wit.add(i)
        elif independent is not None and independent[i]:
            # explicit independence signal: a byte-identical answer from an independently-
            # constructed witness is a NEW independent voice, not a correlated echo (the strong case)
            if any(answers[i] == answers[j] and independent[j] for j in wit):
                wit.add(i)
    n_ind = len(wit)
    # measured effective independent witnesses (correlation-adjusted), when rho is known
    if rho is not None:
        n_effective = n / (1 + (n - 1) * rho)
        eff = n_effective
    else:
        n_effective = float(n_ind)
        eff = n_ind
    verdict = ("strong" if eff >= 2 else
               "correlated_weak" if (eff < n and n >= 2) else
               "single")
    return {"ok": True, "schema": "memweave.consensus.v1", "n_answers": n,
            "n_independent": n_ind, "n_effective": round(n_effective, 4),
            "rho": rho, "correlated": n_ind < n, "verdict": verdict}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="memweave")
    ap.add_argument("goal", nargs="?", default="weave the swarm state into memory")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    print(json.dumps(weave(a.goal, n_workers=a.workers), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
