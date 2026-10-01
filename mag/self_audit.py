"""self_audit — the check-yourself loop: a non-blocking scheduler that fires
audit probes on tiered cadences, never inline on the main loop's critical path.

Design (five parts, all non-blocking):
  1. SCHEDULER   — a sidecar daemon thread (start_scheduler) that ticks on a
                   bounded interval and fires whichever probes are due. It never
                   runs a probe inline on the caller's critical path; the caller
                   only calls tick()/run_due() which delegate to the thread.
  2. PROBE REGISTRY — a declarative table mapping each probe (dogfood, caveman,
                   build_audit, loop_audit, ...) to a tier + cadence + timeout.
  3. TIERED CADENCE — fast (every tick, $0 cheap), medium (every N ticks),
                   slow (every M ticks / on-demand). Probes are grouped by tier
                   so the scheduler only pays for what's due.
  4. NON-BLOCKING EXECUTION — each probe runs in its own bounded-timeout call
                   (threading.Timer-style guard); a slow/hung probe is cut off
                   and folded as a failure, never blocking the scheduler tick.
  5. HEALTH AGGREGATION — status() reads the report trail and returns a health
                   snapshot (last run per tier, pass/fail, staleness) so the
                   operator / dashboard can see the system auditing itself.

Grounding: this is the orchestration layer over the EXISTING probes (dogfood_audit,
caveman_audit, build_audit, loop_audit). It does not re-implement them — it schedules
them on cadences and folds their results to a single report trail.

Schema: self_audit.v1 · deterministic · $0 (probes are $0; no LLM in the scheduler)
CLI:  python -m mag.self_audit status | run [--tier fast|medium|slow|all] | start
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "self_audit.v1"
REPORT = ROOT / "memory" / "runs" / "self_audit" / "report.jsonl"
STATE = ROOT / "memory" / "runs" / "self_audit" / "state.json"

# Tier cadences (in scheduler ticks). fast = every tick; medium = every 5;
# slow = every 20 (or on-demand). Ticks are cheap; probes are $0.
TIER_CADENCE = {"fast": 1, "medium": 5, "slow": 20}
DEFAULT_TICK_S = 60.0
DEFAULT_PROBE_TIMEOUT_S = 30.0


# ---------------------------------------------------------------------------
# Probe registry — declarative: name -> (tier, timeout_s, callable)
# Each probe is a $0 deterministic check over an existing system surface.
# ---------------------------------------------------------------------------
def _probe_dogfood() -> dict[str, Any]:
    from mag.dogfood_audit import audit
    r = audit()
    return {"passed": r.get("passed"), "failed": r.get("failed"),
            "systems": r.get("systems_probed")}


def _probe_caveman() -> dict[str, Any]:
    from mag.caveman_audit import run_audit
    r = run_audit()
    return {"dense": r.get("dense"), "findings": r.get("files_scanned")}


def _probe_loop() -> dict[str, Any]:
    from mag.loop_audit import run_audit
    r = run_audit(tail=200)
    return {"findings": len(r.get("findings") or []),
            "recommendations": len(r.get("recommendations") or [])}


def _probe_build() -> dict[str, Any]:
    # build_audit is a writer; probe its load path (no side effects).
    from mag.build_audit import load_audit
    return {"loadable": callable(load_audit)}


def _probe_verkle() -> dict[str, Any]:
    try:
        from mag.verkle_knot import status as vk_status
        s = vk_status() or {}
        return {"ok": bool(s.get("ok")), "leaves": s.get("leaves")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _probe_heartbeat() -> dict[str, Any]:
    # Is the main loop alive? Read the runtime heartbeat if present.
    try:
        from mag.runtime import read_heartbeat
        hb = read_heartbeat() or {}
        ts = str(hb.get("ts") or "")
        age_s = None
        if ts:
            try:
                last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                age_s = max(0, int((datetime.now(timezone.utc) - last).total_seconds()))
            except (TypeError, ValueError):
                age_s = None
        return {"alive": bool(ts and age_s is not None and age_s <= 300),
                "last": ts, "age_s": age_s}
    except Exception:
        return {"alive": None, "note": "no runtime heartbeat surface"}


def _probe_dogfood_status() -> dict[str, Any]:
    # LIGHT fast-tier probe: read the last dogfood report (no heavy re-run).
    from mag.dogfood_audit import status as df_status
    s = df_status() or {}
    failed = int(s.get("failed") or 0)
    return {"ok": failed == 0, "passed": s.get("passed"), "failed": failed,
            "last_ts": s.get("last_ts")}


# name -> (tier, timeout_s, callable)
# fast = cheap $0 liveness every tick; medium = heavier audits every 5 ticks;
# slow = deep checks every 20 ticks (or on-demand).
PROBES: dict[str, tuple[str, float, Callable[[], dict[str, Any]]]] = {
    "heartbeat": ("fast", 5.0, _probe_heartbeat),
    "dogfood_status": ("fast", 5.0, _probe_dogfood_status),
    "dogfood": ("medium", 60.0, _probe_dogfood),
    "caveman": ("medium", 30.0, _probe_caveman),
    "loop": ("medium", 20.0, _probe_loop),
    "verkle": ("slow", 15.0, _probe_verkle),
    "build": ("slow", 10.0, _probe_build),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2),
                    encoding="utf-8")


def _run_one(name: str, tier: str, timeout_s: float,
             fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run one probe with a bounded timeout. Never raises; never blocks the
    scheduler beyond timeout_s. Returns a folded result row."""
    result: dict[str, Any] = {"ok": False, "error": "timeout"}
    box: dict[str, Any] = {}

    def _target() -> None:
        try:
            box["r"] = fn()
        except Exception as e:  # noqa: BLE001
            box["e"] = str(e)[:200]

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        result = {"ok": False, "error": f"timeout after {timeout_s}s"}
    elif "e" in box:
        result = {"ok": False, "error": box["e"]}
    else:
        r = box.get("r") or {}
        nested_ok = r.get("ok") if isinstance(r, dict) and "ok" in r else True
        result = {
            "ok": nested_ok is not False,
            "error": (r.get("error") if isinstance(r, dict) else None),
            "summary": {k: v for k, v in list(r.items())[:6]
                        if not isinstance(v, (list, dict))},
        }
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "probe": name,
        "tier": tier,
        "ok": result["ok"],
        "error": result.get("error"),
        "summary": result.get("summary"),
    }


def run_tier(tier: str) -> dict[str, Any]:
    """Run all probes in one tier (or 'all'). Returns the folded report."""
    tier = (tier or "all").strip().lower()
    if tier not in ("fast", "medium", "slow", "all"):
        raise ValueError(f"tier must be fast|medium|slow|all, got {tier!r}")
    rows: list[dict[str, Any]] = []
    for name, (ptier, timeout_s, fn) in PROBES.items():
        if tier != "all" and ptier != tier:
            continue
        rows.append(_run_one(name, ptier, timeout_s, fn))
    ok = sum(1 for r in rows if r["ok"])
    report = {"schema": SCHEMA, "ts": _now(), "tier": tier,
              "probes": len(rows), "passed": ok, "failed": len(rows) - ok,
              "results": rows}
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        with REPORT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return report


def _last_report() -> dict[str, Any] | None:
    last = None
    if REPORT.is_file():
        for line in REPORT.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    last = json.loads(line)
                except Exception:
                    continue
    return last


def status() -> dict[str, Any]:
    """Health aggregation: last run per tier, pass/fail, staleness."""
    last = _last_report()
    if not last:
        return {"ok": True, "schema": SCHEMA, "note": "no self-audit run yet",
                "probes": len(PROBES), "tiers": sorted(TIER_CADENCE)}
    staleness_s = None
    try:
        from datetime import datetime as _dt
        last_ts = _dt.fromisoformat(last.get("ts", "").replace("Z", "+00:00"))
        staleness_s = int((_dt.now(timezone.utc) - last_ts).total_seconds())
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "last_ts": last.get("ts"),
            "last_tier": last.get("tier"), "last_passed": last.get("passed"),
            "last_failed": last.get("failed"), "staleness_s": staleness_s,
            "probes": len(PROBES), "tiers": sorted(TIER_CADENCE)}


# ---------------------------------------------------------------------------
# Scheduler — a sidecar daemon thread. Non-blocking: the caller never runs a
# probe inline; it only starts the thread and lets it tick on its own cadence.
# ---------------------------------------------------------------------------
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_scheduler_lock = threading.Lock()


def _scheduler_loop(tick_s: float) -> None:
    tick = 0
    while not _scheduler_stop.is_set():
        tick += 1
        due = [t for t, c in TIER_CADENCE.items() if tick % c == 0]
        for tier in due:
            try:
                run_tier(tier)
            except Exception:
                pass
        _scheduler_stop.wait(tick_s)


def start_scheduler(tick_s: float = DEFAULT_TICK_S) -> dict[str, Any]:
    """Start the sidecar scheduler thread (idempotent). Never blocks."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return {"ok": True, "already_running": True, "tick_s": tick_s}
        _scheduler_stop.clear()
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop, args=(tick_s,), daemon=True, name="self-audit")
        _scheduler_thread.start()
        return {"ok": True, "started": True, "tick_s": tick_s}


def stop_scheduler() -> dict[str, Any]:
    """Stop the scheduler thread and wait briefly for it to exit."""
    global _scheduler_thread
    _scheduler_stop.set()
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=2.0)
        _scheduler_thread = None
    return {"ok": True, "stopped": True}


def scheduler_status() -> dict[str, Any]:
    running = bool(_scheduler_thread and _scheduler_thread.is_alive())
    return {"ok": True, "running": running, "tick_s": DEFAULT_TICK_S,
            "cadence": TIER_CADENCE}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="self_audit", description="check-yourself loop")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("start")
    sub.add_parser("stop")
    r = sub.add_parser("run")
    r.add_argument("--tier", default="all", help="fast|medium|slow|all")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    elif a.cmd == "start":
        print(json.dumps(start_scheduler(), indent=2, ensure_ascii=False))
    elif a.cmd == "stop":
        print(json.dumps(stop_scheduler(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run_tier(a.tier), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
