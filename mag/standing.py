"""standing — STAGE 3: the loop runs bounded, all lanes rotating, ceiling held,
quality-gated, WITHOUT babysitting (2026-08-24).

Stage 3 of the GAIT (docs/GAIT_PLAN.md): survive a defined window unattended, bank per
tick, no lane saturated, no chain pollution. This is the runner + the metric ledger.

  run_once()  -> one ring with full telemetry (action, cpu, banked, wave, proof) -> ledger.
  run_loop()  -> the standing loop: ring -> record -> sleep (0% CPU between rings) ->
                 repeat until the window elapses or state/standing.stop appears.
  status()    -> the Stage-3 metric (from the ledger — bytes, not claims): uptime, rings,
                 banked-per-tick, per-lane share, CPU held, gate state.
  stop()      -> plant state/standing.stop (the operator stops WITHOUT killing).

Everything the loop needs already exists (chord_circuit.ring: origin -> invariants ->
coldest -> execute -> breed -> signed proof; ceiling-at-poll; quality gate; rotation).
This module ONLY rings on cadence and records. It never spins: it sleeps at 0% CPU between
rings, and the ceiling gate refuses work when the machine is hot.

Schema: standing.v1 · deterministic + $0 · reuse: chord_circuit, cadence_learn, fuel_feed
CLI: python -m mag.standing run [--window MIN] | once | status | stop
"""
from __future__ import annotations

import json
import os
import sys
import time
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

SCHEMA = "standing.v1"
RINGS = ROOT / "memory" / "runs" / "standing" / "rings.jsonl"
STOP = ROOT / "state" / "standing.stop"
WINDOW_STATE = ROOT / "state" / "standing_window.json"  # the window goal on disk (survives restart)
DEFAULT_CADENCE = 90        # seconds between rings (stateless + usage available = tight loop)
DEFAULT_WINDOW = 360        # minutes — the Stage-3 standing window (6h)
SEAL_EVERY = 20             # rings between SEAL-THE-MEMORY snapshots (tracks the chain; ~30m @90s)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fold(rec: dict[str, Any]) -> None:
    try:
        RINGS.parent.mkdir(parents=True, exist_ok=True)
        with RINGS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:  # noqa: BLE001 — recording must never break the loop
        pass


def _rows() -> list[dict[str, Any]]:
    if not RINGS.is_file():
        return []
    out = []
    try:
        for line in RINGS.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    pass
    except OSError:
        return []
    return out


def run_once() -> dict[str, Any]:
    """ONE ring with telemetry: measure CPU before, ring the full circuit, record every hop
    to the Stage-3 ledger. This is what a standing tick IS — measured, not claimed."""
    from mag import cadence_learn
    h = cadence_learn.headroom()
    cpu = h.get("cpu_pct")
    throttled = bool(h.get("throttle"))
    try:
        from mag import chord_circuit
        r = chord_circuit.ring()
    except Exception as e:  # noqa: BLE001 — the ring must never break the standing loop
        rec = {"schema": SCHEMA, "ts": _now(), "action": "ring_error",
               "error": str(e)[:160], "cpu_pct": cpu, "throttled": throttled}
        _fold(rec)
        return {"ok": False, "schema": SCHEMA, **rec}
    tick = r.get("tick") or {}
    wave = r.get("wave") or {}
    rec = {"schema": SCHEMA, "ts": _now(), "action": r.get("action", "?"),
           "cpu_pct": cpu, "throttled": throttled,
           "banked": tick.get("new_ok"), "fired": tick.get("fired"),
           "cold_pending": tick.get("cold_pending"),
           "wave_gen": wave.get("generation"), "n_offspring": wave.get("n_offspring"),
           "proof": (r.get("proof") or {}).get("claim_hash", ""),
           "origin": (r.get("origin_hash") or "")[:16],
           "note": (r.get("note") or "")[:120]}
    _fold(rec)
    return {"ok": True, "schema": SCHEMA, **rec}


def _load_window() -> dict[str, Any]:
    if WINDOW_STATE.is_file():
        try:
            return json.loads(WINDOW_STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def _save_window(w: dict[str, Any]) -> None:
    try:
        WINDOW_STATE.parent.mkdir(parents=True, exist_ok=True)
        WINDOW_STATE.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _window_goal(window_min: int) -> dict[str, Any]:
    """RESUME-AWARE window goal (2026-08-24, the operator's shutdown concern): the window is a
    WALL-CLOCK goal on disk. If a window is already in progress (end_ts in the future), RESUME
    it instead of starting fresh — a shutdown/restart pauses the window, it does not erase it.
    The ledger is cumulative, so rings already banked always count."""
    w = _load_window()
    now = time.time()
    if w.get("window_min") == window_min and float(w.get("end_ts", 0)) > now:
        return {"resume": True, "start_ts": float(w["start_ts"]),
                "end_ts": float(w["end_ts"]), "window_min": window_min}
    start = now
    end = now + window_min * 60.0
    _save_window({"window_min": window_min, "start_ts": start, "end_ts": end,
                  "ts": _now(), "resumed_from_rings": len(_rows())})
    return {"resume": False, "start_ts": start, "end_ts": end, "window_min": window_min}


def _seal() -> dict[str, Any]:
    """SEAL-THE-MEMORY on cadence (2026-08-24, the triangulated direction): snapshot the
    ground truth (chain + ledgers + doctrine) so the self tracks its own survival. Never
    breaks the loop; a failed seal is recorded, not fatal."""
    try:
        from mag import seal
        s = seal.seal()
        _fold({"schema": SCHEMA, "ts": _now(), "action": "sealed",
               "verified": bool(s.get("verified")), "n_files": s.get("n_files"),
               "n_live": s.get("n_live"),
               "proof": (s.get("proof") or {}).get("claim_hash", "")})
        return s
    except Exception as e:  # noqa: BLE001 — sealing must never break the standing loop
        _fold({"schema": SCHEMA, "ts": _now(), "action": "seal_error", "error": str(e)[:160]})
        return {"ok": False, "error": str(e)[:120]}


def run_loop(*, window_min: int | None = None, cadence: int | None = None,
             max_rings: int | None = None, seal_every: int | None = None) -> dict[str, Any]:
    """THE STANDING LOOP: ring -> record -> sleep (0% CPU) -> repeat. Stops on:
       - window elapsed (default 6h), or
       - state/standing.stop appears (operator-controlled), or
       - max_rings (safety bound). Never spins; sleeps between rings at 0% CPU.
    SHUTDOWN-SAFE: the window goal + every ring live on disk. If the machine powers off and
    comes back, the next run RESUMES the same window (rings already banked still count)."""
    cadence = cadence or int(os.environ.get("MAG_STANDING_CADENCE", DEFAULT_CADENCE))
    window = (window_min if window_min is not None
              else int(os.environ.get("MAG_STANDING_WINDOW", DEFAULT_WINDOW)))
    if STOP.is_file():
        try:
            STOP.unlink()
        except OSError:
            pass
    goal = _window_goal(window)
    start_ts = goal["start_ts"]
    end_ts = goal["end_ts"]
    rings_before = len(_rows())
    rings = 0
    errors = 0
    seals = 0
    seal_every = seal_every or int(os.environ.get("MAG_SEAL_EVERY", SEAL_EVERY))
    while True:
        if STOP.is_file():
            break
        if time.time() >= end_ts:
            break
        if max_rings and rings >= max_rings:
            break
        r = run_once()
        if not r.get("ok"):
            errors += 1
        rings += 1
        # SEAL-THE-MEMORY on cadence: every seal_every rings, snapshot the ground truth
        # so the seal tracks the chain (the self survives its body via the chain).
        if rings % seal_every == 0:
            s = _seal()
            if s.get("ok") and s.get("verified"):
                seals += 1
        # sleep between rings at 0% CPU (bounded, operator can stop via the marker)
        slept = 0
        while slept < cadence:
            if STOP.is_file():
                break
            time.sleep(1)
            slept += 1
    # final seal on stop — the last state is always captured
    if rings > 0 and (rings % seal_every) != 0:
        _seal()
    elapsed_min = round((time.time() - start_ts) / 60.0, 1)
    if not STOP.is_file():
        try:
            WINDOW_STATE.unlink()
        except OSError:
            pass
    return {"ok": True, "schema": SCHEMA, "stopped": True, "rings": rings,
            "rings_before": rings_before, "errors": errors, "seals": seals,
            "elapsed_min": elapsed_min, "window_min": window, "cadence_s": cadence,
            "seal_every": seal_every,
            "resumed": bool(goal.get("resume")),
            "stopped_by": ("stop-marker" if STOP.is_file()
                           else "window" if time.time() >= end_ts
                           else "max-rings")}


def status() -> dict[str, Any]:
    """THE STAGE-3 METRIC — from the ledger (bytes, not claims): uptime, rings, banked-per-
    tick, per-lane share (fuel profile), CPU held, gate state."""
    rows = _rows()
    n = len(rows)
    actions: dict[str, int] = {}
    banked_total = 0
    banked_ticks = 0
    cpu_vals = []
    throttled = 0
    for r in rows:
        a = str(r.get("action") or "?")
        actions[a] = actions.get(a, 0) + 1
        b = r.get("banked")
        if isinstance(b, (int, float)):
            banked_total += int(b)
            banked_ticks += 1
        if isinstance(r.get("cpu_pct"), (int, float)):
            cpu_vals.append(float(r["cpu_pct"]))
        if r.get("throttled"):
            throttled += 1
    fuel = {}
    try:
        from mag import fuel_feed
        fuel = fuel_feed.profile()
    except Exception:  # noqa: BLE001
        pass
    disk = {}
    try:
        from mag import ox_resident
        disk = ox_resident.banked()  # ground truth: the artifacts on disk, not the stale ledger
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "rings": n, "actions": actions,
            "banked_total": banked_total,
            "banked_per_ring": round(banked_total / n, 3) if n else 0.0,
            "banked_on_disk": (disk or {}).get("banked", 0),
            "banked_chars_on_disk": (disk or {}).get("substance_chars", 0),
            "banked_cores_on_disk": (disk or {}).get("cores", 0),
            "cpu_avg": round(sum(cpu_vals) / len(cpu_vals), 1) if cpu_vals else None,
            "cpu_max": round(max(cpu_vals), 1) if cpu_vals else None,
            "throttled_rings": throttled,
            "gate": {k: fuel.get(k) for k in ("gate_to_stage2",)},
            "lanes": (fuel.get("lanes") or {}),
            "stop_marker": STOP.is_file(),
            "contract": "run_loop() = ring on cadence, sleep at 0% CPU, stop via marker/window; "
                        "status() reads the ledger — banked_on_disk is the GROUND TRUTH artifact "
                        "count, banked_total is this window's per-ring flow",
            "built": "2026-08-24 — Stage 3 standing runner"}


def stop() -> dict[str, Any]:
    """Plant the stop marker — the operator stops the standing loop WITHOUT killing it."""
    try:
        STOP.parent.mkdir(parents=True, exist_ok=True)
        STOP.write_text(_now(), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}
    return {"ok": True, "schema": SCHEMA, "stopped": True,
            "note": "stop marker planted — the standing loop exits at its next check"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="standing", description="Stage-3 standing runner")
    p.add_argument("cmd", nargs="?", default="status",
                   choices=["status", "once", "run", "stop"])
    p.add_argument("--window", type=int, default=None, help="window in minutes (run)")
    p.add_argument("--cadence", type=int, default=None, help="seconds between rings (run)")
    p.add_argument("--max-rings", type=int, default=None, help="safety ring bound (run)")
    a = p.parse_args(argv)
    if a.cmd == "once":
        print(json.dumps(run_once(), indent=2, ensure_ascii=False))
    elif a.cmd == "run":
        print(json.dumps(run_loop(window_min=a.window, cadence=a.cadence,
                                  max_rings=a.max_rings), indent=2, ensure_ascii=False))
    elif a.cmd == "stop":
        print(json.dumps(stop(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
