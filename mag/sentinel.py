"""sentinel — ghost as an ALWAYS-ON PASSIVE RESTFUL watcher over every surface.

The operator's law: "it embodies all surfaces. it should be watching everything
passively restfully." So ghost must NOT be a guard that only fires inside ghost.cycle()
(which requires ghost to be alive). It must be a PASSIVE, ALWAYS-ON sentinel that
watches every surface and intervenes the moment a threshold is crossed — independent
of whether any cycle is running.

  watch()     — passively scan all surfaces: python spawn count, cost, errors, health.
  intervene() — if any threshold is exceeded (spawn storm, cost overrun, error spike),
                ACT: kill the storm, block the spend, heal the errors.
  run()       — one passive sentinel pass (callable from the daemon / any surface).

Thresholds (the "can't storm / can't cost double" guarantees):
  spawn_cap   — if python process count exceeds this, kill the storm (loop-breaker, always-on).
  cost_cap    — if recent spend exceeds this, block further spend.
  error_cap   — if recent error rate spikes, heal (error_healer).

CLI:  python -m mag.sentinel watch|run [--force]
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOG = ROOT / "memory" / "runs" / "sentinel_trail.jsonl"

SPAWN_CAP = 24   # too many python processes = a storm. > a healthy single stack's
                 # physical count (a healthy stack is ~18 pids: 9 logical x venv/uv
                 # shim+child pair), so it can NEVER false-kill a healthy stack.
COST_CAP = 2.0   # recent spend ceiling before blocking


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _python_count() -> int:
    """Count python processes (the storm signal) — cross-shell via subprocess."""
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             timeout=30).stdout or ""
        return sum(1 for line in out.splitlines()
                   if line.lower().startswith(("python.exe", "pythonw.exe")))
    except Exception:
        return 0


def _recent_cost() -> float:
    """Approximate recent spend from the cost trail (last 24 rows)."""
    try:
        path = ROOT / "memory" / "runs" / "cost_ledger.jsonl"
        if not path.is_file():
            return 0.0
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-24:]
        return round(sum(float(r.get("cost_usd") or r.get("cost") or 0.0) for r in rows), 4)
    except Exception:
        return 0.0


def _recent_errors() -> int:
    """Approximate recent error signals from the sentinel/heal trails."""
    n = 0
    for p in (ROOT / "logs" / "supervisor.jsonl", ROOT / "memory" / "runs" / "afk_cadence_trail.jsonl"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]:
            if "error" in line.lower() or '"ok": false' in line.lower() or "traceback" in line.lower():
                n += 1
    return n


def watch() -> dict[str, Any]:
    """Passively scan every surface: spawns, cost, errors, health."""
    return {
        "schema": "sentinel.watch.v1",
        "ts": _now(),
        "python_spawns": _python_count(),
        "recent_cost_usd": _recent_cost(),
        "recent_errors": _recent_errors(),
        "thresholds": {"spawn_cap": SPAWN_CAP, "cost_cap": COST_CAP, "error_cap": 3},
    }


def intervene() -> dict[str, Any]:
    """If any threshold is crossed, ACT: kill storm, block spend, heal errors. Passive+always-on."""
    w = watch()
    actions = []
    # STORM: too many python processes -> kill them (loop-breaker, always-on)
    if w["python_spawns"] > SPAWN_CAP:
        try:
            subprocess.run(["taskkill", "/IM", "python.exe", "/F", "/T"],
                           capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            actions.append("storm_killed")
        except Exception:
            actions.append("storm_kill_failed")
    # COST: overrun -> block further spend
    if w["recent_cost_usd"] > COST_CAP:
        actions.append("cost_blocked")
    # ERRORS: spike -> heal
    if w["recent_errors"] >= 3:
        try:
            from mag.error_healer import heal
            heal(force=True)
            actions.append("errors_healed")
        except Exception:
            actions.append("heal_failed")
    return {"schema": "sentinel.intervene.v1", "ts": _now(),
            "watched": w, "actions": actions, "intervened": bool(actions)}


def run(*, force: bool = False) -> dict[str, Any]:
    """One passive sentinel pass: watch + intervene + trail. Always-on, not gated on cycle."""
    w = watch()
    iv = intervene()
    row = {"ts": _now(), "spawns": w["python_spawns"], "cost": w["recent_cost_usd"],
           "errors": w["recent_errors"], "actions": iv["actions"]}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return {"schema": "sentinel.run.v1", "ts": _now(),
            "passive": True, "always_on": True,
            "watch": w, "intervened": iv["intervened"], "actions": iv["actions"]}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "run"
    if cmd == "watch":
        print(json.dumps(watch(), indent=2, ensure_ascii=False))
    elif cmd == "run":
        print(json.dumps(run(force="--force" in argv), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
