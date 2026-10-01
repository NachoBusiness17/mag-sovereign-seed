"""afk_orchestrator — run the whole AFK advance stack as ONE ghost-routed cadence.

The operator: "we have so much scaffolding — look at what remains and rightsize it,
and build it via our systems and ghost." The rightsize finding: every AFK capability
exists (capability_steal, self_advance, learn_rightsize, scribe, data_source_watch,
cold_boot) but runs SEPARATELY. This module ties them into ONE pass that runs well:
  run_afk() — when AFK/offline, right-sized:
    1. data_source_watch.watch   — plan+observe high-quality sources (no blind ingest)
    2. capability_steal.expand   — steal-search, test local model, fold verified
    3. self_advance.expand       — socratic reflection + skill-expansion plan
    4. learn_rightsize.loop      — auto-catalog + right-size the learning corpus
    5. scribe.scribe             — the cheap model renders it all as the surface
    6. cold_boot check           — confirm the core is bootable (the material survives)
  Each folds to the learning loop. Right-sized to load (never hogs when busy),
  headless, routed through ghost. run_afk is the "make the scaffold run as one loop."

CLI:  python -m mag.afk_orchestrator run [--force] | status
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


AFK_GATE_ERROR: str | None = None


def _operator_offline() -> bool:
    # SPEC (2026-09-25, t65): FAIL CLOSED per the afk_cadence/t52/t61 convention. The old
    # body had t52's fail-open species ('except Exception: return True'): an errored
    # operator_status read as "operator offline" and the cadence kept spending while the
    # operator was invisible. Every call site treats offline=True as GO (run_afk runs the
    # whole cadence, _right_size grants full budget), so the safe direction on error is
    # the DENY: operator presumed ACTIVE (return False), cause named in AFK_GATE_ERROR.
    global AFK_GATE_ERROR
    try:
        from mag.preferences import operator_status
        offline = not bool((operator_status() or {}).get("operator_active"))
        AFK_GATE_ERROR = None
        return offline
    except Exception as _gate_e:
        AFK_GATE_ERROR = "operator offline gate errored; failing CLOSED (operator presumed active): " + str(_gate_e)[:110]
        return False


RIGHT_SIZE_ERROR: str | None = None


def _right_size() -> str:
    # SPEC (2026-09-25, t75): FAIL CLOSED per the afk_cadence t52 convention. The old
    # body had t52's rightsizer fail-open species ('except Exception: return "full"'):
    # an errored sizing handed run_afk the FULL blast (budget 4). The safe direction is
    # the SMALLEST budget: level "none" (run_afk skips the pass), cause named in
    # RIGHT_SIZE_ERROR for callers to surface.
    global RIGHT_SIZE_ERROR
    try:
        from mag.afk_loop import system_resources, right_size
        level = right_size(system_resources(), operator_active=not _operator_offline())["level"]
        RIGHT_SIZE_ERROR = None
        return level
    except Exception as _rs_e:
        RIGHT_SIZE_ERROR = "rightsizer errored; failing CLOSED (smallest budget, none): " + str(_rs_e)[:110]
        return "none"


def run_afk(*, force: bool = False) -> dict[str, Any]:
    """The one-pass AFK advance cadence (right-sized, ghost-routed)."""
    # SPEC (2026-09-25, t75): this pause gate FAILED OPEN (the t43 species t65 left
    # standing): an errored pause_reason was swallowed by 'except Exception: pass' and
    # the cadence worked through an operator pause. Fix: fail CLOSED per the afk_cadence
    # t43 convention. An errored pause check honors the pause and skips the pass with
    # the error named; silence here is the opposite failure (paused work proceeding).
    try:
        from mag.operator_mode import pause_reason
        if (reason := pause_reason()):
            return {"ok": True, "action": "skip", "reason": reason}
    except Exception as _pg:
        return {"ok": True, "action": "skip",
                "reason": "operator pause gate errored; failing CLOSED (pause honored): " + str(_pg)[:110],
                "pause_gate_error": str(_pg)[:150]}
    if not force and not _operator_offline():
        skip: dict[str, Any] = {"ok": True, "action": "skip", "reason": "operator active (AFK-only)"}
        if AFK_GATE_ERROR:
            skip["afk_gate_error"] = AFK_GATE_ERROR  # t65: a fail-closed denial is never silent
        return skip
    level = _right_size()
    if level == "none":
        skip_rs: dict[str, Any] = {"ok": True, "action": "skip", "reason": "right-sized to none (busy/active)"}
        if RIGHT_SIZE_ERROR:
            skip_rs["right_size_error"] = RIGHT_SIZE_ERROR  # t75: the fail-closed deny is never silent
        return skip_rs
    budget = {"light": 1, "medium": 2, "full": 4}[level]

    steps: dict[str, Any] = {}
    # 1) sources
    steps["sources"] = _safe("mag.data_source_watch", "watch", "")
    # 2) capability steal (only if budget)
    if budget >= 1:
        steps["capability_steal"] = _safe("mag.capability_steal", "expand", "")
    # 3) self-advance reflection
    if budget >= 2:
        steps["self_advance"] = _safe("mag.self_advance", "expand", "")
    # 4) learn rightsize
    if budget >= 2:
        steps["learn_rightsize"] = _safe("mag.learn_rightsize", "learn_loop", "")
    # 5) scribe renders the surface
    steps["scribe"] = _safe("mag.scribe", "scribe", "")
    # 6) cold-boot check (core bootable = the material survives)
    steps["cold_boot"] = _safe("mag.ghost_cold_boot", "cold_boot", "")

    _fold(level, len(steps))
    return {"schema": "afk_orchestrator.run.v1", "ts": _now(),
            "offline": True, "right_size": level, "n_steps": len(steps),
            "steps": {k: _brief(v) for k, v in steps.items()}}


def _safe(mod: str, fn: str, arg: str) -> dict[str, Any]:
    try:
        m = __import__(mod, fromlist=[fn])
        f = getattr(m, fn)
        try:
            res = f(arg) if arg else f()
        except TypeError:
            res = f()
        return {"ok": True, "result": res}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _brief(v: dict[str, Any]) -> dict[str, Any]:
    if not v.get("ok"):
        return {"ok": False, "error": v.get("error", "")[:120]}
    r = v.get("result") or {}
    if isinstance(r, dict):
        return {k: r.get(k) for k in ("right_size", "n_expanded", "folded", "whispers_found", "decoded") if k in r}
    return {"ok": True}


def _fold(level: str, n_steps: int) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "autorun_cycle",
            input_data={"right_size": level, "n_steps": n_steps},
            action={"kind": "afk_orchestrator", "offline": True},
            outcome={"ran": True},
            pattern_tags=["afk_orchestrator", "one_pass", "ghost_cadence", "rightsized"],
            tier_max="T1",
            exportable=False,
        )
    except Exception as _fe:  # noqa: BLE001 - folding must never break the pass; it must be VISIBLE
        # LOOP-DEATH GUARD (2026-09-25, t78): a silently dead training-event fold voids
        # the cadence's own telemetry while run_afk still reports success. Non-fatal,
        # but visible. (pattern: work_loop.py verkle-anchor guard, t19.)
        print(f"[afk-orchestrator] FOLD LOOP DEATH GUARD: training_events.emit exited: {_fe}", flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        st: dict[str, Any] = {"schema": "afk_orchestrator.status.v1", "ts": _now(),
                              "offline": _operator_offline(), "right_size": _right_size()}
        if AFK_GATE_ERROR:
            st["afk_gate_error"] = AFK_GATE_ERROR  # t65: surface the errored gate next to the report
        if RIGHT_SIZE_ERROR:
            st["right_size_error"] = RIGHT_SIZE_ERROR  # t75: surface the errored rightsizer next to the report
        print(json.dumps(st, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(run_afk(force="--force" in argv), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
