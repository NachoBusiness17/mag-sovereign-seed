"""Passive lifecycle — when each Mag piece should be on or off.

Goal: multi-system stack stays **passive by default** (token + CPU efficient).
Pieces wake on demand; expensive seats never idle-burn.

REST:
  GET  /api/v1/lifecycle           — policy + actual + mismatch
  POST /api/v1/lifecycle/reconcile — apply safe offs (never kills UI core)

Policy modes:
  always     — needed for local agent face (backend, dash, lab)
  demand     — on only when work exists
  opt_in     — operator/env toggle
  gated      — opt_in AND operator not blocking
  expensive  — remote/token seats: never "wanted on" at rest
  off        — intentionally disabled

t47 spec (2026-09-25): intentional-vs-silent disablement of MagImproveDaily.
The waste remediation for the "improve" piece (_waste_action) prescribes the
landed executor, not prose: python main.py improve-off --reason "..." /
improve-on (spec aligned by t77 to the t73 flow below). A deliberate disable
must be distinguishable from a silent one, so whoever executes that disable
leaves a marker file:

  logs/magimprove_intentional.flag   (JSON: {ts, reason, by})

mark_improve_intentional() is the single writer; improve_intentional() is the
reader. The doctor probe (mag/doctor.check_scheduled_tasks, t20) respects the
marker: Disabled + marker = intentional, no alarm; a MISSING task still
alarms even with the marker (disable is not delete).

t73 spec (2026-09-25): the deliberate-off flow is the in-repo executor of the
t47 prescription above, exposed as two main.py subcommands.

  improve-off --reason "..."   write marker FIRST, then
                               schtasks /Change /TN MagImproveDaily /Disable.
                               If the marker write fails, abort WITHOUT
                               disabling (fail closed: never a silent-disabled
                               state).
  improve-on                   re-register the task via
                               scripts/register_improve_task.ps1, then clear
                               the marker ONLY on success (if re-register
                               fails, the marker still explains the Disabled
                               state to the doctor probe).

Both return the marker write as a cited artifact ({path, payload}) in the
result JSON. improve_off()/improve_on() take an injectable _run hook so tests
mock the schtasks/powershell calls and never touch the live task.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import ROOT
from mag.win_powershell import powershell_exe

SCHEMA = "mag_lifecycle.v1"
LAUNCH_STATE = ROOT / "state" / "mag_launch.json"

# t47: marker that turns a Disabled MagImproveDaily from "silent" into
# "intentional". Written only by mark_improve_intentional(); read by the
# doctor probe. Lives under logs/ beside the other runtime traces.
IMPROVE_INTENTIONAL_FLAG = ROOT / "logs" / "magimprove_intentional.flag"


def improve_intentional_flag_path() -> Path:
    """Path of the intentional-disable marker (logs/magimprove_intentional.flag)."""
    return IMPROVE_INTENTIONAL_FLAG


def mark_improve_intentional(reason: str = "operator disable") -> dict[str, Any]:
    """Declare a MagImproveDaily disable deliberate (t47 spec above).

    Writes the marker BEFORE/alongside the disable so the doctor probe can
    tell intentional from silent. Returns {ok, path, payload|error}.
    """
    try:
        IMPROVE_INTENTIONAL_FLAG.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "reason": str(reason)[:200],
            "by": "mag.lifecycle.mark_improve_intentional",
        }
        IMPROVE_INTENTIONAL_FLAG.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return {"ok": True, "path": str(IMPROVE_INTENTIONAL_FLAG), "payload": payload}
    except Exception as exc:  # noqa: BLE001 marker write must never crash the caller
        return {"ok": False, "path": str(IMPROVE_INTENTIONAL_FLAG), "error": str(exc)[:120]}


def improve_intentional() -> dict[str, Any] | None:
    """Read the intentional-disable marker; None when absent/unreadable."""
    try:
        if not IMPROVE_INTENTIONAL_FLAG.is_file():
            return None
        return json.loads(IMPROVE_INTENTIONAL_FLAG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 unreadable marker means "not declared"
        return None


# t73: fixed names of the task + register script (mirrors
# scripts/register_improve_task.ps1 and the doctor probe in mag/doctor.py).
IMPROVE_TASK_NAME = "MagImproveDaily"
IMPROVE_REGISTER_SCRIPT = ROOT / "scripts" / "register_improve_task.ps1"

# Injectable task-command runner: tests pass a mock so the live schtask is
# never touched from a test (t73 law).
CmdRunner = Callable[[list[str]], dict[str, Any]]


def _run_cmd(cmd: list[str]) -> dict[str, Any]:
    """Default task-command runner: {ok, returncode, cmd, stdout, stderr}."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "cmd": " ".join(cmd),
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-2000:],
        }
    except Exception as exc:  # noqa: BLE001 scheduler failures must not crash
        return {
            "ok": False,
            "returncode": None,
            "cmd": " ".join(cmd),
            "error": str(exc)[:120],
        }


def clear_improve_intentional() -> dict[str, Any]:
    """Remove the intentional-disable marker (t73 improve-on, success path).

    Returns {ok, path, removed}; removal is idempotent (already-absent is ok).
    """
    try:
        existed = IMPROVE_INTENTIONAL_FLAG.is_file()
        if existed:
            IMPROVE_INTENTIONAL_FLAG.unlink()
        return {"ok": True, "path": str(IMPROVE_INTENTIONAL_FLAG), "removed": existed}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "path": str(IMPROVE_INTENTIONAL_FLAG),
            "removed": False,
            "error": str(exc)[:120],
        }


def improve_off(
    reason: str = "operator disable", _run: CmdRunner | None = None
) -> dict[str, Any]:
    """Deliberate-off flow (t73 spec in this module's docstring).

    Writes the marker FIRST (cited in the result), then disables the
    MagImproveDaily schtask. Marker write failure aborts WITHOUT disabling
    (fail closed: never a silent-disabled state). _run is the injectable
    task-command runner; default shells out to schtasks.
    """
    run: CmdRunner = _run or _run_cmd
    marker = mark_improve_intentional(reason)
    if not marker.get("ok"):
        return {
            "ok": False,
            "cmd": "improve-off",
            "marker": marker,
            "task": None,
            "error": "marker write failed; task NOT disabled (fail closed)",
        }
    task = run(["schtasks", "/Change", "/TN", IMPROVE_TASK_NAME, "/Disable"])
    return {"ok": bool(task.get("ok")), "cmd": "improve-off", "marker": marker, "task": task}


def improve_on(_run: CmdRunner | None = None) -> dict[str, Any]:
    """Deliberate-on flow (t73 spec): re-register MagImproveDaily via
    scripts/register_improve_task.ps1, then clear the marker ONLY on success
    (a failed re-register leaves the marker so the doctor probe still reads
    the Disabled state as intentional)."""
    run: CmdRunner = _run or _run_cmd
    task = run(
        [
            powershell_exe(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(IMPROVE_REGISTER_SCRIPT),
        ]
    )
    if not task.get("ok"):
        return {
            "ok": False,
            "cmd": "improve-on",
            "task": task,
            "marker_cleared": False,
            "error": "task re-register failed; marker kept (disable stays intentional)",
        }
    cleared = clear_improve_intentional()
    return {
        "ok": bool(cleared.get("ok")),
        "cmd": "improve-on",
        "task": task,
        "marker_cleared": cleared,
    }

# token_class: what burns when this piece is "on"
# local_free | local_gpu | scheduled | remote_tokens | interactive
PIECE_DEFS: list[dict[str, Any]] = [
    {
        "id": "backend",
        "label": "Tool backend :8000",
        "mode": "always",
        "token_class": "local_free",
        "why_on": "Local tool API for seats — no remote tokens",
        "why_off": "Seats cannot call tools",
    },
    {
        "id": "dashboard",
        "label": "Web UI :8765",
        "mode": "always",
        "token_class": "local_free",
        "why_on": "Operator face + REST control plane",
        "why_off": "No web interface / no REST",
    },
    {
        "id": "lab",
        "label": "Integral Mag (watch+companion)",
        "mode": "always",
        "token_class": "local_free",
        "why_on": "Heartbeat + live board; idle loop is cheap local",
        "why_off": "Doctor degraded; no catch-up",
    },
    {
        "id": "scribe",
        "label": "Scribe commentary",
        "mode": "demand",
        "token_class": "local_free",
        "why_on": "Session synthesis when work is moving",
        "why_off": "No active session writing needed",
    },
    {
        "id": "mirror",
        "label": "Mirror desk :8743",
        "mode": "opt_in",
        "token_class": "local_free",
        "why_on": "Strike / scaffold work",
        "why_off": "MAG_NO_MIRROR or no scaffold — save a process",
    },
    {
        "id": "drainer",
        "label": "Queue drainer / autorun",
        "mode": "gated",
        "token_class": "scheduled",
        "why_on": "Queue has work and operator not in IDE",
        "why_off": "Empty queue, operator coding, or toggle off — save tokens",
    },
    {
        "id": "engine",
        "label": "Auto engine seat",
        "mode": "opt_in",
        "token_class": "remote_tokens",
        "why_on": "MAG_ENGINE_CMD set for headless seat",
        "why_off": "Default: operator/Direct Mag is the engine",
    },
    {
        "id": "ollama",
        "label": "Ollama L0",
        "mode": "demand",
        "token_class": "local_gpu",
        "why_on": "Local seat call in flight or about to run",
        "why_off": "No local model work — leave daemon if OS-managed",
    },
    {
        "id": "remote_seats",
        "label": "Remote seats (DeepSeek/Claude/…)",
        "mode": "expensive",
        "token_class": "remote_tokens",
        "why_on": "Only while a dispatched job needs them",
        "why_off": "Passive default — never idle-on",
    },
    {
        "id": "browser_env",
        "label": "Browser / OpenClaw seat",
        "mode": "opt_in",
        "token_class": "interactive",
        "why_on": "Allowlisted computer-use job",
        "why_off": "Gate disabled — no free browsing",
    },
    {
        "id": "improve",
        "label": "Improve / scout loops",
        "mode": "opt_in",
        "token_class": "scheduled",
        "why_on": "Scheduled task or explicit improve cycle",
        "why_off": "Default passive — no background research burn",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        from mag_launch import _pid_alive as launch_pid_alive

        return bool(launch_pid_alive(int(pid)))
    except Exception:
        return False


def _port_up(port: int) -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.8) as r:
            return 200 <= r.status < 500
    except Exception:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.8) as r:
                return 200 <= r.status < 500
        except Exception:
            return False


def _launch_state() -> dict[str, Any]:
    try:
        return json.loads(LAUNCH_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _queue_depth() -> int:
    try:
        from mag.orchestrator import TERMINAL, list_tasks

        tasks = list_tasks(limit=40)
        return sum(1 for t in tasks if t.get("status") not in TERMINAL)
    except Exception:
        return 0


def _fleet_running() -> int:
    try:
        from mag.orchestrator import TERMINAL, list_tasks

        tasks = list_tasks(limit=50)
        return sum(1 for t in tasks if t.get("status") not in TERMINAL)
    except Exception:
        return 0


OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def _ollama_up() -> tuple[bool, str]:
    """Probe the local Ollama daemon; return (up, cause-detail).

    Fix B2-81 (2026-09-26, receipt
    watch/inbox/burn_wave_20260926/B2_81_ollama_truth_20260926.md): the old
    probe was a bare urllib.urlopen(timeout=0.6), which (a) inherits
    env/registry proxies, so a process launched with http_proxy set timed out
    against a LIVE daemon at 0.6s with no request ever reaching the server
    (reproduced: URLError timeout 0.61s via a dead proxy while /api/tags
    answered), and (b) had no retry, so load spikes past 600ms read as
    absent. 20 of the 21 verifiable lifecycle_gap:ollama rows show the server
    answering /api/tags 200 within 0-14s of the gap observation. Now:
    ProxyHandler({}) opener so proxies never intercept loopback, 2.0s timeout
    with two tries, then a raw socket-connect fallback (a listener means the
    daemon is on even if HTTP is wedged), and the cause names refused vs
    timeout so future rows carry their own verdict.
    """
    import socket
    import urllib.request

    last = "unknown"
    for _ in range(2):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(OLLAMA_TAGS_URL, timeout=2.0) as r:
                if r.status == 200:
                    return True, "11434"
                last = f"http {r.status}"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"[:90]
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1.0):
            return True, "11434 (socket; http " + last + ")"
    except Exception as exc:
        kind = type(exc).__name__
        flavor = "refused (no listener, daemon absent)" if kind == "ConnectionRefusedError" else "unreachable"
        return False, f"not answering ({flavor}; http {last}; socket {kind})"


def _power_off() -> bool:
    try:
        from mag.power import is_off

        return bool(is_off())
    except Exception:
        return (ROOT / "state" / "mag_power.off").is_file()


def _wanted_map(ml: dict[str, Any]) -> dict[str, bool]:
    return {str(k): bool(v) for k, v in (ml.get("wanted") or {}).items()}


def _actual_process(piece_id: str, ml: dict[str, Any]) -> tuple[bool, str]:
    """Return (on, detail) for supervised / known processes."""
    pids = ml.get("pids") or {}
    health = ml.get("health") or {}
    if piece_id == "backend":
        on = bool(health.get("backend")) or _port_up(8000)
        return on, "port:8000" if on else "down"
    if piece_id == "dashboard":
        on = bool(health.get("dashboard")) or _port_up(8765)
        return on, "port:8765" if on else "down"
    if piece_id == "mirror":
        on = bool(health.get("mirror")) or _port_up(8743)
        return on, "port:8743" if on else "down"
    if piece_id == "lab":
        pid = pids.get("lab")
        if pid and _pid_alive(pid):
            return True, f"pid={pid}"
        try:
            from mag.health import sanity

            s = sanity()
            up = (s.get("integral") or {}).get("up") or s.get("status") == "up"
            return bool(up), "heartbeat" if up else "no integral"
        except Exception:
            return False, "unknown"
    if piece_id in ("scribe", "drainer", "engine"):
        pid = pids.get(piece_id)
        alive = _pid_alive(pid) if pid else False
        return alive, f"pid={pid}" if alive else "stopped"
    if piece_id == "ollama":
        up, cause = _ollama_up()
        return up, cause
    if piece_id == "remote_seats":
        n = _fleet_running()
        return n > 0, f"fleet_running={n}"
    if piece_id == "browser_env":
        try:
            from mag.browser_env import status as browser_status

            st = browser_status()
            return bool(st.get("ready")), st.get("hint") or ""
        except Exception as exc:
            return False, str(exc)[:80]
    if piece_id == "improve":
        # MagImproveDaily scheduled task or running improve jobs
        try:
            from mag.orchestrator import list_tasks

            tasks = list_tasks(limit=30)
            n = sum(
                1
                for t in tasks
                if t.get("status") not in ("done", "failed", "killed", "died")
                and ("improve" in str(t.get("goal") or "").lower() or str(t.get("tag") or "").startswith("improve"))
            )
            return n > 0, f"improve_jobs={n}"
        except Exception:
            return False, "unknown"
    return False, "unknown"


def _policy_should(
    piece: dict[str, Any],
    *,
    power_off: bool,
    wanted: dict[str, bool],
    queue_depth: int,
    fleet_running: int,
    operator_active: bool,
    drainer_allowed: bool,
    browser_enabled: bool,
) -> tuple[bool, str]:
    """Return (should_be_on, reason)."""
    pid = piece["id"]
    if power_off:
        return False, "power off flag — entire stack intentionally down"

    mode = piece["mode"]

    if pid == "backend":
        return True, piece["why_on"]
    if pid == "dashboard":
        return True, piece["why_on"]
    if pid == "lab":
        return True, piece["why_on"]

    if pid == "scribe":
        # light local; want on if supervisor wants it OR work active
        if fleet_running > 0 or queue_depth > 0:
            return True, "work in flight — commentary useful"
        if wanted.get("scribe", True):
            return True, "supervisor wants scribe (cheap local)"
        return False, piece["why_off"]

    if pid == "mirror":
        w = wanted.get("mirror", False)
        if w:
            return True, "supervisor mirror wanted (scaffold present)"
        return False, piece["why_off"]

    if pid == "drainer":
        if not drainer_allowed:
            if operator_active:
                return False, "operator active — pause autorun (token save)"
            return False, "drainer disabled or not allowed"
        if queue_depth <= 0 and fleet_running <= 0:
            return False, "queue empty — stay passive (no drain burn)"
        return True, f"queue_depth={queue_depth} fleet={fleet_running} — drain allowed"

    if pid == "engine":
        return bool(wanted.get("engine")), (
            "MAG_ENGINE_CMD set" if wanted.get("engine") else piece["why_off"]
        )

    if pid == "ollama":
        # demand: recommend on only when local work; actual daemon may stay OS-managed
        if fleet_running > 0 or queue_depth > 0:
            return True, "local/remote fleet may need L0"
        return False, "no queue work — Ollama can idle (OS may keep daemon)"

    if pid == "remote_seats":
        if fleet_running > 0:
            return True, f"{fleet_running} active task(s) may use remotes"
        return False, piece["why_off"]

    if pid == "browser_env":
        return bool(browser_enabled), (
            "browser_env enabled" if browser_enabled else piece["why_off"]
        )

    if pid == "improve":
        # scheduled tasks are external; policy default off unless jobs running
        if fleet_running > 0:
            return False, "prefer explicit improve jobs only — not always-on"
        return False, piece["why_off"]

    if mode == "always":
        return True, piece["why_on"]
    if mode == "expensive":
        return False, piece["why_off"]
    return False, "default passive"


def build_lifecycle() -> dict[str, Any]:
    power_off = _power_off()
    ml = _launch_state()
    wanted = _wanted_map(ml)
    queue_depth = _queue_depth()
    fleet_running = _fleet_running()

    operator_active = False
    drainer_allowed = False
    try:
        from mag.preferences import autorun_allowed, operator_active as op_act

        operator_active = bool(op_act())
        drainer_allowed = bool(autorun_allowed())
    except Exception:
        pass

    browser_enabled = False
    browser_glance: dict[str, Any] = {}
    try:
        from mag.browser_env import status as browser_status

        browser_glance = browser_status()
        browser_enabled = bool(browser_glance.get("enabled"))
    except Exception:
        pass

    pieces: list[dict[str, Any]] = []
    mismatches: list[dict[str, str]] = []
    waste: list[str] = []  # on but should be off → token/cpu waste
    gaps: list[str] = []  # should be on but off → capability hole

    for defn in PIECE_DEFS:
        should, reason = _policy_should(
            defn,
            power_off=power_off,
            wanted=wanted,
            queue_depth=queue_depth,
            fleet_running=fleet_running,
            operator_active=operator_active,
            drainer_allowed=drainer_allowed,
            browser_enabled=browser_enabled,
        )
        actual, detail = _actual_process(defn["id"], ml)
        # When power off, actual may still show zombies briefly
        if power_off:
            should = False

        state = "aligned"
        if should and not actual:
            state = "gap"
            gaps.append(defn["id"])
            mismatches.append(
                {
                    "id": defn["id"],
                    "should": "on",
                    "actual": "off",
                    "action": _gap_action(defn["id"]),
                }
            )
        elif actual and not should:
            # OS-managed local daemons (ollama) can stay warm — not Mag token waste
            if defn["id"] in ("ollama",) or defn.get("token_class") == "local_gpu":
                state = "idle_ok"
            elif defn.get("token_class") == "local_free" and defn["id"] == "scribe":
                state = "idle_ok"  # cheap local commentary
            else:
                state = "waste"
                waste.append(defn["id"])
                mismatches.append(
                    {
                        "id": defn["id"],
                        "should": "off",
                        "actual": "on",
                        "action": _waste_action(defn["id"]),
                    }
                )

        pieces.append(
            {
                "id": defn["id"],
                "label": defn["label"],
                "mode": defn["mode"],
                "token_class": defn["token_class"],
                "should": "on" if should else "off",
                "actual": "on" if actual else "off",
                "aligned": state == "aligned",
                "state": state,
                "reason": reason,
                "detail": detail,
                "api_toggle": _toggle_hint(defn["id"]),
            }
        )

    # Whole-system posture
    if power_off:
        posture = "off"
    elif waste or (drainer_allowed and queue_depth == 0 and "drainer" in [p["id"] for p in pieces if p["actual"] == "on"]):
        posture = "active_waste" if waste else "passive_ready"
    elif fleet_running > 0 or queue_depth > 0:
        posture = "active"
    else:
        posture = "passive"

    core_ok = all(
        p["actual"] == "on"
        for p in pieces
        if p["id"] in ("backend", "dashboard", "lab") and not power_off
    )

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _now(),
        "posture": posture,
        "power_off": power_off,
        "passive_default": True,
        "signals": {
            "queue_depth": queue_depth,
            "fleet_running": fleet_running,
            "operator_active": operator_active,
            "drainer_allowed": drainer_allowed,
            "browser_enabled": browser_enabled,
            "core_ok": core_ok and not power_off,
        },
        "pieces": pieces,
        "waste": waste,
        "gaps": gaps,
        "mismatches": mismatches,
        "efficiency": {
            "rule": "Core local always when stack on; remotes/drainer/improve off unless work exists",
            "token_burn_risk": waste,
            "capability_holes": gaps,
        },
        "browser_env": browser_glance or None,
        "actions": {
            "read": "GET /api/v1/lifecycle",
            "reconcile": "POST /api/v1/lifecycle/reconcile",
            "power": "GET /api/v1/power",
            "drainer_off": "POST /api/v1/drainer {\"enabled\": false}",
            "stack_off": "POST /api/v1/power/stop",
            "stack_on": "POST /api/v1/power/start",
        },
        "hint": _hint(posture, waste, gaps, power_off),
    }


def _gap_action(piece_id: str) -> str:
    if piece_id in ("backend", "dashboard", "lab"):
        return "POST /api/v1/power/start"
    if piece_id == "drainer":
        return "POST /api/v1/drainer {\"enabled\": true}  # only if queue has work"
    if piece_id == "mirror":
        return "unset MAG_NO_MIRROR + restart supervisor"
    return "inspect piece"


def _waste_action(piece_id: str) -> str:
    if piece_id == "drainer":
        return "POST /api/v1/drainer {\"enabled\": false}"
    if piece_id == "mirror":
        return "set MAG_NO_MIRROR=1 or stop mirror process"
    if piece_id == "engine":
        return "unset MAG_ENGINE_CMD"
    if piece_id == "remote_seats":
        return "reap idle agents POST /api/v1/agents/reap"
    if piece_id == "improve":
        # t47: whoever executes this deliberate disable MUST leave the marker
        # (mark_improve_intentional) so the doctor probe does not alarm on it.
        # t77: prescribe the landed t73 executor (improve_off/improve_on) by
        # name instead of prose; improve-off writes the marker itself
        # (fail closed) and improve-on clears it only after re-register.
        return (
            'python main.py improve-off --reason "..." / python main.py improve-on'
            "  # off=marker then schtask disable; on=ps1 re-register then clear marker"
        )
    if piece_id == "scribe":
        return "leave — cheap local; optional stop via supervisor"
    return "POST /api/v1/lifecycle/reconcile"


def _toggle_hint(piece_id: str) -> str | None:
    # t81: improve hint aligned to the landed t73 executor commands for
    # parity with _waste_action (t77); raw schtasks prose dropped.
    return {
        "drainer": "POST /api/v1/drainer",
        "browser_env": "configs/browser_env.yaml",
        "lab": "POST /api/v1/power/start|stop",
        "dashboard": "POST /api/v1/power/start|stop",
        "backend": "POST /api/v1/power/start|stop",
        "mirror": "MAG_NO_MIRROR env",
        "engine": "MAG_ENGINE_CMD env",
        "improve": 'python main.py improve-off --reason "..." / python main.py improve-on',
        "remote_seats": "spawn only via agents/dispatch",
        "ollama": "OS Startup Ollama.lnk — demand use",
        "scribe": "supervisor slot",
    }.get(piece_id)


def _hint(posture: str, waste: list[str], gaps: list[str], power_off: bool) -> str:
    if power_off:
        return "Stack off. POST /api/v1/power/start when needed."
    if gaps and any(g in ("backend", "dashboard", "lab") for g in gaps):
        return "Core gap — POST /api/v1/power/start"
    if waste:
        return f"Passive win available — waste on: {', '.join(waste)}. POST /api/v1/lifecycle/reconcile"
    if posture == "passive":
        return "Passive ready — core local on, expensive seats off."
    if posture == "active":
        return "Work in flight — remotes/drainer may be on for a reason."
    return f"posture={posture}"


def reconcile(*, dry_run: bool = False) -> dict[str, Any]:
    """Apply **safe** offs only — never kill backend/dashboard/lab while stack should run.

    Safe:
      - disable drainer pref when queue empty or operator active
      - note others for operator (no hard kill of UI)
    """
    snap = build_lifecycle()
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for m in snap.get("mismatches") or []:
        pid = m.get("id")
        if m.get("should") != "off":
            skipped.append({"id": pid, "reason": "gap — use power start, not reconcile"})
            continue
        if pid in ("backend", "dashboard", "lab"):
            skipped.append({"id": pid, "reason": "core — never auto-off via reconcile"})
            continue
        if pid == "drainer":
            # Respect the env lock: if MAG_DRAINER is explicitly set on, the drainer
            # is intentionally on (e.g. containerized deployment) — don't fight it.
            if os.environ.get("MAG_DRAINER", "").strip().lower() in ("1", "true", "yes"):
                skipped.append({"id": "drainer", "reason": "env-locked on via MAG_DRAINER"})
                continue
            if dry_run:
                applied.append({"id": "drainer", "action": "would set_drainer(false)", "dry_run": True})
            else:
                try:
                    from mag.preferences import set_drainer

                    set_drainer(False)
                    applied.append({"id": "drainer", "action": "set_drainer(false)", "ok": True})
                except Exception as exc:
                    applied.append({"id": "drainer", "ok": False, "error": str(exc)[:120]})
            continue
        if pid == "scribe":
            skipped.append({"id": pid, "reason": "cheap local — leave running"})
            continue
        if pid == "ollama":
            skipped.append({"id": pid, "reason": "OS-managed daemon — not killed by Mag"})
            continue
        if pid == "mirror":
            skipped.append({"id": pid, "reason": "set MAG_NO_MIRROR=1 + restart to drop"})
            continue
        if pid in ("remote_seats", "improve", "engine", "browser_env"):
            skipped.append({"id": pid, "reason": "no auto-kill; stop jobs via agents API if needed"})
            continue
        skipped.append({"id": pid, "reason": "no safe auto action"})

    after = build_lifecycle() if not dry_run else snap
    result = {
        "ok": True,
        "schema": "mag_lifecycle_reconcile.v1",
        "ts": _now(),
        "dry_run": dry_run,
        "applied": applied,
        "skipped": skipped,
        "before_waste": snap.get("waste"),
        "after_waste": after.get("waste"),
        "lifecycle": after,
        "hint": "Safe offs only (drainer). Core stays for REST face.",
    }
    if not dry_run:
        _write_lifecycle_state(after, reconcile=result)
    return result


def auto_reconcile(*, force: bool = False) -> dict[str, Any] | None:
    """Supervisor hook — run safe passive offs when waste exists.

    Default on. Disable with MAG_NO_AUTO_PASSIVE=1 or prefs auto_passive=false.
    Also tokenizes remaining gaps/waste into improve + training (organic).
    """
    import os

    if not force:
        env = os.environ.get("MAG_NO_AUTO_PASSIVE", "").strip().lower()
        if env in ("1", "true", "yes"):
            return None
        try:
            from mag.preferences import load_prefs

            if load_prefs().get("auto_passive") is False:
                return None
        except Exception:
            pass

    snap = build_lifecycle()
    result: dict[str, Any]
    if not snap.get("waste"):
        _write_lifecycle_state(snap, reconcile=None)
        result = {"ok": True, "action": "noop", "posture": snap.get("posture"), "waste": []}
    else:
        result = reconcile(dry_run=False)

    # Organic self-improve: unbuilt / waste → training + improve candidates
    try:
        from mag.temperature_stack import track_lifecycle_into_improve

        result["gap_track"] = track_lifecycle_into_improve()
    except Exception as exc:
        result["gap_track"] = {"ok": False, "error": str(exc)[:120]}
    return result


def _write_lifecycle_state(
    lifecycle: dict[str, Any],
    *,
    reconcile: dict[str, Any] | None,
) -> None:
    path = ROOT / "state" / "lifecycle_latest.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": _now(),
            "posture": lifecycle.get("posture"),
            "waste": lifecycle.get("waste"),
            "gaps": lifecycle.get("gaps"),
            "signals": lifecycle.get("signals"),
            "hint": lifecycle.get("hint"),
            "pieces": [
                {
                    "id": p.get("id"),
                    "should": p.get("should"),
                    "actual": p.get("actual"),
                    "state": p.get("state"),
                    "token_class": p.get("token_class"),
                }
                for p in (lifecycle.get("pieces") or [])
            ],
            "last_reconcile": (
                {
                    "ts": reconcile.get("ts"),
                    "applied": reconcile.get("applied"),
                    "dry_run": reconcile.get("dry_run"),
                }
                if reconcile
                else None
            ),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass
