"""Feature Lab viewport over existing worktrees, evidence, and handoff rails.

The lab owns no scheduler and no promotion database.  It reads Git worktrees,
roadmap/factory evidence, orchestrator tasks, and peer handoffs.  Its only write
is an existing peer-handoff request for verification or graduation review.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from config import ROOT


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", "-c", f"safe.directory={root}", *args], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10, check=False)
        return p.returncode, (p.stdout or p.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def _worktrees() -> list[dict[str, str]]:
    code, raw = _git(ROOT, "worktree", "list", "--porcelain")
    if code:
        return []
    rows: list[dict[str, str]] = []
    row: dict[str, str] = {}
    for line in raw.splitlines() + [""]:
        if not line.strip():
            if row:
                rows.append(row)
                row = {}
            continue
        key, _, value = line.partition(" ")
        row[key] = value
    return rows


def _slug(branch: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", branch.lower()).strip("-")[:100]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _evidence_for(root: Path, branch: str, head: str) -> dict[str, Any] | None:
    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    for path in (root / "memory" / "runs" / "roadmap").glob("*.json") if (root / "memory" / "runs" / "roadmap").is_dir() else []:
        value = _read_json(path)
        if value and value.get("verified") is True and value.get("branch") == branch:
            candidates.append((path.stat().st_mtime, path, value))
    for path in (root / "memory" / "factory").glob("build_audit-*.json") if (root / "memory" / "factory").is_dir() else []:
        value = _read_json(path)
        # Factory records predate branch binding. Show them as evidence, but do
        # not let an unbound pass graduate a different worktree.
        if value and value.get("verdict") == "pass" and value.get("branch") == branch:
            candidates.append((path.stat().st_mtime, path, value))
    if not candidates:
        return None
    _, path, value = max(candidates, key=lambda x: x[0])
    try:
        display = path.relative_to(root).as_posix()
    except ValueError:
        display = str(path)
    proof_commit = str(value.get("commit") or (value.get("verifier") or {}).get("commit") or "")
    bound = bool(proof_commit and head.startswith(proof_commit))
    return {
        "path": display,
        "schema": value.get("schema"),
        "verified": bool(value.get("verified") or value.get("verdict") == "pass"),
        "bound_to_head": bound,
        "proof_commit": proof_commit or None,
        "tests": value.get("tests") or value.get("verifier") or {},
        "timestamp": value.get("ts") or value.get("timestamp"),
    }


def _task_for(branch: str) -> dict[str, Any] | None:
    try:
        from mag.orchestrator import list_tasks_live

        for task in list_tasks_live(limit=80):
            text = " ".join(str(task.get(k) or "") for k in ("branch", "goal", "tag", "detail"))
            if branch in text or _slug(branch) in _slug(text):
                return {k: task.get(k) for k in ("task_id", "status", "seat", "provider", "phase", "detail")}
    except Exception:
        pass
    return None


def _handoff_for(branch: str) -> dict[str, Any] | None:
    try:
        from mag.peer_handoff import list_peer_handoffs

        for item in list_peer_handoffs(limit=80):
            meta = item.get("meta") or {}
            if meta.get("feature_branch") == branch:
                return {k: item.get(k) for k in ("handoff_id", "status", "goal", "ts")}
    except Exception:
        pass
    return None


def _candidate(row: dict[str, str], operational_branch: str) -> dict[str, Any]:
    root = Path(row.get("worktree") or ROOT)
    branch = str(row.get("branch") or "").removeprefix("refs/heads/")
    head = row.get("HEAD") or ""
    _, dirty_raw = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    up_code, upstream = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    ahead = behind = None
    if up_code == 0 and upstream:
        div_code, div = _git(root, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        if div_code == 0 and len(div.split()) == 2:
            behind, ahead = (int(x) for x in div.split())
    evidence = _evidence_for(root, branch, head)
    task = _task_for(branch)
    handoff = _handoff_for(branch)
    gates = {
        "isolated": branch != operational_branch,
        "clean": not bool(dirty_raw.strip()),
        "tracked": up_code == 0,
        "synced": up_code == 0 and ahead == 0 and behind == 0,
        "verified": bool(evidence and evidence.get("verified") and evidence.get("bound_to_head")),
    }
    ready = all(gates.values()) and branch != operational_branch
    if handoff and handoff.get("status") == "graduation_requested":
        stage = "graduation queued"
    elif ready:
        stage = "ready for review"
    elif task and task.get("status") in {"running", "queued"}:
        stage = "testing"
    elif not gates["clean"]:
        stage = "building"
    else:
        stage = "needs verification"
    return {
        "id": _slug(branch or str(root)), "branch": branch, "root": str(root),
        "head": head[:12], "upstream": upstream if up_code == 0 else None, "ahead": ahead, "behind": behind,
        "operational": branch == operational_branch, "stage": stage, "gates": gates,
        "graduation_ready": ready, "evidence": evidence, "task": task, "handoff": handoff,
    }


def status() -> dict[str, Any]:
    from mag.env_registry import get_track

    operational = get_track("operational") or {}
    operational_branch = str(operational.get("branch") or "unify-mag-home")
    candidates = [_candidate(row, operational_branch) for row in _worktrees()]
    candidates.sort(key=lambda x: (x["operational"], not x["graduation_ready"], x["branch"]))
    experimental = [x for x in candidates if not x["operational"]]
    return {
        "ok": True, "schema": "feature_lab.v1",
        "policy": "Tests happen on isolated worktrees. Graduation files an audit handoff; it never merges from the dashboard.",
        "operational_branch": operational_branch,
        "metrics": {
            "experiments": len(experimental),
            "building": sum(x["stage"] == "building" for x in experimental),
            "testing": sum(x["stage"] in {"testing", "needs verification"} for x in experimental),
            "ready": sum(x["graduation_ready"] for x in experimental),
            "queued": sum(x["stage"] == "graduation queued" for x in experimental),
        },
        "candidates": candidates,
        "sources": ["git worktree list", "git status", "configs/env_tracks.yaml", "memory/runs/roadmap/*.json", "memory/factory/build_audit-*.json", "queue/handoff/peer-*.json"],
    }


def request(branch: str, action: str) -> dict[str, Any]:
    snapshot = status()
    candidate = next((x for x in snapshot["candidates"] if x["branch"] == branch), None)
    if not candidate:
        return {"ok": False, "error": "unknown feature branch"}
    action = action.strip().lower()
    if action not in {"verify", "graduate"}:
        return {"ok": False, "error": "action must be verify or graduate"}
    if action == "graduate" and not candidate["graduation_ready"]:
        missing = [k for k, value in candidate["gates"].items() if not value]
        return {"ok": False, "error": "graduation gates are not green", "missing": missing}
    from mag.peer_handoff import file_peer_handoff

    evidence = candidate.get("evidence") or {}
    if action == "verify":
        goal = f"Verify feature branch {branch} in its isolated worktree; run focused tests and the full suite, then file branch-bound factory evidence. Do not merge."
        status_name = "verification_requested"
    else:
        goal = f"Audit verified feature branch {branch} for graduation into {snapshot['operational_branch']}. Preserve evidence and stop before merge for operator review."
        status_name = "graduation_requested"
    return file_peer_handoff(
        goal=goal, brief=goal, from_seat="feature-lab", to_seat="router",
        merge_target=snapshot["operational_branch"], status=status_name,
        commands=[f"git -C \"{candidate['root']}\" status --short", ".venv\\Scripts\\python.exe -m pytest -q"],
        meta={"kind": "feature_graduation", "feature_branch": branch, "feature_root": candidate["root"], "evidence_path": evidence.get("path")},
    )
