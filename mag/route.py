"""Grok-facing router: classify with clerk; optional local worker answer.

Keeps tokens low: short goal in, compact JSON out.
"""
from __future__ import annotations

from typing import Any

from llm import chat, extract_json
from mag.memory_events import emit_route_decision
from models.registry import model_for

# Lightweight echo-detection counter: bumped when the clerk reply is invalid and
# the keyword heuristic decides (reason="heuristic:fallback"). Hot-path cheap.
_FALLBACKS = 0


def route_goal(
    goal: str,
    *,
    run_local: bool = False,
    force_lane: str | None = None,
) -> dict[str, Any]:
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    # Heuristic first (no model) for obvious local scut — saves clerk tokens
    g = goal.lower()
    heuristic = None
    if any(k in g for k in ("what was i", "what was i doing", "recall", "brief", "session", "open loop")):
        heuristic = "local_recall"
    elif any(k in g for k in ("doctor", "status", "health", "multi-smoke", "smoke", "models")):
        heuristic = "local_ops"
    elif any(k in g for k in ("implement", "refactor", "architecture", "design system", "multi-file")):
        heuristic = "grok"
    elif len(goal) < 80 and any(k in g for k in ("list", "show", "read ", "cat ")):
        heuristic = "local_ops"

    lane = force_lane
    reason = "forced"
    clerk_raw = None
    if not lane:
        if heuristic == "grok":
            lane, reason = "grok", "heuristic:hard"
        elif heuristic in ("local_recall", "local_ops"):
            lane, reason = "local", f"heuristic:{heuristic}"
        else:
            try:
                clerk_raw = chat(
                    "clerk",
                    'Route only. JSON: {"lane":"local|grok|wait","reason":"short"}',
                    f"Goal:\n{goal[:500]}\n\nlocal=Mag/Ollama can do it. grok=needs specialist here. wait=human.",
                    temperature=0.1,
                )
                data = extract_json(clerk_raw)
                lane = None
                if isinstance(data, dict):
                    raw_lane = data.get("lane")
                    if isinstance(raw_lane, str) and raw_lane.lower() in {"local", "grok", "wait"}:
                        lane = raw_lane.lower()
                if lane is None:
                    global _FALLBACKS
                    _FALLBACKS += 1
                    # clerk reply not valid JSON -> keyword heuristic fallback, never silent grok
                    if heuristic in ("local_recall", "local_ops"):
                        lane, reason = "local", "heuristic:fallback"
                    else:
                        lane, reason = "grok", "heuristic:fallback"
                else:
                    reason = str(data.get("reason") or "clerk")[:200]
            except Exception as e:
                lane, reason = "grok", f"clerk_fail:{e}"

    out: dict[str, Any] = {
        "ok": True,
        "goal": goal[:300],
        "lane": lane,
        "reason": reason,
        "clerk_model": model_for("clerk"),
        "worker_model": model_for("worker"),
        "clerk_raw": (clerk_raw or "")[:300] if clerk_raw else None,
        "fallback_count": _FALLBACKS,
        "local_result": None,
        "hint": "",
    }

    if lane == "wait":
        out["hint"] = "Ask the operator; do not auto-run."
        try:
            emit_route_decision(
                goal=goal,
                lane=str(out.get("lane") or "wait"),
                reason=str(out.get("reason") or ""),
                clerk_model=str(out.get("clerk_model") or ""),
                fallback_count=int(out.get("fallback_count") or 0),
            )
        except Exception:
            pass
        return out

    if lane == "grok":
        out["hint"] = "Stay in Grok TUI. Use context-pack for memory, not full chat."
        try:
            emit_route_decision(
                goal=goal,
                lane=str(out.get("lane") or "grok"),
                reason=str(out.get("reason") or ""),
                clerk_model=str(out.get("clerk_model") or ""),
                fallback_count=int(out.get("fallback_count") or 0),
            )
        except Exception:
            pass
        return out

    # local
    if run_local or heuristic in ("local_recall", "local_ops"):
        out["local_result"] = _run_local(goal, heuristic or "local")
        out["hint"] = "Local done — Grok should summarize in few lines only."
    else:
        out["hint"] = (
            "Lane=local. Re-run with --local to execute, or: "
            'python main.py ask "…" / brief / doctor'
        )
    try:
        emit_route_decision(
            goal=goal,
            lane=str(out.get("lane") or "local"),
            reason=str(out.get("reason") or ""),
            clerk_model=str(out.get("clerk_model") or ""),
            fallback_count=int(out.get("fallback_count") or 0),
        )
    except Exception:
        pass
    return out


def _run_local(goal: str, kind: str) -> dict[str, Any]:
    g = goal.lower()
    try:
        if "smoke" in g or "multi-smoke" in g:
            from models.multi_smoke import run_multi_smoke

            r = run_multi_smoke()
            return {"action": "multi_smoke", "ok": r.get("ok"), "verdict": r.get("verdict"), "models": r.get("models_seen")}
        if "doctor" in g or "health" in g or g.strip() in {"status", "mag status"}:
            from mag.health import sanity

            s = sanity()
            return {
                "action": "doctor",
                "status": s.get("status"),
                "live_stale": (s.get("recording") or {}).get("live_stale"),
            }
        if "models" in g and "model" in g.replace("multi", ""):
            from models.registry import inventory

            return {"action": "models", "inventory": inventory()}
        # default: ask biographer
        from mag.ask import ask

        r = ask(goal, use_llm=True)
        return {
            "action": "ask",
            "ok": r.get("ok"),
            "answer": (r.get("answer") or "")[:1500],
            "used_llm": r.get("used_llm"),
        }
    except Exception as e:
        return {"action": "error", "ok": False, "error": str(e)}
