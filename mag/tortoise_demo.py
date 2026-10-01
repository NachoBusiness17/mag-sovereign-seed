"""tortoise_demo — the GEB MUSICIAN's first voice (2026-09-07).

THE TORTOISE: Gödel Escher Bach as one musician, fleet-made.
  GÖDEL  — the theme is DERIVED FROM THE VERKLE CHAIN's latest leaf hash:
           the record IS the engine, so the record is also the melody.
  ESCHER — a Shepard-tone pad: the staircase that climbs forever.
  BACH   — a true CRAB CANON: theme + retrograde + inversion + retrograde-inversion,
           four voices, symmetrical — the Musical Offering's trick, fleet data.

Picasso-theft pipeline stages (v1): steal STRUCTURE from ~/Desktop/music-ai (the
filter-sweep automation seen in the daft_spectrogram receipt), kabuki-lens each draft.
Studio: numpy stems -> ffmpeg loudnorm master.

CLI: python -m mag.tortoise_demo [--out OUT.wav]
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
OUT = ROOT / "dashboard" / "static" / "sound"
SR = 44100
BPM = 120.0
BEAT = 60.0 / BPM            # quarter note seconds
EIGHTH = BEAT / 2
SCALE = [220.0 * 2 ** (i / 12) for i in (0, 3, 5, 7, 10, 12, 15, 17)]  # A min pent, 2 oct


def chain_theme() -> tuple[list[float], str]:
    """GÖDEL: map the latest chain leaf hash onto the scale — 16 notes."""
    tip = "0" * 16
    if CHAIN.is_file():
        lines = [l for l in CHAIN.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            tip = str(json.loads(lines[-1]).get("leaf_hash", tip))
    h = hashlib.sha256(tip.encode()).hexdigest()
    notes = [SCALE[int(h[i], 16) % len(SCALE)] for i in range(16)]
    return notes, tip[:16]


def voice(freqs: np.ndarray, dur: float, detune=0.0, gain=1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    seg = n // len(freqs) if len(freqs) else n
    for i, f in enumerate(freqs):
        a, b = i * seg, min((i + 1) * seg, n)
        tt = t[a:b]
        tone = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * (f + detune) * tt)
                + 0.15 * np.sin(2 * np.pi * f * 2 * tt))
        env = np.minimum(1.0, np.arange(b - a) / (0.01 * SR)) * np.exp(-(tt - tt[0]) * 1.5)
        out[a:b] += tone * env
    return out * gain


def kick(count: int, dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    step = n // count if count else n
    for i in range(count):
        tt = t[:int(0.18 * SR)]
        f = 110 * np.exp(-tt * 28) + 45
        out[i * step:i * step + len(tt)] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 12)
    return out


def shepard(dur: float) -> np.ndarray:
    """ESCHER: the staircase that climbs forever — octave-spaced glides, Gaussian
    amplitude window across octave position, so the top dissolves into the bottom."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    base = 110.0
    rate = 0.06  # octave climb per second fraction
    for k in range(5):  # 5 octave copies
        f = base * (2 ** k)
        phase = 2 * np.pi * f * t * (1 + rate * t % 1)
        pos = (k + rate * t) / 5.0
        amp = np.exp(-((pos - 0.5) ** 2) / 0.08)
        out += np.sin(phase) * amp
    return out * 0.25


def wav_write(path: Path, data: np.ndarray):
    data = np.tanh(data * 0.9)  # soft-clip guard
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> int:
    notes, tip = chain_theme()
    print(f"GÖDEL: theme from chain tip {tip} -> {len(notes)} notes")
    fnotes = np.array(notes)
    theme = fnotes
    retro = fnotes[::-1]
    inv = 2 * SCALE[0] * SCALE[-1] ** 0 / (fnotes)  # inversion about the first degree
    inv = np.array([SCALE[int(np.argmin(np.abs(SCALE - (SCALE[0] * SCALE[0] / f))))] for f in fnotes])
    retro_inv = inv[::-1]

    bars = 2  # 16 eighths per pass, two passes = 32 eighths
    dur = EIGHTH * 16 * bars
    n = int(dur * SR)
    print(f"BACH: crab canon, four voices, {dur:.1f}s")

    mix = np.zeros(n)
    mix += voice(np.tile(theme, bars), dur, detune=0.15, gain=0.5)
    mix += voice(np.tile(retro, bars), dur, detune=-0.15, gain=0.42)
    mix += voice(np.tile(inv, bars), dur, detune=0.1, gain=0.38)
    mix += voice(np.tile(retro_inv, bars), dur, detune=-0.1, gain=0.34)
    mix[:n] += kick(int(dur / BEAT), dur) * 0.9       # BACH's motorik heart
    mix += shepard(dur) * 0.5                          # ESCHER's staircase

    OUT.mkdir(parents=True, exist_ok=True)
    wav = OUT / "tortoise_crab_canon.wav"
    wav_write(wav, mix)
    print(f"TORTOISE: wrote {wav.name} ({dur:.1f}s, SR {SR})")
    print(f"chain tip: {tip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
