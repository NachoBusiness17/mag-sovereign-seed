"""Environment track registry — cutting-edge env switching.

Machine truth: configs/env_tracks.yaml
Active track marker: .mag_active_env (repo root, plain text track name)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from config import CONFIGS_DIR, ROOT

REGISTRY_PATH = CONFIGS_DIR / "env_tracks.yaml"
ACTIVE_ENV_FILE = ROOT / ".mag_active_env"


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {"schema": "mag_env_tracks.v1", "tracks": {}}
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("tracks", {})
    return data


def list_tracks() -> list[dict[str, Any]]:
    tracks = load_registry().get("tracks") or {}
    return [tracks[k] for k in sorted(tracks.keys())]


def get_track(name: str) -> dict[str, Any] | None:
    key = (name or "").strip()
    if not key:
        return None
    tracks = load_registry().get("tracks") or {}
    if key in tracks:
        return tracks[key]
    for track in tracks.values():
        if track.get("name") == key:
            return track
    return None


def get_active_env() -> str | None:
    if not ACTIVE_ENV_FILE.is_file():
        return None
    val = ACTIVE_ENV_FILE.read_text(encoding="utf-8").strip()
    return val or None


def set_active_env(name: str) -> None:
    ACTIVE_ENV_FILE.write_text(f"{name.strip()}\n", encoding="utf-8")


def resolve_worktree_path(track: dict[str, Any]) -> Path | None:
    wt = track.get("worktree_path")
    if wt and str(wt).lower() not in {"null", "none", ""}:
        return ROOT.parent / str(wt)
    if os.environ.get("MAG_MULTI_WORKTREE") == "1":
        return ROOT.parent / f"mag_env_{track['name']}"
    return None


def resolve_track_root(track: dict[str, Any]) -> Path:
    wt = resolve_worktree_path(track)
    return wt if wt else ROOT


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def _git_out(cwd: Path, *args: str) -> str:
    r = _git(cwd, *args, check=False)
    return (r.stdout or "").strip()


def _branch_checked_out_elsewhere(branch: str) -> Path | None:
    """Return worktree path if branch is already checked out elsewhere."""
    current = Path(_git_out(ROOT, "rev-parse", "--show-toplevel")).resolve()
    proc = _git(ROOT, "worktree", "list", "--porcelain", check=False)
    wt_path: Path | None = None
    wt_branch: str | None = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("worktree "):
            if wt_path and wt_branch == branch and wt_path.resolve() != current:
                return wt_path
            wt_path = Path(line.split(" ", 1)[1].strip())
            wt_branch = None
        elif line.startswith("branch refs/heads/"):
            wt_branch = line.split("refs/heads/", 1)[1].strip()
    if wt_path and wt_branch == branch and wt_path.resolve() != current:
        return wt_path
    return None


def ensure_worktree(track: dict[str, Any]) -> Path:
    """Ensure dedicated worktree exists when configured; return track root."""
    wt_path = resolve_worktree_path(track)
    if not wt_path:
        return ROOT

    branch = str(track.get("branch") or "")
    remote = str(track.get("remote_tracking") or "")

    if wt_path.is_dir() and (wt_path / ".git").exists():
        return wt_path

    wt_path.parent.mkdir(parents=True, exist_ok=True)
    _git(ROOT, "fetch", "origin", check=False)
    r = _git(ROOT, "worktree", "add", str(wt_path), branch, check=False)
    if r.returncode != 0 and remote:
        ref = remote.split("/", 1)[-1] if remote.startswith("origin/") else remote
        _git(ROOT, "worktree", "add", "-b", branch, str(wt_path), f"origin/{ref}", check=True)
    elif r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or f"worktree add failed for {wt_path}")
    return wt_path


def sync_track(name: str) -> dict[str, Any]:
    """Fetch + checkout + pull track branch in the appropriate repo root."""
    track = get_track(name)
    if not track:
        return {"ok": False, "error": f"unknown track {name!r}"}

    branch = str(track.get("branch") or "")
    remote = str(track.get("remote_tracking") or f"origin/{branch}")
    pull_ref = remote.replace("origin/", "", 1) if remote.startswith("origin/") else branch

    wt_path = resolve_worktree_path(track)
    if wt_path:
        root = ensure_worktree(track)
    else:
        elsewhere = _branch_checked_out_elsewhere(branch)
        if elsewhere:
            root = elsewhere
        else:
            root = ROOT

    _git(root, "fetch", "origin")
    co = _git(root, "checkout", branch, check=False)
    if co.returncode != 0:
        co = _git(root, "checkout", "-B", branch, remote, check=False)
    if co.returncode != 0:
        return {"ok": False, "error": co.stderr or co.stdout or "checkout failed", "root": str(root)}

    pull = _git(root, "pull", "origin", pull_ref, check=False)
    if pull.returncode != 0:
        return {
            "ok": False,
            "error": pull.stderr or pull.stdout or "pull failed",
            "root": str(root),
            "branch": branch,
        }

    return {
        "ok": True,
        "track": track.get("name"),
        "root": str(root),
        "branch": branch,
        "remote_tracking": remote,
        "port": track.get("port"),
    }


def activate_track(name: str) -> dict[str, Any]:
    res = sync_track(name)
    if not res.get("ok"):
        return res
    set_active_env(name)
    res["active"] = name
    return res


def status_summary() -> dict[str, Any]:
    active = get_active_env()
    active_track = get_track(active) if active else None
    main_branch = _git_out(ROOT, "rev-parse", "--abbrev-ref", "HEAD")
    wt_list = _git_out(ROOT, "worktree", "list")

    tracks_out: list[dict[str, Any]] = []
    for track in list_tracks():
        root = resolve_track_root(track)
        branch = _git_out(root, "rev-parse", "--abbrev-ref", "HEAD") if root.is_dir() else "?"
        tracks_out.append({
            "name": track.get("name"),
            "branch": track.get("branch"),
            "port": track.get("port"),
            "root": str(root),
            "checked_out_branch": branch,
            "active": track.get("name") == active,
            "description": track.get("description"),
        })

    return {
        "ok": True,
        "active": active,
        "main_repo": str(ROOT),
        "main_branch": main_branch,
        "multi_worktree": os.environ.get("MAG_MULTI_WORKTREE") == "1",
        "active_track": active_track,
        "tracks": tracks_out,
        "worktrees": wt_list,
        "registry": str(REGISTRY_PATH),
    }


def format_track_list() -> str:
    active = get_active_env()
    lines = ["Mag environment tracks:", ""]
    for track in list_tracks():
        mark = " *" if track.get("name") == active else "  "
        lines.append(
            f"{mark} {track.get('name'):14}  port {track.get('port')}  "
            f"{track.get('branch')}"
        )
        desc = track.get("description") or ""
        if desc:
            lines.append(f"      {desc}")
    if active:
        lines.extend(["", f"Active: {active}"])
    else:
        lines.extend(["", "Active: (none — run env_switch use <name>)"])
    return "\n".join(lines)


def cmd_env_cli(action: str, track_name: str | None = None) -> int:
    if action == "list":
        print(format_track_list())
        return 0
    if action == "status":
        print(json.dumps(status_summary(), indent=2, default=str))
        return 0
    if action == "use":
        if not track_name:
            print("usage: python main.py env use <track>")
            return 1
        res = activate_track(track_name)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    print(f"unknown env action: {action}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(format_track_list())
        raise SystemExit(0)
    action = sys.argv[1]
    track = sys.argv[2] if len(sys.argv) > 2 else None
    raise SystemExit(cmd_env_cli(action, track))
