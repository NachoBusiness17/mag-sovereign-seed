"""Execute Mag decisions."""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit import log_event
from config import ROOT
from harness.grok_cli import escalate_via_harness, harness_available
from mag.policy import load_policy, resolve



# ---------------------------------------------------------------------------
# Attention surface contract (2026-09-29, gala wave5 attention-channel lane).
#
# memory/attention.md is one file with two regions:
#   1. a newest-first RECORD FLOOD: biographer session pings and daemon pings,
#      prepended at the head and byte-capped;
#   2. a PRESERVED ALERT TAIL below ATTENTION_ALERT_SENTINEL: bottom-appenders
#      (scripts/census_patrol_daily.ps1 Add-Content at :79/:109/:150/:170,
#      mag/improve.py mode "a" at :535) write here.
# Before this contract the flood prepended while the alerts appended, so the
# bottom of the file was the eviction zone and the guillotine ran backwards:
# biography.py prev[:40000] beheaded the 2026-09-26 COLLECT-DRIFT and
# 2026-09-28 fleet-task-doctor patrol alerts within hours of their append
# (watch/inbox/burn_reset_20260927/flash50/w4-09.md). Eviction now runs
# whole-block and can never touch the alert tail.
ATTENTION_ALERT_SENTINEL = "<!-- attention:alerts-preserved-below -->"
ATTENTION_BLOCK_SEP = "\n---\n"


def split_preserved_alerts(prev: str) -> tuple[str, str]:
    """Split an attention.md body into (evictable records, preserved alerts)."""
    idx = prev.find(ATTENTION_ALERT_SENTINEL)
    if idx < 0:
        return prev, ""
    return prev[:idx], prev[idx:]


def evict_for_prepend(prev: str, note: str, cap: int) -> str:
    """Return the new attention.md body after prepending `note` under `cap` bytes.

    Records evict newest-first, whole-block at ATTENTION_BLOCK_SEP boundaries
    (the old prev[:cap] slice ended mid-record and fed consumers headless
    half-blocks). The preserved alert tail below ATTENTION_ALERT_SENTINEL is
    never evicted and never sliced; it is seeded on first write so bottom-
    appended patrol alerts survive every later record flood.
    """
    evictable, preserved = split_preserved_alerts(prev)
    if not preserved:
        preserved = f"\n{ATTENTION_ALERT_SENTINEL}\n"
    body = note + evictable
    budget = max(cap - len(preserved), 0)
    if len(body) > budget:
        cut = body.rfind(ATTENTION_BLOCK_SEP, 0, budget + 1)
        if cut <= len(note):
            # No whole evictable record fits; keep only the new note.
            cut = len(note)
        body = body[:cut]
    return body + preserved


def bump_attention_count(delta: int = 1) -> tuple[str, int]:
    """Advance the daily attention meter watch/attention_count_day.txt.

    Format stays "YYYY-MM-DD N": mag/daemon.py:_attention_over_cap reads it.
    A stale day or an unparsable file restarts at 0 instead of freezing. Every
    writer to an operator attention surface meters here (the flood pays rent);
    only the push path is capped, filing is unconditional.
    """
    count_path = ROOT / "watch" / "attention_count_day.txt"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0
    if count_path.is_file():
        try:
            d, c = count_path.read_text(encoding="utf-8").strip().split()
            if d == day:
                count = int(c)
        except (ValueError, OSError):
            count = 0
    count += max(delta, 0)
    try:
        count_path.parent.mkdir(parents=True, exist_ok=True)
        count_path.write_text(f"{day} {count}", encoding="utf-8")
    except OSError as exc:  # metering is best-effort; the attention action still landed
        print(f"[act] attention counter write failed: {exc}", file=sys.stderr)
    return day, count


def act(decision: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    action = decision.get("action") or "idle"
    pol = snapshot.get("policy") or load_policy()

    if action == "assigned":
        return _do_assigned(decision, pol)
    if action == "attention":
        return _do_attention(decision, pol)
    if action == "escalate":
        return _do_escalate(decision, snapshot, pol)
    return {"ok": True, "action": "idle", "detail": decision.get("reason") or "idle"}


def _do_assigned(decision: dict[str, Any], pol: dict) -> dict[str, Any]:
    goal = decision.get("goal") or ""
    if not goal:
        return {"ok": False, "action": "assigned", "error": "empty goal"}

    thread_id = str(uuid.uuid4())
    from graph import default_graph  # lazy: only assigned path needs LangGraph
    app = default_graph()
    init = {
        "goal": goal,
        "messages": [],
        "tier": "T2",
        "plan": [],
        "step_i": 0,
        "tool_trace": [],
        "critique": "",
        "route": "plan",
        "handoff_id": None,
        "status": "running",
        "success_checks": ["Assigned mag todo addressed with tool evidence"],
        "last_result": "",
        "retry_count": 0,
        "thread_id": thread_id,
    }
    final = app.invoke(init, config={"configurable": {"thread_id": thread_id}})
    status = final.get("status")
    # mark todo done if status done
    if status == "done" and decision.get("todo_raw"):
        _check_off_todo(decision["todo_raw"], pol)
    # if graph escalated, try harness
    if status == "escalated" and pol.get("use_grok_harness"):
        esc = _do_escalate(
            {
                "action": "escalate",
                "goal": goal,
                "reason": "graph escalated",
                "attention_text": "",
            },
            {"live_preview": final.get("last_result"), "policy": pol},
            pol,
        )
        return {
            "ok": True,
            "action": "assigned+escalate",
            "graph_status": status,
            "last_result": (final.get("last_result") or "")[:2000],
            "harness": esc,
        }
    return {
        "ok": status in {"done", "escalated", "waiting"},
        "action": "assigned",
        "graph_status": status,
        "last_result": (final.get("last_result") or "")[:2000],
        "critique": (final.get("critique") or "")[:800],
    }


def _do_attention(decision: dict[str, Any], pol: dict) -> dict[str, Any]:
    path = resolve(pol.get("attention_path") or "memory/attention.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = decision.get("attention_text") or decision.get("reason") or "Mag ping"
    stamp = datetime.now(timezone.utc).isoformat()
    prev = path.read_text(encoding="utf-8") if path.is_file() else "# Mag attention\n"
    # prepend latest; the shared contract evicts whole records and preserves the
    # alert tail below the sentinel (see ATTENTION_ALERT_SENTINEL above)
    block = f"\n---\n\n### {stamp}\n\n{text}\n"
    path.write_text(evict_for_prepend(prev, block, 50000), encoding="utf-8")
    # daily count: records and pushes both meter; only the push is capped
    _day, count = bump_attention_count()
    max_a = int(pol.get("max_attention_per_day") or 8)
    if count > max_a:
        return {
            "ok": True,
            "action": "attention",
            "suppressed": True,
            "count_today": count,
            "detail": f"over daily cap {max_a}",
        }
    _toast_optional("Sovereign Mag", text[:180])
    return {"ok": True, "action": "attention", "path": str(path), "count_today": count}


def _do_escalate(decision: dict[str, Any], snapshot: dict, pol: dict) -> dict[str, Any]:
    import os

    from mag.lanes import can_escalate_grok, latest_brief_text, log_usage

    goal = decision.get("goal") or decision.get("reason") or "Mag escalate"
    force = bool(decision.get("force") or decision.get("force_grok"))
    allowed, why = can_escalate_grok(
        goal=goal,
        reason=str(decision.get("reason") or ""),
        force=force,
    )
    if not allowed:
        log_usage(
            lane="L0",
            action="escalate_blocked",
            detail=why,
            ok=False,
            meta={"goal": goal[:200]},
        )
        _journal(pol, f"L2 blocked: {why}")
        # degrade to attention so operator sees it
        return _do_attention(
            {
                "attention_text": (
                    f"**Grok escalate blocked** ({why}).\n\n"
                    f"Goal: {goal}\n\n"
                    "Tag todo with `[priority]` or `[grok]`, or raise budget in configs/lanes.yaml."
                ),
                "reason": why,
            },
            pol,
        )

    brief = latest_brief_text()
    context = (
        f"reason: {decision.get('reason')}\n"
        f"--- local brief (prefer this over raw chat) ---\n{brief[:3500]}\n"
        f"--- live ---\n{(snapshot.get('live_preview') or '')[:2000]}\n"
        f"--- working ---\n{(snapshot.get('working_preview') or '')[:1200]}"
    )
    use_harness = bool(pol.get("use_grok_harness")) and not os.environ.get("MAG_NO_HARNESS")
    if use_harness and harness_available():
        res = escalate_via_harness(
            goal=goal,
            context=context,
            cwd=ROOT,
            max_turns=int(pol.get("harness_max_turns") or 12),
            yolo=bool(pol.get("harness_yolo")),
            output_format=str(pol.get("harness_output") or "plain"),
        )
        log_event({"mag": "harness_escalate", **{k: res.get(k) for k in ("ok", "handoff_id", "exit_code")}})
        log_usage(
            lane="L2",
            action="escalate_harness",
            detail=goal[:200],
            ok=bool(res.get("ok")),
            meta={"handoff_id": res.get("handoff_id"), "budget_note": why},
        )
        _journal(pol, f"HARNESS escalate ok={res.get('ok')} id={res.get('handoff_id')} summary={res.get('summary')}")
        return {"ok": bool(res.get("ok")), "action": "escalate", "via": "grok-harness", **res}

    # fallback: file handoff via graph escalate node
    from agents.escalate_grok import escalate_grok_node

    state = {
        "goal": goal,
        "tier": "T3",
        "last_result": context[:2500],
        "critique": decision.get("reason") or "",
        "success_checks": ["Specialist result in queue/results"],
        "tool_trace": [],
        "brief": brief[:3500],
    }
    out = escalate_grok_node(state)
    log_usage(
        lane="L2",
        action="handoff",
        detail=goal[:200],
        ok=True,
        meta={"handoff_id": out.get("handoff_id"), "budget_note": why},
    )
    _journal(pol, f"FILE handoff {out.get('handoff_id')}")
    return {"ok": True, "action": "escalate", "via": "file-handoff", **out}


def _check_off_todo(raw_line: str, pol: dict) -> None:
    path = resolve(pol.get("todo_path") or "queue/todo.md")
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    # replace first matching unchecked line
    new_lines = []
    done = False
    for line in text.splitlines():
        if not done and line.strip() == raw_line.strip():
            new_lines.append(line.replace("- [ ]", "- [x]", 1))
            done = True
        else:
            new_lines.append(line)
    path.write_text("\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")


def _journal(pol: dict, line: str) -> None:
    path = resolve(pol.get("journal_path") or "memory/mag_journal.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {stamp} {line}\n")


def _toast_optional(title: str, msg: str) -> None:
    """Best-effort Windows toast; ignore failures."""
    try:
        import subprocess
        import sys

        if sys.platform != "win32":
            return
        # PowerShell balloon / toast via BurntToast not assumed — use msg-less log only
        # Write a side flag file for external notifiers
        flag = ROOT / "watch" / "attention_flag.txt"
        flag.write_text(f"{title}\n{msg}\n", encoding="utf-8")
    except Exception as exc:  # 2026-09-28 FW-46 silent-pass batch 2: the silent pass also killed the watch/attention_flag.txt side-channel with no trace when the write failed (STEAL_WAVE_FOLD_20260911: silent loss masquerading as health); best-effort stands, the reason is now named on stderr
        import sys
        print(f"[act] toast/attention-flag write failed: {exc}", file=sys.stderr)
