"""Voice → REST build tasks for cheap coding agents.

Operator (or Mag) files a small job when voice surfaces a product need
(e.g. better TTS intonation). Cheap seats (DeepSeek/Cursor) implement;
Grok freezes hard design only.

Schema: mag_voice_task.v1
Store: memory/working/voice_build_tasks.jsonl
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_voice_task.v1"
TASKS_PATH = ROOT / "memory" / "working" / "voice_build_tasks.jsonl"
LEDGER_DIR = ROOT / "memory" / "working" / "voice_tasks"

# Phrases that should become build tasks (and get an honest in-band answer)
_PRODUCT_NEED = re.compile(
    r"\b("
    r"change (your |the )?voice|voice model|more intonation|sound more human|"
    r"different voice|female voice|male voice|speak slower|speak faster|"
    r"edge-?tts|piper|tts\b|read better|sound better|"
    r"crazy sounding|sounds crazy|response time|how long|latency|"
    r"voice that.?s used|show (the )?voice|show (the )?time|in the window"
    r")\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_id() -> str:
    return "vt-" + uuid.uuid4().hex[:10]


def is_product_need(text: str) -> bool:
    return bool(_PRODUCT_NEED.search(text or ""))


def file_task(
    goal: str,
    *,
    transcript: str = "",
    session_id: str = "",
    seat_hint: str = "deepseek",
    tags: list[str] | None = None,
    enqueue: bool = True,
) -> dict[str, Any]:
    """Append a REST-shaped task for cheap agents to code like a builder seat."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "goal required"}

    task = {
        "schema": SCHEMA,
        "task_id": _task_id(),
        "ts": _utc(),
        "status": "open",
        "goal": goal[:2000],
        "transcript": (transcript or goal)[:1500],
        "session_id": session_id or "",
        "seat_hint": seat_hint,
        "tags": tags or ["voice", "build"],
        "acceptance": [
            "Works on dashboard /voice without cast-only dependency",
            "Does not break simple listen→answer→speak loop",
            "FILE residual or trail line on done",
        ],
        "builder_prompt": _builder_prompt(goal, transcript or goal),
    }

    TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TASKS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(task, default=str) + "\n")

    # Per-task card for agents to open
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    card = LEDGER_DIR / f"{task['task_id']}.md"
    card.write_text(
        f"# Voice build task `{task['task_id']}`\n\n"
        f"**Status:** open  \n"
        f"**Seat hint:** `{seat_hint}`  \n"
        f"**Session:** `{session_id}`  \n\n"
        f"## Goal\n\n{goal}\n\n"
        f"## Operator said (voice)\n\n> {transcript or goal}\n\n"
        f"## Builder brief\n\n{task['builder_prompt']}\n\n"
        f"## Acceptance\n\n"
        + "\n".join(f"- {a}" for a in task["acceptance"])
        + "\n",
        encoding="utf-8",
    )

    enq: dict[str, Any] | None = None
    if enqueue:
        try:
            from mag.orchestrator import enqueue as orch_enqueue

            rec = orch_enqueue(
                goal=(
                    f"[voice-task {task['task_id']}] {goal[:400]} "
                    f"— read {card.as_posix()} and implement"
                ),
                tag=f"voice-task-{task['task_id']}",
                seat=seat_hint if seat_hint in ("deepseek", "local", "cursor") else "deepseek",
            )
            enq = rec if isinstance(rec, dict) else {"raw": str(rec)[:200]}
            task["enqueued"] = True
        except Exception as exc:
            enq = {"ok": False, "error": str(exc)[:160]}
            task["enqueued"] = False

    try:
        from mag.training_events import emit

        emit(
            "voice_turn",
            join={"session_id": session_id or "", "task_id": task["task_id"]},
            input_data={"transcript": (transcript or "")[:400], "goal": goal[:400]},
            action={"kind": "voice_build_task", "seat_hint": seat_hint},
            outcome={"ok": True, "path": str(card)},
            pattern_tags=["voice", "build_task", "cheap_agent"],
            tier_max="T2",
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "task": task,
        "card_path": str(card.relative_to(ROOT)) if ROOT in card.parents else str(card),
        "enqueue": enq,
    }


def _builder_prompt(goal: str, transcript: str) -> str:
    return (
        "You are a cheap coding agent on Mag (DeepSeek/Cursor). "
        "Implement this product need without breaking the simple voice loop "
        "(listen → answer → speak on /voice).\n\n"
        f"GOAL: {goal}\n"
        f"OPERATOR VOICE: {transcript}\n\n"
        "Constraints:\n"
        "- Prefer dashboard/static/cast-voice.html + mag/* small modules\n"
        "- Browser TTS: SpeechSynthesisUtterance voice/rate/pitch if possible\n"
        "- Optional later: Piper/edge-tts as extra seat, not required for first pass\n"
        "- Do not reintroduce VAD/swarm complexity into the default UI\n"
        "- FILE a short note in memory/working when done\n"
    )


def list_tasks(*, limit: int = 30, status: str | None = "open") -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if TASKS_PATH.is_file():
        for line in TASKS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if status:
        rows = [r for r in rows if r.get("status") == status]
    rows = list(reversed(rows[-limit:]))
    return {"ok": True, "schema": SCHEMA, "n": len(rows), "tasks": rows}


def handle_voice_task(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or "list").strip().lower()
    if action in ("list", "status", "get"):
        return list_tasks(
            limit=int(body.get("limit") or 30),
            status=body.get("status", "open"),
        )
    if action in ("create", "file", "new"):
        return file_task(
            str(body.get("goal") or body.get("text") or ""),
            transcript=str(body.get("transcript") or body.get("text") or ""),
            session_id=str(body.get("session_id") or ""),
            seat_hint=str(body.get("seat_hint") or "deepseek"),
            tags=list(body.get("tags") or ["voice", "build"]),
            enqueue=body.get("enqueue", True) is not False,
        )
    return {"ok": False, "error": f"unknown action {action!r}"}


def product_need_reply(transcript: str, *, session_id: str = "") -> dict[str, Any] | None:
    """If voice is asking for product change, file a task and return a spoken answer."""
    if not is_product_need(transcript):
        return None
    tl = (transcript or "").lower()
    # UX meta: show voice + latency in window (implement in UI; still file task)
    if re.search(r"crazy sound|sounds crazy|response time|how long|latency|voice that|in the window|show (the )?(voice|time)", tl):
        filed = file_task(
            goal=(
                "Voice UX: show active TTS voice name and last response latency (ms) "
                "in the Mag Voice window; keep simple loop. "
                f"Triggered by: {transcript[:300]}"
            ),
            transcript=transcript,
            session_id=session_id,
            seat_hint="deepseek",
            tags=["voice", "ux", "latency", "build"],
        )
        tid = (filed.get("task") or {}).get("task_id") or "?"
        answer = (
            "You're right — the window should show which voice is speaking and how long "
            "the answer took. That strip is on the page now after refresh: voice name plus "
            f"response time. I also filed task {tid} so a cheap agent can harden it. "
            "Sorry if the last line sounded off — that was TTS, not a new topic about RAM."
        )
        return {
            "ok": True,
            "answer": answer,
            "speak_text": answer,
            "seat": "mag",
            "route": "product_task",
            "provider": "voice_tasks",
            "used_llm": False,
            "task": filed.get("task"),
            "card_path": filed.get("card_path"),
        }
    filed = file_task(
        goal=(
            "Voice UX: richer TTS — voice selection, rate/pitch/intonation controls, "
            "prefer more natural browser voices; optional Piper/edge-tts later. "
            f"Triggered by: {transcript[:300]}"
        ),
        transcript=transcript,
        session_id=session_id,
        seat_hint="deepseek",
        tags=["voice", "tts", "intonation", "build"],
    )
    tid = (filed.get("task") or {}).get("task_id") or "?"
    answer = (
        "Got it — Mag can change how I sound in the browser right now with the voice "
        "and intonation controls on this page. I also filed a build task "
        f"{tid} so a cheap coding agent can harden better TTS "
        "(more natural voices, optional Piper later). "
        "Try the voice dropdown and intonation slider after you refresh."
    )
    return {
        "ok": True,
        "answer": answer,
        "speak_text": answer,
        "seat": "mag",
        "route": "product_task",
        "provider": "voice_tasks",
        "used_llm": False,
        "task": filed.get("task"),
        "card_path": filed.get("card_path"),
    }
