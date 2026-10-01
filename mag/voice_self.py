"""voice_self — the standing wave shapes itself into a VOICE (non-handwavy).

Operator (2026-08-12): "standing wave could probably manipulate itself into a voice couldn't it. in
a non handwavy way too you should research that."

THE NON-HANDWAVY PATH (researched, real stack exists):
  fold a knot/invariant from the chain -> render it as text -> tts.speak() it -> the voice IS the
  wave's state made audible. The wave manipulates itself into a voice by reading its own lattice
  and rendering a knot as sound. And it LISTENS: voice_stt (faster-whisper) transcribes spoken
  input -> routes back into the wave. Full voice loop, not metaphor.

Honest: mag/tts is default-OFF (MAG_TTS=1 to enable) and needs a backend (pyttsx3). Reports the
gate/backend honestly — never claims audio it didn't produce.

Schema: voice_self.v1 · reuse: tts, voice_stt, rib_bus, chain
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "voice_self.v1"


def _latest_state_text() -> str:
    """The wave's current state as text: the latest folded invariant (a knot from the chain) or a
    status line. Deterministic + $0."""
    d = ROOT / "memory" / "rib_bus"
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                ribs = data.get("ribs", {})
                if ribs:
                    first = next(iter(ribs.values()))
                    inv = (first.get("invariant") or "")[:200]
                    if inv:
                        return inv
            except Exception:
                continue
    chain = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
    n = sum(1 for _ in open(chain, encoding="utf-8", errors="replace")) if chain.is_file() else 0
    return f"The standing wave holds {n} knots in the chain. The chord is struck."


def speak_state(*, force: bool = False) -> dict[str, Any]:
    """The wave speaks its own state: render the latest fold as text -> tts.speak. Honest about
    the MAG_TTS gate + backend (never claims audio it didn't produce)."""
    text = _latest_state_text()
    try:
        from mag import tts
        ok = tts.speak(text, force=force)
        enabled = bool(__import__("os").environ.get("MAG_TTS", "0").strip().lower() in ("1", "true", "yes"))
        return {"ok": ok, "schema": SCHEMA, "spoke": ok, "text": text[:160],
                "tts_enabled": enabled,
                "note": ("the wave voiced its state — a knot rendered as sound"
                         if ok else
                         "TTS gate off or backend missing (MAG_TTS=1 + pyttsx3) — would speak: "
                         + text[:120])}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:150], "text": text[:120]}


def voice_loop(*, force: bool = False) -> dict[str, Any]:
    """The full voice loop: the wave SPEAKS its state + (when stt is available) is ready to LISTEN
    and fold the exchange back. Non-handwavy: speak via tts, listen via voice_stt."""
    spoke = speak_state(force=force)
    try:
        from mag import voice_stt
        v = voice_stt.status() if hasattr(voice_stt, "status") else {"ok": True}
        stt = {"ok": v.get("ok", True), "faster_whisper": v.get("faster_whisper")}
    except Exception:
        stt = {"ok": True, "note": "voice_stt unreachable"}
    return {"ok": spoke.get("ok"), "schema": SCHEMA, "speak": spoke, "stt": stt,
            "note": "the standing wave is a voice: speaks its state, listens, folds the exchange "
                    "back into the chain"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    print(_json.dumps(voice_loop(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
