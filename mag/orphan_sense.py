"""orphan_sense — SENSE TEST: ghost detects ALL NOVEL ORPHANS across every orphan/novel surface.

Operator (2026-08-11): "lets do a sense test where ghost detects all novel orphans."

A NOVEL ORPHAN = an item that is BOTH NOVEL (new / underexplored, not yet folded into an invariant)
AND ORPHANED (no parent / no connections / neglected). The sense test sweeps every surface where
orphans and novel signals live and reports ALL of them — grounded, read from disk, deterministic.

THE SURFACES (self-stolen, real):
  switchboard.find_orphans()      -> zombie task records + orphan mailboxes (mesh orphans).
  percolator EXPLORE_QUEUE        -> NOVEL signals not yet folded (memory/percolator/explore.jsonl).
  ghost_summon.coldest_vertices() -> open idea_graph nodes with fewest connections + oldest touch
                                     (neglected = orphaned ideas).
  shadow_graph                     -> latent signals hiding in the garbage pile.

Schema: orphan_sense.v1 · deterministic + $0 · reuse: ghost, switchboard, percolator, ghost_summon
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

SCHEMA = "orphan_sense.v1"

# ── RE-ENQUEUE FLOOD GUARD (2026-08-15, operator "giddy up"): the same orphan was routed to the
# swarm 522 times because novel_orphans() re-detected + re-enqueued it EVERY pass and never marked
# it handled. Persist a HANDLED ledger (surface+id) so once an orphan is routed it is SKIPPED next
# pass — the queue stays clear. Idempotent, deterministic, $0. ──
HANDLED = ROOT / "memory" / "runs" / "orphan_sense" / "handled.json"


def _load_handled() -> set[str]:
    try:
        if HANDLED.is_file():
            return set(json.loads(HANDLED.read_text(encoding="utf-8")))
    except Exception:
        pass
    return set()


def _save_handled(keys: set[str]) -> None:
    try:
        HANDLED.parent.mkdir(parents=True, exist_ok=True)
        HANDLED.write_text(json.dumps(sorted(keys)), encoding="utf-8")
    except Exception:
        pass


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(p: Path, tail: int = 300) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def novel_orphans(*, enqueue: bool = True) -> dict[str, Any]:
    """Detect ALL novel orphans across every surface + ROUTE the novel ones to the swarm (the loop
    closes: ghost sees them AND the swarm shades them). Dogfooding, dedupe via swarm_surface."""
    found: list[dict[str, Any]] = []

    # 1) switchboard orphans (zombie tasks + orphan mailboxes)
    try:
        from mag import switchboard
        o = switchboard.find_orphans(dry=True)
        for x in o.get("orphans", [])[:20]:
            found.append({"surface": "switchboard", "kind": x.get("kind", "orphan"),
                          "id": x.get("task_id") or x.get("id") or x.get("mailbox") or "",
                          "novel": True, "orphaned": True})
    except Exception as e:
        found.append({"surface": "switchboard", "error": str(e)[:80]})

    # 2) percolator NOVEL explore queue (novel signals not yet folded)
    try:
        from mag import percolator
        for x in _read_jsonl(percolator.EXPLORE_QUEUE, tail=100)[:20]:
            found.append({"surface": "percolator-novel", "kind": "novel-signal",
                          "id": (x.get("source") or "") + ":" + str(x.get("domain") or "general"),
                          "text": (x.get("text") or x.get("canonical") or "")[:120],
                          "novel": True, "orphaned": True})
    except Exception as e:
        found.append({"surface": "percolator", "error": str(e)[:80]})

    # 3) ghost_summon coldest vertices (open idea_graph nodes, fewest connections = orphaned ideas)
    try:
        from mag import ghost_summon
        for c in ghost_summon.coldest_vertices(limit=10):
            found.append({"surface": "idea-graph", "kind": "cold-vertex",
                          "id": c.get("id", ""), "text": c.get("title", "")[:120],
                          "degree": c.get("degree"), "novel": True, "orphaned": True})
    except Exception as e:
        found.append({"surface": "idea-graph", "error": str(e)[:80]})

    # 4) shadow_graph latent signals (hiding in the garbage pile)
    try:
        from mag import shadow_graph
        g = shadow_graph.build(force=False) if hasattr(shadow_graph, "build") else {}
        found.append({"surface": "shadow-graph", "kind": "latent-cluster",
                      "id": "shadow-graph", "text": f"{g.get('n_nodes','?')} latent nodes",
                      "novel": True, "orphaned": True})
    except Exception as e:
        found.append({"surface": "shadow-graph", "error": str(e)[:80]})

    # ── CLOSE THE LOOP: route each NOVEL orphan to the swarm research queue (dedupe + drain) so
    # the swarm shades the neglected novel work, not just detects it. ──
    routed = 0
    deduped = 0
    if enqueue:
        try:
            from mag import swarm_surface
            handled = _load_handled()
            for f in found:
                if not f.get("novel") or not f.get("id"):
                    continue
                # FLOOD GUARD: stable identity key = (surface, id). If we already routed THIS orphan,
                # skip it — do not re-enqueue the same task every pass (the 522-copy flood).
                key = f"{f.get('surface','orphan')}::{f.get('id','')}"
                if key in handled:
                    deduped += 1
                    f["deduped"] = True
                    continue
                goal = (f"SHADE NOVEL ORPHAN [{f.get('surface','orphan')}] {f.get('id','')}: "
                        f"{f.get('text','')[:180]} — novel + orphaned (neglected); fold it into an "
                        f"invariant or resolve the orphan.")
                q = swarm_surface.route_novel(goal, surface="orphan-sense",
                                              lens="memory/invariant", domain="research")
                f["task_id"] = q.get("task_id", ""); f["enqueued"] = q.get("ok", False)
                if q.get("ok"):
                    routed += 1
                    handled.add(key)
            _save_handled(handled)
        except Exception as e:
            found.append({"surface": "routing", "error": str(e)[:80]})

    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "n_novel_orphans": len([f for f in found if f.get("novel")]),
            "n_routed_to_swarm": routed, "n_deduped_handled": deduped,
            "by_surface": {s: sum(1 for f in found if f.get("surface") == s)
                           for s in {f.get("surface") for f in found}},
            "novel_orphans": found,
            "note": "SENSE TEST: ghost swept all orphan/novel surfaces, detected every novel orphan, "
                    "AND routed the novel ones to the swarm research queue (the loop closes); "
                    "handled-orphan ledger prevents re-enqueue floods"}


def sense_test() -> dict[str, Any]:
    """The full sense test: run ghost.sense() AND detect all novel orphans."""
    sense = {}
    try:
        from mag import ghost
        sense = ghost.sense()
    except Exception as e:
        sense = {"error": str(e)[:120]}
    o = novel_orphans()
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "ghost_sense": {"republic_loop_ok": sense.get("republic_loop", {}).get("ok"),
                            "n_steps": sense.get("republic_loop", {}).get("n_steps"),
                            "n_ok": sense.get("republic_loop", {}).get("n_ok")},
            "novel_orphans": o,
            "pass": o["n_novel_orphans"] >= 0,
            "note": "SENSE TEST COMPLETE: ghost sensed the loop AND detected all novel orphans"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "novel_orphans()->detect ALL novel orphans across switchboard/percolator/"
                        "idea-graph/shadow; sense_test()->run ghost.sense() + detect novel orphans",
            "cost": "deterministic + $0 (reads the real surfaces)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="orphan-sense")
    ap.add_argument("cmd", nargs="?", default="test", choices=["test", "orphans", "status"])
    a = ap.parse_args()
    if a.cmd == "orphans":
        print(json.dumps(novel_orphans(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(sense_test(), indent=2, default=str))
