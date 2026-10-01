"""space_ear — the desk's ears for X Spaces: capture + live transcription (v0, 2026-09-10).

Operator: "could you listen to the podcast live on x to transcript it? it would be the
first time you'd hear my voice." Pipeline (stolen from the wild: twspace-dl + faster-whisper):

  1. geturl: twspace_dl Space API -> live HLS playlist URL (needs cookies.txt, Netscape
     format, from the operator's logged-in X session — contains auth_token; file stays
     local, never echoed).
  2. listen: ffmpeg segments the live playlist into 60s chunks -> faster-whisper
     (small/int8, CPU) transcribes each new chunk -> transcript lines append to
     memory/runs/space_ear/<stamp>_transcript.md with ~1-2 min lag.
  3. transcribe: one-shot STT of a finished audio file (phone-recording fallback).

CLI:
  python -m mag.space_ear listen --url <space-url> [--cookies configs/x_cookies.txt] [--label L]
  python -m mag.space_ear transcribe <audio-file>
  python -m mag.space_ear geturl --url <space-url> [--cookies ...]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EAR_DIR = ROOT / "memory" / "runs" / "space_ear"
COOKIES = ROOT / "configs" / "x_cookies.txt"
FFMPEG = "ffmpeg"  # winget Gyan.FFmpeg build is on PATH
WHISPER_MODEL = "small"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def geturl(url: str, cookies: Path) -> str:
    """Resolve a Space URL to its live HLS playlist via twspace_dl (cookies required)."""
    out = EAR_DIR / f"playlist_{_ts()}.txt"
    EAR_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "twspace_dl", "-i", url, "-c", str(cookies),
         "--write-url", str(out), "-s"],
        capture_output=True, text=True, timeout=120)
    if not out.is_file():
        raise SystemExit(f"playlist resolution failed: {(proc.stderr or proc.stdout)[-300:]}")
    return out.read_text(encoding="utf-8").strip().splitlines()[0]


def _whisper():
    from faster_whisper import WhisperModel

    return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


def transcribe(audio: Path, transcript_fh) -> str:
    model = _whisper()
    segments, _info = model.transcribe(str(audio), beam_size=2, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments)
    if text:
        transcript_fh.write(f"[{_now()}] {text}\n")
        transcript_fh.flush()
    return text


def listen(url: str, cookies: Path, label: str = "") -> None:
    """Live loop: resolve playlist -> ffmpeg 60s chunks -> whisper each new chunk."""
    EAR_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _ts()
    run_dir = EAR_DIR / f"live_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    playlist = geturl(url, cookies)
    print("playlist resolved:", playlist[:80])
    seg = subprocess.Popen(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-i", playlist,
         "-f", "segment", "-segment_time", "60", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(run_dir / "chunk_%04d.wav")])
    transcript_path = run_dir / "transcript.md"
    transcript_path.write_text(
        f"# SPACE TRANSCRIPT — {label or url}\n\n*started {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
        f"whisper {WHISPER_MODEL}/int8 · ~60s lag*\n\n", encoding="utf-8")
    print(f"EAR LIVE — transcript: {transcript_path}")
    seen: set[str] = set()
    model = _whisper()
    try:
        while seg.poll() is None:
            time.sleep(20)
            for chunk in sorted(run_dir.glob("chunk_*.wav")):
                if chunk.name in seen:
                    continue
                # only transcribe chunks ffmpeg has likely closed (60s segments; 70s guard)
                if time.time() - chunk.stat().st_mtime < 70:
                    continue
                seen.add(chunk.name)
                with transcript_path.open("a", encoding="utf-8") as fh:
                    line = transcribe(chunk, fh)
                    print(f"[{_now()}] {line[:100]}")
    except KeyboardInterrupt:
        pass
    finally:
        seg.terminate()
        print("ear stopped — transcript:", transcript_path)


def transcribe_file(path: Path) -> None:
    out = path.with_suffix(".transcript.md")
    with out.open("w", encoding="utf-8") as fh:
        fh.write(f"# TRANSCRIPT — {path.name}\n\n")
        text = transcribe(path, fh)
    print(json.dumps({"ok": True, "transcript": str(out), "chars": len(text)}))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.space_ear")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("listen")
    l.add_argument("--url", required=True)
    l.add_argument("--cookies", default=str(COOKIES))
    l.add_argument("--label", default="")
    t = sub.add_parser("transcribe")
    t.add_argument("audio", type=Path)
    g = sub.add_parser("geturl")
    g.add_argument("--url", required=True)
    g.add_argument("--cookies", default=str(COOKIES))
    args = ap.parse_args(argv)
    if args.cmd == "listen":
        listen(args.url, Path(args.cookies), args.label)
    elif args.cmd == "transcribe":
        transcribe_file(args.audio)
    elif args.cmd == "geturl":
        print(geturl(args.url, Path(args.cookies)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
