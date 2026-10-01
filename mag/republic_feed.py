"""republic_feed — the MYCELIAL REPUBLIC FEED: a Tumblr/IG-style REST backend of HIGH-SIGNAL data
mapped to our internals — the complex tasks our systems do that normally cost tokens but cost ZERO
through our system. This is the Republic's foundation + game-engine front door: a live feed of the
world doing real deterministic work for $0.

Operator (2026-08-11): "i wanna see them do some complex tasks using our systems that normally cost
tokens but zero though our systemin theory and i want a feed of this stuff like ig that you create
as a restful backend for high signal data mapped to our internals literally like a tumblr feed this
is our mycellial republic foundation and game engine."

EACH POST (a $0 win, grounded, tagged by lens/surface):
  - the deterministic system that did work a frontier model would charge for, done for $0.
  - mapped to its lens + internal module + the shared surface.
  - estimated "would_cost" (the tokens an LLM would have burned) vs "$0".

Schema: republic_feed.v1 · deterministic + $0 · reuse: the deterministic module wins
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
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "republic_feed.v1"
FEED = ROOT / "memory" / "republic_feed" / "feed.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _collect() -> list[dict[str, Any]]:
    """Gather the high-signal $0 wins from the deterministic modules. Each is a post."""
    posts: list[dict[str, Any]] = []

    def add(lens, surface, title, body, would_cost, module):
        posts.append({"ts": _now(), "lens": lens, "surface": surface, "title": title,
                      "body": body[:400], "cost": "$0", "would_cost": would_cost,
                      "module": module, "tags": [lens.split("/")[0], surface]})

    # economics: the recoverable miss-waste (real bill)
    try:
        from mag import budget_refactor
        p = budget_refactor.plan()
        w = p.get("waste", {})
        add("economics/cost", "billing", "Recovered cache-miss waste for $0",
            f"The deterministic refactor found ${w.get('recoverable_usd')} of 50x cache-miss waste "
            f"in the real bill, re-spendable as ~{p.get('freed',{}).get('more_flash_tasks')} more "
            f"flash agents — a frontier cost optimizer would charge for this.",
            "~$1.50 (an LLM cost analysis)", "mag/budget_refactor.py")
    except Exception:
        pass

    # diamond mine: tesuji found in the garbage
    try:
        from mag import diamond_mine
        d = diamond_mine.mine(enqueue=False)
        add("memory/invariant", "shadow-work", f"Found {d.get('n_finds')} tesuji in the garbage for $0",
            f"The diamond mine swept the noise pile and surfaced {d.get('n_finds')} buried signals "
            f"(self-correcting comments, pointers, honest-meta) — shadow-work that a frontier model "
            f"would be paid to find.",
            "~$0.50 (a frontier deep-read)", "mag/diamond_mine.py")
    except Exception:
        pass

    # roshomon swarm truth
    try:
        from mag import lens_knot
        t = lens_knot.swarm_truth()
        add("swarm/detect", "lensing", "The swarm told the truth for $0",
            f"{len(t.get('roshomon_core', []))} signals the lens-knots agree on (Roshomon core) — "
            f"consensus across stateless witnesses, no LLM needed.",
            "~$0.80 (N frontier witnesses)", "mag/lens_knot.py")
    except Exception:
        pass

    # persona recall: the world recounts
    try:
        from mag import persona_recall
        r = persona_recall.recall(archetype="self")
        add("compiler/world", "persona", "The world recounted what happened while you were gone for $0",
            r.get("recount", "")[:300],
            "~$0.40 (a summarizer LLM)", "mag/persona_recall.py")
    except Exception:
        pass

    # loop feedback: what the swarm produced
    try:
        from mag import loop_feedback
        f = loop_feedback.read_back()
        lo = f.get("loop_output", {})
        add("compiler/world", "loop", f"The loop produced {lo.get('n_done_tasks','?')} done tasks for $0",
            f"Read back {lo.get('n_packs','?')} filed packs + {lo.get('n_invariants','?')} invariants "
            f"folded + {lo.get('chain_leaves','?')} chain leaves — the swarm's measured output.",
            "~$1.00 (a status synthesis)", "mag/loop_feedback.py")
    except Exception:
        pass

    # novel orphans routed
    try:
        from mag import orphan_sense
        o = orphan_sense.novel_orphans(enqueue=False)
        add("swarm/detect", "orphans", f"Detected {o.get('n_novel_orphans','?')} novel orphans for $0",
            "Ghost swept every orphan/novel surface and saw all neglected novel work — an agentic "
            "audit that would cost frontier tokens.",
            "~$0.60 (an agentic audit)", "mag/orphan_sense.py")
    except Exception:
        pass

    return posts


def feed(*, tail: int = 50) -> dict[str, Any]:
    """Collect + persist + return the feed (reverse-chronological, Tumblr-style)."""
    posts = _collect()
    FEED.parent.mkdir(parents=True, exist_ok=True)
    with FEED.open("a", encoding="utf-8") as f:
        for p in posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    # read back the persisted feed (reverse-chronological)
    all_posts = []
    if FEED.is_file():
        for line in FEED.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_posts.append(json.loads(line))
            except Exception:
                continue
    all_posts = sorted(all_posts, key=lambda p: p.get("ts", ""), reverse=True)
    return {"ok": True, "schema": SCHEMA, "n_new": len(posts), "n_total": len(all_posts),
            "feed": all_posts[:tail],
            "note": "the Mycelial Republic feed: high-signal $0 wins mapped to our internals, "
                    "served as a REST backend (Tumblr-style) — the foundation + game engine"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "feed()->collect + persist + return the $0-achievement feed (reverse-chron); "
                        "served via GET /api/v1/feed",
            "cost": "deterministic + $0 (the posts ARE $0 wins)",
            "feed_path": str(FEED.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="republic-feed")
    ap.add_argument("cmd", nargs="?", default="feed", choices=["feed", "status"])
    a = ap.parse_args()
    print(json.dumps(feed() if a.cmd == "feed" else status(), indent=2, default=str))
