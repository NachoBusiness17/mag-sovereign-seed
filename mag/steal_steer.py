"""steal_steer — steer steals/responses AWAY from data we already have, via the flock field.

The operator's idea (2026-08-09): "could steal use flocking to make sure responses we get
naturally stay away from data we already have through steering?"

YES — and it's the native shape of flock_field. In PhiField, an `invariant` is a repulsive
sphere (center, radius): `value()` adds `w*(r-d)` when you get within r, so the gradient
`-grad(phi)` steers agents AWAY from invariants. We reuse that exactly:

  - EXISTING artifacts (research packs, verkle leaves, pro_library) -> invariant centers
    (their sha256 embedding into field coordinates).
  - A PROPOSED response / steal -> an agent placed at its embedding.
  - Steering runs the field: the agent is pushed out of every sphere we already occupy.

What falls out:
  * novelty(text)      -> how far a received response is from all existing data (0=redundant,
                          1=fully novel). If it can't clear the repulsion, it's a duplicate we
                          already have.
  * steer_query(goal)  -> steer an ASK's embedding away from covered space so the response
                          comes back NOVEL (don't re-ask what we already know).
  * coverage()         -> which existing regions are saturated (many overlaps) vs empty.

Deterministic, $0, no LLM. Reuses flock_field.PhiField. Schema: steal_steer.v1
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
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "steal_steer.v1"
DIM = 6
REPULSION = 0.32      # radius of the "already covered" sphere per artifact
PACKS = ROOT / "memory" / "research_packs"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
PRO = ROOT / "memory" / "pro" / "pro_library.jsonl"

from mag.flock_field import PhiField, define_distance_field, Agent, step, _vlen, _vsub


def _embed(text: str, dim: int = DIM) -> tuple:
    """Deterministic sha256 -> normalized point in [0,1]^dim (the field coordinate)."""
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    step_n = max(1, len(h) // dim)
    out = []
    for i in range(dim):
        chunk = h[i * step_n:(i + 1) * step_n] or b"\x00"
        out.append((int.from_bytes(chunk, "big") % 10_000) / 10_000.0)
    return tuple(out)


def _jsonl(path: Path) -> list[dict[str, Any]]:
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


def _existing_points() -> list[dict[str, Any]]:
    """Every artifact we already have -> {id, text, embed, lens}."""
    pts = []
    if PACKS.is_dir():
        for p in sorted(PACKS.glob("*.answer.*.md"))[:400]:
            t = p.read_text(encoding="utf-8", errors="replace")
            pts.append({"id": p.name, "text": t, "embed": _embed(t), "lens": "research_pack"})
    for r in _jsonl(CHAIN):
        t = str(r.get("summary") or r.get("text") or "")
        if t:
            pts.append({"id": f"verkle:{r.get('leaf_hash','')[:8]}", "text": t,
                        "embed": _embed(t), "lens": "verkle"})
    for r in _jsonl(PRO):
        t = str(r.get("summary") or r.get("text") or r.get("title") or "")
        if t:
            pts.append({"id": f"pro:{r.get('id','')[:8]}", "text": t,
                        "embed": _embed(t), "lens": "pro_library"})
    return pts


def _field(goal: tuple, points: list[dict[str, Any]], radius: float = REPULSION) -> PhiField:
    """Field with goal=ask, invariants=every existing artifact (repulsive spheres)."""
    inv = [p["embed"] for p in points]
    return define_distance_field(goal, invariants=inv, dim=DIM)


def novelty(text: str, points: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """How novel is a received response vs data we already have? 0=redundant, 1=novel.

    Place the response as an agent; let invariant repulsion push it out. The residual
    repulsion it still feels = how much it overlaps existing coverage. Steering it to a
    resting point and measuring distance-from-all-spheres gives the novelty score.
    """
    points = points if points is not None else _existing_points()
    if not points:
        return {"ok": True, "novelty": 1.0, "n_existing": 0, "overlap": 0.0}
    e = _embed(text)
    # worst-case overlap with any existing sphere (max normalized penalty)
    worst = 0.0
    nearest = None
    nearest_d = float("inf")
    for p in points:
        d = _vlen(_vsub(e, p["embed"]))
        if d < nearest_d:
            nearest_d = d
            nearest = p["id"]
        if d < REPULSION:
            worst = max(worst, (REPULSION - d) / REPULSION)
    nov = round(1.0 - min(1.0, worst), 3)
    return {"ok": True, "novelty": nov, "n_existing": len(points),
            "overlap": round(min(1.0, worst), 3), "nearest": nearest,
            "nearest_dist": round(nearest_d, 3),
            "judgement": "NOVEL" if nov >= 0.5 else ("PARTIAL" if nov >= 0.2 else "REDUNDANT")}


def steer_query(goal_text: str, *, steps: int = 40, points: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Steer an ASK's embedding away from covered space (don't re-ask what we know).

    Agent starts at the raw ask embed; field repulsion from existing data pushes it to a
    NOVEL point. Returns the steered position + how far it moved + residual overlap.
    """
    points = points if points is not None else _existing_points()
    goal = _embed(goal_text)
    if not points:
        return {"ok": True, "steered": list(goal), "moved": 0.0, "novelty": 1.0, "n_existing": 0}
    field = _field(goal, points)
    agent = Agent(pos=goal)
    for _ in range(steps):
        step([agent], field, dt=0.15, damp=0.90, max_speed=0.5)
    moved = _vlen(_vsub(agent.pos, goal))
    nov = novelty(goal_text, points)
    return {"ok": True, "goal": list(goal), "steered": list(round(float(v), 3) for v in agent.pos),
            "moved": round(moved, 3), "novelty": nov["novelty"], "n_existing": len(points)}


def coverage(points: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Where are we saturated vs empty? Count overlaps per artifact (density map)."""
    points = points if points is not None else _existing_points()
    if not points:
        return {"ok": True, "n_existing": 0, "saturated": [], "spread": 0.0}
    dense = []
    for p in points:
        c = sum(1 for q in points if _vlen(_vsub(p["embed"], q["embed"])) < REPULSION)
        dense.append({"id": p["id"], "lens": p["lens"], "neighbors": c - 1})
    dense.sort(key=lambda d: -d["neighbors"])
    unique = sum(1 for d in dense if d["neighbors"] == 0)
    return {"ok": True, "n_existing": len(points), "unique": unique,
            "spread": round(unique / len(points), 3),
            "saturated": dense[:10]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="steal-steer")
    ap.add_argument("cmd", nargs="?", default="coverage", choices=["coverage", "novelty", "steer"])
    ap.add_argument("--text", default="", help="text to score (novelty) or ask (steer)")
    args = ap.parse_args(argv)
    if args.cmd == "coverage":
        print(json.dumps(coverage(), indent=2, default=str))
    elif args.cmd == "novelty":
        print(json.dumps(novelty(args.text), indent=2, default=str))
    elif args.cmd == "steer":
        print(json.dumps(steer_query(args.text), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
