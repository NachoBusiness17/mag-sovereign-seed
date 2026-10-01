"""Factory machine — branch → sprint → retrospective → bead → behavioral catalog.

Chains existing coding_session_runner + improve hooks. Minimal new logic.
CLI: mag.cmd factory-machine run --note "goal"
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

from mag.coding_session_loop import CONFIG_PATH, close_session_if_ready, load_config
from mag.coding_session_runner import build_run_report, run_until_done

RETRO_DIR = ROOT / "memory" / "runs" / "retrospectives"
REPORT_DIR = ROOT / "memory" / "runs" / "factory_machine"
SCHEMA = "factory_machine_report.v1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_path(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _git_run(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        check=check,
    )


def _git_out(*args: str) -> str:
    try:
        proc = _git_run(*args)
        if proc.returncode == 0:
            return (proc.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _slug(s: str, *, max_len: int = 32) -> str:
    t = re.sub(r"[^a-zA-Z0-9_-]+", "-", (s or "run").strip().lower())
    t = re.sub(r"-+", "-", t).strip("-")
    return (t or "run")[:max_len]


def checkout_run_branch(
    *,
    session_id: str,
    branch_prefix: str = "mag/run",
    track: str | None = None,
) -> dict[str, Any]:
    """Create mag/run-<session>-<ts> branch; fall back to env track on failure."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sid = _slug(session_id or "session", max_len=24)
    prefix = (branch_prefix or "mag/run").strip().rstrip("/")
    branch = f"{prefix}-{sid}-{ts}"

    proc = _git_run("checkout", "-b", branch)
    if proc.returncode == 0:
        return {
            "ok": True,
            "branch": branch,
            "mode": "branch",
            "stdout": (proc.stdout or "").strip(),
        }

    track_out: dict[str, Any] | None = None
    if track:
        try:
            from mag.env_registry import activate_track

            track_out = activate_track(str(track).strip())
        except Exception as exc:
            track_out = {"ok": False, "error": str(exc)}

    return {
        "ok": False,
        "branch": branch,
        "mode": "track_fallback" if track_out and track_out.get("ok") else "failed",
        "error": (proc.stderr or proc.stdout or "git checkout -b failed").strip(),
        "track": track_out,
    }


def _orchestrator_summary() -> dict[str, Any]:
    try:
        from mag.coding_session_orchestrator import assess_sprint_status

        cfg = load_config(CONFIG_PATH)
        return assess_sprint_status(config=cfg)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def write_retrospective(
    *,
    session_id: str,
    sprint: dict[str, Any],
    note: str = "",
    branch: dict[str, Any] | None = None,
    bead: dict[str, Any] | None = None,
    behavioral: dict[str, Any] | None = None,
) -> str:
    """Rules-based retrospective markdown — what went right / wrong / next."""
    report = sprint.get("report") if isinstance(sprint.get("report"), dict) else {}
    phase = sprint.get("phase") or report.get("phase") or "unknown"
    ticks = sprint.get("ticks") if sprint.get("ticks") is not None else report.get("ticks")
    gates = report.get("session_done_gates") or []
    diff_stat = report.get("git_diff_stat_head") or ""
    orch = _orchestrator_summary()

    passed_gates = [g for g in gates if isinstance(g, dict) and (g.get("pass") or g.get("ok"))]
    failed_gates = [g for g in gates if isinstance(g, dict) and not (g.get("pass") or g.get("ok"))]

    right: list[str] = []
    wrong: list[str] = []
    nxt: list[str] = []

    if phase == "closed":
        right.append(f"Sprint reached **closed** after {ticks or '?'} orchestrator tick(s).")
    elif phase == "stalled":
        wrong.append(f"Sprint **stalled** ({sprint.get('reason') or 'no progress'}) at tick {ticks or '?'}." )
    elif phase == "preflight_fail":
        wrong.append("Preflight gates blocked the run before orchestrator ticks.")
    else:
        wrong.append(f"Ended in phase `{phase}` — review run report.")

    if passed_gates:
        right.append(f"{len(passed_gates)} session_done gate(s) green.")
    if failed_gates:
        wrong.append(f"{len(failed_gates)} session_done gate(s) still open.")
    if diff_stat:
        lines = [ln.strip() for ln in diff_stat.splitlines() if ln.strip()]
        if lines:
            right.append(f"Git diff stat: `{lines[0]}`" + (f" (+{len(lines)-1} more)" if len(lines) > 1 else ""))
    if branch and branch.get("ok"):
        right.append(f"Worked on branch `{branch.get('branch')}`." )
    elif branch and branch.get("error"):
        wrong.append(f"Branch checkout failed — {str(branch.get('error'))[:120]}")

    if isinstance(bead, dict) and bead.get("ok"):
        right.append("Run bead filed to trail.")
    elif sprint.get("close") and (sprint.get("close") or {}).get("bead"):
        right.append("Session close wrote bead via coding_session_loop.")

    if behavioral and behavioral.get("ok"):
        right.append("Behavioral catalog + improve scout ran post-run.")
    elif behavioral and behavioral.get("error"):
        wrong.append(f"Behavioral catalog error: {str(behavioral.get('error'))[:120]}")

    if note.strip():
        nxt.append(f"Operator note: {note.strip()[:400]}")
    if orch.get("next_action"):
        nxt.append(f"Orchestrator next: {orch.get('next_action')}")
    if failed_gates:
        for g in failed_gates[:4]:
            nxt.append(f"Clear gate `{g.get('id', '?')}`")
    if phase != "closed":
        nxt.append("Re-run factory-machine after fixing blockers or steering on desk.")
    if not nxt:
        nxt.append("Review retrospective + diff; merge branch or file follow-up bead.")

    right_lines = [f"- {x}" for x in right] or ["- (none recorded)"]
    wrong_lines = [f"- {x}" for x in wrong] or ["- (none recorded)"]
    next_lines = [f"- {x}" for x in nxt]

    RETRO_DIR.mkdir(parents=True, exist_ok=True)
    path = RETRO_DIR / f"{_slug(session_id, max_len=48)}.md"
    body = "\n".join(
        [
            f"# Retrospective — {session_id}",
            "",
            f"_Generated {_utc()} · phase `{phase}` · ticks {ticks}_",
            "",
            "## What went right",
            "",
            *right_lines,
            "",
            "## What went wrong",
            "",
            *wrong_lines,
            "",
            "## Next",
            "",
            *next_lines,
            "",
            "## Artifacts",
            "",
            f"- sprint report: `{sprint.get('report_path') or '—'}`",
            f"- orchestrator: `{json.dumps(orch, default=str)[:500]}`",
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return _rel_path(path)


def behavioral_catalog(*, dry: bool = False) -> dict[str, Any]:
    """Scout behavioral leaves + light improve cycle; log training event."""
    out: dict[str, Any] = {"ok": True, "dry": dry}
    try:
        from mag.improve import scout as improve_scout

        out["scout"] = improve_scout(dry=dry)
        if not out["scout"].get("ok"):
            out["ok"] = False
    except Exception as exc:
        out["scout_error"] = str(exc)[:200]
        out["ok"] = False

    if not dry:
        try:
            from mag.improve_loop import run_improve_cycle

            out["improve_cycle"] = run_improve_cycle(source="factory_machine", scout=True)
        except Exception as exc:
            out["improve_cycle_error"] = str(exc)[:200]

        try:
            from mag.training_events import emit

            out["training_event"] = emit(
                "factory_cycle",
                join={"session_id": "factory_machine"},
                input_data={"note": "post-run behavioral catalog"},
                outcome={"scout_ok": bool((out.get("scout") or {}).get("ok"))},
                pattern_tags=["behavioral", "factory_machine"],
            )
        except Exception as exc:
            out["training_event_error"] = str(exc)[:200]

    return out


def _write_machine_report(report: dict[str, Any], *, session_id: str) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"{_slug(session_id, max_len=32)}-{ts}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    rel = _rel_path(path)
    report["report_path"] = rel
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return rel


def factory_machine_status(*, config_path: Path | None = None) -> dict[str, Any]:
    """Lightweight status for Home / desk ops strip."""
    cfg = load_config(config_path or CONFIG_PATH)
    sid = str(cfg.get("session_id") or "coding-session")
    latest_report: dict[str, Any] | None = None
    if REPORT_DIR.is_dir():
        files = sorted(REPORT_DIR.glob("*.json"), reverse=True)
        if files:
            try:
                latest_report = json.loads(files[0].read_text(encoding="utf-8"))
            except Exception:
                latest_report = None
    retro_path = RETRO_DIR / f"{_slug(sid, max_len=48)}.md"
    return {
        "ok": True,
        "schema": SCHEMA,
        "session_id": sid,
        "branch": _git_out("rev-parse", "--abbrev-ref", "HEAD") or None,
        "latest_report": latest_report,
        "retrospective_path": _rel_path(retro_path) if retro_path.is_file() else None,
        "ts": _utc(),
    }


def factory_machine_run(
    config_path: Path | str | None = None,
    *,
    branch_prefix: str = "mag/run",
    note: str = "",
    max_ticks: int = 50,
    track: str | None = None,
    dry: bool = False,
    force_new_seed: bool = False,
) -> dict[str, Any]:
    """Full machine: branch → sprint → retro → bead → behavioral → JSON report."""
    cfg_path = Path(config_path) if config_path else CONFIG_PATH
    cfg = load_config(cfg_path)
    if not cfg.get("ok"):
        return {**cfg, "ok": False, "phase": "config_fail"}

    sid = str(cfg.get("session_id") or "coding-session")
    machine: dict[str, Any] = {
        "schema": SCHEMA,
        "session_id": sid,
        "note": (note or "")[:500],
        "phases": {},
        "ts": _utc(),
    }

    # 1 — branch
    branch = checkout_run_branch(session_id=sid, branch_prefix=branch_prefix, track=track)
    machine["phases"]["branch"] = branch
    machine["branch"] = branch.get("branch")

    # 2 — sprint
    sprint = run_until_done(
        max_ticks=max_ticks,
        track=None if branch.get("ok") else track,
        note=note,
        config=cfg,
        dry=dry,
        force_new_seed=force_new_seed,
    )
    machine["phases"]["sprint"] = {
        "phase": sprint.get("phase"),
        "ticks": sprint.get("ticks"),
        "ok": sprint.get("ok"),
        "report_path": sprint.get("report_path"),
    }
    machine["sprint"] = sprint

    # 3 — retrospective
    retro_path = write_retrospective(
        session_id=sid,
        sprint=sprint,
        note=note,
        branch=branch,
    )
    machine["phases"]["retro"] = {"path": retro_path}
    machine["retrospective_path"] = retro_path

    # 4 — close session if still open
    close_out: dict[str, Any] | None = None
    if not dry and sprint.get("phase") != "preflight_fail":
        close_out = close_session_if_ready(config=cfg, dry=dry)
        machine["phases"]["close"] = close_out

    # 5 — bead
    bead: dict[str, Any] | None = None
    if not dry:
        if isinstance(close_out, dict) and close_out.get("bead"):
            bead = close_out["bead"]
        else:
            try:
                from mag.run_trail import close_run

                bead = close_run(reason=f"factory_machine:{sid}")
            except Exception as exc:
                bead = {"ok": False, "error": str(exc)[:200]}
        machine["phases"]["bead"] = bead

    # 6 — behavioral catalog
    behavioral = behavioral_catalog(dry=dry)
    machine["phases"]["behavioral"] = behavioral

    # enrich retro with bead + behavioral (rewrite once)
    retro_full = write_retrospective(
        session_id=sid,
        sprint=sprint,
        note=note,
        branch=branch,
        bead=bead,
        behavioral=behavioral,
    )
    machine["retrospective_path"] = retro_full

    # 7 — machine report JSON
    machine["phase"] = sprint.get("phase")
    machine["ok"] = sprint.get("ok") is not False and behavioral.get("ok", True)
    machine["report"] = build_run_report(
        phase=str(sprint.get("phase") or "unknown"),
        session_id=sid,
        cfg=cfg,
        track=track,
        preflight=(sprint.get("report") or {}).get("preflight") if isinstance(sprint.get("report"), dict) else None,
        close=close_out,
        ticks=int(sprint.get("ticks") or 0),
        last=sprint.get("last") if isinstance(sprint.get("last"), dict) else None,
    )
    report_path = _write_machine_report(machine, session_id=sid)
    machine["report_path"] = report_path

    return machine
