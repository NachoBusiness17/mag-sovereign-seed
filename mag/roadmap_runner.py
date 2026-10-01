"""Compile the next release-roadmap gate into a frozen factory run."""
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT


def _rel_posix(path) -> str:
    """Repo-relative posix path, absolute when outside ROOT.

    Cause (ball3 follow-up sweep 2026-09-29): display/receipt derivations
    raised ValueError whenever the path lived outside the repo (the suite
    runs use an out-of-repo pytest basetemp). Same fix as the driver-meter
    lane's _rel_posix in tools/stealth_driver.py.
    """
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()



ROADMAP_PATH = ROOT / "configs" / "version_roadmap.yaml"
RELEASES_PATH = ROOT / "configs" / "releases.yaml"
BUILD_DIR = ROOT / "queue" / "handoff"
RUN_CONFIG_DIR = ROOT / "memory" / "working" / "roadmap_runs"
EVIDENCE_DIR = ROOT / "memory" / "runs" / "roadmap"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return data if isinstance(data, dict) else {}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")[:80]


def _passed(version: str) -> set[str]:
    from mag.release_registry import read_gate_log

    return {
        str(row.get("gate_id"))
        for row in read_gate_log(limit=1000, version=version)
        if row.get("ok") and row.get("gate_id")
    }


def select_next(*, version: str | None = None, gate: str | None = None) -> dict[str, Any]:
    """Select the first executable, unpassed release gate in roadmap order."""
    roadmap = _load(ROADMAP_PATH)
    registry = _load(RELEASES_PATH)
    arc = [row for row in roadmap.get("version_arc") or [] if isinstance(row, dict)]
    releases = {str(row.get("id")): row for row in registry.get("releases") or [] if isinstance(row, dict)}
    shipped = {str(row.get("id")) for row in arc if row.get("status") == "shipped"}

    for arc_row in arc:
        vid = str(arc_row.get("id") or "")
        if version and vid.lstrip("v") != str(version).lstrip("v"):
            continue
        status = str(arc_row.get("status") or "")
        if status == "shipped":
            continue
        if status == "curriculum_tbd":
            if version:
                return {"ok": False, "error": "curriculum_tbd", "version": vid, "reason": "Roadmap gates must be defined before autonomous execution."}
            continue
        rel = releases.get(vid) or {}
        parent = str(rel.get("parent") or "")
        if parent and parent not in shipped:
            return {"ok": False, "error": "parent_not_shipped", "version": vid, "parent": parent}
        gates = rel.get("gates")
        if not isinstance(gates, list) or not gates:
            return {"ok": False, "error": "gates_not_defined", "version": vid}
        passed = _passed(vid)
        for gate_row in gates:
            if not isinstance(gate_row, dict) or not gate_row.get("id"):
                continue
            gid = str(gate_row["id"])
            if gate and gid != gate:
                continue
            if gid in passed:
                continue
            sources = []
            for key in ("notes_path", "plan_path", "direction_path", "run_sheet_path", "mold_path", "pipe_path"):
                if rel.get(key):
                    sources.append(str(rel[key]))
            sources.extend(str(t.get("path")) for t in rel.get("tracks") or [] if isinstance(t, dict) and t.get("path"))
            return {
                "ok": True,
                "schema": "roadmap_selection.v1",
                "version": vid,
                "era": rel.get("era") or arc_row.get("era"),
                "meaning": arc_row.get("meaning") or rel.get("meaning") or "",
                "commitment": rel.get("commitment"),
                "gate": {**gate_row, "id": gid},
                "passed_gates": sorted(passed),
                "sources": sources,
            }
        if gate:
            return {"ok": False, "error": "gate_not_available", "version": vid, "gate": gate}
        return {"ok": False, "error": "release_has_no_remaining_gates", "version": vid}
    return {"ok": False, "error": "no_executable_roadmap_work"}


def compile_run(selection: dict[str, Any]) -> dict[str, Any]:
    if not selection.get("ok"):
        return selection
    vid = str(selection["version"])
    gate = dict(selection["gate"])
    gid = str(gate["id"])
    slug = f"{_slug(vid)}-{_slug(gid)}"
    build_path = BUILD_DIR / f"BUILD-roadmap-{slug}.md"
    config_path = RUN_CONFIG_DIR / f"{slug}.yaml"
    evidence_path = EVIDENCE_DIR / f"{slug}.json"
    sources = [s for s in selection.get("sources") or [] if (ROOT / s).is_file()]
    goal = (
        f"[build] Complete roadmap {vid} gate {gid} from the frozen contract at "
        f"queue/handoff/{build_path.name}. Use the cheapest capable worker to inspect and implement "
        "only this gate, run its focused tests once, then return a concise result to the verifier."
    )
    source_lines = "\n".join(f"- `{s}`" for s in sources) or "- `configs/releases.yaml`"
    description = str(gate.get("description") or f"Implement and verify release gate {gid}.")
    verify = gate.get("verify") or []
    verify_lines = "\n".join(f"- {v}" for v in verify) if isinstance(verify, list) else ""
    build = f"""# BUILD — roadmap {vid} / {gid}

**Status:** frozen
**Tier:** T2
**Commitment:** `{selection.get('commitment') or vid}`
**Generated:** {_now()}

## Goal

{description}

This is one gate-sized branch in the filed roadmap. Do not expand scope to the rest of {vid}.

## Sources

{source_lines}

## Required behavior

- Inspect existing implementation before adding a parallel subsystem.
- Prefer the cheapest capable local/DeepSeek worker; summon frontier judgment only for uncertainty.
- Preserve T0/T1 locally and keep external seats optional.
- Add or update focused tests for the gate.
- Run focused tests once. The roadmap verifier owns the full repository suite, evidence file, commit, and release-gate record.
- If an unrelated infrastructure or test-harness problem appears, report it concisely after one diagnosed retry; do not investigate operating-system locks or broaden scope.
{verify_lines}

## Done when

1. Focused tests for `{gid}` pass.
2. Return control to the roadmap verifier. It will run full `pytest tests -q`, file evidence, commit, and record the gate.

## Stop conditions

Stop for completion or a genuine external dependency, secret, spending/publishing approval, irreversible action, or a focused-test failure that cannot be repaired safely. Do not diagnose unrelated full-suite or operating-system failures; the verifier owns them.
"""
    cfg = {
        "schema": "coding_session_loop.v1",
        "session_id": f"roadmap-{slug}",
        "commitment": selection.get("commitment") or f"roadmap-{vid}",
        "goal": goal,
        "playbook": "code_scout_janitor",
        "surface": "roadmap",
        "loop_mode": "loop",
        "gates": {
            "preflight": [
                {"id": "frozen_build", "cmd": f'python -c "from mag.factory_gate import check_frozen_build; assert check_frozen_build({goal!r}).get(\'ok\')"'},
            ],
            "session_done": [
                {"id": "roadmap_evidence", "path": _rel_posix(evidence_path)},
                {"id": "full_tests", "cmd": "python -m pytest tests -q"},
            ],
        },
        "scrum": {
            "sprint_0_preflight": {"owner": "router", "done_when": "frozen BUILD gate passes"},
            "sprint_1_implement": {"owner": "deepseek+local", "desk_task": goal, "artifact": _rel_posix(evidence_path)},
            "sprint_2_verify": {"owner": "verifier", "done_when": "full tests green and evidence filed"},
        },
        "knowns": [f"Roadmap selected {vid}.{gid}", f"Frozen contract: queue/handoff/{build_path.name}", *sources],
        "unknowns": ["Implementation delta and external blockers must be discovered from the repository and source docs."],
        "current_sprint": "sprint_0_preflight",
        "done_marker": "Done",
        "bead_on_close": True,
        "clear_dialogue_on_seed": True,
        "roadmap": {"version": vid, "gate": gid, "evidence_path": _rel_posix(evidence_path)},
    }
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    RUN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    build_path.write_text(build, encoding="utf-8")
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {
        "ok": True,
        "schema": "roadmap_run_contract.v1",
        "selection": selection,
        "goal": goal,
        "build_path": _rel_posix(build_path),
        "config_path": _rel_posix(config_path),
        "evidence_path": _rel_posix(evidence_path),
        "branch_prefix": f"mag/roadmap-{slug}",
    }


def _run_command(*args: str, timeout: int = 900) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "stdout_tail": proc.stdout[-4000:], "stderr_tail": proc.stderr[-2000:]}


def execute_contract(contract: dict[str, Any], *, dry: bool = False, timeout: int = 900) -> dict[str, Any]:
    """Create the branch, run the cheap coding seat, verify, file, and commit."""
    if dry:
        return {"ok": True, "dry": True, "phase": "prepared", "contract": contract}
    from mag.factory_machine import checkout_run_branch

    selection = contract["selection"]
    vid = str(selection["version"])
    gid = str((selection.get("gate") or {}).get("id") or "gate")
    branch = checkout_run_branch(session_id=f"{vid}-{gid}", branch_prefix=contract["branch_prefix"])
    if not branch.get("ok"):
        return {"ok": False, "phase": "branch_failed", "branch": branch, "contract": contract}

    from mag.operating_protocol import build_envelope

    envelope = build_envelope(contract["goal"], source="automation", depth="heavy_code", dry=True)
    provider = str((envelope.get("execution") or {}).get("provider") or "deepseek")
    if provider in {"ollama", "local"}:
        provider = "deepseek"
    from mag.orchestrator import spawn_task, task_status

    task = spawn_task(
        contract["goal"],
        provider=provider,
        timeout=timeout,
        tag=f"roadmap-{vid}-{gid}",
        require_build=Path(contract["build_path"]).name,
    )
    if not task.get("ok"):
        return {"ok": False, "phase": "spawn_failed", "branch": branch, "task": task, "contract": contract}
    tid = str(task["task_id"])
    deadline = time.monotonic() + max(30, timeout + 30)
    terminal = task
    while time.monotonic() < deadline:
        terminal = task_status(tid) or terminal
        if terminal.get("status") in {"done", "failed", "timeout", "stalled", "killed", "died"}:
            break
        time.sleep(2)

    worker_ok = terminal.get("status") == "done"
    tests = _run_command(str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "tests", "-q", timeout=timeout) if worker_ok else {"ok": False, "deferred": True, "reason": "worker did not finish green"}
    evidence_path = ROOT / contract["evidence_path"]
    evidence = {
        "schema": "roadmap_gate_evidence.v1",
        "ts": _now(),
        "version": vid,
        "gate": gid,
        "branch": branch.get("branch"),
        "worker": {k: terminal.get(k) for k in ("task_id", "status", "provider", "detail", "duration_s", "exit_code", "log")},
        "tests": tests,
        "contract": {k: contract.get(k) for k in ("build_path", "config_path", "goal")},
        "verified": bool(worker_ok and tests.get("ok")),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    commit: dict[str, Any] = {"ok": False, "deferred": True}
    gate_record = None
    if evidence["verified"]:
        _run_command("git", "add", "-A", timeout=60)
        diff = _run_command("git", "diff", "--cached", "--quiet", timeout=60)
        if diff.get("returncode") == 1:
            commit = _run_command("git", "commit", "-m", f"Complete roadmap {vid} gate {gid}", timeout=120)
        else:
            commit = {"ok": True, "no_changes": True}
        if commit.get("ok"):
            from mag.release_registry import record_gate

            gate_record = record_gate(vid, gid, ok=True, note="Roadmap worker and full suite green", evidence_path=contract["evidence_path"])
    return {
        "ok": bool(evidence["verified"] and commit.get("ok")),
        "schema": "roadmap_run.v1",
        "phase": "verified" if evidence["verified"] else "failed_verification",
        "contract": contract,
        "branch": branch,
        "envelope": envelope,
        "task": terminal,
        "tests": tests,
        "evidence_path": contract["evidence_path"],
        "commit": commit,
        "gate_record": gate_record,
    }


def run_next(*, version: str | None = None, gate: str | None = None, prepare_only: bool = False, dry: bool = False, max_ticks: int = 50) -> dict[str, Any]:
    selection = select_next(version=version, gate=gate)
    contract = compile_run(selection)
    if not contract.get("ok") or prepare_only:
        return contract
    return execute_contract(contract, dry=dry, timeout=max(120, int(max_ticks) * 30))


def status() -> dict[str, Any]:
    return {"ok": True, "schema": "roadmap_runner_status.v1", "next": select_next()}
