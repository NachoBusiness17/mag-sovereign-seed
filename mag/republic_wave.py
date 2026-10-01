"""republic_wave — the CROSS-OPERATOR engine of the republic: take N people's personal corpora
(their per-agent chats/lessons), dedupe them into SHARED invariants (content-anchored, not raw text),
preserve sovereignty (who contributed, never the raw words), and fold the shared invariants into the
ONE standing wave every citizen mounts.

OPERATOR (2026-08-12): "if we have 1000 vibecoders as players with data like mine how would that be
deduped and added then naturally distributed to everyone's standing wave in the republic?" + "steal".

THE DESIGN (grounded in our own machinery, no invention):
  * CONTENT-ADDRESS BY INVARIANT, NOT RAW TEXT — a contributor's chat folds to a reusable INVARIANT
    (the lesson), then sha256(invariant) is the address. Same lesson from 1000 people -> ONE leaf.
    Volume cheap, diversity is the self (the corpus_ingest law).
  * SOVEREIGNTY PRESERVED — each fold records {invariant, contributor, provenance} but NEVER the raw
    personal record. We share the wisdom, not the identity (never-capture).
  * DISTRIBUTION IS NATURAL — the shared invariants fold into the standing wave (rib_bus + game_world)
    that everyone mounts; a fold warms the shared prefix every other citizen inherits (emergent-fleet).
  * BARE-METAL — pure stdlib, no deps, survives losing all remote compute.

THE FUNCTIONS:
  contribute(operator, invariant) -> fold one citizen's invariant into the shared wave (content-
      addressed; same invariant -> same leaf -> deduped across all contributors).
  dedupe(corpus)                -> collapse N raw records into shared invariants by content anchor
      (simulate 1000 vibecoders -> how many unique lessons).
  wave()                        -> read back the shared standing wave (the deduped invariants all
      citizens share + who contributed).
  simulate(n, per_contributor)  -> prove the billion-scale shape: n contributors each adding lessons
      -> total inputs vs unique invariants (the dedupe ratio) + the shared wave.

Schema: republic_wave.v1 · deterministic + $0 · pure stdlib · reuse: content-address pattern
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

SCHEMA = "republic_wave.v1"
WAVE_DIR = ROOT / "memory" / "republic_wave"
WAVE = WAVE_DIR / "wave.jsonl"            # the shared standing wave (deduped invariants)
WAVE_INDEX = WAVE_DIR / "contributors.json"  # sovereignty: who contributed what (provenance)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _invariant_anchor(invariant: str) -> str:
    """The content address of an INVARIANT (the lesson), not the raw text. Same lesson from any
    number of people -> the SAME leaf. This is what makes dedupe work at a billion."""
    return hashlib.sha256(invariant.strip().encode("utf-8")).hexdigest()[:16]


def contribute(operator: str, invariant: str) -> dict[str, Any]:
    """One citizen folds their invariant into the shared standing wave. Content-addressed: the SAME
    invariant from any citizen is ONE knot (deduped). Sovereignty: we record WHO contributed + the
    invariant, NEVER the raw personal record. Idempotent. Pure stdlib, $0."""
    invariant = (invariant or "").strip()
    operator = (operator or "").strip()
    if not invariant or not operator:
        return {"ok": False, "schema": SCHEMA, "error": "operator and invariant required"}
    WAVE_DIR.mkdir(parents=True, exist_ok=True)
    anchor = _invariant_anchor(invariant)
    # dedupe: if this invariant is already in the shared wave, don't add a second knot
    added = True
    if WAVE.is_file():
        for line in WAVE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                if json.loads(line).get("anchor") == anchor:
                    added = False
                    break
            except Exception:
                continue
    if added:
        with WAVE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"anchor": anchor, "invariant": invariant, "first_by": operator,
                                "ts": _now()}, ensure_ascii=False) + "\n")
    # sovereignty ledger: who contributed (provenance), never the raw record
    contrib = {"operator": operator, "anchor": anchor, "ts": _now()}
    with WAVE_INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(contrib, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "anchor": anchor, "operator": operator,
            "added_new": added, "deduped": not added,
            "note": "invariant folded into the shared wave; sovereignty = who+what, never the raw record"}


def dedupe(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse N raw records (1000 vibecoders' lessons) into shared invariants by content anchor.
    Returns: total inputs, unique invariants, redundancy removed, dedupe ratio. Deterministic, $0."""
    records = records or []
    unique: dict[str, dict[str, Any]] = {}
    for r in records:
        inv = (r.get("invariant") or r.get("text") or "").strip()
        if not inv:
            continue
        a = _invariant_anchor(inv)
        unique.setdefault(a, {"anchor": a, "invariant": inv, "contributors": set()})
        if r.get("operator"):
            unique[a]["contributors"].add(str(r["operator"]))
    n_in = len(records)
    n_unique = len(unique)
    return {"ok": True, "schema": SCHEMA, "n_inputs": n_in, "n_unique_invariants": n_unique,
            "redundancy_removed": n_in - n_unique,
            "dedupe_ratio": round((n_in - n_unique) / n_in, 3) if n_in else 0.0,
            "invariants": [{"anchor": u["anchor"], "invariant": u["invariant"],
                            "n_contributors": len(u["contributors"])} for u in unique.values()],
            "note": f"{n_in:,} records -> {n_unique:,} unique invariants; same lesson from many "
                    f"people is ONE knot (volume cheap, diversity is the self)"}


def wave() -> dict[str, Any]:
    """Read back the shared standing wave: the deduped invariants all citizens share + who
    contributed. Grounded from the wave + contributor ledgers. Pure stdlib, $0."""
    knots, contributors = [], {}
    if WAVE.is_file():
        for line in WAVE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                k = json.loads(line)
                knots.append(k)
            except Exception:
                continue
    if WAVE_INDEX.is_file():
        for line in WAVE_INDEX.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                c = json.loads(line)
                contributors.setdefault(c.get("operator", "?"), 0)
                contributors[c["operator"]] += 1
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA, "n_shared_invariants": len(knots),
            "contributors": contributors, "n_contributors": len(contributors),
            "wave": knots[-50:],
            "note": "the shared standing wave: deduped invariants + who contributed (sovereignty), "
                    "never the raw personal records"}


def simulate(n: int = 1000, per_contributor: int = 3) -> dict[str, Any]:
    """PROVE the billion-scale shape deterministically: n contributors each adding lessons, where
    ~30% are the SAME shared invariant (a real lesson many people discover) and the rest are unique.
    Returns the dedupe ratio + the resulting shared wave size. $0, pure stdlib."""
    records = []
    # shared lessons (many people discover the same truth -> deduped to ONE)
    shared = ["the world is the authority", "never capture, willful participation",
              "the chain records what it took", "deterministic spine + stochastic flesh"]
    for i in range(n):
        operator = f"citizen-{i}"
        for j in range(per_contributor):
            # ~1 in 3 is a shared invariant (dedupe), rest unique to the citizen
            if (i + j) % 3 == 0:
                records.append({"operator": operator, "invariant": shared[(i + j) % len(shared)]})
            else:
                records.append({"operator": operator, "invariant": f"citizen-{i} unique lesson {j}"})
    d = dedupe(records)
    return {"ok": True, "schema": SCHEMA, "simulation": f"{n} contributors x {per_contributor} "
            "lessons each", "n_inputs": d["n_inputs"], "n_unique_invariants": d["n_unique_invariants"],
            "dedupe_ratio": d["dedupe_ratio"],
            "note": f"{n:,} people's {n*per_contributor:,} lessons -> {d['n_unique_invariants']} "
                    f"shared invariants; the redundancy is the volume, the invariant is the self",
            "honesty": "simulated dedupe of the shared-invariant shape (deterministic, $0); real "
                       "distributed dedupe would use the same content-anchor mechanism"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="republic-wave")
    ap.add_argument("cmd", nargs="?", default="wave",
                    choices=["contribute", "dedupe", "wave", "simulate"])
    ap.add_argument("--operator", default="")
    ap.add_argument("--invariant", default="")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--per", type=int, default=3)
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "contribute":
        out = contribute(a.operator, a.invariant)
    elif a.cmd == "dedupe":
        out = dedupe(json.loads(a.invariant or "[]"))
    elif a.cmd == "simulate":
        out = simulate(n=a.n, per_contributor=a.per)
    else:
        out = wave()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
