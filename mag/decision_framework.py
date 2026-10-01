"""Decision framework — Mirror + behavioral history → routing + escalation.

Layers (do not confuse):
  - **Breadcrumbs** (`operator_inbox`) — operator interference; deferred notes on the path
  - **Steer** (`!steer`) — emergency mid-round override
  - **This module** — framework decisions from compass, case law, behavioral mining,
    session patterns → route hints, tips, loop escalation (smarter seat, not more tokens)

Schema: decision_framework.v1
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

EVENTS_PATH = ROOT / "logs" / "behavioral_events.jsonl"
DECISIONS_PATH = ROOT / "memory" / "decisions_log.jsonl"
SESSIONS_DIR = ROOT / "memory" / "agent_sessions"
BEHAVIORAL_DAILY = ROOT / "memory" / "improve" / "daily"

# Seat tier order for loop escalation (dumb → smart)
_ESCALATION_LADDER = (
    ("ollama", "deepseek"),
    ("groq", "deepseek"),
    ("openrouter", "deepseek"),
    ("deepseek", "deepseek_overmind"),
    ("deepseek_overmind", "grok_tui"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, *, tail: int = 100) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-tail:]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                rows.append(o)
        except json.JSONDecodeError:
            continue
    return rows


def surface_tips(*, goal: str = "", limit: int = 6) -> list[dict[str, str]]:
    """Tips/tools from behavioral history — injected into packs and loop recovery."""
    tips: list[dict[str, str]] = []
    g = (goal or "").lower()

    # Latest behavioral leaf themes
    try:
        from mag.governance import _latest_behavioral_leaf

        leaf = _latest_behavioral_leaf()
        for t in (leaf.get("themes") or [])[:4]:
            tips.append({
                "id": str(t.get("id") or "theme"),
                "tip": str(t.get("title") or ""),
                "avoid": str(t.get("avoid") or "")[:200],
                "source": "behavioral_leaf",
            })
    except Exception:
        pass

    # Recent collapse/degenerate events → concrete avoids
    kinds = Counter()
    for ev in _read_jsonl(EVENTS_PATH, tail=60):
        k = str(ev.get("kind") or "")
        kinds[k] += 1
        if k in ("collapse", "degenerate", "tool_fail") and len(tips) < limit:
            detail = str(ev.get("detail") or "")[:120]
            tool = str(ev.get("tool") or "")
            tips.append({
                "id": f"event-{k}",
                "tip": f"Avoid repeating: {detail}" if detail else f"Recent {k}",
                "avoid": f"tool={tool}" if tool else "",
                "source": "behavioral_events",
            })

    # Case law patterns (steer outcomes)
    for d in _read_jsonl(DECISIONS_PATH, tail=40):
        outcome = str(d.get("outcome") or "").lower()
        steer = str(d.get("steer_input") or d.get("context") or "")[:100]
        if any(x in outcome for x in ("collapse", "loop", "degenerate", "failed", "empty")):
            tips.append({
                "id": "case-law",
                "tip": steer or str(d.get("context") or "")[:80],
                "avoid": str(d.get("outcome") or "")[:160],
                "source": "decisions_log",
            })
            if len(tips) >= limit:
                break

    # Goal-specific skill hints
    if any(k in g for k in ("fix", "patch", "implement", "refactor")):
        tips.append({
            "id": "patch-verify",
            "tip": "Use patch-verify weave: read → single write → verify — not 18 grep loops",
            "avoid": "identical tool calls",
            "source": "skills",
        })

    # Failure KB — recurring tool/collapse patterns
    try:
        from mag.failure_kb import surface_hits

        for hit in surface_hits(goal=g, limit=3):
            if len(tips) >= limit:
                break
            tips.append(hit)
    except Exception:
        pass

    # Dedupe by tip text
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for t in tips:
        key = t.get("tip", "")
        if key and key not in seen:
            seen.add(key)
            out.append(t)
        if len(out) >= limit:
            break
    return out


def format_tips_block(tips: list[dict[str, str]], *, max_chars: int = 900) -> str:
    if not tips:
        return ""
    lines = ["[DECISION FRAMEWORK — tips from your history (not chat heat)]"]
    for t in tips:
        lines.append(f"- {t.get('id', '?')}: {t.get('tip', '')}")
        if t.get("avoid"):
            lines.append(f"  avoid: {t['avoid'][:140]}")
    text = "\n".join(lines)
    return text[:max_chars]


def build_framework_context(*, goal: str = "", reason: str = "route") -> str:
    """Compass + behavioral tips for injection."""
    from mag.compass import build_compass

    tips = surface_tips(goal=goal)
    tips_block = format_tips_block(tips)
    compass = build_compass(reason=reason if reason in ("input", "steer", "loop") else "loop")
    parts = [compass]
    if tips_block:
        parts.append(tips_block)
    return "\n\n".join(parts)


def decide(
    goal: str,
    *,
    depth: str | None = None,
    include_breadcrumbs: bool = True,
) -> dict[str, Any]:
    """Framework decision: route + tips + interference layer status."""
    from mag.router import route

    routed = route(goal, depth=depth)
    tips = surface_tips(goal=goal)
    interference: dict[str, Any] = {"breadcrumbs_pending": 0, "layer": "operator_inbox"}
    if include_breadcrumbs:
        try:
            from mag.operator_inbox import status as inbox_status

            interference["breadcrumbs_pending"] = int(inbox_status().get("pending_n") or 0)
        except Exception:
            pass

    return {
        "ok": routed.get("ok", False),
        "schema": "decision.v1",
        "goal": (goal or "")[:300],
        "route": routed,
        "tips": tips,
        "tips_block": format_tips_block(tips),
        "interference": interference,
        "framework": {
            "compass_on_loop": True,
            "behavioral_synth": str(BEHAVIORAL_DAILY / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-behavioral.md"),
        },
    }


def _next_escalation_provider(current: str) -> tuple[str, str]:
    """Return (provider, action_kind) for loop escalation."""
    cur = (current or "ollama").strip().lower()
    for low, high in _ESCALATION_LADDER:
        if cur == low:
            return high, "queue_delegate"
    if cur == "deepseek_overmind":
        return "grok_tui", "file_for_grok"
    return "deepseek", "queue_delegate"


def escalate_on_loop(
    *,
    goal: str,
    provider: str,
    tool: str = "",
    detail: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Dumb seat stuck in a loop → stop burning tokens; hand off to smarter tier."""
    from mag.compass import record_decision
    from mag.operator_inbox import log_behavioral_event

    log_behavioral_event(
        kind="collapse",
        detail=detail or f"loop on {tool}",
        tool=tool or None,
        phase="escalate",
        session_id=session_id,
        provider=provider,
    )
    record_decision(
        "loop escalation",
        detail[:200] or f"{tool} loop",
        "escalate to smarter seat — stop token bleed",
    )

    target, action = _next_escalation_provider(provider)
    # In-the-moment classification: feed this escalation into the local pile so
    # the overnight job (tools/pile_classify.py) classifies + folds it later.
    try:
        from mag.state_snapshot import capture_summary

        capture_summary(
            goal=goal, outcome="escalated", tier=f"{provider}->{target}",
            kind="escalation", source="decision_framework", session_id=session_id,
            lessons=[detail[:200] or f"loop on {tool}"],
        )
    except Exception:
        pass
    out: dict[str, Any] = {
        "ok": True,
        "schema": "escalation.v1",
        "from_provider": provider,
        "target": target,
        "action": action,
    }

    if action == "file_for_grok":
        from mag.lanes import can_escalate_grok

        allowed, why = can_escalate_grok(
            goal=f"[priority] loop recovery: {goal[:200]}",
            force=False,
        )
        if not allowed:
            target = "deepseek_overmind"
            action = "queue_delegate"
            out["grok_blocked"] = why
        else:
            try:
                from mag.context_pack import build_context_pack, format_context_pack_text

                pack = build_context_pack(max_brief=700, max_live=300)
                out["pack_excerpt"] = format_context_pack_text(pack, max_chars=2000)
            except Exception as e:
                out["pack_error"] = str(e)[:120]
            out["hint"] = "Paste pack into Grok TUI with [priority] — local seat stopped looping"
            return out

    if action == "queue_delegate":
        try:
            from mag.orchestrator import enqueue

            esc_goal = (
                f"[loop-escalation from {provider}] {goal[:350]}\n\n"
                f"Context: tool={tool} detail={detail[:200]}\n"
                f"Use framework tips — do not repeat the failed tool pattern."
            )
            rec = enqueue(esc_goal, provider=target, tag="loop-escalate")
            out["queue_id"] = rec.get("queue_id") or rec.get("id")
            out["hint"] = f"Queued on {target} — local loop stopped"
        except Exception as e:
            out["ok"] = False
            out["error"] = str(e)[:200]
    return out


def session_loop_patterns(*, limit: int = 20) -> list[dict[str, Any]]:
    """Mine agent_sessions for repeated tool patterns (lightweight)."""
    if not SESSIONS_DIR.is_dir():
        return []
    patterns: Counter[str] = Counter()
    for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        msgs = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(msgs, list):
            continue
        for m in msgs:
            if not isinstance(m, dict):
                continue
            for tc in m.get("tool_calls") or []:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                name = fn.get("name") if isinstance(fn, dict) else None
                if name:
                    patterns[str(name)] += 1
    return [{"tool": k, "count": v} for k, v in patterns.most_common(8)]
