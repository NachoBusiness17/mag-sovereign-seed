"""Peer agent handoff — file instructions between seats on disk.

Any seat reading shared_activity, context-pack, or handoff queue sees what
the other agent said. Uses existing Mag coordination + improve-loop paths.

CLI: python main.py peer-handoff file|list|latest
Trail: memory/handoff/peer_trail.jsonl
Queue: queue/handoff/peer-*.json (ingested by improve-loop)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

HANDOFF_DIR = ROOT / "queue" / "handoff"
PEER_TRAIL = ROOT / "memory" / "handoff" / "peer_trail.jsonl"
SCHEMA = "peer_handoff.v1"
PEER_PREFIX = "peer-"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    PEER_TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **fields}
    with PEER_TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def file_peer_handoff(
    *,
    goal: str,
    brief: str = "",
    from_seat: str = "cursor-cloud",
    to_seat: str = "home-pc",
    env_track: str | None = None,
    commands: list[str] | None = None,
    pr_url: str = "",
    merge_target: str = "",
    status: str = "filed",
    enqueue: bool = False,
    meta: dict[str, Any] | None = None,
    claimed: str = "",
    delivered: str = "",
    receiver_can_act_on: str = "",
) -> dict[str, Any]:
    """File cross-agent instructions — visible in coordination feed + handoff queue.

    Entanglement check (meters law, 2026-09-22): a handoff is a correlation
    test across a noisy channel, so it names CLAIMED (what the sender says it
    did), DELIVERED (the bytes), and what the RECEIVER CAN ACT ON. All three
    empty = unmetered handoff (Γ = 1.00 by default until measured).
    """
    goal = (goal or brief or "").strip()
    if not goal:
        return {"ok": False, "error": "goal or brief required"}

    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    rid = uuid.uuid4().hex[:10]
    path = HANDOFF_DIR / f"{PEER_PREFIX}{rid}.json"

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "handoff_id": rid,
        "ts": _now(),
        "from_seat": from_seat,
        "to_seat": to_seat,
        "goal": goal[:500],
        "brief": (brief or goal)[:4000],
        "env_track": env_track,
        "commands": commands or [],
        "pr_url": pr_url[:500],
        "merge_target": merge_target[:120],
        "status": status,
        "claimed": claimed[:500],
        "delivered": delivered[:500],
        "receiver_can_act_on": receiver_can_act_on[:500],
        "meta": meta or {},
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    detail = f"from={from_seat} track={env_track or 'n/a'}"
    if pr_url:
        detail += f" pr={pr_url[:80]}"

    try:
        from mag.coordination import log_activity

        log_activity(
            seat=from_seat,
            depth="plan",
            goal=f"[peer-handoff] {goal[:200]}",
            status=status,
            actor=from_seat,
            detail=detail,
            activity_id=f"peer-{rid}",
        )
    except Exception:
        pass

    try:
        from mag.operator_inbox import log_behavioral_event

        log_behavioral_event(
            kind="peer_handoff",
            detail=goal[:300],
            session_id=from_seat,
            provider=to_seat,
            phase=status,
        )
    except Exception:
        pass

    try:
        from mag.improve_loop import write_cloud_handoff

        write_cloud_handoff(
            goal=f"[peer] {goal[:200]}",
            claim=goal[:300],
            brief=brief[:2000],
            source=from_seat,
            depth="plan",
            enqueue=False,
            meta={"peer_handoff_id": rid, "env_track": env_track, "pr_url": pr_url},
        )
    except Exception:
        pass

    _trail("filed", handoff_id=rid, from_seat=from_seat, to_seat=to_seat, env_track=env_track)

    out: dict[str, Any] = {
        "ok": True,
        "handoff_id": rid,
        "path": str(path),
        "goal": goal,
        "env_track": env_track,
    }

    if enqueue:
        try:
            from mag.improve_loop import run_improve_cycle

            out["cycle"] = run_improve_cycle(source=f"peer-{from_seat}", scout=True)
        except Exception as exc:
            out["cycle_error"] = str(exc)[:200]

    return out


def list_peer_handoffs(*, limit: int = 10) -> list[dict[str, Any]]:
    """Newest peer handoffs from queue/handoff/peer-*.json."""
    if not HANDOFF_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(HANDOFF_DIR.glob(f"{PEER_PREFIX}*.json"), reverse=True)[:limit]:
        try:
            h = json.loads(p.read_text(encoding="utf-8"))
            h["_path"] = p.name
            rows.append(h)
        except Exception:
            continue
    return rows


def latest_for_track(track_name: str) -> dict[str, Any] | None:
    """Most recent peer handoff targeting env_track (if any)."""
    for row in list_peer_handoffs(limit=30):
        if row.get("env_track") == track_name:
            return row
    return None


def format_latest_brief() -> str:
    """Plain block for context-pack / operator glance."""
    rows = list_peer_handoffs(limit=3)
    if not rows:
        return ""
    lines = ["[PEER HANDOFFS — other agents filed for home PC]"]
    for r in rows:
        lines.append(
            f"- {r.get('from_seat', '?')} → {r.get('to_seat', '?')} · "
            f"track={r.get('env_track') or 'any'} · {str(r.get('goal', ''))[:100]}"
        )
        for cmd in (r.get("commands") or [])[:3]:
            lines.append(f"  cmd: {cmd[:120]}")
        if r.get("claimed") or r.get("delivered"):
            lines.append(f"  claimed: {str(r.get('claimed', ''))[:100]}")
            lines.append(f"  delivered: {str(r.get('delivered', ''))[:100] or '(none — Γ=1.00)'}")
            lines.append(f"  receiver can act on: {str(r.get('receiver_can_act_on', ''))[:100]}")
    return "\n".join(lines)[:1200]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="peer-handoff")
    sub = ap.add_subparsers(dest="cmd")

    pf = sub.add_parser("file", help="File instructions from another agent/seat")
    pf.add_argument("--goal", required=True)
    pf.add_argument("--brief", default="")
    pf.add_argument("--from", dest="from_seat", default="cursor-cloud")
    pf.add_argument("--to", dest="to_seat", default="home-pc")
    pf.add_argument("--track", dest="env_track", default=None)
    pf.add_argument("--command", action="append", dest="commands", default=[])
    pf.add_argument("--pr", dest="pr_url", default="")
    pf.add_argument("--merge-target", default="")
    pf.add_argument("--claimed", default="", help="what the sender says it did")
    pf.add_argument("--delivered", default="", help="the bytes actually on disk")
    pf.add_argument("--act-on", dest="receiver_can_act_on", default="", help="what the receiver can act on")
    pf.add_argument("--enqueue", action="store_true")
    pf.add_argument("--json", action="store_true")

    pl = sub.add_parser("list", help="List recent peer handoffs")
    pl.add_argument("--json", action="store_true")

    sub.add_parser("latest", help="Print latest handoff brief block")

    args = ap.parse_args(argv)
    if args.cmd == "file":
        res = file_peer_handoff(
            goal=args.goal,
            brief=args.brief,
            from_seat=args.from_seat,
            to_seat=args.to_seat,
            env_track=args.env_track,
            commands=args.commands or None,
            pr_url=args.pr_url,
            merge_target=args.merge_target,
            claimed=args.claimed,
            delivered=args.delivered,
            receiver_can_act_on=args.act_on,
            enqueue=bool(args.enqueue),
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "list":
        rows = list_peer_handoffs()
        print(json.dumps(rows, indent=2, default=str) if args.json else json.dumps(rows, indent=2))
        return 0
    if args.cmd == "latest":
        print(format_latest_brief() or "(no peer handoffs)")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
