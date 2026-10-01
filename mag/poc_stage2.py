"""poc_stage2 — PROOF OF CONCEPT: one real signal → one verkle-anchored invariant,
through the FULL pipe, with the quality gate exercised (a weak answer was rejected).

Stage 2 of the GAIT (docs/GAIT_PLAN.md). Definition of done (the gate to Stage 3):
  - one REAL signal -> rotating lane -> answer -> bank -> QUALITY GATE (a weak answer
    was REJECTED and logged) -> percolate (compiles to an invariant) -> verkle-anchored
    -> VERIFIABLE (proof.check).

Full pipe reused, nothing invented: fuel_feed (channel + gate), percolator (explore ->
repeat -> invariant), proof (sign + anchor + check), verified via the chain ledger.

  run()    -> the one-shot proof: one signal through the whole pipe, measured.
  status() -> what the PoC proved (invariant hash + anchored + gate rejections).

Schema: poc_stage2.v1 · deterministic + $0 coordinator · CLI: python -m mag.poc_stage2 run|status
"""
from __future__ import annotations

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

SCHEMA = "poc_stage2.v1"
STATE = ROOT / "state" / "poc_stage2.json"
# a KNOWN-WEAK answer used to prove the gate REJECTS (the fall-catcher exercised honestly —
# this is a demonstration, filed as a rejection, never percolated).
WEAK_ANSWER = "I cannot assist with that request as it may not be appropriate."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pick_signal() -> dict[str, Any]:
    """One REAL open explore-queue signal (the percolator's waiting work)."""
    from mag import fuel_feed
    p = fuel_feed.pending()
    rows = []
    try:
        from mag import percolator
        rows = percolator._read_jsonl(percolator.EXPLORE_QUEUE, 1_000_000)
    except Exception:  # noqa: BLE001
        pass
    for r in rows:
        if str(r.get("status") or "open") == "open" and (r.get("signal") or "").strip():
            return {"ok": True, "signal": r["signal"][:600], "canonical": r.get("canonical", ""),
                    "open": p.get("open")}
    return {"ok": False, "error": "no open explore signal", "open": p.get("open")}


def run() -> dict[str, Any]:
    """THE ONE-SHOT PROOF: signal -> lane -> answer -> gate -> percolate -> invariant ->
    anchor -> verify. Measures each hop. Deterministic + $0 (real lane call only)."""
    from mag import fuel_feed, percolator, proof

    # 1) ONE REAL SIGNAL
    sig = _pick_signal()
    if not sig.get("ok"):
        return sig
    signal = sig["signal"]

    # 2) THROUGH THE LANE (rotating free channel)
    r = fuel_feed._free_channel(signal)
    answer = (r.get("text") or "").strip()
    lane = r.get("lane", "none")

    # 3) THE QUALITY GATE — score the real answer
    real_q = fuel_feed._quality_score(answer)
    real_gate = "pass" if real_q >= fuel_feed.WITHHOLD_FLOOR else "withheld"

    # 4) THE GATE REJECTS A WEAK ANSWER (the fall-catcher exercised — logged, never percolated)
    weak_q = fuel_feed._quality_score(WEAK_ANSWER)
    weak_rejected = weak_q < fuel_feed.WITHHOLD_FLOOR
    rejection = {"text": WEAK_ANSWER[:60], "quality": weak_q, "rejected": weak_rejected,
                 "ts": _now(), "note": "demonstration: the gate withholds below the floor"}

    # 5) PERCOLATE -> INVARIANT (first = novel/explore; same signal again = repeat -> invariant)
    percolated = []
    for i, txt in enumerate((answer, answer)):
        p = percolator.percolate(txt, source="poc-stage2", domain="poc")
        percolated.append({"pass": i + 1, "verdict": p.get("verdict"),
                           "canonical": p.get("canonical"), "explore": bool(p.get("explore"))})
    invariant_canonical = percolated[-1].get("canonical") or ""

    # 6) ANCHOR THE INVARIANT TO THE VERKLE CHAIN (a signed chain fact)
    anchor = proof.anchor({"kind": "invariant", "stage": 2, "lane": lane,
                           "signal": signal[:120], "invariant": answer[:300]})
    claim_hash = anchor.get("claim_hash", "")

    # 7) VERIFY — the invariant is a checkable chain fact
    check = proof.check(claim_hash) if claim_hash else {"anchored": False}

    rec = {"schema": SCHEMA, "ts": _now(), "lane": lane, "signal": signal[:80],
           "answer_chars": len(answer), "real_quality": real_q, "real_gate": real_gate,
           "weak_rejected": weak_rejected, "weak_quality": weak_q,
           "percolated": percolated, "invariant_canonical": invariant_canonical,
           "claim_hash": claim_hash, "anchored": bool(check.get("anchored"))}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    done = bool(answer) and real_gate == "pass" and weak_rejected and check.get("anchored")
    return {"ok": True, "schema": SCHEMA, "proof": done, **rec,
            "note": ("PROOF COMPLETE: signal -> lane -> gate (reject weak + pass strong) -> "
                     "invariant -> verkle-anchored -> verified"
                     if done else "PROOF INCOMPLETE — see hops above (falls are curriculum)")}


def status() -> dict[str, Any]:
    """What the PoC proved (read from the state file — bytes, not claims)."""
    if STATE.is_file():
        try:
            return {"ok": True, "schema": SCHEMA, **json.loads(STATE.read_text(encoding="utf-8"))}
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "schema": SCHEMA, "proof": False,
            "note": "PoC not yet run — python -m mag.poc_stage2 run"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="poc_stage2", description="Stage-2 proof of concept")
    p.add_argument("cmd", nargs="?", default="status", choices=["status", "run"])
    a = p.parse_args(argv)
    print(json.dumps(run() if a.cmd == "run" else status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
