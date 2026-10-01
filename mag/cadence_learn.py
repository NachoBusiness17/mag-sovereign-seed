"""cadence_learn — learn the parallel provider-launch cadence + hold a CPU ceiling (2026-08-23).

Operator (2026-08-23, handing off to family): "run this shit autonomously but leave enough for her
to operate the computer. don't hog 100% of cpu keep it at 90%. i want you to iterate and learn
cadence and parallel launches of providers."

Self-steal: we already had resource_governor (k8s) + afk_loop.right_size (budget levels) but NO
LOCAL CPU-ceiling governor for the DESKTOP's parallel provider launches. This is that missing seam.

WHAT IT DOES
  ceiling()          — the CPU ceiling (default 90, override MAG_CPU_CEILING).
  headroom()         — current system CPU% + how much room is left before the ceiling.
  throttled_workers(base) — pick a worker count for parallel provider launches so aggregate CPU
                      stays AT/BELOW the ceiling (shrink as CPU climbs, grow back when it cools).
  learn(round)       — fold one round's real timing/CPU/ok into a ledger; a tiny adaptive learner
                      bumps/lowers the "learned" worker ceiling based on whether we stayed under.
  learned_workers()  — the persisted learned worker cap (starts at base, adapts over rounds).

All deterministic + $0 (psutil read only). Guards: missing psutil -> safe defaults (no throttle).
Schema: cadence_learn.v1
CLI:  python -m mag.cadence_learn status | sample | learn
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

SCHEMA = "cadence_learn.v1"
STATE = ROOT / "state" / "cadence_learn.json"
LEDGER = ROOT / "memory" / "runs" / "cadence_learn" / "rounds.jsonl"

DEFAULT_CEILING = 90.0          # keep aggregate CPU at/below this so the operator can use the box
DEFAULT_BASE = 8                # starting parallel worker cap (matches real_swarm concurrency)
STEP = 2                        # how much to move the learned worker cap per round


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ceiling() -> float:
    try:
        return float(sysenv("MAG_CPU_CEILING", str(DEFAULT_CEILING)))
    except Exception:  # noqa: BLE001
        return DEFAULT_CEILING


def sysenv(k: str, d: str) -> str:
    import os
    return os.environ.get(k, d)


def _cpu_pct() -> float | None:
    try:
        import psutil
        return float(psutil.cpu_percent(interval=0.25))
    except Exception:  # noqa: BLE001
        return None


def headroom() -> dict[str, Any]:
    """Current CPU% + how much room is left before the ceiling."""
    cpu = _cpu_pct()
    cap = ceiling()
    if cpu is None:
        return {"ok": True, "schema": SCHEMA, "cpu_pct": None, "ceiling": cap,
                "headroom_pct": None, "throttle": False,
                "note": "no psutil — cannot measure; assume safe (no throttle)"}
    return {"ok": True, "schema": SCHEMA, "cpu_pct": cpu, "ceiling": cap,
            "headroom_pct": round(max(0.0, cap - cpu), 1),
            "throttle": bool(cpu >= cap),
            "note": f"{(cpu >= cap and 'at/above ceiling — shrink workers') or 'under ceiling — ok'}"}


def _read_state() -> dict[str, Any]:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "schema": SCHEMA, "learned_workers": DEFAULT_BASE,
            "rounds": 0, "last_ts": None}


def _write_state(st: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def learned_workers() -> int:
    """The persisted learned worker cap (starts at DEFAULT_BASE, adapts over rounds)."""
    st = _read_state()
    return int(st.get("learned_workers") or DEFAULT_BASE)


def throttled_workers(base: int | None = None) -> int:
    """Pick a worker count for a parallel launch so aggregate CPU stays at/below the ceiling.
    Keep FULL parallelism while system CPU is under the throttle floor (50%); taper linearly
    toward 1 worker as CPU climbs from the floor to the ceiling. The operator said "don't hog
    100% cpu keep it at 90%" — so we run the work up to the ceiling but never past it."""
    base = base or learned_workers()
    cap = ceiling()
    cpu = _cpu_pct()
    if cpu is None:
        return base
    floor = 50.0  # below this system CPU%, run full parallelism (don't starve the work)
    if cpu <= floor:
        return base
    if cpu >= cap:
        return 1
    # taper: from floor (base workers) to ceiling (1 worker)
    frac = (cap - cpu) / max(1.0, cap - floor)
    workers = max(1, int(round(base * frac)))
    return min(workers, base)


def _fold(rec: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def learn(round_rec: dict[str, Any]) -> dict[str, Any]:
    """Fold one real parallel round: timing, workers, ok, cpu. Adapt the learned worker cap.
    If we ran at/above ceiling -> step DOWN. If we had headroom AND success -> step UP (bounded)."""
    st = _read_state()
    cap = ceiling()
    cpu = round_rec.get("cpu_pct")
    workers = int(round_rec.get("workers") or DEFAULT_BASE)
    ok = bool(round_rec.get("ok"))
    cur = int(st.get("learned_workers") or DEFAULT_BASE)

    if cpu is not None:
        if cpu >= cap:
            cur = max(1, cur - STEP)      # we burned the box — shrink
        elif ok and cpu < cap - 10:
            cur = min(DEFAULT_BASE * 2, cur + STEP)  # headroom + success — grow (bounded)

    st["learned_workers"] = cur
    st["rounds"] = int(st.get("rounds") or 0) + 1
    st["last_ts"] = _now()
    _write_state(st)

    rec = {"schema": SCHEMA, "ts": _now(), "cpu_pct": cpu, "workers": workers,
           "ok": ok, "learned_workers": cur, "ceiling": cap}
    _fold(rec)
    return {"ok": True, "schema": SCHEMA, "learned_workers": cur, "round": rec}


def status() -> dict[str, Any]:
    st = _read_state()
    h = headroom()
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "ceiling": ceiling(), "headroom": h,
            "learned_workers": st.get("learned_workers"),
            "rounds": st.get("rounds"), "last_ts": st.get("last_ts"),
            "recommended_workers": throttled_workers(),
            "note": "parallel provider launches throttle to the CPU ceiling so the operator "
                    "keeps the machine; cadence adapts from real round data."}


def sample() -> dict[str, Any]:
    """Show what a parallel launch would use right now (no side effects)."""
    h = headroom()
    return {"ok": True, "schema": SCHEMA, "ts": _now(), **h,
            "learned_workers": learned_workers(),
            "recommended_workers": throttled_workers()}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    if cmd == "sample":
        print(json.dumps(sample(), indent=2, ensure_ascii=False))
    elif cmd == "learn":
        workers = int(argv[1]) if len(argv) > 1 else DEFAULT_BASE
        print(json.dumps(learn({"workers": workers, "ok": True, "cpu_pct": _cpu_pct()}),
                         indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
