# Seat Guard - auto-relaunch supervisor for the long-lived interactive seat.
# WHY (operator, 2026-08-03): "we're building a system to detect and work
# around it by relaunching yourself." The seat (mag/agent_cli.py REPL) is the
# one long-lived process with NO auto-restart supervisor - orchestrator only
# supervises short-lived one-shot sub-agents. When the seat glitches (empty
# reply loops, collapse hard-stops, provider hangs, unhandled crashes) the
# operator had to notice and relaunch manually. This guard:
#   - spawns the seat as a child (same console, so typing still works)
#   - gives it a STABLE MAG_TASK_ID across restarts, so the pigeonhole mailbox
#     (steer/pause/continue channel + heartbeats + status) survives relaunch
#   - detects: nonzero crash exit | suspicious quick exit | heartbeat stall
#     mid-turn (nudge once, then kill) | >=3 consecutive hard-stop phases
#     (empty_stop/collapse_stop/budget_stop/agent_error) with no recovery
#   - relaunches with backoff, records every event in the guard trail
# Usage (via main.py):
#   python main.py seat-guard run [--provider deepseek] [--model X]
#                                 [--stall 45] [--grace 60] [--max-restarts 5]
#   python main.py seat-guard status <task_id>
#   python main.py seat-guard stop <task_id>
#   python main.py seat-guard trail [--limit 20]
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from mag import headless
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GUARD_DIR = ROOT / "memory" / "runs" / "seat_guard"
TRAIL = GUARD_DIR / "seat_guard_trail.jsonl"

# Seat failure phases (mag/agent_cli.py _mail phase=...). A healthy turn writes
# "started" at turn start and "answered" at the end; these mean the turn ended
# in a hard stop and the seat is sitting at the REPL.
STOP_PHASES = {"empty_stop", "collapse_stop", "budget_stop", "agent_error", "crashed"}
GOOD_PHASES = {"started", "answered", "done"}
HARD_STOP_STREAK = 3        # N consecutive failure phases -> relaunch
NUDGE_AT_STREAK = 2         # nudge (recovery steer) at this streak first
DEFAULT_BACKOFF = (2, 5, 10, 20, 30)
POLL_S = 5.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    GUARD_DIR.mkdir(parents=True, exist_ok=True)


def _trail(event: str, task_id: str, **meta: Any) -> None:
    _ensure_dirs()
    entry = {"timestamp": _now(), "event": event, "task_id": task_id, **meta}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _seat_path(task_id: str) -> Path:
    return GUARD_DIR / (task_id + ".json")


def _load_seat(task_id: str) -> dict[str, Any] | None:
    p = _seat_path(task_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_seat(rec: dict[str, Any]) -> None:
    _ensure_dirs()
    _seat_path(rec["task_id"]).write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _ph() -> Any:
    try:
        from mag import pigeonhole as ph
        return ph
    except Exception:
        return None


def _kill_tree(pid: int | None) -> None:
    """Terminate the process and its children (Windows process tree)."""
    if not pid:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0,
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
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _dim(msg: str) -> str:
    try:
        return "\x1b[2m" + msg + "\x1b[0m"
    except Exception:
        return msg


def _launch(task_id: str, provider: str, model: str | None) -> subprocess.Popen:
    """Spawn the seat REPL sharing our console; stable MAG_TASK_ID = knot."""
    cmd = [headless.PYTHON, str(ROOT / "main.py"), "agent", "--provider", provider]
    if model:
        cmd += ["--model", model]
    env = dict(os.environ)
    env["MAG_TASK_ID"] = task_id
    env["MAG_ALLOW_REPL"] = "1"  # supervised interactive seat — not restful one-shot
    flags = 0
    if sys.platform == "win32":
        # own group so guard Ctrl+C / taskkill reaps it; CREATE_NO_WINDOW so the
        # supervised seat does not pop a console window on the desktop.
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP
                 | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    return subprocess.Popen(
        cmd, env=env, stdin=None, stdout=None, stderr=None,
        creationflags=flags,
    )


def _finish(rec: dict[str, Any], status: str, detail: str) -> None:
    rec["status"] = status
    rec["last_event"] = detail
    rec["ended_at"] = _now()
    _save_seat(rec)


def run_seat(*, provider: str = 'deepseek', model: str | None = None,
             task_id: str | None = None, stall_s: int = 45,
             grace_s: int = 60, max_restarts: int = 5,
             min_uptime_s: int = 30) -> int:
    _ensure_dirs()
    task_id = task_id or ('seat-' + uuid.uuid4().hex[:8])
    backoff = DEFAULT_BACKOFF
    rec = {'task_id': task_id, 'status': 'running', 'provider': provider,
           'model': model or '', 'spawned_at': _now(), 'pid': None,
           'restarts': 0, 'last_event': 'started', 'phases_seen': []}
    _save_seat(rec)
    stop_marker = GUARD_DIR / (task_id + '.stop')
    ph = _ph()
    nudge_sent = False
    streak = 0
    last_status_ts = None
    print(_dim('[seat-guard] supervising seat %s (provider=%s)' % (task_id, provider)), flush=True)
    _trail('guard_start', task_id, provider=provider)
    try:
        from mag.seat_registry import register as register_seat

        register_seat(
            seat="agent",
            goal=f"supervised seat ({provider})",
            mode="interactive",
            task_id=task_id,
            pid=None,
            tag="seat-guard",
            parent="seat_guard",
        )
    except Exception:
        pass
    proc = _launch(task_id, provider, model)
    rec['pid'] = proc.pid
    rec['spawned_at'] = _now()
    rec['_started_unix'] = time.time()
    _save_seat(rec)
    print(_dim('[seat-guard] seat up pid=%d' % proc.pid), flush=True)
    _trail('seat_start', task_id, pid=proc.pid)

    def _relaunch(reason, exit_code=None, uptime_s=None):
        nonlocal proc, nudge_sent, streak, last_status_ts
        rec['restarts'] += 1
        n = rec['restarts']
        rec['last_event'] = 'relaunch#%d:%s' % (n, reason)
        _save_seat(rec)
        _trail('relaunch', task_id, reason=reason, attempt=n,
               exit_code=exit_code, uptime_s=uptime_s)
        print(_dim('[seat-guard] relaunch #%d after %s (exit=%s, uptime=%.0fs)'
                   % (n, reason, exit_code, uptime_s or 0)), flush=True)
        if n > max_restarts:
            _finish(rec, 'gave_up', 'max_restarts=%d exceeded: %s' % (max_restarts, reason))
            _trail('guard_gave_up', task_id, reason=reason)
            print(_dim('[seat-guard] GAVE UP after %d restarts' % n), flush=True)
            return False
        delay = backoff[min(n - 1, len(backoff) - 1)]
        print(_dim('[seat-guard] relaunching in %ds ...' % delay), flush=True)
        time.sleep(delay)
        proc = _launch(task_id, provider, model)
        rec['pid'] = proc.pid
        rec['spawned_at'] = _now()
        rec['_started_unix'] = time.time()
        _save_seat(rec)
        print(_dim('[seat-guard] seat up pid=%d' % proc.pid), flush=True)
        _trail('seat_start', task_id, pid=proc.pid)
        nudge_sent = False
        streak = 0
        last_status_ts = None
        return True

    try:
        while True:
            time.sleep(POLL_S)
            if stop_marker.is_file():
                print(_dim('[seat-guard] stop requested - killing seat'), flush=True)
                _kill_tree(proc.pid)
                _trail('guard_stop', task_id, reason='operator stop')
                try:
                    stop_marker.unlink()
                except OSError:
                    pass
                _finish(rec, 'stopped', 'operator stop')
                return 0
            rc = proc.poll()
            if rc is not None:
                uptime = time.time() - rec.get('_started_unix', time.time())
                if rc != 0:
                    if not _relaunch('crash exit %d' % rc, rc, uptime):
                        return 1
                    continue
                if uptime < min_uptime_s:
                    if not _relaunch('quick exit 0 after %.0fs (<%ds)' % (uptime, min_uptime_s), rc, uptime):
                        return 1
                    continue
                print(_dim('[seat-guard] seat exited cleanly (rc=0, uptime=%.0fs) - guard stopping' % uptime), flush=True)
                _trail('seat_clean_exit', task_id, uptime_s=round(uptime, 1))
                _finish(rec, 'done', 'clean seat exit')
                return 0

            age = None
            st = None
            if ph is not None:
                try:
                    age = ph.staleness_s(task_id)
                except Exception:
                    age = None
                try:
                    st = ph.read_status(task_id)
                except Exception:
                    st = None
            if age is not None and age > stall_s:
                if not nudge_sent:
                    nudge_sent = True
                    try:
                        ph.post_steer(task_id, 'No heartbeat for %.0fs mid-turn - re-anchor to the active Blueprint and keep reporting progress.' % age)
                    except Exception:
                        pass
                    _trail('stall_nudge', task_id, age_s=round(age, 1))
                    print(_dim('[seat-guard] stall-nudge (no heartbeat %.0fs)' % age), flush=True)
                elif age > stall_s + grace_s:
                    print(_dim('[seat-guard] seat stalled %.0fs - killing and relaunching' % age), flush=True)
                    _kill_tree(proc.pid)
                    time.sleep(2.0)
                    if not _relaunch('heartbeat stall %.0fs' % age, None, age):
                        return 1
                    continue

            if st and st.get('ts') != last_status_ts:
                last_status_ts = st.get('ts')
                phase = st.get('phase', '')
                rec['phases_seen'] = (rec.get('phases_seen') or [])[-20:] + [phase]
                _save_seat(rec)
                if phase in GOOD_PHASES:
                    streak = 0
                    nudge_sent = False
                elif phase in STOP_PHASES:
                    streak += 1
                    print(_dim('[seat-guard] seat phase=%s (streak %d/%d)'
                               % (phase, streak, HARD_STOP_STREAK)), flush=True)
                    if streak == NUDGE_AT_STREAK and not nudge_sent:
                        nudge_sent = True
                        try:
                            ph.post_steer(task_id, 'Last turns ended in a hard stop. Re-anchor to the active Blueprint and continue with a concrete tool call.')
                        except Exception:
                            pass
                        _trail('hardstop_nudge', task_id, phase=phase, streak=streak)
                    elif streak >= HARD_STOP_STREAK:
                        print(_dim('[seat-guard] %d hard stops in a row - relaunching seat' % streak), flush=True)
                        _kill_tree(proc.pid)
                        time.sleep(2.0)
                        if not _relaunch('%d consecutive %s' % (streak, phase), None, None):
                            return 1
                        continue
    except KeyboardInterrupt:
        print(_dim('[seat-guard] Ctrl+C - stopping seat'), flush=True)
        _kill_tree(proc.pid)
        _trail('guard_stop', task_id, reason='ctrl-c')
        _finish(rec, 'stopped', 'ctrl-c')
        return 0
    finally:
        _kill_tree(proc.pid)



def _read_trail(n: int = 10) -> list[str]:
    """Return the last n trail lines (plain text)."""
    if not TRAIL.is_file():
        return []
    lines = TRAIL.read_text(encoding="utf-8").splitlines()
    out = []
    for ln in lines[-n:]:
        try:
            e = json.loads(ln)
            out.append("%s %-14s %s" % (e.get("timestamp", "?")[11:19], e.get("event", "?"), e.get("task_id", "?")))
        except Exception:
            out.append(ln)
    return out

def main(argv: list[str] | None = None) -> int:
    """CLI: python mag/seat_guard.py run|status|stop|trail [args]"""
    import argparse
    ap = argparse.ArgumentParser(prog='seat-guard', description='Supervise the autonomous seat REPL')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='launch and supervise the seat')
    r.add_argument('--provider', default='deepseek')
    r.add_argument('--model', default=None)
    r.add_argument('--task-id', default=None)
    r.add_argument('--stall', type=int, default=45, help='seconds without heartbeat before nudge')
    r.add_argument('--grace', type=int, default=60, help='extra seconds before hard relaunch')
    r.add_argument('--max-restarts', type=int, default=5)
    r.add_argument('--min-uptime', type=int, default=30, help='min uptime for a clean exit to count')
    s = sub.add_parser('status', help='print seat record')
    s.add_argument('--task-id', default=None)
    t = sub.add_parser('stop', help='request guard stop (writes .stop marker)')
    t.add_argument('task_id')
    tr = sub.add_parser('trail', help='tail guard trail')
    tr.add_argument('--n', type=int, default=10)
    args = ap.parse_args(argv)
    if args.cmd == 'run':
        return run_seat(provider=args.provider, model=args.model, task_id=args.task_id,
                        stall_s=args.stall, grace_s=args.grace,
                        max_restarts=args.max_restarts, min_uptime_s=args.min_uptime)
    if args.cmd == 'status':
        rec = _load_seat(args.task_id)
        if not rec:
            print('no seat record found')
            return 1
        import json
        print(json.dumps(rec, indent=2))
        return 0
    if args.cmd == 'stop':
        if args.task_id:
            (GUARD_DIR / (args.task_id + '.stop')).touch()
            print('stop marker written for %s' % args.task_id)
            return 0
        print('task_id required')
        return 1
    if args.cmd == 'trail':
        lines = _read_trail(args.n)
        for ln in lines:
            print(ln)
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
