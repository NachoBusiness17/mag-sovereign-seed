"""legacy_audit — catalog + retire leftover/legacy Mag processes.

Systematic governance of "leftover" processes. Instead of one-off kills, this:
  1. Enumerates every running Mag python process (host + tracked).
  2. Classifies each against the KNOWN system map: current | legacy | orphan | test_leak.
  3. Catalogs the mapping to its NEWER replacement (e.g. host autorun -> container brain),
     and the action: retire | research | keep.
  4. Retires (stops) the legacy ones via the framework, and flags unclassified for research.

Design rules (per doctrine): deterministic, $0, no LLM. scan/catalog are report-only and
SAFE. retire() mutates but only stops processes classified `legacy` (explicit action).
research() persists unclassified/uncertain procs for a follow-up (never auto-retires).

The "newer system" map is data-driven: a host `autorun_loop` is LEGACY only when a newer
brain exists (container MAG_DRAINER=1 OR a single tracked supervisor loop). `current()`
reads container + process_supervisor state to decide.

Schema: legacy_audit.v1
CLI:  python -m mag.legacy_audit scan|catalog|retire|research
REST: GET  /api/v1/legacy            (catalog, report-only)
      POST /api/v1/legacy {action: retire|research}
"""
from __future__ import annotations

import json
import shutil
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

SCHEMA = "legacy_audit.v1"
CATALOG_DIR = ROOT / "memory" / "runs" / "legacy_audit"
CATALOG = CATALOG_DIR / "catalog.jsonl"

# Known Mag process signatures -> newer replacement + default action.
# `newer` is what replaces it if it's legacy; `current` is resolved dynamically.
REGISTRY: list[dict[str, Any]] = [
    {
        "name": "host_autorun_loop",
        "pattern": "governor_autorun import autorun_loop",
        "newer": "container brain (mag-sovereign, MAG_DRAINER=1) OR the single tracked supervisor loop",
        "default_action": "retire",
        "note": "A host drainer. Legacy when a newer brain owns draining (double-drain guard).",
    },
    {
        "name": "mag_launch_supervisor",
        "pattern": "mag_launch.py",
        "newer": "container entrypoint (scripts/container/entrypoint.sh -> mag_launch)",
        "default_action": "retire",
        "note": "Host mag_launch stack; superseded by the containerized supervisor.",
    },
    {
        "name": "backend_server",
        "pattern": "backend.server",
        "newer": "container backend :8000",
        "default_action": "retire",
        "note": "Host backend; the container serves it.",
    },
    {
        "name": "host_dashboard",
        "pattern": "main.py dashboard",
        "newer": "container dashboard :8765",
        "default_action": "retire",
        "note": "Host dashboard; the container serves it.",
    },
    {
        "name": "synthesis_scribe",
        "pattern": "synthesis_agent",
        "newer": "container scribe slot",
        "default_action": "retire",
        "note": "Host scribe; part of the mag_launch stack.",
    },
    {
        "name": "ghost_daemon",
        "pattern": "ghost --daemon",
        "newer": "ghost (current — intent/summon layer)",
        "default_action": "keep",
        "note": "Ghost is the current summon/intent layer; keep unless a newer host owns :9000.",
    },
    {
        "name": "ghost_cycle",
        "pattern": "from mag.ghost import cycle",
        "newer": "ghost_daemon",
        "default_action": "retire",
        "note": "Ad-hoc host ghost cycle loop; prefer the supervised ghost daemon.",
    },
    {
        "name": "legacy_mag_loop",
        "pattern": "from mag.daemon import run_loop",
        "newer": "ghost daemon sense family (sense/sense_context/sense_surfaces/sense_session/sense_copilot)",
        "default_action": "retire",
        "note": "Legacy mag sense->judge->act loop (main.py mag -> mag.daemon -> mag.sense). Not in mag_launch slots; superseded by the ghost daemon control plane (:9000).",
    },
    {
        "name": "pytest_runner",
        "pattern": "run_pytest_script.py",
        "newer": "(test tooling — do not retire)",
        "default_action": "research",
        "note": "VS Code pytest runner. NOT a framework process; left alone but flagged if it leaks loops.",
    },
    {
        "name": "orchestrator_seat",
        "pattern": "main.py agent",
        "newer": "(task subprocess — spawned, not legacy)",
        "default_action": "keep",
        "note": "A spawned agent task subprocess; retire only via task supervision, not here.",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


import time as _time
_BRAIN_CACHE: dict[str, Any] = {"ts": 0.0, "container": False, "sup_pids": set()}


def _refresh_brain() -> None:
    """Cache brain + supervisor probes for ~20s so scan/retire stay fast (no per-proc docker/netstat)."""
    if _time.time() - _BRAIN_CACHE["ts"] < 20:
        return
    _BRAIN_CACHE["ts"] = _time.time()
    _BRAIN_CACHE["container"] = _brain_is_container()
    try:
        _BRAIN_CACHE["sup_pids"] = _supervisor_tracked_pids()
    except Exception:
        _BRAIN_CACHE["sup_pids"] = set()


def _brain_is_container() -> bool:
    """True when the container is the intended drainer brain (MAG_DRAINER=1 + container up)."""
    try:
        from mag.docker_ops import status as dstatus
        d = dstatus()
        return bool(d.get("cutover_ready")) or bool(d.get("containers"))
    except Exception:
        return False


def _supervisor_tracked_pids() -> set[int]:
    """Pids the process_supervisor currently tracks as running."""
    try:
        from mag.process_supervisor import status as pstatus
        p = pstatus()
        return {int(l["pid"]) for l in p.get("loops", []) if l.get("running") and l.get("pid")}
    except Exception:
        return set()


def _enum_procs() -> list[dict[str, Any]]:
    """Enumerate running Mag python processes (host). psutil preferred, else PowerShell."""
    out: list[dict[str, Any]] = []
    try:
        import psutil  # type: ignore
        for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "local_sovereign_agent" not in cmd and not any(
                        t in cmd for t in ("mag.", "mag_", "main.py", "backend", "dashboard",
                                           "ghost", "autorun", "governor", "orchestrator",
                                           "synthesis_agent", "mag_launch")):
                    continue
                out.append({"pid": proc.info["pid"], "ppid": proc.info.get("ppid"),
                            "name": proc.info["name"], "cmd": cmd[:400]})
            except Exception:
                continue
    except ImportError:
        import subprocess
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
                            "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        try:
            import json as _j
            data = _j.loads(r.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            for p in data or []:
                out.append({"pid": p.get("ProcessId"), "ppid": p.get("ParentProcessId"),
                            "name": p.get("Name"), "cmd": (p.get("CommandLine") or "")[:400]})
        except Exception:
            pass
    return out


def classify(proc: dict[str, Any]) -> dict[str, Any]:
    """Classify a process: current | legacy | orphan | test_leak | unknown."""
    cmd = proc.get("cmd") or ""
    _refresh_brain()
    tracked = _BRAIN_CACHE["sup_pids"]
    container_brain = _BRAIN_CACHE["container"]
    hit = next((r for r in REGISTRY if r["pattern"] in cmd), None)
    pid = proc.get("pid")
    if pid in tracked:
        return {"name": hit["name"] if hit else "tracked_loop", "class": "current",
                "action": "keep", "newer": "(tracked by process_supervisor)", "note": "tracked running loop"}
    if hit and hit["name"] == "pytest_runner":
        return {"name": "pytest_runner", "class": "test_leak", "action": "research",
                "newer": hit["newer"], "note": hit["note"]}
    if hit:
        # host autorun / mag_launch / backend / dashboard are legacy when a container brain owns them
        if hit["name"] == "host_autorun_loop":
            legacy = container_brain
        elif hit["name"] in ("mag_launch_supervisor", "backend_server", "host_dashboard", "synthesis_scribe", "ghost_cycle"):
            legacy = container_brain
        else:
            legacy = False
        return {"name": hit["name"], "class": "legacy" if legacy else "current",
                "action": hit["default_action"] if legacy else "keep",
                "newer": hit["newer"], "note": hit["note"]}
    # unclassified but mag-looking
    return {"name": "unknown", "class": "orphan" if not container_brain else "unknown",
            "action": "research", "newer": "?", "note": "unclassified mag process — flag for research"}


def scan() -> dict[str, Any]:
    """Enumerate + classify every running Mag process (report-only)."""
    procs = _enum_procs()
    items = []
    for p in procs:
        c = classify(p)
        items.append({"pid": p["pid"], "ppid": p["ppid"], "name": p["name"],
                      "cmd": p["cmd"][:120], **c})
    legacy = [i for i in items if i["class"] == "legacy"]
    research = [i for i in items if i["action"] == "research"]
    return {
        "schema": SCHEMA, "ts": _now(), "ok": True,
        "brain": {"container": _brain_is_container(),
                  "supervisor_pids": sorted(_supervisor_tracked_pids())},
        "total": len(items),
        "by_class": {k: sum(1 for i in items if i["class"] == k)
                     for k in ("current", "legacy", "orphan", "test_leak", "unknown")},
        "processes": items,
        "legacy_count": len(legacy), "research_count": len(research),
    }


def catalog() -> dict[str, Any]:
    """Persist the scan to CATALOG + return it (report-only)."""
    s = scan()
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CATALOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": s["ts"], "legacy": s["legacy_count"],
                            "research": s["research_count"], "procs": s["processes"]},
                           ensure_ascii=False, default=str) + "\n")
    s["catalog_path"] = str(CATALOG)
    return s


def retire(*, dry: bool = False) -> dict[str, Any]:
    """Stop processes classified `legacy` (explicit action). Never touches current/test/unknown."""
    s = scan()
    stopped = []
    errors = []
    for i in s["processes"]:
        if i["class"] != "legacy":
            continue
        if dry:
            stopped.append({"pid": i["pid"], "name": i["name"], "dry": True})
            continue
        try:
            import subprocess
            import os
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(i["pid"]), "/T", "/F"],
                               capture_output=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
            else:
                import signal
                os.kill(i["pid"], signal.SIGKILL)
            stopped.append({"pid": i["pid"], "name": i["name"], "dry": False})
        except Exception as e:
            errors.append({"pid": i["pid"], "name": i["name"], "error": str(e)[:120]})
    return {"schema": SCHEMA, "ts": _now(), "ok": True, "dry": dry,
            "stopped": stopped, "errors": errors, "stopped_count": len(stopped)}


def research() -> dict[str, Any]:
    """Flag unclassified / test-leak / unknown procs for a follow-up (never retires)."""
    s = scan()
    flagged = [i for i in s["processes"] if i["action"] == "research"]
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    research_file = CATALOG_DIR / "research.jsonl"
    with open(research_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": s["ts"], "flagged": flagged}, ensure_ascii=False, default=str) + "\n")
    return {"schema": SCHEMA, "ts": _now(), "ok": True,
            "flagged": flagged, "flagged_count": len(flagged),
            "research_path": str(research_file)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "catalog").lower()
    dry = "--dry" in argv
    if cmd == "scan":
        print(json.dumps(scan(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "retire":
        print(json.dumps(retire(dry=dry), indent=2, ensure_ascii=False, default=str))
    elif cmd == "research":
        print(json.dumps(research(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(catalog(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
