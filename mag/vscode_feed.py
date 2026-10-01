"""VS Code chat → behavioral loop bridge.

Every VS Code Copilot/chat session is a learning sample: what the operator asked,
what got built, what they corrected. This module captures those signals into the
existing behavioral-loop memory structures so the framework learns the user and
builds the structures that inform later processes:

  capture_summary  -> memory/pile/state_summaries.jsonl  (-> overnight pile_classify -> training rows)
  behavioral_events-> logs/behavioral_events.jsonl        (-> daily behavioral leaf / scout)
  skill_ledger     -> record_decision / record_labeled_row (case-law + training)
  pro_library      -> aim_once (transferable moves when a signal is strong)

Idempotent: dedup by state_hash / session_id, so re-running never double-captures.

CLI:
  python -m mag.vscode_feed capture --goal "..." --outcome ok --source copilot [--lesson "..."] [--session <id>]
  python -m mag.vscode_feed status

REST (registered in dashboard/rest.py):
  POST /api/v1/behavior/vscode   {goal?, outcome?, lessons?, session_id?, source?}
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ROOT  # noqa: E402

EVENTS_PATH = ROOT / "logs" / "behavioral_events.jsonl"

_OUTCOMES = {"ok", "fail", "escalated", "loop", "unknown"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_behavioral_event(row: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _fold_skill_ledger(
    goal: str, outcome: str, lessons: list[str], source: str, session_id: str = ""
) -> None:
    """Fold a chat outcome into skill_ledger case-law + labeled rows (best-effort)."""
    try:
        from mag.skill_ledger import record_decision

        record_decision(
            goal=(goal or "")[:300] or "vscode-chat",
            task_shape="chat",
            provider="vscode",
            model="copilot",
            reasoning_level="none",
            seat="operator",
            outcome=outcome,
            detail=" ".join(lessons)[:200],
            source=f"vscode_chat:{source}",
        )
    except Exception:
        pass
    try:
        from mag.skill_ledger import record_labeled_row

        if lessons:
            record_labeled_row(
                text="\n".join(lessons)[:400],
                label=outcome,
                classifier="vscode_feed",
                confidence=1.0,
                source=f"vscode_chat:{source}",
            )
    except Exception:
        pass


def _maybe_pro_move(goal: str, outcome: str, lessons: list[str]) -> None:
    """If a chat yields a reusable winning move, feed the pro_library aimbot."""
    if outcome != "ok":
        return
    hint = " ".join(lessons).lower()
    if any(k in hint for k in ("steer", "poke", "restart", "respawn", "skip", "meta")):
        try:
            from mag.pro_library import aim_once

            # Best-effort SENSE/MATCH; dry-run so the bridge never injects a live steer.
            state = {"operator_inbox_pending": 0, "goal": (goal or "")[:300], "hint": hint[:200]}
            aim_once(
                state,
                goal=f"vscode-chat win: {(goal or '')[:120]}",
                fire_moves=False,
            )
        except Exception:
            pass


def capture(
    *,
    goal: str = "",
    outcome: str = "unknown",
    tier: str = "",
    kind: str = "session_end",
    lessons: list[str] | None = None,
    source: str = "copilot",
    session_id: str = "",
) -> dict[str, Any]:
    """Capture one VS Code chat session signal into the behavioral loop."""
    outcome = outcome if outcome in _OUTCOMES else "unknown"
    lessons = [str(l) for l in (lessons or []) if str(l).strip()][:3]

    # 1. pile / training feed
    from mag.state_snapshot import capture_summary

    res = capture_summary(
        goal=goal,
        outcome=outcome,
        tier=tier or "T1",
        kind=kind,
        lessons=lessons,
        source=f"vscode-chat:{source}",
        session_id=session_id or None,
    )

    # 2. behavioral_events for the daily leaf / scout
    _append_behavioral_event(
        {
            "ts": _now(),
            "kind": "vscode_chat",
            "tool": "vscode_feed",
            "outcome": outcome,
            "goal": (goal or "")[:200],
            "lessons": lessons,
            "source": source,
            "session_id": session_id or "",
            "captured": bool(res.get("ok")),
        }
    )

    # 3. skill_ledger case-law + labeled rows
    _fold_skill_ledger(goal, outcome, lessons, source, session_id)

    # 4. pro_library transferable move when strong
    _maybe_pro_move(goal, outcome, lessons)

    return {
        "ok": True,
        "schema": "vscode_feed.v1",
        "captured": bool(res.get("ok")),
        "dedup": res.get("error") if not res.get("ok") else None,
        "outcome": outcome,
        "feeds": ["pile", "behavioral_events", "skill_ledger", "pro_library"],
    }


def status() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if EVENTS_PATH.is_file():
        for line in EVENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
                if isinstance(o, dict) and o.get("kind") == "vscode_chat":
                    rows.append(o)
            except json.JSONDecodeError:
                continue
    outcomes: dict[str, int] = {}
    for r in rows[-500:]:
        outcomes[r.get("outcome") or "unknown"] = outcomes.get(r.get("outcome") or "unknown", 0) + 1
    return {
        "ok": True,
        "schema": "vscode_feed.v1",
        "events": len(rows),
        "outcomes": outcomes,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vscode-feed", description="VS Code chat -> behavioral loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_cap = sub.add_parser("capture", help="Capture a chat session signal")
    p_cap.add_argument("--goal", default="", help="What was asked / built")
    p_cap.add_argument("--outcome", default="unknown", choices=_OUTCOMES)
    p_cap.add_argument("--tier", default="T1")
    p_cap.add_argument("--kind", default="session_end")
    p_cap.add_argument("--lesson", action="append", default=[], help="Repeatable lesson")
    p_cap.add_argument("--source", default="copilot")
    p_cap.add_argument("--session", default="", help="Session id")

    sub.add_parser("status", help="Show capture stats")

    args = ap.parse_args(argv)
    if args.cmd == "capture":
        res = capture(
            goal=args.goal,
            outcome=args.outcome,
            tier=args.tier,
            kind=args.kind,
            lessons=args.lesson,
            source=args.source,
            session_id=args.session,
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
