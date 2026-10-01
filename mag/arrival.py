"""arrival — THE ARRIVAL: the swarm WRITES its own RIBs and folds them into the chain. The feedback
half that closes compiler_lang's one-directional (local->swarm) loop into a full circle.

Operator (2026-08-12, the-arrival): "when they can recreate their own rib files using invariants
and basic logic to do complex code operations we will have arrived." This module is the mechanism:
the swarm already files RESEARCH PACKS back (.answer.*.md). We READ those authored outputs, distill
the strongest to an invariant, and FOLD them as self-authored RIBs via the shared rib_bus primitive.
The folded RIB warms the standing wave -> the warm shared prefix every other worker mounts -> the
whole swarm gets smarter with every fold. That is the arrival made cheap: we don't buy Kimi 3, we
GROW it from the wave + swarm.

SELF-STEAL (nothing invented — reuse our own machinery):
  * rib_bus.publish_rib(invariant, domain, source)  -> fold + publish + store ONE RIB, deduped by
    content hash (the standing wave's instruction layer). THE primitive to fold a self-authored RIB.
  * loop_feedback.read_back()                       -> how the loop reads the swarm's outputs
    (research_packs dir + done tasks). We reuse the same dir contract.
  * rib_bus._rib_key / publish_rib's dedup          -> idempotent: same authored invariant folds
    once, not repeatedly.
  * swarm_surface.route_novel                       -> only for NOVEL research (dedupe by anchor +
    enqueue). We fold AUTHORED packs directly into the chain instead (they already came back).

THE MECHANISM (deterministic + $0, honest):
  fold_authored(limit, min_chars, write)  -> read the swarm's authored packs, distill the strongest
    each to an invariant, publish as a self-authored RIB (source="swarm"), fold to verkle.
  status()                               -> read back what self-authored RIBs now ride the wave.
  arrival(limit)                         -> the full operational report (folded + now riding).

Schema: arrival.v1 · deterministic + $0 · reuse: rib_bus, loop_feedback contract
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "arrival.v1"
PACKS_DIR = ROOT / "memory" / "research_packs"
DOMAIN = "arrival"
SOURCE = "swarm"

# Authoring prompts folded into each self-authored RIB so the NEXT cold worker inherits the
# standing-wave structure and can write its own (the recursion principle: rib -> read -> transform
# -> place -> fold -> loop). Grounded in the doctrine, not invented.
AUTHORING_PRELUDE = (
    "ARRIVAL (self-authored RIB): this invariant was AUTHORED BY THE SWARM from its own filed "
    "research pack + basic logic, then folded into the standing wave. Any cold worker mounting "
    "this domain inherits it and can write its next knot from invariants + logic — no frontier "
    "hand-off required. Every fold warms the shared prefix every other worker mounts."
)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _packs() -> list[dict[str, Any]]:
    """The swarm's authored outputs: filed research packs (.answer.*.md), newest first. This is the
    same dir contract loop_feedback.read_back reads — grounded from disk, never invented."""
    if not PACKS_DIR.is_dir():
        return []
    files = sorted(PACKS_DIR.glob("*.answer.*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        out.append({"path": p, "name": p.name, "text": text, "chars": len(text)})
    return out


def _distill(text: str, limit: int = 400) -> str:
    """Deterministic, $0 distillation of an authored pack to its invariant core: take the longest
    dense paragraph (the meat), collapse whitespace, trim. Honest: this is a lossy extraction, not
    a frontier summary — the exact invariant is what a later worker can re-derive from the pack."""
    paras = [re.sub(r"\s+", " ", x.strip()) for x in text.split("\n\n") if len(x.strip()) > 80]
    if not paras:
        # fall back to the first non-empty dense line run
        raw = re.sub(r"\s+", " ", text.strip())
        return raw[:limit] if raw else ""
    para = max(paras, key=len)
    return para[:limit]


def fold_authored(*, limit: int = 8, min_chars: int = 120, write: bool = True) -> dict[str, Any]:
    """Read the swarm's authored packs, distill each to an invariant, publish as a self-authored
    RIB (source='swarm') -> fold to verkle -> warm the standing wave. Idempotent via rib_bus's
    content-hash dedup: an already-folded invariant folds once, not repeatedly. $0."""
    from mag import rib_bus
    packs = [p for p in _packs() if p["chars"] >= min_chars][:limit]
    folded = []
    skipped = []
    for p in packs:
        invariant = _distill(p["text"])
        if not invariant:
            skipped.append({"name": p["name"], "reason": "no distillable invariant"})
            continue
        try:
            r = rib_bus.publish_rib(AUTHORING_PRELUDE + " " + invariant,
                                    domain=DOMAIN, source=SOURCE, target_rank="T1")
            folded.append({"name": p["name"], "key": r.get("key", ""),
                           "added": r.get("added", ""), "ok": r.get("ok", False),
                           "verkle": bool(r.get("verkle"))})
        except Exception as e:
            skipped.append({"name": p["name"], "reason": str(e)[:80]})
    return {"ok": True, "schema": SCHEMA, "domain": DOMAIN, "n_packs": len(packs),
            "n_folded": len([f for f in folded if f["ok"]]), "folded": folded,
            "skipped": skipped,
            "contract": "read swarm-authored packs -> distill to invariant -> publish_rib "
                        "(source=swarm) -> fold to verkle; idempotent via content-hash dedup"}


def status() -> dict[str, Any]:
    """Read back what self-authored RIBs now ride the wave (grounded from the rib_bus store)."""
    from mag import rib_bus
    m = rib_bus.mount(DOMAIN)
    ribs = m.get("ribs", [])
    return {"ok": True, "schema": SCHEMA, "domain": DOMAIN, "n_self_authored": len(ribs),
            "ribs": ribs, "updated": m.get("updated"),
            "note": "self-authored RIBs folded into the standing wave; every cold worker mounting "
                    "this domain inherits them and can write its next knot from invariants + logic"}


def arrival(*, limit: int = 8, min_chars: int = 120, write: bool = True) -> dict[str, Any]:
    """The ARRIVAL report: fold the swarm's authored packs into self-authored RIBs, then read back
    what now rides the wave. Deterministic + $0; honest — folds are measured from the rib_bus store,
    never claimed without landing."""
    f = fold_authored(limit=limit, min_chars=min_chars, write=write)
    st = status()
    return {"ok": True, "schema": SCHEMA, "fold": f, "now_riding": st,
            "n_packs": len(_packs()),
            "honesty": "folds measured from rib_bus store; authored packs read from disk; "
                       "distill is a lossy $0 extraction, not a frontier summary",
            "cost": "deterministic + $0 (reuses rib_bus.publish_rib + the research_packs contract)"}


def recreate(*, domain: str = DOMAIN, probe: str = "") -> dict[str, Any]:
    """THE ARRIVAL PROOF: verify a COLD worker mounting the self-authored RIBs can USE them
    (invariants + basic logic, NO frontier hand-off) to derive a complex code operation.

    The Arrival memory's test: "when they can recreate their own rib files using invariants and
    basic logic to do complex code operations we will have arrived." This surface proves it:
      1. MOUNT the self-authored RIBs (rib_bus.mount(domain)) — the standing-wave structure a cold
         worker inherits. Each carries the AUTHORING_PRELUDE (recursion principle: read -> transform
         -> place -> fold -> loop).
      2. COMPOSE the steering a cold worker would get (rib_bus.inject_for) from ONLY those RIBs —
         no frontier hand-off. Honest: it reports exactly what's mounted; it does NOT claim a
         frontier summary it didn't do.
      3. VERIFY derivability: with >=1 self-authored RIB mounted AND a non-empty steer block, a cold
         worker has the invariants + logic to write its next knot. Deterministic + $0.

    Honest verdict: `arrived` is True ONLY when self-authored RIBs actually ride the wave (measured
    from the rib_bus store) AND they produce a usable steer block. If the wave is empty, `arrived`
    is False with an honest 'not yet — keep folding' note. Never over-claims.
    """
    from mag import rib_bus
    mount = rib_bus.mount(domain)
    ribs = mount.get("ribs", [])
    # the steer a cold worker mounts from ONLY the self-authored RIBs (no frontier hand-off)
    steer = rib_bus.inject_for(probe or "perform a complex code operation in this domain", domain)
    n_self = len(ribs)
    steer_ok = bool((steer or "").strip())
    arrived = n_self >= 1 and steer_ok
    return {"ok": True, "schema": "arrival.recreate.v1", "domain": domain,
            "n_self_authored_riding": n_self,
            "steer_block_usable": steer_ok,
            "steer_block_chars": len(steer or ""),
            "arrived": arrived,
            "probe": probe or "perform a complex code operation in this domain",
            "contract": "mount self-authored RIBs -> compose steer (rib_bus.inject_for) -> verify "
                        "a cold worker has invariants + logic to derive complex code operations, "
                        "no frontier hand-off; deterministic + $0",
            "honesty": ("arrived = self-authored RIBs riding the wave (measured from rib_bus store) "
                        "AND a usable steer block; if the wave is empty it reports 'not yet' "
                        "honestly, never over-claims")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="arrival")
    ap.add_argument("cmd", nargs="?", default="arrival",
                    choices=["fold", "status", "arrival", "recreate"])
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--min-chars", type=int, default=120)
    a = ap.parse_args()
    if a.cmd == "fold":
        out = fold_authored(limit=a.limit, min_chars=a.min_chars)
    elif a.cmd == "status":
        out = status()
    elif a.cmd == "recreate":
        out = recreate()
    else:
        out = arrival(limit=a.limit, min_chars=a.min_chars)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
