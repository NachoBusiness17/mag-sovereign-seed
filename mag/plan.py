"""Planning gate — clarify & workshop before committing to big tasks.

Commitment: planning-mode-mag-001
Parents: docs/ref/MAG_OS_v2.md · docs/ref/OPERATOR_CARD.md · mag/dispatch.py

A cheap, local-first clarification pass that runs BEFORE dispatch commits to a
big/ambiguous/expensive task. Produces a short plan object (goal → scope →
success checks → seat → token budget) the operator can approve, edit, or reject.

Small tasks (list, show, read, brief, recall, status) skip the gate entirely.

Priority store: the gate consults memory/plans/priority_store.json so its one
clarifying round is anchored against the operator's known ordered priorities
(INTJ: ask once, answer once, go — no open-ended planning theater).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

PLANS = ROOT / "memory" / "plans"
PRIORITY_STORE = PLANS / "priority_store.json"
SCHEMA = "mag_plan.v1"

# Trigger signals — fire the gate when the goal matches ANY of these.
_AMBIGUOUS = ("improve", "fix", "make better", "handle", "something about",
              "smarter", "know what i mean", "better than")
_SCOPE = ("all", "everything", "full", "entire", "multi-file", "refactor",
          "architecture", "design system", "system", "by default",
          "incorporate", "incorporat")
_EXPENSE = ("research", "scrape", "analyze deeply", "compare", "train",
            "weight", "build", "implement")
_IRREVERSIBLE = ("delete", "archive", "move", "rename", "migrate", "reset")

# Small-task keywords that ALWAYS skip the gate (cheap + unambiguous).
_SKIP = ("list", "show", "read ", "ls", "dir", "brief", "recall", "status",
         "health", "what was i", "open loop", "session", "doctor", "quota")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "plan").strip().lower()).strip("-")
    return (s[:n] or "plan").rstrip("-")


def should_plan(goal: str) -> bool:
    """Return True when the goal should pass through the planning gate."""
    g = (goal or "").strip()
    if not g:
        return False
    gl = g.lower()
    # Small tasks always skip.
    if any(k in gl for k in _SKIP):
        return False
    # Explicit opt-in.
    if gl.startswith("plan:") or "--plan" in gl:
        return True
    # Length threshold (matches dispatch hard_code).
    if len(g) > 400:
        return True
    # Signal match.
    if any(k in gl for k in _AMBIGUOUS):
        return True
    if any(k in gl for k in _SCOPE):
        return True
    if any(k in gl for k in _EXPENSE):
        return True
    if any(k in gl for k in _IRREVERSIBLE):
        return True
    return False


def _signals(goal: str) -> list[str]:
    gl = (goal or "").lower()
    out = []
    for name, keys in (("ambiguous", _AMBIGUOUS), ("scope", _SCOPE),
                       ("expense", _EXPENSE), ("irreversible", _IRREVERSIBLE)):
        hit = [k for k in keys if k in gl]
        if hit:
            out.append(f"{name}:{','.join(hit)}")
    return out


def priority_hint(goal: str = "") -> dict[str, Any]:
    """Return the top open priority from the store to anchor the gate's ask.

    Reads memory/plans/priority_store.json. Falls back to an empty dict if the
    store is missing or unreadable (gate still works, just unanchored).
    """
    try:
        data = json.loads(PRIORITY_STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    prios = [p for p in data.get("priorities", []) if p.get("status") == "open"]
    if not prios:
        return {}
    top = prios[0]
    return {
        "store": str(PRIORITY_STORE).replace(str(ROOT), "MAG").replace("\\", "/"),
        "top_open": top.get("id"),
        "rank": top.get("rank"),
        "hint": top.get("gate_hint", ""),
    }


def build_plan(goal: str, answers: dict[str, str] | None = None,
               *, seat: str = "local", provider: str = "auto") -> dict[str, Any]:
    """Build a plan object from the stated goal + optional clarifying answers."""
    answers = answers or {}
    plan_id = f"plan_{_slug(goal)}_{uuid.uuid4().hex[:6]}"
    return {
        "schema": SCHEMA,
        "plan_id": plan_id,
        "goal": (goal or "").strip(),
        "clarified_goal": answers.get("clarified_goal", "").strip(),
        "scope": {
            "in": [s.strip() for s in answers.get("scope_in", "").split(",") if s.strip()],
            "out": [s.strip() for s in answers.get("scope_out", "").split(",") if s.strip()],
        },
        "success_checks": [
            s.strip() for s in answers.get("success_checks", "").split(",") if s.strip()
        ],
        "seat": seat,
        "provider": provider,
        "est_tokens": answers.get("est_tokens", "medium"),
        "steps": [s.strip() for s in answers.get("steps", "").split(";") if s.strip()],
        "open_questions": [
            s.strip() for s in answers.get("open_questions", "").split(";") if s.strip()
        ],
        "signals": _signals(goal),
        "status": "draft",
        "created": _utc(),
    }


def save_plan(plan: dict[str, Any]) -> Path:
    PLANS.mkdir(parents=True, exist_ok=True)
    path = PLANS / f"{plan['plan_id']}.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_plan(plan_id: str) -> dict[str, Any] | None:
    path = PLANS / f"{plan_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_plans() -> list[dict[str, Any]]:
    if not PLANS.is_dir():
        return []
    out = []
    for p in sorted(PLANS.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def set_status(plan_id: str, status: str) -> dict[str, Any] | None:
    plan = load_plan(plan_id)
    if not plan:
        return None
    plan["status"] = status
    save_plan(plan)
    return plan


def plan_gate(goal: str) -> dict[str, Any]:
    """Return a gate result: either 'skip' (small task) or a draft plan + questions.

    When the gate fires, it anchors the clarifying round against the top open
    priority from the store (one sharp question, not open-ended).
    """
    if not should_plan(goal):
        return {"ok": True, "gate": "skip", "goal": goal}
    plan = build_plan(goal)
    save_plan(plan)
    hint = priority_hint(goal)
    return {
        "ok": True,
        "gate": "plan",
        "plan": plan,
        "priority_hint": hint,
        "question": (
            f"Goal '{goal}' is ambiguous/expensive. "
            + (f"Top open priority is {hint.get('top_open')} (rank {hint.get('rank')}). "
               f"{hint.get('hint', '')} "
               if hint else "")
            + "Is this goal that priority, or a new one? Answer once, then we go."
        ),
    }
