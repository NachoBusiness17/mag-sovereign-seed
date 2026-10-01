"""Agent stack viewport — services, fleet, and REST-sourced outputs.

Composes existing REST-backed modules into one desk-like payload for UI/Roku/brain.
Schema: mag_stack.v1
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "mag_stack.v1"

TRIAD_ROLES = (
    ("backend", "Backend", "FastAPI tool service - 127.0.0.1:8000"),
    ("engine", "Engineer", "the Mag seat / planner"),
    ("scribe", "Scribe", "synthesis_agent.py - running commentary"),
    ("dashboard", "Dashboard", "this board - 127.0.0.1:8765"),
    ("lab", "Integral lab", "watch + companion heartbeat (no dashboard)"),
    ("mirror", "Mirror desk", "Sovereign Mirror strike - 127.0.0.1:8743"),
    ("drainer", "Drainer", "optional queue auto-advance"),
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        from mag_launch import _pid_alive as launch_pid_alive

        return bool(launch_pid_alive(int(pid)))
    except Exception:
        return False


def build_fleet_triad() -> list[dict[str, Any]]:
    """Persistent supervisor roles from mag_launch.json + live pid checks."""
    import json

    from config import ROOT

    state_path = ROOT / "state" / "mag_launch.json"
    try:
        st = json.loads(state_path.read_text(encoding="utf-8"))
        pids = st.get("pids") or {}
        notes = st.get("notes") or {}
        health = st.get("health") or {}
    except Exception:
        pids, notes, health = {}, {}, {}
    out: list[dict[str, Any]] = []
    for key, label, desc in TRIAD_ROLES:
        pid = pids.get(key)
        out.append(
            {
                "key": key,
                "label": label,
                "desc": desc,
                "pid": pid,
                "alive": _pid_alive(pid),
                "health": health.get(key),
                "note": notes.get(key, ""),
                "api": "GET /api/v1/fleet/triad",
            }
        )
    return out


def build_supervisor_snapshot() -> dict[str, Any]:
    """Supervisor slice — same shape as router-status supervisor block."""
    import json

    from config import ROOT

    try:
        ml = json.loads((ROOT / "state" / "mag_launch.json").read_text(encoding="utf-8"))
        pids = ml.get("pids") or {}
        wanted = ml.get("wanted") or {}
        alive = {role: pid for role, pid in pids.items() if pid and _pid_alive(pid)}
        any_live = any(alive.get(r) for r in wanted if wanted.get(r))
        return {
            "running": any_live,
            "pids": alive,
            "wanted": wanted,
            "started": ml.get("started"),
            "check_s": ml.get("check_s"),
            "api": "GET /api/v1/router-status",
        }
    except Exception:
        return {"running": False, "pids": {}, "wanted": {}, "api": "GET /api/v1/router-status"}


def build_fleet_snapshot() -> dict[str, Any]:
    """Orchestrator fleet + queue — same shape as router-status fleet block."""
    import json

    from mag.orchestrator import TASK_DIR, TERMINAL

    tasks: list[dict[str, Any]] = []
    if TASK_DIR.is_dir():
        for p in TASK_DIR.glob("*.json"):
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            tasks.append(
                {
                    "task_id": t.get("task_id"),
                    "goal": (t.get("goal") or "")[:80],
                    "status": t.get("status"),
                    "provider": t.get("provider"),
                    "created": t.get("created"),
                    "finished": t.get("finished"),
                    "exit_code": t.get("exit_code"),
                }
            )
    tasks.sort(key=lambda t: t.get("created") or "", reverse=True)
    fleet = {
        "total": len(tasks),
        "running": sum(1 for t in tasks if t["status"] not in TERMINAL),
        "done": sum(1 for t in tasks if t["status"] == "done"),
        "failed": sum(1 for t in tasks if t["status"] in ("failed", "died")),
        "killed": sum(1 for t in tasks if t["status"] == "killed"),
        "recent": tasks[:10],
        "api": "GET /api/v1/router-status",
    }
    try:
        from mag.orchestrator import queue_status

        fleet["queue"] = queue_status()
    except Exception:
        pass
    return fleet


def _read_jsonl_tail(path: Path, n: int = 1) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            import json

            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


def build_research_glance() -> list[dict[str, Any]]:
    """Research loops visible on Stack — spider, conductor, resonance, desk health."""
    rows: list[dict[str, Any]] = []

    try:
        from mag.spider import tick

        s = tick(dry=True)
        rows.append(
            {
                "id": "spider",
                "label": "Spider",
                "status": "ok" if s.get("ok") else "degraded",
                "text": f"{s.get('n_signals', 0)} signal(s)" + (
                    f" · last: {(s.get('signals') or [{}])[0].get('kind', '?')}"
                    if s.get("signals")
                    else ""
                ),
                "api": "python main.py spider tick",
                "proof": "memory/runs/spider_trail.jsonl",
            }
        )
    except Exception as e:
        rows.append(
            {
                "id": "spider",
                "label": "Spider",
                "status": "error",
                "text": str(e)[:120],
                "api": "python main.py spider tick",
            }
        )

    try:
        from config import ROOT

        tail = _read_jsonl_tail(ROOT / "memory" / "runs" / "conductor_trail.jsonl", 1)
        last = tail[0] if tail else {}
        rows.append(
            {
                "id": "conductor",
                "label": "L-conductor",
                "status": "ok" if last else "idle",
                "text": (
                    f"phase={last.get('phase', '?')} · seat={last.get('seat', '?')}"
                    if last
                    else "no trail yet — run main.py conductor"
                ),
                "api": "python main.py conductor",
                "proof": "memory/runs/conductor_trail.jsonl",
            }
        )
        desk_tail = _read_jsonl_tail(ROOT / "memory" / "runs" / "desk_conductor_trail.jsonl", 1)
        desk_last = desk_tail[0] if desk_tail else {}
        rows.append(
            {
                "id": "desk_conductor",
                "label": "Desk conductor",
                "status": "ok" if desk_last else "idle",
                "text": (
                    f"action={desk_last.get('action', desk_last.get('mode', '?'))}"
                    if desk_last
                    else "no desk trail — Step on Agent Desk"
                ),
                "api": "desk Step / Loop",
                "proof": "memory/runs/desk_conductor_trail.jsonl",
            }
        )
    except Exception as e:
        rows.append({"id": "conductor", "label": "Conductor", "status": "error", "text": str(e)[:80]})

    try:
        from config import ROOT

        findings = ROOT / "memory" / "resonance" / "findings.jsonl"
        n = 0
        if findings.is_file():
            n = sum(1 for ln in findings.read_text(encoding="utf-8").splitlines() if ln.strip())
        rows.append(
            {
                "id": "resonance",
                "label": "Resonance",
                "status": "ok" if n else "idle",
                "text": f"{n} finding(s) on disk",
                "api": "python main.py resonance tick",
                "proof": "memory/resonance/findings.jsonl",
            }
        )
    except Exception as e:
        rows.append({"id": "resonance", "label": "Resonance", "status": "error", "text": str(e)[:80]})

    try:
        from mag.desk_dialogue import desk_health_check

        dh = desk_health_check(auto_heal=False)
        rows.append(
            {
                "id": "desk_health",
                "label": "Desk health",
                "status": "ok" if not dh.get("polluted") else "warn",
                "text": (
                    "clean"
                    if not dh.get("polluted")
                    else f"polluted: {', '.join(dh.get('canvas_issues') or [])}"
                ),
                "api": "GET /api/v1/nervous",
                "proof": "memory/working/agent_desk.md",
            }
        )
    except Exception as e:
        rows.append({"id": "desk_health", "label": "Desk health", "status": "error", "text": str(e)[:80]})

    try:
        from mag.local_pulse import build_local_pulse

        lp = build_local_pulse()
        cpu = lp.get("cpu") or {}
        st = lp.get("state") or "offline"
        status = "ok" if st == "loaded" else ("warn" if st == "thinking" else st)
        cpu_bits: list[str] = []
        if cpu.get("system_pct") is not None:
            cpu_bits.append(f"sys {cpu['system_pct']}%")
        if cpu.get("ollama_proc_pct") is not None:
            cpu_bits.append(f"proc {cpu['ollama_proc_pct']}%")
        text = lp.get("headline") or st
        if cpu_bits:
            text += f" · {' · '.join(cpu_bits)}"
        rows.append(
            {
                "id": "local_pulse",
                "label": "Local pulse",
                "status": status,
                "text": text[:160],
                "api": "GET /api/v1/local-pulse",
                "proof": "memory/working/local_thinking.json",
            }
        )
    except Exception as e:
        rows.append({"id": "local_pulse", "label": "Local pulse", "status": "error", "text": str(e)[:80]})

    try:
        from mag.gstd_probe import build_gstd_stack_row

        rows.append(build_gstd_stack_row())
    except Exception as e:
        rows.append({"id": "gstd_probe", "label": "GSTD probe", "status": "error", "text": str(e)[:80]})

    try:
        from mag.local_scheduler import build_stack_row as sched_row

        rows.append(sched_row())
    except Exception as e:
        rows.append({"id": "local_scheduler", "label": "Local scheduler", "status": "error", "text": str(e)[:80]})

    try:
        from mag.unsloth_seat import build_unsloth_payload

        up = build_unsloth_payload()
        rr = up.get("research_row") or {}
        rows.append(
            {
                "id": rr.get("id") or "unsloth_studio",
                "label": rr.get("label") or "Unsloth GPU",
                "status": rr.get("status") or "idle",
                "text": rr.get("text") or "",
                "api": rr.get("api") or "GET /api/v1/unsloth",
                "proof": rr.get("proof") or "memory/working/unsloth_seat.json",
            }
        )
    except Exception as e:
        rows.append({"id": "unsloth_studio", "label": "Unsloth GPU", "status": "error", "text": str(e)[:80]})

    return rows


def build_stack_payload(*, feed_limit: int = 24, agent_limit: int = 30) -> dict[str, Any]:
    from mag.chronicle import build_chronicle_payload
    from mag.desk_dialogue import desk_health_check, read_cursor, read_trust_status
    from mag.nervous_system import build_glance
    from mag.power import stack_status
    from mag.seat_feed import unified_seat_feed

    power = stack_status()
    nervous = build_glance(write=False)
    body = nervous.get("body") or {}
    cur = read_cursor()
    trust = read_trust_status()

    services: list[dict[str, Any]] = []
    probes = {
        "backend": ("GET", "http://127.0.0.1:8000/health", 8000),
        "dashboard": ("GET", "http://127.0.0.1:8765/", 8765),
        "mirror": ("GET", "http://127.0.0.1:8743/", 8743),
    }
    for sid, up in (power.get("services") or {}).items():
        method, url, port = probes.get(sid, ("GET", "", None))
        services.append(
            {
                "id": sid,
                "label": sid.replace("_", " ").title(),
                "up": bool(up),
                "port": port,
                "probe": url,
                "method": method,
                "api": "GET /api/v1/power",
            }
        )
    services.append(
        {
            "id": "ollama",
            "label": "Ollama",
            "up": bool(body.get("ollama_11434")),
            "port": 11434,
            "probe": "http://127.0.0.1:11434/api/tags",
            "method": "GET",
            "api": "GET /api/v1/nervous",
        }
    )

    sup = power.get("supervisor") or {}
    for role, pid in (sup.get("pids") or {}).items():
        if not pid:
            continue
        services.append(
            {
                "id": f"supervisor_{role}",
                "label": f"Supervisor · {role}",
                "up": True,
                "port": None,
                "probe": f"pid:{pid}",
                "method": "PROC",
                "api": "GET /api/v1/power",
            }
        )

    agents: list[dict[str, Any]] = []
    try:
        from mag.orchestrator import list_tasks_live

        for t in list_tasks_live(limit=agent_limit) or []:
            agents.append(
                {
                    "kind": "worker",
                    "id": t.get("task_id"),
                    "name": (t.get("tag") or t.get("task_id") or "?")[:40],
                    "goal": (t.get("goal") or "")[:140],
                    "status": t.get("status"),
                    "phase": t.get("phase"),
                    "provider": t.get("provider"),
                    "heartbeat_age_s": t.get("heartbeat_age_s"),
                    "api": "GET /api/v1/agents",
                }
            )
    except Exception:
        pass

    try:
        from mag.seat_registry import list_registered

        for s in list_registered(live_only=True, limit=15) or []:
            agents.append(
                {
                    "kind": "seat",
                    "id": s.get("task_id") or s.get("seat"),
                    "name": str(s.get("seat") or "seat"),
                    "goal": (s.get("goal") or "")[:140],
                    "status": "live",
                    "phase": s.get("mode"),
                    "provider": s.get("parent"),
                    "heartbeat_age_s": s.get("heartbeat_age_s"),
                    "api": "GET /api/v1/seats",
                }
            )
    except Exception:
        pass

    agents.extend(
        [
            {
                "kind": "desk_local",
                "id": "desk-local",
                "name": "Local · gemma4",
                "status": "wake_pending" if cur.get("local_wake_pending") else "ready",
                "phase": cur.get("holder"),
                "provider": "ollama",
                "turn": cur.get("turn"),
                "api": "GET /api/v1/desk-dialogue",
            },
            {
                "kind": "desk_remote",
                "id": "desk-deepseek",
                "name": "DeepSeek · remote",
                "status": "asleep" if cur.get("remote_asleep", True) else "awake",
                "phase": "wake_on_edit",
                "provider": "deepseek",
                "turn": cur.get("turn"),
                "api": "GET /api/v1/desk-dialogue",
            },
        ]
    )

    try:
        from mag.unsloth_seat import build_unsloth_payload

        up = build_unsloth_payload()
        agents.append(up.get("agent_row") or {})
    except Exception:
        pass

    outputs: list[dict[str, Any]] = []
    feed = unified_seat_feed(limit=feed_limit)
    paths = feed.get("paths") or {}
    for e in feed.get("entries") or []:
        src = str(e.get("source") or "?")
        outputs.append(
            {
                "ts": e.get("ts"),
                "channel": src,
                "text": (e.get("preview") or e.get("event") or "")[:220],
                "api": "GET /api/v1/seat-feed",
                "proof": paths.get(f"{src}_feed") or paths.get(src),
            }
        )

    chronicle = build_chronicle_payload()
    for ev in (chronicle.get("events") or [])[:12]:
        outputs.append(
            {
                "ts": ev.get("ts"),
                "channel": str(ev.get("kind") or ev.get("source") or "chronicle"),
                "text": (ev.get("layman") or ev.get("preview") or "")[:220],
                "api": "GET /api/v1/chronicle",
                "proof": ev.get("proof"),
            }
        )

    outputs.sort(key=lambda o: str(o.get("ts") or ""), reverse=True)
    outputs = outputs[:feed_limit]

    triad = build_fleet_triad()
    supervisor = build_supervisor_snapshot()
    fleet = build_fleet_snapshot()
    alive_triad = sum(1 for t in triad if t.get("alive"))
    research = build_research_glance()
    desk_health = desk_health_check(auto_heal=False)
    try:
        from mag.local_pulse import build_local_pulse

        local_pulse = build_local_pulse()
    except Exception as exc:
        local_pulse = {"ok": False, "error": str(exc)[:120]}

    try:
        from mag.local_scheduler import status as sched_status

        local_scheduler = sched_status()
    except Exception as exc:
        local_scheduler = {"ok": False, "error": str(exc)[:120]}

    try:
        from mag.unsloth_seat import build_unsloth_payload

        unsloth = build_unsloth_payload()
    except Exception as exc:
        unsloth = {"ok": False, "error": str(exc)[:120]}

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "headline": power.get("headline"),
        "stack_up": power.get("stack_up"),
        "power_off": power.get("power_off"),
        "integral_ok": nervous.get("integral_ok"),
        "triad": triad,
        "triad_alive": alive_triad,
        "supervisor": supervisor,
        "services": services,
        "agents": agents,
        "outputs": outputs,
        "fleet": fleet,
        "queue": fleet.get("queue"),
        "switchboard": power.get("switchboard_summary"),
        "desk_cursor": cur,
        "desk_trust": trust,
        "desk_health": desk_health,
        "local_pulse": local_pulse,
        "local_scheduler": local_scheduler,
        "unsloth": unsloth,
        "research": research,
        "chronicle_updated": chronicle.get("updated"),
        "poll_seconds": 10,
        "note": "All rows cite the REST endpoint or file path Mag read — not chat invention.",
    }
