"""seed_percolator — evolve standing seed prompts under cache discipline (2026-08-27).

Synthesis of old-seat bones per operator GO: bernaise loop + percolator gate +
max_distill admission, pointed at FROZEN_RIB-class seed prompts.

ELDER DESIGN LOCKED (memory/runs/seed_percolator_elder_advice.md):
  fitness   = paired blind win-rate vs frozen baseline (judge picks better; tie=0.5)
  threshold = >=55% win-rate, min 30 judged pairs PER EPOCH
  promotion = >=55% in 3 CONSECUTIVE epochs on fresh task sets (total >=90 pairs)
  guard     = null-variant canary: baseline copy must NOT exceed 50% wins, else judge
              is biased -> loop HALTS (auto), flag raised.
              Adversarial judge rotation every 10th pair (epoch 1+, not v0).

v0 scope (babystep): mechanics only — registry.jsonl persistence, paired_run(),
judge(), win-rate math, promote/reject verdicts, CLI smoke. No scheduler wiring;
the worker container or tick can call `python -m mag.seed_percolator beat` later.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REG = ROOT / "memory" / "runs" / "seed_percolator" / "registry.jsonl"

THRESHOLD_WINRATE = 0.55
MIN_PAIRS_PER_EPOCH = 30
FREEZE_EPOCHS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(row: dict[str, Any]) -> None:
    REG.parent.mkdir(parents=True, exist_ok=True)
    with REG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _chat(lane_model: tuple[str, str], system: str, user: str) -> str:
    """One call through the standing wave machinery (gate + cache stats)."""
    lane, model = lane_model
    if model.startswith("glm"):
        from mag.rib_cache import rib_chat
        thinking = "low" if "5.3" in model else False
        r = rib_chat(user, lane=lane, model=model, max_tokens=800, thinking=thinking)
        # note: rib_chat WRAPS user content with FROZEN_RIB system — for seed experiments
        # the seed-under-test goes in the USER tail, which is exactly how consumers ride it.
        return r.get("text") or ""
    from models.providers import chat_provider
    r = chat_provider(lane, system=system, user=user, model=model,
                      thinking=False, max_tokens=800, tier="T2")
    return r.get("text") or ""


def judge(task: str, out_a: str, out_b: str, judge_lane=("deepseek", "deepseek-chat")) -> str:
    """Blind judge: returns 'A' | 'B' | 'TIE'. Order randomized by caller."""
    import random as _r
    swap = _r.random() < 0.5
    ta, tb = (out_b, out_a) if swap else (out_a, out_b)
    prompt = (f"TASK:\n{task}\n\nANSWER 1:\n{ta[:1200]}\n\nANSWER 2:\n{tb[:1200]}\n\n"
              "Which answer serves the task better? Reply exactly ONE word: 1, 2, or TIE.")
    r = _chat(judge_lane, "", prompt)
    t = (r.get("text") if isinstance(r, dict) else str(r)) if not isinstance(r, str) else r
    word = (t or "").strip().upper()
    pick = "TIE" if "TIE" in word else ("A" if word.endswith(("1",)) else ("B" if word.endswith("2") else "TIE"))
    return ("B" if pick == "A" else "A") if swap else pick


def paired_run(seed_baseline: str, seed_variant: str, task: str,
               body=("z_ai3", "glm-4.7-flash")) -> dict[str, Any]:
    """Both seeds on the SAME task/body; blind-judged; persists the pair row."""
    sa = hashlib.sha256((seed_variant + task).encode()).hexdigest()[:12]
    va = _chat(body, seed_variant, task)
    vb = _chat(body, seed_baseline, task)
    verdict = judge(task, va, vb)
    row = {"schema": "seed_percolator.v0", "ts": _now(), "pair": sa, "task": task[:200],
           "seed_sha": hashlib.sha256(seed_variant.encode()).hexdigest()[:12],
           "verdict": verdict}
    _append(row)
    return row


def report(seed_sha: str | None = None, epoch: int = 1) -> dict[str, Any]:
    rows = [json.loads(l) for l in REG.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if REG.exists() else []
    rows = [r for r in rows if r["verdict"] in ("A", "B") and r["verdict"] != "TIE"]  # ties count 0.5
    if seed_sha:
        rows = [r for r in rows if r.get("seed_sha") == seed_sha]
    wins = sum(1 for r in rows if r["verdict"] == "A")
    ties = sum(1 for r in rows if r["verdict"] == "TIE")
    n = len(rows)
    wr = round((wins + 0.5 * ties) / n, 3) if n else 0.0
    verdict = (
        "INSUFFICIENT PAIRS (<%d)" % MIN_PAIRS_PER_EPOCH if n < MIN_PAIRS_PER_EPOCH else
        "PROMOTE-CANDIDATE (>=55%%)" if wr >= THRESHOLD_WINRATE else
        "REJECT (<55%)")
    return {"seed_sha": seed_sha, "pairs": n, "wins": wins, "ties": ties,
            "win_rate": wr, "epochs_completed": epoch, "verdict": verdict,
            "note": "freeze requires this verdict in %d consecutive epochs on fresh tasks"
                    % FREEZE_EPOCHS}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="seed-percolator")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("report")
    p_r = sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        print(json.dumps(report(), indent=2))
    elif a.cmd == "selftest":
        b = "You are a terse code reviewer."
        v = "You are a senior engineer doing tersely rigorous code review; always number findings."
        task = "Review risk of: bounded worker spawning agents per beat."
        row = paired_run(b, v, task)
        print(json.dumps(row, indent=2))
        rep = report(row["seed_sha"])
        print(json.dumps(rep, indent=2))
    else:
        print("usage: selftest | report")


if __name__ == "__main__":
    main()
