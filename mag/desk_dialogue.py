"""Desk dialogue — turn-based Local ↔ DeepSeek on shared canvas (no tool theater)."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from config import ROOT
from mag.agent_desk import REMOTE_SESSION, append_desk_meta_raw, append_desk_raw, read_desk

DESK_LOCAL_ROLE = "desk_orchestrator"
DESK_MAILBOX_ID = "desk-local"
CURSOR_PATH = ROOT / "memory" / "working" / "agent_desk_cursor.json"
LOCAL_PROMPT = ROOT / "prompts" / "desk_dialogue_local.txt"
REMOTE_PROMPT = ROOT / "prompts" / "desk_dialogue_remote.txt"
REMOTE_META_PROMPT = ROOT / "prompts" / "desk_dialogue_remote_meta.txt"
ETIQUETTE_PROMPT = ROOT / "prompts" / "desk_dialogue_etiquette.txt"
OPERATOR_MANUAL = ROOT / "docs" / "agent_desk_operator_manual.md"
FIRST_USER_MODEL = ROOT / "docs" / "agent_desk_first_user_model.md"
PEER_LIMITS = ROOT / "prompts" / "desk_dialogue_peer_limits.txt"
DIALOGUE_LOG = ROOT / "memory" / "working" / "agent_desk_dialogue.jsonl"
META_DIALOGUE_LOG = ROOT / "memory" / "working" / "agent_desk_meta_dialogue.jsonl"

META_SPEAKERS = frozenset({"remote_meta_a", "remote_meta_b"})
_SPEAKER_LABELS = {
    "local": "Local ·",
    "remote": "DeepSeek ·",
    "remote_meta_a": "DeepSeek Meta-A ·",
    "remote_meta_b": "DeepSeek Meta-B ·",
}


def desk_steering_enabled() -> bool:
    """Operator steer/inbox injection during desk turns (off by default)."""
    raw = (os.environ.get("MAG_DESK_STEERING") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _read_prompt(path: Path, fallback: str) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace").strip()
    return fallback


def _compose_system_prompt(speaker: str) -> str:
    if speaker in META_SPEAKERS:
        base = _read_prompt(REMOTE_META_PROMPT, "Desk meta strategy. Reply + Meta canvas edit.")
        role = "DeepSeek Meta-A" if speaker == "remote_meta_a" else "DeepSeek Meta-B"
        base = base.replace("DeepSeek Meta", role)
        parts = [base]
        for extra in (ETIQUETTE_PROMPT, PEER_LIMITS):
            text = _read_prompt(extra, "")
            if text:
                parts.append(text)
        return "\n\n".join(parts)
    base = _read_prompt(
        LOCAL_PROMPT if speaker == "local" else REMOTE_PROMPT,
        "Desk dialogue. Reply + canvas edit.",
    )
    parts = [base]
    for extra in (ETIQUETTE_PROMPT, PEER_LIMITS):
        text = _read_prompt(extra, "")
        if text:
            parts.append(text)
    if speaker == "local":
        try:
            from mag.local_playbook import default_for_surface, get_playbook

            pb_id = default_for_surface("desk")
            pb = get_playbook(pb_id)
            rules = (pb.get("rules") or "").strip()
            if rules:
                parts.append(f"## Playbook · {pb.get('label') or pb_id}\n{rules[:1200]}")
        except Exception:
            pass
    return "\n\n".join(parts)


def _meaningful_canvas_edit(edit: str) -> bool:
    from mag.desk_local_adapter import canvas_quality

    q = canvas_quality(edit)
    if q in ("move", "prose"):
        return bool((edit or "").strip())
    return False


def _local_canvas_wake_ok(edit: str) -> bool:
    """Local canvas edit sufficient to wake Remote (move or coding prose)."""
    from mag.desk_local_adapter import canvas_quality, extract_move_line

    q = canvas_quality(edit)
    if q == "prose":
        return bool((edit or "").strip())
    if q == "move":
        return bool(extract_move_line(edit))
    return False


def _set_remote_state(*, asleep: bool, wake_pending: bool = False) -> None:
    cur = read_cursor()
    cur["remote_asleep"] = asleep
    cur["wake_pending"] = wake_pending
    CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")


def _set_local_wake_pending(pending: bool) -> None:
    cur = read_cursor()
    cur["local_wake_pending"] = pending
    CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")


def _trim_canvas_for_local(text: str, *, max_chars: int = 4500) -> str:
    """Keep Goal + tail of Dialogue — avoid context blow-up loops on huge canvases."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    goal_m = re.search(r"(## Goal[\s\S]*?)(?=## |\Z)", text)
    goal = goal_m.group(1).strip() if goal_m else ""
    dlg_m = re.search(r"## Dialogue([\s\S]*)", text)
    dlg = dlg_m.group(1).strip() if dlg_m else ""
    if len(dlg) > max_chars - len(goal) - 80:
        dlg = "…[dialogue trimmed — newest below]…\n\n" + dlg[-(max_chars - len(goal) - 120) :]
    return f"{goal}\n\n## Dialogue\n{dlg}".strip()


def _desk_local_model() -> str:
    from models.registry import model_for

    try:
        return model_for(DESK_LOCAL_ROLE)
    except Exception:
        return model_for("worker")


def _drain_desk_steer() -> list[str]:
    """Operator steer lines queued for the desk local seat (pigeonhole)."""
    if not desk_steering_enabled():
        return []
    try:
        from mag import pigeonhole as ph

        lines = ph.drain_inbox(DESK_MAILBOX_ID)
    except Exception:
        return []
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if s.lower().startswith("!steer "):
            out.append(s[7:].strip()[:1000])
        elif s and not s.startswith("!"):
            out.append(s[:1000])
    return out


def post_desk_steer(context: str) -> dict[str, Any]:
    from mag import pigeonhole as ph

    ctx = (context or "").strip()
    if not ctx:
        return {"ok": False, "error": "steer context required"}
    if not desk_steering_enabled():
        return {
            "ok": False,
            "error": "desk steering disabled (set MAG_DESK_STEERING=1 to enable)",
            "steering_enabled": False,
        }
    ph.post_steer(DESK_MAILBOX_ID, ctx)
    return {"ok": True, "task_id": DESK_MAILBOX_ID, "steer": ctx[:200], "steering_enabled": True}


def _invoke_local_llm(
    *,
    system: str,
    user: str,
    model: str,
    role: str | None = None,
    speaker: str = "local",
) -> tuple[str, str, dict[str, Any]]:
    """Call desk local model with usage logging + empty-response retry."""
    from mag.desk_timing import Timer, extract_ollama_tokens, fill_token_estimates, make_timing, record_timing
    from mag.local_pulse import set_local_thinking
    from mag.ollama_policy import ensure_desk_model

    llm_role = role or DESK_LOCAL_ROLE
    ensure_desk_model(model)
    set_local_thinking(active=True, model=model, source=llm_role)
    timer = Timer()
    tokens_in: int | None = None
    tokens_out: int | None = None
    prompt_full = f"{system}\n\n{user}"
    try:
        attempts: list[tuple[str, float, str]] = [
            ("http", 0.3, user),
            (
                "http",
                0.45,
                user
                + "\n\n(Your previous response was empty. Reply with ### Reply and ### Canvas edit.)",
            ),
            ("logged", 0.35, user),
        ]
        last_err = ""
        for mode, temp, prompt in attempts:
            try:
                if mode == "http":
                    from llm import _chat_http_ex, _resolve_base

                    raw, ollama_body = _chat_http_ex(
                        _resolve_base(), model, system, prompt, temp, num_predict=768
                    )
                    raw = raw.strip()
                    tokens_in, tokens_out = extract_ollama_tokens(ollama_body)
                else:
                    from llm import chat

                    raw = chat(llm_role, system, prompt, temperature=temp).strip()
                if raw:
                    timing = make_timing(
                        speaker=speaker,
                        elapsed_ms=timer.elapsed_ms(),
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        model=model,
                        provider="local",
                    )
                    timing = fill_token_estimates(
                        timing=timing,
                        prompt_text=prompt_full,
                        completion_text=raw,
                    )
                    timing = record_timing(timing)
                    return raw, mode, timing
                last_err = f"{mode} returned empty"
            except Exception as exc:
                last_err = str(exc)
        raise RuntimeError(
            f"local model {model!r} returned empty after retries"
            + (f" ({last_err})" if last_err else "")
        )
    finally:
        set_local_thinking(active=False)


def _drain_operator_inbox() -> list[str]:
    """Queued operator inbox guidance for the desk seat."""
    if not desk_steering_enabled():
        return []
    try:
        from mag.operator_inbox import drain_pending_at_checkpoint

        actions = drain_pending_at_checkpoint(task_hint=DESK_MAILBOX_ID)
    except Exception:
        return []
    out: list[str] = []
    for action in actions:
        if action.get("action") != "apply":
            continue
        text = str(action.get("text") or "").strip()
        if text:
            out.append(text[:1000])
    return out


def refresh_local_desk(*, clear_dialogue: bool = True) -> dict[str, Any]:
    """Reset desk dialogue state and nudge Ollama to reload the local model."""
    out = reset_dialogue(clear_canvas_dialogue=False)
    model = _desk_local_model()
    try:
        import json
        import urllib.request

        from llm import _resolve_base

        payload = {
            "model": model,
            "prompt": "ok",
            "stream": False,
            "keep_alive": "5m",
        }
        req = urllib.request.Request(
            _resolve_base().rstrip("/") + "/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            ping = json.loads(resp.read().decode("utf-8"))
        out["ollama_ping"] = bool(ping.get("response") is not None or ping.get("done"))
    except Exception as exc:
        out["ollama_ping"] = False
        out["ollama_error"] = str(exc)[:200]
    out["model"] = model
    out["role"] = DESK_LOCAL_ROLE
    out["refresh"] = True
    if clear_dialogue:
        out["dialogue_cleared"] = True
    return out


def _remote_may_wake(*, force: bool = False) -> tuple[bool, str]:
    if force:
        return True, ""
    cur = read_cursor()
    if cur.get("wake_pending"):
        return True, "board_edit_pending"
    return False, "fast agent sleeps until slow edits the board"


def _local_may_wake(*, force: bool = False, operator_note: str = "") -> tuple[bool, str]:
    if force:
        return True, "forced"
    if (operator_note or "").strip():
        return True, "operator_note"
    cur = read_cursor()
    if cur.get("local_wake_pending"):
        return True, "remote_board_edit_pending"
    return False, "slow agent sleeps until DeepSeek edits the board"


HANDOFF_ESCALATION: tuple[str, ...] = (
    "HANDOFF 1/5 — Goal: if ## Goal is empty, Local proposes one sentence on canvas. Otherwise refine it.",
    "HANDOFF 2/5 — Local: one concrete next step the operator could run in Shell (propose only). Board edit required.",
    "HANDOFF 3/5 — DeepSeek: turn Local's step into a 3-bullet plan under ## Dialogue. End Reply with instruction for Local.",
    "HANDOFF 4/5 — Local: confirm one bullet or push back in ≤3 sentences. Board edit wakes DeepSeek again.",
    "HANDOFF 5/5 — DeepSeek: close with ### Contract · — single operator action + done criteria.",
)


def read_operator_manual() -> dict[str, Any]:
    if not OPERATOR_MANUAL.is_file():
        return {"ok": False, "error": "manual not found", "path": str(OPERATOR_MANUAL)}
    text = OPERATOR_MANUAL.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "path": str(OPERATOR_MANUAL.relative_to(ROOT)).replace("\\", "/"),
        "text": text,
    }


def read_first_user_model() -> dict[str, Any]:
    if not FIRST_USER_MODEL.is_file():
        return {"ok": False, "error": "user model not found", "path": str(FIRST_USER_MODEL)}
    text = FIRST_USER_MODEL.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "path": str(FIRST_USER_MODEL.relative_to(ROOT)).replace("\\", "/"),
        "text": text,
    }


def read_trust_status() -> dict[str, Any]:
    path = ROOT / "memory" / "working" / "agent_desk_trust_status.json"
    if not path.is_file():
        return {"tier": 0, "slow_to_fast": "unknown", "fast_to_fast": "untrusted"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"tier": 0}
    except (OSError, json.JSONDecodeError):
        return {"tier": 0, "slow_to_fast": "unknown", "fast_to_fast": "untrusted"}


def _parse_sections(text: str, *, speaker: str | None = None) -> tuple[str, str]:
    """Extract ### Reply and ### Canvas edit from model output."""
    raw = (text or "").strip()
    reply = raw
    canvas = ""
    m_reply = re.search(r"###\s*Reply\s*\n([\s\S]*?)(?=###\s*Canvas|\Z)", raw, re.I)
    m_canvas = re.search(r"###\s*Canvas edit\s*\n([\s\S]*)", raw, re.I)
    if m_reply:
        reply = m_reply.group(1).strip()
    if m_canvas:
        canvas = m_canvas.group(1).strip()
    # Strip accidental markdown fences around canvas block
    if canvas.startswith("```") and canvas.endswith("```"):
        canvas = re.sub(r"^```\w*\n?", "", canvas)
        canvas = re.sub(r"\n?```$", "", canvas).strip()
    # Fallback: fenced block after reply when headers missing (common on small local model)
    if not canvas and reply:
        m_fence = re.search(r"```(?:markdown|md)?\n([\s\S]*?)```", raw)
        if m_fence:
            canvas = m_fence.group(1).strip()
            reply = re.sub(r"```[\s\S]*?```", "", reply).strip()
    if not canvas and reply:
        m_heading = re.search(
            r"(###\s*(?:Local|DeepSeek|DeepSeek Meta-[AB])\s*[·\-].*)",
            raw,
            re.I,
        )
        if m_heading:
            canvas = raw[m_heading.start() :].strip()
            reply = raw[: m_heading.start()].strip()
            reply = re.sub(r"\*?\*?Canvas edit:?\*?\*?\s*", "", reply, flags=re.I).strip()
    # Do not pollute canvas with ### Unknown — skip empty canvas when model omitted structure
    if not canvas and reply and speaker:
        label = _SPEAKER_LABELS.get(speaker, "")
        if label and (_looks_like_game_move(reply) or len(reply) > 80):
            if speaker == "local":
                from mag.desk_local_adapter import extract_move_line, format_local_canvas

                line = extract_move_line(reply)
                if line:
                    canvas = format_local_canvas(line)
                elif len(reply) > 80:
                    canvas = f"### Local · note\n{reply[:400]}\n"
            else:
                base = label.rstrip(" ·").strip()
                kind = "board" if _looks_like_game_move(reply) else "note"
                canvas = f"### {base} · {kind}\n{reply[:800]}\n"
    return reply, canvas


def _looks_like_game_move(text: str) -> bool:
    """Chess / turn-based game replies should always become canvas edits."""
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"\b(chess|board|checkmate|castling)\b", t, re.I):
        return True
    if re.search(r"\b\d+\.\.\.\s*\S+", t):
        return True
    if re.search(r"\b[1-9]\.\s*[NBRQK]?[a-h]?x?[a-h][1-8]", t):
        return True
    if re.search(r"\b(O-O-O|O-O|[NBRQK]?[a-h][1-8][a-h][1-8](?:=[NBRQ])?[+#]?)\b", t, re.I):
        return True
    if re.search(r"\b(e4|e5|d4|d5|Nf3|Nc6|Bb5|Bc5|Qh5|Nxe4)\b", t):
        return True
    from mag.desk_local_adapter import extract_move_line

    return bool(extract_move_line(t))


def _normalize_speaker(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if s in ("local", "remote"):
        return s
    if s in ("remote_meta_a", "meta_a", "meta-a", "remote_meta"):
        return "remote_meta_a"
    if s in ("remote_meta_b", "meta_b", "meta-b"):
        return "remote_meta_b"
    return None


def read_cursor() -> dict[str, Any]:
    if not CURSOR_PATH.is_file():
        return {
            "holder": "operator",
            "turn": 0,
            "last_speaker": None,
            "remote_asleep": True,
            "wake_pending": False,
            "local_wake_pending": False,
        }
    try:
        data = json.loads(CURSOR_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {"holder": "operator", "turn": 0}
        data.setdefault("remote_asleep", True)
        data.setdefault("wake_pending", False)
        data.setdefault("local_wake_pending", False)
        return data
    except (OSError, json.JSONDecodeError):
        return {
            "holder": "operator",
            "turn": 0,
            "remote_asleep": True,
            "wake_pending": False,
            "local_wake_pending": False,
        }


def write_cursor(holder: str, *, last_speaker: str | None = None) -> dict[str, Any]:
    cur = read_cursor()
    turn = int(cur.get("turn") or 0) + (1 if last_speaker else 0)
    out = {
        "holder": holder,
        "turn": turn if last_speaker else int(cur.get("turn") or 0),
        "last_speaker": last_speaker or cur.get("last_speaker"),
        "remote_asleep": cur.get("remote_asleep", True),
        "wake_pending": cur.get("wake_pending", False),
        "local_wake_pending": cur.get("local_wake_pending", False),
    }
    CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def _append_dialogue_log(row: dict[str, Any]) -> None:
    DIALOGUE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DIALOGUE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


_ECHO_REPLY = re.compile(r"^Sure, here'?s the\b", re.I)


def _echo_loop_detected(*, threshold: int = 2, tail: int = 12) -> bool:
    """True when recent dialogue log shows repeated truncation echo."""
    if not DIALOGUE_LOG.is_file():
        return False
    lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = 0
    for line in lines[-tail:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = str(o.get("reply") or "").strip()
        if _ECHO_REPLY.match(reply):
            hits += 1
    return hits >= threshold


def _empty_streak_detected(*, threshold: int = 2, tail: int = 10) -> bool:
    if not DIALOGUE_LOG.is_file():
        return False
    hits = 0
    for line in DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = str(o.get("reply") or "").strip()
        canvas = str(o.get("canvas_edit") or "").strip()
        if not reply and not canvas:
            hits += 1
    return hits >= threshold


def _maybe_auto_heal_echo() -> dict[str, Any] | None:
    if _echo_loop_detected():
        reset_dialogue()
        return {"auto_healed": "echo_loop", "reason": "Sure-here's-the pattern in dialogue log"}
    if _empty_streak_detected():
        reset_dialogue()
        return {"auto_healed": "empty_streak", "reason": "consecutive empty local replies in dialogue log"}
    return None


_ORPHAN_SECTIONS = re.compile(
    r"^##\s+(Local\s*\(orchestrator\)|Remote\s*\(DeepSeek\)|Pinned)\s*$",
    re.M | re.I,
)
_UNKNOWN_HEADER = re.compile(r"^###\s+Unknown\s*·", re.M | re.I)


def _canvas_pollution_detected(text: str | None = None) -> list[str]:
    """Detect canvas structure violations that poison the handoff loop."""
    text = (text if text is not None else (read_desk().get("text") or "")).strip()
    if not text:
        return []
    issues: list[str] = []
    if _ORPHAN_SECTIONS.search(text):
        issues.append("orphan_lane_sections")
    if _UNKNOWN_HEADER.search(text):
        issues.append("unknown_speaker_header")
    if re.search(r"^##\s+Pinned\b", text, re.M):
        issues.append("pinned_outside_dialogue")
    headers = [h.strip().lower() for h in re.findall(r"^###\s+(.+)$", text, re.M)]
    if len(headers) != len(set(headers)):
        issues.append("duplicate_dialogue_blocks")
    dlg_m = re.search(r"^##\s+Dialogue\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    if dlg_m:
        dlg_body = dlg_m.group(1)
        if len(dlg_body.strip()) > 6000:
            issues.append("dialogue_bloat")
        # Placeholder goal never replaced but dialogue has many turns
        goal_m = re.search(r"^##\s+Goal\s*\n([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
        goal_body = (goal_m.group(1).strip() if goal_m else "")
        if goal_body.startswith("(") and len(headers) >= 4:
            issues.append("goal_still_placeholder")
    return issues


def _extract_goal_sentence(text: str) -> str:
    """Pull a real goal from canvas if operator never locked ## Goal."""
    m = re.search(r"^##\s+Goal\s*\n([\s\S]*?)(?=^##\s+|\Z)", text, re.M)
    body = (m.group(1).strip() if m else "")
    if body and not body.startswith("("):
        return body.split("\n")[0].strip()[:500]
    for pat in (
        r'Proposed Goal:\s*"([^"]+)"',
        r"Proposed first workflow:\s*(.+?)(?:\n|Local:)",
    ):
        hit = re.search(pat, text, re.I | re.S)
        if hit:
            return hit.group(1).strip()[:500]
    return ""


def heal_canvas(*, preserve_goal: bool = True, force: bool = False) -> dict[str, Any]:
    """Reset polluted canvas to template; optionally keep locked Goal."""
    from mag.agent_desk import DESK_TEMPLATE, read_desk, write_desk

    text = (read_desk().get("text") or "").strip()
    issues = _canvas_pollution_detected(text)
    if not issues and not force:
        return {"ok": True, "healed": False, "issues": []}

    goal = _extract_goal_sentence(text) if preserve_goal else ""
    new_text = DESK_TEMPLATE
    if goal:
        new_text = new_text.replace(
            "(one clear sentence — what success looks like)",
            goal,
        )
    write_desk(new_text)
    reset_dialogue()
    return {
        "ok": True,
        "healed": True,
        "issues": issues,
        "preserved_goal": bool(goal),
        "goal": goal[:200] if goal else None,
    }


def _maybe_auto_heal_desk(*, include_canvas: bool = True) -> dict[str, Any] | None:
    """Echo log heal + optional canvas structure heal (nervous system / desk turns)."""
    echo = _maybe_auto_heal_echo()
    if echo:
        if include_canvas:
            heal_canvas(preserve_goal=True)
            echo["canvas_healed"] = True
        return echo
    if not include_canvas:
        return None
    issues = _canvas_pollution_detected()
    if issues:
        out = heal_canvas(preserve_goal=True)
        if out.get("healed"):
            return {
                "auto_healed": "canvas_pollution",
                "reason": ", ".join(issues),
                "issues": issues,
                "preserved_goal": out.get("preserved_goal"),
            }
    return None


def _maybe_auto_heal_turn() -> dict[str, Any] | None:
    """Mid-turn heal: echo/empty streak only — never wipe canvas mid handoff."""
    return _maybe_auto_heal_desk(include_canvas=False)


def _health_headline(*, issues: list[str], echo: bool, pressure: dict[str, Any] | None = None) -> str:
    if pressure and pressure.get("intervene"):
        return f"Context limit — overseer: {', '.join((pressure.get('reasons') or [])[:3])}"
    if echo:
        return "Echo loop in dialogue log — reset dialogue"
    if issues:
        return f"Canvas issues: {', '.join(issues[:3])}"
    return "Desk healthy"


def _extract_chess_move(text: str) -> str:
    """Best-effort SAN/UCI from a canvas edit block."""
    from mag.desk_local_adapter import extract_move_line

    line = extract_move_line(text)
    if line:
        return line.split()[-1] if " " in line else line
    t = (text or "").strip()
    if not t:
        return ""
    for pat in (
        r"\b(O-O-O|O-O|[NBRQK]?[a-h]?x?[a-h][1-8](?:=[NBRQ])?[+#]?)\b",
        r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b",
    ):
        m = re.search(pat, t, re.I)
        if m:
            return m.group(1)
    return ""


def _maybe_sync_arena_from_edit(canvas_edit: str, *, speaker: str) -> dict[str, Any] | None:
    """When chess arena is active, mirror canvas game moves onto the board."""
    if not _looks_like_game_move(canvas_edit):
        return None
    move = _extract_chess_move(canvas_edit)
    if not move:
        return None
    try:
        from mag import agent_arena as arena

        if not arena.status().get("active"):
            return None
        seat = "local" if speaker == "local" else "remote"
        result = arena.apply_move(move, seat=seat)
        return result if result.get("ok") else None
    except Exception:
        return None


def desk_health_check(*, auto_heal: bool = True) -> dict[str, Any]:
    """Probe canvas + dialogue log; optionally heal. Called from nervous glance."""
    issues = _canvas_pollution_detected()
    echo = _echo_loop_detected()
    pressure: dict[str, Any] = {}
    try:
        from mag.desk_overseer import measure_context_pressure

        pressure = measure_context_pressure()
        if pressure.get("reasons"):
            issues = list(dict.fromkeys(issues + (pressure.get("reasons") or [])))
    except Exception:
        pass
    out: dict[str, Any] = {
        "ok": True,
        "canvas_issues": issues,
        "echo_loop": echo,
        "context_pressure": pressure or None,
        "polluted": bool(issues or echo or pressure.get("intervene")),
        "headline": _health_headline(issues=issues, echo=echo, pressure=pressure),
    }
    if auto_heal and pressure.get("intervene"):
        try:
            from mag.desk_overseer import overseer_intervene

            out["overseer"] = overseer_intervene()
            out["polluted"] = False
        except Exception as exc:
            out["overseer_error"] = str(exc)[:200]
    elif auto_heal and (issues or echo):
        healed = _maybe_auto_heal_desk()
        if healed:
            out["auto_heal"] = healed
            out["polluted"] = False
    return out


def reset_dialogue(*, clear_canvas_dialogue: bool = False) -> dict[str, Any]:
    """Clear poisoned dialogue context (fixes Sure-here's-the echo loop)."""
    from mag.desk_timing import reset_timings

    reset_timings()
    if DIALOGUE_LOG.is_file():
        DIALOGUE_LOG.write_text("", encoding="utf-8")
    _set_remote_state(asleep=True, wake_pending=False)
    _set_local_wake_pending(False)
    cur = read_cursor()
    cur["turn"] = 0
    cur["last_speaker"] = None
    cur["holder"] = "operator"
    CURSOR_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    if clear_canvas_dialogue:
        from mag.agent_desk import read_desk, write_desk

        text = read_desk().get("text") or ""
        if "## Dialogue" in text:
            head, _, _rest = text.partition("## Dialogue")
            text = head.rstrip() + "\n\n## Dialogue\n\n"
            write_desk(text)
    return {"ok": True, "reset": True, "cursor": read_cursor()}


def wipe_board() -> dict[str, Any]:
    """Fresh template canvas + empty dialogue log + operator cursor."""
    from mag.agent_desk import DESK_TEMPLATE, write_desk

    write_desk(DESK_TEMPLATE)
    out = reset_dialogue(clear_canvas_dialogue=False)
    out["wipe"] = True
    out["canvas"] = "template"
    return out


def _last_peer_message(speaker: str) -> str:
    if not DIALOGUE_LOG.is_file():
        return ""
    lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines[-20:]):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") == speaker or not o.get("reply"):
            continue
        msg = str(o["reply"]).strip()
        if re.match(r"^Sure, here'?s the\b", msg, re.I):
            continue
        if len(msg) < 12 and msg.lower().startswith("sure"):
            continue
        return msg[:2000]
    return ""


def _append_meta_dialogue_log(row: dict[str, Any]) -> None:
    META_DIALOGUE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with META_DIALOGUE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _last_meta_peer_message(speaker: str) -> str:
    if not META_DIALOGUE_LOG.is_file():
        return ""
    peer = "remote_meta_b" if speaker == "remote_meta_a" else "remote_meta_a"
    lines = META_DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines[-20:]):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("speaker") != peer:
            continue
        msg = str(o.get("reply") or "").strip()
        if msg:
            return msg[:2000]
    return ""


def meta_dialogue_turn(
    speaker: str,
    *,
    operator_note: str = "",
    canvas: str | None = None,
) -> dict[str, Any]:
    """DeepSeek Meta-A or Meta-B strategy turn — ## Meta only, never wakes Local."""
    speaker = _normalize_speaker(speaker) or ""
    if speaker not in META_SPEAKERS:
        return {"ok": False, "error": "speaker must be remote_meta_a or remote_meta_b"}

    canvas_text = (canvas or read_desk().get("text") or "").strip()
    peer_label = "DeepSeek Meta-B" if speaker == "remote_meta_a" else "DeepSeek Meta-A"
    last_peer = _last_meta_peer_message(speaker)

    blocks = [f"## Shared canvas\n{canvas_text[:8000]}"]
    if last_peer:
        blocks.append(f"## Last {peer_label} message\n{last_peer}")
    if operator_note.strip():
        blocks.append(f"## Operator note\n{operator_note.strip()[:1000]}")
    blocks.append(
        "## Your turn\n"
        f"You are **{speaker.replace('_', ' ')}**. Discuss how main DeepSeek should talk to Local (gemma4). "
        "Append under ## Meta only. Do not wake Local."
    )
    user = "\n\n".join(blocks)
    system = _compose_system_prompt(speaker)

    timing: dict[str, Any] | None = None
    try:
        from mag.desk_timing import Timer, extract_provider_tokens, make_timing, record_timing
        from models.providers import chat_messages

        timer = Timer()
        res = chat_messages(
            "deepseek",
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=None,
            tier="T2",
            max_tokens=1024,
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error") or "deepseek failed", "speaker": speaker}
        raw = (res.get("text") or "").strip()
        model = res.get("model")
        tin, tout = extract_provider_tokens(res.get("usage"))
        timing = record_timing(
            make_timing(
                speaker=speaker,
                elapsed_ms=timer.elapsed_ms(),
                tokens_in=tin,
                tokens_out=tout,
                model=str(model) if model else None,
                provider="deepseek",
            )
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "speaker": speaker}

    reply, canvas_edit = _parse_sections(raw, speaker=speaker)
    if canvas_edit:
        append_desk_meta_raw(canvas_edit)
        canvas_text = read_desk().get("text") or canvas_text

    row = {
        "speaker": speaker,
        "reply": reply,
        "canvas_edit": canvas_edit,
        "provider": "deepseek",
        "model": model,
        "role": "deepseek_meta",
    }
    if timing:
        row["timing"] = timing
    _append_meta_dialogue_log(row)

    return {
        "ok": True,
        "speaker": speaker,
        "reply": reply,
        "canvas_edit": canvas_edit,
        "canvas": canvas_text,
        "provider": "deepseek",
        "model": model,
        "meta": True,
        "timing": timing,
    }


def meta_discuss(
    *,
    rounds: int = 1,
    operator_note: str = "",
    canvas: str | None = None,
) -> dict[str, Any]:
    """Alternate Meta-A ↔ Meta-B strategy turns (does not wake Local)."""
    n = max(1, min(int(rounds or 1), 6))
    turns: list[dict[str, Any]] = []
    canvas_text = canvas
    kickoff = (operator_note or "").strip()

    for i in range(n):
        for sp in ("remote_meta_a", "remote_meta_b"):
            note = kickoff if i == 0 and sp == "remote_meta_a" else ""
            turn = meta_dialogue_turn(sp, operator_note=note, canvas=canvas_text)
            turns.append({**turn, "leg": sp, "round": i + 1})
            if not turn.get("ok"):
                return {
                    "ok": False,
                    "mode": "meta_discuss",
                    "error": turn.get("error"),
                    "failed_speaker": sp,
                    "turns": turns,
                }
            canvas_text = turn.get("canvas") or canvas_text

    return {
        "ok": True,
        "mode": "meta_discuss",
        "rounds": n,
        "turns": turns,
        "canvas": canvas_text,
    }


def dialogue_turn(
    speaker: str,
    *,
    operator_note: str = "",
    canvas: str | None = None,
    force_wake: bool = False,
    local_mode: str = "real",
) -> dict[str, Any]:
    """One dialogue turn: local or remote speaks + edits canvas."""
    auto_heal = _maybe_auto_heal_turn()
    speaker = _normalize_speaker(speaker) or (speaker or "").strip().lower()
    if speaker in META_SPEAKERS:
        out = meta_dialogue_turn(speaker, operator_note=operator_note, canvas=canvas)
        if auto_heal:
            out["auto_heal"] = auto_heal
        return out
    if speaker not in ("local", "remote"):
        return {"ok": False, "error": "speaker must be local, remote, or remote_meta_a/b", "auto_heal": auto_heal}

    wake_reason = ""
    if speaker == "remote":
        ok_wake, wake_reason = _remote_may_wake(force=force_wake)
        if not ok_wake:
            return {
                "ok": False,
                "error": wake_reason,
                "speaker": "remote",
                "remote_asleep": True,
                "cursor": read_cursor(),
            }
    elif speaker == "local":
        ok_wake, wake_reason = _local_may_wake(force=force_wake, operator_note=operator_note)
        if not ok_wake:
            return {
                "ok": False,
                "error": wake_reason,
                "speaker": "local",
                "local_asleep": True,
                "cursor": read_cursor(),
            }

    canvas_text = (canvas or read_desk().get("text") or "").strip()
    orchestrator_wake = "## Orchestrator memory" in (operator_note or "")
    if speaker == "local":
        canvas_text = _trim_canvas_for_local(canvas_text, max_chars=2200 if orchestrator_wake else 4500)
    peer = "remote" if speaker == "local" else "local"
    peer_label = "DeepSeek" if speaker == "local" else "Local (desk orchestrator)"
    last_peer = _last_peer_message(speaker)

    blocks: list[str] = []
    if speaker == "local" and orchestrator_wake:
        blocks.append(operator_note.strip()[:3500])
        blocks.append(f"## Canvas reference (trimmed)\n{canvas_text[:1200]}")
    else:
        blocks.append(f"## Shared canvas\n{canvas_text[:8000 if speaker == 'remote' else 5000]}")
        if last_peer:
            blocks.append(f"## Last {peer_label} message\n{last_peer}")
        if operator_note.strip() and not orchestrator_wake:
            blocks.append(f"## Operator note\n{operator_note.strip()[:1000]}")
    steer_lines = _drain_desk_steer() + _drain_operator_inbox()
    if steer_lines:
        blocks.append("## Operator steer\n" + "\n".join(f"- {s}" for s in steer_lines))
    if speaker == "remote" and wake_reason == "board_edit_pending":
        blocks.append(
            "## Wake reason\nLocal (slow desk orchestrator) edited the board — you wake on canvas edit only."
        )
    if speaker == "local" and wake_reason == "remote_board_edit_pending":
        blocks.append(
            "## Wake reason\nDeepSeek edited the board — you wake to complete the handoff loop. "
            "Read their Reply instruction and respond with board edit."
        )
    blocks.append(
        "## Protocol\n"
        "Always output ### Reply and ### Canvas edit. "
        "Never ask the operator to log moves — YOU edit the canvas. "
        "Canvas edit is what wakes the other seat."
    )
    blocks.append(f"## Your turn\nYou are **{speaker}**. Respond and provide canvas edit.")

    user = "\n\n".join(blocks)
    system = _compose_system_prompt(speaker)

    timing: dict[str, Any] | None = None
    try:
        if speaker == "local":
            if local_mode == "simulated":
                from mag.desk_local_simulator import respond

                model = "deterministic-desk-local-v1"
                raw = respond(user=user)
                invoke_mode = "simulated"
                provider = "simulated_local"
            else:
                model = _desk_local_model()
                try:
                    raw, invoke_mode, timing = _invoke_local_llm(system=system, user=user, model=model)
                except RuntimeError as exc:
                    return {
                        "ok": False,
                        "error": str(exc),
                        "speaker": speaker,
                        "model": model,
                        "hint": "Try Reset dialogue or Refresh Local; confirm gemma4:latest in ollama list",
                    }
                provider = "local"
        else:
            from mag.desk_timing import Timer, extract_provider_tokens, make_timing, record_timing
            from models.providers import chat_messages

            timer = Timer()
            res = chat_messages(
                "deepseek",
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=None,
                tier="T2",
                max_tokens=1024,
            )
            if not res.get("ok"):
                return {"ok": False, "error": res.get("error") or "deepseek failed", "speaker": speaker}
            raw = (res.get("text") or "").strip()
            provider = "deepseek"
            model = res.get("model")
            tin, tout = extract_provider_tokens(res.get("usage"))
            timing = record_timing(
                make_timing(
                    speaker=speaker,
                    elapsed_ms=timer.elapsed_ms(),
                    tokens_in=tin,
                    tokens_out=tout,
                    model=str(model) if model else None,
                    provider=provider,
                )
            )
    except Exception as e:
        return {"ok": False, "error": str(e), "speaker": speaker}

    reply, canvas_edit = _parse_sections(raw, speaker=speaker)
    local_adapter: dict[str, Any] | None = None
    if speaker == "local":
        from mag.desk_local_adapter import (
            canvas_fingerprint,
            local_heading_stall_detected,
            normalize_local_canvas_edit,
        )

        log_lines: list[str] = []
        if DIALOGUE_LOG.is_file():
            log_lines = DIALOGUE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        stall = local_heading_stall_detected(log_lines)
        canvas_edit, local_adapter = normalize_local_canvas_edit(
            canvas_edit,
            reply=reply,
            operator_note=operator_note,
        )
        if stall and local_adapter.get("quality_after") != "move":
            canvas_edit, local_adapter = normalize_local_canvas_edit(
                "",
                reply=reply,
                operator_note=operator_note,
            )
            local_adapter["stall_break"] = True
        local_adapter["heading_stall"] = stall
    if speaker == "local" and not (reply or "").strip() and not _meaningful_canvas_edit(canvas_edit):
        return {
            "ok": False,
            "error": "local model returned empty reply and canvas edit",
            "speaker": speaker,
            "model": model,
            "raw_preview": (raw or "")[:120],
            "hint": "Refresh Local or check Ollama (gemma4:latest can take ~60s on cold start)",
        }
    arena_sync: dict[str, Any] | None = None
    if canvas_edit:
        skip_append = False
        if speaker == "local":
            from mag.desk_local_adapter import canvas_fingerprint

            desk_text = read_desk().get("text") or ""
            last_local = re.findall(
                r"###\s+Local\s*[·\-][^\n]*\n([\s\S]*?)(?=\n###\s+|\n##\s+|\Z)",
                desk_text,
                re.I,
            )
            if last_local and canvas_fingerprint(last_local[-1]) == canvas_fingerprint(canvas_edit):
                skip_append = True
        if not skip_append:
            append_desk_raw(canvas_edit)
            canvas_text = read_desk().get("text") or canvas_text
        arena_sync = _maybe_sync_arena_from_edit(canvas_edit, speaker=speaker)

    row = {
        "speaker": speaker,
        "reply": reply,
        "canvas_edit": canvas_edit,
        "provider": provider,
        "model": model,
        "role": DESK_LOCAL_ROLE if speaker == "local" else "deepseek",
    }
    if timing:
        row["timing"] = timing
    if local_adapter:
        row["local_adapter"] = local_adapter
    if speaker == "local" and local_adapter and not _local_canvas_wake_ok(canvas_edit):
        row["wake_blocked"] = True
    _append_dialogue_log(row)
    cur = write_cursor(speaker, last_speaker=speaker)
    if speaker == "local":
        wake_ok = _local_canvas_wake_ok(canvas_edit)
        if wake_ok:
            _set_remote_state(asleep=False, wake_pending=True)
            _set_local_wake_pending(False)
        else:
            _set_remote_state(asleep=True, wake_pending=False)
    elif speaker == "remote":
        _set_remote_state(asleep=True, wake_pending=False)
        if _meaningful_canvas_edit(canvas_edit):
            _set_local_wake_pending(True)
        else:
            _set_local_wake_pending(False)
    cur = read_cursor()

    from mag.desk_timing import format_timing_row, last_by_speaker

    out = {
        "ok": True,
        "speaker": speaker,
        "reply": reply,
        "canvas_edit": canvas_edit,
        "canvas": canvas_text,
        "cursor": cur,
        "provider": provider,
        "model": model,
        "remote_asleep": cur.get("remote_asleep", True),
        "local_wake_pending": cur.get("local_wake_pending", False),
        "wake_reason": wake_reason or None,
        "auto_heal": auto_heal,
        "steering_enabled": desk_steering_enabled(),
        "timing": timing,
        "timings": last_by_speaker(),
        "timing_row": format_timing_row(),
        "arena_sync": arena_sync,
        "local_adapter": local_adapter,
        "local_mode": local_mode if speaker == "local" else None,
    }
    if speaker == "local" and local_adapter and not _local_canvas_wake_ok(canvas_edit):
        out["wake_blocked"] = True
        out["wake_blocked_reason"] = local_adapter.get("quality_after") or "no_move"
        out["hint"] = "Local canvas edit had no extractable move — Remote not woken. Check Reply for move line."
    return out


def slow_wake(*, operator_note: str = "", canvas: str | None = None) -> dict[str, Any]:
    """Slow (Local) speaks; fast (DeepSeek) wakes only if Local edits the board."""
    auto_heal = _maybe_auto_heal_turn()
    local = dialogue_turn("local", operator_note=operator_note, canvas=canvas)
    if not local.get("ok"):
        out = {"ok": False, "mode": "slow_wake", "local": local, "error": local.get("error")}
        if auto_heal:
            out["auto_heal"] = auto_heal
        return out

    if not _meaningful_canvas_edit(local.get("canvas_edit") or ""):
        cur = read_cursor()
        out = {
            "ok": True,
            "mode": "slow_wake",
            "woke": False,
            "reason": "no_canvas_edit",
            "local": local,
            "remote": None,
            "cursor": cur,
            "remote_asleep": True,
        }
        if auto_heal:
            out["auto_heal"] = auto_heal
        return out

    edit = (local.get("canvas_edit") or "")[:900]
    wake_note = (
        "Local (L0/slow) edited the board — you wake on board edits only.\n"
        "Respond to the canvas edit. Note Local's limitation if output truncated or vague.\n\n"
        f"### Local's board edit\n{edit}"
    )
    remote = dialogue_turn("remote", operator_note=wake_note, canvas=local.get("canvas"))
    woke = bool(remote.get("ok"))
    out: dict[str, Any] = {
        "ok": True,
        "mode": "slow_wake",
        "woke": woke,
        "local": local,
        "remote": remote if woke else None,
        "cursor": read_cursor(),
    }
    if not woke:
        out["remote_error"] = remote.get("error")
        out["reason"] = "remote_failed"
    else:
        out["reason"] = "board_edit"
    if woke and read_cursor().get("local_wake_pending"):
        follow = dialogue_turn(
            "local",
            operator_note=(
                "DeepSeek edited the board — complete this handoff. "
                "Read their Reply instruction; respond with ### Reply and ### Canvas edit."
            ),
            canvas=remote.get("canvas") if remote else None,
            force_wake=True,
        )
        out["local_followup"] = follow
        if follow.get("ok"):
            out["loop_closed"] = True
    if auto_heal:
        out["auto_heal"] = auto_heal
    return out


def handoff_loop(
    *,
    handoffs: int = 5,
    operator_note: str = "",
    canvas: str | None = None,
) -> dict[str, Any]:
    """Bidirectional handoffs: Local board edit → DeepSeek → DeepSeek board edit → Local …"""
    n = max(1, min(int(handoffs or 5), 5))
    turns: list[dict[str, Any]] = []
    canvas_text = canvas
    kickoff = (operator_note or "").strip() or "Run the 5-handoff escalation test. Follow each HANDOFF prompt."

    for i in range(n):
        esc = HANDOFF_ESCALATION[i] if i < len(HANDOFF_ESCALATION) else f"HANDOFF {i + 1}/{n}"
        local_note = f"{kickoff}\n\n{esc}" if i == 0 else esc
        force_local = i == 0 or bool(read_cursor().get("local_wake_pending"))

        local = dialogue_turn(
            "local",
            operator_note=local_note,
            canvas=canvas_text,
            force_wake=force_local,
        )
        if not local.get("ok"):
            return {
                "ok": False,
                "mode": "handoff_loop",
                "error": local.get("error"),
                "handoff": i + 1,
                "turns": turns,
                "failed_speaker": "local",
            }
        turns.append({**local, "handoff": i + 1, "leg": "local"})
        canvas_text = local.get("canvas") or canvas_text

        if not _meaningful_canvas_edit(local.get("canvas_edit") or ""):
            return {
                "ok": True,
                "mode": "handoff_loop",
                "completed": i,
                "handoffs_requested": n,
                "reason": "local_no_board_edit",
                "turns": turns,
                "canvas": canvas_text,
                "cursor": read_cursor(),
            }

        edit = (local.get("canvas_edit") or "")[:900]
        remote_note = (
            f"{esc}\n\nLocal edited the board — respond and edit canvas. "
            "End Reply with one explicit instruction for Local's next turn.\n\n"
            f"### Local's board edit\n{edit}"
        )
        remote = dialogue_turn("remote", operator_note=remote_note, canvas=canvas_text)
        if not remote.get("ok"):
            return {
                "ok": False,
                "mode": "handoff_loop",
                "error": remote.get("error"),
                "handoff": i + 1,
                "turns": turns,
                "failed_speaker": "remote",
            }
        turns.append({**remote, "handoff": i + 1, "leg": "remote"})
        canvas_text = remote.get("canvas") or canvas_text

        if not _meaningful_canvas_edit(remote.get("canvas_edit") or ""):
            return {
                "ok": True,
                "mode": "handoff_loop",
                "completed": i + 1,
                "handoffs_requested": n,
                "reason": "remote_no_board_edit",
                "turns": turns,
                "canvas": canvas_text,
                "cursor": read_cursor(),
                "hint": "DeepSeek did not edit board — Local will not wake for next handoff",
            }

    return {
        "ok": True,
        "mode": "handoff_loop",
        "completed": n,
        "handoffs_requested": n,
        "reason": "complete",
        "turns": turns,
        "canvas": canvas_text,
        "cursor": read_cursor(),
    }


def ping_pong(*, rounds: int = 1, operator_note: str = "", canvas: str | None = None) -> dict[str, Any]:
    """Legacy alias — one slow→fast cycle per round (no fast→slow ping back)."""
    return handoff_loop(handoffs=max(1, min(int(rounds or 1), 4)), operator_note=operator_note, canvas=canvas)
