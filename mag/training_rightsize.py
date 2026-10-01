"""training_rightsize — apply the RIGHTSIZING lesson to TRAINING/STEAL.

RIGHTSIZING LESSON (the operator's sharpest one): "use the cheapest capable tier; the right
size algo should do this — forcing things is what gets us in trouble." Escalate only when the
task genuinely needs it.

Applied to TRAINING/STEAL, that means THREE right-sizings, not one:
  1. DATA right-size  — which examples are worth training on (quality + dedup = signal not
     noise). Don't feed the model garbage. data_refinery already does this.
  2. COMPUTE right-size — match the base model + method to the DATA VOLUME. A 660-1157 example
     set does NOT need a rented 7B; QLoRA a 1.5-2B locally is the right size. Rent bigger only
     when the data volume demands it.
  3. ESCALATE only when required — frontier distillation/rented GPU only when the task's
     fidelity genuinely requires it (anomaly path), not by default.

This module reuses one_sizer's tier logic and maps it onto the training decision, so training
spend follows the same cheap-first doctrine as inference. Schema: training_rightsize.v1
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "training_rightsize.v1"
TRAINING = ROOT / "memory" / "training" / "refined_training_data.jsonl"


def _n_examples() -> int:
    if not TRAINING.is_file():
        return 0
    return sum(1 for _ in TRAINING.open(encoding="utf-8", errors="replace"))


def _one_sizer_shape(goal: str = "") -> str:
    try:
        from mag.self_drive import plan as _plan
        return str(_plan(goal).get("model_shape") or "balanced")
    except Exception:
        return "balanced"


def decide(*, n_examples: int | None = None, goal: str = "train ghost adapter",
           force_local: bool = True) -> dict[str, Any]:
    """Right-size a training job: cheapest-capable (base model, method, hardware, budget)
    given the data volume + task shape. Reuses one_sizer's cheap-first tier logic."""
    n = n_examples if n_examples is not None else _n_examples()
    shape = _one_sizer_shape(goal)

    # COMPUTE right-size: base model + method scale WITH data volume (cheapest capable first)
    if n < 300:
        base, method, hardware, cost = "google/gemma-2-2b-it", "qlora_4bit", "local_gpu", 0.0
    elif n < 1500:
        base, method, hardware, cost = "Qwen/Qwen2.5-1.5B-Instruct", "qlora_4bit", "local_gpu", 0.0
    elif n < 5000:
        base, method, hardware, cost = "Qwen/Qwen2.5-3B-Instruct", "qlora_4bit", "rent_gpu", 0.50
    else:
        base, method, hardware, cost = "Qwen/Qwen2.5-7B-Instruct", "qlora_4bit", "rent_gpu", 0.80

    # ESCALATE only if the task genuinely demands frontier fidelity (anomaly path)
    escalate = False
    reason = ""
    low = goal.lower()
    if any(k in low for k in ("frontier", "deep", "7b", "high-fidelity", "max")):
        escalate = True
        reason = "task explicitly requests frontier-grade fidelity"

    # DATA right-size check: are we feeding signal (deduped/quality) or noise?
    data_ok = n > 0
    note = (f"{n} deduped/quality-filtered examples from data_refinery" if data_ok
            else "NO training data — run data_refinery first")

    return {"ok": True, "schema": SCHEMA, "n_examples": n, "task_shape": shape,
            "data": {"ok": data_ok, "note": note},
            "compute": {"base_model": base, "method": method, "hardware": hardware,
                        "est_cost_per_hr_usd": cost},
            "escalate": {"escalate": escalate, "reason": reason or "not needed — cheap-first"},
            "verdict": ("ESCALATE-RENT" if escalate and hardware == "rent_gpu"
                        else "LOCAL-QLORA" if hardware == "local_gpu" else "RENT-QLORA")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="training-rightsize")
    ap.add_argument("--goal", default="train ghost adapter")
    ap.add_argument("--n", type=int, default=None)
    args = ap.parse_args(argv)
    print(json.dumps(decide(goal=args.goal, n_examples=args.n), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
