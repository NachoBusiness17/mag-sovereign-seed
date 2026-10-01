"""Deterministic hard rails (Maelstrom V2 pattern) — machine-parseable constitution.

configs/constitutional_rails.json is the code-as-law contract checked at
preflight (Layer 1). Rails are regex/pattern rules with NO LLM involved:
block -> the tool call never reaches the OS.

Path rails mirror the legacy banned list in agent_cli._safe_tool_args
(defense in depth; rails file is the single editable source for new rules).
Content rails are the genuine delta: they catch live-looking secret values
being written into ordinary artifacts (path check alone misses those).

A content rule may carry "git_first_commit_after": "YYYY-MM-DD": it then
applies only to files BORN after that date (Mickey17 W2 scarless-clone law,
2026-09-29). Everything whose git first-commit is on/before the cutoff is
grandfathered and keeps its scars; a path with no git history is a file
being born now and is fully subject. Git probe failure fails OPEN (the
existing engine law: never crash or wrongly block preflight; the pre-push
ratchet stays the second layer for undatable files).
"""
from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAILS_PATH = ROOT / "configs" / "constitutional_rails.json"

_EMPTY: dict = {"write_file_content": [], "write_file_path": []}


@lru_cache(maxsize=1)
def load_rails() -> dict:
    """Load the rails contract; on any failure degrade to empty (never crash preflight)."""
    try:
        if not RAILS_PATH.exists():
            return _EMPTY
        data = json.loads(RAILS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _EMPTY
        return data
    except Exception:
        return _EMPTY


def check_path(path: str) -> tuple[bool, str]:
    """Block writes whose path matches a path rail (residual DNA / knots / env)."""
    p = str(path or "").replace("\\", "/").lower()
    for rule in load_rails().get("write_file_path", []):
        for pat in rule.get("patterns", []):
            if pat.lower().replace("\\", "/") in p:
                return False, "rail[%s] blocked path: %s (%s)" % (
                    rule.get("id", "?"), pat, rule.get("desc", ""))
    return True, ""


def check_content(path: str, content: str) -> tuple[bool, str]:
    """Block writes whose content matches a content rail (live secret values;
    date-conditioned scar rails for files born after their cutoff)."""
    if not content:
        return True, ""
    for rule in load_rails().get("write_file_content", []):
        rx = rule.get("regex")
        if not rx:
            continue
        cutoff = rule.get("git_first_commit_after")
        if cutoff and _grandfathered(path, str(cutoff)):
            continue
        try:
            if re.search(rx, content):
                return False, "rail[%s] blocked content: %s" % (
                    rule.get("id", "?"), rule.get("desc", ""))
        except re.error:
            continue
    return True, ""


# Sentinel returns of _git_first_commit: "" = git answered and the path has
# no history yet (untracked, i.e. a file being born now); "?" = the git
# probe itself failed (not a repo, timeout, OSError) and age is unknowable.
_GIT_UNTRACKED = ""
_GIT_UNKNOWN = "?"


@lru_cache(maxsize=256)
def _git_first_commit(path: str) -> str:
    """ISO date (YYYY-MM-DD) the path first appeared in git history.

    '' = untracked (git ran fine, no history yet); '?' = probe failed. The
    cache key is the raw path string; two spellings of one file cost two
    entries, harmless. A first-commit date never moves, and an untracked
    verdict can only harden into an after-cutoff commit, so caching is safe.
    """
    rel = str(path or "")
    if not rel:
        return _GIT_UNKNOWN
    p = Path(rel)
    if not p.is_absolute():
        p = ROOT / p
    try:
        rel_posix = p.resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        rel_posix = rel.replace("\\", "/")
    try:
        out = subprocess.run(
            ["git", "log", "--reverse", "--format=%as", "--", rel_posix],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _GIT_UNKNOWN
    if out.returncode != 0:
        return _GIT_UNKNOWN
    lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    if not lines:
        return _GIT_UNTRACKED
    return lines[0]


def _grandfathered(path: str, cutoff: str) -> bool:
    """True when the scar rail must NOT fire for this path (skip the rule).

    Born on/before cutoff -> grandfathered. Untracked -> not grandfathered
    (this write is the file's birth). Probe failed -> grandfathered (fail
    open; preflight never crashes or wrongly blocks, pre-push ratchet holds).
    """
    first = _git_first_commit(path)
    if first == _GIT_UNKNOWN:
        return True
    if first == _GIT_UNTRACKED:
        return False
    return first <= cutoff


def check_write_file(path: str, content: str) -> tuple[bool, str]:
    """Combined preflight check for write_file (path then content)."""
    ok, msg = check_path(path)
    if not ok:
        return False, msg
    return check_content(path, content)
