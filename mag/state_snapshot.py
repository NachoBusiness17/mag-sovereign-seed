"""State snapshot — in-the-moment classification for posterity + training.

Every session/escalation contributes a structured "current state summary" to a
local pile (memory/pile/state_summaries.jsonl). The overnight job
(tools/pile_classify.py) later drains the pile with a local model and folds the
classifications into case law + training rows.

This is the "classification in the moment model": capture the structured
summary (goal/outcome/tier/lessons) at the moment it happens — cheap,
deterministic, provenance-attached — instead of re-deriving it later.

Callers:
  escalate_on_loop (wired)   → kind=escalation
  session close / run close  → kind=session_end (callable / CLI)
  operator / seat            → any moment worth keeping

CLI:
  python -m mag.state_snapshot capture --goal "..." --outcome ok --tier local [--lesson "..."]
  python -m mag.state_snapshot status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ROOT  # noqa: E402

PILE_DIR = ROOT / "memory" / "pile"
PILE = PILE_DIR / "state_summaries.jsonl"
CLASSIFIED = PILE_DIR / "classified.jsonl"
TRAINING = PILE_DIR / "training_rows.jsonl"

_KINDS = {"session_end", "escalation", "run_close", "autoaim", "operator"}
_OUTCOMES = {"ok", "fail", "escalated", "loop", "unknown"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_ids(path: Path) -> set[str]:
    """ids AND state_hashes already in the pile (dedup keys)."""
    if not path.is_file():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
            keys.add(row.get("id"))
            if row.get("state_hash"):
                keys.add(row.get("state_hash"))
        except (json.JSONDecodeError, TypeError):
            continue
    return keys


def _state_hash(goal: str, outcome: str, kind: str, tier: str) -> str:
    return hashlib.sha256(f"{kind}|{tier}|{goal}|{outcome}".encode("utf-8")).hexdigest()[:16]


def capture_summary(
    *,
    goal: str = "",
    outcome: str = "unknown",
    tier: str = "",
    kind: str = "session_end",
    lessons: list[str] | None = None,
    source: str = "",
    session_id: str | None = None,
    state_hash: str | None = None,
) -> dict[str, Any]:
    """Append one structured state summary to the pile (dedup by state_hash)."""
    outcome = outcome if outcome in _OUTCOMES else "unknown"
    kind = kind if kind in _KINDS else "session_end"
    sh = state_hash or _state_hash(goal, outcome, kind, tier)
    if sh in _load_ids(PILE):
        return {"ok": False, "error": "duplicate state (already captured)", "id": sh}
    row = {
        "id": f"st-{uuid.uuid4().hex[:10]}",
        "ts": _now(),
        "kind": kind,
        "tier": tier[:24],
        "source": source[:60],
        "goal": (goal or "")[:300],
        "outcome": outcome,
        "lessons": [str(l)[:200] for l in (lessons or [])[:3]],
        "session_id": session_id,
        "state_hash": sh,
        "classified": False,
    }
    _append(PILE, row)
    return {"ok": True, "row": row}


def status() -> dict[str, Any]:
    from collections import Counter

    rows = [json.loads(l) for l in PILE.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()] if PILE.is_file() else []
    kinds = Counter(r.get("kind") for r in rows)
    outcomes = Counter(r.get("outcome") for r in rows)
    classified_n = sum(1 for r in rows if r.get("classified"))
    return {
        "ok": True,
        "schema": "state_snapshot.v1",
        "pile": len(rows),
        "classified": classified_n,
        "unclassified": len(rows) - classified_n,
        "by_kind": dict(kinds),
        "by_outcome": dict(outcomes),
        "pile_path": str(PILE),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="state-snapshot", description="In-the-moment state summary capture.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_cap = sub.add_parser("capture")
    p_cap.add_argument("--goal", default="")
    p_cap.add_argument("--outcome", choices=list(_OUTCOMES), default="unknown")
    p_cap.add_argument("--tier", default="")
    p_cap.add_argument("--kind", choices=list(_KINDS), default="session_end")
    p_cap.add_argument("--lesson", action="append")
    p_cap.add_argument("--source", default="")
    p_cap.add_argument("--session-id", default=None)
    sub.add_parser("status")
    args = ap.parse_args(argv)

    if args.cmd == "capture":
        r = capture_summary(goal=args.goal, outcome=args.outcome, tier=args.tier, kind=args.kind,
                            lessons=args.lesson, source=args.source, session_id=args.session_id)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
