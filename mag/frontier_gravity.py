"""frontier_gravity — frontier advice as GRAVITY that changes operation (Titor-sinusoidal).

OPERATOR (2026-08-12): "understand what frontier advice looks like, where to find it, and how to
use it most effectively as a gravity that changes our operation titor sinosoidal time machine style."

EXTERNAL-STEAL (active inference / free energy principle — Friston, pymdp):
  "We define the preferred observations as a separate goal vector C … the agent chooses actions to
  increase the probability of observing itself in its preferred state." Self-organization is
  ATTRACTION to preferred states: the agent does not follow commands — it minimizes expected free
  energy by continuously moving toward C, oscillating + self-correcting around the target
  (sinusoidal). TITOR: the advice is the "future" preferred state the present moves toward —
  time-shifted, deniable, self-steering.

SELF-STEAL (reuse, not invent): attractor_tools (roshomon -> memlang chord -> swarm attractor),
bernaise (plant-not-command), frontier_advisor/council (scarce allowance -> folded advice).

ADAPTATION (deterministic, architecture-native, pure stdlib):
  * ADVICE -> C VECTOR: folded frontier-advice reports (memory/runs/frontier_advice/) are distilled
    into preferred-state attractors (steer directions + weights) — the gravity the operation is
    pulled toward.
  * GRAVITY DISTANCE (free-energy proxy): deterministic measure of how far the current operation
    (recent routed/refined/mined items) is from the preferred-state C — drives self-correction.
  * RE-PLANT (bernaise plant-not-command): the top attractors are planted into the shared map so the
    operation is continuously PULLED toward C, not commanded. Idempotent + recorded.

Schema: frontier_gravity.v1 · deterministic + $0 · pure stdlib
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "frontier_gravity.v1"
ADVICE_DIR = ROOT / "memory" / "runs" / "frontier_advice"     # where frontier_advisor folds advice
GRAVITY_DIR = ROOT / "memory" / "frontier_gravity"
LEDGER = GRAVITY_DIR / "gravity.jsonl"                          # recordable: every gravity pull

# Operational surfaces we read to measure "current operation" (deterministic, $0).
_CURRENT_SOURCES = [
    ROOT / "memory" / "arxiv_mine" / "ledger.jsonl",            # mined-arxiv titles
    ROOT / "memory" / "working" / "refine_chains" / "index.jsonl",  # refine chain goals
    ROOT / "memory" / "swarm_surface" / "sent.jsonl",           # routed research goals
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def advice_attractors(*, top: int = 20) -> dict[str, Any]:
    """Distill folded frontier-advice into preferred-state attractors (the C vector = gravity)."""
    if not ADVICE_DIR.is_dir():
        return {"ok": True, "schema": SCHEMA, "n_attractors": 0, "attractors": [],
                "note": "no folded frontier-advice yet — dispatch [frontier-advice] goals"}
    rows: list[dict[str, Any]] = []
    for p in sorted(ADVICE_DIR.glob("advice_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        answer = str(d.get("answer") or "")
        goal = str(d.get("goal") or "")
        surface = str(d.get("surface") or "?")
        # steer directions = substantive lines of the answer (preferred states), weighted.
        seen = set()
        for line in answer.splitlines():
            line = _clean(line)
            if len(line) < 24:  # too short to be a steer
                continue
            if line in seen:
                continue
            seen.add(line)
            rows.append({
                "steer": line[:180], "weight": 1.0, "surface": surface,
                "goal": goal[:100], "source": p.name,
            })
    rows = rows[:top]
    return {"ok": True, "schema": SCHEMA, "n_attractors": len(rows),
            "note": "frontier advice distilled to preferred-state attractors (C vector)",
            "attractors": rows}


def _current_corpus() -> str:
    """Gather a deterministic snapshot of the current operation's vocabulary."""
    parts: list[str] = []
    for path in _CURRENT_SOURCES:
        for r in _read_jsonl(path):
            for k in ("title", "goal", "claim", "detail", "surface"):
                v = r.get(k)
                if isinstance(v, str):
                    parts.append(v)
    return " ".join(parts).lower()


def gravity_distance() -> dict[str, Any]:
    """Free-energy proxy: how far is the current operation from the preferred-state C?
    0.0 = perfectly aligned (at the attractor); 1.0 = maximally off (needs the pull)."""
    attrs = advice_attractors()
    attractors = attrs.get("attractors") or []
    if not attractors:
        return {"ok": True, "schema": SCHEMA, "distance": 1.0, "n_attractors": 0,
                "note": "no preferred states yet"}
    cur = _current_corpus()
    tokens = set(re.findall(r"[a-z]{3,}", cur))
    aligned = 0
    for a in attractors:
        steer_tokens = set(re.findall(r"[a-z]{3,}", str(a["steer"]).lower()))
        if not steer_tokens:
            continue
        # alignment = fraction of the steer's substantive tokens present in current operation
        overlap = len(steer_tokens & tokens) / len(steer_tokens)
        aligned += overlap * float(a.get("weight") or 1.0)
    n = max(1, len(attractors))
    alignment = aligned / n
    return {"ok": True, "schema": SCHEMA, "distance": round(1.0 - alignment, 4),
            "alignment": round(alignment, 4), "n_attractors": len(attractors),
            "note": "distance 0 = at the attractor; 1 = far from the advice (gravity should pull)"}


def apply_gravity(*, top: int = 5, dry: bool = False) -> dict[str, Any]:
    """Re-plant the strongest attractors (bernaise plant-not-command) so the operation is PULLED
    toward the preferred-state C — gravity that changes operation, not a command. Records each pull.
    Idempotent (bernaise + content hash)."""
    attrs = advice_attractors()
    attractors = attrs.get("attractors") or []
    if not attractors:
        return {"ok": False, "schema": SCHEMA, "error": "no frontier-advice attractors yet"}
    dist = gravity_distance()
    planted = 0
    results = []
    GRAVITY_DIR.mkdir(parents=True, exist_ok=True)
    for a in attractors[:top]:
        move = str(a.get("steer") or "")[:240]
        if not move:
            continue
        if dry:
            results.append({"planted": False, "dry": True, "steer": move[:100]})
            continue
        try:
            from mag import bernaise
            r = bernaise.plant(move, signature=_hash(move),
                               goal=f"frontier-gravity pull from {a.get('surface')}",
                               source="frontier_gravity")
        except Exception as e:
            results.append({"planted": False, "steer": move[:100], "error": str(e)[:120]})
            continue
        row = {"schema": SCHEMA, "ts": _now(), "steer": move[:160],
               "surface": a.get("surface"), "planted": bool(r.get("ok")),
               "distance": dist.get("distance"), "source": a.get("source")}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        planted += 1 if r.get("ok") else 0
        results.append({"planted": bool(r.get("ok")), "steer": move[:100],
                        "detail": (r.get("detail") or r.get("steer_token") or "")[:80]})
    return {"ok": True, "schema": SCHEMA, "n_pulls": len(results), "planted": planted,
            "distance_before": dist.get("distance"), "dry": dry, "pulls": results}


CLUSTER_DESIRED = GRAVITY_DIR / "cluster_desired.json"  # layer 2 desired-state manifest (plan)


def deploy_to_swarm(*, top: int = 8, dry: bool = False) -> dict[str, Any]:
    """LAYER 1 — Swarm guidance: inject the frontier-gravity C attractors into the swarm's
    three-body action-RIB (rib_action) so the in-cluster agents are PULLED toward the advice.
    Deterministic, $0 (local flock dynamics; the k8s workers share the same action field)."""
    attrs = advice_attractors(top=top)
    attractors = attrs.get("attractors") or []
    if not attractors:
        return {"ok": True, "schema": SCHEMA, "action": "skip", "reason": "no attractors yet"}
    try:
        from mag import rib_action as ra
        spec = [{"id": f"grav_{i}", "action": str(a.get("steer") or "")[:180],
                 "radius": 0.3, "weight": float(a.get("weight") or 1.0)}
                for i, a in enumerate(attractors)]
        if dry:
            return {"ok": True, "schema": SCHEMA, "action": "dry", "n_slots": len(spec),
                    "spec": [{"id": s["id"], "action": s["action"]} for s in spec]}
        rib = ra.declare(spec)
        for a in attractors[:top]:
            ra.influence(rib, action=str(a.get("steer") or "")[:180], strength=1.5)
        run = ra.run_three_body(rib, steps=40, seed=3)
        return {"ok": True, "schema": SCHEMA, "action": "deployed", "n_slots": len(rib.slots),
                "collective": run.get("goal"), "actions": run.get("actions")}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "action": "error", "error": str(e)[:160]}


def cluster_desired_state(*, dry: bool = True) -> dict[str, Any]:
    """LAYER 2 — Kubernetes k8s/k3s steering: distill the C vector into a cluster DESIRED-STATE
    manifest (worker focus / CronJob priorities / resource policy). PLAN by default (dry) — never
    auto-mutates a live cluster without the explicit MAG_FRONTIER_GRAVITY_APPLY_CLUSTER=live gate.
    The guard_registry / k8s_bridge reconciler pulls actual -> desired (the reconcile loop IS the
    sinusoid)."""
    attrs = advice_attractors(top=6)
    attractors = attrs.get("attractors") or []
    manifest = {
        "schema": SCHEMA, "layer": "cluster", "ts": _now(),
        "gravity_distance": gravity_distance().get("distance"),
        "focus": [str(a.get("steer") or "")[:80] for a in attractors[:6]],
        "n_focus": len(attractors),
        "reconciler": "guard_registry / k8s_bridge (observe -> diff -> apply -> re-observe)",
        "apply_gate": "PLAN only unless MAG_FRONTIER_GRAVITY_APPLY_CLUSTER=live",
        "applied": False,
    }
    live = (os.environ.get("MAG_FRONTIER_GRAVITY_APPLY_CLUSTER", "").strip().lower()
            in ("live", "1", "true"))
    if dry or not live:
        return {"ok": True, "schema": SCHEMA, "action": "plan", "manifest": manifest,
                "note": "dry by default — set MAG_FRONTIER_GRAVITY_APPLY_CLUSTER=live to reconcile"}
    GRAVITY_DIR.mkdir(parents=True, exist_ok=True)
    CLUSTER_DESIRED.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest["applied"] = True
    return {"ok": True, "schema": SCHEMA, "action": "reconciled", "manifest": manifest,
            "desired_file": str(CLUSTER_DESIRED.relative_to(ROOT)).replace("\\", "/")}


def steer_systems(*, top: int = 5, dry: bool = True) -> dict[str, Any]:
    """LAYER 3 — the shared gravity bus: return the C vector + apply the pull across every
    reconciler-driven surface (local bernaise plant + swarm three-body + cluster desired-state).
    One gravity source, many pulled systems. Tangential systems (docker/memory/dashboard/cadence)
    read the same C vector to pull their own reconcilers."""
    c = advice_attractors(top=top)
    pull = None if dry else apply_gravity(top=top, dry=False)
    swarm = deploy_to_swarm(top=top, dry=dry)
    cluster = cluster_desired_state(dry=dry)
    return {"ok": True, "schema": SCHEMA, "n_attractors": c.get("n_attractors"),
            "attractors": c.get("attractors"),
            "gravity": {"pull_planted": (pull.get("planted") if pull else None),
                         "distance": gravity_distance().get("distance")},
            "surfaces": {"swarm": swarm.get("action"), "cluster": cluster.get("action"),
                         "local_plant": bool(pull.get("planted")) if pull else None},
            "cluster_manifest": cluster.get("manifest")}


def run_cadence(*, dry: bool = False, top: int = 5) -> dict[str, Any]:
    """Cadence hook (always-on): consume folded frontier-advice and apply the gravity pull across
    every reconciler surface — local bernaise plant + swarm three-body + cluster desired-state.
    Skips cleanly when no advice has landed. Swarm runs locally; cluster is PLAN-only (never
    auto-mutates a live cluster on cadence). Deterministic, $0."""
    if not ADVICE_DIR.is_dir() or not any(ADVICE_DIR.glob("advice_*.json")):
        return {"ok": True, "action": "skip", "reason": "no folded frontier-advice yet"}
    out = {"ok": True, "action": "gravity", "ts": _now()}
    try:
        p = apply_gravity(top=top, dry=dry)
        out["local_planted"] = p.get("planted")
    except Exception as e:
        out["local_error"] = str(e)[:120]
    try:
        sw = deploy_to_swarm(top=top, dry=dry)
        out["swarm"] = sw.get("action")
        out["swarm_slots"] = sw.get("n_slots")
    except Exception as e:
        out["swarm_error"] = str(e)[:120]
    try:
        cl = cluster_desired_state(dry=True)  # always plan on cadence; never mutate the cluster
        out["cluster"] = cl.get("action")
        out["cluster_distance"] = (cl.get("manifest") or {}).get("gravity_distance")
    except Exception as e:
        out["cluster_error"] = str(e)[:120]
    try:
        out["distance"] = gravity_distance().get("distance")
    except Exception:
        pass
    return out


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def status() -> dict[str, Any]:
    pulls = _read_jsonl(LEDGER)
    planted = sum(1 for r in pulls if r.get("planted"))
    return {"ok": True, "schema": SCHEMA,
            "contract": "advice_attractors() = frontier advice -> preferred-state C vector; "
                        "gravity_distance() = free-energy proxy (0 aligned .. 1 far); "
                        "apply_gravity() = bernaise plant the pull; deploy_to_swarm() = L1 swarm "
                        "three-body attractors; cluster_desired_state() = L2 k8s/k3s desired-state "
                        "(plan); steer_systems() = L3 shared gravity bus. Titor-sinusoidal: the "
                        "advice is the future preferred state every reconciler is pulled toward.",
            "reuse": "frontier_advisor (fold) + attractor_tools/rib_action (swarm) + bernaise "
                      "(plant) + guard_registry/k8s_bridge (cluster reconciler)",
            "n_pulls": len(pulls), "n_planted": planted,
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
            "cluster_desired": str(CLUSTER_DESIRED.relative_to(ROOT)).replace("\\", "/")}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="frontier_gravity")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("attractors")
    sub.add_parser("distance")
    g = sub.add_parser("apply")
    g.add_argument("--top", type=int, default=5)
    g.add_argument("--dry", action="store_true")
    sub.add_parser("swarm")
    sub.add_parser("cluster")
    sub.add_parser("steer")
    sub.add_parser("cadence")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "attractors":
        print(json.dumps(advice_attractors(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "distance":
        print(json.dumps(gravity_distance(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "apply":
        print(json.dumps(apply_gravity(top=a.top, dry=a.dry), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "swarm":
        print(json.dumps(deploy_to_swarm(top=a.top or 8, dry=a.dry), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "cluster":
        print(json.dumps(cluster_desired_state(dry=True), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "steer":
        print(json.dumps(steer_systems(top=a.top or 5, dry=True), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "cadence":
        print(json.dumps(run_cadence(dry=a.dry, top=a.top or 5), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
