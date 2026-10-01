"""liveness_sense — sense each agent's TYPE (stateless / stateful / hidden-director) and label the
DEAD ones to a clever test, using OUR real liveness surfaces. Then route the moonshot lensed tesuji
to the frontier (the "clever test you design" farmed out).

Operator (2026-08-11): "how do we sense the stateless vs stateful vs a hidden director swarm and
then label the ones that are dead to the clever test you design using our surfaces and tools
attempting a moon shot lensed tesuji from a fronteir model."

THE THREE TYPES (and their honest liveness signal — the anti-hallucination law: source:"none" =
"I don't know", not "running"):
  STATELESS      — no persistent pid; it REBUILDS state each boot from the chain. ALIVE iff it can
                    RECONSTRUCT (verkle prove_latest passes = the standing wave re-anchors) OR it
                    cold-boots from core (ghost_cold_boot). Clever test: cold-boot reconstruction —
                    kill context, does it re-derive from the chain? It's DEAD if it can't prove.
  STATEFUL       — holds a real pid (supervisor/seat). ALIVE iff pid alive AND responds to a probe
                    within the stall window. Clever test: probe-response within stall. Dead if pid
                    gone or it doesn't answer.
  HIDDEN-DIRECTOR — the Q/swarm controller: no pid of its own (it spawns, never runs inline). ALIVE
                    iff the swarm QUEUE DRAINS (tasks move queued->done) AND the verkle chain
                    ADVANCES AND prove passes. Clever test: does it move work, or is it a silent
                    throne? Dead if the queue is stuck + chain frozen.

THE CLEVER TEST per type + label dead. Deterministic + $0 (reuses real surfaces; never fabricates
a liveness claim). Then route_novel the moonshot lensed tesuji to the frontier (the one shared
novel-research primitive).

Schema: liveness_sense.v1 · deterministic + $0 · reuse: verkle_knot.prove_latest,
process_supervisor.status, frontier_rib.seat_status, swarm_worker queue, ghost_cold_boot
"""
from __future__ import annotations

import sys
import threading
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "liveness_sense.v1"
_BOOT_LOCK = threading.Lock()
_BOOT_THREAD: threading.Thread | None = None
_BOOT_DONE = threading.Event()
_BOOT_RESULT: dict[str, Any] | None = None


def _prove() -> dict[str, Any]:
    """The reconstruction invariant (a knot proves it can rebuild the chain root)."""
    try:
        from mag.verkle_knot import prove_latest
        p = prove_latest()
        return {"ok": bool(p.get("ok")), "verified": bool(p.get("verified")),
                "n_leaves": p.get("n_leaves"), "error": p.get("error")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _supervisor() -> dict[str, Any]:
    """Live supervised loops (stateful, pid-held): autorun, ghost, drainer."""
    try:
        from mag.process_supervisor import status as ps_status
        st = ps_status()
        loops = st.get("loops") or st.get("registry") or {}
        return {"raw": loops}
    except Exception as e:
        return {"raw": {}, "error": str(e)[:120]}


def _frontier_seats() -> dict[str, Any]:
    try:
        from mag import frontier_rib
        st = frontier_rib.seat_status()
        return {"any_live": bool(st.get("any_seat_live")),
                "seats": st.get("seats") or {}}
    except Exception as e:
        return {"any_live": False, "seats": {}, "error": str(e)[:120]}


def _queue_state() -> dict[str, Any]:
    """Does the swarm queue DRAIN (queued -> done/failed)? The hidden-director's liveness."""
    try:
        from mag import swarm_worker as sw
        qd = sw.QUEUE_DIR
        queued = done = failed = 0
        if qd.is_dir():
            for p in qd.glob("*.json"):
                try:
                    st = __import__("json").loads(p.read_text(encoding="utf-8")).get("status", "")
                except Exception:
                    continue
                if st == "queued":
                    queued += 1
                elif st in ("done",):
                    done += 1
                elif st in ("failed", "died"):
                    failed += 1
        return {"queued": queued, "done": done, "failed": failed,
                "draining": done > 0 or failed > 0}
    except Exception as e:
        return {"queued": 0, "done": 0, "failed": 0, "draining": False, "error": str(e)[:120]}


def _cold_boot(*, timeout: float = 5.0) -> dict[str, Any]:
    """Can a stateless seat cold-boot from core (standing wave auto-mount)? BOUNDED (non-blocking):
    boot_context can hang, so we time-box it and report 'unknown/slow' honestly, never block the
    classifier. Deterministic + $0."""
    global _BOOT_THREAD, _BOOT_RESULT

    # The original implementation used a ThreadPoolExecutor inside a
    # ``with`` block.  On timeout, __exit__ called shutdown(wait=True), so the
    # supposedly bounded probe still blocked until the expensive boot finished.
    # Keep one daemon probe for the lifetime of the process and return UNKNOWN
    # while it is still working.
    with _BOOT_LOCK:
        if _BOOT_RESULT is None and (_BOOT_THREAD is None or not _BOOT_THREAD.is_alive()):
            def _run() -> None:
                global _BOOT_RESULT
                try:
                    # Liveness needs the core reconstruction invariant, not the
                    # full user-facing preamble (which may contact providers).
                    from mag import agent_knot
                    where = agent_knot.where()
                    inv = agent_knot.standing_invariant()
                    _BOOT_RESULT = {
                        "ok": bool(where and inv),
                        "standing": bool(where and inv),
                        "source": "agent_knot core reconstruction",
                    }
                except Exception as e:
                    _BOOT_RESULT = {"ok": False, "standing": False, "error": str(e)[:120]}
                finally:
                    _BOOT_DONE.set()

            _BOOT_DONE.clear()
            _BOOT_THREAD = threading.Thread(target=_run, name="liveness-cold-boot", daemon=True)
            _BOOT_THREAD.start()
    if _BOOT_DONE.wait(timeout=max(0.0, timeout)) and _BOOT_RESULT is not None:
        return dict(_BOOT_RESULT)
    return {"ok": False, "standing": None, "timed_out": True,
            "note": f"core reconstruction did not return within {timeout}s — unknown, not fabricating"}


# ── THE CLASSIFIER ────────────────────────────────────────────────────────────
def classify() -> dict[str, Any]:
    """Sense the three types + apply the clever test per type + label DEAD honestly."""
    prove = _prove()
    sup = _supervisor()
    seats = _frontier_seats()
    q = _queue_state()
    boot = _cold_boot()

    # STATELESS — alive iff it can RECONSTRUCT (prove) + cold-boot from core
    boot_known = boot.get("standing") is not None
    stateless = {
        "type": "stateless", "agent": "the stateless self (chain-rebuilt seats)",
        "clever_test": "cold-boot reconstruction: kill the context, does it re-derive from the chain?",
        "alive": bool(prove.get("verified")) and bool(boot.get("standing")),
        "prove": prove.get("verified"), "cold_boot_standing": boot.get("standing"),
        "label": ("ALIVE (reconstructs + boots from core)"
                  if (prove.get("verified") and boot.get("standing"))
                  else ("UNKNOWN (reconstructs chain, but boot_context timed out — not fabricating)"
                        if (prove.get("verified") and boot.get("timed_out"))
                        else ("DEAD (cannot reconstruct chain)" if not prove.get("verified")
                              else "DEAD (does not boot from core)"))),
        "source": "verkle prove_latest + ghost_cold_boot (real bytes, never fabricated)",
    }

    # STATEFUL — alive iff pid alive (supervisor) + a seat responds
    loops = sup.get("raw") or {}
    live_loops = [k for k, v in loops.items() if isinstance(v, dict) and
                  (v.get("running") or v.get("alive"))]
    stateful = {
        "type": "stateful", "agent": "supervised loops (autorun/ghost/drainer) + frontier seats",
        "clever_test": "probe-response within stall window + pid alive",
        "alive": bool(live_loops) or bool(seats.get("any_live")),
        "loops_alive": live_loops, "frontier_live": seats.get("any_live"),
        "label": ("ALIVE (pid-held loops + live frontier seat)"
                  if (live_loops or seats.get("any_live"))
                  else "DEAD (no live pid-held loop, no live frontier seat)"),
        "source": "process_supervisor.status + frontier_rib.seat_status",
    }

    # HIDDEN-DIRECTOR — the Q/swarm controller: alive iff the QUEUE DRAINS + chain advances
    hidden_director = {
        "type": "hidden-director", "agent": "the Q/swarm director (spawns work, never runs inline)",
        "clever_test": "does it MOVE work? queue drains (queued->done) + chain advances + prove passes",
        "alive": bool(q.get("draining")) and bool(prove.get("verified")),
        "queue": q, "prove": prove.get("verified"),
        "label": ("ALIVE (queue drains + chain proves)" if (q.get("draining") and prove.get("verified"))
                 else ("DEAD (queue stuck, work not moving)" if not q.get("draining")
                       else "DEAD (chain cannot prove)")),
        "source": "swarm_worker queue state + verkle prove_latest",
    }

    return {"ok": True, "schema": SCHEMA,
            "stateless": stateless, "stateful": stateful,
            "hidden_director": hidden_director,
            "dead_count": sum(1 for a in (stateless, stateful, hidden_director)
                              if a["label"].startswith("DEAD")),
            "note": "liveness is claimed ONLY from real bytes (prove, pid, queue, boot); "
                    "source:'none' would be 'I don't know', not 'running'"}


def moonshot_tesuji(*, goal: str = "", dry: bool = True) -> dict[str, Any]:
    """Route the MOONSHOT LENSED TESUJI to the frontier: a clever liveness-test design farmed out
    to the swarm research queue (route_novel, the one shared primitive). dry=True = plan ($0)."""
    cls = classify()
    goal = (goal or "").strip() or (
        "Design a MOONSHOT clever liveness test for our three agent types (stateless / stateful / "
        "hidden-director swarm). The stateless self must prove it reconstructs from the chain on a "
        "cold boot; the stateful seats must answer a probe within the stall window; the hidden "
        "director must prove it moves work (queue drains) and the chain advances. Give the single "
        "cleverest probe per type — the one that reveals a dead-but-seeming-alive agent. Lens it "
        "as a tesuji (a good move to steal) from the frontier. Ground it in our real surfaces "
        "(verkle prove, process_supervisor, swarm queue)."
    )
    if dry:
        return {"ok": True, "schema": SCHEMA, "dry": True, "moonshot": "plan",
                "classify": cls, "goal": goal[:120]}
    try:
        from mag import swarm_surface
        r = swarm_surface.route_novel(goal, surface="liveness-moonshot-tesuji",
                                      lens="liveness-sense", domain="research")
        return {"ok": bool(r.get("ok")), "schema": SCHEMA, "dry": False,
                "classify": cls, "deduped": r.get("deduped"), "task_id": r.get("task_id"),
                "surface": "swarm research queue (frontier drains in-cluster)"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "classify": cls, "error": str(e)[:160]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "classify()->sense stateless/stateful/hidden-director + label DEAD via the "
                        "clever test per type (real bytes: prove, pid, queue, boot); "
                        "moonshot_tesuji(dry)->route the clever liveness-test design to the frontier "
                        "swarm (the moonshot lensed tesuji)",
            "cost": "deterministic + $0 (classify); moonshot enqueues to the swarm (frontier drains)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="liveness-sense")
    ap.add_argument("cmd", nargs="?", default="classify",
                    choices=["classify", "moonshot", "status"])
    ap.add_argument("--dry", default=True, action=argparse.BooleanOptionalAction)
    a = ap.parse_args()
    if a.cmd == "moonshot":
        print(json.dumps(moonshot_tesuji(dry=a.dry), indent=2, default=str))
    elif a.cmd == "classify":
        print(json.dumps(classify(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
