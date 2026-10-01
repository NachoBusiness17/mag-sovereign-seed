"""seeds — STEERING-BY-SEEDING (bernaise): plant intent as a seed, not a command (2026-08-24).

The orphan (docs/DOCTRINE_MAP.md #5): "partial — loop takes a queue, not seeds." Bernaise
plants moves into the inbox; what was missing is the LOOP taking a seed. This is that seam:

  plant()   -> plant a compact intent seed (signature = the chord-like key), anchored as a
               SIGNED chain fact (proof). Plant-not-command: the seed biases, never orders.
  active()  -> the current seed (last planted) — read before the loop picks work.
  rank()    -> re-rank discovered cold vertices by overlap with the seed's terms, so the
               drill leans toward the planted direction. No seed -> original order. The
               loop still only touches REAL discovered work (never fabricates toward a seed).
  status()  -> the seed store.

Wired: ox_resident.run() (the drill ranks seed-aware) + chord_circuit.strike() (the seed is
part of full-fidelity context).

Schema: seeds.v1 · deterministic + $0 · reuse: proof (anchor), ox_resident (target_cells)
CLI: python -m mag.seeds plant "<intent>" --sig "<signature>" | active | status
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "seeds.v1"
SEED_FILE = ROOT / "memory" / "seeds" / "active.json"
LEDGER = ROOT / "memory" / "seeds" / "seeds.jsonl"

# deterministic term filter (small, cheap, no imports beyond re)
STOP = {"this", "that", "with", "from", "have", "into", "they", "will", "what", "when",
        "your", "the", "and", "for", "are", "how", "why", "our", "their", "these",
        "those", "where", "which", "while", "about", "each", "more", "most", "other",
        "some", "such", "than", "then", "there", "them", "been", "being", "were",
        "would", "could", "should", "does", "doing", "done", "also", "just", "only",
        "very", "can", "may", "might", "must", "shall", "not", "but", "its", "has",
        "had", "one", "two", "new", "use", "used", "make", "made"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(s: str, n: int = 40) -> str:
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in (s or "seed").lower())
    return (s or "seed")[:n]


def _terms(text: str) -> list[str]:
    """Deterministic keyword terms from free text (the steering vocabulary)."""
    toks = re.findall(r"[a-z0-9]{4,}", (text or "").lower())
    return [t for t in toks if t not in STOP]


def plant(intent: str, signature: str = "", *, source: str = "operator") -> dict[str, Any]:
    """PLANT a seed: compact intent + a chord-like signature, anchored as a signed chain
    fact. Plant-not-command: the seed biases the drill's ranking; it never orders the loop."""
    intent = (intent or "").strip()
    if not intent:
        return {"ok": False, "schema": SCHEMA, "error": "empty intent"}
    sig = (signature or "").strip() or _slug(intent)
    terms = _terms(intent)
    rec = {"schema": SCHEMA, "intent": intent[:400], "signature": sig[:120],
           "terms": terms, "source": source, "ts": _now()}
    SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEED_FILE.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass
    proof: dict[str, Any] = {}
    try:
        from mag import proof
        proof = proof.anchor({"kind": "seed", "signature": sig, "intent": intent[:200]})
    except Exception:  # noqa: BLE001 — anchoring must never break planting
        pass
    return {"ok": True, "schema": SCHEMA, "signature": sig, "terms": terms,
            "source": source, "ts": _now(),
            "proof": {k: proof.get(k) for k in ("anchored", "persisted", "claim_hash")},
            "note": "planted — the seed steers the loop's drill (plant-not-command)"}


def active() -> dict[str, Any]:
    """The current seed (last planted). Empty dict = no seed = the loop runs un-steered."""
    if SEED_FILE.is_file():
        try:
            return json.loads(SEED_FILE.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def rank(cells: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Re-rank discovered cold vertices by overlap with the active seed's terms. The seed
    STEERS (biases), it never commands: no seed -> original variants order, and the cells
    are still only REAL discovered work (never fabricated toward a seed)."""
    if not cells:
        return cells or []
    seed = active()
    terms = seed.get("terms") or []
    if not terms:
        return sorted(cells, key=lambda c: -int(c.get("variants") or 1))
    scored = []
    for c in cells:
        blob = _terms(f"{c.get('core', '')} {c.get('scope', '')}")
        overlap = len(set(blob) & set(terms))
        scored.append((overlap, int(c.get("variants") or 1), c))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [c for _, _, c in scored]


def status() -> dict[str, Any]:
    seed = active()
    n_ledger = 0
    if LEDGER.is_file():
        try:
            n_ledger = sum(1 for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "schema": SCHEMA,
            "active": bool(seed),
            "seed": {"signature": seed.get("signature", ""), "intent": (seed.get("intent") or "")[:200],
                     "terms": seed.get("terms") or []},
            "planted_total": n_ledger,
            "contract": "plant() a seed -> the drill leans toward it (rank), never commanded; "
                        "no seed -> the loop runs un-steered",
            "built": "2026-08-24 — steering-by-seeding (bernaise) wired into the loop"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="seeds", description="steering-by-seeding")
    sub = p.add_subparsers(dest="cmd")
    p_plant = sub.add_parser("plant", help="plant an intent seed")
    p_plant.add_argument("intent", help="the planted intent (compact)")
    p_plant.add_argument("--sig", default="", help="chord-like signature")
    p_plant.add_argument("--source", default="operator")
    sub.add_parser("active")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "plant":
        print(json.dumps(plant(a.intent, a.sig, source=a.source), indent=2, ensure_ascii=False))
    elif a.cmd == "active":
        print(json.dumps(active(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
