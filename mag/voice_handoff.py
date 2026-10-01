"""Voice handoff stack — FILE jobs to DeepSeek without interrupting the talk seat.

Law:
  - Local/voice stays the continuous mind (Grok-like UX on Mag Voice).
  - Scut / implement / multi-file → cold handoff: brief + pack + card.
  - DeepSeek runs async or queued; operator keeps talking.
  - Not: block the mic on a frontier call for every hard job.

Schema: mag_voice_handoff.v1
Tesuji: intention-fidelity + diary freeze; swarm economics.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _under_root(p: Path) -> bool:
    """True when p sits under ROOT; False for sandbox/external-basetemp paths."""
    try:
        p.relative_to(ROOT)
        return True
    except ValueError:
        return False

SCHEMA = "mag_voice_handoff.v1"
HANDOFF_DIR = ROOT / "memory" / "working" / "voice_handoffs"
INDEX_PATH = HANDOFF_DIR / "index.jsonl"

# Explicit: operator wants FILE not interrupt
_HANDOFF_HINT = re.compile(
    r"\b("
    r"hand\s*off|handoff|file (that |this |it )?(for|to) deepseek|"
    r"pass (that |this |it )?to deepseek|queue (that |this |it )?(for|to)|"
    r"let deepseek (do|handle|implement)|deepseek (should |can )?(do|handle|implement)|"
    r"spawn (a )?(worker|task)|file a (task|job|build)|"
    r"don'?t block|keep (me )?talking|background (that|this|it)|"
    r"implement that|build that|code that"
    r")\b",
    re.I,
)
# Jobs that should prefer handoff over blocking DeepSeek-on-the-mic
_SCUT_IMPLEMENT = re.compile(
    r"\b("
    r"implement|refactor|multi[- ]?file|write (the )?code|add (a )?feature|"
    r"fix the (bug|test)|wire (up |in )|patch |pull request|pytest|"
    r"build (the )?|create (the )?module|edit (all|every|several) files"
    r")\b",
    re.I,
)
# Operator wants answer *now* on the smarter seat (blocking ok)
_ANSWER_NOW = re.compile(
    r"\b("
    r"answer (me )?now|tell me now|think hard(er)?|fidelity mode|"
    r"use deepseek (to )?(answer|explain|discuss)|escalate"
    r")\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hid() -> str:
    return "vh-" + uuid.uuid4().hex[:10]


def wants_handoff(text: str, *, depth: str = "") -> bool:
    t = text or ""
    if _ANSWER_NOW.search(t) and not _HANDOFF_HINT.search(t):
        return False
    if _HANDOFF_HINT.search(t):
        return True
    if depth in ("heavy_code", "simple_code") and _SCUT_IMPLEMENT.search(t):
        return True
    if _SCUT_IMPLEMENT.search(t) and len(t) > 40:
        return True
    return False


def wants_blocking_smart(text: str) -> bool:
    """Explicit: smarter seat should answer on the mic now."""
    return bool(_ANSWER_NOW.search(text or "")) and not bool(_HANDOFF_HINT.search(text or ""))


def list_handoffs(*, limit: int = 20, status: str | None = "open") -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if INDEX_PATH.is_file():
        for line in INDEX_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if status:
        # latest status per handoff_id wins
        by_id: dict[str, dict[str, Any]] = {}
        for r in rows:
            hid = str(r.get("handoff_id") or "")
            if hid:
                by_id[hid] = r
        rows = list(by_id.values())
        rows = [r for r in rows if r.get("status") == status]
    rows = sorted(rows, key=lambda r: str(r.get("ts") or ""), reverse=True)[:limit]
    return {"ok": True, "schema": SCHEMA, "n": len(rows), "handoffs": rows}


def get_handoff(handoff_id: str) -> dict[str, Any]:
    path = HANDOFF_DIR / f"{handoff_id}.json"
    if not path.is_file():
        return {"ok": False, "error": "missing handoff"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"ok": True, "schema": SCHEMA, "handoff": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}


def ready_handoff_for_session(session_id: str) -> dict[str, Any] | None:
    """Latest completed handoff for this session not yet spoken."""
    sid = (session_id or "").strip()
    if not sid or not HANDOFF_DIR.is_dir():
        return None
    best = None
    for p in sorted(HANDOFF_DIR.glob("vh-*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(data.get("session_id") or "") != sid:
            continue
        if data.get("status") != "ready":
            continue
        if data.get("spoken"):
            continue
        best = data
        break
    return best


def mark_spoken(handoff_id: str) -> None:
    path = HANDOFF_DIR / f"{handoff_id}.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["spoken"] = True
        data["spoken_ts"] = _utc()
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        _index_row(data)
    except Exception:
        pass


def _index_row(data: dict[str, Any]) -> None:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": data.get("ts") or _utc(),
                    "handoff_id": data.get("handoff_id"),
                    "status": data.get("status"),
                    "session_id": data.get("session_id"),
                    "goal": str(data.get("goal") or "")[:160],
                    "seat": data.get("seat"),
                },
                default=str,
            )
            + "\n"
        )


def _write(data: dict[str, Any]) -> Path:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    path = HANDOFF_DIR / f"{data['handoff_id']}.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    _index_row(data)
    return path


def _pack_slice(max_chars: int = 1200) -> str:
    try:
        from mag.context_pack import build_context_pack, format_context_pack_text

        pack = build_context_pack(max_brief=600, max_live=300)
        text = format_context_pack_text(pack)
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text
    except Exception:
        return "(pack unavailable)"


def file_handoff(
    goal: str,
    *,
    transcript: str = "",
    session_id: str = "",
    brief: dict[str, Any] | None = None,
    seat: str = "deepseek",
    run_async: bool = True,
    freeze: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """FILE a cold job for DeepSeek (or seat). Voice keeps talking."""
    goal = (goal or transcript or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    hid = _hid()
    brief = brief or {}
    try:
        from mag.intention_brief import render_brief_for_model

        brief_text = render_brief_for_model(brief, spoken=False) if brief.get("goal") else ""
    except Exception:
        brief_text = ""
    if not brief_text:
        brief_text = f"## Goal\n{goal}\n\n## Operator said\n{transcript or goal}"

    pack = _pack_slice()
    freeze = freeze or {}
    if not freeze:
        try:
            from mag.diary_node import freeze_context

            freeze = freeze_context(
                session_id=session_id, channel="voice", reason="handoff"
            )
        except Exception:
            freeze = {}

    data: dict[str, Any] = {
        "schema": SCHEMA,
        "handoff_id": hid,
        "ts": _utc(),
        "status": "open",
        "spoken": False,
        "session_id": session_id or "",
        "seat": seat if seat in ("deepseek", "local", "cursor") else "deepseek",
        "goal": goal[:2000],
        "transcript": (transcript or goal)[:1500],
        "brief": {
            "goal": brief.get("goal"),
            "depth": brief.get("depth"),
            "why": brief.get("why"),
            "constraints": (brief.get("constraints") or [])[:6],
            "seat_recommend": brief.get("seat_recommend"),
        },
        "brief_text": brief_text[:4000],
        "pack_excerpt": pack[:1500],
        "frozen": {
            "day": freeze.get("day"),
            "agent_commit": (freeze.get("agent") or {}).get("content_commit"),
            "verkle_n": (freeze.get("session_verkle") or {}).get("n_leaves"),
            "freeze_hash": freeze.get("freeze_hash"),
        },
        "result": "",
        "error": "",
    }

    # Markdown card for builders
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    card = HANDOFF_DIR / f"{hid}.md"
    card.write_text(
        f"# Voice handoff `{hid}`\n\n"
        f"**Status:** open  \n"
        f"**Seat:** `{data['seat']}`  \n"
        f"**Session:** `{session_id}`  \n"
        f"**Day freeze:** `{data['frozen'].get('day')}`  \n\n"
        f"## Goal\n\n{goal}\n\n"
        f"## Intention brief\n\n{brief_text}\n\n"
        f"## Pack (excerpt)\n\n```\n{pack[:1200]}\n```\n\n"
        f"## Law\n\n"
        f"- Cold seat: pack + brief only — no chat sludge\n"
        f"- FILE trail when done; voice will speak result when ready\n"
        f"- Do not reinvent Mag product spine\n",
        encoding="utf-8",
    )
    # Fix 2026-09-29 (gala ball3 live-state): card.relative_to(ROOT) raised
    # ValueError whenever HANDOFF_DIR sits outside the repo (tests point it at
    # tmp_path; the wave5 full-suite run used an external --basetemp), and the
    # raise was swallowed by the caller's except in mag/voice_turn.py, so the
    # handoff silently degraded to a local 'frontier'-route answer
    # (suite-burn.check.txt + live-state repro: assert 'frontier' == 'handoff').
    # Display only: the card bytes and handoff id are unchanged.
    try:
        data["card_path"] = str(card.relative_to(ROOT)).replace("\\", "/")
    except ValueError:  # sandbox/external-basetemp handoff dir outside ROOT
        data["card_path"] = str(card)
    path = _write(data)

    # Also mirror into voice_tasks ledger for existing cheap-agent path
    try:
        from mag.voice_tasks import file_task

        vt = file_task(
            goal=f"[handoff {hid}] {goal[:500]}",
            transcript=transcript or goal,
            session_id=session_id,
            seat_hint=data["seat"],
            tags=["voice", "handoff", "deepseek"],
            enqueue=True,
        )
        data["voice_task_id"] = (vt.get("task") or {}).get("task_id")
        data["voice_task"] = vt.get("card_path")
        _write(data)
    except Exception:
        pass

    if run_async and data["seat"] == "deepseek":
        t = threading.Thread(
            target=_run_deepseek_worker,
            args=(hid,),
            daemon=True,
            name=f"voice-handoff-{hid}",
        )
        t.start()
        data["async"] = True
    else:
        data["async"] = False

    try:
        from mag.training_events import emit

        emit(
            "voice_turn",
            join={"session_id": session_id or "", "handoff_id": hid},
            input_data={"goal": goal[:400], "depth": brief.get("depth")},
            action={"kind": "voice_handoff", "seat": data["seat"], "async": data.get("async")},
            outcome={"ok": True, "card": data.get("card_path")},
            pattern_tags=["voice", "handoff", "deepseek", "non_blocking"],
            tier_max="T2",
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "handoff_id": hid,
        "handoff": data,
        # Same sandbox guard as card_path above (gala ball3 live-state
        # 2026-09-29): this raise fired AFTER card+index were written and was
        # swallowed by mag/voice_turn.py's except, degrading a completed
        # handoff to a local 'frontier'-route answer under external basetemp.
        "path": (str(path.relative_to(ROOT)) if _under_root(path)
                 else str(path)).replace("\\", "/"),
        "card_path": data.get("card_path"),
    }


def _run_deepseek_worker(handoff_id: str) -> None:
    path = HANDOFF_DIR / f"{handoff_id}.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    data["status"] = "running"
    data["started"] = _utc()
    _write(data)

    user = (
        "You are Mag's DeepSeek handoff seat — cold worker, not the voice mic.\n"
        "Implement or answer from the brief + pack only. Be concrete. "
        "If code: list files to touch and the patch plan; if knowledge: short substance.\n\n"
        f"{data.get('brief_text') or data.get('goal')}\n\n"
        f"## Pack excerpt\n{data.get('pack_excerpt') or ''}\n"
    )
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            "You are a cheap high-fidelity coding/reasoning seat for Mag. "
            "No handoff theater. Deliver the job. Under 400 words unless code plan needs more.",
            user,
            tier="T2",
            max_tokens=700,
            temperature=0.3,
        )
        if res.get("ok"):
            text = str(res.get("text") or res.get("content") or "").strip()
            data["result"] = text[:4000]
            data["status"] = "ready"
            data["model"] = res.get("model")
            data["finished"] = _utc()
        else:
            data["status"] = "failed"
            data["error"] = str(res.get("error") or "deepseek failed")[:300]
            data["finished"] = _utc()
    except Exception as exc:
        data["status"] = "failed"
        data["error"] = str(exc)[:300]
        data["finished"] = _utc()

    _write(data)

    # Dig board + scout-style note for next local pull
    try:
        from mag.voice_dig_board import note_scout_ready

        brief = (
            f"HANDOFF {handoff_id} ({data.get('status')})\n"
            f"Goal: {str(data.get('goal') or '')[:200]}\n"
            f"{(data.get('result') or data.get('error') or '')[:900]}"
        )
        note_scout_ready(
            session_id=str(data.get("session_id") or "voice"),
            trigger=f"handoff:{handoff_id}",
            brief=brief,
        )
    except Exception:
        pass


def handoff_spoken_reply(filed: dict[str, Any]) -> str:
    hid = filed.get("handoff_id") or (filed.get("handoff") or {}).get("handoff_id") or "?"
    goal = str((filed.get("handoff") or {}).get("goal") or filed.get("goal") or "")[:80]
    return (
        f"Filed handoff {hid} to DeepSeek in the background — you can keep talking. "
        f"Job: {goal}. I'll use the result when it's ready, or ask for handoff status."
    )


def try_handoff_reply(
    transcript: str,
    *,
    session_id: str = "",
    brief: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """If this turn is a handoff job, FILE and return spoken ack (non-blocking)."""
    brief = brief or {}
    depth = str(brief.get("depth") or "")
    if not wants_handoff(transcript, depth=depth):
        return None
    if wants_blocking_smart(transcript):
        return None

    goal = str(brief.get("goal") or transcript)
    # Strip meta handoff words from goal for cleaner worker brief
    goal_clean = re.sub(
        r"\b(hand\s*off|handoff|file for deepseek|pass to deepseek|queue for)\b",
        "",
        goal,
        flags=re.I,
    ).strip() or goal

    filed = file_handoff(
        goal_clean,
        transcript=transcript,
        session_id=session_id,
        brief=brief,
        seat="deepseek",
        run_async=True,
    )
    if not filed.get("ok"):
        return None
    speak = handoff_spoken_reply(filed)
    return {
        "ok": True,
        "answer": speak,
        "speak_text": speak,
        "seat": "local",
        "route": "handoff",
        "provider": "voice_handoff",
        "used_llm": False,
        "handoff_id": filed.get("handoff_id"),
        "handoff": filed.get("handoff"),
        "card_path": filed.get("card_path"),
        "conversation": True,
        "token_note": "handoff FILE — DeepSeek async; mic stays free",
    }


def inject_ready_result(session_id: str) -> dict[str, Any] | None:
    """If a handoff finished, return a one-shot speak payload and mark spoken."""
    h = ready_handoff_for_session(session_id)
    if not h:
        return None
    hid = h.get("handoff_id")
    result = str(h.get("result") or "").strip()
    if not result:
        return None
    clip = result[:500]
    if len(result) > 500:
        clip = clip.rsplit(" ", 1)[0] + "…"
    speak = f"Handoff {hid} is ready. {clip}"
    mark_spoken(str(hid))
    return {
        "handoff_id": hid,
        "result": result,
        "speak_text": speak,
        "goal": h.get("goal"),
    }


def handle_handoff(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or "list").strip().lower()
    if action in ("list", "status"):
        return list_handoffs(
            limit=int(body.get("limit") or 20),
            status=body.get("status", "open"),
        )
    if action in ("get",):
        return get_handoff(str(body.get("handoff_id") or body.get("id") or ""))
    if action in ("file", "create", "handoff"):
        return file_handoff(
            str(body.get("goal") or body.get("text") or ""),
            transcript=str(body.get("transcript") or body.get("text") or ""),
            session_id=str(body.get("session_id") or ""),
            brief=body.get("brief") if isinstance(body.get("brief"), dict) else None,
            seat=str(body.get("seat") or "deepseek"),
            run_async=body.get("run_async", True) is not False,
        )
    if action in ("ready", "poll"):
        h = ready_handoff_for_session(str(body.get("session_id") or ""))
        return {"ok": True, "ready": h}
    return {"ok": False, "error": f"unknown action: {action}"}
