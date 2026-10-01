"""Governor supervisor — slow thinking between the sub-agent's heartbeats.

The orchestrator spawns isolated sub-agents (fast executors). This module turns
the orchestrator window into a *supervisor agent*: between heartbeat intervals
it reads the task's knot (goal, status phase, last beads, log tail), makes its
own model call (slow thinking / planning), and injects a short governance note
back through the mailbox (post_steer) so the seat can course-correct mid-run.

Two escalations, both over the same knot channel:

  1. Healthy tick   -> slow_think() verdict; inject STEER only when actionable
                       ("on-track, continue" is NOT injected — zero noise).
  2. Stall detected -> context-aware nudge: the seat gets receipts (goal,
                       phase, last_tool/step, log tail) so it can diagnose and
                       fix the stall instead of guessing (the "pass timeouts to
                       prompt it to fix the stalled prompt" ask).

No new channels, no pipes: inbox.txt + heartbeat.jsonl + status.json only.
"""
from __future__ import annotations

from typing import Any

from mag import pigeonhole as ph

GOVERNOR_SYSTEM = (
    "You are the governor of a sovereign agent run (mycelial republic). A "
    "sub-agent is executing a goal autonomously. You read its heartbeat beads, "
    "status phase, and log tail, then think slowly about whether it is on "
    "track. Reply with EXACTLY two lines:\n"
    "VERDICT: on-track|drift|stalled|blocked\n"
    "STEER: <one actionable sentence, max 160 chars, second person to the "
    "sub-agent, concrete next step or course correction>\n"
    "If the agent is genuinely on track and needs nothing, write STEER: - "
    "(dash only). Never restate the goal. Never praise. Steer only when it "
    "changes what the agent does next."
)


def context_bundle(task_id: str, log_tail_n: int = 10,
                   max_chars: int = 2400) -> dict[str, Any]:
    """Assemble everything the governor needs to judge one task."""
    st = ph.read_status(task_id) or {}
    beads = ph.heartbeats(task_id, limit=6)
    from mag import orchestrator as orc

    rec = orc._load(task_id) or {}
    goal = rec.get("goal") or ""
    cmd = rec.get("cmd") or []
    log_tail = orc.tail_log(task_id, log_tail_n)
    if len(log_tail) > max_chars:
        log_tail = log_tail[-max_chars:]
    bead_lines = []
    for b in beads:
        bead_lines.append(
            "%s step=%s last_tool=%s phase=%s" % (
                b.get("ts", "?")[11:19], b.get("step", "?"),
                b.get("last_tool", "-"), b.get("phase", "?")))
    return {
        "task_id": task_id,
        "goal": goal,
        "phase": st.get("phase", "?"),
        "status_ts": st.get("ts", "?"),
        "beads": "\n".join(bead_lines) or "(no beads yet)",
        "log_tail": log_tail,
        "cmd_tail": " ".join(cmd)[-200:],
        "age_s": ph.staleness_s(task_id),
    }

def slow_think(bundle: dict[str, Any], *, provider: str = "deepseek",
               model: str | None = None, max_tokens: int = 400,
               timeout: int = 120) -> dict[str, Any]:
    """One governor model call over the bundle. Returns verdict + steer."""
    from models.providers import chat_messages

    user = (
        "GOAL: %s\n\n"
        "AGENT PHASE: %s (status written %s)\n"
        "HEARTBEAT AGE: %s s\n\n"
        "RECENT BEADS (step / last_tool / phase):\n%s\n\n"
        "LOG TAIL:\n%s\n\n"
        "Last command: %s\n"
        "Give VERDICT + STEER." % (
            bundle.get("goal") or "(not recorded)",
            bundle.get("phase", "?"),
            bundle.get("status_ts", "?"),
            bundle.get("age_s"),
            bundle.get("beads", ""),
            bundle.get("log_tail", ""),
            bundle.get("cmd_tail", ""),
        )
    )
    messages = [
        {"role": "system", "content": GOVERNOR_SYSTEM},
        {"role": "user", "content": user},
    ]
    res = chat_messages(provider, messages, model=model,
                        temperature=0.2, max_tokens=max_tokens,
                        tier="T2", timeout=timeout)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "provider error")}
    text = (res.get("text") or "").strip()
    verdict = "?"
    steer = ""
    for ln in text.splitlines():
        s = ln.strip()
        if s.lower().startswith("verdict:"):
            verdict = s.split(":", 1)[1].strip().lower()
        elif s.lower().startswith("steer:"):
            steer = s.split(":", 1)[1].strip()
    return {"ok": True, "verdict": verdict, "steer": steer,
            "raw": text, "provider": res.get("provider"),
            "model": res.get("model")}

def supervise_once(task_id: str, *, provider: str = "deepseek",
                   model: str | None = None, inject: bool = True,
                   log_tail_n: int = 10) -> dict[str, Any]:
    """Bundle -> think -> inject (if actionable). Returns the summary."""
    bundle = context_bundle(task_id, log_tail_n=log_tail_n)
    note = slow_think(bundle, provider=provider, model=model)
    out = {"task_id": task_id, "bundle": bundle, "note": note}
    if not note.get("ok"):
        out["injected"] = False
        return out
    steer = (note.get("steer") or "").strip()
    if steer and steer != "-" and inject:
        ph.post_steer(task_id, "[governor] " + steer[:400])
        out["injected"] = True
    else:
        out["injected"] = False
    try:
        from mag.orchestrator import _trail
        _trail("governor", task_id, verdict=note.get("verdict"),
               injected=out["injected"],
               steer=steer[:160] if steer and steer != "-" else "")
    except Exception:
        pass
    return out


def supervise_loop(task_id: str, *, provider: str = "deepseek",
                   model: str | None = None, interval_s: int = 90,
                   stop_statuses: set[str] | None = None) -> None:
    """Daemon: every interval_s, supervise while the task is live.

    Runs in its own thread so a slow model call never delays the monitor's
    kill backstop. Skips ticks while the task is terminal.
    """
    import time
    from mag import orchestrator as orc

    terminal = stop_statuses or orc.TERMINAL
    while True:
        time.sleep(interval_s)
        rec = orc._load(task_id)
        if not rec or rec.get("status") in terminal:
            return
        try:
            supervise_once(task_id, provider=provider, model=model)
        except Exception:
            # Governor failure must never take down the run or the monitor.
            pass

# --- stall nudge with receipts -----------------------------------------------

def stall_nudge_text(task_id: str, age_s: int) -> str:
    """Context-aware nudge: give the seat what it needs to fix the stall.

    Generic "re-anchor" steers are useless when the seat is stuck mid-tool.
    This one carries goal, phase, last activity and log tail so the sub-agent
    can diagnose the stall itself instead of guessing. It also names the
    stall timeout explicitly so a blocked tool call gets killed, not waited
    on forever (the "pass timeouts to prompt it to fix the stalled prompt"
    ask).
    """
    st = ph.read_status(task_id) or {}
    beads = ph.heartbeats(task_id, limit=3)
    from mag import orchestrator as orc

    rec = orc._load(task_id) or {}
    goal = (rec.get("goal") or "(not recorded)")[:400]
    last = ""
    for b in beads:
        last = "%s step=%s last_tool=%s phase=%s" % (
            b.get("ts", "?")[11:19], b.get("step", "?"),
            b.get("last_tool", "-"), b.get("phase", "?"))
    log_tail = orc.tail_log(task_id, 6)[-800:]
    return (
        "[governor] STALL DETECTED (%s s since last heartbeat). Receipts to "
        "fix it: goal=%r | phase=%s | last activity: %s | log tail: %s. "
        "Diagnose the stall from these, re-anchor to the goal, and continue. "
        "If a tool call is blocked, treat it as timed out (default timeout "
        "applies) and move on with a revised approach." % (
            age_s, goal, st.get("phase", "?"), last or "(none yet)", log_tail)
    )


def stall_nudge(task_id: str, age_s: int) -> dict[str, Any]:
    """Post the receipt nudge into the task mailbox. Returns the message."""
    msg = stall_nudge_text(task_id, age_s)
    ph.post_steer(task_id, msg)
    try:
        from mag.orchestrator import _trail
        _trail("governor", task_id, verdict="stalled", injected=True,
               steer="stall nudge with receipts (age=%ss)" % age_s)
    except Exception:
        pass
    return {"task_id": task_id, "injected": True, "msg": msg[:200]}
