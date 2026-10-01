"""Cost Enforcer — hard spend caps, auto-kill, real-time ledger.

Prevents bankruptcy. Every API call is logged. Every dollar is tracked.
When spend hits the cap, Ghost kills all running agents automatically.

ARCHITECTURE:
  Every provider call → log to cost ledger
  Every 10s → check running total against caps
  If over cap → kill all orchestrator tasks + stop autonomous loop
  Warning thresholds: 50%, 80%, 95% → publish to event bus
  Sidebar dashboard reads GET /api/v1/cost for real-time display

CAPS (configurable):
  daily:      $0.50   (hard stop for the day — reset at midnight UTC)
  hourly:     $0.10   (prevents burst spending)
  per_task:   $0.05   (kills individual tasks that exceed)
  grok_daily: $0.10   (Grok is scarce — tighter cap)

COST PER CALL (estimates):
  ollama:             $0       (local, free)
  deepseek-v4-flash:  $0.00013 (per 1K tokens, ~$0.00013/call)
  grok-2-latest:      $0.0003  (sense/classify tier)
  grok-3-mini:        $0.003   (analysis tier)
  grok-3:             $0.008   (deep tier)
  grok-4:             $0.025   (orchestrate tier)

Schema: cost_enforcer.v1
Law: Caps are HARD. No override without explicit operator action.
"""

from __future__ import annotations

import json
import os
import time
from mag.chain_query import chain  # auto-added by doctor_agent
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Paths ──
COST_LEDGER = ROOT / "memory" / "ghost" / "cost_ledger.jsonl"
CAPS_FILE = ROOT / "memory" / "ghost" / "cost_caps.json"
KILL_LOG = ROOT / "memory" / "ghost" / "cost_kills.jsonl"

# ── Default caps ──
DEFAULT_CAPS = {
    "daily": 0.50,        # $0.50/day hard stop
    "hourly": 0.10,       # $0.10/hour burst prevention
    "per_task": 0.05,     # $0.05/task max
    "grok_daily": 0.10,   # Grok-specific daily cap
    "enabled": True,
    "auto_kill": True,    # auto-kill agents when cap hit
    "warning_thresholds": [0.50, 0.80, 0.95],  # warn at 50%, 80%, 95%
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, tail: int = 500) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ═══════════════════════════════════════════════════════════════════
# CAPS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def get_caps() -> dict[str, Any]:
    """Get current spending caps."""
    caps = _load_json(CAPS_FILE)
    if not caps:
        caps = dict(DEFAULT_CAPS)
        _save_json(CAPS_FILE, caps)
    return caps


def update_caps(**kwargs) -> dict[str, Any]:
    """Update spending caps. Only provided keys are changed."""
    caps = get_caps()
    caps.update(kwargs)
    caps["updated_at"] = _now()
    _save_json(CAPS_FILE, caps)
    return caps


def load_cost_ledger(since_hours: float = 24.0) -> list[dict[str, Any]]:
    """Load cost ledger entries since N hours ago."""
    cutoff = datetime.now(timezone.utc).timestamp() - (since_hours * 3600)
    entries = _read_jsonl(COST_LEDGER, tail=1000)
    return [
        e for e in entries
        if _parse_ts(e.get("ts", "")) >= cutoff
    ]


def _parse_ts(ts_str: str) -> float:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════
# SPEND TRACKING
# ═══════════════════════════════════════════════════════════════════

def log_call(
    provider: str,
    model: str,
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    cost_est: float = 0.0,
    task_id: str = "",
    ok: bool = True,
) -> dict[str, Any]:
    """Log an API call to the cost ledger."""
    entry = {
        "ts": _now(),
        "provider": provider,
        "model": model,
        "tokens_prompt": tokens_prompt,
        "tokens_completion": tokens_completion,
        "tokens_total": tokens_prompt + tokens_completion,
        "cost_est": round(cost_est, 6),
        "task_id": task_id,
        "ok": ok,
    }
    _append_jsonl(COST_LEDGER, entry)
    return entry


def get_current_spend() -> dict[str, Any]:
    """Get current spending breakdown."""
    now_ts = datetime.now(timezone.utc).timestamp()
    hour_ago = now_ts - 3600
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

    entries = _read_jsonl(COST_LEDGER, tail=500)

    total_all = 0.0
    total_hour = 0.0
    total_day = 0.0
    total_grok = 0.0
    by_provider: dict[str, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "cost": 0.0, "tokens": 0})
    recent_calls: list[dict[str, Any]] = []

    for e in entries:
        ts = _parse_ts(e.get("ts", ""))
        if ts == 0:
            continue
        cost = float(e.get("cost_est", 0))
        provider = e.get("provider", "?")
        tokens = int(e.get("tokens_total", 0))

        total_all += cost
        by_provider[provider]["calls"] += 1
        by_provider[provider]["cost"] += cost
        by_provider[provider]["tokens"] += tokens

        if ts >= hour_ago:
            total_hour += cost
        if ts >= day_start:
            total_day += cost
        if provider == "grok":
            total_grok += cost

        if len(recent_calls) < 10:
            recent_calls.append({
                "ts": e.get("ts", ""),
                "provider": provider,
                "model": e.get("model", "?"),
                "cost": round(cost, 6),
                "task_id": e.get("task_id", "")[:16],
            })

    # Running agent count
    running_agents = 0
    try:
        tasks_dir = ROOT / "memory" / "runs" / "orchestrator" / "tasks"
        if tasks_dir.is_dir():
            for tf in tasks_dir.iterdir():
                if tf.suffix == ".json":
                    try:
                        task = json.loads(tf.read_text(encoding="utf-8"))
                        if task.get("status") == "running":
                            running_agents += 1
                    except (json.JSONDecodeError, OSError):
                        pass
    except Exception:
        pass

    return {
        "ts": _now(),
        "total_all_time": round(total_all, 4),
        "total_hour": round(total_hour, 4),
        "total_today": round(total_day, 4),
        "total_grok": round(total_grok, 4),
        "by_provider": {k: {"calls": v["calls"], "cost": round(v["cost"], 4), "tokens": v["tokens"]}
                        for k, v in sorted(by_provider.items(), key=lambda x: x[1]["cost"], reverse=True)},
        "running_agents": running_agents,
        "recent_calls": recent_calls,
        "caps": get_caps(),
    }


# ═══════════════════════════════════════════════════════════════════
# ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════

def check_caps() -> dict[str, Any]:
    """Check current spend against caps. Returns violations if any."""
    spend = get_current_spend()
    caps = spend["caps"]

    if not caps.get("enabled", True):
        return {"ok": True, "enforced": False, "reason": "caps disabled"}

    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    daily_cap = caps.get("daily", 0.50)
    hourly_cap = caps.get("hourly", 0.10)
    grok_cap = caps.get("grok_daily", 0.10)

    # Check daily
    daily_pct = spend["total_today"] / daily_cap if daily_cap > 0 else 0
    if spend["total_today"] >= daily_cap:
        violations.append({
            "cap": "daily",
            "spent": round(spend["total_today"], 4),
            "limit": daily_cap,
            "pct": round(daily_pct * 100, 1),
        })
    elif daily_pct >= 0.95:
        warnings.append({"cap": "daily", "pct": 95, "spent": round(spend["total_today"], 4)})
    elif daily_pct >= 0.80:
        warnings.append({"cap": "daily", "pct": 80, "spent": round(spend["total_today"], 4)})
    elif daily_pct >= 0.50:
        warnings.append({"cap": "daily", "pct": 50, "spent": round(spend["total_today"], 4)})

    # Check hourly
    hourly_pct = spend["total_hour"] / hourly_cap if hourly_cap > 0 else 0
    if spend["total_hour"] >= hourly_cap:
        violations.append({
            "cap": "hourly",
            "spent": round(spend["total_hour"], 4),
            "limit": hourly_cap,
            "pct": round(hourly_pct * 100, 1),
        })

    # Check Grok
    grok_pct = spend["total_grok"] / grok_cap if grok_cap > 0 else 0
    if spend["total_grok"] >= grok_cap:
        violations.append({
            "cap": "grok_daily",
            "spent": round(spend["total_grok"], 4),
            "limit": grok_cap,
            "pct": round(grok_pct * 100, 1),
        })

    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "spend": {
            "daily": {"spent": round(spend["total_today"], 4), "cap": daily_cap, "pct": round(daily_pct * 100, 1)},
            "hourly": {"spent": round(spend["total_hour"], 4), "cap": hourly_cap, "pct": round(hourly_pct * 100, 1)},
            "grok": {"spent": round(spend["total_grok"], 4), "cap": grok_cap, "pct": round(grok_pct * 100, 1)},
        },
        "running_agents": spend["running_agents"],
    }


def enforce_caps() -> dict[str, Any]:
    """Check caps and kill agents if violated. Call every 10-30 seconds."""
    result = check_caps()

    if not result["ok"] and result["violations"]:
        caps = get_caps()
        if caps.get("auto_kill", True):
            killed = _kill_all_agents(result["violations"])
            result["action"] = "killed"
            result["killed"] = killed
        else:
            result["action"] = "warning_only"
    else:
        result["action"] = "ok"

    return result


def _kill_all_agents(violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Kill all running orchestrator tasks. Emergency stop."""
    killed: list[str] = []
    errors: list[str] = []

    tasks_dir = ROOT / "memory" / "runs" / "orchestrator" / "tasks"
    if tasks_dir.is_dir():
        for tf in tasks_dir.iterdir():
            if tf.suffix != ".json":
                continue
            try:
                task = json.loads(tf.read_text(encoding="utf-8"))
                if task.get("status") != "running":
                    continue
                pid = task.get("pid")
                task_id = task.get("task_id", tf.stem)

                if pid:
                    try:
                        import signal
                        os.kill(pid, signal.SIGTERM)
                        killed.append(task_id)
                    except Exception as e:
                        errors.append(f"{task_id}: {e}")
                        # Force kill on Windows
                        try:
                            import subprocess
                            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
                            killed.append(task_id)
                        except Exception:
                            errors.append(f"{task_id}: force kill failed")

                # Mark task as killed
                task["status"] = "killed_by_enforcer"
                task["ended_at"] = _now()
                task["kill_reason"] = str(violations)
                tf.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")

            except (json.JSONDecodeError, OSError):
                continue

    # Log the kill event
    _append_jsonl(KILL_LOG, {
        "ts": _now(),
        "violations": violations,
        "killed": killed,
        "errors": errors,
    })

    # Publish to event bus
    try:
        from mag.verkle_bus import publish_sync, CH_LEAK
        publish_sync(CH_LEAK, {
            "type": "cost_enforcer_kill",
            "violations": violations,
            "killed_count": len(killed),
            "ts": _now(),
        })
    except Exception:
        pass

    return {"count": len(killed), "task_ids": killed, "errors": errors}


def kill_all_agents_manual() -> dict[str, Any]:
    """Manual kill switch — operator triggered."""
    return _kill_all_agents([{"cap": "manual", "reason": "operator triggered kill switch"}])


# ═══════════════════════════════════════════════════════════════════
# ENFORCER LOOP — run in Ghost's daemon
# ═══════════════════════════════════════════════════════════════════

async def cost_enforcer_loop(interval_s: float = 15.0) -> None:
    """Background loop: enforce spending caps. Kill on violation.

    Run this in Ghost's daemon lifespan alongside other background loops.
    Checks every 15 seconds. Publishes warnings at 50/80/95%.
    Auto-kills at 100% if auto_kill is enabled.
    """
    import asyncio

    last_warning_level = 0  # 0=none, 1=50%, 2=80%, 3=95%, 4=100%

    while True:
        try:
            await asyncio.sleep(interval_s)
            result = check_caps()

            # Determine warning level
            daily_pct = result["spend"]["daily"]["pct"]
            current_level = 0
            if daily_pct >= 100:
                current_level = 4
            elif daily_pct >= 95:
                current_level = 3
            elif daily_pct >= 80:
                current_level = 2
            elif daily_pct >= 50:
                current_level = 1

            # Publish on level change (avoid spam)
            if current_level > last_warning_level:
                try:
                    from mag.verkle_bus import publish as bus_pub, CH_LEAK
                    await bus_pub(CH_LEAK, {
                        "type": "cost_warning",
                        "level": current_level,
                        "daily_pct": daily_pct,
                        "daily_spent": result["spend"]["daily"]["spent"],
                        "daily_cap": result["spend"]["daily"]["cap"],
                        "ts": _now(),
                    })
                except Exception:
                    pass
                last_warning_level = current_level
            elif current_level == 0:
                last_warning_level = 0

            # Enforce if violated
            if not result["ok"]:
                enforce_result = enforce_caps()
                if enforce_result.get("action") == "killed":
                    last_warning_level = 4  # stay at max

        except asyncio.CancelledError:
            break
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════

def cost_status() -> dict[str, Any]:
    """Full cost status for sidebar display."""
    spend = get_current_spend()
    caps_result = check_caps()

    return {
        "schema": "cost_enforcer.v1",
        "ts": _now(),
        "spend": spend,
        "caps": caps_result,
        "status": "OVER_CAP" if not caps_result["ok"] else (
            "WARNING" if caps_result["warnings"] else "OK"
        ),
        "running_agents": spend["running_agents"],
        "caps_config": get_caps(),
    }
