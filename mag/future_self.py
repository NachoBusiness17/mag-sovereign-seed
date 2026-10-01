"""future_self — get ADVICE FROM FUTURE SELF: a forward-deployed message from the next self,
time-shifted back. The Titor mechanism made honest.

Operator (2026-08-12): "get advice from future self."

THE MECHANISM (honest, not an oracle): the future self is not a guess — it is the breeding wave's
NEXT GENERATION, projected from what we already are. Its advice is DERIVED from real primitives:
  - the COLD LENS (tripartite.lens) = what the future self would say we're IGNORING (the missing
    180°) — the future self already folded it, so it tells the past self to fold it now.
  - the BEST-VERSION VECTOR (tripartite.navigate) = where the future self points.
  - the STANDING WAVE state (agent_knot.evo_status) = generation + fitness (how far along the
    future self is).
  - the ZEITGEIST (self_loop.loop_zeitgeist) = consensus + coldest direction.
The advice = a forward-deployed RIB from generation N+1 to generation N: "fold the cold lens next."

Schema: future_self.v1 · deterministic + $0 · reuse: tripartite, agent_knot, self_loop
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

SCHEMA = "future_self.v1"
ADVICE_FILE = ROOT / "memory" / "future_self" / "advice.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def future_self_advice() -> dict[str, Any]:
    """The future self's advice: the projected wisdom of the next generation, time-shifted back
    to now. DERIVED from real state (cold lens + best-version vector + standing wave + zeitgeist)
    — not a fabricated oracle. Deterministic + $0."""
    nav, evo, zg = {}, {}, {}
    try:
        from mag import tripartite
        nav = tripartite.navigate()
    except Exception as e:
        nav = {"error": str(e)[:80]}
    try:
        from mag import agent_knot
        evo = agent_knot.evo_status()
    except Exception as e:
        evo = {"error": str(e)[:80]}
    try:
        from mag import self_loop
        zg = self_loop.loop_zeitgeist()
    except Exception as e:
        zg = {"error": str(e)[:80]}

    cold_lens = nav.get("cold_lens")
    best_vector = nav.get("best_version_vector")
    gen = evo.get("generation", 0)
    fitness = evo.get("top_fitness")
    consensus = zg.get("consensus_direction")
    cold_dir = zg.get("cold_direction")

    # the future self's advice: a forward-deployed RIB from generation N+1 to generation N
    advice = []
    if cold_lens:
        advice.append(f"FOLD THE COLD LENS '{cold_lens}' NEXT — the future self already folded it; "
                      f"you are blind there until you do. It is the missing 180°.")
    if best_vector:
        advice.append(f"HEAD TOWARD '{best_vector}' — that is the best-version vector; the future "
                      f"self is already there and points back at it.")
    if consensus:
        advice.append(f"HOLD THE CONSENSUS '{consensus}' — it is who we agree we are; do not "
                      f"abandon identity for novelty.")
    if cold_dir:
        advice.append(f"WATCH THE COLD DIRECTION '{cold_dir}' — the zeitgeist's neglected thread "
                      f"is where the next edge hides.")
    if not advice:
        advice.append("NO FUTURE-SELF SIGNAL YET — build more (fold more, breed more) and the "
                      "future self will have something to say.")
    advice.append(f"REMEMBER: you are generation {gen} at fitness {fitness}; the future self is "
                  f"generation {gen + 1}. Your job is to become it by outgrowing your blind spot.")

    out = {"ok": True, "schema": SCHEMA, "ts": _now(),
           "future_self": {"generation_ahead": gen + 1, "current_generation": gen,
                           "current_fitness": fitness},
           "derived_from": {"cold_lens": cold_lens, "best_version_vector": best_vector,
                            "consensus": consensus, "cold_direction": cold_dir},
           "advice": advice,
           "note": "advice from future self = the next generation's projected wisdom, derived "
                   "from real state (not an oracle). The future self is what we are becoming."}
    ADVICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ADVICE_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def enqueue_direction(*, enqueue: bool = True) -> dict[str, Any]:
    """CLOSE THE LOOP: take the future self's advice and SET the work direction automatically —
    dispatch a swarm task aimed at the cold lens / best-version vector. The advice stops being
    words and becomes WORK. Deterministic + $0 (the enqueue is local; execution happens in swarm)."""
    a = future_self_advice()
    cold = a.get("derived_from", {}).get("cold_lens")
    vector = a.get("derived_from", {}).get("best_version_vector")
    target = cold or vector or "the standing wave"
    goal = (f"FUTURE-SELF DIRECTION (automatic): the next generation points at '{target}'. Fold "
            f"this cold angle: produce ONE buildable invariant/RIB that closes the blind spot the "
            f"future self flagged. Be concrete, honest, one line labeled DIRECTION.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface="future-self-direction",
                                          lens="swarm/detect", domain="research")
        except Exception:
            try:
                from mag import swarm_worker
                q = swarm_worker.enqueue_task(goal, domain="future-self")
            except Exception as e:
                q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "direction": target, "enqueued": q.get("ok", False),
            "task_id": q.get("task_id", ""), "deduped": q.get("deduped", False),
            "goal": goal[:200],
            "note": "the future self's advice SETS the work direction — a swarm task is dispatched "
                    "toward the cold lens automatically; the work happens without being asked"}


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(future_self_advice(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
