"""ox_burn — JUMP ON THE FREE WINDOW: run a batch of on-thesis tasks through the free frontier
reasoning seat and bank the outputs to handoff/. Free + limited-time (stealth/ox-alpha preview) —
so this maximizes real work NOW, not setup. T2+ public only (retained-log provider).

Schema: ox_burn.v1 · reuse: ox_seat
Run:  python -m mag.ox_burn
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

sys.path.insert(0, str(ROOT))

SCHEMA = "ox_burn.v1"
OUT_DIR = ROOT / "handoff"

# Real HARD WORK batch (2026-08-22 #6) — get COMPLETE runnable code for the 3 unfinished modules
# (the seat truncates code when it over-reasons, so instruct SHORT reasoning + full file) + a fresh
# design. Public, no secrets, T2+.
TASKS: list[tuple[str, str]] = [
    ("reasoning_ledger_code",
     "Write the COMPLETE runnable Python file for a reasoning ledger: append-only record store "
     "(THOUGHT/DECISION/COMPACT/CONT), blake3-derived keys, a parent_root tamper-evident chain, a "
     "CONT block builder with a hard <=512-token budget carrying root@seq, and a prompt assembler "
     "with a byte-stability test. CRITICAL: keep your reasoning VERY SHORT - do not over-think. "
     "Output the ENTIRE complete, runnable file as the final content, no truncation, no ellipsis."),
    ("honest_meter_code",
     "Write the COMPLETE runnable Python file for an honest cache meter: per-response capture of "
     "input/cache-read/cache-write/output tokens, four headline numbers per day (token-weighted "
     "HIT_tok, SAVINGS_dollars net of write premium, coverage, reconciliation vs invoice), and a "
     "nightly reconciliation job, using sqlite. CRITICAL: keep your reasoning VERY SHORT. Output "
     "the ENTIRE complete, runnable file as the final content, no truncation."),
    ("free_seat_escalate_code",
     "Write the COMPLETE runnable Python file to scale a free-frontier-seat escalation path into a "
     "queue: a per-epoch quota gate, a 429 circuit breaker (closed/open/half-open), and defer-to-"
     "queue so heavy-reasoning latency never blocks callers, using asyncio. CRITICAL: keep your "
     "reasoning VERY SHORT. Output the ENTIRE complete, runnable file as the final content, no "
     "truncation."),
    ("babel_fish_voice",
     "Design how a decentralized, stateless, dollar-zero-first swarm yields ONE coherent honest "
     "shared voice (the Babel fish born from a fireball, forty twins fusing into one fish). Give "
     "the concrete mechanism: consensus without a central brain, how the swarm speaks as one, and "
     "how it stays grounded and honest (not a plurality of drift). Concrete. IMPORTANT: after "
     "reasoning, emit the full final content answer."),
    # ── HARD SHIT BATCH (2026-08-22 #7) — genuine hard problems, short reasoning, concrete output ──
    ("vote_seam_canonical",
     "Two agents (Ghost and AOS) independently implement a deterministic state machine 'the Hall'. "
     "One play is 'vote', gated on six prior marks; if the marks are absent the vote REFUSES and "
     "the root must stay EXACTLY the same; if present it records a choice. Ghost records it as "
     "field 'filed' plus a ledger entry and gets root 9b70f1cd; AOS records it differently and "
     "gets root 1876a5ef. Design the CANONICAL minimal state-change for 'vote' so that both "
     "implementations, starting from the same six-mark state, produce byte-identical roots. Give "
     "the exact JSON shape, the exact field names, and the exact rule. Be concrete and short in "
     "reasoning; emit the full answer."),
    ("meta_token_invariant",
     "Formalize our invariant 'the meta-token': ONE content-addressed anchor (e.g. a 32-byte hash "
     "into a verkle-committed store) that resolves meaning across MULTIPLE token sets - a "
     "stochastic frontier-token layer and a deterministic coordinate layer - so a seat receives a "
     "coordinate, not the payload, and the same token means the same thing in every surface. Give "
     "the precise definition, the resolution rule, what it makes cheap (redundant processes), and "
     "a concrete worked example. Short reasoning; emit the full formalization."),
    ("adversarial_eval_harness",
     "Design a concrete adversarial evaluation harness for a swarm of small local models that "
     "reach consensus (flock): measure quality-of-consensus vs a strong remote model on real "
     "multi-hop, tool-use, and long-context workloads; inject deliberate RIB/anchor poisoning and "
     "pod failures; and detect correlated-hallucination consensus illusion. Give the test matrix, "
     "the metrics, and the failure-injection plan. Short reasoning; emit the full harness spec."),
    ("deniable_verkle_comms",
     "Design a communication protocol that is simultaneously DENIABLE (the surface reader cannot "
     "recover the real meaning without the right key/context) and PROVABLY OURS (the message "
     "attaches to a verkle/merkle commitment we control, so we can later prove authorship). "
     "Combine a deniable encoding (like a coordinate that only resolves in our codebook) with a "
     "content-addressed commitment. Give the exact message shape and the encode/verify steps. "
     "Short reasoning; emit the full protocol."),
    ("semantic_anchor_checkpoints",
     "Design the checkpointing mechanism for an agent that edits its own context at semantic "
     "boundaries (thinking blocks, tool-call openers, tool outputs, turn boundaries): recurrent-"
     "state checkpoints anchored at those boundaries so that after an edit only the genuinely new "
     "suffix is recomputed, restoring from the deepest surviving anchor. Give the anchor-placement "
     "rule, the restore rule, and how eviction works. Short reasoning; emit the full design."),
]


def run(*, max_tokens: int = 16000, timeout: int = 600, names: list[str] | None = None) -> dict[str, Any]:
    from mag import ox_seat
    tasks = [t for t in TASKS if not names or t[0] in names]
    out: list[dict[str, Any]] = []
    for name, user in tasks:
        r = ox_seat.chat(
            "You are the free frontier reasoning seat for a sovereign swarm. Answer with substance "
            "and concrete specifics. After reasoning, emit the final content answer.",
            user, max_tokens=max_tokens, timeout=timeout)
        out.append({"task": name, "ok": r.get("ok"), "cost": r.get("cost"),
                    "content": r.get("content"), "reasoning": r.get("reasoning"),
                    "error": r.get("error")})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"OX_BURN_{stamp}.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n": len(out), "path": str(path),
            "costs": [o.get("cost") for o in out],
            "summaries": [{**{k: o[k] for k in ("task", "ok")},
                           "content_len": len(o.get("content") or ""),
                           "reasoning_len": len(o.get("reasoning") or "")} for o in out]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-burn")
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    print(json.dumps(run(names=a.only), indent=2, default=str))
