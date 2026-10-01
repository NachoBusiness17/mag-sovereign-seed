"""Desk conductor — local percolator orchestrates Local ↔ Remote handoff.

Schema: mag_desk_conductor.v3
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_desk_conductor.v4"
TRAIL_PATH = ROOT / "memory" / "runs" / "desk_conductor_trail.jsonl"
SCRATCH_SECTION = "Conductor scratch"
DESK_CONDUCTOR_ROLE = "desk_conductor"
CONDUCTOR_PROMPT = ROOT / "prompts" / "desk_conductor.txt"

_DEEPSEEK_CONDUCTOR_SYSTEM = """You are the Mag Desk Conductor (DeepSeek fallback) between Local (slow) and DeepSeek (fast seat).

Maintain ## Conductor scratch. Wake the correct seat with seat-specific notes. Never ask operator to log moves.

Reply EXACTLY:
### Advisory
### Scratch update
### Wake note
### Canvas edit"""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conductor_system() -> str:
    if CONDUCTOR_PROMPT.is_file():
        return CONDUCTOR_PROMPT.read_text(encoding="utf-8", errors="replace").strip()
    return _DEEPSEEK_CONDUCTOR_SYSTEM


def conductor_model() -> str:
    from models.registry import model_for

    return model_for(DESK_CONDUCTOR_ROLE)


def conductor_backend() -> str:
    """local | deepseek | auto — default local (hot-swapped via lanes.yaml)."""
    raw = (os.environ.get("MAG_DESK_CONDUCTOR_BACKEND") or "local").strip().lower()
    if raw in ("local", "ollama", "l0"):
        return "local"
    if raw in ("deepseek", "remote", "l2", "cloud"):
        return "deepseek"
    return "auto"


def _append_trail(row: dict[str, Any]) -> None:
    TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    row.setdefault("source", "desk_conductor")
    row.setdefault("trail", "desk_conductor_trail.jsonl")
    with TRAIL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def recommend_action(cursor: dict[str, Any] | None = None) -> str:
    from mag.desk_dialogue import DIALOGUE_LOG, read_cursor
    from mag.desk_local_adapter import echo_without_commit_detected

    try:
        from mag.desk_overseer import measure_context_pressure

        pressure = measure_context_pressure()
        if pressure.get("intervene"):
            return "overseer_intervene"
    except Exception:
        pressure = None

    cur = cursor or read_cursor()
    log_lines: list[str] = []
    if DIALOGUE_LOG.is_file():
        log_lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    echo = echo_without_commit_detected(log_lines)
    if echo.get("detected"):
        return "frontier_commit"
    if cur.get("local_wake_pending"):
        return "wake_local"
    if cur.get("wake_pending"):
        return "wake_remote"
    holder = str(cur.get("holder") or "operator").lower()
    if cur.get("remote_asleep") and holder in ("local", "operator"):
        return "waiting_local_edit"
    if not cur.get("remote_asleep"):
        return "remote_awake"
    return "hold"


def _target_seat(action: str) -> str | None:
    if action == "wake_local":
        return "local"
    if action == "wake_remote":
        return "remote"
    return None


def _action_label(action: str) -> str:
    return {
        "wake_local": "Wake Local — DeepSeek edited board",
        "wake_remote": "Wake DeepSeek — Local edited board",
        "waiting_local_edit": "Waiting — Local must canvas-edit",
        "frontier_commit": "Frontier assist — Local echo loop; DeepSeek commits move",
        "overseer_intervene": "Overseer — context limit; heal + record + frontier steer",
        "remote_awake": "Remote awake — in flight",
        "hold": "Hold — loop idle",
    }.get(action, action)


def _recent_dialogue(*, last_n: int = 8) -> list[dict[str, Any]]:
    from mag.desk_dialogue import DIALOGUE_LOG

    if not DIALOGUE_LOG.is_file():
        return []
    lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-last_n:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("reply") or o.get("canvas_edit"):
            out.append(
                {
                    "speaker": o.get("speaker"),
                    "reply_preview": str(o.get("reply") or "")[:400],
                    "canvas_preview": str(o.get("canvas_edit") or "")[:400],
                }
            )
    return out


def _arena_glance() -> dict[str, Any] | None:
    path = ROOT / "memory" / "working" / "agent_arena.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not data.get("active"):
        return None
    return {
        "game": data.get("game") or "chess",
        "turn": data.get("turn"),
        "fen": (data.get("fen") or "")[:80],
        "moves": len(data.get("moves") or []),
    }


def build_seat_fidelity(seat: str) -> dict[str, Any]:
    """Maximum-fidelity context bundle for waking a specific seat."""
    from mag.desk_dialogue import (
        LOCAL_PROMPT,
        PEER_LIMITS,
        REMOTE_PROMPT,
        _compose_system_prompt,
        _desk_local_model,
        _last_peer_message,
        read_trust_status,
    )

    seat = (seat or "").strip().lower()
    if seat not in ("local", "remote"):
        return {"seat": seat, "error": "unknown seat"}

    peer = "remote" if seat == "local" else "local"
    peer_label = "DeepSeek" if seat == "local" else "Local (gemma4 desk orchestrator)"
    trust = read_trust_status()

    fidelity: dict[str, Any] = {
        "seat": seat,
        "peer": peer,
        "peer_label": peer_label,
        "model": _desk_local_model() if seat == "local" else "deepseek-v4-flash",
        "role_prompt_excerpt": (
            LOCAL_PROMPT.read_text(encoding="utf-8", errors="replace")[:900]
            if seat == "local" and LOCAL_PROMPT.is_file()
            else REMOTE_PROMPT.read_text(encoding="utf-8", errors="replace")[:900]
            if REMOTE_PROMPT.is_file()
            else _compose_system_prompt(seat)[:900]
        ),
        "peer_limits_excerpt": (
            PEER_LIMITS.read_text(encoding="utf-8", errors="replace")[:600] if PEER_LIMITS.is_file() else ""
        ),
        "last_peer_message": _last_peer_message(seat),
        "recent_dialogue": _recent_dialogue(last_n=6),
        "trust_tier": trust.get("tier"),
        "slow_to_fast": trust.get("slow_to_fast"),
    }
    if seat == "local":
        fidelity["local_constraints"] = [
            "Slow seat — orchestrator is your external memory; do not rely on full canvas",
            "Canvas edit body = one bare line only (server adds ### Local · move)",
            "No tools — never claim commands ran",
            "Lane chat does not wake DeepSeek — canvas edit does",
        ]
    else:
        fidelity["remote_constraints"] = [
            "Chat-only — no tools on desk",
            "Wake only on board edit — respond to canvas not lane chat",
            "End ### Reply with one explicit instruction for Local's next turn",
            "Name Local's L0 limit when visible (truncation, echo, vagueness)",
        ]
    arena = _arena_glance()
    if arena:
        fidelity["arena"] = arena
    return fidelity


def _read_scratch_tail(*, max_chars: int = 1200) -> str:
    from mag.agent_desk import read_desk

    text = read_desk().get("text") or ""
    header = f"## {SCRATCH_SECTION}"
    idx = text.find(header)
    if idx < 0:
        return ""
    rest = text[idx + len(header) :]
    nxt = rest.find("\n## ")
    block = rest[:nxt] if nxt >= 0 else rest
    return block.strip()[-max_chars:]


def apply_scratch_update(body: str) -> dict[str, Any] | None:
    """Append conductor summary under ## Conductor scratch."""
    body = (body or "").strip()
    if not body or body.lower() in ("hold", "none", "—", "-"):
        return None
    tail = _read_scratch_tail(max_chars=400)
    if tail and body[:120].lower() in tail.lower():
        return None
    from mag.agent_desk import append_desk_section

    stamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
    return append_desk_section(SCRATCH_SECTION, f"[{stamp}] {body}", author="Conductor")


def apply_conductor_canvas_edit(edit: str) -> dict[str, Any] | None:
    edit = (edit or "").strip()
    if not edit or edit.lower() in ("hold", "none", "—", "-", "n/a"):
        return None
    from mag.agent_desk import append_desk_raw

    return append_desk_raw(edit)


def _parse_conductor_response(raw: str) -> dict[str, str]:
    text = (raw or "").strip()

    def _section(name: str, next_names: tuple[str, ...] = ()) -> str:
        pattern = rf"###\s*{re.escape(name)}\s*\n([\s\S]*?)(?=###\s*(?:{'|'.join(re.escape(n) for n in next_names)})\s*\n|\Z)"
        m = re.search(pattern, text, re.I)
        return (m.group(1).strip() if m else "").strip()

    advisory = _section("Advisory", ("Scratch update", "Wake note", "Canvas edit", "Next note"))
    if not advisory:
        advisory = text[:240]
    scratch = _section("Scratch update", ("Wake note", "Canvas edit", "Next note"))
    wake = _section("Wake note", ("Canvas edit", "Next note"))
    canvas = _section("Canvas edit", ("Next note",))
    if not wake:
        wake = _section("Next note", ("Canvas edit",))
    if wake.lower() == "hold":
        wake = ""
    return {
        "advisory": advisory,
        "scratch_update": scratch,
        "wake_note": wake,
        "canvas_edit": canvas,
    }


def _fallback_plan(
    *,
    action: str,
    operator_note: str,
    target: str | None,
    fidelity: dict[str, Any],
) -> dict[str, Any]:
    """Rule-based percolator when LLM fails — keeps loop moving."""
    scratch = operator_note[:400] if operator_note else f"State: {action} · {_action_label(action)}"
    wake = ""
    if action == "wake_remote" and target == "remote":
        peer = (fidelity.get("last_peer_message") or "")[:400]
        wake = (
            "Local edited the board — respond with ### Reply and ### Canvas edit. "
            "End with one instruction for Local's next turn."
            + (f"\n\nLocal said:\n{peer}" if peer else "")
        )
    elif action == "wake_local" and target == "local":
        from mag.desk_orchestrator_memory import build_local_memory_packet, compose_local_wake_payload

        mem = build_local_memory_packet(fidelity=fidelity, operator_note=operator_note)
        wake = compose_local_wake_payload(memory=mem, wake_note="", operator_note=operator_note)
        wake = wake.split("## Protocol")[0].strip()[:900]
    elif action == "waiting_local_edit" and operator_note:
        from mag.desk_orchestrator_memory import build_local_memory_packet, compose_local_wake_payload

        mem = build_local_memory_packet(fidelity=fidelity, operator_note=operator_note)
        wake = compose_local_wake_payload(memory=mem, wake_note="", operator_note=operator_note)[:900]
    return {
        "ok": True,
        "action": action,
        "target_seat": target or "none",
        "advisory": _action_label(action),
        "scratch_update": scratch,
        "wake_note": wake,
        "canvas_edit": "none",
        "backend": "rule",
        "model": "rule",
    }


def _invoke_local_conductor(*, system: str, user: str) -> dict[str, Any]:
    from mag.desk_dialogue import _invoke_local_llm

    model = conductor_model()
    try:
        raw, mode, timing = _invoke_local_llm(
            system=system,
            user=user,
            model=model,
            role=DESK_CONDUCTOR_ROLE,
            speaker="conductor",
        )
        return {"ok": True, "raw": raw, "model": model, "mode": mode, "timing": timing, "backend": "local"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:240], "model": model, "backend": "local"}


def _invoke_deepseek_conductor(*, system: str, user: str) -> dict[str, Any]:
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            system,
            user,
            tier="T2",
            max_tokens=520,
            temperature=0.2,
        )
        if not res.get("ok"):
            return {"ok": False, "error": str(res.get("error") or "deepseek failed"), "backend": "deepseek"}
        raw = str(res.get("text") or res.get("content") or "").strip()
        return {
            "ok": True,
            "raw": raw,
            "model": res.get("model"),
            "backend": "deepseek",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "backend": "deepseek"}


def _plan_from_raw(
    *,
    raw: str,
    action: str,
    target: str | None,
    fidelity: dict[str, Any],
    backend: str,
    model: Any,
) -> dict[str, Any]:
    parsed = _parse_conductor_response(raw)
    if not parsed.get("scratch_update") and not parsed.get("wake_note"):
        parsed["advisory"] = parsed.get("advisory") or raw[:240]
    return {
        "ok": True,
        "action": action,
        "target_seat": target or "none",
        "advisory": parsed["advisory"],
        "scratch_update": parsed["scratch_update"],
        "wake_note": parsed["wake_note"],
        "canvas_edit": parsed["canvas_edit"],
        "fidelity": fidelity,
        "model": model,
        "backend": backend,
        "raw_preview": raw[:280],
    }


def _compose_wake_payload(
    *,
    seat: str,
    wake_note: str,
    fidelity: dict[str, Any],
    operator_note: str = "",
    glance: dict[str, Any] | None = None,
) -> str:
    from mag.desk_orchestrator_memory import (
        build_local_memory_packet,
        build_remote_memory_packet,
        compose_local_wake_payload,
        compose_remote_wake_payload,
    )

    if seat == "local":
        memory = build_local_memory_packet(
            fidelity=fidelity,
            operator_note=operator_note,
            glance=glance,
        )
        return compose_local_wake_payload(
            memory=memory,
            wake_note=wake_note,
            operator_note=operator_note,
        )
    memory = build_remote_memory_packet(fidelity=fidelity, operator_note=operator_note)
    return compose_remote_wake_payload(
        memory=memory,
        wake_note=wake_note,
        fidelity=fidelity,
        operator_note=operator_note,
    )


def conductor_glance() -> dict[str, Any]:
    from mag.desk_dialogue import desk_health_check, read_cursor, read_trust_status

    cur = read_cursor()
    action = recommend_action(cur)
    health = desk_health_check(auto_heal=False)
    trust = read_trust_status()
    target = _target_seat(action)
    out: dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "cursor": cur,
        "next_action": action,
        "next_label": _action_label(action),
        "target_seat": target,
        "trust_tier": trust.get("tier"),
        "slow_to_fast": trust.get("slow_to_fast"),
        "health_ok": bool(health.get("ok") and not health.get("polluted")),
        "health_headline": health.get("headline"),
        "scratch_tail": _read_scratch_tail(max_chars=400),
        "conductor_backend": conductor_backend(),
        "conductor_model": conductor_model(),
        "conductor_role": DESK_CONDUCTOR_ROLE,
        "keepalive_hint": (
            "Keep alive runs conductor → wakes the seat that owes a canvas edit."
            if action in ("wake_local", "wake_remote", "waiting_local_edit", "overseer_intervene")
            else "Set a goal in canvas or prompt conductor, then Tick."
        ),
    }
    try:
        from mag.desk_overseer import glance as overseer_glance

        out["overseer"] = overseer_glance()
    except Exception:
        pass
    return out


def _conductor_plan(
    *,
    glance: dict[str, Any],
    operator_note: str = "",
    fidelity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from mag.desk_dialogue import read_desk

    cur = glance.get("cursor") or {}
    canvas = (read_desk().get("text") or "")[:4500]
    action = glance.get("next_action") or "hold"
    target = _target_seat(action)
    if action == "waiting_local_edit" and operator_note.strip():
        target = "local"
    fid = fidelity or (build_seat_fidelity(target) if target else {})
    memory: dict[str, Any] | None = None
    if target == "local":
        from mag.desk_orchestrator_memory import build_local_memory_packet

        memory = build_local_memory_packet(fidelity=fid, operator_note=operator_note, glance=glance)

    user = (
        f"## Cursor\n{json.dumps(cur, indent=2)}\n\n"
        f"## Recommended action\n{action} — {glance.get('next_label')}\n"
        f"## Target seat for wake note\n{target or 'none'}\n\n"
        f"## Conductor scratch tail\n{_read_scratch_tail() or '(empty — start one)'}\n\n"
        f"## Canvas tail\n{canvas[-2500:]}\n\n"
        f"## Seat fidelity\n{json.dumps(fid, indent=2)[:2800]}\n\n"
    )
    if memory:
        user += f"## Local memory packet (distill into wake note)\n{json.dumps(memory, indent=2)}\n\n"
    if operator_note.strip():
        user += f"## Operator prompt\n{operator_note.strip()[:1200]}\n\n"
    user += (
        "## Task\nPercolate: scratch update + seat-fidelity wake note. "
        "For Local: low bandwidth — repeat the ONE canvas line from memory packet; do not dump full context. "
        "For Remote: high bandwidth — structure + explicit bare line for Local's next edit."
    )

    system = _conductor_system()
    backend_pref = conductor_backend()
    attempts: list[str] = []
    if backend_pref == "local":
        attempts = ["local", "deepseek"]
    elif backend_pref == "deepseek":
        attempts = ["deepseek", "local"]
    else:
        attempts = ["local", "deepseek"]

    last_err = ""
    for backend in attempts:
        if backend == "local":
            res = _invoke_local_conductor(system=system, user=user)
        else:
            res = _invoke_deepseek_conductor(system=_DEEPSEEK_CONDUCTOR_SYSTEM, user=user)
        if res.get("ok") and (res.get("raw") or "").strip():
            return _plan_from_raw(
                raw=str(res["raw"]),
                action=action,
                target=target,
                fidelity=fid,
                backend=str(res.get("backend") or backend),
                model=res.get("model"),
            )
        last_err = str(res.get("error") or "empty response")

    return _fallback_plan(action=action, operator_note=operator_note, target=target, fidelity=fid) | {
        "fallback_reason": last_err[:200],
    }


def _meaningful_canvas_edit_from_turn(turn: dict[str, Any]) -> bool:
    from mag.desk_dialogue import _meaningful_canvas_edit

    return _meaningful_canvas_edit(str(turn.get("canvas_edit") or ""))


def frontier_compact_commit(
    *,
    operator_note: str = "",
    required_move: str = "",
    echo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DeepSeek writes the canvas line Local failed to commit — compact frontier assist."""
    from mag.desk_dialogue import dialogue_turn, read_desk, _last_peer_message
    from mag.desk_local_adapter import echo_without_commit_detected, extract_move_line, format_local_canvas
    from mag.desk_orchestrator_memory import build_remote_memory_packet

    if echo is None:
        from mag.desk_dialogue import DIALOGUE_LOG

        log_lines = (
            DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            if DIALOGUE_LOG.is_file()
            else []
        )
        echo = echo_without_commit_detected(log_lines)

    move = (required_move or echo.get("last_move") or "").strip()
    if not move:
        move = extract_move_line(echo.get("last_reply_preview") or "") or ""
    if not move:
        move = extract_move_line(_last_peer_message("local")) or ""

    canvas = read_desk().get("text") or ""
    if move:
        payload = (
            "## Frontier compact assist\n"
            f"Local echoed without canvas commit ({echo.get('streak', '?')} turns). "
            "You commit the board.\n\n"
            f"## Required move\n`{move}`\n\n"
        )
    else:
        payload = (
            "## Frontier compact assist\n"
            f"Local failed canvas commit ({echo.get('streak', '?')} echo turns).\n\n"
        )
    payload += (
        f"## Operator intent\n{(operator_note or '')[:600]}\n\n"
        f"## Board tail\n{canvas[-1800:]}\n\n"
        "## Protocol\n### Reply — one sentence.\n### Canvas edit — one bare move line only.\n"
    )

    acted = dialogue_turn("remote", operator_note=payload, canvas=canvas, force_wake=True)
    out: dict[str, Any] = {
        "ok": bool(acted.get("ok")),
        "mode": "frontier_compact_commit",
        "required_move": move or None,
        "echo": echo,
        "acted": acted,
    }
    if not acted.get("ok"):
        out["error"] = acted.get("error")
        return out

    if move and not _meaningful_canvas_edit_from_turn(acted):
        from mag.agent_desk import append_desk_raw

        edit = format_local_canvas(move)
        append_desk_raw(edit)
        out["server_committed"] = edit
        out["hint"] = "Overseer committed move server-side after Local echo loop"
    return out


def _goal_from_canvas() -> str:
    from mag.agent_desk import read_desk

    text = read_desk().get("text") or ""
    m = re.search(r"## Goal\s*\n([\s\S]*?)(?=\n## |\Z)", text)
    if not m:
        return ""
    body = m.group(1).strip()
    if not body or body.startswith("("):
        return ""
    return body[:500]


def _effective_prompt(*, prompt: str, auto_act: bool) -> str:
    p = (prompt or "").strip()
    if p:
        return p
    if not auto_act:
        return ""
    scratch = _read_scratch_tail(max_chars=600)
    goal = _goal_from_canvas()
    if goal:
        return f"Goal on canvas: {goal}"
    if scratch:
        return f"Continue from conductor scratch: {scratch}"
    return "Begin behavioral handoff — propose goal or next move on canvas with ### Reply and ### Canvas edit."


def conductor_tick(
    *,
    auto_act: bool = False,
    operator_note: str = "",
    conductor_prompt: str = "",
    advise: bool = True,
) -> dict[str, Any]:
    from mag.desk_dialogue import _canvas_pollution_detected, dialogue_turn, heal_canvas, read_desk

    canvas_heal: dict[str, Any] | None = None
    if "duplicate_dialogue_blocks" in _canvas_pollution_detected():
        canvas_heal = heal_canvas(preserve_goal=True)

    prompt = _effective_prompt(prompt=(conductor_prompt or operator_note or "").strip(), auto_act=auto_act)
    glance = conductor_glance()
    action = str(glance.get("next_action") or "hold")
    target = _target_seat(action)
    kick_local = action == "waiting_local_edit" and auto_act
    if kick_local:
        target = "local"
    fidelity = build_seat_fidelity(target) if target else {}

    plan: dict[str, Any] = {
        "ok": True,
        "action": action,
        "advisory": _action_label(action),
        "scratch_update": "",
        "wake_note": "",
        "canvas_edit": "",
        "backend": conductor_backend(),
        "model": conductor_model(),
    }
    if advise:
        plan = _conductor_plan(glance=glance, operator_note=prompt, fidelity=fidelity or None)

    scratch_applied = apply_scratch_update(plan.get("scratch_update") or "")
    canvas_applied = apply_conductor_canvas_edit(plan.get("canvas_edit") or "")

    acted: dict[str, Any] | None = None
    tick_action = action
    wake_actions = ("wake_local", "wake_remote")
    should_act = auto_act and target and (action in wake_actions or kick_local)
    memory_packet: dict[str, Any] | None = None
    frontier_result: dict[str, Any] | None = None

    if auto_act and action == "overseer_intervene":
        from mag.desk_overseer import overseer_intervene

        frontier_result = overseer_intervene(operator_note=prompt)
        acted = frontier_result.get("local_retry") if isinstance(frontier_result.get("local_retry"), dict) else None
        tick_action = "overseer_intervene"
        skill_id = ((frontier_result.get("teaching") or {}).get("artifact") or {}).get("skill_id")
        if frontier_result.get("heal"):
            apply_scratch_update(
                f"Overseer teaching loop — skill `{skill_id or 'pending'}` — "
                f"{', '.join((frontier_result.get('pressure') or {}).get('reasons') or [])[:2]}"
            )
    elif auto_act and action == "frontier_commit":
        from mag.desk_dialogue import DIALOGUE_LOG
        from mag.desk_local_adapter import echo_without_commit_detected

        log_lines = (
            DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            if DIALOGUE_LOG.is_file()
            else []
        )
        echo = echo_without_commit_detected(log_lines)
        frontier_result = frontier_compact_commit(operator_note=prompt, echo=echo)
        acted = frontier_result.get("acted") if isinstance(frontier_result.get("acted"), dict) else None
        tick_action = "frontier_commit"
        if frontier_result.get("server_committed"):
            apply_scratch_update(
                f"Overseer frontier commit — server wrote move after Local echo loop "
                f"({echo.get('streak', '?')} turns)."
            )
    elif should_act:
        from mag.desk_orchestrator_memory import build_local_memory_packet

        wake_note = (plan.get("wake_note") or "").strip()
        if target == "local":
            memory_packet = build_local_memory_packet(
                fidelity=fidelity,
                operator_note=prompt,
                glance=glance,
            )
        payload = _compose_wake_payload(
            seat=target,
            wake_note=wake_note,
            fidelity=fidelity,
            operator_note=prompt,
            glance=glance,
        )
        if not wake_note and target != "local":
            payload = _compose_wake_payload(
                seat=target,
                wake_note="Conductor tick — complete handoff with ### Reply and ### Canvas edit.",
                fidelity=fidelity,
                operator_note=prompt,
                glance=glance,
            )
        canvas_now = read_desk().get("text")
        acted = dialogue_turn(target, operator_note=payload, canvas=canvas_now, force_wake=action in wake_actions)
        tick_action = "wake_local" if target == "local" else "wake_remote"

    out: dict[str, Any] = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _utc(),
        "glance": conductor_glance(),
        "recommended": action,
        "plan": plan,
        "advisory": plan,
        "scratch_applied": bool(scratch_applied),
        "canvas_applied": bool(canvas_applied),
        "auto_act": bool(auto_act),
        "acted": acted,
        "action_taken": tick_action if (acted or frontier_result) else None,
        "canvas": read_desk().get("text"),
        "memory_packet": memory_packet,
        "frontier_commit": frontier_result,
        "canvas_heal": canvas_heal,
    }
    if acted and not acted.get("ok"):
        out["ok"] = False
        out["error"] = acted.get("error")

    _append_trail(
        {
            "ts": out["ts"],
            "recommended": action,
            "auto_act": auto_act,
            "acted_ok": bool(acted and acted.get("ok")),
            "scratch_applied": bool(scratch_applied),
            "advisory": (plan.get("advisory") or "")[:300],
            "operator_prompt": prompt[:200],
            "backend": plan.get("backend"),
            "model": plan.get("model"),
        }
    )
    return out
