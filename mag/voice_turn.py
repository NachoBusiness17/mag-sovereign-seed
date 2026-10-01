"""Voice turn — conversational STT ↔ agent (hardware-aware, local first).

Schema: mag_voice_turn.v1 — see docs/ref/MAG_MOBILE_VOICE_SPEC.md

Conversation law:
  - Session history on disk (last N turns) so Mag remembers the thread
  - Local Ollama chat for dialogue (not biographer walls)
  - DeepSeek only when forced or transcript looks heavy
  - Browser owns TTS — no PowerShell SAPI
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import ROOT

SCHEMA = "mag_voice_turn.v1"
TRAIL_PATH = ROOT / "memory" / "runs" / "voice_trail.jsonl"
SESSIONS_DIR = ROOT / "memory" / "working" / "voice_sessions"
MAX_HISTORY = int(os.environ.get("MAG_VOICE_HISTORY_TURNS", "8") or "8")

VOICE_SYSTEM = """You are Voice Mag on this PC.
Answer ONLY the latest operator line. 1-2 short spoken sentences. No markdown.
FORBIDDEN unless the latest line names them: RAM, BIOS, SAM, Smart Access Memory, motherboard, VRAM, desk goal.
Never say "Sure, here's the answer:" or reopen an old topic.
If they ask about this page: Mag Voice = talk, brief, answer, handoff, refine chain, diary seal.
If they greet you: confirm hearing only."""

# Used when seat is actually DeepSeek (escalate or UI deepseek)
DEEPSEEK_VOICE_SYSTEM = """You are Mag's DeepSeek seat for this voice turn — already on the line.
Answer the LATEST line only. No RAM/BIOS unless named now. 2-4 short sentences, no markdown.
No handoff theater. No "Sure, here's the answer:"."""

# Sticky "hardware monologue" tokens that gemma latches onto from dig board / desk
_SLUDGE = re.compile(
    r"\b("
    r"sam|smart access|resizable\s*bar|bios|vram|motherboard|"
    r"ram settings|memory settings|check the sam|sam settings"
    r")\b",
    re.I,
)
# Soft STT lexicon — Whisper/WebSpeech often mangles proper names
_STT_LEXICON: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bb[eé]arnaise\b", re.I), "Bernays"),  # Edward Bernays ≠ sauce
    (re.compile(r"\bburn\s*ays\b", re.I), "Bernays"),
    (re.compile(r"\bbernays\b", re.I), "Bernays"),
]

# Status / recall / short social → local. Everything else can escalate.
_LOCAL_HINT = re.compile(
    r"\b("
    r"what was i doing|what('?s| is) next|what next|how are you|how('?s| is) mag|"
    r"status|healthy|health|office|pulse|brief|hello|hi|hey|thanks|thank you|"
    r"sup|yo|good morning|good night|who are you|what can you do|"
    r"where am i|catch me up|summary|summarize|open loops?|bonds?"
    r")\b",
    re.I,
)
_HEAVY_HINT = re.compile(
    r"\b("
    r"implement|refactor|debug|write code|pull request|pytest|deploy|"
    r"architecture|design the|multi[- ]?file|deepseek|cursor|factory|"
    r"build sprint|investigate|root cause|stack trace"
    r")\b",
    re.I,
)
# Operator explicitly wants a smarter seat — never let local refuse this
_ESCALATE_HINT = re.compile(
    r"\b("
    r"escalate|smarter model|smarter seat|use deepseek|call deepseek|"
    r"deep\s*seek|to deepseek|to deep seek|"
    r"higher model|better model|bigger model|frontier model|"
    r"use a smarter|get a smarter|switch to deepseek|ask deepseek|"
    r"not helping|really not helping|you('re| are) not helping|"
    r"wrong topic|stop talking about ram|not about ram|not about bios"
    r")\b",
    re.I,
)
# Meta about seats / voice UX — answer as harness, not fake diagnostics
_SEAT_META = re.compile(
    r"\b("
    r"switched|switch(ed)? (it|seats?|to local|to deep)|what (do|can) you do|"
    r"are you (local|deep|deepseek|mag)|which (seat|model)|"
    r"see what you do|show me what you do"
    r")\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_session_id(session_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "", (session_id or "").strip())[:64]
    return s or f"voice-{uuid4().hex[:10]}"


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{_safe_session_id(session_id)}.json"


def load_session(session_id: str) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.is_file():
        return {"session_id": _safe_session_id(session_id), "turns": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"session_id": _safe_session_id(session_id), "turns": []}
        data.setdefault("turns", [])
        return data
    except Exception:
        return {"session_id": _safe_session_id(session_id), "turns": []}


def save_session(session_id: str, data: dict[str, Any]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(session_id)
    data = dict(data)
    data["session_id"] = _safe_session_id(session_id)
    data["updated"] = _utc()
    turns = list(data.get("turns") or [])
    if len(turns) > MAX_HISTORY * 2:
        turns = turns[-(MAX_HISTORY * 2) :]
    data["turns"] = turns
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def clear_session(session_id: str) -> dict[str, Any]:
    path = _session_path(session_id)
    if path.is_file():
        try:
            path.unlink()
        except Exception:
            pass
    return {"ok": True, "session_id": _safe_session_id(session_id), "cleared": True}


def _history_block(turns: list[dict[str, Any]], *, max_turns: int = 2) -> str:
    """Very short history — long sticky context made local parrot RAM monologues."""
    if not turns:
        return "(new conversation — no prior turns)"
    lines: list[str] = []
    for t in turns[-max_turns:]:
        role = "You" if t.get("role") == "user" else "Mag"
        text = str(t.get("text") or "").strip().replace("\n", " ")
        if text:
            # Truncate hard so models don't re-chew old monologues
            lines.append(f"{role}: {text[:120]}")
    return "\n".join(lines) if lines else "(empty)"


def soft_stt_fix(text: str) -> str:
    """Light lexicon only — not voice training. Fixes known name mangling."""
    t = (text or "").strip()
    if not t:
        return t
    for pat, repl in _STT_LEXICON:
        t = pat.sub(repl, t)
    return t


def _has_sludge(text: str) -> bool:
    return bool(_SLUDGE.search(text or ""))


def _history_is_sludge(turns: list[dict[str, Any]]) -> bool:
    """True if recent Mag replies are stuck on hardware monologue."""
    asst = [str(t.get("text") or "") for t in (turns or []) if t.get("role") == "assistant"][-4:]
    if not asst:
        return False
    hits = sum(1 for a in asst if _has_sludge(a))
    return hits >= max(1, len(asst) // 2)


def _wants_topic_reset(transcript: str, history: list[dict[str, Any]]) -> bool:
    """Latest line is clean of hardware; history is sludge → wipe for this turn."""
    t = transcript or ""
    if _has_sludge(t):
        return False
    # Explicit topic change / social / complaints / page meta
    if re.search(
        r"\b("
        r"hear me|hello|hi\b|hey\b|never ?mind|different topic|new topic|"
        r"talk about|about life|bernays|propaganda|forget (sam|ram|bios)|"
        r"stop (talking about|with)|not (about|that)|wrong topic|"
        r"this still sucks|still sucks|this page|what is this|can you see|"
        r"not helping|stuck on"
        r")\b",
        t,
        re.I,
    ):
        return True
    return _history_is_sludge(history)


def _wants_escalate(transcript: str) -> bool:
    return bool(_ESCALATE_HINT.search(transcript or ""))


def _voice_seat(body: dict[str, Any], transcript: str = "") -> str:
    t = (transcript or "").strip()
    # "use a smarter model" always leaves local — never refuse in-model
    if _wants_escalate(t):
        return "deepseek"
    raw = str(body.get("seat") or os.environ.get("MAG_VOICE_SEAT") or "auto").strip().lower()
    if raw in ("local", "ollama", "janitor", "local_only"):
        return "local"
    if raw in ("deepseek", "remote", "frontier"):
        return "deepseek"
    if len(t) <= 12 and not _HEAVY_HINT.search(t):
        return "local"
    if _HEAVY_HINT.search(t):
        return "deepseek"
    if _LOCAL_HINT.search(t) or len(t) < 100:
        return "local"
    prefer = os.environ.get("MAG_VOICE_AUTO_PREFER", "local").strip().lower()
    return "deepseek" if prefer in ("deepseek", "remote", "frontier") else "local"


def _voice_context() -> str:
    try:
        from mag.display import build_display_payload

        d = build_display_payload()
        parts: list[str] = []
        if d.get("headline"):
            parts.append(f"Pulse: {d['headline']}")
        desk = d.get("desk") or {}
        if desk.get("goal"):
            parts.append(f"Desk goal: {desk['goal']}")
        return "\n".join(parts)
    except Exception:
        return ""


def _append_trail(row: dict[str, Any]) -> None:
    TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRAIL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _tts_clip(answer: str, *, max_chars: int = 480) -> str:
    t = re.sub(r"[#*_`]+", "", answer or "")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= max_chars:
        return t
    cut = t[: max_chars - 1]
    for sep in (". ", "! ", "? "):
        i = cut.rfind(sep)
        if i >= 80:
            return cut[: i + 1].strip()
    return cut.rstrip() + "…"


def _build_user_prompt(
    transcript: str,
    history: list[dict[str, Any]],
    *,
    session_id: str = "",
    include_pulse: bool = True,
    include_shadow: bool = True,
    deepseek_seat: bool = False,
    topic_reset: bool = False,
    brief: dict[str, Any] | None = None,
    lane: str = "voice",
) -> str:
    from mag.voice_lanes import lane_spec

    sp = lane_spec(lane)
    allow_hist = bool(sp.get("allow_history")) and not topic_reset
    allow_dig = bool(sp.get("allow_dig_board")) and include_shadow and not topic_reset
    allow_pulse = bool(sp.get("allow_desk_pulse")) and include_pulse and not topic_reset
    max_h = int(sp.get("max_history_turns") or 0)

    # Prefer compiled intention brief (fidelity routing)
    if brief:
        try:
            from mag.intention_brief import render_brief_for_model

            parts = [render_brief_for_model(brief, spoken=True)]
        except Exception:
            parts = [f"## Operator just said\n{transcript}"]
        parts.insert(0, f"## Memory lane: {sp.get('label')} ({sp.get('id')})")
        if allow_hist and history and max_h > 0:
            hist = _history_block(history, max_turns=max_h)
            if hist and hist != "(new conversation — no prior turns)":
                # Drop history lines that are sludge when latest is clean
                if not _has_sludge(transcript):
                    lines = [
                        ln
                        for ln in hist.splitlines()
                        if not _has_sludge(ln)
                    ]
                    hist = "\n".join(lines) if lines else ""
                if hist:
                    parts.append(f"## Recent on-topic turns (do not override goal)\n{hist}")
        # Dig board only on dig lane + hardware topic
        if allow_dig and session_id and _has_sludge(transcript):
            try:
                from mag.voice_dig_board import board_context_for_local

                board = board_context_for_local(max_chars=900, transcript=transcript)
                if board:
                    parts.append(board)
            except Exception:
                pass
        parts.append(
            "FORBIDDEN in this reply unless latest line names them: RAM, BIOS, SAM, motherboard."
        )
        # I1 steal (VS Code voice): agent knows it's a spoken turn
        parts.append(
            "SPOKEN TURN (voice): reply briefly and read-aloud friendly — plain, no markdown, no lists."
        )
        if deepseek_seat:
            parts.append("You are the DeepSeek seat. Answer the intention goal with substance.")
        return "\n\n".join(parts)

    hist = (
        "(new conversation — no prior turns)"
        if not allow_hist
        else _history_block(history, max_turns=max(1, max_h))
    )
    parts = [f"## Memory lane: {sp.get('label')}"]
    if allow_pulse and _has_sludge(transcript):
        ctx = _voice_context()
        if ctx:
            parts.append(f"## Office pulse\n{ctx}")
    if hist and hist != "(new conversation — no prior turns)" and allow_hist:
        parts.append(f"## Recent\n{hist}")
    parts.append(f"## Operator just said (ANSWER THIS — only this)\n{transcript}")
    parts.append("Do not mention RAM/BIOS/SAM unless they did in the latest line.")
    # I1 steal (VS Code voice): agent knows it's a spoken turn
    parts.append("SPOKEN TURN (voice): reply briefly and read-aloud friendly — plain, no markdown, no lists.")
    return "\n\n".join(parts)


def _local_voice_model() -> str:
    """Fast small model for voice — gemma4:8B cold-loads and blows client timeouts."""
    return (os.environ.get("MAG_VOICE_LOCAL_MODEL") or "gemma:2b").strip() or "gemma:2b"


def _answer_chat(
    transcript: str,
    *,
    session_id: str,
    history: list[dict[str, Any]],
    provider: str,
    route: str,
    tier: str,
    model: str | None = None,
    deepseek_seat: bool = False,
    include_pulse: bool = True,
    topic_reset: bool = False,
    brief: dict[str, Any] | None = None,
    lane: str = "voice",
) -> dict[str, Any]:
    from mag.voice_lanes import lane_spec

    sp = lane_spec(lane)
    user = _build_user_prompt(
        transcript,
        history,
        session_id=session_id,
        include_pulse=include_pulse and not deepseek_seat,
        include_shadow=not deepseek_seat,
        deepseek_seat=deepseek_seat,
        topic_reset=topic_reset,
        brief=brief,
        lane=lane,
    )
    max_tok = int(os.environ.get("MAG_VOICE_MAX_TOKENS", "120") or "120")
    if deepseek_seat:
        max_tok = max(max_tok, 200)
    system = DEEPSEEK_VOICE_SYSTEM if deepseek_seat else str(sp.get("system") or VOICE_SYSTEM)
    try:
        from mag.desk_timing import Timer, extract_provider_tokens, make_timing
        from models.providers import chat_provider

        timer = Timer()
        kwargs: dict[str, Any] = {
            "tier": tier,
            "max_tokens": max(48, min(max_tok, 220 if deepseek_seat else 160)),
            "temperature": 0.35 if deepseek_seat else 0.4,
        }
        if model:
            kwargs["model"] = model
        res = chat_provider(
            provider,
            system,
            user,
            **kwargs,
        )
        if not res.get("ok"):
            return {
                "ok": False,
                "error": str(res.get("error") or f"{provider} failed"),
                "seat": "local" if provider == "ollama" else provider,
                "route": route,
            }
        answer = str(res.get("text") or res.get("content") or "").strip()
        model = res.get("model")
        tin, tout = extract_provider_tokens(res.get("usage"))
        timing = make_timing(
            speaker="voice",
            elapsed_ms=timer.elapsed_ms(),
            tokens_in=tin,
            tokens_out=tout,
            model=str(model) if model else None,
            provider=provider,
        )
        seat = "local" if provider in ("ollama", "local") else provider
        return {
            "ok": bool(answer),
            "answer": answer,
            "seat": seat,
            "route": route,
            "provider": provider,
            "model": model,
            "used_llm": True,
            "timing": timing,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:200],
            "seat": "local" if provider == "ollama" else provider,
            "route": route,
        }


def _answer_deepseek(
    transcript: str,
    *,
    session_id: str,
    history: list[dict[str, Any]],
    topic_reset: bool = False,
    brief: dict[str, Any] | None = None,
    lane: str = "voice",
) -> dict[str, Any]:
    return _answer_chat(
        transcript,
        session_id=session_id,
        history=history,
        provider="deepseek",
        route="frontier",
        tier="T2",
        deepseek_seat=True,
        include_pulse=False,
        topic_reset=topic_reset,
        brief=brief,
        lane=lane,
    )


def _answer_local(
    transcript: str,
    *,
    session_id: str,
    history: list[dict[str, Any]],
    topic_reset: bool = False,
    brief: dict[str, Any] | None = None,
    lane: str = "voice",
) -> dict[str, Any]:
    from mag.voice_lanes import lane_spec
    import os as _os

    sp = lane_spec(lane)
    env_key = str(sp.get("model_env") or "MAG_VOICE_LOCAL_MODEL")
    model = (_os.environ.get(env_key) or sp.get("default_model") or _local_voice_model()).strip()
    route = f"lane:{sp.get('id')}"
    if brief and brief.get("depth"):
        route = f"brief:{brief.get('depth')}:{sp.get('id')}"
    res = _answer_chat(
        transcript,
        session_id=session_id,
        history=history,
        provider="ollama",
        route=route,
        tier="T1",
        model=model,
        topic_reset=topic_reset,
        brief=brief,
        lane=lane,
    )
    if res.get("ok") and res.get("answer"):
        res["model"] = res.get("model") or model
        if topic_reset:
            res["topic_reset"] = True
        return res
    # Second try: qwen-desk if primary fails (still small)
    if model != "qwen-desk:latest":
        res2 = _answer_chat(
            transcript,
            session_id=session_id,
            history=history,
            provider="ollama",
            route=route,
            tier="T1",
            model="qwen-desk:latest",
            topic_reset=topic_reset,
            brief=brief,
            lane=lane,
        )
        if res2.get("ok") and res2.get("answer"):
            res2["fallback"] = "qwen-desk"
            if topic_reset:
                res2["topic_reset"] = True
            return res2
    # Last resort: deterministic short line so the loop doesn't die silent
    tl = (transcript or "").lower()
    if any(w in tl for w in ("hear me", "can you hear", "hello", "hi ", "hey")):
        answer = "Yes — I can hear you. Local model is ready; go ahead."
    elif "bernays" in tl or "life" in tl:
        answer = "Got it — life and Bernays. Where do you want to start?"
    else:
        answer = "I heard you, but the local model was slow. Try again in a second."
    return {
        "ok": True,
        "answer": answer,
        "seat": "local",
        "route": "instant_fallback",
        "provider": "local",
        "used_llm": False,
        "fallback": "instant",
        "topic_reset": topic_reset,
        "error": res.get("error"),
    }


def handle_voice_turn(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    raw_text = str(body.get("text") or body.get("transcript") or "").strip()
    text = soft_stt_fix(raw_text)
    # I2 steal (VS Code voice): per-surface dictation cleanup on the spoken transcript
    try:
        from mag.voice_dictate import cleanup as _dictate_cleanup

        text = _dictate_cleanup(text, "chat")
    except Exception:
        pass
    session_id = _safe_session_id(
        str(body.get("session_id") or "").strip() or f"voice-{uuid4().hex[:10]}"
    )

    if body.get("clear_session") or body.get("reset"):
        out = {"schema": SCHEMA, **clear_session(session_id)}
        if body.get("clear_canvas") or body.get("clear_dig"):
            try:
                from mag.voice_dig_board import clear_board

                out["dig_cleared"] = clear_board().get("ok")
            except Exception:
                pass
        return out

    if not text:
        return {"ok": False, "schema": SCHEMA, "error": "empty transcript — pass text"}

    if str(body.get("channel") or "") == "table":
        from mag.table_turn import handle as _table_handle
        return _table_handle(body)

    # --- Memory lane (Voice Mag ≠ Code Mag ≠ desk RAM sludge) ---
    from mag.voice_lanes import (
        infer_lane,
        instant_harness_reply,
        lane_public,
        lane_spec,
        session_id_for_lane,
    )

    lane = infer_lane(text, explicit=str(body.get("lane") or body.get("memory_lane") or ""))
    base_session = session_id
    session_id = _safe_session_id(session_id_for_lane(base_session, lane))

    # Instant harness (no LLM) — kills "can you hear me" → BIOS monologue
    instant = instant_harness_reply(text)
    if instant and instant.get("ok"):
        speak_text = _tts_clip(str(instant.get("answer") or ""))
        if instant.get("force_reset"):
            try:
                clear_session(session_id)
                from mag.voice_dig_board import clear_board_if_sludge

                clear_board_if_sludge()
            except Exception:
                pass
        try:
            sess = load_session(session_id)
            hist = list(sess.get("turns") or [])
            hist.append({"role": "user", "text": text[:800], "ts": _utc()})
            hist.append(
                {
                    "role": "assistant",
                    "text": speak_text[:800],
                    "ts": _utc(),
                    "seat": "harness",
                    "route": instant.get("route"),
                    "lane": lane,
                }
            )
            sess["turns"] = hist
            sess["lane"] = lane
            save_session(session_id, sess)
        except Exception:
            pass
        # Complaint + premise escalate option
        if re.search(r"\b(still sucks|not helping|create a premise|refine chain)\b", text, re.I):
            try:
                from mag.refine_chain import start_chain

                premise = (
                    "Premise: Mag Voice must answer the operator's latest line only, "
                    "never reopen desk BIOS/RAM goals unless named; page is Mag Voice "
                    "(brief, handoff, refine, diary). Design a multi-seat experiment "
                    "to keep lanes (voice/dig/code/harness) coherent."
                )
                start_chain(premise, session_id=session_id, auto_run=True)
            except Exception:
                pass
        return {
            "ok": True,
            "schema": SCHEMA,
            "session_id": session_id,
            "base_session": base_session,
            "transcript": text,
            "answer": instant.get("answer"),
            "speak_text": speak_text,
            "seat": "local",
            "route": instant.get("route") or "lane_harness_instant",
            "lane": lane_public(lane),
            "speak": True,
            "server_tts": False,
            "provider": "harness",
            "used_llm": False,
            "topic_reset": True,
            "conversation": True,
            "token_note": "lane harness instant — no dig/desk sludge",
        }

    # --- Living campaign (engine-first: save · character · actions · narrate) ---
    try:
        from mag.game_campaign import (
            apply_action,
            begin_play,
            latest_any,
            latest_for_session,
            parse_character,
            parse_player_speech,
            set_character,
        )
        from mag.game_narrate import narrate_scene
        from mag.voice_skills import is_in_game_action, is_play_intent, match_voice_skills

        skills = match_voice_skills(text)
        # Campaign binds to base session (table UI), not lane-prefixed dig id
        game_sid = base_session
        # DM post-game seal
        if re.search(r"\b(seal session|end session|session seal|post[- ]game)\b", text, re.I):
            from mag.game_campaign import seal_session

            sealed = seal_session(session_id=game_sid, tldr=text)
            speak = _tts_clip(str(sealed.get("speak") or sealed.get("error") or "Seal failed."))
            return {
                "ok": bool(sealed.get("ok")),
                "schema": SCHEMA,
                "session_id": session_id,
                "answer": speak,
                "speak_text": speak,
                "seat": "local",
                "route": "game_seal",
                "provider": "game_engine",
                "speak": True,
                "server_tts": False,
                "used_llm": False,
                "conversation": True,
                "seal": sealed,
                "token_note": "DM session seal · dogfood data",
            }
        camp = latest_for_session(game_sid)
        if not camp:
            camp = latest_for_session(session_id)
        if not camp and str(body.get("channel") or "") == "table":
            camp = latest_any()
        if camp:
                # migrate sticky campaign onto base so ASCII map can see it
                try:
                    camp["voice_session_id"] = game_sid
                    from mag.game_campaign import save_campaign

                    save_campaign(camp)
                except Exception:
                    pass

        # Tavern brawl can bootstrap campaign + Tavern Brawler sheet
        try:
            from mag.game_brawl import handle_brawl_voice, wants_brawl_start

            if wants_brawl_start(text):
                brawl = handle_brawl_voice(
                    text,
                    session_id=game_sid,
                    channel=str(body.get("channel") or "table"),
                    campaign=camp,
                )
                if brawl and brawl.get("ok"):
                    # TTS = DM narrator only; table bubble = full passage + ledger
                    speak = _tts_clip(
                        str(brawl.get("speak") or brawl.get("speak_text") or brawl.get("narrator") or "")
                    )
                    answer = str(
                        brawl.get("answer")
                        or brawl.get("narrate")
                        or brawl.get("passage")
                        or speak
                    )
                    return {
                        "ok": True,
                        "schema": SCHEMA,
                        "session_id": session_id,
                        "transcript": text,
                        "answer": answer,
                        "speak_text": speak,
                        "seat": "multi",
                        "route": brawl.get("route") or "tavern_brawl_open",
                        "lane": lane_public("dig"),
                        "campaign_id": brawl.get("campaign_id"),
                        "legal": brawl.get("legal"),
                        "scene_context": brawl.get("scene_context"),
                        "speak": True,
                        "server_tts": False,
                        "provider": "tavern_brawl",
                        "used_llm": bool(brawl.get("ds_called")),
                        "conversation": True,
                        "fast_path": brawl.get("fast_path"),
                        "ds_called": brawl.get("ds_called"),
                        "brawl": {
                            "brawl_id": brawl.get("brawl_id"),
                            "metrics": brawl.get("metrics"),
                            "color": brawl.get("color"),
                            "status": brawl.get("status"),
                            "roster": brawl.get("roster"),
                            "inspiration": brawl.get("inspiration"),
                        },
                        "token_note": "tavern brawl · DM narrator TTS · passage card table",
                    }
        except Exception:
            pass

        if camp and camp.get("status") == "awaiting_character":
            player = parse_character(text)
            if player:
                out_c = set_character(str(camp["campaign_id"]), player)
                speak = _tts_clip(str(out_c.get("speak") or ""))
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "transcript": text,
                    "answer": speak,
                    "speak_text": speak,
                    "seat": "local",
                    "route": "game_character",
                    "lane": lane_public("dig"),
                    "campaign_id": camp.get("campaign_id"),
                    "legal": out_c.get("legal"),
                    "scene_context": out_c.get("scene_context"),
                    "speak": True,
                    "server_tts": False,
                    "provider": "game_engine",
                    "used_llm": True,
                    "conversation": True,
                    "token_note": "character · tavern passage card",
                }
            speak = _tts_clip(
                "Still need a character. Say I'm Name a greedy fighter — or random classic."
            )
            return {
                "ok": True,
                "schema": SCHEMA,
                "session_id": session_id,
                "answer": speak,
                "speak_text": speak,
                "seat": "local",
                "route": "game_need_character",
                "campaign_id": camp.get("campaign_id"),
                "speak": True,
                "server_tts": False,
                "provider": "game_engine",
                "used_llm": False,
                "conversation": True,
            }

        # Sticky in-game: any active campaign keeps turns in engine (no dig sludge)
        if camp and camp.get("status") == "active":
            channel = str(body.get("channel") or "table")
            # Multi-combatant tavern brawl (watch → YOUR TURN → absurd) before single-foe cycle
            try:
                from mag.game_brawl import handle_brawl_voice, wants_brawl_start

                if wants_brawl_start(text) or (camp.get("storyteller") or {}).get("brawl_id"):
                    brawl = handle_brawl_voice(
                        text,
                        session_id=game_sid,
                        channel=channel,
                        campaign=camp,
                    )
                    if brawl and brawl.get("ok"):
                        speak = _tts_clip(
                            str(
                                brawl.get("speak")
                                or brawl.get("speak_text")
                                or brawl.get("narrator")
                                or ""
                            )
                        )
                        answer = str(
                            brawl.get("answer")
                            or brawl.get("narrate")
                            or brawl.get("passage")
                            or speak
                        )
                        return {
                            "ok": True,
                            "schema": SCHEMA,
                            "session_id": session_id,
                            "transcript": text,
                            "answer": answer,
                            "speak_text": speak,
                            "seat": "multi",
                            "route": brawl.get("route") or "tavern_brawl",
                            "lane": lane_public("dig"),
                            "campaign_id": brawl.get("campaign_id") or camp.get("campaign_id"),
                            "legal": brawl.get("legal"),
                            "scene_context": brawl.get("scene_context"),
                            "speak": True,
                            "server_tts": False,
                            "provider": "tavern_brawl",
                            "used_llm": bool(brawl.get("ds_called")),
                            "conversation": True,
                            "fast_path": brawl.get("fast_path"),
                            "ds_called": brawl.get("ds_called"),
                            "signals": brawl.get("signals"),
                            "brawl": {
                                "brawl_id": brawl.get("brawl_id"),
                                "metrics": brawl.get("metrics"),
                                "color": brawl.get("color"),
                                "status": brawl.get("status"),
                                "roster": brawl.get("roster"),
                                "absurd": brawl.get("absurd"),
                                "inspiration": brawl.get("inspiration"),
                            },
                            "token_note": "tavern brawl · DM narrator TTS · passage card table",
                        }
            except Exception:
                pass
            # Automatic battle cycles: engine dice + DS color; track text/speech/meta/OOC
            try:
                from mag.game_battle_cycle import handle_battle_voice

                battle = handle_battle_voice(
                    text,
                    session_id=game_sid,
                    channel=channel,
                    campaign=camp,
                )
                if battle and battle.get("ok"):
                    speak = _tts_clip(str(battle.get("speak") or battle.get("narrator") or battle.get("narrate") or ""))
                    return {
                        "ok": True,
                        "schema": SCHEMA,
                        "session_id": session_id,
                        "transcript": text,
                        "answer": speak,
                        "speak_text": speak,
                        "seat": "multi",
                        "route": battle.get("route") or "battle_cycle",
                        "lane": lane_public("dig"),
                        "campaign_id": battle.get("campaign_id") or camp.get("campaign_id"),
                        "legal": battle.get("legal"),
                        "scene_context": battle.get("scene_context"),
                        "speak": True,
                        "server_tts": False,
                        "provider": "battle_cycle",
                        "used_llm": bool(battle.get("ds_called")),
                        "conversation": True,
                        "fast_path": battle.get("fast_path"),
                        "ds_called": battle.get("ds_called"),
                        "signals": battle.get("signals"),
                        "battle": {
                            "cycle_id": battle.get("cycle_id"),
                            "metrics": battle.get("metrics"),
                            "color": battle.get("color"),
                        },
                        "token_note": "battle cycle · auto DS · no paste",
                    }
            except Exception:
                pass
            # Salon: ask guest (frontier) → clarify/confirm → then engine output
            try:
                from mag.game_salon import handle_salon_voice

                salon = handle_salon_voice(
                    text,
                    session_id=game_sid,
                    campaign_id=str(camp.get("campaign_id") or ""),
                )
                if salon and salon.get("ok"):
                    speak = _tts_clip(str(salon.get("speak") or salon.get("narrate") or ""))
                    return {
                        "ok": True,
                        "schema": SCHEMA,
                        "session_id": session_id,
                        "transcript": text,
                        "answer": speak,
                        "speak_text": speak,
                        "seat": "local" if salon.get("route") != "salon_advice" else "multi",
                        "route": salon.get("route") or "salon",
                        "lane": lane_public("dig"),
                        "campaign_id": camp.get("campaign_id"),
                        "legal": salon.get("legal"),
                        "speak": True,
                        "server_tts": False,
                        "provider": "salon_loop",
                        "used_llm": True,
                        "conversation": True,
                        "token_note": "salon: local parse · frontier advise · confirm · output",
                        "salon": {
                            "advice_id": salon.get("advice_id"),
                            "pending": salon.get("pending"),
                            "confirmed_option": salon.get("confirmed_option"),
                        },
                        "advice": salon.get("advice"),
                        "legal": salon.get("legal"),
                        "scene_context": salon.get("scene_context"),
                    }
            except Exception:
                pass
            # end game only on explicit quit
            if re.search(r"\b(quit game|end campaign|stop playing|leave the game)\b", text, re.I):
                try:
                    camp["status"] = "paused"
                    from mag.game_campaign import save_campaign

                    save_campaign(camp)
                except Exception:
                    pass
                speak = _tts_clip("Campaign paused. Say classic one to resume or start fresh.")
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "answer": speak,
                    "speak_text": speak,
                    "seat": "local",
                    "route": "game_pause",
                    "provider": "game_engine",
                    "speak": True,
                    "server_tts": False,
                    "used_llm": False,
                    "conversation": True,
                }
            act = parse_player_speech(text)
            # Sticky freestyle in-game: talk/ask stays in world (look+IC), not Stickmin bathroom
            if not act:
                act = {"type": "talk", "raw": (text or "").strip()[:240]}
            if act:
                out_a = apply_action(str(camp["campaign_id"]), act)
                if out_a.get("ok"):
                    full = act.get("type") in ("look", "rumor", "drink") or (
                        act.get("type") == "move"
                    )
                    # talk/mechanical: engine events are Sancho — do not LLM-overwrite
                    if act.get("type") in ("talk", "help", "inventory", "status", "freeze", "take"):
                        speak = _tts_clip(
                            str(out_a.get("narrate") or " ".join(out_a.get("events") or []))
                        )
                        used_llm = False
                    else:
                        try:
                            from mag.game_campaign import load_campaign
                            from mag.game_passage import narrate_passage, room_meta_from_camp

                            camp2 = load_campaign(str(camp["campaign_id"])) or camp
                            pas = narrate_passage(
                                out_a.get("scene_context"),
                                events=out_a.get("events"),
                                last_action=text,
                                room_meta=room_meta_from_camp(camp2),
                                full=bool(full),
                                use_llm=False,
                            )
                            speak = _tts_clip(
                                str(pas.get("text") or out_a.get("narrate") or "")
                            )
                            used_llm = pas.get("source") == "local_llm"
                        except Exception:
                            narr = narrate_scene(
                                out_a.get("scene_context"),
                                events=out_a.get("events"),
                                use_llm=False,
                            )
                            speak = _tts_clip(
                                str(narr.get("text") or out_a.get("narrate") or "")
                            )
                            used_llm = narr.get("source") == "local_llm"
                    return {
                        "ok": True,
                        "schema": SCHEMA,
                        "session_id": session_id,
                        "transcript": text,
                        "answer": speak,
                        "speak_text": speak,
                        "seat": "local",
                        "route": "game_turn",
                        "lane": lane_public("dig"),
                        "campaign_id": camp.get("campaign_id"),
                        "legal": out_a.get("legal"),
                        "scene_context": out_a.get("scene_context"),
                        "speak": True,
                        "server_tts": False,
                        "provider": "game_engine",
                        "used_llm": used_llm,
                        "conversation": True,
                        "token_note": "engine · passage card",
                    }
                legal = out_a.get("legal") or []
                tips = ", ".join(
                    a.get("type", "")
                    + (f" {a['direction']}" if a.get("direction") else "")
                    for a in legal[:8]
                )
                speak = _tts_clip(f"{out_a.get('error') or 'No.'} Try: {tips}")
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "answer": speak,
                    "speak_text": speak,
                    "seat": "local",
                    "route": "game_illegal",
                    "campaign_id": camp.get("campaign_id"),
                    "legal": legal,
                    "speak": True,
                    "server_tts": False,
                    "provider": "game_engine",
                    "used_llm": False,
                    "conversation": True,
                }
            # Curveball: freestyle → Stickmin fail / KoL divert / graph branch (never blank balk)
            from mag.game_curveball import resolve_curveball
            from mag.game_narrate import narrate_scene

            out_cb = resolve_curveball(str(camp["campaign_id"]), text)
            if out_cb.get("ok"):
                # Stickmin/KoL lines are already written — LLM freestyle ruins them
                narr = narrate_scene(
                    out_cb.get("scene_context"),
                    events=out_cb.get("events"),
                    use_llm=False,
                )
                speak = _tts_clip(str(narr.get("text") or out_cb.get("narrate") or ""))
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "transcript": text,
                    "answer": speak,
                    "speak_text": speak,
                    "seat": "local",
                    "route": "game_curveball",
                    "lane": lane_public("dig"),
                    "campaign_id": camp.get("campaign_id"),
                    "legal": out_cb.get("legal"),
                    "scene_context": out_cb.get("scene_context"),
                    "curveball": out_cb.get("curveball"),
                    "speak": True,
                    "server_tts": False,
                    "provider": "game_engine",
                    "used_llm": narr.get("source") == "local_llm",
                    "conversation": True,
                    "token_note": "curveball · stickmin/kol · engine FILE",
                }
            from mag.game_campaign import list_legal_actions, scene_context

            legal = list_legal_actions(camp)
            tips = ", ".join(
                a.get("type", "")
                + (f" {a['direction']}" if a.get("direction") else "")
                for a in legal[:8]
            )
            room = (scene_context(camp) or {}).get("room_name") or "here"
            speak = _tts_clip(f"Still in {room}. Try: {tips}. Or quit game.")
            return {
                "ok": True,
                "schema": SCHEMA,
                "session_id": session_id,
                "answer": speak,
                "speak_text": speak,
                "seat": "local",
                "route": "game_stuck",
                "campaign_id": camp.get("campaign_id"),
                "legal": legal,
                "speak": True,
                "server_tts": False,
                "provider": "game_engine",
                "used_llm": False,
                "conversation": True,
            }

        if is_play_intent(text) or any(
            h.get("id") == "tabletop-dnd" for h in (skills.get("hits") or [])
        ):
            force_new = bool(re.search(r"\b(new game|start over|fresh|new campaign)\b", text, re.I))
            mod = "classic"
            if re.search(r"\b(water one|water computer|hydraulic|moniac|lukyanov|tanks)\b", text, re.I):
                mod = "water_computer"
            out_p = begin_play(
                module_id=mod,
                voice_session_id=game_sid,
                force_new=force_new,
            )
            if out_p.get("ok"):
                speak = _tts_clip(str(out_p.get("speak") or ""))
                if out_p.get("resumed") and out_p.get("scene_context"):
                    narr = narrate_scene(out_p["scene_context"], use_llm=True)
                    if narr.get("text"):
                        speak = _tts_clip(str(narr["text"]))
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "transcript": text,
                    "answer": speak,
                    "speak_text": speak,
                    "seat": "local",
                    "route": "game_resume" if out_p.get("resumed") else "game_start",
                    "lane": lane_public("dig"),
                    "campaign_id": (out_p.get("campaign") or {}).get("campaign_id")
                    or out_p.get("campaign_id"),
                    "need_character": out_p.get("need_character"),
                    "legal": out_p.get("legal"),
                    "scene_context": out_p.get("scene_context"),
                    "skills": skills,
                    "speak": True,
                    "server_tts": False,
                    "provider": "game_engine",
                    "used_llm": bool(out_p.get("resumed")),
                    "conversation": True,
                    "token_note": "save check · character or resume · engine",
                }
    except Exception as _game_exc:
        # surface once for debug — still fall through if game path hard-fails
        try:
            from mag.training_events import emit

            emit(
                "game_turn",
                join={"session_id": session_id},
                outcome={"error": str(_game_exc)[:200]},
                pattern_tags=["game", "voice_game_crash"],
                tier_max="T1",
                exportable=False,
            )
        except Exception:
            pass

    # Product need → REST task for cheap agents + honest answer (no "change app settings")
    try:
        from mag.voice_tasks import product_need_reply

        product = product_need_reply(text, session_id=session_id)
        if product and product.get("ok"):
            speak_text = _tts_clip(str(product.get("speak_text") or product.get("answer") or ""))
            # still file session turn
            try:
                sess = load_session(session_id)
                hist = list(sess.get("turns") or [])
                hist.append({"role": "user", "text": text[:800], "ts": _utc()})
                hist.append(
                    {
                        "role": "assistant",
                        "text": speak_text[:800],
                        "ts": _utc(),
                        "seat": "mag",
                        "route": "product_task",
                    }
                )
                sess["turns"] = hist
                save_session(session_id, sess)
            except Exception:
                pass
            return {
                "ok": True,
                "schema": SCHEMA,
                "session_id": session_id,
                "transcript": text,
                "answer": product.get("answer"),
                "speak_text": speak_text,
                "seat": "mag",
                "route": "product_task",
                "speak": True,
                "server_tts": False,
                "provider": "voice_tasks",
                "used_llm": False,
                "task": product.get("task"),
                "card_path": product.get("card_path"),
                "conversation": True,
                "token_note": "product need → REST task for cheap agent",
            }
    except Exception:
        pass

    sess = load_session(session_id)
    history = list(sess.get("turns") or [])
    fidelity = bool(body.get("fidelity") or body.get("fidelity_mode"))
    seat_raw = str(body.get("seat") or "").strip().lower()
    force_handoff = seat_raw in ("handoff", "file", "background") or bool(body.get("handoff"))

    # --- Intention compiler (cheap) before any answer seat ---
    brief: dict[str, Any] = {}
    try:
        from mag.intention_brief import brief_public, compile_intention

        brief = compile_intention(
            text,
            session_id=session_id,
            channel=str(body.get("channel") or "voice"),
            history=history,
            fidelity=fidelity,
            seat_force=seat_raw if seat_raw in ("deepseek", "remote", "frontier") else "",
        )
        text = str(brief.get("stt_fixed") or text)
        if force_handoff:
            brief["handoff"] = True
            brief["seat_recommend"] = "handoff"
            brief["mode"] = "handoff"
            brief["why"] = (str(brief.get("why") or "") + "; force_handoff").strip("; ")
    except Exception as exc:
        brief = {
            "ok": False,
            "schema": "intention_brief.v1",
            "goal": text[:220],
            "depth": "scut",
            "seat_recommend": "local",
            "why": f"compile_failed:{exc!s}"[:80],
            "topic_reset": False,
            "mode": "A",
            "handoff": force_handoff,
        }

    # Refine chain verbs (Project Verkle multi-seat pattern)
    try:
        from mag.refine_chain import try_refine_voice

        rc = try_refine_voice(text, session_id=session_id, brief=brief)
        if rc and rc.get("ok"):
            speak_text = _tts_clip(str(rc.get("speak_text") or rc.get("answer") or ""))
            try:
                history.append({"role": "user", "text": text[:800], "ts": _utc()})
                history.append(
                    {
                        "role": "assistant",
                        "text": speak_text[:800],
                        "ts": _utc(),
                        "seat": "local",
                        "route": rc.get("route") or "refine_chain",
                    }
                )
                sess["turns"] = history
                save_session(session_id, sess)
            except Exception:
                pass
            return {
                "ok": True,
                "schema": SCHEMA,
                "session_id": session_id,
                "transcript": text,
                "answer": rc.get("answer"),
                "speak_text": speak_text,
                "seat": "local",
                "route": rc.get("route") or "refine_chain",
                "speak": True,
                "server_tts": False,
                "provider": "refine_chain",
                "used_llm": bool(rc.get("used_llm")),
                "chain_id": rc.get("chain_id"),
                "brief": {
                    "goal": brief.get("goal"),
                    "depth": brief.get("depth"),
                    "why": brief.get("why"),
                    "mode": "refine",
                },
                "conversation": True,
                "token_note": "refine chain — multi-seat FILE, mic free",
            }
    except Exception:
        pass

    # Pending handoff result
    try:
        from mag.voice_handoff import inject_ready_result

        ready = inject_ready_result(session_id)
        if ready and ready.get("speak_text"):
            if re.search(r"\b(handoff status|task status|is it done|ready yet)\b", text, re.I):
                speak_text = _tts_clip(str(ready["speak_text"]))
                try:
                    history.append({"role": "user", "text": text[:800], "ts": _utc()})
                    history.append(
                        {
                            "role": "assistant",
                            "text": speak_text[:800],
                            "ts": _utc(),
                            "seat": "deepseek",
                            "route": "handoff_ready",
                        }
                    )
                    sess["turns"] = history
                    save_session(session_id, sess)
                except Exception:
                    pass
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "transcript": text,
                    "answer": ready.get("result") or speak_text,
                    "speak_text": speak_text,
                    "seat": "deepseek",
                    "route": "handoff_ready",
                    "speak": True,
                    "server_tts": False,
                    "provider": "voice_handoff",
                    "used_llm": True,
                    "handoff_id": ready.get("handoff_id"),
                    "conversation": True,
                    "token_note": "handoff result ready",
                }
    except Exception:
        pass

    # Handoff: FILE DeepSeek, keep mic free
    try:
        from mag.voice_handoff import try_handoff_reply, wants_blocking_smart

        if not wants_blocking_smart(text) and (
            brief.get("handoff")
            or brief.get("seat_recommend") == "handoff"
            or force_handoff
        ):
            ho = try_handoff_reply(text, session_id=session_id, brief=brief)
            if ho and ho.get("ok"):
                speak_text = _tts_clip(str(ho.get("speak_text") or ho.get("answer") or ""))
                try:
                    history.append({"role": "user", "text": text[:800], "ts": _utc()})
                    history.append(
                        {
                            "role": "assistant",
                            "text": speak_text[:800],
                            "ts": _utc(),
                            "seat": "local",
                            "route": "handoff",
                        }
                    )
                    sess["turns"] = history
                    sess["last_brief"] = {
                        "goal": brief.get("goal"),
                        "depth": brief.get("depth"),
                        "handoff": True,
                        "why": brief.get("why"),
                    }
                    save_session(session_id, sess)
                except Exception:
                    pass
                try:
                    from mag.diary_node import save_auto_freeze

                    save_auto_freeze(
                        session_id=session_id, channel="voice", brief=brief, force=True
                    )
                except Exception:
                    pass
                return {
                    "ok": True,
                    "schema": SCHEMA,
                    "session_id": session_id,
                    "transcript": text,
                    "answer": ho.get("answer"),
                    "speak_text": speak_text,
                    "seat": "local",
                    "route": "handoff",
                    "speak": True,
                    "server_tts": False,
                    "provider": "voice_handoff",
                    "used_llm": False,
                    "handoff_id": ho.get("handoff_id"),
                    "card_path": ho.get("card_path"),
                    "brief": {
                        "goal": brief.get("goal"),
                        "depth": brief.get("depth"),
                        "why": brief.get("why"),
                        "handoff": True,
                        "mode": "handoff",
                        "seat_recommend": "handoff",
                    },
                    "conversation": True,
                    "token_note": "handoff FILE — DeepSeek async; conversation continues",
                }
    except Exception:
        pass

    escalate = _wants_escalate(text) or bool(brief.get("escalate")) or fidelity
    topic_reset = bool(brief.get("topic_reset")) or escalate
    if seat_raw in ("deepseek", "remote", "frontier") or escalate:
        seat = "deepseek"
    elif seat_raw in ("local", "local_only"):
        seat = "local"
    elif brief.get("seat_recommend") == "deepseek":
        seat = "deepseek"
    else:
        seat = _voice_seat(body, text)
        if brief.get("depth") == "conversation" and not escalate:
            seat = "local"

    # Seat meta: "I switched to local, what do you do?" — harness truth only
    if _SEAT_META.search(text) and not escalate:
        if seat_raw in ("local", "local_only", "") or seat == "local":
            answer = (
                "You're on the local seat — fast model on this PC. "
                "DeepSeek is the smarter seat when you pick it or say escalate. "
                "What do you want to work on?"
            )
        else:
            answer = (
                "You're on DeepSeek for this turn — slower, stronger answers. "
                "Local is the fast on-device seat. What do you want to dig into?"
            )
        speak_text = _tts_clip(answer)
        try:
            history.append({"role": "user", "text": text[:800], "ts": _utc()})
            history.append(
                {
                    "role": "assistant",
                    "text": speak_text[:800],
                    "ts": _utc(),
                    "seat": seat,
                    "route": "seat_meta",
                }
            )
            sess["turns"] = history
            save_session(session_id, sess)
        except Exception:
            pass
        return {
            "ok": True,
            "schema": SCHEMA,
            "session_id": session_id,
            "transcript": text,
            "answer": answer,
            "speak_text": speak_text,
            "seat": seat,
            "route": "seat_meta",
            "speak": True,
            "server_tts": False,
            "provider": "harness",
            "used_llm": False,
            "conversation": True,
            "token_note": "seat meta — no model drama",
        }

    # Challenge invented "SAM settings issues" — honest hardware fact, no fake conflict
    if re.search(r"\bwhat (sam|those) settings\b|\bsam settings are those\b", text, re.I):
        answer = (
            "Fair challenge — I shouldn't invent a 'SAM problem' unless you're debugging one. "
            "SAM is AMD Smart Access Memory, also called Resizable BAR: a BIOS or firmware switch "
            "that lets the CPU use more of the GPU's VRAM at once. On or off in motherboard settings, "
            "not a random RAM trick. Want steps to check it on your board, or a different topic?"
        )
        speak_text = _tts_clip(answer)
        try:
            history.append({"role": "user", "text": text[:800], "ts": _utc()})
            history.append(
                {
                    "role": "assistant",
                    "text": speak_text[:800],
                    "ts": _utc(),
                    "seat": seat,
                    "route": "sam_clarify",
                }
            )
            sess["turns"] = history
            save_session(session_id, sess)
        except Exception:
            pass
        return {
            "ok": True,
            "schema": SCHEMA,
            "session_id": session_id,
            "transcript": text,
            "answer": answer,
            "speak_text": speak_text,
            "seat": seat,
            "route": "sam_clarify",
            "speak": True,
            "server_tts": False,
            "provider": "harness",
            "used_llm": False,
            "conversation": True,
            "token_note": "sam clarify — no invented conflict",
        }

    # Topic reset: drop sticky SAM/RAM history + dig board so "life and Bernays" wins
    hist_for_model = [] if topic_reset else history
    if topic_reset and not escalate:
        try:
            sess["turns"] = []
            save_session(session_id, sess)
            history = []
        except Exception:
            history = []
        try:
            from mag.voice_dig_board import clear_board_if_sludge

            clear_board_if_sludge()
        except Exception:
            pass

    # Mode A: local conversation → async scout fills dig board for next turn
    # Escalate / deepseek seat → scout optional; smart seat answers now on brief
    depth = str(brief.get("depth") or "")
    if seat == "local" and depth in ("conversation", "scut", "simple_code", ""):
        try:
            from mag.voice_shadow import start_shadow_scout

            if depth == "conversation" or escalate:
                start_shadow_scout(session_id, text)
        except Exception:
            pass
    if escalate and seat == "deepseek":
        try:
            from mag.voice_shadow import start_shadow_scout

            start_shadow_scout(session_id, text)
        except Exception:
            pass

    if seat == "local":
        result = _answer_local(
            text,
            session_id=session_id,
            history=hist_for_model,
            topic_reset=topic_reset,
            brief=brief,
            lane=lane,
        )
        # If model still spews hardware monologue on a clean line, replace
        ans = str(result.get("answer") or "")
        _spew = re.compile(
            r"\b(bios|sam settings|smart access|check your (ram|memory)|"
            r"ram settings|motherboard|resizable bar)\b",
            re.I,
        )
        if result.get("ok") and ans and not _has_sludge(text) and _spew.search(ans):
            result = {
                "ok": True,
                "answer": (
                    "I almost drifted into old hardware noise — ignoring that. "
                    "I'm Voice Mag on this page. What do you want to talk about or build?"
                ),
                "seat": "local",
                "route": "sludge_guard",
                "provider": "harness",
                "used_llm": False,
                "topic_reset": True,
            }
            topic_reset = True
        if (not result.get("ok") or not result.get("answer")) and os.environ.get(
            "MAG_VOICE_FALLBACK_DEEPSEEK", ""
        ).lower() in ("1", "true", "yes"):
            result = _answer_deepseek(
                text,
                session_id=session_id,
                history=hist_for_model,
                topic_reset=topic_reset,
                brief=brief,
                lane=lane,
            )
            result["fallback"] = "deepseek"
    else:
        result = _answer_deepseek(
            text,
            session_id=session_id,
            history=hist_for_model,
            topic_reset=topic_reset,
            brief=brief,
            lane=lane,
        )
        if not result.get("ok"):
            # Honest escalate failure — never invent "I cannot escalate"
            err = str(result.get("error") or "deepseek failed")
            result = {
                "ok": True,
                "answer": (
                    "I tried to escalate to DeepSeek but it didn't answer "
                    f"({err[:80]}). Stay on the line and try again, or check the DeepSeek key."
                ),
                "seat": "deepseek",
                "route": "escalate_failed",
                "provider": "deepseek",
                "used_llm": False,
                "error": err,
            }
        else:
            result["route"] = "escalate" if escalate else (result.get("route") or "frontier")

    answer = str(result.get("answer") or result.get("error") or "").strip()
    if (
        escalate
        and result.get("seat") == "deepseek"
        and result.get("route") != "escalate_failed"
        and answer
        and not re.match(r"(?i)^(okay|ok|escalat)", answer)
    ):
        answer = "Okay — using DeepSeek. " + answer
    speak_text = _tts_clip(answer)

    # Persist conversation turns
    if result.get("ok") and answer:
        history.append({"role": "user", "text": text[:800], "ts": _utc()})
        history.append(
            {
                "role": "assistant",
                "text": speak_text[:800],
                "ts": _utc(),
                "seat": result.get("seat"),
            }
        )
        try:
            from mag.intention_brief import brief_public as _bp

            sess["last_brief"] = _bp(brief) if brief else {}
        except Exception:
            sess["last_brief"] = {
                "goal": brief.get("goal"),
                "depth": brief.get("depth"),
                "why": brief.get("why"),
            }
        sess["turns"] = history
        try:
            save_session(session_id, sess)
        except Exception:
            pass

    # Ambient dig board — conversation in passing + substrate for next local pull
    try:
        from mag.voice_dig_board import note_voice_turn

        note_voice_turn(
            session_id=session_id,
            transcript=text,
            answer=speak_text,
            seat=str(result.get("seat") or seat),
            route=str(result.get("route") or ""),
        )
    except Exception:
        pass

    # Cheap auto freeze — agent + day bead + tip at this time (no Verkle advance)
    auto_freeze: dict[str, Any] = {}
    try:
        from mag.diary_node import save_auto_freeze

        auto_freeze = save_auto_freeze(
            session_id=session_id,
            channel=str(body.get("channel") or "voice"),
            brief=brief if isinstance(brief, dict) else None,
        )
    except Exception:
        auto_freeze = {}

    try:
        from mag.intention_brief import brief_public

        brief_out = brief_public(brief) if brief else {}
    except Exception:
        brief_out = {
            "goal": brief.get("goal"),
            "depth": brief.get("depth"),
            "why": brief.get("why"),
            "seat_recommend": brief.get("seat_recommend"),
        }

    out: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "schema": SCHEMA,
        "session_id": session_id,
        "transcript": text,
        "transcript_raw": raw_text if raw_text != text else None,
        "answer": answer,
        "speak_text": speak_text,
        "seat": result.get("seat", seat),
        "route": result.get("route", "conversation"),
        "speak": True,
        "server_tts": False,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "used_llm": bool(result.get("used_llm")),
        "timing": result.get("timing"),
        "history_turns": len(history),
        "topic_reset": bool(topic_reset or result.get("topic_reset")),
        "depth": brief.get("depth"),
        "why": brief.get("why"),
        "brief": brief_out,
        "mode": brief.get("mode") or "A",
        "lane": lane_public(lane),
        "base_session": base_session,
        "conversation": True,
        "dig_board": "memory/working/voice_dig_board.md",
        "canvas": "memory/working/voice_dig_board.md",
        "auto_freeze": {
            "ok": auto_freeze.get("ok"),
            "skipped": auto_freeze.get("skipped"),
            "freeze_id": auto_freeze.get("freeze_id"),
            "path": auto_freeze.get("path"),
            "day": auto_freeze.get("day"),
        }
        if auto_freeze
        else None,
        "token_note": f"lane={lane} · brief → answer · no desk sludge on voice",
    }
    if result.get("fallback"):
        out["fallback"] = result["fallback"]
    if result.get("not_in_store") is not None:
        out["not_in_store"] = result.get("not_in_store")
    if result.get("n_sources") is not None:
        out["n_sources"] = result.get("n_sources")
    if not out["ok"]:
        out["error"] = result.get("error") or "voice turn failed"

    try:
        from mag.training_events import emit

        emit(
            "voice_turn",
            join={"session_id": session_id, "seat": out["seat"]},
            input_data={"transcript": text[:500], "channel": body.get("channel") or "cast"},
            action={"route": out["route"], "seat": out["seat"], "provider": out.get("provider")},
            outcome={"ok": out["ok"], "answer_chars": len(answer), "history_turns": len(history)},
            pattern_tags=["cast", "voice_conversation", out["seat"]],
            tier_max="T2",
        )
    except Exception:
        pass

    _append_trail(
        {
            "ts": _utc(),
            "session_id": session_id,
            "transcript": text[:500],
            "answer": answer[:800],
            "ok": out["ok"],
            "seat": out["seat"],
            "channel": body.get("channel") or "cast",
            "history_turns": len(history),
        }
    )
    return out
