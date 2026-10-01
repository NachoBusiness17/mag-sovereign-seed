"""Janitor — autonomous prune + document to keep the environment lean and documented.

This is the standing "keep the house clean" job the operator wanted wired into the
autorun loop. It is PURE (no side effects beyond its own report) and CONSERVATIVE:

  Prune
    - temp dirs at project root matching  codex_*  and  *_temp
    - pytest scratch dirs under  agents/pytest-*
    - stale .tmp files under  memory/  (older than PRUNE_TMP_MIN_AGE_S)
    - best-effort: locked/in-use files are skipped (never crash the loop)

  Document
    - regenerate  memory/briefs/latest.md   (session_state_brief.write_brief)
    - regenerate  memory/ideas/LATEST.md    (idea_graph.write_latest_face)

  Guard
    - refuses to run while the operator is active (preferences.operator_status)
      or when the drainer/autonomy is disabled — so it never prunes under you.

Cadence is enforced by the caller (governor_autorun cadence); this module is the
unit of work. Every run appends a row to memory/runs/janitor_report.jsonl.

REST: POST /api/v1/janitor   -> run()
      GET  /api/v1/janitor   -> last report
CLI:  python -m mag.janitor [--dry] [--prune-only] [--document-only]
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPORT_PATH = ROOT / "memory" / "runs" / "janitor_report.jsonl"
PRUNE_TMP_MIN_AGE_S = 86400  # only delete .tmp files older than 1 day


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_report(row: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def last_report() -> dict[str, Any] | None:
    if not REPORT_PATH.is_file():
        return None
    lines = REPORT_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _guard() -> dict[str, bool]:
    """Refuse to prune/document under an active operator or a disabled drainer."""
    op_active = False
    drainer_ok = True
    try:
        from mag.preferences import operator_status
        op_active = bool(operator_status().get("operator_active"))
    except Exception:
        pass
    try:
        from mag.preferences import drainer_status
        drainer_ok = bool(drainer_status().get("autorun_allowed"))
    except Exception:
        pass
    return {"operator_active": op_active, "drainer_allowed": drainer_ok}


# ====================================================================
# PRUNE
# ====================================================================
def _rmtree_tolerant(p: Path) -> bool:
    try:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file() or p.is_symlink():
            p.unlink(missing_ok=True)
        return not p.exists()
    except Exception:
        return False


def prune(*, dry: bool = False) -> dict[str, Any]:
    removed: list[str] = []
    failed: list[str] = []
    freed_est = 0

    # 1. codex_* and *_temp dirs at project root
    for child in ROOT.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith("codex_") or name.endswith("_temp"):
            if dry:
                removed.append(str(child.relative_to(ROOT)))
                continue
            if _rmtree_tolerant(child):
                removed.append(str(child.relative_to(ROOT)))
            else:
                failed.append(str(child.relative_to(ROOT)))

    # 2. pytest scratch dirs under agents/pytest-*
    agents = ROOT / "agents"
    if agents.is_dir():
        for child in agents.iterdir():
            if child.is_dir() and child.name.startswith("pytest-"):
                if dry:
                    removed.append(str(child.relative_to(ROOT)))
                    continue
                if _rmtree_tolerant(child):
                    removed.append(str(child.relative_to(ROOT)))
                else:
                    failed.append(str(child.relative_to(ROOT)))

    # 3. stale .tmp files under memory/
    cutoff = time.time() - PRUNE_TMP_MIN_AGE_S
    mem = ROOT / "memory"
    if mem.is_dir():
        for child in mem.rglob("*.tmp"):
            try:
                if child.stat().st_mtime < cutoff:
                    if dry:
                        removed.append(str(child.relative_to(ROOT)))
                        continue
                    if _rmtree_tolerant(child):
                        removed.append(str(child.relative_to(ROOT)))
                    else:
                        failed.append(str(child.relative_to(ROOT)))
            except Exception:
                continue

    return {
        "removed": removed,
        "n_removed": len(removed),
        "failed": failed[:20],
        "n_failed": len(failed),
        "dry": dry,
    }


# ====================================================================
# DOCUMENT
# ====================================================================
def document(*, dry: bool = False) -> dict[str, Any]:
    written: dict[str, str] = {}

    # 1. Regenerate the live session-state brief
    try:
        from mag.session_state_brief import write_brief
        if not dry:
            res = write_brief()
            written["briefs/latest.md"] = str(res.get("path", "?"))
        else:
            written["briefs/latest.md"] = "(dry)"
    except Exception as e:
        written["briefs/latest.md"] = f"error: {str(e)[:120]}"

    # 2. Regenerate the idea-graph LATEST face
    try:
        from mag.idea_graph import write_latest_face
        if not dry:
            p = write_latest_face()
            written["ideas/LATEST.md"] = str(p.relative_to(ROOT))
        else:
            written["ideas/LATEST.md"] = "(dry)"
    except Exception as e:
        written["ideas/LATEST.md"] = f"error: {str(e)[:120]}"

    return {"written": written, "dry": dry}


# ====================================================================
# RUN
# ====================================================================
def run(*, dry: bool = False, prune_only: bool = False, document_only: bool = False) -> dict[str, Any]:
    guard = _guard()
    row: dict[str, Any] = {
        "schema": "janitor.v1",
        "ts": _now(),
        "dry": dry,
        "guard": guard,
    }

    # Refuse to actually prune while operator is active (safe; still allow doc).
    if not dry and guard.get("operator_active"):
        row["prune"] = {"skipped": "operator_active"}
        row["action"] = "skipped:operator_active"
        _append_report(row)
        return row

    if not document_only:
        row["prune"] = prune(dry=dry)
    if not prune_only:
        row["document"] = document(dry=dry)

    row["action"] = "prune" if prune_only else ("document" if document_only else "prune+document")
    if not dry:
        _append_report(row)
    return row


# ====================================================================
# CLI
# ====================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Janitor — prune + document (lean & documented)")
    ap.add_argument("--dry", action="store_true", help="Report what would change, don't change")
    ap.add_argument("--prune-only", action="store_true")
    ap.add_argument("--document-only", action="store_true")
    ap.add_argument("--last", action="store_true", help="Print the last report")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.last:
        r = last_report()
        if args.json:
            print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
            return 0
        print("LAST JANITOR REPORT")
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str) if r else "(none)")
        return 0

    res = run(dry=args.dry, prune_only=args.prune_only, document_only=args.document_only)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
        return 0

    print(f"JANITOR  {res['ts']}  action={res['action']} dry={res['dry']}")
    g = res.get("guard", {})
    print(f"  operator_active={g.get('operator_active')} drainer_allowed={g.get('drainer_allowed')}")
    if "prune" in res:
        p = res["prune"]
        if p.get("skipped"):
            print(f"  prune: skipped ({p['skipped']})")
        else:
            print(f"  prune: removed {p.get('n_removed', 0)}, failed {p.get('n_failed', 0)}")
            for r in (p.get("removed") or [])[:10]:
                print(f"    - {r}")
    if "document" in res:
        for k, v in (res["document"].get("written") or {}).items():
            print(f"  doc: {k} -> {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
