"""Cross-seat coordination — shared activity + depth routing.

All seats (Cursor, DeepSeek, Grok TUI, local janitor) read the same activity
feed so agents see what others are doing. Depth classifier routes work to the
cheapest capable seat to preserve tokens ecosystem-wide.

Depths: overview | plan | heavy_code | simple_code | scut
Seats:  grok_tui (plan/overview) | deepseek (heavy) | local (simple/scut)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT, STATE_DIR

SCHEMA = "shared_activity.v1"
ACTIVITY_PATH = STATE_DIR / "shared_activity.jsonl"

VALID_DEPTHS = frozenset(
    {"overview", "plan", "heavy_code", "simple_code", "scut", "conversation"}
)

DEPTH_ROUTES: dict[str, dict[str, Any]] = {
    "overview": {
        "seat": "grok_tui",
        "mode": "plan",
        "launch": False,
        "tier": "L2-TUI",
        "token_hint": "File pack + ask in Grok TUI — do not auto-run remote.",
    },
    "plan": {
        "seat": "grok_tui",
        "mode": "plan",
        "launch": False,
        "tier": "L2-TUI",
        "token_hint": "Context-pack + [priority] Grok for architecture planning.",
    },
    "heavy_code": {
        "seat": "deepseek",
        "mode": "delegate",
        "launch": True,
        "provider": "deepseek",
        "tier": "L2-agent",
        "token_hint": "DeepSeek tool loop — multi-step coding.",
    },
    "simple_code": {
        "seat": "local",
        "mode": "dispatch",
        "launch": True,
        "provider": "ollama",
        "tier": "L0",
        "token_hint": "Local janitor / short dispatch — preserve remote tokens.",
    },
    "conversation": {
        "seat": "local",
        "mode": "dispatch",
        "launch": True,
        "provider": "ollama",
        "tier": "L0",
        "token_hint": "Life/ideas dig — local speak + optional scout; fidelity escalate uses brief.",
    },
    "scut": {
        "seat": "local",
        "mode": "dispatch",
        "launch": True,
        "provider": "ollama",
        "tier": "L0",
        "token_hint": "Status, bonds, brief — never Grok.",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(s: str | None, n: int = 400) -> str:
    t = (s or "").replace("\r", " ").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1].strip() + "…"


def log_activity(
    *,
    seat: str,
    depth: str,
    goal: str,
    status: str = "running",
    actor: str | None = None,
    detail: str = "",
    task_id: str | None = None,
    activity_id: str | None = None,
) -> dict[str, Any]:
    """Append one row to state/shared_activity.jsonl (shared visibility)."""
    ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": SCHEMA,
        "id": activity_id or f"act-{uuid.uuid4().hex[:12]}",
        "ts": _now(),
        "seat": (seat or "mag").strip() or "mag",
        "actor": (actor or seat or "mag").strip() or "mag",
        "depth": depth if depth in VALID_DEPTHS else "scut",
        "goal": _clip(goal, 500),
        "status": (status or "running").strip(),
        "detail": _clip(detail, 300),
        "task_id": task_id,
    }
    with ACTIVITY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_activity(*, limit: int = 40) -> list[dict[str, Any]]:
    if not ACTIVITY_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = ACTIVITY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-max(1, min(limit, 200)) :]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                rows.append(o)
        except json.JSONDecodeError:
            continue
    # Latest appended row per activity id wins. File order is the authoritative
    # tie-breaker because Windows can emit identical timestamps for fast events.
    by_id: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for r in reversed(rows):
        aid = str(r.get("id") or "")
        key = aid or f"_row_{len(by_id)}"
        if key in by_id:
            continue
        by_id[key] = r
        ordered.append(r)
    return ordered[:limit]


def activity_summary(*, limit: int = 12) -> dict[str, Any]:
    rows = read_activity(limit=limit)
    running = [r for r in rows if r.get("status") == "running"]
    by_seat: dict[str, int] = {}
    by_depth: dict[str, int] = {}
    for r in rows:
        s = str(r.get("seat") or "?")
        d = str(r.get("depth") or "?")
        by_seat[s] = by_seat.get(s, 0) + 1
        by_depth[d] = by_depth.get(d, 0) + 1
    path_str = str(ACTIVITY_PATH)
    try:
        if ACTIVITY_PATH.is_file():
            path_str = str(ACTIVITY_PATH.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        path_str = str(ACTIVITY_PATH)
    return {
        "ok": True,
        "schema": "coordination_summary.v1",
        "ts": _now(),
        "path": path_str,
        "running_n": len(running),
        "running": running[:8],
        "recent": rows[:limit],
        "by_seat": by_seat,
        "by_depth": by_depth,
    }


def format_activity_excerpt(*, limit: int = 6, max_chars: int = 900) -> str:
    """Plain block for context-pack injection."""
    rows = read_activity(limit=limit)
    if not rows:
        return ""
    lines = ["[COORDINATION — what other seats are doing]"]
    for r in rows[:limit]:
        lines.append(
            f"- {r.get('status', '?')} · {r.get('seat', '?')} · {r.get('depth', '?')} · "
            f"{r.get('goal', '')[:120]}"
        )
    text = "\n".join(lines)
    return text[:max_chars]


def classify_depth(goal: str, *, depth: str | None = None) -> dict[str, Any]:
    """Classify work depth and recommended seat (token-aware)."""
    from mag.router import classify_depth as _classify

    return _classify(goal, depth=depth)


def coordinate(
    goal: str,
    *,
    depth: str | None = None,
    seat: str = "mag",
    actor: str | None = None,
    launch: bool = True,
    background: bool = False,
    session_id: str | None = None,
    force_provider: str | None = None,
    force_seat: str | None = None,
) -> dict[str, Any]:
    """Classify depth, log activity, optionally launch the appropriate worker."""
    from mag.router import route

    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    routed = route(goal, depth=depth, force_seat=force_seat, force_provider=force_provider)
    if not routed.get("ok"):
        return {
            "ok": False,
            "error": routed.get("error") or "unroutable",
            "hint": routed.get("hint"),
            "route": routed,
        }

    classified = routed.get("classification") or {}
    d = str(routed.get("depth") or classified.get("depth"))
    caller = (actor or seat or "mag").strip() or "mag"
    act = log_activity(
        seat=seat,
        depth=d,
        goal=goal,
        status="queued" if launch else "planned",
        actor=caller,
        detail=routed.get("hint") or classified.get("token_hint") or "",
    )

    out: dict[str, Any] = {
        "ok": True,
        "schema": "coordinate.v1",
        "activity_id": act["id"],
        "classification": classified,
        "route": routed,
        "launched": False,
    }

    if not launch:
        out["action"] = "classified_only"
        return out

    if not routed.get("executable"):
        if d in ("overview", "plan"):
            try:
                from mag.context_pack import build_context_pack, format_context_pack_text

                pack = build_context_pack(max_brief=700, max_live=300)
                text = format_context_pack_text(pack, max_chars=2400)
            except Exception as e:
                text = f"(pack failed: {e})"
            log_activity(
                seat="grok_tui",
                depth=d,
                goal=goal,
                status="planned",
                actor=caller,
                detail="Awaiting Grok TUI with context pack",
                activity_id=act["id"],
            )
            out.update(
                {
                    "action": "file_for_grok",
                    "seat": "grok_tui",
                    "hint": routed.get("hint"),
                    "pack_excerpt": text[:2400],
                    "commands": {
                        "pack": "python main.py context-pack",
                        "grok": "Paste ACTIVATION + pack into Grok TUI with [priority]",
                    },
                }
            )
            return out
        if routed.get("seat") == "cursor":
            out.update(
                {
                    "action": "defer_to_cursor",
                    "seat": "cursor",
                    "hint": routed.get("hint"),
                }
            )
            return out
        return {
            "ok": False,
            "error": routed.get("error") or "not_executable",
            "hint": routed.get("hint"),
            "route": routed,
            "activity_id": act["id"],
        }

    mode = str(routed.get("mode") or "dispatch")
    if d == "heavy_code" and background:
        mode = "queue"
    route_seat = str(routed.get("seat") or "local")
    provider = routed.get("provider") or "deepseek"

    log_activity(
        seat=route_seat,
        depth=d,
        goal=goal,
        status="running",
        actor=caller,
        activity_id=act["id"],
    )

    try:
        if mode == "queue":
            from mag.orchestrator import enqueue

            task = enqueue(
                goal=goal,
                provider=provider,
                tag=f"coord-{d}",
            )
            log_activity(
                seat=route_seat,
                depth=d,
                goal=goal,
                status="queued",
                actor=caller,
                task_id=str(task.get("id") or task.get("task_id") or ""),
                detail="orchestrator queue",
                activity_id=act["id"],
            )
            out.update({"launched": True, "action": "queue", "mode": "queue", "task": task})
            return out

        if mode == "delegate":
            from mag.agent_cli import api_agent_turn

            sid = session_id or f"{seat}-coord"
            res = api_agent_turn(
                goal,
                provider=provider,
                session_id=sid,
            )
            log_activity(
                seat=route_seat,
                depth=d,
                goal=goal,
                status="done" if res.get("ok") else "failed",
                actor=caller,
                detail=_clip(str(res.get("error") or res.get("answer") or ""), 200),
                activity_id=act["id"],
            )
            out.update({"launched": True, "action": "delegate", "mode": "delegate", "result": res})
            return out

        if mode == "dispatch":
            from mag.dispatch import dispatch

            res = dispatch(
                goal,
                execute=True,
                force_seat=route_seat if route_seat != "remote" else None,
                force_provider=provider if route_seat == "remote" else None,
            )
            log_activity(
                seat=route_seat,
                depth=d,
                goal=goal,
                status="done" if res.get("ok", True) else "failed",
                actor=caller,
                detail=_clip(str(res.get("hint") or res.get("job") or ""), 200),
                activity_id=act["id"],
            )
            out.update({"launched": True, "action": "dispatch", "mode": "dispatch", "result": res})
            return out

    except Exception as e:
        log_activity(
            seat=route_seat,
            depth=d,
            goal=goal,
            status="failed",
            actor=caller,
            detail=str(e)[:200],
            activity_id=act["id"],
        )
        return {"ok": False, "error": str(e), "activity_id": act["id"], "classification": classified, "route": routed}

    return out
