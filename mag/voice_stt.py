"""Voice STT steal — Whisper-class recognition with isolated capture path.

Origin (honest):
  - OpenAI Whisper / SYSTRAN faster-whisper: strong ASR without training *your* voice
  - Isolation contract: capture with echoCancellation + noiseSuppression (browser)
    then transcribe offline — not Chrome's free-form Web Speech partials

No voice training required. Better models + cleaner audio beat "enroll speaker".

Schema: mag_voice_stt.v1
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_voice_stt.v1"
UPLOAD_DIR = ROOT / "memory" / "agent_uploads" / "voice_stt"
_MODEL = None
_MODEL_NAME = ""


def _model_name() -> str:
    # tiny/base = fast on CPU; small if you have RAM
    return (os.environ.get("MAG_VOICE_WHISPER_MODEL") or "base").strip() or "base"


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def stt_status() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": SCHEMA,
        "faster_whisper": whisper_available(),
        "model": _model_name() if whisper_available() else None,
        "note": (
            "Whisper does not need your voice trained — it generalizes. "
            "Isolation = noise-suppressed capture + offline decode."
        ),
        "steal": {
            "origin": "OpenAI Whisper / SYSTRAN faster-whisper",
            "love": "accuracy without speaker enrollment",
            "grateful": "not locked to Chrome Web Speech or cloud STT throne",
        },
    }


def _get_model():
    global _MODEL, _MODEL_NAME
    name = _model_name()
    if _MODEL is not None and _MODEL_NAME == name:
        return _MODEL
    from faster_whisper import WhisperModel

    # CPU int8 — AMD home box; cuda if ever available
    device = (os.environ.get("MAG_VOICE_WHISPER_DEVICE") or "cpu").strip() or "cpu"
    compute = "int8" if device == "cpu" else "float16"
    _MODEL = WhisperModel(name, device=device, compute_type=compute)
    _MODEL_NAME = name
    return _MODEL


def transcribe_file(path: str | Path, *, language: str = "en") -> dict[str, Any]:
    """Transcribe a wav/webm/ogg file with faster-whisper."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"missing file {path}", "text": ""}
    if not whisper_available():
        return {
            "ok": False,
            "error": "faster-whisper not installed — pip install faster-whisper",
            "text": "",
        }
    t0 = time.monotonic()
    try:
        model = _get_model()
        segments, info = model.transcribe(
            str(p),
            language=language or "en",
            beam_size=5,
            vad_filter=True,  # Silero-style VAD inside whisper path
            vad_parameters=dict(min_silence_duration_ms=400),
        )
        parts = [s.text.strip() for s in segments if s.text and s.text.strip()]
        text = " ".join(parts).strip()
        ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": bool(text),
            "schema": SCHEMA,
            "text": text,
            "language": getattr(info, "language", language),
            "duration_s": getattr(info, "duration", None),
            "elapsed_ms": ms,
            "model": _MODEL_NAME,
            "backend": "faster-whisper",
            "vad_filter": True,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300], "text": "", "backend": "faster-whisper"}


def save_upload(data: bytes, *, suffix: str = ".webm") -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import uuid

    path = UPLOAD_DIR / f"stt-{uuid.uuid4().hex[:12]}{suffix}"
    path.write_bytes(data)
    return path


def _suffix_from_name(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".wav"):
        return ".wav"
    if name.endswith(".ogg"):
        return ".ogg"
    if name.endswith(".mp3"):
        return ".mp3"
    if name.endswith(".m4a"):
        return ".m4a"
    return ".webm"


def handle_stt(
    body: dict[str, Any] | None = None,
    *,
    file_bytes: bytes | None = None,
    filename: str = "",
) -> dict[str, Any]:
    """API helper — base64 audio, path, or raw bytes. No speaker enrollment."""
    body = body or {}
    action = str(body.get("action") or "").strip().lower()
    if action in ("status", "info", ""):
        # status-only when no payload
        has_payload = bool(file_bytes or body.get("data") or body.get("base64") or body.get("path") or body.get("file"))
        if action in ("status", "info") or not has_payload:
            return stt_status()

    raw = file_bytes
    fname = filename or str(body.get("filename") or "clip.webm")
    if raw is None:
        b64 = body.get("data") or body.get("base64") or body.get("audio") or ""
        if isinstance(b64, str) and b64:
            if "," in b64 and b64.strip().startswith("data:"):
                b64 = b64.split(",", 1)[1]
            try:
                raw = base64.b64decode(b64)
            except Exception as exc:
                return {"ok": False, "error": f"bad base64: {exc}", "text": ""}
            if len(raw) > 20 * 1024 * 1024:
                return {"ok": False, "error": "max 20MB audio", "text": ""}

    if raw:
        path = save_upload(raw, suffix=_suffix_from_name(fname))
        out = transcribe_file(path, language=str(body.get("language") or "en"))
        try:
            out["path"] = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            out["path"] = str(path)
        return out

    path = body.get("path") or body.get("file")
    if path:
        return transcribe_file(path, language=str(body.get("language") or "en"))
    return {"ok": False, "error": "path or audio data required", "status": stt_status()}
