"""Desk teaching loop — DeepSeek troubleshoots Local failures into owned skill artifacts.

Not "frontier writes the move." Frontier diagnoses WHY Local failed, files a
compact skill/remedial packet Local can drill on — training data you own.

Schema: mag_desk_teaching.v1
Artifacts: memory/training/desk_skills/*.json
Trail: memory/runs/desk_teaching_trail.jsonl
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_desk_teaching.v1"
SKILLS_DIR = ROOT / "memory" / "training" / "desk_skills"
TRAIL = ROOT / "memory" / "runs" / "desk_teaching_trail.jsonl"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skill_id(failure_class: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (failure_class or "stall").lower()).strip("-")[:40]
    return f"desk-{slug}-{uuid.uuid4().hex[:8]}"


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def build_failure_context(
    *,
    pressure: dict[str, Any] | None = None,
    echo: dict[str, Any] | None = None,
    operator_note: str = "",
) -> dict[str, Any]:
    """Gather compact failure context for frontier troubleshoot prompt."""
    from mag.agent_desk import read_desk
    from mag.desk_dialogue import DIALOGUE_LOG, read_cursor
    from mag.desk_local_adapter import echo_without_commit_detected

    cur = read_cursor()
    log_lines: list[str] = []
    if DIALOGUE_LOG.is_file():
        log_lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    echo = echo or echo_without_commit_detected(log_lines)

    recent_local: list[dict[str, str]] = []
    for line in log_lines[-12:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") != "local":
            continue
        recent_local.append(
            {
                "reply": str(o.get("reply") or "")[:300],
                "canvas_preview": str(o.get("canvas_edit") or "")[:200],
                "wake_blocked": bool(o.get("wake_blocked")),
            }
        )

    reasons = (pressure or {}).get("reasons") or []
    failure_class = "echo_without_commit" if echo.get("detected") else (
        reasons[0] if reasons else "local_stall"
    )

    return {
        "failure_class": failure_class,
        "turn": int(cur.get("turn") or 0),
        "echo_streak": echo.get("streak"),
        "reasons": reasons,
        "recent_local_turns": recent_local[-5:],
        "board_tail": (read_desk().get("text") or "")[-1500:],
        "operator_note": (operator_note or "")[:400],
        "required_move_hint": echo.get("last_move") or "",
    }


def _parse_teaching_response(raw: str, *, failure_class: str) -> dict[str, Any]:
    """Parse DeepSeek troubleshoot into skill artifact fields."""
    text = (raw or "").strip()

    def _section(name: str) -> str:
        m = re.search(rf"###\s*{re.escape(name)}\s*\n([\s\S]*?)(?=###\s|\Z)", text, re.I)
        return (m.group(1).strip() if m else "")[:2000]

    diagnosis = _section("Diagnosis") or _section("TL;DR") or text[:800]
    remedial = _section("Remedial rule") or _section("Rule for Local") or _section("Skill")
    drill = _section("Drill") or _section("Local drill")
    if not remedial and diagnosis:
        remedial = diagnosis.split("\n")[0][:400]

    return {
        "diagnosis": diagnosis,
        "remedial_rule": remedial,
        "local_drill": drill,
        "failure_class": failure_class,
        "raw_preview": text[:500],
    }


def compose_local_skill_packet(artifact: dict[str, Any]) -> str:
    """Low-bandwidth packet for Local — skill drill, not full DeepSeek lecture."""
    return "\n".join(
        [
            "## Skill drill (orchestrator memory)",
            f"Failure: **{artifact.get('failure_class')}**",
            f"Skill id: `{artifact.get('skill_id')}`",
            "",
            "### Rule",
            (artifact.get("remedial_rule") or "One bare canvas line only.")[:600],
            "",
            "### Your drill",
            (artifact.get("local_drill") or "Reply: one sentence. Canvas edit: one move line, no headers.")[:500],
            "",
            "### Do not",
            "- Promise in lane without canvas edit",
            "- Add ### Local headers (server wraps)",
            "- Repeat prior move — commit the new line only",
        ]
    )


def save_skill_artifact(
    parsed: dict[str, Any],
    *,
    context: dict[str, Any],
    teacher_model: str = "deepseek",
) -> dict[str, Any]:
    """Persist owned training artifact on disk."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_id = _skill_id(str(context.get("failure_class") or "stall"))
    artifact = {
        "schema": SCHEMA,
        "skill_id": skill_id,
        "ts": _utc(),
        "failure_class": context.get("failure_class"),
        "teacher": {"seat": "remote", "model": teacher_model},
        "student": {"seat": "local", "role": "desk_orchestrator"},
        "context_snapshot": {
            "turn": context.get("turn"),
            "echo_streak": context.get("echo_streak"),
            "reasons": context.get("reasons"),
        },
        "diagnosis": parsed.get("diagnosis"),
        "remedial_rule": parsed.get("remedial_rule"),
        "local_drill": parsed.get("local_drill"),
        "exportable": True,
        "republic_tags": ["desk_skill", context.get("failure_class"), "slow_to_fast"],
    }
    path = SKILLS_DIR / f"{skill_id}.json"
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    artifact["path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    return artifact


def record_teaching_event(artifact: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
    _trail("skill_filed", skill_id=artifact.get("skill_id"), failure=artifact.get("failure_class"))
    try:
        from mag.training_events import emit

        emit(
            "desk_teaching",
            join={
                "skill_id": str(artifact.get("skill_id") or ""),
                "session_id": "agent-desk",
            },
            input_data={
                "failure_class": context.get("failure_class"),
                "turn": context.get("turn"),
                "echo_streak": context.get("echo_streak"),
            },
            action={
                "teacher": "deepseek",
                "student": "local",
                "artifact_path": artifact.get("path"),
            },
            outcome={
                "remedial_rule": (artifact.get("remedial_rule") or "")[:200],
                "diagnosis_preview": (artifact.get("diagnosis") or "")[:200],
            },
            pattern_tags=["desk_teaching", str(context.get("failure_class") or "stall")],
            tier_max="T2",
        )
    except Exception:
        pass
    return artifact


def frontier_troubleshoot(
    *,
    operator_note: str = "",
    pressure: dict[str, Any] | None = None,
    echo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DeepSeek diagnoses Local failure → owned skill artifact → drill packet for Local."""
    context = build_failure_context(pressure=pressure, echo=echo, operator_note=operator_note)

    prompt = (
        "## Role\nYou are the **teacher/troubleshooter** — NOT playing the game for Local.\n"
        "Diagnose why Local (L0/slow) failed and produce a **skill artifact** Local can drill.\n\n"
        f"## Failure class\n{context.get('failure_class')}\n\n"
        f"## Recent Local turns\n{json.dumps(context.get('recent_local_turns') or [], indent=2)[:2000]}\n\n"
        f"## Board tail\n{context.get('board_tail')}\n\n"
        f"## Operator\n{(operator_note or '')[:400]}\n\n"
        "## Output format (required)\n"
        "### Diagnosis\nWhy Local failed (context limit, echo, format, etc.) — 2-4 sentences.\n\n"
        "### Remedial rule\nOne rule Local must internalize (portable to other tasks).\n\n"
        "### Drill\nOne concrete exercise for Local's next turn (what to put in canvas edit).\n\n"
        "Do NOT just give the chess move. Teach the **skill** — canvas commit, format discipline, bandwidth.\n"
    )

    try:
        from models.providers import chat_messages

        res = chat_messages(
            "deepseek",
            [
                {
                    "role": "system",
                    "content": "Desk teacher seat. Troubleshoot L0 failures into skill artifacts. No move substitution.",
                },
                {"role": "user", "content": prompt},
            ],
            tools=None,
            tier="T2",
            max_tokens=800,
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error") or "deepseek troubleshoot failed", "context": context}
        raw = str(res.get("text") or "").strip()
        model = str(res.get("model") or "deepseek")
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "context": context}

    parsed = _parse_teaching_response(raw, failure_class=str(context.get("failure_class") or "stall"))
    artifact = save_skill_artifact(parsed, context=context, teacher_model=model)
    try:
        from mag.local_playbook import save_teacher_playbook

        save_teacher_playbook(
            playbook_id=f"desk-{artifact.get('skill_id', 'skill')}",
            parsed={
                "domain": "slow_to_fast",
                "label": f"Desk skill · {context.get('failure_class')}",
                "role": "steering_agent",
                "context_keys": ["goal", "board_tail", "skill_drill"],
                "rules": artifact.get("remedial_rule") or "",
                "output": {"kind": "canvas_edit", "format": "move_line_or_one_paragraph"},
            },
            domain="slow_to_fast",
        )
    except Exception:
        pass
    record_teaching_event(artifact, context=context)
    drill_packet = compose_local_skill_packet(artifact)

    return {
        "ok": True,
        "mode": "frontier_troubleshoot",
        "context": context,
        "artifact": artifact,
        "drill_packet": drill_packet,
        "teacher_raw_preview": raw[:400],
    }


def retry_local_with_skill(
    *,
    drill_packet: str,
    operator_note: str = "",
) -> dict[str, Any]:
    """Wake Local with skill drill — approximating higher op via owned remedial packet."""
    from mag.desk_dialogue import dialogue_turn, read_desk

    payload = drill_packet
    if operator_note.strip():
        payload += f"\n\n## Operator\n{operator_note.strip()[:300]}"
    return dialogue_turn("local", operator_note=payload, canvas=read_desk().get("text"), force_wake=True)


def list_skills(*, limit: int = 20) -> dict[str, Any]:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for p in sorted(SKILLS_DIR.glob("desk-*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return {"ok": True, "schema": SCHEMA, "skills": items, "n": len(items), "dir": str(SKILLS_DIR)}
