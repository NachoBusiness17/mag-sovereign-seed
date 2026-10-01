"""Run worth gate — evaluate long runs before auto-truncate or bad classification.

Symmetric to behavioral errors (operator_inbox) and tesuji_shell (wins).
Defer truncation when worth is uncertain; kill hung processes early.

Artifacts:
  logs/run_worth.jsonl          gate decisions + scores
  logs/run_worth_overrides.jsonl operator marks long run as good
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

LOG_PATH = ROOT / "logs" / "run_worth.jsonl"
OVERRIDES_PATH = ROOT / "logs" / "run_worth_overrides.jsonl"
SCHEMA = "run_worth.v1"

DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "max_steps_bad": 100,
    "max_tool_calls_hard": 32,
    "max_tool_calls_defer": 64,
    "worth_valuable": 0.55,
    "worth_worthless": 0.25,
    "hung_timeout_s": 300,
    "hung_identical_window": 5,
    "hung_zero_artifact_s": 180,
    "velocity_min_per_min": 0.15,
    "defer_extensions_max": 2,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    try:
        from mag.improve import load_config as load_improve

        raw = (load_improve().get("run_worth") or {})
    except Exception:
        raw = {}
    cfg = dict(DEFAULTS)
    if isinstance(raw, dict):
        cfg.update(raw)
    return cfg


def _read_jsonl(path: Path, *, tail: int = 500) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except json.JSONDecodeError:
            continue
    return out


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def operator_overrides(*, run_id: str | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl(OVERRIDES_PATH)
    if run_id:
        return [r for r in rows if str(r.get("run_id") or "") == run_id]
    return rows


def is_operator_marked_good(run_id: str) -> bool:
    for r in operator_overrides(run_id=run_id):
        if r.get("verdict") == "good":
            return True
    return False


def mark_run_good(
    run_id: str,
    *,
    note: str = "",
    source: str = "cli",
) -> dict[str, Any]:
    """Operator override — this long run was valuable; do not auto-truncate."""
    run_id = (run_id or "").strip()
    if not run_id:
        return {"ok": False, "error": "run_id required"}
    row = {
        "schema": SCHEMA,
        "ts": _now(),
        "run_id": run_id,
        "verdict": "good",
        "note": (note or "")[:500],
        "source": source,
    }
    _append_jsonl(OVERRIDES_PATH, row)
    log_event(
        run_id=run_id,
        verdict="operator_good",
        score=1.0,
        detail=note or "operator marked good",
        action="override",
    )
    try:
        from mag.training_events import emit

        emit(
            "run_worth",
            join={"run_id": run_id},
            input_data={"source": source},
            action={"override": "good"},
            outcome={"note": note[:200]},
            pattern_tags=["operator_override"],
        )
    except Exception:
        pass
    return {"ok": True, "run_id": run_id, "path": str(OVERRIDES_PATH)}


def log_event(
    *,
    run_id: str = "",
    task_id: str = "",
    verdict: str,
    score: float,
    detail: str = "",
    action: str = "",
    signals: dict[str, Any] | None = None,
) -> None:
    row = {
        "schema": SCHEMA,
        "ts": _now(),
        "run_id": run_id,
        "task_id": task_id,
        "verdict": verdict,
        "score": round(float(score), 3),
        "detail": (detail or "")[:400],
        "action": action,
        "signals": signals or {},
    }
    try:
        _append_jsonl(LOG_PATH, row)
    except OSError:
        pass


def _tool_signature(ev: dict[str, Any]) -> str:
    tool = str(ev.get("tool") or ev.get("kind") or "")
    core = ev.get("core") if isinstance(ev.get("core"), dict) else {}
    text = str(core.get("text") or ev.get("summary") or "")[:80]
    return f"{tool}:{text}"


def _max_identical_streak(events: list[dict[str, Any]]) -> int:
    streak = 0
    best = 0
    prev = ""
    for ev in events:
        if ev.get("kind") not in ("tool", "tool_call", "tool_result") and not ev.get("tool"):
            streak = 0
            prev = ""
            continue
        sig = _tool_signature(ev)
        if sig and sig == prev:
            streak += 1
            best = max(best, streak)
        else:
            streak = 1 if sig else 0
            prev = sig
    return best


def _artifact_events(events: list[dict[str, Any]]) -> int:
    n = 0
    for ev in events:
        kind = str(ev.get("kind") or "").lower()
        tool = str(ev.get("tool") or "").lower()
        summary = str(ev.get("summary") or "").lower()
        core = ev.get("core") if isinstance(ev.get("core"), dict) else {}
        drift = str(core.get("drift_kind") or "").lower()
        if kind in ("write", "artifact", "run_close") or tool in (
            "write_file",
            "write",
            "patch",
            "apply_patch",
        ):
            n += 1
        elif drift in ("finding", "add", "ready"):
            n += 1
        elif any(x in summary for x in ("wrote", "created", "patched", "saved")):
            n += 1
    return n


def _parse_ts(ts: str) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def signals_from_run(
    run: dict[str, Any],
    trail_events: list[dict[str, Any]] | None = None,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Collect heuristic signals from run card + trail (+ optional task heartbeat)."""
    events = trail_events if trail_events is not None else []
    if not events and run.get("run_id"):
        try:
            from mag.run_trail import read_trail

            events = read_trail(str(run["run_id"]), last_n=120)
        except Exception:
            events = []

    n_tool = int(run.get("n_tool_calls") or 0)
    n_events = int(run.get("n_events") or 0)
    created = _parse_ts(str(run.get("created") or ""))
    updated = _parse_ts(str(run.get("updated") or ""))
    now = time.time()
    age_s = max(1, int(now - created)) if created else 1
    stale_s = max(0, int(now - updated)) if updated else age_s

    tools = {str(e.get("tool") or e.get("kind") or "") for e in events if e.get("tool") or e.get("kind")}
    cores = sum(1 for e in events if isinstance(e.get("core"), dict))
    artifacts = _artifact_events(events)
    identical_streak = _max_identical_streak(events)
    velocity = (n_tool / max(age_s / 60.0, 0.1)) if n_tool else 0.0

    hb_step_delta = 0
    hb_age_s: int | None = None
    if task_id:
        try:
            from mag import pigeonhole as ph

            beads = ph.heartbeats(task_id, limit=20)
            if beads:
                hb_age_s = ph.staleness_s(task_id)
                steps = [int(b.get("step") or b.get("step_i") or 0) for b in beads[-10:]]
                if len(steps) >= 2:
                    hb_step_delta = steps[-1] - steps[0]
        except Exception:
            pass

    return {
        "run_id": str(run.get("run_id") or ""),
        "task_id": task_id or "",
        "n_tool_calls": n_tool,
        "n_events": n_events,
        "unique_tools": len(tools),
        "core_count": cores,
        "artifact_count": artifacts,
        "identical_streak": identical_streak,
        "velocity_per_min": round(velocity, 3),
        "age_s": age_s,
        "stale_s": stale_s,
        "hb_step_delta": hb_step_delta,
        "hb_age_s": hb_age_s,
        "operator_good": is_operator_marked_good(str(run.get("run_id") or "")),
        "defer_count": int(run.get("worth_defer_count") or 0),
    }


def score_worth(signals: dict[str, Any], cfg: dict[str, Any] | None = None) -> float:
    """0..1 heuristic — higher = more worth continuing."""
    cfg = cfg or load_config()
    if signals.get("operator_good"):
        return 1.0

    score = 0.35
    n_tool = int(signals.get("n_tool_calls") or 0)
    if n_tool >= int(cfg.get("max_steps_bad") or 100):
        score -= 0.15
    elif n_tool >= int(cfg.get("max_tool_calls_hard") or 32):
        score -= 0.05

    score += min(0.25, int(signals.get("unique_tools") or 0) * 0.04)
    score += min(0.2, int(signals.get("core_count") or 0) * 0.05)
    score += min(0.25, int(signals.get("artifact_count") or 0) * 0.08)

    vel = float(signals.get("velocity_per_min") or 0)
    if vel >= float(cfg.get("velocity_min_per_min") or 0.15):
        score += 0.12
    elif vel < 0.05:
        score -= 0.1

    streak = int(signals.get("identical_streak") or 0)
    if streak >= int(cfg.get("hung_identical_window") or 5):
        score -= 0.35
    elif streak >= 3:
        score -= 0.15

    if int(signals.get("hb_step_delta") or 0) > 0:
        score += 0.1

    stale = int(signals.get("stale_s") or 0)
    if stale > int(cfg.get("hung_zero_artifact_s") or 180) and int(signals.get("artifact_count") or 0) == 0:
        score -= 0.2

    return max(0.0, min(1.0, score))


def classify_run(
    signals: dict[str, Any],
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify: valuable | uncertain | worthless | hung."""
    cfg = cfg or load_config()
    if not cfg.get("enabled", True):
        return {"verdict": "uncertain", "score": 0.5, "reason": "gate disabled"}

    score = score_worth(signals, cfg)
    valuable_t = float(cfg.get("worth_valuable") or 0.55)
    worthless_t = float(cfg.get("worth_worthless") or 0.25)

    if signals.get("operator_good"):
        return {"verdict": "valuable", "score": score, "reason": "operator_good"}

    hung = detect_hung(signals, cfg)
    if hung.get("hung"):
        return {
            "verdict": "hung",
            "score": score,
            "reason": hung.get("reason", "hung"),
            "hung_detail": hung,
        }

    if score >= valuable_t:
        return {"verdict": "valuable", "score": score, "reason": "progress_and_artifacts"}
    if score <= worthless_t:
        return {"verdict": "worthless", "score": score, "reason": "low_signal_long_run"}
    return {"verdict": "uncertain", "score": score, "reason": "defer_truncate"}


def detect_hung(signals: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Hung/dead: no progress, repeated identical tools, zero artifact delta."""
    cfg = cfg or load_config()
    if signals.get("operator_good"):
        return {"hung": False, "reason": "operator_good"}

    hb_age = signals.get("hb_age_s")
    hb_delta = int(signals.get("hb_step_delta") or 0)
    stale = int(signals.get("stale_s") or 0)
    streak = int(signals.get("identical_streak") or 0)
    artifacts = int(signals.get("artifact_count") or 0)
    vel = float(signals.get("velocity_per_min") or 0)

    hung_timeout = int(cfg.get("hung_timeout_s") or 300)
    zero_art = int(cfg.get("hung_zero_artifact_s") or 180)
    ident_win = int(cfg.get("hung_identical_window") or 5)

    if hb_age is not None and hb_age >= hung_timeout and hb_delta == 0:
        return {"hung": True, "reason": f"heartbeat stale {hb_age}s, no step delta"}

    if streak >= ident_win and artifacts == 0 and stale >= zero_art:
        return {
            "hung": True,
            "reason": f"identical tool streak {streak}, zero artifacts {stale}s",
        }

    if stale >= hung_timeout and vel < 0.02 and artifacts == 0:
        return {"hung": True, "reason": f"zero velocity {stale}s, no artifacts"}

    return {"hung": False}


def gate_before_truncate(
    run: dict[str, Any],
    *,
    trail_events: list[dict[str, Any]] | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Called when max_tool_calls exceeded — defer, extend, or block."""
    cfg = load_config()
    sig = signals_from_run(run, trail_events, task_id=task_id)
    cls = classify_run(sig, cfg)
    verdict = str(cls.get("verdict") or "uncertain")
    score = float(cls.get("score") or 0)
    defer_count = int(sig.get("defer_count") or 0)
    max_ext = int(cfg.get("defer_extensions_max") or 2)
    hard = int((run.get("bounds") or {}).get("max_tool_calls") or cfg.get("max_tool_calls_hard") or 32)
    defer_cap = int(cfg.get("max_tool_calls_defer") or 64)

    out: dict[str, Any] = {
        "ok": True,
        "verdict": verdict,
        "score": score,
        "signals": sig,
        "allow_continue": False,
        "new_max_tool_calls": hard,
        "close_reason": "max_tool_calls",
    }

    if verdict == "hung":
        out["allow_continue"] = False
        out["close_reason"] = "hung"
        log_event(
            run_id=str(run.get("run_id") or ""),
            task_id=task_id or "",
            verdict=verdict,
            score=score,
            detail=str(cls.get("reason") or ""),
            action="block",
            signals=sig,
        )
        return out

    if verdict == "worthless":
        out["allow_continue"] = False
        log_event(
            run_id=str(run.get("run_id") or ""),
            verdict=verdict,
            score=score,
            detail=str(cls.get("reason") or ""),
            action="block",
            signals=sig,
        )
        return out

    if verdict in ("valuable", "uncertain") and defer_count < max_ext:
        new_max = min(defer_cap, hard + (defer_cap - hard))
        out["allow_continue"] = True
        out["new_max_tool_calls"] = new_max
        out["close_reason"] = ""
        out["defer"] = True
        log_event(
            run_id=str(run.get("run_id") or ""),
            verdict=verdict,
            score=score,
            detail=f"extended to {new_max} ({verdict})",
            action="defer",
            signals=sig,
        )
        return out

    out["allow_continue"] = False
    log_event(
        run_id=str(run.get("run_id") or ""),
        verdict=verdict,
        score=score,
        detail="defer budget exhausted",
        action="block",
        signals=sig,
    )
    return out


def evaluate_task_hung(task_id: str) -> dict[str, Any]:
    """Orchestrator hook — should we kill a stalled task or defer?"""
    cfg = load_config()
    if not cfg.get("enabled", True):
        return {"verdict": "uncertain", "defer_kill": True}

    sig: dict[str, Any] = {
        "task_id": task_id,
        "n_tool_calls": 0,
        "artifact_count": 0,
        "identical_streak": 0,
        "velocity_per_min": 0,
        "stale_s": 0,
        "operator_good": False,
    }
    try:
        from mag import pigeonhole as ph

        beads = ph.heartbeats(task_id, limit=30)
        sig["hb_age_s"] = ph.staleness_s(task_id)
        if beads:
            steps = [int(b.get("step") or b.get("step_i") or 0) for b in beads]
            sig["hb_step_delta"] = steps[-1] - steps[0] if len(steps) >= 2 else 0
            sig["n_tool_calls"] = steps[-1] if steps else 0
            first = _parse_ts(str(beads[0].get("ts") or ""))
            last = _parse_ts(str(beads[-1].get("ts") or ""))
            if first and last and last > first:
                sig["velocity_per_min"] = (sig["hb_step_delta"]) / max((last - first) / 60.0, 0.1)
            sig["stale_s"] = int(sig["hb_age_s"] or 0)
            tools = [str(b.get("last_tool") or "-") for b in beads[-10:]]
            prev = ""
            streak = 0
            best = 0
            for t in tools:
                if t and t == prev:
                    streak += 1
                    best = max(best, streak)
                else:
                    streak = 1
                    prev = t
            sig["identical_streak"] = best
    except Exception:
        pass

    cls = classify_run(sig, cfg)
    verdict = str(cls.get("verdict") or "uncertain")
    defer_kill = verdict in ("valuable", "uncertain")
    return {
        "verdict": verdict,
        "score": cls.get("score"),
        "defer_kill": defer_kill,
        "hung": verdict == "hung",
        "reason": cls.get("reason"),
        "signals": sig,
    }


def status(*, run_id: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    overrides = operator_overrides(run_id=run_id)
    recent = _read_jsonl(LOG_PATH, tail=20)
    out: dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA,
        "enabled": cfg.get("enabled", True),
        "config": cfg,
        "overrides_n": len(overrides),
        "recent_events_n": len(recent),
        "paths": {
            "log": str(LOG_PATH),
            "overrides": str(OVERRIDES_PATH),
        },
    }
    if run_id:
        try:
            from mag.run_trail import load_run, read_trail

            run = load_run(run_id)
            if run:
                sig = signals_from_run(run, read_trail(run_id, last_n=80))
                out["evaluation"] = classify_run(sig, cfg)
                out["signals"] = sig
        except Exception as e:
            out["evaluation_error"] = str(e)[:200]
    return out
