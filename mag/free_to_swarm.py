"""free_to_swarm — the seam that makes "free seats direct k3s to do local work" real (2026-08-23).

Operator: "those working with the free seats can then direct k3s to do local work" + the k8s check
showed the swarm worker drains `total: 0` — the cluster loop runs but NOTHING is pushed into it.
This is the missing wire: the free-seat discoveries (banked OX_RS_* files) become tasks in the
k8s swarm queue, so the next CronJob pass actually drains real work.

Flow (the scout proposes, the basecamp disposes):
  1. READ the banked free-seat discoveries — real_swarm's OX_RS_*.json files (cold-vertex
     reasoning tapes: core/kind/content/reasoning).
  2. FILTER to substantive ones (ox_fold._substance) that haven't been enqueued yet.
  3. ENQUEUE each as a task to the cluster swarm via swarm_worker.enqueue_task — the spec lands
     on the shared state PVC; the k8s worker picks it up next pass (every 15m).
  4. MARK enqueued (append-only ledger) so a discovery is never handed to the cluster twice.

The free seats PROPOSE (banked reasoning); the k3s basecamp DISPOSES (verifies + folds + roots).
This is the "one queue" seam ox designed: scouts PUSH into swarm.q, local consumers lease.

Schema: free_to_swarm.v1 · deterministic + $0 (just reads banks + writes queue specs).
CLI: python -m mag.free_to_swarm [--limit N] [--dry]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "free_to_swarm.v1"
# the free-seat bank: real_swarm writes OX_RS_*.json discoveries here
RS_OUT = ROOT / "handoff"
# append-only ledger of discoveries already handed to the cluster (never enqueue twice)
SENT = ROOT / "memory" / "runs" / "free_to_swarm" / "sent.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sent_set() -> set[str]:
    """Names (file stems) already handed to the cluster."""
    out = set()
    if SENT.is_file():
        for line in SENT.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.add(json.loads(line).get("name", ""))
            except Exception:  # noqa: BLE001
                continue
    return out


def _mark_sent(name: str, task_id: str) -> None:
    SENT.parent.mkdir(parents=True, exist_ok=True)
    with SENT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "task_id": task_id, "ts": _now()}, ensure_ascii=False) + "\n")


def pending_discoveries() -> list[dict[str, Any]]:
    """Banked free-seat discoveries (OX_RS_*.json) that have substantive content and haven't
    been enqueued to the cluster yet. Grounded: reads the real bank, never fabricates."""
    from mag.ox_fold import _substance
    sent = _sent_set()
    out = []
    for p in sorted(RS_OUT.glob("OX_RS_*.json"), key=lambda x: x.name):
        name = p.stem.removeprefix("OX_RS_")
        if name in sent:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        if not d.get("ok"):
            continue
        sub = _substance(d.get("content") or "", d.get("reasoning") or "")
        if not sub:
            continue  # substantive only — the cluster doesn't burn on empty reasoning
        out.append({"name": name, "core": d.get("core", ""), "kind": d.get("kind", ""),
                    "provider": d.get("provider", "openrouter"),
                    "substance": sub, "ts": d.get("ts", ""), "file": str(p)})
    return out


def push(*, limit: int = 20, dry: bool = False) -> dict[str, Any]:
    """Hand the pending free-seat discoveries to the k3s swarm queue. Each becomes a task the
    CronJob drains next pass. Dry mode reports without enqueueing."""
    from mag import swarm_worker
    discoveries = pending_discoveries()[:max(1, int(limit))]
    enqueued = []
    for d in discoveries:
        goal = (f"[{d['kind']}] {d['core']} — free-seat cold-vertex discovery. "
                f"Verify and fold: {d['substance'][:300]}").strip()
        if dry:
            enqueued.append({"name": d["name"], "goal": goal[:120], "task_id": "(dry)"})
            continue
        r = swarm_worker.enqueue_task(
            goal,
            provider=d.get("provider", "openrouter"),
            domain="cold_vertex", tag="free_to_swarm",
        )
        task_id = r.get("task_id", "?")
        if r.get("ok"):
            _mark_sent(d["name"], task_id)
        enqueued.append({"name": d["name"], "core": d["core"][:60],
                         "task_id": task_id, "ok": bool(r.get("ok"))})
    return {"ok": True, "schema": SCHEMA, "dry": dry, "found": len(discoveries),
            "enqueued": enqueued, "n_enqueued": len(enqueued),
            "note": "free-seat discoveries handed to the k8s swarm queue (scout proposes, basecamp "
                    "disposes). The next CronJob pass drains them."}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="free-to-swarm")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry", action="store_true", help="report without enqueueing")
    a = ap.parse_args(argv)
    print(json.dumps(push(limit=a.limit, dry=a.dry), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
