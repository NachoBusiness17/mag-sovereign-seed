"""divergence_meter — the Steins;Gate readout for the fleet's worldline.

The worldline frame (SELF_STEAL_WORLDLINES_20260905, salon 7/7) is load-bearing
on one instrument: proof that the line actually MOVED rather than snapped back
to pattern. This is that instrument.

Measured doctrine-state surfaces (hashed):
    watch/*.md          the canon cards (the doctrine layer)
    corpus/canon/*      the operator's public record (curriculum + receipts)
    memory/MEMORY.md    the seat memory index (what survives shifts)
    chain tip           memory/biography/verkle_chain.jsonl
    trajectory stream   memory/trajectory/steps.jsonl

Verdict per run:
    BASELINE   first reading (nothing to compare yet)
    DIVERGED   new/changed hashes (the line moved — new doctrine or record)
    SNAP-BACK  previously-seen hashes disappeared (something reverted)
    HOLD       identical state (the standing wave, holding)

Log: memory/worldline/readings.jsonl (append-only, one reading per run).
CLI: python -m mag.divergence_meter
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "memory" / "worldline" / "readings.jsonl"
SURFACES = {
    "watch_cards": REPO / "watch",
    "canon": REPO / "corpus" / "canon",
    "memory_index": REPO / "memory" / "MEMORY.md",
    "chain": REPO / "memory" / "biography" / "verkle_chain.jsonl",
    "trajectory": REPO / "memory" / "trajectory" / "steps.jsonl",
}


def _hash_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _snapshot() -> dict[str, str]:
    state: dict[str, str] = {}
    cards = SURFACES["watch_cards"]
    if cards.is_dir():
        for p in sorted(cards.glob("*.md")):
            state["card:" + p.name] = _hash_file(p)
    canon = SURFACES["canon"]
    if canon.is_dir():
        for p in sorted(canon.rglob("*")):
            if p.is_file() and p.suffix in (".md", ".json", ".jsonl", ".txt"):
                state["canon:" + str(p.relative_to(canon)).replace("\\", "/")] = _hash_file(p)
    for name in ("memory_index", "chain", "trajectory"):
        p = SURFACES[name]
        if p.exists():
            state[name] = _hash_file(p)
    return state


def take_reading() -> dict:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    prev = None
    if LOG.exists():
        lines = [l for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            prev = json.loads(lines[-1]).get("state")
    cur = _snapshot()
    reading: dict = {"ts": now.isoformat(timespec="seconds"), "diverged": [], "snap_back": [], "held": 0}
    if prev is None:
        reading["verdict"] = "BASELINE"
    else:
        for k, v in cur.items():
            if k not in prev:
                reading["diverged"].append("+ " + k)
            elif prev[k] != v:
                reading["diverged"].append("~ " + k)
        for k in prev:
            if k not in cur:
                reading["snap_back"].append("- " + k)
        reading["verdict"] = "DIVERGED" if (reading["diverged"] or reading["snap_back"]) else "HOLD"
        reading["held"] = sum(1 for k in cur if k in prev and cur[k] == prev[k])
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": reading["ts"], "verdict": reading["verdict"],
                            "diverged": reading["diverged"], "snap_back": reading["snap_back"],
                            "state": cur}, ensure_ascii=False) + "\n")
    return reading


def main() -> None:
    ap = argparse.ArgumentParser(prog="mag.divergence_meter")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    r = take_reading()
    print(f"[{r['ts']}Z] worldline: {r['verdict']}  "
          f"(diverged: {len(r['diverged'])}, snap-back: {len(r['snap_back'])}, held: {r.get('held', '-')})")
    for d in (r["diverged"] + r["snap_back"])[:12]:
        print("   ", d)


if __name__ == "__main__":
    main()
