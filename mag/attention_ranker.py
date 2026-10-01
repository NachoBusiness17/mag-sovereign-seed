"""Transparent, safety-bounded ranking for the operator's attention.

This is deliberately not an LLM call.  Mag first makes the ranking inspectable
and dogfoods operator feedback; a learned ranker may later reorder ordinary
items, but deterministic rules always retain control of blockers and failures.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

FEEDBACK_PATH = ROOT / "memory" / "attention_feedback.jsonl"
ALLOWED_SIGNALS = {"useful", "wallpaper", "pin", "mute", "acted"}


def _repo_snapshot() -> dict[str, Any]:
    from mag.repo_readiness import repo_readiness

    return repo_readiness()


def _task_rows() -> list[dict[str, Any]]:
    from mag.orchestrator import list_tasks_live

    return list_tasks_live(limit=30)


def _roadmap_snapshot() -> dict[str, Any]:
    from mag.roadmap_runner import status

    return status()


def _inbox_snapshot() -> dict[str, Any]:
    from mag.operator_inbox import status

    return status()


def _feedback() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not FEEDBACK_PATH.is_file():
        return out
    try:
        rows = FEEDBACK_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
    except OSError:
        return out
    for row in rows:
        try:
            event = json.loads(row)
        except json.JSONDecodeError:
            continue
        item_id, signal = str(event.get("item_id") or ""), str(event.get("signal") or "")
        if item_id and signal in ALLOWED_SIGNALS:
            out.setdefault(item_id, []).append(signal)
    return out


def _find_cast(cast_id: str) -> dict[str, Any] | None:
    """The first settled ledger row carrying this cast_id, else None.

    Full-file scan on purpose: a bounded window would let a retried POST
    double-append once enough newer trades pushed the original row out of the
    window. The ledger is tiny (zero trades in its first 54 days, w4-03), so
    total recall is cheap and the settle-once guarantee is unconditional.
    """
    if not FEEDBACK_PATH.is_file():
        return None
    try:
        rows = FEEDBACK_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for row in rows:
        try:
            event = json.loads(row)
        except json.JSONDecodeError:
            continue
        if str(event.get("cast_id") or "") == cast_id:
            return event
    return None


def record_feedback(
    item_id: str, signal: str, *, source: str = "dashboard", cast_id: str = ""
) -> dict[str, Any]:
    """Append one trade to the ledger; settle once per cast_id.

    cast_id is the idempotency key: a retried POST (network retry, double
    click) replays the original trade instead of appending a second row
    (zero-double-append, pinned by tests/test_attention_feedback_ledger.py).
    A cast without cast_id is a distinct trade every time (legacy semantics).
    """
    item_id, signal = item_id.strip(), signal.strip().lower()
    if not item_id:
        return {"ok": False, "error": "item_id required"}
    if signal not in ALLOWED_SIGNALS:
        return {"ok": False, "error": f"signal must be one of {sorted(ALLOWED_SIGNALS)}"}
    cast_id = cast_id.strip()
    if cast_id:
        prior = _find_cast(cast_id)
        if prior is not None:
            return {"ok": True, "duplicate": True, "event": prior}
    event = {
        "schema": "attention_feedback.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "item_id": item_id[:240],
        "signal": signal,
        "source": source[:80],
    }
    if cast_id:
        event["cast_id"] = cast_id[:120]
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {"ok": True, "event": event}


def read_feedback() -> dict[str, list[str]]:
    """Public read path: the trade ledger mapped item_id -> [signals ...].

    The reading logic has existed since the ranker landed (2026-08-06) as the
    private `_feedback`, already consumed by build_ranked_attention; what was
    missing was trades to read (w4-03: attention_feedback.jsonl ABSENT, zero
    trades ever) and this named surface for every other consumer (audits,
    organ reputation) to read real casts from.
    """
    return _feedback()


def _item(
    item_id: str, kind: str, headline: str, meaning: str, action: str, *,
    actionability: float, impact: float, urgency: float, centrality: float,
    novelty: float = 0.4, uncertainty: float = 0.2, redundancy: float = 0.0,
    wallpaper_cost: float = 0.0, hard_band: str | None = None,
    evidence: list[str] | None = None, controls: list[str] | None = None,
) -> dict[str, Any]:
    raw = (
        3 * actionability + 2.5 * impact + 2 * urgency + 1.5 * centrality
        + 1.2 * novelty + uncertainty - 1.5 * redundancy - wallpaper_cost
    )
    score = max(0, min(100, round(raw / 11.2 * 100)))
    band = "P1" if score >= 72 else "P2" if score >= 52 else "P3" if score >= 32 else "P4"
    if hard_band:
        band = hard_band
    return {
        "id": item_id,
        "kind": kind,
        "headline": headline,
        "meaning": meaning,
        "operator_action": action,
        "score": score,
        "band": band,
        "hard_rule": bool(hard_band),
        "rank_reason": (
            f"action {actionability:.1f} · impact {impact:.1f} · urgency {urgency:.1f} · "
            f"dependency {centrality:.1f}"
        ),
        "evidence": evidence or [],
        "controls": controls or ["inspect", "direct"],
    }


def _collect() -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    sources: list[str] = []
    road_next: dict[str, Any] = {}
    try:
        road_next = _roadmap_snapshot().get("next") or {}
        sources.append("version roadmap runner")
    except Exception:
        pass
    try:
        repo = _repo_snapshot()
        sources.append("git repository snapshot")
        blockers = [str(x) for x in repo.get("blockers") or []]
        if not repo.get("handoff_ready", False):
            items.append(_item(
                "repo:handoff", "repository", "Repository is not ready for an instant handoff",
                "; ".join(blockers) or "Git state could not be verified.",
                "Resolve the repository blockers before another agent takes over.",
                actionability=1, impact=.95, urgency=.9, centrality=1, hard_band="P0",
                evidence=[f"branch: {repo.get('branch') or 'unknown'}", *blockers],
                controls=["inspect", "direct"],
            ))
        else:
            items.append(_item(
                "repo:ready", "repository", "Repository is ready to hand off",
                f"{repo.get('branch')} tracks {repo.get('upstream')}; no local blockers were found.",
                "No action required; keep this as evidence.",
                actionability=.05, impact=.55, urgency=.05, centrality=.8,
                redundancy=.5, wallpaper_cost=.4, evidence=[str(repo.get("head") or "")],
            ))
    except Exception as exc:
        items.append(_item(
            "repo:error", "repository", "Repository readiness could not be read", str(exc),
            "Inspect Git before dispatching another worker.", actionability=1, impact=1,
            urgency=1, centrality=1, hard_band="P0",
        ))

    try:
        tasks = _task_rows()
        sources.append("orchestrator task records")
        active = [t for t in tasks if t.get("status") in {"running", "queued", "paused"}]
        passed_gates = {str(x) for x in road_next.get("passed_gates") or []}
        done_tags = {str(t.get("tag") or "") for t in tasks if t.get("status") == "done"}
        maintenance_markers = ("soak", "self-test", "self_test", "heal", "smoke", "pytest", "[improve]")
        failed = [
            t for t in tasks
            if t.get("status") in {"failed", "timeout", "stalled", "died"}
            and str(t.get("tag") or "") not in done_tags
            and not any(gate and gate in str(t.get("tag") or "") for gate in passed_gates)
            and not any(marker in (str(t.get("tag") or "") + " " + str(t.get("goal") or "")).lower() for marker in maintenance_markers)
        ]
        for task in failed[:3]:
            tid, state = str(task.get("task_id") or "unknown"), str(task.get("status"))
            goal = str(task.get("goal") or task.get("tag") or "worker task")
            items.append(_item(
                f"task:{tid}", "worker", f"Worker {state}: {goal[:90]}",
                str(task.get("detail") or "The worker stopped without a verified result."),
                "Review its evidence, then retry, steer, or supersede it.",
                actionability=1, impact=.8, urgency=.75, centrality=.75, hard_band="P1",
                evidence=[tid, str(task.get("log") or "")], controls=["inspect", "direct", "acted"],
            ))
        if active:
            for task in active[:4]:
                tid, state = str(task.get("task_id") or "unknown"), str(task.get("status"))
                goal = str(task.get("goal") or task.get("tag") or "worker task")
                items.append(_item(
                    f"task:{tid}", "worker", f"{state.title()}: {goal[:100]}",
                    "A delegated worker currently owns this unit of work.",
                    "Monitor it; intervene only if evidence stalls or direction changes.",
                    actionability=.45, impact=.7, urgency=.55, centrality=.7, hard_band="P2",
                    evidence=[tid], controls=["inspect", "direct"],
                ))
    except Exception as exc:
        items.append(_item(
            "tasks:error", "worker", "Worker state could not be read", str(exc),
            "Inspect the orchestrator before starting overlapping work.", actionability=.9,
            impact=.8, urgency=.7, centrality=.8, hard_band="P1",
        ))

    try:
        inbox = _inbox_snapshot()
        sources.append("operator guidance inbox")
        pending_n = int(inbox.get("pending_n") or 0)
        if pending_n:
            items.append(_item(
                "inbox:pending", "guidance", f"{pending_n} operator instruction(s) await a checkpoint",
                "The agent has not yet absorbed your queued direction.",
                "Let the current worker reach a checkpoint, or open Run to steer it.",
                actionability=.75, impact=.8, urgency=.65, centrality=.8, hard_band="P1",
                evidence=[str(x.get("text") or "")[:160] for x in inbox.get("pending", [])[:3]],
                controls=["inspect", "direct"],
            ))
    except Exception:
        pass

    try:
        road = road_next
        if road.get("ok"):
            gate = str((road.get("gate") or {}).get("id") or "next gate")
            items.append(_item(
                f"roadmap:{road.get('version')}:{gate}", "roadmap",
                f"Next roadmap gate: {gate.replace('_', ' ')}",
                str(road.get("meaning") or "The roadmap selected the next unfinished gate."),
                "Review the frozen contract, then dispatch the cheapest capable worker.",
                actionability=.9, impact=.85, urgency=.55, centrality=.9, hard_band="P2",
                evidence=[str(x) for x in road.get("sources") or []],
                controls=["inspect", "direct", "acted"],
            ))
    except Exception:
        pass
    return items, sources


def build_ranked_attention(*, limit: int = 12) -> dict[str, Any]:
    items, sources = _collect()
    feedback = _feedback()
    band_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
    for item in items:
        signals = feedback.get(item["id"], [])
        if "pin" in signals and not item["hard_rule"]:
            item["band"], item["score"] = "P1", max(80, item["score"])
            item["rank_reason"] += " · operator pinned"
        elif "mute" in signals and not item["hard_rule"]:
            item["band"], item["score"] = "P5", 0
            item["rank_reason"] += " · operator muted"
        else:
            item["score"] = max(0, min(100, item["score"] + 4 * signals.count("useful") - 8 * signals.count("wallpaper")))
        item["feedback"] = signals[-5:]
    items.sort(key=lambda x: (band_order.get(x["band"], 9), -int(x["score"]), x["headline"]))
    counts = {band: sum(1 for x in items if x["band"] == band) for band in band_order}
    return {
        "ok": True,
        "schema": "ranked_attention.v1",
        "ranker": "transparent-safety-bounded-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Rules promote blockers and failures; feedback may reorder ordinary items but cannot hide hard rules.",
        "counts": counts,
        "items": items[:max(1, min(int(limit), 50))],
        "sources": sources,
    }
