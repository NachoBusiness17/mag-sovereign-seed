"""Read-only repository readiness for instant multi-agent handoff."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from config import ROOT


def _git(*args: str, root: Path = ROOT) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=8, check=False,
        )
        return proc.returncode, (proc.stdout or proc.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def repo_readiness(root: Path = ROOT) -> dict[str, Any]:
    """Describe repository state without fetching, checking out, or writing refs."""
    ok, branch = _git("branch", "--show-current", root=root)
    if ok:
        return {"ok": False, "schema": "repo_readiness.v1", "error": branch}
    _, head = _git("rev-parse", "--short=12", "HEAD", root=root)
    _, status = _git("status", "--porcelain=v1", "--untracked-files=all", root=root)
    rows = [line for line in status.splitlines() if line.strip()]
    tracked = [line for line in rows if not line.startswith("??")]
    untracked = [line for line in rows if line.startswith("??")]
    up_code, upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", root=root)
    upstream = upstream if up_code == 0 else ""
    ahead = behind = None
    if upstream:
        div_code, divergence = _git("rev-list", "--left-right", "--count", f"{upstream}...HEAD", root=root)
        if div_code == 0:
            parts = divergence.split()
            if len(parts) == 2:
                behind, ahead = (int(parts[0]), int(parts[1]))
    _, wt_text = _git("worktree", "list", "--porcelain", root=root)
    worktrees = []
    current: dict[str, str] = {}
    for line in wt_text.splitlines() + [""]:
        if not line.strip():
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    blockers = []
    if rows:
        blockers.append("working tree has uncommitted changes")
    if not upstream:
        blockers.append("branch has no upstream tracking branch")
    if behind:
        blockers.append(f"branch is {behind} commit(s) behind its known upstream")
    if ahead:
        blockers.append(f"branch has {ahead} unpushed commit(s)")
    return {
        "ok": True,
        "schema": "repo_readiness.v1",
        "root": str(root),
        "branch": branch,
        "head": head,
        "upstream": upstream or None,
        "ahead": ahead,
        "behind": behind,
        "dirty": bool(rows),
        "changed_tracked": len(tracked),
        "untracked": len(untracked),
        "worktrees": worktrees,
        "handoff_ready": not blockers,
        "blockers": blockers,
        "note": "Read-only snapshot; run git fetch before relying on ahead/behind as current remote truth.",
    }
