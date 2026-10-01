"""btw_sidechannel — the live "/btw" aside injection surface for the swarm.

Operator (2026-08-11): "could we make that our tool for our swarms as a feature? like btw k3
new vector coordinates now that you've traveled to this cluster. i really do see our memory
spaces and invariants as almost pointillism of a richer reality we can map to."

THE IDEA: every invariant / memory-space is a DOT; a "/btw" aside is a dot being placed LIVE that
re-maps the territory. The swarm's rightsizing (and any consumer) must be able to react to a live
contextual coordinate ("btw, new cluster, new vector position") instead of only automatic learned
sizing. This is the missing live-aside surface that swarm_rightsize.rightsize() currently lacks.

THE SHAPE (deterministic + $0):
  inject(coordinate, note, seat) -> append a live aside to the btw ledger, deduped by a content
        anchor (same coordinate+note repeated = same dot, not re-placed). Returns novel? + the dot.
  travel(coordinate, note, seat) -> semantic wrapper: "we've traveled to this coordinate now."
        A NEW vector (cold cluster) means the deterministic prefix is NOT cached -> MORE agents.
        A RETURNED vector (warm cluster) means cache-warm -> FEWER agents. Honest: only decides
        "novel vs warm" from the LEDGER, never fabricates cache state.
  sense(latest_n)            -> read the N most recent placed dots (the live vector position).
  rightsize(goal, provider, btw) -> the LIVE-aware sizing: starts from swarm_rightsize.rightsize()
        then PERTURBS by the latest btw dot: novel vector -> +1 (cold prefix, needs more agents);
        warm/revisited vector -> -1 (cache reuse). Never below 1. Honest about the perturbation.

Ledger: memory/btw/ledger.jsonl (append-only, content-addressed anchors).

Schema: btw_sidechannel.v1 · deterministic + $0 · reuse: swarm_rightsize
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

SCHEMA = "btw_sidechannel.v1"
LEDGER = ROOT / "memory" / "btw" / "ledger.jsonl"
ANCHORS = ROOT / "memory" / "btw" / "anchors.json"  # content anchors -> dedupe


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _anchor(coordinate: str, note: str) -> str:
    """Deterministic content anchor for a placed dot (dedupe key)."""
    import hashlib
    return hashlib.sha256(f"{coordinate}:::{note}".encode("utf-8")).hexdigest()[:16]


def _load_anchors() -> set[str]:
    if ANCHORS.is_file():
        try:
            return set(json.loads(ANCHORS.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_anchors(a: set[str]) -> None:
    ANCHORS.parent.mkdir(parents=True, exist_ok=True)
    ANCHORS.write_text(json.dumps(sorted(a), indent=2), encoding="utf-8")


def _all_dots() -> list[dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def inject(*, coordinate: str, note: str = "", seat: str = "ghost") -> dict[str, Any]:
    """Place a live aside dot. Deduped by content anchor: the same dot placed twice is NOT
    re-placed (same point on the map, not two points). Returns novel + the dot."""
    coordinate = (coordinate or "").strip()
    if not coordinate:
        return {"ok": False, "schema": SCHEMA, "error": "coordinate required"}
    note = (note or "").strip()
    a = _anchor(coordinate, note)
    anchors = _load_anchors()
    if a in anchors:
        return {"ok": True, "schema": SCHEMA, "novel": False, "deduped": True,
                "dot": {"coordinate": coordinate, "note": note, "anchor": a},
                "reason": "same dot already placed (content anchor match) — not re-placed"}
    dot = {"ts": _now(), "coordinate": coordinate, "note": note,
           "seat": seat, "anchor": a}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dot) + "\n")
    anchors.add(a)
    _save_anchors(anchors)
    return {"ok": True, "schema": SCHEMA, "novel": True, "deduped": False, "dot": dot,
            "reason": "new dot placed (novel coordinate/note)"}


def travel(*, coordinate: str, note: str = "", seat: str = "ghost") -> dict[str, Any]:
    """Semantic wrapper: 'we've traveled to this coordinate now.' Determines cold vs warm from
    the LEDGER (real placement history) — never fabricates cache state."""
    coordinate = (coordinate or "").strip()
    if not coordinate:
        return {"ok": False, "schema": SCHEMA, "error": "coordinate required"}
    # warm = this coordinate has been placed before (returned vector); cold = brand new cluster
    visited = any((d.get("coordinate") or "") == coordinate for d in _all_dots())
    res = inject(coordinate=coordinate, note=note, seat=seat)
    return {**res, "visited": visited,
            "vector": "warm" if visited else "cold",
            "meaning": ("returned to a known coordinate (cache-warm -> reuse -> fewer agents)"
                        if visited else
                        "brand-new coordinate (cold prefix -> needs more agents)")}


def sense(*, latest_n: int = 3) -> dict[str, Any]:
    """Read the N most recent placed dots = the live vector position of the swarm."""
    dots = _all_dots()
    latest = dots[-latest_n:] if latest_n > 0 else dots
    return {"ok": True, "schema": SCHEMA, "n_placed": len(dots), "latest": latest,
            "position": latest[-1]["coordinate"] if latest else None}


def rightsize(goal: str = "", *, provider: str = "auto", btw: dict[str, Any] | None = None) -> dict[str, Any]:
    """LIVE-AWARE sizing: start from swarm_rightsize.rightsize() then PERTURB by the latest btw dot.
    Novel/cold vector -> +1 agent (cold deterministic prefix, needs more agents to cover it);
    warm/revisited -> -1 (cache reuse). Never below 1. Honest: the perturbation is named."""
    from mag import swarm_rightsize
    base = swarm_rightsize.rightsize(goal, provider=provider)
    n = int(base.get("n_agents", 3))
    perturb = None
    # source the btw vector: explicit arg, else the ledger's latest dot
    coordinate = None
    if isinstance(btw, dict) and btw.get("coordinate"):
        coordinate = str(btw["coordinate"])
    if not coordinate:
        s = sense(latest_n=1)
        lt = (s.get("latest") or [None])[-1]
        coordinate = (lt or {}).get("coordinate")
    if coordinate:
        visited = any((d.get("coordinate") or "") == coordinate for d in _all_dots()[:-1])
        if visited:
            n = max(1, n - 1)
            perturb = f"btw warm vector ({coordinate}) -> cache reuse, -1 agent"
        else:
            n = min(int(base.get("n_agents", 3)) + 1, 16)
            perturb = f"btw cold vector ({coordinate}) -> cold prefix, +1 agent"
    return {**base, "n_agents": n, "btw_perturbation": perturb,
            "btw_coordinate": coordinate, "schema": SCHEMA}


def status() -> dict[str, Any]:
    s = sense(latest_n=0)
    return {"ok": True, "schema": SCHEMA,
            "contract": "inject/travel -> place a live '/btw' dot (deduped); sense -> read the "
                        "live vector position; rightsize(goal, provider, btw) -> live-aware sizing "
                        "(cold vector +1 agent, warm -1), perturbing swarm_rightsize",
            "cost": "deterministic + $0", "n_dots": s["n_placed"],
            "position": s["position"], "ledger": str(LEDGER)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="btw-sidechannel")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "inject", "travel", "sense", "size"])
    ap.add_argument("coordinate", nargs="?", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--provider", default="auto")
    a = ap.parse_args()
    if a.cmd == "inject":
        print(json.dumps(inject(coordinate=a.coordinate, note=a.note), indent=2, default=str))
    elif a.cmd == "travel":
        print(json.dumps(travel(coordinate=a.coordinate, note=a.note), indent=2, default=str))
    elif a.cmd == "sense":
        print(json.dumps(sense(), indent=2, default=str))
    elif a.cmd == "size":
        print(json.dumps(rightsize(a.coordinate, provider=a.provider), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
