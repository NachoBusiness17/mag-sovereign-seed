"""source_trace — ghost 'sense runaway python TO SOURCE'.

STEAL (2026-08-10, supervisord/pm2/systemd contracts adapted):
  * supervisord attributes each child to its source via an INHERITED env marker
    (SUPERVISOR_PROCESS_NAME / SUPERVISOR_GROUP_NAME) — attribution by marker,
    not by guessing ppids.
  * systemd's unit cgroup IS the source attribution — killing the unit kills the
    whole tree.
  * pm2 names slots and shows the source script.

On Windows (no cgroups; psutil optional) we adapt:
  1. Every framework spawner stamps its children with MAG_SLOT / MAG_SOURCE env
     (the supervisord marker analog) — see mag_launch._spawn / mag/headless.py.
  2. trace_source(pid) walks the ppid ancestry (CIM ParentProcessId) up to the
     ROOT spawner, so ghost reports WHERE a storm came from (boot_mag.cmd ->
     power start -> mag_launch -> ghost daemon -> runaway autorun_loop), not just
     "too many processes".
  3. break_source(root) taskkills /T the whole source tree (systemd-kill-unit
     analog), never genuine leaf work.

The 2026-08-10 window storm this catches: duplicate autorun_loop/ghost-cycle
children under one ghost daemon + a second windowed boot stacking the same slots.
Ghost previously reported a storm existed; now it reports the SOURCE chain and
can break the source tree.

Schema: source_trace.v1
CLI:  python -m mag.source_trace sense
      python -m mag.source_trace trace <pid>
      python -m mag.source_trace break <pid> [--live]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "source_trace.v1"

# Slots a HEALTHY stack has exactly ONE of. More than one = duplicate/runaway.
# (venv shim + uv cpython child share the same cmd text, so they collapse to one.)
SINGLETON_SLOTS = {
    "lab", "scribe", "ghost", "dashboard", "backend", "mirror",
    "drainer", "mag_launch", "power_boot", "ghost_cycle",
}
# A framework spawner parent spawning this many children = runaway cascade.
RUN_AWAY_CHILD_COUNT = 6
# Distinct top-level boot roots above this = multi-boot stacking storm.
MULTI_BOOT = 2

# cmd-text -> slot (order matters; specific before generic).
_SLOT_RULES = (
    ("governor_autorun", "drainer"), ("autorun_loop", "drainer"),
    ("from mag.ghost import cycle", "ghost_cycle"),
    ("-m mag.ghost --daemon", "ghost"), ("mag.ghost --daemon", "ghost"),
    ("main.py lab", "lab"), ("synthesis_agent.py", "scribe"),
    ("main.py dashboard", "dashboard"), ("backend.server", "backend"),
    ("run_mirror_dashboard", "mirror"), ("mag_launch.py", "mag_launch"),
    ("main.py power start", "power_boot"), ("main.py autorun", "drainer"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slot_of(cmd: str) -> str:
    for needle, slot in _SLOT_RULES:
        if needle in cmd:
            return slot
    return "other"


def _boot_of(cmd: str) -> str:
    """Root-source label for a top-level spawner, else ''."""
    c = cmd.lower()
    if "boot_mag.cmd" in c:
        return "boot_mag.cmd"
    if "start_everything.cmd" in c:
        return "start_everything.cmd"
    if "power start" in c:
        return "power start"
    if "mag_launch.py" in c:
        return "mag_launch.py"
    return ""


def _bounded_process_call(fn: Any, *, timeout: float = 0.25, default: Any = None) -> Any:
    """Read optional process metadata without letting a protected PID block us."""
    done = threading.Event()
    box: list[Any] = []

    def _run() -> None:
        try:
            box.append(fn())
        except Exception:
            box.append(default)
        finally:
            done.set()

    threading.Thread(target=_run, name="source-trace-probe", daemon=True).start()
    if not done.wait(timeout):
        return default
    return box[0] if box else default


def _enum() -> list[dict[str, Any]]:
    """Enumerate running python/pythonw processes (psutil preferred, else CIM)."""
    out: list[dict[str, Any]] = []
    try:
        import psutil  # type: ignore
        # Do not ask process_iter(attrs=...) for cmdline: on Windows psutil
        # materializes every requested field before yielding the process, and
        # one protected/system process can block or raise outside our loop.
        # Fetch fields independently so a denied cmdline/env only degrades one
        # record instead of taking down the observer.
        for proc in psutil.process_iter():
            try:
                name_value = proc.name()
                name = (name_value or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmdline = _bounded_process_call(proc.cmdline, default=[]) or []
                try:
                    ppid = proc.ppid()
                except Exception:
                    ppid = None
                env = dict(_bounded_process_call(proc.environ, default={}) or {})
                out.append({
                    "pid": proc.pid, "ppid": ppid,
                    "name": name_value,
                    "cmd": " ".join(cmdline)[:400],
                    "env": env,
                })
            except Exception:
                continue
        return out
    except ImportError:
        pass
    except Exception:
        # psutil itself can fail during enumeration if a process exits between
        # snapshots. Fall through to the bounded CIM observer.
        pass
    # psutil absent (the 2026-08-10 reality) -> reliable CIM fallback.
    # NB single-quoted Where-Object (no nested double quotes) — the old
    # `-Filter "Name='python.exe'..."` form is mangled by PowerShell -> 0 procs.
    # B2-352 2026-09-26: bare "powershell" is not on PATH in every launch
    # context (disease class sig run_shell:e566037def80 "[Errno 2] ... powershell",
    # 7,964 FKB rows since 2026-09-19; this site swallowed the same FileNotFoundError
    # into except:pass, a blind observer). Resolve the full path; System32 fallback
    # when PATH lookup misses (pattern mag/process_reaper.py:82-90).
    ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not ps_exe and sys.platform == "win32":
        ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not ps_exe:
        return out
    try:
        r = subprocess.run([ps_exe, "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process | "
                            "Where-Object { $_.Name -in @('python.exe','pythonw.exe') } | "
                            "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
                            "ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        data = json.loads(r.stdout.strip())
        if isinstance(data, dict):
            data = [data]
        for p in data or []:
            out.append({"pid": p.get("ProcessId"), "ppid": p.get("ParentProcessId"),
                        "name": p.get("Name"), "cmd": (p.get("CommandLine") or "")[:400],
                        "env": {}})
    except Exception:
        pass
    return out


def _cmd_invariant(cmd: str) -> str:
    """Stable process-identity invariant: the command tail after the interpreter.

    The venv shim (`...\\.venv\\Scripts\\python.exe -m backend.server ...`) and its
    uv-cpython child (`"C:\\...\\uv\\python\\...\\python.exe" -m backend.server ...`)
    share this invariant — they are ONE logical process (one flock). The shim cmd is
    UNQUOTED, the uv child QUOTED (a real mismatch that made earlier dedup never fire),
    so we strip quotes and collapse whitespace to make them equal. This is the
    flock_field invariant-identity contract applied to process records.
    """
    c = (cmd or "").strip()
    for token in ("pythonw.exe", "python.exe"):
        i = c.lower().rfind(token)
        if i != -1:
            c = c[i + len(token):]
            break
    c = c.strip().strip('"').strip("'").strip()
    return " ".join(c.split())


def dedupe_uv_pairs(procs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse the Windows venv-shim -> uv-cpython pair into ONE logical process.

    FLOCKING DEDUP (2026-08-10): group by the normalized command invariant.
    This observer must remain deterministic and $0; invoking the flock
    scheduler here used to call Ollama over HTTP for every process and could
    hold sensing for 30+ seconds. Within an exact-invariant group, collapse
    ONLY the strict 1:1 parent->single-child twin (venv shim -> uv child). Real
    sibling duplicates (a respawner spawning N identical children) have NO such
    1:1 lineage and are KEPT, so a genuine storm stays visible.
    """
    if not procs:
        return procs
    invs = [_cmd_invariant(p.get("cmd") or "") for p in procs]
    groups_by_invariant: dict[str, list[int]] = {}
    for i, invariant in enumerate(invs):
        # An unavailable/denied command line is not evidence of identity.
        if invariant:
            groups_by_invariant.setdefault(invariant, []).append(i)
    children_of: dict[int, list[dict[str, Any]]] = {}
    for p in procs:
        children_of.setdefault(p.get("ppid"), []).append(p)
    twins: set[int] = set()
    for g in groups_by_invariant.values():
        cluster = [procs[i] for i in g]
        cby = {p["pid"]: p for p in cluster}
        for p in cluster:
            kids = [k for k in (children_of.get(p["pid"]) or []) if k["pid"] in cby]
            if (len(kids) == 1
                    and _cmd_invariant(kids[0].get("cmd") or "") == _cmd_invariant(p.get("cmd") or "")):
                twins.add(kids[0]["pid"])
    return [p for p in procs if p["pid"] not in twins]


def trace_source(pid: int, procs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Walk the ppid ancestry of `pid` up to the root spawner.

    Returns a list leaf->root: [{"pid","name","cmd","slot"}, ...]. Empty if pid
    not found or already a root (no parent in the python set / parent exited).
    """
    procs = procs if procs is not None else _enum()
    by_pid = {p["pid"]: p for p in procs}
    chain: list[dict[str, Any]] = []
    cur = pid
    seen: set[int] = set()
    # Also allow the root to be a non-python parent (cmd.exe boot), so we need
    # one extra lookup beyond the python set to name the boot script.
    while cur and cur not in seen:
        seen.add(cur)
        p = by_pid.get(cur)
        if p is None:
            break
        chain.append({"pid": p["pid"], "name": p["name"], "cmd": p["cmd"],
                      "slot": _slot_of(p["cmd"]), "boot": _boot_of(p["cmd"])})
        cur = p.get("ppid")
    return chain


def _root_source(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """The top-most spawner in an ancestry chain (the SOURCE)."""
    if not chain:
        return {}
    root = chain[-1]
    boot = next((c["boot"] for c in chain if c["boot"]), "")
    return {"root_pid": root["pid"], "root_cmd": root["cmd"], "boot": boot}


def _windowed_hint(p: dict[str, Any]) -> bool:
    """Heuristic: a python.exe (not pythonw) child of a console host = windowed."""
    if "pythonw" in (p.get("name") or "").lower():
        return False
    # venv shim / uv cpython are console apps; if spawned with CREATE_NO_WINDOW
    # they're hidden, but a top-level `python ...` from a cmd boot is windowed.
    return True


def sense() -> dict[str, Any]:
    """Detect runaway python AND trace each runaway to its SOURCE. Read-only."""
    procs = dedupe_uv_pairs(_enum())
    if not procs:
        return {"schema": SCHEMA, "ts": _now(), "verdict": "clean", "python_count": 0,
                "evidence": "no python processes running"}
    by_slot = defaultdict(list)
    for p in procs:
        by_slot[_slot_of(p["cmd"])].append(p)

    # 1) duplicate singleton slots (healthy = exactly 1 each)
    dup: list[dict[str, Any]] = []
    for slot, group in by_slot.items():
        if slot in SINGLETON_SLOTS and len(group) > 1:
            chain = trace_source(group[0]["pid"], procs)
            dup.append({
                "slot": slot, "count": len(group),
                "pids": [g["pid"] for g in group],
                "source": _root_source(chain),
                "chain": chain,
            })

    # 2) one parent spawning many framework children (runaway cascade)
    by_ppid: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for p in procs:
        by_ppid[p.get("ppid")].append(p)
    cascade: list[dict[str, Any]] = []
    for ppid, kids in by_ppid.items():
        if len(kids) >= RUN_AWAY_CHILD_COUNT:
            cascade.append({"parent_pid": ppid, "count": len(kids),
                            "pids": [k["pid"] for k in kids]})

    # 3) multi-boot: >1 distinct top-level supervisor (mag_launch / power start).
    #    Each independent boot spawns its OWN mag_launch supervisor, so counting
    #    supervisors is the TRUE multi-boot signal (counting 'root_pid of every proc'
    #    mis-counts one healthy stack under a single boot shell as N roots).
    boot_count = sum(len(by_slot.get(s, [])) for s in ("mag_launch", "power_boot"))
    multi_boot = boot_count > 1

    runaway = bool(dup or cascade)
    verdict = "runaway" if runaway else ("multi_boot" if multi_boot else "clean")
    evidence_parts = []
    if dup:
        for d in dup:
            src = d["source"]
            boot = f" via {src['boot']}" if src.get("boot") else ""
            evidence_parts.append(
                f"{d['count']}x slot '{d['slot']}' (pids {d['pids']}) sourced from "
                f"{src.get('root_cmd','?')} pid {src.get('root_pid')}{boot}")
    if cascade:
        evidence_parts.append(
            f"parent {cascade[0]['parent_pid']} spawned {cascade[0]['count']} framework children")
    if multi_boot:
        evidence_parts.append(f"{boot_count} mag_launch/power supervisors = multi-boot stacking")

    return {
        "schema": SCHEMA, "ts": _now(), "verdict": verdict,
        "python_count": len(procs),
        "slots": {k: len(v) for k, v in by_slot.items()},
        "duplicates": dup, "cascade": cascade, "multi_boot": multi_boot,
        "evidence": "; ".join(evidence_parts) or "no runaway detected",
        "windowed_hint": sum(1 for p in procs if _windowed_hint(p)),
    }


def break_source(source_pid: int, *, live: bool = False, dry: bool = True) -> dict[str, Any]:
    """Kill a source tree (taskkill /T /F on the root). Dry by default.

    `source_pid` is the ROOT of the runaway chain (from sense().duplicates[].source
    .root_pid or trace_source(pid)[-1].pid). /T kills the whole descendant tree.
    """
    if live:
        dry = False
    if dry:
        return {"schema": SCHEMA, "ts": _now(), "ok": True, "action": "break_source",
                "dry": True, "source_pid": source_pid,
                "reason": "dry run — would taskkill /PID <pid> /T /F the whole source tree"}
    try:
        r = subprocess.run(["taskkill", "/PID", str(source_pid), "/T", "/F"],
                           capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        return {"schema": SCHEMA, "ts": _now(), "ok": r.returncode == 0, "action": "break_source",
                "dry": False, "source_pid": source_pid,
                "detail": (r.stdout or r.stderr or "").strip()[:200]}
    except Exception as e:
        return {"schema": SCHEMA, "ts": _now(), "ok": False, "action": "break_source",
                "dry": False, "source_pid": source_pid, "error": str(e)[:160]}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "trace" and len(argv) >= 2:
        chain = trace_source(int(argv[1]))
        print(json.dumps(chain, indent=2, ensure_ascii=False, default=str))
    elif argv and argv[0] == "break" and len(argv) >= 2:
        live = "--live" in argv
        print(json.dumps(break_source(int(argv[1]), live=live), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(sense(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
