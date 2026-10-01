"""Local task scheduler — one GPU job at a time, DeepSeek triage when backed up.

Desk / probes / janitor work queues here instead of stacking parallel Ollama calls.
Steer controls priority and pause — separate from desk prompt injection (MAG_DESK_STEERING).

Schema: mag_local_scheduler.v1
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import ROOT

SCHEMA = "mag_local_scheduler.v1"
STATE_PATH = ROOT / "memory" / "working" / "local_scheduler.json"
RESULTS_DIR = ROOT / "memory" / "working" / "local_scheduler_results"
DEFAULT_TIMEOUT = float(os.environ.get("MAG_LOCAL_SCHED_TIMEOUT", "600"))


def _enabled() -> bool:
    return os.environ.get("MAG_LOCAL_SCHEDULER", "1").strip().lower() not in ("0", "false", "no", "off")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {"schema": SCHEMA, "paused": False, "pending": [], "current": None, "history": []}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        data.setdefault("pending", [])
        return data
    except Exception:
        return {"schema": SCHEMA, "paused": False, "pending": [], "current": None, "history": []}


def _save(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


_lock = threading.Lock()
_cond = threading.Condition(_lock)


def _task_id() -> str:
    return "lt-" + uuid.uuid4().hex[:10]


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


def _priority_for_body(body: dict[str, Any]) -> int:
    if body.get("operator_note") or body.get("note") or body.get("q"):
        return 10
    if body.get("slow_wake") or body.get("handoff_loop") or body.get("handoffs"):
        return 8
    if body.get("meta_discuss") or body.get("meta_ping"):
        return 6
    if body.get("speaker") == "remote":
        return 5
    return 7


def enqueue(
    *,
    kind: str,
    payload: dict[str, Any],
    priority: int | None = None,
    label: str = "",
) -> dict[str, Any]:
    pri = priority if priority is not None else _priority_for_body(payload)
    task = {
        "id": _task_id(),
        "kind": kind,
        "priority": pri,
        "label": label or kind,
        "payload": payload,
        "status": "queued",
        "created_ts": _utc(),
    }
    with _cond:
        state = _load()
        state.setdefault("pending", []).append(task)
        state["pending"].sort(key=lambda t: (-int(t.get("priority") or 0), t.get("created_ts") or ""))
        _save(state)
        depth = len(state.get("pending") or [])
        _cond.notify_all()
    if depth >= 2:
        try:
            deepseek_triage()
        except Exception:
            pass
    return {"ok": True, "task_id": task["id"], "position": _queue_position(task["id"]), "queued": True}


def _queue_position(task_id: str) -> int:
    state = _load()
    for i, t in enumerate(state.get("pending") or []):
        if t.get("id") == task_id:
            return i + 1
    cur = state.get("current") or {}
    if cur.get("id") == task_id:
        return 0
    return -1


def steer(cmd: str) -> dict[str, Any]:
    """Scheduler steer — pause, continue, priority bump. Not desk prompt injection."""
    text = (cmd or "").strip()
    if not text:
        return {"ok": False, "error": "empty steer cmd"}
    low = text.lower()
    with _cond:
        state = _load()
        if low in ("!pause", "pause"):
            state["paused"] = True
            _save(state)
            try:
                from mag.operator_mode import set_paused
                set_paused(reason="local scheduler pause", requested_by="local_scheduler")
            except Exception:
                pass
            _cond.notify_all()
            return {"ok": True, "action": "pause", "paused": True}
        if low in ("!continue", "continue", "!resume", "resume"):
            state["paused"] = False
            _save(state)
            try:
                from mag.operator_mode import resume
                resume(requested_by="local_scheduler")
            except Exception:
                pass
            _cond.notify_all()
            return {"ok": True, "action": "continue", "paused": False}
        if low.startswith("!escape") or low == "escape":
            kept = [t for t in (state.get("pending") or []) if int(t.get("priority") or 0) >= 9]
            dropped = len(state.get("pending") or []) - len(kept)
            state["pending"] = kept
            _save(state)
            _cond.notify_all()
            return {"ok": True, "action": "escape", "dropped": dropped, "kept": len(kept)}
        if low.startswith("!steer "):
            needle = text[7:].strip().lower()
            bumped = 0
            for t in state.get("pending") or []:
                hay = f"{t.get('label') or ''} {json.dumps(t.get('payload') or {})}".lower()
                if needle in hay or needle in (t.get("kind") or ""):
                    t["priority"] = max(int(t.get("priority") or 0), 15)
                    bumped += 1
            state["pending"].sort(key=lambda t: (-int(t.get("priority") or 0), t.get("created_ts") or ""))
            _save(state)
            _cond.notify_all()
            return {"ok": True, "action": "steer", "bumped": bumped, "needle": needle[:80]}
        return {"ok": False, "error": f"unknown scheduler cmd: {text[:40]}"}


def deepseek_triage(*, dry: bool = False) -> dict[str, Any]:
    """DeepSeek reorders pending queue when local is backed up."""
    state = _load()
    pending = list(state.get("pending") or [])
    if len(pending) < 2:
        return {"ok": True, "skipped": True, "reason": "queue too shallow"}

    summary = []
    for t in pending[:12]:
        summary.append(
            {
                "id": t.get("id"),
                "kind": t.get("kind"),
                "priority": t.get("priority"),
                "label": (t.get("label") or "")[:80],
            }
        )
    prompt = (
        "You are the local GPU scheduler for Mag Agent Desk (RX 5600 XT 6GB, one job at a time).\n"
        "Reorder these pending tasks for best operator value. Prefer: operator notes > desk slow_wake > handoffs > meta > remote.\n"
        "Reply with ONLY a JSON array of task id strings in execution order, nothing else.\n\n"
        f"{json.dumps(summary, indent=2)}"
    )
    if dry:
        return {"ok": True, "dry": True, "would_triage": summary}

    ordered_ids: list[str] = []
    timing: dict[str, Any] | None = None
    try:
        from mag.desk_timing import Timer, extract_provider_tokens, make_timing, record_timing
        from models.providers import chat_provider

        timer = Timer()
        res = chat_provider(
            "deepseek",
            "You reorder local GPU task queues. Reply JSON array of task id strings only.",
            prompt,
            tier="T1",
            max_tokens=256,
            temperature=0.1,
        )
        raw = str(res.get("text") or res.get("content") or "").strip()
        if not raw:
            raise RuntimeError(str(res.get("error") or "empty deepseek triage"))
        tin, tout = extract_provider_tokens(res.get("usage"))
        timing = record_timing(
            make_timing(
                speaker="scheduler_triage",
                elapsed_ms=timer.elapsed_ms(),
                tokens_in=tin,
                tokens_out=tout,
                model=str(res.get("model") or ""),
                provider="deepseek",
            )
        )
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ordered_ids = json.loads(raw.strip())
    except Exception as exc:
        # Fallback: janitor local sort (no API spend)
        try:
            from mag.desk_timing import Timer, make_timing, record_timing
            from llm import chat

            timer = Timer()
            raw = chat("router", "JSON array of ids only.", prompt, temperature=0.1).strip()
            timing = record_timing(
                make_timing(
                    speaker="janitor",
                    elapsed_ms=timer.elapsed_ms(),
                    model=None,
                    provider="local",
                )
            )
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            ordered_ids = json.loads(raw.strip())
        except Exception:
            return {"ok": False, "error": str(exc)[:200], "fallback": "priority_sort", "timing": timing}

    if not isinstance(ordered_ids, list):
        return {"ok": False, "error": "triage did not return list"}

    with _cond:
        state = _load()
        pending = state.get("pending") or []
        by_id = {t["id"]: t for t in pending if t.get("id")}
        new_pending = [by_id[i] for i in ordered_ids if i in by_id]
        seen = {t["id"] for t in new_pending}
        new_pending.extend(t for t in pending if t.get("id") not in seen)
        state["pending"] = new_pending
        state["last_triage_ts"] = _utc()
        _save(state)

    from mag.training_events import emit

    emit(
        "route_decision",
        join={"scheduler": "local", "triage": "deepseek"},
        input_data={"n_pending": len(pending)},
        action={"ordered": ordered_ids[:8]},
        outcome={"ok": True},
        pattern_tags=["local_scheduler", "deepseek_triage"],
    )
    return {"ok": True, "ordered": ordered_ids, "n": len(new_pending), "timing": timing}


def _wait_turn(task_id: str, *, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    with _cond:
        while True:
            state = _load()
            shared_pause = None
            try:
                from mag.operator_mode import pause_reason
                shared_pause = pause_reason()
            except Exception:
                pass
            if state.get("paused") or shared_pause:
                _cond.wait(timeout=min(2.0, max(0.1, deadline - time.monotonic())))
                if time.monotonic() >= deadline:
                    return False
                continue
            pending = state.get("pending") or []
            if not pending:
                return False
            if pending[0].get("id") == task_id and not state.get("current"):
                task = pending.pop(0)
                task["status"] = "running"
                task["started_ts"] = _utc()
                state["current"] = task
                _save(state)
                return True
            _cond.wait(timeout=min(2.0, max(0.1, deadline - time.monotonic())))
            if time.monotonic() >= deadline:
                return False


def _finish(task_id: str, result: dict[str, Any], *, error: str = "") -> None:
    with _cond:
        state = _load()
        cur = state.get("current") or {}
        if cur.get("id") == task_id:
            cur["status"] = "done" if result.get("ok", True) and not error else "failed"
            cur["finished_ts"] = _utc()
            if error:
                cur["error"] = error[:200]
            hist = state.setdefault("history", [])
            hist.append(cur)
            state["history"] = hist[-30:]
            state["current"] = None
            _save(state)
        _cond.notify_all()


def _execute_desk(payload: dict[str, Any]) -> dict[str, Any]:
    from mag.desk_dialogue import (
        dialogue_turn,
        handoff_loop,
        meta_discuss,
        ping_pong,
        slow_wake,
    )

    if payload.get("meta_discuss") or payload.get("meta_ping"):
        return meta_discuss(
            rounds=int(payload.get("rounds") or payload.get("meta_rounds") or 1),
            operator_note=str(payload.get("operator_note") or payload.get("note") or ""),
            canvas=str(payload.get("desk_canvas") or payload.get("canvas") or "").strip() or None,
        )
    if payload.get("slow_wake") or payload.get("wake_on_edit"):
        return slow_wake(
            operator_note=str(payload.get("operator_note") or payload.get("note") or payload.get("q") or ""),
            canvas=str(payload.get("desk_canvas") or payload.get("canvas") or "").strip() or None,
        )
    if payload.get("handoff_loop") or payload.get("handoffs"):
        return handoff_loop(
            handoffs=int(payload.get("handoffs") or payload.get("handoff_loop") or 5),
            operator_note=str(payload.get("operator_note") or payload.get("note") or ""),
            canvas=str(payload.get("desk_canvas") or payload.get("canvas") or "").strip() or None,
        )
    if payload.get("ping_pong") or payload.get("pingpong"):
        return ping_pong(
            rounds=int(payload.get("rounds") or 1),
            operator_note=str(payload.get("operator_note") or payload.get("note") or ""),
            canvas=str(payload.get("desk_canvas") or payload.get("canvas") or "").strip() or None,
        )
    speaker = str(payload.get("speaker") or payload.get("from") or "local").strip().lower()
    note = str(payload.get("operator_note") or payload.get("message") or payload.get("q") or payload.get("note") or "")
    return dialogue_turn(
        speaker,
        operator_note=note,
        canvas=str(payload.get("desk_canvas") or payload.get("canvas") or "").strip() or None,
        force_wake=_truthy(payload.get("force_wake")),
        local_mode=str(payload.get("local_mode") or "real").strip().lower(),
    )


def run_exclusive(
    *,
    kind: str,
    payload: dict[str, Any],
    executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    label: str = "",
    priority: int | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Enqueue and block until this task runs (serializes local GPU work)."""
    if not _enabled():
        fn = executor or _execute_desk
        return fn(payload)

    task = enqueue(kind=kind, payload=payload, priority=priority, label=label)
    task_id = task["task_id"]
    wait = DEFAULT_TIMEOUT if timeout is None else timeout
    if not _wait_turn(task_id, timeout=wait):
        with _cond:
            state = _load()
            state["pending"] = [t for t in (state.get("pending") or []) if t.get("id") != task_id]
            _save(state)
        return {"ok": False, "error": "scheduler timeout or paused", "task_id": task_id}

    fn = executor or _execute_desk
    try:
        from mag.ollama_policy import ensure_desk_model

        ensure_desk_model(None)
        result = fn(payload)
        _finish(task_id, result)
        result.setdefault("scheduler", {"task_id": task_id, "serialized": True})
        return result
    except Exception as exc:
        _finish(task_id, {"ok": False}, error=str(exc))
        return {"ok": False, "error": str(exc), "task_id": task_id}


def status() -> dict[str, Any]:
    state = _load()
    pending = state.get("pending") or []
    cur = state.get("current")
    try:
        from mag.operator_mode import read as read_operator_mode, pause_reason
        operator_mode = read_operator_mode()
        shared_paused = bool(pause_reason())
    except Exception as exc:
        operator_mode = {"mode": "invalid", "reason": str(exc)[:120]}
        shared_paused = True
    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "enabled": _enabled(),
        "paused": bool(state.get("paused")) or shared_paused,
        "local_paused": bool(state.get("paused")),
        "operator_mode": operator_mode,
        "busy": bool(cur),
        "current": cur,
        "pending": pending[:12],
        "depth": len(pending) + (1 if cur else 0),
        "last_triage_ts": state.get("last_triage_ts"),
        "note": "One local GPU job at a time · DeepSeek triage when depth≥2 · steer=pause/priority",
    }


def build_stack_row() -> dict[str, Any]:
    s = status()
    depth = s.get("depth") or 0
    st = "warn" if depth > 2 else ("ok" if s.get("busy") else "idle")
    if s.get("paused"):
        st = "warn"
    text = f"depth {depth}"
    if s.get("paused"):
        text += " · paused"
    elif cur := s.get("current"):
        text += f" · {cur.get('label') or cur.get('kind') or 'running'}"
    return {
        "id": "local_scheduler",
        "label": "Local scheduler",
        "status": st,
        "text": text[:160],
        "api": "GET /api/v1/local-scheduler",
        "proof": str(STATE_PATH),
    }
