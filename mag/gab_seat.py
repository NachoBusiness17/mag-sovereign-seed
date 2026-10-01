"""gab_seat — the HEADLESS gab seat: real-time talk with the sovereign, browser-FREE.

WHY (operator, 2026-08-18): "we have almost all the pieces just costs money" + "the voice
model we had was neat but it also caused 6gb chrome browser hangs."

SELF-STEAL — the loop already exists, split across modules, but the STT capture and the TTS
playback both lived INSIDE Chrome (echoCancellation/noiseSuppression capture + "browser owns
playback"), which is exactly what ballooned Chrome to 6GB. This seat reuses the dialogue
wholesale and replaces ONLY the two browser-bound parts with local ones:

  - HEAR   -> sounddevice local mic capture -> memory/agent_uploads/gab_seat/<ts>.wav
              (no Chrome, no Web Speech, no CDP)
  - STT    -> voice_stt.transcribe_file  (faster-whisper, local, CPU int8)
  - THINK  -> voice_turn.handle_voice_turn  (local Ollama first, DeepSeek only on heavy intent)
  - REMEMBER -> resident-actor continuity: self_recurse + mem_lands grounded context injected,
              so the gab is a CONTINUOUS self (the metal-fish, the Hall) not a cold model/turn.
  - SPEAK  -> tts.speak  (pyttsx3 local; MAG_TTS=1)

Deterministic + $0 for the resident gab; the frontier brain (DeepSeek) is the only part that
bills, and only when the transcript is heavy. RIB-debuggable: gab_turn() is the fully-testable
deterministic core; capture_mic() needs a mic at runtime (clearly separated + flagged).

Schema: gab_seat.v1 · reuse: voice_stt, voice_turn, tts, self_recurse, mem_lands, seat_steer
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "gab_seat.v1"
CAPTURE_DIR = ROOT / "memory" / "agent_uploads" / "gab_seat"
TRAIL_PATH = ROOT / "memory" / "runs" / "gab_seat.jsonl"
SAMPLE_RATE = 16000  # whisper-native
GAB_MODE = os.environ.get("GAB_MODE", "resident")  # resident (local-first) | frontier


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_trail(row: dict[str, Any]) -> None:
    try:
        TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRAIL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# HEAR — local mic capture (no browser). Opt-in at runtime; needs sounddevice. #
# --------------------------------------------------------------------------- #
def capture_mic(*, duration: float = 5.0, sample_rate: int = SAMPLE_RATE) -> dict[str, Any]:
    """Record `duration` seconds from the local mic to a WAV, headless.

    Replaces the browser capture path (the 6GB-hang culprit). Uses sounddevice if
    installed; returns a clear error otherwise. Deterministic given a static mic.
    """
    try:
        import sounddevice as sd
        import soundfile as sf
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"sounddevice/soundfile not installed: {e}",
                "hint": "pip install sounddevice soundfile"}
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / f"gab_{int(datetime.now().timestamp() * 1000)}.wav"
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1,
                       dtype="float32")
        sd.wait()
        sf.write(str(path), audio, sample_rate)
        return {"ok": True, "path": str(path), "duration_s": duration,
                "sample_rate": sample_rate, "bytes": path.stat().st_size,
                "note": "captured headless — no browser, no Chrome, no webview"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300], "path": str(path)}


# --------------------------------------------------------------------------- #
# REMEMBER — resident-actor continuity (self_recurse + mem_lands), grounded.  #
# --------------------------------------------------------------------------- #
def resident_context(mode: str = "dm") -> str:
    """Build a SHORT grounded resident-actor preamble so the gab is continuous, not a
    cold model every turn. Pulls self_recurse recall (the recursive self) + a mem_lands
    grounded read. All try/except — continuity is a bonus, never a blocker."""
    parts: list[str] = []
    try:
        from mag import self_recurse
        r = self_recurse.self_recall(mode=mode,
                                     goal="keep the shared story and the operator's thread")
        if isinstance(r, dict):
            desc = str(r.get("self_description") or r.get("mode_voice") or "").strip()
            if desc:
                parts.append("I (the resident self): " + desc[:400])
    except Exception:  # noqa: BLE001
        pass
    try:
        from mag import mem_lands
        rec = mem_lands.read("the shared story and the operator's most recent intent")
        rows = (rec or {}).get("selected") or []
        lines = []
        for r in rows[:3]:
            t = (r.get("title") or r.get("excerpt") or "")
            if t:
                lines.append(str(t).replace("\n", " ")[:160])
        if lines:
            parts.append("Grounded thread I remember: " + " | ".join(lines))
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# THINK — the dialogue, reused from voice_turn (local-first, deepseek escalate) #
# --------------------------------------------------------------------------- #
def gab_turn(text: str, *, session_id: str = "", mode: str | None = None) -> dict[str, Any]:
    """THE DETERMINISTIC CORE (fully testable, no hardware). Given a spoken line,
    produce the resident actor's answer + speak_text, grounded in continuity.

    Reuses voice_turn.handle_voice_turn wholesale (its lane/history/escalation logic),
    with a resident-actor brief injected so the gab remembers the shared story."""
    mode = mode or GAB_MODE
    text = (text or "").strip()
    if not text:
        return {"ok": False, "schema": SCHEMA, "error": "empty transcript"}
    try:
        from mag.voice_turn import handle_voice_turn
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": f"voice_turn unavailable: {e}"}

    brief = None
    if mode in ("resident", "dm"):
        ctx = resident_context(mode="dm")
        if ctx:
            brief = {"goal": "resident-actor gab: keep the shared story + the operator's thread "
                             "alive; be warm, brief, continuous.",
                     "context": ctx}
    body: dict[str, Any] = {"text": text, "session_id": session_id, "lane": "voice"}
    if brief:
        body["brief"] = brief

    out = handle_voice_turn(body)
    if not isinstance(out, dict):
        out = {"ok": False, "error": "voice_turn returned non-dict"}
    out["schema"] = SCHEMA
    out["mode"] = mode
    _append_trail({"ts": _now(), "transcript": text, "mode": mode,
                   "answer": (out.get("answer") or "")[:400],
                   "seat": out.get("seat"), "route": out.get("route")})
    return out


# --------------------------------------------------------------------------- #
# SPEAK — local playback (pyttsx3), no browser. Default-off, flip MAG_TTS=1.    #
# --------------------------------------------------------------------------- #
def speak(answer: str, *, force: bool = False, async_: bool = False) -> bool:
    try:
        from mag import tts
        if async_:
            tts.speak_async(answer, force=force)
            return True
        return bool(tts.speak(answer, force=force))
    except Exception as e:  # noqa: BLE001
        _append_trail({"ts": _now(), "event": "speak_error", "error": str(e)[:200]})
        return False


# --------------------------------------------------------------------------- #
# ONE FULL HEADLESS TURN + THE LOOP                                            #
# --------------------------------------------------------------------------- #
def gab_once(*, duration: float = 5.0, mode: str | None = None,
             session_id: str = "") -> dict[str, Any]:
    """Capture -> transcribe -> think -> speak, all headless (no browser).
    Returns the full turn. Runtime-only for the capture part."""
    mode = mode or GAB_MODE
    cap = capture_mic(duration=duration)
    if not cap.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": cap.get("error"),
                "hint": cap.get("hint"), "step": "capture"}
    try:
        from mag.voice_stt import transcribe_file
        stt = transcribe_file(cap["path"], language="en")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200], "step": "stt"}
    if not stt.get("ok") or not stt.get("text"):
        return {"ok": False, "schema": SCHEMA, "error": stt.get("error") or "no speech",
                "step": "stt", "text": ""}
    turn = gab_turn(stt["text"], session_id=session_id, mode=mode)
    speak_text = str(turn.get("speak_text") or turn.get("answer") or "")
    spoke = speak(speak_text) if speak_text else False
    turn["spoke"] = spoke
    turn["capture"] = cap
    turn["stt"] = {"text": stt.get("text"), "elapsed_ms": stt.get("elapsed_ms")}
    return turn


def gab_loop(*, duration: float = 5.0, mode: str | None = None,
             session_id: str = "") -> None:
    """Continuous headless gab. Ctrl-C to stop. One turn per capture window."""
    mode = mode or GAB_MODE
    print(f"[gab_seat] headless loop — mode={mode} (no browser). Ctrl-C to stop.")
    try:
        while True:
            turn = gab_once(duration=duration, mode=mode, session_id=session_id)
            print(f"[you] {turn.get('stt', {}).get('text', '')}")
            print(f"[{turn.get('seat', '?')}] {turn.get('answer', turn.get('error', ''))}")
            if not turn.get("ok"):
                print(f"[gab_seat] {turn.get('error')} — {turn.get('hint', '')}")
    except KeyboardInterrupt:
        print("\n[gab_seat] stopped.")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="gab-seat")
    ap.add_argument("cmd", nargs="?", default="once",
                    choices=["once", "loop", "context", "status"])
    ap.add_argument("--text", default="", help="text to turn (skip capture)")
    ap.add_argument("--mode", default=None, help="resident | frontier")
    ap.add_argument("--duration", type=float, default=5.0)
    ap.add_argument("--session", default="")
    a = ap.parse_args()

    if a.cmd == "status":
        try:
            from mag.voice_stt import whisper_available, stt_status
            print(json.dumps({"whisper": whisper_available(),
                              "stt": stt_status(),
                              "sounddevice": _import_ok("sounddevice"),
                              "tts_enabled": os.environ.get("MAG_TTS", "0") == "1",
                              "mode": a.mode or GAB_MODE}, indent=2, default=str))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"error": str(e)}, indent=2))
    elif a.cmd == "context":
        print(resident_context(mode="dm"))
    elif a.text.strip():
        print(json.dumps(gab_turn(a.text, session_id=a.session, mode=a.mode),
                         indent=2, default=str))
    elif a.cmd == "loop":
        gab_loop(duration=a.duration, mode=a.mode, session_id=a.session)
    else:
        print(json.dumps(gab_once(duration=a.duration, mode=a.mode, session_id=a.session),
                         indent=2, default=str))


def _import_ok(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:  # noqa: BLE001
        return False
