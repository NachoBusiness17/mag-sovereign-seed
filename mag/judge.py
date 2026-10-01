"""Decide Mag action from sensed state (heuristic + optional small model)."""
from __future__ import annotations

from typing import Any

from llm import chat, extract_json
from config import PROMPTS_DIR


def judge(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return action dict: assigned|attention|escalate|idle."""
    pol = snapshot.get("policy") or {}
    assigned = snapshot.get("assigned") or []
    if assigned:
        item = assigned[0]
        return {
            "action": "assigned",
            "reason": "unchecked [mag]/[assign] todo",
            "goal": item["goal"],
            "todo_raw": item["raw"],
            "attention_text": "",
        }

    pending = snapshot.get("pending_handoffs") or []
    att_cfg = pol.get("attention") if isinstance(pol.get("attention"), dict) else {}
    # heuristic attention
    reasons = []
    if pending and att_cfg.get("unread_handoff", True):
        reasons.append(f"{len(pending)} handoff(s) awaiting Grok/result: {pending[0]}")
    live_age = snapshot.get("live_age_minutes")
    stale_m = 45
    if isinstance(att_cfg, dict) and "live_session_stale_minutes" in str(att_cfg):
        pass
    if live_age is not None and live_age > 45 and snapshot.get("open_todos"):
        reasons.append(
            f"live board ~{int(live_age)}m old with {len(snapshot['open_todos'])} open todos"
        )
    working = (snapshot.get("working_preview") or "").lower()
    if "open" in working and snapshot.get("open_todos"):
        reasons.append("working.md has open loops and unchecked todos")

    # Try model for nuance when no assigned work
    model_decision = _model_judge(snapshot)
    if model_decision and model_decision.get("action") in {
        "attention",
        "escalate",
        "idle",
        "assigned",
    }:
        # never invent assigned if no todos
        if model_decision["action"] == "assigned" and not assigned:
            model_decision["action"] = "idle"
        if model_decision["action"] == "attention" and not model_decision.get("attention_text"):
            model_decision["attention_text"] = model_decision.get("reason") or "check board"
        # never free-escalate without priority tag (L2 budget gate also in act)
        if model_decision["action"] == "escalate":
            from mag.lanes import text_has_priority

            blob = f"{model_decision.get('goal') or ''}\n{model_decision.get('reason') or ''}"
            if not text_has_priority(blob):
                model_decision["action"] = "attention"
                model_decision["attention_text"] = (
                    model_decision.get("attention_text")
                    or "Model wanted Grok escalate without [priority]/[grok] — review Board; tag todo if real."
                )
        return model_decision

    if reasons:
        return {
            "action": "attention",
            "reason": "; ".join(reasons),
            "goal": "",
            "attention_text": _format_attention(reasons, snapshot),
        }

    return {
        "action": "idle",
        "reason": "no assigned work; no high-signal attention",
        "goal": "",
        "attention_text": "",
    }


def _model_judge(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    system = (PROMPTS_DIR / "mag.txt").read_text(encoding="utf-8") if (PROMPTS_DIR / "mag.txt").is_file() else (
        "JSON only: {action,reason,goal,attention_text}"
    )
    user = f"""Sense snapshot (truncated):
assigned={snapshot.get('assigned')}
open_todos={snapshot.get('open_todos')[:8]}
pending_handoffs={snapshot.get('pending_handoffs')[:5]}
live_age_minutes={snapshot.get('live_age_minutes')}
live_preview:
{(snapshot.get('live_preview') or '')[:1500]}
working_preview:
{(snapshot.get('working_preview') or '')[:800]}

Decide one action JSON:
{{"action":"assigned|attention|escalate|idle","reason":"...","goal":"...","attention_text":"..."}}
Prefer idle over noise. Attention only if operator should look now.
"""
    try:
        # clerk role (small model) — explicit multi-model map
        raw = chat("clerk", system, user, temperature=0.1)
        data = extract_json(raw)
        if not data:
            return None
        return {
            "action": str(data.get("action") or "idle").lower(),
            "reason": str(data.get("reason") or ""),
            "goal": str(data.get("goal") or ""),
            "attention_text": str(data.get("attention_text") or ""),
        }
    except Exception:
        return None


def _format_attention(reasons: list[str], snapshot: dict[str, Any]) -> str:
    lines = [
        "## Mag attention",
        "",
        f"- **when:** {snapshot.get('ts')}",
        "",
        "### Why",
    ]
    for r in reasons:
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "### Suggested",
            "- Open `memory/live_from_grok.md` and `memory/working.md`",
            "- Clear or assign todos in `queue/todo.md` with `[mag]`",
            "- Ingest finished handoffs: `python main.py ingest <id>`",
            "",
        ]
    )
    return "\n".join(lines)
