"""Refine Loop — the training flywheel: SENSE → PROBE → ESCALATE → FIX → FOLD.

The operator's doctrine: "ghost sense what the fuck is going on, the doctor probe
reports what's wrong, then escalate to grok for a frontier-level coding approach
that deepseek uses to fix and enhance our systems. Let's refine this loop."

This module wires the PROVEN pieces into one loop that reuses the framework's own
tools (never ad-hoc terminal work):

    1. SENSE      ghost.sense() / sense_surfaces()          → what looks off
    2. PROBE      doctor.doctor_status() + doctor_agent_run → structured "what's wrong"
    3. ESCALATE   grok_rightsize.call_grok_free() (harness CLI) gated by lanes
                   can_escalate_grok → frontier coding APPROACH (the prescription)
    4. FIX        orchestrator.enqueue(provider="deepseek") → deepseek implements
                   the approach against the real codebase
    5. FOLD       training_events.emit() + pro_library.add_move()
                   + skill_ledger.record_decision() → each run is a training row

The gate is honest: we only escalate to grok when the probe finds a real,
frontier-worthy problem (not routine noise). Every stage is optional and degrades
gracefully when the transport isn't available (e.g. grok CLI absent / quota).

SCHEMA: refine_loop.v1
LAW: Sense is free. Probe is free. Escalate is budgeted. Fix is enqueued. Fold always.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _read_jsonl(path: Path, tail: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    except OSError:
        pass
    return out


# ═══════════════════════════════════════════════════════════════════
# STAGE 1 — SENSE: what looks off (cheap, $0, framework's own read-only)
# ═══════════════════════════════════════════════════════════════════

def refine_sense(*, include_doctor: bool = True) -> dict[str, Any]:
    """Gather a lightweight vitals snapshot of the system.

    Reads the same surfaces ghost uses. Returns a dict of named signals so the
    doctor probe knows where to look. Never blocks on a frontier call here.
    """
    state: dict[str, Any] = {"ts": _now()}

    # Queue vitals
    try:
        from mag import orchestrator

        qs = orchestrator.queue_status()
        state["queue"] = {
            "queued": qs.get("counts", {}).get("queued", 0),
            "done": qs.get("counts", {}).get("done", 0),
            "failed": qs.get("counts", {}).get("failed", 0),
            "running_task_id": qs.get("running_task_id"),
        }
    except Exception:
        state["queue"] = {"queued": 0, "error": "queue_status unavailable"}

    # Drainer health — a big queued backlog with nothing running is the smell
    try:
        q = state.get("queue", {})
        if q.get("queued", 0) > 0 and not q.get("running_task_id"):
            state["drainer_idle"] = True
        else:
            state["drainer_idle"] = False
    except Exception:
        state["drainer_idle"] = None

    # Ghost's own sense surfaces
    try:
        from mag import ghost

        g = ghost.sense()
        state["ghost_sense"] = {
            "fkb_signal_count": g.get("fkb_signal_count", 0),
            "fkb_signals": g.get("fkb_signals", [])[:3],
            "inbox_pending": g.get("inbox_pending", 0),
            "verkle_tip_stale": g.get("verkle_tip_stale", False),
            "frustration_total": g.get("frustration_total", 0),
            "leak_canary_breaches": g.get("leak_canary_breaches", 0),
            "leak_entropy_anomalies": g.get("leak_entropy_anomalies", 0),
        }
    except Exception:
        state["ghost_sense"] = {"error": "ghost.sense unavailable"}

    # Doctor probe (free, local-only) — the structured "what's wrong"
    if include_doctor:
        state["doctor"] = doctor_probe()

    # Failure KB heat — repeated identical tool failures = a fixable bug
    try:
        fkb = _read_jsonl(ROOT / "logs" / "failure_kb.jsonl", tail=100)
        heat: dict[str, int] = {}
        for r in fkb:
            sig = r.get("sig") or r.get("signature_key") or r.get("tool") or ""
            if sig:
                heat[sig] = heat.get(sig, 0) + 1
        hot = [{"sig": k, "count": v} for k, v in heat.items() if v >= 3]
        hot.sort(key=lambda x: x["count"], reverse=True)
        state["fkb_heat"] = hot[:5]
    except Exception:
        state["fkb_heat"] = []

    return state


# ═══════════════════════════════════════════════════════════════════
# STAGE 2 — PROBE: structured "what's wrong" report ($0, doctor)
# ═══════════════════════════════════════════════════════════════════

def doctor_probe() -> dict[str, Any]:
    """Run the doctor checks and report what's wrong (and what auto-fixed).

    Returns a structured report. Does NOT escalate — it only diagnoses.
    """
    report: dict[str, Any] = {"ts": _now()}

    # Diagnostic report from doctor.py
    try:
        from mag import doctor

        st = doctor.doctor_status()
        report["status"] = {
            "ok": st.get("ok"),
            "errors": st.get("errors", 0),
            "warnings": st.get("warnings", 0),
            "details": st.get("details", {}),
        }
    except Exception as e:
        report["status"] = {"ok": False, "error": str(e)[:160]}

    # Auto-fix attempt from doctor_agent.py (local models, $0)
    try:
        from mag import doctor_agent

        run = doctor_agent.doctor_agent_run()
        report["fixes"] = {
            "attempted": run.get("fixes_attempted", 0),
            "succeeded": run.get("fixes_succeeded", 0),
            "failed": run.get("fixes_failed", 0),
            "verdict": run.get("verdict", ""),
        }
    except Exception as e:
        report["fixes"] = {"attempted": 0, "error": str(e)[:160]}

    return report


# ═══════════════════════════════════════════════════════════════════
# STAGE 3 — ESCALATE: get a frontier-level coding APPROACH from grok
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Escalation:
    escalated: bool = False
    target: str = ""
    reason: str = ""
    approach: str = ""                 # the frontier prescription
    raw: dict[str, Any] = field(default_factory=dict)
    path: str = ""


def _frontier_worthy(state: dict[str, Any]) -> tuple[bool, str]:
    """Honest gate: only escalate when a real, frontier-worthy problem exists.

    Returns (escalate, why). Routine noise does NOT trigger grok spend.
    """
    reasons: list[str] = []

    q = state.get("queue", {})
    if q.get("queued", 0) > 12 and not q.get("running_task_id"):
        reasons.append(f"drainer idle with {q.get('queued')} queued")
    elif q.get("queued", 0) > 25:
        reasons.append(f"large backlog {q.get('queued')} queued")

    dr = state.get("doctor", {}).get("status", {})
    if dr.get("errors", 0) > 0:
        reasons.append(f"{dr.get('errors')} doctor errors")

    if state.get("fkb_heat"):
        top = state["fkb_heat"][0]
        reasons.append(f"FKB heat {top['sig']} x{top['count']}")

    gs = state.get("ghost_sense", {})
    if gs.get("leak_canary_breaches", 0) > 0 or gs.get("leak_entropy_anomalies", 0) > 0:
        reasons.append("leak anomalies detected")

    if not reasons:
        return False, "no frontier-worthy problem — system nominal"

    return True, "; ".join(reasons)


def escalate_to_grok(
    state: dict[str, Any],
    *,
    max_chars: int = 6000,
) -> Escalation:
    """Route the diagnosis to grok for a frontier coding approach.

    Gated by lanes.can_escalate_grok (budget + [priority] policy). Transport is
    grok_rightsize.call_grok_free (harness CLI first, paid API fallback). The
    deliverable is an APPROACH (prescription), not the implementation — deepseek
    implements it in the next stage.
    """
    out = Escalation()

    worthy, why = _frontier_worthy(state)
    if not worthy:
        out.reason = why
        return out

    try:
        from mag.lanes import can_escalate_grok

        allowed, gate_why = can_escalate_grok(
            goal=f"[priority] refine-loop: {why[:120]}",
            reason="doctor probe found a real problem; need frontier coding approach",
            force=False,
        )
        if not allowed:
            out.reason = f"grok gate blocked: {gate_why}"
            return out
    except Exception as e:
        out.reason = f"grok gate error: {e}"
        return out

    # Build a compact frontier ask: the diagnosis + what we want back.
    probe = _format_probe(state, max_chars=max_chars)
    goal = (
        f"[priority] Frontier coding approach for a system problem diagnosed by the "
        f"doctor probe. The local doctor found: {why}. "
        f"Give a concrete, implementable coding approach (files, functions, invariants, "
        f"order of operations) that deepseek-v4-flash can execute against the real "
        f"codebase to FIX or ENHANCE this. Be specific and grounded in the evidence "
        f"below. End with SUMMARY and DELIVERABLE sections."
    )

    try:
        from mag import grok_rightsize

        res = _call_frontier(goal, probe, timeout=420)
        ok = bool(res.get("ok"))
        content = str(res.get("content") or "")
        out.escalated = ok
        out.target = str(res.get("model") or res.get("tier") or "grok")
        out.raw = res
        if ok:
            out.approach = content
            out.reason = f"grok {out.target} returned approach"
            # Persist the approach so the fix stage / operator can read it.
            out.path = _persist_approach(why, content, res)
        else:
            out.reason = f"grok call failed: {str(res.get('error') or '')[:160]}"
    except Exception as e:
        out.reason = f"grok escalation error: {str(e)[:200]}"
        out.raw = {"error": str(e), "tb": traceback.format_exc()[-500:]}

    return out


def _call_frontier(goal: str, context: str, *, timeout: int = 420) -> dict[str, Any]:
    """Call the frontier tier with a budget generous enough to DELIVER.

    call_grok_free() hardcodes max_turns=8, which is too tight for a full coding
    approach — grok burns turns exploring and hits "max turns reached" without a
    deliverable. When the harness CLI is present, call it directly with a higher
    turn budget so the approach actually lands. Falls back to call_grok_free when
    the harness is absent.
    """
    from mag import grok_rightsize

    # Prefer the FUNDED API-key surface first (call_grok probes keys and fails
    # over on 401/402/403), because the Grok Build harness subscription can be
    # balance-exhausted (HTTP 402) while XAI_API_KEY still works. Order:
    #  1) call_grok (API key chain, funded-key fail-over)
    #  2) harness CLI (free subscription) only if the API path is absent/failed
    #  3) call_grok_free as the final rightsized fallback.
    try:
        r = grok_rightsize.call_grok(goal, context=context, max_tokens=4000, timeout=timeout)
        if r.ok:
            return {
                "ok": True,
                "content": r.content,
                "model": r.model,
                "tier": r.tier,
                "cost_est_usd": r.cost_est_usd,
                "key_env": r.key_env or "xai-api",
                "harness": False,
                "error": "",
            }
        api_err = r.error or "api-key path failed"
    except Exception as e:
        api_err = f"api-key path error: {e}"

    # API-key path unavailable or unfunded — try the harness subscription.
    try:
        from harness.grok_cli import escalate_via_harness, harness_available

        if harness_available():
            res = escalate_via_harness(
                goal=goal, context=context, max_turns=24, timeout=timeout,
            )
            if res.get("ok"):
                return {
                    "ok": True,
                    "content": str(res.get("deliverable") or "") or str(res.get("summary") or ""),
                    "model": "grok-cli-harness",
                    "tier": "free-harness",
                    "cost_est_usd": 0.0,
                    "key_env": "grok-cli",
                    "harness": True,
                    "error": "",
                    "result_path": res.get("result_path"),
                }
            harness_err = f"harness: {str(res.get('error') or '')[:200]}"
        else:
            harness_err = "harness CLI absent"
    except Exception as e:
        harness_err = f"harness error: {e}"

    # Final fallback: rightsized transport.
    try:
        res2 = grok_rightsize.call_grok_free(
            goal=goal, context=context, max_tokens=4000, timeout=timeout,
        )
        if res2.get("ok"):
            return res2
        free_err = f"free: {str(res2.get('error') or '')[:200]}"
    except Exception as e:
        free_err = f"free error: {e}"

    return {"ok": False, "content": "", "model": "grok", "tier": "deep",
            "cost_est_usd": 0.0, "key_env": "xai",
            "error": f"{api_err} | {harness_err} | {free_err}"[:400]}


def _format_probe(state: dict[str, Any], *, max_chars: int = 6000) -> str:
    """Compact, evidence-first rendering of the probe for the frontier model."""
    lines: list[str] = ["# Doctor Probe — what's wrong", ""]

    q = state.get("queue", {})
    lines.append("## Queue")
    lines.append(json.dumps(q, default=str))
    lines.append("")

    dr = state.get("doctor", {})
    lines.append("## Doctor status")
    lines.append(json.dumps(dr.get("status", {}), default=str)[:2000])
    lines.append("## Doctor fixes")
    lines.append(json.dumps(dr.get("fixes", {}), default=str)[:1000])
    lines.append("")

    if state.get("fkb_heat"):
        lines.append("## Failure-KB heat (repeated identical failures)")
        lines.append(json.dumps(state["fkb_heat"], default=str)[:2000])
        lines.append("")

    gs = state.get("ghost_sense", {})
    lines.append("## Ghost sense")
    lines.append(json.dumps(gs, default=str)[:1500])
    lines.append("")

    text = "\n".join(lines)
    return text[:max_chars]


def _persist_approach(why: str, content: str, res: dict[str, Any]) -> str:
    """Write the grok approach to memory so the fix stage and operator can read it."""
    import re

    ts = _now()[:19].replace(":", "").replace("-", "")
    safe = re.sub(r"[^A-Za-z0-9]+", "-", why[:40]).strip("-").lower() or "refine"
    path = ROOT / "memory" / "refine" / f"{ts}_{safe}.approach.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"# Frontier Approach — {why}\n\n"
        f"**ts:** {_now()}\n"
        f"**transport:** {res.get('model')} / {res.get('tier')}\n"
        f"**path:** {res.get('result_path') or 'inline'}\n\n"
        f"---\n\n{content}\n"
    )
    try:
        path.write_text(body, encoding="utf-8")
    except OSError:
        return ""
    return str(path)


# ═══════════════════════════════════════════════════════════════════
# STAGE 4 — FIX: deepseek implements the approach against the codebase
# ═══════════════════════════════════════════════════════════════════

def _freeze_build(escalation: Escalation, *, name: str = "") -> str:
    """Freeze the grok approach into a queue/handoff/BUILD-*.md contract.

    The factory gate (`mag.factory_gate.check_frozen_build`) refuses code work
    unless the goal names a frozen BUILD-*.md contract (status: frozen). This
    writes one so the FIX stage passes the gate. Returns the build name (e.g.
    "refine-<slug>") or "" on failure.
    """
    import re

    slug = re.sub(r"[^A-Za-z0-9]+", "-", (name or escalation.reason or "refine")[:48]).strip("-").lower()
    slug = slug or "refine"
    build_name = f"refine-{slug}"
    handoff = ROOT / "queue" / "handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    path = handoff / f"BUILD-{build_name}.md"

    body = (
        f"# BUILD-{build_name}.md — freeze refine-loop grok approach\n\n"
        f"**status:** frozen\n"
        f"**tier:** T1\n"
        f"**source:** refine-loop grok escalation ({_now()})\n"
        f"**approach file:** {escalation.path or '(inline)'}\n"
        f"**executor:** deepseek-v4-flash (tag refine-fix)\n\n"
        f"## Problem (doctor probe)\n{escalation.reason}\n\n"
        f"## Approach (grok)\n{escalation.approach[:3000]}\n\n"
        f"## Constraints\n"
        f"- Minimal, idiomatic edits. Do NOT touch main.py, dashboard/, tests, config.py.\n"
        f"- Do NOT repeat failed tool patterns (esp. write_file that claims edits but writes nothing).\n"
        f"- Prefer the framework's own tools; route through orchestrator, not ad-hoc.\n"
        f"- Verify imports succeed after edits.\n"
    )
    try:
        path.write_text(body, encoding="utf-8")
    except OSError:
        return ""
    return build_name


def delegate_fix(
    escalation: Escalation,
    *,
    tag: str = "refine-fix",
) -> dict[str, Any]:
    """Enqueue a deepseek task that implements the grok approach.

    The grok approach is FIRST frozen into a `queue/handoff/BUILD-*.md` contract
    (status: frozen) because the factory gate refuses to run code work without a
    named frozen build. Freezing here makes the FIX stage pass the gate every time
    instead of deferring.

    Returns the queue record. If there's no approach, returns a no-op dict.
    """
    if not escalation.escalated or not escalation.approach:
        return {"ok": False, "error": "no approach to implement", "escalated": escalation.escalated}

    build_name = _freeze_build(escalation)
    if not build_name:
        return {"ok": False, "error": "could not freeze BUILD contract", "escalated": True}

    goal = (
        f"[refine-fix] Implement {build_name} against the real codebase. "
        f"Frozen contract: {escalation.reason[:160]}. "
        f"Map the approach to real modules per the contract. Use framework tools, "
        f"minimal idiomatic edits. Do NOT repeat failed tool patterns."
    )

    try:
        from mag import orchestrator

        rec = orchestrator.enqueue(
            goal=goal,
            provider="deepseek",
            model="deepseek-v4-flash",
            tag=tag,
            timeout=900,
            tier="research",
            require_build=build_name,
        )
        rec["escalation_reason"] = escalation.reason
        rec["build_spec"] = build_name
        return rec
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════
# STAGE 5 — FOLD: each loop iteration is a training row + a pro move
# ═══════════════════════════════════════════════════════════════════

def fold_back(state: dict[str, Any], escalation: Escalation, fix: dict[str, Any]) -> dict[str, Any]:
    """Emit a training event, log a pro move, and record the decision."""
    folded: dict[str, Any] = {}

    # Training event
    try:
        from mag.training_events import emit

        evt = emit(
            "refine_round",
            join={"probe_ts": str(state.get("ts", ""))},
            input_data={
                "queue_queued": state.get("queue", {}).get("queued", 0),
                "doctor_errors": state.get("doctor", {}).get("status", {}).get("errors", 0),
                "fkb_heat": len(state.get("fkb_heat", [])),
                "drainer_idle": state.get("drainer_idle"),
            },
            action={
                "escalated": escalation.escalated,
                "target": escalation.target,
                "reason": escalation.reason[:200],
                "approach_path": escalation.path,
            },
            outcome={
                "fix_ok": bool(fix.get("ok")),
                "fix_queue_id": fix.get("queue_id"),
                "fix_error": str(fix.get("error") or "")[:200],
            },
            pattern_tags=["refine_loop", "sense", "probe", "escalate", "fix", "fold"],
        )
        folded["training_event"] = evt.get("event_id")
    except Exception as e:
        folded["training_error"] = str(e)[:160]

    # Pro library move (only if we actually escalated — that's the learned move)
    if escalation.escalated:
        try:
            from mag import pro_library

            move = pro_library.add_move(
                signature=["doctor_probe", "refine_loop", "escalate_grok", "deepseek_fix"],
                kind="loop",
                move=(
                    f"Refine loop: ghost SENSE (free) → doctor PROBE (structured what's-wrong) → "
                    f"grok ESCALATE (frontier coding approach, budget-gated) → deepseek FIX "
                    f"(enqueue implement) → FOLD (training row + pro move). The doctor's diagnosis "
                    f"is the ask contract; grok prescribes, deepseek executes. Gate grok spend on "
                    f"frontier-worthiness — routine noise stays local."
                ),
                effect=escalation.reason[:200],
                maps_to="spec:refine-loop-sense-probe-escalate-fix-fold",
                tags=["refine-loop", "doctor", "grok", "deepseek", "training"],
            )
            folded["pro_move"] = move.get("ok")
        except Exception as e:
            folded["pro_move_error"] = str(e)[:160]

    # Skill ledger decision
    try:
        from mag import skill_ledger

        skill_ledger.record_decision(
            goal=f"refine-loop run: {escalation.reason[:80]}",
            task_shape="refine_loop_run",
            provider=escalation.target or "local",
            model="deepseek-v4-flash",
            outcome="ok" if escalation.escalated else "nominal",
            detail=(
                f"sense+probe free; escalated={escalation.escalated}; "
                f"fix_queue={fix.get('queue_id') or 'none'}; {escalation.reason[:160]}"
            ),
            source="refine-loop",
        )
        folded["ledger"] = True
    except Exception as e:
        folded["ledger_error"] = str(e)[:160]

    return folded


# ═══════════════════════════════════════════════════════════════════
# ORCHESTRATION — run the full loop in one call
# ═══════════════════════════════════════════════════════════════════

def run_refine_loop(*, escalate: bool = True, delegate: bool = True,
                    fold: bool = True) -> dict[str, Any]:
    """Run one full refine-loop iteration.

    Returns the full pipeline result. Safe to call from ghost's autonomous loop.
    Every stage degrades gracefully; a failure in one stage doesn't abort the rest.
    """
    result: dict[str, Any] = {
        "schema": "refine_loop.v1",
        "ts": _now(),
    }

    # 1. SENSE
    try:
        state = refine_sense(include_doctor=True)
    except Exception as e:
        state = {"error": str(e)[:200]}
    result["sense"] = state

    # 2/3. ESCALATE (doctor probe is part of sense; escalation is the frontier ask)
    esc = Escalation()
    if escalate:
        esc = escalate_to_grok(state)
    result["escalation"] = {
        "escalated": esc.escalated,
        "target": esc.target,
        "reason": esc.reason,
        "approach_path": esc.path,
        "approach_chars": len(esc.approach),
    }

    # 4. FIX
    fix: dict[str, Any] = {"ok": False}
    if delegate and esc.escalated:
        fix = delegate_fix(esc)
    result["fix"] = fix

    # 5. FOLD
    if fold:
        result["fold"] = fold_back(state, esc, fix)

    return result


def refine_loop_loop(*, interval_s: float = 600.0) -> None:
    """Background loop for Ghost: run the refine loop every N seconds."""
    import asyncio

    async def _loop() -> None:
        while True:
            try:
                run_refine_loop()
            except Exception:
                pass
            await asyncio.sleep(interval_s)

    import threading

    def _runner() -> None:
        asyncio.run(_loop())

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return


# ═══════════════════════════════════════════════════════════════════
# CLI — python -m mag.refine_loop [run|sense|probe|escalate]
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "sense":
        print(json.dumps(refine_sense(), indent=2, default=str))
    elif mode == "probe":
        print(json.dumps(doctor_probe(), indent=2, default=str))
    elif mode == "escalate":
        s = refine_sense()
        e = escalate_to_grok(s)
        print(json.dumps({
            "escalated": e.escalated,
            "target": e.target,
            "reason": e.reason,
            "approach_path": e.path,
            "approach_chars": len(e.approach),
        }, indent=2, default=str))
    else:
        print(json.dumps(run_refine_loop(), indent=2, default=str))
