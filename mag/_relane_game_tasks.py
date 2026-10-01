"""Rightsize the game swarm onto the free lanes (2026-08-25).

Finding: every queued game task rides provider=deepseek (the brake, rank 14, $3/day).
The game tasks are design/refine — free-lane material (z_ai flash is our free rank-1
default, cache-mining; groq 91% ok as fallback). This is the unutilized-free-lanes
problem in miniature: the drain crawls on the brake while free lanes sit idle.

This patch re-lanes the QUEUED game tasks to the free channel. It does NOT touch
done/failed/cancelled tasks, and it leaves the drain's own provider reconcile alone —
the drain executes each task's provider, so re-laned tasks ride the free lane.
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from mag import swarm_worker as sw  # noqa: E402
from mag import free_tier  # noqa: E402

FREE = "z_ai"  # free rank-1 default, cache-mining, thinking-off stable (probe 08-24)
QUEUE = Path(sw.QUEUE_DIR)

patched, skipped = [], []
for p in sorted(QUEUE.glob("sw-*.json")):
    try:
        t = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    if t.get("domain") != "game":
        continue
    if t.get("status") != "queued":
        skipped.append((t.get("task_id"), t.get("status")))
        continue
    old = t.get("provider")
    t["provider"] = FREE
    t["_lane_reason"] = "queue_gate rightsize: brake -> free lane (game = free-lane material)"
    p.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    patched.append((t.get("task_id"), old, FREE))

print("patched:", json.dumps(patched))
print("skipped (not queued):", json.dumps(skipped))
print("free lane status:", free_tier.status().get("surfaces", {}).get(FREE, {}).get("ok_rate"))
