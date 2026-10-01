"""diamond_mine — find MORE signals like the logEps tesuji buried in the noise, via our systems.

Operator (2026-08-11): "now we have the beginnings of a diamond mine. how can we find more signals
like this in the noise via our systems."

The logEps find was NOT a recurring latent token (shadow_graph's domain) — it was a SPECIFIC buried
tesuji inside a trash block: a self-correcting comment + a pointer to a better+simpler source. So we
mine that SIGNAL CLASS. Diamond mine = a scanner that detects blocks carrying a buried tesuji,
shadow-graphs them, and routes the novel ones to the swarm.

THE METHOD (deterministic + $0, reuses our systems):
  sweep()   -> gather the garbage/trash corpus (memory/ghost/noise, memory/trash, dump text files).
  detect()  -> score a block for BURIED TESUJI signal via a signal lexicon (self-correction,
               pointer-to-better, honest-meta, mechanism-in-verbose) + extract the tesuji snippet.
  mine()    -> sweep the whole pile, rank by tesuji score, shadow-graph the top finds (reuse
               shadow_graph.latent_signal), route NOVEL ones to the swarm (swarm_surface.route_novel)
               -> dogfooding, no local run.

Schema: diamond_mine.v1 · deterministic + $0 · reuse: shadow_graph, percolator, swarm_surface
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "diamond_mine.v1"
MINE_DIRS = [
    ROOT / "memory" / "ghost" / "noise",   # percolator noise (the trash we discarded)
    ROOT / "memory" / "trash",             # legacy trash dumps (harvested threads/bookmarks)
    ROOT / "memory" / "ghost" / "intake",  # intake register (inaccessible input)
]

# ── THE TESUJI-SIGNAL LEXICON (what a buried diamond looks like) ──────────────
# A block carries a tesuji when it has SELF-CORRECTION, a POINTER to a better/simpler source,
# HONEST-META (the author admits what actually matters), or a MECHANISM hidden in verbose/commented
# code. Each pattern is a small weight toward "buried signal".
SELF_CORRECT = re.compile(
    r"(fails? (at|when|in)|doesn'?t work (when|for)|not good for|disadvantage|better (when|for)|"
    r"performs better|outperforms|instead of|rather than|at the cost of|cost:|disadvantage|trade-?off)",
    re.I)
POINTER = re.compile(
    r"(a better\+?simpler|better( and|,)? ?simpler|simpler demo|the real (one|demo|signal)|"
    r"(shadertoy|github)\.com/|view/[A-Za-z0-9]{4,}|the key (is|point)|the core (idea|part)|"
    r"the actual (mechanism|point))",
    re.I)
HONEST_META = re.compile(
    r"(honest(ly)? signal|buried|in practice|actually works|the truth is|the point (is|underlying)|"
    r"in reality|it really (is|just)|the whole point|underlying)",
    re.I)
MECHANISM = re.compile(
    r"(the core idea lies|the main mechanism|how (calculus|it) works|the essential (part|idea)|"
    r"principle behind|the reason (it|this) works|this (is|was) the (real|actual))",
    re.I)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _walk_texts() -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for d in MINE_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() in (".jsonl", ".json", ".md", ".txt"):
                try:
                    t = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if t and len(t) > 40:
                    files.append({"source": f"{d.name}/{p.name}", "text": t[:40_000]})
    return files


def detect(text: str) -> dict[str, Any]:
    """Score a text block for a BURIED TESUJI signal + extract the tesuji snippet. The four signal
    classes (self-correction, pointer, honest-meta, mechanism) -> a 0..1 diamond score."""
    t = text or ""
    hits = {}
    for name, pat in (("self_correct", SELF_CORRECT), ("pointer", POINTER),
                      ("honest_meta", HONEST_META), ("mechanism", MECHANISM)):
        m = pat.findall(t)
        hits[name] = len(m)
    score = min(1.0, sum(hits.values()) / 6.0)
    # extract the tesuji snippet: the sentence containing a pointer or self-correction
    snippet = ""
    for m in POINTER.finditer(t):
        s = t[max(0, m.start() - 80): m.end() + 160].replace("\n", " ")
        snippet = s[:240]
        break
    if not snippet:
        for m in SELF_CORRECT.finditer(t):
            snippet = t[max(0, m.start() - 80): m.end() + 160].replace("\n", " ")[:240]
            break
    return {"score": round(score, 3), "signal_classes": hits, "is_tesuji": score >= 0.4,
            "tesuji": snippet}


def mine(*, min_score: float = 0.4, enqueue: bool = True) -> dict[str, Any]:
    """MINE the whole garbage pile for tesuji-signals, shadow-graph the finds, route NOVEL ones to
    the swarm. The diamond mine: what the noise keeps hiding."""
    finds = []
    for f in _walk_texts():
        d = detect(f["text"])
        if d["is_tesuji"]:
            finds.append({"source": f["source"], **d})
    finds.sort(key=lambda x: -x["score"])
    # shadow-graph the top finds (reuse shadow_graph.latent_signal) + route novel ones to the swarm
    routed = []
    for f in finds[:12]:
        latent = {}
        try:
            from mag import shadow_graph
            latent = shadow_graph.latent_signal(f["tesuji"][:200]) or {}
        except Exception as e:
            latent = {"error": str(e)[:60]}
        f["latent"] = latent.get("theme") or latent.get("signal") or ""
        if enqueue:
            try:
                from mag import swarm_surface
                goal = (f"DEEP SELF-STEAL [diamond-mine tesuji] {f['source']}: {f['tesuji'][:220]}"
                        f"  signal_classes={f['signal_classes']}")
                q = swarm_surface.route_novel(goal, surface="diamond-mine", lens="memory/invariant",
                                              domain="research")
                f["task_id"] = q.get("task_id", ""); f["enqueued"] = q.get("ok", False)
            except Exception as e:
                f["enqueued"] = False; f["task_id"] = ""
        routed.append(f)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "scanned": len(_walk_texts()),
            "n_finds": len(finds), "n_routed": len([f for f in routed if f.get("enqueued")]),
            "top_tesuji": routed[:12],
            "note": "diamond mine: swept the garbage pile, found tesuji-signals (self-correction/"
                    "pointer/honest-meta/mechanism), shadow-graphed + routed novel ones to the swarm"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "sweep()->the garbage corpus; detect()->tesuji score + snippet; "
                        "mine()->rank + shadow-graph + route novel to the swarm",
            "cost": "deterministic + $0 (reuses shadow_graph, swarm_surface)",
            "mine_dirs": [str(d.relative_to(ROOT)).replace("\\", "/") for d in MINE_DIRS],
            "signal_classes": ["self_correct", "pointer", "honest_meta", "mechanism"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="diamond-mine")
    ap.add_argument("cmd", nargs="?", default="mine",
                    choices=["mine", "status"])
    a = ap.parse_args()
    print(json.dumps(mine() if a.cmd == "mine" else status(), indent=2, default=str))
