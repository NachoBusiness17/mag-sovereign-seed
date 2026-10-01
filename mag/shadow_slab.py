"""shadow_slab — one slab of the 5.3-flash behavioral volume (SHADOW WORK P0).

Operator 2026-09-06: "turn the model on our disk into an environment you traverse...
fanout of 50 agents across whatever the fuck this entire model is." The thought bank
(9,305 reasoning parts, verbatim) IS the model's behavioral volume. 50 slabs, one walker
each; features are deterministic so the 50 slab CSVs tile into one seamless volume.

SHADOW WORK phases: P0 behavioral volume (bank, $0) + weights volume (Qwen GGUF stand-in)
-> P1 volumetric render + seat vision interpretation -> P2 the real 5.3-flash weights
(Rocinante-gated download, 363G free).

CLI:
  python -m mag.shadow_slab carve <n>        # slab n (1..50) -> state/shadow_work/slab_<n>.csv
  python -m mag.shadow_slab stats <n>        # print slab summary
  python -m mag.shadow_slab volume           # aggregate all slabs -> state/shadow_work/volume.json
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "memory" / "thinking" / "app_reasoning.jsonl"
OUT_DIR = ROOT / "state" / "shadow_work"
VOL = OUT_DIR / "volume.json"
N_SLABS = 50
LAW_TERMS = ("standing wave", "tri-state", "falsifier", "cite", "no sacred cows",
             "refeed", "ground", "field", "wall", "tesuji")


def _slab_bounds(n: int) -> tuple[int, int]:
    per = 9305 // N_SLABS  # 186
    start = (n - 1) * per
    end = n * per if n < N_SLABS else 9305
    return start, end


def carve(n: int) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start, end = _slab_bounds(n)
    rows = []
    with BANK.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i < start:
                continue
            if i >= end:
                break
            if not line.strip():
                continue
            try:
                part = json.loads(line)
            except Exception:
                continue
            text = json.dumps(part, ensure_ascii=False) if not isinstance(part, dict) \
                else str(part.get("text") or part.get("data") or part)
            low = text.lower()
            chars = len(text)
            words = text.count(" ") + 1
            law_hits = sum(low.count(t) for t in LAW_TERMS)
            questions = text.count("?")
            digits = sum(c.isdigit() for c in text)
            rows.append({"idx": start + i + 1, "chars": chars, "words": words,
                         "law_hits": law_hits, "questions": questions,
                         "digit_ratio": round(digits / max(chars, 1), 4)})
    out = OUT_DIR / f"slab_{n}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "chars", "words", "law_hits",
                                          "questions", "digit_ratio"])
        w.writeheader()
        w.writerows(rows)
    return {"slab": n, "rows": len(rows), "file": str(out),
            "median_chars": statistics.median([r["chars"] for r in rows]) if rows else 0,
            "law_total": sum(r["law_hits"] for r in rows)}


def stats(n: int) -> dict:
    f = OUT_DIR / f"slab_{n}.csv"
    if not f.is_file():
        return {"error": "slab not carved"}
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    return {"slab": n, "rows": len(rows),
            "median_chars": statistics.median([int(r["chars"]) for r in rows]),
            "law_total": sum(int(r["law_hits"]) for r in rows),
            "questions": sum(int(r["questions"]) for r in rows)}


def volume() -> dict:
    points = []
    for n in range(1, N_SLABS + 1):
        f = OUT_DIR / f"slab_{n}.csv"
        if not f.is_file():
            continue
        for r in csv.DictReader(f.open(encoding="utf-8")):
            points.append({"x": int(r["idx"]), "y": int(r["law_hits"]),
                           "z": int(r["chars"]), "c": int(r["questions"]),
                           "s": float(r["digit_ratio"])})
    data = {"schema": "shadow_work.v1", "n_slabs": N_SLABS, "points": points,
            "axes": {"x": "part index (bank order)", "y": "doctrine-law density",
                     "z": "part size (chars)", "c": "questions asked", "s": "digit ratio"}}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    VOL.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"points": len(points), "file": str(VOL)}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "carve" and len(sys.argv) > 2:
        print(json.dumps(carve(int(sys.argv[2])), ensure_ascii=False))
    elif cmd == "stats" and len(sys.argv) > 2:
        print(json.dumps(stats(int(sys.argv[2])), ensure_ascii=False))
    elif cmd == "volume":
        print(json.dumps(volume(), ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
