"""Voice scratch pad — transcript accumulates, agent wakes on commit.

Architecture (operator intent 2026-08-07):
  mic STT → scratch pad (REST text) → silence/commit → wake agent
  more speech before commit → append, cancel premature wake
  corrections land in the same pad
  local Ollama for quick turns; deepseek / swarm for research-grade replies

Schema: mag_voice_scratch.v1
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import ROOT

SCHEMA = "mag_voice_scratch.v1"
PAD_DIR = ROOT / "memory" / "working" / "voice_scratch"
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

# Default silence before commit is client-side; server just stores state.
DEFAULT_MODE = "local"  # local | deepseek | swarm


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(session_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "", (session_id or "").strip())[:64]
    return s or f"voice-{uuid4().hex[:10]}"


def _path(session_id: str) -> Path:
    return PAD_DIR / f"{_safe_id(session_id)}.json"


def _lock(session_id: str) -> threading.Lock:
    sid = _safe_id(session_id)
    with _LOCKS_GUARD:
        if sid not in _LOCKS:
            _LOCKS[sid] = threading.Lock()
        return _LOCKS[sid]


def _empty(session_id: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "session_id": _safe_id(session_id),
        "status": "idle",  # idle | drafting | committed | thinking | answered
        "draft": "",
        "draft_parts": [],
        "committed": "",
        "generation": 0,  # bump to cancel stale agent wakes
        "last_answer": "",
        "mode": DEFAULT_MODE,
        "updated": _utc(),
        "history": [],  # short {role,text} for UI
    }


def load_pad(session_id: str) -> dict[str, Any]:
    path = _path(session_id)
    if not path.is_file():
        return _empty(session_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty(session_id)
        base = _empty(session_id)
        base.update(data)
        return base
    except Exception:
        return _empty(session_id)


def save_pad(session_id: str, data: dict[str, Any]) -> None:
    PAD_DIR.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["session_id"] = _safe_id(session_id)
    data["updated"] = _utc()
    data["schema"] = SCHEMA
    _path(session_id).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def clear_pad(session_id: str) -> dict[str, Any]:
    with _lock(session_id):
        path = _path(session_id)
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass
        return {"ok": True, "schema": SCHEMA, "session_id": _safe_id(session_id), "cleared": True}


def _merge_text(existing: str, chunk: str) -> str:
    """Append speech chunk; light de-dupe if STT repeats the last phrase."""
    a = (existing or "").strip()
    b = (chunk or "").strip()
    if not b:
        return a
    if not a:
        return b
    # If new chunk starts with old draft, replace (full re-transcript)
    if b.lower().startswith(a.lower()[: min(40, len(a))]) and len(b) >= len(a):
        return b
    # If old ends with new (echo), keep old
    if a.lower().endswith(b.lower()):
        return a
    # Correction markers often restart the sentence
    return f"{a} {b}".strip()


def append_draft(
    session_id: str,
    text: str,
    *,
    interim: bool = False,
    mode: str | None = None,
) -> dict[str, Any]:
    """Add STT text to the pad. Does not wake the agent."""
    with _lock(session_id):
        pad = load_pad(session_id)
        if mode in ("local", "deepseek", "swarm"):
            pad["mode"] = mode
        chunk = (text or "").strip()
        if not chunk:
            return {"ok": True, "schema": SCHEMA, "pad": pad, "appended": False}

        # New speech while thinking/answered → interrupt, new generation
        if pad.get("status") in ("thinking", "answered", "committed"):
            pad["generation"] = int(pad.get("generation") or 0) + 1
            pad["status"] = "drafting"
            # Keep prior committed line in history only
            if pad.get("committed") and pad.get("status") != "drafting":
                pass

        if interim:
            pad["interim"] = chunk
            pad["status"] = "drafting"
        else:
            pad["draft"] = _merge_text(str(pad.get("draft") or ""), chunk)
            parts = list(pad.get("draft_parts") or [])
            parts.append({"ts": _utc(), "text": chunk})
            pad["draft_parts"] = parts[-40:]
            pad["interim"] = ""
            pad["status"] = "drafting"
            # Bump generation so any in-flight commit is stale
            pad["generation"] = int(pad.get("generation") or 0) + 1

        save_pad(session_id, pad)
        return {
            "ok": True,
            "schema": SCHEMA,
            "pad": {
                "session_id": pad["session_id"],
                "status": pad["status"],
                "draft": pad.get("draft") or "",
                "interim": pad.get("interim") or "",
                "generation": pad.get("generation"),
                "mode": pad.get("mode"),
            },
            "appended": True,
            "wake": False,
        }


def commit_and_wake(
    session_id: str,
    *,
    text: str | None = None,
    mode: str | None = None,
    force_generation: int | None = None,
) -> dict[str, Any]:
    """Finalize draft → wake agent. Stale generation returns cancelled."""
    with _lock(session_id):
        pad = load_pad(session_id)
        if mode in ("local", "deepseek", "swarm"):
            pad["mode"] = mode
        draft = (text or pad.get("draft") or "").strip()
        interim = str(pad.get("interim") or "").strip()
        if interim and interim not in draft:
            draft = _merge_text(draft, interim)
        if not draft:
            return {
                "ok": False,
                "schema": SCHEMA,
                "error": "empty scratch pad — nothing to commit",
                "pad": pad,
            }

        gen = int(pad.get("generation") or 0)
        if force_generation is not None and int(force_generation) != gen:
            return {
                "ok": False,
                "schema": SCHEMA,
                "cancelled": True,
                "error": "stale commit — operator kept talking",
                "generation": gen,
            }

        pad["committed"] = draft
        pad["draft"] = ""
        pad["interim"] = ""
        pad["status"] = "thinking"
        pad["wake_generation"] = gen
        save_pad(session_id, pad)
        wake_gen = gen
        mode_use = str(pad.get("mode") or DEFAULT_MODE)

    # Agent wake outside lock (can be slow)
    result = _wake_agent(session_id, draft, mode=mode_use, generation=wake_gen)
    return result


def _wake_agent(
    session_id: str,
    transcript: str,
    *,
    mode: str,
    generation: int,
) -> dict[str, Any]:
    # Check cancel before expensive work
    with _lock(session_id):
        pad0 = load_pad(session_id)
        if int(pad0.get("generation") or 0) != generation:
            return {
                "ok": True,
                "schema": SCHEMA,
                "cancelled": True,
                "error": "answer discarded — operator kept talking",
                "generation": pad0.get("generation"),
                "pad": {
                    "status": pad0.get("status"),
                    "draft": pad0.get("draft"),
                    "generation": pad0.get("generation"),
                },
            }
        hist_lines = []
        for t in (pad0.get("history") or [])[-6:]:
            role = "You" if t.get("role") == "user" else "Mag"
            hist_lines.append(f"{role}: {str(t.get('text') or '')[:200]}")
        history_block = "\n".join(hist_lines)

    mode = (mode or DEFAULT_MODE).lower()
    out: dict[str, Any]

    try:
        if mode in ("swarm", "pipeline"):
            from mag.voice_pipeline import run_voice_pipeline

            out = run_voice_pipeline(
                transcript,
                session_id=session_id,
                history_block=history_block,
            )
            out.setdefault("seat", "pipeline")
            out.setdefault("route", out.get("route") or "local_format_swarm_human")
        elif mode == "deepseek":
            from mag.voice_turn import handle_voice_turn

            out = handle_voice_turn(
                {
                    "text": transcript,
                    "session_id": session_id,
                    "seat": "deepseek",
                    "channel": "voice_scratch",
                    "conversation": True,
                }
            )
        else:
            from mag.voice_turn import handle_voice_turn

            out = handle_voice_turn(
                {
                    "text": transcript,
                    "session_id": session_id,
                    "seat": "local",
                    "channel": "voice_scratch",
                    "conversation": True,
                }
            )
    except Exception as exc:
        # Never crash cast — always return something speakable
        out = {
            "ok": True,
            "answer": (
                "I hit a snag mid-thought, but I'm still here. "
                "Say that again and I'll keep it simple."
            ),
            "speak_text": (
                "I hit a snag mid-thought, but I'm still here. "
                "Say that again and I'll keep it simple."
            ),
            "error": str(exc)[:200],
            "seat": "fallback",
            "route": "crash_guard",
        }

    with _lock(session_id):
        pad = load_pad(session_id)
        if int(pad.get("generation") or 0) != generation:
            return {
                "ok": True,
                "schema": SCHEMA,
                "cancelled": True,
                "error": "answer discarded — operator kept talking",
                "agent": {"ok": out.get("ok"), "route": out.get("route")},
                "generation": pad.get("generation"),
                "pad": {
                    "status": pad.get("status"),
                    "draft": pad.get("draft"),
                    "generation": pad.get("generation"),
                },
            }
        answer = str(out.get("speak_text") or out.get("answer") or "").strip()
        pad["last_answer"] = answer
        pad["status"] = "answered" if (out.get("ok") or answer) else "idle"
        pad["last_agent"] = {
            "ok": out.get("ok"),
            "seat": out.get("seat"),
            "route": out.get("route"),
            "model": out.get("model"),
            "mode": mode,
            "steps": out.get("steps"),
            "elapsed_ms": out.get("elapsed_ms"),
        }
        hist = list(pad.get("history") or [])
        hist.append({"role": "user", "text": transcript[:800], "ts": _utc()})
        if answer:
            hist.append({"role": "assistant", "text": answer[:800], "ts": _utc()})
        pad["history"] = hist[-24:]
        save_pad(session_id, pad)

    return {
        "ok": bool(out.get("ok") or answer),
        "schema": SCHEMA,
        "cancelled": False,
        "session_id": _safe_id(session_id),
        "committed": transcript,
        "answer": out.get("answer") or answer,
        "speak_text": out.get("speak_text") or answer,
        "speak": True,
        "server_tts": False,
        "seat": out.get("seat"),
        "route": out.get("route"),
        "model": out.get("model"),
        "mode": mode,
        "generation": generation,
        "history_turns": out.get("history_turns"),
        "timing": out.get("timing"),
        "steps": out.get("steps"),
        "elapsed_ms": out.get("elapsed_ms"),
        "within_budget": out.get("within_budget"),
        "brief": out.get("brief"),
        "plan": out.get("plan"),
        "error": out.get("error"),
        "token_note": out.get("token_note")
        or "local format → deepseek swarm → human speak",
    }


def handle_scratch(body: dict[str, Any] | None) -> dict[str, Any]:
    """REST dispatcher for scratch pad actions."""
    body = body or {}
    session_id = _safe_id(str(body.get("session_id") or "").strip() or f"voice-{uuid4().hex[:10]}")
    action = str(body.get("action") or body.get("op") or "status").strip().lower()
    mode = str(body.get("mode") or body.get("seat_mode") or "").strip().lower() or None
    if mode == "auto":
        mode = None

    if action in ("clear", "reset", "new"):
        return clear_pad(session_id)

    if action in ("status", "get", "pad"):
        pad = load_pad(session_id)
        return {"ok": True, "schema": SCHEMA, "pad": pad}

    if action in ("append", "partial", "draft"):
        return append_draft(
            session_id,
            str(body.get("text") or body.get("transcript") or ""),
            interim=bool(body.get("interim")),
            mode=mode,
        )

    if action in ("commit", "wake", "done", "finalize"):
        return commit_and_wake(
            session_id,
            text=str(body.get("text") or "").strip() or None,
            mode=mode,
            force_generation=body.get("generation"),
        )

    # Legacy: text without action = append if interim else commit path from voice UI
    text = str(body.get("text") or body.get("transcript") or "").strip()
    if text and body.get("interim"):
        return append_draft(session_id, text, interim=True, mode=mode)
    if text:
        append_draft(session_id, text, interim=False, mode=mode)
        return commit_and_wake(session_id, mode=mode)

    return {"ok": False, "schema": SCHEMA, "error": f"unknown action {action!r}"}
