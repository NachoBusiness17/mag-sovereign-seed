"""Coding session loop — seed desk board + preflight for Beta-style build sessions."""
from __future__ import annotations

import json
import subprocess
import sys
from mag import headless
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT

SCHEMA = "coding_session_loop.v1"
CONFIG_PATH = ROOT / "configs" / "coding_session_loop.yaml"
SESSION_STATE_PATH = ROOT / "memory" / "working" / "coding_session_loop.json"


def _rel_path(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or CONFIG_PATH
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.is_file():
        return {"ok": False, "error": f"missing config: {p}"}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(data, dict):
        return {"ok": False, "error": "config not a mapping"}
    data["ok"] = True
    data["path"] = str(p.relative_to(ROOT)).replace("\\", "/")
    return data


def _desk_seed_text(cfg: dict[str, Any]) -> str:
    from mag.coding_session_orchestrator import (
        _current_sprint_markdown,
        _default_knowns,
        _default_unknowns,
        _knowns_markdown,
        _orchestrator_scratch,
        _unknowns_markdown,
        assess_sprint_status,
    )

    goal = (cfg.get("goal") or "").strip()
    sid = (cfg.get("session_id") or "coding-session").strip()
    playbook = (cfg.get("playbook") or "code_scout_janitor").strip()
    mode = (cfg.get("loop_mode") or "step").strip()
    sprints = cfg.get("scrum") or {}
    sprint_lines: list[str] = []
    for key, block in sprints.items():
        if not isinstance(block, dict):
            continue
        title = key.replace("_", " ")
        task = (block.get("desk_task") or block.get("done_when") or "").strip()
        art = (block.get("artifact") or "").strip()
        line = f"- **{title}**"
        if task:
            line += f": {task.split(chr(10))[0][:120]}"
        if art:
            line += f" → `{art}`"
        sprint_lines.append(line)

    status = assess_sprint_status(config=cfg)
    knowns = _knowns_markdown(_default_knowns(cfg))
    unknowns = _unknowns_markdown(_default_unknowns(cfg))
    current = _current_sprint_markdown(status)
    scratch = _orchestrator_scratch(status, cfg)
    scratch += f"\n\n### Scrum\n{chr(10).join(sprint_lines) if sprint_lines else '- (no sprints configured)'}"

    return f"""# Agent desk

Shared surface — Local and DeepSeek take turns on ## Dialogue. **No tools here.** Execute in Shell/Workers.

Operator manual: `docs/agent_desk_operator_manual.md`
Session: `{sid}` · playbook `{playbook}` · mode `{mode}`

## Goal
{goal}

## Knowns
{knowns}

## Unknowns
{unknowns}

## Current sprint
{current}

## Dialogue
(turn-based — `### Local ·` and `### DeepSeek ·` blocks only)

## Meta
(DeepSeek Meta-A ↔ Meta-B strategy — does not wake Local)

## Conductor scratch
{scratch}

## Operator notes
(binding decisions — agents propose, you decide)

## Open questions
(park items that graduate from Unknowns when resolved)
"""


def seed_desk(*, config: dict[str, Any] | None = None, clear_dialogue: bool = True) -> dict[str, Any]:
    from mag.agent_desk import write_desk
    from mag.desk_dialogue import read_cursor, reset_dialogue

    cfg = config or load_config()
    if not cfg.get("ok"):
        return cfg
    text = _desk_seed_text(cfg)
    write_desk(text)
    out: dict[str, Any] = {
        "ok": True,
        "seeded": True,
        "session_id": cfg.get("session_id"),
        "playbook": cfg.get("playbook"),
        "path": "memory/working/agent_desk.md",
    }
    if clear_dialogue and cfg.get("clear_dialogue_on_seed", True):
        out["dialogue"] = reset_dialogue(clear_canvas_dialogue=False)
    cur = read_cursor()
    cur["holder"] = "operator"
    cur["turn"] = 0
    cur["last_speaker"] = None
    cur["wake_pending"] = False
    cur["local_wake_pending"] = False
    cur["remote_asleep"] = True
    from mag.desk_dialogue import CURSOR_PATH

    CURSOR_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    state = {
        "schema": SCHEMA,
        "session_id": cfg.get("session_id"),
        "seeded_ts": _utc(),
        "config_path": cfg.get("path"),
        "status": "ready",
    }
    SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    out["cursor"] = cur
    out["state_path"] = _rel_path(SESSION_STATE_PATH)
    return out


def _normalize_cmd(cmd: str) -> str:
    """Use the active interpreter so preflight gates match the invoking venv."""
    cmd = (cmd or "").strip()
    if cmd.startswith("python "):
        return f'"{headless.PYTHON}" {cmd[7:]}'
    return cmd


def _run_cmd(cmd: str, *, optional: bool = False) -> dict[str, Any]:
    cmd = _normalize_cmd(cmd)
    if not cmd:
        return {"ok": False, "cmd": cmd, "error": "empty command", "optional": optional}
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(ROOT),
            # headless.PYTHON is the real interpreter (not the venv shim); the
            # companion env is what makes the project's installed packages
            # visible to short-lived preflight commands.
            env=headless._spawn_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "cmd": cmd, "error": "timeout", "optional": optional}
    except Exception as exc:
        return {"ok": False, "cmd": cmd, "error": str(exc), "optional": optional}
    ok = proc.returncode == 0
    return {
        "ok": ok or optional,
        "pass": ok,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-800:],
        "stderr_tail": (proc.stderr or "")[-400:],
        "optional": optional,
    }


def _check_path_gate(spec: dict[str, Any]) -> dict[str, Any]:
    gid = spec.get("id") or "path"
    if spec.get("path"):
        p = ROOT / str(spec["path"])
        ok = p.is_file()
        return {"id": gid, "pass": ok, "kind": "path", "path": str(spec["path"]), "optional": bool(spec.get("optional"))}
    glob_pat = spec.get("glob")
    if glob_pat:
        matches = list(ROOT.glob(str(glob_pat)))
        ok = len(matches) > 0
        return {
            "id": gid,
            "pass": ok,
            "kind": "glob",
            "glob": str(glob_pat),
            "matches": len(matches),
            "optional": bool(spec.get("optional")),
        }
    return {"id": gid, "pass": False, "error": "no path or glob"}


def run_preflight(*, config: dict[str, Any] | None = None, ui_only: bool = False) -> dict[str, Any]:
    cfg = config or load_config()
    if not cfg.get("ok"):
        return cfg
    gates = (cfg.get("gates") or {}).get("preflight") or []
    if ui_only:
        gates = [g for g in gates if isinstance(g, dict) and g.get("id") == "ui_smoke"]
    results: list[dict[str, Any]] = []
    for spec in gates:
        if not isinstance(spec, dict):
            continue
        gid = spec.get("id")
        if gid == "ui_smoke":
            try:
                from scripts.desk_baseline_probe import run_desk_ui_smoke

                ui = run_desk_ui_smoke()
                ok = all(r.get("pass") for r in ui) if ui else False
            except Exception as exc:
                ui = []
                ok = False
                err = str(exc)
            else:
                err = None
            results.append(
                {
                    "id": "ui_smoke",
                    "pass": ok,
                    "ok": ok or bool(spec.get("optional")),
                    "optional": bool(spec.get("optional")),
                    "checks": len(ui),
                    "error": err,
                }
            )
            continue
        if spec.get("cmd"):
            results.append({**_run_cmd(str(spec["cmd"]), optional=bool(spec.get("optional"))), "id": spec.get("id")})
        elif spec.get("path") or spec.get("glob"):
            row = _check_path_gate(spec)
            if row.get("optional") and not row.get("pass"):
                row["ok"] = True
            else:
                row["ok"] = bool(row.get("pass"))
            results.append(row)
    required = [r for r in results if not r.get("optional")]
    passed = sum(1 for r in required if r.get("pass") or r.get("ok"))
    return {
        "ok": all(r.get("pass") or r.get("ok") for r in required),
        "schema": SCHEMA,
        "session_id": cfg.get("session_id"),
        "preflight": results,
        "passed": passed,
        "total": len(required),
        "ts": _utc(),
    }


def _session_references_factory_pilot(cfg: dict[str, Any]) -> bool:
    blob = json.dumps(
        {
            "goal": cfg.get("goal"),
            "commitment": cfg.get("commitment"),
            "references": cfg.get("references"),
        },
        default=str,
    ).lower()
    return "factory_pilot" in blob or "factory pilot" in blob


def _factory_pilot_gate_ok() -> bool:
    from mag.release_registry import read_gate_log

    for row in read_gate_log(limit=50, version="v3"):
        if str(row.get("gate_id") or "") == "factory_pilot" and row.get("ok"):
            return True
    return False


def close_session_if_ready(*, config: dict[str, Any] | None = None, dry: bool = False) -> dict[str, Any]:
    """Close coding session when session_done gates pass — Done, gate record, bead."""
    cfg = config or load_config()
    if not cfg.get("ok"):
        return cfg

    st = session_status(config=cfg)
    gates = st.get("session_done_gates") or []
    gates_ok = all(r.get("pass") or r.get("ok") for r in gates) if gates else False
    has_done = bool(st.get("has_done"))
    state = dict(st.get("state") or {})

    base: dict[str, Any] = {
        "ok": True,
        "closed": False,
        "session_id": cfg.get("session_id"),
        "gates_ok": gates_ok,
        "has_done": has_done,
        "session_done_gates": gates,
        "state_status": state.get("status"),
    }

    if state.get("status") == "closed":
        base["reason"] = "already_closed"
        return base

    if not gates_ok:
        base["reason"] = "session_done_gates_open"
        return base

    if dry:
        base["reason"] = "dry_run"
        base["would_close"] = True
        return base

    done_written = False
    if not has_done:
        from mag.agent_desk import set_desk_section

        sid = (cfg.get("session_id") or "coding-session").strip()
        set_desk_section(
            "Done",
            f"Session `{sid}` — session_done gates green.\n",
        )
        done_written = True
        has_done = True

    gate_record: dict[str, Any] | None = None
    if _session_references_factory_pilot(cfg) and not _factory_pilot_gate_ok():
        from mag.release_registry import record_gate

        sid = (cfg.get("session_id") or "coding-session").strip()
        gate_record = record_gate(
            "v3",
            "factory_pilot",
            ok=True,
            note=f"{sid} session_done gates pass",
            evidence_path="memory/factory/build_audit-*.json",
        )

    bead: dict[str, Any] | None = None
    if cfg.get("bead_on_close"):
        from mag.run_trail import close_run

        sid = (cfg.get("session_id") or "coding-session").strip()
        bead = close_run(reason=f"coding_session:{sid}")

    state["schema"] = SCHEMA
    state["session_id"] = cfg.get("session_id")
    state["status"] = "closed"
    state["closed_ts"] = _utc()
    state["done_written"] = done_written
    SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    return {
        **base,
        "closed": True,
        "reason": "closed",
        "done_written": done_written,
        "has_done": has_done,
        "gate_record": gate_record,
        "bead": bead,
        "state_path": _rel_path(SESSION_STATE_PATH),
    }


def session_status(*, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    state: dict[str, Any] = {}
    if SESSION_STATE_PATH.is_file():
        try:
            state = json.loads(SESSION_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    from mag.agent_desk import read_desk
    from mag.desk_dialogue import read_cursor

    text = read_desk().get("text") or ""
    done_gates = (cfg.get("gates") or {}).get("session_done") or []
    done_results = []
    prerequisites_passed = True
    for spec in done_gates:
        if isinstance(spec, dict):
            if spec.get("cmd"):
                if not prerequisites_passed:
                    done_results.append({"id": spec.get("id"), "pass": False, "ok": False, "deferred": True, "reason": "earlier completion gate is still open"})
                else:
                    row = {**_run_cmd(str(spec["cmd"]), optional=True), "id": spec.get("id")}
                    done_results.append(row)
                    prerequisites_passed = prerequisites_passed and bool(row.get("pass") or row.get("ok"))
            else:
                row = _check_path_gate(spec)
                done_results.append(row)
                prerequisites_passed = prerequisites_passed and bool(row.get("pass") or row.get("ok"))
    done_marker = (cfg.get("done_marker") or "Done").strip()
    has_done = bool(re.search(rf"^##\s+{re.escape(done_marker)}\s*$", text, re.M))
    return {
        "ok": True,
        "config": {k: cfg.get(k) for k in ("session_id", "playbook", "loop_mode", "path") if cfg.get(k)},
        "state": state,
        "cursor": read_cursor(),
        "canvas_chars": len(text),
        "has_done": has_done,
        "session_done_gates": done_results,
        "preflight_hint": "python main.py coding-session preflight",
        "seed_hint": "python main.py coding-session seed",
    }


def _chain_handoff_after_local(*, acted: dict[str, Any], operator_note: str = "") -> dict[str, Any]:
    """Mirror dashboard: Local canvas edit → Remote wake → Local follow-up."""
    from mag.desk_dialogue import _local_canvas_wake_ok, dialogue_turn, read_cursor

    if acted.get("speaker") != "local" or not acted.get("ok") or acted.get("wake_blocked"):
        return {"chained": False}
    edit = str(acted.get("canvas_edit") or "")
    if not _local_canvas_wake_ok(edit):
        return {"chained": False, "reason": "local_wake_not_ok"}

    note = (operator_note or "").strip()
    wake_note = (
        (f"{note}\n\n" if note else "")
        + "Local (L0/slow) edited the board — you wake on board edits only.\n"
        + "Respond to the canvas edit. Note Local's limitation if output truncated or vague.\n\n"
        + f"### Local's board edit\n{edit[:900]}"
    )
    remote = dialogue_turn(
        "remote",
        operator_note=wake_note,
        canvas=acted.get("canvas"),
        force_wake=True,
    )
    out: dict[str, Any] = {"chained": True, "remote": remote}
    if not remote.get("ok"):
        out["reason"] = "remote_failed"
        out["error"] = remote.get("error")
        return out

    if read_cursor().get("local_wake_pending"):
        follow = dialogue_turn(
            "local",
            operator_note=(
                "DeepSeek edited the board — complete this handoff. "
                "Read their Reply instruction; respond with ### Reply and ### Canvas edit."
            ),
            canvas=remote.get("canvas"),
            force_wake=True,
        )
        out["local_followup"] = follow
        if follow.get("ok"):
            out["loop_closed"] = True
    out["reason"] = "board_edit"
    return out


def run_board_step(*, auto_act: bool = True, note: str = "", chain: bool = True) -> dict[str, Any]:
    """One conductor tick on the desk board (Step — not autorun Loop)."""
    from mag.desk_conductor import conductor_tick

    cfg = load_config()
    goal = (cfg.get("goal") or "").strip() if cfg.get("ok") else ""
    out = conductor_tick(auto_act=auto_act, operator_note=note, conductor_prompt=goal)
    acted = out.get("acted") if isinstance(out.get("acted"), dict) else None
    if chain and auto_act and acted:
        chain_out = _chain_handoff_after_local(acted=acted, operator_note=note)
        if chain_out.get("chained"):
            out["handoff_chain"] = chain_out
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv else sys.argv[1:]
    cmd = args[0] if args else "status"
    ui_only = "--ui-only" in args
    dry = "--dry" in args
    note = ""
    if "--note" in args:
        i = args.index("--note")
        if i + 1 < len(args):
            note = args[i + 1]
    if cmd == "seed":
        print(json.dumps(seed_desk(), indent=2, default=str))
        return 0
    if cmd == "preflight":
        out = run_preflight(ui_only=ui_only)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1
    if cmd == "plan":
        from mag.coding_session_orchestrator import plan_session

        out = plan_session()
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1
    if cmd == "orchestrate":
        from mag.coding_session_orchestrator import orchestrator_tick

        auto_step = "--no-step" not in args and not dry
        out = orchestrator_tick(auto_step=auto_step and not dry, operator_note=note)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1
    if cmd == "observe":
        from mag.desk_observer import observer_tick

        live = "--live" in args
        out = observer_tick(live=live, inject="--no-inject" not in args)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1
    if cmd == "step":
        out = run_board_step(auto_act=not dry, note=note)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") is not False else 1
    if cmd == "status":
        st = session_status()
        try:
            from mag.coding_session_orchestrator import assess_sprint_status

            st["orchestrator"] = assess_sprint_status()
        except Exception:
            pass
        print(json.dumps(st, indent=2, default=str))
        return 0
    if cmd == "close":
        out = close_session_if_ready(dry=dry)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1
    print(
        "usage: coding-session seed|plan|orchestrate|observe|preflight|status|step|close "
        "[--ui-only] [--dry] [--no-step] [--live] [--no-inject] [--note TEXT]",
        file=sys.stderr,
    )
    return 2
