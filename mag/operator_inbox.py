"""Operator inbox — deferred guidance (interference layer).

Breadcrumbs are operator interference — dropped on the agent's path, absorbed at
checkpoint. Routing decisions come from mag/decision_framework + mag/router.
See docs/DECISION_LAYERS.md.

Operator types in the dashboard guidance dock (or API), hits Enter to queue.
At the next checkpoint (between tool rounds / model calls), the seat drains
pending notes and either:
  - applies clear direction (decision matrix / operator_directives), or
  - asks Socratic clarifying questions tied to the current task.

Errors during tool loops are logged to logs/behavioral_events.jsonl for the
behavioral-analysis framework (scout mines them like decisions_log).

Emergent wins / brilliant moves: mag.tesuji_shell.log_tesuji_shell or
`python main.py tesuji-shell log` → logs/tesuji_shells.jsonl (scout kind=tesuji).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

INBOX_PATH = ROOT / "memory" / "operator_inbox.json"
EVENTS_PATH = ROOT / "logs" / "behavioral_events.jsonl"

# Vague inputs → Socratic clarify at checkpoint (not raw inject)
_VAGUE = {
    "continue", "go", "next", "fix it", "keep going", "yes",
    "help", "actually", "nevermind", "nvm",
}

# High-authority sovereign signals — VETO / PAUSE. These are the CLEAREST input we
# get, so they must NEVER be classified as vague and routed to Socratic clarify
# (the recurring "why are you prompting me" failure). Mirrors the pause/stop class
# already used by _emit_frustration. Full typed control channel (note|veto|cancel|
# approve|pause|resume) lands via the authority-model research t18aff67401; this is
# the deterministic contract-only fix aligned to the steal memo.
_VETO_PAUSE = {
    "no", "stop", "wait", "hold on", "hold", "pause", "halt", "cancel",
    "abort", "stop that", "stop now", "pause the run",
}


def _is_veto_or_pause(text: str) -> bool:
    """True when the input is a clear veto/pause signal (high authority, immediate).

    Negation guard: "don't stop" / "never pause" are NOT vetoes (they mean continue).
    """
    low = text.strip().lower().rstrip(".!?").strip()
    if low in _VETO_PAUSE:
        return True
    if re.search(r"\b(don'?t|do not|never|not|keep|continue)\b.*\b(stop|pause|wait|halt|cancel|abort)\b", low):
        return False
    return bool(re.search(r"\b(stop|pause|halt|cancel|abort|wait)\b", low))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not INBOX_PATH.is_file():
        return {"committed": [], "processed": []}
    try:
        data = json.loads(INBOX_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"committed": [], "processed": []}
    except (json.JSONDecodeError, OSError):
        return {"committed": [], "processed": []}


def _save(data: dict[str, Any]) -> None:
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def status() -> dict[str, Any]:
    data = _load()
    pending = [x for x in data.get("committed") or [] if x.get("status") == "pending"]
    return {
        "ok": True,
        "schema": "operator_inbox.v1",
        "pending": pending,
        "pending_n": len(pending),
        "processed_n": len(data.get("processed") or []),
        "path": _display_path(INBOX_PATH),
        "layman": (
            f"{len(pending)} note(s) queued — agent reads these at the next checkpoint, "
            "not mid-tool. Clear direction applies; vague notes get Socratic clarify."
        ),
    }


def pending_hints() -> list[str]:
    """Non-destructive read of queued guidance for governor / decision matrix."""
    return [
        str(x.get("text") or "").strip()
        for x in (_load().get("committed") or [])
        if x.get("status") == "pending" and str(x.get("text") or "").strip()
    ]


def commit_guidance(text: str, *, source: str = "dashboard") -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty guidance"}
    data = _load()
    committed = list(data.get("committed") or [])
    now = _now()

    # ── Dedup: an identical pending note already queued → refresh, don't stack.
    #    Prevents the pro-library/ghost flood where concurrent seats all pass the
    #    pending_n==0 guard (TOCTOU) and each append the same guidance, which then
    #    gets injected into every session digest (ghost: "operator_escalate x50").
    for existing in committed:
        if existing.get("status") == "pending" and str(existing.get("text") or "").strip() == text:
            existing["ts"] = now
            existing["source"] = source
            data["committed"] = committed[-50:]
            _save(data)
            return {
                "ok": True,
                "deduped": True,
                "item": existing,
                "pending_n": sum(1 for x in committed if x.get("status") == "pending"),
            }

    item = {
        "id": f"inbox-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "text": text[:4000],
        "source": source,
        "status": "pending",
        "ts": now,
    }
    committed.append(item)
    data["committed"] = committed[-50:]
    _save(data)

    # ── Emit frustration signal for Ghost auto-deploy ──
    _emit_frustration(text, source)

    return {"ok": True, "item": item, "pending_n": sum(1 for x in committed if x.get("status") == "pending")}


def _emit_frustration(text: str, source: str) -> None:
    """Log operator overrides as frustration signals for Ghost auto-deploy triggers."""
    low = text.strip().lower()
    signal = None
    # Belt-and-suspenders: a ghost meta-note reporting frustration must never
    # re-trigger the very signal it reports on (self-amplification loop).
    if "operator frustration detected" in low:
        return
    # System sources (pro-library moves, governor, autopilot) are NOT operator
    # frustration. pro-library's escalate_on_loop move contains the word
    # "escalate" and was being misclassified as operator_escalate (41 false
    # positives). Only real operator/dashboard guidance should emit a signal.
    if source in ("pro-library", "governor", "autopilot", "system", "dashboard", "ghost"):
        return
    if source in ("steer", "operator_override"):
        signal = "operator_steer_override"
    elif any(w in low for w in ("escalate", "grok", "handoff", "send to")):
        signal = "operator_escalate"
    elif any(w in low for w in ("replan", "try again", "wrong", "incorrect", "redo")):
        signal = "operator_replan"
    elif any(w in low for w in ("stuck", "loop", "repeating", "same thing")):
        signal = "operator_stuck"
    elif any(w in low for w in ("pause", "stop", "wait", "hold")):
        signal = "operator_pause"
    elif any(w in low for w in ("cheaper", "too expensive", "cost", "budget")):
        signal = "operator_cost_concern"
    if signal:
        try:
            from mag.ghost import log_frustration
            log_frustration(signal, source=source, detail=text[:200])
        except ImportError:
            pass  # ghost module not available, skip silently


def clear_pending() -> dict[str, Any]:
    data = _load()
    kept = [x for x in data.get("committed") or [] if x.get("status") != "pending"]
    data["committed"] = kept
    _save(data)
    return {"ok": True, "cleared": True}


def capture_mention(text: str, *, source: str = "conversation", log_event: bool = True) -> dict[str, Any]:
    """Live-capture an operator mention so Ghost SEES it (awareness + actionability).

    The seam for "ghost should see something when I mention it while talking":
      - Commits to operator_inbox (status=pending) -> ghost.sense() reads inbox_pending;
        the agent drains it at the next checkpoint and applies/clarifies. (SEE + ACT)
      - Optionally logs a behavioral_event (kind=operator_mention) -> ghost.sense_context()
        reads the last 5 events, so ghost is aware immediately even before a checkpoint.
    Returns the commit result. Idempotent via commit_guidance dedup.
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty mention"}
    res = commit_guidance(text, source=source)
    if log_event:
        try:
            log_behavioral_event(kind="operator_mention", detail=text[:200], phase="conversation")
        except Exception:
            pass
    res["mention"] = text
    return res


def _is_ambiguous(text: str) -> bool:
    low = text.strip().lower().rstrip(".!?")
    if _is_veto_or_pause(low):
        return False  # veto/pause = clear + actionable; never ask, act
    if low in _VAGUE:
        return True
    if len(text.strip()) < 12:
        return True
    if "?" in text and len(text) < 80:
        return True
    # lacks a verb/object heuristic
    if not re.search(r"\b(focus|stop|use|fix|build|wire|add|remove|read|write|skip|ignore|priorit)\w*", low):
        if len(text) < 40:
            return True
    return False


def _socratic_questions(guidance: str, task: str) -> list[str]:
    g = guidance.strip()[:200]
    t = (task or "current work")[:120]
    return [
        f"How does this guidance relate to your active task ({t})?",
        f"What is the single concrete next action implied by: «{g}»?",
        "Does this override the blueprint, or refine how you execute the current step?",
        "What would 'done' look like after applying this note?",
    ]


def _current_task_hint() -> str:
    # Authoritative first: state/CURRENT.md is the live resume contract the seat
    # writes as a byproduct of its tool loop (see mag.agent_cli._sync_current).
    # Reading its ## Goal field kills the guess-by-scanning-prose thrash.
    current = ROOT / "state" / "CURRENT.md"
    if current.is_file():
        try:
            in_goal = False
            for line in current.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s.startswith("## Goal"):
                    in_goal = True
                    continue
                if in_goal:
                    if s.startswith("## "):
                        break
                    if s:
                        return s[:160]
        except OSError:
            pass
    # Fallback: prose-scan only if the live contract is absent.
    for path in (
        ROOT / "memory" / "working.md",
        ROOT / "memory" / "agent_state" / "LATEST.md",
    ):
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if s.startswith("- ") and len(s) > 10:
                        return s[:160]
            except OSError:
                pass
    return "active agent turn"


def drain_pending_at_checkpoint(*, task_hint: str = "") -> list[dict[str, Any]]:
    """Drain pending inbox items into actions for the agent loop."""
    from mag.compass import record_decision

    data = _load()
    task = task_hint or _current_task_hint()
    actions: list[dict[str, Any]] = []
    processed = list(data.get("processed") or [])
    committed = list(data.get("committed") or [])

    for item in committed:
        if item.get("status") != "pending":
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            item["status"] = "skipped"
            continue
        ambiguous = _is_ambiguous(text)
        if ambiguous:
            questions = _socratic_questions(text, task)
            actions.append({
                "action": "socratic",
                "id": item.get("id"),
                "text": text,
                "questions": questions,
                "task_hint": task,
            })
            record_decision(
                "operator inbox checkpoint",
                text,
                "socratic clarify — ambiguous queued guidance",
            )
        else:
            actions.append({
                "action": "apply",
                "id": item.get("id"),
                "text": text,
                "task_hint": task,
            })
            record_decision(
                "operator inbox checkpoint",
                text,
                "applied queued guidance — autonomous per operator_directives",
            )
        item["status"] = "processed"
        item["processed_at"] = _now()
        processed.append({**item, "action": "socratic" if ambiguous else "apply"})
    data["committed"] = committed
    data["processed"] = processed[-100:]
    _save(data)
    return actions


def log_behavioral_event(
    *,
    kind: str,
    detail: str,
    tool: str | None = None,
    error: str | None = None,
    phase: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Feed the overseeing / improve pipeline with seat errors.

    session_id/provider/model identify the seat that produced the event so
    the behavioral-analysis pipeline can attribute failures to a run.
    """
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _now(),
        "kind": kind,
        "detail": (detail or "")[:500],
        "tool": tool,
        "error": (error or "")[:300] if error else None,
        "phase": phase,
        "session_id": session_id,
        "provider": provider,
        "model": model,
    }
    try:
        with EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # Mirror high-signal failures into decisions log for compass case law
    if kind in ("tool_fail", "collapse", "degenerate", "seat_crash"):
        try:
            from mag.compass import record_decision

            record_decision(
                f"behavioral {kind}",
                detail[:200],
                f"logged {EVENTS_PATH.name} — remedy/candidate pipeline may rank",
            )
        except Exception:
            pass
    # FKB: dedupe failures + auto-draft remedies on recurrence
    if kind in ("tool_fail", "collapse", "degenerate", "seat_crash"):
        try:
            from mag.failure_kb import log_failure

            log_failure(
                kind=kind,
                detail=detail,
                tool=tool,
                error=error,
                phase=phase,
                session_id=session_id,
                provider=provider,
                model=model,
            )
        except Exception:
            pass
    # FKB: dedupe failures + auto-draft remedies on recurrence
    if kind in ("tool_fail", "collapse", "degenerate", "seat_crash"):
        try:
            from mag.failure_kb import log_failure

            log_failure(
                kind=kind,
                detail=detail,
                tool=tool,
                error=error,
                phase=phase,
                session_id=session_id,
                provider=provider,
                model=model,
            )
        except Exception:
            pass
    # PERCOLATOR EVERYWHERE (2026-08-11): route the event's free-text through the signal
    # percolator — noise/theater to the noise file, false positives filtered (never truth),
    # repeatable signal compiled into invariants, novel signal queued for exploration, and a
    # training event emitted. Non-blocking: never throws, never alters the caller's contract.
    try:
        from mag.percolator import percolate_signal
        if (detail or "").strip():
            percolate_signal(detail, pattern=kind or "route_decision", source="behavioral_event",
                             domain="behavioral")
    except Exception:
        pass


def apply_actions_to_messages(
    messages: list[dict[str, Any]], actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Inject drained inbox actions into the conversation."""
    out = list(messages)
    for a in actions:
        if a.get("action") == "apply":
            text = a.get("text") or ""
            out.append({
                "role": "user",
                "content": (
                    f"[OPERATOR GUIDANCE — queued while you were working]\n{text}\n\n"
                    "Apply per operator_directives (memory/operator_directives.md): "
                    "execute autonomously; this overrides vague plan drift. "
                    "Record the pick in working.md if significant."
                ),
            })
        elif a.get("action") == "socratic":
            qs = a.get("questions") or []
            qblock = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(qs))
            out.append({
                "role": "user",
                "content": (
                    f"[OPERATOR GUIDANCE — queued, needs clarify]\n{a.get('text')}\n\n"
                    f"Current task context: {a.get('task_hint')}\n\n"
                    "Answer these briefly in one paragraph, then continue autonomously:\n"
                    f"{qblock}"
                ),
            })
    return out
