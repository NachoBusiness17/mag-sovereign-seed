"""loop_breaker — ghost lesson: detect a crash-respawn LOOP vs genuine strain, and break it.

The 2026-08-09 incident: a broken process (main.py SyntaxError) made the supervisor respawn
dashboard/lab/drainer every ~5s; each spawn also leaked to desktop windows. Ghost should have
recognized this as an INFINITE LOOP from a simple broken process, not genuine system load, and
broken the respawner.

This module gives ghost that discrimination, deterministically:
  * LOOP (crash_respawn): many concurrent processes with the SAME cmdline (a healthy system has
    1, not 5+), or a supervisor respawning a process that exits rc!=0 within a short window.
  * GENUINE STRAIN: a few healthy processes using CPU — we NEVER touch those.

detect()  -> {verdict: none|crash_loop|strain, cmd, procs, evidence}
break_loop(dry) -> kill the offending processes + their respawner (parent), never genuine work.

Schema: loop_breaker.v1
CLI: python -m mag.loop_breaker [--dry]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
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

SCHEMA = "loop_breaker.v1"
# Same-cmd concurrent count above this = a respawn storm, not a healthy single process.
LOOP_CONCURRENCY = 4
# A single PARENT spawning this many framework-owned python children = a runaway-spawner
# cascade (the 2026-08-09 case: a respawner parent spawning duplicate daemons/loops).
# A healthy supervisor has ~2-4 children (autorun+ghost, each venv->uv); >= this is a cascade.
RUN_AWAY_CHILD_COUNT = 6
# A process younger than this (seconds) that's one of many same-cmd = short-lived respawn.
SHORT_LIFETIME_S = 30.0
# Process cmdlines we consider framework-owned (and thus a candidate broken loop).
_MAG = (
    "autorun_loop", "main.py dashboard", "main.py lab", "orchestrator drain",
    "backend.server", "mag.ghost", "synthesis_agent", "mag_launch", "main.py agent",
    "main.py autorun", "seat_guard",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize(cmd: str) -> str:
    """Normalize a cmdline to a stable signature (strip pids/ports that vary per instance)."""
    c = cmd
    c = re.sub(r"\b\d{5,}\b", "<PID>", c)          # pids
    c = re.sub(r"--port\s+\d+", "--port <P>", c)   # ports
    c = re.sub(r"--id\s+\S+", "--id <ID>", c)
    return c.strip()


def _enum() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        import psutil  # type: ignore
        import time as _t
        from mag.source_trace import _bounded_process_call

        # Do not use process_iter(attrs=...) here. One protected Windows PID
        # can make psutil materialize create_time/cmdline before yielding and
        # block the loop breaker. Optional fields are independently bounded.
        for proc in psutil.process_iter():
            try:
                name_value = proc.name()
                name = (name_value or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = " ".join(_bounded_process_call(proc.cmdline, default=[]) or [])
                if not any(m in cmd for m in _MAG) or "loop_breaker" in cmd:
                    continue
                ppid = _bounded_process_call(proc.ppid, default=None)
                created = _bounded_process_call(proc.create_time, default=None)
                out.append({"pid": proc.pid, "ppid": ppid,
                            "cmd": cmd[:300], "sig": _normalize(cmd),
                            "age_s": round(_t.time() - (created or _t.time()))})
            except Exception:
                continue
    except ImportError:
        import subprocess
        # NB: use Where-Object with single quotes (NO embedded double quotes) — the old
        # `-Filter "Name='python.exe'..."` nested-quote form is mangled when PowerShell
        # receives it as a subprocess arg on Windows, silently returning 0 procs, which is
        # exactly why ghost could never SEE the duplicate-brain storm it must break.
        # B2-85 2026-09-26: bare "powershell" is not on PATH in every launch
        # context (sig run_shell:e566037def80 "[Errno 2] ... powershell",
        # 7,964 FKB rows since 2026-09-19). Resolve the full path; System32
        # fallback when PATH lookup misses (pattern mag/process_reaper.py).
        ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
        if not ps_exe and sys.platform == "win32":
            ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if not ps_exe:
            return out
        r = subprocess.run([ps_exe, "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process | "
                            "Where-Object { $_.Name -in @('python.exe','pythonw.exe') } | "
                            "Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | "
                            "ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        try:
            import time as _t
            data = json.loads(r.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            for p in data or []:
                cmd = (p.get("CommandLine") or "")
                if not any(m in cmd for m in _MAG) or "loop_breaker" in cmd:
                    continue
                age = 0
                try:
                    age = round(_t.time() - datetime.fromisoformat(str(p.get("CreationDate"))).timestamp())
                except Exception:
                    pass
                out.append({"pid": p.get("ProcessId"), "ppid": p.get("ParentProcessId"),
                            "cmd": cmd[:300], "sig": _normalize(cmd), "age_s": age})
        except Exception:
            pass
    return out


def detect() -> dict[str, Any]:
    """Return verdict: none | crash_loop | strain. LOOP if a same-cmd group is huge/short-lived."""
    # Dedup the Windows venv-shim -> uv-cpython pair (one logical process per slot) so a
    # HEALTHY single stack is never misread as a 2x-duplicate storm (2026-08-10 false alarm).
    try:
        from mag.source_trace import dedupe_uv_pairs
        procs = dedupe_uv_pairs(_enum())
    except Exception:
        procs = _enum()
    if not procs:
        return {"schema": SCHEMA, "ts": _now(), "verdict": "none", "procs": 0,
                "evidence": "no framework processes running"}
    by_sig: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in procs:
        by_sig[p["sig"]].append(p)

    candidates = []
    for sig, group in by_sig.items():
        # A framework SINGLETON loop (autorun_loop / ghost cycle) must have EXACTLY ONE
        # instance — ANY duplicate (>=2) is a duplicate-brains storm, even if all are
        # long-lived (2026-08-09 window-storm + the 2026-08-10 ghost-daemon spawning 2
        # autorun_loops). The old >= LOOP_CONCURRENCY(4) guard made ghost blind to a
        # 2-way duplicate crash-loop — the operator saw this for three days. Lowered.
        singleton = any(m in sig for m in ("autorun_loop", "from mag.ghost import cycle"))
        dup_cap = 2 if singleton else LOOP_CONCURRENCY
        if len(group) < dup_cap:
            continue
        young = [g for g in group if g.get("age_s", 999) < SHORT_LIFETIME_S]
        # a storm = many same-cmd AND most are short-lived (spinning), OR simply too many,
        # OR a duplicate singleton (>=2 identical singleton loops is ALWAYS a storm).
        storm = len(group) >= dup_cap and (
            len(young) >= 2 or len(group) >= LOOP_CONCURRENCY * 2 or singleton
        )
        if storm:
            candidates.append({
                "sig": sig, "count": len(group), "young": len(young),
                "pids": [g["pid"] for g in group],
                "cmd_sample": group[0]["cmd"][:160],
            })
    # Runaway-spawner cascade: one PARENT spawning many framework children. A healthy
    # supervisor has 2-4; >= RUN_AWAY_CHILD_COUNT under one parent = a cascade. Ghost must
    # break the PARENT tree (taskkill /T on the spawner kills all its children).
    by_ppid: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for p in procs:
        by_ppid[p.get("ppid")].append(p)
    for ppid, kids in by_ppid.items():
        if len(kids) >= RUN_AWAY_CHILD_COUNT:
            candidates.append({
                "kind": "spawner_cascade", "ppid": ppid, "count": len(kids),
                "pids": [k["pid"] for k in kids],
                "cmd_sample": kids[0]["cmd"][:160],
            })
    if candidates:
        top = max(candidates, key=lambda c: c["count"])
        kind = top.get("kind", "duplicate_cmdline")
        detail = (f"{top['count']} concurrent identical-cmd processes = respawn storm" if kind != "spawner_cascade"
                  else f"parent {top['ppid']} spawned {top['count']} framework children = runaway-spawner cascade")
        return {"schema": SCHEMA, "ts": _now(), "verdict": "crash_loop",
                "procs": len(procs), "loop": top, "candidates": candidates,
                "evidence": f"{detail}; NOT genuine load — ghost breaks it."}
    return {"schema": SCHEMA, "ts": _now(), "verdict": "strain" if len(procs) >= 2 else "none",
            "procs": len(procs), "evidence": "few healthy processes = genuine work; leave alone."}


def break_loop(*, dry: bool = False) -> dict[str, Any]:
    """If a crash_loop is detected, kill the offending processes AND their respawners."""
    import os
    import subprocess

    d = detect()
    if d["verdict"] != "crash_loop":
        return {"schema": SCHEMA, "ts": _now(), "ok": True, "action": "none",
                "verdict": d["verdict"], "reason": d["evidence"]}
    pids = set(d["loop"]["pids"])
    # include respawner parents (the supervisor that keeps respawning)
    for p in _enum():
        if p["pid"] in pids and p.get("ppid"):
            pids.add(p["ppid"])
    # SOURCE TRACE (steal 2026-08-10): report WHERE the storm came from, not
    # just that it exists — walk the ancestry to the root spawner.
    source: dict[str, Any] = {}
    try:
        from mag.source_trace import trace_source
        chain = trace_source(d["loop"]["pids"][0])
        if chain:
            src = chain[-1]
            source = {"root_pid": src["pid"], "root_cmd": src["cmd"]}
    except Exception:
        pass
    killed = []
    for pid in sorted(pids):
        if dry:
            killed.append({"pid": pid, "dry": True})
            continue
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
            else:
                import signal
                os.kill(pid, signal.SIGKILL)
            killed.append({"pid": pid, "dry": False})
        except Exception as e:
            killed.append({"pid": pid, "error": str(e)[:80]})
    return {"schema": SCHEMA, "ts": _now(), "ok": True, "action": "break_loop",
            "verdict": "crash_loop", "dry": dry, "killed": killed, "killed_count": len(killed),
            "reason": d["evidence"], "source": source}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry" in argv
    if argv and argv[0] == "break":
        print(json.dumps(break_loop(dry=dry), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(detect(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
