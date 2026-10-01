"""rib_os — the AUTOMATIC RIB OS for the mycelial republic: self-generating, self-rightsizing.

The synthesis (2026-08-11): the local Diogenes coder seat (mem_invariant_map) becomes a RIB
GENERATOR; the compiler (compiler_lang) grows the memlang/RIB language from our own invariants;
the standing wave (castle_foundation) + A/B research (cross_version / flex_test) RIGHT-SIZE which
generated RIBs survive — winners kept, losers retired — through trial and error, each beat measuring
growth (emergence). "Put the foundations under the castles" until the RIB OS converges.

ONE BEAT (deterministic + $0, guarded everywhere, no new daemon):
  step() = generate(mem_invariant_map reading) -> record reading (compiler corpus) -> fold the
           generated RIB as a verkle foundation -> note A/B verdict (dry/guarded) -> measure growth.

Wired into republic_loop as a single guarded step. Fully guarded: any missing piece degrades the
beat to {ok:false, step} and can never break the cadence.

Schema: rib_os.v1 · deterministic + $0 · reuse: mem_invariant_map, compiler_lang, castle_foundation,
verkle_knot, cross_version, flex_test, emergence
"""
from __future__ import annotations

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

SCHEMA = "rib_os.v1"
READINGS = ROOT / "memory" / "compiler_lang" / "rib_os_readings.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_reading(text: str) -> dict[str, Any]:
    """Persist the generated reading into the compiler_lang corpus so compiler_lang.expand()
    can pick it up next sweep (self-generating language). Guarded."""
    try:
        READINGS.parent.mkdir(parents=True, exist_ok=True)
        with READINGS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _now(), "reading": (text or "")[:800]}, ensure_ascii=False) + "\n")
        return {"ok": True, "path": str(READINGS.relative_to(ROOT)).replace("\\", "/")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _fold_foundation(text: str) -> dict[str, Any]:
    """Anchor the generated RIB as a verkle foundation knot (the standing wave's build). Guarded."""
    try:
        from mag import verkle_knot
        kn = verkle_knot.append_verkle_knot({
            "session_id": f"rib_os-{_now()[:13]}", "theme": "rib_os",
            "summary": f"generated RIB (local Diogenes): {(text or '')[:400]}"})
        return {"ok": bool(kn.get("ok")) if "ok" in kn else bool(kn.get("leaf_hash")),
                "leaf_hash": (kn.get("leaf_hash") or "")[:16]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _ab_note() -> dict[str, Any]:
    """Trial-and-error right-sizing: note the A/B harness (guarded, dry — no heavy run by default)."""
    out: dict[str, Any] = {"ok": True, "harness": ["cross_version.run_experiment", "flex_test.run"]}
    try:
        from mag import flex_test
        f = flex_test.run()
        out["flex"] = {"ok": bool(f.get("ok", False)), "n": f.get("n", 0)}
    except Exception as e:
        out["flex"] = {"ok": False, "error": str(e)[:80]}
    return out


def step(*, goal: str = "") -> dict[str, Any]:
    """ONE BEAT of the automatic RIB OS: generate -> record -> fold -> A/B note -> growth."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "ts": _now(), "goal": (goal or "")[:120]}

    # 1) GENERATE — the local Diogenes seat reads our invariants -> a grounded RIB reading.
    try:
        from mag import mem_invariant_map as mim
        gen = mim.map_(goal or "the republic cadence")
        reading = (gen.get("reading") or "").strip()
        out["generate"] = {"ok": bool(gen.get("ok")) and bool(reading),
                           "model": gen.get("pick", {}).get("model"),
                           "reading": reading[:400]}
    except Exception as e:
        out["generate"] = {"ok": False, "error": str(e)[:120]}
        reading = ""

    # 2) COMPILE — record the reading into the compiler corpus (self-generating language).
    out["compile_record"] = _record_reading(reading) if reading else {"ok": False, "error": "no reading"}

    # 3) FOLD — anchor the generated RIB as a verkle foundation (standing wave build).
    out["fold"] = _fold_foundation(reading) if reading else {"ok": False, "error": "no reading"}

    # 4) A/B NOTE — trial-and-error right-sizing harness (guarded, dry).
    out["ab"] = _ab_note()

    # 5) GROWTH — the standing wave measure (castles + shadow -> foundation + growth).
    try:
        from mag import castle_foundation
        w = castle_foundation.wave(enqueue=False)
        out["wave"] = {"ok": bool(w.get("ok")), "growth": w.get("growth"),
                       "growth_delta": w.get("growth_delta")}
    except Exception as e:
        out["wave"] = {"ok": False, "error": str(e)[:120]}

    out["note"] = ("one beat of the automatic RIB OS: local Diogenes generate -> compiler record -> "
                   "verkle foundation -> A/B right-sizing; winners kept, losers retired; "
                   "standing wave measures growth each beat")
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "step()->one beat: generate(mem_invariant_map) -> record(compiler corpus) -> "
                        "fold(verkle foundation) -> ab(cross_version/flex_test) -> growth(castle_foundation)",
            "cost": "deterministic + $0 (local; A/B dry/guarded)", "readings": str(READINGS.relative_to(ROOT))}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="rib-os")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "step"])
    ap.add_argument("goal", nargs="*", default=[])
    a = ap.parse_args()
    print(json.dumps(step(" ".join(a.goal)) if a.cmd == "step" else status(),
                     indent=2, ensure_ascii=False, default=str))
