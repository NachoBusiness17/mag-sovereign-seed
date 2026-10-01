"""Coding session runner — one-button sprint until closed, stall, or verifier block."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

from mag.coding_session_loop import (
    close_session_if_ready,
    load_config,
    run_preflight,
    seed_desk,
    session_status,
)

RUN_REPORT_DIR = ROOT / "memory" / "runs" / "coding_session_run"
DEFAULT_STALL_TICKS = 5


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_path(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _git_out(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return (proc.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _progress_key(tick: dict[str, Any]) -> str:
    adv = tick.get("advance") if isinstance(tick.get("advance"), dict) else {}
    status = adv.get("status") if isinstance(adv.get("status"), dict) else {}
    close = tick.get("close") if isinstance(tick.get("close"), dict) else {}
    step = tick.get("step") if isinstance(tick.get("step"), dict) else {}
    acted = step.get("acted") if isinstance(step.get("acted"), dict) else {}
    return json.dumps(
        {
            "active": status.get("active_sprint"),
            "completed": len(status.get("completed_sprints") or []),
            "all_done": status.get("all_sprints_done"),
            "closed": close.get("closed"),
            "verifier_blocked": adv.get("verifier_blocked"),
            "acted_ok": acted.get("ok"),
        },
        sort_keys=True,
    )


def build_run_report(
    *,
    phase: str,
    session_id: str,
    cfg: dict[str, Any],
    track: str | None = None,
    preflight: dict[str, Any] | None = None,
    close: dict[str, Any] | None = None,
    ticks: int = 0,
    last: dict[str, Any] | None = None,
    stall_ticks: int = 0,
    report_path: str | None = None,
) -> dict[str, Any]:
    """Structured post-run report for review — gates, git diff, artifact paths."""
    from mag.env_registry import get_active_env

    st = session_status(config=cfg)
    build_matches = sorted(
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in ROOT.glob("memory/factory/build_audit*.json")
    )
    diff_stat = _git_out("diff", "--stat", "HEAD")
    branch = _git_out("rev-parse", "--abbrev-ref", "HEAD")

    review: dict[str, str] = {
        "handoff_inbox": "GET /api/v1/handoff-inbox",
        "desk_conductor_trail": "memory/runs/desk_conductor_trail.jsonl",
        "session_state": "memory/working/coding_session_loop.json",
        "orchestrator_state": "memory/working/coding_session_orchestrator.json",
    }
    if build_matches:
        review["build_audit_latest"] = build_matches[-1]
    if close and close.get("state_path"):
        review["session_state"] = str(close["state_path"])
    bead = (close or {}).get("bead")
    if isinstance(bead, dict) and bead.get("path"):
        review["bead"] = str(bead["path"])

    return {
        "schema": "coding_session_run.v1",
        "session_id": session_id,
        "phase": phase,
        "ticks": ticks,
        "stall_ticks": stall_ticks,
        "branch": branch or None,
        "track": track or get_active_env(),
        "preflight": preflight,
        "session_done_gates": st.get("session_done_gates"),
        "has_done": st.get("has_done"),
        "build_audit_matches": build_matches,
        "git_diff_stat_head": diff_stat or None,
        "review_artifacts": review,
        "close": close,
        "last_active_sprint": (last or {}).get("active_sprint"),
        "report_path": report_path,
        "ts": _utc(),
    }


def _write_run_report(report: dict[str, Any], *, session_id: str) -> str:
    RUN_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RUN_REPORT_DIR / f"{session_id}-{ts}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    rel = _rel_path(path)
    report["report_path"] = rel
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return rel


def run_until_done(
    *,
    max_ticks: int = 50,
    track: str | None = None,
    note: str = "",
    config: dict[str, Any] | None = None,
    dry: bool = False,
    stall_ticks: int = DEFAULT_STALL_TICKS,
    force_new_seed: bool = False,
) -> dict[str, Any]:
    """Run coding session orchestrator until closed, stall, preflight fail, or verifier block."""
    cfg = config or load_config()
    if not cfg.get("ok"):
        return {**cfg, "phase": "failed", "ticks": 0}

    track_out: dict[str, Any] | None = None
    if track:
        from mag.env_registry import activate_track

        track_out = activate_track(str(track).strip())
        if not track_out.get("ok"):
            out = {
                "ok": False,
                "phase": "failed",
                "ticks": 0,
                "error": track_out.get("error") or "track activation failed",
                "track": track_out,
            }
            return out

    pf = run_preflight(config=cfg)
    if not pf.get("ok"):
        report = build_run_report(
            phase="preflight_fail",
            session_id=str(cfg.get("session_id") or "coding-session"),
            cfg=cfg,
            track=track,
            preflight=pf,
            ticks=0,
        )
        report_path = _write_run_report(report, session_id=str(cfg.get("session_id") or "coding-session"))
        return {
            "ok": False,
            "phase": "preflight_fail",
            "ticks": 0,
            "preflight": pf,
            "track": track_out,
            "report": report,
            "report_path": report_path,
        }

    st = session_status(config=cfg)
    state = st.get("state") if isinstance(st.get("state"), dict) else {}
    if force_new_seed and state.get("status") == "closed":
        seed_desk(config=cfg)
        st = session_status(config=cfg)
        state = st.get("state") if isinstance(st.get("state"), dict) else {}
    if not (st.get("state") or {}).get("seeded_ts"):
        seed_desk(config=cfg)
        st = session_status(config=cfg)
    from mag.coding_session_orchestrator import plan_session

    plan_session(config=cfg)

    sid = str(cfg.get("session_id") or "coding-session")
    state = st.get("state") if isinstance(st.get("state"), dict) else {}
    gates = st.get("session_done_gates") or []
    gates_ok = bool(gates) and all(g.get("pass") or g.get("ok") for g in gates)
    if state.get("status") == "closed" or (st.get("has_done") and gates_ok):
        close_out = close_session_if_ready(config=cfg, dry=dry)
        report = build_run_report(
            phase="closed",
            session_id=sid,
            cfg=cfg,
            track=track,
            preflight=pf,
            close=close_out,
            ticks=0,
            last={"ok": True, "early_exit": True, "session_status": st},
        )
        report_path = _write_run_report(report, session_id=sid)
        return {
            "ok": True,
            "phase": "closed",
            "reason": "already_closed",
            "ticks": 0,
            "last": {"ok": True, "early_exit": True},
            "close": close_out,
            "track": track_out,
            "report": report,
            "report_path": report_path,
        }

    last: dict[str, Any] = {}
    close_out: dict[str, Any] | None = None
    ticks = 0
    no_progress = 0
    prev_key = ""

    for i in range(max(1, int(max_ticks))):
        ticks = i + 1
        last = __import__(
            "mag.coding_session_orchestrator",
            fromlist=["orchestrator_tick"],
        ).orchestrator_tick(
            auto_step=not dry,
            operator_note=note,
            config=cfg,
        )
        if not last.get("ok"):
            report = build_run_report(
                phase="failed",
                session_id=sid,
                cfg=cfg,
                track=track,
                preflight=pf,
                close=close_out,
                ticks=ticks,
                last=last,
            )
            report_path = _write_run_report(report, session_id=sid)
            return {
                "ok": False,
                "phase": "failed",
                "ticks": ticks,
                "last": last,
                "close": close_out,
                "track": track_out,
                "report": report,
                "report_path": report_path,
            }

        close_out = last.get("close") if isinstance(last.get("close"), dict) else None
        if close_out and close_out.get("closed"):
            report = build_run_report(
                phase="closed",
                session_id=sid,
                cfg=cfg,
                track=track,
                preflight=pf,
                close=close_out,
                ticks=ticks,
                last=last,
            )
            report_path = _write_run_report(report, session_id=sid)
            return {
                "ok": True,
                "phase": "closed",
                "ticks": ticks,
                "last": last,
                "close": close_out,
                "track": track_out,
                "report": report,
                "report_path": report_path,
            }

        adv = last.get("advance") if isinstance(last.get("advance"), dict) else {}
        if adv.get("verifier_blocked"):
            close_out = close_session_if_ready(config=cfg, dry=dry)
            report = build_run_report(
                phase="stalled",
                session_id=sid,
                cfg=cfg,
                track=track,
                preflight=pf,
                close=close_out,
                ticks=ticks,
                last=last,
                stall_ticks=no_progress,
            )
            report_path = _write_run_report(report, session_id=sid)
            return {
                "ok": True,
                "phase": "stalled",
                "reason": "verifier_blocked",
                "ticks": ticks,
                "last": last,
                "close": close_out,
                "track": track_out,
                "report": report,
                "report_path": report_path,
            }

        key = _progress_key(last)
        if key == prev_key:
            no_progress += 1
        else:
            no_progress = 0
            prev_key = key

        if no_progress >= max(1, int(stall_ticks)):
            close_out = close_session_if_ready(config=cfg, dry=dry)
            if close_out.get("closed"):
                report = build_run_report(
                    phase="closed",
                    session_id=sid,
                    cfg=cfg,
                    track=track,
                    preflight=pf,
                    close=close_out,
                    ticks=ticks,
                    last=last,
                )
                report_path = _write_run_report(report, session_id=sid)
                return {
                    "ok": True,
                    "phase": "closed",
                    "ticks": ticks,
                    "last": last,
                    "close": close_out,
                    "track": track_out,
                    "report": report,
                    "report_path": report_path,
                }
            report = build_run_report(
                phase="stalled",
                session_id=sid,
                cfg=cfg,
                track=track,
                preflight=pf,
                close=close_out,
                ticks=ticks,
                last=last,
                stall_ticks=no_progress,
            )
            report_path = _write_run_report(report, session_id=sid)
            return {
                "ok": True,
                "phase": "stalled",
                "reason": "no_progress",
                "ticks": ticks,
                "last": last,
                "close": close_out,
                "track": track_out,
                "report": report,
                "report_path": report_path,
            }

    close_out = close_session_if_ready(config=cfg, dry=dry)
    phase = "closed" if close_out.get("closed") else "stalled"
    report = build_run_report(
        phase=phase,
        session_id=sid,
        cfg=cfg,
        track=track,
        preflight=pf,
        close=close_out,
        ticks=ticks,
        last=last,
        stall_ticks=no_progress,
    )
    report_path = _write_run_report(report, session_id=sid)
    return {
        "ok": True,
        "phase": phase,
        "reason": "max_ticks" if phase != "closed" else None,
        "ticks": ticks,
        "last": last,
        "close": close_out,
        "track": track_out,
        "report": report,
        "report_path": report_path,
    }
