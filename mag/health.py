"""Sanity map: is Mag integral alive, what froze, how to reconnect.

Not vibes — file ages, heartbeat, Ollama ping, optional L1/L2 probes.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from mag.win_powershell import powershell_exe
from pathlib import Path
from typing import Any

from config import ROOT, ollama_base

# Default install is the Docker cage (CONTAINER.md). Host `python main.py lab`
# is last-resort disposable-dev soil — a second supervisor if mag-sovereign is up.
# mag.cmd doctor is the first grab: host venv READ of the body. It does not spawn lab.
# mag_exec needs Docker engine + (on Windows) ExecutionPolicy Bypass; many seats have neither.
HOST_DOCTOR = "mag.cmd doctor"
CAGE_DOCTOR = (
    powershell_exe() + r" -NoProfile -ExecutionPolicy Bypass -File scripts\mag_exec.ps1 doctor"
)
CAGE_RESTORE = "docker compose restart mag"
HOST_LAB_LAST = (
    "python main.py lab  # LAST RESORT. CONTAINER.md disposable-dev only. "
    "Second supervisor if mag-sovereign is up — do not grab this first."
)


def in_mag_cage() -> bool:
    return os.environ.get("MAG_CONTAINER") == "1"


def reconnect_plan() -> dict[str, Any]:
    """What seats should grab first when Mag looks down. Cage, not legacy host lab."""
    if in_mag_cage():
        first = "already in mag-sovereign — FILE; host: mag.cmd doctor then docker compose restart mag"
        command = HOST_DOCTOR
    else:
        first = HOST_DOCTOR
        command = HOST_DOCTOR
    return {
        "first": first,
        "command": command,
        "cli": HOST_DOCTOR,
        "doctor": HOST_DOCTOR,
        "cage_cli": CAGE_DOCTOR,
        "if_dash_dead_and_docker": CAGE_RESTORE,
        "catch_up": "mag.cmd catch-up",
        "probe": "mag.cmd probe-lanes",
        "legacy_last_resort": HOST_LAB_LAST,
        "law": (
            "One supervisor. Mag lives in mag-sovereign. "
            "mag.cmd doctor reads the body (no spawn). "
            "mag_exec needs Docker; if npipe/ExecutionPolicy blocks, stay on mag.cmd. "
            "Host lab is last, not first."
        ),
        "stale_note": (
            "Heartbeat stale — cage lab slot may be wedged. First: mag.cmd doctor "
            f"(venv read, no spawn). If dash still dead AND docker works: {CAGE_RESTORE}. "
            "Do not run host python main.py lab (second supervisor). "
            "Do not wait on Docker access to FILE doctor."
        ),
        "commands": [HOST_DOCTOR, CAGE_RESTORE],
    }

BIO = ROOT / "memory" / "biography"
LIVE = ROOT / "memory" / "live_from_grok.md"
DIGEST = ROOT / "watch" / "session_digest.jsonl"
HEARTBEAT = ROOT / "watch" / "heartbeat.json"
PID_FILE = ROOT / "watch" / "mag.pid"
POINTER = ROOT / "watch" / "active_session.json"


def _age_seconds(path: Path) -> float | None:
    if not path.is_file():
        return None
    return datetime.now(timezone.utc).timestamp() - path.stat().st_mtime


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        # Windows-friendly: OpenProcess via os.kill(pid, 0) works on Unix;
        # on Windows, os.kill(pid, 0) raises OSError if gone in some versions
        if os.name == "nt":
            import ctypes

            k = ctypes.windll.kernel32
            handle = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                k.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _port_open(host: str = "127.0.0.1", port: int = 8765, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _bounded_call(fn: Any, *, timeout: float = 0.8, default: Any = None) -> Any:
    """Bound optional network/DNS observers even when socket timeouts do not."""
    done = threading.Event()
    box: list[Any] = []

    def _run() -> None:
        try:
            box.append(fn())
        except Exception:
            box.append(default)
        finally:
            done.set()

    threading.Thread(target=_run, name="health-probe", daemon=True).start()
    if not done.wait(max(0.1, float(timeout))):
        return default
    return box[0] if box else default


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    def _probe() -> bool:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300

    return bool(_bounded_call(_probe, timeout=min(float(timeout), 1.0), default=False))


def check_ollama() -> dict[str, Any]:
    try:
        # Reuse the registry's hard-bounded/cached observer. The old direct
        # urllib probe could stall on an unresolved Docker hostname.
        from models.registry import ollama_tags

        names = ollama_tags(timeout=0.8)
        return {
            "ok": bool(names),
            "models": names,
            "lane": "L0",
            **({} if names else {"note": "Ollama unavailable or no local models are loaded"}),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "lane": "L0"}


def check_openrouter() -> dict[str, Any]:
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OR_API_KEY")
    if not key:
        return {
            "ok": False,
            "configured": False,
            "lane": "L1",
            "note": "Set OPENROUTER_API_KEY to enable free/remote public lanes (T2+ only)",
        }
    # light auth check — list models is enough, no spend
    def _probe() -> bool:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=1.0) as r:
            return 200 <= r.status < 300

    ok = _bounded_call(_probe, timeout=1.0, default=False)
    return {"ok": bool(ok), "configured": True, "lane": "L1",
            **({} if ok else {"note": "OpenRouter probe unavailable or timed out"})}


def check_grok_harness() -> dict[str, Any]:
    try:
        from harness.grok_cli import harness_available

        avail = harness_available()
        return {
            "ok": avail,
            "lane": "L2",
            "note": "grok CLI on PATH" if avail else "grok CLI not found — file handoffs still work",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "lane": "L2"}


def gap_report() -> list[dict[str, str]]:
    """What freezes when Mag dies / what catches up on restart."""
    return [
        {
            "id": "live_board",
            "when_down": "memory/live_from_grok.md freezes — no new turn previews",
            "on_restart": "Watch offset catches up from chat_history.jsonl (no chat lost on disk)",
        },
        {
            "id": "live_amend",
            "when_down": "Open session .md/dossier not auto-amended mid-flight",
            "on_restart": "Mag cycle live_amend + SessionEnd hook rewrite same session id",
        },
        {
            "id": "brief_visual",
            "when_down": "No new brief/visual_pack until summarize/brief/cycle",
            "on_restart": "python main.py brief | visual or wait for mag cycle",
        },
        {
            "id": "companion",
            "when_down": "Todos [mag] not executed; L2 escalate blocked at source",
            "on_restart": "Queue still on disk — next cycle processes assigned work",
        },
        {
            "id": "not_lost",
            "when_down": "—",
            "on_restart": "Grok chat_history.jsonl, existing dossiers, Verkle leaves, ingest catalog remain",
        },
    ]


def sanity() -> dict[str, Any]:
    """Full map: integral, files, lanes, gaps."""
    from mag.runtime import read_heartbeat

    hb = read_heartbeat()
    pid = None
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None
    pid_ok = _pid_alive(pid) if pid else False
    port_ok = _port_open()
    board_ok = _http_ok("http://127.0.0.1:8765/api/board") if port_ok else False
    backend_port_ok = _port_open(port=8000)
    backend_ok = _http_ok("http://127.0.0.1:8000/health") if backend_port_ok else False

    live_age = _age_seconds(LIVE)
    digest_age = _age_seconds(DIGEST)
    hb_age = hb.get("age_seconds")

    # stale thresholds
    live_stale = live_age is None or live_age > 120
    integral_up = bool(hb.get("alive")) and pid_ok
    # port alone is weak (zombie); prefer heartbeat+pid
    status = "up" if integral_up and port_ok else ("degraded" if port_ok or pid_ok else "down")

    missing: list[str] = []
    if not integral_up:
        missing.append("integral Mag process (watch+companion heartbeat)")
    if live_stale:
        missing.append(f"fresh live board (age={None if live_age is None else round(live_age)}s)")
    if not port_ok:
        missing.append("dashboard :8765")
    if not backend_ok:
        missing.append("tool backend :8000")

    pointer = None
    if POINTER.is_file():
        try:
            pointer = json.loads(POINTER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pointer = None

    ollama = check_ollama()
    orouter = check_openrouter()
    grok = check_grok_harness()

    return {
        "ok": status == "up",
        "status": status,
        "ts": datetime.now(timezone.utc).isoformat(),
        "integral": {
            "heartbeat": hb,
            "pid": pid,
            "pid_alive": pid_ok,
            "port_8765": port_ok,
            "board_api": board_ok,
            "port_8000": backend_port_ok,
            "backend_api": backend_ok,
            "up": integral_up,
        },
        "recording": {
            "live_age_seconds": live_age,
            "live_stale": live_stale,
            "digest_age_seconds": digest_age,
            "active_session": pointer,
            "has_latest_dossier": (BIO / "latest.dossier.json").is_file(),
            "has_visual_pack": (BIO / "latest.visual_pack.json").is_file(),
            "has_brief": (ROOT / "memory" / "briefs" / "latest.md").is_file(),
        },
        "lanes": {
            "L0_ollama": ollama,
            "L1_openrouter": orouter,
            "L2_grok": grok,
        },
        "missing_while_down": missing,
        "gaps": gap_report(),
        "reconnect": reconnect_plan(),
        "hallucination_guard": {
            "rule": "Trust file ages + probe results, not model claims about being online",
            "tests": [
                "doctor → status up + live not stale",
                "probe-lanes → L0 chat roundtrip",
                "brief/visual commit changes only when dossier inputs change",
            ],
        },
    }


def catch_up() -> dict[str, Any]:
    """After reconnect: refresh live board, amend open session, rebuild brief/visual lightly."""
    out: dict[str, Any] = {"ok": True, "steps": []}
    try:
        from watch.tail_session import once

        once()
        out["steps"].append({"watch": "ok"})
    except Exception as e:
        out["steps"].append({"watch": "error", "error": str(e)})
        out["ok"] = False

    try:
        from mag.biography import summarize_session
        from watch.tail_session import resolve_session

        resolved = resolve_session()
        if resolved:
            sid = resolved[0]
            res = summarize_session(sid, use_llm=False, force=False, amend=True, pdf=False)
            out["steps"].append({"live_amend": res})
        else:
            out["steps"].append({"live_amend": "no active session"})
    except Exception as e:
        out["steps"].append({"live_amend": "error", "error": str(e)})

    # Mag agent seats file into the same workday / Verkle leaf system
    try:
        from mag.chat_source import file_dirty_agent_sessions

        ar = file_dirty_agent_sessions(use_llm=False, force=False)
        out["steps"].append({"agent_workdays": ar})
    except Exception as e:
        out["steps"].append({"agent_workdays": "error", "error": str(e)})

    # No visual export on catch-up — data layer only (export via POST /api/v1/export)
    out["steps"].append(
        {"visual": "skipped", "reason": "export_on_demand", "hint": "POST /api/v1/export"}
    )

    try:
        from mag.runtime import write_heartbeat

        write_heartbeat(status="catch_up", catch_up=True)
    except Exception:
        pass
    out["sanity"] = {k: sanity()[k] for k in ("status", "recording", "missing_while_down")}
    return out
