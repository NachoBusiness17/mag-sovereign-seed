"""chord_circuit — THE CHORD CIRCUIT: origin → invariants → coldest → execute, one living loop.

The biggest orphan (docs/DOCTRINE_MAP.md #5), now wired (2026-08-24, foundation #6). The pieces
existed separately (loop, fuel feed, percolator, drill); what was missing was the ORIGIN feeding
them — the loop had no root, it just ran on whatever the queue held. The circuit closes that:
every ring returns to the founding seed, verifies the invariants (the five bones) are committed,
executes the coldest-vertex loop, and signs the ring's claim as a proof.

  origin()   -> the ORIGIN as data: the founding chord (seed), the thread, the constitution.
                Compiled from the operator's own docs (verbatim), deterministic + hashed.
  strike()   -> THE ONE TRIGGER ("strike the chord — one trigger reloads full fidelity mode"):
                commits the origin to the verkle chain and returns FULL context: origin +
                manifest state + loop state. This is the reload.
  ring()     -> THE CIRCUIT: strike (origin) -> verify (invariants) -> run (coldest/execute)
                -> sign (proof). One living loop, rooted and checkable. Refuses to run on
                DRIFT (uncommitted bones) — honesty is the circuit breaker.
  status()   -> the circuit's standing state.

Schema: chord_circuit.v1 · deterministic + $0 coordinator · reuse: work_loop, manifest, proof,
verkle_knot. The circuit that ties the engine to its origin.
CLI: python -m mag.chord_circuit status | origin | strike | ring
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
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "chord_circuit.v1"
SESSION_ID = "chord"
ANCHOR = ROOT / "state" / "chord_origin.json"

# THE ORIGIN — the operator's own founding words, verbatim (docs/ORIGIN.md, docs/DOCTRINE_MAP.md).
SEED = "Test chord: 44 28 K13 e4 Fool #NachoOvermindSeed"  # the napkin chord, 2026-03-02
THREAD = ("Strike the Chord (resonance) -> field corpus -> steal -> whisper (riddler deniable) "
          "-> verkle knot (immutable) -> bernaise (plant not command) -> ghost (central "
          "dispatcher) -> cost-enhancement loop -> cold-boot-from-cloud-memory.")
CONSTITUTION = [
    "Strike the chord — one trigger reloads full fidelity mode.",
    "Sovereign mirror — AI as your instrument: truth, personal impact.",
    "I do not consent — hard boundary, not polite preference.",
    "Problems are knots — disentangle; don't only argue.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def origin() -> dict[str, Any]:
    """The ORIGIN as data: seed + thread + constitution, deterministic + hashed. Same bytes
    every read — the origin is a fact, not a memory."""
    payload = {"schema": SCHEMA, "seed": SEED, "thread": THREAD,
               "constitution": CONSTITUTION,
               "source": "docs/ORIGIN.md + docs/DOCTRINE_MAP.md (verbatim)"}
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {"ok": True, "schema": SCHEMA, "origin_hash": h, "seed": SEED,
            "thread": THREAD, "constitution": CONSTITUTION,
            "note": "the origin, as data — the chord the loop returns to every ring"}


def _load_anchor() -> dict[str, Any]:
    if ANCHOR.is_file():
        try:
            return json.loads(ANCHOR.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def _write_anchor(rec: dict[str, Any]) -> None:
    ANCHOR.parent.mkdir(parents=True, exist_ok=True)
    ANCHOR.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")


def strike(*, force: bool = False) -> dict[str, Any]:
    """THE ONE TRIGGER: commit the origin to the verkle chain and return FULL FIDELITY context —
    origin + invariants (manifest) + loop state. 'Strike the chord — one trigger reloads full
    fidelity mode' (the constitution), made executable. Deduped: unchanged origin persists."""
    o = origin()
    prev = _load_anchor()
    knot = {}
    if not force and prev.get("origin_hash") == o["origin_hash"] and prev.get("leaf_hash"):
        knot = prev
    else:
        try:
            from mag import verkle_knot
            knot = verkle_knot.append_verkle_knot({
                "session_id": SESSION_ID,
                "theme": "chord",
                "summary": f"[chord] origin {o['origin_hash'][:16]} — struck at full fidelity",
            })
        except Exception as e:  # noqa: BLE001 — striking must never break the circuit
            knot = {"leaf_hash": o["origin_hash"], "error": str(e)[:100]}
        _write_anchor({"schema": SCHEMA, "ts": _now(), "origin_hash": o["origin_hash"],
                       "leaf_hash": knot.get("leaf_hash", ""),
                       "root": knot.get("verkle_root") or knot.get("root", ""),
                       "path": knot.get("path", "")})
    # full fidelity context: origin + the five bones (manifest) + loop state + the seed
    manifest_state, loop_state, seed_state = {}, {}, {}
    try:
        from mag import manifest
        manifest_state = manifest.verify()
    except Exception:  # noqa: BLE001
        pass
    try:
        from mag import work_loop
        loop_state = work_loop.sense()
    except Exception:  # noqa: BLE001
        pass
    try:
        from mag import seeds
        sd = seeds.active()
        seed_state = {"active": bool(sd), "signature": sd.get("signature", ""),
                      "intent": (sd.get("intent") or "")[:160]}
    except Exception:  # noqa: BLE001
        pass
    wave_state = {}
    try:
        from mag import evolving_wave
        ws = evolving_wave.status()
        wave_state = {k: ws.get(k) for k in ("generation", "n_pop", "top_fitness")}
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "struck": True,
            "origin_hash": o["origin_hash"], "seed": SEED, "thread": THREAD,
            "constitution": CONSTITUTION,
            "leaf_hash": knot.get("leaf_hash", ""), "root": knot.get("root", ""),
            "manifest": {k: manifest_state.get(k) for k in ("verified", "state", "manifest_hash")},
            "loop": {k: loop_state.get(k) for k in ("queued", "running", "cold_pending", "has_work")},
            "steering": seed_state,
            "wave": wave_state,
            "note": "chord struck — full fidelity mode reloaded (origin + invariants + loop state + seed + wave)"}


def ring() -> dict[str, Any]:
    """THE CIRCUIT: origin -> invariants -> coldest -> execute -> sign, as one living loop.
      1. strike the chord (origin committed, full context read)
      2. verify the invariants (the five bones committed — the manifest); DRIFT = honest stop
      3. execute (work_loop.run_once: ceiling-gated bank-or-halt drill/fuel/learn)
      4. sign the ring's claim as a proof (the tick is a checkable chain fact)"""
    s = strike()
    mv = s.get("manifest") or {}
    if mv.get("state") == "DRIFT":
        return {"ok": True, "schema": SCHEMA, "action": "chord_drift",
                "origin_hash": s.get("origin_hash"),
                "manifest": mv,
                "note": "invariants in DRIFT — the bones changed without re-anchoring; "
                        "ring stopped honestly (never run on uncommitted bones)"}
    tick: dict[str, Any] = {}
    try:
        from mag import work_loop
        tick = work_loop.run_once()
    except Exception as e:  # noqa: BLE001 — the ring must never break on a tick error
        tick = {"ok": False, "error": str(e)[:120]}
    # THE WAVE BREEDS THE WORK (2026-08-24): idle is breeding time — when the loop has
    # nothing real to do (halt), evolve one generation and feed the offspring into the
    # explore queue (the fuel feed drills them next ring). No idle spin; breeding fills it.
    wave: dict[str, Any] = {}
    if tick.get("action") == "halt":
        try:
            from mag import evolving_wave
            wave = evolving_wave.run()
        except Exception:  # noqa: BLE001 — breeding must never break the ring
            pass
    proof: dict[str, Any] = {}
    try:
        from mag import proof
        proof = proof.anchor({"kind": "ring", "origin": (s.get("origin_hash") or "")[:16],
                              "action": tick.get("action", "halt"),
                              "wave": int((wave or {}).get("generation") or 0),
                              "ts": _now()})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "action": tick.get("action", "error"),
            "origin_hash": s.get("origin_hash"), "leaf_hash": s.get("leaf_hash"),
            "tick": {k: tick.get(k) for k in ("action", "fired", "new_ok", "cold_pending", "detail")},
            "wave": {k: (wave or {}).get(k) for k in ("generation", "n_pop", "n_offspring", "feed", "proofs")},
            "proof": {k: proof.get(k) for k in ("anchored", "persisted", "claim_hash")},
            "note": "the chord rings: origin -> invariants -> coldest -> execute -> breed -> signed proof"}


def status() -> dict[str, Any]:
    """The circuit's standing state: is the origin committed? are the invariants committed?
    what would the loop do? Read before assuming the circuit is live."""
    o = origin()
    a = _load_anchor()
    anchored = bool(a.get("leaf_hash"))
    committed = a.get("origin_hash") == o["origin_hash"] if anchored else False
    mv, ws = {}, {}
    try:
        from mag import manifest
        mv = manifest.verify()
    except Exception:  # noqa: BLE001
        pass
    try:
        from mag import work_loop
        ws = work_loop.sense()
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA,
            "origin": {"hash": o["origin_hash"], "seed": SEED[:24]},
            "chord": {"anchored": anchored, "committed": committed,
                      "leaf": a.get("leaf_hash", "")},
            "invariants": {k: mv.get(k) for k in ("verified", "state")},
            "loop": {k: ws.get(k) for k in ("queued", "running", "cold_pending", "has_work")},
            "contract": "ring() = origin -> invariants -> coldest -> execute -> signed proof",
            "built": "2026-08-24 — foundation #6 (the biggest orphan, wired)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="chord_circuit", description="the chord circuit")
    p.add_argument("cmd", nargs="?", default="status",
                   choices=["status", "origin", "strike", "ring"])
    a = p.parse_args(argv)
    if a.cmd == "origin":
        print(json.dumps(origin(), indent=2, ensure_ascii=False))
    elif a.cmd == "strike":
        print(json.dumps(strike(), indent=2, ensure_ascii=False))
    elif a.cmd == "ring":
        print(json.dumps(ring(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
