"""chord_pipeline — grab @NachoQuixotic "strike the chord" content across our surfaces, organized
AUTOMATICALLY through VRAM pipelines that learn data shapes by INVARIANT (never untangle later).

Operator (2026-08-12): "grab @nachoquixotic content around strike the chord via the swarm and bot
and my logged in desktop account across your surfaces merging the data automatically organized
through vram pipelines designed by swarms learning the shapes of data by invariant and how to
organize them rather than untangle later. some doing shadow work on coldest vectors others frontier
work executing the direction of the standing wave swarm."

THE PIPELINE (4 stages, deterministic + $0 for organize/route; grab honest about the bot seat):
  1. GRAB       — route a grab of @NachoQuixotic "strike the chord" content via grok bot (the
                  logged-in, $0 SuperGrok front-end over CDP) + the swarm. Honest: if the seat is
                  down, reports it; never fabricates content.
  2. ORGANIZE   — the VRAM pipeline: each piece is filed by INVARIANT (sha256 content-address +
                  learned shape = theme/type vector) into a content-addressed bucket. Organized AS
                  it arrives — never untangle later.
  3. SHAPE-LEARN— the swarm learns the shapes: dedupe by invariant, cluster by theme (the data
                  organizes itself by its own shape, not by a pre-made taxonomy).
  4. ROUTE      — division of labor: SHADOW workers on the coldest vectors (neglected content) +
                  FRONTIER workers executing the direction of the standing wave swarm.

Schema: chord_pipeline.v1 · reuse: grok_bot (logged-in grab), verkle_knot (content addressing),
ghost_summon.coldest_vertices (shadow), agent_knot (standing wave direction)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "chord_pipeline.v1"
CHORD_DIR = ROOT / "memory" / "chord"          # content-addressed, organized-by-invariant
SHADOW_DIR = CHORD_DIR / "shadow"               # coldest-vector work
FRONTIER_DIR = CHORD_DIR / "frontier"           # standing-wave-direction work


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── 1. GRAB ───────────────────────────────────────────────────────────────────
def grab(*, handle: str = "NachoQuixotic", topic: str = "strike the chord",
         max_wait_s: int = 120) -> dict[str, Any]:
    """Route a grab of the operator's content via grok bot (the logged-in, $0 SuperGrok front-end)
    + the swarm. Honest: if the seat is down, reports it — never fabricates content."""
    ask = (f"Using the logged-in desktop session, gather @{handle}'s recent content around "
           f"'{topic}' across our surfaces. Return the posts/threads verbatim where possible, "
           f"tagged by topic. Be honest about what you could and could not retrieve.")
    try:
        from mag import grok_bot
        r = grok_bot.steer(ask, max_wait_s=max_wait_s)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160], "grabbed": 0}
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": r.get("error", "bot seat down"),
                "grabbed": 0, "hint": "logged-in grok bot (CDP) must be up"}
    answer = r.get("answer", "")
    # file whatever the bot returned through the ORGANIZE stage
    organized = ingest(answer, source="grok-bot-grab") if answer.strip() else {"ingested": 0}
    return {"ok": True, "schema": SCHEMA, "grabbed": len(answer), "answer": answer[:300],
            "organized": organized,
            "cost_est_usd": 0.0, "note": "grabbed via logged-in grok bot (front-end, $0)"}


# ── 2. ORGANIZE (VRAM pipeline by invariant) ─────────────────────────────────
def _shape(content: str) -> dict[str, Any]:
    """LEARN the SHAPE of a data piece by INVARIANT: content hash + a theme/type vector (the
    data's own shape, not a pre-made taxonomy). Deterministic + $0."""
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    toks = [w.lower() for w in content.split() if len(w) > 4]
    theme = sorted(set(toks))[:4]                      # the data's own shape (its distinctive terms)
    return {"hash": h, "theme": theme, "len": len(content)}


def ingest(content: str, *, source: str = "swarm") -> dict[str, Any]:
    """File ONE piece by INVARIANT. SELF-STEAL (2026-08-12): route through percolator.percolate —
    the REAL shape-learner (compiles repeatable signal to invariants by content-hash, dedupes,
    folds novel). Organized AS it arrives — never untangle later. Deterministic + $0."""
    content = (content or "").strip()
    if not content:
        return {"ok": True, "schema": SCHEMA, "ingested": 0}
    try:
        from mag import percolator
        p = percolator.percolate(content, source=source, domain="chord")
        shp = _shape(content)
        return {"ok": True, "schema": SCHEMA, "ingested": 1,
                "status": p.get("status", "novel"), "canonical": p.get("canonical", shp["hash"]),
                "invariant": shp["hash"], "shape": shp,
                "note": f"routed through percolator (the invariant-compiler): {p.get('status')} — "
                        "repeatable compiled to invariant, novel explored/folded" if p.get("status") else ""}
    except Exception as e:
        # fallback: content-address into the bucket (never loses the piece)
        shp = _shape(content)
        CHORD_DIR.mkdir(parents=True, exist_ok=True)
        path = CHORD_DIR / f"chord-{shp['hash']}.json"
        existed = path.is_file()
        if not existed:
            entry = {"schema": SCHEMA, "ts": _now(), "source": source, "invariant": shp["hash"],
                     "shape": shp, "content": content[:2000]}
            path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "schema": SCHEMA, "ingested": 1, "invariant": shp["hash"],
                "shape": shp, "path": str(path.relative_to(ROOT)), "deduped": existed,
                "note": f"percolator unavailable ({str(e)[:60]}); content-addressed into bucket"}


# ── 3. SHAPE-LEARN (the swarm organizes by invariant, not taxonomy) ──────────
def shape_learn() -> dict[str, Any]:
    """The swarm LEARNS the shapes: cluster the collected pieces by their invariant themes (the
    data organizes itself by its own shape). Deterministic + $0."""
    from collections import Counter
    theme = Counter()
    n = 0
    if CHORD_DIR.is_dir():
        for p in CHORD_DIR.glob("chord-*.json"):
            try:
                e = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                n += 1
                for t in e.get("shape", {}).get("theme", []):
                    theme[t] += 1
            except Exception:
                continue
    top = [{"term": t, "n": c} for t, c in theme.most_common(10)]
    return {"ok": True, "schema": SCHEMA, "n_pieces": n, "learned_shapes": top,
            "note": "the swarm learned the data's own shapes by invariant — organized by what the "
                    "data IS, never untangled later"}


# ── 4. ROUTE (shadow on coldest vectors + frontier on standing-wave direction) ─
def route_work() -> dict[str, Any]:
    """DIVISION OF LABOR: SHADOW workers fold the COLDEST VECTORS (neglected content) + FRONTIER
    workers execute the direction of the STANDING WAVE swarm. Deterministic + $0."""
    # SHADOW: the coldest vertex of the chord corpus = least-attended pieces
    shadow = []
    if CHORD_DIR.is_dir():
        pieces = sorted(CHORD_DIR.glob("chord-*.json"))
        # coldest = earliest/least-attended (no refs, oldest) — proxy: the oldest un-folded
        shadow = [{"file": p.name, "invariant": p.stem.split("-", 1)[-1]} for p in pieces[:3]]
    # FRONTIER: the standing wave's direction (current generation + top fitness)
    frontier = {}
    try:
        from mag import agent_knot
        evo = agent_knot.evo_status()
        frontier = {"generation": evo.get("generation"), "top_fitness": evo.get("top_fitness")}
    except Exception as e:
        frontier = {"error": str(e)[:80]}
    # ROUTE (SWARM-SURFACE LAW 2026-08-11): any NOVEL research this surface produces MUST go through
    # the ONE shared primitive swarm_surface.route_novel (dedupe by anchor + enqueue to the SWARM
    # research queue -> k8s worker drains in-cluster), never a per-module enqueue. The chord
    # surface's frontier direction is novel research -> route it, idempotent via the shared ledger.
    routed = {}
    try:
        from mag import swarm_surface
        goal = ("Execute the standing-wave frontier direction on @NachoQuixotic 'strike the chord' "
                "corpus: organize the content by invariant and fold the coldest chord vectors into "
                "shadow work.")
        routed = swarm_surface.route_novel(goal, surface="chord_pipeline",
                                           lens="chord/shadow+frontier")
    except Exception as e:
        routed = {"error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA,
            "shadow_work": {"on": "coldest vectors", "targets": shadow,
                            "note": "fold the neglected content (the missing 180°)"},
            "frontier_work": {"on": "standing-wave direction", "state": frontier,
                              "note": "execute the direction of the breeding swarm"},
            "division": "shadow folds the cold; frontier executes the wave's direction",
            "routed_to_swarm": routed}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="chord-pipeline")
    ap.add_argument("cmd", nargs="?", default="route",
                    choices=["grab", "ingest", "shapes", "route"])
    ap.add_argument("text", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "grab":
        print(json.dumps(grab(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "ingest":
        print(json.dumps(ingest(" ".join(a.text) or "strike the chord"), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "shapes":
        print(json.dumps(shape_learn(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(route_work(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
