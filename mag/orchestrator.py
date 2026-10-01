# Orchestrator - spawn isolated sub-agents per task, terminate on completion.
# THE PROBLEM (operator, 2026-08-03): the agent router does everything in one
# window/process. One crash in a tool call, a runaway loop, or a hung provider
# kills the whole session. Crashes eventually, always.
# THE FIX: one orchestration window supervises short-lived sub-agent processes.
# Each task is a fresh Python process running `main.py agent --query "<goal>"`
# in one-shot mode. The orchestrator:
#   spawn   - write task spec, Popen the child, return task_id (window stays up)
#   monitor - finalize record on child exit (done/failed) or stall/timeout (kill)
#   reap    - clean stale records whose pid is dead
#   kill    - terminate a running task (process tree on Windows)
#   steer / pause / continue - live knot commands via the task's pigeonhole
#              mailbox (memory/mail/<task_id>/inbox.txt). stdin is DEVNULL in
#              sub-agents, so the KNOT is the channel - not a pipe, not a timer.
# Crash containment: a sub-agent crash kills ONLY that process. The orchestrator
# window survives, records the failure, and the operator can retry or escalate.
# Crash RECOGNITION is live: the child writes heartbeat beads + status.json into
# its mailbox; staleness detection nudges (!steer) before ever killing, and the
# hard timeout is only the final backstop. The seat's own crash recognizers
# (collapse detector, empty-response retry, seat-crash-guard) now surface to the
# supervisor immediately via status.json phase (collapse_stop/empty_stop/crashed)
# instead of being invisible until exit.
# Frontier fidelity: mirrors Claude Code Task / Anthropic agent-SDK subagents -
# explicit input contract (goal string), isolated tool process, result capture
# (exit code + log), hard timeout, terminate on completion, parent survival.
# Usage (via main.py):
#   python main.py orchestrator run "<goal>" [--provider deepseek] [--timeout 900] [--tag label] [--wait]
#   python main.py orchestrator list
#   python main.py orchestrator status <id> [--tail 20]
#   python main.py orchestrator steer <id> "<context>"
#   python main.py orchestrator pause <id> | continue <id>
#   python main.py orchestrator watch <id>   (poll heartbeat freshness)
#   python main.py orchestrator kill <id>
#   python main.py orchestrator reap
#   python main.py orchestrator self-test
#   python main.py orchestrator queue add "<goal>" [--provider X] [--timeout N] [--tag L]
#   python main.py orchestrator queue list | status
#   python main.py orchestrator drain [--once]   (auto-advance through the queue)
from __future__ import annotations
import json
import os
import subprocess
import sys
from mag import headless
from mag.write_strip import READ_ONLY_ARG
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def dim(s: str) -> str:
    """Minimal dim fallback (agent_cli has the ANSI variant)."""
    if sys.stdout.isatty():
        return "\033[2m" + s + "\033[0m"
    return s
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_DIR = ROOT / "memory" / "runs" / "orchestrator" / "tasks"
QUEUE_DIR = ROOT / "memory" / "runs" / "orchestrator" / "queue"
LOG_DIR = ROOT / "logs" / "orchestrator"
TRAIL = ROOT / "memory" / "runs" / "orchestrator_trail.jsonl"
DEFAULT_TIMEOUT = 900  # seconds — fallback if temperature stacks unavailable
IMPROVE_TIMEOUT = 420  # shorter backstop for [improve] loops (7 min)
EXTERNAL_STALE_S = 300  # external/desktop seats without pid — reap after stale heartbeat
EXTERNAL_NO_REAP_SEATS = {"zcode", "notion", "autoclaw"}  # mailbox seats: human-paced GUI/mailbox work, closed via `done`

TERMINAL = {"done", "failed", "timeout", "stalled", "killed", "died"}

_TASK_LIST_CACHE: tuple[str, float, list[dict[str, Any]]] | None = None
_TASK_LIST_CACHE_LOCK = threading.Lock()
_TASK_LIST_CACHE_TTL_S = 1.0


def timeout_for_goal(goal: str, *, tag: str = "", timeout: int | None = None) -> int:
    """Pick spawn timeout from temperature stacks (adjustable YAML) + size boost.

    Explicit timeout always wins. Else configs/temperature_stacks.yaml heat band.
    """
    if timeout is not None and int(timeout) > 0 and int(timeout) != DEFAULT_TIMEOUT:
        return int(timeout)
    try:
        from mag.temperature_stack import timeout_for_goal as stack_timeout

        return int(stack_timeout(goal, tag=tag, timeout=None, size_hint=len(goal or "")))
    except Exception:
        pass
    g = (goal or "").lower()
    t = (tag or "").lower()
    if "[improve]" in g or t.startswith("improve"):
        return IMPROVE_TIMEOUT
    return DEFAULT_TIMEOUT


def _is_external_task(task: dict[str, Any]) -> bool:
    src = str(task.get("source") or "")
    if src in ("external", "desktop", "cursor", "cloud", "seat_guard", "launcher"):
        return True
    tid = str(task.get("task_id") or "")
    return tid.startswith("ext-") or tid.startswith("seat-")


def register_external(
    goal: str = "",
    *,
    seat: str = "cursor",
    platform: str = "cursor",
    mode: str = "interactive",
    task_id: str | None = None,
    pid: int | None = None,
    tag: str = "",
    parent: str = "desktop",
) -> dict[str, Any]:
    """Register a desktop/cloud seat — visible in list_tasks_live + switchboard steer."""
    _ensure_dirs()
    task_id = (task_id or "").strip() or ("ext-" + uuid.uuid4().hex[:10])
    task: dict[str, Any] = {
        "task_id": task_id,
        "tag": tag or f"{seat}-external",
        "status": "running",
        "source": "external",
        "seat": seat,
        "platform": platform,
        "mode": mode,
        "parent": parent,
        "goal": (goal or "")[:500],
        "cmd": [],
        "created_at": _now(),
        "started_at": _now(),
        "ended_at": None,
        "exit_code": None,
        "timeout_s": None,
        "log": "",
        "detail": f"registered:{parent}",
        "pid": pid,
    }
    _save(task)
    _trail("register_external", task_id, seat=seat, mode=mode, parent=parent)
    ph = _ph()
    if ph is not None:
        try:
            ph.heartbeat(task_id, seat=seat, phase="registered", source=parent)
            ph.write_status(task_id, phase="registered", seat=seat, goal=task["goal"][:200])
        except Exception:
            pass
    task["ok"] = True
    return task


def touch_external(task_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update last_seen on an external task record."""
    task = _load(task_id)
    if not task:
        return None
    task["last_seen_at"] = _now()
    for k, v in fields.items():
        if v is not None and k in ("phase", "goal", "seat", "pid", "detail"):
            task[k] = v
    _save(task)
    return task


def finalize_external(task_id: str, *, status: str = "done", detail: str = "") -> dict[str, Any]:
    """Terminal state for external seats (no process kill)."""
    task = _load(task_id)
    if not task:
        return {"ok": False, "error": "no such task", "task_id": task_id}
    if task.get("status") in TERMINAL:
        return {"ok": True, "task": task, "note": "already terminal"}
    task = _finalize(task_id, status, detail=detail or f"external:{status}") or task
    return {"ok": True, "task": task}


def list_external_tasks(*, limit: int = 50) -> list[dict[str, Any]]:
    """Running/ recent external task records enriched with heartbeat."""
    out: list[dict[str, Any]] = []
    ph = _ph()
    for t in list_tasks(limit=limit):
        if not _is_external_task(t):
            continue
        tid = str(t.get("task_id") or "")
        if ph is not None and t.get("status") in ("running", "queued"):
            try:
                t["heartbeat_age_s"] = ph.staleness_s(tid)
                t["alive"] = ph.alive(tid)
                st = ph.read_status(tid)
                if st:
                    t["phase"] = st.get("phase")
            except Exception:
                pass
        t["peer_id"] = f"ext:{tid}"
        t["why"] = [f"external:{t.get('parent', 'desktop')}"]
        out.append(t)
    return out


def _ph() -> Any:
    """Lazy import of the pigeonhole mailbox (knot channel)."""
    try:
        from mag import pigeonhole as ph
        return ph
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _task_path(task_id: str) -> Path:
    return TASK_DIR / (task_id + ".json")


def _active_task_dir() -> Path:
    """Small durable index containing only non-terminal task ids."""
    return TASK_DIR / ".active"


def _active_marker(task_id: str) -> Path:
    return _active_task_dir() / (task_id + ".marker")


def _rebuild_active_index() -> None:
    """Build the active index once for legacy task records.

    Older versions stored only one JSON file per task, so the first call has to
    scan that history once.  The ready sentinel makes that migration one-time;
    subsequent queue passes read only marker files for live tasks.
    """
    active = _active_task_dir()
    active.mkdir(parents=True, exist_ok=True)
    ready = active / ".ready"
    if ready.is_file():
        return
    for p in TASK_DIR.glob("*.json"):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(row, dict) and row.get("status") not in TERMINAL:
            task_id = str(row.get("task_id") or p.stem)
            try:
                _active_marker(task_id).touch(exist_ok=True)
            except OSError:
                pass
    try:
        ready.write_text(_now(), encoding="utf-8")
    except OSError:
        pass


def _active_task_records() -> list[dict[str, Any]]:
    """Load current task records through the active index, not task history."""
    _active_task_dir().mkdir(parents=True, exist_ok=True)
    if not (_active_task_dir() / ".ready").is_file():
        _rebuild_active_index()
    out: list[dict[str, Any]] = []
    for marker in _active_task_dir().glob("*.marker"):
        task_id = marker.name[:-len(".marker")]
        task = _load(task_id)
        if not task or task.get("status") in TERMINAL:
            try:
                marker.unlink()
            except OSError:
                pass
            continue
        out.append(task)
    return out


def _sync_active_marker(task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or "")
    if not task_id:
        return
    marker = _active_marker(task_id)
    try:
        if task.get("status") in TERMINAL:
            marker.unlink(missing_ok=True)
        else:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch(exist_ok=True)
    except OSError:
        # The JSON task record remains authoritative if the tiny acceleration
        # index cannot be updated (read-only test fixtures, shutdown races).
        pass


def _load(task_id: str) -> dict[str, Any] | None:
    p = _task_path(task_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save(task: dict[str, Any]) -> None:
    global _TASK_LIST_CACHE
    _ensure_dirs()
    task["updated_at"] = _now()
    target = _task_path(task["task_id"])
    temp = target.with_name(
        f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        # Readers never observe a truncated JSON record, and a concurrent
        # status scan can keep reading the previous complete version while the
        # replacement is prepared.
        temp.write_text(
            json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp, target)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    with _TASK_LIST_CACHE_LOCK:
        _TASK_LIST_CACHE = None
    _sync_active_marker(task)


def _goal_from_cmd(cmd: list[str] | None) -> str:
    cmd = cmd or []
    for flag in ("--query", "--goal"):
        if flag not in cmd:
            continue
        i = cmd.index(flag)
        if i + 1 < len(cmd):
            return str(cmd[i + 1])[:240]
    return ""


def _provider_from_cmd(cmd: list[str] | None) -> str:
    cmd = cmd or []
    if "--provider" in cmd:
        i = cmd.index("--provider")
        if i + 1 < len(cmd):
            return str(cmd[i + 1])
    return "deepseek"


def _emit_task_lifecycle(phase: str, task_id: str, **extra: Any) -> None:
    """Training hook — spawn/terminal edges for improve + seat posterior."""
    try:
        from mag.training_events import emit

        task = _load(task_id) or {}
        cmd = task.get("cmd") or []
        emit(
            "task_lifecycle",
            join={"task_id": task_id},
            input_data={
                "goal": (task.get("goal") or _goal_from_cmd(cmd))[:200],
                "provider": task.get("provider") or _provider_from_cmd(cmd),
                "tag": task.get("tag") or "",
            },
            action={"phase": phase, **extra},
            outcome={
                "status": task.get("status"),
                "exit_code": task.get("exit_code"),
                "duration_s": task.get("duration_s"),
            },
            pattern_tags=[f"orc_{phase}"],
        )
    except Exception:
        pass


def _trail_path() -> Path:
    """B2-401 (2026-09-26): MAG_ORCHESTRATOR_TRAIL overrides the sink, else
    the production trail. Same shape as the MAG_SEAT_CRASH_LOG seam (B2-86)
    and the MAG_GAPS_LOG seam (B2-79): tests point the writer at tmp instead
    of appending q-test queue-add rows to the production trail (571 q-test
    rows on disk at fix time). No env set = same path."""
    env = os.environ.get("MAG_ORCHESTRATOR_TRAIL")
    return Path(env) if env else TRAIL


def _trail(event: str, task_id: str, **meta: Any) -> None:
    _ensure_dirs()
    entry = {"timestamp": _now(), "event": event, "task_id": task_id, **meta}
    path = _trail_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _kill_tree(pid: int) -> None:
    """Terminate the process and its children (Windows process tree)."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
    else:
        try:
            os.kill(pid, 9)
        except (ProcessLookupError, PermissionError):
            pass


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    # Prefer psutil on Windows: os.kill(pid, 0) is unreliable there (returns
    # True for recycled/dead pids), which left zombies stuck in "running".
    try:
        import psutil

        return psutil.pid_exists(pid)
    except Exception:
        pass
    if sys.platform == "win32":
        # psutil-free liveness: tasklist filter is authoritative. os.kill(pid, 0)
        # is NOT a probe on Windows - sig 0 means TerminateProcess, and it can
        # return success on already-dead pids whose handle is still open, so a
        # supervisor would never reap zombies. (Found 2026-08-03: env without
        # psutil -> reap_stale/kill verification silently broken.)
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=15,
            )
            return str(pid) in (r.stdout or "")
        except Exception:
            pass
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _finalize(task_id: str, status: str, exit_code: int | None = None,
              detail: str = "", killed: bool = False) -> dict[str, Any] | None:
    task = _load(task_id)
    if not task:
        return None
    if task.get("status") in TERMINAL:
        return task
    task["status"] = status
    task["exit_code"] = exit_code
    task["detail"] = detail
    task["ended_at"] = _now()
    if task.get("started_at"):
        try:
            s = datetime.fromisoformat(task["started_at"])
            e = datetime.fromisoformat(task["ended_at"])
            task["duration_s"] = round((e - s).total_seconds(), 1)
        except Exception:
            pass
    _save(task)
    _trail(status, task_id, exit_code=exit_code, detail=detail, killed=killed)
    _emit_task_lifecycle(status, task_id, killed=killed, detail=(detail or "")[:120])
    try:
        from mag.tripartite_boot import weave_terminal

        weave_terminal(task_id=task_id, status=status, detail=detail)
    except Exception:
        pass
    return task


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    # own process group so taskkill /T can reap children; CREATE_NO_WINDOW so
    # queued sub-agents never pop a console window on the desktop.
    return (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def _spawn_cmd(cmd: list[str], *, task_id: str, timeout: int,
               tag: str = "") -> dict[str, Any]:
    """Popen a child command and supervise it in a daemon thread."""
    _ensure_dirs()
    log_path = LOG_DIR / (task_id + ".out.log")
    log_fh = log_path.open("a", encoding="utf-8", errors="replace")
    log_fh.write("--- %s spawn: %s\n" % (_now(), " ".join(cmd)))
    log_fh.flush()

    env = headless._spawn_env(os.environ)  # PYTHONPATH = project root + venv site-packages
    env["MAG_AGENT_SESSION"] = "orc-" + task_id
    env["MAG_TASK_ID"] = task_id  # pigeonhole mailbox: knot channel for the seat
    env["NO_COLOR"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")

    task: dict[str, Any] = {
        "task_id": task_id,
        "tag": tag,
        "status": "running",
        "cmd": cmd,
        "provider": _provider_from_cmd(cmd),  # top-level stamp: mix queries must not re-parse cmd
        "goal": _goal_from_cmd(cmd),  # persisted so same-goal dedupe works
        "created_at": _now(),
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "timeout_s": timeout,
        "log": str(log_path),
        "detail": "",
    }
    _save(task)

    try:
        proc = subprocess.Popen(
            cmd, stdout=log_fh, stderr=subprocess.STDOUT, env=env,
            cwd=str(ROOT), creationflags=_creation_flags(),
            stdin=subprocess.DEVNULL,  # sub-agents never read stdin; else they hang on input()
        )
    except Exception as e:
        log_fh.close()
        _finalize(task_id, "failed", detail="spawn error: " + str(e))
        return _load(task_id) or task

    task = _load(task_id) or task
    task["pid"] = proc.pid
    task["started_at"] = _now()
    _save(task)
    _trail("spawn", task_id, pid=proc.pid, timeout_s=timeout)
    _emit_task_lifecycle("spawn", task_id, pid=proc.pid, timeout_s=timeout)
    try:
        from mag.tripartite_boot import weave_spawn

        weave_spawn(
            task_id=task_id,
            goal=_goal_from_cmd(cmd),
            provider=_provider_from_cmd(cmd),
            pid=proc.pid,
            tag=tag,
        )
    except Exception:
        pass

    def _monitor() -> None:
        """Supervise: exit -> finalize; stall -> nudge (!steer) then kill;
        hard timeout remains the last-resort backstop only."""
        started = time.time()
        stall_polls = 0
        nudged = False
        ph = _ph()
        while True:
            rc = proc.poll()
            if rc is not None:
                log_fh.close()
                _finalize(task_id, "done" if rc == 0 else "failed",
                          exit_code=rc, detail="exit" if rc == 0 else "non-zero exit %s" % rc)
                return
            elapsed = time.time() - started
            if elapsed > timeout:
                _kill_tree(proc.pid)
                log_fh.close()
                _finalize(task_id, "timeout", exit_code=None,
                          detail="exceeded %ss" % timeout, killed=True)
                return
            # Live crash/stall recognition via the knot: heartbeat staleness.
            # A healthy agent writes a bead every 15s. No bead -> nudge once
            # through the mailbox (!steer re-anchor); if it stays silent, kill
            # as "stalled" instead of burning the whole timeout.
            age = None
            stall_after = None
            if ph is not None:
                try:
                    age = ph.staleness_s(task_id)
                    stall_after = ph.STALL_AFTER_S
                except Exception:
                    age = None
            if age is None or stall_after is None or age < stall_after:
                stall_polls = 0  # healthy (or still starting): reset the counter
            else:
                stall_polls += 1
                if stall_polls == 2 and not nudged:
                    nudged = True
                    try:
                        from mag import supervisor as _sup
                        ph.post_steer(task_id, _sup.stall_nudge_text(task_id, age))
                        _trail("stall-nudge", task_id, age_s=age, receipts=True)
                        print(dim("  [orchestrator] stall-nudge %s (no heartbeat %ss)" % (task_id, age)), flush=True)
                    except Exception:
                        pass
                elif stall_polls >= 6:  # ~30s after the nudge threshold
                    defer_kill = False
                    try:
                        from mag.run_worth import evaluate_task_hung

                        hung_eval = evaluate_task_hung(task_id)
                        defer_kill = bool(hung_eval.get("defer_kill"))
                        if hung_eval.get("hung"):
                            defer_kill = False
                    except Exception:
                        hung_eval = {}
                    if defer_kill and stall_polls < 10:
                        stall_polls = 4  # one grace cycle when worth uncertain
                        _trail(
                            "stall-defer-worth",
                            task_id,
                            age_s=age,
                            verdict=(hung_eval or {}).get("verdict"),
                        )
                    else:
                        _kill_tree(proc.pid)
                        log_fh.close()
                        detail = "no heartbeat for %ss" % age
                        if hung_eval.get("hung"):
                            detail = "hung: %s" % (hung_eval.get("reason") or detail)
                        _finalize(task_id, "stalled", exit_code=None,
                                  detail=detail, killed=True)
                        return
            time.sleep(5.0)

    threading.Thread(target=_monitor, daemon=True).start()
    return _load(task_id) or task
def _running_tasks() -> list[dict[str, Any]]:
    """All non-terminal task records (running/stalled/starting)."""
    _ensure_dirs()
    return _active_task_records()


def spawn_task(goal: str, *, provider: str = "deepseek", model: str | None = None,
               timeout: int = DEFAULT_TIMEOUT, tag: str = "",
               require_build: str | None = None,
               read_only: bool = True) -> dict[str, Any]:
    """Spawn a one-shot sub-agent for a goal. Returns the task record (async).

    Same-goal dedupe (2026-08-03): if a non-terminal task with the SAME goal
    already exists, refuse to spawn a duplicate and return the existing task
    instead. Prevents the 8-identical-smoke-spawns pattern from session mining.

    read_only=True is the fan-out write-strip default (MICKEY-17 owed chore,
    discharged 2026-09-26 from lanes write-delegation#0 +
    orchestrator-war-stories#0): the child's tool schema is compiled to
    read-only before its first model call, so it contributes intelligence and
    returns any proposed write as data in its stdout log. A spawn that MUST
    write (rare, explicit) passes read_only=False — that call site owns the
    exception, visible in the task record.
    """
    goal = goal.strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}
    from mag.factory_gate import check_frozen_build

    build_gate = check_frozen_build(goal, require_build=require_build)
    if not build_gate.get("ok"):
        return {"ok": False, "error": build_gate.get("reason"), "factory_gate": build_gate}

    if goal.lower().startswith("[steward]"):
        try:
            from mag.steward import execute_steward_goal

            res = execute_steward_goal(goal, dry=False)
            tid = "t-steward-" + uuid.uuid4().hex[:8]
            status = "done" if res.get("ok") else "failed"
            rec: dict[str, Any] = {
                "ok": res.get("ok", False),
                "task_id": tid,
                "goal": goal,
                "status": status,
                "provider": "ollama",
                "tag": tag or "steward",
                "detail": str(res.get("path") or res.get("reason") or res.get("error") or "")[:300],
                "steward_result": res,
                "created_at": _now(),
                "ended_at": _now(),
            }
            _ensure_dirs()
            _save(rec)
            _trail("steward-inline", tid, goal=goal[:120], ok=res.get("ok"))
            return rec
        except Exception as exc:
            return {"ok": False, "error": f"steward: {exc}"}

    # Token-chain experiment: DeepSeek plans → local exec (not a long agent tool-loop)
    gl = goal.lower().strip()
    if tag == "token-chain" or gl.startswith("token-chain:") or gl.startswith("[token-chain]"):
        try:
            from mag.token_chain import run_token_chain

            g = goal
            for prefix in ("token-chain:", "[token-chain]", "TOKEN_CHAIN:"):
                if g.lower().startswith(prefix.lower()):
                    g = g[len(prefix) :].strip()
                    break
            res = run_token_chain(goal=g or None, dry=False, live=True, planner="deepseek")
            tid = "t-tchain-" + uuid.uuid4().hex[:8]
            ok = bool(res.get("ok") or (res.get("execution") or {}).get("ok"))
            rec_tc: dict[str, Any] = {
                "ok": ok,
                "task_id": tid,
                "goal": goal,
                "status": "done" if ok else "failed",
                "provider": "deepseek+local",
                "tag": tag or "token-chain",
                "detail": str((res.get("token_thesis") or {}))[:300],
                "token_chain": {
                    "frontier_tokens": (res.get("token_thesis") or {}).get("frontier_tokens"),
                    "artifact": res.get("artifact"),
                    "execution_ok": (res.get("execution") or {}).get("ok"),
                },
                "created_at": _now(),
                "ended_at": _now(),
            }
            _ensure_dirs()
            _save(rec_tc)
            _trail("token-chain-inline", tid, goal=goal[:120], ok=ok)
            return rec_tc
        except Exception as exc:
            return {"ok": False, "error": f"token-chain: {exc}"}

    # FRONTIER-ADVICE (2026-08-12): a drainable task that spends the scarce frontier allowance on a
    # code-planning / frontier-research ask and steers the real seat headless — the operator's "use
    # it for code advice" made a tool the drainer runs, never a hand-run.
    if goal.lower().startswith("[frontier-advice]"):
        try:
            from mag.frontier_advisor import execute_goal

            res = execute_goal(goal, dry=False)
            tid = "t-fadvice-" + uuid.uuid4().hex[:8]
            ok = bool(res.get("ok"))
            rec_fa: dict[str, Any] = {
                "ok": ok,
                "task_id": tid,
                "goal": goal,
                "status": "done" if ok else "failed",
                "provider": res.get("surface", "frontier"),
                "tag": tag or "frontier-advice",
                "detail": (res.get("answer") or res.get("error") or "")[:300],
                "report": res.get("report"),
                "created_at": _now(),
                "ended_at": _now(),
            }
            _ensure_dirs()
            _save(rec_fa)
            _trail("frontier-advice-inline", tid, goal=goal[:120], ok=ok)
            return rec_fa
        except Exception as exc:
            return {"ok": False, "error": f"frontier-advice: {exc}"}

    # SEAT-STEER (2026-08-12): the architecture path for live seat actions (send a message into
    # ChatGPT/grok/deepseek) — the agent enqueues a `[seat-steer]` task file and the DRAINER runs
    # send() headless. Never a shell.
    if goal.lower().startswith("[seat-steer]"):
        try:
            from mag.seat_steer import execute_goal as ss_execute

            res = ss_execute(goal)
            tid = "t-seat-" + uuid.uuid4().hex[:8]
            ok = bool(res.get("ok"))
            rec_ss: dict[str, Any] = {
                "ok": ok,
                "task_id": tid,
                "goal": goal,
                "status": "done" if ok else "failed",
                "provider": res.get("surface", "seat"),
                "tag": tag or "seat-steer",
                "detail": (res.get("answer") or res.get("error") or "")[:300],
                "report": res.get("report"),
                "created_at": _now(),
                "ended_at": _now(),
            }
            _ensure_dirs()
            _save(rec_ss)
            _trail("seat-steer-inline", tid, goal=goal[:120], ok=ok)
            return rec_ss
        except Exception as exc:
            return {"ok": False, "error": f"seat-steer: {exc}"}

    # SALON (2026-08-13): summon the COUNCIL — all three frontier seats (chatgpt + supergrok +
    # v4-pro) witness the same question and salon it into ONE new version. SELF-STEAL: mirrors the
    # existing [frontier-advice]/[seat-steer] drained-handler pattern (frontier_advisor). The drainer
    # runs frontier_salon.salon_project() headless; honest if a witness is unreachable.
    if goal.lower().startswith("[salon]"):
        try:
            from mag.frontier_salon import salon_project as fs_project

            res = fs_project()
            tid = "t-salon-" + uuid.uuid4().hex[:8]
            ok = bool(res.get("ok"))
            rec_sal: dict[str, Any] = {
                "ok": ok,
                "task_id": tid,
                "goal": goal,
                "status": "done" if ok else "failed",
                "provider": "salon",
                "tag": tag or "salon",
                "detail": (res.get("consensus_invariant") or res.get("error") or "")[:300],
                "created_at": _now(),
                "ended_at": _now(),
            }
            _ensure_dirs()
            _save(rec_sal)
            _trail("salon-inline", tid, goal=goal[:120], ok=ok)
            return rec_sal
        except Exception as exc:
            return {"ok": False, "error": f"salon: {exc}"}

    timeout = timeout_for_goal(goal, tag=tag, timeout=timeout)
    # Respect runtime local-only toggle (env or dashboard-controlled file).
    try:
        from mag.local_mode import is_local_only

        if is_local_only():
            provider = "ollama"
    except Exception:
        pass

    # Quota gating: prevent accidental remote calls when provider budget exhausted.
    try:
        if provider and provider != "ollama":
            from models.quota import provider_budget

            b = provider_budget(provider)
            if not b.get("budget_ok"):
                return {"ok": False, "error": f"provider {provider} quota exhausted or not configured", "budget": b}
    except Exception:
        # best-effort: if quota check fails, continue to spawn
        pass
    for t in _running_tasks():
        if t.get("goal") == goal:
            return {
                "ok": False,
                "error": f"duplicate goal already running: {t['task_id']}",
                "existing": t["task_id"],
                "status": t.get("status"),
            }
    task_id = "t" + uuid.uuid4().hex[:10]
    try:
        from mag.autorun_common import refresh_context_for_goal

        refresh_context_for_goal(goal)
    except Exception:
        pass
    cmd = [headless.PYTHON, str(ROOT / "main.py"), "agent", "--query", goal,
           "--provider", provider]
    if read_only:
        # Fan-out write-strip (MICKEY-17 owed chore): only the agent-CLI seat
        # carries a tool schema, so only it takes the flag (the compact
        # research_worker below has no tools and is read-only by construction).
        cmd += [READ_ONLY_ARG]
    if tag == "self-steal-research":
        # Research receipts do not need the full interactive tool seat.  The
        # compact worker avoids loading the entire tool schema/REPL path on a
        # CPU Ollama lane and exits cleanly after one bounded answer.
        cmd = [headless.PYTHON, "-m", "mag.research_worker", "--goal", goal,
               "--provider", provider]
    if build_gate.get("required"):
        cmd += ["--tier", str(build_gate.get("tier") or "T1")]
    if model:
        cmd += ["--model", model]
    rec = _spawn_cmd(cmd, task_id=task_id, timeout=timeout, tag=tag)
    rec["ok"] = True
    rec["goal"] = goal
    rec["read_only"] = bool(read_only)
    return rec


# ---------------------------------------------------------------------------
# Task queue: enqueue goals, drain them sequentially (auto-advance).
# The operator's recurring ask: "the orchestrator didn't move onto the next
# task automatically." spawn_task() is one-shot (spawn + return). This queue
# gives a list of goals that a drain loop processes one at a time, spawning
# the next queued goal the moment the current one reaches a terminal state.
# ---------------------------------------------------------------------------
QUEUE_TERMINAL = {"done", "failed", "timeout", "stalled", "killed", "died"}

# Separate de-facto queues by tier; the single drainer drains in this rank order
# (mission -> research -> maintenance -> filler) so auto-generated busywork never
# crowds out real work. Operated by the ghost via the one drainer.
TIER_RANK = {"mission": 0, "research": 1, "maintenance": 2, "filler": 3}


def _auto_tier(tag: str, goal: str) -> str:
    """Infer a queue tier from the goal/tag so filler self-de-prioritizes."""
    g = (goal or "").lower()
    t = (tag or "").lower()
    if ("research" in t or "research-pack" in g or "grok batch" in g or "code-as-law" in g
            or "context-growth" in g or "self-steal-research" in t):
        return "research"
    if ("janitor" in t or "cleanup" in t or "orphan" in t or "warning" in t or "docker" in t):
        return "maintenance"
    if ("verkle" in g or "summarize-session" in g or "smoke" in g or "milestone" in g
            or "progress in" in g or "scut-retry" in t):
        return "filler"
    return "mission"


def _queue_path(queue_id: str) -> Path:
    return QUEUE_DIR / (queue_id + ".json")


def _queue_load(queue_id: str) -> dict[str, Any] | None:
    p = _queue_path(queue_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _queue_save(q: dict[str, Any]) -> None:
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    _queue_path(q["queue_id"]).write_text(
        json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def queue_has_goal(goal: str) -> bool:
    """Re-export: true if goal already queued/running (steward + autorun)."""
    from mag.governor_autorun import queue_has_goal as _qhg

    return _qhg(goal)


def enqueue(goal: str, *, provider: str = "ollama", model: str | None = None,
            timeout: int = DEFAULT_TIMEOUT, tag: str = "", priority: int = 0,
            tier: str | None = None, require_build: str | None = None,
            heavy: bool | None = None, schedule_policy: str | None = None) -> dict[str, Any]:
    """Add a goal to the queue. Returns the queue entry (not yet spawned)."""
    goal = goal.strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}
    from mag.factory_gate import check_frozen_build

    build_gate = check_frozen_build(goal, require_build=require_build)
    if not build_gate.get("ok"):
        return {"ok": False, "error": build_gate.get("reason"), "factory_gate": build_gate}
    try:
        from mag.loop_audit import _goal_key

        norm = _goal_key(goal)
        for q in list_queue(limit=80):
            if q.get("status") not in ("queued", "running"):
                continue
            if _goal_key(str(q.get("goal") or "")) == norm:
                return {
                    "ok": False,
                    "error": "duplicate goal already queued",
                    "existing_queue_id": q.get("queue_id"),
                    "goal": goal[:120],
                }
    except Exception:
        pass
    timeout = timeout_for_goal(goal, tag=tag, timeout=timeout)
    q = {
        "queue_id": "q" + uuid.uuid4().hex[:10],
        "goal": goal,
        "provider": provider,
        "model": model,
        "timeout": timeout,
        "tag": tag,
        "build_spec": build_gate.get("spec_path"),
        "created_at": _now(),
        "status": "queued",   # queued -> running -> done/failed
        "priority": max(0, int(priority)),
        "tier": (tier if tier in TIER_RANK else _auto_tier(tag, goal)),
        "task_id": None,
        "detail": "",
    }
    try:
        from mag.off_hours import decorate
        decorate(q, heavy=heavy, schedule_policy=schedule_policy)
    except Exception:
        q["compute_class"] = "heavy" if heavy else "normal"
        q["heavy"] = bool(heavy)
        q["schedule_policy"] = schedule_policy or ("off_hours" if heavy else "anytime")
    try:
        from mag.cost_ledger import task_estimate

        q["task_estimate"] = task_estimate(goal, provider=provider, model=model)
    except Exception:
        pass
    _queue_save(q)
    _trail("queue-add", q["queue_id"], goal=goal[:120], tag=tag)
    q["ok"] = True
    return q


def purge_failed_queue(*, also_killed: bool = True) -> dict[str, Any]:
    """Archive failed (and optional killed) queue rows under purged/."""
    import shutil
    from datetime import datetime, timezone

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arch = ROOT / "memory" / "runs" / "orchestrator" / "purged" / f"purge-failed-{stamp}"
    arch.mkdir(parents=True, exist_ok=True)
    moved = 0
    statuses = {"failed", "killed"} if also_killed else {"failed"}
    for p in list(QUEUE_DIR.glob("*.json")):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("status") not in statuses:
            continue
        try:
            shutil.move(str(p), str(arch / p.name))
            moved += 1
        except OSError:
            pass
    _trail("queue-purge-failed", "batch", moved=moved, archive=str(arch))
    return {"ok": True, "moved": moved, "archive": str(arch)}


def list_queue(limit: int = 100) -> list[dict[str, Any]]:
    """All queue entries, newest first, with live task linkage."""
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(QUEUE_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Link live task status so the queue view shows real progress.
        if q.get("task_id"):
            t = _load(q["task_id"])
            if t:
                q["task_status"] = t.get("status")
                q["task_detail"] = t.get("detail")
        out.append(q)
    return out


def promote_queue(queue_id: str, priority: int = 1) -> dict[str, Any]:
    """Raise a queued entry's priority so _next_queued picks it sooner.

    Priority sorts DESC (higher first), then FIFO by created_at within the same
    priority. This replaces the old created_at=2000 promote hack.
    """
    q = _queue_load(queue_id)
    if not q:
        return {"ok": False, "error": f"no queue entry {queue_id}"}
    if q.get("status") != "queued":
        return {"ok": False, "error": f"entry {queue_id} is {q.get('status')}, not queued"}
    q["priority"] = max(0, int(priority))
    q["detail"] = f"operator-promoted priority={priority}"
    _queue_save(q)
    _trail("queue-promote", queue_id, priority=priority)
    return {"ok": True, "queue_id": queue_id, "priority": q["priority"]}


PROVIDER_USAGE = ROOT / "logs" / "provider_usage.jsonl"
BREAKER_CONSECUTIVE = 3  # consecutive provider failures before the circuit opens


def _provider_failures(provider: str) -> int:
    """Most-recent consecutive failures for a provider, from the usage ledger tail.

    External steal (agentswarm breaker.ts / subagent-router health): a provider with a
    run of unreachable/failed calls is 'tripped' — the drainer must not keep handing it
    work. Deterministic $0: reads the bounded tail of logs/provider_usage.jsonl.
    """
    if not PROVIDER_USAGE.is_file():
        return 0
    try:
        with PROVIDER_USAGE.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 262144))
            tail = fh.read().splitlines()
        n = 0
        for line in reversed(tail):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if str(row.get("provider")) != provider:
                continue
            if row.get("ok"):
                return n
            n += 1
            if n >= BREAKER_CONSECUTIVE:
                return n
        return n
    except Exception:
        return 0


def _provider_tripped(provider: str) -> bool:
    """Return whether a provider should be skipped by the queue.

    The usage ledger is intentionally append-only, so it can contain a run of
    failures from before a provider recovered.  Remote providers should remain
    fail-closed on that evidence.  Ollama is different: it is a local, free
    lane with a cheap readiness endpoint, so give it an automatic half-open
    probe before settling queued work.  This prevents a stale breaker from
    turning a healthy Docker sidecar into a permanent outage while preserving
    the circuit when the sidecar is actually down or has no models.
    """
    failures = _provider_failures(provider)
    if failures < BREAKER_CONSECUTIVE:
        return False
    if str(provider or "").strip().lower() == "ollama":
        try:
            from models.registry import ollama_tags

            # registry.ollama_tags() has its own short success/failure cache and
            # a hard observer deadline, so this check cannot hold the drainer
            # hostage on Docker DNS or a stopped sidecar.
            if ollama_tags(timeout=2.0):
                return False  # half-open: permit one fresh dispatch attempt
        except Exception:
            pass
    return True


def _settle_unreachable_queued() -> int:
    """Mark queued tasks whose provider is circuit-open as failed (self-healing head).

    External steal (agentswarm ready-set + blocked state): a dead/unreachable provider's
    tasks must vacate the head instead of blocking the drainer. They settle as failed with
    a stored reason; the drainer then picks the first REACHABLE queued task.
    """
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    tripped_cache: dict[str, bool] = {}
    settled = 0
    for p in QUEUE_DIR.glob("*.json"):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("status") != "queued":
            continue
        prov = str(q.get("provider") or "deepseek")
        if prov not in tripped_cache:
            tripped_cache[prov] = _provider_tripped(prov)
        if not tripped_cache[prov]:
            continue
        q["status"] = "failed"
        q["detail"] = "provider circuit open (unreachable)"
        q["ended_at"] = _now()
        _queue_save(q)
        _trail("queue-fail", q.get("queue_id"), error="provider circuit open (unreachable)")
        settled += 1
    return settled


def _next_queued(*, force: bool = False) -> dict[str, Any] | None:
    """Highest-priority queued (not yet running) entry, by tier then priority then age.

    Drains tier-by-tier (mission -> research -> maintenance -> filler) so real work is
    served before auto-generated busywork — one drainer, ghost-operated, priority-aware.
    """
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    best = None
    for p in QUEUE_DIR.glob("*.json"):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("status") != "queued":
            continue
        try:
            from mag import off_hours
            decision = off_hours.eligibility(q, force=force)
            if not decision.get("eligible"):
                if off_hours.mark_deferred(q, decision):
                    _queue_save(q)
                    _trail("queue-defer", q.get("queue_id"), reason=decision.get("reason"),
                           next_eligible_at=decision.get("next_eligible_at"))
                continue
            if off_hours.mark_eligible(q, decision):
                _queue_save(q)
        except Exception:
            # Scheduling is an efficiency guard, never a reason to strand work
            # if the optional policy module is unavailable.
            pass
        if best is None:
            best = q
            continue
        def _key(x):
            return (TIER_RANK.get(str(x.get("tier") or "mission"), 99),
                    -int(x.get("priority") or 0),
                    str(x.get("created_at") or ""))
        if _key(q) < _key(best):
            best = q
    return best


def _any_running_task() -> bool:
    """True if any task is live: a non-terminal task record OR a queue entry
    still in 'running' state (spawned from the queue, not yet finished)."""
    if _running_tasks():
        return True
    # A queue entry in "running" means we spawned it and it hasn't finished.
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    for p in QUEUE_DIR.glob("*.json"):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("status") == "running":
            return True
    return False


def _reconcile_queue() -> int:
    """Mark queue entries done/failed when their linked task is terminal.

    The queue entry stays "running" while its sub-agent is live. When the
    task record reaches a terminal state, this flips the queue entry to match
    so the drain loop can advance to the next goal. Returns entries reconciled.
    """
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    fixed = 0
    for p in QUEUE_DIR.glob("*.json"):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("status") != "running":
            continue
        tid = q.get("task_id")
        if not tid:
            continue
        t = _load(tid)
        if t and t.get("status") in TERMINAL:
            q["status"] = "done" if t.get("status") == "done" else "failed"
            q["detail"] = t.get("detail") or t.get("status")
            _queue_save(q)
            _trail("queue-end", q["queue_id"], task_status=t.get("status"))
            try:
                from mag.cost_ledger import emit_terminal

                emit_terminal(q, t)
            except Exception:
                pass
            fixed += 1
    return fixed


def _running_task_count() -> int:
    """How many local worker slots are LIVE right now.

    External GUI/mailbox seats are visible in the same task registry, but they
    do not consume a local subprocess slot. Counting them here made a pair of
    human-paced seats block every local Ollama recovery task.
    """
    live = _running_tasks()
    local_ids = {str(t.get("task_id") or "") for t in live if not _is_external_task(t)}
    n = len(local_ids)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    for p in QUEUE_DIR.glob("*.json"):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (q.get("status") == "running"
                and str(q.get("task_id") or "") not in local_ids):
            n += 1
    return n


def _provider_running_count(provider: str) -> int:
    """Count local task processes using one provider (external seats excluded)."""
    needle = str(provider or "").strip().lower()
    n = 0
    for task in _running_tasks():
        if _is_external_task(task):
            continue
        provider = str(task.get("provider") or _provider_from_cmd(task.get("cmd")) or "")
        if provider.strip().lower() == needle:
            n += 1
    return n


def _dispatch_spec(q: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Resolve execution routing while preserving the queue's original intent."""
    original = {
        "provider": q.get("provider") or "deepseek",
        "model": q.get("model"),
    }
    try:
        from mag.off_hours import dispatch_spec

        resolved = dispatch_spec(q, force=force)
        if isinstance(resolved, dict):
            original.update({k: resolved.get(k) for k in ("provider", "model", "lane_id", "rerouted", "original_provider", "original_model") if k in resolved})
    except Exception:
        pass
    return original


def _queue_schedule_detail() -> dict[str, Any]:
    try:
        from mag.off_hours import queue_status

        return queue_status(queue_dir=QUEUE_DIR)
    except Exception:
        return {}


def drain_parallel(*, n_agents: int | None = None, force: bool = False,
                   spawn_cap: int = 8, cost_cap_usd: float | None = None) -> dict[str, Any]:
    """PARALLEL drainer: spawn up to N queued goals concurrently (the DeepSeek swarm speedup).

    Operator (2026-08-12): "how can we speed up the agent queue could we launch a deep seek swarm
    to speed it up" + "it can be both" + "i wanna use it for this mapped to what we are doing".

    THE FIX: drain_once() is SEQUENTIAL (spawns one, waits for it to finish). This drains N at
    once — the real "deepseek swarm". N comes from swarm_rightsize.rightsize() (deepseek-v4-flash
    = the quantized cheap vector -> MORE agents affordably, up to its max), bounded by spawn_cap
    (the "can't double" guard, like swarm_test).

    Honest guards (the "don't fuck it up like last time" guarantee):
      spawn_cap     — never have more than this many concurrent spawns.
      cost_cap_usd  — if the estimated cost of the queued batch would exceed this, stop early.
      tier order    — mission -> research -> maintenance -> filler is still honored per batch.
    Returns what it spawned (the parallel batch) + the running count.
    """
    try:
        from mag.autorun_common import autorun_pause_reason
        if not force and autorun_pause_reason():
            return {"ok": True, "action": "paused", "detail": "autorun paused"}
    except Exception:
        pass
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        reap_stale()
        reap_completed()
    except Exception:
        pass
    _reconcile_queue()
    _settle_unreachable_queued()  # circuit-open providers' tasks vacate the head (steal 2026-08-14)

    # N = right-sized swarm size (quantized flash -> more agents), bounded by spawn_cap.
    if n_agents is None:
        try:
            from mag.swarm_rightsize import rightsize
            n_agents = int(rightsize("parallel drain", provider="deepseek-v4-flash").get("n_agents", 4))
        except Exception:
            n_agents = 4
    n_agents = max(1, min(n_agents, spawn_cap))

    running = _running_task_count()
    budget = n_agents - running  # how many more we may spawn this pass
    spawned = []
    while budget > 0:
        nxt = _next_queued(force=force)
        if nxt is None:
            break
        qid = nxt["queue_id"]
        dispatch = _dispatch_spec(nxt, force=force)
        # Ollama is a single CPU/GPU lane on this host. One active generation
        # is faster and safer than a self-inflicted model-swap storm. Remote
        # providers retain the general parallel path.
        if str(dispatch.get("provider") or "").strip().lower() == "ollama" and _provider_running_count("ollama") >= 1:
            break
        # cost cap: stop if the batch estimate would exceed the cap (honest).
        if cost_cap_usd is not None:
            est = nxt.get("task_estimate") or {}
            if dispatch.get("rerouted"):
                try:
                    from mag.cost_ledger import task_estimate

                    est = task_estimate(nxt["goal"], provider=dispatch.get("provider"), model=dispatch.get("model"))
                except Exception:
                    pass
            est_usd = float(est.get("usd", est.get("cost", 0)) or 0) if isinstance(est, dict) else 0.0
            if est_usd > 0 and est_usd > cost_cap_usd / max(budget, 1):
                break
        rec = spawn_task(nxt["goal"], provider=dispatch.get("provider") or "deepseek",
                         model=dispatch.get("model"), timeout=int(nxt.get("timeout") or DEFAULT_TIMEOUT),
                         tag=nxt.get("tag") or "")
        if not rec.get("ok"):
            q = _queue_load(qid) or nxt
            q["status"] = "failed"
            q["detail"] = rec.get("error", "spawn failed")
            _queue_save(q)
            _trail("queue-fail", qid, error=rec.get("error", ""))
            break  # one bad spawn (e.g. quota) — stop this pass, don't hammer
        q = _queue_load(qid) or nxt
        q["status"] = "running"
        q["task_id"] = rec["task_id"]
        q["detail"] = "spawned (parallel)"
        q["dispatch_provider"] = dispatch.get("provider")
        q["dispatch_model"] = dispatch.get("model")
        q["dispatch_lane"] = dispatch.get("lane_id")
        q["dispatch_rerouted"] = bool(dispatch.get("rerouted"))
        q["usage_started_at"] = _now()
        _queue_save(q)
        _trail("queue-start", qid, spawned_task_id=rec["task_id"], mode="parallel")
        try:
            from mag.tripartite_boot import weave_drain
            weave_drain(action="started", goal=nxt.get("goal", ""), task_id=rec.get("task_id", ""),
                        queue_id=qid)
        except Exception:
            pass
        spawned.append({"queue_id": qid, "task_id": rec["task_id"], "goal": nxt["goal"][:120]})
        budget -= 1

    schedule = _queue_schedule_detail()
    action = "off_hours_deferred" if not spawned and schedule.get("heavy_deferred") and not schedule.get("normal_queued") else "parallel"
    return {"ok": True, "schema": "orchestrator.parallel_drain.v1",
            "action": action, "n_agents": n_agents, "running": _running_task_count(),
            "spawned_this_pass": len(spawned), "spawned": spawned,
            "schedule": schedule,
            "guards": {"spawn_cap": spawn_cap, "cost_cap_usd": cost_cap_usd},
            "note": (f"parallel DeepSeek swarm: up to {n_agents} concurrent flash agents; "
                     f"spawned {len(spawned)} this pass; tier order honored per batch")}


def drain_once(*, force: bool = False) -> dict[str, Any]:
    """Spawn the next queued goal IF no task is currently running.

    This is the auto-advance: call it in a loop (or from a timer) and the
    queue drains one goal at a time, moving to the next the moment the
    current one finishes. Returns what happened.
    """
    try:
        from mag.autorun_common import autorun_pause_reason

        pause = None if force else autorun_pause_reason()
        if pause:
            return {"ok": True, "action": "paused", "detail": pause}
    except Exception:
        pass
    _ensure_dirs()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    # Reap dead/stale/completed pids BEFORE reconciling, so a task whose process
    # exited without a terminal record (e.g. pid died, launcher killed the monitor)
    # flips to died/done/failed and the queue can advance instead of staying busy.
    try:
        reap_stale()
    except Exception:
        pass
    try:
        reap_completed()
    except Exception:
        pass
    _reconcile_queue()
    _settle_unreachable_queued()  # circuit-open providers' tasks vacate the head (steal 2026-08-14)
    if _any_running_task():
        return {"ok": True, "action": "busy", "detail": "a task is already running"}
    # RESUME-ORDER (operator 2026-08-10): before picking the next task, auto-promote the
    # highest-zeitgeist / blocker-unblocking queued tasks so the drainer serves the project's
    # current convergence + blockers first, not just FIFO. Deterministic $0, best-effort.
    try:
        from mag.resume_order import promote_drainer
        promote_drainer(top=3, boost=5)
    except Exception:
        pass
    nxt = _next_queued(force=force)
    if nxt is None:
        schedule = _queue_schedule_detail()
        if schedule.get("heavy_deferred") and not schedule.get("normal_queued"):
            return {"ok": True, "action": "off_hours_deferred",
                    "detail": "heavy work is queued for the next off-hours window",
                    "schedule": schedule}
        return {"ok": True, "action": "empty", "detail": "no queued goals", "schedule": schedule}
    qid = nxt["queue_id"]
    dispatch = _dispatch_spec(nxt, force=force)
    rec = spawn_task(nxt["goal"], provider=dispatch.get("provider") or "deepseek",
                     model=dispatch.get("model"), timeout=int(nxt.get("timeout") or DEFAULT_TIMEOUT),
                     tag=nxt.get("tag") or "")
    if not rec.get("ok"):
        q = _queue_load(qid) or nxt
        q["status"] = "failed"
        q["detail"] = rec.get("error", "spawn failed")
        _queue_save(q)
        _trail("queue-fail", qid, error=rec.get("error", ""))
        try:
            from mag.queue_ops import handle_error, log_event
            handle_error(rec.get("error", ""), queue_id=qid, phase="spawn",
                         goal=nxt.get("goal", ""), provider=nxt.get("provider") or "",
                         model=nxt.get("model") or "")
            log_event("drain_fail", qid, goal=nxt.get("goal", "")[:120])
        except Exception:
            pass
        return {"ok": False, "action": "spawn_failed", "queue_id": qid,
                "detail": rec.get("error", "")}
    q = _queue_load(qid) or nxt
    q["status"] = "running"
    q["task_id"] = rec["task_id"]
    q["detail"] = "spawned"
    q["dispatch_provider"] = dispatch.get("provider")
    q["dispatch_model"] = dispatch.get("model")
    q["dispatch_lane"] = dispatch.get("lane_id")
    q["dispatch_rerouted"] = bool(dispatch.get("rerouted"))
    q["usage_started_at"] = _now()
    _queue_save(q)
    _trail("queue-start", qid, spawned_task_id=rec["task_id"])
    try:
        from mag.queue_ops import log_event
        log_event("drain_start", qid, task_id=rec.get("task_id", ""),
                  tier=nxt.get("tier") or "mission", goal=nxt.get("goal", "")[:120])
    except Exception:
        pass
    try:
        from mag.tripartite_boot import weave_drain

        weave_drain(
            action="started",
            goal=nxt.get("goal", ""),
            task_id=rec.get("task_id", ""),
            queue_id=qid,
        )
    except Exception:
        pass
    return {"ok": True, "action": "started", "queue_id": qid,
            "task_id": rec["task_id"], "goal": nxt["goal"][:120]}


def drain_loop(interval_s: float = 5.0, *, once: bool = False) -> None:
    """Run drain_once repeatedly so the queue auto-advances.

    `once=True` runs a single drain pass and returns (for smoke tests / CLI).
    Otherwise loops forever (Ctrl-C to stop), spawning the next queued goal
    whenever the current one finishes.

    Set MAG_AUTOPILOT_EVERY=N to run autopilot_once every N drain cycles
    (e.g. 60 ≈ 5 min at 5s interval) when drainer is on.
    """
    autopilot_every = int(os.environ.get("MAG_AUTOPILOT_EVERY", "0") or "0")
    tick = 0
    while True:
        try:
            res = drain_once()
            if res.get("action") in ("started", "spawn_failed"):
                print(dim("  [queue] %s %s" % (res.get("action"), res.get("detail", ""))), flush=True)
        except Exception as e:
            print(dim("  [queue] drain error: %s" % e), flush=True)
        tick += 1
        if autopilot_every > 0 and tick % autopilot_every == 0:
            try:
                from mag.autopilot import autopilot_once

                ap = autopilot_once(queue_improve=True, governor=True, drain=False, max_queue=1)
                print(dim("  [autopilot] seed=%s steps=%s" % (
                    ap.get("seed_mirror", {}).get("hint", "?")[:60],
                    len(ap.get("steps") or []),
                )), flush=True)
            except Exception as e:
                print(dim("  [autopilot] error: %s" % e), flush=True)
        if once:
            return
        time.sleep(interval_s)


def queue_status() -> dict[str, Any]:
    """Summary of the queue: counts by status + the running task id."""
    entries = list_queue()
    counts: dict[str, int] = {}
    running = None
    for q in entries:
        st = q.get("status") or "?"
        counts[st] = counts.get(st, 0) + 1
        if st == "running":
            running = q.get("task_id")
    return {"ok": True, "total": len(entries), "counts": counts,
            "running_task_id": running}


def _task_recency(task: dict[str, Any]) -> tuple[str, str]:
    """Return a filesystem-independent recency key for a task record.

    Status surfaces used to sort every task with ``Path.stat()`` before reading
    it. On Windows, a concurrently replaced/locked record could make that
    observer block indefinitely. Task records already carry their lifecycle
    timestamps, so use those as the source of recency and keep the task id as a
    deterministic tie-breaker.
    """
    stamps = (
        str(task.get("updated_at") or ""),
        str(task.get("last_seen_at") or ""),
        str(task.get("ended_at") or ""),
        str(task.get("started_at") or ""),
        str(task.get("created_at") or ""),
    )
    return max(stamps), str(task.get("task_id") or "")


def list_tasks(limit: int = 20) -> list[dict[str, Any]]:
    global _TASK_LIST_CACHE
    _ensure_dirs()
    if limit <= 0:
        return []
    cache_key = str(TASK_DIR)
    now_mono = time.monotonic()
    with _TASK_LIST_CACHE_LOCK:
        cached = _TASK_LIST_CACHE
        if (cached and cached[0] == cache_key
                and now_mono - cached[1] < _TASK_LIST_CACHE_TTL_S):
            return [dict(row) for row in cached[2][:limit]]
    rows: list[dict[str, Any]] = []
    # IDs are random and therefore not chronological. Read the lifecycle stamp
    # already stored in each record instead of stat'ing paths in the hot status
    # path; this remains safe when another process is atomically replacing one.
    try:
        paths = TASK_DIR.glob("*.json")
        for p in paths:
            try:
                row = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return []
    rows.sort(key=_task_recency, reverse=True)
    with _TASK_LIST_CACHE_LOCK:
        _TASK_LIST_CACHE = (cache_key, time.monotonic(), [dict(row) for row in rows])
    return rows[:limit]


def list_tasks_live(limit: int = 50) -> list[dict[str, Any]]:
    """Fleet view WITH live knot state (phase, heartbeat age, alive) — the
    dashboard feeds from this so the tab shows agents as they really are:
    fresh, stale, departed. Raw list_tasks() stays for CLI/orchestrator use."""
    tasks = list_tasks(limit=limit)
    ph = _ph()
    for t in tasks:
        if not t.get("goal"):
            cmd = t.get("cmd") or []
            try:
                i = cmd.index("--query")
                if i + 1 < len(cmd):
                    t["goal"] = cmd[i + 1]
            except ValueError:
                pass

        if t.get("status") not in ("running", "queued"):
            continue
        if ph is None:
            continue
        try:
            t["heartbeat_age_s"] = ph.staleness_s(t["task_id"])
            t["alive"] = ph.alive(t["task_id"])
            st = ph.read_status(t["task_id"])
            if st:
                t["phase"] = st.get("phase")
                t["agent_ts"] = st.get("ts")
        except Exception:
            pass
    return tasks


def task_status(task_id: str) -> dict[str, Any] | None:
    t = _load(task_id)
    if not t:
        return None
    # Live knot view: heartbeat freshness + agent-reported phase. This is the
    # crash recognizer the supervisor sees — not a timeout countdown.
    ph = _ph()
    if ph is not None:
        try:
            t["heartbeat_age_s"] = ph.staleness_s(task_id)
            t["alive"] = ph.alive(task_id)
            st = ph.read_status(task_id)
            if st:
                t["phase"] = st.get("phase")
                t["agent_ts"] = st.get("ts")
        except Exception:
            pass
    return t


def kill_task(task_id: str) -> dict[str, Any]:
    task = _load(task_id)
    if not task:
        return {"ok": False, "error": "no such task"}
    if task.get("status") in TERMINAL:
        return {"ok": True, "task": task, "note": "already terminal"}
    pid = task.get("pid")
    if pid:
        _kill_tree(pid)
    return {"ok": True, "task": _finalize(task_id, "killed",
                                          detail="operator kill", killed=True)}


def reap_stale() -> dict[str, Any]:
    """Mark running tasks whose pid is dead as died (parent survived a crash)."""
    _ensure_dirs()
    fixed = 0
    for t in _active_task_records():
        if t.get("status") != "running":
            continue
        pid = t.get("pid")
        if pid and not _pid_alive(pid):
            _finalize(t["task_id"], "died", detail="pid gone (parent survived)")
            fixed += 1
            continue
        # External/desktop seats: no pid — reap on stale pigeonhole heartbeat.
        # MAILBOX seats (zcode, notion, autoclaw) are human/GUI-paced: no automated
        # heartbeat, and auto-dying a task the operator is actively working is a
        # FALSE kill (2026-08-25: ext-26d39414f1 and ext-6bf4a1266d both died while
        # waiting on human-paced work). They close via `done`, never here.
        if not pid and _is_external_task(t):
            if t.get("seat") in EXTERNAL_NO_REAP_SEATS:
                continue
            ph = _ph()
            if ph is None:
                continue
            try:
                age = ph.staleness_s(t["task_id"])
            except Exception:
                age = None
            if age is not None and age > EXTERNAL_STALE_S:
                _finalize(
                    t["task_id"],
                    "died",
                    detail=f"external heartbeat stale {age}s",
                )
                fixed += 1
    return {"ok": True, "reaped": fixed}


def reap_completed() -> dict[str, Any]:
    """Mark running tasks whose pid is gone as done/failed using the seat's own
    mailbox status.json (agent writes phase=done + exit_code on completion).

    This is the gpipes gap: the launcher exits right after fan_out, killing the
    daemon _monitor threads that were supposed to _finalize() workers on exit.
    The detached supervisor survives, so any status/collect/supervise call must
    reap here instead — reading the agent's self-reported phase lets us classify
    done vs failed (not blanket 'died' like reap_stale).
    """
    _ensure_dirs()
    fixed = 0
    classified = {"done": 0, "failed": 0, "died": 0}
    for t in _active_task_records():
        if t.get("status") != "running":
            continue
        pid = t.get("pid")
        if pid and _pid_alive(pid):
            continue
        tid = t["task_id"]
        # External/desktop seats without a pid: only reap when the mailbox says
        # the agent finished (phase=done/failed) — otherwise leave for reap_stale.
        if not pid and not _is_external_task(t):
            continue
        # Read the agent's self-reported final phase + exit code.
        phase = ""
        code = None
        try:
            from mag import pigeonhole as ph

            st = ph.read_status(tid)
            if isinstance(st, dict):
                phase = str(st.get("phase") or "").strip().lower()
                try:
                    code = int(st.get("exit_code"))
                except (TypeError, ValueError):
                    code = None
        except Exception:
            phase, code = "", None
        if phase in ("done", "complete", "ok") or code == 0:
            _finalize(tid, "done", exit_code=code if code is not None else 0,
                      detail="pid gone (reaped; seat reported done)")
            fixed += 1
            classified["done"] += 1
        elif phase in ("failed", "crashed", "error", "stopped") or (
            code is not None and code != 0
        ):
            _finalize(tid, "failed", exit_code=code if code is not None else 1,
                      detail=f"pid gone (reaped; seat reported {phase or 'failure'})")
            fixed += 1
            classified["failed"] += 1
        elif not pid:
            # No pid (external) and no self-reported terminal phase: not ours.
            continue
        else:
            _finalize(tid, "died", detail="pid gone (reaped; seat reported no phase)")
            fixed += 1
            classified["died"] += 1
    return {"ok": True, "reaped": fixed, "classified": classified}


def respawn_dead(max_per_task: int = 2) -> dict[str, Any]:
    """Watchdog: mark dead-pid running tasks as died, then re-spawn them
    (bounded retries) with the same command. Auto-heal for the fleet."""
    _ensure_dirs()
    reaped = 0
    respawned: list[dict[str, Any]] = []
    for t in _active_task_records():
        if t.get("status") != "running":
            continue
        pid = t.get("pid")
        if not (pid and not _pid_alive(pid)):
            continue
        old_id = t["task_id"]
        rc = int(t.get("respawn_count", 0) or 0)
        if rc >= max_per_task:
            _finalize(old_id, "died", detail="pid gone (watchdog), respawns exhausted")
            reaped += 1
            continue
        _finalize(old_id, "died", detail="pid gone (watchdog), respawning")
        reaped += 1
        cmd = t.get("cmd") or []
        if not cmd or cmd[0] != headless.PYTHON:
            continue  # not a respawnable agent cmd
        new_id = "t" + uuid.uuid4().hex[:10]
        nrec = _spawn_cmd(cmd, task_id=new_id,
                          timeout=int(t.get("timeout_s") or DEFAULT_TIMEOUT),
                          tag=str(t.get("tag") or ""))
        nrec["respawn_of"] = old_id
        nrec["respawn_count"] = rc + 1
        nrec["goal"] = t.get("goal", "")
        _save(nrec)
        _trail("respawn", new_id, from_task=old_id, count=rc + 1)
        respawned.append(nrec)
    return {"ok": True, "reaped": reaped, "respawned": respawned}


def tail_log(task_id: str, n: int = 20) -> str:
    p = LOG_DIR / (task_id + ".out.log")
    if not p.is_file():
        return "no log yet"
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def self_test() -> dict[str, Any]:
    """Spawn a trivial python child; assert it completes with status done."""
    task_id = "t" + uuid.uuid4().hex[:10]
    cmd = [headless.PYTHON, "-c", "print('orc-self-test-ok')"]
    rec = _spawn_cmd(cmd, task_id=task_id, timeout=60, tag="self-test")
    t = rec
    import time
    for _ in range(60):
        t = _load(task_id) or {}
        if t.get("status") in TERMINAL:
            break
        time.sleep(0.5)
    ok = t.get("status") == "done" and t.get("exit_code") == 0
    return {"ok": ok, "task": t}


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv else sys.argv[1:]
    if not args:
        print("usage: orchestrator run|list|status|kill|reap|self-test")
        return 2
    cmd = args[0]
    if cmd == "self-test":
        print(json.dumps(self_test(), indent=2, default=str))
        return 0 if self_test()["ok"] else 1
    if cmd == "list":
        for t in list_tasks():
            print("%s %-9s %-20s %s" % (t.get("task_id", "?"), t.get("status", "?"),
                                        t.get("tag", ""), (t.get("cmd") or [""])[-1][:60]))
        return 0
    if cmd == "status":
        if len(args) < 2:
            print("need task_id")
            return 2
        t = task_status(args[1])
        if not t:
            print("no such task")
            return 1
        print(json.dumps(t, indent=2, default=str))
        tail = 0
        if "--tail" in args:
            try:
                tail = int(args[args.index("--tail") + 1])
            except (ValueError, IndexError):
                tail = 20
        if tail:
            print("--- log tail ---")
            print(tail_log(args[1], tail))
        return 0
    if cmd in ("steer", "pause", "continue"):
        if len(args) < 2:
            print("need task_id")
            return 2
        tid = args[1]
        if not _load(tid):
            print("no such task")
            return 1
        ph = _ph()
        if ph is None:
            print("pigeonhole unavailable")
            return 1
        if cmd == "steer":
            ctx = " ".join(args[2:]).strip()
            if not ctx:
                print("need steer context text")
                return 2
            ph.post_steer(tid, ctx)
            print("steer posted to %s" % tid)
        elif cmd == "pause":
            ph.post_cmd(tid, "!pause")
            print("pause posted to %s" % tid)
        else:
            ph.post_cmd(tid, "!continue")
            print("continue posted to %s" % tid)
        return 0
    if cmd == "watch":
        if len(args) < 2:
            print("need task_id")
            return 2
        tid = args[1]
        ph = _ph()
        for _ in range(60):
            t = task_status(tid)
            if not t:
                print("no such task")
                return 1
            age = t.get("heartbeat_age_s")
            phase = t.get("phase", "?")
            alive = t.get("alive")
            print("%-9s phase=%-14s heartbeat_age=%s alive=%s" % (
                t.get("status", "?"), phase,
                "?" if age is None else ("%ss" % age),
                "?" if alive is None else alive), flush=True)
            if t.get("status") in TERMINAL:
                return 0 if t.get("status") == "done" else 1
            time.sleep(5)
        return 0
    if cmd == "kill":
        if len(args) < 2:
            print("need task_id")
            return 2
        print(json.dumps(kill_task(args[1]), indent=2, default=str))
        return 0
    if cmd == "reap":
        print(json.dumps(reap_stale(), indent=2))
        return 0
    if cmd == "queue":
        sub = args[1] if len(args) > 1 else "list"
        if sub == "add":
            rest = args[2:]
            goal = ""
            provider = "ollama"
            model = None
            timeout = DEFAULT_TIMEOUT
            tag = ""
            heavy = None
            schedule_policy = None
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
                elif a == "--heavy":
                    heavy = True; i += 1
                elif a == "--anytime":
                    schedule_policy = "anytime"; i += 1
                elif a == "--off-hours":
                    schedule_policy = "off_hours"; i += 1
                else:
                    goal = (goal + " " + a).strip(); i += 1
            if not goal:
                print("need a goal")
                return 2
            q = enqueue(goal, provider=provider, model=model,
                        timeout=timeout, tag=tag, heavy=heavy,
                        schedule_policy=schedule_policy)
            print(json.dumps(q, indent=2, default=str))
            return 0 if q.get("ok") else 1
        if sub == "list":
            for q in list_queue():
                print("%s %-9s %-20s %s" % (
                    q.get("queue_id", "?"), q.get("status", "?"),
                    q.get("tag", ""), q.get("goal", "")[:60]))
            return 0
        if sub == "status":
            print(json.dumps(queue_status(), indent=2, default=str))
            return 0
        if sub in ("purge-failed", "purge_failed"):
            print(json.dumps(purge_failed_queue(), indent=2, default=str))
            return 0
        print("unknown queue subcommand: " + sub)
        return 2
    if cmd == "drain":
        once = "--once" in args
        drain_loop(interval_s=5.0, once=once)
        return 0
    if cmd == "run":
        rest = args[1:]
        goal = ""
        provider = "ollama"
        model = None
        timeout = DEFAULT_TIMEOUT
        tag = ""
        wait = False
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
            elif a == "--wait":
                wait = True; i += 1
            else:
                goal = (goal + " " + a).strip(); i += 1
        if not goal:
            print("need a goal")
            return 2
        rec = spawn_task(goal, provider=provider, model=model,
                         timeout=timeout, tag=tag)
        print(json.dumps(rec, indent=2, default=str))
        if wait and rec.get("task_id"):
            import time
            tid = rec["task_id"]
            for _ in range(timeout + 1):
                t = _load(tid) or {}
                if t.get("status") in TERMINAL:
                    print("--- final ---")
                    print(json.dumps(t, indent=2, default=str))
                    print("--- log tail ---")
                    print(tail_log(tid, 40))
                    return 0 if t.get("status") == "done" else 1
                time.sleep(1)
        return 0
    print("unknown orchestrator command: " + cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main())
