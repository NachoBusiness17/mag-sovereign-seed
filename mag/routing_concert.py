"""Routing concert — multi-seat orchestration via switchboard + conductor.

DeepSeek (or conductor seat) plans which models run in what order for a goal.
Local scouts cheaply; frontier executes; errors escalate per tier law.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from config import ROOT

TRAIL = ROOT / "memory" / "runs" / "routing_concert_trail.jsonl"
SCHEMA = "routing_concert.v1"

# Default concert phases for common goal shapes
_PHASE_TEMPLATES: list[dict[str, str]] = [
    {"phase": "scout", "seat": "local", "pack_mode": "janitor", "why": "cheap context + status"},
    {"phase": "route", "seat": "local", "pack_mode": "route", "why": "switchboard dry run"},
    {"phase": "execute", "seat": "deepseek", "pack_mode": "build", "why": "primary work seat"},
    {"phase": "audit", "seat": "cursor", "pack_mode": "audit", "why": "gate + file artifact"},
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _goal_shape(goal: str) -> str:
    g = (goal or "").lower()
    if any(w in g for w in ("doctor", "status", "health", "probe", "audit", "verkle")):
        return "scout"
    if any(w in g for w in ("implement", "build", "fix", "code", "wire")):
        return "build"
    if any(w in g for w in ("plan", "define", "scope", "research")):
        return "plan"
    if any(w in g for w in ("route", "dispatch", "handoff", "coordinate")):
        return "route"
    return "general"


def build_concert_plan(goal: str, *, conductor_seat: str = "deepseek") -> dict[str, Any]:
    """Plan multi-seat concert without executing — switchboard + heuristics."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    shape = _goal_shape(goal)
    concert_id = f"concert-{uuid.uuid4().hex[:10]}"

    try:
        from mag.switchboard import route_intent, mesh, peers

        route = route_intent(goal, dry=True)
        mesh_snap = mesh(include_seats=True)
        live = peers(live_only=True)
    except Exception as exc:
        route = {"error": str(exc)}
        mesh_snap = {}
        live = []

    primary = (route.get("target") or {}) if isinstance(route, dict) else {}
    primary_seat = str(primary.get("seat") or "local")

    steps: list[dict[str, Any]] = []

    # Always open with local janitor scout when not already local-only
    if shape in ("build", "plan", "general", "route"):
        steps.append(
            {
                "order": 1,
                "phase": "scout",
                "seat": "local",
                "pack_mode": "janitor",
                "goal": f"Scout status for: {goal[:120]}",
                "why": "L0 cheap — gather gate/context before frontier",
                "status": "pending",
            }
        )

    steps.append(
        {
            "order": len(steps) + 1,
            "phase": "route",
            "seat": "local",
            "pack_mode": "route",
            "goal": goal,
            "why": "switchboard route_intent (dry)",
            "status": "pending",
            "route_hint": primary,
        }
    )

    exec_seat = primary_seat if primary_seat not in ("defer", "human") else "deepseek"
    if shape == "scout":
        exec_seat = "local"
    elif shape == "build" and exec_seat == "local":
        exec_seat = "deepseek"

    steps.append(
        {
            "order": len(steps) + 1,
            "phase": "execute",
            "seat": exec_seat,
            "pack_mode": "build" if shape == "build" else "janitor",
            "goal": goal,
            "why": f"primary seat from switchboard ({primary_seat})",
            "status": "pending",
            "tier_max": primary.get("tier_max") or "T2",
        }
    )

    if shape == "build":
        steps.append(
            {
                "order": len(steps) + 1,
                "phase": "audit",
                "seat": "cursor",
                "pack_mode": "audit",
                "goal": f"Audit output for: {goal[:80]}",
                "why": "gate before merge",
                "status": "pending",
            }
        )

    # Conductor validates plan (DeepSeek meta — not executed here)
    conductor_step = {
        "order": 0,
        "phase": "conductor",
        "seat": conductor_seat,
        "pack_mode": "route",
        "goal": goal,
        "why": "validate concert plan + reorder seats if needed",
        "status": "pending",
        "prompt_hint": (
            "You are routing conductor. Given goal and steps[], confirm seat order "
            "or reorder for cost (local first) vs quality (frontier for build). "
            "Reply JSON: {ok, steps[], escalate_to?}"
        ),
    }

    plan = {
        "ok": True,
        "schema": SCHEMA,
        "concert_id": concert_id,
        "goal": goal[:500],
        "shape": shape,
        "conductor_seat": conductor_seat,
        "conductor": conductor_step,
        "steps": steps,
        "switchboard_route": route,
        "mesh_summary": (mesh_snap.get("summary") or {}) if isinstance(mesh_snap, dict) else {},
        "live_peers": len(live),
        "ts": _utc(),
    }
    _trail("plan", concert_id=concert_id, goal=goal[:200], shape=shape, n_steps=len(steps))
    return plan


def run_concert_step(plan: dict[str, Any], *, step_order: int, dry: bool = False) -> dict[str, Any]:
    """Execute one concert step — route, coordinate, or desk wake."""
    steps = list(plan.get("steps") or [])
    step = next((s for s in steps if int(s.get("order") or 0) == step_order), None)
    if not step:
        return {"ok": False, "error": f"no step order={step_order}"}

    seat = str(step.get("seat") or "local")
    goal = str(step.get("goal") or plan.get("goal") or "")
    phase = str(step.get("phase") or "execute")
    result: dict[str, Any] = {"ok": True, "step": step, "phase": phase, "seat": seat}

    if dry:
        result["dry"] = True
        result["would"] = f"{phase} via {seat}: {goal[:120]}"
        return result

    try:
        if phase == "route":
            from mag.switchboard import route_intent

            result["output"] = route_intent(goal, dry=False)
        elif phase == "scout":
            from mag.nervous_system import build_glance

            result["output"] = build_glance(write=False)
        elif phase in ("execute", "conductor"):
            from mag.coordination import coordinate

            result["output"] = coordinate(
                goal,
                seat=seat if seat != "deepseek" else "agent",
                actor="routing_concert",
                launch=True,
                background=seat == "local",
            )
        elif phase == "audit":
            from mag.router import route

            result["output"] = route(goal, depth="audit")
        else:
            result["output"] = {"note": f"unknown phase {phase}"}
    except Exception as exc:
        result["ok"] = False
        result["error"] = str(exc)[:300]

    step["status"] = "done" if result.get("ok") else "failed"
    step["result_ts"] = _utc()
    _trail(
        "step",
        concert_id=plan.get("concert_id"),
        order=step_order,
        phase=phase,
        seat=seat,
        ok=result.get("ok"),
    )
    return result


def run_concert(plan: dict[str, Any], *, dry: bool = False, max_steps: int = 6) -> dict[str, Any]:
    """Run all pending steps in order."""
    results = []
    for step in sorted(plan.get("steps") or [], key=lambda s: int(s.get("order") or 0)):
        if step.get("status") == "done":
            continue
        if len(results) >= max_steps:
            break
        r = run_concert_step(plan, step_order=int(step.get("order") or 0), dry=dry)
        results.append(r)
        if not r.get("ok") and not dry:
            break
    return {"ok": True, "concert_id": plan.get("concert_id"), "results": results, "plan": plan}


def conductor_review_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Task DeepSeek to review/reorder concert plan (routing network job)."""
    goal = str(plan.get("goal") or "")
    steps_json = json.dumps(plan.get("steps") or [], indent=0)[:2000]
    prompt = (
        f"Routing conductor review.\nGoal: {goal}\n\nProposed steps:\n{steps_json}\n\n"
        "Reply with compact JSON only: "
        '{"ok":true,"steps":[{"order":1,"seat":"local|deepseek|cursor|grok_tui","phase":"...","why":"..."}],'
        '"escalate_to":null|"deepseek"|"human","notes":"one line"}'
    )
    try:
        from models.providers import chat_messages

        res = chat_messages(
            "deepseek",
            [
                {
                    "role": "system",
                    "content": (
                        "You are Mag routing conductor. Output JSON only. "
                        "Prefer local first for scout/route; deepseek for build."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            tools=None,
            tier="T2",
            max_tokens=512,
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error") or "deepseek failed", "plan": plan}
        text = (res.get("text") or "").strip()
        # Best-effort JSON extract
        start = text.find("{")
        end = text.rfind("}") + 1
        parsed = json.loads(text[start:end]) if start >= 0 and end > start else {"raw": text}
        plan["conductor_review"] = parsed
        plan["conductor"]["status"] = "done"
        _trail("conductor_review", concert_id=plan.get("concert_id"), ok=parsed.get("ok", True))
        return {"ok": True, "review": parsed, "plan": plan}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "plan": plan}


def status() -> dict[str, Any]:
    """Glance for dashboard."""
    try:
        from mag.switchboard import mesh, peers

        m = mesh(include_seats=False)
        live = peers(live_only=True)
    except Exception as exc:
        m = {"error": str(exc)}
        live = []
    rows = []
    if TRAIL.is_file():
        try:
            for line in TRAIL.read_text(encoding="utf-8").splitlines()[-8:]:
                if line.strip():
                    rows.append(json.loads(line))
        except Exception:
            pass
    return {
        "ok": True,
        "schema": SCHEMA,
        "mesh": m.get("summary") if isinstance(m, dict) else m,
        "live_peers": len(live),
        "recent_trail": rows,
    }
