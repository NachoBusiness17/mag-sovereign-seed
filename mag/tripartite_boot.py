"""Tripartite coordinated boot — heart (local) · mind (routing) · body (agents).

When Mag boots multiple seats, each layer files to shared_activity so every
spawned agent reads the same coordination state on first context-pack.

  Heart — local disk, state, active env track (home PC is sovereign)
  Mind  — router, peer handoffs, depth doctrine (where work goes)
  Body  — spawned slots: dashboard, scribe, drainer, cursor, deepseek…

CLI: python main.py boot-coordination run
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT, STATE_DIR

SCHEMA = "tripartite_boot.v1"
BOOT_DIR = ROOT / "memory" / "boot"
LATEST_JSON = BOOT_DIR / "tripartite_latest.json"
LATEST_MD = BOOT_DIR / "tripartite_latest.md"
BOOT_LOG = ROOT / "logs" / "boot_coordination.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _heart_pulse() -> dict[str, Any]:
    """Local sovereign layer — disk, env track, state paths."""
    active_env: str | None = None
    try:
        from mag.env_registry import get_active_env

        active_env = get_active_env()
    except Exception:
        pass

    return {
        "role": "heart",
        "ok": True,
        "root": str(ROOT),
        "active_env": active_env,
        "state_dir": _rel(STATE_DIR),
        "activity_path": "state/shared_activity.jsonl",
        "law": "File on disk; human promote; local is sovereign",
    }


def _mind_pulse() -> dict[str, Any]:
    """Routing framework — depth doctrine, peer handoffs, coordination feed."""
    peer_brief = ""
    peer_n = 0
    try:
        from mag.peer_handoff import format_latest_brief, list_peer_handoffs

        peer_brief = format_latest_brief()
        peer_n = len(list_peer_handoffs(limit=5))
    except Exception:
        pass

    route_ok = True
    sample_route: dict[str, Any] = {}
    try:
        from mag.coordination import classify_depth

        sample_route = classify_depth("status check scut work", depth="scut")
    except Exception as exc:
        route_ok = False
        sample_route = {"error": str(exc)[:120]}

    return {
        "role": "mind",
        "ok": route_ok,
        "doctrine": "overview/plan→Grok · heavy→DeepSeek · simple/scut→local",
        "peer_handoffs_n": peer_n,
        "peer_brief": peer_brief[:800] if peer_brief else "",
        "sample_route": {
            "depth": sample_route.get("depth"),
            "seat": (sample_route.get("route") or {}).get("seat")
            if isinstance(sample_route.get("route"), dict)
            else sample_route.get("seat"),
        },
        "law": "Route by depth; never auto-run Grok; coordination feed is truth",
    }


def _body_pulse(
    *,
    body_slots: list[dict[str, Any]] | None = None,
    seat: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Spawned agents — supervisor slots + registering seat."""
    slots_out: list[dict[str, Any]] = []
    if body_slots:
        for s in body_slots:
            proc = s.get("proc")
            pid = None
            alive = False
            if proc is not None:
                try:
                    pid = proc.pid
                    alive = proc.poll() is None
                except Exception:
                    pass
            slots_out.append({
                "name": s.get("name"),
                "wanted": bool(s.get("wanted")),
                "alive": alive,
                "pid": pid,
                "note": s.get("note", ""),
            })

    registering = seat or "mag"
    return {
        "role": "body",
        "ok": True,
        "registering_seat": registering,
        "task_id": task_id,
        "slots": slots_out,
        "slot_names": [x["name"] for x in slots_out if x.get("wanted")],
        "law": "Body executes; mind routes; heart files outcomes",
    }


def _write_markdown(manifest: dict[str, Any]) -> None:
    heart = manifest.get("heart") or {}
    mind = manifest.get("mind") or {}
    body = manifest.get("body") or {}
    lines = [
        "# Tripartite boot — heart · mind · body",
        "",
        f"_ts: {manifest.get('ts')}_ · actor: `{manifest.get('actor')}`",
        "",
        "## Heart (local)",
        f"- root: `{heart.get('root')}`",
        f"- active env: `{heart.get('active_env') or '(none)'}`",
        f"- state: `{heart.get('state_dir')}`",
        "",
        "## Mind (routing)",
        f"- doctrine: {mind.get('doctrine')}",
        f"- peer handoffs pending: {mind.get('peer_handoffs_n', 0)}",
    ]
    if mind.get("peer_brief"):
        lines.extend(["", mind.get("peer_brief", "")])
    lines.extend([
        "",
        "## Body (spawned agents)",
        f"- registering seat: `{body.get('registering_seat')}`",
    ])
    if body.get("task_id"):
        lines.append(f"- task_id: `{body.get('task_id')}`")
    for slot in body.get("slots") or []:
        status = "alive" if slot.get("alive") else ("wanted" if slot.get("wanted") else "off")
        lines.append(f"- {slot.get('name')}: {status}")
    lines.extend([
        "",
        "_Every seat reads this via context-pack coordination block._",
        "",
    ])
    LATEST_MD.write_text("\n".join(lines), encoding="utf-8")


def _log_coordination(manifest: dict[str, Any]) -> None:
    try:
        from mag.coordination import log_activity

        heart = manifest.get("heart") or {}
        mind = manifest.get("mind") or {}
        body = manifest.get("body") or {}
        slots = ", ".join(body.get("slot_names") or []) or body.get("registering_seat", "mag")

        log_activity(
            seat="heart",
            depth="scut",
            goal=f"local boot env={heart.get('active_env') or 'default'}",
            status="ok" if heart.get("ok") else "degraded",
            actor=manifest.get("actor") or "mag",
            detail=f"root={_rel(ROOT)}",
            activity_id=f"boot-heart-{manifest.get('boot_id', '')[:8]}",
        )
        log_activity(
            seat="mind",
            depth="plan",
            goal="routing framework online",
            status="ok" if mind.get("ok") else "degraded",
            actor=manifest.get("actor") or "mag",
            detail=f"peer_handoffs={mind.get('peer_handoffs_n', 0)}",
            activity_id=f"boot-mind-{manifest.get('boot_id', '')[:8]}",
        )
        log_activity(
            seat="body",
            depth="scut",
            goal=f"agents spawning: {slots}",
            status="running",
            actor=manifest.get("actor") or "mag",
            detail=f"seat={body.get('registering_seat')}",
            activity_id=f"boot-body-{manifest.get('boot_id', '')[:8]}",
        )
    except Exception:
        pass


def run_coordinated_boot(
    *,
    actor: str = "mag",
    body_slots: list[dict[str, Any]] | None = None,
    seat: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """File heart/mind/body boot manifest + coordination heartbeats."""
    import uuid

    boot_id = uuid.uuid4().hex[:12]
    heart = _heart_pulse()
    mind = _mind_pulse()
    body = _body_pulse(body_slots=body_slots, seat=seat, task_id=task_id)

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "boot_id": boot_id,
        "ts": _now(),
        "actor": actor,
        "ok": heart.get("ok") and mind.get("ok") and body.get("ok"),
        "heart": heart,
        "mind": mind,
        "body": body,
    }

    BOOT_DIR.mkdir(parents=True, exist_ok=True)
    BOOT_LOG.parent.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _write_markdown(manifest)
    _log_coordination(manifest)

    slim = {
        "ts": manifest["ts"],
        "boot_id": boot_id,
        "actor": actor,
        "ok": manifest["ok"],
        "active_env": heart.get("active_env"),
        "body_seats": body.get("slot_names") or [body.get("registering_seat")],
    }
    with BOOT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(slim, ensure_ascii=False, default=str) + "\n")

    try:
        from mag.training_events import emit

        emit(
            "autorun_cycle",
            join={"boot_id": boot_id, "actor": actor},
            input_data={"active_env": heart.get("active_env")},
            action={"layers": ["heart", "mind", "body"]},
            outcome={
                "body_slots": body.get("slot_names"),
                "peer_handoffs": mind.get("peer_handoffs_n"),
            },
            pattern_tags=["tripartite_boot", f"actor_{actor}"],
        )
    except Exception:
        pass

    manifest["report_md"] = _rel(LATEST_MD)
    manifest["report_json"] = _rel(LATEST_JSON)
    return manifest


def _pulse_layer(
    *,
    layer: str,
    goal: str,
    status: str = "running",
    detail: str = "",
    task_id: str | None = None,
    depth: str | None = None,
    actor: str = "mag",
) -> None:
    """Lightweight coordination pulse — woven into orchestrator/autorun loops."""
    import uuid as _uuid

    depth_map = {"heart": "scut", "mind": "plan", "body": "heavy_code"}
    try:
        from mag.coordination import log_activity

        log_activity(
            seat=layer,
            depth=depth or depth_map.get(layer, "scut"),
            goal=goal[:500],
            status=status,
            actor=actor,
            detail=detail[:300],
            task_id=task_id,
            activity_id=f"weave-{layer}-{task_id or _uuid.uuid4().hex[:8]}",
        )
    except Exception:
        pass


def _load_manifest() -> dict[str, Any]:
    if not LATEST_JSON.is_file():
        return {}
    try:
        return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_manifest_patch(**fields: Any) -> None:
    """Patch tripartite manifest without full reboot — keeps loops cheap."""
    manifest = _load_manifest()
    if not manifest:
        return
    manifest["ts"] = _now()
    manifest["weave"] = {**(manifest.get("weave") or {}), **fields, "ts": _now()}
    try:
        LATEST_JSON.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass


def refresh_manifest_body(
    *,
    supervisor_slots: list[dict[str, Any]] | None = None,
) -> None:
    """Sync body layer from mag_launch slots + orchestrator running tasks."""
    running: list[dict[str, Any]] = []
    try:
        from mag.orchestrator import list_tasks_live

        for t in list_tasks_live(limit=12):
            if t.get("status") not in ("running", "stalled"):
                continue
            running.append({
                "task_id": t.get("task_id"),
                "goal": str(t.get("goal") or _goal_from_task(t))[:100],
                "pid": t.get("pid"),
                "status": t.get("status"),
                "tag": t.get("tag"),
            })
    except Exception:
        pass

    manifest = _load_manifest()
    if not manifest:
        return
    body = manifest.get("body") or {}
    if supervisor_slots:
        slot_rows = []
        for s in supervisor_slots:
            proc = s.get("proc")
            alive = False
            if proc is not None:
                try:
                    alive = proc.poll() is None
                except Exception:
                    alive = False
            slot_rows.append({
                "name": s.get("name"),
                "wanted": bool(s.get("wanted")),
                "alive": alive,
                "pid": getattr(proc, "pid", None) if proc else None,
            })
        body["slots"] = slot_rows
        body["slot_names"] = [s["name"] for s in slot_rows if s.get("wanted")]
    body["orchestrator_running"] = running
    body["orchestrator_n"] = len(running)
    manifest["body"] = body
    manifest["ts"] = _now()
    try:
        LATEST_JSON.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        _write_markdown(manifest)
    except OSError:
        pass


def _goal_from_task(task: dict[str, Any]) -> str:
    cmd = task.get("cmd") or []
    for i, part in enumerate(cmd):
        if part in ("run", "agent") and i + 1 < len(cmd):
            return str(cmd[i + 1])
    return str(task.get("tag") or "orchestrator task")


def weave_route(*, goal: str, route: dict[str, Any], tag: str = "") -> None:
    """Mind pulse when governor routes a goal into the orchestrator queue."""
    import uuid

    depth = str(route.get("depth") or "?")
    provider = str(route.get("provider") or "?")
    _pulse_layer(
        layer="mind",
        goal=f"route→queue: {goal[:160]}",
        status="filed",
        detail=f"depth={depth} provider={provider} tag={tag[:40]}",
        depth=depth if depth in ("overview", "plan", "heavy_code", "simple_code", "scut") else "plan",
        actor="governor_autorun",
    )
    _save_manifest_patch(last_route={"goal": goal[:120], "depth": depth, "provider": provider})


def weave_spawn(*, task_id: str, goal: str, provider: str = "", pid: int | None = None, tag: str = "") -> None:
    """Body pulse when orchestrator spawns a subprocess agent."""
    _pulse_layer(
        layer="body",
        goal=f"spawn: {goal[:180]}",
        status="running",
        detail=f"provider={provider} tag={tag} pid={pid}",
        task_id=task_id,
        depth="heavy_code",
        actor="orchestrator",
    )
    _save_manifest_patch(last_spawn={"task_id": task_id, "goal": goal[:120], "pid": pid})


def weave_terminal(*, task_id: str, status: str, detail: str = "") -> None:
    """Body pulse when orchestrator subprocess finishes."""
    _pulse_layer(
        layer="body",
        goal=f"terminal: {task_id}",
        status=status,
        detail=detail[:200],
        task_id=task_id,
        depth="heavy_code",
        actor="orchestrator",
    )
    _save_manifest_patch(last_terminal={"task_id": task_id, "status": status})


def weave_drain(*, action: str, goal: str = "", task_id: str = "", queue_id: str = "") -> None:
    """Heart pulse on drain loop edge — local queue advancing."""
    _pulse_layer(
        layer="heart",
        goal=f"drain {action}: {goal[:140] or queue_id}",
        status="ok" if action == "started" else action,
        detail=f"task_id={task_id} queue_id={queue_id}",
        task_id=task_id or None,
        actor="orchestrator",
    )


def weave_autorun_tick(*, action: str, fill_total: int = 0, drain_action: str = "") -> None:
    """Weave one governor autorun tick into tripartite manifest."""
    _pulse_layer(
        layer="heart",
        goal=f"autorun {action}",
        status="running" if action in ("drain", "governor", "fill") else action,
        detail=f"fill={fill_total} drain={drain_action}",
        actor="governor_autorun",
    )
    _save_manifest_patch(last_autorun={"action": action, "fill_total": fill_total, "drain": drain_action})


def maybe_boot_on_autorun_start() -> dict[str, Any] | None:
    """Full tripartite boot on autorun tick 0 if manifest missing or stale."""
    manifest = _load_manifest()
    if manifest:
        try:
            ts = datetime.fromisoformat(str(manifest.get("ts", "")).replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h < 6:
                return None
        except Exception:
            pass
    return run_coordinated_boot(actor="autorun_loop", seat="mag")


def format_tripartite_excerpt(*, max_chars: int = 900) -> str:
    """Context-pack block — what heart/mind/body filed at last boot."""
    if not LATEST_JSON.is_file():
        return ""
    try:
        m = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    heart = m.get("heart") or {}
    mind = m.get("mind") or {}
    body = m.get("body") or {}
    lines = [
        "[TRIPARTITE — heart·mind·body]",
        f"- heart (local): env={heart.get('active_env') or 'default'} · {_rel(ROOT)}",
        f"- mind (routing): {mind.get('doctrine', '')[:80]}",
        f"- body (agents): {', '.join(body.get('slot_names') or [body.get('registering_seat', 'mag')])}",
    ]
    orc_n = body.get("orchestrator_n") or 0
    if orc_n:
        lines.append(f"- orchestrator subprocesses running: {orc_n}")
        for rt in (body.get("orchestrator_running") or [])[:3]:
            lines.append(f"  · {rt.get('task_id')}: {str(rt.get('goal', ''))[:60]}")
    weave = m.get("weave") or {}
    if weave.get("last_route"):
        lr = weave["last_route"]
        lines.append(f"- last route: {lr.get('depth')} → {str(lr.get('goal', ''))[:50]}")
    peer = (mind.get("peer_brief") or "").strip()
    if peer:
        lines.append(peer[:400])
    return "\n".join(lines)[:max_chars]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="boot-coordination")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--actor", default="mag")
    ap.add_argument("--seat", default=None)
    args = ap.parse_args(argv)
    res = run_coordinated_boot(actor=args.actor, seat=args.seat)
    print(json.dumps(res, indent=2, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
