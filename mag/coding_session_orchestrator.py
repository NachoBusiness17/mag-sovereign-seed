"""Coding session orchestrator — PO/Scrum Master tick for desk board sessions.

Rule-based planning (no LLM in unit tests). Drives sprint progression toward
Beta 1 factory goal; delegates seat handoff to desk_conductor.conductor_tick.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

from mag.coding_session_loop import (
    CONFIG_PATH,
    SCHEMA,
    SESSION_STATE_PATH,
    _check_path_gate,
    _run_cmd,
    load_config,
)

ORCH_STATE_PATH = ROOT / "memory" / "working" / "coding_session_orchestrator.json"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_path(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _default_knowns(cfg: dict[str, Any]) -> list[str]:
    """Knowns from config + Beta 1 ILAP doc facts."""
    out: list[str] = list(cfg.get("knowns") or [])
    if not out:
        out = [
            "Beta 1 gate checklist in docs/ref/proposals/ILAP-beta1-definition.md",
            "Verkle tip: 90 leaves filed (verkle_honest gate partial pass)",
            "Desk loop + conductor_tick wired (mag/desk_conductor.py)",
            "Playbook code_scout_janitor in configs/local_playbooks.yaml",
            "Session mode: step (not loop until trust tier ≥ 1)",
            "Factory pilot #1 spec: docs/ref/BUILD-factory-audit-json-EXAMPLE.md",
        ]
    return out


def _default_unknowns(cfg: dict[str, Any]) -> list[str]:
    out: list[str] = list(cfg.get("unknowns") or [])
    if not out:
        out = [
            "Desk trust tier 1 — scripts/desk_baseline_probe.py 3× green not yet verified",
            "First build_audit.v1 JSON on disk — run build-audit after Step validates",
            "RUN A gates (PRs 8-11) merge status for Beta 1 claim",
        ]
    return out


def _sprint_keys(cfg: dict[str, Any]) -> list[str]:
    scrum = cfg.get("scrum") or {}
    return [k for k in scrum if isinstance(scrum.get(k), dict)]


def _sprint_block(cfg: dict[str, Any], key: str) -> dict[str, Any]:
    scrum = cfg.get("scrum") or {}
    block = scrum.get(key)
    return block if isinstance(block, dict) else {}


def _load_orch_state() -> dict[str, Any]:
    if ORCH_STATE_PATH.is_file():
        try:
            return json.loads(ORCH_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_orch_state(state: dict[str, Any]) -> None:
    ORCH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ORCH_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def active_sprint_key(*, config: dict[str, Any] | None = None, state: dict[str, Any] | None = None) -> str:
    cfg = config or load_config()
    st = state if state is not None else _load_orch_state()
    explicit = (st.get("active_sprint") or cfg.get("current_sprint") or "").strip()
    keys = _sprint_keys(cfg)
    if explicit and explicit in keys:
        return explicit
    completed = set(st.get("completed_sprints") or [])
    for key in keys:
        if key not in completed:
            return key
    return keys[-1] if keys else ""


def _sprint_gate_check(cfg: dict[str, Any], sprint_key: str) -> dict[str, Any]:
    """Assess whether a sprint's done_when criteria are met (rule-based)."""
    block = _sprint_block(cfg, sprint_key)
    done_when = (block.get("done_when") or "").strip().lower()
    artifact = (block.get("artifact") or "").strip()

    if "preflight" in done_when or sprint_key.endswith("preflight"):
        from mag.coding_session_loop import run_preflight

        pf = run_preflight(config=cfg)
        return {
            "sprint": sprint_key,
            "pass": bool(pf.get("ok")),
            "reason": f"preflight {pf.get('passed')}/{pf.get('total')}",
            "detail": pf,
        }

    if artifact:
        if "*" in artifact or "?" in artifact:
            matches = list(ROOT.glob(artifact))
            ok = len(matches) > 0
            return {"sprint": sprint_key, "pass": ok, "reason": f"artifact glob {artifact}", "matches": len(matches)}
        p = ROOT / artifact
        ok = p.is_file()
        return {"sprint": sprint_key, "pass": ok, "reason": f"artifact path {artifact}", "exists": ok}

    # desk_task sprints — operator marks via Done on canvas or dialogue progress
    from mag.agent_desk import read_desk

    text = read_desk().get("text") or ""
    done_marker = (cfg.get("done_marker") or "Done").strip()
    has_done = bool(re.search(rf"^##\s+{re.escape(done_marker)}\s*$", text, re.M))
    sprint_done_tag = f"sprint:{sprint_key}:done"
    tagged = sprint_done_tag.lower() in text.lower()
    return {
        "sprint": sprint_key,
        "pass": has_done or tagged,
        "reason": "canvas Done section or sprint tag",
        "has_done": has_done,
        "tagged": tagged,
    }


def assess_sprint_status(*, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    if not cfg.get("ok"):
        return cfg
    state = _load_orch_state()
    if state.get("session_id") != cfg.get("session_id"):
        state = {}
    active = active_sprint_key(config=cfg, state=state)
    keys = _sprint_keys(cfg)
    completed = list(state.get("completed_sprints") or [])
    checks: list[dict[str, Any]] = []
    for key in keys:
        chk = _sprint_gate_check(cfg, key)
        checks.append(chk)
        if chk.get("pass") and key not in completed:
            completed.append(key)
    if active in completed and keys:
        idx = keys.index(active) if active in keys else -1
        if idx >= 0 and idx + 1 < len(keys):
            active = keys[idx + 1]
        elif idx == len(keys) - 1:
            active = keys[-1]
    block = _sprint_block(cfg, active)
    return {
        "ok": True,
        "schema": "coding_session_orchestrator.v1",
        "session_id": cfg.get("session_id"),
        "active_sprint": active,
        "active_title": active.replace("_", " "),
        "owner": block.get("owner") or "operator",
        "done_when": block.get("done_when") or block.get("desk_task") or "",
        "desk_task": (block.get("desk_task") or "").strip(),
        "artifact": block.get("artifact") or "",
        "sprint_checks": checks,
        "completed_sprints": completed,
        "all_sprints_done": len(completed) >= len(keys) and all(c.get("pass") for c in checks),
        "ts": _utc(),
    }


def _knowns_markdown(knowns: list[str]) -> str:
    return "\n".join(f"- {k}" for k in knowns if k.strip())


def _unknowns_markdown(unknowns: list[str]) -> str:
    return "\n".join(f"- {u}" for u in unknowns if u.strip())


def _current_sprint_markdown(status: dict[str, Any]) -> str:
    key = status.get("active_sprint") or "?"
    title = status.get("active_title") or key.replace("_", " ")
    owner = status.get("owner") or "operator"
    done_when = status.get("done_when") or ""
    task = status.get("desk_task") or ""
    art = status.get("artifact") or ""
    active_chk = next((c for c in (status.get("sprint_checks") or []) if c.get("sprint") == key), {})
    sprint_pass = active_chk.get("pass")
    st_label = "done" if sprint_pass else "in_progress"
    lines = [
        f"**{key}** ({title}) — owner: {owner} · status: `{st_label}`",
    ]
    if done_when:
        lines.append(f"- done_when: {done_when[:200]}")
    if task:
        lines.append(f"- desk_task: {task.split(chr(10))[0][:200]}")
    if art:
        lines.append(f"- artifact: `{art}`")
    return "\n".join(lines)


def _orchestrator_scratch(status: dict[str, Any], cfg: dict[str, Any]) -> str:
    sid = (cfg.get("session_id") or "coding-session").strip()
    active = status.get("active_sprint") or "?"
    blockers: list[str] = []
    active_chk = next((c for c in (status.get("sprint_checks") or []) if c.get("sprint") == active), {})
    if not active_chk.get("pass"):
        blockers.append(active_chk.get("reason") or "sprint gate open")
    next_action = recommend_desk_action(status=status, config=cfg)
    return f"""Session `{sid}` · orchestrator PO/SM · {_utc()[:16]}Z
- **Active sprint:** `{active}`
- **Acceptance:** {(status.get('done_when') or status.get('desk_task') or 'see Current sprint')[:120]}
- **Blockers:** {', '.join(blockers) if blockers else '(none)'}
- **Next desk action:** {next_action}
- Ponytail: FILE canvas → wake → FILE → Done → bead.
- Playbook: `{cfg.get('playbook') or 'code_scout_janitor'}` · mode `{cfg.get('loop_mode') or 'step'}`"""


def recommend_desk_action(*, status: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> str:
    cfg = config or load_config()
    st = status or assess_sprint_status(config=cfg)
    active = st.get("active_sprint") or ""
    active_chk = next((c for c in (st.get("sprint_checks") or []) if c.get("sprint") == active), {})

    if active.endswith("preflight") or "preflight" in str(st.get("done_when") or "").lower():
        if not active_chk.get("pass"):
            return "run `python main.py coding-session preflight` — fix failing gates"
        return "preflight passed — seed desk if needed, then **Step** sprint_1"

    if not active_chk.get("pass"):
        task = (st.get("desk_task") or "").split("\n")[0][:100]
        if task:
            return f"Step cycle: Local canvas commit → DeepSeek validate — {task}"
        return "Step cycle — commit intent on canvas, then conductor Step"

    if st.get("all_sprints_done"):
        return "session sprints complete — verify session_done gates, append ## Done"

    return "advance sprint — run orchestrate tick, then Step"


def plan_session(*, config: dict[str, Any] | None = None, update_desk: bool = True) -> dict[str, Any]:
    """Populate Knowns / Unknowns / Current sprint + orchestrator scratch on desk canvas."""
    from mag.agent_desk import set_desk_section

    cfg = config or load_config()
    if not cfg.get("ok"):
        return cfg

    status = assess_sprint_status(config=cfg)
    knowns = _default_knowns(cfg)
    unknowns = _default_unknowns(cfg)

    state = {
        "schema": "coding_session_orchestrator.v1",
        "session_id": cfg.get("session_id"),
        "active_sprint": status.get("active_sprint"),
        "completed_sprints": status.get("completed_sprints") or [],
        "planned_ts": _utc(),
        "knowns_count": len(knowns),
        "unknowns_count": len(unknowns),
    }
    _save_orch_state(state)

    if update_desk:
        set_desk_section("Knowns", _knowns_markdown(knowns))
        set_desk_section("Unknowns", _unknowns_markdown(unknowns))
        set_desk_section("Current sprint", _current_sprint_markdown(status))
        set_desk_section("Conductor scratch", _orchestrator_scratch(status, cfg))

    return {
        "ok": True,
        "planned": update_desk,
        "session_id": cfg.get("session_id"),
        "active_sprint": status.get("active_sprint"),
        "knowns": knowns,
        "unknowns": unknowns,
        "current_sprint": status,
        "recommended_action": recommend_desk_action(status=status, config=cfg),
        "state_path": _rel_path(ORCH_STATE_PATH),
        "ts": _utc(),
    }


def advance_sprint_if_ready(*, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    status = assess_sprint_status(config=cfg)
    state = _load_orch_state()
    active = status.get("active_sprint") or ""
    active_chk = next((c for c in (status.get("sprint_checks") or []) if c.get("sprint") == active), {})

    steal = (cfg.get("steal_protocol") or {}) if isinstance(cfg.get("steal_protocol"), dict) else {}
    verifier_block = False
    verifier_out: dict[str, Any] | None = None
    if steal.get("enabled", True) and steal.get("verifier_before_advance", True):
        from mag.desk_observer import verify_sprint_handoff

        verifier_out = verify_sprint_handoff(config=cfg)
        if active_chk.get("pass") and not verifier_out.get("approve_advance"):
            verifier_block = True

    advanced = False
    new_active = active
    if active_chk.get("pass") and not verifier_block:
        keys = _sprint_keys(cfg)
        if active in keys:
            idx = keys.index(active)
            if idx + 1 < len(keys):
                new_active = keys[idx + 1]
                advanced = new_active != active
    state["active_sprint"] = new_active
    state["completed_sprints"] = status.get("completed_sprints") or []
    state["last_advance_ts"] = _utc()
    out = {"advanced": advanced, "from": active, "to": new_active, "status": status}
    if verifier_out:
        out["verifier"] = verifier_out
    if verifier_block:
        out["verifier_blocked"] = True
    _save_orch_state(state)
    return out


def orchestrator_tick(
    *,
    auto_step: bool = False,
    operator_note: str = "",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """PO/SM tick: assess sprint, refresh plan sections, optionally run conductor Step."""
    cfg = config or load_config()
    if not cfg.get("ok"):
        return cfg

    advance = advance_sprint_if_ready(config=cfg)
    plan = plan_session(config=cfg, update_desk=True)
    status = plan.get("current_sprint") or assess_sprint_status(config=cfg)
    recommended = recommend_desk_action(status=status, config=cfg)

    steal = (cfg.get("steal_protocol") or {}) if isinstance(cfg.get("steal_protocol"), dict) else {}
    observer_out: dict[str, Any] | None = None
    if steal.get("enabled", True):
        from mag.desk_observer import observer_tick

        observer_out = observer_tick(config=cfg, live=bool(steal.get("observer_live")), inject=True)

    out: dict[str, Any] = {
        "ok": True,
        "schema": "coding_session_orchestrator.v1",
        "session_id": cfg.get("session_id"),
        "active_sprint": status.get("active_sprint"),
        "recommended_action": recommended,
        "advance": advance,
        "plan": {k: plan.get(k) for k in ("knowns", "unknowns", "recommended_action") if k in plan},
        "ts": _utc(),
    }
    if observer_out:
        out["observer"] = observer_out

    loop_mode = (cfg.get("loop_mode") or "step").strip().lower()
    if auto_step and loop_mode != "loop":
        from mag.coding_session_loop import run_board_step

        note = operator_note.strip() or f"Sprint {status.get('active_sprint')}: {recommended}"
        step = run_board_step(auto_act=True, note=note)
        out["step"] = step
        out["auto_step"] = True
    else:
        out["auto_step"] = False
        if auto_step and loop_mode == "loop":
            out["step_skipped"] = "loop_mode=loop blocked — use step until trust tier ≥ 1"

    if status.get("all_sprints_done"):
        from mag.coding_session_loop import close_session_if_ready

        close_out = close_session_if_ready(config=cfg)
        out["close"] = close_out
        if close_out.get("closed"):
            out["recommended_action"] = "session closed — session_done gates filed"

    return out
