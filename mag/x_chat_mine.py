"""x_chat_mine — mine an X (Twitter) chat for high-signal data via ghost, THROUGH the swarm, even
when it's protected from screenshots. Screenshots are blocked, but the DOM/accessible TEXT is not:
ghost reads it via browser_driver (CDP inner_text) or the x-surface tools, then percolates + folds.

Operator (2026-08-11): "https://x.com/i/chat/g2066529771400450108 can we use this via mem tools even
though its sprotected from screenshots using ghost to mine it for high signal data"

PER THE LAW (5-W + swarm-surface): WHAT=steal/mine, WHERE=x-surface/swarm, WHO=ghost -> the mining
task is DEDUPED + ENQUEUED to the SWARM research queue (swarm_surface.route_novel); ghost (or the
k8s worker with browser_driver/x-surface tools) executes it in-cluster. We never run it locally.

THE MINING INSTRUCTION (what ghost does):
  1. OPEN the chat via browser_driver (CDP inner_text — NOT screenshots, which are protected) or
     the x-surface tools.
  2. EXTRACT the accessible text (the conversation / thread content).
  3. PERCOLATE it (percolator: strip noise/theater -> invariants + novel explore).
  4. FOLD the high-signal data (invariants + any novel tesuji) into the learning loop.

Schema: x_chat_mine.v1 · deterministic + $0 spec · swarm-routed mining
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

SCHEMA = "x_chat_mine.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _chat_id(url: str) -> str:
    return (url or "").rstrip("/").split("/")[-1].split("?")[0]


def mine(url: str = "", *, enqueue: bool = True, surface: str = "x-chat-mine") -> dict[str, Any]:
    """Route a ghost mining task to the swarm: read the chat's accessible text (not screenshots),
    percolate it, fold the high-signal data. Dedupe + enqueue via swarm_surface."""
    cid = _chat_id(url or "https://x.com/i/chat/g2066529771400450108")
    if not cid:
        return {"ok": False, "schema": SCHEMA, "error": "no chat id in url"}
    anchor = hashlib.sha256(f"x-chat-mine::{cid}".encode("utf-8")).hexdigest()[:16]
    goal = (f"MINE X CHAT [ghost] {cid}: open https://x.com/i/chat/{cid} via browser_driver CDP "
            f"(page.inner_text — read the DOM/accessible TEXT, NOT screenshots which are protected). "
            f"If the chat is auth-gated or empty, use the x-surface tools (x_semantic_search/x_thread"
            f"_fetch) on the linked thread. Then: (1) extract the high-signal text; (2) percolate it "
            f"with mag.percolator (strip noise/theater -> invariants + novel explore); (3) fold the "
            f"high-signal data (invariants) + route any novel tesuji to the swarm; (4) write a "
            f"summary of what was mined to memory/ghost/x_surface/mining/{cid}.md. Return the number "
            f"of invariants folded + the high-signal findings. HONEST: if nothing is accessible, "
            f"say so — never fabricate the chat content.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "chat_id": cid, "anchor": anchor,
            "enqueued": q.get("ok", False), "task_id": q.get("task_id", ""),
            "deduped": q.get("deduped", False),
            "note": "x-chat mining task routed to the swarm (ghost reads accessible text, not "
                    "screenshots; percolate + fold high-signal data)"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "mine(url)->route a ghost mining task to the swarm (browser_driver CDP "
                        "inner_text, not screenshots; percolate + fold); dedupe by chat id",
            "cost": "deterministic + $0 spec (ghost/swarm executes the mining)",
            "reuse": ["browser_driver.connect+inner_text", "x-surface tools", "percolator",
                      "swarm_surface.route_novel"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="x-chat-mine")
    ap.add_argument("url", nargs="?", default="https://x.com/i/chat/g2066529771400450108")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    print(json.dumps(mine(a.url, enqueue=not a.dry), indent=2, default=str))
