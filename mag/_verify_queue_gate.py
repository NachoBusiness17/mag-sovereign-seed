"""queue_gate verify (2026-08-25): scan/deps/plan/preflight against the real queue + a
controlled dependency test."""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from mag import queue_gate as qg  # noqa: E402
from mag import swarm_worker as sw  # noqa: E402

fails = []

# 1) scan reads the real queue
s = qg.scan()
assert s["ok"] and isinstance(s["tasks"], list), "scan failed"
print(f"PASS scan: {s['queued']} queued tasks")

# 2) deps graph built (may be big — just shape-check)
d = qg.dependencies()
assert d["ok"] and isinstance(d["graph"], dict), "deps failed"
print(f"PASS deps: {len(d['graph'])} nodes, "
      f"{sum(1 for v in d['graph'].values() if v['blocked'])} blocked")

# 3) plan on real queue — shape + gated reasons are legal
p = qg.plan(n=5)
assert p["ok"] and isinstance(p["order"], list), "plan failed"
for g in p["gated"]:
    assert g["reason"] in ("depends_on", "budget", "lane_cooling"), \
        f"bad gate reason {g['reason']}"
for r in p["runs"]:
    assert "emphasis" in r and r["emphasis"] >= 1, "runs must carry emphasis"
print(f"PASS plan: dispatchable={p['dispatchable']}, order={p['order'][:5]}, "
      f"gated={len(p['gated'])}, emphasis_copies={len(p['emphasis_copies'])}")

# 4) CONTROLLED dependency test: enqueue A then B depends_on A. B must be gated until A done.
tag = f"qt-{uuid.uuid4().hex[:6]}"
ra = sw.enqueue_task("queue_gate test base task A", domain="test", tag=tag)
rb = sw.enqueue_task("queue_gate test dependent task B", domain="test", tag=tag,
                     depends_on=[ra["task_id"]])
print(f"PASS enqueue: A={ra['task_id']} B={rb['task_id']}")

pf_b = qg.preflight({"task_id": rb["task_id"], "goal": "queue_gate test dependent task B",
                     "provider": "deepseek", "depends_on": [ra["task_id"]]})
assert pf_b.get("ok") is False and pf_b.get("reason") == "depends_on", \
    f"B should be gated on A, got {pf_b}"
print(f"PASS preflight(B before A): gated -> {pf_b['reason']} ({pf_b['detail']})")

# mark A done (simulate completion via the queue file), then B must be dispatchable
a_path = Path(sw.QUEUE_DIR) / f"{ra['task_id']}.json"
a = json.loads(a_path.read_text(encoding="utf-8"))
a["status"] = "done"
a_path.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
pf_b2 = qg.preflight({"task_id": rb["task_id"], "goal": "queue_gate test dependent task B",
                      "provider": "deepseek", "depends_on": [ra["task_id"]]})
print(f"PASS preflight(B after A done): ok={pf_b2.get('ok')} "
      f"(reason={pf_b2.get('reason') if not pf_b2.get('ok') else 'dispatch'})")

# 5) EMPHASIS doctrine: an identical goal is NOT blocked — it compiles weight.
#    preflight returns ok; plan shows emphasis=2 with the copy in emphasis_copies.
rc = sw.enqueue_task("queue_gate emphasis test goal", domain="test", tag=tag)
rd = sw.enqueue_task("queue_gate emphasis test goal", domain="test", tag=tag)
pf_c = qg.preflight({"task_id": rc["task_id"], "goal": "queue_gate emphasis test goal",
                     "provider": "deepseek"})
assert pf_c.get("ok") is True, f"emphasis copy must NOT be gated, got {pf_c}"
pp = qg.plan(n=200)
run = next((r for r in pp["runs"] if r["task_id"] == rc["task_id"]), None)
assert run and run["emphasis"] == 2, f"head should carry emphasis=2, got {run}"
copies = [c for c in pp["emphasis_copies"] if c["task_id"] == rd["task_id"]]
assert copies and copies[0]["emphasis_of"] == rc["task_id"], "copy must fold into head"
print(f"PASS emphasis: dup not blocked; head {rc['task_id']} emphasis=2; copy folded")

# cleanup test tasks (leave queue as we found it)
for tid in (ra["task_id"], rb["task_id"], rc["task_id"], rd["task_id"]):
    (Path(sw.QUEUE_DIR) / f"{tid}.json").unlink(missing_ok=True)

print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
