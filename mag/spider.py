"""Spider — meta-supervisor on the agent web (v3-007 research, Phase 0 rules).

Read-only watcher across orchestrator children, autorun trail, FKB recurrence.
Emits steer signals via pigeonhole — never spawns a second orchestrator.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SPIDER_TRAIL = ROOT / "memory" / "runs" / "spider_trail.jsonl"
STALL_THRESHOLD_S = 180

# Q-008 (2026-09-28): the old flat FKB_REPEAT_THRESHOLD=3 plus a [:5] rank
# slice over recurring_patterns() made the spider blind to 10 of the 15 real
# signatures in memory/failure_kb/signatures.json (census 2026-09-28): a
# run_shell sig at x11 with a remedy attached ranked 6th and was sliced away,
# and the severe "collapse" (x2) / "fake_success" (x1) kinds fell under the
# count bar. Policy now: no rank cut (the index is already the recurring-class
# view, failure_kb.rebuild_index keeps count>=2 sigs only); ordinary kinds
# surface at count>=2, the same bar failure_kb.surface_hits uses; the severe
# "lying agent" kinds surface on the FIRST occurrence because one instance is
# already verdict-grade (claimed edits with nothing on disk). Count-1
# ordinary sigs stay hidden per the FKB's own log-only law
# (mag/failure_kb.py, rebuild_index: count-1 sigs stay log-only by design).
FKB_REPEAT_THRESHOLD = 2
FKB_SEVERE_KINDS = ("collapse", "fake_success")
FKB_SEVERE_REPEAT_THRESHOLD = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    SPIDER_TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **fields}
    with SPIDER_TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _read_jsonl_tail(path: Path, n: int = 20) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _check_orchestrator_tasks() -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    try:
        from mag import orchestrator as orc
        from mag import pigeonhole as ph

        for task in orc.list_tasks_live() or []:
            tid = task.get("id") or task.get("task_id")
            if not tid:
                continue
            status = task.get("status")
            if status in orc.TERMINAL:
                continue
            age = ph.staleness_s(str(tid))
            if age is not None and age >= STALL_THRESHOLD_S:
                signals.append({
                    "kind": "stall",
                    "severity": "warn",
                    "task_id": tid,
                    "age_s": age,
                    "action": "steer",
                    "message": f"Task {tid} stalled {age}s — spider recommends steer",
                })
    except Exception as exc:
        signals.append({
            "kind": "spider_error",
            "severity": "info",
            "message": f"orchestrator probe failed: {exc}",
        })
    return signals


def _check_autorun_trail() -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    trail = ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl"
    rows = _read_jsonl_tail(trail, 30)
    fails = [r for r in rows if r.get("event") in ("fail", "error", "blocked")]
    if len(fails) >= 3:
        signals.append({
            "kind": "autorun_fail_burst",
            "severity": "warn",
            "count": len(fails),
            "action": "pause_suggest",
            "message": "Autorun trail shows repeated failures — consider MAG_OPERATOR_ACTIVE",
        })
    try:
        from mag.loop_audit import analyze_autorun_trail

        audit = analyze_autorun_trail(_read_jsonl_tail(trail, 120))
        for f in audit.get("findings") or []:
            if f.get("kind") in ("plan_theater", "idle_autorun"):
                signals.append({
                    "kind": str(f.get("kind")),
                    "severity": f.get("severity") or "warn",
                    "count": f.get("count"),
                    "goal": f.get("goal"),
                    "action": "loop_audit",
                    "message": f.get("message") or "Autorun plan theater — run loop-audit",
                })
    except Exception:
        pass
    return signals


def _check_fkb_repeat() -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    try:
        from mag.failure_kb import recurring_patterns

        # Q-008: min_count=1 so this function owns the whole threshold policy
        # (the old call leaned on the default min_count=3 and then re-checked
        # the same 3), and there is no [:5] rank slice: the count floors below
        # are the only bar between an index signature and a signal.
        for pat in recurring_patterns(min_count=FKB_SEVERE_REPEAT_THRESHOLD):
            count = int(pat.get("count") or 0)
            kind = str(pat.get("kind") or "")
            severe = kind in FKB_SEVERE_KINDS
            floor = FKB_SEVERE_REPEAT_THRESHOLD if severe else FKB_REPEAT_THRESHOLD
            if count < floor:
                continue
            signals.append({
                "kind": "fkb_repeat",
                "severity": "error" if severe else "warn",
                "signature": pat.get("signature") or pat.get("key") or pat.get("sig"),
                "count": count,
                "fkb_kind": kind,
                "action": "surface_remedy",
                "message": f"FKB {kind} pattern repeated {count}x - remedy may exist",
            })
    except Exception:
        pass
    return signals


def _check_operator_active() -> list[dict[str, Any]]:
    import os

    if os.environ.get("MAG_OPERATOR_ACTIVE", "").strip().lower() in ("1", "true", "yes"):
        return [{
            "kind": "operator_active",
            "severity": "info",
            "action": "defer_autorun",
            "message": "MAG_OPERATOR_ACTIVE — spider defers proactive steer on autorun",
        }]
    return []


def _check_cloud_seats() -> list[dict[str, Any]]:
    """Stale cloud/desktop external seats — orphan detection."""
    signals: list[dict[str, Any]] = []
    try:
        from mag.seat_registry import list_registered

        for seat in list_registered(live_only=True):
            age = seat.get("heartbeat_age_s")
            src = str(seat.get("source") or seat.get("parent") or "")
            if age is not None and age >= STALL_THRESHOLD_S:
                signals.append({
                    "kind": "cloud_seat_stale",
                    "severity": "warn",
                    "task_id": seat.get("task_id"),
                    "age_s": age,
                    "source": src,
                    "action": "steer",
                    "message": f"External seat {seat.get('task_id')} stale {age}s — heartbeat or unregister",
                })
    except Exception:
        pass
    return signals


def tick(*, dry: bool = False, inject: bool = False, deep: bool = False) -> dict[str, Any]:
    """Run bounded spider checks; reserve orphan reaping for deep cadence.

    A normal improve/health cycle is a control-plane observer.  Scanning the
    entire task corpus and then reaping from inside that observer made a law
    enforcement call unexpectedly block on thousands of JSON files.  Deep
    cadence is explicit for operators that want mesh hygiene in this tick.
    """
    signals = []
    signals.extend(_check_operator_active())
    signals.extend(_check_orchestrator_tasks())
    signals.extend(_check_cloud_seats())
    signals.extend(_check_autorun_trail())
    signals.extend(_check_fkb_repeat())

    injected = []
    reaped = None
    if inject and not dry:
        from mag.switchboard import steer_drop

        for sig in signals:
            if sig.get("action") != "steer":
                continue
            tid = sig.get("task_id")
            if not tid:
                continue
            msg = sig.get("message") or "course correct"
            steer_drop(
                "spider",
                str(tid),
                f"[spider] {msg}"[:1200],
                tier="T2",
                reason=str(sig.get("kind") or "stall"),
            )
            injected.append(tid)

    if not dry and deep:
        try:
            from mag.switchboard import find_orphans, reap

            orphans = find_orphans(dry=True)
            if orphans.get("n", 0) > 0:
                reaped = reap()
                signals.append({
                    "kind": "orphan_reap",
                    "severity": "info",
                    "count": orphans.get("n"),
                    "action": "reap",
                    "message": f"Switchboard reaped {reaped.get('reaped', 0)} stale; {orphans.get('n')} orphan(s) noted",
                })
        except Exception:
            pass

    _trail("tick", dry=dry, n_signals=len(signals), injected=injected)
    try:
        from mag.training_events import emit

        for sig in signals:
            emit(
                "spider_signal",
                input_data={"message": sig.get("message", "")[:200]},
                action={"kind": sig.get("kind"), "severity": sig.get("severity")},
                outcome={"injected": sig.get("task_id") in injected if injected else False},
                pattern_tags=[str(sig.get("kind") or "signal")],
            )
    except Exception:
        pass
    return {
        "schema": "spider_tick.v1",
        "ts": _now(),
        "ok": True,
        "dry": dry,
        "signals": signals,
        "injected": injected,
        "reaped": reaped,
        "n_signals": len(signals),
    }
