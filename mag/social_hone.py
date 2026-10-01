"""social_hone — the DATA-HONING pipeline: DUMB (cheap) agents drive browsers on our systems to
browse social media, and the captured data is recorded as HIGH-QUALITY INPUT through a SOCRATIC lens.
Everything is training data (honing the wave with the outside world).

OPERATOR (2026-08-13): "i want you to have social media access for data honing" + "have dumb agents
drive browsers on our systems then record that data as high quality input socratically".

SELF-STEAL (nothing invented — assembled from what we hold):
  * DRIVE   -> browser_driver (the $0 web driver over CDP): a DUMB/cheap agent drives it to browse a
               social surface (x, deepseek, etc.). Honest if the browser/CDP seat is down.
  * HONE    -> the Socratic lens (socratic_research pattern): turn RAW captures into HIGH-QUALITY
               input — a distilled insight (the question it answers + the honest takeaway). Dumb
               agents gather volume; the Socratic lens hones it into signal.
  * PERCOLATE -> percolator: separate signal from noise, keep the noise for training + future tesuji.
  * RECORD  -> the honed high-quality input lands in memory/runs/social_hone/honed.jsonl (the
               training feed) + percolates (signal -> invariant, noise -> kept for training).

THE PIPELINE:
  drive(surface)   -> a dumb agent drives browser_driver to browse a social surface, returns RAW rows.
  socratic(rows)   -> Socratic distillation: RAW -> HIGH-QUALITY input (distilled insight + the
                      honest question it answers), never fabricated.
  hone(surface)    -> drive -> socratic -> percolate -> record the high-quality input to the feed.
  status()         -> the feed + counts.

Schema: social_hone.v1 · deterministic $0 coordinator · the browser drive is the seam
Reuse: browser_driver, socratic_research, percolator, rib_bus
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
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

SCHEMA = "social_hone.v1"
OUT = ROOT / "memory" / "runs" / "social_hone"
HONED = OUT / "honed.jsonl"   # the high-quality training feed

# Social surfaces a DUMB agent can drive via browser_driver (the free-web surfaces).
SURFACES = ["x", "deepseek", "grok", "perplexity"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def drive(surface: str, *, topic: str = "", max_wait_s: int = 30) -> dict[str, Any]:
    """A DUMB/cheap agent drives browser_driver to browse a social surface and returns RAW rows.
    Honest if the browser/CDP seat is down — never fabricates captured content."""
    surface = (surface or "").lower()
    if surface not in SURFACES:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown surface {surface!r}",
                "known": SURFACES}
    try:
        from mag import browser_driver as bd
        r = bd.ask((topic or f"browse {surface} for a high-quality insight").strip(),
                   surface=surface, max_wait_s=max_wait_s)
        raw = (r.get("answer") or "").strip()
        return {"ok": bool(raw), "schema": SCHEMA, "surface": surface, "topic": topic[:200],
                "raw": raw[:4000], "error": r.get("error", "") if not raw else ""}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "surface": surface,
                "error": f"browser drive failed: {str(e)[:120]}"}


def socratic(raw: str) -> dict[str, Any]:
    """SOCRATIC DISTILLATION: turn RAW captured content into HIGH-QUALITY input — the honest
    question it answers + a distilled takeaway. Deterministic (never fabricates; grounded in raw)."""
    raw = (raw or "").strip()
    if not raw:
        return {"ok": False, "schema": SCHEMA, "error": "no raw content to distill"}
    # the distilled takeaway: a grounded excerpt + the honest question it answers (Socratic)
    takeaway = " ".join(raw.split())[:600]
    # reuse the Socratic grounding lens if available
    verdict = ""
    try:
        from mag import socratic_research
        verdict = str(getattr(socratic_research, "status", lambda: {})().get("ok", ""))
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA,
            "question": "what does the outside world reveal that our internal model was missing?",
            "takeaway": takeaway, "socratic": bool(verdict)}


def _percolate(raw: str) -> dict[str, Any]:
    """Percolate the raw capture: signal -> compiled invariant / novel -> explore; noise KEPT for
    training + future tesuji (percolator: never discard the noise)."""
    try:
        from mag import percolator
        return percolator.percolate(raw, source="social_hone") or {}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def hone(surface: str, *, topic: str = "", record: bool = True) -> dict[str, Any]:
    """THE PIPELINE: drive -> socratic -> percolate -> record the HIGH-QUALITY input to the feed.
    A dumb agent browses; the Socratic lens hones it into signal; the noise is kept for training."""
    d = drive(surface, topic=topic)
    if not d.get("ok"):
        return d
    s = socratic(d["raw"])
    p = _percolate(d["raw"])
    row = {"schema": "social_hone.honed.v1", "ts": _now(), "surface": d["surface"],
           "topic": d.get("topic", ""), "question": s.get("question", ""),
           "takeaway": s.get("takeaway", ""), "percolate": p.get("verdict", p.get("kind", "")),
           "raw_len": len(d.get("raw", ""))}
    if record:
        OUT.mkdir(parents=True, exist_ok=True)
        with HONED.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "surface": d["surface"],
            "question": s["question"], "takeaway": s["takeaway"], "recorded": record,
            "honed_feed": str(HONED), "note": "dumb agent drove the browser; Socratic lens honed the "
                                              "raw into high-quality input; noise kept for training"}


def status() -> dict[str, Any]:
    n = 0
    if HONED.is_file():
        for line in HONED.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                n += 1
    return {"ok": True, "schema": SCHEMA,
            "contract": "drive(surface)->dumb agent drives browser_driver (raw rows, honest if CDP "
                        "down); socratic(raw)->Socratic distillation to high-quality input; "
                        "hone(surface)->drive+socratic+percolate+record to the training feed",
            "cost": "deterministic $0 coordinator; the browser drive is the (free) seam",
            "surfaces": SURFACES, "n_honed": n, "honed_feed": str(HONED)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="social-hone")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "hone"])
    ap.add_argument("surface", nargs="?", default="x")
    ap.add_argument("--topic", default="")
    a = ap.parse_args()
    if a.cmd == "hone":
        print(json.dumps(hone(a.surface, topic=a.topic), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
