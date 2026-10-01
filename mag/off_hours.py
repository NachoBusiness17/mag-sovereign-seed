"""Durable off-hours policy for heavy queue work.

This module is intentionally deterministic and small. It does not launch jobs,
change provider credentials, or promise a lower invoice. It classifies queue
items, decides eligibility against an operator-editable local-time window, and
leaves schedule events that explain why a job waited or was released.

Schema: off_hours.v1
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from config import ROOT

SCHEMA = "off_hours.v1"
CONFIG = ROOT / "configs" / "off_hours.yaml"
TRAIL = ROOT / "logs" / "compute_schedule.jsonl"
QUEUE_DIR = ROOT / "memory" / "runs" / "orchestrator" / "queue"
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_KEYWORDS = (
    "full audit", "deep research", "fine-tune", "finetune", "training",
    "train model", "benchmark", "render", "compile", "vast.ai", "gpu",
    "180b", "long context", "full codebase", "swarm burn",
)
DEFAULT_IMMEDIATE_KEYWORDS = (
    "fleet", "gateway", "openclaw", "repair", "fix", "broken", "outage",
    "incident", "recover", "recovery", "liveness", "health check", "queue",
    "drain", "reconcile", "rightsiz", "right-size", "scheduler",
)
DEFAULT_OVERNIGHT_KEYWORDS = (
    "coding", "codegen", "game", "gaming", "gameplay", "shader", "level design",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_config() -> dict[str, Any]:
    try:
        data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def _tz(config: dict[str, Any]) -> tuple[str, Any]:
    name = str(config.get("timezone") or "America/New_York")
    try:
        return name, ZoneInfo(name)
    except ZoneInfoNotFoundError:
        # Windows may lack the IANA tz database. Keep behavior usable and mark
        # the fallback in the response rather than silently pretending precision.
        return "local-fallback", datetime.now().astimezone().tzinfo or timezone.utc


def _clock(value: Any) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(value or ""))
    if not match:
        return 0, 0
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return 0, 0
    return hour, minute


def _days(window: dict[str, Any]) -> set[int]:
    raw = window.get("days") or list(DAY_NAMES)
    out: set[int] = set()
    for item in raw:
        key = str(item).strip().lower()[:3]
        if key in DAY_NAMES:
            out.add(DAY_NAMES.index(key))
    return out or set(range(7))


def _window_bounds(local: datetime, window: dict[str, Any]) -> tuple[datetime, datetime, bool] | None:
    start_h, start_m = _clock(window.get("start"))
    end_h, end_m = _clock(window.get("end"))
    start_t = local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_t = local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    days = _days(window)
    if (start_h, start_m) == (end_h, end_m):
        return None
    if end_t > start_t:
        active = local.weekday() in days and start_t <= local < end_t
        return start_t, end_t, active
    # Cross-midnight: the early-morning side belongs to the previous day's start.
    if local.weekday() in days and local >= start_t:
        return start_t, end_t + timedelta(days=1), True
    previous = (local.weekday() - 1) % 7
    if previous in days and local < end_t:
        return start_t - timedelta(days=1), end_t, True
    return start_t, end_t + timedelta(days=1), False


def _next_start(local: datetime, windows: list[dict[str, Any]]) -> datetime | None:
    best = None
    for offset in range(0, 15):
        day = (local + timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        for window in windows:
            if day.weekday() not in _days(window):
                continue
            hour, minute = _clock(window.get("start"))
            candidate = day.replace(hour=hour, minute=minute)
            if candidate <= local:
                continue
            if best is None or candidate < best:
                best = candidate
    return best


def schedule_status(*, now: datetime | None = None) -> dict[str, Any]:
    config = _load_config()
    tz_name, tz = _tz(config)
    current = (now or _now()).astimezone(tz)
    windows = [w for w in (config.get("windows") or []) if isinstance(w, dict)]
    active: list[dict[str, Any]] = []
    for window in windows:
        bounds = _window_bounds(current, window)
        if bounds and bounds[2]:
            active.append({"id": window.get("id") or "window", "start": bounds[0].isoformat(), "end": bounds[1].isoformat()})
    next_start = _next_start(current, windows)
    return {
        "schema": SCHEMA,
        "timezone": tz_name,
        "local_now": current.isoformat(),
        "inside_off_hours": bool(active),
        "active_windows": active,
        "next_window_start": next_start.isoformat() if next_start else None,
        "default_policy": str(config.get("default_policy") or "defer_heavy"),
        "overnight_lane": _overnight_lane(config),
        "config_path": str(CONFIG),
    }


def _matches(text: str, values: Any) -> bool:
    return any((item := str(value).strip().lower()) and item in text for value in (values or []))


def _overnight_lane(config: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = (config or _load_config()).get("overnight_lane") or {}
    if not isinstance(raw, dict):
        return {}
    return {
        "id": str(raw.get("id") or "overnight-5.3-max"),
        "provider": str(raw.get("provider") or ""),
        "model": str(raw.get("model") or ""),
        "reason": str(raw.get("reason") or ""),
    }


def overnight_lane() -> dict[str, Any]:
    """Return the configured overnight routing hint without exposing secrets."""
    return _overnight_lane()


def classify(*, goal: str = "", tag: str = "", heavy: bool | None = None,
             schedule_policy: str | None = None) -> dict[str, Any]:
    config = _load_config()
    explicit_policy = str(schedule_policy or "").strip().lower()
    text = f"{tag} {goal}".lower()
    keywords = [str(x).lower() for x in (config.get("heavy_keywords") or DEFAULT_KEYWORDS)]
    inferred = any(keyword and keyword in text for keyword in keywords)
    immediate = _matches(text, config.get("immediate_keywords") or DEFAULT_IMMEDIATE_KEYWORDS)
    overnight = _matches(text, config.get("overnight_keywords") or DEFAULT_OVERNIGHT_KEYWORDS)
    if immediate:
        work_class = "fleet_operation"
    elif overnight and _matches(text, config.get("overnight_keywords") or DEFAULT_OVERNIGHT_KEYWORDS):
        work_class = "gaming" if _matches(text, ("game", "gaming", "gameplay", "shader", "level design")) else "coding"
    else:
        work_class = "general_heavy" if (inferred or heavy) else "normal"
    # Coding/game work is heavy by default because the operator explicitly
    # wants it to use the overnight 5.3 lane. An explicit heavy=False remains
    # an escape hatch for a tiny interactive task.
    if heavy is None:
        is_heavy = inferred or (work_class in {"coding", "gaming"})
    else:
        is_heavy = bool(heavy)
    if explicit_policy in {"anytime", "always", "immediate", "now"}:
        policy = "anytime"
    elif explicit_policy in {"off_hours", "overnight", "defer"}:
        is_heavy = True if heavy is None else bool(heavy)
        policy = "off_hours"
    elif immediate:
        # Fleet/repair/recovery work is valuable precisely because it improves
        # the machinery that schedules everything else.
        policy = "anytime"
    else:
        policy = "off_hours" if is_heavy and str(config.get("default_policy") or "defer_heavy") == "defer_heavy" else "anytime"
    return {
        "compute_class": "heavy" if is_heavy else "normal",
        "heavy": is_heavy,
        "schedule_policy": policy,
        "work_class": work_class,
        "overnight_lane": _overnight_lane(config) if work_class in {"coding", "gaming"} else {},
        "classification_basis": "+".join(filter(None, [
            "explicit" if heavy is not None or explicit_policy else "",
            "fleet-operation" if immediate else "",
            "overnight-work" if overnight else ("heavy-keyword" if inferred else "default"),
        ])),
    }


def decorate(task: dict[str, Any], *, heavy: bool | None = None,
             schedule_policy: str | None = None) -> dict[str, Any]:
    task.update(classify(goal=str(task.get("goal") or ""), tag=str(task.get("tag") or ""),
                        heavy=heavy if heavy is not None else task.get("heavy"),
                        schedule_policy=schedule_policy or task.get("schedule_policy")))
    task.setdefault("schedule_state", "eligible")
    task.setdefault("deferred_count", 0)
    return task


def eligibility(task: dict[str, Any], *, now: datetime | None = None, force: bool = False) -> dict[str, Any]:
    if force:
        return {"eligible": True, "reason": "forced", "schedule": schedule_status(now=now)}
    info = decorate(dict(task))
    schedule = schedule_status(now=now)
    if info["schedule_policy"] != "off_hours" or not info["heavy"]:
        return {"eligible": True, "reason": "anytime", "schedule": schedule, "classification": info}
    if schedule["inside_off_hours"]:
        return {"eligible": True, "reason": "off_hours_window_open", "schedule": schedule, "classification": info}
    return {
        "eligible": False,
        "reason": "heavy_deferred_until_off_hours",
        "next_eligible_at": schedule.get("next_window_start"),
        "schedule": schedule,
        "classification": info,
    }


def dispatch_spec(task: dict[str, Any], *, now: datetime | None = None, force: bool = False) -> dict[str, Any]:
    """Resolve the provider/model for a queued task at dispatch time.

    The original provider/model remain on the queue record. A reroute is
    recorded separately so receipts can distinguish intent from execution.
    Force means "run now" and therefore bypasses the overnight reroute too.
    """
    info = decorate(dict(task))
    original_provider = str(task.get("provider") or "")
    original_model = str(task.get("model") or "")
    out = {
        "provider": original_provider,
        "model": original_model,
        "lane_id": None,
        "rerouted": False,
        "original_provider": original_provider,
        "original_model": original_model,
    }
    if force or info.get("work_class") not in {"coding", "gaming"} or info.get("schedule_policy") != "off_hours":
        return out
    schedule = schedule_status(now=now)
    lane = info.get("overnight_lane") or _overnight_lane()
    if not schedule.get("inside_off_hours") or not lane.get("provider") or not lane.get("model"):
        return out
    out.update({"provider": lane["provider"], "model": lane["model"], "lane_id": lane.get("id"), "rerouted": True})
    return out


def _trail(action: str, task: dict[str, Any], *, reason: str, schedule: dict[str, Any]) -> None:
    try:
        TRAIL.parent.mkdir(parents=True, exist_ok=True)
        with TRAIL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "schema": SCHEMA, "ts": _now().isoformat(), "action": action,
                "queue_id": task.get("queue_id"), "goal": str(task.get("goal") or "")[:180],
                "reason": reason, "schedule": schedule,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def mark_deferred(task: dict[str, Any], decision: dict[str, Any]) -> bool:
    """Annotate a queue row; return True only when a durable state event changed."""
    next_at = decision.get("next_eligible_at")
    changed = task.get("schedule_state") != "deferred" or task.get("next_eligible_at") != next_at
    task["schedule_state"] = "deferred"
    task["schedule_checked_at"] = _now().isoformat()
    task["next_eligible_at"] = next_at
    if changed:
        task["deferred_count"] = int(task.get("deferred_count") or 0) + 1
        task.setdefault("deferred_at", task["schedule_checked_at"])
        _trail("deferred", task, reason=str(decision.get("reason") or "off_hours"), schedule=decision.get("schedule") or {})
    return changed


def mark_eligible(task: dict[str, Any], decision: dict[str, Any]) -> bool:
    changed = task.get("schedule_state") == "deferred"
    task["schedule_state"] = "eligible"
    task["schedule_checked_at"] = _now().isoformat()
    task["next_eligible_at"] = None
    if changed:
        task["released_at"] = task["schedule_checked_at"]
        _trail("released", task, reason=str(decision.get("reason") or "eligible"), schedule=decision.get("schedule") or {})
    return changed


def queue_status(*, queue_dir: Path | None = None) -> dict[str, Any]:
    schedule = schedule_status()
    counts = {"queued": 0, "running": 0, "heavy_queued": 0, "heavy_deferred": 0, "normal_queued": 0}
    scan_dir = queue_dir or QUEUE_DIR
    if scan_dir.is_dir():
        for path in scan_dir.glob("*.json"):
            try:
                task = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            state = str(task.get("status") or "")
            if state in {"queued", "running"}:
                counts[state] += 1
            if state == "queued":
                info = decorate(dict(task))
                if info["heavy"]:
                    counts["heavy_queued"] += 1
                    if task.get("schedule_state") == "deferred":
                        counts["heavy_deferred"] += 1
                else:
                    counts["normal_queued"] += 1
    return {"schema": SCHEMA, **schedule, **counts, "trail": str(TRAIL)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="off-hours")
    parser.add_argument("cmd", nargs="?", default="status", choices=["status", "queue"])
    args = parser.parse_args()
    print(json.dumps(queue_status() if args.cmd == "queue" else schedule_status(), indent=2, default=str))
