"""afk_cadence — ONE ghost-routed AFK loop running the whole self-advance machine.

Automates the refined loop: when the operator is AFK, run the pieces as a single
cadence, all model routing through the rightsizer (cheap-first ladder). Everything
headless, cheap-first, folded.

  run_loop()  — the cadence: rightsize -> seed_chain -> self_advance
                -> capability_steal -> learn_rightsize -> scribe -> fold -> cold_boot.
  run_once()  — one full pass (returns structured result).
  status()    — what the cadence would do.

Wired for the governor/supervisor to call; CLI: python -m mag.afk_cadence run|status
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TRAIL = ROOT / "memory" / "runs" / "afk_cadence_trail.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


AFK_GATE_ERROR: str | None = None


def _operator_afk() -> bool:
    # SPEC (2026-09-25, t52): FAIL CLOSED. The old `except: return True` treated a broken
    # operator_status as "operator AFK" and kept the cadence spending while the operator
    # was invisible. An errored check now presumes the operator is ACTIVE (deny honored,
    # work denied) and names the cause in AFK_GATE_ERROR for callers to surface.
    global AFK_GATE_ERROR
    try:
        from mag.preferences import operator_status
        afk = not bool((operator_status() or {}).get("operator_active"))
        AFK_GATE_ERROR = None
        return afk
    except Exception as _afk_e:
        AFK_GATE_ERROR = "afk gate errored; failing CLOSED (operator presumed active): " + str(_afk_e)[:110]
        return False


def _right_size() -> dict[str, Any]:
    # SPEC (2026-09-25, t52): FAIL CLOSED. The old `except: return {"level": "full",
    # "budget": 4}` handed the cadence FULL BLAST on a broken rightsizer. An errored
    # sizing now denies work (level none -> run_once skips the tick) and names the error.
    try:
        from mag.afk_loop import system_resources, right_size
        rs = right_size(system_resources(), operator_active=not _operator_afk())
        if AFK_GATE_ERROR:
            rs["afk_gate_error"] = AFK_GATE_ERROR
        return rs
    except Exception as _rs_e:
        return {"level": "none", "budget": 0,
                "right_size_error": "rightsizer errored; failing CLOSED (deny honored): " + str(_rs_e)[:110]}


def _safe(label: str, fn: Any) -> dict[str, Any]:
    try:
        r = fn()
        return {"step": label, "ok": True, "result": r}
    except Exception as e:
        return {"step": label, "ok": False, "error": str(e)[:150]}


def run_once() -> dict[str, Any]:
    """One full AFK loop pass. Each step folds to the learning surface."""
    out: dict[str, Any] = {"schema": "afk_cadence.v1", "ts": _now()}
    # SPEC (2026-09-25, t43): this operator pause gate FAILED OPEN. If pause_reason()
    # errored, the bare except fell through and the cadence kept working during an
    # operator pause. Fix: fail CLOSED. An errored pause check honors the pause and
    # skips the tick with the error named. Species note for a14's taxonomy: the
    # loop-death guards make a swallowed death VISIBLE, but a deny-gate must DENY on
    # error; silence here is the opposite failure (paused work proceeding). Filed in
    # watch/inbox/gala_20260925/afterparty/lanes/t43.species.md.
    try:
        from mag.operator_mode import pause_reason
        if (reason := pause_reason()):
            out["action"] = "skip"
            out["reason"] = reason
            return out
    except Exception as _pg:
        out["action"] = "skip"
        out["reason"] = "operator pause gate errored; failing CLOSED (pause honored): " + str(_pg)[:110]
        out["pause_gate_error"] = str(_pg)[:150]
        return out
    rs = _right_size()
    out["right_size"] = rs
    if rs.get("level") == "none":
        out["action"] = "skip"
        out["reason"] = "operator active / machine busy (right-sized to none)"
        return out
    budget = int(rs.get("budget") or 1)

    steps = []
    # MID-STEER HEAL: see errors, mint the mem solution, patch for the future
    # BEFORE running, so past errors never recur while the loop advances.
    steps.append(_safe("error_healer", lambda: _import_run("error_healer", "heal", None)))
    # FRONTIER REACH BY DEFAULT (operator 2026-08-15: "how do we do that by default"): ensure the
    # host-loopback CDP seat (mag.host_browser on 127.0.0.1:9222 — the PROVEN transport that
    # browser_driver connects to by default, bypassing the broken Docker CDP forwarding) is up
    # every cycle, so the operator-safe frontier surfaces (grok/chatgpt/deepseek via browser_driver)
    # are reachable without a manual step and without ever touching the desktop keyboard.
    steps.append(_safe("frontier_reach", lambda: _import_run("host_browser", "ensure", None)))
    # FREE-COMPUTE HUNT (legacy afk_loop) — always: scan free tiers for running/more freebies, $0.
    steps.append(_safe("freebie_scan", lambda: _import_run("afk_loop", "freebie_scan", None)))
    # SEAT HUNT (2026-08-23, self-steal): the swarm of free seats finding MORE free seats — glob
    # ~/.grok* for new authed seats + pull the live OpenRouter free-model list. Composes proven
    # checks (grok_seat_burner auth.json, health urllib probe). $0. Folds to memory/runs/seat_hunt.
    steps.append(_safe("seat_hunt", lambda: _import_run("seat_hunter", "hunt", None)))
    # SEAT HEARTBEAT (2026-08-23): heartbeat EVERY seat/lane (grok nacho+sd, ox per account,
    # deepseek balance, openrouter lanes, ollama) and fold ONE cool/heat profile. Generalizes the
    # ox heartbeat the operator asked for — 'we need it for all of em' — so the flywheel knows
    # where to send work (free now) and what's cooling. Gentle, tiny pings, ~$0.
    steps.append(_safe("seat_heartbeat", lambda: _import_run("seat_availability", "ping", None)))
    # PARALLEL PROVIDER LAUNCH + CADENCE-LEARN (2026-08-23, operator: "run this autonomously but
    # leave enough for her to operate the computer... don't hog 100% cpu keep it at 90%. iterate
    # and learn cadence and parallel launches of providers"): fire a real_swarm round across the
    # funded/mixed fleet (deepseek + openrouter) — throttled to the CPU ceiling by cadence_learn
    # — and fold the round timing/success so the loop LEARNS the right cadence + concurrency.
    steps.append(_safe("parallel_provider_launch", lambda: _import_run("real_swarm", "run", None)))
    steps.append(_safe("cadence_learn", lambda: _import_run("cadence_learn", "status", None)))
    # FREE → SWARM (2026-08-23): the seam that makes "free seats direct k3s to do local work" real.
    # Hand every substantive banked free-seat discovery (OX_RS_*) to the k8s swarm queue, so the
    # cluster worker drains it next CronJob pass (scout proposes, basecamp disposes). $0. Only
    # substantive discoveries are pushed — empty reasoning never lands in the cluster.
    steps.append(_safe("free_to_swarm", lambda: _import_run("free_to_swarm", "push", None)))
    # DOGFOOD SENTINEL (this is why we dogfood): probe the real systems every cycle so failures
    # (cache-miss waste, broken grok dispatch, graph persistence) SURFACE instead of hiding.
    steps.append(_safe("dogfood_audit", lambda: _import_run("dogfood_audit", "audit", None)))
    # SESSION BUS: relay bounded, sanitized cross-session messages during the same AFK cadence.
    # This is deterministic and $0; the bridge writes its own receipt without retaining bodies.
    steps.append(_safe("session_bridge", lambda: _import_run("session_bridge", "relay", None)))
    # ROUTE FEEDBACK: refresh the local lane cascade without model calls or provider spend.
    steps.append(_safe("ask_router", lambda: _route_health()))
    # AUTHORITY HEALTH: one known board-write control smoke; never drains the opaque queue.
    steps.append(_safe("harness_health", lambda: _import_run("harness", "health_check", None)))
    steps.append(_safe("seed_chain", lambda: _import_run("seed_chain", "seed_build", _next_problem())))
    if budget >= 2:
        steps.append(_safe("self_advance", lambda: _import_run("self_advance", "expand", None, force=True)))
    # GHOST AUTO (bounded, cheap): synthesize the tesuji leaf, record sizing, and dispatch a bounded
    # frontier-steered stateless agent (cap=1/day) to mine the untagged shadow corpus.
    steps.append(_safe("ghost_auto", lambda: _import_run("ghost_auto", "run_cadence", None)))
    # AUTO HANDOFF: keep a current handoff persisted every cycle so any new chat picks up cleanly
    # without asking (the operator wants handoffs automatic, not on request).
    steps.append(_safe("auto_handoff", lambda: _import_run("auto_handoff", "run", None)))
    # VS CODE SEAT: auto-prepare a ready-to-paste controlled task spec from the pending backlog,
    # so the next chat (or a fresh executor seat) has an opener ready — no re-explaining.
    steps.append(_safe("vscode_seat", lambda: _import_run("vscode_seat", "cadence_generate", None)))
    if budget >= 3:
        steps.append(_safe("capability_steal", lambda: _import_run("capability_steal", "expand", None, force=True)))
        # THE BUS SWARM (legacy emergent_harvest) — full-time, rightsized: the flock hunts
        # emergent tesuji across free compute + shared invariants. Full blast, not runaway.
        steps.append(_safe("emergent_harvest", lambda: _import_run("emergent_harvest", "tesuji_harvest", None, n_agents=40, steps=120)))
    if budget >= 2:
        steps.append(_safe("learn_rightsize", lambda: _import_run("learn_rightsize", "learn_loop", None)))
    if budget >= 1:
        steps.append(_safe("scribe", lambda: _import_run("scribe", "scribe", None)))
    # GPU AFK inference-training: if operator AFK + GPU free + local models up, run FREE local
    # inference on curated seed prompts -> training rows -> folded. Free compute -> training data.
    steps.append(_safe("gpu_afk_train", lambda: _import_run("gpu_ghost", "afk_train", None)))
    steps.append(_safe("cold_boot", lambda: _import_run("ghost_cold_boot", "boot_and_fold", None)))
    # ---- SELF-RUNNING AUGMENTATION (operator 2026-08-10: 'wire the full autonomous loop') ----
    # DOCTRINE DEDUPE: consolidate structural-template doctrine families (template = invariant,
    # instances = data) so the graph never bloats. $0.
    steps.append(_safe("doctrine_dedupe", lambda: _import_run("template_invariant", "consolidate_all", None)))
    # MEMORY CONSOLIDATE (2026-08-18, the missing half of persistence): fold the shared mem_lands
    # layer — importance + recursive summary + decayed retrieval + active layer — so retrieval
    # stays sharp and long sessions don't bloat. Deterministic $0; the 4B/frontier scorer is a
    # pluggable hook. The republic's memory sleeps here.
    steps.append(_safe("memory_consolidate", lambda: _import_run("memory_consolidate", "run_sleep_step", None)))
    # CORPUS MINE: mine the leaked-prompt corpus for invariants (expand the knowledge corpus). $0.
    steps.append(_safe("corpus_mine", lambda: _import_run("leaked_prompt_mine", "mine", None)))
    # GHOST PLAY: the ghost experiments on the swarms/tools -> training rows + steer-protocol learning.
    steps.append(_safe("ghost_play", lambda: _import_run("ghost_experimenter", "ghost_play", None, iterations=2)))
    # READOUT FOLD: close the reservoir loop — read the liquid, curate + inject the readout back.
    steps.append(_safe("readout_fold", lambda: _import_run("readout_controller", "control_loop", None, iterations=1)))
    # RIB RECONCILE: report how the k8s cluster conforms to the RIB invariants (read-only; no auto-apply).
    steps.append(_safe("rib_reconcile", lambda: _import_run("rib_k8s", "reconcile", None, apply=False)))
    # STEER RESUME: process any pinned tasks from the steer protocol (pop the pin stack).
    steps.append(_safe("steer_resume", lambda: _import_run("steer_router", "resume", None)))
    # ---- HONESTY EVERYWHERE (operator 2026-08-10): the ponytail grounding audit runs every cycle
    # so ungrounded doctrine (incl. mislabeled 'grok/frontier' claims) is CHALLENGED, not trusted.
    steps.append(_safe("ponytail_grounding", lambda: _import_run("ponytail_audit", "run_audit", None)))
    # ---- CONTINUOUS VERIFY GATE (Prow-lite, 2026-08-23, Ben-The-Elder lane): run the bounded
    # test suite every cycle, emit an honest typed verdict (green | red | timeout), surface
    # failures. "Don't trust the report, reproduce the reality" — the bone-doctrine made a gate.
    # Reuses mag.test_runner (bounded/restful/headless). Lean: no baseline ceremony (sacred-cow cut).
    steps.append(_safe("verify_gate", lambda: _import_run("verify_gate", "gate", None)))

    out["steps"] = steps
    out["ok_steps"] = sum(1 for s in steps if s.get("ok"))
    out["total_steps"] = len(steps)
    _trail(out)
    _fold(out)
    return out


def _next_problem() -> str:
    try:
        from mag.scrum import sprint
        item = (sprint() or {}).get("item") or {}
        return str(item.get("title") or "")[:200]
    except Exception:
        return "advance the sovereign agent self-advance loop"


def _route_health() -> Any:
    from mag.ask_router import route
    return route("AFK cadence route health", dry=True)


def _import_run(mod: str, fn: str, arg: Any, **kw: Any) -> Any:
    m = __import__(f"mag.{mod}", fromlist=[fn])
    f = getattr(m, fn)
    if arg is not None:
        return f(arg, **kw)
    return f(**kw)


def _trail(out: dict[str, Any]) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": out.get("ts"), "ok_steps": out.get("ok_steps"),
                            "total_steps": out.get("total_steps"),
                            "right_size": out.get("right_size", {}).get("level")}) + "\n")


def _fold(out: dict[str, Any]) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "autorun_cycle",
            input_data={"right_size": out.get("right_size", {}).get("level")},
            action={"kind": "afk_cadence", "ok_steps": out.get("ok_steps")},
            outcome={"total_steps": out.get("total_steps")},
            pattern_tags=["afk_cadence", "self_advance_loop", "automated"],
            tier_max="T1",
            exportable=False,
        )
    except Exception as _fe:  # noqa: BLE001 - folding must never break the cadence; it must be VISIBLE
        # LOOP-DEATH GUARD (2026-09-25, t78): a silently dead training-event fold voids
        # the cadence's own telemetry while run_once still reports ok_steps. Non-fatal,
        # but visible. (pattern: work_loop.py verkle-anchor guard, t19.)
        print(f"[afk-cadence] FOLD LOOP DEATH GUARD: training_events.emit exited: {_fe}", flush=True)


def status() -> dict[str, Any]:
    st: dict[str, Any] = {"schema": "afk_cadence.status.v1", "ts": _now(),
                          "afk": _operator_afk(), "right_size": _right_size(),
                          "steps": ["rightsize", "freebie_scan", "seed_chain", "self_advance",
                                    "capability_steal", "emergent_harvest", "learn_rightsize", "scribe",
                                    "cold_boot", "verify_gate"]}
    # t52: surface the afk gate error so a fail-closed denial is never silent
    if AFK_GATE_ERROR:
        st["afk_gate_error"] = AFK_GATE_ERROR
    return st


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "run"
    if cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run_once(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
