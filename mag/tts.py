"""Text-to-speech for Mag (Windows-first).

**Default is OFF.** Browser Mag Voice owns playback (pause/skip/scrub).
Server-side TTS was spawning PowerShell SAPI on every `ask()`, stuffing full
markdown essays into `-Command`, timing out at 60s, and crashing the feel.

Enable only when you want the *PC* to speak without a browser:
  MAG_TTS=1
  MAG_TTS_RATE=220
  MAG_TTS_MAX_CHARS=280

Backend chain (first available wins), only if enabled:
  1. pyttsx3 (if installed)
  2. PowerShell SAPI via **temp .ps1 file** (never giant -Command lines)
  3. no-op + log
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from config import ROOT

LOG = ROOT / "logs" / "tts.log"
_SPEAK_LOCK = threading.Lock()
_ACTIVE_PROC: subprocess.Popen | None = None
_ACTIVE_LOCK = threading.Lock()


def _enabled() -> bool:
    # Default OFF — browser voice player is primary; PowerShell was a crash magnet.
    v = os.environ.get("MAG_TTS", "0").strip().lower()
    return v in ("1", "on", "true", "yes")


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _clip(text: str) -> str:
    spoken = " ".join((text or "").strip().split())
    # Strip markdown noise that sounds terrible and bloats SAPI
    for ch in ("#", "*", "`", "_"):
        spoken = spoken.replace(ch, "")
    max_chars = int(os.environ.get("MAG_TTS_MAX_CHARS", "280") or "280")
    if len(spoken) > max_chars:
        cut = spoken[: max(0, max_chars - 1)]
        for sep in (". ", "! ", "? "):
            i = cut.rfind(sep)
            if i >= 60:
                return cut[: i + 1].strip()
        spoken = cut.rstrip() + "…"
    return spoken


def _backend_pyttsx3(text: str, rate: int) -> bool:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        _log(f"pyttsx3 failed: {e}")
        return False


def _kill_active() -> None:
    global _ACTIVE_PROC
    with _ACTIVE_LOCK:
        proc = _ACTIVE_PROC
        _ACTIVE_PROC = None
    if proc is None:
        return
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=2)
    except Exception:
        pass


def _backend_powershell(text: str, rate: int) -> bool:
    """Windows SAPI via temp .ps1 — avoids command-line length limits and hangs."""
    if sys.platform != "win32":
        return False
    # B2-352 2026-09-26: bare "powershell" is not on PATH in every launch
    # context (disease class sig run_shell:e566037def80 "[Errno 2] ... powershell");
    # the generic except arm swallowed it into a logged False, voice silently
    # dead on scrubbed-PATH seats. Resolve the full path; System32 fallback
    # when PATH lookup misses (pattern mag/process_reaper.py:82-90).
    ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not ps_exe and sys.platform == "win32":
        ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not ps_exe:
        _log("powershell SAPI skipped: no powershell on PATH or System32")
        return False
    # Map WPM-ish rate → SAPI -10..10
    sapi_rate = max(-10, min(10, int(round((rate - 150) / 12))))
    # Escape for single-quoted PowerShell string
    safe = text.replace("'", "''")
    ps_body = (
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        f"$s.Rate = {sapi_rate}\n"
        f"$s.Speak('{safe}')\n"
    )
    timeout_s = int(os.environ.get("MAG_TTS_TIMEOUT_S", "20") or "20")
    path: str | None = None
    try:
        fd, path = tempfile.mkstemp(prefix="mag_tts_", suffix=".ps1")
        os.close(fd)
        Path(path).write_text(ps_body, encoding="utf-8")
        # -File avoids stuffing the whole essay into process args
        proc = subprocess.Popen(
            [
                ps_exe,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with _ACTIVE_LOCK:
            global _ACTIVE_PROC
            _ACTIVE_PROC = proc
        try:
            _stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _log(f"powershell SAPI timeout after {timeout_s}s — killing")
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.communicate(timeout=2)
            except Exception:
                pass
            return False
        finally:
            with _ACTIVE_LOCK:
                if _ACTIVE_PROC is proc:
                    _ACTIVE_PROC = None
        if proc.returncode == 0:
            return True
        err = (stderr or b"").decode("utf-8", errors="replace")[:200]
        _log(f"powershell SAPI rc={proc.returncode}: {err}")
        return False
    except Exception as e:
        _log(f"powershell SAPI error: {e}")
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except Exception:
                pass


def speak(text: str, *, force: bool = False) -> bool:
    """Speak `text` out loud on the PC. Returns True if audio was produced.

    Default-off unless MAG_TTS=1. `force=True` bypasses the env gate (CLI only).
    """
    if not text or not text.strip():
        return False
    if not force and not _enabled():
        return False

    spoken = _clip(text)
    if not spoken:
        return False

    rate = int(os.environ.get("MAG_TTS_RATE", "220") or "220")

    # Serialize — concurrent PowerShell SAPI was a crash source
    if not _SPEAK_LOCK.acquire(blocking=False):
        _log("tts busy — skip overlapping speak")
        return False
    try:
        _kill_active()
        if _backend_pyttsx3(spoken, rate):
            return True
        if _backend_powershell(spoken, rate):
            return True
        _log(f"no TTS backend available; would speak: {spoken[:200]}")
        return False
    finally:
        _SPEAK_LOCK.release()


def speak_async(text: str, *, force: bool = False) -> None:
    """Speak in a background thread so the caller never blocks."""
    if not force and not _enabled():
        return
    import threading

    def _run() -> None:
        try:
            speak(text, force=force)
        except Exception as e:
            _log(f"async speak error: {e}")

    threading.Thread(target=_run, name="mag-tts", daemon=True).start()


def stop() -> None:
    """Hard-stop any in-flight server TTS (PowerShell/SAPI)."""
    _kill_active()


if __name__ == "__main__":
    # CLI: python -m mag.tts "hello from Mag"
    msg = " ".join(sys.argv[1:]) or "Mag text to speech is online."
    ok = speak(msg, force=True)
    print(f"tts ok={ok} backend={'audio' if ok else 'none'} enabled={_enabled()}")
