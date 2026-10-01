"""feedback — OUR feedback pipe (replaces the vendor thumbs-up). A 👍/👎 becomes a training
signal in the SOVEREIGN mem weave, not Microsoft telemetry.

Operator (2026-08-11): "delete theirs and put our common tools there" — the feedback gesture feeds
OUR system: attention_ranker.record_feedback (ranking) + training_row.v1 (training) + verkle knot
(durable, content-addressed record). Same gesture, signal lands in OUR memory.

Contract: feedback.v1 · deterministic · $0.
Vocabulary (2026-09-29, gala wave5 attention-channel): ONE vocabulary everywhere, the ranker's
ALLOWED_SIGNALS {useful, wallpaper, pin, mute, acted} (mag/attention_ranker.py:17). Thumbs
spellings (good/bad/up/down/positive/negative/thumbs-up/thumbs-down) are aliases mapped before
the cast: good* -> useful, bad* -> wallpaper. Before this fix the pipe cast good/bad into a
ranker that only accepts the five signals, so EVERY cast was rejected with
{"ok": False, "error": "signal must be one of ..."} while this pipe still reported overall
success (boolean-cosmetic; w4-37 Receipt 6). A cast the ranker now rejects is a contract break:
capture returns ok False and the CLI exits 1.
CLI: python -m mag.feedback useful|wallpaper|pin|mute|acted|good|bad [item_id] [--context "..."]
(also via ghost chat / REST)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from mag.attention_ranker import ALLOWED_SIGNALS, record_feedback

SCHEMA = "feedback.v1"
TRAINING = ROOT / "memory" / "pile" / "training_rows.jsonl"
FEEDBACK_LEDGER = ROOT / "memory" / "runs" / "feedback" / "feedback.jsonl"

# thumbs vocabulary -> the one canonical ranker vocabulary
SIGNAL_ALIASES = {
    "good": "useful",
    "up": "useful",
    "positive": "useful",
    "thumbs-up": "useful",
    "bad": "wallpaper",
    "down": "wallpaper",
    "negative": "wallpaper",
    "thumbs-down": "wallpaper",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_signal(raw: str) -> str:
    """Any accepted spelling -> the one canonical ranker vocabulary.

    ONE definition (2026-09-29 ball attention-ledger): the CLI pipe (capture)
    and the dashboard POST handler (dashboard/rest.py h_attention_feedback) both
    cast through this, so no surface can resurrect the 2026-08 two-vocabulary
    drift (w4-37 Receipt 6) where good/bad casts were silently rejected by the
    ranker while the pipe reported success.
    """
    s = (raw or "").strip().lower()
    return SIGNAL_ALIASES.get(s, s)


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def capture(signal: str, *, item_id: str = "", context: str = "", source: str = "ghost-chat") -> dict[str, Any]:
    """Turn a positive/negative signal into a sovereign training + ranking + verkle record."""
    rank_signal = normalize_signal(signal)
    if rank_signal not in ALLOWED_SIGNALS:
        return {
            "ok": False,
            "schema": SCHEMA,
            "error": f"unknown signal: {signal} (vocabulary: {sorted(ALLOWED_SIGNALS)})",
        }
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "ts": _now(),
                           "signal": rank_signal, "source": source, "item_id": item_id}

    # 1) ranking feedback (attention_ranker pipe). A rejected cast is a contract
    #    break, not a soft-skip: the 2026-08 vocabulary drift silently zeroed
    #    price discovery while this pipe reported success. Failure is loud.
    try:
        r = record_feedback(item_id or f"feedback-{datetime.now(timezone.utc).strftime('%H%M%S')}",
                            rank_signal, source=source)
        out["ranking"] = bool(r.get("ok"))
        if not r.get("ok"):
            out["ok"] = False
            out["ranking_error"] = str(r.get("error"))[:120]
    except Exception as e:
        out["ok"] = False
        out["ranking"] = False
        out["ranking_error"] = str(e)[:80]

    # 2) training_row.v1 (our training data)
    _append_jsonl(TRAINING, {"schema": "training_row.v1", "ts": _now(),
                             "source": "feedback", "signal": rank_signal,
                             "input": context or item_id, "output": rank_signal})
    out["training_written"] = True

    # 3) feedback ledger
    _append_jsonl(FEEDBACK_LEDGER, {"ts": _now(), "signal": rank_signal, "item_id": item_id,
                                    "context": context, "source": source})

    # 4) verkle knot (durable content-addressed record)
    try:
        from mag.verkle_knot import append_verkle_knot
        append_verkle_knot({"session_id": f"feedback:{datetime.now(timezone.utc).strftime('%H%M%S')}",
                            "theme": "behavior",
                            "summary": f"[feedback] {rank_signal} signal from {source} on {item_id or context[:60]}"})
        out["verkle"] = True
    except Exception as e:
        out["verkle_error"] = str(e)[:80]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="feedback",
                                 description="Our feedback pipe: ranker-vocabulary cast -> training + ranking + verkle (not Microsoft).")
    ap.add_argument("signal", nargs="?", default="good")
    ap.add_argument("item_id", nargs="?", default="")
    ap.add_argument("--context", default="")
    ap.add_argument("--source", default="ghost-chat")
    a = ap.parse_args(argv)
    result = capture(a.signal, item_id=a.item_id, context=a.context, source=a.source)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["capture", "main"]
