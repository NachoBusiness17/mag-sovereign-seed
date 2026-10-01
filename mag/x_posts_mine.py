"""x_posts_mine — mine a BATCH of X posts for high-signal data via ghost, THROUGH the swarm. Each
post is content-addressed (dedupe), and ONE ghost mining task routes the whole batch to the swarm
(x-surface tools + percolator + fold).

Operator (2026-08-11): pasted 20 X post URLs to mine.

PER THE LAW (5-W + swarm-surface): WHAT=steal/mine, WHERE=swarm/x-surface, WHO=ghost -> the batch
mining task is DEDUPED (by post id) + ENQUEUED to the swarm research queue (swarm_surface
.route_novel). Ghost (with x_thread_fetch / x_semantic_search / browser_driver) executes it
in-cluster. We never run it locally.

THE MINING INSTRUCTION (what ghost does per post):
  1. FETCH the post text (x_thread_fetch / x_semantic_search / browser_driver inner_text).
  2. PERCOLATE it (strip noise/theater -> invariants + novel).
  3. FOLD the high-signal data + route any novel tesuji to the swarm.
  4. Report per-post what was mined. HONEST: if a post is inaccessible, say so — never fabricate.

Schema: x_posts_mine.v1 · deterministic + $0 spec · swarm-routed batch mining
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "x_posts_mine.v1"

# the 20 posts from the operator (the batch to mine)
BATCH = [
    "https://x.com/poetengineer__/status/2085767565771518163",
    "https://x.com/VoidStateKate/status/2085204113009016888",
    "https://x.com/BabylonNoMore/status/2083334595957694795",
    "https://x.com/PhilosophyOfPhy/status/2083021077937369134",
    "https://x.com/FarmGirlCarrie/status/2082229495516570027",
    "https://x.com/mathemetica/status/2081127852616093706",
    "https://x.com/maximumpain333/status/2080543502883004910",
    "https://x.com/0xkkai/status/2079965372069839119",
    "https://x.com/mathelirium/status/2079969566499713487",
    "https://x.com/DataChaz/status/2079357537250664839",
    "https://x.com/pickover/status/2078613200283521276",
    "https://x.com/Rainmaker1973/status/2078547852322549868",
    "https://x.com/VincentCrypt46/status/2071289713252556870",
    "https://x.com/NachoQuixotic/status/2071315275354390775",
    "https://x.com/NachoQuixotic/status/2078482079608721898",
    "https://x.com/LastingCzardd/status/2065594135520625098",
    "https://x.com/DataChaz/status/2071189870253666567",
    "https://x.com/pickover/status/1568949131380686848",
    "https://x.com/Rainmaker1973/status/2077765195401703908",
    "https://x.com/cotterzz/status/2078205216860618835",
]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _post_id(url: str) -> str:
    return (url or "").rstrip("/").split("/")[-1].split("?")[0]


def _posts() -> list[dict[str, str]]:
    out, seen = [], set()
    for u in BATCH:
        pid = _post_id(u)
        if pid in seen:
            continue
        seen.add(pid)
        out.append({"id": pid, "url": u})
    return out


def mine(*, enqueue: bool = True, surface: str = "x-posts-mine") -> dict[str, Any]:
    """Dedupe the batch + route ONE ghost mining task to the swarm (x tools -> percolate -> fold).
    The swarm executes it in-cluster; we never run it locally."""
    posts = _posts()
    anchor = hashlib.sha256("x-posts-mine::" + ",".join(p["id"] for p in posts)).hexdigest()[:16]
    ids = ",".join(p["id"] for p in posts)
    goal = (f"MINE X POSTS [ghost] {len(posts)} posts: {ids}. For each, use x_thread_fetch / "
            f"x_semantic_search / browser_driver inner_text to fetch the post text (accessible "
            f"text, not screenshots). Then: (1) percolate it with mag.percolator (strip noise/"
            f"theater -> invariants + novel); (2) fold the high-signal data + route any novel tesuji "
            f"to the swarm; (3) write a per-post summary to memory/ghost/x_surface/mining/batch_"
            f"{anchor}.md. Return the number of invariants folded + the high-signal findings per "
            f"post. HONEST: if a post is inaccessible, say so — never fabricate its content.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_posts": len(posts), "anchor": anchor,
            "post_ids": [p["id"] for p in posts], "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "deduped": q.get("deduped", False),
            "note": "20-post batch routed to the swarm for ghost mining (x tools -> percolate -> "
                    "fold); honest provenance — no fabricated post content"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "mine()->dedupe the batch + route ONE ghost mining task to the swarm "
                        "(x_thread_fetch/x_semantic_search + percolator + fold); honest",
            "cost": "deterministic + $0 spec (ghost/swarm executes the mining)",
            "n_posts": len(_posts())}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="x-posts-mine")
    ap.add_argument("cmd", nargs="?", default="mine", choices=["mine", "status"])
    a = ap.parse_args()
    print(json.dumps(mine() if a.cmd == "mine" else status(), indent=2, default=str))
