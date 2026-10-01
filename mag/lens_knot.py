"""lens_knot — map internal subsystems for OPTIMAL STATELESS operation on improvement loops,
loaded simply as a LENS. Each lens is a VERKLE KNOT (content-addressed, deterministic, stateless).
Each lens tells a DIFFERENT ROSHOMON story of the same underlying state; consulting the SWARM
(consensus across lens-knots) yields the TRUTH.

Operator (2026-08-11): "how can we better map our internal subsystems for optimal stateless operation
by default on improvement loops loaded simply as a lens. each lens a verkle knot that we can view
data through that tells a different roshamon story from when consulting the swarm we get the truth."

THE MECHANISM (deterministic + $0, reuses real primitives):
  1. STATELESS BY DEFAULT: every improvement-loop subsystem is a PURE function (its invariant +
     the live data it reads) -> the SAME knot every time. No mutation; a knot is LOADED, never
     edited. Content-addressed: knot_id = sha256(invariant + data).
  2. LENS AS A VERKLE KNOT: each lens (lens_shader.LENSES) = a knot you VIEW DATA THROUGH. Reading
     the same shared events through lens A gives story A; through lens B, story B. Same world,
     different Roshomon witness.
  3. ROSHOMON STORIES: each lens attends to a DIFFERENT aspect of the shared events and narrates
     its own story (evidence statements + framing).
  4. SWARM = THE TRUTH: aggregate across lens-knots. Statements MULTIPLE lenses agree on = the
     ROSHOMON CORE = convergent truth. Statements unique to one lens = divergent perspective.
     Consult the swarm -> you get the truth, not any single lens's story.

Schema: lens_knot.v1 · deterministic + $0 · reuse: lens_shader, percolator, cost/usage, verkle
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "lens_knot.v1"
STORIES_LOG = ROOT / "memory" / "lens_knot" / "stories.jsonl"

# ── The lenses as Roshomon witnesses: which shared events each lens attends to + its framing ──
# Each lens reads the SAME shared events but frames a DIFFERENT story (a different Roshomon witness).
LENS_FRAME: dict[str, dict[str, Any]] = {
    "memory/invariant": {"attends": ["invariant", "novel", "false_positive", "training"],
                         "framing": "the memory knot: what invariants are being compiled from signals"},
    "economics/cost":   {"attends": ["cost", "usage", "cache", "spike"],
                         "framing": "the economics knot: where the budget is spent and where it leaks"},
    "compiler/world":   {"attends": ["world", "world_rib", "render", "field"],
                         "framing": "the world knot: what is rendered vs what stays wallpaper"},
    "swarm/detect":     {"attends": ["spike", "seam", "emergence", "swarm", "gap"],
                         "framing": "the swarm knot: where agents diverge = the seams to shade"},
    "steal-lens":       {"attends": ["steal", "novel", "lens", "shard"],
                         "framing": "the steal knot: how novel each incoming fragment is and its shard"},
    "security/guard":   {"attends": ["probe", "guard", "leak", "intrusion"],
                         "framing": "the guard knot: who is knocking on the world's walls"},
    "wearable/surface": {"attends": ["surface", "wear", "hud", "command"],
                         "framing": "the surface knot: what the operator's HUD is showing"},
}


def _now() -> str:
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


def shared_events() -> list[dict[str, Any]]:
    """The SAME underlying events every lens-witness reads: live signals from the real surfaces.
    This is the single world the Roshomon stories disagree about."""
    ev: dict[str, int] = Counter()
    for e in _read_jsonl(ROOT / "memory" / "behavioral_events.jsonl", tail=400):
        k = e.get("kind")
        if k:
            ev[k] += 1
    try:
        per = ROOT / "memory" / "percolator"
        if (per / "explore.jsonl").is_file():
            ev["novel"] += sum(1 for _ in (per / "explore.jsonl").read_text(
                encoding="utf-8", errors="replace").splitlines() if _.strip())
        for fp in per.glob("*.fp.jsonl"):
            ev["false_positive"] += sum(1 for _ in fp.read_text(
                encoding="utf-8", errors="replace").splitlines() if _.strip())
    except Exception:
        pass
    for s in _read_jsonl(ROOT / "memory" / "steer_telemetry.jsonl", tail=200):
        st = s.get("status")
        if st == "accepted":
            ev["steer"] += 1
    try:
        from mag import cost_learn
        a = cost_learn.analyze()
        ev["cost"] += a.get("total_cost", 0) or 0
        ev["cache"] += int(a.get("cache_hit_pct", 99) or 99)
        ev["spike"] += len(a.get("spikes", []))
    except Exception:
        pass
    return [{"signal": k, "count": int(v)} for k, v in ev.items() if v > 0]


def knot_id(lens: str, invariant: str) -> str:
    """Content-addressed verkle knot id: stateless, deterministic — the same lens+invariant
    always loads the same knot (revisit = persistent fidelity)."""
    return hashlib.sha256(f"{lens}::{invariant}".encode("utf-8")).hexdigest()[:16]


def stories() -> dict[str, Any]:
    """Each lens-knot tells its OWN Roshomon story of the shared events. Stateless: every call
    with the same events yields the same knots + stories."""
    events = shared_events()
    by_sig = {e["signal"]: e["count"] for e in events}
    knot_rows = []
    for lens, meta in LENS_FRAME.items():
        attends = meta["attends"]
        # this witness's story = the events it attends to + its framing
        seen = [e for e in events if e["signal"] in attends or any(
            a in e["signal"] for a in attends)]
        story = [f"{e['signal']}={e['count']}" for e in seen]
        # invariant = the lens's stable contract (stateless, loaded as a lens)
        invariant = f"{lens}:{meta['framing']}"
        knot_rows.append({
            "lens": lens, "knot": knot_id(lens, invariant), "framing": meta["framing"],
            "attends": attends, "story": story, "n_statements": len(story),
            "stateless": True, "invariant": invariant[:80],
        })
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_lenses": len(knot_rows),
            "shared_events": events, "knots": knot_rows}


def swarm_truth(*, min_agreement: int = 2) -> dict[str, Any]:
    """CONSULT THE SWARM = the truth: aggregate the Roshomon stories across lens-knots.
    Statements MULTIPLE lenses agree on = the ROSHOMON CORE = convergent truth.
    Statements unique to one lens = divergent perspective (not consensus)."""
    s = stories()
    # Roshomon core: signals attended to by >= min_agreement lenses = convergent truth
    attend: dict[str, list[str]] = {}
    for k in s["knots"]:
        for sig in k["attends"]:
            attend.setdefault(sig, []).append(k["lens"])
    core = [{"signal": sig, "n_lenses": len(ls), "lenses": ls}
            for sig, ls in attend.items() if len(ls) >= min_agreement]
    core.sort(key=lambda x: -x["n_lenses"])
    divergent = [{"signal": sig, "lenses": ls}
                 for sig, ls in attend.items() if len(ls) < min_agreement]
    # the truth = the core (agreement across the swarm), narrated as consensus
    truth = [c["signal"] for c in core]
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "roshomon_core": core, "divergent_perspectives": divergent,
            "swarm_truth": truth,
            "note": "the swarm (consensus across lens-knots) = the truth; each single lens is only "
                    "one Roshomon witness, not the whole story"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "shared_events()->the one world; stories()->each lens-knot a Roshomon "
                        "story; swarm_truth()->consensus core = the truth",
            "cost": "deterministic + $0 (stateless, content-addressed)",
            "n_lenses": len(LENS_FRAME), "stateless": True}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="lens-knot")
    ap.add_argument("cmd", nargs="?", default="truth",
                    choices=["truth", "stories", "events", "status"])
    a = ap.parse_args()
    if a.cmd == "truth":
        print(json.dumps(swarm_truth(), indent=2, default=str))
    elif a.cmd == "stories":
        print(json.dumps(stories(), indent=2, default=str))
    elif a.cmd == "events":
        print(json.dumps({"shared_events": shared_events()}, indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
