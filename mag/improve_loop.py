"""Cloud handoff + unified improve cycle — feeds behavioral, nervous, spider, queue.

Cloud agents file handoff JSON on disk; local cycle ingests, queues, emits training
events, refreshes nervous glance, and runs spider tick.

CLI: python main.py improve-loop cycle|cloud-handoff|ingest
REST: POST /api/v1/improve/cloud · POST /api/v1/improve/cycle
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

HANDOFF_DIR = ROOT / "queue" / "handoff"
CLOUD_PREFIX = "cloud-"
TRAIL = ROOT / "memory" / "runs" / "improve_loop_trail.jsonl"
SCHEMA = "improve_loop.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _pile_training_count() -> int:
    """Rows accumulated in the pile training file (feeds train/prepare.py)."""
    from mag.state_snapshot import TRAINING

    if not TRAINING.is_file():
        return 0
    return sum(1 for l in TRAINING.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())


def write_cloud_handoff(
    *,
    goal: str = "",
    claim: str = "",
    brief: str = "",
    source: str = "cursor-cloud",
    depth: str = "simple_code",
    enqueue: bool = False,
    run_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """File a cloud-agent outcome for local improve loop ingestion."""
    goal = (goal or claim or brief or "").strip()
    if not goal:
        return {"ok": False, "error": "goal, claim, or brief required"}

    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    rid = run_id or uuid.uuid4().hex[:10]
    path = HANDOFF_DIR / f"{CLOUD_PREFIX}{rid}.json"
    if claim and not goal.startswith("[improve]"):
        goal = f"[improve] {claim.strip()}"

    payload: dict[str, Any] = {
        "schema": "cloud_handoff.v1",
        "run_id": rid,
        "ts": _now(),
        "source": source,
        "goal": goal[:500],
        "claim": (claim or goal)[:300],
        "brief": (brief or "")[:2000],
        "depth": depth,
        "parent": "cloud",
        "meta": meta or {},
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _trail("cloud_handoff", path=path.name, goal=goal[:120], source=source)

    try:
        from mag.operator_inbox import log_behavioral_event

        log_behavioral_event(
            kind="cloud_handoff",
            detail=goal[:300],
            session_id=source,
            provider="cloud",
            phase="filed",
        )
    except Exception:
        pass

    out: dict[str, Any] = {"ok": True, "path": str(path), "run_id": rid, "goal": goal}
    if enqueue:
        out["cycle"] = run_improve_cycle(source="cloud", drain_one=True)
    return out


def ingest_cloud_handoffs(*, limit: int = 10) -> list[dict[str, Any]]:
    """List unprocessed cloud handoffs (newest first)."""
    if not HANDOFF_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    # UUID filenames are deliberately opaque and are not chronological.  The
    # old lexical sort could hide a just-written handoff behind ten older
    # records, making the mailbox look unwired.  Read the durable timestamp,
    # then apply the limit after sorting.
    for p in HANDOFF_DIR.glob(f"{CLOUD_PREFIX}*.json"):
        try:
            h = json.loads(p.read_text(encoding="utf-8"))
            h["_path"] = p.name
            rows.append(h)
        except Exception:
            continue
    rows.sort(key=lambda row: str(row.get("ts") or ""), reverse=True)
    return rows[: max(0, int(limit))]


def run_improve_cycle(
    *,
    source: str = "local",
    max_improve: int = 2,
    drain_one: bool = False,
    spider_inject: bool = False,
    scout: bool = False,
    control_plane: bool = False,
) -> dict[str, Any]:
    """One improve cycle — behavioral + queue + nervous + spider + training events.

    ``control_plane=True`` admits only bounded queue work and emits explicit
    deferrals for cadence-owned surfaces; it is used by synchronous law/health
    enforcement so those callers cannot recursively run the whole flywheel.
    """
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": _now(),
        "source": source,
        "ok": True,
    }

    if scout:
        try:
            from mag.improve import scout as improve_scout

            report["scout"] = improve_scout(dry=False)
        except Exception as exc:
            report["scout_error"] = str(exc)[:200]

    handoffs = ingest_cloud_handoffs(limit=5)
    report["cloud_handoffs_pending"] = len(handoffs)

    try:
        from mag.governor_autorun import fill_queue

        filled = fill_queue(
            max_improve=max_improve,
            max_state=0 if control_plane else 2,
            max_handoff=0 if control_plane else 3,
            max_verkle=0 if control_plane else 2,
            budget_seconds=2.0 if control_plane else 12.0,
        )
        report["fill"] = {
            "improve": len(filled.get("improve") or []),
            "handoff": len(filled.get("handoff") or []),
            "skipped": len(filled.get("skipped") or []),
            "detail": filled,
        }
    except Exception as exc:
        report["fill_error"] = str(exc)[:200]
        report["ok"] = False

    # Self-improvement expansion: feed the state-summary pile through the local
    # classifier (bounded per cycle — the full drain is the overnight job).
    # Escalations/session-close capture → pile → classify → case law + training rows.
    try:
        from mag.state_snapshot import status as pile_status

        ps = pile_status()
        report["pile"] = {"pending": ps.get("unclassified", 0), "total": ps.get("pile", 0)}
        if control_plane:
            report["pile"]["deferred"] = "control_plane"
        elif ps.get("unclassified"):
            # Do not import the heavyweight LangChain/Transformers classifier
            # until the local model lane is actually present. On an offline
            # host that import can itself consume the whole control-plane
            # timeout before it ever reaches a model call.
            from models.registry import ollama_tags

            if not ollama_tags(timeout=0.6):
                report["pile"]["deferred"] = "ollama_unavailable"
            else:
                from tools.pile_classify import run_pile

                pr = run_pile(model="gemma4:latest", limit=3, fold=True)
                report["pile"]["classified"] = pr.get("classified_this_run", 0)
                report["pile"]["errors"] = len(pr.get("errors") or [])
                report["pile"]["training_rows"] = _pile_training_count()
    except Exception as exc:
        report["pile_error"] = str(exc)[:200]

    if drain_one and not control_plane:
        try:
            from mag.orchestrator import drain_once

            report["drain"] = drain_once()
        except Exception as exc:
            report["drain_error"] = str(exc)[:200]

    try:
        from mag.operator_inbox import log_behavioral_event

        n_imp = (report.get("fill") or {}).get("improve", 0)
        log_behavioral_event(
            kind="improve_cycle",
            detail=f"source={source} improve_queued={n_imp} handoffs={len(handoffs)}",
            provider=source,
            phase="cycle",
        )
    except Exception:
        pass

    try:
        from mag.training_events import emit

        emit(
            "autorun_cycle",
            input_data={"source": source, "cloud_handoffs": len(handoffs)},
            action={"max_improve": max_improve, "drain_one": drain_one},
            outcome={
                "improve_queued": (report.get("fill") or {}).get("improve", 0),
                "handoff_queued": (report.get("fill") or {}).get("handoff", 0),
            },
            pattern_tags=["improve_loop", f"source_{source}"],
        )
    except Exception:
        pass

    try:
        from mag.spider import tick

        report["spider"] = (
            {"ok": True, "deferred": "control_plane"}
            if control_plane
            else tick(dry=False, inject=spider_inject)
        )
    except Exception as exc:
        report["spider_error"] = str(exc)[:200]

    try:
        from mag.nervous_system import build_glance

        if control_plane:
            report["nervous"] = {"ok": True, "deferred": "control_plane"}
        else:
            report["nervous"] = {
                "ok": build_glance(write=True).get("ok"),
                "integral_ok": build_glance(write=False).get("integral_ok"),
            }
    except Exception as exc:
        report["nervous_error"] = str(exc)[:200]

    _trail("cycle", source=source, report_summary={
        k: report.get(k) for k in ("fill", "drain", "spider", "nervous", "cloud_handoffs_pending")
    })
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="improve-loop")
    sub = ap.add_subparsers(dest="cmd")

    pc = sub.add_parser("cycle", help="Run one improve cycle (queue + nervous + spider)")
    pc.add_argument("--source", default="local")
    pc.add_argument("--max-improve", type=int, default=2)
    pc.add_argument("--drain", action="store_true")
    pc.add_argument("--scout", action="store_true")
    pc.add_argument("--spider-inject", action="store_true")
    pc.add_argument("--json", action="store_true")

    ph = sub.add_parser("cloud-handoff", help="File cloud agent handoff JSON")
    ph.add_argument("--goal", default="")
    ph.add_argument("--claim", default="")
    ph.add_argument("--brief", default="")
    ph.add_argument("--source", default="cursor-cloud")
    ph.add_argument("--enqueue", action="store_true")
    ph.add_argument("--json", action="store_true")

    pi = sub.add_parser("ingest", help="List pending cloud handoffs")
    pi.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "cycle":
        res = run_improve_cycle(
            source=args.source,
            max_improve=args.max_improve,
            drain_one=bool(args.drain),
            spider_inject=bool(args.spider_inject),
            scout=bool(args.scout),
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "cloud-handoff":
        res = write_cloud_handoff(
            goal=args.goal,
            claim=args.claim,
            brief=args.brief,
            source=args.source,
            enqueue=bool(args.enqueue),
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "ingest":
        rows = ingest_cloud_handoffs()
        print(json.dumps(rows, indent=2, default=str) if args.json else json.dumps(rows, indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
