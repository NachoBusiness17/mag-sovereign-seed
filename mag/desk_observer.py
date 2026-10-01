"""Desk observer — steal protocol: Agent-as-Judge + DEBATE critic off the hot path.

Reads dialogue JSONL + canvas; scores alignment to sprint/knowns; injects steer
before the next seat wakes. Optional live DeepSeek critic (--live).

Steals from: LbMAS critic, AgentSwarm verifier, DEBATE devil's advocate, C3 text logs.

Schema: mag_desk_observer.v1
Trail: memory/runs/desk_observer_trail.jsonl
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_desk_observer.v1"
TRAIL = ROOT / "memory" / "runs" / "desk_observer_trail.jsonl"
OBSERVER_PROMPT = ROOT / "prompts" / "desk_observer.txt"

STEER_THRESHOLD = 0.55


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc(), "event": event, "schema": SCHEMA, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _steal_cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    from mag.coding_session_loop import load_config

    base = cfg if cfg and cfg.get("ok") else load_config()
    sp = base.get("steal_protocol") or {}
    if not isinstance(sp, dict):
        sp = {}
    return {
        "enabled": bool(sp.get("enabled", True)),
        "steer_threshold": float(sp.get("steer_threshold") or STEER_THRESHOLD),
        "verifier_before_advance": bool(sp.get("verifier_before_advance", True)),
        "observer_live": bool(sp.get("observer_live", False)),
        "provider": (sp.get("provider") or "deepseek").strip(),
    }


def _read_dialogue_tail(n: int = 8) -> list[dict[str, Any]]:
    from mag.desk_dialogue import DIALOGUE_LOG

    rows: list[dict[str, Any]] = []
    if not DIALOGUE_LOG.is_file():
        return rows
    for line in DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def collect_observer_context(*, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Snapshot for rule + live observer (C3-style text checkpoint)."""
    from mag.agent_desk import read_desk
    from mag.coding_session_orchestrator import assess_sprint_status
    from mag.desk_dialogue import read_cursor
    from mag.desk_local_adapter import echo_without_commit_detected
    from mag.desk_overseer import measure_context_pressure

    cfg = config or {}
    text = read_desk().get("text") or ""
    cur = read_cursor()
    log_lines = []
    from mag.desk_dialogue import DIALOGUE_LOG

    if DIALOGUE_LOG.is_file():
        log_lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    echo = echo_without_commit_detected(log_lines)
    pressure = measure_context_pressure()
    sprint = assess_sprint_status(config=cfg if cfg.get("ok") else None)

    knowns_m = re.search(r"^##\s+Knowns\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    unknowns_m = re.search(r"^##\s+Unknowns\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.M)

    return {
        "schema": SCHEMA,
        "ts": _utc(),
        "cursor": cur,
        "canvas_chars": len(text),
        "goal": _section_body(text, "Goal")[:500],
        "knowns": (knowns_m.group(1).strip() if knowns_m else "")[:800],
        "unknowns": (unknowns_m.group(1).strip() if unknowns_m else "")[:800],
        "active_sprint": sprint.get("active_sprint"),
        "desk_task": (sprint.get("desk_task") or "")[:400],
        "artifact": sprint.get("artifact"),
        "echo": echo,
        "pressure": {k: pressure.get(k) for k in ("intervene", "reasons", "turn")},
        "recent_turns": _read_dialogue_tail(6),
    }


def _section_body(text: str, section: str) -> str:
    m = re.search(rf"^##\s+{re.escape(section)}\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    return m.group(1).strip() if m else ""


def score_turn_rules(ctx: dict[str, Any]) -> dict[str, Any]:
    """Rule-based process reward (Agent-as-Judge lite — no LLM)."""
    scores: dict[str, float] = {}
    reasons: list[str] = []

    echo = ctx.get("echo") or {}
    if echo.get("detected"):
        scores["no_echo"] = 0.0
        reasons.append("echo_without_commit")
    elif (echo.get("streak") or 0) >= 2:
        scores["no_echo"] = 0.3
        reasons.append("echo_streak")
    else:
        scores["no_echo"] = 1.0

    pressure = ctx.get("pressure") or {}
    if pressure.get("intervene"):
        scores["pressure_ok"] = 0.2
        reasons.extend((pressure.get("reasons") or [])[:2])
    else:
        scores["pressure_ok"] = 1.0

    turns = ctx.get("recent_turns") or []
    last = turns[-1] if turns else {}
    reply = str(last.get("reply") or "")
    edit = str(last.get("canvas_edit") or "")
    speaker = str(last.get("speaker") or "")

    fmt_ok = "### Reply" in reply or "### Canvas edit" in reply or bool(edit.strip())
    scores["format"] = 1.0 if fmt_ok else 0.4
    if not fmt_ok:
        reasons.append("missing_reply_canvas_format")

    if last.get("wake_blocked"):
        scores["wake_ok"] = 0.0
        reasons.append("local_wake_blocked")
    else:
        scores["wake_ok"] = 1.0

    artifact = (ctx.get("artifact") or "").split()[0].strip("`")
    sprint_align = 0.5
    if artifact and (artifact in edit or artifact in reply or artifact in (ctx.get("goal") or "")):
        sprint_align = 1.0
    elif ctx.get("desk_task"):
        task_words = [w for w in re.findall(r"[a-z_]{4,}", (ctx.get("desk_task") or "").lower()) if w not in ("local", "deepseek", "append", "canvas")]
        hits = sum(1 for w in task_words[:6] if w in (edit + reply).lower())
        sprint_align = min(1.0, 0.4 + hits * 0.15)
    scores["sprint_align"] = sprint_align
    if sprint_align < 0.6:
        reasons.append("weak_sprint_alignment")

    weights = {"no_echo": 0.35, "pressure_ok": 0.15, "format": 0.2, "wake_ok": 0.15, "sprint_align": 0.15}
    total = sum(scores[k] * weights[k] for k in weights)
    return {
        "schema": SCHEMA,
        "mode": "rules",
        "score": round(total, 3),
        "pass": total >= STEER_THRESHOLD,
        "components": scores,
        "reasons": reasons,
        "last_speaker": speaker,
    }


def build_steer_packet(ctx: dict[str, Any], score_row: dict[str, Any]) -> str:
    """DEBATE-style critic steer — injected before next Local/Remote wake."""
    reasons = score_row.get("reasons") or []
    artifact = ctx.get("artifact") or "sprint artifact"
    task = (ctx.get("desk_task") or "").split("\n")[0][:120]
    lines = [
        f"Observer (steal protocol): score {score_row.get('score')} — alignment drift.",
    ]
    if "echo_without_commit" in reasons or "echo_streak" in reasons:
        lines.append("Stop echoing prior Dialogue — ONE new canvas commit required.")
    if "local_wake_blocked" in reasons:
        lines.append("Local: extractable canvas edit only — bare move line or one Status paragraph.")
    if "weak_sprint_alignment" in reasons:
        lines.append(f"Sprint task: {task}")
        lines.append(f"Target artifact: `{artifact}` — commit paths/status on canvas.")
    if "missing_reply_canvas_format" in reasons:
        lines.append("Use ### Reply + ### Canvas edit per desk protocol.")
    return "\n".join(lines)[:1200]


def inject_steer(steer: str) -> dict[str, Any]:
    """Post steer to pigeonhole (if enabled) + conductor scratch tail."""
    steer = (steer or "").strip()
    if not steer:
        return {"ok": False, "error": "empty steer"}

    out: dict[str, Any] = {"ok": True, "steer_len": len(steer)}
    from mag.desk_dialogue import desk_steering_enabled, post_desk_steer

    if desk_steering_enabled():
        out["pigeonhole"] = post_desk_steer(steer)
    else:
        out["pigeonhole"] = {"ok": False, "hint": "set MAG_DESK_STEERING=1 for inbox inject"}

    try:
        from mag.agent_desk import read_desk, set_desk_section

        scratch = _section_body(read_desk().get("text") or "", "Conductor scratch")
        stamp = _utc()[:16]
        block = f"\n\n### Observer steer · {stamp}Z\n{steer}\n"
        if "### Observer steer" not in scratch[-800:]:
            set_desk_section("Conductor scratch", (scratch + block).strip())
            out["scratch_appended"] = True
    except Exception as exc:
        out["scratch_error"] = str(exc)

    return out


def verify_sprint_handoff(*, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """AgentSwarm adversarial verifier — block sprint advance on process failure."""
    from mag.coding_session_orchestrator import assess_sprint_status

    ctx = collect_observer_context(config=config)
    score_row = score_turn_rules(ctx)
    cfg = _steal_cfg(config)
    status = assess_sprint_status(config=config if (config or {}).get("ok") else None)
    active = status.get("active_sprint") or ""
    active_chk = next((c for c in (status.get("sprint_checks") or []) if c.get("sprint") == active), {})

    artifact_ok = bool(active_chk.get("pass"))
    process_ok = bool(score_row.get("pass"))
    echo = ctx.get("echo") or {}

    blockers: list[str] = []
    if echo.get("detected"):
        blockers.append("echo_without_commit")
    if not process_ok and cfg.get("verifier_before_advance"):
        blockers.append(f"observer_score_{score_row.get('score')}")
    if not artifact_ok:
        blockers.append("artifact_gate_open")

    approve_advance = artifact_ok and process_ok and not echo.get("detected")
    return {
        "ok": True,
        "schema": SCHEMA,
        "approve_advance": approve_advance,
        "artifact_ok": artifact_ok,
        "process_ok": process_ok,
        "score": score_row,
        "blockers": blockers,
        "active_sprint": active,
    }


def _live_critic(ctx: dict[str, Any], score_row: dict[str, Any]) -> dict[str, Any]:
    """Optional DeepSeek agent-as-judge (hot path optional — off by default)."""
    prompt_path = OBSERVER_PROMPT
    system = "You are the desk observer (devil's advocate). Score process alignment 0-1. Output JSON only."
    if prompt_path.is_file():
        system = prompt_path.read_text(encoding="utf-8", errors="replace").strip()

    user = json.dumps(
        {
            "goal": ctx.get("goal"),
            "active_sprint": ctx.get("active_sprint"),
            "desk_task": ctx.get("desk_task"),
            "rule_score": score_row,
            "recent_turns": [
                {
                    "speaker": t.get("speaker"),
                    "reply_head": str(t.get("reply") or "")[:300],
                    "edit_head": str(t.get("canvas_edit") or "")[:200],
                }
                for t in (ctx.get("recent_turns") or [])[-3:]
            ],
        },
        indent=2,
    )[:6000]

    try:
        from models.providers import chat_messages

        res = chat_messages(
            "deepseek",
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            tools=None,
            tier="T2",
            max_tokens=512,
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error"), "mode": "live"}
        raw = (res.get("text") or "").strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        parsed = json.loads(m.group(0)) if m else {"critique": raw[:500]}
        return {"ok": True, "mode": "live", "critic": parsed, "raw_head": raw[:300]}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "mode": "live"}


def observer_tick(
    *,
    config: dict[str, Any] | None = None,
    live: bool = False,
    inject: bool = True,
) -> dict[str, Any]:
    """One observer pass — score, optional live critic, steer if drift."""
    from mag.coding_session_loop import load_config

    cfg = config or load_config()
    steal = _steal_cfg(cfg)
    if not steal.get("enabled"):
        return {"ok": True, "skipped": "steal_protocol disabled"}

    ctx = collect_observer_context(config=cfg)
    score_row = score_turn_rules(ctx)
    threshold = steal.get("steer_threshold") or STEER_THRESHOLD
    score_row["pass"] = (score_row.get("score") or 0) >= threshold

    out: dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA,
        "score": score_row,
        "verifier": verify_sprint_handoff(config=cfg),
        "threshold": threshold,
    }

    if live or steal.get("observer_live") or os.environ.get("MAG_OBSERVER_LIVE", "").lower() in ("1", "true", "yes"):
        out["live"] = _live_critic(ctx, score_row)
        critic = (out.get("live") or {}).get("critic") or {}
        if isinstance(critic, dict) and critic.get("steer"):
            score_row["pass"] = False
            out["steer_from"] = "live_critic"

    steer_text = ""
    if not score_row.get("pass"):
        live_steer = ((out.get("live") or {}).get("critic") or {}).get("steer")
        steer_text = str(live_steer).strip() if live_steer else build_steer_packet(ctx, score_row)

    out["steer_recommended"] = bool(steer_text)
    if steer_text and inject:
        out["inject"] = inject_steer(steer_text)

    _trail("observer_tick", score=score_row.get("score"), passed=score_row.get("pass"), steer=bool(steer_text))
    return out
