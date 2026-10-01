"""guard_registry — desired-state RECONCILER for every known fix (2026-08-10).

Operator law: "permanent fixes that you forget about are not fixes, they're future
bugs" (and "not just AMD, everything"). Steal (2026-08-10): the industry mechanism for
"known fix stays fixed" is a DESIRED-STATE CONTROLLER (K8s reconcile loop / systemd /
GitOps): observe -> diff against desired -> converge. Every fix here carries its OWN
probe (the test) + an idempotent reapply_fn (or None = alert-only), and reconcile() runs
on cadence:

  probe actual vs desired
    PASS              -> no-op
    FAIL + safe/idempotent + within budget + not human_required -> REAPPLY (log, reset on success)
    FAIL + otherwise  -> ALERT (labeled failure_kb signal) + backoff (no flapping)

A fix with no probe is exactly the "future bug" the operator warns about — it regresses
with no witness. All probes are read-only; reapply only when declarative + idempotent.

Schema: guard_registry.v1
CLI: python -m mag.guard_registry check|reconcile
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STATE = ROOT / "memory" / "runs" / "guard_registry.json"
ALERT_BACKOFF_S = 3600  # don't re-alert the same regression more than hourly


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}
    except Exception:
        return {}


def _save_state(s: dict[str, Any]) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ── probes (read-only "the test") ───────────────────────────────────────────

def _probe_amd() -> tuple[bool, str]:
    try:
        from mag.amd_window_guard import check as amd_check
        r = amd_check()
        return bool(r.get("ok")), ("StartCN/StartDVR disabled" if r.get("ok")
                                   else "re-enabled: " + ",".join(r.get("reenabled", [])))
    except Exception as e:
        return False, f"err: {str(e)[:80]}"


def _probe_real_interpreter() -> tuple[bool, str]:
    try:
        from mag.headless import _resolve_python
        exe = _resolve_python()
        bad = ".venv" in exe.lower() and "scripts" in exe.lower() and "python.exe" in exe.lower()
        return (not bad), (exe if bad else "spawners use real interpreter")
    except Exception as e:
        return False, f"err: {str(e)[:80]}"


def _probe_tools_headless() -> tuple[bool, str]:
    for rel in ("tools/shell.py", "tools/code_execution.py"):
        try:
            if "CREATE_NO_WINDOW" not in (ROOT / rel).read_text(encoding="utf-8", errors="replace"):
                return False, f"{rel} missing CREATE_NO_WINDOW"
        except OSError:
            return False, f"{rel} missing"
    return True, "shell + run_python executors headless"


def _probe_no_windowed_python() -> tuple[bool, str]:
    try:
        from mag.window_audit import _snapshot
        n = len(_snapshot())
        return (n == 0), ("no windowed python" if n == 0 else f"{n} windowed python in-tree")
    except Exception as e:
        return False, f"err: {str(e)[:80]}"


def _probe_spawn_sites() -> tuple[bool, str]:
    """REGISTRY MONKEY-STEAL (2026-08-10): static scan of EVERY subprocess spawn site.

    Verifies the no-window invariant holds everywhere, not just the known files:
    each .py that spawns a subprocess must be CREATE_NO_WINDOW-covered (explicit
    creationflags, a headless helper, or install_no_window_defaults at its entry).
    Catches the setdefault-bypass class of bug in ANY future/new spawn site.
    """
    import re as _re
    spawn_re = _re.compile(
        r"\bsubprocess\.(?:Popen|run|call|check_output|check_call)\s*\(|"
        r"\bos\.system\s*\(|"
        r"\bos\.startfile\s*\("
    )
    bad: list[str] = []
    files = [ROOT / "main.py"]
    for d in (ROOT / "mag", ROOT / "tools"):
        if d.is_dir():
            files += [p for p in d.rglob("*.py") if p.is_file()]
    for p in files:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not spawn_re.search(src):
            continue
        covered = any(
            kw in src for kw in (
                "CREATE_NO_WINDOW", "install_no_window_defaults",
                "run_headless", "popen_headless", "no_window_flags",
            )
        )
        if not covered:
            bad.append(str(p.relative_to(ROOT)))
    if bad:
        return False, "spawn sites missing CREATE_NO_WINDOW: " + ", ".join(sorted(bad)[:8])
    return True, "all spawn sites CREATE_NO_WINDOW-covered"


def _probe_restful_observer() -> tuple[bool, str]:
    try:
        src = (ROOT / "mag" / "ghost.py").read_text(encoding="utf-8", errors="replace")
        obs = "health_law(h, apply=False)" in src
        return obs, ("health_law is observer" if obs else "health_law still apply=True")
    except OSError:
        return False, "ghost.py missing"


def _probe_single_controller() -> tuple[bool, str]:
    """The L8 refactor fix must hold: under MAG_CONTAINER=1, process_supervisor is an
    observer (start_loop/reap gated), so mag_launch + Docker are the ONE controller.
    Without this probe, a future edit can silently reintroduce double-supervision."""
    try:
        src = (ROOT / "mag" / "process_supervisor.py").read_text(encoding="utf-8", errors="replace")
        gated_start = "_container_mode()" in src and "start_loop(name: str)" in src
        gated_reap = "if _container_mode():" in src and "def reap(" in src
        return (gated_start and gated_reap), (
            "process_supervisor gated under MAG_CONTAINER (single controller)"
            if (gated_start and gated_reap) else "L8 gate missing/reverted")
    except OSError:
        return False, "process_supervisor.py missing"


# ── registry: desired-state entries ─────────────────────────────────────────
# reapply is None + human_required=True => alert-only (admin / source / code change).
REGISTRY: list[dict[str, Any]] = [
    {"id": "amd_flash_tasks", "desc": "AMD StartCN/StartDVR disabled (flash windows)",
     "desired": "StartCN/StartDVR Disabled", "probe": _probe_amd,
     "reapply": None, "human_required": True,
     "fix": "elevated: schtasks /Change /TN StartCN /DISABLE; StartDVR /DISABLE"},
    {"id": "spawner_real_interpreter", "desc": "spawners use real interpreter, not venv shim",
     "desired": "headless resolves pyvenv home", "probe": _probe_real_interpreter,
     "reapply": None, "human_required": True,
     "fix": "headless._resolve_python() reads pyvenv.cfg 'home'"},
    {"id": "tools_headless", "desc": "agent shell/python executors are CREATE_NO_WINDOW",
     "desired": "shell.py + code_execution.py have CREATE_NO_WINDOW", "probe": _probe_tools_headless,
     "reapply": None, "human_required": True,
     "fix": "add CREATE_NO_WINDOW to tools/shell.py + code_execution.py"},
    {"id": "no_windowed_python", "desc": "no python with a visible console window in-tree",
     "desired": "0 windowed python", "probe": _probe_no_windowed_python,
     "reapply": None, "human_required": True,
     "fix": "any windowed python = leak; trace via window_audit"},
    {"id": "spawn_sites_no_window", "desc": "every subprocess spawn site is CREATE_NO_WINDOW-covered",
     "desired": "no .py spawns without CREATE_NO_WINDOW / headless helper / entry patch",
     "probe": _probe_spawn_sites,
     "reapply": None, "human_required": True,
     "fix": "add CREATE_NO_WINDOW to any spawn site, or call install_no_window_defaults at its entry"},
    {"id": "restful_observer", "desc": "health_law is an observer, not a timer-restarter",
     "desired": "health_law(h, apply=False)", "probe": _probe_restful_observer,
     "reapply": None, "human_required": True,
     "fix": "ghost.cycle must call health_law(h, apply=False)"},
    {"id": "single_controller", "desc": "one controller owns the loops (L8 refactor: process_supervisor gated under MAG_CONTAINER)",
     "desired": "process_supervisor.start_loop/reap gated by _container_mode()", "probe": _probe_single_controller,
     "reapply": None, "human_required": True,
     "fix": "keep mag/process_supervisor.py gated under MAG_CONTAINER=1 (mag_launch + Docker are the one controller)"},
]


def reconcile(*, dry: bool = False) -> dict[str, Any]:
    """Desired-state reconcile: probe each guard; reapply safe/idempotent/within-budget
    fixes; alert (with backoff) on the rest. Read-only probes; only reapply declarative."""
    st = _load_state()
    now = time.time()
    results = []
    regressions = []
    for g in REGISTRY:
        ok, detail = g["probe"]()
        if ok:
            st.pop(g["id"], None)  # healthy -> forget backoff
            results.append({"id": g["id"], "ok": True, "detail": detail, "action": "pass"})
            continue
        last = st.get(g["id"], {}).get("last_alert", 0)
        can_auto = bool(g.get("reapply")) and not g.get("human_required") and (now - last >= ALERT_BACKOFF_S)
        if can_auto and not dry:
            try:
                g["reapply"]()
                st[g["id"]] = {"last_alert": 0, "reapplied": _now()}
                results.append({"id": g["id"], "ok": True, "detail": detail, "action": "reapplied"})
                continue
            except Exception as e:
                detail = f"reapply failed: {str(e)[:80]}"
        if now - last < ALERT_BACKOFF_S:
            results.append({"id": g["id"], "ok": False, "detail": detail, "action": "alert_backoff"})
            continue
        regressions.append({"id": g["id"], "desc": g["desc"], "detail": detail, "fix": g["fix"]})
        st[g["id"]] = {"last_alert": now}
        results.append({"id": g["id"], "ok": False, "detail": detail, "action": "alert"})
    _save_state(st)
    if regressions:
        try:
            from mag.failure_kb import log_failure
            log_failure(kind="guard_registry", tool="guard_registry",
                        error="known-fix regression(s): " + ", ".join(f["id"] for f in regressions),
                        detail=(" | ".join(f"{f['id']}: {f['fix']}" for f in regressions))[:400],
                        phase="cadence")
        except Exception:
            pass
    return {"schema": "guard_registry.v1", "ts": _now(), "dry": dry,
            "ok": all(r["ok"] for r in results), "guards": results, "regressions": regressions}


def check() -> dict[str, Any]:
    return reconcile(dry=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = not (argv and argv[0] == "reconcile")
    print(json.dumps(reconcile(dry=dry), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

