"""Voice shadow scout — DeepSeek researches in the background; local draws on it.

Mode idea (operator 2026-08):
  Local answers immediately (cheap/fast).
  DeepSeek runs a longer scout on the same utterance / thread.
  When ready, next local turns load that context — higher function without blocking the loop.

Schema: mag_voice_shadow.v1
Files: memory/working/voice_shadow/{session_id}.json
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import ROOT

SCHEMA = "mag_voice_shadow.v1"
SHADOW_DIR = ROOT / "memory" / "working" / "voice_shadow"
_JOBS: dict[str, threading.Thread] = {}
_LOCK = threading.Lock()

SCOUT_SYSTEM = """You are Mag's background dig scout (DeepSeek). Operator talks to a small local model live.
Fill a shared dig board they will pull from next turn. Not a full essay.
Include:
FACTS: 3-6 short distinctions (truthful, useful)
ANGLES: 2-3 ways to answer well
SOCRATIC: 2-3 questions that dig deeper (Plato: define the thing; Bernays: who benefits; Jung: what's under the ask) — one line each, end with ?
PITFALLS: 1-2 wrong pivots (e.g. sticky RAM/BIOS when they meant Smart Access Memory)
READY LINE: one sentence local can use if asked "what did you find?"
Under 220 words. Plain text."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(session_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "", (session_id or "").strip())[:64]
    return s or f"voice-{uuid4().hex[:10]}"


def _path(session_id: str) -> Path:
    return SHADOW_DIR / f"{_safe(session_id)}.json"


def load_shadow(session_id: str) -> dict[str, Any]:
    path = _path(session_id)
    if not path.is_file():
        return {
            "schema": SCHEMA,
            "session_id": _safe(session_id),
            "status": "idle",
            "brief": "",
            "trigger": "",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("status", "idle")
            return data
    except Exception:
        pass
    return {"schema": SCHEMA, "session_id": _safe(session_id), "status": "idle", "brief": ""}


def save_shadow(session_id: str, data: dict[str, Any]) -> None:
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["schema"] = SCHEMA
    data["session_id"] = _safe(session_id)
    data["updated"] = _utc()
    _path(session_id).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def shadow_context_for_local(session_id: str, *, max_chars: int = 900) -> str:
    """Excerpt for local model prompt — empty if not ready."""
    sh = load_shadow(session_id)
    if sh.get("status") != "ready":
        return ""
    brief = str(sh.get("brief") or "").strip()
    if not brief:
        return ""
    if len(brief) > max_chars:
        brief = brief[: max_chars - 1].rstrip() + "…"
    return (
        f"## Background scout (DeepSeek — use if relevant, don't recite wholesale)\n"
        f"Trigger: {str(sh.get('trigger') or '')[:200]}\n"
        f"{brief}"
    )


def _run_scout(session_id: str, trigger: str, job_id: str) -> None:
    sid = _safe(session_id)
    try:
        from models.providers import chat_provider

        timeout_s = float(os.environ.get("MAG_VOICE_SHADOW_TIMEOUT_S", "55") or "55")
        t0 = time.monotonic()
        res = chat_provider(
            "deepseek",
            SCOUT_SYSTEM,
            f"Operator said (voice):\n{trigger}\n\nWrite the scout brief for the local seat.",
            tier="T2",
            max_tokens=280,
            temperature=0.35,
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        brief = str(res.get("text") or res.get("content") or "").strip()
        with _LOCK:
            cur = load_shadow(sid)
            # Ignore stale job
            if cur.get("job_id") and cur.get("job_id") != job_id:
                return
            if res.get("ok") and brief:
                cur.update(
                    {
                        "status": "ready",
                        "brief": brief,
                        "trigger": trigger[:500],
                        "job_id": job_id,
                        "model": res.get("model"),
                        "elapsed_ms": elapsed,
                        "error": None,
                    }
                )
                try:
                    from mag.voice_dig_board import note_scout_ready

                    note_scout_ready(session_id=sid, trigger=trigger, brief=brief)
                except Exception:
                    pass
            else:
                cur.update(
                    {
                        "status": "failed",
                        "error": str(res.get("error") or "empty scout")[:240],
                        "job_id": job_id,
                        "elapsed_ms": elapsed,
                    }
                )
            save_shadow(sid, cur)
    except Exception as exc:
        with _LOCK:
            cur = load_shadow(sid)
            if cur.get("job_id") == job_id:
                cur["status"] = "failed"
                cur["error"] = str(exc)[:240]
                save_shadow(sid, cur)
    finally:
        with _LOCK:
            _JOBS.pop(sid, None)


def start_shadow_scout(session_id: str, trigger: str) -> dict[str, Any]:
    """Kick DeepSeek scout in a daemon thread. Non-blocking."""
    sid = _safe(session_id)
    text = (trigger or "").strip()
    if len(text) < 3:
        return {"ok": False, "error": "trigger too short", "status": "idle"}

    # Don't stampede DeepSeek on every "uh huh"
    if len(text) < 12 and text.lower() in {"hi", "hey", "hello", "yes", "no", "ok", "okay", "thanks"}:
        return {"ok": True, "status": "skipped", "reason": "too_short_or_phatic"}

    job_id = uuid4().hex[:12]
    with _LOCK:
        # One scout per session at a time
        if sid in _JOBS and _JOBS[sid].is_alive():
            return {
                "ok": True,
                "status": "busy",
                "session_id": sid,
                "note": "scout already running",
            }
        save_shadow(
            sid,
            {
                "status": "running",
                "brief": "",
                "trigger": text[:500],
                "job_id": job_id,
                "started": _utc(),
            },
        )
        th = threading.Thread(
            target=_run_scout,
            args=(sid, text, job_id),
            name=f"voice-shadow-{sid[:8]}",
            daemon=True,
        )
        _JOBS[sid] = th
        th.start()

    return {
        "ok": True,
        "schema": SCHEMA,
        "status": "running",
        "session_id": sid,
        "job_id": job_id,
        "note": "DeepSeek scouting in background; local answers immediately",
    }


def shadow_status(session_id: str) -> dict[str, Any]:
    sh = load_shadow(session_id)
    return {
        "ok": True,
        "schema": SCHEMA,
        "session_id": _safe(session_id),
        "status": sh.get("status") or "idle",
        "has_brief": bool(str(sh.get("brief") or "").strip()),
        "trigger": (sh.get("trigger") or "")[:200],
        "error": sh.get("error"),
        "elapsed_ms": sh.get("elapsed_ms"),
        "updated": sh.get("updated"),
    }


def handle_shadow(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or "status").strip().lower()
    sid = str(body.get("session_id") or "").strip()
    if action in ("start", "scout", "kick"):
        return start_shadow_scout(sid, str(body.get("text") or body.get("trigger") or ""))
    if action in ("clear", "reset"):
        path = _path(sid)
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass
        return {"ok": True, "status": "idle", "cleared": True, "session_id": _safe(sid)}
    return shadow_status(sid)
