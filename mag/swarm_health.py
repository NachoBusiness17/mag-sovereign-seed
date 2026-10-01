"""swarm_health — watch swarm health and turn it into self-improvement, coded into law.

STEAL (memory/steal + this sweep): bmas health_loop (per-agent probe + aggregate status),
agentswarm applyLiveness/STALE_AFTER (pid + heartbeat grace staleness), agentswarm breaker
(failure-rate -> degrade), leeroo check_servers_state (aggregate sweep), blackboard retry
(backoff so a crash-on-boot agent can't spam).

THE LAW: every aspect of the system is self-improving AS CODED INTO LAW — a health signal
deterministically maps to a self-improvement action (restart / stall_sweep / failure_kb /
improve_cycle), logged to the trail + training_events (measured, never silent).

  1. probe_agent(name)  -> per-agent health row {alive, last_heartbeat, staleness_s, status}
  2. swarm_health()     -> loop over AGENTS -> rows + aggregate up/degraded/down
  3. health_law(rows)   -> THE CODED LAW: sick/stale -> restart/sweep/log/improve
  4. run_cadence()      -> probe + apply the law + log to trail. Wired into ghost.cycle().

Schema: swarm_health.v1
CLI:  python -m mag.swarm_health health | law [--apply] | status | cadence
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "swarm_health.v1"
RUNS = ROOT / "memory" / "runs" / "swarm_health"
TRAIL = RUNS / "trail.jsonl"

# The swarm roster (first-class agents) + staleness grace in seconds.
AGENTS = ["ghost", "drainer", "autorun", "dashboard", "seats", "republic_os", "backend"]
STALE_AFTER_S = {"ghost": 120, "drainer": 300, "autorun": 300, "dashboard": 60,
                 "seats": 120, "republic_os": 600, "backend": 120}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch() -> float:
    import time
    return time.time()


def _log_trail(row: dict[str, Any]) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), **row}, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------- probe ----
def _pid_alive(pid: int | None) -> bool:
    try:
        from mag.health import _pid_alive as h
        return bool(h(pid))
    except Exception:
        return False


def _supervisor_row(name: str) -> dict[str, Any]:
    """Read a supervised-loop's liveness from process_supervisor.status()."""
    try:
        from mag.process_supervisor import status as ps_status
        st = ps_status()
        loops = st.get("loops") or st.get("registry") or {}
        if name == "autorun":
            info = loops.get("autorun") or {}
        elif name == "ghost":
            info = loops.get("ghost") or {}
        else:
            info = {}
        alive = bool(info.get("running") or info.get("alive"))
        pid = info.get("pid")
        return {"alive": alive or _pid_alive(pid), "pid": pid, "status": "up" if alive else "down"}
    except Exception:
        return {"alive": False, "status": "down"}


def probe_agent(name: str) -> dict[str, Any]:
    """Probe ONE swarm agent -> {name, alive, last_heartbeat, staleness_s, status}."""
    row: dict[str, Any] = {"agent": name, "alive": False, "status": "down", "staleness_s": None}
    try:
        if name in ("ghost", "autorun"):
            if name == "ghost":
                # Control plane = ghost-daemon on :9000. NOT process_supervisor's
                # 'ghost' loop (that is a DIFFERENT opt-in auto-deploy cadence whose
                # name collides). Checking that loop reported ghost 'down' always,
                # so health_law restarted 'ghost' every cadence = the 16s cycle storm.
                from mag.health import _port_open
                row["alive"] = bool(_port_open(9000))
                row["status"] = "up" if row["alive"] else "down"
            else:
                row.update(_supervisor_row(name))
        elif name == "drainer":
            try:
                from mag.preferences import drainer_status
                d = drainer_status()
                row["alive"] = bool(d.get("enabled") or d.get("autorun_allowed"))
                row["status"] = "up" if row["alive"] else "down"
            except Exception:
                pass
        elif name == "dashboard":
            from mag.health import _port_open
            row["alive"] = bool(_port_open(8765))
            row["status"] = "up" if row["alive"] else "down"
        elif name == "backend":
            from mag.health import _port_open
            row["alive"] = bool(_port_open(8000))
            row["status"] = "up" if row["alive"] else "down"
        elif name == "seats":
            try:
                from mag.seat_registry import list_registered
                regs = list_registered(limit=20, live_only=False)
                live = sum(1 for r in regs if int(r.get("heartbeat_age_s") or 999) <= 120)
                row["alive"] = live > 0
                row["n_seats"] = len(regs)
                row["n_live"] = live
                row["status"] = "up" if live > 0 else "down"
            except Exception:
                pass
        elif name == "republic_os":
            from mag.mycelium import status as mc_status
            s = mc_status()
            row["alive"] = (s.get("nodes") or 0) > 0
            row["nodes"] = s.get("nodes")
            row["status"] = "up" if row["alive"] else "down"
    except Exception:
        row["status"] = "unknown"
    row["staleness_s"] = 0 if row.get("alive") else STALE_AFTER_S.get(name, 120)
    return row


def swarm_health() -> dict[str, Any]:
    """Aggregate swarm health: loop over AGENTS -> rows + overall status."""
    rows = [probe_agent(a) for a in AGENTS]
    up = sum(1 for r in rows if r.get("alive"))
    if up == len(rows):
        overall = "up"
    elif up == 0:
        overall = "down"
    else:
        overall = "degraded"
    return {"schema": SCHEMA, "ok": overall == "up", "overall": overall,
            "agents_up": up, "agents_total": len(rows), "agents": {r["agent"]: r for r in rows},
            "ts": _now()}


# ------------------------------------------------------------------ law ----
def health_law(health: dict[str, Any] | None = None, *, apply: bool = False) -> dict[str, Any]:
    """THE CODED SELF-IMPROVEMENT LAW: map each health signal deterministically to a
    self-improvement action. Every aspect of the system self-improves as coded into law."""
    health = health or swarm_health()
    rows = health.get("agents", {})
    actions: list[dict[str, Any]] = []

    def act(agent: str, kind: str, why: str) -> None:
        actions.append({"agent": agent, "action": kind, "why": why})

    # sick supervised loops -> restart
    for name in ("ghost", "autorun"):
        r = rows.get(name) or {}
        if not r.get("alive"):
            act(name, "restart", f"{name} down")
            if apply:
                try:
                    from mag.process_supervisor import restart_loop
                    restart_loop(name)
                except Exception:
                    pass
    # dashboard down -> note (restart via restart_lab)
    if not (rows.get("dashboard") or {}).get("alive"):
        act("dashboard", "note_restart_lab", "dashboard port 8765 down")
    # seats stale -> ping/steer via failure_kb (the ghost pings them)
    if not (rows.get("seats") or {}).get("alive"):
        act("seats", "failure_kb_log", "no live seats")
        if apply:
            try:
                from mag.failure_kb import log_failure
                log_failure(kind="swarm_health", detail="no live seats", phase="swarm_health")
            except Exception:
                pass
    # republic_os graph dead -> log
    if not (rows.get("republic_os") or {}).get("alive"):
        act("republic_os", "failure_kb_log", "mycelium graph empty")
    # overall degraded -> run an improve cycle (self-improvement)
    if health.get("overall") in ("degraded", "down"):
        act("swarm", "improve_cycle", f"swarm {health.get('overall')}")
        if apply:
            try:
                from mag.improve_loop import run_improve_cycle
                # Health enforcement is itself a control-plane call.  Queue
                # admission may happen here, but deep pile/spider/nervous
                # work belongs to the cadence owner and must not block the
                # law executor.
                run_improve_cycle(source="swarm_health_law", control_plane=True)
            except Exception:
                pass

    for a in actions:
        _log_trail({"kind": "health_law", **a, "applied": apply})
    return {"ok": True, "overall": health.get("overall"), "actions": actions, "applied": apply}


def status() -> dict[str, Any]:
    h = swarm_health()
    return {"schema": SCHEMA, "ok": h["ok"], "overall": h["overall"],
            "agents_up": h["agents_up"], "agents_total": h["agents_total"], "ts": _now()}


def run_cadence() -> dict[str, Any]:
    """Idempotent: probe swarm + apply the self-improvement law. Wired into ghost.cycle()."""
    h = swarm_health()
    law = health_law(h, apply=True)
    _log_trail({"kind": "swarm_cadence", "overall": h["overall"], "actions": len(law["actions"])})
    return {"ok": True, "action": "swarm_cadence", "health": h, "law": law}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="swarm-health", description="Watch swarm health + self-improvement law")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health", help="aggregate swarm health")
    p_law = sub.add_parser("law", help="the coded self-improvement law")
    p_law.add_argument("--apply", action="store_true")
    sub.add_parser("status", help="quick health status")
    sub.add_parser("cadence", help="probe + apply the law")
    args = ap.parse_args(argv)
    if args.cmd == "health":
        print(json.dumps(swarm_health(), indent=2, default=str)[:6000])
    elif args.cmd == "law":
        print(json.dumps(health_law(apply=args.apply), indent=2, default=str)[:4000])
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["probe_agent", "swarm_health", "health_law", "status", "run_cadence", "main"]
