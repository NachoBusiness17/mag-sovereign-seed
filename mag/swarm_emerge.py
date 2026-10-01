"""swarm_emerge — surface the core self-improve loop NATIVELY through swarm detection.

Operator (2026-08-11): "surfacing them through swarm detection natively amongst other tasks right
sized across swarms and subswarms like i am tasking you with agents. this entire verkle exercise is
a start to finish lesson on how to do that with rich data from me."

THE PATTERN (deterministic + $0 at dispatch; execution runs in the k8s/swarm worker):
  detect()  -> the SWARM-DETECTION lens: find where the swarm should spend (the seams/gaps):
               explore backlog, research_class gaps (thinnest cells), shadow latent clusters,
               live usage spike. Each becomes a right-sized task spec with a domain/provider/tag.
  fanout()  -> enqueue the detected tasks NATIVELY via mag.swarm_worker.enqueue_task (shared queue,
               k8s worker drains). Right-size: cap by budget + priority; each subswarm handles one
               piece of the core loop (fold+classify, latent discovery, gap-fill, world-compile).
  surface() -> read the emergence grid + swarm queue and surface "what the swarm is detecting and
               doing" — the shared field (stigmergy) the subswarms contribute to.

Schema: swarm_emerge.v1 · deterministic + $0 at dispatch · reuse: emergence, research_class,
shadow_graph, usage_monitor, swarm_worker, novelty_lens.
"""
from __future__ import annotations

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

SCHEMA = "swarm_emerge.v1"
MAX_FANOUT = 8


def _rdl(path: Path, tail: int = 100_000) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def detect() -> dict[str, Any]:
    """SWARM DETECTION: the seams/gaps where the swarm should spend (right-sized task specs)."""
    tasks: list[dict[str, Any]] = []
    # 1) explore backlog (novel signal waiting to be explored+folded)
    for r in _rdl(ROOT / "memory" / "percolator" / "explore.jsonl"):
        if r.get("status") == "open":
            tasks.append({"kind": "fold_classify", "domain": r.get("domain") or "general",
                          "goal": ("FOLD+CLASSIFY: percolate this novel signal through the core loop "
                                   f"and classify it through the one lens: {str(r.get('signal'))[:200]}"),
                          "provider": "deepseek", "tag": "swarm-emerge-fold", "priority": 1})
    # 2) thinnest cells (gaps) -> build from mirrored tools
    try:
        from mag import research_class as rc
        for g in rc.gaps(6)["gaps"][:4]:
            cell = g["cell"]
            tools = g["plan"].get("mirrored_tools") or []
            tasks.append({"kind": "gap_fill", "domain": cell.split(":")[0], "goal": (
                f"GAP-FILL: the (domain,kind) cell '{cell}' is thinnest. Compose/adapt the mirrored "
                f"tools {', '.join(tools[:4])} to cover it, then fold through research_class."),
                "provider": "deepseek", "tag": "swarm-emerge-gap", "priority": 2})
    except Exception:
        pass
    # 3) latent shadow clusters -> RIBs on the fly
    try:
        from mag import shadow_graph as sg
        j = sg.jungal_loop(top=2, emit_rib=False)
        for c in j.get("clusters", []):
            tasks.append({"kind": "latent", "domain": c.get("lens") or "general", "goal": (
                f"LATENT: the garbage keeps repeating '{c['pair'][0]} {c['pair'][1]}' (weight "
                f"{c['weight']}). Apply current knowledge, route via the {c.get('lens')} lens, emit "
                f"a coherent RIB for the vmemory/k8 swarm."), "provider": "deepseek",
                "tag": "swarm-emerge-latent", "priority": 2})
    except Exception:
        pass
    # 4) live usage spike -> route/guard before it hits
    try:
        from mag import usage_monitor
        w = usage_monitor.watch()
        if w.get("is_spike"):
            tasks.append({"kind": "usage_guard", "domain": "economics", "goal": (
                f"USAGE-GUARD: live cache-miss spike (miss={w.get('miss_tokens')}). Preserve the "
                "stable prefix and route the volatile tail to cheap/free before the 50x tax hits."),
                "provider": "deepseek", "tag": "swarm-emerge-usage", "priority": 0})
    except Exception:
        pass
    tasks.sort(key=lambda t: t.get("priority", 5))
    return {"ok": True, "schema": SCHEMA, "n_detected": len(tasks), "tasks": tasks}


def fanout(*, max_tasks: int = MAX_FANOUT, dry: bool = True) -> dict[str, Any]:
    """Right-size + enqueue the detected tasks NATIVELY via swarm_worker. dry=True = plan ($0)."""
    det = detect()
    chosen = det["tasks"][:max_tasks]
    dispatched = []
    for t in chosen:
        if dry:
            dispatched.append({"task": t["goal"][:120], "domain": t["domain"],
                               "tag": t["tag"], "dry": True})
            continue
        try:
            from mag import swarm_worker
            r = swarm_worker.enqueue_task(t["goal"], provider=t.get("provider", "deepseek"),
                                          domain=t.get("domain", "general"), tag=t.get("tag", "swarm-emerge"))
            dispatched.append({"ok": r.get("ok"), "task_id": r.get("task_id"),
                               "tag": t.get("tag"), "domain": t.get("domain")})
        except Exception as e:
            dispatched.append({"error": str(e)[:120], "tag": t.get("tag")})
    return {"ok": True, "schema": SCHEMA, "n_detected": det["n_detected"],
            "n_dispatched": len(dispatched), "dry": dry, "dispatched": dispatched}


def surface(*, grid_tail: int = 10) -> dict[str, Any]:
    """Surface what the swarm is detecting + doing, through the emergence grid (shared field)."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "detect": detect()["tasks"][:3]}
    try:
        from mag import emergence
        g = _rdl(emergence.GRID, grid_tail)
        out["grid_rows"] = len(g)
        out["emergence"] = emergence.emergence(grid_tail)
        if g:
            out["last_cycle_deltas"] = g[-1].get("deltas", {})
    except Exception as e:
        out["emergence"] = {"error": str(e)[:120]}
    try:
        from mag.swarm_worker import QUEUE_DIR
        if QUEUE_DIR.is_dir():
            files = [f for f in QUEUE_DIR.glob("*.json")]
            queued = sum(1 for f in files if _rdl(f, 1) and _rdl(f, 1)[0].get("status") == "queued")
            out["swarm_queued"] = queued
    except Exception:
        pass
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "detect()->seams/gaps as right-sized tasks; fanout(dry)->enqueue natively "
                        "to the swarm queue; surface()->emergence grid + swarm status",
            "cost": "deterministic + $0 at dispatch (execution runs in k8s/swarm worker)",
            "max_fanout": MAX_FANOUT}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-emerge")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "detect", "fanout", "surface"])
    ap.add_argument("--live", action="store_true", help="fanout: actually enqueue (not dry)")
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "detect":
        print(json.dumps(detect(), indent=2, default=str))
    elif a.cmd == "fanout":
        print(json.dumps(fanout(dry=not a.live), indent=2, default=str))
    else:
        print(json.dumps(surface(), indent=2, default=str))
