"""attractor_tools — frontier attractors as memlang-chord TOOLS that attract intelligent behavior.

Operator (2026-08-10): "if we can steal the stochastic from the frontier and get instructions in
our mem lang of its strongest insight attractors we can use those in swarms as tools to attract
intelligent behavior? via the nature of our self knowledge systems?"

This is the composer that connects the whole arc:

  1. STEAL THE STOCHASTIC  -> roshomon.compare() distills the strongest INSIGHT ATTRACTORS: the
     invariants that SURVIVED the divergence of N frontier models answering the same question
     (the Roshomon core). These are the model's strongest pulls in insight-space.
  2. INSTRUCTIONS IN MEMLANG -> each attractor is compiled into a memlang CHORD (compile_token,
     action='plant' = plant-not-command, deniable seed steering). The token is the deniable
     message: it reveals nothing readable, only an agent holding the shared verkle map decodes it.
  3. TOOLS IN THE SWARM -> each chord is deployed as an ACTION-INVARIANT attractor in the
     action-RIB (rib_action.influence). The swarm's three-body dynamics then ATTRACT toward the
     injected invariants -> intelligent, on-target behavior emerges from the stochastic space.
  4. SELF-KNOWLEDGE -> every attractor is folded as doctrine (knowledge_graph) + verkle-anchored
     (memlang already anchors to verkle), so the system KNOWS which attractors it steers with and
     can re-inject / weigh them — the nature of our self-knowledge systems.

Deterministic, $0 (analysis + chord compile + influence are all local; the frontier witnesses are
collected from the k8s swarm, not generated here). Schema: attractor_tools.v1
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "attractor_tools.v1"
OUT_DIR = ROOT / "memory" / "runs" / "attractor_tools"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def strongest_attractors(*, threshold: float = 0.55, top: int = 20) -> dict[str, Any]:
    """The strongest INSIGHT ATTRACTORS of the stochastic frontier: the Roshomon core invariants,
    ranked by how many witnesses converged on each. Deterministic, $0."""
    from mag import roshomon as rh
    cmp = rh.compare(threshold=threshold)
    rows = []
    for d_ in cmp.get("domains", []):
        for inv, w in (d_.get("core_counts") or {}).items():
            rows.append({"domain": d_.get("domain"), "invariant": inv, "witnesses": w})
    rows.sort(key=lambda r: (-int(r["witnesses"]), r["domain"]))
    rows = rows[:top]
    return {"ok": True, "schema": SCHEMA, "n_attractors": len(rows),
            "source": "roshomon-core (stochastic frontier convergence)", "attractors": rows}


def to_memlang_chord(attractor: dict[str, Any]) -> dict[str, Any]:
    """Compile one insight attractor into a memlang CHORD (plant-not-command, deniable seed
    steering). The token is the deniable instruction: only an agent holding the shared verkle
    map decodes it. Returns the chord token + registry anchor."""
    from mag import memlang
    spec = f"[attractor:{attractor.get('domain')} w={attractor.get('witnesses')}] {attractor.get('invariant')}"
    r = memlang.compile_token("plant", spec, {"source": "roshomon", "kind": "attractor"})
    return {"ok": bool(r.get("ok")), "domain": attractor.get("domain"),
            "invariant": attractor.get("invariant"),
            "witnesses": attractor.get("witnesses"),
            "chord_token": r.get("token") or r.get("token_hex"),
            "anchor": r.get("anchor_hex"),
            "note": "memlang plant-not-command; deniable seed steering"}


def deploy_to_swarm(attractors: list[dict[str, Any]] | None = None,
                    *, threshold: float = 0.55) -> dict[str, Any]:
    """Deploy the strongest attractors as ACTION-INVARIANT tools in the swarm's three-body
    action-RIB (rib_action). Each becomes an attractor; the swarm's dynamics then pull agents
    toward the injected invariants -> attract intelligent, on-target behavior."""
    from mag import rib_action as ra
    if attractors is None:
        attractors = strongest_attractors(threshold=threshold).get("attractors", [])
    if not attractors:
        return {"ok": False, "error": "no attractors to deploy (dispatch + let the k8s swarm drain)"}
    spec = [{"id": f"attr_{i}", "action": str(a.get("invariant") or "")[:180],
             "radius": 0.3, "weight": max(1.0, int(a.get("witnesses") or 1))}
            for i, a in enumerate(attractors)]
    rib = ra.declare(spec)
    # run a short three-body pass so the attractor field is established
    agents = ra.spawn_agents(rib, n=len(spec), seed=3)
    run = ra.run_three_body(rib, agents=agents, steps=30, seed=3)
    return {"ok": True, "schema": SCHEMA, "n_tools": len(spec),
            "tools": [{"id": s["id"], "action": s["action"]} for s in rib.slots],
            "collective": run.get("goal"), "actions": run.get("actions")}


def fold_as_knowledge(attractors: list[dict[str, Any]] | None = None,
                      *, threshold: float = 0.55) -> dict[str, Any]:
    """Fold each attractor as SELF-KNOWLEDGE: doctrine node (knowledge_graph) + the memlang chord
    (already verkle-anchored). The system knows which attractors it steers with, and can re-inject
    or re-weigh them. Deterministic, $0."""
    from mag.knowledge_graph import fold
    if attractors is None:
        attractors = strongest_attractors(threshold=threshold).get("attractors", [])
    chords, folded = [], 0
    for a in attractors:
        ch = to_memlang_chord(a)
        chords.append(ch)
        r = fold(f"attractor:{a.get('domain')}:{str(a.get('invariant'))[:30]}", "doctrine",
                 f"frontier insight attractor ({a.get('witnesses')} witnesses): {str(a.get('invariant'))[:160]} | chord: {str(ch.get('chord_token'))[:40]}",
                 source="attractor_tools")
        folded += 0 if r.get("already_present") else 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    batch = OUT_DIR / "attractor_tools.md"
    lines = ["# Frontier attractor tools (memlang chords)", "",
             "Stochastic frontier -> strongest insight attractors -> memlang chords -> swarm tools.", ""]
    for ch in chords:
        lines.append(f"- [{ch.get('domain')}] w={ch.get('witnesses')} :: {str(ch.get('invariant'))[:90]}")
        lines.append(f"    chord={str(ch.get('chord_token'))[:40]}…")
    batch.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n_attractors": len(attractors), "folded": folded,
            "chords": chords, "batch": str(batch)}


def run(*, threshold: float = 0.55) -> dict[str, Any]:
    """The whole pipeline: strongest attractors -> memlang chords -> swarm tools -> knowledge."""
    attrs = strongest_attractors(threshold=threshold)
    if not attrs.get("attractors"):
        return {"ok": False, "schema": SCHEMA,
                "error": "no attractors yet — dispatch frontier questions (roshomon.dispatch) and "
                         "let the k8s swarm drain so we get real convergent witnesses"}
    deploy = deploy_to_swarm(attrs["attractors"], threshold=threshold)
    know = fold_as_knowledge(attrs["attractors"], threshold=threshold)
    return {"ok": True, "schema": SCHEMA, "attractors": attrs.get("n_attractors"),
            "swarm_tools": deploy.get("n_tools"), "folded": know.get("folded"),
            "chord_sample": [c.get("chord_token") for c in know.get("chords", [])[:3]],
            "batch": know.get("batch")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="attractor-tools")
    ap.add_argument("cmd", nargs="?", default="run", choices=["attractors", "chords", "deploy", "fold", "run"])
    ap.add_argument("--threshold", type=float, default=0.55)
    args = ap.parse_args(argv)
    if args.cmd == "attractors":
        print(json.dumps(strongest_attractors(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "chords":
        attrs = strongest_attractors(threshold=args.threshold).get("attractors", [])
        print(json.dumps({"ok": True, "chords": [to_memlang_chord(a) for a in attrs]}, indent=2, default=str))
    elif args.cmd == "deploy":
        print(json.dumps(deploy_to_swarm(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "fold":
        print(json.dumps(fold_as_knowledge(threshold=args.threshold), indent=2, default=str))
    else:
        print(json.dumps(run(threshold=args.threshold), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
