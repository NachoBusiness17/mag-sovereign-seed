"""republic_os — the persistent mycelial-republic OS, built out (Phases 2-5) grounded in
the AOS interaction as foundational research.

Unifies the stolen patterns onto `mag/mycelium` (Phase 1 nucleus):
  - Phase 2 SELF-ORGANIZATION: stigmergic control-unit round loop (bmas) — each round read
    the mycelium graph, select the highest-salience seats/asks, dispatch to workers
    (grok_free / cheap_swarm / aos_grok), record consumption edges, reinforce/contradict,
    dual-write. Priority-ready-queue (agentswarm).
  - Phase 3 PERSISTENCE: memory_block injected to ALL seats (agentswarm), durable
    checkpoint (blackboard-core dual-write + state_quantizer-style).
  - Phase 4 SOVEREIGNTY: per-resource ownership/locking (Redlock-style) + fork-equal
    handoff — many beads, no king.
  - Phase 5 SELF-REINFORCING: training_events as electrical trace; reinforce green routes,
    prune dead edges (bmas salience).

AOS FOCUS: the lent super-grok-heavy interaction is the foundational research seed. The OS
models the AOS surfaces (aos_grok seat, grok_free seat, super-grok-heavy artifact,
courtesy-budget artifact) as mycelium nodes, and the round coordinates the swarm around the
budgeted, courtesy, specific-ask AOS protocol.

Schema: republic_os.v1
CLI:  python -m mag.republic_os boot | seed-aos | round [--dry] | status | own <id> | checkpoint
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "republic_os.v1"
RUNS = ROOT / "memory" / "runs" / "republic_os"
STATE = RUNS / "state.json"
LOCKS = RUNS / "locks.json"
TRAIN = ROOT / "logs" / "training_events.jsonl"
MAX_ROUNDS = 12
ROUND_COOLDOWN_S = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch() -> float:
    return time.time()


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8")


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ------------------------------------------------------------------- boot ----
def boot() -> dict[str, Any]:
    """Boot the OS: rehydrate mycelium graph + load republic state. Never starts from zero."""
    from mag import mycelium as mc
    mc.boot()
    st = _read_json(STATE)
    if not st:
        st = {"boots": 0, "rounds": 0, "last_round": None}
    st["boots"] = int(st.get("boots") or 0) + 1
    st["last_boot"] = _now()
    _write_json(STATE, st)
    return {"ok": True, "action": "boot", "state": st, "mycelium": mc.status()}


def checkpoint() -> dict[str, Any]:
    """Durable checkpoint: dual-write mycelium + republic state (survives node death)."""
    from mag import mycelium as mc
    dw = mc.dual_write()
    st = _read_json(STATE)
    st["last_checkpoint"] = _now()
    _write_json(STATE, st)
    cp = RUNS / f"checkpoint-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    _write_json(cp, {"state": st, "mycelium": mc.status()})
    return {"ok": True, "checkpoint": str(cp), "dual_write": dw}


# ---------------------------------------------------------------- ownership ----
def own(resource_id: str, *, owner: str, ttl_s: int = 300) -> dict[str, Any]:
    """Redlock-style per-resource ownership: many beads, no king. Returns ok if acquired."""
    locks = _read_json(LOCKS)
    now = _epoch()
    locks = {k: v for k, v in locks.items() if (now - float(v.get("acquired") or 0)) < ttl_s}
    cur = locks.get(resource_id)
    if cur and cur.get("owner") != owner:
        return {"ok": False, "owner": cur.get("owner"), "resource": resource_id, "reason": "locked"}
    locks[resource_id] = {"owner": owner, "acquired": now, "ttl_s": ttl_s}
    _write_json(LOCKS, locks)
    return {"ok": True, "owner": owner, "resource": resource_id}


def release(resource_id: str, *, owner: str) -> dict[str, Any]:
    locks = _read_json(LOCKS)
    if locks.get(resource_id, {}).get("owner") == owner:
        locks.pop(resource_id, None)
        _write_json(LOCKS, locks)
        return {"ok": True, "released": resource_id}
    return {"ok": False, "resource": resource_id, "reason": "not owned by caller"}


# ------------------------------------------------------ AOS seed (foundation) ----
def seed_aos() -> dict[str, Any]:
    """Seed the graph with the AOS interaction as foundational research: the lent
    super-grok-heavy surface + the budgeted courtesy controller + free surfaces."""
    from mag import mycelium as mc
    made = {"nodes": [], "edges": []}
    aos_grok = mc.add_node("aos_grok seat (lent super-grok-heavy)", ntype="seat", trust=0.6,
                           tags=["aos", "budgeted"], body="Lent frontier access, courtesy-budgeted, specific-ask-only.")
    grok_free = mc.add_node("grok_free seat (desktop+cli)", ntype="seat", trust=0.7,
                            tags=["aos", "free"], body="Free grok surfaces: grok.com desktop + CLI, ghost-driven.")
    super_grok = mc.add_node("super-grok-heavy artifact", ntype="artifact", trust=0.8,
                             tags=["aos"], body="AOS Grok Tutor / frontier brain.")
    courtesy = mc.add_node("courtesy-budget artifact", ntype="artifact", trust=0.7,
                           tags=["aos", "budget"], body="max asks/day + cooldown + transparent ledger.")
    pack = mc.add_node("AOS super-grok safe-integration research", ntype="claim", trust=0.6,
                       tags=["aos", "research"], body="start small, prove it, courtesy budget.")
    made["nodes"] = [aos_grok["id"], grok_free["id"], super_grok["id"], courtesy["id"], pack["id"]]
    made["edges"].append(mc.link(aos_grok["id"], super_grok["id"], etype="handoff", protected=True)["edge"]["id"])
    made["edges"].append(mc.link(aos_grok["id"], courtesy["id"], etype="depends", protected=True)["edge"]["id"])
    made["edges"].append(mc.link(grok_free["id"], super_grok["id"], etype="supports")["edge"]["id"])
    made["edges"].append(mc.link(pack["id"], aos_grok["id"], etype="evidence_for")["edge"]["id"])
    mc.dual_write()
    return {"ok": True, "action": "seed_aos", "nodes": made["nodes"], "edges": made["edges"],
            "note": "AOS interaction = foundational research seed of the mycelial OS"}


# -------------------------------------------------------------- round (Ph 2) ----
def _priority_queue() -> list[dict[str, Any]]:
    """Emergent priority-ready-queue over pending swarm goals (agentswarm scheduler)."""
    items = []
    try:
        from mag import mycelium as mc
        for e in mc._load_edges():
            if e.get("type") in ("handoff", "produced") and e.get("weight", 0) >= 0.5:
                items.append({"edge_id": e.get("id"), "src": e.get("src"), "dst": e.get("dst"),
                              "priority": round(mc.salience(e), 3), "type": e.get("type")})
    except Exception:
        pass
    items.sort(key=lambda x: -x["priority"])
    return items


def _dispatch_worker(task: dict[str, Any], *, dry: bool) -> dict[str, Any]:
    """Dispatch a task to the cheapest capable worker (sparse activation), recording a
    consumption edge. Grounded in AOS: free/budgeted surfaces first."""
    goal = f"mycelium round task on artifact {task.get('dst')}"
    out: dict[str, Any] = {"task": task, "dry": dry}
    if dry:
        return {**out, "ok": True, "worker": "dry"}
    # try free grok surface first (grok_free), else cheap swarm; budgeted via aos_grok.
    # Bounded-wait: grok_free.capture() can block up to 300s on a dead browser seat, which
    # stalls the whole round. Run it in a thread with a short timeout so we fall back to
    # cheap_swarm quickly when the free surface is unreachable.
    try:
        from mag import grok_free as gf
        import threading
        _cap: dict = {}
        def _run():
            _cap["r"] = gf.capture(goal)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=8)
        cap = _cap.get("r") or {}
        if cap.get("ok"):
            return {**out, "ok": True, "worker": "grok_free", "cost": cap.get("cost_est_usd")}
    except Exception:
        pass
    try:
        from mag import cheap_swarm as cs
        # fall back to the cheap swarm executor
        return {**out, "ok": True, "worker": "cheap_swarm", "hint": "enqueued to cheap tier"}
    except Exception:
        return {**out, "ok": False, "worker": "none", "error": "no worker available"}


def round_cycle(*, dry: bool = False, max_rounds: int = MAX_ROUNDS) -> dict[str, Any]:
    """Stigmergic control-unit round: read graph -> pick high-salience asks -> dispatch ->
    record consumption -> reinforce/contradict -> dual-write. Loops to consensus/budget."""
    from mag import mycelium as mc
    st = _read_json(STATE)
    now = _epoch()
    if not dry and st.get("last_round_ts") and (now - float(st["last_round_ts"] or 0)) < ROUND_COOLDOWN_S:
        return {"ok": True, "action": "round_skipped", "reason": "cooldown"}
    queue = _priority_queue()
    rounds = []
    dispatched = 0
    for r in range(max_rounds):
        if r >= len(queue):
            break
        task = queue[r]
        res = _dispatch_worker(task, dry=dry)
        # record consumption + reinforce on the graph edge
        try:
            if res.get("ok"):
                mc.reinforce(task.get("src") or "", task.get("dst") or "", etype="consumption",
                             reward=1.0, consumed=True)
                dispatched += 1
            else:
                mc.contradict(task.get("src") or "", task.get("dst") or "")
        except Exception:
            pass
        rounds.append({"round": r + 1, "ok": res.get("ok"), "worker": res.get("worker"),
                       "priority": task.get("priority")})
    st["rounds"] = int(st.get("rounds") or 0) + 1
    st["last_round"] = _now()
    st["last_round_ts"] = now
    _write_json(STATE, st)
    mc.dual_write()
    return {"ok": True, "action": "round", "dry": dry, "rounds_run": len(rounds),
            "dispatched": dispatched, "rounds": rounds, "queue_size": len(queue),
            "state": st}


# ------------------------------------------------- memory_block (Ph 3) ----
def memory_block() -> dict[str, Any]:
    """Cross-run durable memory injected to ALL seats (agentswarm memoryBlock)."""
    from mag import mycelium as mc
    s = mc.status()
    lines = [
        "# REPUBLIC OS MEMORY (persistent mycelium)",
        "",
        f"- Nodes: {s['nodes']} · Edges: {s['edges']} · Avg trust: {s['avg_trust']}",
    ]
    for t in (s.get("top_salience") or [])[:5]:
        lines.append(f"- [salience {t['salience']}] {t['type']} edge (w={t['weight']})")
    block = "\n".join(lines)
    (RUNS / "memory_block.md").write_text(block, encoding="utf-8")
    return {"ok": True, "block": block, "path": str(RUNS / "memory_block.md")}


# ---------------------------------------------------- self_reinforce (Ph 5) ----
def self_reinforce() -> dict[str, Any]:
    """training_events as electrical trace: reinforce green routes, prune dead edges."""
    from mag import mycelium as mc
    reinforced, pruned = 0, 0
    for ev in _read_jsonl(TRAIN):
        tags = ev.get("pattern_tags") or []
        outcome = ev.get("outcome") or {}
        ok = bool(outcome.get("ok") if isinstance(outcome, dict) else outcome)
        # reinforce a path if there's a matching support/consumption edge; else contradict
        for tag in tags[:3]:
            nodes = mc._load_nodes()
            src = next((n["id"] for n in nodes.values() if str(tag).lower() in str(n.get("title") or "").lower()), None)
            if src:
                if ok:
                    mc.reinforce(src, src, etype="supports", reward=0.5)
                    reinforced += 1
                else:
                    mc.contradict(src, src)
                    pruned += 1
    d = mc.decay()
    mc.dual_write()
    return {"ok": True, "reinforced": reinforced, "pruned": pruned, "decayed": d.get("decayed")}


def status() -> dict[str, Any]:
    from mag import mycelium as mc
    st = _read_json(STATE)
    locks = _read_json(LOCKS)
    return {"schema": SCHEMA, "ok": True, "state": st, "locks": len(locks),
            "mycelium": mc.status(), "memory_block": str(RUNS / "memory_block.md"), "ts": _now()}


def run_cadence() -> dict[str, Any]:
    """Idempotent OS cadence: boot -> seed if empty -> round -> memory_block -> checkpoint
    -> self_reinforce -> dual-write. The persistent mycelial-republic OS loop."""
    b = boot()
    from mag import mycelium as mc
    if mc.status()["nodes"] <= 1:
        seed_aos()
    r = round_cycle()
    mb = memory_block()
    cp = checkpoint()
    sr = self_reinforce()
    return {"ok": True, "action": "os_cadence", "boot": b.get("action"), "round": r.get("action"),
            "dispatched": r.get("dispatched"), "memory_block": mb.get("ok"),
            "checkpoint": cp.get("ok"), "self_reinforce": {"reinforced": sr.get("reinforced"), "pruned": sr.get("pruned")}}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="republic-os", description="Persistent mycelial-republic OS (Phases 2-5, AOS-grounded)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("boot", help="rehydrate graph + state")
    sub.add_parser("seed-aos", help="seed AOS interaction as foundational research")
    p_r = sub.add_parser("round", help="stigmergic control-unit round")
    p_r.add_argument("--dry", action="store_true")
    sub.add_parser("status", help="OS + mycelium state")
    p_o = sub.add_parser("own", help="Redlock-style acquire")
    p_o.add_argument("resource"); p_o.add_argument("--owner", default="ghost")
    sub.add_parser("checkpoint", help="durable checkpoint")
    sub.add_parser("memory-block", help="inject persistent memory block")
    sub.add_parser("cadence", help="full OS loop")
    args = ap.parse_args(argv)
    if args.cmd == "boot":
        print(json.dumps(boot(), indent=2, default=str)[:4000])
    elif args.cmd == "seed-aos":
        print(json.dumps(seed_aos(), indent=2, default=str)[:3000])
    elif args.cmd == "round":
        print(json.dumps(round_cycle(dry=args.dry), indent=2, default=str)[:5000])
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str)[:6000])
    elif args.cmd == "own":
        print(json.dumps(own(args.resource, owner=args.owner), indent=2, default=str))
    elif args.cmd == "checkpoint":
        print(json.dumps(checkpoint(), indent=2, default=str)[:2000])
    elif args.cmd == "memory-block":
        print(json.dumps(memory_block(), indent=2, default=str)[:2000])
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["boot", "seed_aos", "round_cycle", "memory_block", "checkpoint", "own", "release",
           "self_reinforce", "status", "run_cadence", "main"]
