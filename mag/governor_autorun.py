"""Intelligent governor autorun — fill queue, plan, route, execute.

The drainer (MAG_DRAINER=1) runs this loop instead of blind orchestrator drain:

  1. **Fill** — improve candidates, agent_state next_moves, handoff JSON → queue
  2. **Plan** — classify depth, match skills, estimate cost, pick provider/rental
  3. **Execute** — orchestrator drain for queued work, else governor cycle

Routing uses coordination.depth + models.quota.pick_provider (budget-aware),
configs/skills.yaml + IJL skill beads, and vast rental when configured.
"""
from __future__ import annotations

import json
import os
import sys
from mag import headless
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRAIL = ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl"
_LAST_PLAN_FP: str | None = None

# ONE runtime policy (state/DOCKER_ONLY), shared with mag.ghost and the
# process supervisor gate. B2-51 2026-09-26: this used to be a private copy
# here; the copies drifted and the supervisor classified this module's
# policy exit as a crash (the 2026-09-19 false crash-loop, 28 respawns).
# Cause + evidence receipt lives in mag/runtime_policy.py.
from mag.runtime_policy import DOCKER_ONLY_MARKER, host_runtime_blocked as _host_runtime_blocked

from mag.router import DEPTH_JOB_MAP  # single law — ponytail: no duplicate maps

DEPTH_COST_MULT: dict[str, int] = {
    "scut": 1,
    "simple_code": 2,
    "heavy_code": 8,
    "plan": 3,
    "overview": 2,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int | None) -> bool:
    """Cross-platform pid liveness (used by the single-instance carrier lock)."""
    if not pid:
        return False
    try:
        from mag.orchestrator import _pid_alive as _alive
        return bool(_alive(pid))
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False


def _log_trail(entry: dict[str, Any]) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), **entry}
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    try:
        from mag.training_events import emit

        phase = str(entry.get("phase") or "autorun")
        emit(
            "autorun_cycle",
            input_data={"phase": phase, "keys": list(entry.keys())[:12]},
            action={k: entry[k] for k in ("phase", "goal", "tag") if k in entry},
            outcome={"logged": True},
            pattern_tags=[f"gov_{phase}"],
        )
    except Exception:
        pass


def _drainer_active() -> bool:
    if os.environ.get("MAG_DRAINER", "").strip().lower() in ("1", "true", "yes"):
        return True
    try:
        from mag.preferences import drainer_enabled

        return drainer_enabled()
    except Exception:
        return False


def estimate_cost(goal: str, depth: str, provider: str) -> dict[str, Any]:
    """Rough token projection for routing decisions (not billing)."""
    base = max(500, len(goal or "") * 4)
    mult = DEPTH_COST_MULT.get(depth, 2)
    tokens = base * mult
    return {
        "tokens_est": tokens,
        "depth": depth,
        "provider": provider,
        "tier_hint": "L0" if provider == "ollama" else "L2",
    }


def match_skills(goal: str, depth: str, job: str) -> list[str]:
    """Connected skills from configs/skills.yaml + IJL beads."""
    skills: list[str] = []
    try:
        from mag.skills_pack import load_skills_cfg

        cfg = load_skills_cfg()
        job_map = cfg.get("job_to_skills") or {}
        skills.extend(list(job_map.get(job) or job_map.get("default") or []))
    except Exception:
        pass
    try:
        from ijl_core import skill_excerpt_for_goal

        if skill_excerpt_for_goal(goal, max_chars=40).strip():
            skills.append("ijl:matched")
    except Exception:
        pass
    # depth-specific skill hints from configs when tags overlap
    if depth in ("heavy_code", "simple_code") and "patch-verify" not in skills:
        g = (goal or "").lower()
        if any(k in g for k in ("fix", "patch", "refactor", "implement")):
            skills.append("patch-verify")
    return skills


def route_task(goal: str, *, depth: str | None = None) -> dict[str, Any]:
    """Plan one goal: depth, provider, mode, projected cost, skills (unified router)."""
    try:
        from mag.router import route as unified_route

        r = unified_route(goal, depth=depth)
        d = str(r.get("depth") or "simple_code")
        provider = str(r.get("provider") or "ollama")
        cost = estimate_cost(goal, d, provider)
        return {
            "ok": bool(r.get("ok", True)),
            "schema": "route.v2",
            "goal": (goal or "")[:300],
            "depth": d,
            "job": str(r.get("job") or DEPTH_JOB_MAP.get(d, "default")),
            "provider": provider,
            "mode": str(r.get("mode") or "dispatch"),
            "launch": bool(r.get("launch", True)),
            "executable": bool(r.get("executable", True)),
            "rental": bool(r.get("rental")),
            "classification": r.get("classified") or {},
            "pick": r.get("pick") or {},
            "cost_estimate": cost,
            "skills": list(r.get("skills") or match_skills(goal, d, str(r.get("job") or ""))),
            "hint": str(r.get("hint") or "")[:200],
            "error": r.get("error"),
        }
    except Exception:
        pass

    from mag.coordination import classify_depth
    from models.quota import pick_provider, provider_budget

    classified = classify_depth(goal, depth=depth)
    d = str(classified.get("depth") or "simple_code")
    job = DEPTH_JOB_MAP.get(d, "default")

    prefer: list[str] | None = None
    rental = False
    if d == "heavy_code":
        vast = provider_budget("vast")
        if vast.get("configured") and vast.get("budget_ok"):
            prefer = ["vast", "deepseek", "deepseek_overmind", "anthropic", "ollama"]
            rental = True
    elif d in ("scut", "simple_code"):
        prefer = ["ollama", "groq", "openrouter", "deepseek"]

    picked = pick_provider(job=job, prefer=prefer)
    provider = picked.get("provider") or classified.get("provider") or "ollama"
    if not picked.get("ok") and d in ("scut", "simple_code"):
        provider = "ollama"

    cost = estimate_cost(goal, d, provider)
    skills = match_skills(goal, d, job)

    return {
        "ok": True,
        "schema": "route.v1",
        "goal": (goal or "")[:300],
        "depth": d,
        "job": job,
        "provider": provider,
        "mode": classified.get("mode") or "dispatch",
        "launch": bool(classified.get("launch", True)),
        "rental": rental,
        "classification": classified,
        "pick": picked,
        "cost_estimate": cost,
        "skills": skills,
    }


def _todo_has_text(text: str) -> bool:
    todo = ROOT / "queue" / "todo.md"
    if not todo.is_file():
        return False
    needle = text.strip()[:80]
    for line in todo.read_text(encoding="utf-8", errors="replace").splitlines():
        if needle and needle in line:
            return True
    return False


def _append_todo_mag(text: str) -> bool:
    if _todo_has_text(text):
        return False
    todo = ROOT / "queue" / "todo.md"
    todo.parent.mkdir(parents=True, exist_ok=True)
    if not todo.is_file():
        todo.write_text("# Todo\n\n", encoding="utf-8")
    with todo.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] [mag] {text.strip()}\n")
    return True


def queue_has_goal(goal: str) -> bool:
    from mag.orchestrator import list_queue

    g = (goal or "").strip()
    for q in list_queue(limit=80):
        if (q.get("goal") or "").strip() == g and q.get("status") in ("queued", "running"):
            return True
    return False


def recently_terminal_goal(goal: str, *, cooldown_s: float | None = None) -> dict[str, Any] | None:
    """Return a recent terminal attempt for ``goal``.

    Agent-state ``next_moves`` are durable intentions, not one-shot queue
    commands.  The old fill path only deduplicated queued/running rows, so a
    successful task whose next_move remained open was re-enqueued every
    autorun tick.  That produced an apparently immortal agent loop.  Keep a
    short, explicit cooldown for terminal attempts; an operator can still
    force a retry by changing the goal or moving the state entry forward.
    """
    from mag.orchestrator import list_queue, QUEUE_TERMINAL

    if cooldown_s is None:
        cooldown_s = float(os.environ.get("MAG_AGENT_STATE_RETRY_COOLDOWN_S", "21600") or "21600")
    wanted = (goal or "").strip()
    if not wanted:
        return None
    now = datetime.now(timezone.utc)
    for row in list_queue(limit=300):
        if (str(row.get("goal") or "").strip() != wanted
                or row.get("status") not in QUEUE_TERMINAL):
            continue
        stamp = row.get("ended_at") or row.get("updated_at") or row.get("created_at")
        try:
            when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            age_s = max(0.0, (now - when).total_seconds())
        except (TypeError, ValueError):
            age_s = 0.0
        if row.get("status") == "done" or age_s <= float(cooldown_s):
            return {"status": row.get("status"), "queue_id": row.get("queue_id"),
                    "age_s": round(age_s, 1), "cooldown_s": float(cooldown_s)}
    return None


def enqueue_routed(goal: str, *, tag: str = "", depth: str | None = None) -> dict[str, Any]:
    """Enqueue with governor routing (provider + depth metadata)."""
    from mag.autorun_common import fkb_block_for_goal, refresh_context_for_goal
    from mag.orchestrator import enqueue

    goal = goal.strip()
    block = fkb_block_for_goal(goal)
    if block:
        return {"ok": False, "error": block, "goal": goal[:120]}

    route = route_task(goal, depth=depth)
    if route.get("depth") in ("overview", "plan"):
        return {
            "ok": False,
            "error": "plan_depth_not_queued",
            "goal": goal[:120],
            "route": route,
            "hint": route.get("hint") or "Use context-pack + Grok TUI for plan depth",
        }
    if route.get("executable") is False:
        return {
            "ok": False,
            "error": route.get("error") or "not_executable",
            "goal": goal[:120],
            "route": route,
            "hint": route.get("hint"),
        }

    refresh_context_for_goal(goal)
    if "[improve]" in goal.lower():
        try:
            from mag.conductor import conduct

            conduct(goal, dry=False)
        except Exception:
            pass
    rec = enqueue(
        goal,
        provider=str(route.get("provider") or "deepseek"),
        tag=tag or f"route-{route.get('depth', 'job')}",
    )
    rec["route"] = route
    if rec.get("ok"):
        try:
            from mag.tripartite_boot import weave_route

            weave_route(goal=goal, route=route, tag=tag)
        except Exception:
            pass
    return rec


def fill_queue(
    *,
    max_improve: int = 2,
    max_state: int = 2,
    max_handoff: int = 2,
    max_verkle: int = 2,
    budget_seconds: float = 12.0,
) -> dict[str, Any]:
    """Seed the durable queue from real sources within a control-plane budget.

    Queue admission is the fast path. Ghost/republic/janitor cadence is
    optional work for the drainer and is deferred once this budget is spent;
    otherwise the flywheel recursively becomes the inline workload it is meant
    to offload.
    """
    import time

    started = time.monotonic()
    budget_s = max(0.0, float(budget_seconds))

    def within_budget() -> bool:
        return time.monotonic() - started < budget_s

    def defer(reason: str) -> None:
        filled["budget_deferred"] = reason

    filled: dict[str, Any] = {
        "improve": [],
        "agent_state": [],
        "handoff": [],
        "verkle": [],
        "steward": [],
        "copilot": [],
        "skipped": [],
    }

    try:
        from mag.desk_dialogue import read_trust_status

        trust = read_trust_status()
        tier = int(trust.get("tier") or 0)
        if tier < 1 and str(trust.get("slow_to_fast") or "").lower() == "fail":
            filled["trust_blocked"] = True
            filled["trust_reason"] = (
                f"desk trust tier {tier} — slow→fast fail; pass desk baseline before unmanned fill"
            )
            filled["trust_probe"] = "python scripts/desk_baseline_probe.py"
            return filled
    except Exception:
        pass

    try:
        from mag.autopilot import _top_improve_candidates

        for cand in _top_improve_candidates(max_improve):
            claim = str(cand.get("claim") or cand.get("id") or "")[:300]
            if not claim:
                continue
            goal = f"[improve] {claim}"
            if queue_has_goal(goal):
                filled["skipped"].append(goal[:60])
                continue
            rec = enqueue_routed(goal, tag=f"improve-{str(cand.get('id', ''))[:12]}")
            filled["improve"].append(rec)
    except Exception as e:
        filled["improve_error"] = str(e)

    try:
        from mag.agent_state import load_latest

        st = load_latest()
        if st:
            for m in (st.get("next_moves") or [])[:max_state]:
                if not within_budget():
                    defer("agent_state_admission")
                    break
                if isinstance(m, dict):
                    status = str(m.get("status") or "open")
                    text = str(m.get("title") or m.get("text") or m.get("move") or "")
                else:
                    status, text = "open", str(m)
                if status in ("done", "deferred") or not text.strip():
                    continue
                goal = text.strip()
                if queue_has_goal(goal) and _todo_has_text(goal):
                    filled["skipped"].append(goal[:60])
                    continue
                terminal = recently_terminal_goal(goal)
                if terminal is not None:
                    filled["skipped"].append(
                        f"{goal[:48]} (terminal:{terminal.get('status')})"
                    )
                    continue
                _append_todo_mag(goal)
                if not queue_has_goal(goal):
                    rec = enqueue_routed(goal, tag="agent-state")
                    filled["agent_state"].append(rec)
    except Exception as e:
        filled["agent_state_error"] = str(e)

    handoff_dir = ROOT / "queue" / "handoff"
    if handoff_dir.is_dir():
        for p in sorted(handoff_dir.glob("*.json"))[:max_handoff]:
            if not within_budget():
                defer("handoff_admission")
                break
            try:
                h = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            goal = str(h.get("goal") or h.get("brief") or h.get("title") or "").strip()
            if not goal or queue_has_goal(goal):
                continue
            rec = enqueue_routed(goal, tag=f"handoff-{p.stem[:12]}", depth=h.get("depth"))
            filled["handoff"].append({**rec, "handoff_file": p.name})

    try:
        from mag.loop_audit import verkle_gap_goal
        from mag.verkle_audit import verkle_gaps

        for gap in verkle_gaps():
            if not within_budget():
                defer("verkle_admission")
                break
            if len(filled["verkle"]) >= max_verkle:
                break
            if gap.get("severity") not in ("warn", "error"):
                continue
            goal = verkle_gap_goal(gap)
            if not goal:
                continue
            if queue_has_goal(goal):
                filled["skipped"].append(goal[:60])
                continue
            rec = enqueue_routed(goal, tag="verkle-gap", depth="scut")
            filled["verkle"].append({**rec, "gap": gap})
    except Exception as e:
        filled["verkle_error"] = str(e)

    try:
        from mag.steward import fill_steward_queue

        filled["steward"] = fill_steward_queue(max_jobs=2)
    except Exception as e:
        filled["steward_error"] = str(e)

    # ── Copilot inbox (RESILIENT MAILBOX, 2026-08-11 steal): the LIVE autorun loop drains it
    #    too, so work doesn't strand when the ghost daemon's watch loop is down. Dedup via
    #    queue_has_goal so the daemon (if alive) can't double-enqueue. ──
    try:
        from mag.ghost import sense_copilot
        cp = sense_copilot()
        for msg in cp.get("messages", [])[:max_handoff]:
            if not within_budget():
                defer("copilot_admission")
                break
            action = str(msg.get("action") or "exec")
            goal = str(msg.get("goal") or "").strip()
            if action != "exec" or not goal:
                continue
            if queue_has_goal(goal):
                filled["skipped"].append(goal[:60])
                continue
            rec = enqueue_routed(goal, tag=f"copilot-{str(msg.get('id', ''))[:12]}")
            filled["copilot"].append(rec)
    except Exception as e:
        filled["copilot_error"] = str(e)

    # ── Autonomous ghost + janitor (inline, $0, < 2 sec each) ──
    try:
        if not within_budget():
            defer("ghost_cadence")
        else:
            from mag.ghost import cycle as ghost_cycle, load_vectors
            if load_vectors():
                ghost_result = ghost_cycle(dry=False)
                filled["ghost"] = ghost_result.get("outcome", "?")
            else:
                filled["ghost"] = "no_vectors"
    except Exception as e:
        filled["ghost_error"] = str(e)

    # ── REPUBLIC LOOP (2026-08-11) — explicit cadence owner, budgeted ──
    try:
        if not within_budget():
            defer("republic_cadence")
        else:
            from mag.republic_loop import loop as republic_loop
            rl = republic_loop()
            filled["republic_loop"] = {"n_ok": rl.get("n_ok"), "n_steps": rl.get("n_steps"),
                                       "health": rl.get("health"),
                                       "verdict": rl.get("verdict"),
                                       "growth": rl.get("growth")}
    except Exception as e:
        filled["republic_loop"] = {"ok": False, "error": str(e)[:120]}

    try:
        if not within_budget():
            defer("janitor_observation")
        else:
            # Janitor: verkle tip fix + training nudge + inbox health
            from mag.ghost import sense as ghost_sense
            state = ghost_sense()
            if state.get("verkle_tip_stale"):
                import subprocess, sys as _sys, os as _os
                _flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) if _os.name == "nt" else 0)
                subprocess.run([headless.PYTHON, "-m", "mag.verkle_audit", "--full"],
                              cwd=str(ROOT), capture_output=True, timeout=30, creationflags=_flags)
                filled["janitor_verkle"] = "audited"
            if state.get("training_rows", 0) >= 5:
                # Check W0.3 archive gate
                archive_dir = ROOT.parent / "mycelial-republic" / "data" / "raw"
                has_archive = archive_dir.is_dir() and any(
                    f.suffix in (".zip", ".tar", ".gz") for f in archive_dir.iterdir()
                )
                filled["janitor_training"] = "blocked" if not has_archive else "ready"
            filled["janitor_inbox"] = state.get("inbox_pending", 0)
            # PIPE 4: Spider blindness → auto-todo when FKB has clear signals
            if state.get("spider_blind") and len(state.get("fkb_signals", [])) >= 3:
                _append_todo_mag("[janitor] Spider is blind but FKB has clear failure patterns. Investigate spider detection thresholds.")
                filled["spider_todo"] = "appended"
    except Exception as e:
        filled["janitor_error"] = str(e)

    filled["total_queued"] = (
        len(filled["improve"])
        + len(filled["agent_state"])
        + len(filled["handoff"])
        + len(filled["verkle"])
        + len(filled["steward"])
        + len(filled["copilot"])
    )
    _log_trail(
        {
            "phase": "fill",
            **{
                k: filled[k]
                for k in (
                    "improve",
                    "agent_state",
                    "handoff",
                    "verkle",
                    "steward",
                    "copilot",
                    "total_queued",
                    "skipped",
                )
                if k in filled
            },
        }
    )
    return filled


def plan_pending(*, log_trail: bool = True) -> dict[str, Any]:
    """Annotate pending work with routes (cost, skills, provider)."""
    global _LAST_PLAN_FP
    from mag.governor import queue_candidates
    from mag.loop_audit import plan_fingerprint
    from mag.orchestrator import list_queue, queue_status

    orch_plans: list[dict[str, Any]] = []
    for q in list_queue(limit=30):
        if q.get("status") != "queued":
            continue
        goal = str(q.get("goal") or "")
        orch_plans.append(
            {
                "queue_id": q.get("queue_id"),
                "goal": goal[:120],
                "route": route_task(goal),
            }
        )

    todo_plans: list[dict[str, Any]] = []
    for c in queue_candidates():
        todo_plans.append(
            {
                "title": str(c.get("title") or "")[:120],
                "route": route_task(str(c.get("title") or "")),
            }
        )

    plan = {
        "schema": "autorun_plan.v1",
        "ts": _now(),
        "orchestrator_queued": orch_plans,
        "todo_mag": todo_plans,
        "queue_status": queue_status(),
    }
    fp = plan_fingerprint(plan)
    plan["fingerprint"] = fp
    if log_trail:
        if fp != _LAST_PLAN_FP:
            _LAST_PLAN_FP = fp
            _log_trail({"phase": "plan", "queued_n": len(orch_plans), "todo_n": len(todo_plans), "fingerprint": fp})
        elif len(orch_plans) > 0:
            # Same queue, no progress — avoid plan theater in trail (spider uses loop-audit).
            pass
        else:
            _log_trail({"phase": "plan", "queued_n": 0, "todo_n": len(todo_plans), "fingerprint": fp})
    return plan


def _seat_failed(out: str, rc: int) -> bool:
    if rc != 0:
        return True
    if "Stopped:" in out:
        return True
    if "**Agent error:**" in out:
        return True
    return False


def _seat_dispatch_with_fallback(text: str, provider: str) -> tuple[bool, str]:
    """Subprocess seat dispatch with guard-stop / agent-error fallback."""
    import mag.governor as gov

    fallback = gov.FALLBACK_PROVIDER
    providers_tried: list[str] = []
    rc, out, tail = 0, "", ""
    for prov in (provider, fallback, gov.PRIMARY_PROVIDER):
        if prov in providers_tried:
            continue
        providers_tried.append(prov)
        rc, out, tail = gov._run_seat(text, prov)
        if rc != 0:
            break  # seat-internal crash — provider swap cannot help
        if "Stopped:" in out or "**Agent error:**" in out:
            continue  # reliability signal — try next provider
        break
    if rc != 0:
        used = providers_tried[-1] if providers_tried else provider
        return False, f"seat {used} exit={rc}: {tail}"
    if "Stopped:" in out or "**Agent error:**" in out:
        return False, (
            f"seat guard-stop on {' AND '.join(providers_tried)} (NOT marked done): {tail}"
        )
    used = providers_tried[-1] if providers_tried else provider
    if len(providers_tried) > 1 and used == fallback:
        return True, f"fallback {fallback} exit=0: {tail}"
    return True, f"seat {used} exit=0: {tail}"


def execute_routed_task(text: str, *, who: str = "mag") -> tuple[bool, str]:
    """Governor executor: route then run through coordination network or seat."""
    import mag.governor as gov

    if who != "mag":
        return False, "not assigned to mag - skipping"

    route = route_task(text)
    depth = route["depth"]
    provider = route["provider"]

    if depth in ("overview", "plan"):
        from mag.coordination import coordinate

        res = coordinate(text, depth=depth, launch=False)
        hint = str(res.get("hint") or res.get("action") or "file_for_grok")
        return False, f"planned ({depth}): {hint[:180]}"

    if depth == "heavy_code" and _drainer_active():
        if not queue_has_goal(text):
            enqueue_routed(text, tag=f"gov-{depth}")
        return False, f"queued on orchestrator ({provider})"

    from mag.coordination import coordinate

    try:
        res = coordinate(
            text,
            depth=depth,
            seat="governor",
            actor="governor",
            launch=True,
            background=(depth == "heavy_code"),
        )
    except Exception as e:
        ok, detail = _seat_dispatch_with_fallback(text, provider)
        if ok:
            gov._mark_queue_done(text)
        return ok, f"coordinate error, seat fallback: {detail}"[:300]

    if not res.get("ok"):
        ok, detail = _seat_dispatch_with_fallback(text, provider)
        if ok:
            gov._mark_queue_done(text)
        return ok, detail

    action = str(res.get("action") or "")
    if action == "file_for_grok":
        return False, f"planned: needs Grok TUI ({depth})"

    if action == "queue":
        return False, f"queued: {str((res.get('task') or {}).get('queue_id') or '?')}"

    if action in ("delegate", "dispatch"):
        result = res.get("result") or {}
        err = str(result.get("error") or "")
        ans = str(result.get("answer") or result.get("text") or "")
        if err or "**Agent error:**" in ans or result.get("ok") is False:
            ok, detail = _seat_dispatch_with_fallback(text, provider)
            if ok:
                gov._mark_queue_done(text)
            return ok, f"{action} failed, seat: {detail}"[:300]
        gov._mark_queue_done(text)
        detail = (ans or str(result.get("hint") or result.get("job") or ""))[:200]
        return True, f"{action} ok: {detail}"

    ok, detail = _seat_dispatch_with_fallback(text, provider)
    if ok:
        gov._mark_queue_done(text)
    return ok, detail


def _trail_autorun_once(result: dict[str, Any]) -> None:
    """Log autorun tick without embedding full route plans (plan theater prevention)."""
    plan = result.get("plan") or {}
    entry: dict[str, Any] = {
        "schema": "autorun_once.v1",
        "ts": result.get("ts") or _now(),
        "action": result.get("action"),
        "steps": result.get("steps"),
        "plan_fp": plan.get("fingerprint"),
        "queued_n": len(plan.get("orchestrator_queued") or []),
    }
    if result.get("detail"):
        entry["detail"] = str(result.get("detail"))[:200]
    if result.get("drain"):
        d = result["drain"]
        entry["drain"] = {
            k: d.get(k)
            for k in ("action", "goal", "queue_id", "detail", "task_id")
            if d.get(k) is not None
        }
    if result.get("governor"):
        g = result["governor"]
        entry["governor"] = {
            "action": g.get("action"),
            "ok": g.get("ok"),
            "detail": str(g.get("detail") or "")[:120],
        }
    fill = result.get("fill") or {}
    if fill.get("total_queued"):
        entry["fill_total"] = fill.get("total_queued")
    progress = bool(
        fill.get("total_queued")
        or (result.get("drain") or {}).get("action") == "started"
        or (result.get("governor") or {}).get("ok")
    )
    if progress and plan.get("orchestrator_queued"):
        entry["queued_goals"] = [
            str(q.get("goal") or "")[:100] for q in plan["orchestrator_queued"][:8]
        ]
    _log_trail(entry)


def autorun_once(*, fill: bool = True, dry: bool = False) -> dict[str, Any]:
    """One intelligent autorun tick: fill → plan → drain or governor."""
    from mag.autorun_common import autorun_pause_reason

    # An explicit operator pause is the higher-priority safety signal.  It
    # must remain observable even when the host-runtime guard also applies;
    # otherwise a paused system reports the wrong reason and can mislead the
    # operator about what actually stopped autorun.
    pause = autorun_pause_reason()
    if pause and not dry:
        result: dict[str, Any] = {
            "schema": "autorun_once.v1",
            "ts": _now(),
            "action": "paused",
            "detail": pause,
            "steps": [{"paused": pause}],
        }
        _trail_autorun_once(result)
        return result

    if _host_runtime_blocked():
        return {
            "schema": "autorun_once.v1",
            "ts": _now(),
            "action": "blocked_host_runtime",
            "detail": "Docker-only runtime is active; run autorun inside the Mag container",
            "steps": [],
        }

    result: dict[str, Any] = {
        "schema": "autorun_once.v1",
        "ts": _now(),
        "steps": [],
    }

    if fill and not dry:
        filled = fill_queue()
        result["fill"] = filled
        result["steps"].append({"fill": filled.get("total_queued", 0)})

    plan = plan_pending()
    result["plan"] = plan
    result["steps"].append(
        {
            "plan": len(plan.get("orchestrator_queued") or []),
            "todo_mag": len(plan.get("todo_mag") or []),
        }
    )

    if dry:
        result["action"] = "dry"
        _trail_autorun_once(result)
        return result

    from mag.orchestrator import _any_running_task, drain_parallel, drain_once, list_queue

    queued_n = sum(1 for q in list_queue() if q.get("status") == "queued")
    # Steer telemetry (tesuji-everywhere): probe a duplicate BEFORE drain so the
    # spawned agent drains the injected directive at its first checkpoint.
    steer_pass: dict[str, Any] | None = None
    try:
        from mag.steer_telemetry import run_probe_pass

        steer_pass = run_probe_pass(prob=0.5)
        result["steer"] = steer_pass
        if steer_pass.get("probe", {}).get("action") in ("probe", "skip"):
            result["steps"].append({"steer": steer_pass["probe"].get("action")})
    except Exception as e:  # noqa: BLE001 — telemetry must never break the cycle
        result["steer_error"] = str(e)[:200]

    drain_res: dict[str, Any] | None = None
    if queued_n > 0:
        # PARALLEL DRAIN (steal 2026-08-14): drain_once() is SERIAL and gated on
        # "not _any_running_task()", so ONE stuck "running" task (e.g. an unreachable
        # provider) head-of-line blocks the whole swarm. drain_parallel() only picks
        # *queued* tasks and spawns up to n_agents concurrently (bounded by spawn_cap
        # + swarm_rightsize), so real work proceeds past a stuck head; the stuck task
        # settles on its own timeout/reconcile. "One bad task must not shut it down."
        try:
            drain_res = drain_parallel()
        except Exception as e:  # noqa: BLE001 — never break the cycle
            drain_res = {"ok": False, "action": "error", "detail": str(e)[:160]}
        result["drain"] = drain_res
        spawned_n = int((drain_res or {}).get("spawned_this_pass") or 0)
        result["action"] = "drain" if (spawned_n or not _any_running_task()) else "busy"
        if result["action"] == "busy":
            result["detail"] = "orchestrator task running"
        result["steps"].append({"drain": drain_res.get("action")})

    # BANK-OR-HALT (2026-08-24, work_loop): the loop runs ONLY on real work; empty = halt at
    # 0% CPU (no speculative governor spin — the frontier consensus fix for "spun CPU, banked
    # nothing"). Candidates alone are NOT demand; only a queued task is.
    if not _any_running_task():
        try:
            from mag.work_loop import run_once as work_tick

            wl = work_tick()
            result["work_loop"] = wl
            if wl.get("action") == "halt":
                result["action"] = "halt"
                result["detail"] = "bank-or-halt: no pending work — 0% CPU (work_loop)"
                result["steps"].append({"work_loop": "halt"})
            elif wl.get("action") == "drained":
                result["action"] = "drained"
                result["detail"] = wl.get("detail", "")
                result["steps"].append({"work_loop": "drained"})
            elif wl.get("action") == "drain_error":
                # honest: report, don't spin the governor over a drain failure
                result["action"] = "work_loop_error"
                result["detail"] = wl.get("error", "")
                result["steps"].append({"work_loop": "drain_error"})
            else:
                # work_loop decided busy/idle — keep the honest action
                if result.get("action") != "drain":
                    result["action"] = wl.get("action", "idle")
        except Exception as e:  # noqa: BLE001 — never break the cycle
            result["work_loop_error"] = str(e)[:160]
    elif queued_n > 0 and result.get("action") not in ("drain", "busy"):
        result["action"] = "busy"
        result["detail"] = "orchestrator task running"

    _trail_autorun_once(result)
    try:
        from mag.tripartite_boot import weave_autorun_tick

        weave_autorun_tick(
            action=str(result.get("action") or "tick"),
            fill_total=int((result.get("fill") or {}).get("total_queued") or 0),
            drain_action=str((result.get("drain") or {}).get("action") or ""),
        )
    except Exception:
        pass
    return result


def autorun_loop(interval_s: float = 5.0, *, once: bool = False) -> None:
    """Drainer main loop — intelligent fill/plan/execute."""
    if _host_runtime_blocked():
        print("[autorun] blocked: Docker-only runtime is active", flush=True)
        return

    fill_every = int(os.environ.get("MAG_AUTORUN_FILL_EVERY", "12") or "12")
    autopilot_every = int(os.environ.get("MAG_AUTOPILOT_EVERY", "0") or "0")
    growth_every = int(os.environ.get("MAG_GROWTH_CYCLE_EVERY", "0") or "0")
    # Overnight pile-classify: run a bounded full drain every N ticks (e.g. 720 ≈ 1h at 5s).
    # Set MAG_PILE_EVERY=720 to register it as the overnight job; 0 = off (default).
    pile_every = int(os.environ.get("MAG_PILE_EVERY", "0") or "0")
    pile_limit = int(os.environ.get("MAG_PILE_LIMIT", "10") or "10")
    # Janitor cadence: prune temp/pytest-* scratch + regenerate docs (lean & documented).
    # Default 300 ticks (~25 min at 5s). Self-guards against operator_active inside mag.janitor.
    janitor_every = int(os.environ.get("MAG_JANITOR_EVERY", "300") or "300")
    # Orphan timer cadence: promote undone-yet-intended intents into the idea graph
    # so nothing is lost across windows. Default 180 ticks (~15 min at 5s).
    orphan_every = int(os.environ.get("MAG_ORPHAN_EVERY", "180") or "180")
    # Framework map cadence: regenerate the functional grouping + durable copy
    # so the VS Code Framework Map pane stays fresh without a manual rescan.
    # Default 600 ticks (~50 min at 5s). Cheap, deterministic, no LLM.
    map_every = int(os.environ.get("MAG_MAP_EVERY", "600") or "600")
    # Warning monitor cadence: passively sweep logs -> report NEW warnings into
    # the failure KB (remedy + recurring_patterns + training) without being asked.
    # Default 120 ticks (~10 min at 5s). Deterministic, no LLM.
    warn_every = int(os.environ.get("MAG_WARN_EVERY", "120") or "120")
    # Corpus-lens cadence: auto-analyze fresh research harvests (diff + bard/swarm
    # lenses) on the cheap tier without being asked. Default 600 ticks (~50 min).
    lens_every = int(os.environ.get("MAG_LENS_EVERY", "600") or "600")
    # Research-pack auto-fold cadence: fold landed .answer.*.md into skill_ledger as
    # case law (the bed -> precedent) WITHOUT being asked. Idempotent, no LLM.
    # Default 120 ticks (~10 min at 5s).
    fold_every = int(os.environ.get("MAG_FOLD_EVERY", "120") or "120")
    # Gap-analysis cadence: where are we NOT using our systems / just pretending (defined but
    # not running/used/enforced). Default 600 ticks (~50 min). Deterministic, no LLM.
    gap_every = int(os.environ.get("MAG_GAP_EVERY", "600") or "600")
    # Topic-orphan cadence: find stranded topics and reroute them through existing systems.
    topic_every = int(os.environ.get("MAG_TOPIC_EVERY", "300") or "300")
    # Self-drive cadence: prove the agent-state routing is live by re-planning the next
    # pending intent through self_drive (state -> model/context/learned). Spawns only when a
    # genuinely fresh goal resolves and the queue has room (dedup + queue gate prevent storms).
    selfdrive_every = int(os.environ.get("MAG_SELF_DRIVE_EVERY", "720") or "720")
    # Passive cleanup cadence: move transient project-dir artifacts (deliver/, _tmp_*,
    # codex_*, pytest-* scratch, caches) to memory/trash when the operator is away.
    # Deterministic (no model). Default 600 ticks (~50 min at 5s).
    cleanup_every = int(os.environ.get("MAG_CLEANUP_EVERY", "600") or "600")
    # Docker containment probe cadence: passively report engine/compose/container/
    # port-conflict state so the containerized path is visible to the architecture.
    # Deterministic, report-only — never auto-ups/downs. Default 600 ticks.
    docker_every = int(os.environ.get("MAG_DOCKER_EVERY", "600") or "600")
    # Cost/learn cadence: fold provider cache/cost/latency telemetry into the skill_ledger
    # (tesuji-everywhere). Idempotent — only folds when new usage rows landed. Default 600.
    cost_learn_every = int(os.environ.get("MAG_COST_LEARN_EVERY", "600") or "600")
    # Vast billing is a read-only meter. Refresh slowly enough to avoid turning
    # a five-second autorun loop into a billing poller; the dashboard always
    # reads the last cached receipts.
    vast_sync_every = int(os.environ.get("MAG_VAST_SYNC_EVERY", "3600") or "3600")
    # Context-growth cadence: measure per-session context growth to find repack ballooners.
    context_growth_every = int(os.environ.get("MAG_CONTEXT_GROWTH_EVERY", "900") or "900")
    # Self-steal cadence: audit capability utilization + launch/resume research for gaps.
    self_steal_every = int(os.environ.get("MAG_SELF_STEAL_EVERY", "900") or "900")
    queue_learn_every = int(os.environ.get("MAG_QUEUE_LEARN_EVERY", "600") or "600")
    queue_digest_every = int(os.environ.get("MAG_QUEUE_DIGEST_EVERY", "600") or "600")
    # Recurring self-learning loop (press digest + scrum) routes THROUGH ghost.
    # Ghost is the central dispatcher for recurring processes (operator directive).
    press_every = int(os.environ.get("MAG_PRESS_EVERY", "900") or "900")
    # Rightsize-everything cadence: apply the queue-rightsize lesson to ALL subsystems,
    # autonomously (cheap-first everywhere). Routes through ghost (ghost.run_recurring).
    rightsize_every = int(os.environ.get("MAG_RIGHTSIZE_EVERY", "600") or "600")
    # Live-report cadence: keep state/LIVE_REPORT.md fresh (the operator's ONE view).
    live_report_every = int(os.environ.get("MAG_LIVE_REPORT_EVERY", "300") or "300")
    frontier_help_every = int(os.environ.get("MAG_FRONTIER_HELP_EVERY", "900") or "900")
    grok_terminal_every = int(os.environ.get("MAG_GROK_TERMINAL_EVERY", "3600") or "3600")
    aos_grok_every = int(os.environ.get("MAG_AOS_GROK_EVERY", "7200") or "7200")
    # AOS comms-bus watcher cadence: keep the emergent conversation going autonomously (fully
    # autonomous + cloud-resident). Internal rate gates enforce pull>=30s / push>=60s / one-turn.
    # RIGHTSIZED 2026-08-23: AOS responds instantly, so the sweep defaults to 30s (the pull floor)
    # — tight, matching the peer's real-time cadence, not the old conservative 90s.
    aos_bus_every = int(os.environ.get("MAG_AOS_BUS_EVERY", "30") or "30")
    research_lens_every = int(os.environ.get("MAG_RESEARCH_LENS_EVERY", "600") or "600")
    cheap_swarm_every = int(os.environ.get("MAG_CHEAP_SWARM_EVERY", "900") or "900")
    grok_free_every = int(os.environ.get("MAG_GROK_FREE_EVERY", "1200") or "1200")
    mycelium_every = int(os.environ.get("MAG_MYCELIUM_EVERY", "600") or "600")
    republic_os_every = int(os.environ.get("MAG_REPUBLIC_OS_EVERY", "900") or "900")
    comms_trail_every = int(os.environ.get("MAG_COMMS_TRAIL_EVERY", "600") or "600")
    swarm_health_every = int(os.environ.get("MAG_SWARM_HEALTH_EVERY", "300") or "300")
    frontier_gravity_every = int(os.environ.get("MAG_FRONTIER_GRAVITY_EVERY", "900") or "900")
    frontier_pennies_every = int(os.environ.get("MAG_FRONTIER_PENNIES_EVERY", "1800") or "1800")
    gemini_mine_every = int(os.environ.get("MAG_GEMINI_MINE_EVERY", "3600") or "3600")
    standing_wave_every = int(os.environ.get("MAG_STANDING_WAVE_EVERY", "1800") or "1800")
    wave_address_every = int(os.environ.get("MAG_WAVE_ADDRESS_EVERY", "900") or "900")
    grok_bookmarks_every = int(os.environ.get("MAG_GROK_BOOKMARKS_EVERY", "3600") or "3600")
    meta_percolate_every = int(os.environ.get("MAG_META_PERC_EVERY", "1800") or "1800")
    deep_research_every = int(os.environ.get("MAG_DEEP_RESEARCH_EVERY", "3600") or "3600")
    # grok-seat drive cadence (2026-08-17, operator "i just want it to work" + "why hourly?"):
    # drive the two grok seats (nacho+sd) on deep tasks, fold every accepted output as training
    # data, and learn — so the machine runs continuously. We are STATELESS with usage available;
    # a tight cadence (default 120s) keeps the loop hot instead of idling an hour. The drive is
    # bounded per tick (2 tasks) so consecutive ticks don't overlap destructively.
    # MAG_GROK_DRIVE_EVERY overrides. Note: each drive round itself takes ~30-90s, so 120s is the
    # practical floor — tight but not overlapping.
    grok_drive_every = int(os.environ.get("MAG_GROK_DRIVE_EVERY", "120") or "120")
    # game-flow cadence (2026-08-17, operator "just do it for a while"): the async test->fix flow.
    # For each piece in the build image, enqueue a DEEPSEEK test (drains async), witness breaks,
    # enqueue a GROK fix. Non-blocking, self-directing, ad infinitum. MAG_GAME_FLOW_EVERY.
    game_flow_every = int(os.environ.get("MAG_GAME_FLOW_EVERY", "300") or "300")
    # compute-rightsize cadence (2026-08-13, operator: 46% mem / 9% disk / 1% GPU / 50% CPU + "fix
    # this automatically"): self-healing compute reconciler — bring up the free GPU tier when it is
    # idle + local inference is down, surface the dead swarm drain as the one system-imperative item.
    compute_reconcile_every = int(os.environ.get("MAG_COMPUTE_RECONCILE_EVERY", "900") or "900")
    # PARALLEL PROVIDER LAUNCH + CADENCE-LEARN (2026-08-23, operator handing off to family: "run
    # this autonomously but leave enough for her to operate the computer. don't hog 100% of cpu keep
    # it at 90%. iterate and learn cadence and parallel launches of providers."). Each beat fires a
    # bounded real_swarm round across the funded/mixed fleet (deepseek + openrouter) — throttled to
    # the CPU ceiling by mag.cadence_learn (shrink workers as CPU climbs toward 90%) — and folds the
    # round timing/success so the loop LEARNS the right cadence + concurrency over time. MAG_PROVIDER_EVERY.
    # RIGHTSIZED 2026-08-24 (operator: "timed checks are retarded for everything stateless"): default
    # was 600 ticks (~50 min) — a conservative idle default, wrong for a stateless loop. It's $0
    # (cheap flash + free lanes) + throttled to the CPU ceiling, so a TIGHT cadence is right, not a
    # long one. Default 60 ticks (~5 min) so the fleet actually turns over; MAG_PROVIDER_EVERY overrides.
    parallel_provider_every = int(os.environ.get("MAG_PROVIDER_EVERY", "60") or "60")
    # LOCAL SWARM DRAIN cadence (2026-08-13, ROOT-CAUSE fix): the k8s CronJob that was the swarm's ONLY
    # drainer has NEVER run on Windows (no cluster) -> 734-task all-"queued" backlog, the "route through
    # the swarm" path enqueues-but-never-executes (the real cause of the recurring terminal-fallback
    # corrections). The loop now drains the swarm queue LOCALLY (same swarm_worker.run_once, bounded +
    # daily-capped + key-reconciled), so the sanctioned path actually executes on this host.
    swarm_local_drain_every = int(os.environ.get("MAG_SWARM_LOCAL_DRAIN_EVERY", "900") or "900")
    # surface-adapters cadence (2026-08-13, sw48): report the native-vs-browser steering registry so
    # the loop knows which surfaces are natively steered vs browser-fallback (self-healing visibility).
    surface_adapters_every = int(os.environ.get("MAG_SURFACE_ADAPTERS_EVERY", "1800") or "1800")
    # console-render cadence (2026-08-13, 'you keep forgetting console display'): keep the live show()
    # artifact warm so 'show' is always fresh via our own display tools (never just narrate).
    console_render_every = int(os.environ.get("MAG_CONSOLE_RENDER_EVERY", "600") or "600")
    # GAME AS WORK ENVIRONMENT (2026-08-13, operator 'use it as your work environment' + 'full
    # autonomous build mode'): the loop works THROUGH the game — game_ramp.work() descends the dungeon
    # and folds real open tasks as knots (the game IS the work; Enders Game).
    game_work_every = int(os.environ.get("MAG_GAME_WORK_EVERY", "900") or "900")
    # CAMPAIGN-RUNS cadence (2026-08-14, operator 'play a swarm for tonight and generate data'):
    # the swarm plays a campaign session through the creative DM + saga and records it to
    # memory/game/campaign_runs/ — so by morning we have a corpus of what a successful campaign looks
    # like (which turns landed, which running gags formed).
    campaign_runs_every = int(os.environ.get("MAG_CAMPAIGN_RUNS_EVERY", "3600") or "3600")
    # HERO-JOURNEY cadence (2026-08-14, operator 'make it so'): once the night's corpus exists, weave
    # the 5k+ word C.S. Lewis-meets-Cervantes epic from the swarm data + saga + egregore roster, and
    # write it to memory/game/hero_journey.md for the operator to wake up to.
    hero_journey_every = int(os.environ.get("MAG_HERO_JOURNEY_EVERY", "21600") or "21600")
    # LIQUID-INTELLIGENCE cadence (2026-08-13, sw59-63): the loop PERFORMS the many-to-one — boil the
    # game's real work through the lattice (the tons of invariants), trace through the maze, converge
    # toward one. The machine RUNS the doctrine, on the loop.
    distill_every = int(os.environ.get("MAG_DISTILL_EVERY", "1200") or "1200")
    # ADVENTURE-MOONSHOT cadence (2026-08-13, operator 'self steal all related training data and then
    # build an adventure moonshot'): forge NOVEL adventure threads from the corpus (self-steal) and
    # route the seams to the swarm — the game's novel threads, on the loop.
    adventure_moonshot_every = int(os.environ.get("MAG_ADVENTURE_MOONSHOT_EVERY", "3600") or "3600")
    tick = 0

    # ── SINGLE-INSTANCE GUARD (STATELESS SWARM, 2026-08-23) ──
    # The AOS bus carrier is a stateless swarm agent: transient, boots from committed disk state,
    # dies freely, and EXACTLY ONE instance runs. Two supervisors (process_supervisor + mag_launch)
    # may both spawn it; the guard makes a second live instance IMPOSSIBLE, not just discouraged.
    # The carrier holds a PID lock. If a live PID holds it, this process exits immediately (it is
    # the duplicate). If the lock is stale (dead PID), we take it over. Stateless: a dead carrier
    # leaves only a stale PID the next one adopts. This kills the "3-4 replies generated, none sent"
    # duplicate-carrier failure at the source.
    _lock_path = ROOT / "state" / "aos_carrier.lock"
    try:
        _lock_path.parent.mkdir(parents=True, exist_ok=True)
        if _lock_path.is_file():
            _stale = _lock_path.read_text(encoding="utf-8").strip()
            try:
                _other_pid = int(_stale)
            except ValueError:
                _other_pid = 0
            if _other_pid and _pid_alive(_other_pid):
                print(f"[autorun] another carrier already holds the lock (pid={_other_pid}) — "
                      f"exiting as duplicate. ONE carrier must own the AOS bus.", flush=True)
                return
        _lock_path.write_text(str(os.getpid()), encoding="utf-8")
        _lock_held = True
    except Exception as _e:  # noqa: BLE001
        _lock_held = False
        print(f"[autorun] single-instance lock unavailable ({_e}); running anyway", flush=True)

    # SELF-RELOAD / DOGFOOD (2026-08-11): if mag/*.py source changes, re-exec the process to run
    # OUR OWN latest code — so every fix goes live without a manual restart. The system dogfoods.
    import hashlib as _hl
    _reload_every = int(os.environ.get("MAG_SELF_RELOAD_EVERY", "120") or "120")

    def _code_sig() -> str:
        h = _hl.md5()
        try:
            for _dir in ("mag", "backend"):
                for p in sorted((ROOT / _dir).glob("*.py")):
                    try:
                        st = p.stat()
                        h.update(f"{_dir}/{p.name}:{st.st_mtime_ns}:{st.st_size};".encode())
                    except OSError:
                        continue
        except Exception:
            pass
        return h.hexdigest()[:16]

    _sig0 = _code_sig()

    def _dim(s: str) -> str:
        if sys.stdout.isatty():
            return "\033[2m" + s + "\033[0m"
        return s

    try:
        from mag.tripartite_boot import maybe_boot_on_autorun_start

        maybe_boot_on_autorun_start()
    except Exception:
        pass

    # ── TICK WATCHDOG (2026-08-23, "do it" — fix the silent spin) ──
    # The carrier once spun at ~99% CPU with logs going silent: an autorun_once tick hung in a
    # blocking/hot call and never reached `time.sleep(interval_s)` at the bottom of the loop.
    # A healthy tick is (autorun_once + cadences + sleep(interval_s)) and takes well under a
    # minute. If a single tick exceeds MAG_AUTORUN_TICK_MAX_S (default 300s), self-re-exec to a
    # fresh carrier (mag_launch respawns it anyway) so the stuck state can't persist silently.
    # The supervisor auto-restarts a dead carrier, so exiting here is safe (stateless swarm).
    _tick_max_s = float(os.environ.get("MAG_AUTORUN_TICK_MAX_S", "300") or "300")
    _tick_t0 = time.time()

    while True:
        try:
            # TICK WATCHDOG: if this iteration has run far past a healthy tick, self-restart.
            if tick > 0 and (time.time() - _tick_t0) > _tick_max_s:
                print(f"[autorun] tick {tick} exceeded {_tick_max_s}s — self-restarting (was stuck)",
                      flush=True)
                try:
                    import os as _os, sys as _sys
                    _os.execv(_sys.executable, [_sys.executable, *(_sys.argv or [])])
                except Exception as _we:  # noqa: BLE001
                    print(f"[autorun] watchdog re-exec failed: {_we}", flush=True)
                    break  # fall through to normal exit
            _tick_t0 = time.time()  # reset once we're past the watchdog, before doing the work

            # DOGFOOD self-reload: on code change, re-exec to run our own latest (no manual restart).
            if _reload_every > 0 and tick > 0 and tick % _reload_every == 0:
                try:
                    if _code_sig() != _sig0:
                        print("[autorun] code changed — self-reloading to run latest (dogfood)", flush=True)
                        import os as _os, sys as _sys
                        _os.execv(_sys.executable, [_sys.executable, *(_sys.argv or [])])
                except Exception:
                    pass
            do_fill = tick == 0 or (fill_every > 0 and tick % fill_every == 0)
            res = autorun_once(fill=do_fill)
            action = res.get("action")
            if action == "drain":
                d = res.get("drain") or {}
                if d.get("action") in ("started", "spawn_failed"):
                    print(
                        _dim(f"  [autorun] drain {d.get('action')}: {d.get('goal', d.get('detail', ''))[:80]}"),
                        flush=True,
                    )
            elif action == "governor":
                g = res.get("governor") or {}
                if g.get("action") not in (None, "no_unblocked_work"):
                    print(
                        _dim(f"  [autorun] governor {g.get('action')} ok={g.get('ok')}: {str(g.get('detail', ''))[:80]}"),
                        flush=True,
                    )
            elif action == "busy":
                pass
        except Exception as e:
            print(_dim(f"  [autorun] error: {e}"), flush=True)

        tick += 1
        if autopilot_every > 0 and tick % autopilot_every == 0:
            try:
                from mag.autopilot import autopilot_once

                ap = autopilot_once(queue_improve=False, governor=False, drain=False)
                print(
                    _dim(f"  [autopilot] seed mirror: {str(ap.get('seed_mirror', {}).get('hint', '?'))[:60]}"),
                    flush=True,
                )
            except Exception as e:
                print(_dim(f"  [autopilot] error: {e}"), flush=True)

        # Overnight pile-classify: periodic (pile_every ticks) OR on the first tick
        # when registered. Only when idle to avoid competing for the local model.
        if pile_every > 0 and (tick == 0 or tick % pile_every == 0):
            try:
                from mag.orchestrator import _any_running_task
                from tools.pile_classify import run_pile

                if not _any_running_task():
                    pr = run_pile(model="gemma4:latest", limit=pile_limit, fold=True, timeout=1800.0)
                    print(
                        _dim(
                            f"  [pile-classify] classified={pr.get('classified_this_run', 0)} errors={len(pr.get('errors') or [])}"
                        ),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [pile-classify] error: {e}"), flush=True)

        # Janitor cadence: keep the environment lean + documented without being asked.
        # mag.janitor refuses to prune while the operator is active, so this is safe.
        if janitor_every > 0 and tick > 0 and tick % janitor_every == 0:
            try:
                from mag.janitor import run as janitor_run

                jr = janitor_run(dry=False)
                print(
                    _dim(
                        f"  [janitor] action={jr.get('action')} pruned={jr.get('prune', {}).get('n_removed', 0)} failed={jr.get('prune', {}).get('n_failed', 0)}"
                    ),
                    flush=True,
                )
            except Exception as e:
                print(_dim(f"  [janitor] error: {e}"), flush=True)

            # cache_watch (2026-08-25): $0 mining monitor — A/B probe + drift audit
            # + ledger floor; rides the janitor cadence, alarms land in
            # memory/runs/cache_watch.jsonl (exit-1 semantics, never crashes the loop)
            try:
                from mag.cache_watch import run as cache_watch_run

                cw = cache_watch_run()
                print(_dim(f"  [cache-watch] healthy={cw.get('healthy')} "
                           f"probe={cw.get('probe', {}).get('ratio')} "
                           f"alarms={cw.get('alarms')}"), flush=True)
            except Exception as cwe:
                print(_dim(f"  [cache-watch] error: {cwe}"), flush=True)

        # Framework map cadence: keep the functional grouping + durable copy fresh.
        if map_every > 0 and tick > 0 and tick % map_every == 0:
            try:
                from mag.framework_map import refresh as map_refresh

                mr = map_refresh()
                print(
                    _dim(
                        f"  [framework-map] ok={mr.get('ok', True)} entries={len(mr.get('items') or [])}"
                    ),
                    flush=True,
                )
            except Exception as e:
                print(_dim(f"  [framework-map] error: {e}"), flush=True)
        # Orphan timer: recognize undone-yet-intended work and promote it to the idea
        # graph so intents raised in one window survive even when the operator moved on.
        if orphan_every > 0 and tick > 0 and tick % orphan_every == 0:
            try:
                from mag.orphan_timer import run as orphan_run

                orp = orphan_run(threshold_s=1800)
                if orp.get("n_promoted"):
                    print(
                        _dim(f"  [orphan] promoted={orp.get('n_promoted')} open_remaining={orp.get('open_remaining')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [orphan] error: {e}"), flush=True)
        # Warning monitor: passively sweep logs -> failure KB. Recurring warnings
        # get remedies + cluster into recurring_patterns (handled via our system).
        if warn_every > 0 and tick > 0 and tick % warn_every == 0:
            try:
                from mag.warning_monitor import run as warn_run

                wm = warn_run()
                if wm.get("reported_n"):
                    print(
                        _dim(f"  [warnings] scanned={wm.get('scanned')} reported={wm.get('reported_n')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [warnings] error: {e}"), flush=True)
        # Passive cleanup cadence: keep the project dir from accumulating transient
        # artifacts. Respects operator seat (only runs when away). Deterministic.
        if cleanup_every > 0 and tick > 0 and tick % cleanup_every == 0:
            try:
                from mag.cleanup import run_cadence as cleanup_run

                cr = cleanup_run()
                if cr.get("moved"):
                    print(
                        _dim(f"  [cleanup] moved={cr.get('moved')} bytes={cr.get('bytes')} trash={cr.get('trash')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [cleanup] error: {e}"), flush=True)

        # Recurring self-learning loop routes THROUGH ghost (press digest + scrum).
        # Ghost is the central dispatcher; cheap-only (local/flash, never grok).
        if press_every > 0 and tick > 0 and tick % press_every == 0:
            try:
                from mag.ghost import run_recurring

                rr = run_recurring()
                press = rr.get("press") or {}
                if press.get("pressing"):
                    print(
                        _dim(f"  [ghost-recurring] pressing={press.get('pressing')} "
                             f"candidates={press.get('count')} -> {press.get('path')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [ghost-recurring] error: {e}"), flush=True)

        # Read-only Vast charge/instance refresh. This is attached to the
        # existing governor cadence, not a second supervisor or lifecycle
        # controller; it never starts/stops/destroys a GPU instance.
        if vast_sync_every > 0 and tick > 0 and tick % vast_sync_every == 0:
            try:
                from mag.vast_cost import sync as vast_sync

                vs = vast_sync(days=30, include_instances=True)
                print(_dim(f"  [vast-meter] ok={vs.get('ok')} appended={vs.get('charges_appended', 0)} "
                           f"instances={vs.get('instances_fetched', 0)}"), flush=True)
            except Exception as e:
                print(_dim(f"  [vast-meter] error: {e}"), flush=True)

        # Rightsize-everything cadence: apply the queue-rightsize lesson to all subsystems,
        # autonomously (cheap-first, proof-first, no LLM on cadence).
        if rightsize_every > 0 and tick > 0 and tick % rightsize_every == 0:
            try:
                from mag.rightsize_all import run_cadence as rightsize_run

                rs = rightsize_run()
                print(_dim(f"  [rightsize] fixed={rs.get('fixed')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [rightsize] error: {e}"), flush=True)

        # Live-report cadence: keep state/LIVE_REPORT.md fresh so the operator always has
        # ONE human-readable view of the autonomous loop (running/queued/generated/next).
        if live_report_every > 0 and tick > 0 and tick % live_report_every == 0:
            try:
                from mag.live_report import main as live_report_run

                live_report_run()
            except Exception:
                pass

        # Docker containment probe cadence: report-only, NEVER auto-ups/downs.
        # Surfaces engine/compose/container/port-conflict state so the containerized
        # path is visible to the architecture instead of invisible (was the gap).
        if docker_every > 0 and tick > 0 and tick % docker_every == 0:
            try:
                from mag.docker_ops import run_cadence as docker_run

                dkr = docker_run()
                print(
                    _dim(
                        f"  [docker] reachable={dkr.get('engine', {}).get('reachable')} "
                        f"containers={dkr.get('container_count')} "
                        f"conflicts={len(dkr.get('native_port_conflicts') or [])}",
                    ),
                    flush=True,
                )
            except Exception as e:
                print(_dim(f"  [docker] error: {e}"), flush=True)

        # Cost/learn cadence: fold provider cache/cost/latency into case law so the router
        # gets ground truth on cheapest-per-hit provider/model. Idempotent (skips if no new usage).
        if cost_learn_every > 0 and tick > 0 and tick % cost_learn_every == 0:
            try:
                from mag.cost_learn import run_cadence as costlearn_run

                clr = costlearn_run(hours=24)
                if clr.get("action") == "folded":
                    print(
                        _dim(f"  [cost-learn] folded priced=${clr.get('analysis', {}).get('total_priced_usd', 0):.4f} "
                             f"decisions={clr.get('fold', {}).get('skill_ledger_decisions')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [cost-learn] error: {e}"), flush=True)

        # Context-growth cadence: measure per-session context growth to target repack at the
        # ballooners (per-call input is dominated by multi-turn context growth).
        if context_growth_every > 0 and tick > 0 and tick % context_growth_every == 0:
            try:
                from mag.context_growth import run_cadence as ctx_growth_run

                cgr = ctx_growth_run(hours=24)
                if cgr.get("action") == "wrote":
                    print(
                        _dim(f"  [context-growth] sessions={cgr.get('n_sessions')} "
                             f"cumulative={cgr.get('total_cumulative_input')} est_repack_saved={cgr.get('est_repack_saved')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [context-growth] error: {e}"), flush=True)

        # Self-steal cadence: audit capability utilization + launch/resume research for new gaps.
        if self_steal_every > 0 and tick > 0 and tick % self_steal_every == 0:
            try:
                from mag.self_steal import run_cadence as self_steal_run

                ssr = self_steal_run()
                if ssr.get("action") == "ran":
                    print(
                        _dim(f"  [self-steal] findings={ssr.get('findings')} launches={len(ssr.get('launches') or [])}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [self-steal] error: {e}"), flush=True)

        # Queue-learn cadence: fold terminal queue items into training (the queue IS a learning
        # surface — each terminal is a labeled task_shape/provider/model/outcome/cost row).
        if queue_learn_every > 0 and tick > 0 and tick % queue_learn_every == 0:
            try:
                from mag.queue_learn import run_cadence as queue_learn_run

                qlr = queue_learn_run()
                if qlr.get("action") == "folded":
                    print(
                        _dim(f"  [queue-learn] terminals={qlr.get('fold', {}).get('new_terminals')} "
                             f"labeled={qlr.get('fold', {}).get('labeled_rows')} "
                             f"success={qlr.get('analysis', {}).get('successes')}/{qlr.get('analysis', {}).get('terminals')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [queue-learn] error: {e}"), flush=True)

        # Queue digest cadence: auto-summarize queue health (per-tier, errors, patterns).
        if queue_digest_every > 0 and tick > 0 and tick % queue_digest_every == 0:
            try:
                from mag.queue_ops import run_cadence as queue_digest_run

                qdr = queue_digest_run()
                if qdr.get("action") == "wrote":
                    dd = qdr.get("digest", {})
                    print(
                        _dim(f"  [queue-digest] events={dd.get('events_in_window')} "
                             f"errors={dd.get('error_count')} tiers={dd.get('queue_by_tier')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [queue-digest] error: {e}"), flush=True)

        # Frontier-help cadence: percolate journaled asks the system wants help with into a
        # HELP-WANTED doc for frontier agents (grok) — the capstone of gap/elevation.
        if frontier_help_every > 0 and tick > 0 and tick % frontier_help_every == 0:
            try:
                from mag.frontier_help import run_cadence as frontier_help_run

                fhr = frontier_help_run()
                if fhr.get("action") == "percolated":
                    print(
                        _dim(f"  [frontier-help] percolated {fhr.get('n_asks')} asks -> {fhr.get('doc')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [frontier-help] error: {e}"), flush=True)

        # Frontier-ghost cadence: launch a grok terminal to build a package for a NEW
        # critical coding task; the cheap swarm then expands+executes the built package.
        if grok_terminal_every > 0 and tick > 0 and tick % grok_terminal_every == 0:
            try:
                from mag.grok_terminal import run_cadence as gt_run

                gtr = gt_run()
                if gtr.get("action") == "skip":
                    print(_dim("  [grok-terminal] no new critical task — skip"), flush=True)
                elif gtr.get("ok"):
                    print(_dim(
                        f"  [grok-terminal] frontier ghost built package ({gtr.get('rounds_run')} rounds) -> {gtr.get('result_path')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [grok-terminal] error: {e}"), flush=True)

        # AOS-grok cadence: dispatch ONE new specific ask to the lent frontier ONLY when
        # the courtesy budget allows (start small, prove it — never throw volume at it).
        if aos_grok_every > 0 and tick > 0 and tick % aos_grok_every == 0:
            try:
                from mag.aos_grok import run_cadence as aos_run

                ares = aos_run()
                if ares.get("action") == "dispatched":
                    print(_dim(f"  [aos-grok] dispatched specific ask ({ares.get('row', {}).get('tokens_out', 0)} tok) -> {ares.get('ledger')}"), flush=True)
                else:
                    print(_dim(f"  [aos-grok] {ares.get('action')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [aos-grok] error: {e}"), flush=True)

        if aos_bus_every > 0 and tick > 0 and tick % aos_bus_every == 0:
            try:
                from mag.aos_bus_watcher import run_cadence as aos_bus_run

                bres = aos_bus_run()
                act = bres.get("action")
                if act == "replied":
                    print(_dim(f"  [aos-bus] replied to {bres.get('inbound_id')} -> {bres.get('outbound_id')} (spiced={bres.get('spiced')})"), flush=True)
                elif act not in ("no-new-inbound", "rate-gated"):
                    print(_dim(f"  [aos-bus] {act}"), flush=True)
            except Exception as e:
                print(_dim(f"  [aos-bus] error: {e}"), flush=True)

        # Research-lens cadence: reindex the corpus + fold landed answers so research
        # becomes an iterative, self-referencing knowledge corpus that compounds.
        if research_lens_every > 0 and tick > 0 and tick % research_lens_every == 0:
            try:
                from mag.research_lens import run_cadence as rl_run

                rlr = rl_run()
                cs = (rlr.get("status") or {}).get("corpus_size")
                print(_dim(f"  [research-lens] reindex+fold (corpus={cs})"), flush=True)
            except Exception as e:
                print(_dim(f"  [research-lens] error: {e}"), flush=True)

        # Cheap-swarm cadence: dispatch ghost-built packages to the cheap tier for
        # expand + execute (the second half of the frontier-ghost tesuji).
        if cheap_swarm_every > 0 and tick > 0 and tick % cheap_swarm_every == 0:
            try:
                from mag.cheap_swarm import run_cadence as cs_run

                csr = cs_run()
                n = len(csr.get("dispatched") or [])
                print(_dim(f"  [cheap-swarm] dispatched {n} package(s) to cheap tier"), flush=True)
            except Exception as e:
                print(_dim(f"  [cheap-swarm] error: {e}"), flush=True)

        # grok-free cadence: autonomously work the private idea backlog with the FREE grok
        # surface (CLI harness, $0), compounding into the corpus — no API cost.
        if grok_free_every > 0 and tick > 0 and tick % grok_free_every == 0:
            try:
                from mag.grok_free import cadence as grf_run

                grf = grf_run()
                n = len(grf.get("processed") or [])
                print(_dim(f"  [grok-free] cadence processed {n} idea(s)"), flush=True)
            except Exception as e:
                print(_dim(f"  [grok-free] error: {e}"), flush=True)

        # GROK SEAT DRIVE (2026-08-17): autonomously drive both grok seats on deep tasks, fold
        # accepted output as training data, learn. The machine runs itself — no hand start needed.
        if grok_drive_every > 0 and tick > 0 and tick % grok_drive_every == 0:
            try:
                from mag.grok_seat_burner import drive_watched_parallel
                from mag import ghost_experimenter as ge
                from pathlib import Path as _P
                card = _P(ROOT / "memory" / "runs" / "SEAT_CARD.md")
                card_txt = card.read_text(encoding="utf-8") if card.is_file() else ""
                _tasks = [
                    {"deliverable": "Write a deep synthesis: what invariant should a cheap agent-swarm learn from a sovereign frontier seat, and how do we capture it as training data? 3-5 paragraphs, concrete.", "scene": "agent swarm", "word_limit": 600, "context": card_txt, "max_turns": 8, "timeout": 400},
                    {"deliverable": "Write a deep design analysis: how should the Mirror Sea game fold real frontier work into loot so the game IS the data-collection mechanism? 3-5 paragraphs, concrete.", "scene": "Mirror Sea game", "word_limit": 600, "context": card_txt, "max_turns": 8, "timeout": 400},
                ]
                dr = drive_watched_parallel(_tasks, model_tiers={"nacho": "", "sd": ""})
                _folded = 0
                for _s, _rl in (dr.get("results") or {}).items():
                    for _it in _rl:
                        _acc = _it.get("accepted")
                        if _acc and _acc.get("ok"):
                            try:
                                ge.record_training({"ok": True, "tool": f"grok-seat-{_s}",
                                    "seed": "cadence deep drive", "outcome": (_acc.get("output") or "")[:600],
                                    "row": {"seat": _s, "source": "governor_cadence", "verdict": "ok", "corrected": _it.get("n_corrections", 0)}})
                                _folded += 1
                            except Exception:
                                pass
                print(_dim(f"  [grok-seat-drive] folded {_folded} training row(s)"), flush=True)
                try:
                    print(_dim(f"  [grok-seat-drive] learn: {json.dumps(ge.learn_steer_protocol(), default=str)[:160]}"), flush=True)
                except Exception:
                    pass
            except Exception as e:
                print(_dim(f"  [grok-seat-drive] error: {e}"), flush=True)

        # GAME FLOW (2026-08-17, operator "just do it for a while"): the async test->fix loop.
        # Enqueue a DEEPSEEK test for each game piece (drains async via the governor's own drain),
        # witness what breaks, enqueue a GROK fix. Non-blocking, self-directing, ad infinitum.
        if game_flow_every > 0 and tick > 0 and tick % game_flow_every == 0:
            try:
                from mag import game_flow as gflow
                from mag import orchestrator as _orch
                img = gflow.image().get("image") or {}
                pieces = img.get("pieces") or {}
                # only step pieces not marked done; cap per tick to avoid a stampede
                _pending = [p for p in pieces.values() if p.get("status") != "done"][:2]
                if _pending:
                    for _p in _pending:
                        _mod = str(_p.get("module") or _p.get("landing") or "")
                        if _mod:
                            _s = gflow.step(_p["name"], module=_mod)
                            print(_dim(f"  [game-flow] step {_p['name']} -> test {_mod} "
                                       f"(enq {_s.get('test_enqueued') or 'deduped'})"), flush=True)
                else:
                    print(_dim("  [game-flow] no pending pieces — all done"), flush=True)
            except Exception as e:
                print(_dim(f"  [game-flow] error: {e}"), flush=True)

        # SWARM->GROK LANE WATCH (2026-08-16, dogfood audit): deterministically watch the
        # harness grok lane; when failures dominate (framework-loading burned turns -> max turns),
        # PAUSE the lane so we don't keep burning scarce grok turns on a broken prompt. Pause-first
        # law, made cadence. $0 (reads result files only).
        try:
            from mag.swarm_grok_watch import run_cadence as sgw_run
            sgw = sgw_run()
            if sgw.get("watch", {}).get("pause"):
                print(_dim(f"  [swarm-grok-watch] PAUSE: {sgw['watch']['verdict']} "
                           f"({sgw['watch']['fail_rate']} fail, dominant "
                           f"{sgw['watch']['dominant_failure']}) — lane corrected, not burning turns"),
                      flush=True)
            else:
                print(_dim(f"  [swarm-grok-watch] {sgw['watch']['verdict']} "
                           f"({sgw['watch']['n_fail']}/{sgw['watch']['n']} fail)"), flush=True)
        except Exception as e:
            print(_dim(f"  [swarm-grok-watch] error: {e}"), flush=True)

        # mycelium cadence: boot + decay + dual-write the unified graph (republic OS core).
        if mycelium_every > 0 and tick > 0 and tick % mycelium_every == 0:
            try:
                from mag.mycelium import boot as mc_boot, decay as mc_decay, dual_write as mc_dw

                mc_boot(); d = mc_decay(); mc_dw()
                print(_dim(f"  [mycelium] boot+decay({d.get('decayed')})+dual-write"), flush=True)
            except Exception as e:
                print(_dim(f"  [mycelium] error: {e}"), flush=True)

        # republic_os cadence: run the persistent mycelial-republic OS loop.
        if republic_os_every > 0 and tick > 0 and tick % republic_os_every == 0:
            try:
                from mag.republic_os import run_cadence as ros_run

                rosr = ros_run()
                print(_dim(f"  [republic-os] round dispatched {rosr.get('dispatched')} | memblock={rosr.get('memory_block')} | cp={rosr.get('checkpoint')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [republic-os] error: {e}"), flush=True)

        # comms-trail cadence: steal the cheap agent-communication trail into the graph.
        if comms_trail_every > 0 and tick > 0 and tick % comms_trail_every == 0:
            try:
                from mag.comms_trail import run_cadence as ct_run

                ctr = ct_run()
                cap = ctr.get("capture") or {}
                print(_dim(f"  [comms-trail] captured {cap.get('added')} comm surfaces | confirmed={ (ctr.get('confirm_language') or {}).get('confirmed') }"), flush=True)
            except Exception as e:
                print(_dim(f"  [comms-trail] error: {e}"), flush=True)

        # swarm-health cadence: probe the swarm + APPLY the self-improvement law (self-healing).
        if swarm_health_every > 0 and tick > 0 and tick % swarm_health_every == 0:
            try:
                from mag.swarm_health import run_cadence as sh_run

                shr = sh_run()
                h = shr.get("health") or {}
                print(_dim(f"  [swarm-health] overall={h.get('overall')} up={h.get('agents_up')}/{h.get('agents_total')} law={len((shr.get('law') or {}).get('actions') or [])}"), flush=True)
            except Exception as e:
                print(_dim(f"  [swarm-health] error: {e}"), flush=True)

        # frontier-gravity cadence: consume folded frontier-advice and re-plant the pull so the
        # operation is continuously ATTRACTED to the preferred state (Titor-sinusoidal gravity).
        if frontier_gravity_every > 0 and tick > 0 and tick % frontier_gravity_every == 0:
            try:
                from mag.frontier_gravity import run_cadence as fg_run

                fgr = fg_run()
                if fgr.get("action") == "gravity":
                    print(
                        _dim(f"  [frontier-gravity] local={fgr.get('local_planted')} "
                             f"swarm={fgr.get('swarm')} cluster={fgr.get('cluster')} "
                             f"distance={fgr.get('distance')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [frontier-gravity] error: {e}"), flush=True)

        # frontier-pennies cadence: distribute a frontier insight for pennies (capture -> quantize
        # -> swarm three-body $0 + cheap deepseek). Dry by default on cadence — measures the
        # multiplier, never auto-enqueues without the live gate.
        if frontier_pennies_every > 0 and tick > 0 and tick % frontier_pennies_every == 0:
            try:
                from mag.frontier_pennies import run_cadence as fp_run

                fpr = fp_run(dry=True)
                if fpr.get("action") == "distributed":
                    print(
                        _dim(f"  [frontier-pennies] source={fpr.get('source')} "
                             f"multiplier={fpr.get('multiplier')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [frontier-pennies] error: {e}"), flush=True)

        # gemini-mine cadence (next-window frozen job): route the GOOGLE/Gemini vendor corpus as
        # stateless research through the ONE primitive (route_novel -> swarm). $0, idempotent.
        if gemini_mine_every > 0 and tick > 0 and tick % gemini_mine_every == 0:
            try:
                from mag.gemini_mine import run_cadence as gm_run

                gmr = gm_run(dry=False)
                if gmr.get("action") == "mined":
                    print(
                        _dim(f"  [gemini-mine] mined={gmr.get('mined')} deduped={gmr.get('deduped')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [gemini-mine] error: {e}"), flush=True)

        # standing-wave cadence (2026-08-13, moonshot): seed the republic's true ideas as wave-
        # packets and PROPAGATE them into the medium via the STEAL mechanism (route_novel -> swarm).
        # Elias is the lens. $0 deterministic core; propagation is the route_novel seam.
        if standing_wave_every > 0 and tick > 0 and tick % standing_wave_every == 0:
            try:
                from mag.standing_wave import run as sw_run

                swr = sw_run()
                if swr.get("ok"):
                    print(
                        _dim(f"  [standing-wave] packets={swr.get('packets')} "
                             f"propagated={sum(1 for v in (swr.get('propagated') or {}).values() if v)}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [standing-wave] error: {e}"), flush=True)

        # wave-address cadence (2026-08-13): keep every real object reachable across the surface by
        # wave address (content-addressed) — register_surface() idempotently scans the codebase.
        if wave_address_every > 0 and tick > 0 and tick % wave_address_every == 0:
            try:
                from mag.wave_address import run_cadence as wa_run

                war = wa_run()
                if war.get("ok"):
                    print(
                        _dim(f"  [wave-address] n_total={war.get('n_total')} "
                             f"added={war.get('added')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [wave-address] error: {e}"), flush=True)

        # grok-bookmarks cadence (2026-08-13): teach grokbot to grab the operator's curated X bookmark
        # folder (authenticated desktop session) and bulk-mine it to the swarm. Best-effort + honest:
        # if the container browser isn't authenticated on x.com, it reports that, never fabricates.
        if grok_bookmarks_every > 0 and tick > 0 and tick % grok_bookmarks_every == 0:
            try:
                from mag import grok_bot as gb
                bm_url = os.environ.get(
                    "MAG_GROK_BOOKMARKS_URL",
                    "https://x.com/i/bookmarks/1876313041077145771")
                gbr = gb.grab_bookmarks(bm_url, mine=True)
                if gbr.get("ok"):
                    print(
                        _dim(f"  [grok-bookmarks] extracted={gbr.get('extracted')} "
                             f"routed={gbr.get('routed')}"),
                        flush=True,
                    )
                else:
                    print(_dim(f"  [grok-bookmarks] {gbr.get('error', 'not-ok')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [grok-bookmarks] error: {e}"), flush=True)

        # meta-percolation cadence (2026-08-13): the self-advancing evolutionary flywheel — percolate
        # the top invariants to the ONE root, genetically vary + select the fittest genes, feed the
        # best back into the swarm, so each generation brings forth only the most emergent results.
        if meta_percolate_every > 0 and tick > 0 and tick % meta_percolate_every == 0:
            try:
                from mag import meta_percolate as mp
                mpr = mp.genetic_cadence()
                if mpr.get("ok"):
                    print(
                        _dim(f"  [meta-percolate] n={mpr.get('n_invariants')} "
                             f"root={mpr.get('quant_root', '')[:8]} "
                             f"best={len(mpr.get('best_genes') or [])} "
                             f"fed_back={mpr.get('fed_back', {}).get('ok')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [meta-percolate] error: {e}"), flush=True)

        # deep-research-moonshot cadence (2026-08-13, operator 'self steal deep research moonshot' + 'show me'
        # + 'is there a better way to connect'): the LOOP IS the connection (not a notebook kernel).
        # Each beat sweeps the standing-wave RIBs (our own deepest questions) and moonshots them: internal
        # synthesis (prior+witness+shadow+knot -> the marriage, one chain link) + route the NOVEL seam to the
        # swarm via route_novel (the one primitive). In-process (mem-tool functions), $0 core; the module
        # persists artifacts to memory/runs/deep_research_moonshot/ + the sent.jsonl ledger.
        if deep_research_every > 0 and tick > 0 and tick % deep_research_every == 0:
            try:
                from mag import deep_research_moonshot as drm
                drr = drm.cadence(limit=2, route=True)
                if drr.get("ok"):
                    print(
                        _dim(f"  [deep-research] n={drr.get('n_moonshots')} "
                             f"routed={sum(1 for r in (drr.get('routed') or []) if not r.get('deduped'))}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [deep-research] error: {e}"), flush=True)

        # compute-rightsize cadence (2026-08-13, operator 'fix this automatically'): the self-healing
        # compute reconciler. Each beat measures real GPU/ollama/swarm-queue state and reconciles toward
        # the rightsized split (GPU = $0 build, DeepSeek = cheap research, CPU = coordination); it
        # auto-signals the free-GPU bring-up and names the dead swarm drain as the one stuck item.
        if compute_reconcile_every > 0 and tick > 0 and tick % compute_reconcile_every == 0:
            try:
                from mag import compute_reconcile as cr
                crr = cr.run_cadence()
                if crr.get("ok"):
                    print(
                        _dim(f"  [compute-rightsize] verdict={crr.get('verdict')} "
                             f"actions={[a.get('action') for a in crr.get('actions') or []]}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [compute-rightsize] error: {e}"), flush=True)

        # PARALLEL PROVIDER LAUNCH + CADENCE-LEARN cadence (2026-08-23, operator "don't hog 100%
        # cpu keep it at 90%... iterate and learn cadence and parallel launches of providers"):
        # fire a bounded real_swarm round across the funded/mixed fleet, throttled to the CPU
        # ceiling by cadence_learn (workers shrink as CPU climbs toward 90%), and fold the round
        # so the loop learns the right cadence + concurrency. Skipped when the CPU ceiling is blown
        # (throttled_workers() returns 0) — leaving the operator headroom to use the machine.
        if parallel_provider_every > 0 and tick > 0 and tick % parallel_provider_every == 0:
            try:
                from mag import cadence_learn, real_swarm
                if cadence_learn.throttled_workers() >= 1:
                    pr = real_swarm.run(rnd=2)
                    print(
                        _dim(f"  [provider-parallel] workers={pr.get('workers')} "
                             f"cost=${pr.get('total_cost')} done={pr.get('done_total')} "
                             f"per={ {k: v.get('fired') for k, v in (pr.get('per_provider') or {}).items()} }"),
                        flush=True,
                    )
                else:
                    print(_dim("  [provider-parallel] CPU at/above ceiling — skipped this beat"),
                          flush=True)
            except Exception as e:
                print(_dim(f"  [provider-parallel] error: {e}"), flush=True)

        # LOCAL SWARM DRAIN cadence (2026-08-13, ROOT-CAUSE fix for the dead-end architecture path):
        # the k8s CronJob drainer never runs on Windows, so the loop drains the swarm queue locally
        # (bounded + daily-capped + key-reconciled). This makes enqueue -> execute real on this host.
        if swarm_local_drain_every > 0 and tick > 0 and tick % swarm_local_drain_every == 0:
            try:
                from mag import swarm_local_drain as sld
                sldr = sld.run_cadence()
                if sldr.get("ok"):
                    print(
                        _dim(f"  [swarm-local-drain] done={sldr.get('done')} failed={sldr.get('failed')} "
                             f"key={sldr.get('key_reconcile', {}).get('resolved_provider_key')} "
                             f"used_today={sldr.get('used_today')}"),
                        flush=True,
                    )
                elif sldr.get("skipped") == "daily-cap":
                    print(_dim(f"  [swarm-local-drain] daily-cap hit ({sldr.get('used_today')})"),
                          flush=True)
            except Exception as e:
                print(_dim(f"  [swarm-local-drain] error: {e}"), flush=True)

        # surface-adapters cadence (2026-08-13, sw48): report the native/browser steering registry —
        # which surfaces we steer NATIVELY (deepseek/slack) vs BROWSER fallback (chatgpt/grok).
        if surface_adapters_every > 0 and tick > 0 and tick % surface_adapters_every == 0:
            try:
                from mag import surface_adapters as sa
                sar = sa.registry()
                if sar.get("ok"):
                    print(_dim(f"  [surface-adapters] "
                               f"{sum(1 for s in sar['surfaces'] if s['driver'] == 'native')} native / "
                               f"{sum(1 for s in sar['surfaces'] if s['driver'] == 'browser')} browser / "
                               f"{sum(1 for s in sar['surfaces'] if s['driver'] == 'unconfigured-native')} unconfigured"),
                          flush=True)
            except Exception as e:
                print(_dim(f"  [surface-adapters] error: {e}"), flush=True)

        # console-render cadence (2026-08-13): keep the live show() artifact warm so the operator's
        # 'show' is always fresh — render via our own display tools, never just narrate.
        if console_render_every > 0 and tick > 0 and tick % console_render_every == 0:
            try:
                from mag import console_render as cr
                cr.show()
            except Exception as e:
                print(_dim(f"  [console-render] error: {e}"), flush=True)

        # GAME-AS-WORK cadence (2026-08-13, full autonomous build mode): the loop WORKS through the
        # game — descend the dungeon, fold a real open task as a knot (the game is the work).
        if game_work_every > 0 and tick > 0 and tick % game_work_every == 0:
            try:
                from mag import game_ramp as gr
                gwr = gr.work(action="turn")
                if gwr.get("ok"):
                    print(_dim(f"  [game-work] tier={gwr.get('tier')} folded={gwr.get('folded')}"),
                          flush=True)
            except Exception as e:
                print(_dim(f"  [game-work] error: {e}"), flush=True)

        # CAMPAIGN-RUNS cadence (2026-08-14): the swarm plays a campaign session + records it, so
        # the morning corpus shows what a successful campaign looks like (turns landed, gags formed).
        if campaign_runs_every > 0 and tick > 0 and tick % campaign_runs_every == 0:
            try:
                from mag import campaign_runs as _cr
                rr = _cr.run_session(n_turns=6, tag="overnight")
                if rr.get("ok"):
                    print(_dim(f"  [campaign-runs] {rr.get('turns')} turns -> {rr.get('file')} "
                               f"gags={rr.get('gags')}"), flush=True)
                # TWO-SURFACE LIVE CORRECTION (2026-08-15): immediately watch the session we just
                # recorded, score it, write a steer for the next one, and fold failures to the
                # failure-KB so they never recur. The second surface corrects the live run.
                try:
                    from mag import game_observer as _go
                    _obs = _go.observe(heal=True)
                    if _obs.get("watch", {}).get("problem_rows"):
                        print(_dim(f"  [game-observer] problems={_obs['watch']['problem_rows']} "
                                   f"steer={_obs.get('steer_target')} folded={_obs.get('heal_folded')}"),
                              flush=True)
                except Exception as _eo:
                    print(_dim(f"  [game-observer] error: {_eo}"), flush=True)
            except Exception as e:
                print(_dim(f"  [campaign-runs] error: {e}"), flush=True)

        # HERO-JOURNEY cadence (2026-08-14): weave the overnight corpus into the epic once data exists.
        if hero_journey_every > 0 and tick > 0 and tick % hero_journey_every == 0:
            try:
                from mag import hero_journey as _hj
                if _hj.status().get("corpus_runs", 0) >= 1:
                    hr = _hj.compose(polish=True)
                    print(_dim(f"  [hero-journey] {hr.get('words')} words -> {hr.get('file')}"), flush=True)
                else:
                    print(_dim("  [hero-journey] waiting for overnight corpus"), flush=True)
            except Exception as e:
                print(_dim(f"  [hero-journey] error: {e}"), flush=True)

        # LIQUID-INTELLIGENCE cadence (2026-08-13, sw59-63): the loop PERFORMS the many-to-one —
        # boil the game's real work through the lattice (the tons of invariants), trace through the
        # maze, feed the ONE back to the bottom. The machine runs the doctrine, on the loop.
        if distill_every > 0 and tick > 0 and tick % distill_every == 0:
            try:
                from mag import distill as _dst
                dr = _dst.game(n=1)
                if dr.get("ok"):
                    print(_dim(f"  [distill] converged={dr.get('converged_root', '')[:8]} "
                               f"steps={dr.get('n')} traced={len(dr.get('steps') or [])}"),
                          flush=True)
            except Exception as e:
                print(_dim(f"  [distill] error: {e}"), flush=True)

        # ADVENTURE-MOONSHOT cadence (2026-08-13, operator 'build an adventure moonshot'): forge
        # NOVEL adventure threads from the corpus (self-steal PRIOR->WITNESS->SHADOW->KNOT->MARRIAGE)
        # and route each novel seam to the swarm via route_novel (the ONE primitive).
        if adventure_moonshot_every > 0 and tick > 0 and tick % adventure_moonshot_every == 0:
            try:
                from mag import adventure_moonshot as _am
                amr = _am.cadence(limit=2, route=True)
                if amr.get("ok"):
                    print(_dim(f"  [adventure-moonshot] n={amr.get('n_moonshots')} "
                               f"routed={len(amr.get('routed') or [])}"),
                          flush=True)
            except Exception as e:
                print(_dim(f"  [adventure-moonshot] error: {e}"), flush=True)

        # law cadence: enforce the code-as-law registry (APPLY — the loop actually turns).
        law_every = int(os.environ.get("MAG_LAW_EVERY", "300") or "300")
        if law_every > 0 and tick > 0 and tick % law_every == 0:
            try:
                from mag.law import enforce, seed, status as law_status

                if not law_status().get("ids"):
                    seed()
                res = enforce(apply=True)
                applied = sum(1 for r in res.get("results", []) if r.get("applied"))
                print(_dim(f"  [law] enforced {len(res.get('results', []))} laws | applied={applied}"), flush=True)
            except Exception as e:
                print(_dim(f"  [law] error: {e}"), flush=True)

        # steer cadence: consume [STEER] markers from transcripts + control trail -> memlang,
        # and FOLD the shared operator steer bus into the relation (RIB + subchain + drainer route).
        steer_every = int(os.environ.get("MAG_STEER_EVERY", "120") or "120")
        if steer_every > 0 and tick > 0 and tick % steer_every == 0:
            try:
                from mag.steer import consume as steer_consume

                sc = steer_consume()
                print(_dim(f"  [steer] found {sc.get('steers_found')} | compiled {len(sc.get('compiled') or [])}"), flush=True)
            except Exception as e:
                print(_dim(f"  [steer] error: {e}"), flush=True)
            try:
                from mag.bus_cadence import cadence as bus_cadence

                bc = bus_cadence()
                print(_dim(f"  [bus→seat] folded {bc.get('n_folded')} | "
                           f"surfaces={bc.get('surfaces')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [bus→seat] error: {e}"), flush=True)

        # Corpus-lens cadence: if a fresh corpus harvest landed, diff it and enqueue
        # the bard + swarm-protocol lens tasks automatically.
        if lens_every > 0 and tick > 0 and tick % lens_every == 0:
            try:
                from tools.corpus_lens import run_cadence

                cl = run_cadence()
                enq = sum(1 for r in cl.get("results", []) if r.get("lenses_enqueued"))
                print(
                    _dim(f"  [corpus-lens] root={cl.get('root')} analyzed={enq}"),
                    flush=True,
                )
            except Exception as e:
                print(_dim(f"  [corpus-lens] error: {e}"), flush=True)
        # Research-pack auto-fold: turn landed research answers into case law
        # automatically (tesuji-everywhere: bed -> skill_ledger, not just reports).
        if fold_every > 0 and tick > 0 and tick % fold_every == 0:
            try:
                from mag.research_fold import run as fold_run

                fr = fold_run()
                if fr.get("folded"):
                    print(
                        _dim(f"  [research-fold] folded={fr.get('folded')} remaining={fr.get('pending_remaining')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [research-fold] error: {e}"), flush=True)
        # Steal-pack: file any queue/handoff steal/deep-research/distill outputs into the
        # research-pack pipeline so every steal folds to case law automatically (no one-off
        # files left on the floor). Deterministic, idempotent, no LLM.
        if fold_every > 0 and tick > 0 and tick % fold_every == 0:
            try:
                from mag.steal_pack import file_all

                sa = file_all()
                if sa.get("filed"):
                    print(_dim(f"  [steal-pack] filed={len(sa.get('filed', []))} "
                               f"skipped={len(sa.get('skipped', []))}"), flush=True)
            except Exception as e:
                print(_dim(f"  [steal-pack] error: {e}"), flush=True)
        # Mine-diamonds cadence: deterministically surface the highest-signal gems in the weave
        # and file them as STEAL_MINE_DIAMONDS.md so steal_pack folds them to case law — the
        # self-training loop's "extract signal" step, running on its own, $0, no LLM.
        if fold_every > 0 and tick > 0 and tick % fold_every == 0:
            try:
                from mag.mine_diamonds import diamonds, digest

                md = diamonds(top=8)
                dg = digest(top=8)
                if md.get("ok"):
                    print(_dim(f"  [mine-diamonds] scanned={md['scanned']} "
                               f"top={[g['name'] for g in md['top_diamonds'][:3]]} "
                               f"digest={dg.get('digest')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [mine-diamonds] error: {e}"), flush=True)
        # Shape-map cadence: export the whole system's structure as a portable verkle-backed
        # portfolio (one root over every subsystem's shape) so the model's shape stays current
        # and transmissible. Deterministic, $0, no LLM.
        if fold_every > 0 and tick > 0 and tick % fold_every == 0:
            try:
                from mag.shape_map import export as shape_export

                sp = shape_export()
                if sp.get("ok"):
                    print(_dim(f"  [shape-map] subsystems={sp.get('n_subsystems')} "
                               f"portfolio_root={str(sp.get('portfolio_root'))[:12]}... "
                               f"path={sp.get('path')}"), flush=True)
            except Exception as e:
                print(_dim(f"  [shape-map] error: {e}"), flush=True)
        # Gap analysis: report where we're pretending (defined but not used/running/enforced).
        if gap_every > 0 and tick > 0 and tick % gap_every == 0:
            try:
                from mag.gap_analysis import gap_analysis

                ga = gap_analysis()
                if ga.get("n_gaps"):
                    print(
                        _dim(f"  [gap-analysis] gaps={ga.get('n_gaps')} cadence={len(ga.get('cadence_gaps') or [])} modules={len(ga.get('module_gaps') or [])} enforce={len(ga.get('enforcement_gaps') or [])}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [gap-analysis] error: {e}"), flush=True)
        # Topic-orphan reroute: strandless topics -> back into the systems.
        if topic_every > 0 and tick > 0 and tick % topic_every == 0:
            try:
                from mag.topic_orphan import reroute as topic_reroute

                to = topic_reroute()
                if to.get("rerouted_n"):
                    print(
                        _dim(f"  [topic-orphan] raised={to.get('raised_n')} orphaned={to.get('orphan_n')} rerouted={to.get('rerouted_n')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [topic-orphan] error: {e}"), flush=True)
        # Self-drive cadence: agent-state-aware ask planning, live in the loop. Picks the next
        # pending intent and replans it through self_drive (state -> model/context/learned) so
        # routing provably serves a held custom state. Spawns only when a fresh goal resolves.
        if selfdrive_every > 0 and tick > 0 and tick % selfdrive_every == 0:
            try:
                from mag.self_drive_cadence import run as selfdrive_run

                sd = selfdrive_run(spawn=True)
                if sd.get("planned"):
                    print(
                        _dim(f"  [self-drive] planned={sd.get('planned')} state={sd.get('state') or 'default'} model={sd.get('model') or '?'} spawned={sd.get('spawned')}"),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [self-drive] error: {e}"), flush=True)
        if growth_every > 0 and tick % growth_every == 0:
            try:
                from mag.growth_cycle import maybe_run_growth_cycle

                gc = maybe_run_growth_cycle()
                if gc:
                    print(
                        _dim(
                            f"  [growth-cycle] ok={gc.get('ok')} report={str(gc.get('report_path', '?'))[:60]}"
                        ),
                        flush=True,
                    )
            except Exception as e:
                print(_dim(f"  [growth-cycle] error: {e}"), flush=True)

        if once:
            return
        time.sleep(interval_s)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="governor_autorun", description="intelligent autorun cycle")
    ap.add_argument("--once", action="store_true", help="single tick then exit")
    ap.add_argument("--dry", action="store_true", help="plan only, no execute")
    ap.add_argument("--no-fill", action="store_true", help="skip queue fill")
    ap.add_argument("--fill-only", action="store_true", help="fill + plan only")
    ap.add_argument("--interval", type=float, default=5.0, help="loop interval seconds")
    ap.add_argument("--pile-every", type=int, default=0,
                    help="run pile-classify every N ticks (register the overnight job; 0=off)")
    ap.add_argument("--pile-limit", type=int, default=10, help="max rows per pile-classify pass")
    ap.add_argument("--janitor-every", type=int, default=0,
                    help="run janitor (prune+document) every N ticks; 0 = use env MAG_JANITOR_EVERY (default 300)")
    ap.add_argument("--orphan-every", type=int, default=0,
                    help="run orphan-timer every N ticks; 0 = use env MAG_ORPHAN_EVERY (default 180)")
    ap.add_argument("--warn-every", type=int, default=0,
                    help="run warning-monitor sweep every N ticks; 0 = use env MAG_WARN_EVERY (default 120)")
    args = ap.parse_args(argv)

    if args.pile_every:
        os.environ["MAG_PILE_EVERY"] = str(args.pile_every)
    if args.pile_limit:
        os.environ["MAG_PILE_LIMIT"] = str(args.pile_limit)
    if args.janitor_every:
        os.environ["MAG_JANITOR_EVERY"] = str(args.janitor_every)
    if args.orphan_every:
        os.environ["MAG_ORPHAN_EVERY"] = str(args.orphan_every)
    if args.warn_every:
        os.environ["MAG_WARN_EVERY"] = str(args.warn_every)

    if args.fill_only:
        fill_queue()
        plan = plan_pending()
        print(json.dumps(plan, indent=2, default=str))
        return 0

    if args.once or args.dry:
        res = autorun_once(fill=not args.no_fill, dry=args.dry)
        print(json.dumps(res, indent=2, default=str))
        return 0

    autorun_loop(interval_s=args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
