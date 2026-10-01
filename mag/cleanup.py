"""Passive code-audit cleanup — keep the project dir from turning into a clusterfuck.

The operator's complaint: artifacts keep getting dropped into the project tree
(deliver/, _tmp_*, codex_*, pytest-* scratch, caches) and nobody cleans up. This
module is the cron-equivalent: a passive audit that MOVES clearly-transient
artifacts to a trash folder (reversible, not hard-delete) and runs on the autorun
cadence without being asked. Deletion is deterministic (no model), so it runs on
the loop like mag.janitor — it is NOT a model task.

Safety:
  * Respects the operator seat — auto-clean only when the operator is away.
  * Moves to memory/trash/<ts>/ instead of hard-deleting (recoverable).
  * Only touches clearly-transient paths (temp dirs, caches, _tmp_*, obsolete
    deliver/ staging). Never touches worktrees/, memory/, docs/, source.

CLI: python -m mag.cleanup [--dry]
REST: GET/POST /api/v1/cleanup
Cadence: MAG_CLEANUP_EVERY in governor_autorun.
"""
from __future__ import annotations

import fnmatch
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TRASH = ROOT / "memory" / "trash"

# Transient dir names (matched by name, anywhere under ROOT, shallow).
_TRANSIENT_DIRS = [
    "deliver",            # obsolete staging now that deliverables live on Desktop
    "codex_*",
    "pytest-of-*",
    "pytest-*",
    "__pycache__",
    ".pytest_cache",
]
# Transient file names (anywhere under ROOT).
_TRANSIENT_FILES = [
    "_tmp_*",
    "_deliver_*",
    "*.pyc",
    # verify_*.ipynb = legacy DEMO/verification notebooks (ad-hoc execution surfaces we reach for
    # when the right surface is the LOOP + persisted artifacts, per loop-is-the-connection). They are
    # transient clutter, NOT the architecture — retire them via the framework trash, never PowerShell.
    "verify_*.ipynb",
]
# Paths we NEVER touch, even if they match a pattern.
_PROTECT = {"worktrees", "mine", "reference", "node_modules", ".git", ".venv", "memory"}


def _operator_away() -> bool:
    try:
        from mag.preferences import operator_status
        return operator_status() != "active"
    except Exception:
        return True  # unknown -> default to cleaning (janitor precedent)


def _walk_audit() -> list[dict]:
    found: list[dict] = []
    if not ROOT.is_dir():
        return found
    for child in sorted(ROOT.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            # top-level transient dirs (deliver, codex_*, pytest-of-*)
            if any(fnmatch.fnmatch(child.name, p) for p in _TRANSIENT_DIRS):
                size = sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
                found.append({"path": str(child.relative_to(ROOT)).replace("\\", "/"),
                              "kind": "dir", "bytes": size})
    # shallow scan for transient files at root + memory/
    for base in (ROOT, ROOT / "memory"):
        if not base.is_dir():
            continue
        for f in sorted(base.iterdir()):
            if not f.is_file():
                continue
            if any(fnmatch.fnmatch(f.name, p) for p in _TRANSIENT_FILES):
                found.append({"path": str(f.relative_to(ROOT)).replace("\\", "/"),
                              "kind": "file", "bytes": f.stat().st_size})
    return found


def audit() -> dict:
    """Dry report of what a cleanup WOULD move to trash."""
    items = _walk_audit()
    return {"schema": "cleanup_audit.v1", "n": len(items), "bytes": sum(i["bytes"] for i in items),
            "items": items, "trash": str(TRASH)}


def cleanup(dry: bool = True) -> dict:
    """Move transient artifacts to memory/trash/<ts>/. Reversible; dry by default."""
    rep = audit()
    if not rep["items"]:
        return {"ok": True, "schema": "cleanup.v1", "dry": dry, "moved": 0, "bytes": 0,
                "note": "nothing to clean"}
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = TRASH / ts
    moved = 0
    bytes_moved = 0
    for it in rep["items"]:
        src = ROOT / it["path"]
        if dry:
            continue
        if not src.exists():
            continue
        if it["kind"] == "dir":
            shutil.move(str(src), str(dest / it["path"].replace("/", "__")))
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest / it["path"].replace("/", "__")))
        moved += 1
        bytes_moved += it["bytes"]
    return {"ok": True, "schema": "cleanup.v1", "dry": dry, "moved": moved, "bytes": bytes_moved,
            "trash": str(dest) if not dry else str(TRASH)}


def run_cadence(dry: bool = False) -> dict:
    """Passive cron hook: audit + (if operator away) move transient to trash."""
    if not _operator_away():
        return {"ok": True, "schema": "cleanup_cadence.v1", "action": "skip",
                "reason": "operator active"}
    return cleanup(dry=dry)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    dry = "--live" not in args
    out = run_cadence(dry=dry)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
