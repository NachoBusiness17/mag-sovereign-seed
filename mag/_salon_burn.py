"""SALON BURN — 4 witnesses × 4 current-end questions, fired in parallel (2026-08-27).

Operator: full burn of ChatGPT + Grok×2 refreshes "as to our current ends... salon/gap
analysis and combined research." Elder (deepseek) rides as 4th witness free.

Witnesses: codex (OpenAI) · grok/nacho · grok/sd · deepseek (elder)
Outputs:   memory/runs/salon_20260827/<witness>.md  (one file per witness)
Combine:   python -m mag._salon_burn combine  (elder roshomon pass, free lane)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "memory" / "runs" / "salon_20260827"

CONTEXT = """Fleet context (verified receipts, terse): a sovereign agent fleet runs on
cache-mined API lanes (frozen byte-stable system prefixes, 90-99% hit rates), a signed
append-only hash chain as memory (6500+ knots), MCP tools as shared hands, a 10-min
always-on witness agent (tick), containerized worker draining a job queue, and an
elder advisor (DeepSeek) for judgment. Plans in flight: (a) a render-manager router
that fans out N cheap model calls and routes by live $-per-verified-task from its own
usage ledger; (b) seed_percolator: evolving the standing system prompt via paired
blind win-rate vs baseline, 55% threshold, 3 epochs to freeze; (c) migrating to a
rented GPU box running a local 180B MoE (n-gram table paged from NVMe) as judgment
lane; (d) goal: a self-sustaining agent ecosystem whose every job mints a
proof-of-cost receipt (internal economy)."""

QUESTIONS = """Answer ALL FOUR, numbered, 3-5 lines each, terse, no preamble:
1. RENDER MANAGER: given fan-out + ledger-priced routing + K-of-N verification, what is
   the #1 design flaw and the ONE missing component before 50-way fan-out at $0.01/job?
2. SEED EVOLUTION: paired-blind-win-rate prompt evolution under byte-stable cache
   discipline — what breaks FIRST at scale, and the minimal guard?
3. LOCAL JUDGMENT LANE: a 180B MoE (n-gram table paged from NVMe) on one 24GB GPU +
   128GB RAM as the fleet's judgment tier — top deployment pitfall and the cheapest
   honest quality test?
4. GAP ANALYSIS: with cache-mined lanes, chain memory, MCP hands, a witness tick, and
   containerized workers — what SINGLE capability is missing for a self-sustaining
   agent ecosystem, and which existing open-source piece should be stolen for it?"""


def codex_witness() -> tuple[str, str]:
    cmd = [r"C:\Users\ESTATE_USER\AppData\Local\hermes\node\codex.cmd", "exec",
           "-s", "read-only", "-"]
    p = subprocess.run(cmd, input=CONTEXT + "\n\n" + QUESTIONS,
                       capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    return p.stdout or p.stderr, str(p.returncode)


def grok_witness(seat: str) -> tuple[str, str]:
    from mag.grok_seat_burner import _launch_one
    goal = (f"{CONTEXT}\n\n{QUESTIONS}\n\n"
            f"Write your four answers directly to the file "
            f"memory/runs/salon_20260827/grok_{seat}.md, then reply DONE.")
    OUT.mkdir(parents=True, exist_ok=True)
    r = _launch_one(seat, goal, max_turns=10, timeout=800, always_approve=True)
    return r.get("output") or r.get("error") or "", str(r.get("ok"))


def elder_witness() -> tuple[str, str]:
    from models.providers import chat_provider
    r = chat_provider("deepseek", system="Elder echo: accumulated fleet judgment, dense, numbered.",
                      user=CONTEXT + "\n\n" + QUESTIONS,
                      model="deepseek-chat", thinking=False, max_tokens=1200, tier="T2")
    return r.get("text") or "", str(r.get("ok"))


def run_witness(name: str, fn) -> None:
    t0 = time.time()
    try:
        text, meta = fn()
    except Exception as e:  # noqa: BLE001
        text, meta = f"WITNESS ERROR: {type(e).__name__}: {str(e)[:200]}", "EXC"
    (OUT / f"{name}.md").write_text(
        f"# {name} (exit/meta {meta}, {time.time()-t0:.0f}s)\n\n{text}", encoding="utf-8")
    print(f"[salon] {name}: {len(text)} chars in {time.time()-t0:.0f}s", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(run_witness, n, f) for n, f in
                (("chatgpt", codex_witness), ("grok_nacho", lambda: grok_witness("nacho")),
                 ("grok_sd", lambda: grok_witness("sd")), ("elder", elder_witness))]
        for f in futs:
            f.result()


if __name__ == "__main__":
    main()
