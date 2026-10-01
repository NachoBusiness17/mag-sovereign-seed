# gpipes - Governor pipes: parallel fan-out of isolated sub-agents + merged collection.
# THE DELTA (2026-08-03, manifesto Phase 3 "multiprocessing.Queue for parallel task delegation"):
#   orchestrator.py already gives one-window supervision of isolated short-lived sub-agent
#   processes (spawn/kill/monitor/timeout/kill-tree). What it does NOT give is the Governor's
#   fan-out: spawn N workers on a shared goal-set, collect their results, and merge.
#   gpipes is that layer. No new process machinery - every worker IS an orchestrator task,
#   so pipes inherit crash containment, hard timeouts, and kill-tree semantics for free.
#
# Worker contract (mirrors orchestrator.spawn_task): each worker is a fresh process running
#   main.py agent --query "<goal>"  ->  stdout/stderr merged into its per-task log, task record
#   gets status + exit code. gpipes tracks the GROUP (a pipe record) and merges.
#
# Usage (via main.py):
#   python main.py gpipes fan "goal1" "goal2" ... [--provider deepseek] [--timeout 900] [--tag x]
#   python main.py gpipes collect <pipe_id> [--wait N] [--tail 15]
#   python main.py gpipes status <pipe_id>
#   python main.py gpipes kill <pipe_id>
#   python main.py gpipes list
from __future__ import annotations
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mag import orchestrator as orc  # reuse spawn/kill/monitor/log machinery (no reinvent)
from mag import headless

import os
PIPE_DIR = Path(os.environ.get("MAG_PIPES_DIR", str(ROOT / "memory" / "runs" / "gpipes")))
TRAIL = ROOT / "memory" / "runs" / "gpipes_trail.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    PIPE_DIR.mkdir(parents=True, exist_ok=True)


def _pipe_path(pipe_id: str) -> Path:
    return PIPE_DIR / (pipe_id + ".json")


def _load(pipe_id: str) -> dict[str, Any] | None:
    p = _pipe_path(pipe_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save(pipe: dict[str, Any]) -> None:
    _ensure_dirs()
    _pipe_path(pipe["pipe_id"]).write_text(
        json.dumps(pipe, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _trail(event: str, pipe_id: str, **meta: Any) -> None:
    _ensure_dirs()
    entry = {"timestamp": _now(), "event": event, "pipe_id": pipe_id, **meta}
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
def fan_out(goals: list[str], *, provider: str = "deepseek",
            model: str | None = None, timeout: int = orc.DEFAULT_TIMEOUT,
            tags: list[str] | None = None, agent_state: str | None = None) -> dict[str, Any]:
    """Spawn one orchestrator sub-agent per goal, in parallel. Returns the pipe record.

    If a custom agent_state (research-agent / janitor-agent / coding-agent / default) is given,
    the state's resource spec resolves the model for the whole fan-out (sub-agents inherit the
    state), and the state name is recorded on the pipe. Explicit `model` always wins over the
    state-resolved model.
    """
    goals = [g.strip() for g in goals if g and g.strip()]
    if not goals:
        return {"ok": False, "error": "no goals"}
    # Resolve a held custom agent state -> resource spec (model + shape) for this fan-out.
    state_spec: dict[str, Any] | None = None
    state_name = (agent_state or "").strip() or None
    if state_name:
        try:
            from mag.agent_state_router import pick as state_pick
            sr = state_pick(state_name, goals[0])
            if sr.get("ok"):
                state_spec = sr
                if model is None:
                    model = sr.get("model")
            else:
                return {"ok": False, "error": f"unknown agent state: {state_name}", "known": sr.get("known")}
        except Exception as e:
            return {"ok": False, "error": f"agent state resolve failed: {e}"}
    pipe_id = "p" + uuid.uuid4().hex[:10]
    tags = (tags or []) + [""] * max(0, len(goals) - len(tags or []))
    tasks: list[dict[str, Any]] = []
    # Respect runtime local-only toggle and check per-provider budget before spawning many workers.
    try:
        from mag.local_mode import is_local_only

        if is_local_only():
            provider = "ollama"
    except Exception:
        pass
    try:
        if provider and provider != "ollama":
            from models.quota import provider_budget

            b = provider_budget(provider)
            if not b.get("budget_ok"):
                return {"ok": False, "error": f"provider {provider} quota exhausted or not configured", "budget": b}
    except Exception:
        pass
    for i, goal in enumerate(goals):
        rec = orc.spawn_task(goal, provider=provider, model=model,
                             timeout=timeout, tag=(tags[i] or "gpipes"))
        tasks.append(rec)
    # Keep only successfully spawned workers in the pipe (a gated/failed spawn
    # returns ok=False with no task_id; tracking it would crash status/collect).
    spawned_goals = []
    spawned_task_ids = []
    spawned_tags = []
    spawned_recs = []
    for i, rec in enumerate(tasks):
        tid = rec.get("task_id")
        if tid:
            spawned_goals.append(goals[i])
            spawned_task_ids.append(tid)
            spawned_tags.append(tags[i] if i < len(tags) else "gpipes")
            spawned_recs.append(rec)
    if not spawned_task_ids:
        return {"ok": False, "error": "all workers failed to spawn", "tasks": tasks}
    pipe: dict[str, Any] = {
        "pipe_id": pipe_id,
        "created_at": _now(),
        "goals": spawned_goals,
        "task_ids": spawned_task_ids,
        "tags": spawned_tags,
        "provider": provider,
        "timeout_s": timeout,
        "agent_state": state_name,
        "status": "running",
        "spawn_failures": [t for t in tasks if not t.get("task_id")],
        "tasks": tasks,
    }
    _save(pipe)
    _spawn_supervisor(pipe_id, timeout + 30)  # detached; launcher exits now
    _trail("fan_out", pipe_id, n=len(goals), task_ids=pipe["task_ids"])
    return {"ok": True, "pipe": pipe}


def pipe_status(pipe_id: str) -> dict[str, Any] | None:
    """Pipe record with live per-task status refreshed from orchestrator task files.

    Reaps finished workers first: the gpipes launcher exits right after fan_out,
    killing the orchestrator's daemon monitor threads, so tasks whose process has
    exited would otherwise stay 'running' forever. Calling reap_completed() here
    means status/collect/supervise all surface terminal states promptly.
    """
    pipe = _load(pipe_id)
    if not pipe:
        return None
    try:
        orc.reap_completed()
    except Exception:
        pass  # reap is best-effort; never let it break status
    live = []
    task_ids = pipe.get("task_ids", [])
    tags = pipe.get("tags", [])
    for i, tid in enumerate(task_ids):
        if not tid:
            live.append({
                "task_id": None,
                "status": "failed",
                "exit_code": None,
                "duration_s": None,
                "tag": tags[i] if i < len(tags) else "",
            })
            continue
        t = orc.task_status(tid) or {}
        live.append({
            "task_id": tid,
            "status": t.get("status", "unknown"),
            "exit_code": t.get("exit_code"),
            "duration_s": t.get("duration_s"),
            "tag": t.get("tag", ""),
        })
    pipe["live"] = live
    statuses = [l["status"] for l in live]
    if statuses and all(s in orc.TERMINAL for s in statuses):
        pipe["status"] = "done" if all(s == "done" for s in statuses) else "partial"
    elif any(s == "running" for s in statuses):
        pipe["status"] = "running"
    _save(pipe)
    return pipe
def collect(pipe_id: str, *, wait: int = 0, tail: int = 15) -> dict[str, Any]:
    """Wait (seconds) for all workers to reach a terminal state, then merge results."""
    import time
    deadline = time.monotonic() + wait
    pipe = _load(pipe_id)
    if not pipe:
        return {"ok": False, "error": "no such pipe"}
    while True:
        st = pipe_status(pipe_id) or {}
        live = st.get("live", [])
        statuses = [l["status"] for l in live]
        if statuses and all(s in orc.TERMINAL for s in statuses):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    st = pipe_status(pipe_id) or {}
    live = st.get("live", [])
    results = []
    for goal, l in zip(st.get("goals", []), live):
        results.append({
            "goal": goal,
            "status": l.get("status"),
            "exit_code": l.get("exit_code"),
            "duration_s": l.get("duration_s"),
            "log_tail": orc.tail_log(l["task_id"], tail) if l.get("task_id") else "",
        })
    merged = {
        "n": len(results),
        "done": sum(1 for r in results if r["status"] == "done"),
        "failed": sum(1 for r in results if r["status"] in ("failed", "died")),
        "timeout": sum(1 for r in results if r["status"] == "timeout"),
        "killed": sum(1 for r in results if r["status"] == "killed"),
        "all_done": bool(results) and all(r["status"] == "done" for r in results),
        "exit_codes": [r["exit_code"] for r in results],
    }
    out = {"ok": True, "pipe_id": pipe_id, "status": st.get("status"),
           "merged": merged, "results": results}
    _trail("collect", pipe_id, status=st.get("status"), merged=merged)
    return out


def kill_pipe(pipe_id: str) -> dict[str, Any]:
    """Kill every running worker in the pipe (kill-tree per task, orchestrator semantics)."""
    pipe = _load(pipe_id)
    if not pipe:
        return {"ok": False, "error": "no such pipe"}
    killed = []
    for tid in pipe.get("task_ids", []):
        r = orc.kill_task(tid)
        killed.append({"task_id": tid, "ok": r.get("ok", False)})
    st = pipe_status(pipe_id)  # refresh record from live task states (was stale "running")
    _trail("kill", pipe_id, killed=killed, status=st.get("status"))
    return {"ok": True, "pipe_id": pipe_id, "killed": killed, "status": st.get("status")}


def list_pipes(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_dirs()
    out = []
    for p in sorted(PIPE_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            if rec.get("status") not in orc.TERMINAL:
                rec = pipe_status(rec["pipe_id"]) or rec  # honest refresh, not stale cache
            out.append(rec)
        except Exception:
            pass
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv else sys.argv[1:]
    if not args:
        print("usage: gpipes fan <goals...> | collect <id> [--wait N] [--tail N] | status <id> | kill <id> | list")
        return 2
    cmd = args[0]
    if cmd == "supervise":
        if len(args) < 2:
            print("need pipe_id")
            return 2
        timeout = 0
        if "--timeout" in args:
            try:
                timeout = int(args[args.index("--timeout") + 1])
            except (ValueError, IndexError):
                pass
        return supervise(args[1], timeout=timeout)
    if cmd == "list":
        for p in list_pipes():
            print("%s %-9s n=%d %s" % (p.get("pipe_id", "?"), p.get("status", "?"),
                                       len(p.get("task_ids", [])), p.get("created_at", "")))
        return 0
    if cmd in ("status", "collect", "kill"):
        if len(args) < 2:
            print("need pipe_id")
            return 2
        pid = args[1]
        if cmd == "status":
            st = pipe_status(pid)
            if not st:
                print("no such pipe")
                return 1
            print(json.dumps(st, indent=2, default=str))
            return 0
        if cmd == "kill":
            print(json.dumps(kill_pipe(pid), indent=2, default=str))
            return 0
        wait = 0
        tail = 15
        if "--wait" in args:
            try:
                wait = int(args[args.index("--wait") + 1])
            except (ValueError, IndexError):
                pass
        if "--tail" in args:
            try:
                tail = int(args[args.index("--tail") + 1])
            except (ValueError, IndexError):
                pass
        res = collect(pid, wait=wait, tail=tail)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("merged", {}).get("all_done") else 1
    if cmd == "fan":
        rest = args[1:]
        goals = []
        provider = "deepseek"
        model = None
        timeout = orc.DEFAULT_TIMEOUT
        tag = ""
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--provider" and i + 1 < len(rest):
                provider = rest[i + 1]; i += 2
            elif a == "--model" and i + 1 < len(rest):
                model = rest[i + 1]; i += 2
            elif a == "--timeout" and i + 1 < len(rest):
                try:
                    timeout = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            elif a == "--tag" and i + 1 < len(rest):
                tag = rest[i + 1]; i += 2
            else:
                goals.append(a); i += 1
        if not goals:
            print("need at least one goal")
            return 2
        res = fan_out(goals, provider=provider, model=model,
                      timeout=timeout, tags=[tag] * len(goals))
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    print("unknown gpipes command: " + cmd)
    return 2


def _spawn_supervisor(pipe_id: str, timeout: int) -> None:
    """Launch a standalone supervisor process for the pipe.

    THE FIX (2026-08-03): the launcher (`fan`) exits right after printing the pipe
    record, which kills its daemon monitor threads -> workers would orphan and the
    per-worker timeout would never fire. A detached process owns supervision:
    polls pipe_status, kills the whole pipe when the deadline passes.
    """
    import subprocess
    cmd = [headless.PYTHON, str(ROOT / "mag" / "gpipes.py"), "supervise",
           pipe_id, "--timeout", str(int(timeout))]
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=str(ROOT), creationflags=flags)
    except Exception:
        pass  # supervision is best-effort; collect still works


def supervise(pipe_id: str, *, timeout: int = 0) -> int:
    """Poll a pipe until terminal, or kill it when timeout (seconds) passes."""
    import time
    start = time.monotonic()
    _ensure_dirs()
    while True:
        st = pipe_status(pipe_id)
        if st is None:
            return 2  # pipe record vanished
        live = st.get("live", [])
        statuses = [l["status"] for l in live]
        if statuses and all(s in orc.TERMINAL for s in statuses):
            return 0
        if timeout and time.monotonic() - start > timeout:
            kill_pipe(pipe_id)
            return 1
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
