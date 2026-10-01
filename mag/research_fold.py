"""Passive research-pack auto-fold — turn landed research answers into case law.

Closes the loop the operator asked for: "fold the landed research threads into the
ledger so the bed's findings become case law rather than just reports, using our
passive systems which should happen automatically."

When a research-pack task completes, it writes `memory/research_packs/<id>.answer.{remote,local}.md`.
This module (run on the governor cadence, not by hand) scans for completed answers that
haven't been folded yet and records each as a skill_ledger DECISION (case law), so the
bed's findings become precedent the router/decision layer can inherit — automatically.

Idempotent: a per-pack fold registry (memory/runs/research_fold/folded.jsonl) prevents
re-folding. Deterministic, cheap, no LLM.

CLI:  python -m mag.research_fold run [--limit N] | status
Wired into: mag.governor_autorun autorun_loop cadence (MAG_FOLD_EVERY).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

PACKS = ROOT / "memory" / "research_packs"
FOLD_DIR = ROOT / "memory" / "runs" / "research_fold"
FOLDED = FOLD_DIR / "folded.jsonl"
SCHEMA = "research_fold.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _folded_ids() -> set[str]:
    if not FOLDED.is_file():
        return set()
    out: set[str] = set()
    for line in FOLDED.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.add(str(json.loads(line).get("pack_id") or ""))
        except json.JSONDecodeError:
            continue
    return {x for x in out if x}


def _mark_folded(pack_id: str, *, path: str, source: str) -> None:
    FOLD_DIR.mkdir(parents=True, exist_ok=True)
    with FOLDED.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "pack_id": pack_id, "path": path, "source": source}) + "\n")


def _completed_answers() -> list[Path]:
    """All completed answer files in the pack dir (remote + local), newest first."""
    if not PACKS.is_dir():
        return []
    return sorted(
        list(PACKS.glob("*.answer.remote.md")) + list(PACKS.glob("*.answer.local.md")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _pack_title(pack_id: str) -> str:
    """Best-effort title: read the pack .json title, else decode the filename slug."""
    j = PACKS / f"{pack_id}.json"
    try:
        if j.is_file():
            return str((json.loads(j.read_text(encoding="utf-8")) or {}).get("title") or pack_id)[:200]
    except Exception:
        pass
    return pack_id[:200]


def fold_one(answer: Path) -> dict[str, Any]:
    """Fold ONE completed answer into skill_ledger as a decision (case law)."""
    base = answer.name.split(".answer.")[0]
    pack_id = base if base else answer.stem
    source = "remote" if "remote" in answer.name else "local"
    text = ""
    try:
        text = answer.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass

    from mag.skill_ledger import record_decision

    rec = record_decision(
        goal=f"research-pack: {_pack_title(pack_id)}",
        task_shape="research-pack",
        provider="deepseek",
        model="deepseek-v4-flash",
        reasoning_level="none",
        seat="remote" if source == "remote" else "local",
        outcome="ok",
        detail=(text[:180].replace("\n", " ") or "(empty answer)"),
        source="research-pack-fold",
    )
    _mark_folded(pack_id, path=answer.name, source=source)
    return {
        "pack_id": pack_id,
        "source": source,
        "ok": bool(rec.get("ok", True)),
        "decision": rec,
        "path": answer.name,
    }


def run(*, limit: int = 0) -> dict[str, Any]:
    """Scan for completed answers not yet folded, fold them. Idempotent."""
    folded = _folded_ids()
    pending = [a for a in _completed_answers() if (a.name.split(".answer.")[0]) not in folded]
    if limit and limit > 0:
        pending = pending[:limit]
    results = [fold_one(a) for a in pending]
    after = _folded_ids()
    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": _now(),
        "folded": len(results),
        "pending_remaining": len([a for a in _completed_answers() if (a.name.split('.answer.')[0]) not in after]),
        "results": results,
    }


def status() -> dict[str, Any]:
    answers = _completed_answers()
    folded = _folded_ids()
    return {
        "ok": True,
        "schema": SCHEMA,
        "total_answers": len(answers),
        "folded": len(folded),
        "pending": len([a for a in answers if (a.name.split('.answer.')[0]) not in folded]),
        "path": str(FOLDED),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="research-fold", description="Auto-fold landed research answers into skill_ledger case law")
    sub = ap.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run")
    p_run.add_argument("--limit", type=int, default=0)
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(run(limit=int(getattr(args, "limit", 0) or 0)), indent=2, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
