"""swarm_surface — THE ONE shared primitive every task surface uses to route NOVEL research to the
swarm: dedupe (by content anchor) + enqueue to the SWARM RESEARCH QUEUE (swarm_worker.enqueue_task
-> k8s worker drains in-cluster). Dogfooding the process: the swarm coordinates the surface, never a
local run.

Operator (2026-08-11): "this should be everywhere no? rightsize it and learn this is what i want for
new stuff you build weave it in though self steal don't invent."

SELF-STEAL (not invented): reuses mag.swarm_worker.enqueue_task (the shared queue the drainer eats)
+ the dedup-by-anchor ledger pattern. This is the right-sized primitive; every new surface calls
route_novel() and the swarm handles it. Idempotent: repeated calls with the same anchor enqueue
nothing.

Schema: swarm_surface.v1 · deterministic + $0 · reuse: swarm_worker
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "swarm_surface.v1"
LEDGER = ROOT / "memory" / "swarm_surface" / "sent.jsonl"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def anchor(goal: str, surface: str) -> str:
    """Deterministic content anchor: the same novel item always maps to the same anchor -> dedupe."""
    return hashlib.sha256(f"{surface}::{goal}".encode("utf-8")).hexdigest()[:16]


def _sent_anchors() -> set[str]:
    if not LEDGER.is_file():
        return set()
    out = set()
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            a = json.loads(line).get("anchor") or ""
            if a:
                out.add(a)
        except Exception:
            continue
    return out


def route_novel(goal: str, *, surface: str, lens: str | None = None,
                domain: str = "research", provider: str | None = None,
                model: str | None = None) -> dict[str, Any]:
    """The ONE primitive: dedupe a novel research goal by anchor, enqueue it to the SWARM research
    queue (swarm_worker.enqueue_task -> k8s worker drains in-cluster), record the anchor. Idempotent.
    Returns {ok, task_id, deduped, anchor}."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "surface": surface, "error": "empty goal"}
    a = anchor(goal, surface)
    if a in _sent_anchors():
        return {"ok": True, "surface": surface, "deduped": True, "anchor": a, "task_id": ""}
    q = {}
    try:
        from mag import swarm_worker
        q = swarm_worker.enqueue_task(
            goal,
            domain=domain,
            tag=surface,
            # The worker owns the free-first default.  Do not silently turn
            # every novel surface into a paid DeepSeek dispatch.
            provider=provider or swarm_worker.DEFAULT_PROVIDER,
            model=model,
        )
    except Exception as e:
        return {"ok": False, "surface": surface, "anchor": a, "error": str(e)[:120]}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"anchor": a, "surface": surface, "lens": lens,
                            "task_id": q.get("task_id", ""), "ts": _now()},
                           ensure_ascii=False) + "\n")
    return {"ok": bool(q.get("ok")), "surface": surface, "anchor": a,
            "deduped": False, "task_id": q.get("task_id", "")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "route_novel(goal, surface, lens)->dedupe by anchor + enqueue to the swarm "
                        "research queue (swarm_worker.enqueue_task); idempotent; every surface "
                        "weaves this in",
            "cost": "deterministic + $0 (reuses swarm_worker; dogfoods the swarm)",
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
            "n_sent": len(_sent_anchors())}


if __name__ == "__main__":
    print(json.dumps(status(), indent=2, default=str))
