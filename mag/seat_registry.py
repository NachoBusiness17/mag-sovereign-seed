"""Unified seat registry — desktop/cloud/seat-guard peers visible to orchestrator + switchboard.

Desktop-launched agents (Cursor IDE, cloud agents, seat-guard REPL) register here so
the orchestrator mesh, switchboard steer/reap, and improve loops see them — not
orphan processes waiting on stdin.

CLI: python main.py seats register|heartbeat|unregister|list
REST: POST /api/v1/seats/register · POST /api/v1/seats/heartbeat
Trail: memory/runs/seat_registry_trail.jsonl
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

TRAIL = ROOT / "memory" / "runs" / "seat_registry_trail.jsonl"
GUARD_DIR = ROOT / "memory" / "runs" / "seat_guard"
EXTERNAL_STALE_S = 300  # seconds without heartbeat before reap marks died

_SEAT_PLATFORM: dict[str, str] = {
    "local": "ollama",
    "agent": "deepseek",
    "deepseek": "deepseek",
    "grok_tui": "xai",
    "grok_bot": "grok-desktop",
    "chatgpt_bot": "openai-desktop",
    "sol": "sol-app",
    "cursor": "cursor",
    "cloud": "cursor",
    "hermes": "hermes",
    "human": "operator",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail_path() -> Path:
    """B2-401 (2026-09-26): MAG_SEAT_REGISTRY_TRAIL overrides the sink, else
    the production trail. Same shape as the MAG_SEAT_CRASH_LOG seam (B2-86)
    and the MAG_GAPS_LOG seam (B2-79): tests point the writer at tmp instead
    of appending register/unregister rows to the production trail (111
    pytest-parent rows were on disk at fix time). No env set = same path."""
    env = os.environ.get("MAG_SEAT_REGISTRY_TRAIL")
    return Path(env) if env else TRAIL


def _trail(event: str, task_id: str, **meta: Any) -> None:
    path = _trail_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, "task_id": task_id, **meta}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def register(
    *,
    seat: str = "cursor",
    goal: str = "",
    mode: str = "interactive",
    task_id: str | None = None,
    pid: int | None = None,
    platform: str | None = None,
    tag: str = "",
    parent: str = "desktop",
) -> dict[str, Any]:
    """Register an external seat with the orchestrator task mesh."""
    from mag.orchestrator import register_external

    seat = (seat or "cursor").strip()
    platform = (platform or _SEAT_PLATFORM.get(seat, seat)).strip()
    rec = register_external(
        goal=goal,
        seat=seat,
        platform=platform,
        mode=mode,
        task_id=task_id,
        pid=pid,
        tag=tag or f"{seat}-external",
        parent=parent,
    )
    _trail("register", rec["task_id"], seat=seat, mode=mode, parent=parent)
    rec["mag_task_id"] = rec["task_id"]
    rec["hint"] = (
        f"Set MAG_TASK_ID={rec['task_id']} in the seat environment; "
        "use --query for queued/restful work (not REPL)."
    )
    return rec


def heartbeat(task_id: str, **fields: Any) -> dict[str, Any]:
    """Refresh liveness for a registered seat (pigeonhole + task record)."""
    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "error": "task_id required"}

    from mag import pigeonhole as ph
    from mag.orchestrator import touch_external

    meta = {k: v for k, v in fields.items() if v is not None}
    ph.heartbeat(task_id, seat=meta.get("seat"), phase=meta.get("phase"), **meta)
    if meta.get("phase") or meta.get("goal"):
        ph.write_status(
            task_id,
            phase=str(meta.get("phase") or "running"),
            goal=str(meta.get("goal") or "")[:300],
        )
    touch_external(task_id, **meta)
    _trail("heartbeat", task_id, **{k: meta[k] for k in ("phase", "seat", "goal") if k in meta})
    return {"ok": True, "task_id": task_id}


def unregister(task_id: str, *, status: str = "done", detail: str = "") -> dict[str, Any]:
    """Mark a registered external seat terminal."""
    from mag.orchestrator import finalize_external

    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "error": "task_id required"}
    rec = finalize_external(task_id, status=status, detail=detail or f"unregister:{status}")
    _trail("unregister", task_id, status=status)
    return {"ok": True, **rec}


def list_registered(*, limit: int = 50, live_only: bool = False) -> list[dict[str, Any]]:
    """External + seat-guard seats for operator glance."""
    from mag.orchestrator import list_external_tasks

    out = list_external_tasks(limit=limit)
    if live_only:
        out = [t for t in out if t.get("status") == "running"]
    for p in _seat_guard_records(limit=limit):
        tid = p.get("task_id")
        if tid and not any(t.get("task_id") == tid for t in out):
            out.append(p)
    return out[:limit]


def _seat_guard_records(*, limit: int = 20) -> list[dict[str, Any]]:
    if not GUARD_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(GUARD_DIR.glob("seat-*.json"), reverse=True)[:limit]:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("status") != "running":
            continue
        tid = str(rec.get("task_id") or "")
        rows.append({
            "task_id": tid,
            "tag": "seat-guard",
            "status": "running",
            "source": "seat_guard",
            "seat": rec.get("provider") or "agent",
            "platform": _SEAT_PLATFORM.get(str(rec.get("provider") or ""), "deepseek"),
            "mode": "interactive",
            "goal": f"supervised seat ({rec.get('provider')})",
            "pid": rec.get("pid"),
            "peer_id": f"seat:{tid}",
            "why": ["seat_guard:running"],
        })
    return rows


def mesh_peers() -> list[dict[str, Any]]:
    """ProcessPeer-shaped dicts for switchboard (external + seat-guard)."""
    peers: list[dict[str, Any]] = []
    for t in list_registered(limit=80, live_only=True):
        tid = str(t.get("task_id") or "")
        seat = str(t.get("seat") or "unknown")
        platform = str(t.get("platform") or _SEAT_PLATFORM.get(seat, seat))
        peers.append({
            "peer_id": t.get("peer_id") or f"ext:{tid}",
            "kind": "seat" if t.get("source") == "seat_guard" else "external",
            "seat": seat,
            "platform": platform,
            "tier_max": "T2",
            "status": t.get("status") or "running",
            "group": "external_seats",
            "importance": 85 if seat == "cursor" else 70,
            "alive": t.get("alive"),
            "phase": t.get("phase"),
            "goal": str(t.get("goal") or "")[:200],
            "task_id": tid,
            "pid": t.get("pid"),
            "heartbeat_age_s": t.get("heartbeat_age_s"),
            "why": t.get("why") or [f"source:{t.get('source', 'external')}"],
        })
    return peers


def register_env_for_launch(seat: str = "cursor", goal: str = "") -> dict[str, Any]:
    """Register + return env vars for launcher scripts."""
    rec = register(seat=seat, goal=goal, mode="interactive", parent="launcher")
    tid = rec["task_id"]
    os.environ["MAG_TASK_ID"] = tid
    os.environ["MAG_OPERATOR_ACTIVE"] = "1"
    return rec


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(prog="mag seats", description="Unified seat registry")
    sub = p.add_subparsers(dest="action")

    pr = sub.add_parser("register", help="Register desktop/cloud seat with orchestrator mesh")
    pr.add_argument("--seat", default="cursor")
    pr.add_argument("--goal", default="")
    pr.add_argument("--mode", default="interactive", choices=["interactive", "oneshot", "cloud", "improve"])
    pr.add_argument("--task-id", default="")
    pr.add_argument("--pid", type=int, default=None)
    pr.add_argument("--tag", default="")
    pr.add_argument("--parent", default="desktop")
    pr.add_argument("--json", action="store_true")

    phb = sub.add_parser("heartbeat", help="Refresh seat liveness")
    phb.add_argument("task_id")
    phb.add_argument("--phase", default="")
    phb.add_argument("--goal", default="")
    phb.add_argument("--seat", default="")
    phb.add_argument("--json", action="store_true")

    pu = sub.add_parser("unregister", help="Mark seat done/failed")
    pu.add_argument("task_id")
    pu.add_argument("--status", default="done")
    pu.add_argument("--detail", default="")
    pu.add_argument("--json", action="store_true")

    pl = sub.add_parser("list", help="List registered external seats")
    pl.add_argument("--live", action="store_true")
    pl.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    if args.action == "register":
        rec = register(
            seat=args.seat,
            goal=args.goal,
            mode=args.mode,
            task_id=(args.task_id or None) or None,
            pid=args.pid,
            tag=args.tag,
            parent=args.parent,
        )
        if args.json:
            print(json.dumps(rec, indent=2, default=str))
        else:
            print(f"registered {rec['task_id']} seat={args.seat} mode={args.mode}")
            print(rec.get("hint", ""))
        return 0
    if args.action == "heartbeat":
        rec = heartbeat(
            args.task_id,
            phase=(args.phase or None),
            goal=(args.goal or None),
            seat=(args.seat or None),
        )
        print(json.dumps(rec, indent=2, default=str) if args.json else f"heartbeat ok {args.task_id}")
        return 0 if rec.get("ok") else 1
    if args.action == "unregister":
        rec = unregister(args.task_id, status=args.status, detail=args.detail)
        print(json.dumps(rec, indent=2, default=str) if args.json else f"unregistered {args.task_id}")
        return 0 if rec.get("ok") else 1
    if args.action == "list":
        rows = list_registered(live_only=bool(args.live))
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
        else:
            for r in rows:
                print(f"  {r.get('task_id')} {r.get('seat')} {r.get('status')} {str(r.get('goal',''))[:50]}")
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
